"""Kill mutations in execution.py that break the exactly-once idempotency guarantee.

Every test in here is written to fail RED if a single source line is flipped,
deleted, or mutated. If your changes pass all tests in test_execution.py but
fail one of these, your mutation was caught.

TARGET INVARIANT: exactly once per (Decision ID + Decision Version + Destination).
  - Flipping any field in the triple breaks deduplication.
  - Normalizing the destination system (lower, upper, strip) collapses keys.
  - Changing comparison operators on validation hides duplicates.
  - Removing validation passes garbage through that looks like a new key.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.execution import (
    AuditReference,
    ClassifiedError,
    ExecutionAttemptId,
    ExecutionId,
    ExecutionResult,
    IdempotencyKey,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

DECISION_ID_A = ArtifactId(uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
DECISION_ID_B = ArtifactId(uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
VALIDATION_ID = ArtifactId(uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
VERSION_ONE = 1
VERSION_TWO = 2
VERSION_THREE = 3
VERSION_FIVE = 5
VERSION_TEN = 10
VERSION_NINETYNINE = 99
THREE_DISTINCT_KEYS = 3


def _result(**overrides: object) -> ExecutionResult:
    """One complete valid Execution Result with field overrides."""

    # Type-safe extraction of overrides with defaults
    def get_override(key: str, default: object) -> object:
        """Get override value or use default."""
        return overrides.get(key, default)

    execution_id = cast(ExecutionId, get_override("execution_id", ExecutionId.new()))

    audit_reference = cast(
        AuditReference,
        get_override("audit_reference", AuditReference(execution_id=execution_id)),
    )

    return ExecutionResult(
        identity=cast(
            IdentityEnvelope,
            get_override(
                "identity",
                IdentityEnvelope(
                    artifact_id=ArtifactId.new(),
                    version=VERSION_ONE,
                    parent_versions=(),
                    transaction_id=TransactionId.new(),
                ),
            ),
        ),
        execution_attempt_id=cast(
            ExecutionAttemptId, get_override("execution_attempt_id", ExecutionAttemptId.new())
        ),
        accounting_decision_id=cast(
            ArtifactId, get_override("accounting_decision_id", DECISION_ID_A)
        ),
        decision_version=cast(int, get_override("decision_version", VERSION_ONE)),
        validation_decision_id=cast(
            ArtifactId, get_override("validation_decision_id", VALIDATION_ID)
        ),
        destination_system=cast(str, get_override("destination_system", "Tally")),
        corrects_execution_result=cast(
            ExecutionId | None, get_override("corrects_execution_result", None)
        ),
        posting_status=cast(str, get_override("posting_status", "posted")),
        external_transaction_ids=cast(
            tuple[str, ...], get_override("external_transaction_ids", ())
        ),
        retry_count=cast(int, get_override("retry_count", 0)),
        queue_status=cast(str, get_override("queue_status", "not-queued")),
        notification_status=cast(str, get_override("notification_status", "sent")),
        classified_error=cast(ClassifiedError | None, get_override("classified_error", None)),
        execution_outcome=cast(str, get_override("execution_outcome", "success")),
        execution_confidence=cast(Decimal, get_override("execution_confidence", Decimal("0.98"))),
        execution_timestamp=cast(
            datetime, get_override("execution_timestamp", datetime(2026, 8, 3, 12, 0, tzinfo=UTC))
        ),
        execution_id=execution_id,
        audit_reference=audit_reference,
    )


# ── Idempotency key field inclusion tests ──────────────────────────────────
# These catch mutations that add/remove/change fields in the key construction.


def test_idempotency_key_includes_accounting_decision_id() -> None:
    """Flipping this field or removing it breaks duplicate detection."""
    key_a = _result(accounting_decision_id=DECISION_ID_A).idempotency_key
    key_b = _result(accounting_decision_id=DECISION_ID_B).idempotency_key

    assert key_a != key_b
    assert key_a.accounting_decision_id == DECISION_ID_A
    assert key_b.accounting_decision_id == DECISION_ID_B


def test_idempotency_key_includes_decision_version() -> None:
    """Omitting or changing this field allows corrections to be treated as retries."""
    key_v1 = _result(decision_version=VERSION_ONE).idempotency_key
    key_v2 = _result(decision_version=VERSION_TWO).idempotency_key

    assert key_v1 != key_v2
    assert key_v1.decision_version == VERSION_ONE
    assert key_v2.decision_version == VERSION_TWO


def test_idempotency_key_includes_destination_system() -> None:
    """Removing or changing this field allows one transaction to post to two destinations
    and have them collapse as duplicates."""
    key_tally = _result(destination_system="Tally").idempotency_key
    key_zoho = _result(destination_system="Zoho Books").idempotency_key

    assert key_tally != key_zoho
    assert key_tally.destination_system == "Tally"
    assert key_zoho.destination_system == "Zoho Books"


def test_idempotency_key_does_not_include_execution_id() -> None:
    """Including execution ID would make every retry look like a new decision."""
    exec_a = ExecutionId.new()
    exec_b = ExecutionId.new()

    key_a = _result(execution_id=exec_a).idempotency_key
    key_b = _result(execution_id=exec_b).idempotency_key

    assert key_a == key_b


def test_idempotency_key_does_not_include_execution_attempt_id() -> None:
    """Including attempt ID would make every retry look like a new decision."""
    attempt_a = ExecutionAttemptId.new()
    attempt_b = ExecutionAttemptId.new()

    key_a = _result(execution_attempt_id=attempt_a).idempotency_key
    key_b = _result(execution_attempt_id=attempt_b).idempotency_key

    assert key_a == key_b


def test_idempotency_key_does_not_include_retry_count() -> None:
    """Including retry count would make retry attempts distinct."""
    key_0 = _result(retry_count=0).idempotency_key
    key_2 = _result(retry_count=VERSION_TWO).idempotency_key

    assert key_0 == key_2


# ── Destination system comparison tests ────────────────────────────────────
# These catch mutations that normalize the destination system, which would
# accidentally merge "Tally" and "tally" into a single key.


def test_destination_system_comparison_is_case_sensitive() -> None:
    """Adding .lower(), .upper() or .casefold() would hide this difference."""
    key_upper = _result(destination_system="TALLY").idempotency_key
    key_lower = _result(destination_system="tally").idempotency_key
    key_title = _result(destination_system="Tally").idempotency_key

    assert key_upper != key_lower
    assert key_lower != key_title
    assert key_upper != key_title
    assert len({key_upper, key_lower, key_title}) == THREE_DISTINCT_KEYS


def test_destination_system_comparison_is_space_sensitive() -> None:
    """Adding .strip() or .replace(' ', '') would hide this difference.

    Padded destination systems are rejected at validation time, so we test
    that the validator is doing its job by confirming the rejection."""
    key_clean = _result(destination_system="Tally").idempotency_key

    # Padded values are rejected at validation time
    with pytest.raises(ValidationError, match="must not be padded"):
        _result(destination_system=" Tally")

    with pytest.raises(ValidationError, match="must not be padded"):
        _result(destination_system="Tally ")

    # This test proves that if someone removed the padding check from
    # _opaque_value, the keys would collapse. We cannot test the collapsed
    # keys directly because the validator prevents it, but the test name
    # documents the risk.
    assert key_clean.destination_system == "Tally"


def test_destination_system_with_internal_space_is_distinct_from_normalized() -> None:
    """Zoho Books (with space) must be distinct from ZohoBooks."""
    key_spaced = _result(destination_system="Zoho Books").idempotency_key
    key_compact = _result(destination_system="ZohoBooks").idempotency_key

    assert key_spaced != key_compact


# ── Decision version off-by-one tests ──────────────────────────────────────
# These catch mutations that use the wrong version or modify it.


def test_off_by_one_mutation_in_version_field() -> None:
    """If someone uses `decision_version + 1` or `- 1`, keys become distinct when they shouldn't."""
    # Test that the key uses the EXACT version, not a derived one.
    # If code uses version - 1, two results with versions 1 and 2 would both get key with version 1.
    key_v1_a = _result(decision_version=VERSION_ONE).idempotency_key
    key_v1_b = _result(
        accounting_decision_id=DECISION_ID_A, decision_version=VERSION_ONE
    ).idempotency_key

    assert key_v1_a == key_v1_b
    assert key_v1_a.decision_version == VERSION_ONE


def test_decision_version_is_used_directly_not_incremented() -> None:
    """If someone uses `decision_version + 1`, this catches it."""
    version = VERSION_FIVE
    key = _result(decision_version=version).idempotency_key

    assert key.decision_version == version


def test_decision_version_exact_match_in_key() -> None:
    """The key carries the exact version, not a derived value."""
    versions = [VERSION_ONE, VERSION_TWO, VERSION_FIVE, VERSION_TEN, VERSION_NINETYNINE]
    for ver in versions:
        key = _result(decision_version=ver).idempotency_key
        assert key.decision_version == ver


# ── Validation operator mutation tests ─────────────────────────────────────
# These catch mutations of comparison operators in validators.


def test_self_correction_validator_uses_equality_not_inequality() -> None:
    """If the validator flips `==` to `!=`, this catches it."""
    execution_id = ExecutionId.new()

    # This SHOULD raise (self-correction is forbidden)
    with pytest.raises(ValidationError, match="cannot correct itself"):
        _result(execution_id=execution_id, corrects_execution_result=execution_id)


def test_self_correction_passes_when_different() -> None:
    """Confirming the validator uses `==` not `!=`."""
    exec_a = ExecutionId.new()
    exec_b = ExecutionId.new()

    # This SHOULD succeed (different execution is allowed)
    result = _result(execution_id=exec_a, corrects_execution_result=exec_b)
    assert result.corrects_execution_result == exec_b


def test_audit_reference_validator_uses_inequality() -> None:
    """If the validator flips `!=` to `==`, this catches it."""
    # Mismatched audit reference SHOULD raise
    with pytest.raises(ValidationError, match="audit reference"):
        _result(
            execution_id=ExecutionId.new(),
            audit_reference=AuditReference(execution_id=ExecutionId.new()),
        )


def test_audit_reference_passes_when_matching() -> None:
    """Confirming the validator uses `!=` not `==`."""
    execution_id = ExecutionId.new()

    # Matching audit reference SHOULD succeed
    result = _result(execution_id=execution_id)
    assert result.audit_reference.execution_id == execution_id


# ── Key mutability tests ───────────────────────────────────────────────────
# IdempotencyKey must be frozen and hashable.


def test_idempotency_key_is_hashable() -> None:
    """The key must work in a set or dict for duplicate stores."""
    key1 = _result(accounting_decision_id=DECISION_ID_A).idempotency_key
    key2 = _result(accounting_decision_id=DECISION_ID_B).idempotency_key

    store: dict[IdempotencyKey, str] = {key1: "first"}
    assert store[key1] == "first"
    assert key2 not in store


def test_identical_keys_hash_identically() -> None:
    """Duplicate keys must have the same hash for dict/set lookup."""
    key1 = IdempotencyKey(
        accounting_decision_id=DECISION_ID_A, decision_version=1, destination_system="Tally"
    )
    key2 = IdempotencyKey(
        accounting_decision_id=DECISION_ID_A, decision_version=1, destination_system="Tally"
    )

    assert hash(key1) == hash(key2)
    assert len({key1, key2}) == 1


# ── Field presence tests ───────────────────────────────────────────────────
# These catch if someone adds a field to the key or removes one from the triple.


def test_accounting_decision_id_field_is_named_correctly() -> None:
    """If someone renames the field, the key will use a different name."""
    key = _result().idempotency_key

    # Must have this exact field name
    assert hasattr(key, "accounting_decision_id")
    assert key.accounting_decision_id == DECISION_ID_A


def test_decision_version_field_is_named_correctly() -> None:
    """If someone renames the field, the key will use a different name."""
    key = _result(decision_version=VERSION_THREE).idempotency_key

    # Must have this exact field name
    assert hasattr(key, "decision_version")
    assert key.decision_version == VERSION_THREE


def test_destination_system_field_is_named_correctly() -> None:
    """If someone renames the field, the key will use a different name."""
    key = _result(destination_system="Custom").idempotency_key

    # Must have this exact field name
    assert hasattr(key, "destination_system")
    assert key.destination_system == "Custom"


# ── Integration: full triple distinctness ─────────────────────────────────
# These test the complete idempotency guarantee with realistic scenarios.


def test_different_decisions_post_separately() -> None:
    """Two different decisions must have distinct keys."""
    decision_1 = _result(accounting_decision_id=DECISION_ID_A)
    decision_2 = _result(accounting_decision_id=DECISION_ID_B)

    assert decision_1.idempotency_key != decision_2.idempotency_key


def test_corrected_decision_has_distinct_key() -> None:
    """Version 2 of a decision must have a distinct key from version 1."""
    original = _result(decision_version=1)
    correction = _result(decision_version=2)

    assert original.idempotency_key != correction.idempotency_key


def test_multi_destination_posting_has_distinct_keys() -> None:
    """The same decision posting to two destinations must have distinct keys."""
    to_tally = _result(destination_system="Tally")
    to_zoho = _result(destination_system="Zoho Books")

    assert to_tally.idempotency_key != to_zoho.idempotency_key


def test_key_triple_hashable_in_production_pattern() -> None:
    """Simulate a real duplicate store and verify the key works."""
    # Simulate production: store of (Decision ID, Version, Destination) -> Execution ID
    store: dict[IdempotencyKey, ExecutionId] = {}

    # Post version 1 to Tally
    exec1 = ExecutionId.new()
    key1 = _result(
        accounting_decision_id=DECISION_ID_A, decision_version=VERSION_ONE
    ).idempotency_key
    store[key1] = exec1

    # Retry: same key
    key_retry = _result(
        accounting_decision_id=DECISION_ID_A, decision_version=VERSION_ONE
    ).idempotency_key
    assert key_retry in store  # DUPLICATE — same key exists

    # Correction: version 2
    key_v2 = _result(
        accounting_decision_id=DECISION_ID_A, decision_version=VERSION_TWO
    ).idempotency_key
    assert key_v2 not in store  # NEW — different key, posts again

    # Second destination: same decision
    key_zoho = _result(
        accounting_decision_id=DECISION_ID_A,
        decision_version=VERSION_ONE,
        destination_system="Zoho Books",
    ).idempotency_key
    assert key_zoho not in store  # NEW — different destination, posts independently
