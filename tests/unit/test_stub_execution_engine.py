"""Tests for the Execution Engine stub. Written to prove it POSTS, not that it works.

The stub's whole job is negative — produce a valid artifact, contact nothing,
invent nothing — and a negative is exactly what a confirming test misses. So the
file is organised by the ways it could do harm, worst first:

  1. It claims a posting that did not happen. Tested by asserting the empty
     `external_transaction_ids`, the zero transport confidence, and that no
     open-vocabulary field borrows a real destination's vocabulary.
  2. It actually reaches something. Tested by parsing the module with `ast` and
     asserting its ENTIRE import list against an allowlist, plus a blacklist of
     identifiers that need no import (`open`, `eval`, `__import__`). A source
     TEXT scan was rejected: it would trip over the words in the module's own
     prose and would have to be loosened until it caught nothing.
  3. It bypasses Engine 5 by recording an execution for an unapproved decision.
  4. It hides the non-execution where a consumer would not look.

Two tests are the tripwires this file exists for. `test_the_module_imports...`
and `test_no_identifier_that_touches_the_outside_world...` go red the moment an
edit adds a socket, a file write or a subprocess — which is the one change to
this module that could put a fabricated entry into somebody's books.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.execution import (
    ExecutionAttemptId,
    ExecutionId,
    ExecutionResult,
    IdempotencyKey,
)
from accountant_dad.artifacts.validation import (
    APPROVING_STATUSES,
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationFinding,
    ValidationStatus,
)
from accountant_dad.engines.tally_engine import stub
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

FIRST_VERSION = 1
SECOND_VERSION = 2

#: Fixed, not `.new()`. Two calls must be comparable for equality, which is the
#: only way to assert that the stub reads no clock and rolls no dice.
EXECUTION_ARTIFACT_ID = ArtifactId(uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
DECISION_ID = ArtifactId(uuid.UUID("11111111-1111-4111-8111-111111111111"))
OTHER_DECISION_ID = ArtifactId(uuid.UUID("22222222-2222-4222-8222-222222222222"))
VALIDATION_ID = ArtifactId(uuid.UUID("33333333-3333-4333-8333-333333333333"))
TRANSACTION_ID = TransactionId(uuid.UUID("44444444-4444-4444-8444-444444444444"))
EXECUTION_ID = ExecutionId(uuid.UUID("55555555-5555-4555-8555-555555555555"))
ATTEMPT_ID = ExecutionAttemptId(uuid.UUID("66666666-6666-4666-8666-666666666666"))

MOMENT = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)

#: `ENGINE_6_EXECUTION_ENGINE_RULES.md:65` — the destinations the specification
#: itself names. None of these words may appear in anything the stub emits.
REAL_DESTINATIONS = ("tally", "zoho", "busy", "sap", "quickbooks")

#: The five opaque fields of the Execution Result whose values no document
#: enumerates (`artifacts/execution.py`, `UNENUMERATED_FIELDS`).
OPEN_VOCABULARY_FIELDS = (
    "destination_system",
    "posting_status",
    "queue_status",
    "notification_status",
    "execution_outcome",
)

#: Everything the module is allowed to import, by top-level root. A SUBSET
#: assertion, not a blacklist: a blacklist only catches the names I thought of,
#: and the import that puts an entry in someone's books is the one I did not.
ALLOWED_IMPORT_ROOTS = frozenset({"__future__", "datetime", "decimal", "accountant_dad"})

#: Names that reach the outside world without needing an import, plus the clock
#: and the dice. `now`/`utcnow`/`today` are here because `datetime` IS on the
#: allowlist above — the import is legitimate, reading the clock is not.
FORBIDDEN_IDENTIFIERS = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "socket",
        "urlopen",
        "connect",
        "sendall",
        "system",
        "popen",
        "Popen",
        "check_output",
        "write",
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "unlink",
        "mkdir",
        "environ",
        "getenv",
        "now",
        "utcnow",
        "today",
        "monotonic",
        "sleep",
        "uuid4",
        "uuid1",
        "random",
        "choice",
        "shuffle",
        "print",
    }
)


def _finding() -> ValidationFinding:
    return ValidationFinding(
        what_failed="the supplier GSTIN is absent from the document",
        why_it_failed="no GSTIN appears on the invoice and none was supplied",
        responsible_engine=ResponsibleEngine.INPUT,
        affected_artifact="Document Evidence Object",
        blocking_severity=Severity.HIGH,
        recommended_next_step="ask the user for the supplier GSTIN",
        supporting_evidence_references=("page 1, header block",),
    )


def _validation(
    status: ValidationStatus = ValidationStatus.APPROVED,
    related_decision_id: ArtifactId = DECISION_ID,
    related_artifact_version: int = FIRST_VERSION,
) -> ValidationDecision:
    """A real Validation Decision, built through its own validators (§J.6).

    A non-approving status must record at least one issue or the artifact
    refuses to exist, so the finding is attached exactly when it is required.
    """
    blocking = status not in APPROVING_STATUSES
    return ValidationDecision(
        identity=IdentityEnvelope(
            artifact_id=VALIDATION_ID,
            version=FIRST_VERSION,
            parent_versions=(),
            transaction_id=TRANSACTION_ID,
        ),
        related_decision_id=related_decision_id,
        related_artifact_version=related_artifact_version,
        validation_status=status,
        validation_findings=(_finding(),) if blocking else (),
        validation_errors=(),
        validation_warnings=(),
        validation_risks=(),
        failed_validation_rules=(),
        supporting_evidence_references=("page 1, header block",),
        validation_confidence=Decimal("0.9000"),
        validation_reasoning="recorded by the Validation Engine for this decision",
        validation_timestamp=datetime(2026, 8, 4, 9, 0, tzinfo=UTC),
    )


def _identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=EXECUTION_ARTIFACT_ID,
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TRANSACTION_ID,
    )


def _call(**overrides: object) -> ExecutionResult:
    arguments: dict[str, object] = {
        "identity": _identity(),
        "execution_id": EXECUTION_ID,
        "execution_attempt_id": ATTEMPT_ID,
        "validation": _validation(),
        "execution_timestamp": MOMENT,
    }
    arguments.update(overrides)
    return stub.report_nothing_posted(**arguments)  # type: ignore[arg-type]


def _module_tree() -> ast.Module:
    return ast.parse(inspect.getsource(stub))


def _imported_names() -> set[str]:
    """Every dotted name the stub imports — what it imports FROM, and what it
    pulls OUT of it.

    Both halves, and the second one is not decoration. A mutation pass caught
    this test in its first form: `from accountant_dad.engines import
    input_engine` reaches sideways into another engine while the module it
    imports *from* is only `accountant_dad.engines`, so recording the source
    alone let an AL-INV-5 violation through green. Recording both closes it.

    A relative import contributes a leading dot and therefore fails the
    allowlist, which is correct — its root cannot be read off this file alone.
    """
    found: set[str] = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            source = "." * node.level + (node.module or "")
            found.add(source)
            found.update(f"{source}.{alias.name}" for alias in node.names)
    return found


def _identifiers() -> set[str]:
    """Every name and attribute the module actually references.

    The AST, not the text. Scanning the source string would match the words in
    the module's own docstring — which names `socket` and `uuid4` precisely
    because it promises not to use them — and the test would have to be loosened
    until it caught nothing.
    """
    found: set[str] = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            found.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
    return found


# ── 1. It claims nothing that did not happen ──────────────────────────────
# `ENGINE_6:458` — "Never assume success. Never invent external IDs."


def test_no_external_transaction_id_is_invented() -> None:
    """The field that would be PROOF a voucher reached a ledger. Empty is the
    only honest value, and an empty tuple is a real answer, not a missing one."""
    assert _call().external_transaction_ids == ()


def test_the_transport_confidence_is_zero() -> None:
    """`ENGINE_6:177` — Execution Confidence is transport success ONLY. No
    transport happened, so there is no evidence of transport success."""
    assert _call().execution_confidence == Decimal("0.0000")


def test_the_retry_count_is_zero_because_nothing_was_attempted() -> None:
    assert _call().retry_count == 0


def test_the_stub_never_claims_to_have_corrected_a_posting() -> None:
    """`ENGINE_6:79` — Engine 6 must never invent corrections."""
    assert _call().corrects_execution_result is None


@pytest.mark.parametrize("field", OPEN_VOCABULARY_FIELDS)
def test_every_open_vocabulary_field_opens_with_a_negation(field: str) -> None:
    """The first token is what a human skimming a log actually reads. If any of
    these ever starts with something affirmative, a stub record has begun to
    look like a posting."""
    value = getattr(_call(), field)

    assert value.startswith(("NONE", "NOT")), (
        f"{field} does not state that nothing happened: {value}"
    )


@pytest.mark.parametrize("field", OPEN_VOCABULARY_FIELDS)
@pytest.mark.parametrize("destination", REAL_DESTINATIONS)
def test_no_open_vocabulary_field_borrows_a_real_destinations_name(
    field: str, destination: str
) -> None:
    """`ENGINE_6:321` leaves the destination set OPEN, so nothing stops this
    module writing `"Tally"` into `destination_system`. Nothing except this.

    A record naming a real destination asserts that destination was contacted,
    and `posting_manager` keys duplicate protection on that exact string
    (`ENGINE_6:401`) — so a stub borrowing the name would also occupy the
    idempotency slot of the real posting that has not happened yet.
    """
    assert destination not in getattr(_call(), field).lower()


@pytest.mark.parametrize("destination", ["Tally", "Zoho Books", "Busy", "SAP", "QuickBooks"])
def test_the_idempotency_key_can_never_collide_with_a_real_destination(destination: str) -> None:
    """The consequence of the test above, asserted on the key itself.

    `ENGINE_6:401` — the key is Accounting Decision ID + Decision Version +
    Destination System. Two of the three are shared with the real posting, so
    only the destination keeps a stub out of the real posting's slot.
    """
    assert _call().idempotency_key != IdempotencyKey(
        accounting_decision_id=DECISION_ID,
        decision_version=FIRST_VERSION,
        destination_system=destination,
    )


def test_the_classified_error_names_no_real_destination_either() -> None:
    """`cause` is free text and is the easiest place for a destination's name to
    reappear once someone pastes a real response into it."""
    error = _call().classified_error
    assert error is not None

    for destination in REAL_DESTINATIONS:
        assert destination not in error.cause.lower()
        assert destination not in error.category.lower()
        assert destination not in error.severity.lower()


# ── 2. It reaches nothing ─────────────────────────────────────────────────
# The tripwires. `CLAUDE.md` §K.6 — nothing posts to a real ledger.


def test_the_module_imports_nothing_outside_the_allowlist() -> None:
    """No network, no file I/O, no subprocess — and no anything-else either.

    Asserted as a subset of an allowlist rather than as the absence of a
    blacklist, because the import that would post an entry is by definition the
    one nobody predicted. `requests`, `socket`, `pathlib` and `subprocess` all
    fail this, and so does a name that does not exist yet.
    """
    roots = {name.split(".")[0] for name in _imported_names()}

    assert roots <= ALLOWED_IMPORT_ROOTS, (
        f"the Execution Engine stub imports {sorted(roots - ALLOWED_IMPORT_ROOTS)}. "
        "Nothing in this module may reach the outside world (CLAUDE.md section P "
        "freezes Tally posting; section K.6 — nothing posts to a real ledger)."
    )


def test_no_identifier_that_touches_the_outside_world_appears_in_the_module() -> None:
    """`open` and `eval` need no import, and `datetime` is on the allowlist —
    so the import test alone would not catch `datetime.now()` or a file write."""
    used = _identifiers() & FORBIDDEN_IDENTIFIERS

    assert used == set(), (
        f"the Execution Engine stub references {sorted(used)}. It must read no "
        "clock, roll no dice and touch no file, socket or process."
    )


def test_no_other_engine_is_imported() -> None:
    """AL-INV-5 — engines never call each other; every artifact passes through
    the Application Layer. AL-INV-11 — Engine 6 has no backward arrow at all."""
    reaching_sideways = sorted(
        name
        for name in _imported_names()
        if name.startswith("accountant_dad.engines")
        and not name.startswith("accountant_dad.engines.tally_engine")
    )

    assert reaching_sideways == [], (
        f"AL-INV-5 broken by {reaching_sideways}. The bare `accountant_dad.engines` "
        "package is refused too: a module inside it has no reason to import it, "
        "and importing it is one `getattr` away from holding another engine."
    )


def test_the_application_layer_is_not_imported() -> None:
    """AL-INV-4 — no engine may read, write, observe or infer transaction
    state. The conformance check named there is exactly this one: no engine
    module imports the state store."""
    reaching_up = sorted(
        name for name in _imported_names() if name.startswith("accountant_dad.services")
    )

    assert reaching_up == [], f"AL-INV-4 broken by {reaching_up}"


def test_the_module_offers_exactly_one_public_callable() -> None:
    """A second function is where a `post_to_tally` helper would arrive."""
    public = {
        name
        for name, value in vars(stub).items()
        if not name.startswith("_")
        and callable(value)
        and getattr(value, "__module__", "") == stub.__name__
    }

    assert public == {"report_nothing_posted"}


def test_no_caller_can_tell_the_stub_which_destination_it_reached() -> None:
    """The structural half of the anti-mimicry rule.

    Every value that names a destination or a status is fixed in the module.
    If `destination_system` were a parameter, a caller could make this stub emit
    a record indistinguishable from a Tally posting without editing a line here.
    """
    parameters = inspect.signature(stub.report_nothing_posted).parameters

    assert set(parameters) == {
        "identity",
        "execution_id",
        "execution_attempt_id",
        "validation",
        "execution_timestamp",
    }
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values()
    ), "positional arguments let two identities be swapped silently"


# ── 3. It never bypasses Engine 5 ─────────────────────────────────────────
# `ENGINE_6:151` · AL-INV-6.


@pytest.mark.parametrize(
    "status", [ValidationStatus.APPROVED, ValidationStatus.APPROVED_WITH_WARNING]
)
def test_an_approving_decision_produces_a_record(status: ValidationStatus) -> None:
    """`Approved With Warning` is included: `ENGINE_6:147` says the Application
    Layer releases it after human attention, and AL-INV-4 forbids Engine 6 from
    learning that the gate existed — so it cannot refuse what it cannot see."""
    assert isinstance(_call(validation=_validation(status)), ExecutionResult)


@pytest.mark.parametrize(
    "status", [ValidationStatus.REJECTED, ValidationStatus.CLARIFICATION_REQUIRED]
)
def test_a_non_approving_decision_raises_instead_of_producing_a_record(
    status: ValidationStatus,
) -> None:
    """An Execution Result naming a rejected decision is a bypass of Engine 5
    written into the permanent record, whether or not anything posted."""
    with pytest.raises(ValueError, match="not approving"):
        _call(validation=_validation(status))


def test_the_decision_and_version_are_read_off_the_validation_decision() -> None:
    """So the record cannot name a decision version nobody validated."""
    result = _call(
        validation=_validation(
            related_decision_id=OTHER_DECISION_ID, related_artifact_version=SECOND_VERSION
        )
    )

    assert result.accounting_decision_id == OTHER_DECISION_ID
    assert result.decision_version == SECOND_VERSION
    assert result.validation_decision_id == VALIDATION_ID


# ── 4. The non-execution is visible where a consumer looks ────────────────
# `ENGINE_6:245-253` · `ENGINE_6:491`.


def test_the_non_execution_is_reported_through_the_classified_error() -> None:
    """`classified_error is None` is what a consumer reads as "no trouble", so
    leaving it empty would hide the one fact that matters here."""
    error = _call().classified_error

    assert error is not None
    assert error.category.startswith("NOT")
    assert "stub" in error.cause.lower()


def test_retry_is_not_permitted() -> None:
    """AL-INV-12 — only runtime failures are retried. A stub is not a runtime
    failure, and retrying would return this identical record forever."""
    error = _call().classified_error

    assert error is not None
    assert error.retry_permissible is False


def test_the_responsible_stage_is_this_engine_and_no_other() -> None:
    """AL-INV-11 — Engine 6 names the responsible stage; the Application Layer
    routes. Naming an earlier engine here would be routing by suggestion."""
    error = _call().classified_error

    assert error is not None
    assert error.responsible_stage == "Execution Engine"
    for other in ("input", "understanding", "accounting", "clarification", "validation"):
        assert other not in error.responsible_stage.lower()


# ── 5. It is reproducible ─────────────────────────────────────────────────
# No clock, no randomness. Everything that varies is an argument.


def test_two_identical_calls_produce_equal_records() -> None:
    """The behavioural half of the no-clock rule. A `datetime.now()` or a
    `uuid4()` anywhere in the module makes this fail."""
    assert _call() == _call()


def test_the_timestamp_is_the_one_supplied_and_nothing_else() -> None:
    later = datetime(2026, 12, 25, 18, 45, tzinfo=UTC)

    assert _call().execution_timestamp == MOMENT
    assert _call(execution_timestamp=later).execution_timestamp == later


def test_a_naive_timestamp_is_refused_rather_than_localised() -> None:
    """The artifact's own validator has to fire through the stub. A stub that
    attached a timezone would be inventing the one thing it was handed."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        _call(execution_timestamp=datetime(2026, 8, 4, 9, 30))


def test_a_non_utc_timestamp_is_accepted() -> None:
    """No document requires UTC, so nothing here may require it."""
    ist = datetime(2026, 8, 4, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    assert _call(execution_timestamp=ist).execution_timestamp == ist


@pytest.mark.parametrize("hostile", ["2026-08-04T09:30:00Z", 1786000000, None])
def test_a_timestamp_that_is_not_a_datetime_is_refused(hostile: object) -> None:
    """The integer is the dangerous one: pydantic's lax mode would read it as a
    unix timestamp and a mistyped count would become a posting time."""
    with pytest.raises(ValidationError, match="must be a datetime"):
        _call(execution_timestamp=hostile)


# ── 6. The artifact is the real one ───────────────────────────────────────
# INV-5 · §J.6 — exercise the production dependency, not a stand-in.


def test_the_record_is_an_execution_result_and_is_immutable() -> None:
    result = _call()

    assert isinstance(result, ExecutionResult)
    with pytest.raises(ValidationError):
        result.posting_status = "posted"


def test_the_audit_reference_points_at_this_execution() -> None:
    """`ENGINE_6:507` — one Audit Record per Execution ID. A reference pointing
    elsewhere looks like traceability and leads somewhere else."""
    assert _call().audit_reference.execution_id == EXECUTION_ID


def test_the_identity_envelope_is_the_real_one_with_its_validators_intact() -> None:
    """Not a stand-in: the envelope's own lineage rule must still fire."""
    with pytest.raises(ValidationError, match="must record the parent version"):
        _call(
            identity=IdentityEnvelope(
                artifact_id=EXECUTION_ARTIFACT_ID,
                version=SECOND_VERSION,
                parent_versions=(),
                transaction_id=TRANSACTION_ID,
            )
        )


def test_a_corrected_execution_still_records_its_lineage() -> None:
    """A stub result can legitimately be version 2 of an Execution Result; the
    envelope, not this module, is what keeps the chain intact (INV-5)."""
    result = _call(
        identity=IdentityEnvelope(
            artifact_id=EXECUTION_ARTIFACT_ID,
            version=SECOND_VERSION,
            parent_versions=(
                ParentVersion(artifact_id=EXECUTION_ARTIFACT_ID, version=FIRST_VERSION),
            ),
            transaction_id=TRANSACTION_ID,
        )
    )

    assert result.identity.parent_versions[0].version == FIRST_VERSION


def test_an_attempt_id_cannot_be_passed_where_an_execution_id_belongs() -> None:
    """INV-3's argument. The stub must not launder a type error into a record."""
    with pytest.raises(ValidationError):
        _call(execution_id=ATTEMPT_ID)


def test_the_transaction_id_travels_unchanged() -> None:
    """`ENGINE_6:138` — Engine 6 must never modify any upstream artifact, and
    `ENGINE_6:163` — the Transaction ID is lifecycle grouping only."""
    result = _call()

    assert result.identity.transaction_id == TRANSACTION_ID
    assert result.identity.transaction_id == _validation().transaction_id
