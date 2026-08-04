"""The state store, attacked.

Three questions decide whether this module is correct, and each one is a silent
financial defect if the answer is wrong:

  can a transaction hold two states, or none?          AL-INV-2
  can a rejected move leave a partial write behind?    AL-INV-3
  can a stage be skipped by going through the store
  instead of through the locked machine?               AL-INV-6

So the suite is built to make those three happen rather than to watch them not
happen. The transition tests are exhaustive over all 64 ordered pairs, driven
through the REAL store on a REAL walk from `Input`; the atomicity test snapshots
every row and demands byte-identity after every rejection; and the structural
tests parse `store.py` itself, because a rule that only holds while someone
remembers it is not an invariant.

Transaction IDs here are built from `uuid.UUID(int=n)`, never `TransactionId.new()`.
A suite that generates random identifiers is a suite whose failures are not
reproducible (Law 43), and INV-9 means the value cannot influence any outcome —
so a fixed one loses nothing.
"""

from __future__ import annotations

import ast
import collections
import inspect
import itertools
import pathlib
import uuid
from typing import cast

import pytest

import accountant_dad.services.store as store_module
from accountant_dad.identity import TransactionId
from accountant_dad.services.state import (
    ALLOWED_TRANSITIONS,
    INITIAL_STATE,
    TransactionState,
    TransitionRejectedError,
    is_allowed,
    require_allowed,
)
from accountant_dad.services.store import (
    TransactionAlreadyExistsError,
    TransactionStore,
    UnknownTransactionError,
)

#: The only imports `store.py` is allowed to carry. An exhaustive allowlist, not
#: a denylist, because a denylist only forbids what someone thought of.
#: `AL-INV-4` (APPLICATION_LAYER_INVARIANTS.md:57), `AL-INV-5` (:69) and
#: `AL-INV-8` (:106) all reduce to "this file imports neither an engine nor the
#: Brain", and "no clock, no randomness, no I/O" reduces to the same list.
PERMITTED_IMPORTS = {
    "__future__",
    "accountant_dad.identity",
    "accountant_dad.services.state",
}

#: Read only to make a failure message say WHY. `PERMITTED_IMPORTS` is the gate.
#: Matched against dotted-path SEGMENTS, never as substrings — "os" inside
#: another word is not the `os` module, and a test that cannot tell the
#: difference produces failures nobody trusts.
FORBIDDEN_IMPORT_SEGMENTS = {
    # AL-INV-4 · AL-INV-5 · AL-INV-8 — no engine, no Brain, no artifact.
    "engines",
    "brain",
    "artifacts",
    # No clock. APPLICATION_LAYER_API.md:113 puts "when it was entered" in the
    # history (:131), which is a different component with a different owner.
    "time",
    "datetime",
    "calendar",
    # No randomness. Law 43 — every production failure must be reproducible.
    "random",
    "secrets",
    "uuid",
    # No I/O. "In-memory is correct for P3" is a claim this makes checkable.
    "os",
    "sys",
    "io",
    "pathlib",
    "shutil",
    "socket",
    "sqlite3",
    "http",
    "urllib",
    "requests",
    "json",
    "pickle",
    "subprocess",
    "threading",
    "asyncio",
    # AL-INV-6, APPLICATION_LAYER_INVARIANTS.md:82 — a disallowed transition is
    # "rejected, not logged and permitted". Without a logger, logging-and-
    # continuing is not an option that exists to be taken by mistake.
    "logging",
}

#: Names that would reintroduce `set_transaction_state()`, listed as absent at
#: APPLICATION_LAYER_API.md:147 because "an arbitrary setter would void
#: AL-INV-6" — plus the deletions AL-INV-2 forbids, since a store you can empty
#: is a store where a transaction can hold no state at all.
FORBIDDEN_API_MARKERS = (
    "force",
    "override",
    "skip",
    "bypass",
    "unsafe",
    "set_state",
    "set_transaction_state",
    "cancel",
    "delete",
    "remove",
    "clear",
    "pop",
    "reset",
    "discard",
    "purge",
    "drop",
    "truncate",
)

PUBLIC_API = ["create", "exists", "move", "state_of"]

_SOURCE_TREE = ast.parse(
    pathlib.Path(str(store_module.__file__)).read_text(encoding="utf-8"),
)


# ── helpers ───────────────────────────────────────────────────────────────


def _tid(seed: int) -> TransactionId:
    """A deterministic Transaction ID. INV-9 — the value influences nothing."""
    return TransactionId(uuid.UUID(int=seed))


def _legal_path_to(goal: TransactionState) -> list[TransactionState]:
    """The shortest walk from `INITIAL_STATE` to `goal` over locked edges only.

    Breadth-first over `ALLOWED_TRANSITIONS`, iterated in sorted order so the
    same commit produces the same walk on every run. Nothing here restates the
    machine; it reads it.
    """
    queue: collections.deque[tuple[TransactionState, list[TransactionState]]]
    queue = collections.deque([(INITIAL_STATE, [])])
    seen = {INITIAL_STATE}
    ordered = sorted(ALLOWED_TRANSITIONS)
    while queue:
        current, path = queue.popleft()
        if current is goal:
            return path
        for source, target in ordered:
            if source is current and target not in seen:
                seen.add(target)
                queue.append((target, [*path, target]))
    raise AssertionError(f"{goal.value} is unreachable from {INITIAL_STATE.value}")


def _store_at(state: TransactionState, seed: int = 1) -> tuple[TransactionStore, TransactionId]:
    """A real store holding one real transaction, walked to `state` legally."""
    store = TransactionStore()
    transaction_id = _tid(seed)
    store.create(transaction_id)
    for step in _legal_path_to(state):
        store.move(transaction_id, step)
    assert store.state_of(transaction_id) is state
    return store, transaction_id


# ── AL-INV-2, part one: a state exists only because it was recorded ───────


def test_a_fresh_store_holds_nothing() -> None:
    store = TransactionStore()
    assert not store.exists(_tid(1))


def test_create_records_the_state_the_locked_machine_starts_in() -> None:
    """APPLICATION_LAYER_API.md:32 — start_transaction()'s postcondition, "state
    is `Input`". Read from state.py, never spelled here."""
    store = TransactionStore()
    transaction_id = _tid(1)
    assert store.create(transaction_id) is INITIAL_STATE
    assert INITIAL_STATE is TransactionState.INPUT


def test_create_returns_the_state_it_actually_stored() -> None:
    """A return value that agrees with the documents while the stored row does
    not is the exact shape of a lie this system cannot afford."""
    store = TransactionStore()
    transaction_id = _tid(1)
    returned = store.create(transaction_id)
    assert store.state_of(transaction_id) is returned


def test_exists_answers_before_and_after_creation() -> None:
    store = TransactionStore()
    transaction_id = _tid(1)
    assert not store.exists(transaction_id)
    store.create(transaction_id)
    assert store.exists(transaction_id)


# ── AL-INV-2, part two: never zero, never a default ───────────────────────


def test_an_unknown_transaction_is_rejected_rather_than_given_a_default() -> None:
    """APPLICATION_LAYER_API.md:117 — "reject, never an empty or default state."

    Returning `Input` would be the most dangerous available answer: it reads as
    "this transaction is at the start" about a transaction nobody started.
    """
    store = TransactionStore()
    with pytest.raises(UnknownTransactionError):
        store.state_of(_tid(1))


def test_no_operation_answers_for_a_transaction_that_was_never_created() -> None:
    """Every entry point, not just the read one. One unguarded door is enough."""
    store = TransactionStore()
    transaction_id = _tid(1)
    assert store.exists(transaction_id) is False
    with pytest.raises(UnknownTransactionError):
        store.state_of(transaction_id)
    with pytest.raises(UnknownTransactionError):
        store.move(transaction_id, TransactionState.UNDERSTANDING)


def test_a_rejected_move_does_not_quietly_create_the_transaction() -> None:
    """The tempting repair — "it does not exist, so start it" — invents a
    transaction the Application Layer never issued an ID for (AL-INV-1)."""
    store = TransactionStore()
    transaction_id = _tid(1)
    with pytest.raises(UnknownTransactionError):
        store.move(transaction_id, TransactionState.UNDERSTANDING)
    assert not store.exists(transaction_id)


def test_the_unknown_error_names_the_rule_it_is_enforcing() -> None:
    """APPLICATION_LAYER_API.md:18 — "Every failure is loud." A refusal that
    does not say which rule refused cannot be acted on by whoever reads it."""
    store = TransactionStore()
    with pytest.raises(UnknownTransactionError) as raised:
        store.state_of(_tid(1))
    message = str(raised.value)
    assert "APPLICATION_LAYER_API.md:117" in message
    assert "AL-INV-2" in message


# ── AL-INV-1: one row per ID, created once, never reissued ────────────────


def test_creating_the_same_transaction_twice_is_refused() -> None:
    """AL-INV-1, APPLICATION_LAYER_INVARIANTS.md:13 — "Never changed, never
    reissued, never reused.\" """
    store = TransactionStore()
    transaction_id = _tid(1)
    store.create(transaction_id)
    with pytest.raises(TransactionAlreadyExistsError):
        store.create(transaction_id)


def test_a_duplicate_create_does_not_reset_a_live_transaction() -> None:
    """The failure this refusal prevents. Overwriting would return a
    transaction in `Validation` to `Input` with no transition at all — AL-INV-6
    voided by one assignment, and no record that it happened."""
    store, transaction_id = _store_at(TransactionState.VALIDATION)
    with pytest.raises(TransactionAlreadyExistsError):
        store.create(transaction_id)
    assert store.state_of(transaction_id) is TransactionState.VALIDATION


def test_the_duplicate_error_names_the_state_it_refused_to_overwrite() -> None:
    store, transaction_id = _store_at(TransactionState.VALIDATION)
    with pytest.raises(TransactionAlreadyExistsError) as raised:
        store.create(transaction_id)
    message = str(raised.value)
    assert "AL-INV-1" in message
    assert "Validation" in message


def test_an_id_that_reached_completed_can_never_be_created_again() -> None:
    """AL-INV-1, :17 — reuse after `Completed` is forbidden by name. Nothing in
    this class removes a row, so the refusal holds for the process's life."""
    store, transaction_id = _store_at(TransactionState.COMPLETED)
    with pytest.raises(TransactionAlreadyExistsError):
        store.create(transaction_id)
    assert store.state_of(transaction_id) is TransactionState.COMPLETED


def test_a_correction_reuses_the_row_the_transaction_already_has() -> None:
    """DATA_FLOW.md §15 via APPLICATION_LAYER.md:228 — a correction re-enters at
    `Understanding` under the SAME Transaction ID. One row, not a second."""
    store, transaction_id = _store_at(TransactionState.COMPLETED)
    assert store.move(transaction_id, TransactionState.UNDERSTANDING) is (
        TransactionState.UNDERSTANDING
    )
    assert store.state_of(transaction_id) is TransactionState.UNDERSTANDING


def test_an_equal_id_is_the_same_row_even_as_a_different_object() -> None:
    """The real-world case: an ID that came back from storage or the wire.

    `TransactionId` is a frozen dataclass, so equality and hashing are by value.
    If this store keyed on object identity instead, a round-tripped ID would
    open a SECOND row for one transaction — AL-INV-2's "two states at once",
    arriving through the door nobody watches.
    """
    store = TransactionStore()
    original = _tid(7)
    round_tripped = TransactionId(uuid.UUID(int=7))
    assert original is not round_tripped
    store.create(original)
    assert store.exists(round_tripped)
    assert store.state_of(round_tripped) is INITIAL_STATE
    with pytest.raises(TransactionAlreadyExistsError):
        store.create(round_tripped)


# ── AL-INV-6: the locked machine decides, and it is the only thing that ───


@pytest.mark.parametrize(
    ("source", "target"),
    list(itertools.product(TransactionState, repeat=2)),
)
def test_the_store_accepts_exactly_the_edges_the_locked_machine_draws(
    source: TransactionState,
    target: TransactionState,
) -> None:
    """All 64 ordered pairs, each on a real store walked to `source` legally.

    This is the test that makes duplication impossible to hide. If `move()` ever
    grows its own copy of the transition rules, the copy and `is_allowed` will
    disagree on some pair the moment either is amended, and this reddens on that
    pair (Law 14). It is also the exhaustive form of "every illegal transition
    is rejected" — 43 of the 64 pairs are illegal.
    """
    store, transaction_id = _store_at(source)
    if is_allowed(source, target):
        assert store.move(transaction_id, target) is target
        assert store.state_of(transaction_id) is target
    else:
        with pytest.raises(TransitionRejectedError):
            store.move(transaction_id, target)
        assert store.state_of(transaction_id) is source


def test_a_stage_cannot_be_skipped_by_going_through_the_store() -> None:
    """AL-INV-6's real content, APPLICATION_LAYER_INVARIANTS.md:76 — "No
    decision reaches an external system without a Validation Decision approving
    it." Named explicitly, rather than left to the exhaustive test, because it
    is the one failure this whole component exists to prevent."""
    for stage in (
        TransactionState.INPUT,
        TransactionState.UNDERSTANDING,
        TransactionState.ACCOUNTING,
        TransactionState.CLARIFICATION,
    ):
        store, transaction_id = _store_at(stage)
        with pytest.raises(TransitionRejectedError):
            store.move(transaction_id, TransactionState.EXECUTION)
        assert store.state_of(transaction_id) is stage


@pytest.mark.parametrize("state", list(TransactionState))
def test_a_transaction_cannot_be_moved_to_the_state_it_is_already_in(
    state: TransactionState,
) -> None:
    """AL-INV-2 — re-entering the occupied state records movement that did not
    happen, and would make the history claim a transition the machine never
    drew."""
    store, transaction_id = _store_at(state)
    with pytest.raises(TransitionRejectedError, match="to itself"):
        store.move(transaction_id, state)
    assert store.state_of(transaction_id) is state


def test_move_returns_the_state_it_actually_stored() -> None:
    store, transaction_id = _store_at(TransactionState.INPUT)
    returned = store.move(transaction_id, TransactionState.UNDERSTANDING)
    assert store.state_of(transaction_id) is returned


#: Values that are NOT states but survive `==` and `hash` against one, or that
#: name a state AL-INV-13 forbids outright. Every one of them lied to mypy.
IMPOSTOR_TARGETS = ("Understanding", "Input", "Execution", "Completed", "Cancelled", "Paused")


@pytest.mark.parametrize("impostor", IMPOSTOR_TARGETS)
def test_a_target_that_only_looks_like_a_state_never_reaches_the_store(impostor: str) -> None:
    """The hole this module was red-teamed into closing. Law 23 — untrusted
    input, including input that lied to mypy.

    `TransactionState` is a `StrEnum`, so `hash("Understanding") ==
    hash(TransactionState.UNDERSTANDING)` and the locked machine's own
    `require_allowed` RETURNS QUIETLY for the raw string. Without the identity
    guard in `move()`, a plain `str` becomes a live transaction's recorded state
    — equal to a state under `==`, never identical under `is`, and therefore a
    state that AL-INV-13 says does not exist.

    Found: `state.py`'s `require_allowed` accepts a raw string target and, for a
    string that is not a state value, fails with `AttributeError` from
    `target.value` while formatting its refusal. · Impact: none reaches this
    store, because `move()` refuses first. · Not changed: `state.py` is locked
    and outside this module's scope (§E.7); reported, not patched there.
    """
    store, transaction_id = _store_at(TransactionState.INPUT)
    hostile = cast(TransactionState, impostor)
    with pytest.raises(TransitionRejectedError, match="AL-INV-13"):
        store.move(transaction_id, hostile)
    stored = store.state_of(transaction_id)
    assert stored is TransactionState.INPUT
    assert type(stored) is TransactionState


def test_the_locked_machine_now_refuses_the_impostor_itself() -> None:
    """This test previously asserted the OPPOSITE, and that was correct at the
    time: `state.py` accepted a raw string, because `TransactionState` is a
    `StrEnum` whose members hash as their own text.

    Red-teaming this store is what surfaced it. The hole was then closed at the
    root — in `state.py`, where the rule belongs — rather than left for every
    caller to guard separately. This test was rewritten to assert what is now
    true, which §J.4 permits as correcting a wrong expectation; it was not
    loosened.

    The guard inside `move()` is kept even though it is now redundant. That is
    a deliberate second check rather than an accident: this store is the thing
    that WRITES into a live transaction, and the cost of a redundant comparison
    is nothing against a state value that would be `==` a state forever and
    `is` a state never. The rule still has one owner — `state.py` — and the
    store defers to it.
    """
    impostor = cast(TransactionState, "Understanding")
    with pytest.raises(TransitionRejectedError, match="not a TransactionState"):
        require_allowed(TransactionState.INPUT, impostor)
    # Equal to a state, and not one. Asserted after the refusal because mypy
    # narrows `impostor` to Never once told it is not that member.
    assert impostor == TransactionState.UNDERSTANDING
    assert type(impostor) is not TransactionState


# ── AL-INV-3: a rejected move leaves everything exactly as it was ─────────


def test_a_rejected_move_leaves_every_row_in_the_store_byte_identical() -> None:
    """APPLICATION_LAYER_INVARIANTS.md:45 — "A crash mid-transition leaves the
    previous state intact." APPLICATION_LAYER_FAILURE_MATRIX.md:119 names the
    failure: "A transition is half-applied."

    Three transactions, each parked in a different state, then every illegal
    target attempted against each. After every single rejection the WHOLE store
    is compared — not just the row that was attacked, because a partial write
    that touched a neighbour is the harder bug and the one a single-row
    assertion would miss. Identity (`is`) rather than equality: enum members are
    singletons, so `is` is the strongest form of "byte-identical" available.
    """
    parked = {
        _tid(1): TransactionState.ACCOUNTING,
        _tid(2): TransactionState.VALIDATION,
        _tid(3): TransactionState.COMPLETED,
    }
    store = TransactionStore()
    for transaction_id, destination in parked.items():
        store.create(transaction_id)
        for step in _legal_path_to(destination):
            store.move(transaction_id, step)

    snapshot = {transaction_id: store.state_of(transaction_id) for transaction_id in parked}
    assert snapshot == parked

    for transaction_id, source in parked.items():
        for target in TransactionState:
            if is_allowed(source, target):
                continue
            with pytest.raises(TransitionRejectedError):
                store.move(transaction_id, target)
            for other, expected in snapshot.items():
                assert store.state_of(other) is expected


def test_an_unknown_id_rejected_by_move_leaves_the_other_rows_untouched() -> None:
    """The other half of atomicity: the rejection that happens at the FIRST
    gate rather than the second must be just as inert."""
    store, known = _store_at(TransactionState.ACCOUNTING)
    with pytest.raises(UnknownTransactionError):
        store.move(_tid(99), TransactionState.VALIDATION)
    assert store.state_of(known) is TransactionState.ACCOUNTING
    assert not store.exists(_tid(99))


# ── AL-INV-2, part three: parallel transactions, never parallel states ────


def test_two_transactions_are_independent() -> None:
    """DATA_FLOW.md:646 — "Parallel transactions are allowed. Parallel states
    for one transaction are prohibited.\" """
    store = TransactionStore()
    first, second = _tid(1), _tid(2)
    store.create(first)
    store.create(second)
    store.move(first, TransactionState.UNDERSTANDING)
    assert store.state_of(first) is TransactionState.UNDERSTANDING
    assert store.state_of(second) is INITIAL_STATE


def test_a_rejection_on_one_transaction_does_not_move_another() -> None:
    store = TransactionStore()
    first, second = _tid(1), _tid(2)
    store.create(first)
    store.create(second)
    with pytest.raises(TransitionRejectedError):
        store.move(first, TransactionState.EXECUTION)
    assert store.state_of(first) is INITIAL_STATE
    assert store.state_of(second) is INITIAL_STATE


def test_every_state_can_be_occupied_at_once_by_different_transactions() -> None:
    """Eight transactions, one in each state, all live simultaneously. Parallel
    transactions are the allowed half of DATA_FLOW.md:646."""
    store = TransactionStore()
    placed: dict[TransactionId, TransactionState] = {}
    for index, destination in enumerate(TransactionState):
        transaction_id = _tid(100 + index)
        store.create(transaction_id)
        for step in _legal_path_to(destination):
            store.move(transaction_id, step)
        placed[transaction_id] = destination
    assert {t: store.state_of(t) for t in placed} == placed


def test_two_stores_never_share_a_row() -> None:
    """`_states` is built in `__init__`, not on the class. A class-level dict
    would make every store in the process one store — every test would pass and
    two tenants would read each other's workflow."""
    first_store, second_store = TransactionStore(), TransactionStore()
    transaction_id = _tid(1)
    first_store.create(transaction_id)
    assert not second_store.exists(transaction_id)
    with pytest.raises(UnknownTransactionError):
        second_store.state_of(transaction_id)


# ── there is no setter, no override, and no hidden queue ──────────────────


def test_move_takes_a_transaction_and_a_target_and_nothing_else() -> None:
    """APPLICATION_LAYER_API.md:147 lists `set_transaction_state()` as absent
    because "an arbitrary setter would void AL-INV-6". A `force=` parameter here
    would be that setter under this method's name, so the signature is asserted
    rather than trusted to review."""
    store = TransactionStore()
    assert list(inspect.signature(store.move).parameters) == ["transaction_id", "target"]
    assert list(inspect.signature(TransactionStore.move).parameters) == [
        "self",
        "transaction_id",
        "target",
    ]


def test_the_public_surface_is_exactly_four_methods() -> None:
    """A fifth is a new capability and must be a deliberate edit here."""
    assert sorted(name for name in dir(TransactionStore) if not name.startswith("_")) == PUBLIC_API


def test_no_public_method_offers_an_override_or_a_deletion() -> None:
    """Both halves: no method NAMED for a bypass, and no method with a parameter
    named for one. `delete`/`clear` are on the list too — a store you can empty
    is a store where a transaction can hold no state at all (AL-INV-2, :30)."""
    for name in PUBLIC_API:
        assert not any(marker in name.lower() for marker in FORBIDDEN_API_MARKERS), name
        parameters = inspect.signature(getattr(TransactionStore, name)).parameters
        offending = sorted(
            parameter
            for parameter in parameters
            if any(marker in parameter.lower() for marker in FORBIDDEN_API_MARKERS)
        )
        assert offending == [], f"{name} offers a bypass parameter: {offending}"


def test_the_store_cannot_grow_a_second_attribute() -> None:
    """AL-INV-13, APPLICATION_LAYER_INVARIANTS.md:169 — "any hidden queue · any
    implicit waiting place" is forbidden. The cheapest way to build one is to
    hang a list off the store from outside. `__slots__` makes that an
    AttributeError instead of a code review someone has to win."""
    store = TransactionStore()
    with pytest.raises(AttributeError):
        store.pending = []  # type: ignore[attr-defined]
    assert TransactionStore.__slots__ == ("_states",)


# ── structural: what the file itself is allowed to contain ────────────────


def _imported_modules() -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(_SOURCE_TREE):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_the_module_imports_nothing_outside_the_permitted_list() -> None:
    """One assertion covering AL-INV-4, AL-INV-5, AL-INV-8 and "no clock, no
    randomness, no I/O" at once. An allowlist, so it also forbids the import
    nobody predicted."""
    assert _imported_modules() == PERMITTED_IMPORTS


def test_the_module_imports_no_engine_no_brain_no_clock_and_no_io() -> None:
    """Redundant with the allowlist by design — this one names the reason when
    it fails. Segments, not substrings: `os` inside another word is not `os`."""
    segments = {segment for name in _imported_modules() for segment in name.split(".")}
    offenders = sorted(segments & FORBIDDEN_IMPORT_SEGMENTS)
    assert offenders == [], f"forbidden import(s): {offenders}"


def test_the_module_holds_no_transition_table_of_its_own() -> None:
    """Law 14. A second copy of the machine passes every behavioural test on the
    day it is written and drifts on the first amendment — and a drifted copy of
    a state machine is how a decision reaches Tally without Validation."""
    assigned: set[str] = set()
    for node in ast.walk(_SOURCE_TREE):
        if isinstance(node, ast.Assign):
            assigned.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned.add(node.target.id)
    restated = sorted(
        name
        for name in assigned
        if any(marker in name.upper() for marker in ("TRANSITION", "ALLOWED", "EDGE", "SUCCESSOR"))
    )
    assert restated == [], f"the transition rules are restated here: {restated}"


def _function(name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(_SOURCE_TREE)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _row_writes(node: ast.AST) -> list[ast.AST]:
    """Assignments into `self._states[...]` — the only real mutations there are."""
    writes: list[ast.AST] = []
    for candidate in ast.walk(node):
        targets: list[ast.expr]
        if isinstance(candidate, ast.Assign):
            targets = list(candidate.targets)
        elif isinstance(candidate, ast.AugAssign):
            targets = [candidate.target]
        else:
            continue
        if any(isinstance(target, ast.Subscript) for target in targets):
            writes.append(candidate)
    return writes


def test_move_delegates_to_the_locked_machine_and_names_no_state_of_its_own() -> None:
    """The positive half of the no-duplication rule.

    `move()` calls `require_allowed`, and mentions no individual state anywhere
    in its body. That second half is what actually bans a hand-rolled rule:
    every restatement of the machine has to name a member — `if target is
    TransactionState.EXECUTION` — and there is no way to write one without an
    attribute access this catches, whatever the surrounding code is called.
    """
    move = _function("move")
    called = {
        node.func.id
        for node in ast.walk(move)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "require_allowed" in called
    named_states = sorted(
        node.attr
        for node in ast.walk(move)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "TransactionState"
    )
    assert named_states == [], f"move() restates the machine by naming {named_states}"


def test_move_writes_the_row_in_exactly_one_place() -> None:
    """AL-INV-3 as a property of the code, not only of the behaviour.

    "Every transition is a single committed write" (:45). Two writes is where a
    half-applied transition comes from; one write cannot be half anything. Local
    bindings are not counted — `source = self.state_of(...)` mutates nothing.
    Only assignments INTO the row are writes.
    """
    assert len(_row_writes(_function("move"))) == 1


def test_only_create_and_move_write_a_row_at_all() -> None:
    """Module-wide, so a future method cannot acquire a write quietly. `create`
    writes `INITIAL_STATE` once; `move` writes the validated target once."""
    writers = sorted(
        node.name
        for node in ast.walk(_SOURCE_TREE)
        if isinstance(node, ast.FunctionDef) and _row_writes(node)
    )
    assert writers == ["create", "move"]


def test_nothing_in_this_module_deletes_a_row() -> None:
    """AL-INV-2, :30 — "no state at all" is forbidden as firmly as two states.
    A `del self._states[...]` anywhere would make it reachable, and AL-INV-1
    (:17) would lose the refusal that stops a `Completed` ID being reissued."""
    assert [node for node in ast.walk(_SOURCE_TREE) if isinstance(node, ast.Delete)] == []


def test_every_error_this_module_raises_is_named_error() -> None:
    """Ruff N818 enforces it on the linter side; this holds it at runtime too,
    so the rule survives a lint configuration change."""
    for raised in (UnknownTransactionError, TransactionAlreadyExistsError):
        assert issubclass(raised, Exception)
        assert raised.__name__.endswith("Error")
