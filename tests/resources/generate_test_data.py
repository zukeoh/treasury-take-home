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
    country_of_origin: str = ""
    imported: bool = False


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
        country_of_origin="Mexico",
        imported=True,
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
        country_of_origin="Mexico",
        imported=True,
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


LABELS.extend(
    [
        # Distilled spirits: physical damage, camera geometry, and nonstandard artwork.
        LabelSpec("ember_cask_torn_bourbon.png", "EMBER CASK", "Straight Bourbon Whiskey", "47% Alc./Vol. (94 Proof)", "750 mL", "Distilled and Bottled by Ember Cask Co., Lexington, KY", "DISTILLED SPIRITS", (238, 222, 190), (52, 31, 20), (165, 73, 34), variant="torn"),
        LabelSpec("midnight_vodka_blurry.png", "MIDNIGHT CURRENT", "Vodka", "40% Alc./Vol. (80 Proof)", "1 L", "Bottled by Midnight Current Spirits, Detroit, MI", "DISTILLED SPIRITS", (28, 35, 50), (220, 229, 238), (82, 151, 193), variant="blurry"),
        LabelSpec("copper_fox_rotated_left.png", "COPPER FOX", "American Single Malt Whiskey", "46% Alc./Vol. (92 Proof)", "750 mL", "Distilled by Copper Fox Works, Santa Fe, NM", "DISTILLED SPIRITS", (240, 226, 202), (61, 38, 25), (177, 91, 46), variant="rotated_left"),
        LabelSpec("atlas_gin_zoomed_out.png", "ATLAS NORTH", "London Dry Gin", "43% Alc./Vol. (86 Proof)", "750 mL", "Distilled and Bottled by Atlas North, Duluth, MN", "DISTILLED SPIRITS", (232, 241, 237), (22, 54, 48), (45, 128, 109), variant="zoomed_out"),
        LabelSpec("lunar_rum_dirty.png", "LUNAR TIDE", "Dark Rum", "42% Alc./Vol. (84 Proof)", "750 mL", "Bottled by Lunar Tide Rum Co., Tampa, FL", "DISTILLED SPIRITS", (225, 211, 183), (52, 38, 28), (133, 94, 52), variant="dirty"),
        LabelSpec("jade_dragon_flipped.png", "JADE DRAGON", "Rice Spirit", "38% Alc./Vol. (76 Proof)", "700 mL", "Imported by Jade Dragon Imports, Seattle, WA", "IMPORTED SPIRITS", (225, 238, 222), (22, 58, 38), (75, 139, 76), origin="Product of China", variant="flipped_horizontal", country_of_origin="China", imported=True),
        LabelSpec("crooked_still_weird_layout.png", "CROOKED STILL", "Corn Whiskey", "50% Alc./Vol. (100 Proof)", "750 mL", "Distilled by Crooked Still House, Knoxville, TN", "DISTILLED SPIRITS", (243, 233, 205), (38, 32, 28), (148, 79, 39), variant="weird_layout"),
        LabelSpec("prairie_moon_glare.png", "PRAIRIE MOON", "Wheat Whiskey", "45% Alc./Vol. (90 Proof)", "750 mL", "Bottled by Prairie Moon Distillers, Wichita, KS", "DISTILLED SPIRITS", (229, 221, 194), (45, 39, 28), (118, 103, 49), variant="glare"),
        LabelSpec("black_anchor_cropped_side.png", "BLACK ANCHOR", "Navy Strength Gin", "57% Alc./Vol. (114 Proof)", "700 mL", "Distilled by Black Anchor Spirits, Norfolk, VA", "DISTILLED SPIRITS", (220, 232, 235), (18, 42, 52), (39, 103, 125), variant="cropped_side"),
        LabelSpec("summit_brandy_perspective.png", "SUMMIT HOUSE", "French Brandy", "40% Alc./Vol. (80 Proof)", "750 mL", "Imported by Summit House Imports, Boston, MA", "IMPORTED BRANDY", (238, 226, 201), (69, 38, 33), (144, 73, 62), origin="Product of France", variant="perspective", country_of_origin="France", imported=True),
        # Wine: lighting, scale, orientation, texture, and layout challenges.
        LabelSpec("frost_line_upside_down.png", "FROST LINE", "Riesling", "12% Alc./Vol.", "750 mL", "Produced by Frost Line Cellars, Traverse City, MI", "AMERICAN WINE", (232, 241, 245), (31, 55, 72), (90, 151, 182), vintage="2022", variant="upside_down"),
        LabelSpec("wild_rose_water_stain.png", "WILD ROSE", "Rosé Wine", "12.5% Alc./Vol.", "750 mL", "Produced and Bottled by Wild Rose Winery, Walla Walla, WA", "WASHINGTON WINE", (248, 229, 229), (92, 42, 51), (181, 90, 105), vintage="2023", variant="water_stain"),
        LabelSpec("canyon_echo_zoomed_in.png", "CANYON ECHO", "Syrah", "14.1% Alc./Vol.", "750 mL", "Produced by Canyon Echo Vineyards, Paso Robles, CA", "CALIFORNIA WINE", (236, 222, 205), (67, 38, 33), (148, 76, 55), vintage="2020", variant="zoomed_in"),
        LabelSpec("blue_door_vertical_text.png", "BLUE DOOR", "Pinot Gris", "12.8% Alc./Vol.", "750 mL", "Produced by Blue Door Wines, McMinnville, OR", "OREGON WINE", (224, 236, 242), (24, 52, 73), (58, 120, 158), vintage="2021", variant="vertical_text"),
        LabelSpec("orchard_lane_low_resolution.png", "ORCHARD LANE", "Apple Wine", "11% Alc./Vol.", "750 mL", "Produced by Orchard Lane Winery, Geneva, NY", "NEW YORK WINE", (239, 235, 207), (55, 64, 31), (132, 145, 63), vintage="2023", variant="low_resolution"),
        LabelSpec("granite_peak_shadow.png", "GRANITE PEAK", "Cabernet Franc", "13.9% Alc./Vol.", "750 mL", "Produced by Granite Peak Cellars, Palisade, CO", "COLORADO WINE", (229, 226, 220), (53, 47, 43), (105, 95, 85), vintage="2019", variant="shadow"),
        LabelSpec("paper_crane_logo_heavy.png", "PAPER CRANE", "Sake", "15% Alc./Vol.", "720 mL", "Imported by Paper Crane Beverage Co., Los Angeles, CA", "IMPORTED SAKE", (242, 236, 224), (45, 41, 39), (181, 65, 64), origin="Product of Japan", variant="logo_heavy", country_of_origin="Japan", imported=True),
        LabelSpec("mossy_bank_crumpled.png", "MOSSY BANK", "Sauvignon Blanc", "13% Alc./Vol.", "750 mL", "Produced by Mossy Bank Estate, Charlottesville, VA", "VIRGINIA WINE", (225, 235, 218), (35, 66, 43), (79, 132, 75), vintage="2022", variant="crumpled"),
        LabelSpec("sunroom_overexposed.png", "SUNROOM", "Chenin Blanc", "12.2% Alc./Vol.", "750 mL", "Produced by Sunroom Vineyards, Clarksburg, CA", "CALIFORNIA WINE", (249, 240, 203), (82, 64, 27), (213, 170, 51), vintage="2021", variant="overexposed"),
        LabelSpec("broken_compass_cropped_top.png", "BROKEN COMPASS", "Red Blend", "14% Alc./Vol.", "750 mL", "Produced by Broken Compass Wines, Yakima, WA", "WASHINGTON WINE", (231, 219, 211), (67, 38, 41), (135, 75, 79), vintage="2020", variant="cropped_top"),
        LabelSpec("night_jar_dark.png", "NIGHT JAR", "Petite Sirah", "14.5% Alc./Vol.", "750 mL", "Produced by Night Jar Cellars, Lodi, CA", "CALIFORNIA WINE", (29, 29, 34), (103, 104, 112), (78, 76, 91), vintage="2018", variant="dark"),
        LabelSpec("riverbend_noisy.png", "RIVERBEND", "Muscadine Wine", "11.5% Alc./Vol.", "750 mL", "Produced by Riverbend Winery, Macon, GA", "GEORGIA WINE", (230, 236, 218), (38, 61, 34), (93, 127, 70), vintage="2022", variant="noisy"),
        LabelSpec("golden_hour_occluded.png", "GOLDEN HOUR", "Zinfandel", "13.8% Alc./Vol.", "750 mL", "Produced by Golden Hour Wines, Sonoma, CA", "CALIFORNIA WINE", (244, 224, 186), (76, 44, 28), (185, 112, 44), vintage="2019", variant="partial_occlusion"),
        # Beer and malt beverages: cans, dense logos, damage, blur, and unusual placement.
        LabelSpec("iron_hop_rotated_right.png", "IRON HOP", "Double India Pale Ale", "8.2% Alc./Vol.", "16 FL. OZ. (473 mL)", "Brewed and Canned by Iron Hop Brewing, Pittsburgh, PA", "CRAFT BEER", (226, 228, 219), (43, 47, 39), (115, 125, 87), variant="rotated_right"),
        LabelSpec("cloudline_motion_blur.png", "CLOUDLINE", "Hazy Pale Ale", "5.8% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Cloudline Brewing, Portland, ME", "CRAFT BEER", (226, 238, 244), (31, 61, 79), (86, 151, 180), variant="motion_blur"),
        LabelSpec("tiny_ale_zoomed_out.png", "TINY ALE", "Session Ale", "3.8% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Tiny Ale Works, Madison, WI", "CRAFT BEER", (241, 231, 200), (64, 48, 28), (157, 116, 49), variant="zoomed_out"),
        LabelSpec("festival_lager_weird_layout.png", "FESTIVAL LAGER", "American Lager", "4.7% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Festival Brewing Co., Milwaukee, WI", "MALT BEVERAGE", (245, 224, 179), (70, 43, 24), (207, 112, 34), variant="weird_layout"),
        LabelSpec("brickhouse_dirty.png", "BRICKHOUSE", "Amber Ale", "5.4% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Brickhouse Ales, Richmond, VA", "CRAFT BEER", (224, 203, 186), (70, 38, 29), (143, 67, 48), variant="dirty"),
        LabelSpec("neon_stag_glare.png", "NEON STAG", "Pilsner", "5% Alc./Vol.", "16 FL. OZ. (473 mL)", "Brewed and Canned by Neon Stag Brewing, Austin, TX", "CRAFT BEER", (32, 37, 52), (213, 218, 229), (222, 74, 157), variant="glare"),
        LabelSpec("coastal_pilsner_perspective.png", "COASTAL CURRENT", "German-Style Pilsner", "5.1% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Coastal Current Brewing, Charleston, SC", "CRAFT BEER", (222, 238, 236), (24, 66, 67), (57, 148, 143), variant="perspective"),
        LabelSpec("upside_down_stout.png", "NORTH STAR STOUT", "Oatmeal Stout", "6.2% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by North Star Brewing, Fargo, ND", "CRAFT BEER", (44, 39, 36), (219, 208, 188), (139, 111, 73), variant="upside_down"),
        LabelSpec("torn_ticket_saison.png", "TORN TICKET", "Farmhouse Saison", "6.7% Alc./Vol.", "750 mL", "Brewed and Bottled by Torn Ticket Farm Brewery, Burlington, VT", "CRAFT BEER", (239, 226, 193), (61, 49, 31), (160, 118, 51), variant="torn"),
        LabelSpec("pixel_porter_low_resolution.png", "PIXEL PORTER", "Robust Porter", "6% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Pixel Porter Brewing, San Jose, CA", "CRAFT BEER", (50, 48, 49), (207, 203, 196), (92, 167, 169), variant="low_resolution"),
        LabelSpec("sidecrop_amber.png", "SIDECROP", "American Amber Ale", "5.6% Alc./Vol.", "16 FL. OZ. (473 mL)", "Brewed by Sidecrop Brewing, Boise, ID", "CRAFT BEER", (233, 213, 189), (79, 43, 29), (170, 86, 45), variant="cropped_side"),
        LabelSpec("mirror_ipa_flipped.png", "MIRROR IPA", "India Pale Ale", "7.1% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Mirror Lake Brewing, Reno, NV", "CRAFT BEER", (216, 233, 239), (24, 58, 74), (58, 137, 168), variant="flipped_horizontal"),
        LabelSpec("curved_can_pale_ale.png", "CURVED CAN", "Pale Ale", "5.5% Alc./Vol.", "16 FL. OZ. (473 mL)", "Brewed and Canned by Curved Can Brewing, Columbus, OH", "CRAFT BEER", (228, 236, 221), (42, 67, 38), (103, 150, 78), variant="curved_can"),
        LabelSpec("mudtrack_brown_ale.png", "MUDTRACK", "Brown Ale", "5.9% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Mudtrack Brewing, Little Rock, AR", "CRAFT BEER", (215, 198, 172), (65, 48, 34), (129, 91, 49), variant="mud_splatter"),
        LabelSpec("half_label_wheat_cropped.png", "HALF LABEL", "American Wheat Ale", "4.9% Alc./Vol.", "12 FL. OZ. (355 mL)", "Brewed by Half Label Brewing, Omaha, NE", "MALT BEVERAGE", (238, 227, 190), (74, 57, 25), (177, 132, 44), variant="cropped_bottom"),
    ]
)


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
    spec.file_name: [
        spec.brand,
        spec.product_type,
        spec.alcohol,
        spec.net_contents,
        spec.producer,
        spec.country_of_origin,
        str(spec.imported).lower(),
    ]
    for spec in LABELS
}
CSV_ROWS.update({
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
    # Deliberate application/label mismatches in the expanded failure set.
    "black_anchor_cropped_side.png": ["BLACK ANCHOR", "Navy Strength Gin", "57% Alc./Vol. (114 Proof)", "750 mL", "Black Anchor Spirits, Norfolk, VA", "", "false"],
    "golden_hour_occluded.png": ["GOLDEN HOUR", "Zinfandel", "14.2% Alc./Vol.", "750 mL", "Golden Hour Wines, Sonoma, CA", "", "false"],
    "festival_lager_weird_layout.png": ["FESTIVAL RESERVE", "American Lager", "4.7% Alc./Vol.", "12 FL. OZ. (355 mL)", "Festival Brewing Co., Milwaukee, WI", "", "false"],
})

SAMPLE_LABELS = [
    "old_tom_distillery.png",
    "stones_throw_case_variation.png",
    "casa_azul_tequila_import.png",
    "pine_trail_beer.png",
    "laurel_ridge_wine.png",
    "copper_fox_rotated_left.png",
    "atlas_gin_zoomed_out.png",
    "lunar_rum_dirty.png",
    "wild_rose_water_stain.png",
    "orchard_lane_low_resolution.png",
    "granite_peak_shadow.png",
    "mossy_bank_crumpled.png",
    "iron_hop_rotated_right.png",
    "cloudline_motion_blur.png",
    "brickhouse_dirty.png",
    "coastal_pilsner_perspective.png",
    "curved_can_pale_ale.png",
    "mudtrack_brown_ale.png",
]

FAILING_LABELS = [
    "red_ridge_missing_warning.png",
    "north_point_wrong_abv.png",
    "sol_y_mar_missing_country.png",
    "cropped_warning_label.png",
    "hilltop_wrong_net_contents.png",
    "ember_cask_torn_bourbon.png",
    "midnight_vodka_blurry.png",
    "jade_dragon_flipped.png",
    "black_anchor_cropped_side.png",
    "summit_brandy_perspective.png",
    "frost_line_upside_down.png",
    "broken_compass_cropped_top.png",
    "night_jar_dark.png",
    "golden_hour_occluded.png",
    "upside_down_stout.png",
    "half_label_wheat_cropped.png",
]

CSV_GROUPS = {
    "sample_labels.csv": [
        *SAMPLE_LABELS,
    ],
    "failing_labels.csv": [
        *FAILING_LABELS,
    ],
    "batch_mixed.csv": [
        *(spec.file_name for spec in LABELS),
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
    elif spec.variant == "logo_heavy":
        draw.regular_polygon((700, 335, 220), n_sides=4, rotation=45, outline=accent, width=14)
        draw.regular_polygon((700, 335, 145), n_sides=3, rotation=180, fill=accent)
        draw.ellipse((610, 245, 790, 425), outline=spec.foreground, width=10)
    elif spec.variant in {"vertical_text", "weird_layout"}:
        draw.arc((145, 145, 1255, 660), 190, 350, fill=accent, width=13)
        draw.rectangle((1020, 170, 1210, 480), outline=accent, width=10)
    else:
        draw.ellipse((570, 210, 830, 470), outline=accent, width=8)
        draw.line((420, 340, 980, 340), fill=accent, width=5)


def apply_variant(image: Image.Image, spec: LabelSpec) -> Image.Image:
    """Apply deterministic physical- and camera-like damage after artwork rendering."""

    variant = spec.variant
    rng = random.Random(f"variant:{spec.file_name}")
    if variant == "low_contrast":
        return ImageEnhance.Contrast(image).enhance(0.62).filter(ImageFilter.GaussianBlur(0.65))
    if variant == "cropped":
        return image.crop((0, 0, WIDTH, 1415))
    if variant == "cropped_top":
        return image.crop((0, 230, WIDTH, HEIGHT))
    if variant == "cropped_bottom":
        return image.crop((0, 0, WIDTH, 1280))
    if variant == "cropped_side":
        return image.crop((230, 0, WIDTH, HEIGHT))
    if variant == "skewed":
        rotated = image.rotate(7, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(41, 47, 49))
        shade = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        shade_draw.polygon([(0, 0), (430, 0), (150, HEIGHT), (0, HEIGHT)], fill=(0, 0, 0, 70))
        return Image.alpha_composite(rotated.convert("RGBA"), shade).convert("RGB")
    if variant in {"rotated_left", "rotated_right"}:
        angle = 13 if variant == "rotated_left" else -11
        return image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(38, 43, 47))
    if variant == "upside_down":
        return image.rotate(180, resample=Image.Resampling.BICUBIC)
    if variant == "flipped_horizontal":
        return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if variant == "blurry":
        return image.filter(ImageFilter.GaussianBlur(4.2))
    if variant == "motion_blur":
        blurred = image.copy()
        for offset in (3, 6, 9, 12):
            shifted = Image.new("RGB", image.size, image.getpixel((0, 0)))
            shifted.paste(image, (offset, 0))
            blurred = Image.blend(blurred, shifted, 0.22)
        return blurred.filter(ImageFilter.GaussianBlur(0.8))
    if variant == "zoomed_out":
        canvas = Image.new("RGB", (1900, 1900), (92, 96, 101))
        small = image.copy()
        small.thumbnail((820, 1100), Image.Resampling.LANCZOS)
        canvas.paste(small, ((canvas.width - small.width) // 2, (canvas.height - small.height) // 2))
        return canvas
    if variant == "zoomed_in":
        return image.crop((185, 245, WIDTH - 170, HEIGHT - 210)).resize(
            (WIDTH, HEIGHT), Image.Resampling.LANCZOS
        )
    if variant == "low_resolution":
        return image.resize((280, 360), Image.Resampling.BILINEAR).resize(
            (WIDTH, HEIGHT), Image.Resampling.NEAREST
        )
    if variant == "perspective":
        return image.transform(
            image.size,
            Image.Transform.QUAD,
            (120, 80, 35, HEIGHT - 220, WIDTH - 155, HEIGHT - 90, WIDTH - 45, 210),
            resample=Image.Resampling.BICUBIC,
            fillcolor=(42, 46, 50),
        )

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if variant in {"dirty", "mud_splatter"}:
        count = 95 if variant == "mud_splatter" else 55
        color = (80, 53, 30, 125) if variant == "mud_splatter" else (105, 79, 45, 95)
        for _ in range(count):
            x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            radius = rng.randrange(4, 34)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        for _ in range(18):
            x = rng.randrange(WIDTH)
            draw.line((x, 0, x + rng.randrange(-90, 90), HEIGHT), fill=(80, 66, 46, 45), width=2)
    elif variant == "torn":
        tears = [
            [(0, 0), (250, 0), (205, 85), (155, 42), (98, 132), (0, 90)],
            [(WIDTH, HEIGHT), (WIDTH - 310, HEIGHT), (WIDTH - 255, HEIGHT - 115), (WIDTH - 170, HEIGHT - 68), (WIDTH - 95, HEIGHT - 170), (WIDTH, HEIGHT - 120)],
            [(0, 1010), (96, 970), (55, 1100), (125, 1190), (0, 1260)],
        ]
        for tear in tears:
            draw.polygon(tear, fill=(62, 67, 72, 255))
            draw.line(tear, fill=(90, 72, 54, 180), width=5, joint="curve")
    elif variant == "water_stain":
        for x, y, rx, ry in [(390, 430, 230, 170), (1010, 1120, 250, 210), (610, 1510, 180, 120)]:
            draw.ellipse((x - rx, y - ry, x + rx, y + ry), outline=(117, 89, 54, 100), width=18)
            draw.ellipse((x - rx + 20, y - ry + 20, x + rx - 20, y + ry - 20), fill=(151, 117, 71, 28))
    elif variant == "glare":
        draw.polygon([(760, 0), (1110, 0), (630, HEIGHT), (320, HEIGHT)], fill=(255, 255, 255, 135))
        draw.polygon([(1080, 0), (1240, 0), (900, HEIGHT), (760, HEIGHT)], fill=(255, 255, 255, 70))
    elif variant == "shadow":
        for x in range(WIDTH):
            alpha = int(175 * (1 - x / WIDTH) ** 2)
            draw.line((x, 0, x, HEIGHT), fill=(0, 0, 0, alpha))
    elif variant == "crumpled":
        for _ in range(28):
            x1, y1 = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            x2, y2 = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            draw.line((x1, y1, x2, y2), fill=(255, 255, 255, 55), width=rng.randrange(2, 8))
            draw.line((x1 + 5, y1 + 5, x2 + 5, y2 + 5), fill=(0, 0, 0, 38), width=rng.randrange(2, 6))
    elif variant == "partial_occlusion":
        draw.polygon([(110, 1250), (1170, 1150), (1215, 1395), (145, 1485)], fill=(193, 173, 128, 235))
        draw.line((125, 1270, 1190, 1170), fill=(128, 103, 68, 180), width=6)
    elif variant == "curved_can":
        for x in range(WIDTH):
            distance = abs((x - WIDTH / 2) / (WIDTH / 2))
            alpha = int(145 * distance**2)
            draw.line((x, 0, x, HEIGHT), fill=(0, 0, 0, alpha))
        draw.rectangle((0, 0, 55, HEIGHT), fill=(255, 255, 255, 60))
        draw.rectangle((WIDTH - 55, 0, WIDTH, HEIGHT), fill=(255, 255, 255, 60))
    elif variant == "noisy":
        for _ in range(15000):
            x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            value = rng.choice((0, 255))
            draw.point((x, y), fill=(value, value, value, rng.randrange(18, 75)))
    elif variant == "dark":
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 105))

    composited = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    if variant == "overexposed":
        composited = ImageEnhance.Brightness(composited).enhance(1.75)
        composited = ImageEnhance.Contrast(composited).enhance(0.72)
    return composited


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
    if spec.variant == "weird_layout":
        draw.text((115, 560), spec.brand, font=load_font(63, bold=True, serif=True), fill=spec.foreground)
        product_layer = Image.new("RGBA", (620, 150), (0, 0, 0, 0))
        ImageDraw.Draw(product_layer).text((8, 35), spec.product_type, font=load_font(39, serif=True), fill=(*spec.foreground, 255))
        product_layer = product_layer.rotate(-13, resample=Image.Resampling.BICUBIC, expand=True)
        image.paste(product_layer, (690, 520), product_layer)
        draw = ImageDraw.Draw(image)
        y = 770
    elif spec.variant == "vertical_text":
        brand_layer = Image.new("RGBA", (760, 120), (0, 0, 0, 0))
        ImageDraw.Draw(brand_layer).text((10, 15), spec.brand, font=load_font(68, bold=True, serif=True), fill=(*spec.foreground, 255))
        brand_layer = brand_layer.rotate(90, resample=Image.Resampling.BICUBIC, expand=True)
        image.paste(brand_layer, (90, 470), brand_layer)
        draw = ImageDraw.Draw(image)
        y = draw_centered_lines(draw, spec.product_type, load_font(43, serif=True), 630, spec.foreground, width=760)
    else:
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

    return apply_variant(image, spec)


def write_csv_files(csv_dir: Path) -> None:
    csv_dir.mkdir(parents=True, exist_ok=True)
    for file_name, label_names in CSV_GROUPS.items():
        with (csv_dir / file_name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            for label_name in label_names:
                writer.writerow([label_name, *CSV_ROWS[label_name]])


VARIANT_PURPOSES = {
    "standard": "clean control artwork",
    "stones": "decorative shapes and punctuation variation",
    "agave": "imported product with dense logo artwork",
    "ridge": "missing statutory warning",
    "compass": "prominent logo with an application alcohol mismatch",
    "sun": "imported product missing country-of-origin text",
    "low_contrast": "low contrast with slight blur",
    "cropped": "bottom crop removes part of the warning",
    "hill": "application and label net contents disagree",
    "pine": "clean beer control with landscape logo",
    "laurel": "clean wine control with vintage",
    "skewed": "seven-degree rotation with uneven shadow",
    "torn": "multiple torn-away label sections",
    "blurry": "strong Gaussian focus blur",
    "rotated_left": "thirteen-degree counterclockwise rotation",
    "rotated_right": "eleven-degree clockwise rotation",
    "zoomed_out": "small distant label surrounded by background",
    "zoomed_in": "tight crop enlarged beyond the label edges",
    "dirty": "stains, dirt spots, and vertical scratches",
    "mud_splatter": "heavy mud splatter and scratches",
    "flipped_horizontal": "mirrored label photograph",
    "weird_layout": "off-center brand and diagonally placed product text",
    "glare": "strong diagonal reflective glare",
    "cropped_side": "side crop removes portions of multiple lines",
    "perspective": "trapezoidal camera perspective distortion",
    "upside_down": "180-degree inverted photograph",
    "water_stain": "large translucent water rings",
    "vertical_text": "brand printed vertically beside normal text",
    "low_resolution": "severe downsample and pixelated upscale",
    "shadow": "deep directional shadow across half the label",
    "logo_heavy": "oversized geometric logo competing with text",
    "crumpled": "paper folds, highlights, and crease shadows",
    "overexposed": "washed-out highlights and reduced contrast",
    "cropped_top": "top crop removes category and logo context",
    "dark": "underexposed dark label with weak contrast",
    "noisy": "dense salt-and-pepper camera noise",
    "partial_occlusion": "opaque tape covers warning text",
    "motion_blur": "horizontal camera-motion blur",
    "curved_can": "simulated cylindrical can-edge shading",
    "cropped_bottom": "lower half and statutory warning removed",
}


def beverage_group(spec: LabelSpec) -> str:
    category = spec.category.casefold()
    if "wine" in category or "sake" in category:
        return "Wine / sake"
    if "beer" in category or "malt" in category:
        return "Beer / malt beverage"
    return "Distilled spirits"


def write_readme(output: Path) -> None:
    counts = {
        group: sum(1 for spec in LABELS if beverage_group(spec) == group)
        for group in ("Distilled spirits", "Wine / sake", "Beer / malt beverage")
    }
    lines = [
        "# Synthetic TTB test resources",
        "",
        "These 50 labels are deterministic test assets only. They use fictional brands, generated",
        "logos, and synthetic application data; they are not regulatory approvals.",
        "",
        "Regenerate every image and the three CSV batches from the repository root:",
        "",
        "```bash",
        "python tests/resources/generate_test_data.py",
        "```",
        "",
        "## Coverage",
        "",
        f"- Distilled spirits: {counts['Distilled spirits']}",
        f"- Wine / sake: {counts['Wine / sake']}",
        f"- Beer / malt beverage: {counts['Beer / malt beverage']}",
        "- Physical/camera variants include torn, rotated, blurred, dirty, zoomed, cropped,",
        "  mirrored, upside-down, low-resolution, glare, shadow, perspective, water damage,",
        "  occlusion, dense logos, curved-container shading, and unconventional text placement.",
        "",
        "## Scenarios",
        "",
        "| Label | Category | Purpose | Expected routing | CSV |",
        "| --- | --- | --- | --- | --- |",
    ]
    for spec in LABELS:
        if spec.file_name in FAILING_LABELS:
            routing = "FAIL or NEEDS REVIEW"
            csv_name = "failing_labels.csv"
        elif spec.file_name in SAMPLE_LABELS:
            routing = "PASS or OCR-dependent review"
            csv_name = "sample_labels.csv"
        else:
            routing = "Mixed OCR/rule outcome"
            csv_name = "batch_mixed.csv"
        lines.append(
            f"| `{spec.file_name}` | {beverage_group(spec)} | "
            f"{VARIANT_PURPOSES.get(spec.variant, spec.variant.replace('_', ' '))} | "
            f"{routing} | `{csv_name}` |"
        )
    lines.extend(
        [
            "",
            "## CSV sets",
            "",
            f"- `sample_labels.csv`: {len(SAMPLE_LABELS)} clean-to-moderate examples across categories.",
            f"- `failing_labels.csv`: {len(FAILING_LABELS)} compliance failures and severe OCR cases.",
            f"- `batch_mixed.csv`: all {len(LABELS)} images for full-batch evaluation.",
            "",
            "The CSVs retain the original take-home schema for compatibility. Image distortion may",
            "cause OCR-dependent routing even when the synthetic application row matches the artwork.",
            "",
        ]
    )
    content = "\n".join(lines)
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
