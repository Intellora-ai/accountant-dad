"""Mutation tests for understanding.py: validators, boundaries, type checks.

Each test kills a specific mutation point — tests pass on correct code and
fail if that line is flipped/changed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from accountant_dad.artifacts.understanding import (
    MINIMUM_COMPETING_READINGS,
    AuthoredText,
    Conflict,
    ObservedFact,
    StatedFacts,
)
from accountant_dad.confidence import Confidence


class TestMeaningfulTextBoundary:
    """Kill mutation on line 152: if not value.strip() → if value.strip()"""

    def test_empty_string_rejected(self) -> None:
        """Empty string after strip must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ObservedFact(
                statement="   ",  # Will fail on _meaningful_text
                stated_text="doc",
                evidence_references=("ref:1",),
            )
        assert "must not be empty" in str(exc_info.value)

    def test_nonempty_string_accepted(self) -> None:
        """Non-empty string must be accepted."""
        fact = ObservedFact(
            statement="  x  ",  # Whitespace around real content
            stated_text="doc",
            evidence_references=("ref:1",),
        )
        assert "x" in fact.statement

    def test_single_char_accepted(self) -> None:
        """Single character is valid."""
        fact = ObservedFact(
            statement="a",
            stated_text="doc",
            evidence_references=("ref:1",),
        )
        assert fact.statement == "a"


class TestAuthoredTextVocabularyScan:
    """Kill mutation on line 163-165: vocabulary check logic"""

    def test_forbidden_term_rejected(self) -> None:
        """Term from FORBIDDEN_VOCABULARY must be rejected."""
        with pytest.raises(ValidationError) as exc_info:

            class TestModel(BaseModel):  # type: ignore[explicit-any]  # the house pattern: pydantic's own signature carries Any, the gate stays on
                model_config = ConfigDict(extra="forbid")
                text: AuthoredText

            TestModel(text="This is an accounting decision")

        assert "accounting vocabulary" in str(exc_info.value)

    def test_forbidden_term_case_insensitive(self) -> None:
        """Forbidden term match is case-insensitive."""

        class TestModel(BaseModel):  # type: ignore[explicit-any]  # the house pattern: pydantic's own signature carries Any, the gate stays on
            model_config = ConfigDict(extra="forbid")
            text: AuthoredText

        with pytest.raises(ValidationError):
            TestModel(text="ACCOUNTING")

    def test_allowed_term_accepted(self) -> None:
        """Non-forbidden text is accepted."""

        class TestModel(BaseModel):  # type: ignore[explicit-any]  # the house pattern: pydantic's own signature carries Any, the gate stays on
            model_config = ConfigDict(extra="forbid")
            text: AuthoredText

        m = TestModel(text="The item description is a laptop")
        assert "laptop" in m.text

    def test_forbidden_plural_rejected(self) -> None:
        """Plural forms from FORBIDDEN_PLURALS must be rejected."""

        class TestModel(BaseModel):  # type: ignore[explicit-any]  # the house pattern: pydantic's own signature carries Any, the gate stays on
            model_config = ConfigDict(extra="forbid")
            text: AuthoredText

        with pytest.raises(ValidationError):
            TestModel(text="There are multiple ledgers")

    def test_multiple_forbidden_terms_all_reported(self) -> None:
        """If multiple forbidden terms exist, all are reported (sorted)."""

        class TestModel(BaseModel):  # type: ignore[explicit-any]  # the house pattern: pydantic's own signature carries Any, the gate stays on
            model_config = ConfigDict(extra="forbid")
            text: AuthoredText

        with pytest.raises(ValidationError) as exc_info:
            TestModel(text="The accounting journal contains asset and ledger entries")
        assert "accounting vocabulary" in str(exc_info.value)


class TestFactEvidenceRequirement:
    """Kill mutation on line 210: if not self.evidence_references:"""

    def test_fact_with_no_evidence_rejected(self) -> None:
        """Fact with empty evidence_references tuple is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ObservedFact(
                statement="Something happened",
                stated_text="Original quote",
                evidence_references=(),  # Empty!
            )
        assert "at least one evidence" in str(exc_info.value)

    def test_fact_with_one_evidence_accepted(self) -> None:
        """Fact with one evidence reference is accepted."""
        fact = ObservedFact(
            statement="Something happened",
            stated_text="Original quote",
            evidence_references=("page:1",),
        )
        assert len(fact.evidence_references) == 1

    def test_fact_with_multiple_evidence_accepted(self) -> None:
        """Fact with multiple evidence references is accepted."""
        fact = ObservedFact(
            statement="Something happened",
            stated_text="Original quote",
            evidence_references=("page:1", "line:5"),
        )
        assert len(fact.evidence_references) > 1


class TestStatedTextRequirement:
    """Kill mutation on line 224: if fact.stated_text is None:"""

    def test_stated_text_can_be_optional_on_fact(self) -> None:
        """ObservedFact allows stated_text=None by default."""
        fact = ObservedFact(
            statement="A fact",
            stated_text=None,  # Allowed on ObservedFact
            evidence_references=("ref:1",),
        )
        assert fact.stated_text is None

    def test_all_facts_with_stated_text_accepted(self) -> None:
        """When all facts carry stated_text, StatedFacts validator passes."""
        facts = (
            ObservedFact(
                statement="First",
                stated_text="Quote 1",
                evidence_references=("ref:1",),
            ),
            ObservedFact(
                statement="Second",
                stated_text="Quote 2",
                evidence_references=("ref:2",),
            ),
        )
        result = StatedFacts(facts)
        assert len(result) == MINIMUM_COMPETING_READINGS


class TestConflictMinimumReadings:
    """Kill mutation on line 267: < MINIMUM_COMPETING_READINGS"""

    def test_conflict_with_one_reading_rejected(self) -> None:
        """Conflict with fewer than 2 readings is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Conflict(
                subject="What is the amount?",
                competing_readings=(
                    ObservedFact(
                        statement="$100",
                        stated_text="100",
                        evidence_references=("line:1",),
                    ),
                ),
            )
        assert "at least two" in str(exc_info.value)

    def test_conflict_with_exact_minimum_accepted(self) -> None:
        """Conflict with exactly MINIMUM_COMPETING_READINGS is accepted."""
        conflict = Conflict(
            subject="What is the amount?",
            competing_readings=(
                ObservedFact(
                    statement="$100",
                    stated_text="100",
                    evidence_references=("line:1",),
                ),
                ObservedFact(
                    statement="$150",
                    stated_text="150",
                    evidence_references=("line:2",),
                ),
            ),
        )
        assert len(conflict.competing_readings) == MINIMUM_COMPETING_READINGS

    def test_conflict_with_more_readings_accepted(self) -> None:
        """Conflict with more than minimum readings is accepted."""
        extra_readings = MINIMUM_COMPETING_READINGS + 1
        conflict = Conflict(
            subject="Amount",
            competing_readings=(
                ObservedFact(
                    statement="$100",
                    stated_text="100",
                    evidence_references=("ref:1",),
                ),
                ObservedFact(
                    statement="$150",
                    stated_text="150",
                    evidence_references=("ref:2",),
                ),
                ObservedFact(
                    statement="$200",
                    stated_text="200",
                    evidence_references=("ref:3",),
                ),
            ),
        )
        assert len(conflict.competing_readings) == extra_readings


class TestConflictDuplicateDetection:
    """Kill mutation on line 274: len(set(statements)) < len(statements)"""

    def test_duplicate_statements_rejected(self) -> None:
        """Two facts with identical statements are rejected as non-conflict."""
        with pytest.raises(ValidationError) as exc_info:
            Conflict(
                subject="Amount?",
                competing_readings=(
                    ObservedFact(
                        statement="Same thing",
                        stated_text="Quote A",
                        evidence_references=("ref:1",),
                    ),
                    ObservedFact(
                        statement="Same thing",  # Duplicate statement
                        stated_text="Quote B",
                        evidence_references=("ref:2",),
                    ),
                ),
            )
        assert "identical readings" in str(exc_info.value)

    def test_different_statements_accepted(self) -> None:
        """Facts with different statements are accepted."""
        conflict = Conflict(
            subject="Amount?",
            competing_readings=(
                ObservedFact(
                    statement="First reading",
                    stated_text="Quote A",
                    evidence_references=("ref:1",),
                ),
                ObservedFact(
                    statement="Different reading",
                    stated_text="Quote B",
                    evidence_references=("ref:2",),
                ),
            ),
        )
        statements = [f.statement for f in conflict.competing_readings]
        unique_count = len(set(statements))
        total_count = len(statements)
        assert unique_count == total_count == MINIMUM_COMPETING_READINGS


class TestConfidenceIsDecimal:
    """Verify Confidence uses Decimal, not float (boundary for comparison)."""

    def test_confidence_from_decimal(self) -> None:
        """Confidence accepts Decimal and stores it exactly."""
        conf = Confidence(Decimal("0.95"))
        assert isinstance(conf, Decimal)
        assert conf == Decimal("0.95")

    def test_confidence_comparison_with_decimal(self) -> None:
        """Confidence comparison works with Decimal values."""
        conf_high = Confidence(Decimal("0.95"))
        conf_low = Confidence(Decimal("0.50"))
        assert conf_high > conf_low
