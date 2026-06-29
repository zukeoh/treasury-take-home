"""Strict wording and capitalization checks for the government warning."""

from __future__ import annotations

import re
from collections import Counter

from rapidfuzz.fuzz import partial_ratio

from app.config import GOVERNMENT_WARNING
from app.models import FieldResult, OcrResult, Status
from app.normalizer import extract_alcohol_measures, normalize_text


UPPERCASE_HEADER = re.compile(r"\bGOVERNMENT\s+WARNING\s*:")
ANYCASE_HEADER = re.compile(r"\bgovernment\s+warning\s*:?", re.I)
NON_ALCOHOLIC = re.compile(r"\b(?:non[-\s]?alcoholic|alcohol[-\s]?free)\b", re.I)
WARNING_CONFIDENCE_THRESHOLD = 0.55
PASS_WORDING_THRESHOLD = 98
TOKEN_COVERAGE_REVIEW_THRESHOLD = 0.55
WARNING_SOURCE = {
    "requirement_basis": (
        "Common required warning for alcohol beverages containing at least 0.5% alcohol by volume."
    ),
}
WARNING_TYPOGRAPHY_SOURCE = {
    "requirement_basis": (
        "Health-warning typography, continuous-paragraph layout, type size, and character-density rules."
    ),
}


def government_warning_required(application_alcohol: str, extracted_text: str) -> bool:
    """Determine whether the statutory warning is required at 0.5% ABV or above.

    Label OCR takes precedence when it clearly identifies a zero/low-alcohol product. Any
    detected value at or above the threshold keeps the warning required. The application
    value is the fallback when OCR cannot establish the alcohol level.
    """

    detected = extract_alcohol_measures(extracted_text)
    detected_abv = [measure.abv for measure in detected if measure.abv is not None]
    detected_proof = [measure.proof for measure in detected if measure.proof is not None]
    if any(value >= 0.5 for value in detected_abv) or any(value >= 1 for value in detected_proof):
        return True
    if detected_abv or detected_proof or NON_ALCOHOLIC.search(extracted_text):
        return False

    expected = extract_alcohol_measures(application_alcohol)
    return any(
        (measure.abv is not None and measure.abv >= 0.5)
        or (measure.proof is not None and measure.proof >= 1)
        for measure in expected
    )


def warning_ocr_confidence(ocr: OcrResult) -> float:
    """Estimate confidence from fragments likely to belong to the warning text."""

    required_tokens = set(normalize_text(GOVERNMENT_WARNING).split())
    weighted_total = 0.0
    token_total = 0
    for fragment in ocr.fragments:
        tokens = set(normalize_text(fragment.text).split())
        overlap = len(tokens & required_tokens)
        is_heading = "government" in tokens and "warning" in tokens
        if overlap >= 2 or is_heading:
            weight = max(1, overlap)
            weighted_total += fragment.confidence * weight
            token_total += weight
    return weighted_total / token_total if token_total else ocr.average_confidence


def warning_not_required_result(extracted_text: str) -> FieldResult:
    measures = extract_alcohol_measures(extracted_text)
    abv = next((measure.abv for measure in measures if measure.abv is not None), None)
    if abv is not None:
        detected = f"{abv:g}% ABV"
    elif NON_ALCOHOLIC.search(extracted_text):
        detected = "Non-alcoholic designation detected"
    else:
        detected = "Below 0.5% ABV per application data"
    return FieldResult(
        field="Government Health Warning",
        expected="Not required below 0.5% ABV",
        detected=detected,
        status=Status.PASS,
        explanation="A missing statutory warning does not fail a product below 0.5% ABV.",
        **WARNING_SOURCE,
    )


def warning_physical_review() -> FieldResult:
    return FieldResult(
        field="Warning Typography & Physical Size",
        expected=(
            "Continuous paragraph; required heading bold; body not bold; compliant type "
            "size and character density"
        ),
        detected="Cannot be determined reliably from this digital image",
        status=Status.NEEDS_REVIEW,
        explanation=(
            "Physical font size cannot be determined without scale metadata. Boldness, "
            "paragraph layout, and characters per inch also require image-layout analysis "
            "or human review. This informational item does not affect the automated result."
        ),
        affects_overall=False,
        **WARNING_TYPOGRAPHY_SOURCE,
    )


def validate_government_warning(
    extracted_text: str,
    confidence: float = 1.0,
) -> FieldResult:
    expected = GOVERNMENT_WARNING
    if not extracted_text.strip():
        return FieldResult(
            field="Government Health Warning",
            expected=expected,
            detected="Not detected",
            status=Status.FAIL,
            explanation="No warning text was readable in the label image.",
            **WARNING_SOURCE,
        )

    wording_score = float(
        partial_ratio(normalize_text(expected), normalize_text(extracted_text))
    )
    expected_tokens = Counter(normalize_text(expected).split())
    detected_tokens = Counter(normalize_text(extracted_text).split())
    matched_tokens = sum((expected_tokens & detected_tokens).values())
    token_coverage = matched_tokens / sum(expected_tokens.values())
    heading_tokens_present = {"government", "warning"}.issubset(detected_tokens)
    uppercase_header = bool(UPPERCASE_HEADER.search(extracted_text))
    any_header = ANYCASE_HEADER.search(extracted_text)
    detected = (
        f"Warning wording {wording_score:.0f}% similar; {token_coverage:.0%} required-word coverage; "
        + ("uppercase heading detected" if uppercase_header else "uppercase heading not confirmed")
    )

    if (
        wording_score >= PASS_WORDING_THRESHOLD
        and uppercase_header
        and confidence < WARNING_CONFIDENCE_THRESHOLD
    ):
        return FieldResult(
            field="Government Health Warning",
            expected=expected,
            detected=f"{detected}; {confidence:.0%} OCR confidence",
            status=Status.NEEDS_REVIEW,
            explanation=(
                "Government warning detected with low OCR confidence. Manual review recommended."
            ),
            **WARNING_SOURCE,
        )
    if wording_score >= PASS_WORDING_THRESHOLD and uppercase_header:
        return FieldResult(
            field="Government Health Warning",
            expected=expected,
            detected=detected,
            status=Status.PASS,
            explanation=(
                "Required wording and all-caps heading were detected anywhere on the uploaded "
                "label. Physical formatting is reported separately for manual review."
            ),
            **WARNING_SOURCE,
        )
    if token_coverage >= TOKEN_COVERAGE_REVIEW_THRESHOLD and heading_tokens_present:
        return FieldResult(
            field="Government Health Warning",
            expected=expected,
            detected=detected,
            status=Status.NEEDS_REVIEW,
            explanation=(
                "Most required warning words and both heading words were detected, but OCR "
                "reading order was unreliable. Confirm the exact wording and heading manually."
            ),
            **WARNING_SOURCE,
        )
    if wording_score >= 72 or (wording_score >= 60 and any_header):
        issue = (
            "the heading capitalization is questionable"
            if not uppercase_header
            else "the OCR wording is incomplete or uncertain"
        )
        return FieldResult(
            field="Government Health Warning",
            expected=expected,
            detected=detected,
            status=Status.NEEDS_REVIEW,
            explanation=f"Most warning content appears present, but {issue}.",
            **WARNING_SOURCE,
        )
    return FieldResult(
        field="Government Health Warning",
        expected=expected,
        detected=detected,
        status=Status.FAIL,
        explanation="The required warning is missing, materially incomplete, or substantially reworded.",
        **WARNING_SOURCE,
    )
