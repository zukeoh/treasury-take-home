from app.config import GOVERNMENT_WARNING
from app.models import Status
from app.warning_validator import (
    government_warning_required,
    validate_government_warning,
    warning_physical_review,
)


def test_exact_warning_passes() -> None:
    result = validate_government_warning(GOVERNMENT_WARNING)
    assert result.status == Status.PASS


def test_title_case_heading_needs_review() -> None:
    text = GOVERNMENT_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    result = validate_government_warning(text)
    assert result.status == Status.NEEDS_REVIEW


def test_missing_warning_fails() -> None:
    result = validate_government_warning("OLD TOM DISTILLERY 45% ABV")
    assert result.status == Status.FAIL


def test_scrambled_warning_words_need_review_instead_of_passing_or_failing() -> None:
    words = GOVERNMENT_WARNING.replace("GOVERNMENT WARNING:", "").split()
    scrambled = "WARNING GOVERNMENT " + " ".join(reversed(words))

    result = validate_government_warning(scrambled)

    assert result.status == Status.NEEDS_REVIEW
    assert "reading order was unreliable" in result.explanation


def test_exact_warning_with_low_confidence_needs_review() -> None:
    result = validate_government_warning(GOVERNMENT_WARNING, confidence=0.42)
    assert result.status == Status.NEEDS_REVIEW
    assert "low OCR confidence" in result.explanation


def test_warning_is_required_at_point_five_percent() -> None:
    assert government_warning_required("0.5% ABV", "0.5% ABV") is True


def test_warning_is_not_required_for_zero_abv_or_non_alcoholic_text() -> None:
    assert government_warning_required("0.0% ABV", "0.0% ABV") is False
    assert government_warning_required("45% ABV", "NON-ALCOHOLIC") is False


def test_physical_format_review_is_visible_but_informational() -> None:
    result = warning_physical_review()
    assert result.status == Status.NEEDS_REVIEW
    assert result.affects_overall is False
    assert "scale metadata" in result.explanation
