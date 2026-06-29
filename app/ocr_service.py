"""A process-wide EasyOCR reader with an adaptive second pass for weak images."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from app import config
from app.image_service import PreparedImage
from app.models import OcrFragment, OcrResult
from app.telemetry import RequestTrace, current_rss_mb


logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)
ocr_semaphore = threading.BoundedSemaphore(config.OCR_MAX_WORKERS)


class OcrUnavailableError(RuntimeError):
    pass


class OcrService:
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
            except Exception as exc:  # EasyOCR surfaces several backend exception types.
                self._initialization_error = str(exc)
                raise OcrUnavailableError("The local OCR engine could not be initialized.") from exc

    def extract(
        self,
        image: PreparedImage,
        trace: RequestTrace | None = None,
        image_context: str = "",
    ) -> OcrResult:
        if self._reader is None:
            if self._initialization_error:
                raise OcrUnavailableError("The local OCR engine is unavailable.")
            self.initialize()
        if self._reader is None:
            raise OcrUnavailableError("The local OCR engine is disabled in this environment.")

        # The module-level gate applies across every request in this process. The
        # first pass and any enhanced retry count as one image OCR operation.
        with ocr_semaphore:
            ocr_started = time.perf_counter()
            if trace is not None:
                trace.stage(5, "OCR start", image_context)
                trace.info(
                    "Starting OCR | Reader already initialized: %s | GPU enabled: %s | "
                    "Image dimensions: %dx%d | %s",
                    str(self.ready).lower(),
                    str(config.OCR_GPU).lower(),
                    image.width,
                    image.height,
                    image_context,
                )
                trace.mark("before_ocr", image_context)
            else:
                logger.info(
                    "[-] Starting OCR | reader_initialized=%s | gpu=%s | image=%dx%d | rss_mb=%s",
                    self.ready,
                    config.OCR_GPU,
                    image.width,
                    image.height,
                    current_rss_mb(),
                )
            try:
                first = self._read(image.original)
                if (
                    first.fragments and first.average_confidence >= 0.55
                ) or not config.ENABLE_SECOND_OCR_PASS or image.enhanced is None:
                    result = first
                else:
                    second = self._read(image.enhanced)
                    second.used_enhanced_pass = True
                    first_score = first.average_confidence * max(1, len(first.fragments)) ** 0.5
                    second_score = second.average_confidence * max(1, len(second.fragments)) ** 0.5
                    result = second if second_score >= first_score else first

                elapsed_ms = (time.perf_counter() - ocr_started) * 1000
                if trace is not None:
                    trace.stage(6, "OCR complete", image_context)
                    trace.info(
                        "OCR complete | Detected text blocks: %d | Average confidence: %.2f | "
                        "OCR elapsed: %.0f ms | Enhanced pass: %s | %s",
                        len(result.fragments),
                        result.average_confidence,
                        elapsed_ms,
                        str(result.used_enhanced_pass).lower(),
                        image_context,
                    )
                return result
            except Exception:
                if trace is not None:
                    trace.exception("OCR failed | %s", image_context)
                else:
                    logger.exception("[-] OCR failed")
                raise
            finally:
                if trace is not None:
                    trace.mark("after_ocr", image_context)
                else:
                    logger.info("[-] OCR finished | rss_mb=%s", current_rss_mb())

    def _read(self, image: np.ndarray) -> OcrResult:
        raw_results = self._reader.readtext(
            image,
            detail=1,
            paragraph=False,
            decoder="greedy",
            batch_size=1,
            workers=0,
        )
        fragments: list[OcrFragment] = []
        for item in raw_results:
            if len(item) < 3:
                continue
            text = str(item[1]).strip()
            confidence = max(0.0, min(1.0, float(item[2])))
            if text:
                fragments.append(OcrFragment(text=text, confidence=confidence))
        average = (
            sum(fragment.confidence for fragment in fragments) / len(fragments)
            if fragments
            else 0.0
        )
        return OcrResult(
            fragments=fragments,
            text="\n".join(fragment.text for fragment in fragments),
            average_confidence=average,
        )


ocr_service = OcrService()
