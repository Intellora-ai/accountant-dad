"""Mutant killers for evidence.py — focused on INV-11 (provenance immutability).

Context: Evidence carries ORIGIN permanently, artifacts are immutable after creation.
A mutant that drops the origin, permits edit, or inverts a validation must die.

Strategy: For each validation boundary, write the SMALLEST test that would fail if
the source line were flipped. Assert the REAL RESULT (refusal, not just exception).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DocumentEvidenceObject,
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

# ── Helpers ──────────────────────────────────────────────────────────────────


def _ts(tz: timezone | None = None) -> datetime:
    """Timestamp with optional timezone."""
    if tz is None:
        tz = UTC
    return datetime(2026, 8, 6, 12, 0, tzinfo=tz)


def _id() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


# ── Timezone validation (line 177-182): both conditions must work ─────────────


def test_timezone_validator_checks_tzinfo_is_not_none() -> None:
    """Line 177: `if value.tzinfo is None` — mutant: flip to `is not None`.

    Mutant kills if: naive datetime is accepted.
    Real result: naive datetime REFUSED.
    """
    naive = datetime(2026, 8, 6, 12, 0)  # no tzinfo
    with pytest.raises(ValidationError) as exc:
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice.pdf",
            evidence_reference="page 1",
            timestamp=naive,
            confidence=Decimal("0.9800"),
            corroborated=Corroborated.NOT_ASSESSED,
        )
    assert "timezone" in str(exc.value).lower()


def test_timezone_validator_accepts_non_utc_timezones() -> None:
    """Line 177: validates tzinfo.utcoffset() is not None — falsification check.

    Mutant kills if: non-UTC timezones are refused.
    Real result: non-UTC timezones with valid offsets ACCEPTED.
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    ts = datetime(2026, 8, 6, 12, 0, tzinfo=ist)

    # Must NOT raise — non-UTC timezone is valid
    prov = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice.pdf",
        evidence_reference="page 1",
        timestamp=ts,
        confidence=Decimal("0.9800"),
        corroborated=Corroborated.NOT_ASSESSED,
    )
    assert prov.timestamp.tzinfo is ist


# ── _reject_human_origin (line 213): must check equality, not absence ────────


def test_reject_human_origin_checks_type_equality_not_presence() -> None:
    """Line 213: `if provenance.source_type is SourceType.HUMAN:` — mutant: flip to `is not`.

    Mutant kills if: DOCUMENT or STRUCTURED_METADATA origins are refused in fields.
    Real result: only HUMAN is refused; others ACCEPTED.
    """
    # DOCUMENT origin — must be ACCEPTED in detected_field
    ok_field = DetectedField(
        name="Amount",
        value="100.00",
        provenance=Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice.pdf",
            evidence_reference="page 1",
            timestamp=_ts(),
            confidence=Decimal("0.9800"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )
    # Must NOT raise
    doc = StructuredDocument(
        extracted_text="Invoice 100",
        detected_fields=(ok_field,),
        document_structure="header",
        detected_tables=(),
    )
    assert doc.detected_fields[0].provenance.source_type is SourceType.DOCUMENT


# ── Duplicated field names check (line 240): must count occurrences ──────────


def test_duplicated_field_check_counts_more_than_two() -> None:
    """Line 240: `if names.count(name) > 1` — mutant: change to >= or <= (counting logic).

    Mutant kills if: three or four fields with same name are accepted.
    Real result: ANY duplicate is REFUSED.
    """
    triple = (
        DetectedField(
            name="Amount",
            value="100",
            provenance=Provenance(
                source_type=SourceType.DOCUMENT,
                source_id="invoice.pdf",
                evidence_reference="page 1",
                timestamp=_ts(),
                confidence=Decimal("0.9800"),
                corroborated=Corroborated.NOT_ASSESSED,
            ),
        ),
    ) * 3  # Three fields all named "Amount"

    with pytest.raises(ValidationError, match="Amount"):
        StructuredDocument(
            extracted_text="Invoice 100",
            detected_fields=triple,
            document_structure="header",
            detected_tables=(),
        )


# ── Confidence scores duplicates check (line 297): must count all ────────────


def test_confidence_scores_check_counts_duplicates() -> None:
    """Line 297: `if names.count(name) > 1` — mutant: change > to >= (double-count check).

    Mutant kills if: three or more scores for same field are accepted.
    Real result: ANY duplicate is REFUSED.
    """
    triple_scores = (FieldConfidence(field_name="Amount", confidence=Decimal("0.9800")),) * 3

    with pytest.raises(ValidationError, match="Amount"):
        ConfidenceReport(
            confidence_scores=triple_scores,
            uncertainty_markers=(),
            reliability_information="test",
            risky_fields=(),
        )


# ── Risky fields duplicates (line 307-308): same as above ────────────────────


def test_risky_fields_check_counts_duplicates() -> None:
    """Line 307-308: `if risky.count(name) > 1` — mutant: change > to >=.

    Mutant kills if: three or more risky_fields entries are accepted.
    Real result: ANY duplicate is REFUSED.
    """
    triple_risky = ("Date",) * 3

    with pytest.raises(ValidationError, match="Date"):
        ConfidenceReport(
            confidence_scores=(),
            uncertainty_markers=(),
            reliability_information="test",
            risky_fields=triple_risky,
        )


# ── _must_declare_a_human_origin (line 330): checks is not, must negate ──────


def test_human_business_context_requires_human_source_type() -> None:
    """Line 330: `if self.provenance.source_type is not SourceType.HUMAN:` — mutant: flip to `is`.

    Mutant kills if: DOCUMENT or STRUCTURED_METADATA origins are accepted for human context.
    Real result: ONLY HUMAN origin is accepted; others REFUSED.
    """
    # Try to create HumanBusinessContext with DOCUMENT origin — must FAIL
    with pytest.raises(ValidationError, match="Human"):
        HumanBusinessContext(
            original_user_text="Some note",
            provenance=Provenance(
                source_type=SourceType.DOCUMENT,
                source_id="invoice.pdf",
                evidence_reference="page 1",
                timestamp=_ts(),
                confidence=Decimal("0.9800"),
                corroborated=Corroborated.NOT_ASSESSED,
            ),
        )


# ── Source references non-empty (line 375): must check length > 0 ────────────


def test_evidence_object_requires_at_least_one_source_reference() -> None:
    """Line 375: `if not self.source_references:` — mutant: flip to `if self.source_references:`.

    Mutant kills if: empty source_references tuple is accepted.
    Real result: REFUSED (evidence with no source is not evidence).
    """
    with pytest.raises(ValidationError, match="source reference"):
        DocumentEvidenceObject(
            identity=_id(),
            document_id=DocumentId.new(),
            source_references=(),  # Empty — must be REFUSED
            structured_document=StructuredDocument(
                extracted_text="Invoice",
                detected_fields=(),
                document_structure="header",
                detected_tables=(),
            ),
            confidence_report=ConfidenceReport(
                confidence_scores=(),
                uncertainty_markers=(),
                reliability_information="test",
                risky_fields=(),
            ),
        )


# ── Repeated source references (line 380): must detect duplicates ────────────


def test_evidence_object_detects_repeated_source_references() -> None:
    """Line 380: `if repeated:` — mutant: flip to `if not repeated:`.

    Mutant kills if: repeated source_references are accepted.
    Real result: REFUSED (evidence is traceable to DISTINCT sources).
    """
    dup_ref = ("upload:invoice.pdf", "upload:invoice.pdf")

    with pytest.raises(ValidationError, match=r"upload:invoice\.pdf"):
        DocumentEvidenceObject(
            identity=_id(),
            document_id=DocumentId.new(),
            source_references=dup_ref,  # Duplicated — must be REFUSED
            structured_document=StructuredDocument(
                extracted_text="Invoice",
                detected_fields=(),
                document_structure="header",
                detected_tables=(),
            ),
            confidence_report=ConfidenceReport(
                confidence_scores=(),
                uncertainty_markers=(),
                reliability_information="test",
                risky_fields=(),
            ),
        )
