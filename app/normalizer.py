"""Normalization and parsing helpers for tolerant label comparisons."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from rapidfuzz.fuzz import ratio, token_set_ratio


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    # OCR commonly drops possessive apostrophes and returns STONES for STONE'S.
    # Treat those literal typography variants as equivalent before punctuation removal.
    value = re.sub(r"(?i)([a-z0-9])['’]s\b", r"\1s", value)
    value = value.casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    ordered_score = float(ratio(left_normalized, right_normalized))
    expected_tokens = Counter(left_normalized.split())
    detected_tokens = Counter(right_normalized.split())
    matched_tokens = sum((expected_tokens & detected_tokens).values())
    coverage = matched_tokens / sum(expected_tokens.values()) if expected_tokens else 0.0
    unordered_score = float(token_set_ratio(left_normalized, right_normalized)) * coverage
    return max(ordered_score, unordered_score)


@dataclass(frozen=True)
class AlcoholMeasure:
    abv: float | None = None
    proof: float | None = None


ABV_PATTERNS = (
    re.compile(r"(?P<value>\d{1,3}(?:[.,]\d+)?)\s*%\s*(?:alc(?:ohol)?\.?\s*/?\s*vol\.?|abv)?", re.I),
    re.compile(r"(?P<value>\d{1,3}(?:[.,]\d+)?)\s*percent\s+alcohol\s+by\s+volume", re.I),
)
PROOF_PATTERN = re.compile(r"(?P<value>\d{1,3}(?:[.,]\d+)?)\s*(?:°\s*)?proof\b", re.I)


def extract_alcohol_measures(value: str) -> list[AlcoholMeasure]:
    measures: list[AlcoholMeasure] = []
    for pattern in ABV_PATTERNS:
        for match in pattern.finditer(value or ""):
            number = float(match.group("value").replace(",", "."))
            if 0 <= number <= 100:
                measures.append(AlcoholMeasure(abv=number))
    for match in PROOF_PATTERN.finditer(value or ""):
        number = float(match.group("value").replace(",", "."))
        if 0 <= number <= 200:
            measures.append(AlcoholMeasure(proof=number))
    return measures


NET_CONTENTS_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|cl)\b",
    re.I,
)


@dataclass(frozen=True)
class NetContents:
    source: str
    milliliters: float


def extract_net_contents(value: str) -> list[NetContents]:
    values: list[NetContents] = []
    for match in NET_CONTENTS_PATTERN.finditer(value or ""):
        number = float(match.group("value").replace(",", "."))
        unit = match.group("unit").casefold()
        if unit == "cl":
            number *= 10
        elif unit == "l" or unit.startswith("lit"):
            number *= 1000
        if 0 < number <= 100_000:
            values.append(NetContents(match.group(0), number))
    return values


def human_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"
