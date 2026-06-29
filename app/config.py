"""Application configuration kept in one place for easy deployment tuning."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

APP_NAME = "TTB Alcohol Label Pre-Screener"
APP_VERSION = "1.0.0"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", 12 * 1024 * 1024))
MAX_TOTAL_BYTES = int(os.getenv("MAX_TOTAL_BYTES", 100 * 1024 * 1024))
MAX_IMAGES = int(os.getenv("MAX_IMAGES", 300))
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", 3200))
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", 36_000_000))

OCR_LANGUAGES = ["en"]
OCR_GPU = os.getenv("OCR_GPU", "false").lower() == "true"
OCR_MODEL_DIR = os.getenv("EASYOCR_MODEL_DIR")
SKIP_OCR_INIT = os.getenv("TTB_SKIP_OCR_INIT", "false").lower() == "true"

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
