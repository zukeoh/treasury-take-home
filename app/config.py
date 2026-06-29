"""Application configuration kept in one place for easy deployment tuning."""

from __future__ import annotations

import os
from pathlib import Path


def _positive_int_env(name: str, default: int) -> int:
    """Read a positive integer without making an optional setting startup-critical."""

    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

APP_NAME = "TTB Alcohol Label Pre-Screener"
APP_VERSION = "1.0.0"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}
MAX_IMAGE_BYTES = _positive_int_env("MAX_IMAGE_BYTES", 12_582_912)
MAX_TOTAL_BYTES = _positive_int_env("MAX_TOTAL_BYTES", 104_857_600)
MAX_IMAGES = _positive_int_env("MAX_IMAGES", 300)
MAX_IMAGE_DIMENSION = _positive_int_env("MAX_IMAGE_DIMENSION", 3200)
MAX_IMAGE_PIXELS = _positive_int_env("MAX_IMAGE_PIXELS", 36_000_000)

OCR_LANGUAGES = ["en"]
OCR_GPU = os.getenv("OCR_GPU", "false").lower() == "true"
OCR_MODEL_DIR = os.getenv("EASYOCR_MODEL_DIR") or None
OCR_MAX_WORKERS = _positive_int_env("OCR_MAX_WORKERS", 1)
SKIP_OCR_INIT = os.getenv("TTB_SKIP_OCR_INIT", "false").lower() == "true"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
    LOG_LEVEL = "INFO"

REQUIRED_CSV_COLUMNS = {
    "file_name",
    "brand_name",
    "product_type",
    "abv",
    "net_contents",
    "producer",
    "country_of_origin",
}

# Accepted for compatibility with the original take-home build-plan schema.
LEGACY_CSV_COLUMNS = {
    "file_name",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "country_of_origin",
    "imported",
}

GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to drive "
    "a car or operate machinery, and may cause health problems."
)
