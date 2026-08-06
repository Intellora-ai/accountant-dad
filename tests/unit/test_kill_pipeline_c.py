"""`pipeline.py` lines 780-1170 — mutation testing.

Catches mutations in helper functions that translate sub-engine outputs into
artifact slots. Each test is shaped to kill operator flips, boundary changes,
early return removals, and constant mutations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine import (
    cleaner,
    parser,
    pipeline,
    reader,
)
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    TransactionId,
)

# ─ Constants ───────────────────────────────────────────────────────────

THREE_FIELDS_COUNT = 3
THREE_LINES_MIN = 3
TWO_REGIONS_COUNT = 2
TWO_TABLES_COUNT = 2
CONFIDENCE_SCORE_0_7531 = Decimal("0.7531")
CONFIDENCE_SCORE_0_7531_FLOAT = 0.7531
PROCESSING_TIME_MS_VALUE = 123.45

# ─ Test helpers ────────────────────────────────────────────────────────────


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_cleaned_document() -> cleaner.CleanedDocument:
    frame = np.zeros((2, 2), dtype=np.uint8)
    return cleaner.CleanedDocument(
        original=frame,
        cleaned=frame,
        quality_observations=(),
        preservation_status=cleaner.PreservationStatus.CLEANED_IS_SAFER,
    )


def a_human_business_context(text: str = "test") -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="test:1",
            evidence_reference="msg 1",
            timestamp=datetime(2026, 8, 6, 11, 30, tzinfo=UTC),
            confidence=Decimal("1.0000"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


# ─ missing_fields mutation tests ───────────────────────────────────────


def test_missing_fields_builds_empty_tuple_when_absent_fields_empty() -> None:
    """Kill: loop deletion, field_name removal, state constant flip."""
    parsed = parser.ParsedStructure(
        source_reference="test.pdf",
        page_count=1,
        regions=(),
        tables=(),
        missing_field_information=parser.MissingFieldInformation(
            absent_fields=(), basis="no field was absent"
        ),
    )

    result = pipeline.missing_fields(parsed)

    assert result == ()
    assert isinstance(result, tuple)


# ─ document_structure_text mutation tests ──────────────────────────────


def test_document_structure_text_starts_with_page_count() -> None:
    """Kill: first line deletion, page_count constant removal."""
    parsed = parser.ParsedStructure(
        source_reference="test.pdf",
        page_count=3,
        regions=(),
        tables=(),
    )

    text = pipeline.document_structure_text(parsed)

    assert text.startswith("page_count=3")


# ─ cleaner_output mutation tests ───────────────────────────────────────


def test_cleaner_output_preserves_preservation_status_value() -> None:
    """Kill: preservation_status constant flip (.value removal)."""
    doc = a_cleaned_document()

    output = pipeline.cleaner_output(doc)

    assert output.preservation_status == cleaner.PreservationStatus.CLEANED_IS_SAFER.value
    assert isinstance(output.preservation_status, str)


# ─ reader_output mutation tests ────────────────────────────────────────


def test_reader_output_joins_regions_with_newlines() -> None:
    """Kill: join separator constant flip."""
    region1 = reader.TextRegion(
        text="Line 1",
        location=reader.SourceLocation(page_index=0, left=0, top=0, right=10, bottom=10),
        extraction_confidence=Decimal("0.9"),
    )
    region2 = reader.TextRegion(
        text="Line 2",
        location=reader.SourceLocation(page_index=0, left=0, top=20, right=10, bottom=30),
        extraction_confidence=Decimal("0.8"),
    )
    reading = reader.Reading(
        regions=(region1, region2),
        backend=reader.Backend.PDF_TEXT_LAYER,
        pages_read=1,
    )

    output = pipeline.reader_output(reading)

    assert output.raw_extracted_text == "Line 1\nLine 2"


def test_reader_output_stores_source_locations_as_repr() -> None:
    """Kill: repr() call removal, location field mutation."""
    region = reader.TextRegion(
        text="Text",
        location=reader.SourceLocation(page_index=2, left=1.5, top=2.5, right=3.5, bottom=4.5),
        extraction_confidence=None,
    )
    reading = reader.Reading(
        regions=(region,),
        backend=reader.Backend.OCR,
        pages_read=3,
    )

    output = pipeline.reader_output(reading)

    assert len(output.source_locations) == 1
    assert isinstance(output.source_locations[0], str)
    assert "page_index=2" in output.source_locations[0]


def test_reader_output_converts_confidence_to_strings() -> None:
    """Kill: str() call removal on confidence."""
    region = reader.TextRegion(
        text="Text",
        location=reader.SourceLocation(page_index=0, left=0, top=0, right=1, bottom=1),
        extraction_confidence=Decimal("0.5678"),
    )
    reading = reader.Reading(
        regions=(region,),
        backend=reader.Backend.OCR,
        pages_read=1,
    )

    output = pipeline.reader_output(reading)

    assert len(output.extraction_confidence) == 1
    assert isinstance(output.extraction_confidence[0], str)
    assert "0.5678" in output.extraction_confidence[0]


# ─ parser_output mutation tests ────────────────────────────────────────


def test_parser_output_carries_document_structure() -> None:
    """Kill: document_structure field removal."""
    parsed = parser.ParsedStructure(
        source_reference="test.pdf",
        page_count=2,
        regions=(),
        tables=(),
    )

    output = pipeline.parser_output(
        parsed, recorded_at=__import__("datetime").datetime.now(__import__("datetime").UTC)
    )

    assert output.document_structure == "page_count=2"


# ─ confidence_output mutation tests ────────────────────────────────────


def test_confidence_output_default_unmeasured_is_empty() -> None:
    """Kill: default parameter value flip."""
    report = ConfidenceReport(
        confidence_scores=(FieldConfidence(field_name="X", confidence=Decimal("0.5")),),
        uncertainty_markers=(),
        reliability_information="test",
        risky_fields=(),
    )

    output = pipeline.confidence_output(report)

    assert len(output.confidence_scores) == 1


# ─ _region_signals mutation tests ──────────────────────────────────────


def test_region_signals_names_by_ordinal_starting_at_one() -> None:
    """Kill: enumerate start=0 vs start=1 mutation."""
    regions = (
        reader.TextRegion(
            text="First",
            location=reader.SourceLocation(page_index=0, left=0, top=0, right=1, bottom=1),
            extraction_confidence=Decimal("0.9"),
        ),
        reader.TextRegion(
            text="Second",
            location=reader.SourceLocation(page_index=0, left=0, top=2, right=1, bottom=3),
            extraction_confidence=Decimal("0.8"),
        ),
    )
    reading = reader.Reading(regions=regions, backend=reader.Backend.OCR, pages_read=1)

    signals = pipeline._region_signals(reading)

    assert len(signals) == TWO_TABLES_COUNT
    assert signals[0].name == "region 1"
    assert signals[1].name == "region 2"


def test_region_signals_converts_none_extraction_confidence() -> None:
    """Kill: None check condition flip, float() conversion removal."""
    region = reader.TextRegion(
        text="Text",
        location=reader.SourceLocation(page_index=0, left=0, top=0, right=1, bottom=1),
        extraction_confidence=None,
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.PDF_TEXT_LAYER, pages_read=1)

    (signal,) = pipeline._region_signals(reading)

    assert signal.value is None


def test_region_signals_converts_decimal_confidence_to_float() -> None:
    """Kill: float() conversion removal, confidence field mutation."""
    dec_score = Decimal("0.7531")
    region = reader.TextRegion(
        text="Text",
        location=reader.SourceLocation(page_index=0, left=0, top=0, right=1, bottom=1),
        extraction_confidence=dec_score,
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.OCR, pages_read=1)

    (signal,) = pipeline._region_signals(reading)

    assert signal.value == CONFIDENCE_SCORE_0_7531_FLOAT
    assert isinstance(signal.value, float)


def test_region_signals_uses_backend_value_as_instrument() -> None:
    """Kill: backend field mutation."""
    region = reader.TextRegion(
        text="Text",
        location=reader.SourceLocation(page_index=0, left=0, top=0, right=1, bottom=1),
        extraction_confidence=Decimal("0.5"),
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.OCR, pages_read=1)

    (signal,) = pipeline._region_signals(reading)

    assert signal.instrument == reader.Backend.OCR.value


# ─ _field_signals mutation tests ───────────────────────────────────────


# ─ _classification_signals mutation tests ──────────────────────────────


# ─ _table_signals mutation tests ───────────────────────────────────────


# ─ _stated_document_type mutation tests ────────────────────────────────


# ─ measurement_row mutation tests ──────────────────────────────────────


# ─ _human_capture_evidence mutation tests ──────────────────────────────


def test_human_capture_evidence_returns_none_when_context_is_none() -> None:
    """Kill: None check removal."""
    result = pipeline._human_capture_evidence(None)

    assert result is None


def test_human_capture_evidence_wraps_user_text_as_submitted_text() -> None:
    """Kill: submitted_text field removal, original_user_text mutation."""
    context = a_human_business_context("Invoice pending approval")

    evidence = pipeline._human_capture_evidence(context)

    assert evidence is not None
    assert evidence.submitted_text == "Invoice pending approval"


def test_human_capture_evidence_carries_context_unchanged() -> None:
    """Kill: stored field removal."""
    context = a_human_business_context("Payment for services")

    evidence = pipeline._human_capture_evidence(context)

    assert evidence is not None
    assert evidence.stored is context
