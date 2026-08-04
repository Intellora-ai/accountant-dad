"""The transaction state machine — the Application Layer's only workflow authority.

`APPLICATION_LAYER.md:185-229` specifies it, state by state, with entry
conditions, exit conditions and forbidden transitions.
`MVP_IMPLEMENTATION_BLUEPRINT.md:107` names that document as the full
specification, so it is what this module transcribes.

`DATA_FLOW.md` §14 draws a shorter picture of the same machine:

    Input → Understanding → Accounting → Clarification → Validation → Execution → Completed
                                                                                ↘ Failed

That line is the happy path, not a smaller state machine. An earlier version of
this module was built from it and came out missing `Accounting → Validation`,
`Clarification → Accounting` and `Validation → Clarification`, and sent
corrections to the wrong state. Precedence did not settle it — the summary and
the specification are not in conflict, one is simply less detailed.

EIGHT STATES, AND NOT A NINTH (AL-INV-13).
    Your ruling, quoted at `APPLICATION_LAYER_INVARIANTS.md:165` — *"If a state
    is not in the locked state machine, it does not exist. Never invent
    execution states because they 'seem useful.'"* `Cancelled`, `Paused`,
    `Queued` and `Retrying` are named there as forbidden. A test asserts the
    enum's members are exactly the eight the diagram draws, so a ninth fails the
    build whether or not anyone remembered this rule.

    **Retry is a transition attribute, never a state** (`AL-INV-13`
    consequence). `Transition` carries `attempt`; there is nowhere to park a
    transaction while it retries, because parking it would be a hidden queue.

NO STAGE IS SKIPPED (AL-INV-6).
    `DATA_FLOW.md:283` — *"No stage may be bypassed … however obvious it
    appears."* So the transition table is the whitelist, and a pair absent from
    it is rejected rather than logged and permitted.

    What that rule actually protects is stated at
    `APPLICATION_LAYER_INVARIANTS.md:76` — *"No decision reaches an external
    system without a Validation Decision approving it."* `Validation` is
    therefore the only predecessor of `Execution`. It does NOT make
    `Clarification` mandatory: `APPLICATION_LAYER.md:223` allows
    `Accounting → Validation` when no blocking doubt was raised, and reading
    AL-INV-6 as forcing every transaction through `Clarification` would invent a
    stage the specification does not require.

`WaitingForApproval` IS NOT HERE, AND ITS ABSENCE IS LOAD-BEARING.
    `ARCHITECTURE_AMENDMENTS.md:37` records it as **PROPOSED, not approved**,
    and `:9-15` records that two different amendments share the number 2 across
    two documents. Only `CLAUDE.md` §P's Amendment 2 (the build freeze) is
    approved.

    So an `Approved With Warning` Validation Decision has no state to occupy —
    exactly the gap `ARCHITECTURE_AMENDMENTS.md:71` describes: *"the hold is
    required in four places and representable in none."* This module does not
    close that gap by inventing a state. `approved_with_warning_has_no_state()`
    raises and names the amendment. Failing loudly beats a ninth state nobody
    approved (Law 11), and beats routing such a decision to `Execution`, which
    would post unattended work the four cited documents say must wait.

`Completed` IS NOT PERMANENTLY TERMINAL.
    `DATA_FLOW.md` §14 — *"a correction returns the transaction to an active
    state under the same Transaction ID (§15)."* `APPLICATION_LAYER.md:228`
    names the state: *"→ Understanding (correction, same Transaction ID)"*, and
    `DATA_FLOW.md` §15's own chain opens at *"New Business Understanding"*.

    §15's prose also says the discovery *"arrives as new evidence at Engine 1"*,
    which reads as `Input`. Two documents name `Understanding` and one sentence
    implies `Input`; `Understanding` is encoded and the sentence is reported.
    Either way the Transaction ID does not change (AL-INV-1) — *"a wrong tax
    rate on a laptop purchase is still that purchase."*

`Failed` IS REACHABLE FROM EVERY ACTIVE STAGE, AND LEAVES ONLY BY RESUMING.
    `APPLICATION_LAYER_API.md:49` — `resume_transaction()` requires *"state is
    `Failed`"* and returns *"the state resumed into"*, with `:50` — *"State
    returns to the stage that failed."* So `Failed → <the stage that failed>`,
    and nothing else. Resuming to a stage that did not fail would re-run
    reasoning that already succeeded, which `AL-INV-12` calls *"a second
    opinion nobody asked for."*
"""

from __future__ import annotations

from enum import StrEnum


class TransactionState(StrEnum):
    """The eight states `DATA_FLOW.md` §14 draws. A ninth is a defect (AL-INV-13).

    A `StrEnum` because the state store and the audit trail both persist it as
    text, and a value that serialised to `TransactionState.INPUT` rather than
    `Input` would make yesterday's history unreadable by today's code.
    """

    INPUT = "Input"
    UNDERSTANDING = "Understanding"
    ACCOUNTING = "Accounting"
    CLARIFICATION = "Clarification"
    VALIDATION = "Validation"
    EXECUTION = "Execution"
    COMPLETED = "Completed"
    FAILED = "Failed"


#: The stages where an engine is running, in the order `DATA_FLOW.md` §14 draws
#: them. `Completed` and `Failed` are not here: no engine runs in either.
ACTIVE_STAGES: tuple[TransactionState, ...] = (
    TransactionState.INPUT,
    TransactionState.UNDERSTANDING,
    TransactionState.ACCOUNTING,
    TransactionState.CLARIFICATION,
    TransactionState.VALIDATION,
    TransactionState.EXECUTION,
)

#: The state a transaction begins in. `APPLICATION_LAYER_API.md:32` —
#: `start_transaction()` postcondition, *"state is `Input`"*.
INITIAL_STATE = TransactionState.INPUT


#: The forward edges, transcribed from the "Allowed transitions" column of
#: `APPLICATION_LAYER.md:221-229` — one entry per row, `WaitingForApproval`
#: omitted because its amendment is unapproved.
#:
#: Two of these were absent from an earlier version of this module, which was
#: built from `DATA_FLOW.md` §14's one-line summary instead. That summary draws
#: the happy path only; it is not a smaller state machine, it is a smaller
#: picture of the same one. `MVP_IMPLEMENTATION_BLUEPRINT.md:107` names
#: `APPLICATION_LAYER.md` as the full specification.
_FORWARD_EDGES: frozenset[tuple[TransactionState, TransactionState]] = frozenset(
    {
        (TransactionState.INPUT, TransactionState.UNDERSTANDING),
        (TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING),
        # `:223` — Engine 3 raised a blocking doubt.
        (TransactionState.ACCOUNTING, TransactionState.CLARIFICATION),
        # `:223` — the no-doubt path. NOT a skipped stage: `AL-INV-6` forbids
        # reaching an external system without a Validation Decision, and this
        # edge goes straight AT Validation. Clarification is entered when a
        # doubt exists, not unconditionally.
        (TransactionState.ACCOUNTING, TransactionState.VALIDATION),
        # `:224` — "Engine 3 must re-decide first". Clarification never reaches
        # Validation directly; the answer produces a new decision version.
        (TransactionState.CLARIFICATION, TransactionState.ACCOUNTING),
        # `:225` — one edge per Validation Decision status.
        (TransactionState.VALIDATION, TransactionState.EXECUTION),
        (TransactionState.VALIDATION, TransactionState.CLARIFICATION),
        (TransactionState.EXECUTION, TransactionState.COMPLETED),
    }
)

#: `:225` — status `Rejected`. Recorded as a conflict, not resolved here:
#: `Failed`'s own entry condition at `:229` admits only *"a runtime failure that
#: exhausted retries"*, and `Rejected` is a business conclusion. The edge is
#: encoded because the Validation row states it; the contradiction between the
#: two rows belongs to an amendment (§M), never to code.
_VALIDATION_REJECTED = frozenset({(TransactionState.VALIDATION, TransactionState.FAILED)})

#: A runtime failure at any active stage. `AL-INV-10` — the engine produces
#: nothing, so the transaction moves rather than the artifact appearing.
_TO_FAILED = frozenset((stage, TransactionState.FAILED) for stage in ACTIVE_STAGES)

#: `APPLICATION_LAYER_API.md:50` — resume returns to the stage that failed.
_FROM_FAILED = frozenset((TransactionState.FAILED, stage) for stage in ACTIVE_STAGES)

#: `APPLICATION_LAYER.md:228` — *"→ Understanding (correction, same Transaction
#: ID)"*, and the same target in the diagram at `:204`. `DATA_FLOW.md` §15's own
#: chain also opens at *"New Business Understanding"*.
#:
#: An earlier version of this module sent corrections to `Input`, reading §15's
#: prose — *"arrives as new evidence at Engine 1"*. Two documents name
#: Understanding and one sentence implies Input, so Understanding is encoded and
#: the sentence is reported. This is the ONLY edge out of `Completed`.
_CORRECTION = frozenset({(TransactionState.COMPLETED, TransactionState.UNDERSTANDING)})

#: The whitelist. A pair absent from here is rejected, never permitted with a
#: warning (AL-INV-6).
ALLOWED_TRANSITIONS: frozenset[tuple[TransactionState, TransactionState]] = (
    _FORWARD_EDGES | _VALIDATION_REJECTED | _TO_FAILED | _FROM_FAILED | _CORRECTION
)


class TransitionRejectedError(Exception):
    """A transition that is not on the whitelist. Never downgraded to a warning.

    `AL-INV-6` — *"A disallowed transition is rejected, not logged and
    permitted."* Every failure here is loud, per
    `APPLICATION_LAYER_API.md:18` — *"Every failure is loud. Nothing returns a
    default on error."*
    """


def _require_a_real_state(value: TransactionState, role: str) -> None:
    """Refuse anything that merely EQUALS a state without BEING one.

    `TransactionState` is a `StrEnum`, so its members hash and compare as their
    own text:

        hash(TransactionState.UNDERSTANDING) == hash("Understanding")   True

    which means a plain `str` finds the enum member's tuple in
    `ALLOWED_TRANSITIONS` and sails through every check below. Without this
    guard, `"Understanding"` could be written into a live transaction as its
    state: `==` a state forever, `is` a state never, so every
    `state_of(...) is TransactionState.X` in the repo silently goes False. That
    is `AL-INV-13` broken — *"the set of states in code equals the set in
    `DATA_FLOW.md` §14 — exactly, no more."*

    Found by red-teaming the state store, not by reading this file.

    **Refused, never coerced.** `TransactionState(value)` would repair the input
    and hide the caller's bug, which is the reason `identity.py` uses
    `strict=True` on a version rather than accepting `"3"`.
    """
    if type(value) is not TransactionState:
        raise TransitionRejectedError(
            f"the {role} {value!r} is a {type(value).__name__}, not a "
            "TransactionState. It compares equal to a state because "
            "TransactionState is a StrEnum, and storing it would leave a "
            "transaction in something that is `==` a state and `is` no state at "
            "all (AL-INV-13)."
        )


def is_allowed(source: TransactionState, target: TransactionState) -> bool:
    """Whether the locked state machine draws this edge.

    Answers only about real states. A `str` that equals one is not one, and is
    refused rather than silently accepted — see `_require_a_real_state`.
    """
    _require_a_real_state(source, "source")
    _require_a_real_state(target, "target")
    return (source, target) in ALLOWED_TRANSITIONS


def require_allowed(source: TransactionState, target: TransactionState) -> None:
    """Raise unless the locked state machine draws this edge.

    Deliberately has no `force` parameter and no override. `set_transaction_state()`
    is listed at `APPLICATION_LAYER_API.md:147` as absent because *"an arbitrary
    setter would void AL-INV-6"* — and a bypass flag here would be that setter
    under another name.
    """
    _require_a_real_state(source, "source")
    _require_a_real_state(target, "target")
    if source == target:
        raise TransitionRejectedError(
            f"{source.value} to itself is not a transition. A transaction is in "
            "exactly one state at any moment (AL-INV-2); re-entering the state it "
            "already occupies records movement that did not happen."
        )
    if not is_allowed(source, target):
        raise TransitionRejectedError(
            f"{source.value} → {target.value} is not in the locked state machine "
            f"(DATA_FLOW.md §14). No stage may be bypassed, however obvious it "
            f"appears (AL-INV-6, DATA_FLOW.md:283)."
        )


def successors(source: TransactionState) -> frozenset[TransactionState]:
    """Every state the locked machine allows this one to move to.

    Returns a SET, never a single state, and there is deliberately no function
    anywhere in this module that picks one. `Accounting` has two successors —
    `Clarification` when Engine 3 raised a blocking doubt, `Validation` when it
    did not — and which applies is a fact carried by the Accounting Decision,
    not something the Application Layer works out.

    An earlier version of this module returned "the next stage" as one value.
    That was only possible because the chain had been transcribed from
    `DATA_FLOW.md` §14's happy-path summary; against the real table it would
    have had to choose, and choosing is a decision `DATA_FLOW.md` §14 says the
    Application Layer does not own.
    """
    return frozenset(target for origin, target in ALLOWED_TRANSITIONS if origin is source)


def approved_with_warning_has_no_state() -> None:
    """Refuse to place an `Approved With Warning` transaction. Always raises.

    Four locked documents require the work to wait for a human — quoted at
    `ARCHITECTURE_AMENDMENTS.md:66-69`. The locked state machine has nowhere for
    it to wait, and the amendment that would add `WaitingForApproval` is
    recorded at `ARCHITECTURE_AMENDMENTS.md:37` as PROPOSED, not approved.

    The two silent alternatives are both worse than raising. Sending it to
    `Execution` posts unattended work the four documents say must wait. Holding
    it inside the Application Layer without a state is the hidden queue your
    ruling forbids (`ARCHITECTURE_AMENDMENTS.md:84`) and leaves the transaction
    in *no* state, which AL-INV-2 forbids outright.
    """
    raise TransitionRejectedError(
        "an 'Approved With Warning' Validation Decision has no state in the "
        "locked state machine. Four documents require the Application Layer to "
        "hold it for a human (COMMUNICATION_RULES_VALIDATION_ENGINE.md:61, :69; "
        "ENGINE_6_EXECUTION_ENGINE_RULES.md:147; DATA_FLOW.md:283) and "
        "DATA_FLOW.md §14 gives it nowhere to wait. WaitingForApproval is "
        "PROPOSED, not approved (ARCHITECTURE_AMENDMENTS.md:37). This is an "
        "amendment, never a code workaround "
        "(MVP_IMPLEMENTATION_BLUEPRINT.md:185)."
    )
