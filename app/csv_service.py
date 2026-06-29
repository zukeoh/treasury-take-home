"""Safe, in-memory parsing of application data supplied as CSV."""

from __future__ import annotations

import csv
import io
import re

from pydantic import ValidationError

from app.config import LEGACY_CSV_COLUMNS, REQUIRED_CSV_COLUMNS
from app.models import ApplicationData


class CsvValidationError(ValueError):
    """A CSV issue that is safe and useful to show to the user."""


def _parse_bool(value: str, row_number: int) -> bool:
    normalized = (value or "").strip().casefold()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0", ""}:
        return False
    raise CsvValidationError(
        f"Row {row_number}: imported must be true or false (received {value!r})."
    )


def _normalize_abv(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d+)?", value):
        return f"{value}% ABV"
    if re.fullmatch(r"\d{1,3}(?:\.\d+)?\s*%", value):
        return f"{value} ABV"
    return value


def parse_application_csv(data: bytes) -> dict[str, ApplicationData]:
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV must be UTF-8 encoded.") from exc

    try:
        reader = csv.DictReader(io.StringIO(content))
        headers = {header.strip() for header in (reader.fieldnames or []) if header}
    except csv.Error as exc:
        raise CsvValidationError(f"CSV could not be read: {exc}.") from exc

    if REQUIRED_CSV_COLUMNS.issubset(headers):
        schema = "simple"
    elif LEGACY_CSV_COLUMNS.issubset(headers):
        schema = "legacy"
    else:
        missing = sorted(REQUIRED_CSV_COLUMNS - headers)
        raise CsvValidationError(
            "CSV is missing required columns: " + ", ".join(missing) + ". "
            "Download a fresh sample CSV for the expected format."
        )

    applications: dict[str, ApplicationData] = {}
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise CsvValidationError(f"CSV could not be read: {exc}.") from exc
    if not rows:
        raise CsvValidationError("CSV has headers but no application rows.")

    for row_number, raw_row in enumerate(rows, start=2):
        if None in raw_row:
            raise CsvValidationError(
                f"Row {row_number}: row has more values than the CSV header. "
                "Quote fields that contain commas."
            )
        row = {(key or "").strip(): (value or "").strip() for key, value in raw_row.items()}
        file_name = row.get("file_name", "").replace("\\", "/").rsplit("/", 1)[-1]
        if not file_name:
            raise CsvValidationError(f"Row {row_number}: file_name is required.")
        key = file_name.casefold()
        if key in applications:
            raise CsvValidationError(f"Row {row_number}: duplicate file_name {file_name!r}.")
        try:
            if schema == "simple":
                country = row.get("country_of_origin", "")
                class_type = row.get("product_type", "")
                alcohol_content = _normalize_abv(row.get("abv", ""))
                producer = row.get("producer", "")
                imported = bool(country)
            else:
                country = row.get("country_of_origin", "")
                class_type = row.get("class_type", "")
                alcohol_content = row.get("alcohol_content", "")
                producer = row.get("bottler_name_address", "")
                imported = _parse_bool(row.get("imported", ""), row_number)
            applications[key] = ApplicationData(
                file_name=file_name,
                beverage_type=row.get("beverage_type") or None,
                brand_name=row.get("brand_name", ""),
                class_type=class_type,
                alcohol_content=alcohol_content,
                net_contents=row.get("net_contents", ""),
                bottler_name_address=producer,
                country_of_origin=country,
                imported=imported,
                beer_special_disclosure=row.get("beer_special_disclosure", ""),
                wine_appellation=row.get("wine_appellation", ""),
                wine_sulfite_declaration=row.get("wine_sulfite_declaration", ""),
                spirits_age_statement=row.get("spirits_age_statement", ""),
                spirits_commodity_statement=row.get("spirits_commodity_statement", ""),
            )
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            raise CsvValidationError(f"Row {row_number}: {details}.") from exc
    return applications
