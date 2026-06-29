"""Opt-in tests that execute the real Tesseract binary against generated labels."""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path


RESOURCE_DIR = Path(__file__).parent / "resources"
sys.path.insert(0, str(RESOURCE_DIR))

from benchmark_tesseract_fixtures import CASES, benchmark_case  # noqa: E402
from app.ocr_service import TesseractOcrProvider  # noqa: E402


RUN_REAL_OCR = (
    os.getenv("RUN_TESSERACT_FIXTURE_TESTS") == "1"
    and shutil.which("tesseract") is not None
)


@unittest.skipUnless(
    RUN_REAL_OCR,
    "Set RUN_TESSERACT_FIXTURE_TESTS=1 where the Tesseract binary is installed.",
)
class TesseractFixtureQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = TesseractOcrProvider()
        cls.provider.initialize()

    def result(self, file_name: str) -> dict[str, object]:
        return benchmark_case(self.provider, file_name, CASES[file_name])

    def test_clean_category_controls_remain_fully_readable(self) -> None:
        for file_name in (
            "old_tom_distillery.png",
            "casa_azul_tequila_import.png",
            "pine_trail_beer.png",
            "laurel_ridge_wine.png",
        ):
            with self.subTest(file_name=file_name):
                result = self.result(file_name)
                self.assertEqual(result["fields_found"], result["fields_total"], result)
                self.assertGreaterEqual(result["warning_coverage"], 0.95, result)

    def test_uniform_dark_label_is_recovered(self) -> None:
        result = self.result("night_jar_dark.png")
        self.assertEqual(result["fields_found"], result["fields_total"], result)
        self.assertGreaterEqual(result["warning_coverage"], 0.75, result)

    def test_severely_damaged_dark_labels_retain_partial_readability(self) -> None:
        minimums = {
            "midnight_vodka_blurry.png": (2, 0.0),
            "pixel_porter_low_resolution.png": (2, 0.10),
            "neon_stag_glare.png": (2, 0.55),
        }
        for file_name, (minimum_fields, minimum_warning) in minimums.items():
            with self.subTest(file_name=file_name):
                result = self.result(file_name)
                self.assertGreaterEqual(result["fields_found"], minimum_fields, result)
                self.assertGreaterEqual(result["warning_coverage"], minimum_warning, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
