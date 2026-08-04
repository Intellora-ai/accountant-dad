"""The audit trail, attacked.

The tests that matter most are the ones that try to take something out of the
history, put reasoning into it, or get a timestamp from somewhere other than the
caller. Each of those succeeding turns a permanent record into a story.

Several of these read the module's own source off disk with `ast` rather than
asserting on behaviour. That is deliberate: "does not call a clock" and "cannot
delete" are properties of what the code IS, and a behavioural test can only ever
sample the cases someone thought of.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools
import pathlib
from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

import accountant_dad.services.audit as audit_module
from accountant_dad.identity import TransactionId
from accountant_dad.services.audit import AuditTrail, Transition, UnrecordableTransitionError
from accountant_dad.services.state import ALLOWED_TRANSITIONS, INITIAL_STATE, TransactionState

AT = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)

FIRST_ATTEMPT, SECOND_ATTEMPT, THIRD_ATTEMPT = 1, 2, 3
OTHER_RECORDS = 3

#: The exact shape another module is written against. A rename here is a broken
#: caller, so the names are pinned rather than trusted to review.
CONTRACT_FIELDS = ("from_state", "to_state", "at", "trigger", "engine", "attempt")

#: `APPLICATION_LAYER_API.md:135` — "history is never truncated, compacted or
#: summarised." A method whose name contains one of these is that sentence being
#: contradicted, whatever the docstring says.
DESTRUCTIVE_WORDS = (
    "delete",
    "remove",
    "clear",
    "truncate",
    "compact",
    "update",
    "edit",
    "pop",
    "discard",
    "purge",
    "prune",
    "drop",
    "reset",
    "overwrite",
    "rewrite",
    "replace",
    "expire",
    "evict",
    "trim",
)

#: `APPLICATION_LAYER_API.md:138` — the history "never returns artifact content,
#: decision reasoning or confidence". A field named for any of these is that
#: boundary being crossed.
REASONING_WORDS = (
    "confidence",
    "artifact",
    "amount",
    "decision",
    "reason",
    "rational",
    "score",
    "probab",
    "certain",
    "doubt",
    "risk",
    "content",
    "payload",
    "body",
    "text",
    "ledger",
    "account",
    "voucher",
    "tax",
    "gst",
    "currency",
    "debit",
    "credit",
    "total",
    "narration",
    "note",
    "evidence",
    "understanding",
    "explanation",
    "judgment",
    "verdict",
)

#: Anything that produces "the current time". `at` is passed in, so none of
#: these may appear anywhere in the module.
CLOCK_ATTRIBUTES = (
    "now",
    "utcnow",
    "today",
    "fromtimestamp",
    "time",
    "time_ns",
    "monotonic",
    "perf_counter",
    "clock_gettime",
)

MODULE_SOURCE = pathlib.Path(str(audit_module.__file__)).read_text(encoding="utf-8")
MODULE_TREE = ast.parse(MODULE_SOURCE)


def imported_modules() -> set[str]:
    """Every module name this module imports, read off disk, not off `sys.modules`."""
    names: set[str] = set()
    for node in ast.walk(MODULE_TREE):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def public_names(target: object) -> list[str]:
    return [name for name in dir(target) if not (name.startswith("__") and name.endswith("__"))]


#: One valid record. Every case below is this one with a single field changed
#: via `dataclasses.replace`, which re-runs `__post_init__` — so a test that
#: breaks one field proves that field is what did it.
VALID = Transition(
    from_state=TransactionState.INPUT,
    to_state=TransactionState.UNDERSTANDING,
    at=AT,
    trigger="engine 1 produced a Document Evidence Object",
    engine="input_engine",
    attempt=1,
)


def transition(
    source: TransactionState | None = TransactionState.INPUT,
    target: TransactionState = TransactionState.UNDERSTANDING,
) -> Transition:
    return dataclasses.replace(VALID, from_state=source, to_state=target)


# ── the record carries workflow, and nothing else ─────────────────────────


def test_the_transition_fields_are_exactly_the_six_the_contract_names() -> None:
    """`APPLICATION_LAYER_API.md:131` — "from · to · timestamp · trigger ·
    engine involved · retry attempt". A seventh field is either reasoning
    crossing :138's boundary or a rename breaking a caller."""
    assert tuple(f.name for f in dataclasses.fields(Transition)) == CONTRACT_FIELDS


@pytest.mark.parametrize("banned", REASONING_WORDS)
def test_no_transition_field_is_named_for_reasoning(banned: str) -> None:
    """:138 — "It never returns artifact content, decision reasoning or
    confidence — those belong to the artifacts and the engines that own them.\" """
    offenders = [f.name for f in dataclasses.fields(Transition) if banned in f.name.lower()]
    assert offenders == [], f"field(s) named for reasoning: {offenders} (matched {banned!r})"


def test_a_transition_cannot_be_given_a_reasoning_field_after_construction() -> None:
    """`slots=True` is what makes :138 structural rather than remembered.

    Without slots, `record.confidence = 0.4` succeeds silently and the next
    reader of the history sees a confidence the engines never published there.
    """
    entry = transition()
    assert not hasattr(entry, "__dict__"), "no __dict__ means no field can be added later"
    assert Transition.__slots__ == CONTRACT_FIELDS
    # CPython 3.12 raises TypeError, not FrozenInstanceError, for an UNDECLARED
    # name on a frozen+slots dataclass — the generated `__setattr__` closes over
    # the pre-slots class and its `super()` call fails first. Which exception
    # CPython picks is CPython's business and may change; that the attribute
    # does not exist afterwards is the claim this test actually makes, and it
    # holds whatever gets raised.
    with pytest.raises((AttributeError, TypeError)):
        entry.confidence = 0.4  # type: ignore[attr-defined]
    assert not hasattr(entry, "confidence")


def test_a_transition_is_frozen() -> None:
    """INV-5 — history is never modified. Correction is a new entry, not an edit."""
    entry = transition()
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.trigger = "something else"  # type: ignore[misc]


def test_no_transition_field_has_a_default() -> None:
    """A default is a field the caller may omit. `at` defaulting to anything
    would be a clock by another route; `attempt` defaulting to 1 would let a
    retry be recorded as a first attempt."""
    defaulted = [
        f.name
        for f in dataclasses.fields(Transition)
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
    ]
    assert defaulted == []


def test_the_record_has_no_releasing_identity_field() -> None:
    """`:131` lists "releasing identity where applicable" and this record does
    not carry it, deliberately.

    The only producer is `release_waiting_for_approval()` (`:84`), which `:7`
    records as depending on an amendment `ARCHITECTURE_AMENDMENTS.md:37` marks
    PROPOSED, not approved. `WaitingForApproval` is not in the locked machine,
    so "where applicable" applies nowhere. If the amendment is approved, THIS
    test is what must be edited deliberately — it will not pass by accident.
    """
    names = {f.name for f in dataclasses.fields(Transition)}
    assert not {n for n in names if "releas" in n or "identity" in n or "approv" in n}
    assert "WaitingForApproval" not in {s.value for s in TransactionState}


# ── append-only ───────────────────────────────────────────────────────────


def test_the_trail_has_exactly_two_methods() -> None:
    """The exact set, not a ban list. A third method called something innocent —
    `reindex`, `vacuum`, `rotate` — is still the compaction :135 forbids."""
    assert sorted(n for n in public_names(AuditTrail) if not n.startswith("_")) == [
        "history",
        "record",
    ]


@pytest.mark.parametrize("banned", DESTRUCTIVE_WORDS)
def test_no_name_on_the_trail_could_remove_or_alter_history(banned: str) -> None:
    """Covers private helpers too, which the exact-set test above does not."""
    on_class = [n for n in public_names(AuditTrail) if banned in n.lower()]
    on_instance = [n for n in public_names(AuditTrail()) if banned in n.lower()]
    assert on_class == [], f"AuditTrail.{on_class} could alter history (matched {banned!r})"
    assert on_instance == [], f"instance attribute {on_instance} (matched {banned!r})"


@pytest.mark.parametrize("banned", DESTRUCTIVE_WORDS)
def test_no_function_in_the_module_could_remove_or_alter_history(banned: str) -> None:
    """Read off the source, so a module-level `def compact_old_trails()` is
    caught even though it is not attached to the class."""
    defined = [
        node.name
        for node in ast.walk(MODULE_TREE)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and banned in node.name.lower()
    ]
    assert defined == [], f"function(s) that could alter history: {defined}"


def test_record_takes_an_id_and_a_transition_and_nothing_else() -> None:
    """A `force=`, `replace=` or `at=` parameter would be the missing delete
    method arriving as an argument instead."""
    assert list(inspect.signature(AuditTrail.record).parameters) == [
        "self",
        "transaction_id",
        "transition",
    ]


def test_history_takes_an_id_and_nothing_else() -> None:
    """`:135` — never truncated. A `limit=`, `since=` or `max_entries=`
    parameter is truncation with a friendlier name, and `:136` calls this a
    pure idempotent read."""
    assert list(inspect.signature(AuditTrail.history).parameters) == ["self", "transaction_id"]


def test_a_recorded_history_is_a_tuple_so_it_cannot_be_shortened_in_place() -> None:
    trail = AuditTrail()
    tid = TransactionId.new()
    trail.record(tid, transition())
    stored = trail.history(tid)
    assert isinstance(stored, tuple)
    with pytest.raises(AttributeError):
        stored.append(transition())  # type: ignore[attr-defined]


def test_holding_an_old_history_cannot_shorten_the_stored_one() -> None:
    """The returned value is the stored value, and it is immutable — so there is
    no reference a caller can keep that lets them edit what is recorded."""
    trail = AuditTrail()
    tid = TransactionId.new()
    first = transition()
    trail.record(tid, first)
    escaped = trail.history(tid)
    second = transition(TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING)
    trail.record(tid, second)
    assert escaped == (first,)
    assert trail.history(tid) == (first, second)
    assert trail.history(tid)[0] is first


def test_recording_the_same_transition_twice_keeps_both() -> None:
    """Deduplication is summarising, which `:135` forbids. A retried edge is two
    events, and `attempt` is what tells them apart."""
    trail = AuditTrail()
    tid = TransactionId.new()
    edge = transition(TransactionState.VALIDATION, TransactionState.EXECUTION)
    first = dataclasses.replace(edge, attempt=FIRST_ATTEMPT)
    second = dataclasses.replace(edge, attempt=SECOND_ATTEMPT)
    trail.record(tid, first)
    trail.record(tid, second)
    assert trail.history(tid) == (first, second)


def test_reading_the_history_never_changes_it() -> None:
    """`:133` — "Postconditions: None. Pure read." `:136` — idempotent."""
    trail = AuditTrail()
    tid = TransactionId.new()
    trail.record(tid, transition())
    before = trail.history(tid)
    for _ in range(5):
        assert trail.history(tid) == before
    assert len(trail.history(tid)) == 1


# ── no clock ──────────────────────────────────────────────────────────────


def test_the_module_imports_exactly_what_it_needs_and_nothing_else() -> None:
    """One assertion covering every dependency ban at once: no `time`, no engine,
    no Brain, no store, no database driver, no file I/O.

    In-memory is the whole of P3. A `sqlite3` or `pathlib` import here is a
    storage decision nobody approved arriving as an import line.
    """
    assert imported_modules() == {
        "__future__",
        "dataclasses",
        "datetime",
        "accountant_dad.identity",
        "accountant_dad.services.state",
    }


@pytest.mark.parametrize("forbidden", ["time", "accountant_dad.engines", "accountant_dad.brain"])
def test_the_module_imports_no_clock_no_engine_and_no_brain(forbidden: str) -> None:
    """Named separately from the exact-set test so the failure says WHY.

    `time` is banned because a module that reads a clock is not reproducible.
    Engines and the Brain are banned because the audit trail records; it does
    not enforce, and AL-INV-8 keeps `services/` and `brain/` unlinked.
    """
    offenders = sorted(m for m in imported_modules() if m == forbidden or m.startswith(forbidden))
    assert offenders == [], f"forbidden import: {offenders}"


def test_the_module_never_imports_the_state_store() -> None:
    """The store owns existence; this module owns history. One concept, one
    owner (INV-10)."""
    assert not any("store" in m for m in imported_modules())


@pytest.mark.parametrize("attribute", CLOCK_ATTRIBUTES)
def test_the_module_never_reads_a_clock(attribute: str) -> None:
    """`datetime.now()`, `time.time()`, `datetime.today()` — all of them make the
    module's output depend on when it ran, which makes "the order is exactly
    this" untestable and makes `at` describe the bookkeeping, not the event."""
    calls = [
        node.attr
        for node in ast.walk(MODULE_TREE)
        if isinstance(node, ast.Attribute) and node.attr == attribute
    ]
    assert calls == [], f"clock read in audit.py: {attribute}"


def test_a_naive_datetime_is_rejected_loudly() -> None:
    """Never assumed to be UTC. Assuming turns a +05:30 stamp into an ordering
    nobody can reproduce, and `:18` says every failure is loud."""
    with pytest.raises(UnrecordableTransitionError, match="timezone-aware"):
        dataclasses.replace(VALID, at=datetime(2026, 8, 4, 9, 30))


@pytest.mark.parametrize("offset_hours", [0, 5.5, -8, 14])
def test_any_aware_datetime_is_accepted(offset_hours: float) -> None:
    """The rule is "carries its offset", not "is UTC". India is +05:30 and the
    MVP is the Indian GST regime."""
    tz = timezone(timedelta(hours=offset_hours))
    assert dataclasses.replace(VALID, at=datetime(2026, 8, 4, 9, 30, tzinfo=tz)).at.tzinfo is tz


def test_a_datetime_whose_zone_yields_no_offset_is_rejected() -> None:
    """`tzinfo is not None` is not the same question as "aware". A tzinfo whose
    `utcoffset()` returns None is naive wearing a timezone."""

    class NoOffset(tzinfo):
        def utcoffset(self, _dt: datetime | None) -> timedelta | None:
            return None

        def tzname(self, _dt: datetime | None) -> str | None:
            return "fake"

        def dst(self, _dt: datetime | None) -> timedelta | None:
            return None

    with pytest.raises(UnrecordableTransitionError, match="timezone-aware"):
        dataclasses.replace(VALID, at=datetime(2026, 8, 4, 9, 30, tzinfo=NoOffset()))


# ── the record must describe something that happened ──────────────────────


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n", "   \n  "])
def test_a_blank_trigger_is_rejected(blank: str) -> None:
    """`:131` lists the trigger. An entry recording the movement but not its
    cause leaves the reader inferring, which is what `:126` exists to prevent."""
    with pytest.raises(UnrecordableTransitionError, match="trigger"):
        dataclasses.replace(VALID, trigger=blank)


@pytest.mark.parametrize("blank", ["", " ", "\t"])
def test_a_blank_engine_name_is_rejected(blank: str) -> None:
    """`None` is the answer for "no engine was involved". A blank string is a
    missing answer wearing the shape of one."""
    with pytest.raises(UnrecordableTransitionError, match="engine"):
        dataclasses.replace(VALID, engine=blank)


def test_no_engine_is_recorded_as_none() -> None:
    assert dataclasses.replace(transition(None, INITIAL_STATE), engine=None).engine is None


@pytest.mark.parametrize("attempt", [0, -1, -100])
def test_an_attempt_below_one_is_rejected(attempt: int) -> None:
    """`APPLICATION_LAYER_INVARIANTS.md:172` — retry is a transition attribute,
    never a state. Counting from 1 means attempt 0 describes a transition nobody
    made; it is not "before the first try", it is nothing."""
    with pytest.raises(UnrecordableTransitionError, match="attempt"):
        dataclasses.replace(VALID, attempt=attempt)


def test_a_retry_is_an_attribute_and_never_a_state() -> None:
    """AL-INV-13 forbids a `Retrying` state, so the second attempt at the same
    edge is the SAME two states with a different `attempt`."""
    assert "Retrying" not in {s.value for s in TransactionState}
    edge = transition(TransactionState.VALIDATION, TransactionState.EXECUTION)
    retried = dataclasses.replace(edge, attempt=THIRD_ATTEMPT)
    assert retried.attempt == THIRD_ATTEMPT
    assert retried.from_state is TransactionState.VALIDATION
    assert retried.to_state is TransactionState.EXECUTION


def test_the_creation_entry_has_no_previous_state() -> None:
    """`APPLICATION_LAYER_API.md:32` — start_transaction() leaves the transaction
    in `Input` and audit records the creation."""
    created = dataclasses.replace(
        transition(None, INITIAL_STATE), engine=None, trigger="start_transaction()"
    )
    assert created.from_state is None
    assert created.to_state is INITIAL_STATE


@pytest.mark.parametrize("target", [s for s in TransactionState if s is not INITIAL_STATE])
def test_a_creation_entry_that_does_not_end_in_input_is_rejected(
    target: TransactionState,
) -> None:
    """`from_state=None` anywhere but creation claims a transaction had no
    previous state when it did — the one thing this record must never say."""
    with pytest.raises(UnrecordableTransitionError, match="creation entry"):
        transition(None, target)


@pytest.mark.parametrize("state", list(TransactionState))
def test_a_state_to_itself_is_rejected(state: TransactionState) -> None:
    """AL-INV-2 — exactly one state at any moment. `state.py` rejects the same
    pair; recording it would preserve, permanently, movement that never was."""
    with pytest.raises(UnrecordableTransitionError, match="itself"):
        transition(state, state)


@pytest.mark.parametrize(("source", "target"), sorted(ALLOWED_TRANSITIONS))
def test_every_edge_the_locked_machine_draws_can_be_recorded(
    source: TransactionState, target: TransactionState
) -> None:
    """Exhaustive over the whitelist. A record type that refuses a legal edge is
    a history with holes in it, which is the same failure as one with fictions."""
    entry = transition(source, target)
    assert entry.from_state is source
    assert entry.to_state is target


def test_every_pair_outside_the_whitelist_is_refused() -> None:
    """Exhaustive over all 64 ordered pairs — AL-INV-3, a recorded transition is
    one that actually completed, so an edge that cannot happen cannot be one.

    Attacks the delegation as well as the rule: if this module ever grew its own
    copy of the transition table, this test is where the two copies disagree.
    """
    leaked: list[str] = []
    for source, target in itertools.product(TransactionState, repeat=2):
        if (source, target) in ALLOWED_TRANSITIONS:
            continue
        try:
            transition(source, target)
        except UnrecordableTransitionError:
            continue
        leaked.append(f"{source.value} -> {target.value}")
    assert leaked == [], f"recordable but impossible: {leaked}"


def test_the_refusal_of_an_impossible_edge_says_why() -> None:
    """A refusal nobody can act on is a failure that gets worked around."""
    with pytest.raises(UnrecordableTransitionError) as raised:
        transition(TransactionState.INPUT, TransactionState.EXECUTION)
    message = str(raised.value)
    assert "not in the locked state machine" in message
    assert "AL-INV-3" in message


def test_a_rejection_is_an_exception_not_a_return_value() -> None:
    """`:18` — "Every failure is loud. Nothing returns a default on error." No
    boolean anyone could forget to check."""
    assert issubclass(UnrecordableTransitionError, Exception)
    assert not hasattr(Transition, "is_valid")


# ── ordering, isolation, and the unknown transaction ──────────────────────


def test_the_order_recorded_is_the_order_returned() -> None:
    """`:131` — "Every transition in order". Insertion order, exactly."""
    trail = AuditTrail()
    tid = TransactionId.new()
    chain = [
        dataclasses.replace(
            transition(None, TransactionState.INPUT), engine=None, trigger="start_transaction()"
        ),
        transition(TransactionState.INPUT, TransactionState.UNDERSTANDING),
        transition(TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING),
        transition(TransactionState.ACCOUNTING, TransactionState.VALIDATION),
        transition(TransactionState.VALIDATION, TransactionState.EXECUTION),
        transition(TransactionState.EXECUTION, TransactionState.COMPLETED),
    ]
    for entry in chain:
        trail.record(tid, entry)
    assert trail.history(tid) == tuple(chain)
    assert [e.to_state for e in trail.history(tid)] == [e.to_state for e in chain]


def test_the_order_recorded_wins_over_the_timestamps() -> None:
    """`at` is data in the record, not the index of it. Re-sorting by timestamp
    would let one caller's clock skew rewrite the order of events it did not
    control — and the rewritten order would look authoritative."""
    trail = AuditTrail()
    tid = TransactionId.new()
    later = dataclasses.replace(transition(), at=AT)
    earlier = dataclasses.replace(
        transition(TransactionState.UNDERSTANDING, TransactionState.ACCOUNTING),
        at=AT - timedelta(hours=3),
    )
    trail.record(tid, later)
    trail.record(tid, earlier)
    assert trail.history(tid) == (later, earlier)


def test_two_transactions_are_kept_separate() -> None:
    trail = AuditTrail()
    first, second = TransactionId.new(), TransactionId.new()
    a = dataclasses.replace(transition(), trigger="a")
    b = dataclasses.replace(
        transition(TransactionState.ACCOUNTING, TransactionState.VALIDATION), trigger="b"
    )
    trail.record(first, a)
    trail.record(second, b)
    assert trail.history(first) == (a,)
    assert trail.history(second) == (b,)


def test_a_later_record_for_another_transaction_leaves_this_history_alone() -> None:
    """AL-INV-1 — the Transaction ID is the whole of the partition. A shared
    list behind the scenes would show up exactly here."""
    trail = AuditTrail()
    mine, theirs = TransactionId.new(), TransactionId.new()
    entry = transition()
    trail.record(mine, entry)
    before = trail.history(mine)
    noise = transition(TransactionState.ACCOUNTING, TransactionState.VALIDATION)
    for _ in range(OTHER_RECORDS):
        trail.record(theirs, noise)
    assert trail.history(mine) == before == (entry,)
    assert len(trail.history(theirs)) == OTHER_RECORDS


def test_an_unknown_transaction_returns_empty_rather_than_raising() -> None:
    """A REPORTED divergence from `get_transaction_history()`'s `:132`/`:135`
    contract, which rejects an unknown Transaction ID.

    Existence is the state store's question — `APPLICATION_LAYER_INVARIANTS.md:32`,
    "The state store permits exactly one row per Transaction ID." This class
    holds history, not existence; rejecting here would make two owners of one
    concept (INV-10) or force it to import the store, the one dependency it is
    specified not to have. The rejection belongs to the caller that owns
    existence, and is not implemented here.
    """
    trail = AuditTrail()
    assert trail.history(TransactionId.new()) == ()


def test_an_empty_history_is_empty_and_not_a_default_entry() -> None:
    """`:18` — nothing returns a default. An invented "Input" entry for an
    unknown ID would be a fabricated record (Law 24)."""
    empty = AuditTrail().history(TransactionId.new())
    assert empty == ()
    assert isinstance(empty, tuple)
    assert len(empty) == 0


def test_two_trails_share_nothing() -> None:
    """A dict on the class instead of the instance would make every AuditTrail in
    the process one trail, and the tests above would still pass."""
    first, second = AuditTrail(), AuditTrail()
    tid = TransactionId.new()
    first.record(tid, transition())
    assert second.history(tid) == ()
