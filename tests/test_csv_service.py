import pytest

from app.csv_service import CsvValidationError, parse_application_csv
from app.models import BeverageType


HEADERS = (
    "file_name,brand_name,class_type,alcohol_content,net_contents,"
    "bottler_name_address,country_of_origin,imported\n"
)

SIMPLE_HEADERS = (
    "file_name,brand_name,product_type,abv,net_contents,producer,country_of_origin\n"
)


def test_parses_plain_language_csv_and_infers_import() -> None:
    content = SIMPLE_HEADERS + (
        'casa.png,Casa Azul,Tequila,40,750 mL,"Importer, Austin, TX",Mexico\n'
    )
    rows = parse_application_csv(content.encode())
    assert rows["casa.png"].class_type == "Tequila"
    assert rows["casa.png"].alcohol_content == "40% ABV"
    assert rows["casa.png"].imported is True


def test_parses_valid_imported_application() -> None:
    content = HEADERS + (
        'casa.png,CASA AZUL,Tequila,40% ABV,750 mL,"Importer, Austin, TX",Mexico,true\n'
    )
    rows = parse_application_csv(content.encode())
    assert rows["casa.png"].imported is True
    assert rows["casa.png"].country_of_origin == "Mexico"


def test_reports_missing_columns() -> None:
    with pytest.raises(CsvValidationError, match="missing required columns"):
        parse_application_csv(b"file_name,brand_name\nlabel.png,TEST\n")


def test_rejects_import_without_country() -> None:
    content = HEADERS + "casa.png,CASA,Tequila,40% ABV,750 mL,Importer,,true\n"
    with pytest.raises(CsvValidationError, match="country_of_origin"):
        parse_application_csv(content.encode())


def test_explains_unquoted_extra_csv_values() -> None:
    content = HEADERS + "label.png,BRAND,Whiskey,45% ABV,750 mL,Producer, City,,false\n"
    with pytest.raises(CsvValidationError, match="more values than the CSV header"):
        parse_application_csv(content.encode())


@pytest.mark.parametrize(
    ("product_type", "expected"),
    [
        ("American Single Malt Whiskey", BeverageType.DISTILLED_SPIRITS),
        ("German-Style Pilsner", BeverageType.BEER_MALT),
        ("Farmhouse Saison", BeverageType.BEER_MALT),
        ("American Malt Liquor", BeverageType.BEER_MALT),
        ("Sauvignon Blanc", BeverageType.WINE),
        ("Sake", BeverageType.WINE),
        ("Red Blend", BeverageType.WINE),
    ],
)
def test_infers_beverage_type_without_misclassifying_single_malt_whiskey(
    product_type: str,
    expected: BeverageType,
) -> None:
    content = SIMPLE_HEADERS + (
        f'label.png,TEST,{product_type},40,750 mL,"Producer, City, ST",\n'
    )

    rows = parse_application_csv(content.encode())

    assert rows["label.png"].beverage_type == expected
