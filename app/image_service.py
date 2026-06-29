"""Image validation and conservative preprocessing for OCR."""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_FORMATS,
    ENABLE_SECOND_OCR_PASS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_OCR_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
)
from app.telemetry import RequestTrace


Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ImageValidationError(ValueError):
    """An invalid upload message safe to present in the results UI."""


@dataclass(frozen=True)
class PreparedImage:
    original: np.ndarray
    enhanced: np.ndarray | None
    width: int
    height: int


def create_result_preview_data_url(prepared: PreparedImage, size: int = 1200) -> str:
    """Create a bounded result viewer image without retaining the uploaded image."""

    image = Image.fromarray(prepared.original)
    output = io.BytesIO()
    try:
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.save(output, format="JPEG", quality=80, optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    finally:
        image.close()
        output.close()


def prepare_image(
    data: bytes,
    file_name: str,
    content_type: str | None = None,
    trace: RequestTrace | None = None,
    image_context: str = "",
) -> PreparedImage:
    preprocessing_started = time.perf_counter()
    extension = Path(file_name).suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise ImageValidationError("Only JPEG and PNG label images are supported.")
    if len(data) > MAX_IMAGE_BYTES:
        limit = MAX_IMAGE_BYTES // (1024 * 1024)
        raise ImageValidationError(f"Image exceeds the {limit} MB per-file limit.")
    if not data:
        raise ImageValidationError("The uploaded image is empty.")

    try:
        with Image.open(io.BytesIO(data)) as source:
            if trace is not None:
                trace.info(
                    "Filename: %s | Image size: %dx%d | File size: %.2f MB | %s",
                    file_name,
                    source.width,
                    source.height,
                    len(data) / (1024 * 1024),
                    image_context,
                )
            if (source.format or "").upper() not in ALLOWED_FORMATS:
                raise ImageValidationError("File contents are not a valid JPEG or PNG image.")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ImageValidationError("Image dimensions are too large to process safely.")
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            ocr_dimension = min(MAX_IMAGE_DIMENSION, MAX_OCR_IMAGE_DIMENSION)
            resize_started = time.perf_counter()
            if trace is not None:
                trace.stage(2, "Resize", image_context)
            if max(image.size) > ocr_dimension:
                scale = ocr_dimension / max(image.size)
                resized = image.resize(
                    (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                    Image.Resampling.LANCZOS,
                )
                image.close()
                image = resized
            if trace is not None:
                trace.info(
                    "Resize complete | Dimensions: %dx%d | Long-edge limit: %d | %s",
                    image.width,
                    image.height,
                    ocr_dimension,
                    image_context,
                )
                trace.timing("Image resize", resize_started, image_context)
                trace.memory("After resize", image_context)

            rgb_started = time.perf_counter()
            if trace is not None:
                trace.stage(3, "RGB conversion", image_context)
            try:
                # Own the RGB buffer independently so Pillow can release its image.
                rgb = np.array(image, dtype=np.uint8, copy=True)
            finally:
                image.close()
            if trace is not None:
                trace.timing("RGB conversion", rgb_started, image_context)
                trace.memory("After RGB conversion", image_context)
    except Image.DecompressionBombError as exc:
        if trace is not None:
            trace.exception("Image preprocessing failed | %s", image_context)
        raise ImageValidationError("Image dimensions are too large to process safely.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if trace is not None:
            trace.exception("Image preprocessing failed | %s", image_context)
        if isinstance(exc, ImageValidationError):
            raise
        raise ImageValidationError("The file is damaged or is not a readable image.") from exc

    enhanced: np.ndarray | None = None
    preprocessing_pass_started = time.perf_counter()
    if trace is not None:
        trace.stage(4, "Preprocessing", image_context)
    if ENABLE_SECOND_OCR_PASS:
        # OpenCV and the grayscale buffer are only loaded when the optional retry
        # is enabled, avoiding their memory cost on small Render instances.
        import cv2

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrasted, (3, 3), 0)
        enhanced = cv2.addWeighted(contrasted, 1.35, blurred, -0.35, 0)
        del gray, contrasted, blurred, clahe
        if trace is not None:
            trace.info("Enhanced OCR preprocessing complete | %s", image_context)
    elif trace is not None:
        trace.info("Enhanced OCR preprocessing skipped (disabled) | %s", image_context)
    if trace is not None:
        trace.timing("Image preprocessing pass", preprocessing_pass_started, image_context)
        trace.memory("After preprocessing", image_context)
        trace.timing("Image preprocessing", preprocessing_started, image_context)
    return PreparedImage(
        original=rgb,
        enhanced=enhanced,
        width=int(rgb.shape[1]),
        height=int(rgb.shape[0]),
    )
