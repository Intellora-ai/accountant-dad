"""Mutation killer tests for conformance_registry.py (lines 1-430).

Targets:
  - Line 152: _CONFIDENCE Decimal value (0.9 vs 0.8/0.95)
  - Line 158: _UNSURE Decimal value (0.4 vs 0.3/0.5)
  - Line 173: UUID marker multiplier (8 vs 7/9)
  - Line 174: UUID version/variant nibbles (4, 8, 12 format)
  - Line 181-186: Envelope version and parent_versions empty tuple
  - Line 198: next(iter()) early return guard
  - Line 245, 249: Empty tuples in _structured_document
  - Line 256: Empty tuples in _confidence_report
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import Corroborated
from accountant_dad.conformance_registry import (
    _CONFIDENCE,
    _UNSURE,
    _confidence_report,
    _detected_field,
    _envelope,
    _evidence,
    _mutate,
    _provenance,
    _structured_document,
    _uuid,
)
from accountant_dad.identity import ArtifactId

_MARKER_MULTIPLIER_8 = 8
_MARKER_MULTIPLIER_4 = 4
_MARKER_MULTIPLIER_12 = 12
_MARKER_MULTIPLIER_11 = 11
_DECIMAL_SCALE = -4
_ENVELOPE_VERSION = 1
_ENVELOPE_VERSION_0 = 0
_ENVELOPE_VERSION_2 = 2
_VERSION_2_INDEX = 2


class TestConfidenceConstant:
    """Kill mutations in _CONFIDENCE value."""

    def test_confidence_is_exactly_090(self) -> None:
        """_CONFIDENCE must be 0.9000, not 0.8, 0.95, etc."""
        assert Decimal("0.9000") == _CONFIDENCE

    def test_confidence_not_089(self) -> None:
        """Catches mutation 0.9 -> 0.89."""
        assert Decimal("0.8900") != _CONFIDENCE

    def test_confidence_not_091(self) -> None:
        """Catches mutation 0.9 -> 0.91."""
        assert Decimal("0.9100") != _CONFIDENCE

    def test_confidence_not_080(self) -> None:
        """Catches mutation 0.9 -> 0.8."""
        assert Decimal("0.8000") != _CONFIDENCE

    def test_confidence_not_100(self) -> None:
        """Catches mutation 0.9 -> 1.0."""
        assert Decimal("1.0000") != _CONFIDENCE

    def test_confidence_scale_is_four_places(self) -> None:
        """Decimal scale must be exactly 4 places."""
        assert _CONFIDENCE.as_tuple().exponent == _DECIMAL_SCALE


class TestUnsureConstant:
    """Kill mutations in _UNSURE value."""

    def test_unsure_is_exactly_040(self) -> None:
        """_UNSURE must be 0.4000, not 0.3, 0.5, etc."""
        assert Decimal("0.4000") == _UNSURE

    def test_unsure_not_039(self) -> None:
        """Catches mutation 0.4 -> 0.39."""
        assert Decimal("0.3900") != _UNSURE

    def test_unsure_not_041(self) -> None:
        """Catches mutation 0.4 -> 0.41."""
        assert Decimal("0.4100") != _UNSURE

    def test_unsure_not_030(self) -> None:
        """Catches mutation 0.4 -> 0.3."""
        assert Decimal("0.3000") != _UNSURE

    def test_unsure_not_050(self) -> None:
        """Catches mutation 0.4 -> 0.5."""
        assert Decimal("0.5000") != _UNSURE

    def test_unsure_differs_from_confidence(self) -> None:
        """_UNSURE and _CONFIDENCE must be distinct."""
        assert _CONFIDENCE != _UNSURE


class TestUuidMarkerMultiplier:
    """Kill mutations in UUID marker multiplication (line 173)."""

    def test_uuid_body_is_eight_chars(self) -> None:
        """marker * 8 produces 8 hex digits."""
        u = _uuid("a")
        uuid_str = str(u)
        first_segment = uuid_str.split("-")[0]
        assert len(first_segment) == _MARKER_MULTIPLIER_8
        assert first_segment == "aaaaaaaa"

    def test_uuid_marker_multiplier_not_seven(self) -> None:
        """Catches mutation 8 -> 7."""
        u = _uuid("1")
        first_eight = str(u).split("-")[0]
        assert len(first_eight) == _MARKER_MULTIPLIER_8
        assert first_eight != "1111111"  # 7 chars

    def test_uuid_marker_multiplier_not_nine(self) -> None:
        """Catches mutation 8 -> 9."""
        u = _uuid("1")
        parts = str(u).split("-")
        # First segment should be 8, not 9
        assert len(parts[0]) == _MARKER_MULTIPLIER_8

    def test_uuid_second_segment_is_four_chars(self) -> None:
        """marker * 4 in second segment."""
        u = _uuid("2")
        segments = str(u).split("-")
        assert len(segments[1]) == _MARKER_MULTIPLIER_4
        assert segments[1] == "2222"

    def test_uuid_second_segment_not_three_chars(self) -> None:
        """Catches mutation 4 -> 3."""
        u = _uuid("3")
        segments = str(u).split("-")
        assert len(segments[1]) == _MARKER_MULTIPLIER_4
        assert segments[1] != "333"


class TestUuidVersionVariantNibbles:
    """Kill mutations in UUID format string (line 174)."""

    def test_uuid_version_nibble_is_4(self) -> None:
        """Third segment must start with '4' (v4 UUID)."""
        u = _uuid("5")
        version_segment = str(u).split("-")[2]
        assert version_segment[0] == "4"

    def test_uuid_version_not_3(self) -> None:
        """Catches mutation version 4 -> 3."""
        u = _uuid("5")
        version_segment = str(u).split("-")[2]
        assert version_segment[0] != "3"

    def test_uuid_version_not_5(self) -> None:
        """Catches mutation version 4 -> 5."""
        u = _uuid("5")
        version_segment = str(u).split("-")[2]
        assert version_segment[0] != "5"

    def test_uuid_variant_nibble_is_8(self) -> None:
        """Fourth segment must start with '8' (variant)."""
        u = _uuid("6")
        variant_segment = str(u).split("-")[3]
        assert variant_segment[0] == "8"

    def test_uuid_variant_not_9(self) -> None:
        """Catches mutation variant 8 -> 9."""
        u = _uuid("6")
        variant_segment = str(u).split("-")[3]
        assert variant_segment[0] != "9"

    def test_uuid_variant_not_a(self) -> None:
        """Catches mutation variant 8 -> a."""
        u = _uuid("6")
        variant_segment = str(u).split("-")[3]
        assert variant_segment[0] != "a"

    def test_uuid_tail_is_twelve_chars(self) -> None:
        """Last segment is marker * 12."""
        u = _uuid("7")
        tail = str(u).split("-")[4]
        assert len(tail) == _MARKER_MULTIPLIER_12
        assert tail == "777777777777"

    def test_uuid_tail_not_eleven_chars(self) -> None:
        """Catches mutation 12 -> 11."""
        u = _uuid("7")
        tail = str(u).split("-")[4]
        assert len(tail) == _MARKER_MULTIPLIER_12
        assert len(tail) != _MARKER_MULTIPLIER_11


class TestEnvelopeVersion:
    """Kill mutations in envelope field values."""

    def test_envelope_version_is_1(self) -> None:
        """Envelope version must be exactly 1."""
        env = _envelope()
        assert env.version == _ENVELOPE_VERSION

    def test_envelope_version_not_0(self) -> None:
        """Catches mutation version 1 -> 0."""
        env = _envelope()
        assert env.version != _ENVELOPE_VERSION_0

    def test_envelope_version_not_2(self) -> None:
        """Catches mutation version 1 -> 2."""
        env = _envelope()
        assert env.version != _ENVELOPE_VERSION_2

    def test_envelope_parent_versions_empty(self) -> None:
        """parent_versions must be empty tuple, not None or single item."""
        env = _envelope()
        assert env.parent_versions == ()
        assert len(env.parent_versions) == 0

    def test_envelope_parent_versions_not_none(self) -> None:
        """parent_versions tuple never becomes None."""
        env = _envelope()
        assert env.parent_versions is not None

    def test_envelope_has_transaction_id(self) -> None:
        """transaction_id must be set."""
        env = _envelope()
        assert env.transaction_id is not None

    def test_envelope_has_artifact_id(self) -> None:
        """artifact_id must be set."""
        env = _envelope()
        assert env.artifact_id is not None
        assert isinstance(env.artifact_id, ArtifactId)


class TestProvenanceConfidenceValue:
    """Kill mutations in Provenance confidence field."""

    def test_provenance_confidence_is_confidence_constant(self) -> None:
        """Provenance must use _CONFIDENCE, not _UNSURE or other value."""
        prov = _provenance()
        assert prov.confidence == _CONFIDENCE
        assert Decimal("0.9000") == prov.confidence

    def test_provenance_confidence_not_unsure(self) -> None:
        """Catches mutation confidence -> unsure."""
        prov = _provenance()
        assert prov.confidence != _UNSURE

    def test_provenance_corroborated_is_not_assessed(self) -> None:
        """corroborated must be NOT_ASSESSED, not other status."""
        prov = _provenance()
        assert prov.corroborated == Corroborated.NOT_ASSESSED


class TestDetectedFieldTuples:
    """Kill mutations in tuple structure."""

    def test_structured_document_detected_fields_is_tuple(self) -> None:
        """detected_fields must be a tuple, not empty."""
        sd = _structured_document()
        assert isinstance(sd.detected_fields, tuple)
        assert len(sd.detected_fields) == 1

    def test_structured_document_detected_fields_not_empty(self) -> None:
        """Catches mutation (field,) -> ()."""
        sd = _structured_document()
        assert len(sd.detected_fields) != 0

    def test_structured_document_detected_tables_empty(self) -> None:
        """detected_tables must be empty tuple."""
        sd = _structured_document()
        assert sd.detected_tables == ()
        assert len(sd.detected_tables) == 0

    def test_structured_document_detected_tables_not_none(self) -> None:
        """Empty tuple never becomes None."""
        sd = _structured_document()
        assert sd.detected_tables is not None


class TestConfidenceReportTuples:
    """Kill mutations in ConfidenceReport empty tuples."""

    def test_confidence_report_uncertainty_markers_empty(self) -> None:
        """uncertainty_markers must be empty tuple."""
        cr = _confidence_report()
        assert cr.uncertainty_markers == ()

    def test_confidence_report_risky_fields_empty(self) -> None:
        """risky_fields must be empty tuple."""
        cr = _confidence_report()
        assert cr.risky_fields == ()

    def test_confidence_report_has_confidence_scores(self) -> None:
        """confidence_scores must not be empty."""
        cr = _confidence_report()
        assert len(cr.confidence_scores) == 1


class TestEvidenceMutateGuard:
    """Kill mutations in _mutate early return (line 198)."""

    def test_mutate_attempts_to_assign_field(self) -> None:
        """_mutate must use next(iter()) to find a field to set.

        The function is designed to prove that frozen fields are enforced,
        so it will raise ValidationError.
        """
        deo = _detected_field()
        # _mutate uses next(iter()) to get the first field
        # If next(iter()) was removed or changed, this would fail differently
        with pytest.raises(ValidationError):
            _mutate(deo)

    def test_mutate_gets_frozen_field_exception(self) -> None:
        """_mutate raises ValidationError when trying to set a frozen field."""
        deo = _detected_field()
        # This proves that the field is actually frozen
        with pytest.raises(ValidationError) as exc_info:
            _mutate(deo)
        # The error should be about frozen instances
        assert "frozen" in str(exc_info.value).lower()


class TestEvidenceHasAllRequiredFields:
    """Kill mutations in _evidence builder completeness."""

    def test_evidence_has_identity(self) -> None:
        """evidence must have identity."""
        deo = _evidence()
        assert deo.identity is not None

    def test_evidence_has_document_id(self) -> None:
        """evidence must have document_id."""
        deo = _evidence()
        assert deo.document_id is not None

    def test_evidence_has_source_references(self) -> None:
        """evidence must have source_references tuple."""
        deo = _evidence()
        assert deo.source_references is not None
        assert len(deo.source_references) > 0

    def test_evidence_has_structured_document(self) -> None:
        """evidence must have structured_document."""
        deo = _evidence()
        assert deo.structured_document is not None

    def test_evidence_has_confidence_report(self) -> None:
        """evidence must have confidence_report."""
        deo = _evidence()
        assert deo.confidence_report is not None

    def test_evidence_human_context_is_none(self) -> None:
        """human_business_context is explicitly None in clean payload."""
        deo = _evidence()
        assert deo.human_business_context is None
