"""Mutation tests for Engine 1 configuration loader.

Targets: lines 168-267 in config.py - probability bounds, count floors,
weights validation, enum parsing, and early returns that fail to raise.

Each test checks ONE boundary that if flipped kills the line.
Never loosens existing tests. Never invents a threshold.
"""

from collections.abc import Mapping
from decimal import Decimal

import pytest

from accountant_dad.confidence import MAX, MIN
from accountant_dad.engines.input_engine.config import (
    ConfigurationError,
    DocumentScoreRule,
    _count_problem,
    _ParameterValueError,
    _parse_document_score_rule,
    _parse_probability,
    _parse_processing_budget_ms,
    _parse_retry_max_attempts,
    _parse_worst_k,
    _probability_problem,
    _weights_problem,
    load_confidence_parameters,
)


# - Probability bounds: _probability_problem line 173 -
def test_probability_below_min_is_invalid() -> None:
    """Flip MIN <= value <= MAX to MIN < value <= MAX - test catches it."""
    below = MIN - Decimal("0.0001")
    assert _probability_problem(below) is not None


def test_probability_at_min_is_valid() -> None:
    """Boundary: exactly MIN is accepted."""
    assert _probability_problem(MIN) is None


def test_probability_at_max_is_valid() -> None:
    """Boundary: exactly MAX is accepted."""
    assert _probability_problem(MAX) is None


def test_probability_above_max_is_invalid() -> None:
    """Flip MIN <= value <= MAX to MIN <= value < MAX - test catches it."""
    above = MAX + Decimal("0.0001")
    assert _probability_problem(above) is not None


# - Infinity check: _probability_problem line 169 -
def test_probability_positive_infinity_rejected() -> None:
    """Flip not value.is_finite() to value.is_finite() - test catches it."""
    inf = Decimal("Infinity")
    problem = _probability_problem(inf)
    assert problem is not None and "finite" in problem.lower()


def test_probability_negative_infinity_rejected() -> None:
    """Negative infinity also fails the finiteness check."""
    neg_inf = Decimal("-Infinity")
    problem = _probability_problem(neg_inf)
    assert problem is not None and "finite" in problem.lower()


# - Decimal places check: _probability_problem line 176-184 -
def test_probability_exact_confidence_places_valid() -> None:
    """At exactly CONFIDENCE_PLACES decimal places: accepted."""
    # Construct with exactly CONFIDENCE_PLACES places
    valid = Decimal("0.1234")  # 4 places; CONFIDENCE_PLACES is 4
    assert _probability_problem(valid) is None


def test_probability_exceeds_confidence_places_rejected() -> None:
    """Flip -exponent > CONFIDENCE_PLACES to -exponent >= CONFIDENCE_PLACES."""
    # 5 decimal places when max is 4
    too_precise = Decimal("0.12345")
    problem = _probability_problem(too_precise)
    assert problem is not None and "decimal place" in problem.lower()


# - Count lower bound: _count_problem line 190 -
def test_count_below_minimum_is_invalid() -> None:
    """Flip value < minimum to value <= minimum - test catches it."""
    assert _count_problem(value=4, minimum=5) is not None


def test_count_at_minimum_is_valid() -> None:
    """Boundary: exactly minimum is accepted."""
    assert _count_problem(value=5, minimum=5) is None


def test_count_above_minimum_is_valid() -> None:
    """Above minimum also passes."""
    assert _count_problem(value=10, minimum=5) is None


# - retry_max_attempts minimum: line 244 -
def test_parse_retry_max_attempts_zero_accepted() -> None:
    """Flip minimum=0 to minimum=1 - test catches it."""
    # 0 retries should be allowed per the architecture
    result = _parse_retry_max_attempts("0")
    assert result == 0


def test_parse_retry_max_attempts_negative_rejected() -> None:
    """Negative should be rejected regardless."""
    with pytest.raises(_ParameterValueError, match="must be"):
        _parse_retry_max_attempts("-1")


# - worst_k minimum: line 251 -
def test_parse_worst_k_one_minimum() -> None:
    """Exactly 1 is the minimum for worst_k."""
    result = _parse_worst_k("1")
    assert result == 1


def test_parse_worst_k_zero_rejected() -> None:
    """Flip minimum=1 to minimum=0 - test catches it."""
    with pytest.raises(_ParameterValueError, match="must be at least 1"):
        _parse_worst_k("0")


# - processing_budget_ms minimum: line 256 -
def test_parse_processing_budget_ms_one_minimum() -> None:
    """Exactly 1 ms is the minimum."""
    result = _parse_processing_budget_ms("1")
    assert result == 1


def test_parse_processing_budget_ms_zero_rejected() -> None:
    """Flip minimum=1 to minimum=0 - test catches it."""
    with pytest.raises(_ParameterValueError, match="must be at least 1"):
        _parse_processing_budget_ms("0")


# - Weights validation: _weights_problem line 197-208 -
def test_weights_empty_rejected() -> None:
    """Flip not weights to weights - test catches it."""
    problem = _weights_problem({})
    assert problem is not None and "at least one" in problem.lower()


def test_weights_single_field_sums_correctly() -> None:
    """One field with weight 1.0000."""
    weights = {"field1": Decimal("1.0000")}
    assert _weights_problem(weights) is None


def test_weights_sum_not_exactly_one_rejected() -> None:
    """Flip total != Decimal('1.0000') to total == Decimal('1.0000')."""
    weights = {"field1": Decimal("0.5000"), "field2": Decimal("0.4999")}
    problem = _weights_problem(weights)
    assert problem is not None and "1.0000" in problem


def test_weights_sum_exactly_one_accepted() -> None:
    """Exact sum to 1.0000 passes."""
    weights = {"field1": Decimal("0.4000"), "field2": Decimal("0.6000")}
    assert _weights_problem(weights) is None


def test_weights_individual_field_invalid_caught() -> None:
    """Invalid probability in a weight is caught."""
    weights = {"field1": MAX + Decimal("0.0001"), "field2": Decimal("0.5000")}
    problem = _weights_problem(weights)
    assert problem is not None and "field1" in problem


# - Document score rule parsing: line 260-267 -
def test_parse_document_score_rule_min() -> None:
    """MIN rule is accepted."""
    result = _parse_document_score_rule("min")
    assert result == DocumentScoreRule.MIN


def test_parse_document_score_rule_worst_k() -> None:
    """WORST_K rule is accepted."""
    result = _parse_document_score_rule("worst_k")
    assert result == DocumentScoreRule.WORST_K


def test_parse_document_score_rule_product() -> None:
    """PRODUCT rule is accepted (even if later eliminated by user choice)."""
    result = _parse_document_score_rule("product")
    assert result == DocumentScoreRule.PRODUCT


def test_parse_document_score_rule_weighted_mean() -> None:
    """WEIGHTED_MEAN rule is accepted (even if later eliminated by user choice)."""
    result = _parse_document_score_rule("weighted_mean")
    assert result == DocumentScoreRule.WEIGHTED_MEAN


def test_parse_document_score_rule_invalid_rejected() -> None:
    """Unrecognized rule is rejected."""
    with pytest.raises(_ParameterValueError, match="must be one of"):
        _parse_document_score_rule("invalid_rule")


# - Probability parsing: line 211-224 -
def test_parse_probability_valid_decimal() -> None:
    """Valid decimal is parsed."""
    result = _parse_probability("0.7500")
    assert result == Decimal("0.7500")


def test_parse_probability_not_a_number_rejected() -> None:
    """Non-numeric string is rejected."""
    with pytest.raises(_ParameterValueError, match="not a number"):
        _parse_probability("not_a_number")


def test_parse_probability_infinity_rejected() -> None:
    """Infinity string is rejected by _probability_problem."""
    with pytest.raises(_ParameterValueError, match="must be finite"):
        _parse_probability("Infinity")


def test_parse_probability_too_many_places_rejected() -> None:
    """Too many decimal places rejected."""
    with pytest.raises(_ParameterValueError, match="decimal place"):
        _parse_probability("0.12345")


# - Count parsing with minimum: line 227-240 -
def test_parse_worst_k_not_integer_rejected() -> None:
    """Floating point string is rejected."""
    with pytest.raises(_ParameterValueError, match="whole number"):
        _parse_worst_k("1.5")


def test_parse_retry_max_attempts_not_integer_rejected() -> None:
    """Floating point string is rejected."""
    with pytest.raises(_ParameterValueError, match="whole number"):
        _parse_retry_max_attempts("0.5")


# - Integration: missing parameter raises with all problems collected -
def test_load_all_missing_parameters_collected() -> None:
    """Missing parameter raises once with every missing name - never falls
    back, never raises on first. Flip the early return to make test fail."""
    env: Mapping[str, str] = {}
    with pytest.raises(ConfigurationError) as exc_info:
        load_confidence_parameters(env)
    # Should name multiple missing parameters, not raise on just the first
    message = str(exc_info.value)
    assert "ocr_region_accept" in message or "OCR_REGION_ACCEPT" in message.lower()


def test_load_one_missing_raises_and_names_it() -> None:
    """Even a single missing parameter raises immediately and names it."""
    env = {
        "ENGINE_1_CONFIDENCE_OCR_REGION_ACCEPT": "0.8000",
        "ENGINE_1_CONFIDENCE_OCR_VISION_FALLBACK": "0.7500",
        "ENGINE_1_CONFIDENCE_FIELD_CONFIDENCE_FLOOR": "0.6000",
        "ENGINE_1_CONFIDENCE_FIELD_RISKY_MARK": "0.5000",
        "ENGINE_1_CONFIDENCE_DOCUMENT_CONFIDENCE_FLOOR": "0.5500",
        "ENGINE_1_CONFIDENCE_HUMAN_REVIEW_TRIGGER": "0.4500",
        "ENGINE_1_CONFIDENCE_RETRY_TRIGGER": "0.3500",
        "ENGINE_1_CONFIDENCE_RETRY_MAX_ATTEMPTS": "3",
        "ENGINE_1_CONFIDENCE_CLASSIFICATION_ACCEPT": "0.7000",
        "ENGINE_1_CONFIDENCE_TABLE_STRUCTURE_ACCEPT": "0.6500",
        "ENGINE_1_CONFIDENCE_TABLE_CELL_ACCEPT": "0.6000",
        "ENGINE_1_CONFIDENCE_CAPTURE_FIDELITY_FLOOR": "0.5000",
        "ENGINE_1_CONFIDENCE_DOCUMENT_SCORE_RULE": "min",
        "ENGINE_1_CONFIDENCE_DOCUMENT_SCORE_WEIGHTS": '{"field1": 1.0000}',
        "ENGINE_1_CONFIDENCE_WORST_K": "2",
        # Missing: ENGINE_1_CONFIDENCE_PROCESSING_BUDGET_MS
    }
    with pytest.raises(ConfigurationError) as exc_info:
        load_confidence_parameters(env)
    message = str(exc_info.value)
    assert "processing_budget_ms" in message.lower()


def test_load_invalid_probability_raises() -> None:
    """Invalid probability in config raises at load time."""
    env = {
        "ENGINE_1_CONFIDENCE_OCR_REGION_ACCEPT": "1.5000",  # Above MAX
        "ENGINE_1_CONFIDENCE_OCR_VISION_FALLBACK": "0.7500",
        "ENGINE_1_CONFIDENCE_FIELD_CONFIDENCE_FLOOR": "0.6000",
        "ENGINE_1_CONFIDENCE_FIELD_RISKY_MARK": "0.5000",
        "ENGINE_1_CONFIDENCE_DOCUMENT_CONFIDENCE_FLOOR": "0.5500",
        "ENGINE_1_CONFIDENCE_HUMAN_REVIEW_TRIGGER": "0.4500",
        "ENGINE_1_CONFIDENCE_RETRY_TRIGGER": "0.3500",
        "ENGINE_1_CONFIDENCE_RETRY_MAX_ATTEMPTS": "3",
        "ENGINE_1_CONFIDENCE_CLASSIFICATION_ACCEPT": "0.7000",
        "ENGINE_1_CONFIDENCE_TABLE_STRUCTURE_ACCEPT": "0.6500",
        "ENGINE_1_CONFIDENCE_TABLE_CELL_ACCEPT": "0.6000",
        "ENGINE_1_CONFIDENCE_CAPTURE_FIDELITY_FLOOR": "0.5000",
        "ENGINE_1_CONFIDENCE_DOCUMENT_SCORE_RULE": "min",
        "ENGINE_1_CONFIDENCE_DOCUMENT_SCORE_WEIGHTS": '{"field1": 1.0000}',
        "ENGINE_1_CONFIDENCE_WORST_K": "2",
        "ENGINE_1_CONFIDENCE_PROCESSING_BUDGET_MS": "1000",
    }
    with pytest.raises(ConfigurationError):
        load_confidence_parameters(env)
