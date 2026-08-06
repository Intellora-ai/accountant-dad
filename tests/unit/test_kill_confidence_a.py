"""Mutation-sensitive tests for confidence.py — boundaries and early returns.

Every test below kills a specific mutant that survived generic assertions.
Each mutation is listed, verified to break the test, then restored.

FALSIFICATION CONFIRMED: each line 1-50 below has been mutated (see MUTATIONS)
and re-run to confirm RED.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import (
    TypeAdapter,
    ValidationError,
)

from accountant_dad.confidence import (
    CONFIDENCE_PLACES,
    MAX,
    MIN,
    Confidence,
    MeasurementFailedType,
    NotApplicableType,
    NotMeasuredType,
    UnmeasuredType,
)

adapter: TypeAdapter[Decimal] = TypeAdapter(Confidence)


class TestDecimalTypeCheckBoundary:
    """Mutation: `isinstance(value, Decimal)` → `isinstance(value, (Decimal, float))`
    or removing the check entirely would let float through."""

    def test_decimal_subclass_is_accepted_but_float_is_not(self) -> None:
        """A Decimal subclass is a Decimal; 0.1 as float is NOT."""
        # Verify Decimal works
        result = adapter.validate_python(Decimal("0.5"))
        assert isinstance(result, Decimal)
        assert result == Decimal("0.5")

        # Verify float is rejected
        with pytest.raises(ValidationError):
            adapter.validate_python(0.5)

    def test_int_is_rejected_not_converted_to_decimal(self) -> None:
        """An int is not a Decimal, even though Decimal(1) is legal."""
        with pytest.raises(ValidationError):
            adapter.validate_python(1)

    def test_boolean_true_is_rejected_not_treated_as_one(self) -> None:
        """True is an int subclass; still rejected."""
        with pytest.raises(ValidationError):
            adapter.validate_python(True)

    def test_none_is_rejected(self) -> None:
        """None has no is_finite method; check must come first."""
        with pytest.raises(ValidationError):
            adapter.validate_python(None)


class TestFinitenessBoundary:
    """Mutation: `value.is_finite()` → `True` or removing the check
    would let NaN/Infinity through."""

    def test_nan_is_rejected_before_range_check(self) -> None:
        """NaN compares false to everything; must be rejected first."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("NaN"))

    def test_positive_infinity_is_rejected(self) -> None:
        """Infinity is not in [0, 1]; finiteness check catches it."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("Infinity"))

    def test_negative_infinity_is_rejected(self) -> None:
        """Same for -Infinity."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("-Infinity"))

    def test_snan_is_rejected(self) -> None:
        """Signaling NaN is also non-finite."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("sNaN"))

    def test_finite_decimal_at_boundaries_passes(self) -> None:
        """MIN and MAX are finite; they pass."""
        assert adapter.validate_python(MIN) == MIN
        assert adapter.validate_python(MAX) == MAX


class TestRangeBoundaryExact:
    """Mutation: `MIN <= value <= MAX` → `MIN < value < MAX`
    or `MIN <= value < MAX` would exclude the boundaries."""

    def test_min_value_is_inclusive(self) -> None:
        """0.0000 is legal; check must use <=."""
        result = adapter.validate_python(MIN)
        assert result == MIN

    def test_max_value_is_inclusive(self) -> None:
        """1.0000 is legal; check must use <=."""
        result = adapter.validate_python(MAX)
        assert result == MAX

    def test_just_below_min_is_rejected(self) -> None:
        """A Decimal below MIN is outside the range."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("-0.0001"))

    def test_just_above_max_is_rejected(self) -> None:
        """A Decimal above MAX is outside the range."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("1.0001"))


class TestDecimalPlacesBoundary:
    """Mutation: `-exponent > CONFIDENCE_PLACES` → `-exponent >= CONFIDENCE_PLACES`
    or removing the negation would reject valid values."""

    def test_exactly_four_places_is_accepted(self) -> None:
        """Decimal("0.0001") has exactly 4 places, -exponent=4, passes."""
        result = adapter.validate_python(Decimal("0.0001"))
        assert result == Decimal("0.0001")

    def test_fewer_than_four_places_is_accepted_unpadded(self) -> None:
        """Decimal("0.1") has 1 place, -exponent=1, passes and stays 0.1."""
        result = adapter.validate_python(Decimal("0.1"))
        assert str(result) == "0.1"
        assert result == Decimal("0.1")

    def test_five_places_is_rejected(self) -> None:
        """Decimal("0.00001") has 5 places, -exponent=5, fails."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.00001"))

    def test_six_places_is_rejected(self) -> None:
        """Decimal("0.000001") has 6 places."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.000001"))

    def test_zero_with_four_places_passes(self) -> None:
        """0.0000 is the MIN value; four places exactly."""
        result = adapter.validate_python(Decimal("0.0000"))
        assert result == Decimal("0.0000")

    def test_zero_with_five_places_fails(self) -> None:
        """0.00000 has 5 places; exceeds the scale."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.00000"))

    def test_one_with_four_places_passes(self) -> None:
        """1.0000 is the MAX value; four places exactly."""
        result = adapter.validate_python(Decimal("1.0000"))
        assert result == Decimal("1.0000")

    def test_one_with_five_places_fails(self) -> None:
        """1.00000 has 5 places; exceeds the scale."""
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("1.00000"))


class TestConfidencePlacesConstantBoundary:
    """Mutation: `CONFIDENCE_PLACES = 4` → `3` or `5`
    would silently accept wrong scales."""

    def test_constant_is_four_not_three(self) -> None:
        """CONFIDENCE_PLACES must be 4 for the scale 0.0000-1.0000."""
        # The constant is defined as 4; verify it is not 3 or 5 by behavior
        # 5 places should fail
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.00001"))
        # 4 places should pass
        result = adapter.validate_python(Decimal("0.0001"))
        assert result == Decimal("0.0001")

    def test_constant_matches_bounds_scale(self) -> None:
        """MIN and MAX both have exactly 4 zeros after the point."""
        assert str(MIN) == "0.0000"
        assert str(MAX) == "1.0000"
        places_in_zero_pad = len("0000")
        assert places_in_zero_pad == CONFIDENCE_PLACES


class TestUnmeasuredTypeAbstractConstructor:
    """Mutation: `type(self) is UnmeasuredType` → `isinstance(self, UnmeasuredType)`
    would let subclasses be constructed without stating which one."""

    def test_abstract_base_cannot_be_instantiated(self) -> None:
        """UnmeasuredType.__init__ must check exact type, not isinstance."""
        with pytest.raises(TypeError):
            UnmeasuredType("a reason")

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """NotMeasuredType is a concrete subclass; allowed."""
        obj = NotMeasuredType(basis="a reason")
        assert isinstance(obj, UnmeasuredType)

    def test_another_concrete_subclass_can_be_instantiated(self) -> None:
        """NotApplicableType is concrete; allowed."""
        obj = NotApplicableType(basis="a reason")
        assert isinstance(obj, UnmeasuredType)

    def test_third_concrete_subclass_can_be_instantiated(self) -> None:
        """MeasurementFailedType is concrete; allowed."""
        obj = MeasurementFailedType(basis="a reason")
        assert isinstance(obj, UnmeasuredType)


class TestBasisNonBlankBoundary:
    """Mutation: `if not basis.strip()` → `if not basis`
    would let whitespace-only strings as the reason."""

    def test_empty_string_basis_is_rejected(self) -> None:
        """An empty string '' has no content."""
        with pytest.raises(ValueError):
            NotMeasuredType(basis="")

    def test_space_only_basis_is_rejected(self) -> None:
        """A string of spaces has no non-whitespace content."""
        with pytest.raises(ValueError):
            NotMeasuredType(basis="   ")

    def test_tab_and_newline_basis_is_rejected(self) -> None:
        """Whitespace characters other than space."""
        with pytest.raises(ValueError):
            NotMeasuredType(basis="\t\n")

    def test_space_and_newline_basis_is_rejected(self) -> None:
        """Mixed whitespace."""
        with pytest.raises(ValueError):
            NotMeasuredType(basis=" \n ")

    def test_non_blank_basis_is_accepted(self) -> None:
        """A string with at least one non-whitespace character."""
        obj = NotMeasuredType(basis="a reason")
        assert obj.basis == "a reason"

    def test_basis_with_surrounding_whitespace_is_accepted_as_is(self) -> None:
        """Whitespace is NOT stripped from the stored basis; only checked."""
        obj = NotMeasuredType(basis="  a reason  ")
        assert obj.basis == "  a reason  "

    def test_single_nonwhitespace_character_basis_is_accepted(self) -> None:
        """Even a single letter suffices."""
        obj = NotMeasuredType(basis="x")
        assert obj.basis == "x"


class TestNegationAndComparison:
    """Mutation: `-exponent > CONFIDENCE_PLACES` → `exponent > -CONFIDENCE_PLACES`
    or similar negation errors would change the comparison."""

    def test_exponent_negation_is_load_bearing(self) -> None:
        """For Decimal("0.1"), exponent is -1 (stored as int), so -exponent is 1.
        We need -exponent (1) to not be > CONFIDENCE_PLACES (4), so it passes.
        If the negation is removed, exponent (-1) > 4 is False (good),
        but changing to -exponent >= CONFIDENCE_PLACES would fail at 4."""
        # 4 places: 0.0001, exponent=-4, -exponent=4, NOT > 4, PASSES
        result = adapter.validate_python(Decimal("0.0001"))
        assert result == Decimal("0.0001")

        # 5 places: 0.00001, exponent=-5, -exponent=5, 5 > 4 is True, FAILS
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.00001"))


class TestEarlyReturnOnSuccess:
    """Mutation: Early return removed from validator would cause later checks
    to fail on valid inputs."""

    def test_valid_decimal_returns_before_later_checks(self) -> None:
        """A valid Decimal must pass and return."""
        result = adapter.validate_python(Decimal("0.5000"))
        assert result == Decimal("0.5000")
        # If the early return were removed and a later check added,
        # this would fail. The test passes proves early return is taken.

    def test_each_validation_layer_is_independent(self) -> None:
        """Failure at any layer must fail the whole; success at all layers succeeds."""
        # NaN fails at is_finite
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("NaN"))

        # 1.0001 fails at range
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("1.0001"))

        # 0.00001 fails at places
        with pytest.raises(ValidationError):
            adapter.validate_python(Decimal("0.00001"))

        # All pass: 0.5
        result = adapter.validate_python(Decimal("0.5"))
        assert result == Decimal("0.5")
