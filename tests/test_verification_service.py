from app.config import GOVERNMENT_WARNING
from app.extraction_service import extract_fields
from app.models import ApplicationData, BeverageType, OcrFragment, OcrResult, Status
from app.verification_service import verify_application


def _application() -> ApplicationData:
    return ApplicationData(
        brand_name="Stone's Throw",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
        bottler_name_address="Old Tom Distillery, Louisville, KY",
    )


def _ocr(alcohol: str = "45% Alc./Vol. (90 Proof)") -> OcrResult:
    lines = [
        "STONE'S THROW",
        "Kentucky Straight Bourbon Whiskey",
        alcohol,
        "750ml",
        "Old Tom Distillery, Louisville, KY",
        GOVERNMENT_WARNING,
    ]
    return OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.95) for line in lines],
        text="\n".join(lines),
        average_confidence=0.95,
    )


def test_clean_label_passes_with_common_fields() -> None:
    application = _application()
    ocr = _ocr()
    status, fields = verify_application(application, extract_fields(ocr, application), ocr)
    assert status == Status.PASS
    assert all(field.field != "Commodity-specific Disclosures" for field in fields)
    typography = next(field for field in fields if field.field == "Warning Typography & Physical Size")
    assert typography.status == Status.NEEDS_REVIEW
    assert typography.affects_overall is False
    assert all(field.requirement_basis for field in fields)
    assert all(field.source_name for field in fields)
    assert all(field.source_url.startswith("https://www.ttb.gov/") for field in fields)
    brand = next(field for field in fields if field.field == "Brand Name")
    warning = next(field for field in fields if field.field == "Government Health Warning")
    assert brand.source_name == "TTB Distilled Spirits Labeling"
    assert warning.source_name == "TTB Distilled Spirits Health Warning"
    assert warning.source_url.endswith("/distilled-spirits/ds-labeling-home/ds-health-warning")


def test_wrong_alcohol_value_fails() -> None:
    application = _application()
    ocr = _ocr("40% Alc./Vol. (80 Proof)")
    status, _ = verify_application(application, extract_fields(ocr, application), ocr)
    assert status == Status.FAIL


def test_producer_extraction_prefers_complete_address_over_brand_fragment() -> None:
    application = ApplicationData(
        beverage_type=BeverageType.WINE,
        brand_name="Laurel Ridge",
        class_type="Red Wine",
        alcohol_content="13% ABV",
        net_contents="750 mL",
        bottler_name_address="Laurel Ridge Wines, Healdsburg, CA",
    )
    lines = [
        "LAUREL RIDGE",
        "RED WINE",
        "13% ABV",
        "750 mL",
        "PRODUCED AND BOTTLED BY",
        "LAUREL RIDGE WINES",
        "HEALDSBURG CA",
        GOVERNMENT_WARNING,
    ]
    ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.95) for line in lines],
        text="\n".join(lines),
        average_confidence=0.95,
    )

    extracted = extract_fields(ocr, application)

    assert extracted.bottler_name_address != "LAUREL RIDGE"
    assert "LAUREL RIDGE WINES" in extracted.bottler_name_address
    assert "HEALDSBURG CA" in extracted.bottler_name_address


def test_skewed_fragment_order_uses_complete_expected_tokens() -> None:
    application = ApplicationData(
        beverage_type=BeverageType.DISTILLED_SPIRITS,
        brand_name="BAYVIEW SPICED RUM",
        class_type="Spiced Rum",
        alcohol_content="35% ABV",
        net_contents="750 mL",
        bottler_name_address="Bayview Spirits Co., San Diego, CA",
    )
    fragments = [
        OcrFragment(text="Rum", confidence=0.72),
        OcrFragment(text="750 mL", confidence=0.99),
        OcrFragment(text="San Diego, CA", confidence=0.93),
        OcrFragment(text="Spirits Co", confidence=0.63),
        OcrFragment(text="RUM", confidence=0.99),
        OcrFragment(text="SPICED", confidence=0.99),
        OcrFragment(text="BAYVIEW", confidence=0.97),
        OcrFragment(text="Spiced", confidence=0.69),
        OcrFragment(text="35% ABV", confidence=0.99),
        OcrFragment(text="Bayview", confidence=0.61),
        OcrFragment(text=GOVERNMENT_WARNING, confidence=0.95),
    ]
    ocr = OcrResult(
        fragments=fragments,
        text="\n".join(fragment.text for fragment in fragments),
        average_confidence=0.9,
    )

    status, fields = verify_application(application, extract_fields(ocr, application), ocr)

    assert status == Status.PASS
    assert next(field for field in fields if field.field == "Brand Name").status == Status.PASS
    assert next(field for field in fields if field.field == "Class / Type").status == Status.PASS
    producer = next(field for field in fields if field.field == "Bottler / Producer")
    assert producer.status == Status.PASS
    assert "San Diego, CA" in producer.detected
    assert "Spirits Co" in producer.detected
    assert "bayview" in producer.detected.casefold()


def test_zero_abv_product_does_not_fail_for_missing_warning() -> None:
    application = ApplicationData(
        brand_name="Clear Day",
        class_type="Non-Alcoholic Malt Beverage",
        alcohol_content="0.0% ABV",
        net_contents="355 mL",
        bottler_name_address="Clear Day Brewing, Austin, TX",
    )
    lines = [
        "CLEAR DAY",
        "Non-Alcoholic Malt Beverage",
        "0.0% ABV",
        "355 mL",
        "Clear Day Brewing, Austin, TX",
    ]
    ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.95) for line in lines],
        text="\n".join(lines),
        average_confidence=0.95,
    )
    status, fields = verify_application(application, extract_fields(ocr, application), ocr)
    warning = next(field for field in fields if field.field == "Government Health Warning")
    assert warning.status == Status.PASS
    assert "Not required" in warning.expected
    assert status == Status.PASS
    brand = next(field for field in fields if field.field == "Brand Name")
    assert brand.source_name == "TTB Malt Beverage Labeling"
    assert warning.source_name == "TTB Malt Beverage Health Warning"


def test_warning_with_low_fragment_confidence_routes_to_review() -> None:
    application = _application()
    ocr = _ocr()
    ocr.fragments[-1].confidence = 0.35
    status, fields = verify_application(application, extract_fields(ocr, application), ocr)
    warning = next(field for field in fields if field.field == "Government Health Warning")
    assert warning.status == Status.NEEDS_REVIEW
    assert status == Status.NEEDS_REVIEW


def test_wine_specific_fields_are_verified_and_sourced() -> None:
    application = ApplicationData(
        beverage_type=BeverageType.WINE,
        brand_name="Hillside Cellars",
        class_type="Cabernet Sauvignon",
        alcohol_content="13.5% ABV",
        net_contents="750 mL",
        bottler_name_address="Hillside Cellars, Napa, CA",
        wine_appellation="Napa Valley",
        wine_sulfite_declaration="Contains sulfites",
    )
    lines = [
        "HILLSIDE CELLARS",
        "Cabernet Sauvignon",
        "13.5% ABV",
        "750 mL",
        "Hillside Cellars, Napa, CA",
        "Napa Valley",
        "Contains sulfites",
        GOVERNMENT_WARNING,
    ]
    ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.95) for line in lines],
        text="\n".join(lines),
        average_confidence=0.95,
    )
    status, fields = verify_application(application, extract_fields(ocr, application), ocr)
    appellation = next(field for field in fields if field.field == "Wine Appellation of Origin")
    sulfites = next(field for field in fields if field.field == "Wine Sulfite Declaration")
    assert status == Status.PASS
    assert appellation.status == Status.PASS
    assert sulfites.status == Status.PASS
    assert appellation.source_name == "TTB Wine Labeling"


def test_beer_and_spirits_specific_fields_are_verified() -> None:
    cases = [
        (
            ApplicationData(
                beverage_type=BeverageType.BEER_MALT,
                brand_name="North Star",
                class_type="Lager Beer",
                alcohol_content="5% ABV",
                net_contents="355 mL",
                bottler_name_address="North Star Brewing, Austin, TX",
                beer_special_disclosure="Contains sulfites",
            ),
            ["Contains sulfites"],
            ["Beer / Malt Beverage Special Disclosure"],
        ),
        (
            ApplicationData(
                beverage_type=BeverageType.DISTILLED_SPIRITS,
                brand_name="North Star",
                class_type="Straight Bourbon Whiskey",
                alcohol_content="45% ABV",
                net_contents="750 mL",
                bottler_name_address="North Star Distilling, Austin, TX",
                spirits_age_statement="Aged 4 years",
                spirits_commodity_statement="Distilled from grain",
            ),
            ["Aged 4 years", "Distilled from grain"],
            ["Distilled Spirits Age Statement", "Distilled Spirits Commodity Statement"],
        ),
    ]
    for application, specific_lines, field_names in cases:
        lines = [
            application.brand_name,
            application.class_type,
            application.alcohol_content,
            application.net_contents,
            application.bottler_name_address,
            *specific_lines,
            GOVERNMENT_WARNING,
        ]
        ocr = OcrResult(
            fragments=[OcrFragment(text=line, confidence=0.95) for line in lines],
            text="\n".join(lines),
            average_confidence=0.95,
        )
        status, fields = verify_application(application, extract_fields(ocr, application), ocr)
        assert status == Status.PASS
        for field_name in field_names:
            assert next(field for field in fields if field.field == field_name).status == Status.PASS
