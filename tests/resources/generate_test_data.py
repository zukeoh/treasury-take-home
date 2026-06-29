"""Generate deterministic synthetic label fixtures for the pre-screener.

Run from the repository root:

    python tests/resources/generate_test_data.py

No network access or third-party artwork is used. Every label and CSV row is
synthetic and is generated from the test-data specification supplied with the
take-home project.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


WIDTH = 1400
HEIGHT = 1800
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "sample_data"
WARNING_HEADING = "GOVERNMENT WARNING:"
WARNING_BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. (2) "
    "Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)
WARNING = f"{WARNING_HEADING} {WARNING_BODY}"


@dataclass(frozen=True)
class LabelSpec:
    file_name: str
    brand: str
    product_type: str
    alcohol: str
    net_contents: str
    producer: str
    category: str
    background: tuple[int, int, int]
    foreground: tuple[int, int, int]
    accent: tuple[int, int, int]
    origin: str = ""
    vintage: str = ""
    warning: bool = True
    variant: str = "standard"


LABELS = [
    LabelSpec(
        "old_tom_distillery.png",
        "OLD TOM DISTILLERY",
        "Kentucky Straight Bourbon Whiskey",
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        "Distilled and Bottled by Old Tom Distillery, Louisville, KY",
        "DISTILLED SPIRITS",
        (245, 235, 210),
        (48, 31, 22),
        (142, 83, 34),
    ),
    LabelSpec(
        "stones_throw_case_variation.png",
        "STONE'S THROW",
        "Kentucky Straight Bourbon Whiskey",
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        "Distilled and Bottled by Stone & Throw Distillery, Frankfort, KY",
        "DISTILLED SPIRITS",
        (236, 226, 204),
        (37, 36, 33),
        (111, 90, 61),
        variant="stones",
    ),
    LabelSpec(
        "casa_azul_tequila_import.png",
        "CASA AZUL",
        "Tequila",
        "40% Alc./Vol.",
        "750 mL",
        "Imported by Casa Azul Imports, Austin, TX",
        "IMPORTED TEQUILA",
        (229, 242, 240),
        (18, 52, 67),
        (27, 128, 145),
        origin="Product of Mexico",
        variant="agave",
    ),
    LabelSpec(
        "red_ridge_missing_warning.png",
        "RED RIDGE DISTILLING",
        "Rye Whiskey",
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        "Distilled and Bottled by Red Ridge Distilling Co., Asheville, NC",
        "DISTILLED SPIRITS",
        (241, 225, 214),
        (68, 25, 24),
        (152, 42, 42),
        warning=False,
        variant="ridge",
    ),
    LabelSpec(
        "north_point_wrong_abv.png",
        "NORTH POINT VODKA",
        "Vodka",
        "40% Alc./Vol.",
        "750 mL",
        "Bottled by North Point Spirits, Portland, OR",
        "DISTILLED SPIRITS",
        (235, 242, 246),
        (21, 43, 63),
        (52, 108, 150),
        variant="compass",
    ),
    LabelSpec(
        "sol_y_mar_missing_country.png",
        "SOL Y MAR",
        "Tequila",
        "40% Alc./Vol.",
        "750 mL",
        "Imported by Sol Y Mar Imports, Miami, FL",
        "IMPORTED TEQUILA",
        (255, 239, 195),
        (44, 66, 72),
        (227, 136, 49),
        variant="sun",
    ),
    LabelSpec(
        "silver_oak_low_contrast.png",
        "SILVER OAK",
        "Cabernet Sauvignon",
        "13.5% Alc./Vol.",
        "750 mL",
        "Produced and Bottled by Silver Oak Winery, Napa, CA",
        "NAPA VALLEY WINE",
        (72, 75, 78),
        (116, 119, 121),
        (103, 105, 107),
        vintage="2019",
        variant="low_contrast",
    ),
    LabelSpec(
        "cropped_warning_label.png",
        "HARBOR LIGHT",
        "Chardonnay",
        "13% Alc./Vol.",
        "750 mL",
        "Produced and Bottled by Harbor Light Cellars, Sonoma, CA",
        "CALIFORNIA WINE",
        (239, 244, 241),
        (24, 55, 64),
        (49, 132, 139),
        origin="California",
        vintage="2021",
        variant="cropped",
    ),
    LabelSpec(
        "hilltop_wrong_net_contents.png",
        "HILLTOP GIN",
        "Gin",
        "40% Alc./Vol.",
        "1 Liter",
        "Distilled and Bottled by Hilltop Distillery, Denver, CO",
        "DISTILLED SPIRITS",
        (235, 242, 227),
        (31, 62, 43),
        (84, 137, 87),
        variant="hill",
    ),
    LabelSpec(
        "pine_trail_beer.png",
        "PINE TRAIL IPA",
        "India Pale Ale",
        "6.5% Alc./Vol.",
        "12 FL. OZ. (355 mL)",
        "Brewed and Bottled by Pine Trail Brewing Co., Bend, OR",
        "CRAFT BEER",
        (226, 235, 211),
        (30, 57, 39),
        (75, 116, 61),
        variant="pine",
    ),
    LabelSpec(
        "laurel_ridge_wine.png",
        "LAUREL RIDGE",
        "Merlot",
        "13.5% Alc./Vol.",
        "750 mL",
        "Produced and Bottled by Laurel Ridge Wines, Healdsburg, CA",
        "CALIFORNIA WINE",
        (244, 233, 224),
        (73, 31, 45),
        (133, 62, 79),
        origin="California",
        vintage="2020",
        variant="laurel",
    ),
    LabelSpec(
        "bayview_skewed_angle.png",
        "BAYVIEW SPICED RUM",
        "Spiced Rum",
        "35% Alc./Vol.",
        "750 mL",
        "Bottled by Bayview Spirits Co., San Diego, CA",
        "DISTILLED SPIRITS",
        (231, 239, 240),
        (25, 52, 63),
        (38, 111, 137),
        variant="skewed",
    ),
]


CSV_HEADER = [
    "file_name",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "country_of_origin",
    "imported",
]

CSV_ROWS = {
    "old_tom_distillery.png": ["OLD TOM DISTILLERY", "Kentucky Straight Bourbon Whiskey", "45% Alc./Vol. (90 Proof)", "750 mL", "Old Tom Distillery, Louisville, KY", "", "false"],
    "stones_throw_case_variation.png": ["Stone's Throw", "Kentucky Straight Bourbon Whiskey", "45% Alc./Vol. (90 Proof)", "750 mL", "Stone & Throw Distillery, Frankfort, KY", "", "false"],
    "casa_azul_tequila_import.png": ["CASA AZUL", "Tequila", "40% Alc./Vol.", "750 mL", "Casa Azul Imports, Austin, TX", "Mexico", "true"],
    "red_ridge_missing_warning.png": ["RED RIDGE DISTILLING", "Rye Whiskey", "45% Alc./Vol. (90 Proof)", "750 mL", "Red Ridge Distilling Co., Asheville, NC", "", "false"],
    "north_point_wrong_abv.png": ["NORTH POINT VODKA", "Vodka", "45% Alc./Vol.", "750 mL", "North Point Spirits, Portland, OR", "", "false"],
    "sol_y_mar_missing_country.png": ["SOL Y MAR", "Tequila", "40% Alc./Vol.", "750 mL", "Sol Y Mar Imports, Miami, FL", "Mexico", "true"],
    "silver_oak_low_contrast.png": ["SILVER OAK", "Cabernet Sauvignon", "13.5% Alc./Vol.", "750 mL", "Silver Oak Winery, Napa, CA", "", "false"],
    "cropped_warning_label.png": ["HARBOR LIGHT", "Chardonnay", "13% Alc./Vol.", "750 mL", "Harbor Light Cellars, Sonoma, CA", "", "false"],
    "hilltop_wrong_net_contents.png": ["HILLTOP GIN", "Gin", "40% Alc./Vol.", "750 mL", "Hilltop Distillery, Denver, CO", "", "false"],
    "pine_trail_beer.png": ["PINE TRAIL IPA", "India Pale Ale", "6.5% Alc./Vol.", "12 FL. OZ. (355 mL)", "Pine Trail Brewing Co., Bend, OR", "", "false"],
    "laurel_ridge_wine.png": ["LAUREL RIDGE", "Merlot", "13.5% Alc./Vol.", "750 mL", "Laurel Ridge Wines, Healdsburg, CA", "", "false"],
    "bayview_skewed_angle.png": ["BAYVIEW SPICED RUM", "Spiced Rum", "35% Alc./Vol.", "750 mL", "Bayview Spirits Co., San Diego, CA", "", "false"],
}

CSV_GROUPS = {
    "sample_labels.csv": [
        "old_tom_distillery.png",
        "stones_throw_case_variation.png",
        "casa_azul_tequila_import.png",
        "pine_trail_beer.png",
        "laurel_ridge_wine.png",
    ],
    "failing_labels.csv": [
        "red_ridge_missing_warning.png",
        "north_point_wrong_abv.png",
        "sol_y_mar_missing_country.png",
        "hilltop_wrong_net_contents.png",
    ],
    "batch_mixed.csv": [
        "old_tom_distillery.png",
        "stones_throw_case_variation.png",
        "red_ridge_missing_warning.png",
        "north_point_wrong_abv.png",
        "sol_y_mar_missing_country.png",
        "silver_oak_low_contrast.png",
        "cropped_warning_label.png",
        "hilltop_wrong_net_contents.png",
        "pine_trail_beer.png",
        "laurel_ridge_wine.png",
        "bayview_skewed_angle.png",
    ],
}


@lru_cache(maxsize=None)
def load_font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif and bold:
        candidates = [
            "C:/Windows/Fonts/georgiab.ttf",
            "C:/Windows/Fonts/timesbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ]
    elif serif:
        candidates = [
            "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/times.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]
    elif bold:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> float:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = " ".join([*current, word])
        if current and text_width(draw, candidate, font) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    y: int,
    fill: tuple[int, int, int],
    width: int = 1120,
    spacing: int = 12,
) -> int:
    for line in wrap_lines(draw, text, font, width):
        box = draw.textbbox((0, 0), line, font=font)
        line_width = box[2] - box[0]
        line_height = box[3] - box[1]
        draw.text(((WIDTH - line_width) / 2, y), line, font=font, fill=fill)
        y += line_height + spacing
    return y


def draw_warning(
    draw: ImageDraw.ImageDraw,
    y: int,
    fill: tuple[int, int, int],
) -> None:
    left, right = 105, WIDTH - 105
    regular = load_font(27)
    bold = load_font(27, bold=True)
    tokens = [(word, bold) for word in WARNING_HEADING.split()]
    tokens.extend((word, regular) for word in WARNING_BODY.split())
    x = left
    line_height = 38
    for word, font in tokens:
        word_with_space = word + " "
        width = text_width(draw, word_with_space, font)
        if x + width > right:
            x = left
            y += line_height
        draw.text((x, y), word_with_space, font=font, fill=fill)
        x += width


def draw_decoration(draw: ImageDraw.ImageDraw, spec: LabelSpec) -> None:
    accent = spec.accent
    if spec.variant in {"sun", "agave"}:
        draw.ellipse((530, 190, 870, 530), outline=accent, width=12)
        for offset in range(-240, 241, 60):
            draw.line((700, 165, 700 + offset, 80), fill=accent, width=7)
    elif spec.variant in {"pine", "hill", "ridge"}:
        draw.polygon([(180, 520), (430, 210), (640, 520)], outline=accent)
        draw.polygon([(480, 520), (760, 160), (1030, 520)], outline=accent)
        draw.line((140, 520, 1260, 520), fill=accent, width=8)
    elif spec.variant == "compass":
        draw.ellipse((540, 180, 860, 500), outline=accent, width=8)
        draw.polygon([(700, 205), (745, 370), (700, 475), (655, 370)], fill=accent)
    elif spec.variant == "stones":
        for x, y, radius in [(480, 320, 70), (620, 260, 95), (790, 330, 80)]:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=accent, width=8)
    else:
        draw.ellipse((570, 210, 830, 470), outline=accent, width=8)
        draw.line((420, 340, 980, 340), fill=accent, width=5)


def render_label(spec: LabelSpec) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), spec.background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 55, WIDTH - 55, HEIGHT - 55), radius=24, outline=spec.accent, width=8)
    draw.rounded_rectangle((77, 77, WIDTH - 77, HEIGHT - 77), radius=18, outline=spec.accent, width=2)
    draw_decoration(draw, spec)

    y = 105
    category_font = load_font(25, bold=True)
    category_width = text_width(draw, spec.category, category_font)
    draw.text(((WIDTH - category_width) / 2, y), spec.category, font=category_font, fill=spec.accent)

    y = 545
    y = draw_centered_lines(draw, spec.brand, load_font(76, bold=True, serif=True), y, spec.foreground, spacing=8)
    y += 16
    y = draw_centered_lines(draw, spec.product_type, load_font(43, serif=True), y, spec.foreground)
    if spec.origin:
        y += 6
        y = draw_centered_lines(draw, spec.origin, load_font(31, bold=True), y, spec.accent)
    if spec.vintage:
        y += 4
        y = draw_centered_lines(draw, spec.vintage, load_font(34, serif=True), y, spec.foreground)

    y = max(y + 50, 850)
    y = draw_centered_lines(draw, spec.alcohol, load_font(37, bold=True), y, spec.foreground)
    y += 12
    y = draw_centered_lines(draw, spec.net_contents, load_font(35), y, spec.foreground)
    y += 42
    draw.line((210, y, WIDTH - 210, y), fill=spec.accent, width=3)
    y += 35
    draw_centered_lines(draw, spec.producer, load_font(29), y, spec.foreground, width=1040)

    if spec.warning:
        draw.line((105, 1300, WIDTH - 105, 1300), fill=spec.foreground, width=3)
        draw_warning(draw, 1330, spec.foreground)

    rng = random.Random(spec.file_name)
    for _ in range(1400):
        x = rng.randrange(85, WIDTH - 85)
        y = rng.randrange(85, HEIGHT - 85)
        base = image.getpixel((x, y))
        shift = rng.choice((-5, -3, 3, 5))
        image.putpixel((x, y), tuple(max(0, min(255, channel + shift)) for channel in base))

    if spec.variant == "low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.62)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.65))
    elif spec.variant == "cropped":
        image = image.crop((0, 0, WIDTH, 1415))
    elif spec.variant == "skewed":
        image = image.rotate(7, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(41, 47, 49))
        shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        shade_draw.polygon([(0, 0), (430, 0), (150, HEIGHT), (0, HEIGHT)], fill=(0, 0, 0, 70))
        image = Image.alpha_composite(image.convert("RGBA"), shade).convert("RGB")
    return image


def write_csv_files(csv_dir: Path) -> None:
    csv_dir.mkdir(parents=True, exist_ok=True)
    for file_name, label_names in CSV_GROUPS.items():
        with (csv_dir / file_name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            for label_name in label_names:
                writer.writerow([label_name, *CSV_ROWS[label_name]])


def write_readme(output: Path) -> None:
    content = """# Synthetic TTB test resources

These labels are generated assets for prototype testing only. They do not use real brands,
logos, applications, or regulatory approvals.

Regenerate every image and CSV from the repository root:

```bash
python tests/resources/generate_test_data.py
```

## Scenarios

| Label | Purpose | Expected outcome | Suggested CSV |
| --- | --- | --- | --- |
| `old_tom_distillery.png` | Complete bourbon label | PASS | `sample_labels.csv` |
| `stones_throw_case_variation.png` | Case and punctuation variation | Brand PASS | `sample_labels.csv` |
| `casa_azul_tequila_import.png` | Imported tequila with origin | PASS | `sample_labels.csv` |
| `red_ridge_missing_warning.png` | Missing statutory warning | FAIL warning | `failing_labels.csv` |
| `north_point_wrong_abv.png` | Label 40% vs application 45% | FAIL alcohol | `failing_labels.csv` |
| `sol_y_mar_missing_country.png` | Imported label without origin | FAIL/NEEDS REVIEW country | `failing_labels.csv` |
| `silver_oak_low_contrast.png` | Low-contrast wine artwork | NEEDS REVIEW likely | `batch_mixed.csv` |
| `cropped_warning_label.png` | Warning cut off at bottom | FAIL/NEEDS REVIEW warning | `batch_mixed.csv` |
| `hilltop_wrong_net_contents.png` | Label 1 L vs application 750 mL | FAIL net contents | `failing_labels.csv` |
| `pine_trail_beer.png` | Complete beer label | PASS | `sample_labels.csv` |
| `laurel_ridge_wine.png` | Complete wine label | PASS | `sample_labels.csv` |
| `bayview_skewed_angle.png` | Angled label and uneven lighting | PASS/NEEDS REVIEW | `batch_mixed.csv` |

## CSV sets

- `sample_labels.csv`: mostly passing labels for a clean demonstration.
- `failing_labels.csv`: missing or mismatched compliance data.
- `batch_mixed.csv`: passing, failing, and OCR-challenging labels together.

The CSVs intentionally use the original take-home schema. The application continues to
accept that schema for compatibility in addition to the simplified UI sample format.
"""
    (output / "README.md").write_text(content, encoding="utf-8", newline="\n")


def generate(output: Path = DEFAULT_OUTPUT) -> None:
    label_dir = output / "labels"
    csv_dir = output / "csv"
    label_dir.mkdir(parents=True, exist_ok=True)
    for spec in LABELS:
        image = render_label(spec)
        image.save(label_dir / spec.file_name, format="PNG", optimize=True)
    write_csv_files(csv_dir)
    write_readme(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory (default: tests/resources/sample_data)",
    )
    args = parser.parse_args()
    generate(args.output.resolve())
    print(f"Generated {len(LABELS)} labels and {len(CSV_GROUPS)} CSV files in {args.output.resolve()}")


if __name__ == "__main__":
    main()
