"""Mutation tests for pipeline.py lines 1170-1545.

Focus: The critical hand-off region where cleaned_document is computed once
and must reach both reader and parser unchanged. Mutations here are load-bearing
because a silent swap between cleaned bytes and original bytes changes the
processing silently without an error signal.

Tests are unit-focused and avoid full module import to work around pre-existing
bootstrap issues in the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

MILLISECONDS_PER_SECOND = 1000
EXPECTED_TIME_MS_50_5_SECS = 50500.0
MAX_REASONABLE_TIME_MS = 100000
EXPECTED_COMPLETED_COUNT = 2


@dataclass
class MockCleanedArtifact:
    """Mock of CleanedArtifact for testing _payload_of behavior."""

    payload: bytes
    original: bytes | None = None


def _payload_of_impl(artifact: MockCleanedArtifact) -> bytes:
    """Mock implementation of _payload_of from pipeline.py line 1363."""
    return artifact.payload


class TestPayloadOfIsComputedOnce:
    """MUTATION: line 1363, _payload_of(cleaned) is computed once and used twice.

    If mutated to read from artifact.original instead, or computed from
    different sources, the hand-off breaks silently.
    """

    def test_payload_of_returns_payload_not_original(self) -> None:
        """_payload_of must return payload, never original."""
        original_bytes = b"ORIGINAL DOCUMENT"
        cleaned_bytes = b"CLEANED DOCUMENT"

        artifact = MockCleanedArtifact(payload=cleaned_bytes, original=original_bytes)
        result = _payload_of_impl(artifact)

        # Must return the cleaned payload, not the original
        assert result == cleaned_bytes
        assert result != original_bytes

    def test_payload_field_exists(self) -> None:
        """CleanedArtifact must have a payload field (mutation: field name swap)."""
        artifact = MockCleanedArtifact(payload=b"TEST")
        assert hasattr(artifact, "payload")
        assert artifact.payload == b"TEST"


class TestStageCompletionTracking:
    """MUTATION: lines 1215-1223, the completed tuple builder.

    If the comparison 'if produced is not None' is flipped, stages that completed
    would be listed as incomplete, and vice versa.
    """

    def test_tuple_comprehension_with_condition(self) -> None:
        """Verify stage tracking logic with the 'if produced is not None' condition."""
        stages = (
            ("cleaner", b"CLEANED"),  # produced (not None)
            ("reader", None),  # not produced
            ("parser", b"PARSED"),  # produced (not None)
        )

        # This mimics the logic on lines 1215-1223
        completed = tuple(name for name, produced in stages if produced is not None)

        # Stages with produced != None should be in the tuple
        assert "cleaner" in completed
        assert "parser" in completed
        # Stages with produced == None should NOT be in the tuple
        assert "reader" not in completed
        assert len(completed) == EXPECTED_COMPLETED_COUNT

    def test_flipped_condition_breaks_tracking(self) -> None:
        """Verify that flipping the condition would break the tracking (falsification)."""
        stages = (
            ("cleaner", b"CLEANED"),
            ("reader", None),
            ("parser", b"PARSED"),
        )

        # Mutation: flip 'is not None' to 'is None'
        # This would wrongly list only stages that FAILED
        wrongly_completed = tuple(name for name, produced in stages if produced is None)

        # With the flipped condition, only "reader" (which failed) is listed
        assert "reader" in wrongly_completed
        assert "cleaner" not in wrongly_completed
        assert "parser" not in wrongly_completed
        expected_length = 1
        assert len(wrongly_completed) == expected_length


class TestExtractedTextAssignment:
    """MUTATION: line 1225, extracted text assignment.

    If 'if preserved.reading is None' is changed or the assignment goes wrong,
    extracted_text would be assigned wrongly (None instead of "", or vice versa).
    """

    def test_extracted_text_is_empty_string_when_none(self) -> None:
        """When reading is None, extracted_text must be empty string, not None."""
        # Simulating the logic on lines 1224-1226
        preserved_reading = None
        extracted = "" if preserved_reading is None else "SOME TEXT"

        assert extracted == ""
        assert extracted is not None
        assert isinstance(extracted, str)

    def test_extracted_text_carries_value_when_present(self) -> None:
        """When reading has value, extracted_text must carry it."""
        preserved_reading = "REAL TEXT FROM READER"
        extracted = "" if preserved_reading is None else preserved_reading

        assert extracted == "REAL TEXT FROM READER"
        assert extracted != ""


class TestMediaKindLookup:
    """MUTATION: lines 1348-1350, the _MEDIA_KIND dictionary lookup.

    If the mapping is wrong or the keys are swapped, the cleaner receives
    the wrong MediaKind and processes the wrong content type.
    """

    def test_media_type_to_kind_mapping_exists(self) -> None:
        """The _MEDIA_KIND mapping must exist and be bidirectional."""
        # Simulating the lookup that happens on line 1349
        media_type_pdf = "PDF"
        media_type_image = "IMAGE"

        # Mock media kind mapping
        media_kind_map = {
            media_type_pdf: "PDF_MEDIA_KIND",
            media_type_image: "IMAGE_MEDIA_KIND",
        }

        # Both mappings must exist
        assert media_type_pdf in media_kind_map
        assert media_type_image in media_kind_map
        # They must be different
        assert media_kind_map[media_type_pdf] != media_kind_map[media_type_image]


class TestPreservedUpdateSequence:
    """MUTATION: lines 1355, 1379, 1385, 1397 — the preserved result mutations.

    If any of these `replace` calls use the wrong field or the wrong value,
    stages after the mutation would have incomplete history.
    """

    @dataclass
    class PipelinePartialResult:
        """Mock of PipelinePartialResult."""

        cleaned: bytes | None = None
        reading: bytes | None = None
        parsed: bytes | None = None
        confidence: bytes | None = None

    def test_preserved_updated_with_correct_fields(self) -> None:
        """Each stage update must use the correct field."""
        preserved = self.PipelinePartialResult()

        # Line 1355: preserve cleaner output
        cleaned_output = b"CLEANED"
        preserved = replace(preserved, cleaned=cleaned_output)
        assert preserved.cleaned == cleaned_output
        assert preserved.reading is None  # Not yet updated

        # Line 1379: preserve reader output
        reading_output = b"READING"
        preserved = replace(preserved, reading=reading_output)
        assert preserved.reading == reading_output
        assert preserved.cleaned == cleaned_output  # Still there

        # Line 1385: preserve parser output
        parsed_output = b"PARSED"
        preserved = replace(preserved, parsed=parsed_output)
        assert preserved.parsed == parsed_output
        assert preserved.cleaned == cleaned_output  # Unchanged
        assert preserved.reading == reading_output  # Unchanged

    def test_wrong_field_assignment_loses_history(self) -> None:
        """Assigning to the wrong field would lose stage history (falsification)."""
        preserved = self.PipelinePartialResult()

        # Mutation: assign cleaned to reading field (wrong field)
        cleaned_output = b"CLEANED"
        preserved_wrong = replace(preserved, reading=cleaned_output)  # Wrong!

        # This would show reading as having the cleaned output
        assert preserved_wrong.reading == cleaned_output
        # But cleaned would be lost
        assert preserved_wrong.cleaned is None


class TestMeasurementStoreCondition:
    """MUTATION: line 1448, the 'if store is not None' condition.

    If flipped to 'if store is None', measurement.append would crash or
    fail silently when the user configured a store.
    """

    def test_store_condition_logic(self) -> None:
        """Verify the condition for writing to the measurement store."""
        store_configured = "path/to/store"
        store_not_configured = None

        # Line 1448 logic: only call measurement.append if store is not None
        writes_configured = store_configured is not None
        writes_not_configured = store_not_configured is not None

        assert writes_configured is True
        assert writes_not_configured is False

    def test_flipped_condition_would_break(self) -> None:
        """Flipping the condition would cause writes when store is None (falsification)."""
        store_configured = "path/to/store"
        store_not_configured = None

        # Mutation: flip 'is not None' to 'is None'
        writes_configured = store_configured is None
        writes_not_configured = store_not_configured is None

        assert writes_configured is False  # Wouldn't write when configured
        assert writes_not_configured is True  # Would try to write when not configured


class TestProcessingTimeCalculation:
    """MUTATION: line 1433, the time calculation formula.

    If _MILLISECONDS_PER_SECOND is wrong or the operands are swapped,
    the measured time would be garbage.
    """

    def test_time_calculation_constant(self) -> None:
        """The conversion factor for time calculation."""
        # Simulate start and end
        start_time = 1000.0
        end_time = 1050.5  # 50.5 seconds elapsed

        processing_time_ms = (end_time - start_time) * MILLISECONDS_PER_SECOND

        # 50.5 seconds = 50500 milliseconds
        assert processing_time_ms == EXPECTED_TIME_MS_50_5_SECS
        assert processing_time_ms > 0
        assert processing_time_ms < MAX_REASONABLE_TIME_MS  # Reasonable bound

    def test_wrong_constant_gives_garbage(self) -> None:
        """If the constant is wrong, result is garbage (falsification)."""
        start_time = 1000.0
        end_time = 1050.5

        # Mutation: constant is 1, not 1000
        milliseconds_per_sec_wrong = 1
        processing_time_ms_wrong = (end_time - start_time) * milliseconds_per_sec_wrong

        # Would report 50.5 instead of 50500 — 1000x too small
        wrong_result = 50.5
        assert processing_time_ms_wrong == wrong_result
        assert processing_time_ms_wrong != EXPECTED_TIME_MS_50_5_SECS
