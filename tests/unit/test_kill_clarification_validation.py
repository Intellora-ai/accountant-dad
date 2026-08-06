"""Mutation killers for validation and clarification decision logic.

Each test targets specific mutation points where logical flips (in→not in,
is→==, and→or) or boundary changes would pass existing tests but break invariants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.clarification import (
    TERMINAL_STATUSES,
    ClarificationStatus,
    may_transition,
)
from accountant_dad.artifacts.validation import (
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationFinding,
    ValidationStatus,
)
from accountant_dad.confidence import Confidence
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

#: A real clock makes two runs of this suite two different suites, and mutmut
#: runs the stats phase with `-x`. The timestamp is never asserted on here —
#: only its presence matters — so freezing it removes variance and removes
#: nothing else.
FIXED_VALIDATION_TIME = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)

FIRST_VERSION = 1
EXPECTED_TERMINALS = 3


def valid_identity(**overrides: object) -> IdentityEnvelope:
    base: dict[str, object] = {
        "artifact_id": ArtifactId.new(),
        "version": FIRST_VERSION,
        "parent_versions": (),
        "transaction_id": TransactionId.new(),
    }
    base.update(overrides)
    return IdentityEnvelope(
        artifact_id=base["artifact_id"],  # type: ignore[arg-type]
        version=base["version"],  # type: ignore[arg-type]
        parent_versions=base["parent_versions"],  # type: ignore[arg-type]
        transaction_id=base["transaction_id"],  # type: ignore[arg-type]
    )


def valid_finding() -> ValidationFinding:
    return ValidationFinding(
        what_failed="test failed",
        why_it_failed="for testing",
        responsible_engine=ResponsibleEngine.INPUT,
        affected_artifact="artifact-1",
        blocking_severity=Severity.LOW,
        recommended_next_step="fix it",
        supporting_evidence_references=("evidence-1",),
    )


def critical_finding() -> ValidationFinding:
    return ValidationFinding(
        what_failed="critical issue",
        why_it_failed="blocking",
        responsible_engine=ResponsibleEngine.ACCOUNTING,
        affected_artifact="artifact-1",
        blocking_severity=Severity.CRITICAL,
        recommended_next_step="stop",
        supporting_evidence_references=("evidence-critical",),
    )


class TestValidationCriticalBlock:
    """Approved status with critical finding must reject."""

    def test_approved_plus_critical_rejected(self) -> None:
        """APPROVED + Critical → reject. Kills: in→not in."""
        with pytest.raises(ValidationError) as exc:
            ValidationDecision(
                identity=valid_identity(),
                related_decision_id=ArtifactId.new(),
                related_artifact_version=FIRST_VERSION,
                validation_status=ValidationStatus.APPROVED,
                validation_findings=(critical_finding(),),
                validation_errors=(),
                validation_warnings=(),
                validation_risks=(),
                failed_validation_rules=(),
                supporting_evidence_references=("e1",),
                validation_confidence=Confidence(Decimal("0.95")),
                validation_reasoning="test",
                validation_timestamp=FIXED_VALIDATION_TIME,
            )
        assert "Critical" in str(exc.value)

    def test_critical_in_warnings_blocks(self) -> None:
        """Critical in any list blocks approval. Kills: missing list."""
        with pytest.raises(ValidationError):
            ValidationDecision(
                identity=valid_identity(),
                related_decision_id=ArtifactId.new(),
                related_artifact_version=FIRST_VERSION,
                validation_status=ValidationStatus.APPROVED,
                validation_findings=(),
                validation_errors=(),
                validation_warnings=(critical_finding(),),
                validation_risks=(),
                failed_validation_rules=(),
                supporting_evidence_references=("e1",),
                validation_confidence=Confidence(Decimal("0.95")),
                validation_reasoning="test",
                validation_timestamp=FIXED_VALIDATION_TIME,
            )

    def test_noncritical_allow_approval(self) -> None:
        """HIGH+MEDIUM+LOW don't block. Kills: treating all as critical."""
        decision = ValidationDecision(
            identity=valid_identity(),
            related_decision_id=ArtifactId.new(),
            related_artifact_version=FIRST_VERSION,
            validation_status=ValidationStatus.APPROVED,
            validation_findings=(valid_finding(),),
            validation_errors=(),
            validation_warnings=(),
            validation_risks=(),
            failed_validation_rules=(),
            supporting_evidence_references=("e1",),
            validation_confidence=Confidence(Decimal("0.95")),
            validation_reasoning="ok",
            validation_timestamp=FIXED_VALIDATION_TIME,
        )
        assert decision.validation_status == ValidationStatus.APPROVED


class TestValidationBareRejection:
    """Non-approval without issues must reject."""

    def test_rejection_without_issues_rejected(self) -> None:
        """REJECTED + no findings → reject. Kills: inverted not."""
        with pytest.raises(ValidationError) as exc:
            ValidationDecision(
                identity=valid_identity(),
                related_decision_id=ArtifactId.new(),
                related_artifact_version=FIRST_VERSION,
                validation_status=ValidationStatus.REJECTED,
                validation_findings=(),
                validation_errors=(),
                validation_warnings=(),
                validation_risks=(),
                failed_validation_rules=(),
                supporting_evidence_references=(),
                validation_confidence=Confidence(Decimal("0.80")),
                validation_reasoning="rejected",
                validation_timestamp=FIXED_VALIDATION_TIME,
            )
        assert "at least one issue" in str(exc.value)

    def test_rejection_with_one_issue_allowed(self) -> None:
        """REJECTED + issue → allow. Kills: inverted condition."""
        decision = ValidationDecision(
            identity=valid_identity(),
            related_decision_id=ArtifactId.new(),
            related_artifact_version=FIRST_VERSION,
            validation_status=ValidationStatus.REJECTED,
            validation_findings=(valid_finding(),),
            validation_errors=(),
            validation_warnings=(),
            validation_risks=(),
            failed_validation_rules=(),
            supporting_evidence_references=("e1",),
            validation_confidence=Confidence(Decimal("0.80")),
            validation_reasoning="rejected for reason",
            validation_timestamp=FIXED_VALIDATION_TIME,
        )
        assert len(decision.issues) == 1

    def test_approved_without_issues_allowed(self) -> None:
        """APPROVED + no findings → allow. Kills: wrong branch check."""
        decision = ValidationDecision(
            identity=valid_identity(),
            related_decision_id=ArtifactId.new(),
            related_artifact_version=FIRST_VERSION,
            validation_status=ValidationStatus.APPROVED,
            validation_findings=(),
            validation_errors=(),
            validation_warnings=(),
            validation_risks=(),
            failed_validation_rules=(),
            supporting_evidence_references=("clean",),
            validation_confidence=Confidence(Decimal("0.99")),
            validation_reasoning="all ok",
            validation_timestamp=FIXED_VALIDATION_TIME,
        )
        assert len(decision.issues) == 0


class TestClarificationTransitions:
    """State transitions must follow the table."""

    def test_created_to_open_allowed(self) -> None:
        assert may_transition(ClarificationStatus.CREATED, ClarificationStatus.OPEN)

    def test_created_to_answered_forbidden(self) -> None:
        assert not may_transition(ClarificationStatus.CREATED, ClarificationStatus.ANSWERED)

    def test_open_to_answered_allowed(self) -> None:
        assert may_transition(ClarificationStatus.OPEN, ClarificationStatus.ANSWERED)

    def test_open_to_resolved_forbidden(self) -> None:
        assert not may_transition(ClarificationStatus.OPEN, ClarificationStatus.RESOLVED)

    def test_answered_to_resolved_allowed(self) -> None:
        assert may_transition(ClarificationStatus.ANSWERED, ClarificationStatus.RESOLVED)

    def test_any_nonterminal_can_go_superseded(self) -> None:
        nonterminals = [
            ClarificationStatus.CREATED,
            ClarificationStatus.OPEN,
            ClarificationStatus.ANSWERED,
        ]
        for status in nonterminals:
            assert may_transition(status, ClarificationStatus.SUPERSEDED)


class TestTerminalStatuses:
    """Terminal statuses are exactly: Resolved, Superseded, Cancelled."""

    def test_exactly_three_terminals(self) -> None:
        assert len(TERMINAL_STATUSES) == EXPECTED_TERMINALS

    def test_resolved_terminal(self) -> None:
        assert ClarificationStatus.RESOLVED in TERMINAL_STATUSES

    def test_superseded_terminal(self) -> None:
        assert ClarificationStatus.SUPERSEDED in TERMINAL_STATUSES

    def test_cancelled_terminal(self) -> None:
        assert ClarificationStatus.CANCELLED in TERMINAL_STATUSES


class TestValidationIssuesCompleteness:
    """All four issue lists must be checked, not just one."""

    def test_mixed_critical_and_noncritical_blocks_approval(self) -> None:
        """Even one critical blocks when mixed with noncritical. Kills: any→all."""
        critical = ValidationFinding(
            what_failed="critical",
            why_it_failed="blocking",
            responsible_engine=ResponsibleEngine.ACCOUNTING,
            affected_artifact="art-1",
            blocking_severity=Severity.CRITICAL,
            recommended_next_step="stop",
            supporting_evidence_references=("ev",),
        )

        noncritical = ValidationFinding(
            what_failed="warning",
            why_it_failed="low issue",
            responsible_engine=ResponsibleEngine.INPUT,
            affected_artifact="art-1",
            blocking_severity=Severity.LOW,
            recommended_next_step="check",
            supporting_evidence_references=("ev",),
        )

        with pytest.raises(ValidationError):
            ValidationDecision(
                identity=valid_identity(),
                related_decision_id=ArtifactId.new(),
                related_artifact_version=FIRST_VERSION,
                validation_status=ValidationStatus.APPROVED,
                validation_findings=(critical, noncritical),
                validation_errors=(),
                validation_warnings=(),
                validation_risks=(),
                failed_validation_rules=(),
                supporting_evidence_references=("e1",),
                validation_confidence=Confidence(Decimal("0.95")),
                validation_reasoning="test",
                validation_timestamp=FIXED_VALIDATION_TIME,
            )
