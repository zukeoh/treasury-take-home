"""Run the real local Tesseract engine against representative generated labels.

This is intentionally separate from the fast mocked unit suite. Run it in the
project Docker image so the Tesseract binary and language data match deployment.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import GOVERNMENT_WARNING  # noqa: E402
from app.image_service import prepare_image  # noqa: E402
from app.normalizer import normalize_text  # noqa: E402
from app.ocr_service import TesseractOcrProvider  # noqa: E402


LABEL_DIR = ROOT / "tests" / "resources" / "sample_data" / "labels"
CASES = {
    "old_tom_distillery.png": ["OLD TOM DISTILLERY", "Bourbon Whiskey", "45%", "750 mL"],
    "casa_azul_tequila_import.png": ["CASA AZUL", "Tequila", "40%", "750 mL", "Mexico"],
    "pine_trail_beer.png": ["PINE TRAIL IPA", "India Pale Ale", "6.5%", "355 mL"],
    "laurel_ridge_wine.png": ["LAUREL RIDGE", "Merlot", "13.5%", "750 mL"],
    "midnight_vodka_blurry.png": ["MIDNIGHT CURRENT", "Vodka", "40%", "1 L"],
    "night_jar_dark.png": ["NIGHT JAR", "Petite Sirah", "14.5%", "750 mL"],
    "pixel_porter_low_resolution.png": ["PIXEL PORTER", "Robust Porter", "6%", "355 mL"],
    "neon_stag_glare.png": ["NEON STAG", "Pilsner", "5%", "473 mL"],
    "copper_fox_rotated_left.png": ["COPPER FOX", "Single Malt Whiskey", "46%", "750 mL"],
    "coastal_pilsner_perspective.png": ["COASTAL CURRENT", "Pilsner", "5.1%", "355 mL"],
    "atlas_gin_zoomed_out.png": ["ATLAS NORTH", "London Dry Gin", "43%", "750 mL"],
    "sunroom_overexposed.png": ["SUNROOM", "Chenin Blanc", "12.2%", "750 mL"],
    "mossy_bank_crumpled.png": ["MOSSY BANK", "Sauvignon Blanc", "13%", "750 mL"],
}


def token_coverage(expected: str, detected: str) -> float:
    expected_tokens = Counter(normalize_text(expected).split())
    detected_tokens = Counter(normalize_text(detected).split())
    return sum((expected_tokens & detected_tokens).values()) / sum(expected_tokens.values())


def benchmark_case(
    provider: TesseractOcrProvider,
    file_name: str,
    phrases: list[str],
) -> dict[str, object]:
    path = LABEL_DIR / file_name
    prepared = prepare_image(path.read_bytes(), file_name, "image/png")
    ocr = provider.read(prepared.original)
    normalized = normalize_text(ocr.text)
    phrase_results = {
        phrase: normalize_text(phrase) in normalized
        for phrase in phrases
    }
    return {
        "file_name": file_name,
        "fields_found": sum(phrase_results.values()),
        "fields_total": len(phrase_results),
        "missing": [phrase for phrase, found in phrase_results.items() if not found],
        "warning_coverage": round(token_coverage(GOVERNMENT_WARNING, ocr.text), 3),
        "average_confidence": round(ocr.average_confidence, 3),
        "blocks": len(ocr.blocks),
        "elapsed_ms": ocr.elapsed_ms,
    }


def run_benchmark() -> list[dict[str, object]]:
    provider = TesseractOcrProvider()
    provider.initialize()
    results: list[dict[str, object]] = []
    for file_name, phrases in CASES.items():
        results.append(benchmark_case(provider, file_name, phrases))
    return results


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
