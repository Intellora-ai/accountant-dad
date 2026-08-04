"""The Execution Result — Engine 6's permanent record.

`DATA_FLOW.md` §2 row 7 and `ENGINE_6_EXECUTION_ENGINE_RULES.md:159-179`.

EXECUTION IS TRANSPORT, NOT REASONING.
    `DATA_FLOW.md:357` lists eight things Engine 6 may never decide and
    therefore may never record: accounting treatment · journal structure ·
    ledger selection · tax treatment · validation approval · clarification
    requirements · business meaning · accounting confidence.

    `extra="forbid"` makes that structural rather than remembered. A field for
    any of them cannot be bolted on, and a test asserts the field set is
    exactly the eighteen the specification lists — so a nineteenth fails
    whether or not anyone thought to forbid its name.

EXACTLY ONCE PER DECISION ID + DECISION VERSION + DESTINATION SYSTEM.
    `DATA_FLOW.md:693`, `ENGINE_6:401`, `EXECUTION_INTERNAL:108`. That triple
    is the idempotency key and nothing else is:

      - the TRANSACTION ID is not in it. One business event can legitimately
        post to two destinations, and keying on the transaction would collapse
        them into a duplicate.
      - the EXECUTION ID and ATTEMPT ID are not in it. They are what makes two
        attempts distinguishable, so keying on them would make every retry look
        like a fresh posting — which is precisely the double-post the rule
        exists to prevent.
      - DECISION VERSION is in it, so a corrected decision may post again.
      - DESTINATION SYSTEM is in it, so a second destination may post.

    The key is a frozen dataclass, hashable, usable directly as a store key.
    Comparison on `destination_system` is case- and space-sensitive: `"tally"`
    and `"Tally"` are different keys, because treating them as equal would be
    inventing an equivalence no document states.

SIX FIELDS ARE NAMED BUT ENUMERATED NOWHERE.
    Verified across the whole repository: `Posting Status` (8 references, zero
    values), `Execution Outcome` (4 references, zero values, and no document
    says how it differs from Posting Status), `Queue Status`,
    `Notification Status`, `Destination System` (`ENGINE_6:321` explicitly
    leaves the set OPEN), and `Classified Error`'s severity and responsible
    stage.

    Each is modelled as an opaque validated string, and `UNENUMERATED_FIELDS`
    names them so the gap is visible in code rather than only in a commit
    message. **No enum is invented for any of them** (Law 54). A schema that
    invented six enums would be worse than one that names six gaps honestly —
    the invented set would look authoritative and would be wrong.

    Opaque does not mean unvalidated. Blank, padded, unprintable and non-string
    values are all refused. An internal space is allowed, because `ENGINE_6:65`
    names `Zoho Books` and a token rule forbidding spaces would reject a
    destination the specification itself lists.

THE AUDIT RECORD IS REFERENCED, NEVER CARRIED.
    `DATA_FLOW.md` §2 row 7 — it is append-only history. Carrying it inside an
    immutable artifact would make one copy of an append-only log, frozen at a
    moment, and every later append invisible to whoever holds it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainValidator, model_validator

from accountant_dad.confidence import Confidence
from accountant_dad.identity import ArtifactId, IdentityEnvelope, VersionField

_FROZEN = ConfigDict(frozen=True, extra="forbid")

#: The fields whose value sets no document states. Named here so the gap is
#: visible in the code, not only in a commit message. Law 54: an undefined term
#: in a specification is a false statement waiting to be discovered.
UNENUMERATED_FIELDS = (
    "ExecutionResult.destination_system",
    "ExecutionResult.posting_status",
    "ExecutionResult.queue_status",
    "ExecutionResult.notification_status",
    "ExecutionResult.execution_outcome",
    "ClassifiedError.category",
    "ClassifiedError.severity",
    "ClassifiedError.responsible_stage",
)


def _opaque_value(value: object) -> str:
    """A validated string whose SET of legal values no document states.

    Opaque about the vocabulary, strict about the shape. Padding is refused
    rather than stripped: `" Tally"` and `"Tally"` must not become one value,
    because the idempotency key compares these exactly and silently
    normalising would merge two keys that a later reader could not tell apart.
    """
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value:
        raise ValueError("must not be empty")
    if value != value.strip():
        raise ValueError(f"must not be padded: {value!r}")
    if not value.strip():
        raise ValueError("must not be blank")
    if not value.isprintable():
        # A newline, tab or NUL in an audit record corrupts every log line and
        # every store key derived from it.
        raise ValueError(f"must be printable: {value!r}")
    return value


OpaqueValue = Annotated[str, PlainValidator(_opaque_value)]


def _captured_text(value: object) -> str:
    """Text captured from somewhere else, stored exactly as received.

    Unlike `OpaqueValue` this permits newlines and tabs: a `cause` is the
    destination's own response body, and destinations routinely answer with
    several lines. Truncating or flattening it would destroy the only record of
    why a posting failed.
    """
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError("must not be empty or blank")
    if value != value.strip():
        # Padding is refused here too. Internal newlines are the destination's
        # own formatting and are kept; leading or trailing whitespace is ours
        # to reject, and stripping it would edit a captured record.
        raise ValueError(f"must not be padded: {value!r}")
    return value


CapturedText = Annotated[str, PlainValidator(_captured_text)]


def _a_real_moment(value: object) -> datetime:
    """An actual timezone-aware datetime. Never a string, never a number.

    pydantic would happily parse `"2026-08-03T12:00:00Z"` and an epoch int into
    a datetime. Both are refused: a permanent record should carry the moment
    its producer meant, not this module's guess at how to read a string.
    """
    if not isinstance(value, datetime):
        raise ValueError(f"must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(
            "must be timezone-aware; a naive datetime in a permanent record "
            "cannot be ordered against anything else"
        )
    return value


AwareMoment = Annotated[datetime, PlainValidator(_a_real_moment)]


@dataclass(frozen=True, slots=True)
class ExecutionId:
    """Identifies one execution. Distinct from an attempt (INV-3, INV-9)."""

    value: uuid.UUID

    @classmethod
    def new(cls) -> ExecutionId:
        return cls(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class ExecutionAttemptId:
    """Identifies one ATTEMPT at an execution. A retry is a new attempt, not a
    new execution — which is why these are two types and not one."""

    value: uuid.UUID

    @classmethod
    def new(cls) -> ExecutionAttemptId:
        return cls(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Accounting Decision ID + Decision Version + Destination System.

    Frozen and hashable so it works directly as a duplicate-store key. See the
    module docstring for what is deliberately NOT in it.
    """

    accounting_decision_id: ArtifactId
    decision_version: int
    destination_system: str


class ClassifiedError(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """A component of the result, never a separate artifact.

    `category`, `severity` and `responsible_stage` are opaque: no document
    enumerates them. `SUB_ENGINE_RESPONSIBILITIES.md:704` lists four categories
    and `ENGINE_6:476` requires a fifth (`unclassifiable`) that is absent from
    that list, so even the one partial list in the repository is internally
    inconsistent. Reported, not resolved here.
    """

    model_config = _FROZEN

    category: OpaqueValue
    cause: CapturedText
    severity: OpaqueValue
    retry_permissible: Annotated[bool, Field(strict=True)]
    responsible_stage: OpaqueValue


class AuditReference(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Points AT the audit record. Never contains it."""

    model_config = _FROZEN

    execution_id: ExecutionId


class ExecutionResult(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Engine 6 → the permanent record. `DATA_FLOW.md` §2 row 7.

    Eighteen fields, exactly as `ENGINE_6:159-179` lists them. Transaction ID
    is not among them: it lives in the identity envelope, which `DATA_FLOW.md:32`
    says is universal and not repeated.
    """

    model_config = _FROZEN

    identity: IdentityEnvelope
    execution_id: ExecutionId
    execution_attempt_id: ExecutionAttemptId
    accounting_decision_id: ArtifactId
    decision_version: VersionField
    validation_decision_id: ArtifactId
    destination_system: OpaqueValue
    corrects_execution_result: ExecutionId | None
    posting_status: OpaqueValue
    external_transaction_ids: tuple[OpaqueValue, ...]
    retry_count: Annotated[int, Field(ge=0, strict=True)]
    queue_status: OpaqueValue
    notification_status: OpaqueValue
    classified_error: ClassifiedError | None
    audit_reference: AuditReference
    execution_outcome: OpaqueValue
    execution_confidence: Confidence
    execution_timestamp: AwareMoment

    @property
    def idempotency_key(self) -> IdempotencyKey:
        """Exactly once per this triple, and nothing else."""
        return IdempotencyKey(
            accounting_decision_id=self.accounting_decision_id,
            decision_version=self.decision_version,
            destination_system=self.destination_system,
        )

    @model_validator(mode="after")
    def _the_record_is_internally_consistent(self) -> ExecutionResult:
        if self.corrects_execution_result == self.execution_id:
            # A self-correcting execution is a cycle in the correction chain,
            # and nothing walking that chain would terminate.
            raise ValueError(
                "an execution cannot correct itself; corrects_execution_result "
                "must name a different execution"
            )

        if self.audit_reference.execution_id != self.execution_id:
            # An audit reference pointing at a different execution is worse
            # than none: it looks like traceability and leads somewhere else.
            raise ValueError(
                f"the audit reference points at execution "
                f"{self.audit_reference.execution_id.value}, "
                f"but this execution is {self.execution_id.value}"
            )
        return self
