"""Mutation tests for state.py - kill each vulnerable line exactly.

Kills mutations at:
1. Line 212: type identity check
2. Line 230: membership test in ALLOWED_TRANSITIONS
3. Line 243: self-transition equality check
4. Line 249: is_allowed negation check
5. Line 272: origin identity in successors
6. Lines 128-176: transition edge presence
7. Lines 93-100: enum members existence
"""

import pytest

from accountant_dad.services.state import (
    ACTIVE_STAGES,
    ALLOWED_TRANSITIONS,
    INITIAL_STATE,
    TransactionState,
    TransitionRejectedError,
    approved_with_warning_has_no_state,
    is_allowed,
    require_allowed,
    successors,
)

_EXPECTED_STATE_COUNT = 8
_EXPECTED_ACTIVE_STAGES_COUNT = 6
_EXPECTED_ACCOUNTING_SUCCESSORS = 2


class TestTypeCheckIdentity:
    """Kill line 212: type(value) is not TransactionState.

    Flip to: type(value) is TransactionState or type(value) == TransactionState
    Test fails if a string passes through.
    """

    def test_is_allowed_rejects_string_source(self) -> None:
        """String source must raise, not silently accept via ==."""
        with pytest.raises(TransitionRejectedError):
            is_allowed("Input", TransactionState.UNDERSTANDING)  # type: ignore[arg-type]

    def test_is_allowed_rejects_string_target(self) -> None:
        """String target must raise, not silently accept via ==."""
        with pytest.raises(TransitionRejectedError):
            is_allowed(TransactionState.INPUT, "Understanding")  # type: ignore[arg-type]

    def test_require_allowed_rejects_string_source(self) -> None:
        """String source in require_allowed must raise."""
        with pytest.raises(TransitionRejectedError):
            require_allowed("Input", TransactionState.UNDERSTANDING)  # type: ignore[arg-type]

    def test_require_allowed_rejects_string_target(self) -> None:
        """String target in require_allowed must raise."""
        with pytest.raises(TransitionRejectedError):
            require_allowed(TransactionState.INPUT, "Understanding")  # type: ignore[arg-type]


class TestMembershipInAllowedTransitions:
    """Kill line 230: (source, target) in ALLOWED_TRANSITIONS.

    Flip to: (source, target) not in ALLOWED_TRANSITIONS
    Test fails if valid transitions return False.
    """

    def test_is_allowed_true_for_valid_transition(self) -> None:
        """Valid edge must return True, not False."""
        assert is_allowed(TransactionState.INPUT, TransactionState.UNDERSTANDING)

    def test_is_allowed_true_for_another_valid_transition(self) -> None:
        """Another valid edge must return True."""
        assert is_allowed(TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING)

    def test_is_allowed_true_for_validation_accepted(self) -> None:
        """Validation → Execution must return True."""
        assert is_allowed(TransactionState.VALIDATION, TransactionState.EXECUTION)

    def test_is_allowed_false_for_invalid_transition(self) -> None:
        """Invalid edge must return False."""
        assert not is_allowed(TransactionState.COMPLETED, TransactionState.ACCOUNTING)


class TestSelfTransitionCheck:
    """Kill line 243: if source == target.

    Flip to: if source != target
    Test fails if self-transitions are allowed.
    """

    def test_require_allowed_rejects_self_transition_input(self) -> None:
        """Input → Input must raise."""
        with pytest.raises(TransitionRejectedError):
            require_allowed(TransactionState.INPUT, TransactionState.INPUT)

    def test_require_allowed_rejects_self_transition_completed(self) -> None:
        """Completed → Completed must raise."""
        with pytest.raises(TransitionRejectedError):
            require_allowed(TransactionState.COMPLETED, TransactionState.COMPLETED)

    def test_require_allowed_error_message_mentions_movement(self) -> None:
        """Error for self-transition must mention it records no movement."""
        with pytest.raises(TransitionRejectedError) as exc_info:
            require_allowed(TransactionState.ACCOUNTING, TransactionState.ACCOUNTING)
        assert "itself" in str(exc_info.value) or "movement" in str(exc_info.value)


class TestIsAllowedNegation:
    """Kill line 249: if not is_allowed(source, target).

    Flip to: if is_allowed(source, target)
    Test fails if invalid transitions are not rejected.
    """

    def test_require_allowed_accepts_valid_transition(self) -> None:
        """Valid transition must not raise."""
        require_allowed(TransactionState.INPUT, TransactionState.UNDERSTANDING)

    def test_require_allowed_rejects_invalid_transition(self) -> None:
        """Invalid transition must raise, not pass."""
        with pytest.raises(TransitionRejectedError):
            require_allowed(TransactionState.COMPLETED, TransactionState.INPUT)

    def test_require_allowed_error_mentions_state_machine(self) -> None:
        """Invalid transition error must reference the state machine."""
        with pytest.raises(TransitionRejectedError) as exc_info:
            require_allowed(TransactionState.FAILED, TransactionState.COMPLETED)
        assert "locked state machine" in str(exc_info.value) or "AL-INV" in str(exc_info.value)


class TestSuccessorsIdentityCheck:
    """Kill line 272: if origin is source (identity vs equality).

    Flip to: if origin == source or if origin is not source
    Test fails if successors returns wrong set.
    """

    def test_successors_input_returns_understanding(self) -> None:
        """INPUT → UNDERSTANDING must be in successors."""
        succ = successors(TransactionState.INPUT)
        assert TransactionState.UNDERSTANDING in succ

    def test_successors_accounting_has_both_branches_plus_failed(self) -> None:
        """ACCOUNTING has successors: CLARIFICATION, VALIDATION, and FAILED."""
        succ = successors(TransactionState.ACCOUNTING)
        assert TransactionState.CLARIFICATION in succ
        assert TransactionState.VALIDATION in succ
        assert TransactionState.FAILED in succ

    def test_successors_input_has_understanding_and_failed(self) -> None:
        """INPUT can go to UNDERSTANDING or FAILED."""
        succ = successors(TransactionState.INPUT)
        assert TransactionState.UNDERSTANDING in succ
        assert TransactionState.FAILED in succ

    def test_successors_completed_only_goes_to_understanding(self) -> None:
        """COMPLETED → UNDERSTANDING (correction only)."""
        succ = successors(TransactionState.COMPLETED)
        assert succ == frozenset({TransactionState.UNDERSTANDING})

    def test_successors_failed_can_resume_to_all_active(self) -> None:
        """FAILED can resume to any active stage."""
        succ = successors(TransactionState.FAILED)
        assert succ == frozenset(ACTIVE_STAGES)


class TestTransitionEdgePresence:
    """Kill lines 128-176: missing edges in transition sets.

    Edges that must exist for the system to be correct.
    """

    def test_forward_edge_input_understanding(self) -> None:
        """Forward edge INPUT → UNDERSTANDING exists."""
        assert (TransactionState.INPUT, TransactionState.UNDERSTANDING) in ALLOWED_TRANSITIONS

    def test_forward_edge_understanding_accounting(self) -> None:
        """Forward edge UNDERSTANDING → ACCOUNTING exists."""
        assert (TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING) in ALLOWED_TRANSITIONS

    def test_forward_edge_accounting_clarification(self) -> None:
        """Forward edge ACCOUNTING → CLARIFICATION exists."""
        assert (TransactionState.ACCOUNTING, TransactionState.CLARIFICATION) in ALLOWED_TRANSITIONS

    def test_forward_edge_accounting_validation_no_doubt(self) -> None:
        """Forward edge ACCOUNTING → VALIDATION exists (no-doubt path)."""
        assert (TransactionState.ACCOUNTING, TransactionState.VALIDATION) in ALLOWED_TRANSITIONS

    def test_forward_edge_clarification_accounting(self) -> None:
        """Forward edge CLARIFICATION → ACCOUNTING exists."""
        assert (TransactionState.CLARIFICATION, TransactionState.ACCOUNTING) in ALLOWED_TRANSITIONS

    def test_validation_edge_to_execution(self) -> None:
        """Validation edge VALIDATION → EXECUTION exists."""
        assert (TransactionState.VALIDATION, TransactionState.EXECUTION) in ALLOWED_TRANSITIONS

    def test_validation_edge_to_clarification(self) -> None:
        """Validation edge VALIDATION → CLARIFICATION exists."""
        assert (TransactionState.VALIDATION, TransactionState.CLARIFICATION) in ALLOWED_TRANSITIONS

    def test_validation_rejected_edge(self) -> None:
        """Validation edge VALIDATION → FAILED exists (rejected)."""
        assert (TransactionState.VALIDATION, TransactionState.FAILED) in ALLOWED_TRANSITIONS

    def test_execution_edge_to_completed(self) -> None:
        """Forward edge EXECUTION → COMPLETED exists."""
        assert (TransactionState.EXECUTION, TransactionState.COMPLETED) in ALLOWED_TRANSITIONS

    def test_correction_edge_completed_to_understanding(self) -> None:
        """Correction edge COMPLETED → UNDERSTANDING exists."""
        assert (TransactionState.COMPLETED, TransactionState.UNDERSTANDING) in ALLOWED_TRANSITIONS

    def test_failed_edges_exist_for_all_active_stages(self) -> None:
        """Failed edges from each active stage exist."""
        for stage in ACTIVE_STAGES:
            assert (stage, TransactionState.FAILED) in ALLOWED_TRANSITIONS

    def test_failed_resume_edges_exist_for_all_active_stages(self) -> None:
        """Resume edges from FAILED to each active stage exist."""
        for stage in ACTIVE_STAGES:
            assert (TransactionState.FAILED, stage) in ALLOWED_TRANSITIONS


class TestEnumMembers:
    """Kill lines 93-100: enum members must be exactly the 8 states.

    Adding a 9th state (Cancelled, Paused, Queued, Retrying) fails the build.
    """

    def test_exactly_eight_states(self) -> None:
        """Enum has exactly 8 members, not 9."""
        assert len(TransactionState) == _EXPECTED_STATE_COUNT

    def test_all_eight_states_present(self) -> None:
        """All 8 required states are defined."""
        required = {
            TransactionState.INPUT,
            TransactionState.UNDERSTANDING,
            TransactionState.ACCOUNTING,
            TransactionState.CLARIFICATION,
            TransactionState.VALIDATION,
            TransactionState.EXECUTION,
            TransactionState.COMPLETED,
            TransactionState.FAILED,
        }
        assert set(TransactionState) == required

    def test_no_cancelled_state(self) -> None:
        """Cancelled is not in the enum."""
        with pytest.raises(AttributeError):
            _ = TransactionState.CANCELLED  # type: ignore[attr-defined]

    def test_no_paused_state(self) -> None:
        """Paused is not in the enum."""
        with pytest.raises(AttributeError):
            _ = TransactionState.PAUSED  # type: ignore[attr-defined]

    def test_no_queued_state(self) -> None:
        """Queued is not in the enum."""
        with pytest.raises(AttributeError):
            _ = TransactionState.QUEUED  # type: ignore[attr-defined]

    def test_no_retrying_state(self) -> None:
        """Retrying is not in the enum."""
        with pytest.raises(AttributeError):
            _ = TransactionState.RETRYING  # type: ignore[attr-defined]


class TestInitialState:
    """Kill line 116: INITIAL_STATE = TransactionState.INPUT.

    Flip to a different state.
    """

    def test_initial_state_is_input(self) -> None:
        """INITIAL_STATE must be INPUT."""
        assert INITIAL_STATE == TransactionState.INPUT

    def test_initial_state_is_not_understanding(self) -> None:
        """INITIAL_STATE must not be UNDERSTANDING."""
        assert INITIAL_STATE != TransactionState.UNDERSTANDING


class TestActiveStages:
    """Kill lines 105-112: ACTIVE_STAGES must be exactly the 6 engine-running states.

    Add or remove one.
    """

    def test_active_stages_has_six_members(self) -> None:
        """ACTIVE_STAGES has exactly 6 states."""
        assert len(ACTIVE_STAGES) == _EXPECTED_ACTIVE_STAGES_COUNT

    def test_active_stages_excludes_completed(self) -> None:
        """COMPLETED is not in ACTIVE_STAGES."""
        assert TransactionState.COMPLETED not in ACTIVE_STAGES

    def test_active_stages_excludes_failed(self) -> None:
        """FAILED is not in ACTIVE_STAGES."""
        assert TransactionState.FAILED not in ACTIVE_STAGES

    def test_active_stages_includes_input(self) -> None:
        """INPUT is in ACTIVE_STAGES."""
        assert TransactionState.INPUT in ACTIVE_STAGES

    def test_active_stages_includes_validation(self) -> None:
        """VALIDATION is in ACTIVE_STAGES."""
        assert TransactionState.VALIDATION in ACTIVE_STAGES

    def test_active_stages_correct_order(self) -> None:
        """ACTIVE_STAGES order matches the state machine."""
        expected = (
            TransactionState.INPUT,
            TransactionState.UNDERSTANDING,
            TransactionState.ACCOUNTING,
            TransactionState.CLARIFICATION,
            TransactionState.VALIDATION,
            TransactionState.EXECUTION,
        )
        assert expected == ACTIVE_STAGES


class TestApprovedWithWarningAlwaysRaises:
    """Kill line 289: approved_with_warning_has_no_state always raises."""

    def test_approved_with_warning_raises(self) -> None:
        """Must raise unconditionally."""
        with pytest.raises(TransitionRejectedError):
            approved_with_warning_has_no_state()

    def test_approved_with_warning_error_message(self) -> None:
        """Error must mention 'Approved With Warning' and amendment."""
        with pytest.raises(TransitionRejectedError) as exc_info:
            approved_with_warning_has_no_state()
        msg = str(exc_info.value)
        assert "Approved With Warning" in msg or "approved" in msg.lower()
        assert "amendment" in msg.lower() or "PROPOSED" in msg


class TestTransitionRejectedError:
    """Kill the error type definition."""

    def test_transition_rejected_is_exception(self) -> None:
        """TransitionRejectedError is an Exception."""
        assert issubclass(TransitionRejectedError, Exception)


# === FALSIFICATION HELPERS ===


def test_falsify_type_check_passes_with_enum() -> None:
    """Sanity check: real enum passes type check."""
    # This test would fail if type check is broken.
    # If flipped to `is`, this would raise; we verify it does NOT.
    assert is_allowed(TransactionState.INPUT, TransactionState.UNDERSTANDING)


def test_falsify_membership_passes_with_valid_edge() -> None:
    """Sanity check: valid edge passes membership check."""
    # This test would fail if membership is inverted.
    result = is_allowed(TransactionState.ACCOUNTING, TransactionState.VALIDATION)
    assert result is True


def test_falsify_self_transition_rejected() -> None:
    """Sanity check: self-transition is rejected."""
    # This test would fail if equality check is inverted.
    with pytest.raises(TransitionRejectedError):
        require_allowed(TransactionState.INPUT, TransactionState.INPUT)
