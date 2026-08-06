"""Tests for the Execution Result — the artifact Engine 6 publishes.

Written before the schema existed, and every one of them was watched failing
first. The order of the file follows the order of the risk:

  1. The idempotency triple. `DATA_FLOW.md:693` — exactly once per
     Accounting Decision ID + Decision Version + Destination System. A duplicate
     posting is the failure this whole engine exists to prevent, so the triple
     gets the most tests and the sharpest ones.
  2. Transport, not reasoning. `DATA_FLOW.md:357` names eight things Engine 6
     may never record. Each is asserted rejected by name.
  3. Everything else — identity, immutability, timestamps, opaque values.

Two assertions in here record behaviour that is DANGEROUS rather than desired:
`test_destination_system_is_case_sensitive...` and
`test_repeated_external_transaction_ids_are_preserved...`. Both are marked. They
exist so the exposure cannot change silently, not because it is good.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.execution import (
    UNENUMERATED_FIELDS,
    AuditReference,
    ClassifiedError,
    ExecutionAttemptId,
    ExecutionId,
    ExecutionResult,
    IdempotencyKey,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

# Ruff's PLR2004 flags a bare integer in a comparison, correctly: a number in an
# assertion should say what it counts.
COLLAPSED_TO_ONE = 1
TWO_DISTINCT = 2

#: `DATA_FLOW.md:357` — the eight things the Execution Engine may NEVER decide,
#: and therefore may never record. Plus concrete Engine 3 field names
#: (`DATA_FLOW.md:97-111`) that an implementer would plausibly reach for, because
#: the hostile input is the realistic name, not the abstract one.
FORBIDDEN_ACCOUNTING_FIELDS = (
    "accounting_treatment",
    "journal_structure",
    "ledger_selection",
    "tax_treatment",
    "validation_approval",
    "clarification_requirements",
    "business_meaning",
    "accounting_confidence",
    "debit_entries",
    "credit_entries",
    "ledger_classification",
    "accounting_assumptions",
    "decision_confidence",
    "unresolved_doubts",
)

#: `ENGINE_6_EXECUTION_ENGINE_RULES.md:159-179` and `DATA_FLOW.md:45`, exactly.
#: Transaction ID is not listed here because it lives inside the identity
#: envelope — `DATA_FLOW.md:32`: *"the identity envelope is universal and not
#: repeated."*
EXPECTED_FIELDS = frozenset(
    {
        "identity",
        "execution_id",
        "execution_attempt_id",
        "accounting_decision_id",
        "decision_version",
        "validation_decision_id",
        "destination_system",
        "corrects_execution_result",
        "posting_status",
        "external_transaction_ids",
        "retry_count",
        "queue_status",
        "notification_status",
        "classified_error",
        "audit_reference",
        "execution_outcome",
        "execution_confidence",
        "execution_timestamp",
    }
)

DECISION_ID = ArtifactId(uuid.UUID("11111111-1111-4111-8111-111111111111"))
OTHER_DECISION_ID = ArtifactId(uuid.UUID("22222222-2222-4222-8222-222222222222"))
VALIDATION_ID = ArtifactId(uuid.UUID("33333333-3333-4333-8333-333333333333"))

FIRST_VERSION = 1
SECOND_VERSION = 2


def messages(raised: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    """Every message pydantic reported, EXACTLY as the validator worded it.

    Equality, not substring. Every refusal in `execution.py` is written to tell
    an operator what a destination sent back that could not be recorded, and
    `match="must be a string"` passes against a message whose remaining half
    has been deleted — measured, not supposed: twenty mutations of these
    refusals survived CI run 30946373087 with every test in this file green.
    """
    return [str(error["msg"]) for error in raised.value.errors()]


class LyingText(str):
    """A `str` whose inequality test always answers "equal".

    Not a curiosity. `_opaque_value` asks `value != value.strip()` and then,
    separately, `not value.strip()`. For an ordinary string the second question
    can never be reached, because anything that strips to nothing is unequal to
    its own strip and is refused as padded first. It is reachable for a value
    that ANSWERS the first question falsely — and this artifact validates
    untrusted input (§C.23), where the object handed in is whatever the caller
    constructed, not necessarily a plain `str`.

    So the blank check is the second line, and this is the input that proves it
    is a line rather than dead code.
    """

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return super().__hash__()


def _identity(transaction_id: TransactionId | None = None) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=transaction_id if transaction_id is not None else TransactionId.new(),
    )


def _classified_error() -> ClassifiedError:
    return ClassifiedError(
        category="transport",
        cause="the destination closed the connection before acknowledging the voucher",
        severity="high",
        retry_permissible=True,
        responsible_stage="tally_connector",
    )


def _fields() -> dict[str, object]:
    """One complete, valid set of constructor arguments."""
    execution_id = ExecutionId.new()
    return {
        "identity": _identity(),
        "execution_id": execution_id,
        "execution_attempt_id": ExecutionAttemptId.new(),
        "accounting_decision_id": DECISION_ID,
        "decision_version": FIRST_VERSION,
        "validation_decision_id": VALIDATION_ID,
        "destination_system": "Tally",
        "corrects_execution_result": None,
        "posting_status": "posted",
        "external_transaction_ids": ("TALLY-VCH-0001",),
        "retry_count": 0,
        "queue_status": "not-queued",
        "notification_status": "sent",
        "classified_error": None,
        "audit_reference": AuditReference(execution_id=execution_id),
        "execution_outcome": "success",
        "execution_confidence": Decimal("0.9800"),
        "execution_timestamp": datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
    }


def _result(**overrides: object) -> ExecutionResult:
    """A valid Execution Result, with the named fields replaced.

    Overriding `execution_id` re-derives `audit_reference` unless the test
    overrode that too — otherwise every execution_id test would fail on the
    audit-reference invariant instead of the thing it is testing.
    """
    fields = _fields()
    fields.update(overrides)
    if "execution_id" in overrides and "audit_reference" not in overrides:
        fields["audit_reference"] = AuditReference(execution_id=overrides["execution_id"])  # type: ignore[arg-type]
    return ExecutionResult(**fields)  # type: ignore[arg-type]


# ── 1. The idempotency triple ─────────────────────────────────────────────
# `DATA_FLOW.md:693` · `ENGINE_6_EXECUTION_ENGINE_RULES.md:401` ·
# `COMMUNICATION_RULES_EXECUTION_INTERNAL.md:108`.


def test_the_key_is_exactly_the_three_specified_components() -> None:
    key = _result().idempotency_key

    assert key == IdempotencyKey(
        accounting_decision_id=DECISION_ID,
        decision_version=FIRST_VERSION,
        destination_system="Tally",
    )


def test_two_results_carrying_the_same_triple_are_detectable_as_duplicates() -> None:
    """The central test. Two independently built results, same triple."""
    first = _result()
    second = _result()

    assert first != second, "different executions, so the artifacts must differ"
    assert first.idempotency_key == second.idempotency_key
    assert hash(first.idempotency_key) == hash(second.idempotency_key)
    assert len({first.idempotency_key, second.idempotency_key}) == COLLAPSED_TO_ONE


def test_a_different_accounting_decision_id_makes_the_key_distinct() -> None:
    first = _result()
    second = _result(accounting_decision_id=OTHER_DECISION_ID)

    assert first.idempotency_key != second.idempotency_key
    assert len({first.idempotency_key, second.idempotency_key}) == TWO_DISTINCT


def test_a_different_decision_version_makes_the_key_distinct_so_a_correction_posts() -> None:
    """`COMMUNICATION_RULES_EXECUTION_INTERNAL.md:116` — a correction must post."""
    original = _result(decision_version=FIRST_VERSION)
    correction = _result(decision_version=SECOND_VERSION)

    assert original.idempotency_key != correction.idempotency_key
    assert len({original.idempotency_key, correction.idempotency_key}) == TWO_DISTINCT


def test_a_different_destination_makes_the_key_distinct_so_the_second_destination_posts() -> None:
    """`COMMUNICATION_RULES_EXECUTION_INTERNAL.md:117` — independent targets."""
    tally = _result(destination_system="Tally")
    zoho = _result(destination_system="Zoho Books")

    assert tally.idempotency_key != zoho.idempotency_key
    assert len({tally.idempotency_key, zoho.idempotency_key}) == TWO_DISTINCT


def test_the_transaction_id_is_never_part_of_the_key() -> None:
    """`ENGINE_6:410` — keying on it would read every correction as a duplicate."""
    first = _result(identity=_identity(TransactionId.new()))
    second = _result(identity=_identity(TransactionId.new()))

    assert first.identity.transaction_id != second.identity.transaction_id
    assert first.idempotency_key == second.idempotency_key


def test_retrying_the_same_version_produces_the_same_key() -> None:
    """`ENGINE_6:534` — every retry references the same Execution ID; a new
    attempt, a new timestamp and a higher retry count change nothing about
    whether this posting is a duplicate."""
    execution_id = ExecutionId.new()
    first_attempt = _result(execution_id=execution_id, retry_count=0)
    third_attempt = _result(
        execution_id=execution_id,
        execution_attempt_id=ExecutionAttemptId.new(),
        retry_count=2,
        execution_timestamp=datetime(2026, 8, 3, 13, 30, tzinfo=UTC),
    )

    assert first_attempt.execution_attempt_id != third_attempt.execution_attempt_id
    assert first_attempt.idempotency_key == third_attempt.idempotency_key


def test_identity_never_influences_the_key() -> None:
    """INV-9. Every identifier that is not one of the three is irrelevant."""
    baseline = _result()
    everything_else_different = _result(
        identity=_identity(),
        execution_id=ExecutionId.new(),
        execution_attempt_id=ExecutionAttemptId.new(),
        validation_decision_id=ArtifactId.new(),
    )

    assert baseline.idempotency_key == everything_else_different.idempotency_key


def test_the_key_works_as_a_duplicate_store_key() -> None:
    """Not decoration: `posting_manager` has to look the key up somewhere."""
    posted: dict[IdempotencyKey, ExecutionId] = {}
    first = _result()
    posted[first.idempotency_key] = first.execution_id

    retry = _result()
    assert retry.idempotency_key in posted

    correction = _result(decision_version=SECOND_VERSION)
    assert correction.idempotency_key not in posted


def test_the_key_is_frozen() -> None:
    key = _result().idempotency_key

    with pytest.raises(dataclasses.FrozenInstanceError):
        key.decision_version = SECOND_VERSION  # type: ignore[misc]


def test_destination_system_is_case_sensitive_so_a_spelling_difference_defeats_it() -> None:
    """RECORDED EXPOSURE, not desired behaviour.

    `ENGINE_6:321` leaves the destination set OPEN, so Destination System is a
    free string and `"Tally"` and `"tally"` are two different keys — which means
    duplicate protection can be defeated by a spelling difference and the same
    voucher posts twice. Nothing in the repository defines a canonical form, so
    nothing here may invent one (Law 54). The exposure is asserted so that it
    cannot change without a test changing with it.
    """
    upper = _result(destination_system="Tally")
    lower = _result(destination_system="tally")

    assert upper.idempotency_key != lower.idempotency_key


# ── 2. Transport, not reasoning ───────────────────────────────────────────
# `DATA_FLOW.md:357` · `ENGINE_6:92-101` · `ENGINE_6:239`.


@pytest.mark.parametrize("forbidden", FORBIDDEN_ACCOUNTING_FIELDS)
def test_an_accounting_field_is_rejected_at_construction(forbidden: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _result(**{forbidden: "anything at all"})


@pytest.mark.parametrize("forbidden", FORBIDDEN_ACCOUNTING_FIELDS)
def test_no_accounting_concept_is_a_field(forbidden: str) -> None:
    assert forbidden not in ExecutionResult.model_fields


def test_the_field_set_is_exactly_what_the_specification_lists() -> None:
    """Catches both directions: an added field and a dropped one."""
    assert set(ExecutionResult.model_fields) == EXPECTED_FIELDS


def test_the_transaction_id_is_not_repeated_outside_the_identity_envelope() -> None:
    """`DATA_FLOW.md:32` — one source of truth for the transaction."""
    assert "transaction_id" not in ExecutionResult.model_fields
    assert isinstance(_result().identity.transaction_id, TransactionId)


# ── 3. Execution Confidence ───────────────────────────────────────────────
# The canonical type, imported. `confidence.py` owns these rules; the tests
# below prove this artifact did not quietly redeclare them.


def test_a_float_confidence_is_refused() -> None:
    with pytest.raises(ValidationError, match="must be a Decimal"):
        _result(execution_confidence=0.98)


def test_a_confidence_above_one_is_refused() -> None:
    with pytest.raises(ValidationError, match=r"within \[0.0000, 1.0000\]"):
        _result(execution_confidence=Decimal("1.7"))


def test_a_confidence_with_five_places_is_refused() -> None:
    with pytest.raises(ValidationError, match="5 decimal places"):
        _result(execution_confidence=Decimal("0.98765"))


def test_the_confidence_bounds_are_inclusive() -> None:
    assert _result(execution_confidence=Decimal("0.0000")).execution_confidence == Decimal("0.0000")
    assert _result(execution_confidence=Decimal("1.0000")).execution_confidence == Decimal("1.0000")


def test_confidence_is_stored_verbatim() -> None:
    assert _result(execution_confidence=Decimal("0.5")).execution_confidence == Decimal("0.5")


# ── 4. Identity ───────────────────────────────────────────────────────────


def test_an_execution_id_and_an_attempt_id_are_different_types() -> None:
    """INV-3's argument, applied inside Engine 6: one decision version may be
    attempted many times, so these are not interchangeable."""
    shared = uuid.uuid4()

    assert ExecutionId(shared) != ExecutionAttemptId(shared)  # type: ignore[comparison-overlap]


def test_an_attempt_id_cannot_be_passed_where_an_execution_id_belongs() -> None:
    attempt = ExecutionAttemptId.new()

    with pytest.raises(ValidationError):
        _result(
            execution_id=attempt, audit_reference=AuditReference(execution_id=ExecutionId.new())
        )


def test_a_bare_uuid_is_not_an_execution_id() -> None:
    with pytest.raises(ValidationError):
        _result(execution_id=uuid.uuid4())


def test_new_ids_are_distinct() -> None:
    assert ExecutionId.new() != ExecutionId.new()
    assert ExecutionAttemptId.new() != ExecutionAttemptId.new()


def test_the_identity_envelope_is_the_real_one() -> None:
    """Not a stand-in: the envelope's own lineage rule must still fire (§J.6)."""
    with pytest.raises(ValidationError, match="must record the parent version"):
        _result(
            identity=IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=SECOND_VERSION,
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )
        )


def test_a_corrected_execution_records_its_parent_version() -> None:
    """INV-5 — a correction is a new version with its lineage recorded."""
    original = ArtifactId.new()
    correction = _result(
        identity=IdentityEnvelope(
            artifact_id=original,
            version=SECOND_VERSION,
            parent_versions=(ParentVersion(artifact_id=original, version=FIRST_VERSION),),
            transaction_id=TransactionId.new(),
        )
    )

    assert correction.identity.parent_versions[0].version == FIRST_VERSION


# ── 5. Correction lineage ─────────────────────────────────────────────────
# `ENGINE_6:210` · `DATA_FLOW.md:686`.


def test_a_non_correction_carries_no_corrected_execution() -> None:
    assert _result().corrects_execution_result is None


def test_a_correction_points_at_the_execution_it_corrected() -> None:
    original = ExecutionId.new()

    assert _result(corrects_execution_result=original).corrects_execution_result == original


def test_an_execution_cannot_correct_itself() -> None:
    execution_id = ExecutionId.new()

    with pytest.raises(ValidationError, match="cannot correct itself"):
        _result(execution_id=execution_id, corrects_execution_result=execution_id)


# ── 6. Audit reference ────────────────────────────────────────────────────
# `ENGINE_6:507` — one Audit Record per Execution ID, referenced not carried.


def test_the_audit_reference_must_point_at_this_execution() -> None:
    with pytest.raises(ValidationError, match="audit reference"):
        _result(
            execution_id=ExecutionId.new(),
            audit_reference=AuditReference(execution_id=ExecutionId.new()),
        )


def test_a_matching_audit_reference_is_accepted() -> None:
    execution_id = ExecutionId.new()
    result = _result(execution_id=execution_id)

    assert result.audit_reference.execution_id == execution_id


def test_the_audit_record_itself_is_not_carried() -> None:
    """`COMMUNICATION_RULES_EXECUTION_INTERNAL.md:137` — referenced, never
    carried; carrying it would put two artifacts on one arrow."""
    assert set(AuditReference.model_fields) == {"execution_id"}


# ── 7. Retry count ────────────────────────────────────────────────────────


def test_a_negative_retry_count_is_refused() -> None:
    with pytest.raises(ValidationError):
        _result(retry_count=-1)


def test_a_zero_retry_count_is_accepted() -> None:
    assert _result(retry_count=0).retry_count == 0


@pytest.mark.parametrize("hostile", [True, "3", 3.0, None])
def test_a_retry_count_that_is_not_an_integer_is_refused(hostile: object) -> None:
    """`True` is the one that matters: `bool` is a subclass of `int`, so a
    plain `int` annotation would silently record one retry."""
    with pytest.raises(ValidationError):
        _result(retry_count=hostile)


# ── 8. Timestamps ─────────────────────────────────────────────────────────


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        _result(execution_timestamp=datetime(2026, 8, 3, 12, 0))

    assert messages(raised) == [
        "Value error, must be timezone-aware; a naive datetime in a permanent record "
        "cannot be ordered against anything else"
    ]


def test_a_non_utc_timezone_is_accepted() -> None:
    """No document requires UTC. Inventing that rule would reject a legitimate
    artifact, so the check is aware-or-not, nothing more."""
    ist = timezone(timedelta(hours=5, minutes=30))
    stamped = datetime(2026, 8, 3, 17, 30, tzinfo=ist)

    assert _result(execution_timestamp=stamped).execution_timestamp == stamped


def test_a_timestamp_in_a_named_zone_is_accepted() -> None:
    """A `ZoneInfo` stamp is the ordinary case for an Indian deployment, and it
    is the case that separates a real awareness check from a lookalike.

    `tzinfo.utcoffset(dt)` takes the datetime because a named zone's offset
    DEPENDS on the moment — Asia/Kolkata answers +05:30 for a real instant and
    `None` for no instant at all, exactly as the tzinfo protocol permits. Ask
    it without the datetime and every zoneinfo-stamped posting looks naive and
    is refused. `timezone.utc` answers +00:00 either way, so the fixed-offset
    test above cannot see the difference and passes on both.
    """
    stamped = datetime(2026, 8, 3, 17, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    result = _result(execution_timestamp=stamped)

    assert result.execution_timestamp == stamped
    assert result.execution_timestamp.utcoffset() == timedelta(hours=5, minutes=30)


@pytest.mark.parametrize(
    ("hostile", "type_name"),
    [
        ("2026-08-03T12:00:00Z", "str"),
        (1785000000, "int"),
        (None, "NoneType"),
        (1785000000.0, "float"),
    ],
)
def test_a_timestamp_that_is_not_a_datetime_is_refused(hostile: object, type_name: str) -> None:
    """The integer case is the dangerous one: pydantic's lax mode would read it
    as a unix timestamp, so a mistyped count would become a posting time.

    The refusal names the type it got, because the whole point is that the
    value LOOKS like a moment. `"2026-08-03T12:00:00Z"` refused as
    "must be a datetime, got NoneType" would send the reader hunting a missing
    field that is not missing.
    """
    with pytest.raises(ValidationError) as raised:
        _result(execution_timestamp=hostile)

    assert messages(raised) == [f"Value error, must be a datetime, got {type_name}"]


# ── 9. The six unenumerated fields ────────────────────────────────────────
# No document states their values. Nothing here invents any (Law 54).


def test_every_unenumerated_field_exists_on_the_model_that_declares_it() -> None:
    models = {"ExecutionResult": ExecutionResult, "ClassifiedError": ClassifiedError}

    for entry in UNENUMERATED_FIELDS:
        model_name, _, field_name = entry.partition(".")
        assert model_name in models, entry
        assert field_name in models[model_name].model_fields, entry  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "field",
    [
        "destination_system",
        "posting_status",
        "queue_status",
        "notification_status",
        "execution_outcome",
    ],
)
def test_no_enumeration_was_invented(field: str) -> None:
    """A value no document mentions is accepted, because no document says what
    the values are. If this ever fails, someone guessed a set."""
    assert getattr(_result(**{field: "NO-DOCUMENT-DEFINES-THIS"}), field) == (
        "NO-DOCUMENT-DEFINES-THIS"
    )


@pytest.mark.parametrize(
    "field",
    [
        "destination_system",
        "posting_status",
        "queue_status",
        "notification_status",
        "execution_outcome",
    ],
)
@pytest.mark.parametrize(
    ("hostile", "reason"),
    [
        ("", "must not be empty"),
        ("   ", "must not be padded: '   '"),
        (" Tally", "must not be padded: ' Tally'"),
        ("Tally ", "must not be padded: 'Tally '"),
        ("post\ned", "must be printable: 'post\\ned'"),
        ("post\ted", "must be printable: 'post\\ted'"),
        ("\x00", "must be printable: '\\x00'"),
    ],
)
def test_an_opaque_value_that_is_blank_padded_or_unprintable_is_refused(
    field: str, hostile: str, reason: str
) -> None:
    """Which of the four refusals fired is the answer, not a detail.

    `" Tally"` refused as "must not be empty" would send an operator looking
    for a missing configuration value instead of a stray space, and every one
    of these four messages was free to say anything at all while this test
    only asserted that SOMETHING was raised. The offending value is quoted
    with `!r` for the same reason: a padded or unprintable string prints
    identically to a clean one, so an unquoted message describes a value the
    reader cannot see.
    """
    with pytest.raises(ValidationError) as raised:
        _result(**{field: hostile})

    assert messages(raised) == [f"Value error, {reason}"]


def test_an_opaque_value_whose_equality_lies_is_still_refused_as_blank() -> None:
    """The blank check is a second line, not dead code — see `LyingText`.

    A value that answers "equal" to its own stripped form walks past the
    padding check. Without this, three whole spellings of the refusal in that
    branch were free to change, because nothing reached it.
    """
    with pytest.raises(ValidationError) as raised:
        _result(destination_system=LyingText("   "))

    assert messages(raised) == ["Value error, must not be blank"]


@pytest.mark.parametrize(
    "field",
    [
        "destination_system",
        "posting_status",
        "queue_status",
        "notification_status",
        "execution_outcome",
    ],
)
@pytest.mark.parametrize(
    ("hostile", "type_name"),
    [(None, "NoneType"), (1, "int"), (True, "bool"), (b"posted", "bytes"), (["posted"], "list")],
)
def test_an_opaque_value_that_is_not_a_string_is_refused(
    field: str, hostile: object, type_name: str
) -> None:
    """The refusal names the type it actually got.

    `b"posted"` and `"posted"` are one character apart in a traceback, and
    `True` reaching a status field is a bug that reads as harmless until the
    message tells you a bool arrived. A message that reported one fixed type
    for all five is wrong four times out of five and still raises.
    """
    with pytest.raises(ValidationError) as raised:
        _result(**{field: hostile})

    assert messages(raised) == [f"Value error, must be a string, got {type_name}"]


def test_an_opaque_value_may_contain_an_internal_space() -> None:
    """`ENGINE_6:65` names `Zoho Books`. A token rule that forbade spaces would
    reject a destination the specification lists."""
    assert _result(destination_system="Zoho Books").destination_system == "Zoho Books"


# ── 10. Classified Error ──────────────────────────────────────────────────
# `SUB_ENGINE_RESPONSIBILITIES.md:704,710` · `ENGINE_6:476`.


def test_a_successful_execution_carries_no_classified_error() -> None:
    assert _result().classified_error is None


def test_a_failed_execution_carries_the_full_classification() -> None:
    error = _classified_error()
    result = _result(classified_error=error)

    assert result.classified_error == error
    assert result.classified_error.responsible_stage == "tally_connector"


def test_the_unclassifiable_category_is_accepted() -> None:
    """`ENGINE_6:476` requires it; `SUB_ENGINE_RESPONSIBILITIES.md:704` omits it
    from the list of four. Reported as a contradiction, not resolved here — the
    field is opaque, so both readings fit."""
    error = ClassifiedError(
        category="unclassifiable",
        cause="the destination returned a body no rule matched",
        severity="high",
        retry_permissible=False,
        responsible_stage="response_processor",
    )

    assert error.category == "unclassifiable"


@pytest.mark.parametrize("hostile", ["yes", 1, 0, "true", None])
def test_retry_permissible_refuses_anything_that_is_not_a_bool(hostile: object) -> None:
    with pytest.raises(ValidationError):
        ClassifiedError(
            category="transport",
            cause="connection reset",
            severity="high",
            retry_permissible=hostile,  # type: ignore[arg-type]
            responsible_stage="tally_connector",
        )


@pytest.mark.parametrize(
    ("hostile", "reason"),
    [
        ("", "must not be empty or blank"),
        ("   ", "must not be empty or blank"),
        (" padded", "must not be padded: ' padded'"),
        ("padded ", "must not be padded: 'padded '"),
    ],
)
def test_a_blank_or_padded_cause_is_refused(hostile: str, reason: str) -> None:
    """A `cause` is the destination's own words about a posting that failed.

    Refusing it is the right call and refusing it VAGUELY is not: the operator
    holding a failed voucher needs to know whether the connector sent nothing
    or sent something with a stray space, because those are different faults in
    different code. `_captured_text` checks blankness BEFORE padding, the
    reverse of `_opaque_value`, so `"   "` is answered differently by the two —
    asserted here rather than assumed.
    """
    with pytest.raises(ValidationError) as raised:
        ClassifiedError(
            category="transport",
            cause=hostile,
            severity="high",
            retry_permissible=True,
            responsible_stage="tally_connector",
        )

    assert messages(raised) == [f"Value error, {reason}"]


@pytest.mark.parametrize(
    ("hostile", "type_name"),
    [(None, "NoneType"), (500, "int"), (b"HTTP 500", "bytes"), (["HTTP 500"], "list")],
)
def test_a_cause_that_is_not_a_string_is_refused_and_the_type_is_named(
    hostile: object, type_name: str
) -> None:
    """`b"HTTP 500"` is what a raw socket read hands you, and it is the case
    most likely to arrive from a connector that forgot to decode. The message
    has to say `bytes`, or the reader looks at `HTTP 500` in the traceback and
    concludes the string was fine."""
    with pytest.raises(ValidationError) as raised:
        ClassifiedError.model_validate(
            {
                "category": "transport",
                "cause": hostile,
                "severity": "high",
                "retry_permissible": True,
                "responsible_stage": "tally_connector",
            }
        )

    assert messages(raised) == [f"Value error, must be a string, got {type_name}"]


def test_a_multi_line_cause_is_preserved() -> None:
    """An external system's error text is evidence. Refusing to build the
    artifact because it contains a newline would lose the record of a real
    posting — `ENGINE_6:433`, never lose the validated transaction."""
    cause = "HTTP 500\nbody: <error>ledger locked</error>"
    error = ClassifiedError(
        category="destination rejection",
        cause=cause,
        severity="high",
        retry_permissible=False,
        responsible_stage="tally_connector",
    )

    assert error.cause == cause


def test_the_classified_error_is_frozen() -> None:
    error = _classified_error()

    with pytest.raises(ValidationError):
        error.severity = "low"


# ── 11. External transaction IDs ──────────────────────────────────────────


def test_no_external_id_is_the_normal_state_of_a_failed_execution() -> None:
    """`ENGINE_6:458` — never invent external IDs. Empty is a real answer."""
    assert _result(external_transaction_ids=()).external_transaction_ids == ()


def test_external_ids_are_stored_as_a_tuple_even_when_given_a_list() -> None:
    result = _result(external_transaction_ids=["A-1", "A-2"])

    assert result.external_transaction_ids == ("A-1", "A-2")
    assert isinstance(result.external_transaction_ids, tuple)


@pytest.mark.parametrize("hostile", ["", "  ", " A-1", "A\n1"])
def test_a_blank_or_unprintable_external_id_is_refused(hostile: str) -> None:
    """An empty string is an invented identifier that means nothing."""
    with pytest.raises(ValidationError):
        _result(external_transaction_ids=(hostile,))


def test_repeated_external_transaction_ids_are_preserved_verbatim() -> None:
    """RECORDED DECISION, and the less obvious of the two options.

    A destination that returns the same identifier twice is reporting something.
    Refusing to build the Execution Result would lose the record of a posting
    that actually happened (`ENGINE_6:433`), and de-duplicating would be Engine 6
    altering what an external system said (`COMMUNICATION_RULES_EXECUTION_INTERNAL.md:71`).
    So it is kept exactly as received.
    """
    result = _result(external_transaction_ids=("V-1", "V-1"))

    assert result.external_transaction_ids == ("V-1", "V-1")


# ── 12. Immutability ──────────────────────────────────────────────────────
# INV-5 — history is never modified.


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("posting_status", "posted"),
        ("retry_count", 9),
        ("execution_confidence", Decimal("0.1")),
        ("external_transaction_ids", ()),
    ],
)
def test_an_execution_result_cannot_be_edited(field: str, value: object) -> None:
    result = _result()

    with pytest.raises(ValidationError):
        setattr(result, field, value)


def test_the_audit_reference_cannot_be_repointed() -> None:
    reference = AuditReference(execution_id=ExecutionId.new())

    with pytest.raises(ValidationError):
        reference.execution_id = ExecutionId.new()


def test_a_missing_field_is_refused_rather_than_defaulted() -> None:
    """`SYSTEM_INVARIANTS.md:295` — gaps stay gaps. No field may default."""
    fields = _fields()
    del fields["posting_status"]

    with pytest.raises(ValidationError, match="Field required"):
        ExecutionResult(**fields)  # type: ignore[arg-type]


def test_every_field_is_required_or_explicitly_optional() -> None:
    optional = {"corrects_execution_result", "classified_error"}

    for name, field in ExecutionResult.model_fields.items():
        if name in optional:
            continue
        assert field.is_required(), f"{name} acquired a default; a default is an invented value"
