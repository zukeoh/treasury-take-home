"""Parse filename-keyed manual application data submitted by the browser."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.models import ApplicationData


class ManualValidationError(ValueError):
    """A manual-form issue that is safe and useful to show to the user."""


def _validation_fields(exc: ValidationError) -> str:
    fields: set[str] = set()
    for error in exc.errors():
        location = error["loc"]
        if location:
            fields.add(str(location[-1]).replace("_", " "))
        elif "country_of_origin" in error["msg"]:
            fields.add("country of origin")
        else:
            fields.add("application data")
    return ", ".join(sorted(fields))


def parse_manual_applications(payload: str) -> dict[str, ApplicationData]:
    if not payload.strip():
        raise ManualValidationError(
            "Choose label images so the application fields can be created for each file."
        )
    try:
        records = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ManualValidationError("Manual application data could not be read. Try again.") from exc
    if not isinstance(records, list) or not records:
        raise ManualValidationError("Add application data for each selected label image.")

    applications: dict[str, ApplicationData] = {}
    for record_number, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            raise ManualValidationError(
                f"Application {record_number} is not formatted correctly."
            )
        file_name = Path(str(raw.get("file_name", ""))).name
        if not file_name:
            raise ManualValidationError(f"Application {record_number} is missing its file name.")
        key = file_name.casefold()
        if key in applications:
            raise ManualValidationError(f"Duplicate image file name {file_name!r}.")
        if not raw.get("beverage_type"):
            raise ManualValidationError(f"{file_name}: select a beverage type.")
        try:
            applications[key] = ApplicationData(**{**raw, "file_name": file_name})
        except ValidationError as exc:
            raise ManualValidationError(
                f"{file_name}: complete the required fields: {_validation_fields(exc)}."
            ) from exc
    return applications
