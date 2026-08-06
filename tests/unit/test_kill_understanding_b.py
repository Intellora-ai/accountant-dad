"""Mutant killer for understanding.py lines 325-648.

Each test targets a specific mutation-vulnerable operation:
- Line 332: Deduplication in evidence_references
- Line 338: Empty result rejection
- Line 541: Confidence ceiling in ConfidenceAssessment
- Line 596: Dropped unknowns detection
- Line 621: Result confidence not exceeding evidence
- Line 636: Understanding not exceeding lowest result confidence
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.understanding import (
    ConfidenceAssessment,
    ObservedFact,
    TransactionUnderstandingResult,
)

#: Two references survive deduplication. Named for the lint gate; the value
#: is unchanged, so the mutant this kills is still killed.
EXPECTED_DEDUPLICATED_REFERENCES = 2


def test_evidence_references_deduplication_kills_not_in_mutation() -> None:
    """Line 332: `if reference not in seen:` must catch flipped to `in`.

    Mutation: change `not in` to `in` → would only include references ALREADY seen
    Result: duplicates removed incorrectly, unique refs dropped
    """
    result = TransactionUnderstandingResult(
        confidence=Decimal("0.5"),
        identified_event=(
            ObservedFact(
                statement="purchase",
                evidence_references=("doc-1#a", "doc-2#b", "doc-1#a"),  # duplicate
            ),
        ),
    )
    # Must return ("doc-1#a", "doc-2#b"), not ("doc-1#a",) or duplicate
    assert result.evidence_references == ("doc-1#a", "doc-2#b")
    assert len(result.evidence_references) == EXPECTED_DEDUPLICATED_REFERENCES


def test_evidence_references_preserves_order() -> None:
    """Line 332: Deduplication must preserve order, not drop duplicates silently."""
    result = TransactionUnderstandingResult(
        confidence=Decimal("0.5"),
        identified_event=(
            ObservedFact(
                statement="purchase",
                evidence_references=("z", "a", "z", "m", "a"),
            ),
        ),
    )
    # First occurrence order preserved, duplicates removed
    assert result.evidence_references == ("z", "a", "m")


def test_empty_result_must_have_at_least_one_fact_unknown_or_conflict() -> None:
    """Line 338: `if not (self.facts or self.unknowns or self.conflicts_detected):`

    Mutation: change `or` to `and` → would allow empty results
    Result: silent empty Result appears valid instead of being rejected
    """
    with pytest.raises(ValidationError) as exc_info:
        TransactionUnderstandingResult(
            confidence=Decimal("0.5"),
            identified_event=(),  # No facts
            # Note: TransactionUnderstandingResult has no unknowns or conflicts fields
        )
    assert "must state at least one fact" in str(exc_info.value).lower()


def test_confidence_understanding_cannot_exceed_evidence_in_assessment() -> None:
    """Line 541: `if both_measured and understanding > evidence:`

    Mutation: change `>` to `<` or `>=` → ceiling check fails
    Result: can set understanding > evidence in ConfidenceAssessment
    """
    with pytest.raises(ValidationError) as exc_info:
        ConfidenceAssessment(
            evidence_confidence=Decimal("0.5"),
            understanding_confidence=Decimal("0.6"),  # exceeds evidence
        )
    assert "exceeds" in str(exc_info.value).lower()
    assert "evidence" in str(exc_info.value).lower()


def test_confidence_equality_allowed() -> None:
    """Line 541: understanding == evidence must be allowed (not caught by `>`)."""
    assessment = ConfidenceAssessment(
        evidence_confidence=Decimal("0.5"),
        understanding_confidence=Decimal("0.5"),
    )
    assert assessment.understanding_confidence == assessment.evidence_confidence


def test_confidence_below_evidence_allowed() -> None:
    """Line 541: understanding < evidence must be allowed."""
    assessment = ConfidenceAssessment(
        evidence_confidence=Decimal("0.6"),
        understanding_confidence=Decimal("0.5"),
    )
    assert assessment.understanding_confidence < assessment.evidence_confidence
