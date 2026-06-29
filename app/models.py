"""Typed data contracts shared by extraction, verification, and presentation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS REVIEW"


class BeverageType(str, Enum):
    BEER_MALT = "beer_malt"
    WINE = "wine"
    DISTILLED_SPIRITS = "distilled_spirits"


class ApplicationData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    file_name: str | None = None
    beverage_type: BeverageType | None = None
    brand_name: str = Field(min_length=1)
    class_type: str = Field(min_length=1)
    alcohol_content: str = Field(min_length=1)
    net_contents: str = Field(min_length=1)
    bottler_name_address: str = Field(min_length=1)
    country_of_origin: str = ""
    imported: bool = False
    beer_special_disclosure: str = ""
    wine_appellation: str = ""
    wine_sulfite_declaration: str = ""
    spirits_age_statement: str = ""
    spirits_commodity_statement: str = ""

    @field_validator("file_name")
    @classmethod
    def clean_file_name(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @model_validator(mode="after")
    def infer_type_and_validate_import(self) -> "ApplicationData":
        if self.beverage_type is None:
            normalized = self.class_type.casefold()
            if any(term in normalized for term in ("beer", "ale", "lager", "malt", "porter", "stout", "ipa")):
                self.beverage_type = BeverageType.BEER_MALT
            elif any(term in normalized for term in ("wine", "cabernet", "chardonnay", "merlot", "pinot", "riesling", "champagne")):
                self.beverage_type = BeverageType.WINE
            elif any(term in normalized for term in ("bourbon", "brandy", "gin", "rum", "tequila", "vodka", "whiskey", "whisky", "distilled spirits")):
                self.beverage_type = BeverageType.DISTILLED_SPIRITS
        if self.imported and not self.country_of_origin:
            raise ValueError("country_of_origin is required when imported is true")
        return self


class OcrFragment(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class OcrResult(BaseModel):
    fragments: list[OcrFragment] = Field(default_factory=list)
    text: str = ""
    average_confidence: float = Field(default=0, ge=0, le=1)
    used_enhanced_pass: bool = False


class FieldResult(BaseModel):
    field: str
    expected: str | None
    detected: str | None
    status: Status
    explanation: str
    requirement_basis: str = ""
    source_name: str = ""
    source_url: str = ""
    affects_overall: bool = True


class LabelResult(BaseModel):
    file_name: str
    status: Status
    application: ApplicationData | None = None
    image_preview_url: str | None = None
    processing_time_ms: int = 0
    confidence: float = 0
    fields: list[FieldResult] = Field(default_factory=list)
    extracted_text: str = ""
    error: str | None = None
