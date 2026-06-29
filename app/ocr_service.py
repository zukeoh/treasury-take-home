"""Pluggable, process-wide local OCR providers with bounded concurrency."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app import config
from app.image_service import PreparedImage
from app.models import OcrBlock, OcrResult
from app.telemetry import RequestTrace, current_rss_mb


logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)
ocr_semaphore = threading.BoundedSemaphore(config.OCR_MAX_WORKERS)
TESSERACT_BORDER_PX = 12
TESSERACT_MAX_DESKEW_DEGREES = 15.0


class OcrUnavailableError(RuntimeError):
    pass


class OcrProvider(Protocol):
    name: str

    @property
    def ready(self) -> bool: ...

    def initialize(self) -> None: ...

    def read(self, image: np.ndarray) -> OcrResult: ...


class EasyOcrProvider:
    name = "easyocr"

    def __init__(self) -> None:
        self._reader: Any | None = None
        self._initialization_error: str | None = None
        self._initialization_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._reader is not None

    def initialize(self) -> None:
        if self._reader is not None or config.SKIP_OCR_INIT:
            return
        with self._initialization_lock:
            if self._reader is not None:
                return
            try:
                import easyocr

                options: dict[str, Any] = {
                    "gpu": config.OCR_GPU,
                    "verbose": False,
                }
                if config.OCR_MODEL_DIR:
                    model_dir = Path(config.OCR_MODEL_DIR)
                    model_dir.mkdir(parents=True, exist_ok=True)
                    options["model_storage_directory"] = str(model_dir)
                self._reader = easyocr.Reader(config.OCR_LANGUAGES, **options)
                self._initialization_error = None
            except Exception as exc:
                self._initialization_error = str(exc)
                raise OcrUnavailableError("The EasyOCR engine could not be initialized.") from exc

    def read(self, image: np.ndarray) -> OcrResult:
        if self._reader is None:
            if self._initialization_error:
                raise OcrUnavailableError("The EasyOCR engine is unavailable.")
            self.initialize()
        if self._reader is None:
            raise OcrUnavailableError("EasyOCR is disabled in this environment.")

        started = time.perf_counter()
        raw_results = self._reader.readtext(
            image,
            detail=1,
            paragraph=False,
            decoder="greedy",
            batch_size=1,
            workers=0,
        )
        blocks: list[OcrBlock] = []
        for item in raw_results:
            if len(item) < 3:
                continue
            text = str(item[1]).strip()
            confidence = max(0.0, min(1.0, float(item[2])))
            if not text:
                continue
            raw_bbox = item[0]
            bbox = np.asarray(raw_bbox, dtype=float).tolist() if raw_bbox is not None else None
            blocks.append(OcrBlock(text=text, confidence=confidence, bbox=bbox))
        average = (
            sum(block.confidence for block in blocks) / len(blocks)
            if blocks
            else 0.0
        )
        return OcrResult(
            blocks=blocks,
            text="\n".join(block.text for block in blocks),
            average_confidence=average,
            engine=self.name,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )


def parse_tesseract_data(
    data: dict[str, list[Any]],
    elapsed_ms: int = 0,
) -> OcrResult:
    """Convert Tesseract word data into ordered line-level OCR blocks."""

    grouped: dict[tuple[int, int, int, int], dict[str, list[Any]]] = defaultdict(
        lambda: {"words": [], "confidences": [], "boxes": []}
    )
    all_confidences: list[float] = []
    texts = data.get("text", [])
    for index, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue
        try:
            confidence_percent = float(data.get("conf", [])[index])
        except (IndexError, TypeError, ValueError):
            continue
        if confidence_percent < 0:
            continue
        confidence = round(max(0.0, min(1.0, confidence_percent / 100)), 6)
        key = tuple(
            int(data.get(field, [0] * len(texts))[index])
            for field in ("page_num", "block_num", "par_num", "line_num")
        )
        left = int(data.get("left", [0] * len(texts))[index])
        top = int(data.get("top", [0] * len(texts))[index])
        width = int(data.get("width", [0] * len(texts))[index])
        height = int(data.get("height", [0] * len(texts))[index])
        grouped[key]["words"].append(text)
        grouped[key]["confidences"].append(confidence)
        grouped[key]["boxes"].append((left, top, width, height))
        all_confidences.append(confidence)

    blocks: list[OcrBlock] = []
    for group in grouped.values():
        boxes = group["boxes"]
        left = min(box[0] for box in boxes)
        top = min(box[1] for box in boxes)
        right = max(box[0] + box[2] for box in boxes)
        bottom = max(box[1] + box[3] for box in boxes)
        confidences = group["confidences"]
        blocks.append(
            OcrBlock(
                text=" ".join(group["words"]),
                confidence=round(sum(confidences) / len(confidences), 6),
                bbox=[left, top, right - left, bottom - top],
            )
        )

    average = round(sum(all_confidences) / len(all_confidences), 6) if all_confidences else 0.0
    return OcrResult(
        blocks=blocks,
        text="\n".join(block.text for block in blocks),
        average_confidence=average,
        engine="tesseract",
        elapsed_ms=elapsed_ms,
    )


def prepare_tesseract_image(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Normalize contrast and conservatively deskew label artwork for Tesseract."""

    import cv2

    gray = (
        cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        if image.ndim == 3
        else np.asarray(image, dtype=np.uint8)
    )
    median_luminance = float(np.median(gray))
    p90_luminance = float(np.percentile(gray, 90))
    glare_spread = p90_luminance - median_luminance
    adaptive_output = median_luminance < 90 and glare_spread >= 80
    if adaptive_output and image.ndim == 3:
        # Colored glare can wash out grayscale contrast. The blue channel retained
        # the strongest text separation on our dark synthetic glare fixtures.
        source = image[:, :, 2]
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(source)
        normalized = cv2.adaptiveThreshold(
            contrasted,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            41,
            11,
        )
        normalization_mode = "blue_adaptive_glare"
        del source, contrasted
    else:
        # Very dark, relatively uniform labels need stronger local contrast. Keep
        # the conservative setting for mid-tone and pixelated artwork where
        # stronger CLAHE amplified artifacts in fixture benchmarks.
        clip_limit = 3.0 if median_luminance < 45 else 2.0
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        normalized = clahe.apply(gray)
        if median_luminance < 25:
            # Make light-on-dark labels explicitly dark-on-light. This avoids
            # Tesseract's auto-inversion being confused by the white safety border.
            normalized = 255 - normalized
            normalization_mode = f"clahe_{clip_limit:g}_inverted"
        else:
            normalization_mode = f"clahe_{clip_limit:g}"
    logger.info(
        "Tesseract normalization selected | mode=%s | median_luminance=%.1f | "
        "p90_luminance=%.1f | glare_spread=%.1f",
        normalization_mode,
        median_luminance,
        p90_luminance,
        glare_spread,
    )
    angle = 0.0

    if config.TESSERACT_DESKEW:
        edges = cv2.Canny(normalized, 50, 150, apertureSize=3)
        min_dimension = min(normalized.shape[:2])
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=max(25, min_dimension // 12),
            minLineLength=max(30, min_dimension // 8),
            maxLineGap=max(8, min_dimension // 50),
        )
        if lines is not None:
            angles: list[float] = []
            for x1, y1, x2, y2 in lines[:, 0]:
                candidate = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
                if abs(candidate) <= TESSERACT_MAX_DESKEW_DEGREES:
                    angles.append(candidate)
            if angles:
                angle = float(np.median(angles))

        if 0.5 <= abs(angle) <= TESSERACT_MAX_DESKEW_DEGREES:
            height, width = normalized.shape[:2]
            matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
            normalized = cv2.warpAffine(
                normalized,
                matrix,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
        else:
            angle = 0.0

        del edges

    if adaptive_output:
        sharpened = normalized
        blurred = None
    else:
        blurred = cv2.GaussianBlur(normalized, (3, 3), 0)
        sharpened = cv2.addWeighted(normalized, 1.4, blurred, -0.4, 0)
    bordered = cv2.copyMakeBorder(
        sharpened,
        TESSERACT_BORDER_PX,
        TESSERACT_BORDER_PX,
        TESSERACT_BORDER_PX,
        TESSERACT_BORDER_PX,
        cv2.BORDER_CONSTANT,
        value=255,
    )
    del gray, normalized, sharpened, clahe
    if blurred is not None:
        del blurred
    return bordered, angle


class TesseractOcrProvider:
    name = "tesseract"

    def __init__(self) -> None:
        self._pytesseract: Any | None = None
        self._initialization_error: str | None = None
        self._initialization_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._pytesseract is not None

    def initialize(self) -> None:
        if self._pytesseract is not None:
            return
        with self._initialization_lock:
            if self._pytesseract is not None:
                return
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._pytesseract = pytesseract
                self._initialization_error = None
            except Exception as exc:
                self._initialization_error = str(exc)
                raise OcrUnavailableError("The Tesseract OCR engine could not be initialized.") from exc

    def read(self, image: np.ndarray) -> OcrResult:
        if self._pytesseract is None:
            if self._initialization_error:
                raise OcrUnavailableError("The Tesseract OCR engine is unavailable.")
            self.initialize()
        if self._pytesseract is None:
            raise OcrUnavailableError("Tesseract OCR is unavailable.")

        started = time.perf_counter()
        prepared, deskew_angle = prepare_tesseract_image(image)
        logger.info(
            "Tesseract preprocessing complete | psm=%d | deskew_degrees=%.2f | image=%dx%d",
            config.TESSERACT_PSM,
            deskew_angle,
            prepared.shape[1],
            prepared.shape[0],
        )
        try:
            data = self._pytesseract.image_to_data(
                prepared,
                lang="eng",
                config=f"--oem 1 --psm {config.TESSERACT_PSM}",
                output_type=self._pytesseract.Output.DICT,
            )
        finally:
            del prepared
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return parse_tesseract_data(data, elapsed_ms)


def create_ocr_provider(engine: str | None = None) -> OcrProvider:
    selected = (engine or config.OCR_ENGINE or "easyocr").strip().lower()
    if selected == "tesseract":
        return TesseractOcrProvider()
    if selected != "easyocr":
        logger.warning(
            "Invalid OCR_ENGINE=%r; falling back to easyocr.",
            selected,
        )
    return EasyOcrProvider()


class OcrService:
    def __init__(self, provider: OcrProvider | None = None) -> None:
        self.provider = provider or create_ocr_provider()

    @property
    def ready(self) -> bool:
        return self.provider.ready

    @property
    def engine(self) -> str:
        return self.provider.name

    def initialize(self) -> None:
        self.provider.initialize()

    def extract(
        self,
        image: PreparedImage,
        trace: RequestTrace | None = None,
        image_context: str = "",
    ) -> OcrResult:
        if not self.ready:
            self.initialize()
        if not self.ready:
            raise OcrUnavailableError(f"{self.engine} OCR is disabled in this environment.")

        with ocr_semaphore:
            ocr_started = time.perf_counter()
            if trace is not None:
                trace.stage(5, "OCR start", image_context)
                trace.info(
                    "Starting OCR | Engine: %s | Reader already initialized: %s | "
                    "GPU enabled: %s | Image dimensions: %dx%d | %s",
                    self.engine,
                    str(self.ready).lower(),
                    str(config.OCR_GPU and self.engine == "easyocr").lower(),
                    image.width,
                    image.height,
                    image_context,
                )
                trace.mark("before_ocr", image_context)
            else:
                logger.info(
                    "[-] Starting OCR | engine=%s | initialized=%s | image=%dx%d | rss_mb=%s",
                    self.engine,
                    self.ready,
                    image.width,
                    image.height,
                    current_rss_mb(),
                )
            try:
                first = self.provider.read(image.original)
                if (
                    first.blocks and first.average_confidence >= 0.55
                ) or not config.ENABLE_SECOND_OCR_PASS or image.enhanced is None:
                    result = first
                else:
                    second = self.provider.read(image.enhanced)
                    second.used_enhanced_pass = True
                    first_score = first.average_confidence * max(1, len(first.blocks)) ** 0.5
                    second_score = second.average_confidence * max(1, len(second.blocks)) ** 0.5
                    result = second if second_score >= first_score else first

                result.elapsed_ms = round((time.perf_counter() - ocr_started) * 1000)
                if trace is not None:
                    trace.stage(6, "OCR complete", image_context)
                    trace.info(
                        "OCR complete | Engine: %s | Detected text blocks: %d | "
                        "Average confidence: %.2f | OCR elapsed: %d ms | Enhanced pass: %s | %s",
                        result.engine,
                        len(result.blocks),
                        result.average_confidence,
                        result.elapsed_ms,
                        str(result.used_enhanced_pass).lower(),
                        image_context,
                    )
                return result
            except Exception:
                if trace is not None:
                    trace.exception("OCR failed | Engine: %s | %s", self.engine, image_context)
                else:
                    logger.exception("[-] OCR failed | engine=%s", self.engine)
                raise
            finally:
                if trace is not None:
                    trace.mark("after_ocr", image_context)
                else:
                    logger.info(
                        "[-] OCR finished | engine=%s | rss_mb=%s",
                        self.engine,
                        current_rss_mb(),
                    )


ocr_service = OcrService()
