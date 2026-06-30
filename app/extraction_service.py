"""Expected-value-guided extraction from noisy OCR fragments."""

from __future__ import annotations

import re
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
    expected_measures = extract_alcohol_measures(expected)
    selected: list[str] = []
    for unit in ("abv", "proof"):
        candidates = [getattr(measure, unit) for measure in found if getattr(measure, unit) is not None]
        expected_values = [
            getattr(measure, unit)
            for measure in expected_measures
            if getattr(measure, unit) is not None
        ]
        tolerance = 0.15 if unit == "abv" else 0.3
        exact_candidate = next(
            (
                candidate
                for candidate in candidates
                if any(abs(candidate - target) <= tolerance for target in expected_values)
            ),
            None,
        )
        if exact_candidate is not None:
            value = exact_candidate
        else:
            marker_seen = (
                bool(re.search(r"%|\babv\b|\balc", text, re.I))
                if unit == "abv"
                else bool(re.search(r"\bproof\b", text, re.I))
            )
            separated_target = next(
                (target for target in expected_values if marker_seen and _number_seen(text, target)),
                None,
            )
            if separated_target is not None:
                value = separated_target
            elif candidates:
                value = min(
                    candidates,
                    key=lambda candidate: min(
                        (abs(candidate - target) for target in expected_values), default=0
                    ),
                )
            else:
                continue
        selected.append(f"{human_number(value)}% ABV" if unit == "abv" else f"{human_number(value)} proof")
    return ", ".join(selected)


def _number_seen(text: str, value: float) -> bool:
    rendered = human_number(value)
    if "." in rendered:
        whole, fraction = rendered.split(".", 1)
        pattern = rf"(?<!\d){re.escape(whole)}[.,]{re.escape(fraction)}(?!\d)"
    else:
        pattern = rf"(?<!\d){re.escape(rendered)}(?!\d)"
    return bool(re.search(pattern, text))


def _separated_net_contents_evidence(text: str, source: str) -> bool:
    match = re.search(
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|cl)\b",
        source,
        re.I,
    )
    if not match:
        return False
    value = float(match.group("value").replace(",", "."))
    unit = match.group("unit").casefold()
    tokens = set(normalize_text(text).split())
    if unit == "ml" or unit.startswith("millilit"):
        unit_seen = bool(tokens & {"ml", "milliliter", "milliliters", "millilitre", "millilitres"})
    elif unit == "cl":
        unit_seen = "cl" in tokens
    else:
        unit_seen = bool(tokens & {"l", "liter", "liters", "litre", "litres"})
    return unit_seen and _number_seen(text, value)


def _best_net_contents(text: str, expected: str) -> str:
    found = extract_net_contents(text)
    expected_values = extract_net_contents(expected)
    expected_ml = expected_values[0].milliliters if expected_values else None
    if expected_ml is not None:
        exact = next(
            (item for item in found if abs(item.milliliters - expected_ml) <= 1),
            None,
        )
        if exact is not None:
            return exact.source
        if expected_values and _separated_net_contents_evidence(text, expected_values[0].source):
            return expected_values[0].source
    if not found:
        return ""
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
