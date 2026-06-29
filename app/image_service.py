"""Image validation and conservative preprocessing for OCR."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_FORMATS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
)


Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ImageValidationError(ValueError):
    """An invalid upload message safe to present in the results UI."""


@dataclass(frozen=True)
class PreparedImage:
    original: np.ndarray
    enhanced: np.ndarray
    width: int
    height: int


def create_result_preview_data_url(prepared: PreparedImage, size: int = 1200) -> str:
    """Create a bounded result viewer image without retaining the uploaded image."""

    image = Image.fromarray(prepared.original)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=80, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def prepare_image(data: bytes, file_name: str, content_type: str | None = None) -> PreparedImage:
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
            if (source.format or "").upper() not in ALLOWED_FORMATS:
                raise ImageValidationError("File contents are not a valid JPEG or PNG image.")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ImageValidationError("Image dimensions are too large to process safely.")
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if max(image.size) > MAX_IMAGE_DIMENSION:
                scale = MAX_IMAGE_DIMENSION / max(image.size)
                image = image.resize(
                    (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            rgb = np.asarray(image)
    except Image.DecompressionBombError as exc:
        raise ImageValidationError("Image dimensions are too large to process safely.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, ImageValidationError):
            raise
        raise ImageValidationError("The file is damaged or is not a readable image.") from exc

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)
    enhanced = cv2.addWeighted(clahe.apply(gray), 1.35, enhanced, -0.35, 0)
    return PreparedImage(
        original=rgb,
        enhanced=enhanced,
        width=int(rgb.shape[1]),
        height=int(rgb.shape[0]),
    )
