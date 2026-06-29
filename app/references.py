"""Central TTB reference catalog and beverage-type source selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TtbReference:
    key: str
    name: str
    short_name: str
    url: str


BEER_REFERENCE = TtbReference(
    key="beer",
    name="TTB Malt Beverage Labeling",
    short_name="Beer / Malt Beverage",
    url="https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling",
)
SPIRITS_REFERENCE = TtbReference(
    key="spirits",
    name="TTB Distilled Spirits Labeling",
    short_name="Distilled Spirits",
    url="https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling",
)
WINE_REFERENCE = TtbReference(
    key="wine",
    name="TTB Wine Labeling",
    short_name="Wine",
    url="https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling",
)
BEER_HEALTH_WARNING_REFERENCE = TtbReference(
    key="beer-health-warning",
    name="TTB Malt Beverage Health Warning",
    short_name="Beer Health Warning",
    url=(
        "https://www.ttb.gov/regulated-commodities/beverage-alcohol/"
        "beer/labeling/malt-beverage-health-warning"
    ),
)
SPIRITS_HEALTH_WARNING_REFERENCE = TtbReference(
    key="spirits-health-warning",
    name="TTB Distilled Spirits Health Warning",
    short_name="Spirits Health Warning",
    url=(
        "https://www.ttb.gov/regulated-commodities/beverage-alcohol/"
        "distilled-spirits/ds-labeling-home/ds-health-warning"
    ),
)
WINE_HEALTH_WARNING_REFERENCE = TtbReference(
    key="wine-health-warning",
    name="TTB Wine Health Warning",
    short_name="Wine Health Warning",
    url=(
        "https://www.ttb.gov/regulated-commodities/beverage-alcohol/"
        "wine/labeling-wine/wine-labeling-health-warning-statement"
    ),
)

TTB_REFERENCES = (
    BEER_REFERENCE,
    SPIRITS_REFERENCE,
    WINE_REFERENCE,
    BEER_HEALTH_WARNING_REFERENCE,
    SPIRITS_HEALTH_WARNING_REFERENCE,
    WINE_HEALTH_WARNING_REFERENCE,
)

TTB_REFERENCE_GROUPS = (
    ("Beer / Malt Beverage", (BEER_REFERENCE, BEER_HEALTH_WARNING_REFERENCE)),
    ("Wine", (WINE_REFERENCE, WINE_HEALTH_WARNING_REFERENCE)),
    ("Distilled Spirits", (SPIRITS_REFERENCE, SPIRITS_HEALTH_WARNING_REFERENCE)),
)

BEER_TERMS = {
    "ale",
    "beer",
    "ipa",
    "lager",
    "malt beverage",
    "porter",
    "stout",
}
WINE_TERMS = {
    "cabernet",
    "champagne",
    "chardonnay",
    "merlot",
    "pinot",
    "riesling",
    "rose",
    "rosé",
    "sauvignon",
    "wine",
}
SPIRITS_TERMS = {
    "bourbon",
    "brandy",
    "distilled spirits",
    "gin",
    "rum",
    "tequila",
    "vodka",
    "whiskey",
    "whisky",
}


def reference_for_product_type(product_type: str) -> TtbReference | None:
    normalized = product_type.casefold()
    if any(term in normalized for term in BEER_TERMS):
        return BEER_REFERENCE
    if any(term in normalized for term in WINE_TERMS):
        return WINE_REFERENCE
    if any(term in normalized for term in SPIRITS_TERMS):
        return SPIRITS_REFERENCE
    return None


def reference_for_beverage_type(beverage_type: str | None) -> TtbReference | None:
    return {
        "beer_malt": BEER_REFERENCE,
        "wine": WINE_REFERENCE,
        "distilled_spirits": SPIRITS_REFERENCE,
    }.get(beverage_type or "")


def health_reference_for_product_type(product_type: str) -> TtbReference | None:
    reference = reference_for_product_type(product_type)
    if reference == BEER_REFERENCE:
        return BEER_HEALTH_WARNING_REFERENCE
    if reference == WINE_REFERENCE:
        return WINE_HEALTH_WARNING_REFERENCE
    if reference == SPIRITS_REFERENCE:
        return SPIRITS_HEALTH_WARNING_REFERENCE
    return None


def health_reference_for_beverage_type(beverage_type: str | None) -> TtbReference | None:
    return {
        "beer_malt": BEER_HEALTH_WARNING_REFERENCE,
        "wine": WINE_HEALTH_WARNING_REFERENCE,
        "distilled_spirits": SPIRITS_HEALTH_WARNING_REFERENCE,
    }.get(beverage_type or "")
