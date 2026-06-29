from app.normalizer import extract_alcohol_measures, extract_net_contents, normalize_text, similarity


def test_punctuation_and_case_do_not_change_normalized_brand() -> None:
    assert normalize_text("STONE'S THROW") == normalize_text("Stone’s Throw")
    assert similarity("STONE'S THROW", "Stone's Throw") == 100


def test_complete_token_reordering_matches_but_missing_words_are_penalized() -> None:
    assert similarity("BAYVIEW SPICED RUM", "RUM SPICED BAYVIEW") == 100
    assert similarity("BAYVIEW SPICED RUM", "SPICED BAYVIEW") < 82


def test_alcohol_formats_are_parsed() -> None:
    measures = extract_alcohol_measures("45% Alc./Vol. (90 Proof)")
    assert any(item.abv == 45 for item in measures)
    assert any(item.proof == 90 for item in measures)


def test_zero_abv_is_parsed_for_non_alcoholic_products() -> None:
    measures = extract_alcohol_measures("0.0% ABV")
    assert any(item.abv == 0 for item in measures)


def test_volume_units_are_normalized_to_milliliters() -> None:
    assert extract_net_contents("750 mL")[0].milliliters == 750
    assert extract_net_contents("0.75 liter")[0].milliliters == 750
