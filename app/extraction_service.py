"""Expected-value-guided extraction from noisy OCR fragments."""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz.fuzz import WRatio

from app.models import ApplicationData, OcrResult
from app.normalizer import (
    extract_alcohol_measures,
    extract_net_contents,
    human_number,
    normalize_text,
)


@dataclass(frozen=True)
class ExtractedFields:
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler_name_address: str
    country_of_origin: str
    beer_special_disclosure: str
    wine_appellation: str
    wine_sulfite_declaration: str
    spirits_age_statement: str
    spirits_commodity_statement: str


def _best_window(ocr: OcrResult, expected: str, max_fragments: int) -> str:
    if not expected or not ocr.fragments:
        return ""
    texts = [fragment.text for fragment in ocr.fragments]
    expected_normalized = normalize_text(expected)
    expected_tokens = set(expected_normalized.split())
    best_candidate = ""
    best_score = 0.0
    for size in range(1, min(max_fragments, len(texts)) + 1):
        for start in range(0, len(texts) - size + 1):
            candidate = " ".join(texts[start : start + size])
            candidate_normalized = normalize_text(candidate)
            candidate_tokens = set(candidate_normalized.split())
            coverage = (
                len(expected_tokens & candidate_tokens) / len(expected_tokens)
                if expected_tokens
                else 0.0
            )
            # WRatio intentionally favors useful partial matches, but that can make a
            # short brand fragment beat the complete producer/address line. Reward
            # coverage so explanations show the most complete matching OCR window.
            score = float(WRatio(expected_normalized, candidate_normalized)) * (
                0.55 + (0.45 * coverage)
            )
            if score > best_score:
                best_candidate = candidate
                best_score = score

    # Skewed or multi-column artwork can make OCR return correct words in a
    # non-reading order. Collect only fragments that add previously unseen
    # expected tokens, bounded by the same field-specific fragment limit.
    remaining_tokens = set(expected_tokens)
    selected_indexes: list[int] = []
    available_indexes = set(range(len(ocr.fragments)))
    while remaining_tokens and available_indexes and len(selected_indexes) < max_fragments:
        best_index = max(
            available_indexes,
            key=lambda index: (
                len(set(normalize_text(ocr.fragments[index].text).split()) & remaining_tokens),
                ocr.fragments[index].confidence,
                -index,
            ),
        )
        new_tokens = set(normalize_text(ocr.fragments[best_index].text).split()) & remaining_tokens
        if not new_tokens:
            break
        selected_indexes.append(best_index)
        available_indexes.remove(best_index)
        remaining_tokens -= new_tokens
    if selected_indexes:
        candidate = " ".join(texts[index] for index in sorted(selected_indexes))
        candidate_normalized = normalize_text(candidate)
        candidate_tokens = set(candidate_normalized.split())
        coverage = len(expected_tokens & candidate_tokens) / len(expected_tokens)
        score = float(WRatio(expected_normalized, candidate_normalized)) * (
            0.55 + (0.45 * coverage)
        )
        if score > best_score:
            best_candidate = candidate
    return best_candidate


def _best_alcohol(text: str, expected: str) -> str:
    found = extract_alcohol_measures(text)
    if not found:
        return ""
    expected_measures = extract_alcohol_measures(expected)
    selected: list[str] = []
    for unit in ("abv", "proof"):
        candidates = [getattr(measure, unit) for measure in found if getattr(measure, unit) is not None]
        if not candidates:
            continue
        expected_values = [
            getattr(measure, unit)
            for measure in expected_measures
            if getattr(measure, unit) is not None
        ]
        value = min(
            candidates,
            key=lambda candidate: min(
                (abs(candidate - target) for target in expected_values), default=0
            ),
        )
        selected.append(f"{human_number(value)}% ABV" if unit == "abv" else f"{human_number(value)} proof")
    return ", ".join(selected)


def _best_net_contents(text: str, expected: str) -> str:
    found = extract_net_contents(text)
    if not found:
        return ""
    expected_values = extract_net_contents(expected)
    expected_ml = expected_values[0].milliliters if expected_values else None
    selected = min(
        found,
        key=lambda item: abs(item.milliliters - expected_ml) if expected_ml is not None else 0,
    )
    return selected.source


def extract_fields(ocr: OcrResult, application: ApplicationData) -> ExtractedFields:
    return ExtractedFields(
        brand_name=_best_window(ocr, application.brand_name, 3),
        class_type=_best_window(ocr, application.class_type, 3),
        alcohol_content=_best_alcohol(ocr.text, application.alcohol_content),
        net_contents=_best_net_contents(ocr.text, application.net_contents),
        bottler_name_address=_best_window(ocr, application.bottler_name_address, 4),
        country_of_origin=(
            _best_window(ocr, application.country_of_origin, 2)
            if application.imported
            else "Not required"
        ),
        beer_special_disclosure=_best_window(ocr, application.beer_special_disclosure, 4),
        wine_appellation=_best_window(ocr, application.wine_appellation, 3),
        wine_sulfite_declaration=_best_window(ocr, application.wine_sulfite_declaration, 3),
        spirits_age_statement=_best_window(ocr, application.spirits_age_statement, 4),
        spirits_commodity_statement=_best_window(ocr, application.spirits_commodity_statement, 5),
    )
