"""Which state each transaction is in RIGHT NOW. One row per Transaction ID.

`APPLICATION_LAYER_INVARIANTS.md:32` states this component's entire job in one
line — *"The state store permits exactly one row per Transaction ID. A
transaction with zero or two states is a hard failure."*
`MVP_BUILD_VERIFY_FIX.md:178` repeats it as the P3 predicate the Application
Layer is judged on. This module is that row, and nothing else.

WHAT IT IS NOT, AND WHY THE ABSENCES ARE STRUCTURAL.
    Not a database, not a queue, not an artifact store. `AL-INV-13`
    (`APPLICATION_LAYER_INVARIANTS.md:169`) forbids *"any hidden queue · any
    implicit waiting place"*, and a store that grew a `pending` list would be
    one without anyone having to name it. `__slots__` is what turns that from a
    rule into a fact: `TransactionStore` has exactly one attribute and a second
    cannot be attached, so a hidden queue has nowhere to live.

    It holds no history either. `APPLICATION_LAYER_API.md:113` says
    `get_transaction_state()` reports the state, *when it was entered* and *what
    triggered it*. The last two are a timestamp and a trigger, they belong to
    `get_transaction_history()` (`:131`), and both need a clock. This module has
    no clock, so it owns the first of the three and leaves the other two to the
    component that can record them honestly — rather than inventing a time.

AL-INV-2 — EXACTLY ONE STATE, WHICH ALSO MEANS NOT ZERO.
    `:30` forbids *"Two states at once · no state at all · a state inferred from
    artifacts rather than recorded"*. All three are closed here by shape:

      two at once   a `dict` keyed by Transaction ID cannot hold two values for
                    one key, and `move()` overwrites in place rather than
                    appending, so a second state is not representable.
      none at all   `state_of()` raises on an unknown ID. There is no `get(id,
                    default)` and no `None` return, because
                    `APPLICATION_LAYER_API.md:117` says *"reject, never an empty
                    or default state"* — a default would be this module quietly
                    asserting a workflow position it never recorded.
      inferred      nothing here imports an artifact module, so there is nothing
                    to infer a state FROM.

    `create()` refusing an ID it already holds is the same invariant read
    forward: `AL-INV-1` (`:13`) — *"Never changed, never reissued, never
    reused"* — and `:17` forbids reuse after `Completed` specifically. Nothing
    in this class removes a row, so an ID that ever existed can never be
    re-created, and `Completed` is a state rather than a deletion.

AL-INV-3 — ATOMIC, WHICH IN MEMORY MEANS VALIDATE BEFORE YOU WRITE.
    `:45` — *"Every transition is a single committed write. A crash
    mid-transition leaves the previous state intact."*
    `APPLICATION_LAYER_FAILURE_MATRIX.md:119` names the failure it prevents: *"A
    transition is half-applied."*

    `move()` therefore has exactly one mutation, one statement long, and every
    way of rejecting a transition raises strictly before it. A rejected move
    cannot leave a partial write because there is no partial write to leave —
    the dict assignment either ran or did not.

AL-INV-6 — THE TRANSITION RULES ARE IMPORTED, NEVER RESTATED.
    `:82` — *"Every transition is validated against the allowed-transitions
    table. A disallowed transition is rejected, not logged and permitted."*

    `move()` calls `require_allowed` from `state.py`. There is no table here, no
    `if source is X and target is Y`, and no second opinion about which edges the
    machine draws. A copy would satisfy today's tests and drift on the first
    amendment, which is Law 14 — and a drifted copy of a state machine is how a
    decision reaches Tally without Validation.

AL-INV-13 — THE TARGET MUST *BE* ONE OF THE EIGHT, NOT MERELY EQUAL TO ONE.
    Found while red-teaming this module, and it is why
    `_require_a_state_the_machine_defines()` exists. `TransactionState` is a
    `StrEnum`, and a `StrEnum` member hashes and compares as its own value:

        hash(TransactionState.UNDERSTANDING) == hash("Understanding")   True
        (INPUT, "Understanding") in ALLOWED_TRANSITIONS                 True
        require_allowed(INPUT, "Understanding")                         RETURNS

    So the locked machine accepts the raw string, and without this guard `move()`
    would write `"Understanding"` — a plain `str` — into a real transaction's
    row. Every later `state_of(...) is TransactionState.UNDERSTANDING` in this
    repository would then be `False` while `==` stayed `True`: a transaction in a
    state that compares right and is not one, which is precisely what `AL-INV-13`
    (`APPLICATION_LAYER_INVARIANTS.md:171`) forbids — *"The set of states in code
    equals the set in `DATA_FLOW.md` §14 … exactly, no more."*

    Refused, never coerced. `TransactionState(target)` would repair the value and
    make the hole invisible, which `identity.py:47-52` already rejects for the
    same reason — *"coercion is how untrusted input stops looking untrusted"*
    (Law 23). Membership is tested by IDENTITY against the enum, because identity
    is the one comparison a `str` cannot satisfy by accident.

    `state.py` is locked and this module does not edit it, so the gap is closed
    on this side and reported rather than patched there (§E.7). The raised type
    stays `TransitionRejectedError`: a caller already handles it, and a third
    exception class would change an interface other modules are written against.

THERE IS NO SETTER, NO `force`, NO OVERRIDE.
    `APPLICATION_LAYER_API.md:147` lists `set_transaction_state()` as absent
    because *"an arbitrary setter would void AL-INV-6"*. A `force=True` on
    `move()` would be that setter under a friendlier name, so `move()` takes a
    Transaction ID and a target and nothing else. The signature is asserted in
    the test suite rather than trusted to review.

WHAT THIS MODULE MAY NEVER IMPORT.
    `AL-INV-4` (`:57`) — *"no engine module imports the state store"* — and
    `AL-INV-5` (`:69`), and `AL-INV-8` (`:106`) — *"`src/services/` never
    imports `src/brain/`"*. The dependency runs one way and this end of it must
    stay clean too: an engine reachable from here is a route by which an engine
    could observe workflow. The import list is asserted whole, by parsing this
    file, so a future import of an engine, the Brain, a clock, a socket or a
    filesystem fails the build rather than a reviewer's attention.
"""

from __future__ import annotations

from accountant_dad.identity import TransactionId
from accountant_dad.services.state import (
    INITIAL_STATE,
    TransactionState,
    TransitionRejectedError,
    require_allowed,
)


def _require_a_state_the_machine_defines(target: TransactionState) -> None:
    """Raise unless `target` IS one of the eight locked states, by identity.

    `AL-INV-13` (`APPLICATION_LAYER_INVARIANTS.md:171`) — *"The set of states in
    code equals the set in `DATA_FLOW.md` §14 … exactly, no more."*

    Identity, not equality, and not `isinstance`. `TransactionState` is a
    `StrEnum`, so `"Understanding" == TransactionState.UNDERSTANDING` and the two
    even hash alike — equality cannot tell a state from a string that looks like
    one. `is` can, because enum members are singletons and no `str` literal is
    ever the same object as one.

    Eight comparisons on the transition path. That is the entire cost of making
    "the recorded state is a state" a fact instead of a convention.
    """
    if all(target is not state for state in TransactionState):
        raise TransitionRejectedError(
            f"{target!r} is not one of the states the locked machine defines "
            "(DATA_FLOW.md §14). Refused rather than coerced: TransactionState is a StrEnum, "
            "so a raw string compares and hashes as a state without being one, and storing it "
            "would put a transaction in a state that does not exist (AL-INV-13, "
            "APPLICATION_LAYER_INVARIANTS.md:171)."
        )


class UnknownTransactionError(Exception):
    """A Transaction ID this store never recorded. Never a default, never `None`.

    `APPLICATION_LAYER_API.md:117` — *"Unknown Transaction ID → reject, never an
    empty or default state."* `:18` — *"Every failure is loud. Nothing returns a
    default on error."*

    Returning `Input` for an unknown ID would be the worst available answer: it
    reads as *"this transaction is at the start"*, which is a claim about a
    transaction the Application Layer has never seen.
    """


class TransactionAlreadyExistsError(Exception):
    """A Transaction ID this store already holds. Creating it again is forbidden.

    `AL-INV-1` (`APPLICATION_LAYER_INVARIANTS.md:13`) — *"Created once by the
    Application Layer. Never changed, never reissued, never reused"* — with
    `:17` forbidding reuse after `Completed`.

    Overwriting instead of raising would send a live transaction back to `Input`
    without a transition, which is `AL-INV-6` voided in one assignment.
    """


class TransactionStore:
    """One state per Transaction ID, in memory, for the lifetime of the process.

    In-memory is the correct shape for P3 and not a placeholder for a database.
    `MVP_BUILD_VERIFY_FIX.md:178` asks one thing of this component — one row per
    ID, zero or two being a hard failure — and a dict satisfies it without a
    dependency to configure, and `AL-INV-14` (`:182`) forbids configuration
    values chosen by the implementation. A store nobody has to configure cannot
    acquire a default connection string nobody chose.
    """

    #: One attribute, and no way to attach a second. `AL-INV-13`
    #: (`APPLICATION_LAYER_INVARIANTS.md:169`) forbids *"any hidden queue · any
    #: implicit waiting place"*, and the cheapest way to build one is
    #: `store.pending = []` from outside the class. `__slots__` makes that an
    #: `AttributeError` rather than a code review someone has to win.
    __slots__ = ("_states",)

    def __init__(self) -> None:
        self._states: dict[TransactionId, TransactionState] = {}

    def create(self, transaction_id: TransactionId) -> TransactionState:
        """Record a new transaction in `INITIAL_STATE`. Return that state.

        `APPLICATION_LAYER_API.md:32` — `start_transaction()`'s postcondition,
        *"Transaction ID created and never reused · state is `Input`"*. The
        starting state is read from `state.py`, not spelled `Input` here, for
        the same reason `move()` imports the table.

        Not idempotent, by `APPLICATION_LAYER_API.md:35` — *"Two calls create
        two transactions."* Two calls with the SAME ID are a different thing
        entirely and are refused: they are one ID being reused, which `AL-INV-1`
        forbids outright.
        """
        if transaction_id in self._states:
            raise TransactionAlreadyExistsError(
                f"transaction {transaction_id.value} already exists in state "
                f"{self._states[transaction_id].value}. A Transaction ID is created once and "
                "never reissued or reused (AL-INV-1, APPLICATION_LAYER_INVARIANTS.md:13); "
                "re-creating it would return a live transaction to Input without a transition."
            )
        self._states[transaction_id] = INITIAL_STATE
        return INITIAL_STATE

    def state_of(self, transaction_id: TransactionId) -> TransactionState:
        """The one state this transaction is in. Raise if it was never created.

        `AL-INV-2` (`APPLICATION_LAYER_INVARIANTS.md:26`) — *"A Transaction ID is
        in exactly one state at any moment."* Pure read: nothing is created,
        changed or started (`APPLICATION_LAYER_API.md:115`).
        """
        try:
            return self._states[transaction_id]
        except KeyError as unknown:
            raise UnknownTransactionError(
                f"transaction {transaction_id.value} was never created. Rejected rather than "
                "answered with a default state (APPLICATION_LAYER_API.md:117); a default would "
                "report a workflow position this store never recorded (AL-INV-2)."
            ) from unknown

    def move(self, transaction_id: TransactionId, target: TransactionState) -> TransactionState:
        """Validate against the locked machine, then apply. Return the new state.

        Three gates then one write, in a fixed order, and the order is the
        invariant:

          1. `state_of` raises `UnknownTransactionError` on an unknown ID. A
             transaction with no current state has nothing to move FROM, and
             inventing one would be `AL-INV-2`'s *"no state at all"* case
             answered with a fabrication.
          2. `_require_a_state_the_machine_defines` raises on a target that only
             looks like a state (`AL-INV-13`). See the module docstring — the
             locked machine accepts a raw string, so the row is protected here.
          3. `require_allowed` raises `TransitionRejectedError` on any edge the
             locked machine does not draw (`AL-INV-6`,
             `APPLICATION_LAYER_INVARIANTS.md:82`). Imported, never restated.
          4. One assignment. Nothing is written until all three gates pass, so a
             rejected move leaves the previous state byte-identical — `AL-INV-3`
             (`:45`), *"a crash mid-transition leaves the previous state
             intact"*, in the form that invariant takes in memory.

        No `force`, no `override`, no third parameter. `set_transaction_state()`
        is absent from the API at `APPLICATION_LAYER_API.md:147` because *"an
        arbitrary setter would void AL-INV-6"*, and a bypass flag here would be
        that setter wearing this method's name.
        """
        source = self.state_of(transaction_id)
        _require_a_state_the_machine_defines(target)
        require_allowed(source, target)
        self._states[transaction_id] = target
        return target

    def exists(self, transaction_id: TransactionId) -> bool:
        """Whether this store holds a state for this Transaction ID.

        The one question about a transaction that is answerable without knowing
        its state, so it is the one that returns a bool instead of raising.
        `state_of()` still raises for the unknown case — this method exists so a
        caller can ASK, not so it can skip the rejection.
        """
        return transaction_id in self._states
