"""The Validation Decision — Engine 5's only outbound artifact.

`DATA_FLOW.md` §2 rows 5 and 6. Engine 5 decides whether something may be
posted, and INV-8 puts that decision BEFORE execution: nothing unapproved
reaches Tally, so an approval this artifact carries wrongly is not caught later
by anything.

VALIDATION ONLY VALIDATES.
    `ENGINE_5:213` — *"Validation cannot repair."* `VALIDATION_INTERNAL:132` —
    *"No sub-engine may fix what it detects."*

    Problem transformed (Law 53). Judging whether a stored value IS a repair
    needs the accounting reasoning Engine 5 is forbidden to do. So the check
    became structural instead: give a repair nowhere to sit. There is no field
    for a corrected ledger, a revised amount or an amended treatment, `extra`
    is forbidden so one cannot be bolted on, and a test reads the model's own
    field names and fails if any word among them could name a repair. Adding
    `corrected_ledger` turns that red without anyone editing the test.

EVERY FINDING NAMES ITS RESPONSIBLE ENGINE.
    `DATA_FLOW.md:43`, and `VALIDATION_INTERNAL:118` — *"A finding without an
    owner cannot be acted on."* Required, no default, no `None`. The blameable
    set is Engines 1-4 only (`ENGINE_5:232`): Validation blaming itself leaves
    a finding nobody can act on, because the engine that found the defect
    cannot repair it, and blaming Execution points backwards past the last
    boundary in the system.

    All four issue lists carry findings, never bare strings. A single list that
    accepted plain text would be an evasion path — file the issue there and it
    arrives with no responsible engine.

NO APPROVAL WHILE A CRITICAL FINDING STANDS.
    `ENGINE_5:467` — *"No approval exists while a Critical finding remains."*
    Checked across all four lists, for both approving statuses.

A CONTRADICTION LEFT UNRESOLVED, DELIBERATELY (§M).
    Severity has the same four values everywhere and two incompatible readings
    of what they block. `ENGINE_5:157-158` — High is *"normally blocked"*,
    Medium is *"policy dependent"*. `ENGINE_RESPONSIBILITIES.md:249` — only
    `Critical` blocks, and *"High · Medium · Low, non-blocking"*. The values
    agree, the semantics do not, so ONLY the Critical rule is encoded and the
    rest is reported rather than guessed.

    `Severity` is a plain `Enum`, not a `StrEnum`, for a related reason.
    `ENGINE_5:442` says *"Unknown risk defaults to higher severity"*, which
    presupposes an ordering no document defines. A `StrEnum` would have
    silently supplied a lexicographic one — Critical < High < Low < Medium —
    which is not the ordering anybody means. Refusing the comparison keeps the
    missing definition visible instead of answering it wrongly.

A DECISION THAT CANNOT APPROVE SAYS EXACTLY WHY.
    `ENGINE_5:219` lists what it must return; `:228` — *"Never simply
    'Validation Failed.' Always exactly why."* A `Rejected` or
    `Clarification Required` decision with every list empty carries no
    responsible engine anywhere, so it is refused.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainValidator, model_validator

from accountant_dad.confidence import Confidence
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId, VersionField

_FROZEN = ConfigDict(frozen=True, extra="forbid")


def _meaningful_text(value: object) -> str:
    """A real string with something in it, stored verbatim and never trimmed."""
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError("must not be empty or blank")
    return value


NonEmptyText = Annotated[str, PlainValidator(_meaningful_text)]


class ValidationStatus(StrEnum):
    """The four, spelled as eight documents spell them.

    `ENGINE_5:128-129,145-148` · `DATA_FLOW.md:43` ·
    `ENGINE_RESPONSIBILITIES.md:248`. A `StrEnum` here on purpose: Engine 6 and
    the Application Layer both read this value off the wire, so it must
    serialise to exactly these strings.
    """

    APPROVED = "Approved"
    APPROVED_WITH_WARNING = "Approved With Warning"
    CLARIFICATION_REQUIRED = "Clarification Required"
    REJECTED = "Rejected"


#: Goes forward, after the Application Layer releases it
#: (`COMMUNICATION_RULES_VALIDATION_ENGINE.md:61`). Grouping
#: `Approved With Warning` with `Rejected` would make the Critical rule below
#: check the wrong thing.
APPROVING_STATUSES = frozenset({ValidationStatus.APPROVED, ValidationStatus.APPROVED_WITH_WARNING})

#: Blocks execution. Neither can break INV-8, so a Critical finding is allowed
#: to stand alongside either.
CANNOT_APPROVE_STATUSES = frozenset(
    {ValidationStatus.REJECTED, ValidationStatus.CLARIFICATION_REQUIRED}
)


class Severity(Enum):
    """Four values, no ordering. See the module docstring for why not a StrEnum."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ResponsibleEngine(Enum):
    """Engines 1-4 — the only stages a finding may point back to (`ENGINE_5:232`)."""

    INPUT = "Input"
    UNDERSTANDING = "Understanding"
    ACCOUNTING = "Accounting"
    CLARIFICATION = "Clarification"


class ValidationFinding(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One defect, and everything `ENGINE_5:219` requires be said about it.

    No field here could hold a repair. That absence is the design, not an
    omission — see VALIDATION ONLY VALIDATES in the module docstring.
    """

    model_config = _FROZEN

    what_failed: NonEmptyText
    why_it_failed: NonEmptyText
    responsible_engine: ResponsibleEngine
    affected_artifact: NonEmptyText
    blocking_severity: Severity
    recommended_next_step: NonEmptyText
    supporting_evidence_references: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def _a_finding_shows_its_evidence(self) -> ValidationFinding:
        if not self.supporting_evidence_references:
            # ENGINE_5:571 — "Every finding contains evidence references."
            # Stated without exception, so an empty tuple is refused rather
            # than tolerated: a defect asserted with nothing behind it is the
            # bare "Validation Failed." under another name.
            raise ValueError(
                "a finding must carry at least one supporting evidence reference; "
                "a defect asserted with nothing behind it cannot be acted on"
            )
        return self


class ValidationDecision(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Engine 5 → Engine 6, or back. `DATA_FLOW.md` §2 rows 5 and 6."""

    model_config = _FROZEN

    identity: IdentityEnvelope
    related_decision_id: ArtifactId
    related_artifact_version: VersionField
    validation_status: ValidationStatus
    validation_findings: tuple[ValidationFinding, ...]
    validation_errors: tuple[ValidationFinding, ...]
    validation_warnings: tuple[ValidationFinding, ...]
    validation_risks: tuple[ValidationFinding, ...]
    failed_validation_rules: tuple[NonEmptyText, ...]
    supporting_evidence_references: tuple[NonEmptyText, ...]
    validation_confidence: Confidence
    validation_reasoning: NonEmptyText
    validation_timestamp: datetime

    @property
    def validation_id(self) -> ArtifactId:
        """The Validation ID IS the Artifact ID (`DATA_FLOW.md:32`).

        A second stored identifier could disagree with the first, and then no
        reader could tell which one traced the artifact.
        """
        return self.identity.artifact_id

    @property
    def transaction_id(self) -> TransactionId:
        return self.identity.transaction_id

    @property
    def issues(self) -> tuple[ValidationFinding, ...]:
        """Every finding, from all four lists.

        The predicates below scan this rather than one list, because a rule
        that only looked at `validation_findings` could be evaded by filing the
        same issue under `validation_errors`.
        """
        return (
            *self.validation_findings,
            *self.validation_errors,
            *self.validation_warnings,
            *self.validation_risks,
        )

    @model_validator(mode="after")
    def _the_status_is_consistent_with_what_was_found(self) -> ValidationDecision:
        if self.validation_timestamp.tzinfo is None or (
            self.validation_timestamp.tzinfo.utcoffset(self.validation_timestamp) is None
        ):
            raise ValueError(
                "validation_timestamp must be timezone-aware; a naive datetime "
                "in an audit trail cannot be ordered against anything else"
            )

        approving = self.validation_status in APPROVING_STATUSES

        if approving and any(found.blocking_severity is Severity.CRITICAL for found in self.issues):
            # ENGINE_5:467 and VALIDATION_INTERNAL:146. INV-8 decides
            # permission HERE; an approval carried wrongly is never caught
            # downstream, because downstream is Tally.
            raise ValueError(
                f"status {self.validation_status.value!r} cannot stand while a "
                "Critical finding remains. No approval exists while a Critical "
                "finding stands (ENGINE_5:467)."
            )

        if not approving and not self.issues:
            # ENGINE_5:219-228. With every list empty there is no responsible
            # engine anywhere in the artifact, which is exactly the bare
            # "Validation Failed." the specification forbids.
            raise ValueError(
                f"status {self.validation_status.value!r} must record at least one "
                "issue naming what failed, why, and the responsible engine. "
                "Never simply 'Validation Failed.' Always exactly why (ENGINE_5:228)."
            )
        return self
