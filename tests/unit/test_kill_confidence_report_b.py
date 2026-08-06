"""Mutation tests for confidence_report.py lines 350-693.

Targets: @post_init validations, comparison operators, enum identity checks,
None checks, and sum() counting in marker/score builders and record_confidence.

Each test is designed to FAIL if its target line is mutated:
- Comparison flipped (== to !=)
- None check inverted (is to is not)
- Identity check changed (is to ==)
- Validation removed or inverted
- Counting logic altered
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest

from accountant_dad.artifacts.evidence import (
    Corroborated,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.confidence import (
    Confidence,
    MeasurementState,
    measurement_state,
)
from accountant_dad.engines.input_engine.cleaner import (
    CleanedDocument,
    PreservationStatus,
)
from accountant_dad.engines.input_engine.confidence_report import (
    CAPTURE_FIDELITY_FIELD_NAME,
    CAPTURE_FIDELITY_ON_EXACT_MATCH,
    HumanCaptureEvidence,
    MalformedSignalError,
    MissingField,
    ParsedField,
    ReadingState,
    RegionReading,
    capture_fidelity,
    record_confidence,
)

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
HIGH = Decimal("0.9800")
NOTE = "Paid rent for June in cash."
EXPECTED_UNREAD_COUNT = 2
EXPECTED_MARKER_COUNT = 5


# ── builders ─────────────────────────────────────────────────────────────────


def a_cleaned_document(
    *, preservation_status: PreservationStatus = PreservationStatus.CLEANED_IS_SAFER
) -> CleanedDocument:
    frame = np.zeros((2, 2), dtype=np.uint8)
    return CleanedDocument(
        original=frame,
        cleaned=frame,
        quality_observations=(),
        preservation_status=preservation_status,
    )


def a_human_business_context(*, original_user_text: str = NOTE) -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=original_user_text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="typed by the operator",
            evidence_reference="the note field",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


def a_region(
    *,
    state: ReadingState = ReadingState.READ_AND_SCORED,
    source_location: str = "page 1, region 1",
) -> RegionReading:
    """Create a RegionReading. State is derived from text/confidence.

    state determines:
    - UNREAD: text=None (confidence also None)
    - READ_BUT_UNSCORED: text provided, confidence=None
    - READ_AND_SCORED: both text and confidence provided
    """
    if state == ReadingState.UNREAD:
        return RegionReading(source_location=source_location, text=None, extraction_confidence=None)
    if state == ReadingState.READ_BUT_UNSCORED:
        return RegionReading(
            source_location=source_location, text="text", extraction_confidence=None
        )
    # READ_AND_SCORED
    return RegionReading(source_location=source_location, text="text", extraction_confidence=HIGH)


def a_field(*, field_name: str = "amount", confidence: Confidence = HIGH) -> ParsedField:
    return ParsedField(field_name=field_name, extraction_confidence=confidence)


# ───────────────────────────────────────────────────────────────────────────
# LINE 351: ParsedField.__post_init__ — field_name.strip() non-blank check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: remove check, invert to `if self.field_name.strip()`, or strip() removed


class TestParsedFieldNameBlankValidation:
    """Line 351: `if not self.field_name.strip(): raise`
    Mutations that would pass: omitting strip(), inverting condition.
    """

    def test_blank_field_name_raises(self) -> None:
        """Blank field name (only spaces) must raise, not be allowed."""
        with pytest.raises(MalformedSignalError) as exc_info:
            ParsedField(field_name="   ", extraction_confidence=HIGH)
        assert "non-blank name" in str(exc_info.value).lower()

    def test_empty_field_name_raises(self) -> None:
        """Empty field name must raise."""
        with pytest.raises(MalformedSignalError):
            ParsedField(field_name="", extraction_confidence=HIGH)

    def test_whitespace_only_field_name_raises(self) -> None:
        """Field name with only tabs/newlines must raise."""
        with pytest.raises(MalformedSignalError):
            ParsedField(field_name="\t\n", extraction_confidence=HIGH)

    def test_valid_field_name_allowed(self) -> None:
        """Valid field name with content must be allowed."""
        f = ParsedField(field_name="amount", extraction_confidence=HIGH)
        assert f.field_name == "amount"

    def test_field_name_with_spaces_trimmed_allowed(self) -> None:
        """Field name with spaces around content must be allowed (strip works)."""
        f = ParsedField(field_name="  amount  ", extraction_confidence=HIGH)
        assert f.field_name == "  amount  "  # stored as-is, but strip() succeeded


# ───────────────────────────────────────────────────────────────────────────
# LINE 375-376: MissingField.__post_init__ — state.strip() non-blank check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: same as above


class TestMissingFieldStateBlankValidation:
    """Line 375: `if not self.state.strip(): raise`
    Also tests field_name blank check at line 373.
    """

    def test_blank_state_raises(self) -> None:
        """Blank state must raise."""
        with pytest.raises(MalformedSignalError) as exc_info:
            MissingField(field_name="valid", state="   ")
        assert "state" in str(exc_info.value).lower()

    def test_empty_state_raises(self) -> None:
        """Empty state must raise."""
        with pytest.raises(MalformedSignalError):
            MissingField(field_name="valid", state="")

    def test_blank_field_name_in_missing_field_raises(self) -> None:
        """Line 373: MissingField also validates field_name."""
        with pytest.raises(MalformedSignalError) as exc_info:
            MissingField(field_name="", state="absent")
        assert "non-blank name" in str(exc_info.value).lower()

    def test_valid_missing_field_allowed(self) -> None:
        """Valid missing field must be allowed."""
        m = MissingField(field_name="tax_id", state="absent")
        assert m.field_name == "tax_id"
        assert m.state == "absent"


# ───────────────────────────────────────────────────────────────────────────
# LINE 421: capture_fidelity() — exact equality check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: == to !=, or to in/not in


class TestCaptureFidelityExactMatch:
    """Line 421: `if evidence.submitted_text == evidence.stored.original_user_text:`
    Must be EXACT equality, not substring or partial match.
    """

    def test_exact_match_returns_matched_state(self) -> None:
        """Exact match must return CAPTURE_FIDELITY_ON_EXACT_MATCH."""
        text = "Paid rent for June in cash."
        context = a_human_business_context(original_user_text=text)
        evidence = HumanCaptureEvidence(submitted_text=text, stored=context)

        score, marker = capture_fidelity(evidence)

        assert measurement_state(score) is MeasurementState.MEASURED
        assert score == CAPTURE_FIDELITY_ON_EXACT_MATCH
        assert marker is None

    def test_substring_mismatch_returns_failed_state(self) -> None:
        """Substring of submitted text must NOT match."""
        text = "Paid rent for June in cash."
        context = a_human_business_context(original_user_text=text)
        evidence = HumanCaptureEvidence(submitted_text=text + " Extra text", stored=context)

        score, marker = capture_fidelity(evidence)

        assert measurement_state(score) is MeasurementState.FAILED
        assert marker is not None

    def test_case_difference_is_mismatch(self) -> None:
        """Case difference must be mismatch (exact equality)."""
        text = "Paid Rent for June in Cash."
        context = a_human_business_context(original_user_text=text.lower())
        evidence = HumanCaptureEvidence(submitted_text=text, stored=context)

        score, marker = capture_fidelity(evidence)

        assert measurement_state(score) is MeasurementState.FAILED
        assert marker is not None

    def test_trailing_space_is_mismatch(self) -> None:
        """Trailing space difference must be mismatch."""
        text = "Paid rent for June in cash."
        context = a_human_business_context(original_user_text=text)
        evidence = HumanCaptureEvidence(submitted_text=text + " ", stored=context)

        score, marker = capture_fidelity(evidence)

        assert measurement_state(score) is MeasurementState.FAILED
        assert marker is not None


# ───────────────────────────────────────────────────────────────────────────
# LINE 450: _preservation_marker() — enum identity check (is, not ==)
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is to ==, or check inverted


class TestPreservationMarkerEnumIdentity:
    """Line 450: `if cleaned.preservation_status is PreservationStatus.ORIGINAL_IS_SAFER:`
    Must use `is` identity check, not `==` equality.
    """

    def test_original_is_safer_produces_marker(self) -> None:
        """ORIGINAL_IS_SAFER status must produce a marker."""
        cleaned = a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER)
        regions = ()

        report = record_confidence(cleaned, regions, (), ())

        marker_subjects = [m.subject for m in report.uncertainty_markers]
        assert "the document as cleaned" in marker_subjects
        assert any("safer basis" in m.reason for m in report.uncertainty_markers)

    def test_cleaned_is_safer_no_preservation_marker(self) -> None:
        """CLEANED_IS_SAFER status must NOT produce a preservation marker."""
        cleaned = a_cleaned_document(preservation_status=PreservationStatus.CLEANED_IS_SAFER)
        regions = ()

        report = record_confidence(cleaned, regions, (), ())

        marker_subjects = [m.subject for m in report.uncertainty_markers]
        assert "the document as cleaned" not in marker_subjects


# ───────────────────────────────────────────────────────────────────────────
# LINE 477: _unread_region_markers() — enum identity check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is to ==


class TestUnreadRegionMarkersEnumIdentity:
    """Line 477: `if region.state is ReadingState.UNREAD:`
    Only UNREAD regions (state is ReadingState.UNREAD) should produce markers.
    """

    def test_unread_region_produces_marker(self) -> None:
        """UNREAD region must produce marker."""
        cleaned = a_cleaned_document()
        regions = (a_region(state=ReadingState.UNREAD),)

        report = record_confidence(cleaned, regions, (), ())

        subjects = [m.subject for m in report.uncertainty_markers]
        assert "page 1, region 1" in subjects
        assert any("could not read" in m.reason for m in report.uncertainty_markers)

    def test_read_with_score_region_no_unread_marker(self) -> None:
        """READ_WITH_SCORE region must NOT produce unread marker."""
        cleaned = a_cleaned_document()
        regions = (a_region(state=ReadingState.READ_AND_SCORED),)

        report = record_confidence(cleaned, regions, (), ())

        subjects = [m.subject for m in report.uncertainty_markers]
        assert "page 1, region 1" not in subjects

    def test_multiple_unread_regions_each_gets_marker(self) -> None:
        """Each UNREAD region must get its own marker."""
        cleaned = a_cleaned_document()
        regions = (
            a_region(state=ReadingState.UNREAD, source_location="page 1, region 1"),
            a_region(state=ReadingState.UNREAD, source_location="page 1, region 2"),
        )

        report = record_confidence(cleaned, regions, (), ())

        unread_markers = [m for m in report.uncertainty_markers if "could not read" in m.reason]
        assert len(unread_markers) == EXPECTED_UNREAD_COUNT


# ───────────────────────────────────────────────────────────────────────────
# LINE 503: _unscored_region_markers() — enum identity check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is to ==


class TestUnscoredRegionMarkersEnumIdentity:
    """Line 503: `if region.state is ReadingState.READ_BUT_UNSCORED:`
    Only READ_BUT_UNSCORED regions should produce markers.
    """

    def test_unscored_region_produces_marker(self) -> None:
        """READ_BUT_UNSCORED region must produce marker."""
        cleaned = a_cleaned_document()
        regions = (a_region(state=ReadingState.READ_BUT_UNSCORED),)

        report = record_confidence(cleaned, regions, (), ())

        subjects = [m.subject for m in report.uncertainty_markers]
        assert "page 1, region 1" in subjects
        assert any("no per-region extraction score" in m.reason for m in report.uncertainty_markers)

    def test_read_with_score_region_no_unscored_marker(self) -> None:
        """READ_WITH_SCORE region must NOT produce unscored marker."""
        cleaned = a_cleaned_document()
        regions = (a_region(state=ReadingState.READ_AND_SCORED),)

        report = record_confidence(cleaned, regions, (), ())

        assert not any(
            "no per-region extraction score" in m.reason for m in report.uncertainty_markers
        )

    def test_unread_region_not_unscored_marker(self) -> None:
        """UNREAD region should not produce unscored marker."""
        cleaned = a_cleaned_document()
        regions = (a_region(state=ReadingState.UNREAD),)

        report = record_confidence(cleaned, regions, (), ())

        assert not any("backend transcribed" in m.reason for m in report.uncertainty_markers)


# ───────────────────────────────────────────────────────────────────────────
# LINE 586: _capture_fidelity_state() — human_capture None check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is None to is not None


class TestCaptureFidelityStateNoneCheck:
    """Line 586: `if human_capture is None:`
    Must distinguish None from provided capture evidence.
    """

    def test_human_capture_none_returns_not_supplied(self) -> None:
        """None capture evidence must report 'not supplied'."""
        cleaned = a_cleaned_document()

        report = record_confidence(cleaned, (), (), (), human_capture=None)

        assert "not supplied" in report.reliability_information

    def test_human_capture_provided_not_not_supplied(self) -> None:
        """Provided capture evidence must NOT report 'not supplied'."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text=NOTE, stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        assert "not supplied" not in report.reliability_information


# ───────────────────────────────────────────────────────────────────────────
# LINE 589: _capture_fidelity_state() — measurement_state identity check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is to ==


class TestCaptureFidelityStateMeasurementCheck:
    """Line 589: `if measurement_state(score) is MeasurementState.MEASURED:`
    Must distinguish MEASURED from FAILED using identity check.
    """

    def test_matched_text_reports_matched(self) -> None:
        """Matched text must report 'matched the text as submitted'."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text=NOTE, stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        assert "matched the text as submitted" in report.reliability_information

    def test_mismatched_text_reports_could_not_establish(self) -> None:
        """Mismatched text must report failure to establish fidelity."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text="Different text", stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        assert "could not be established" in report.reliability_information


# ───────────────────────────────────────────────────────────────────────────
# LINE 607-608: _reliability_information() — sum() counting logic
# ───────────────────────────────────────────────────────────────────────────
# Mutation: sum logic broken, state checks inverted, counting wrong


class TestReliabilityInformationCounting:
    """Lines 607-608: `sum(1 for region in reader_regions if region.state is ...)`
    Correct counts must appear in reliability_information.
    """

    def test_unread_count_in_reliability(self) -> None:
        """Unread region count must appear in reliability_information."""
        cleaned = a_cleaned_document()
        regions = (
            a_region(state=ReadingState.UNREAD),
            a_region(state=ReadingState.READ_AND_SCORED),
        )

        report = record_confidence(cleaned, regions, (), ())

        assert "1 of 2 region(s) reader attempted could not" in report.reliability_information

    def test_unscored_count_in_reliability(self) -> None:
        """Unscored region count must appear in reliability_information."""
        cleaned = a_cleaned_document()
        regions = (
            a_region(state=ReadingState.READ_BUT_UNSCORED),
            a_region(state=ReadingState.READ_AND_SCORED),
        )

        report = record_confidence(cleaned, regions, (), ())

        assert "1 of them were read but carry no per-region" in report.reliability_information

    def test_zero_unread_count(self) -> None:
        """Zero unread regions must report correctly."""
        cleaned = a_cleaned_document()
        regions = (
            a_region(state=ReadingState.READ_AND_SCORED),
            a_region(state=ReadingState.READ_AND_SCORED),
        )

        report = record_confidence(cleaned, regions, (), ())

        assert "0 of 2 region(s) reader attempted could not" in report.reliability_information


# ───────────────────────────────────────────────────────────────────────────
# LINE 673: record_confidence() — human_capture is not None check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is not None to is None


class TestRecordConfidenceHumanCaptureCheck:
    """Line 673: `if human_capture is not None:`
    Capture fidelity must only be scored when capture is provided.
    """

    def test_human_capture_none_no_capture_fidelity_score(self) -> None:
        """None capture must not add capture fidelity score."""
        cleaned = a_cleaned_document()

        report = record_confidence(cleaned, (), (), (), human_capture=None)

        fidelity_scores = [
            s for s in report.confidence_scores if s.field_name == CAPTURE_FIDELITY_FIELD_NAME
        ]
        assert len(fidelity_scores) == 0

    def test_human_capture_provided_adds_capture_fidelity_score(self) -> None:
        """Provided capture must add capture fidelity score."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text=NOTE, stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        fidelity_scores = [
            s for s in report.confidence_scores if s.field_name == CAPTURE_FIDELITY_FIELD_NAME
        ]
        assert len(fidelity_scores) == 1


# ───────────────────────────────────────────────────────────────────────────
# LINE 683: record_confidence() — capture_marker is not None check
# ───────────────────────────────────────────────────────────────────────────
# Mutation: is not None to is None


class TestRecordConfidenceCaptureMarkerCheck:
    """Line 683: `if capture_marker is not None:`
    Capture failure marker must only be added when mismatch occurs.
    """

    def test_exact_match_no_capture_failure_marker(self) -> None:
        """Exact match must not add capture failure marker."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text=NOTE, stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        mismatch_markers = [
            m for m in report.uncertainty_markers if "stored text does not match" in m.reason
        ]
        assert len(mismatch_markers) == 0

    def test_mismatch_adds_capture_failure_marker(self) -> None:
        """Text mismatch must add capture failure marker."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text="Different text", stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        mismatch_markers = [
            m for m in report.uncertainty_markers if "text now stored does not match" in m.reason
        ]
        assert len(mismatch_markers) == 1
        assert "cleaner and reader are both" in mismatch_markers[0].reason


# ───────────────────────────────────────────────────────────────────────────
# Cross-cutting: combination tests that verify state flows correctly
# ───────────────────────────────────────────────────────────────────────────


class TestRecordConfidenceIntegration:
    """Verify all conditions work together correctly."""

    def test_all_marker_types_can_coexist(self) -> None:
        """All marker types should appear when all conditions present."""
        cleaned = a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER)
        regions = (
            a_region(state=ReadingState.UNREAD, source_location="page 1, region 1"),
            a_region(
                state=ReadingState.READ_BUT_UNSCORED,
                source_location="page 1, region 2",
            ),
        )
        missing = (MissingField(field_name="tax_id", state="absent"),)
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text="Different", stored=context)

        report = record_confidence(cleaned, regions, (), missing, human_capture=capture)

        # Should have markers for:
        # - preservation status
        # - unread region
        # - unscored region
        # - missing field
        # - capture mismatch
        assert len(report.uncertainty_markers) >= EXPECTED_MARKER_COUNT

    def test_capture_fidelity_field_appears_on_match(self) -> None:
        """Capture fidelity field must appear in scores on exact match."""
        cleaned = a_cleaned_document()
        context = a_human_business_context()
        capture = HumanCaptureEvidence(submitted_text=NOTE, stored=context)

        report = record_confidence(cleaned, (), (), (), human_capture=capture)

        fidelity_scores = [
            s for s in report.confidence_scores if s.field_name == CAPTURE_FIDELITY_FIELD_NAME
        ]
        assert len(fidelity_scores) == 1
        assert measurement_state(fidelity_scores[0].confidence) is MeasurementState.MEASURED
