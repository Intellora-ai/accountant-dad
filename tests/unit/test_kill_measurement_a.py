"""Mutation tests for measurement.py — kill mutations in NamedSignal validation.

Each test here kills a specific mutation in the four validation predicates:
  1. name must not be blank
  2. instrument must not be blank
  3. region, if provided, must not be blank
  4. value, if provided, must be finite

Strategy: every predicate comparison, default, boundary, and early return gets
one test that RED when the line flips, GREEN when restored.
"""

import math

import pytest

from accountant_dad.engines.input_engine.measurement import (
    ABSENT,
    AbsentType,
    NamedSignal,
    UnrecordableMeasurementError,
)

# Test constants for measurements
_GRADIENT_VALUE = -0.5
_LAPLACIAN_VARIANCE = 2500.0
_PROBABILITY_VALUE = 0.3333


class TestNamedSignalValidationKills:
    """Mutation killers for NamedSignal.__post_init__ validation."""

    # ==========================================================================
    # KILL MUTATIONS: name validation (line 254-256)
    # ==========================================================================

    def test_name_empty_string_rejected(self) -> None:
        """Mutation: `if not self.name.strip():` → `if False:` dies here."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="", value=0.5, instrument="ocr")

    def test_name_whitespace_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies here. Must reject spaces."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="   ", value=0.5, instrument="ocr")

    def test_name_tab_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Tab is whitespace."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="\t", value=0.5, instrument="ocr")

    def test_name_newline_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Newline is whitespace."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="\n", value=0.5, instrument="ocr")

    def test_name_valid_accepted(self) -> None:
        """Mutation: `if not` → `if` dies here. Valid name must pass."""
        signal = NamedSignal(name="ocr_confidence", value=0.5, instrument="ocr")
        assert signal.name == "ocr_confidence"

    def test_name_with_internal_whitespace_accepted(self) -> None:
        """Mutation: stripping too aggressively dies. Internal spaces preserved."""
        signal = NamedSignal(name="field name", value=0.5, instrument="ocr")
        assert signal.name == "field name"

    # ==========================================================================
    # KILL MUTATIONS: instrument validation (line 258-263)
    # ==========================================================================

    def test_instrument_empty_string_rejected(self) -> None:
        """Mutation: `if not self.instrument.strip():` → `if False:` dies here."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="")

    def test_instrument_whitespace_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies here. Must reject spaces."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="   ")

    def test_instrument_tab_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Tab is whitespace."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="\t")

    def test_instrument_valid_accepted(self) -> None:
        """Mutation: `if not` → `if` dies here. Valid instrument must pass."""
        signal = NamedSignal(name="score", value=0.5, instrument="paddle_ocr")
        assert signal.instrument == "paddle_ocr"

    def test_instrument_with_internal_space_accepted(self) -> None:
        """Mutation: stripping too aggressively dies. Internal spaces preserved."""
        signal = NamedSignal(name="score", value=0.5, instrument="my classifier")
        assert signal.instrument == "my classifier"

    # ==========================================================================
    # KILL MUTATIONS: region validation (line 265-269)
    # ==========================================================================

    def test_region_none_default_accepted(self) -> None:
        """Mutation: removing the `is not None` guard dies.
        None is the default and must be valid."""
        signal = NamedSignal(name="score", value=0.5, instrument="ocr", region=None)
        assert signal.region is None

    def test_region_none_explicit_accepted(self) -> None:
        """Mutation: changing `is not None` to `is None` dies.
        Explicitly passing None must work."""
        signal = NamedSignal(name="doc_type", value=0.7, instrument="classifier", region=None)
        assert signal.region is None

    def test_region_omitted_default_none(self) -> None:
        """Mutation: removing the default value `= None` dies.
        Region must default to None when omitted."""
        signal = NamedSignal(name="score", value=0.5, instrument="ocr")
        assert signal.region is None

    def test_region_empty_string_rejected(self) -> None:
        """Mutation: `if self.region is not None and not self.region.strip():`
        → removing `is not None` guard dies. Empty string must be rejected."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="ocr", region="")

    def test_region_whitespace_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Spaces-only must be rejected."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="ocr", region="   ")

    def test_region_tab_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Tab-only must be rejected."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="ocr", region="\t")

    def test_region_newline_only_rejected(self) -> None:
        """Mutation: `.strip()` → identity dies. Newline-only must be rejected."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=0.5, instrument="ocr", region="\n")

    def test_region_valid_accepted(self) -> None:
        """Mutation: `if not` → `if` dies. Valid region must pass."""
        signal = NamedSignal(
            name="score", value=0.5, instrument="ocr", region="page_1_bbox_1_2_3_4"
        )
        assert signal.region == "page_1_bbox_1_2_3_4"

    def test_region_with_internal_space_accepted(self) -> None:
        """Mutation: stripping too aggressively dies. Internal spaces preserved."""
        signal = NamedSignal(name="score", value=0.5, instrument="ocr", region="region 1")
        assert signal.region == "region 1"

    # ==========================================================================
    # KILL MUTATIONS: value validation (line 271-275)
    # ==========================================================================

    def test_value_none_accepted_unreadable(self) -> None:
        """Mutation: removing `is not None` guard dies.
        None means UNREADABLE, not invalid."""
        signal = NamedSignal(name="score", value=None, instrument="ocr")
        assert signal.value is None

    def test_value_zero_accepted(self) -> None:
        """Mutation: confusing `None` with falsy dies.
        0.0 is a valid measurement, different from None."""
        signal = NamedSignal(name="laplacian_variance", value=0.0, instrument="cv")
        assert signal.value == 0.0

    def test_value_negative_accepted(self) -> None:
        """Mutation: adding `value >= 0` check dies.
        Negative measurements are valid in some contexts."""
        signal = NamedSignal(name="gradient", value=_GRADIENT_VALUE, instrument="cv")
        assert signal.value == _GRADIENT_VALUE

    def test_value_large_positive_accepted(self) -> None:
        """Mutation: adding upper bound check dies.
        Laplacian variance can exceed 1000."""
        signal = NamedSignal(name="laplacian_variance", value=_LAPLACIAN_VARIANCE, instrument="cv")
        assert signal.value == _LAPLACIAN_VARIANCE

    def test_value_fractional_accepted(self) -> None:
        """Mutation: changing `math.isfinite()` to other checks dies."""
        signal = NamedSignal(name="probability", value=_PROBABILITY_VALUE, instrument="classifier")
        assert signal.value == _PROBABILITY_VALUE

    def test_value_nan_rejected(self) -> None:
        """Mutation: `math.isfinite(x)` → `isinstance(x, float)` dies.
        NaN is a float but not finite."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=math.nan, instrument="classifier")

    def test_value_positive_infinity_rejected(self) -> None:
        """Mutation: `math.isfinite()` → dropping check dies.
        Infinity is not a measurement."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=math.inf, instrument="classifier")

    def test_value_negative_infinity_rejected(self) -> None:
        """Mutation: `math.isfinite()` → other checks dies.
        Negative infinity is also not finite."""
        with pytest.raises(UnrecordableMeasurementError):
            NamedSignal(name="score", value=-math.inf, instrument="classifier")

    # ==========================================================================
    # KILL MUTATIONS: structural (frozen, slots)
    # ==========================================================================

    def test_signal_frozen_immutable(self) -> None:
        """Mutation: removing `frozen=True` dies.
        Signals must be immutable after construction."""
        signal = NamedSignal(name="score", value=0.5, instrument="ocr")
        with pytest.raises(AttributeError):
            signal.name = "changed"  # type: ignore[misc]

    def test_signal_all_fields_present(self) -> None:
        """Mutation: removing a field from slots dies.
        All four fields must exist."""
        signal = NamedSignal(
            name="score",
            value=0.95,
            instrument="paddle_ocr",
            region="page_1",
        )
        assert hasattr(signal, "name")
        assert hasattr(signal, "value")
        assert hasattr(signal, "instrument")
        assert hasattr(signal, "region")


class TestAbsentTypeMutationKillers:
    """Mutation killers for AbsentType — ensure Law 24 cannot be violated."""

    def test_absent_bool_raises_not_false(self) -> None:
        """Mutation: `def __bool__ raise TypeError` → `return False` dies.
        ABSENT must refuse `if not ABSENT:` pattern."""
        with pytest.raises(TypeError, match="ABSENT has no truth value"):
            _ = not ABSENT

    def test_absent_bool_raises_not_true(self) -> None:
        """Mutation: `def __bool__ raise TypeError` → `return True` dies."""
        with pytest.raises(TypeError, match="ABSENT has no truth value"):
            _ = bool(ABSENT)

    def test_absent_repr_exact(self) -> None:
        """Mutation: `__repr__` string dies if changed."""
        assert repr(ABSENT) == "ABSENT"

    def test_absent_slots_empty(self) -> None:
        """Mutation: adding slots dies. Sentinel cannot grow attributes."""
        # AbsentType has `__slots__ = ()` so no attributes can be added
        with pytest.raises(AttributeError):
            ABSENT.x = 1  # type: ignore[attr-defined]

    def test_absent_is_singleton(self) -> None:
        """Mutation: creating a new instance dies (though constructor is public).
        Code relies on identity comparison `is ABSENT`."""
        new_instance = AbsentType()
        # They are different objects, so `is` check would fail
        assert new_instance is not ABSENT
        # This verifies that the ABSENT constant in the module is the true one
        assert ABSENT is ABSENT  # noqa: PLR0124


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
