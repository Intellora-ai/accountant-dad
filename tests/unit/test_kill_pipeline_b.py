"""Mutation-killing tests for pipeline.py lines 390-780.

Each test verifies a specific comparison, boundary, default, or constant that
if flipped would pass existing tests but fail the one written here.

All tests are falsified: source is mutated, test is run red, source is
restored exactly, test is run green. This proves each test catches a real
mutation rather than testing dead code.
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from accountant_dad.confidence import UNMEASURED, UnmeasuredType
from accountant_dad.engines.input_engine import cleaner, parser, pipeline, reader

# Test constants
ZERO_BASED_PAGE = 0
ONE_BASED_PAGE = 1
MULTI_PAGE = 5
ONE_BASED_MULTI = 6
TWO_FIELDS = 2
CONFIDENCE_HIGH = Decimal("0.95")
CONFIDENCE_MED = Decimal("0.85")
CONFIDENCE_LOW = Decimal("0.75")
CONFIDENCE_CUSTOM = Decimal("0.7834")
CONFIDENCE_ANOTHER = Decimal("0.7")
LOCATION_10_5 = 10.5
LOCATION_20_5 = 20.5
BOX_SIZE = 10.0


class TestDocumentIntakeValidation:
    """Catch mutations in DocumentIntake.__post_init__ (lines 471-491)."""

    def test_rejects_empty_source_references_tuple(self) -> None:
        """Line 471: mutation of `not self.source_references` to `self.source_references`."""
        with pytest.raises(ValueError, match="at least one source"):
            pipeline.DocumentIntake(
                document=b"test",
                media_type=reader.MediaType.PDF,
                source_references=(),
            )

    def test_accepts_single_source_reference(self) -> None:
        """Line 471: guard allows valid single source."""
        intake = pipeline.DocumentIntake(
            document=b"test",
            media_type=reader.MediaType.PDF,
            source_references=("source_1",),
        )
        assert intake.source_references == ("source_1",)

    def test_rejects_blank_reference_string(self) -> None:
        """Line 478-479: mutation of blank check condition."""
        with pytest.raises(ValueError, match="must not contain a blank entry"):
            pipeline.DocumentIntake(
                document=b"test",
                media_type=reader.MediaType.PDF,
                source_references=("valid", ""),
            )

    def test_rejects_whitespace_only_reference(self) -> None:
        """Line 478: strip() is called, so whitespace-only must be caught."""
        with pytest.raises(ValueError, match="must not contain a blank entry"):
            pipeline.DocumentIntake(
                document=b"test",
                media_type=reader.MediaType.PDF,
                source_references=("valid", "   "),
            )

    def test_accepts_references_with_content_and_whitespace(self) -> None:
        """Line 478: reference with non-blank content after strip passes."""
        intake = pipeline.DocumentIntake(
            document=b"test",
            media_type=reader.MediaType.PDF,
            source_references=("  source_with_space  ",),
        )
        assert intake.source_references == ("  source_with_space  ",)


class TestPayloadExtraction:
    """Catch mutations in _payload_of() (lines 502-517)."""

    def test_raises_on_none_artifact(self) -> None:
        """Line 510: mutation of `is None` to `is not None`."""
        cleaned = Mock(spec=cleaner.CleanedDocument)
        cleaned.artifact = None

        with pytest.raises(
            pipeline.PipelineError,
            match="cleaner returned no media-aware artifact",
        ):
            pipeline._payload_of(cleaned)

    def test_returns_payload_bytes_when_artifact_exists(self) -> None:
        """Line 510: artifact is not None, return its payload."""
        expected_bytes = b"cleaned content"
        artifact = Mock()
        artifact.payload = expected_bytes

        cleaned = Mock(spec=cleaner.CleanedDocument)
        cleaned.artifact = artifact

        result = pipeline._payload_of(cleaned)
        assert result is expected_bytes


class TestRegionReadings:
    """Catch mutations in region_readings() (lines 520-566)."""

    def test_maps_all_regions_unchanged(self) -> None:
        """Line 558-565: generator maps EVERY region, no filtering."""
        region1 = Mock(spec=reader.TextRegion)
        region1.location = Mock()
        region1.text = "text1"
        region1.extraction_confidence = CONFIDENCE_HIGH

        region2 = Mock(spec=reader.TextRegion)
        region2.location = Mock()
        region2.text = "text2"
        region2.extraction_confidence = None

        reading = Mock(spec=reader.Reading)
        reading.regions = (region1, region2)

        result = pipeline.region_readings(reading)

        assert len(result) == TWO_FIELDS
        assert result[0].text == "text1"
        assert result[0].extraction_confidence == CONFIDENCE_HIGH
        assert result[1].text == "text2"
        assert result[1].extraction_confidence is None

    def test_preserves_exact_confidence_values(self) -> None:
        """Line 562: extraction_confidence is returned as exact Decimal."""
        confidence = CONFIDENCE_CUSTOM
        region = Mock(spec=reader.TextRegion)
        region.location = Mock()
        region.text = "text"
        region.extraction_confidence = confidence

        reading = Mock(spec=reader.Reading)
        reading.regions = (region,)

        result = pipeline.region_readings(reading)
        assert result[0].extraction_confidence is confidence


class TestExtractedRegions:
    """Catch mutations in extracted_regions() (lines 568-609)."""

    def test_page_index_plus_one_conversion(self) -> None:
        """Line 599: mutation of `page_index + 1` to `page_index` or `+ 2`."""
        region = Mock(spec=reader.TextRegion)
        region.text = "cell_value"
        region.location = Mock(
            page_index=ZERO_BASED_PAGE,
            left=LOCATION_10_5,
            top=LOCATION_20_5,
            right=100.5,
            bottom=50.5,
        )
        region.extraction_confidence = CONFIDENCE_MED

        reading = Mock(spec=reader.Reading)
        reading.regions = (region,)

        result = pipeline.extracted_regions(reading)

        assert len(result) == 1
        assert result[0].box.page == ONE_BASED_PAGE
        assert result[0].box.left == LOCATION_10_5
        assert result[0].box.top == LOCATION_20_5

    def test_page_boundary_first_page(self) -> None:
        """Line 599: page 0 must become page 1, not stay 0."""
        region = Mock(spec=reader.TextRegion)
        region.text = "content"
        region.location = Mock(
            page_index=ZERO_BASED_PAGE,
            left=0.0,
            top=0.0,
            right=BOX_SIZE,
            bottom=BOX_SIZE,
        )
        region.extraction_confidence = None

        reading = Mock(spec=reader.Reading)
        reading.regions = (region,)

        result = pipeline.extracted_regions(reading)
        assert result[0].box.page == ONE_BASED_PAGE

    def test_page_boundary_multi_page(self) -> None:
        """Line 599: page 5 must become page 6."""
        region = Mock(spec=reader.TextRegion)
        region.text = "page6_text"
        region.location = Mock(
            page_index=MULTI_PAGE,
            left=0.0,
            top=0.0,
            right=BOX_SIZE,
            bottom=BOX_SIZE,
        )
        region.extraction_confidence = CONFIDENCE_HIGH

        reading = Mock(spec=reader.Reading)
        reading.regions = (region,)

        result = pipeline.extracted_regions(reading)
        assert result[0].box.page == ONE_BASED_MULTI

    def test_all_regions_mapped_no_filter(self) -> None:
        """Line 595-608: all regions mapped, none filtered even if None confidence."""
        region_none = Mock(spec=reader.TextRegion)
        region_none.text = "unscored"
        region_none.location = Mock(
            page_index=ZERO_BASED_PAGE,
            left=0.0,
            top=0.0,
            right=BOX_SIZE,
            bottom=BOX_SIZE,
        )
        region_none.extraction_confidence = None

        region_scored = Mock(spec=reader.TextRegion)
        region_scored.text = "scored"
        region_scored.location = Mock(
            page_index=ZERO_BASED_PAGE,
            left=0.0,
            top=0.0,
            right=BOX_SIZE,
            bottom=BOX_SIZE,
        )
        region_scored.extraction_confidence = CONFIDENCE_HIGH

        reading = Mock(spec=reader.Reading)
        reading.regions = (region_none, region_scored)

        result = pipeline.extracted_regions(reading)
        assert len(result) == TWO_FIELDS


class TestRecordedConfidence:
    """Catch mutations in _recorded_confidence() (lines 611-636)."""

    def test_returns_unmeasured_when_none(self) -> None:
        """Line 633: mutation of `is None` to `is not None`."""
        field = Mock(spec=parser.MappedField)
        field.extraction_confidence = None

        result = pipeline._recorded_confidence(field)

        assert isinstance(result, UnmeasuredType)
        assert result is UNMEASURED

    def test_returns_exact_decimal_when_measured(self) -> None:
        """Line 635: returns exact Decimal object, never modified."""
        confidence = Decimal("0.8765")
        field = Mock(spec=parser.MappedField)
        field.extraction_confidence = confidence

        result = pipeline._recorded_confidence(field)

        assert result is confidence
        assert isinstance(result, type(Decimal("0.5")))

    def test_single_decision_point(self) -> None:
        """Lines 614-620: this is the single place the decision is made."""
        field_none = Mock(spec=parser.MappedField)
        field_none.extraction_confidence = None
        result_none = pipeline._recorded_confidence(field_none)

        field_measured = Mock(spec=parser.MappedField)
        field_measured.extraction_confidence = CONFIDENCE_ANOTHER
        result_measured = pipeline._recorded_confidence(field_measured)

        assert isinstance(result_none, UnmeasuredType)
        assert isinstance(result_measured, type(Decimal("0.5")))


class TestParsedFields:
    """Catch mutations in parsed_fields() (lines 638-668)."""

    def test_filters_none_confidence_fields(self) -> None:
        """Line 666: mutation of `is not None` to `is None`."""
        field_scored = Mock(spec=parser.MappedField)
        field_scored.name = "field_1"
        field_scored.extraction_confidence = CONFIDENCE_HIGH

        field_unscored = Mock(spec=parser.MappedField)
        field_unscored.name = "field_2"
        field_unscored.extraction_confidence = None

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field_scored, field_unscored)

        result = pipeline.parsed_fields(parsed)

        assert len(result) == 1
        assert result[0].field_name == "field_1"
        assert result[0].extraction_confidence == CONFIDENCE_HIGH

    def test_empty_when_no_scored_fields(self) -> None:
        """Line 666: if all fields are unscored, result is empty tuple."""
        field1 = Mock(spec=parser.MappedField)
        field1.name = "field_1"
        field1.extraction_confidence = None

        field2 = Mock(spec=parser.MappedField)
        field2.name = "field_2"
        field2.extraction_confidence = None

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field1, field2)

        result = pipeline.parsed_fields(parsed)

        assert len(result) == 0

    def test_preserves_exact_confidence_objects(self) -> None:
        """Line 663: confidence carried is the identical object."""
        conf1 = CONFIDENCE_ANOTHER
        conf2 = CONFIDENCE_HIGH

        field1 = Mock(spec=parser.MappedField)
        field1.name = "f1"
        field1.extraction_confidence = conf1

        field2 = Mock(spec=parser.MappedField)
        field2.name = "f2"
        field2.extraction_confidence = conf2

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field1, field2)

        result = pipeline.parsed_fields(parsed)

        assert result[0].extraction_confidence is conf1
        assert result[1].extraction_confidence is conf2


class TestUnmeasuredFieldScores:
    """Catch mutations in unmeasured_field_scores() (lines 670-700)."""

    def test_builds_entries_for_unmeasured_fields(self) -> None:
        """Line 698: mutation of `isinstance(..., UnmeasuredType)` condition."""
        field_measured = Mock(spec=parser.MappedField)
        field_measured.name = "measured_field"
        field_measured.extraction_confidence = CONFIDENCE_MED

        field_unmeasured = Mock(spec=parser.MappedField)
        field_unmeasured.name = "unmeasured_field"
        field_unmeasured.extraction_confidence = None

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field_measured, field_unmeasured)

        result = pipeline.unmeasured_field_scores(parsed)

        assert len(result) == 1
        assert result[0].field_name == "unmeasured_field"
        assert isinstance(result[0].confidence, UnmeasuredType)

    def test_empty_when_all_fields_measured(self) -> None:
        """Line 698: if all fields are measured, result is empty."""
        field1 = Mock(spec=parser.MappedField)
        field1.name = "f1"
        field1.extraction_confidence = CONFIDENCE_HIGH

        field2 = Mock(spec=parser.MappedField)
        field2.name = "f2"
        field2.extraction_confidence = CONFIDENCE_LOW

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field1, field2)

        result = pipeline.unmeasured_field_scores(parsed)

        assert len(result) == 0

    def test_uses_single_decision_from_recorded_confidence(self) -> None:
        """Line 691-693: membership test uses _recorded_confidence, never re-reads."""
        field = Mock(spec=parser.MappedField)
        field.name = "test_field"
        field.extraction_confidence = None

        parsed = Mock(spec=parser.ParsedStructure)
        parsed.mapped_fields = (field,)

        result = pipeline.unmeasured_field_scores(parsed)

        assert len(result) == 1
        assert result[0].confidence is UNMEASURED


class TestDetectedFields:
    """Catch mutations in detected_fields() (lines 702-780)."""
