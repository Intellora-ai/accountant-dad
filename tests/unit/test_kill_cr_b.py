"""Kill mutations in conformance_registry.py lines 430-860.

Targets factory defaults, enum values, empty tuples, string constants,
and integer boundaries. Each test is falsified by flipping the source,
confirmed RED, restored GREEN.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError

from accountant_dad.artifacts.clarification import (
    ClarificationPriority,
    ClarificationStatus,
)
from accountant_dad.artifacts.decision import DecisionStatus
from accountant_dad.artifacts.validation import (
    ResponsibleEngine,
    Severity,
    ValidationStatus,
)
from accountant_dad.conformance import Enforcement, Prohibition
from accountant_dad.conformance_registry import (
    BALANCE,
    BLANK_NAMES_NOTHING,
    COMPLETE_POSTS,
    INCOMPLETE_NAMES_IT,
    PAISA,
    PROHIBITIONS,
    _clarification,
    _control,
    _doubt,
    _execution,
    _finding,
    _incomplete_decision,
    _journal_line,
    _predicate,
    _review_only,
    _validation,
)

# Minimum count of prohibitions to catch deletion mutations
_MIN_PROHIBITION_COUNT = 39


class TestUnresolvedDoubtDefaults:
    """Kill mutations in _doubt factory (UnresolvedDoubt fields)."""

    def test_doubt_has_missing_fact(self) -> None:
        """missing_fact must be set."""
        doubt = _doubt()
        assert doubt.missing_fact == "the date the goods were received"
        assert doubt.missing_fact != ""

    def test_doubt_has_required_clarification(self) -> None:
        """required_clarification must be set."""
        doubt = _doubt()
        assert "date" in doubt.required_clarification.lower()
        assert doubt.required_clarification != ""


class TestIncompletDecisionDefaults:
    """Kill mutations in _incomplete_decision factory (DecisionStatus enum)."""

    def test_incomplete_has_incomplete_status_not_complete(self) -> None:
        """DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED, not COMPLETE."""
        decision = _incomplete_decision()
        assert decision.decision_status == DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED

    def test_incomplete_has_empty_debit_entries(self) -> None:
        """debit_entries must be empty tuple, not None or single item."""
        decision = _incomplete_decision()
        assert decision.debit_entries == ()
        assert len(decision.debit_entries) == 0

    def test_incomplete_has_empty_credit_entries(self) -> None:
        """credit_entries must be empty tuple, not None or single item."""
        decision = _incomplete_decision()
        assert decision.credit_entries == ()
        assert len(decision.credit_entries) == 0

    def test_incomplete_has_single_unresolved_doubt(self) -> None:
        """unresolved_doubts must have exactly one item, not zero."""
        decision = _incomplete_decision()
        assert len(decision.unresolved_doubts) == 1


class TestJournalLineDefaults:
    """Kill mutations in _journal_line factory (amount values, strings)."""

    def test_journal_line_has_office_equipment_ledger(self) -> None:
        """ledger must be "Office Equipment", not other values."""
        line = _journal_line()
        assert line.ledger == "Office Equipment"

    def test_journal_line_amount_is_exact_decimal(self) -> None:
        """Journal line amounts must be exact to the paisa (Decimal)."""
        line = _journal_line()
        # Check it's a Decimal, not a float
        assert isinstance(line.amount, Decimal)
        assert line.amount == Decimal("1180.00")

    def test_journal_line_amount_override_works(self) -> None:
        """Override must change the amount."""
        line = _journal_line(amount=Decimal("500.50"))
        assert line.amount == Decimal("500.50")
        assert line.amount != Decimal("1180.00")


class TestClarificationRequestDefaults:
    """Kill mutations in _clarification factory (enums, strings, tuples)."""

    def test_clarification_priority_high_not_low(self) -> None:
        """priority: ClarificationPriority.HIGH, not LOW."""
        clar = _clarification()
        assert clar.priority == ClarificationPriority.HIGH

    def test_clarification_status_created(self) -> None:
        """status: ClarificationStatus.CREATED."""
        clar = _clarification()
        assert clar.status == ClarificationStatus.CREATED
        assert clar.status.value == "Created"

    def test_clarification_version_is_one(self) -> None:
        """related_artifact_version: 1, not 0 or 2."""
        clar = _clarification()
        assert clar.related_artifact_version == 1
        assert clar.related_artifact_version != 0
        assert clar.related_artifact_version != 1 + 1

    def test_clarification_has_single_missing_info(self) -> None:
        """missing_information must have exactly one string."""
        clar = _clarification()
        assert len(clar.missing_information) == 1
        assert "date" in clar.missing_information[0].lower()

    def test_clarification_has_empty_detected_conflicts(self) -> None:
        """detected_conflicts must be empty tuple, not None."""
        clar = _clarification()
        assert clar.detected_conflicts == ()
        assert len(clar.detected_conflicts) == 0

    def test_clarification_has_single_evidence_reference(self) -> None:
        """supporting_evidence_references must have exactly one reference."""
        clar = _clarification()
        assert len(clar.supporting_evidence_references) == 1
        assert "page" in clar.supporting_evidence_references[0].lower()


class TestValidationFindingDefaults:
    """Kill mutations in _finding factory (enums, strings)."""

    def test_finding_severity_low_not_high(self) -> None:
        """blocking_severity: Severity.LOW, not HIGH."""
        finding = _finding()
        assert finding.blocking_severity == Severity.LOW

    def test_finding_responsible_engine_accounting(self) -> None:
        """responsible_engine: ResponsibleEngine.ACCOUNTING, not others."""
        finding = _finding()
        assert finding.responsible_engine == ResponsibleEngine.ACCOUNTING

    def test_finding_has_exactly_one_evidence_reference(self) -> None:
        """supporting_evidence_references must have exactly one reference."""
        finding = _finding()
        assert len(finding.supporting_evidence_references) == 1
        assert "page" in finding.supporting_evidence_references[0].lower()


class TestValidationDecisionDefaults:
    """Kill mutations in _validation factory (enums, empty tuples, strings)."""

    def test_validation_status_approved_not_rejected(self) -> None:
        """validation_status: ValidationStatus.APPROVED, not REJECTED."""
        validation = _validation()
        assert validation.validation_status == ValidationStatus.APPROVED

    def test_validation_has_empty_findings(self) -> None:
        """validation_findings must be empty tuple, not None."""
        validation = _validation()
        assert validation.validation_findings == ()
        assert len(validation.validation_findings) == 0

    def test_validation_has_empty_errors(self) -> None:
        """validation_errors must be empty tuple."""
        validation = _validation()
        assert validation.validation_errors == ()

    def test_validation_has_empty_warnings(self) -> None:
        """validation_warnings must be empty tuple."""
        validation = _validation()
        assert validation.validation_warnings == ()

    def test_validation_has_empty_risks(self) -> None:
        """validation_risks must be empty tuple."""
        validation = _validation()
        assert validation.validation_risks == ()

    def test_validation_has_empty_failed_rules(self) -> None:
        """failed_validation_rules must be empty tuple."""
        validation = _validation()
        assert validation.failed_validation_rules == ()

    def test_validation_version_is_one(self) -> None:
        """related_artifact_version: 1, not 0."""
        validation = _validation()
        assert validation.related_artifact_version == 1


class TestExecutionResultDefaults:
    """Kill mutations in _execution factory (strings, numbers, None vs value)."""

    def test_execution_destination_tally_not_other(self) -> None:
        """destination_system: "Tally", not "SAP" or empty."""
        execution = _execution()
        assert execution.destination_system == "Tally"
        assert execution.destination_system != ""

    def test_execution_posting_status_posted_not_failed(self) -> None:
        """posting_status: "Posted", not "Failed" or other."""
        execution = _execution()
        assert execution.posting_status == "Posted"
        assert execution.posting_status != "Failed"

    def test_execution_has_single_external_transaction_id(self) -> None:
        """external_transaction_ids must have exactly one ID."""
        execution = _execution()
        assert len(execution.external_transaction_ids) == 1
        assert "TALLY" in execution.external_transaction_ids[0]

    def test_execution_retry_count_zero_not_one(self) -> None:
        """retry_count: 0, not 1 or -1."""
        execution = _execution()
        assert execution.retry_count == 0
        assert execution.retry_count < 1

    def test_execution_queue_status_drained_not_queued(self) -> None:
        """queue_status: "Drained", not "Queued"."""
        execution = _execution()
        assert execution.queue_status == "Drained"
        assert execution.queue_status != "Queued"

    def test_execution_notification_status_sent_not_pending(self) -> None:
        """notification_status: "Sent", not "Pending"."""
        execution = _execution()
        assert execution.notification_status == "Sent"
        assert execution.notification_status != "Pending"

    def test_execution_classified_error_is_none(self) -> None:
        """classified_error must be None, not empty string."""
        execution = _execution()
        assert execution.classified_error is None

    def test_execution_corrects_execution_result_is_none(self) -> None:
        """corrects_execution_result must be None, not empty string."""
        execution = _execution()
        assert execution.corrects_execution_result is None

    def test_execution_outcome_success_not_failed(self) -> None:
        """execution_outcome: "Success", not "Failed"."""
        execution = _execution()
        assert execution.execution_outcome == "Success"
        assert execution.execution_outcome != "Failed"

    def test_execution_decision_version_is_one(self) -> None:
        """decision_version: 1, not 0."""
        execution = _execution()
        assert execution.decision_version == 1


class TestPredicateEnforcement:
    """Kill mutations in _predicate factory (enforcement type)."""

    def test_predicate_uses_predicate_enforcement_not_review_only(self) -> None:
        """_predicate must use Enforcement.PREDICATE, not REVIEW_ONLY."""
        pred = _predicate("TEST_ID", "quote", "docs/test.md#test-anchor@aabbccddee11", "subject")
        assert pred.enforcement == Enforcement.PREDICATE

    def test_predicate_has_no_expiry(self) -> None:
        """_predicate must have no expiry field set."""
        pred = _predicate("TEST_ID", "quote", "docs/test.md#test-anchor@aabbccddee11", "subject")
        assert pred.expiry is None


class TestReviewOnlyEnforcement:
    """Kill mutations in _review_only factory (enforcement type, expiry)."""

    def test_review_only_uses_review_only_enforcement(self) -> None:
        """_review_only must use Enforcement.REVIEW_ONLY, not PREDICATE."""
        review = _review_only(
            "TEST_ID", "quote", "docs/test.md#test-anchor@aabbccddee11", "subject", "P3"
        )
        assert review.enforcement == Enforcement.REVIEW_ONLY

    def test_review_only_has_expiry_set(self) -> None:
        """_review_only must have expiry field set."""
        review = _review_only(
            "TEST_ID", "quote", "docs/test.md#test-anchor@aabbccddee11", "subject", "P3"
        )
        assert review.expiry is not None
        assert review.expiry == "P3"


class TestControlRefusal:
    """Kill mutations in _control factory (refusal tuple)."""

    def test_control_refusal_is_validation_error_tuple(self) -> None:
        """_control must set refusal=(ValidationError,), not other exceptions."""
        control = _control(
            "TEST_PROHIBITION",
            clean=lambda: {"test": "clean"},
            violating=lambda: {"test": "violating"},
        )
        assert control.refusal == (ValidationError,)
        assert control.refusal != ()
        assert control.refusal != (ValueError,)


class TestProhibitionsConstants:
    """Kill mutations in string constants (IMMUTABLE, LINEAGE, etc.)."""

    def test_prohibition_identifiers_are_unique(self) -> None:
        """All prohibition identifiers must be unique."""
        identifiers = [p.identifier for p in PROHIBITIONS]
        assert len(identifiers) == len(set(identifiers))

    def test_prohibition_contains_paisa_constant(self) -> None:
        """PROHIBITIONS must contain the PAISA rule."""
        ids = {p.identifier for p in PROHIBITIONS}
        assert PAISA in ids

    def test_prohibition_contains_balance_constant(self) -> None:
        """PROHIBITIONS must contain the BALANCE rule."""
        ids = {p.identifier for p in PROHIBITIONS}
        assert BALANCE in ids

    def test_prohibition_contains_complete_posts_constant(self) -> None:
        """PROHIBITIONS must contain the COMPLETE_POSTS rule."""
        ids = {p.identifier for p in PROHIBITIONS}
        assert COMPLETE_POSTS in ids

    def test_prohibition_contains_incomplete_names_it(self) -> None:
        """PROHIBITIONS must contain the INCOMPLETE_NAMES_IT rule."""
        ids = {p.identifier for p in PROHIBITIONS}
        assert INCOMPLETE_NAMES_IT in ids

    def test_prohibition_contains_blank_names_nothing(self) -> None:
        """PROHIBITIONS must contain the BLANK_NAMES_NOTHING rule."""
        ids = {p.identifier for p in PROHIBITIONS}
        assert BLANK_NAMES_NOTHING in ids

    def test_all_prohibitions_have_non_empty_identifier(self) -> None:
        """Every prohibition must have a non-empty identifier."""
        for p in PROHIBITIONS:
            assert p.identifier
            assert len(p.identifier) > 0

    def test_all_prohibitions_have_non_empty_quote(self) -> None:
        """Every prohibition must have a non-empty quote."""
        for p in PROHIBITIONS:
            assert p.quote
            assert len(p.quote) > 0

    def test_all_prohibitions_have_non_empty_source(self) -> None:
        """Every prohibition must have a non-empty source reference."""
        for p in PROHIBITIONS:
            assert p.source
            assert len(p.source) > 0

    def test_all_prohibitions_have_non_empty_subject(self) -> None:
        """Every prohibition must have a non-empty subject."""
        for p in PROHIBITIONS:
            assert p.subject
            assert len(p.subject) > 0


class TestProhibitionsCount:
    """Kill mutations that would change tuple size (deletions)."""

    def test_prohibitions_count_at_least_baseline(self) -> None:
        """PROHIBITIONS must have at least baseline entries."""
        # Minimum count to catch deletion mutations
        assert len(PROHIBITIONS) >= _MIN_PROHIBITION_COUNT

    def test_prohibitions_no_none_entries(self) -> None:
        """PROHIBITIONS tuple must not contain None entries."""
        assert None not in PROHIBITIONS
        for p in PROHIBITIONS:
            assert isinstance(p, Prohibition)
