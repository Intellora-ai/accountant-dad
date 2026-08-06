"""Mutation tests for conformance_registry lines 1290-1720.

Target: tuples, empty sequences, enum values, string comparisons.
Falsify: flip (), flip == to !=, flip enum values.
"""

import pytest
from pydantic import ValidationError

from accountant_dad.conformance_registry import (
    AUDIT_POINTS_HOME,
    BLAME_IS_UPSTREAM,
    BLANK_NAMES_NOTHING,
    COMPLETE_POSTS,
    FINDING_SHOWS_EVIDENCE,
    INCOMPLETE_NAMES_IT,
    NO_ANSWER_FIELD,
    NO_APPROVAL_ON_CRITICAL,
    NO_REPAIR_FIELD,
    NO_SELF_CORRECTION,
    REFUSAL_SAYS_WHY,
    REGISTRY,
    REQUEST_CITES_EVIDENCE,
    TRANSPORT_ONLY,
)


class TestEmptyTupleBoundaries:
    """Kill mutants that flip () to (x,) or drop empty checks."""

    def test_incomplete_names_must_have_at_least_one_unresolved_doubt(self) -> None:
        """Verify empty unresolved_doubts=() is rejected. Flipping to (1,) must pass."""
        for rule in REGISTRY.controls:
            if rule.prohibition == INCOMPLETE_NAMES_IT:
                with pytest.raises(ValidationError):
                    rule.violating()
                # Clean should pass
                rule.clean()
                return
        pytest.fail("INCOMPLETE_NAMES_IT not found")

    def test_request_must_cite_evidence(self) -> None:
        """Verify supporting_evidence_references=() is rejected."""
        for rule in REGISTRY.controls:
            if rule.prohibition == REQUEST_CITES_EVIDENCE:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("REQUEST_CITES_EVIDENCE not found")

    def test_refusal_must_include_findings(self) -> None:
        """Verify validation_findings=() is rejected on rejection status."""
        for rule in REGISTRY.controls:
            if rule.prohibition == REFUSAL_SAYS_WHY:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("REFUSAL_SAYS_WHY not found")

    def test_finding_shows_evidence_rejects_empty_references(self) -> None:
        """Verify finding without evidence is rejected."""
        for rule in REGISTRY.controls:
            if rule.prohibition == FINDING_SHOWS_EVIDENCE:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("FINDING_SHOWS_EVIDENCE not found")


class TestStringBoundaries:
    """Kill mutants that blank strings, remove string validation."""

    def test_blank_names_nothing_rejects_whitespace(self) -> None:
        """Verify affected_decision="   " is rejected."""
        for rule in REGISTRY.controls:
            if rule.prohibition == BLANK_NAMES_NOTHING:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("BLANK_NAMES_NOTHING not found")

    def test_no_answer_field_forbids_answer_on_clarification(self) -> None:
        """Verify answer field is forbidden in Clarification. Flip string to empty."""
        for rule in REGISTRY.controls:
            if rule.prohibition == NO_ANSWER_FIELD:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("NO_ANSWER_FIELD not found")


class TestEnumComparisons:
    """Kill mutants that flip Severity.HIGH <-> Severity.CRITICAL."""

    def test_no_approval_on_critical_distinguishes_severity(self) -> None:
        """Verify HIGH allows, CRITICAL blocks. Flip enum kills test."""
        for rule in REGISTRY.controls:
            if rule.prohibition == NO_APPROVAL_ON_CRITICAL:
                # Clean (HIGH) must pass
                clean_obj = rule.clean()
                assert clean_obj is not None
                # Violating (CRITICAL) must fail
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("NO_APPROVAL_ON_CRITICAL not found")


class TestEnumValueIdentity:
    """Kill mutants that flip enum values or replace enums with strings."""

    def test_blame_is_upstream_rejects_self_blame(self) -> None:
        """Verify Validation.ACCOUNTING is accepted, string 'Validation' rejected."""
        for rule in REGISTRY.controls:
            if rule.prohibition == BLAME_IS_UPSTREAM:
                # Clean uses ResponsibleEngine.ACCOUNTING (enum)
                clean_obj = rule.clean()
                assert clean_obj is not None
                # Violating uses string "Validation" (forbidden)
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("BLAME_IS_UPSTREAM not found")


class TestTransportOnlyRule:
    """Kill mutants that remove accounting_treatment field validation."""

    def test_transport_only_forbids_accounting_treatment(self) -> None:
        """Verify accounting_treatment field is forbidden on Execution."""
        for rule in REGISTRY.controls:
            if rule.prohibition == TRANSPORT_ONLY:
                # Clean (no accounting_treatment) passes
                clean_obj = rule.clean()
                assert clean_obj is not None
                # Violating (has accounting_treatment) fails
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("TRANSPORT_ONLY not found")


class TestNoRepairField:
    """Kill mutants that remove corrected_ledger field validation."""

    def test_no_repair_field_forbids_correction(self) -> None:
        """Verify corrected_ledger field is forbidden on Validation."""
        for rule in REGISTRY.controls:
            if rule.prohibition == NO_REPAIR_FIELD:
                # Clean passes (base validation)
                clean_obj = rule.clean()
                assert clean_obj is not None
                # Violating fails (has corrected_ledger)
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("NO_REPAIR_FIELD not found")


class TestUUIDIdentityMutants:
    """Kill mutants that flip UUID "6" <-> "9" or remove checks."""

    def test_no_self_correction_uuid_mismatch(self) -> None:
        """Verify execution_id != corrected_execution_result._uuid.
        Flip 6->9 or 9->6 kills test."""
        for rule in REGISTRY.controls:
            if rule.prohibition == NO_SELF_CORRECTION:
                # Violating: corrects_execution_result=ExecutionId(_uuid("6"))
                # should be rejected because it corrects itself
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("NO_SELF_CORRECTION not found")

    def test_audit_points_home_uuid_match(self) -> None:
        """Verify audit_reference.execution_id matches execution.id.
        Flip 6->9 or 9->6 kills test."""
        for rule in REGISTRY.controls:
            if rule.prohibition == AUDIT_POINTS_HOME:
                # Clean should pass - audit reference points to execution id
                clean_obj = rule.clean()
                assert clean_obj is not None
                # Violating: audit_reference points to wrong ExecutionId
                with pytest.raises(ValidationError):
                    rule.violating()
                return
        pytest.fail("AUDIT_POINTS_HOME not found")


class TestBalanceRule:
    """Kill mutants that flip empty tuple check in balance constraint."""

    def test_balance_both_halves_rejects_empty_both(self) -> None:
        """Verify both debit_entries=() and credit_entries=() is rejected.
        Flip () to (1,) must cause test to fail."""
        for rule in REGISTRY.controls:
            if rule.prohibition == COMPLETE_POSTS:
                with pytest.raises(ValidationError):
                    rule.violating()
                rule.clean()
                return
        pytest.fail("BOTH_HALVES_BALANCE not found")


class TestRuleCountAndIdentifiers:
    """Kill mutants that remove rules or change identifiers."""

    def test_registry_contains_all_required_rules(self) -> None:
        """Verify critical rules exist. Deletion kills this."""
        required = {
            COMPLETE_POSTS,
            INCOMPLETE_NAMES_IT,
            NO_ANSWER_FIELD,
            BLANK_NAMES_NOTHING,
            REQUEST_CITES_EVIDENCE,
            NO_REPAIR_FIELD,
            NO_APPROVAL_ON_CRITICAL,
            REFUSAL_SAYS_WHY,
            FINDING_SHOWS_EVIDENCE,
            BLAME_IS_UPSTREAM,
            NO_SELF_CORRECTION,
            AUDIT_POINTS_HOME,
            TRANSPORT_ONLY,
        }
        found = {r.prohibition for r in REGISTRY.controls}
        assert required.issubset(found), f"Missing: {required - found}"

    def test_registry_has_callable_clean_and_violating(self) -> None:
        """Verify all rules have callable clean/violating. Flip callable kills."""
        for rule in REGISTRY.controls:
            assert callable(rule.clean), f"{rule.prohibition}.clean not callable"
            assert callable(rule.violating), f"{rule.prohibition}.violating not callable"
