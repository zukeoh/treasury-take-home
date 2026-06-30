from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

from app.csv_service import parse_application_csv


RESOURCE_ROOT = Path(__file__).parent / "resources" / "sample_data"
LABEL_DIR = RESOURCE_ROOT / "labels"
CSV_DIR = RESOURCE_ROOT / "csv"
REQUIRED_ORIGINAL_LABELS = {
    "old_tom_distillery.png",
    "stones_throw_case_variation.png",
    "casa_azul_tequila_import.png",
    "red_ridge_missing_warning.png",
    "north_point_wrong_abv.png",
    "sol_y_mar_missing_country.png",
    "silver_oak_low_contrast.png",
    "cropped_warning_label.png",
    "hilltop_wrong_net_contents.png",
    "pine_trail_beer.png",
    "laurel_ridge_wine.png",
    "bayview_skewed_angle.png",
}
LEGACY_HEADER = [
    "file_name",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "country_of_origin",
    "imported",
]


def test_all_required_label_images_exist_and_decode() -> None:
    generated = {path.name for path in LABEL_DIR.glob("*.png")}
    assert len(generated) == 50
    assert REQUIRED_ORIGINAL_LABELS.issubset(generated)
    sizes: set[tuple[int, int]] = set()
    for path in LABEL_DIR.glob("*.png"):
        with Image.open(path) as image:
            image.verify()
            assert image.format == "PNG"
        with Image.open(path) as image:
            sizes.add(image.size)
    assert len(sizes) >= 5


def test_csv_files_use_required_schema_and_match_images() -> None:
    generated = {path.name for path in LABEL_DIR.glob("*.png")}
    assert {path.name for path in CSV_DIR.glob("*.csv")} == {"batch_mixed.csv"}
    path = CSV_DIR / "batch_mixed.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == LEGACY_HEADER
    csv_names = {row[0] for row in rows[1:]}
    assert len(csv_names) == 50
    assert csv_names == generated
    parsed = parse_application_csv(path.read_bytes())
    assert len(parsed) == len(rows) - 1


def test_sample_resource_readme_exists() -> None:
    readme = (RESOURCE_ROOT / "README.md").read_text(encoding="utf-8")
    assert "synthetic" in readme.casefold()
    assert "batch_mixed.csv" in readme
    assert "50 labels" in readme
    assert "torn" in readme.casefold()
    assert "perspective" in readme.casefold()


def test_rule_documentation_lists_official_sources() -> None:
    rule_docs = (Path(__file__).parents[1] / "docs" / "rule_documentation.md").read_text(
        encoding="utf-8"
    )
    assert "TTB Malt Beverage Labeling" in rule_docs
    assert "TTB Distilled Spirits Labeling" in rule_docs
    assert "TTB Wine Labeling" in rule_docs
    assert "TTB Malt Beverage Health Warning" in rule_docs
    assert "TTB Distilled Spirits Health Warning" in rule_docs
    assert "TTB Wine Health Warning" in rule_docs
