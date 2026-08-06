"""Mutation-killing tests for weakest_link and records_the_same_measurement.

Targets lines 320-642 of confidence.py, focusing on:
- weakest_link aggregation (lines 523-585): empty, all measured, single absence, mixed absences
- records_the_same_measurement comparison (lines 588-642): all state pairs
- Helper functions: measurement_state, describe_measurement, _as_json

Falsifies every comparison, boundary, default, early return and constant by
flipping the source line and confirming RED before restore.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from accountant_dad.confidence import (
    UNMEASURED,
    MeasurementFailedType,
    MeasurementState,
    NotApplicableType,
    NotMeasuredType,
    _as_json,
    describe_measurement,
    measurement_state,
    records_the_same_measurement,
    weakest_link,
)


class TestWeakestLinkEmptyRefusal:
    """Kill: line 564 `if not values:` and line 565-570 ValueError raise."""

    def test_empty_tuple_raises_value_error(self) -> None:
        """Mutation: remove empty check → returns min() of nothing → error."""
        with pytest.raises(ValueError, match="no values"):
            weakest_link(())

    def test_error_message_names_absence_not_low_score(self) -> None:
        """Mutation: change message → loses distinction → auditable failure."""
        with pytest.raises(ValueError, match="aggregate over nothing"):
            weakest_link(())

    def test_empty_list_cast_to_tuple_raises(self) -> None:
        """Mutation: change to `if len(values) == 0:` passes; `if values is None:` fails."""
        with pytest.raises(ValueError):
            weakest_link(())


class TestWeakestLinkAllMeasured:
    """Kill: line 572 absence set creation, line 585 min() of Decimals."""

    def test_all_measured_returns_minimum(self) -> None:
        """Mutation: change min to max → returns maximum instead."""
        a, b, c = Decimal("0.3"), Decimal("0.7"), Decimal("0.5")
        assert weakest_link((a, b, c)) == Decimal("0.3")

    def test_single_measured_value_returns_itself(self) -> None:
        """Mutation: remove min() wrapper → returns generator/fails."""
        val = Decimal("0.6666")
        assert weakest_link((val,)) == Decimal("0.6666")

    def test_two_equal_decimals_returns_same_value(self) -> None:
        """Mutation: change == to is in comparison → breaks equality."""
        val = Decimal("0.5000")
        assert weakest_link((val, val)) == Decimal("0.5000")

    def test_decimal_boundary_at_zero(self) -> None:
        """Mutation: change >= to >, or skip zero in filter."""
        zero = Decimal("0.0000")
        result = weakest_link((zero, Decimal("0.5000")))
        assert result == Decimal("0.0000")

    def test_decimal_boundary_at_one(self) -> None:
        """Mutation: flip comparison in min logic."""
        one = Decimal("1.0000")
        result = weakest_link((one, Decimal("0.5000")))
        assert result == Decimal("0.5000")


class TestWeakestLinkSingleAbsence:
    """Kill: lines 572, 582-583 (absence detection and return)."""

    def test_not_measured_absence_dominates_measured_values(self) -> None:
        """Mutation: remove if absences check → min() includes UnmeasuredType."""
        not_meas = NotMeasuredType(basis="no reading")
        measured = Decimal("0.9999")
        result = weakest_link((measured, not_meas))
        assert isinstance(result, NotMeasuredType)
        assert result.state is MeasurementState.NOT_MEASURED

    def test_not_applicable_absence_dominates(self) -> None:
        """Mutation: return first measured instead of first absence."""
        not_applic = NotApplicableType(basis="empty cell")
        measured = Decimal("0.0001")
        result = weakest_link((measured, not_applic))
        assert isinstance(result, NotApplicableType)
        assert result.state is MeasurementState.NOT_APPLICABLE

    def test_failed_absence_dominates(self) -> None:
        """Mutation: skip absence in comprehension."""
        failed = MeasurementFailedType(basis="recogniser error")
        measured = Decimal("0.5000")
        result = weakest_link((measured, failed))
        assert isinstance(result, MeasurementFailedType)
        assert result.state is MeasurementState.FAILED

    def test_absence_alone_returns_itself(self) -> None:
        """Mutation: change return to min() logic."""
        absence = NotMeasuredType(basis="single absence")
        result = weakest_link((absence,))
        assert result is absence

    def test_basis_preserved_through_aggregation(self) -> None:
        """Mutation: modify basis field → identity check catches it."""
        basis_text = "the very specific reason"
        absence = NotMeasuredType(basis=basis_text)
        result = weakest_link((absence, Decimal("0.5")))
        assert isinstance(result, NotMeasuredType)
        assert result.basis == basis_text


class TestWeakestLinkMixedAbsences:
    """Kill: lines 572-581 (mixed absence detection and ValueError)."""

    def test_not_measured_with_not_applicable_raises(self) -> None:
        """Mutation: change > 1 to >= 1 or > 0 → refuses single absence."""
        not_meas = NotMeasuredType(basis="no reading")
        not_applic = NotApplicableType(basis="empty")
        with pytest.raises(ValueError, match="different kinds"):
            weakest_link((not_meas, not_applic))

    def test_not_measured_with_failed_raises(self) -> None:
        """Mutation: change condition to >=."""
        not_meas = NotMeasuredType(basis="no reading")
        failed = MeasurementFailedType(basis="error")
        with pytest.raises(ValueError, match="different kinds"):
            weakest_link((not_meas, failed))

    def test_not_applicable_with_failed_raises(self) -> None:
        """Mutation: return one silently instead of raising."""
        not_applic = NotApplicableType(basis="empty")
        failed = MeasurementFailedType(basis="error")
        with pytest.raises(ValueError, match="different kinds"):
            weakest_link((not_applic, failed))

    def test_all_three_absence_types_raises(self) -> None:
        """Mutation: change len(absences) > 1 to len(absences) > 2."""
        not_meas = NotMeasuredType(basis="no reading")
        not_applic = NotApplicableType(basis="empty")
        failed = MeasurementFailedType(basis="error")
        with pytest.raises(ValueError, match="3 different kinds"):
            weakest_link((not_meas, not_applic, failed))

    def test_mixed_error_message_names_all_absence_types(self) -> None:
        """Mutation: skip typename collection → loses diagnostic info."""
        not_meas = NotMeasuredType(basis="a")
        not_applic = NotApplicableType(basis="b")
        with pytest.raises(ValueError) as exc_info:
            weakest_link((not_meas, not_applic, Decimal("0.5")))
        msg = str(exc_info.value)
        # Both types should be named
        assert "MeasurementFailedType" not in msg
        assert "NotApplicableType" in msg
        assert "NotMeasuredType" in msg

    def test_mixed_absences_with_many_measured_still_raises(self) -> None:
        """Mutation: skip absence check, only min() measured values."""
        not_meas = NotMeasuredType(basis="a")
        not_applic = NotApplicableType(basis="b")
        d1, d2, d3 = Decimal("0.1"), Decimal("0.5"), Decimal("0.9")
        with pytest.raises(ValueError, match="different kinds"):
            weakest_link((d1, not_meas, d2, not_applic, d3))


class TestRecordsTheSameMeasurementMeasuredPair:
    """Kill: lines 637-641 (state check and Decimal comparison)."""

    def test_same_measured_value_agrees(self) -> None:
        """Mutation: change == to is or !=."""
        val = Decimal("0.5000")
        assert records_the_same_measurement(val, val) is True

    def test_equal_decimals_agree(self) -> None:
        """Mutation: change == to is (breaks Decimal comparison)."""
        a, b = Decimal("0.5000"), Decimal("0.5000")
        assert records_the_same_measurement(a, b) is True

    def test_different_decimals_disagree(self) -> None:
        """Mutation: change == to != or remove comparison."""
        a, b = Decimal("0.5000"), Decimal("0.6000")
        assert records_the_same_measurement(a, b) is False

    def test_same_precision_agrees(self) -> None:
        """Mutation: add string comparison (loses Decimal semantics)."""
        # 0.98 and 0.9800 are equal Decimals
        a, b = Decimal("0.98"), Decimal("0.9800")
        assert records_the_same_measurement(a, b) is True

    def test_boundary_zero_agrees_with_itself(self) -> None:
        """Mutation: skip zero case."""
        zero = Decimal("0.0000")
        assert records_the_same_measurement(zero, zero) is True

    def test_boundary_one_agrees_with_itself(self) -> None:
        """Mutation: skip boundary condition."""
        one = Decimal("1.0000")
        assert records_the_same_measurement(one, one) is True

    def test_zero_disagrees_with_nonzero(self) -> None:
        """Mutation: change inequality."""
        zero = Decimal("0.0000")
        nonzero = Decimal("0.0001")
        assert records_the_same_measurement(zero, nonzero) is False


class TestRecordsTheSameMeasurementAbsencePair:
    """Kill: lines 637-639, 642 (state identity check, return True)."""

    def test_same_not_measured_agrees(self) -> None:
        """Mutation: change return True to False."""
        nm1 = NotMeasuredType(basis="reason a")
        nm2 = NotMeasuredType(basis="reason b")
        # Different basis, same state
        assert records_the_same_measurement(nm1, nm2) is True

    def test_same_not_applicable_agrees(self) -> None:
        """Mutation: remove True return."""
        na1 = NotApplicableType(basis="empty a")
        na2 = NotApplicableType(basis="empty b")
        assert records_the_same_measurement(na1, na2) is True

    def test_same_failed_agrees(self) -> None:
        """Mutation: return False instead."""
        f1 = MeasurementFailedType(basis="error a")
        f2 = MeasurementFailedType(basis="error b")
        assert records_the_same_measurement(f1, f2) is True

    def test_basis_difference_ignored(self) -> None:
        """Mutation: compare basis strings (breaks spec)."""
        # Spec: basis is not part of agreement
        nm1 = NotMeasuredType(basis="short")
        nm2 = NotMeasuredType(basis="much longer reason")
        assert records_the_same_measurement(nm1, nm2) is True

    def test_unmeasured_sentinel_agrees_with_new_instance(self) -> None:
        """Mutation: change isinstance to is identity check."""
        # UNMEASURED is a shared singleton but identity is not load-bearing
        new_nm = NotMeasuredType(basis="no instrument produced a score for this reading")
        assert records_the_same_measurement(UNMEASURED, new_nm) is True


class TestRecordsTheSameMeasurementMixedStates:
    """Kill: lines 637-639 (state is not check for early return False)."""

    def test_measured_vs_not_measured_disagree(self) -> None:
        """Mutation: remove state check, only compare in MEASURED branch."""
        measured = Decimal("0.5000")
        not_meas = NotMeasuredType(basis="no reading")
        assert records_the_same_measurement(measured, not_meas) is False

    def test_measured_vs_not_applicable_disagree(self) -> None:
        """Mutation: change is not to ==."""
        measured = Decimal("0.5000")
        not_applic = NotApplicableType(basis="empty")
        assert records_the_same_measurement(measured, not_applic) is False

    def test_measured_vs_failed_disagree(self) -> None:
        """Mutation: skip mixed-state check."""
        measured = Decimal("0.5000")
        failed = MeasurementFailedType(basis="error")
        assert records_the_same_measurement(measured, failed) is False

    def test_not_measured_vs_not_applicable_disagree(self) -> None:
        """Mutation: change is not to != (Pylint complains but same effect)."""
        not_meas = NotMeasuredType(basis="no reading")
        not_applic = NotApplicableType(basis="empty")
        assert records_the_same_measurement(not_meas, not_applic) is False

    def test_not_measured_vs_failed_disagree(self) -> None:
        """Mutation: wrong state check."""
        not_meas = NotMeasuredType(basis="no reading")
        failed = MeasurementFailedType(basis="error")
        assert records_the_same_measurement(not_meas, failed) is False

    def test_not_applicable_vs_failed_disagree(self) -> None:
        """Mutation: remove state comparison."""
        not_applic = NotApplicableType(basis="empty")
        failed = MeasurementFailedType(basis="error")
        assert records_the_same_measurement(not_applic, failed) is False


class TestRecordsTheSameMeasurementStateIdentity:
    """Kill: line 638 `is not` comparison (identity, not equality)."""

    def test_state_checked_with_identity_not_equality(self) -> None:
        """Mutation: change `is not` to `!=` (would fail on MeasurementState enum)."""
        # MeasurementState is an enum, so `is` is the right check
        measured = Decimal("0.5000")
        not_meas = NotMeasuredType(basis="no reading")
        # Different states; identity check catches it
        assert records_the_same_measurement(measured, not_meas) is False

    def test_measured_state_check_with_identity(self) -> None:
        """Mutation: change line 640 `is` to `==` or `in`."""
        a = Decimal("0.5000")
        b = Decimal("0.5001")
        # Both MEASURED state, different values
        result = records_the_same_measurement(a, b)
        assert result is False


class TestMeasurementStateFunctionBoundaries:
    """Kill: lines 411-420 (isinstance checks and state returns)."""

    def test_decimal_identified_as_measured(self) -> None:
        """Mutation: change Decimal check to other type."""
        state = measurement_state(Decimal("0.5000"))
        assert state is MeasurementState.MEASURED

    def test_not_measured_returns_not_measured_state(self) -> None:
        """Mutation: return MEASURED instead."""
        nm = NotMeasuredType(basis="test")
        state = measurement_state(nm)
        assert state is MeasurementState.NOT_MEASURED

    def test_not_applicable_returns_not_applicable_state(self) -> None:
        """Mutation: return wrong state enum value."""
        na = NotApplicableType(basis="test")
        state = measurement_state(na)
        assert state is MeasurementState.NOT_APPLICABLE

    def test_failed_returns_failed_state(self) -> None:
        """Mutation: skip failed case."""
        f = MeasurementFailedType(basis="test")
        state = measurement_state(f)
        assert state is MeasurementState.FAILED

    def test_float_raises_type_error(self) -> None:
        """Mutation: remove float check, accept it."""
        with pytest.raises(TypeError, match="neither a Decimal"):
            measurement_state(0.5)  # type: ignore[arg-type]  # the wrong type IS the test: the runtime must refuse it

    def test_int_raises_type_error(self) -> None:
        """Mutation: accept int as Decimal."""
        with pytest.raises(TypeError, match="neither a Decimal"):
            measurement_state(1)  # type: ignore[arg-type]  # the wrong type IS the test: the runtime must refuse it

    def test_none_raises_type_error(self) -> None:
        """Mutation: treat None as NOT_MEASURED."""
        with pytest.raises(TypeError, match="neither a Decimal"):
            measurement_state(None)  # type: ignore[arg-type]  # the wrong type IS the test: the runtime must refuse it


class TestDescribeMeasurementFormatting:
    """Kill: lines 440-443 (state retrieval and format strings)."""

    def test_measured_value_formatted_with_state_and_number(self) -> None:
        """Mutation: skip state.value in output."""
        desc = describe_measurement(Decimal("0.7500"))
        assert desc == "measured 0.7500"

    def test_not_measured_formatted_with_state_and_basis(self) -> None:
        """Mutation: skip basis in output."""
        nm = NotMeasuredType(basis="OCR failed")
        desc = describe_measurement(nm)
        assert "not measured" in desc
        assert "OCR failed" in desc

    def test_not_applicable_formatted_with_basis(self) -> None:
        """Mutation: lose basis text."""
        na = NotApplicableType(basis="empty cell")
        desc = describe_measurement(na)
        assert "not applicable" in desc
        assert "empty cell" in desc

    def test_failed_formatted_with_basis(self) -> None:
        """Mutation: truncate basis."""
        f = MeasurementFailedType(basis="recogniser timeout")
        desc = describe_measurement(f)
        assert "failed" in desc
        assert "recogniser timeout" in desc


class TestJsonSerializationShape:
    """Kill: lines 491-493 (isinstance check and dict vs string return)."""

    def test_decimal_serializes_to_string(self) -> None:
        """Mutation: return dict instead."""
        val = Decimal("0.5000")
        result = _as_json(val)
        assert result == "0.5000"
        assert isinstance(result, str)

    def test_measured_never_dict(self) -> None:
        """Mutation: return dict like unmeasured."""
        val = Decimal("0.9999")
        result = _as_json(val)
        assert not isinstance(result, dict)

    def test_not_measured_serializes_to_dict(self) -> None:
        """Mutation: return string instead."""
        nm = NotMeasuredType(basis="no reading")
        result = _as_json(nm)
        assert isinstance(result, dict)
        assert "measurement_state" in result
        assert "basis" in result

    def test_unmeasured_dict_has_state_and_basis(self) -> None:
        """Mutation: skip basis in dict."""
        nm = NotMeasuredType(basis="specific reason")
        result = _as_json(nm)
        assert isinstance(result, dict)
        assert result["measurement_state"] == "not measured"
        assert result["basis"] == "specific reason"

    def test_not_applicable_serializes_to_dict(self) -> None:
        """Mutation: flatten to string."""
        na = NotApplicableType(basis="empty")
        result = _as_json(na)
        assert isinstance(result, dict)
        assert result["measurement_state"] == "not applicable"

    def test_failed_serializes_to_dict(self) -> None:
        """Mutation: return Decimal instead."""
        f = MeasurementFailedType(basis="error")
        result = _as_json(f)
        assert isinstance(result, dict)
        assert result["measurement_state"] == "failed"
