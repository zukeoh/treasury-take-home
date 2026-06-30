"""Explainable, deterministic verification rules for extracted label fields."""

from __future__ import annotations

from app.extraction_service import ExtractedFields
from app.models import ApplicationData, BeverageType, FieldResult, OcrResult, Status
from app.normalizer import extract_alcohol_measures, extract_net_contents, similarity
from app.references import (
    health_reference_for_beverage_type,
    health_reference_for_product_type,
    reference_for_beverage_type,
    reference_for_product_type,
)
from app.warning_validator import (
    government_warning_required,
    validate_government_warning,
    warning_not_required_result,
    warning_ocr_confidence,
    warning_physical_review,
)


FIELD_REQUIREMENT_BASIS = {
    "Brand Name": "Brand name on the label should match the submitted application data.",
    "Class / Type": "Class or type designation should identify the beverage and match the application.",
    "Alcohol Content": "Alcohol content must use an accepted statement and match the application value.",
    "Net Contents": "Net contents must be stated on the label and match the application quantity.",
    "Bottler / Producer": "Required bottler, producer, or importer name and address should match the application.",
    "Country of Origin": "Country of origin is conditionally required for imported products.",
    "Beer / Malt Beverage Special Disclosure": "Sulfites, aspartame, color additives, and certain other disclosures are required when applicable.",
    "Wine Appellation of Origin": "An appellation of origin is required for wine labels in specified circumstances.",
    "Wine Sulfite Declaration": "Wine containing 10 or more parts per million sulfur dioxide must bear a sulfite declaration.",
    "Distilled Spirits Age Statement": "An age statement is required for specified distilled spirits classes and circumstances.",
    "Distilled Spirits Commodity Statement": "A commodity or composition statement is required for specified distilled spirits products.",
}
OCR_INCONCLUSIVE_THRESHOLD = 0.55


def _annotate_results(application: ApplicationData, fields: list[FieldResult]) -> list[FieldResult]:
    beverage_type = application.beverage_type.value if application.beverage_type else None
    beverage_reference = (
        reference_for_beverage_type(beverage_type)
        or reference_for_product_type(application.class_type)
    )
    health_reference = (
        health_reference_for_beverage_type(beverage_type)
        or health_reference_for_product_type(application.class_type)
    )
    for field in fields:
        if not field.requirement_basis:
            field.requirement_basis = FIELD_REQUIREMENT_BASIS.get(
                field.field,
                "Common alcohol beverage labeling requirement checked by this prototype.",
            )
        if not field.source_url:
            is_warning = field.field in {
                "Government Health Warning",
                "Warning Typography & Physical Size",
            }
            reference = health_reference if is_warning else beverage_reference
            if reference is not None:
                field.source_name = reference.name
                field.source_url = reference.url
    return fields


def _specific_field_values(application: ApplicationData) -> list[tuple[str, str, str]]:
    if application.beverage_type == BeverageType.BEER_MALT:
        return [
            (
                "Beer / Malt Beverage Special Disclosure",
                application.beer_special_disclosure,
                "beer_special_disclosure",
            )
        ]
    if application.beverage_type == BeverageType.WINE:
        return [
            ("Wine Appellation of Origin", application.wine_appellation, "wine_appellation"),
            (
                "Wine Sulfite Declaration",
                application.wine_sulfite_declaration,
                "wine_sulfite_declaration",
            ),
        ]
    if application.beverage_type == BeverageType.DISTILLED_SPIRITS:
        return [
            (
                "Distilled Spirits Age Statement",
                application.spirits_age_statement,
                "spirits_age_statement",
            ),
            (
                "Distilled Spirits Commodity Statement",
                application.spirits_commodity_statement,
                "spirits_commodity_statement",
            ),
        ]
    return []


def _fuzzy_result(
    field: str,
    expected: str,
    detected: str,
    pass_threshold: float,
    review_threshold: float,
    ocr_confidence: float = 1.0,
) -> FieldResult:
    if not detected:
        inconclusive = ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD
        return FieldResult(
            field=field,
            expected=expected,
            detected="Not detected",
            status=Status.NEEDS_REVIEW if inconclusive else Status.FAIL,
            explanation=(
                f"OCR confidence was too low to establish the {field.casefold()}; review the image manually."
                if inconclusive
                else f"No readable {field.casefold()} matched the application."
            ),
        )
    score = similarity(expected, detected)
    if score >= pass_threshold:
        status = Status.PASS
        explanation = f"Matched the application after normalizing case, punctuation, and spacing ({score:.0f}%)."
    elif score >= review_threshold:
        status = Status.NEEDS_REVIEW
        explanation = f"A possible match was found, but it is ambiguous ({score:.0f}%)."
    elif ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD:
        status = Status.NEEDS_REVIEW
        explanation = (
            f"The possible match scored {score:.0f}%, but OCR confidence was low; "
            "review the image manually before treating it as a mismatch."
        )
    else:
        status = Status.FAIL
        explanation = f"Detected text materially differs from the application ({score:.0f}% match)."
    return FieldResult(
        field=field,
        expected=expected,
        detected=detected,
        status=status,
        explanation=explanation,
    )


def _alcohol_result(expected: str, detected: str, ocr_confidence: float = 1.0) -> FieldResult:
    expected_values = extract_alcohol_measures(expected)
    detected_values = extract_alcohol_measures(detected)
    if not expected_values:
        return FieldResult(
            field="Alcohol Content",
            expected=expected,
            detected=detected or "Not detected",
            status=Status.NEEDS_REVIEW,
            explanation="The application alcohol content could not be normalized; compare it manually.",
        )
    if not detected_values:
        inconclusive = ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD
        return FieldResult(
            field="Alcohol Content",
            expected=expected,
            detected="Not detected",
            status=Status.NEEDS_REVIEW if inconclusive else Status.FAIL,
            explanation=(
                "OCR confidence was too low to establish the alcohol statement; review it manually."
                if inconclusive
                else "No alcohol-by-volume or proof statement was detected."
            ),
        )

    checks: list[bool] = []
    for wanted in expected_values:
        if wanted.abv is not None:
            checks.append(any(
                found.abv is not None and abs(found.abv - wanted.abv) <= 0.15
                for found in detected_values
            ))
        if wanted.proof is not None:
            checks.append(any(
                found.proof is not None and abs(found.proof - wanted.proof) <= 0.3
                for found in detected_values
            ))
    if checks and all(checks):
        status = Status.PASS
        explanation = "Alcohol value and stated unit match the application."
    elif any(checks):
        status = Status.NEEDS_REVIEW
        explanation = "One alcohol measure matches, but another expected measure was not readable."
    else:
        status = (
            Status.NEEDS_REVIEW
            if ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD
            else Status.FAIL
        )
        explanation = (
            "OCR confidence was low and the detected alcohol value is inconclusive; review it manually."
            if status == Status.NEEDS_REVIEW
            else "Detected alcohol value does not match the application."
        )
    return FieldResult(
        field="Alcohol Content",
        expected=expected,
        detected=detected,
        status=status,
        explanation=explanation,
    )


def _net_contents_result(expected: str, detected: str, ocr_confidence: float = 1.0) -> FieldResult:
    expected_values = extract_net_contents(expected)
    detected_values = extract_net_contents(detected)
    if not expected_values:
        return FieldResult(
            field="Net Contents",
            expected=expected,
            detected=detected or "Not detected",
            status=Status.NEEDS_REVIEW,
            explanation="The application quantity could not be normalized; compare it manually.",
        )
    if not detected_values:
        inconclusive = ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD
        return FieldResult(
            field="Net Contents",
            expected=expected,
            detected="Not detected",
            status=Status.NEEDS_REVIEW if inconclusive else Status.FAIL,
            explanation=(
                "OCR confidence was too low to establish net contents; review it manually."
                if inconclusive
                else "No supported net contents statement was detected."
            ),
        )
    matches = any(
        abs(wanted.milliliters - found.milliliters) <= 1
        for wanted in expected_values
        for found in detected_values
    )
    inconclusive = not matches and ocr_confidence < OCR_INCONCLUSIVE_THRESHOLD
    return FieldResult(
        field="Net Contents",
        expected=expected,
        detected=detected,
        status=(Status.PASS if matches else Status.NEEDS_REVIEW if inconclusive else Status.FAIL),
        explanation=(
            "Quantity matches after converting equivalent units."
            if matches
            else (
                "OCR confidence was low and the detected quantity is inconclusive; review it manually."
                if inconclusive
                else "Detected quantity does not match the application."
            )
        ),
    )


def verify_application(
    application: ApplicationData,
    extracted: ExtractedFields,
    ocr: OcrResult,
) -> tuple[Status, list[FieldResult]]:
    fields = [
        _fuzzy_result("Brand Name", application.brand_name, extracted.brand_name, 82, 62, ocr.average_confidence),
        _fuzzy_result("Class / Type", application.class_type, extracted.class_type, 78, 58, ocr.average_confidence),
        _alcohol_result(application.alcohol_content, extracted.alcohol_content, ocr.average_confidence),
        _net_contents_result(application.net_contents, extracted.net_contents, ocr.average_confidence),
        _fuzzy_result(
            "Bottler / Producer",
            application.bottler_name_address,
            extracted.bottler_name_address,
            68,
            48,
            ocr.average_confidence,
        ),
    ]
    if application.imported:
        fields.append(
            _fuzzy_result(
                "Country of Origin",
                application.country_of_origin,
                extracted.country_of_origin,
                82,
                62,
                ocr.average_confidence,
            )
        )
    else:
        fields.append(
            FieldResult(
                field="Country of Origin",
                expected="Not required — application is not imported",
                detected="Not required",
                status=Status.PASS,
                explanation="Country of origin is only required by this prototype for imported products.",
            )
        )
    for field, expected, attribute in _specific_field_values(application):
        if expected:
            fields.append(
                _fuzzy_result(
                    field,
                    expected,
                    getattr(extracted, attribute),
                    78,
                    58,
                    ocr.average_confidence,
                )
            )
    warning_required = government_warning_required(application.alcohol_content, ocr.text)
    if warning_required:
        fields.append(
            validate_government_warning(ocr.text, warning_ocr_confidence(ocr))
        )
        fields.append(warning_physical_review())
    else:
        fields.append(warning_not_required_result(ocr.text))
    consequential = [field for field in fields if field.affects_overall]
    if any(field.status == Status.FAIL for field in consequential):
        overall = Status.FAIL
    elif any(field.status == Status.NEEDS_REVIEW for field in consequential):
        overall = Status.NEEDS_REVIEW
    else:
        overall = Status.PASS
    return overall, _annotate_results(application, fields)


def unreadable_fields(application: ApplicationData) -> list[FieldResult]:
    expected = {
        "Brand Name": application.brand_name,
        "Class / Type": application.class_type,
        "Alcohol Content": application.alcohol_content,
        "Net Contents": application.net_contents,
        "Bottler / Producer": application.bottler_name_address,
        "Country of Origin": (
            application.country_of_origin if application.imported else "Not required"
        ),
    }
    for field, value, _ in _specific_field_values(application):
        if value:
            expected[field] = value
    fields = [
        FieldResult(
            field=field,
            expected=value,
            detected="Not readable",
            status=Status.NEEDS_REVIEW,
            explanation="OCR returned no usable text; request a clearer image or review manually.",
        )
        for field, value in expected.items()
    ]
    if government_warning_required(application.alcohol_content, ""):
        fields.append(
            FieldResult(
                field="Government Health Warning",
                expected="Required exact federal warning",
                detected="Not readable",
                status=Status.NEEDS_REVIEW,
                explanation="OCR returned no usable warning text; request a clearer image or review manually.",
                requirement_basis=(
                    "Common required warning for alcohol beverages containing at least 0.5% alcohol by volume."
                ),
            )
        )
        fields.append(warning_physical_review())
    else:
        fields.append(warning_not_required_result(""))
    return _annotate_results(application, fields)
