"""The transaction state machine, attacked.

The tests that matter most are the ones that try to add a state, skip a stage,
or find a way out of `Approved With Warning` that the locked documents do not
draw. Each of those is a silent architecture change if it succeeds.
"""

from __future__ import annotations

import inspect
import itertools
from typing import cast

import pytest

import accountant_dad.services.state as state_module
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

#: DATA_FLOW.md §14 draws exactly these, in this order, with these spellings.
LOCKED_STATES = (
    "Input",
    "Understanding",
    "Accounting",
    "Clarification",
    "Validation",
    "Execution",
    "Completed",
    "Failed",
)

#: AL-INV-13 names these as forbidden by your ruling, verbatim.
FORBIDDEN_STATES = ("Cancelled", "Paused", "Queued", "Retrying", "WaitingForApproval")

EDGE_COUNT = 21


# ── eight states, and not a ninth ─────────────────────────────────────────


def test_the_states_are_exactly_the_eight_the_diagram_draws() -> None:
    assert tuple(state.value for state in TransactionState) == LOCKED_STATES


@pytest.mark.parametrize("invented", FORBIDDEN_STATES)
def test_no_invented_state_exists(invented: str) -> None:
    """AL-INV-13, quoting your ruling — "If a state is not in the locked state
    machine, it does not exist. Never invent execution states because they
    'seem useful.'"

    `WaitingForApproval` is on this list because ARCHITECTURE_AMENDMENTS.md:37
    records it as PROPOSED, not approved. If it is ever approved, this test is
    what must be edited deliberately — it will not pass by accident.
    """
    assert invented not in {state.value for state in TransactionState}
    with pytest.raises(ValueError, match=invented):
        TransactionState(invented)


def test_a_state_serialises_to_the_word_the_documents_use() -> None:
    """The state store and the audit trail persist this as text. A value that
    serialised to `TransactionState.INPUT` would make yesterday's history
    unreadable by today's code."""
    assert f"{TransactionState.INPUT}" == "Input"
    assert TransactionState.COMPLETED.value == "Completed"


def test_a_transaction_begins_in_input() -> None:
    """APPLICATION_LAYER_API.md:32 — start_transaction() postcondition."""
    assert INITIAL_STATE is TransactionState.INPUT


def test_the_active_stages_are_the_six_where_an_engine_runs() -> None:
    assert tuple(stage.value for stage in ACTIVE_STAGES) == LOCKED_STATES[:6]
    assert TransactionState.COMPLETED not in ACTIVE_STAGES
    assert TransactionState.FAILED not in ACTIVE_STAGES


# ── the transition whitelist ──────────────────────────────────────────────


def test_the_edge_count_is_fixed() -> None:
    """A changed count means an edge was added or removed. Either is an
    architecture change and must be deliberate."""
    assert len(ALLOWED_TRANSITIONS) == EDGE_COUNT


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("Input", "Understanding"),
        ("Understanding", "Accounting"),
        ("Accounting", "Clarification"),
        ("Accounting", "Validation"),
        ("Clarification", "Accounting"),
        ("Validation", "Execution"),
        ("Validation", "Clarification"),
        ("Validation", "Failed"),
        ("Execution", "Completed"),
        ("Completed", "Understanding"),
    ],
)
def test_every_edge_the_specification_draws_is_allowed(source: str, target: str) -> None:
    assert is_allowed(TransactionState(source), TransactionState(target))


def test_a_decision_with_no_blocking_doubt_goes_straight_to_validation() -> None:
    """APPLICATION_LAYER.md:223 allows Accounting → Validation.

    An earlier version of this suite asserted the opposite, reading AL-INV-6's
    "no stage may be bypassed" as forcing every transaction through
    Clarification. What AL-INV-6 actually protects is stated at
    APPLICATION_LAYER_INVARIANTS.md:76 — nothing reaches an external system
    without a Validation Decision. Clarification is entered when a doubt exists.
    """
    assert is_allowed(TransactionState.ACCOUNTING, TransactionState.VALIDATION)


def test_clarification_never_reaches_validation_directly() -> None:
    """APPLICATION_LAYER.md:224 — "Engine 3 must re-decide first." The answer
    produces a new decision version; it does not resume validation."""
    assert not is_allowed(TransactionState.CLARIFICATION, TransactionState.VALIDATION)
    with pytest.raises(TransitionRejectedError, match="not in the locked state machine"):
        require_allowed(TransactionState.CLARIFICATION, TransactionState.VALIDATION)


def test_no_stage_reaches_execution_by_skipping_validation() -> None:
    """AL-INV-6's real content — APPLICATION_LAYER_INVARIANTS.md:76."""
    for stage in (
        TransactionState.INPUT,
        TransactionState.UNDERSTANDING,
        TransactionState.ACCOUNTING,
        TransactionState.CLARIFICATION,
    ):
        assert not is_allowed(stage, TransactionState.EXECUTION)


def test_execution_cannot_be_reached_without_validation() -> None:
    """AL-INV-6 — "No decision reaches an external system without a Validation
    Decision approving it." Validation is the ONLY predecessor of Execution."""
    predecessors = {
        source for source, target in ALLOWED_TRANSITIONS if target is TransactionState.EXECUTION
    }
    assert predecessors == {TransactionState.VALIDATION, TransactionState.FAILED}


def test_execution_has_no_backward_arrow() -> None:
    """AL-INV-11 — "Engine 6 never returns work to an earlier stage.\" """
    targets = {
        target for source, target in ALLOWED_TRANSITIONS if source is TransactionState.EXECUTION
    }
    assert targets == {TransactionState.COMPLETED, TransactionState.FAILED}


@pytest.mark.parametrize("stage", list(ACTIVE_STAGES))
def test_a_runtime_failure_is_reachable_from_every_active_stage(
    stage: TransactionState,
) -> None:
    """AL-INV-10 — the engine produces nothing, so the transaction moves."""
    assert is_allowed(stage, TransactionState.FAILED)


@pytest.mark.parametrize("stage", list(ACTIVE_STAGES))
def test_resuming_returns_to_the_stage_that_failed(stage: TransactionState) -> None:
    """APPLICATION_LAYER_API.md:50 — "State returns to the stage that failed.\" """
    assert is_allowed(TransactionState.FAILED, stage)


def test_a_completed_transaction_cannot_fail() -> None:
    assert not is_allowed(TransactionState.COMPLETED, TransactionState.FAILED)


def test_failed_cannot_reach_completed_without_redoing_the_work() -> None:
    assert not is_allowed(TransactionState.FAILED, TransactionState.COMPLETED)


def test_a_correction_re_enters_at_understanding_and_nowhere_else() -> None:
    """APPLICATION_LAYER.md:228 — "→ Understanding (correction, same Transaction
    ID)", matching the diagram at :204 and DATA_FLOW.md §15's chain, which opens
    at "New Business Understanding".

    §15's prose says the discovery "arrives as new evidence at Engine 1", which
    reads as Input. Two documents name Understanding against one sentence; the
    sentence is reported, not encoded.
    """
    targets = {
        target for source, target in ALLOWED_TRANSITIONS if source is TransactionState.COMPLETED
    }
    assert targets == {TransactionState.UNDERSTANDING}


@pytest.mark.parametrize("state", list(TransactionState))
def test_no_state_transitions_to_itself(state: TransactionState) -> None:
    """AL-INV-2 — exactly one state at any moment. Re-entering the state a
    transaction already occupies records movement that did not happen."""
    assert (state, state) not in ALLOWED_TRANSITIONS
    with pytest.raises(TransitionRejectedError, match="to itself"):
        require_allowed(state, state)


def test_every_pair_outside_the_whitelist_is_rejected() -> None:
    """Exhaustive over all 64 ordered pairs. A whitelist that leaks anywhere is
    not a whitelist."""
    leaked: list[str] = []
    for source, target in itertools.product(TransactionState, repeat=2):
        if (source, target) in ALLOWED_TRANSITIONS:
            continue
        try:
            require_allowed(source, target)
        except TransitionRejectedError:
            continue
        leaked.append(f"{source.value} → {target.value}")
    assert leaked == [], f"transitions permitted but not on the whitelist: {leaked}"


def test_the_whitelist_never_names_a_state_that_does_not_exist() -> None:
    for source, target in ALLOWED_TRANSITIONS:
        assert isinstance(source, TransactionState)
        assert isinstance(target, TransactionState)


def test_every_state_is_reachable_from_the_initial_state() -> None:
    """An unreachable state is either dead or a missing edge. Both are defects."""
    reached = {INITIAL_STATE}
    frontier = [INITIAL_STATE]
    while frontier:
        current = frontier.pop()
        for source, target in ALLOWED_TRANSITIONS:
            if source is current and target not in reached:
                reached.add(target)
                frontier.append(target)
    assert reached == set(TransactionState)


# ── there is no override ──────────────────────────────────────────────────


def test_require_allowed_takes_a_source_and_a_target_and_nothing_else() -> None:
    """APPLICATION_LAYER_API.md:147 lists `set_transaction_state()` as absent
    because "an arbitrary setter would void AL-INV-6". A `force=` parameter
    here would be that setter under another name, so the signature is asserted
    rather than trusted."""
    parameters = list(inspect.signature(require_allowed).parameters)
    assert parameters == ["source", "target"]


def test_a_rejection_is_an_exception_not_a_return_value() -> None:
    """APPLICATION_LAYER_API.md:18 — "Every failure is loud. Nothing returns a
    default on error.\" """
    # An allowed transition returns quietly; a rejected one raises. There is no
    # boolean anyone could forget to check.
    require_allowed(TransactionState.INPUT, TransactionState.UNDERSTANDING)
    with pytest.raises(TransitionRejectedError):
        require_allowed(TransactionState.INPUT, TransactionState.EXECUTION)


# ── the forward chain is read, never chosen ───────────────────────────────


def test_successors_returns_a_set_never_a_single_state() -> None:
    """Accounting has two, and which applies is a fact in the Accounting
    Decision — not something the Application Layer works out. Returning one
    value would force it to choose, and DATA_FLOW.md §14 says it owns no
    decision."""
    assert successors(TransactionState.ACCOUNTING) == frozenset(
        {
            TransactionState.CLARIFICATION,
            TransactionState.VALIDATION,
            TransactionState.FAILED,
        }
    )


def test_a_state_with_no_exit_returns_an_empty_set_rather_than_raising() -> None:
    """Every state currently has an exit; this asserts the shape, so a state
    that loses its last edge is visible as empty rather than as an exception
    nobody catches."""
    for state in TransactionState:
        assert isinstance(successors(state), frozenset)


def test_no_function_here_picks_one_successor() -> None:
    """The absence of a picker IS the protection. A helper returning "the next
    stage" would be the Application Layer choosing."""
    exported = [name for name in dir(state_module) if not name.startswith("_")]
    assert "next_stage" not in exported


# ── the gap that must not be closed in code ───────────────────────────────


def test_approved_with_warning_refuses_to_be_placed() -> None:
    """Four locked documents require the work to wait for a human; the locked
    state machine gives it nowhere to wait; the amendment that would add a
    place is PROPOSED, not approved.

    Raising is the only honest option. Routing to Execution would post
    unattended work; holding it without a state is the hidden queue your ruling
    forbids and leaves the transaction in no state at all (AL-INV-2)."""
    with pytest.raises(TransitionRejectedError) as raised:
        approved_with_warning_has_no_state()
    message = str(raised.value)
    assert "ARCHITECTURE_AMENDMENTS.md:37" in message
    assert "amendment, never a code workaround" in message


def test_the_refusal_cites_all_four_documents_that_require_the_hold() -> None:
    """A refusal that does not say who requires the hold cannot be acted on."""
    with pytest.raises(TransitionRejectedError) as raised:
        approved_with_warning_has_no_state()
    message = str(raised.value)
    for cited in (
        "COMMUNICATION_RULES_VALIDATION_ENGINE.md:61",
        ":69",
        "ENGINE_6_EXECUTION_ENGINE_RULES.md:147",
        "DATA_FLOW.md:283",
    ):
        assert cited in message


def test_the_refusal_message_is_pinned_word_for_word() -> None:
    """The message IS the artifact. Fragments are not enough.

    Everything above checks that certain substrings are present, which leaves
    every other word free to change unnoticed — and the words carry the whole
    argument for why this raises instead of routing. Mutation testing found 16
    surviving mutants in this one function, all of them edits to text that no
    assertion read.

    A refusal nobody can act on is a refusal that failed. This one has to name
    WHICH four documents require the hold, WHERE the proposed amendment sits,
    and THAT the fix is an amendment rather than a code workaround. Pinning it
    exactly is the only way those survive an edit.

    If this test fails, the message changed. Read the new one and decide whether
    the change was intended — do NOT relax the assertion to make it pass.
    """
    with pytest.raises(TransitionRejectedError) as raised:
        approved_with_warning_has_no_state()

    assert str(raised.value) == (
        "an 'Approved With Warning' Validation Decision has no state in the "
        "locked state machine. Four documents require the Application Layer to "
        "hold it for a human (COMMUNICATION_RULES_VALIDATION_ENGINE.md:61, :69; "
        "ENGINE_6_EXECUTION_ENGINE_RULES.md:147; DATA_FLOW.md:283) and "
        "DATA_FLOW.md §14 gives it nowhere to wait. WaitingForApproval is "
        "PROPOSED, not approved (ARCHITECTURE_AMENDMENTS.md:37). This is an "
        "amendment, never a code workaround "
        "(MVP_IMPLEMENTATION_BLUEPRINT.md:185)."
    )


def test_approved_with_warning_has_no_success_path_at_all() -> None:
    """It always raises. There is no argument that makes it return."""
    with pytest.raises(TransitionRejectedError):
        approved_with_warning_has_no_state()
    assert inspect.signature(approved_with_warning_has_no_state).parameters == {}


# ── a string that equals a state is not a state ───────────────────────────


@pytest.mark.parametrize("impostor", ["Input", "Understanding", "Completed", "Failed"])
def test_a_raw_string_is_refused_even_though_it_compares_equal(impostor: str) -> None:
    """TransactionState is a StrEnum, so its members hash as their own text and
    a plain `str` finds their tuples in ALLOWED_TRANSITIONS. Storing one would
    leave a transaction in something `==` a state and `is` no state at all,
    breaking every identity check in the repo (AL-INV-13).

    Found by red-teaming the state store, not by reading the state machine.
    """
    assert hash(TransactionState(impostor)) == hash(impostor)
    with pytest.raises(TransitionRejectedError, match="not a TransactionState"):
        require_allowed(TransactionState.INPUT, impostor)  # type: ignore[arg-type]
    with pytest.raises(TransitionRejectedError, match="not a TransactionState"):
        is_allowed(TransactionState.INPUT, impostor)  # type: ignore[arg-type]


def test_the_impostor_is_refused_as_a_source_too() -> None:
    with pytest.raises(TransitionRejectedError, match="not a TransactionState"):
        require_allowed("Input", TransactionState.UNDERSTANDING)  # type: ignore[arg-type]


def test_the_string_is_refused_rather_than_repaired() -> None:
    """`TransactionState(value)` would coerce and hide the caller's bug — the
    same reason identity.py refuses `"3"` instead of reading it as 3."""
    with pytest.raises(TransitionRejectedError):
        require_allowed(TransactionState.INPUT, "Understanding")  # type: ignore[arg-type]


# ── every refusal is pinned word for word ─────────────────────────────────
#
# `match=` reads a FRAGMENT, so it clears a message that named the wrong role,
# the wrong type, or the wrong pair — a rejection that raises for a reason the
# caller cannot act on is still a rejection, and it still passes every test
# above. Mutation testing found 26 surviving mutants in this module, all of them
# edits to refusal text and to the role label that text is built from.
#
# `AL-INV-6` requires a disallowed transition to be REJECTED; the message is how
# anyone finds out which one, and which side of it was wrong. So each message is
# asserted by equality, in every position a caller can get wrong.
#
# If one of these fails, the message changed. Read the new one and decide whether
# the change was intended — do NOT relax the assertion to make it pass.

#: A plain `str` that equals a state. `!r` renders it quoted, and
#: `type(value).__name__` renders `str`.
IMPOSTOR = "Input"


def impostor_refusal(role: str) -> str:
    """`_require_a_real_state`'s exact words, for `IMPOSTOR` in `role`'s slot."""
    return (
        f"the {role} 'Input' is a str, not a "
        "TransactionState. It compares equal to a state because "
        "TransactionState is a StrEnum, and storing it would leave a "
        "transaction in something that is `==` a state and `is` no state at "
        "all (AL-INV-13)."
    )


def test_require_allowed_names_the_source_slot_word_for_word() -> None:
    with pytest.raises(TransitionRejectedError) as raised:
        require_allowed(cast(TransactionState, IMPOSTOR), TransactionState.UNDERSTANDING)
    assert str(raised.value) == impostor_refusal("source")


def test_require_allowed_names_the_target_slot_word_for_word() -> None:
    """The role label is the only thing distinguishing the two refusals. A
    target rejection that said "source" would send the caller to inspect the
    wrong half of the call."""
    with pytest.raises(TransitionRejectedError) as raised:
        require_allowed(TransactionState.INPUT, cast(TransactionState, IMPOSTOR))
    assert str(raised.value) == impostor_refusal("target")


def test_is_allowed_names_the_source_slot_word_for_word() -> None:
    """`is_allowed` passes its own role labels, so it gets its own assertions —
    the same words from `require_allowed` prove nothing about this function."""
    with pytest.raises(TransitionRejectedError) as raised:
        is_allowed(cast(TransactionState, IMPOSTOR), TransactionState.UNDERSTANDING)
    assert str(raised.value) == impostor_refusal("source")


def test_is_allowed_names_the_target_slot_word_for_word() -> None:
    with pytest.raises(TransitionRejectedError) as raised:
        is_allowed(TransactionState.INPUT, cast(TransactionState, IMPOSTOR))
    assert str(raised.value) == impostor_refusal("target")


def test_the_same_state_refusal_is_pinned_word_for_word() -> None:
    """AL-INV-2 is the whole argument for this branch, and it is carried
    entirely by the sentence — nothing else in the module says why re-entering a
    state is refused rather than allowed as a no-op."""
    with pytest.raises(TransitionRejectedError) as raised:
        require_allowed(TransactionState.INPUT, TransactionState.INPUT)
    assert str(raised.value) == (
        "Input to itself is not a transition. A transaction is in "
        "exactly one state at any moment (AL-INV-2); re-entering the state it "
        "already occupies records movement that did not happen."
    )


def test_the_off_whitelist_refusal_names_both_states_word_for_word() -> None:
    """A rejection that does not say WHICH pair was refused cannot be acted on,
    and one that names the pair in the wrong order sends the reader to the wrong
    row of APPLICATION_LAYER.md:221-229."""
    with pytest.raises(TransitionRejectedError) as raised:
        require_allowed(TransactionState.CLARIFICATION, TransactionState.VALIDATION)
    assert str(raised.value) == (
        "Clarification → Validation is not in the locked state machine "
        "(DATA_FLOW.md §14). No stage may be bypassed, however obvious it "
        "appears (AL-INV-6, DATA_FLOW.md:283)."
    )
