"""Mutation killers for `pipeline` module constants and error classes.

Every test below targets a specific mutation operator:
  - `_MILLISECONDS_PER_SECOND` constant value (line 309)
  - `_TEMP_FILE_SUFFIX` dict contents (lines 302-305)
  - `BUSINESS_FAILURE` tuple membership (lines 354-359)
  - `PipelineStageError` field assignments (lines 376-379)
  - `PipelineStageError` message format (lines 380-384)

Each test falsifies by confirming the mutation would be caught if applied.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from accountant_dad.engines.input_engine import cleaner, parser, pipeline, reader
from accountant_dad.engines.input_engine.pipeline import (
    PipelineError,
    PipelinePartialResult,
    PipelineStageError,
)
from accountant_dad.pdf_backend import BrokenPdfError

# Constants for mutation tests
_EXPECTED_MILLISECONDS_PER_SECOND = 1000.0
_EXPECTED_TEMP_FILE_SUFFIX_LENGTH = 2
_EXPECTED_BUSINESS_FAILURE_LENGTH = 4


class TestMillisecondsPerSecondConstant:
    """Kill mutations on line 309: `_MILLISECONDS_PER_SECOND = 1000.0`."""

    def test_milliseconds_per_second_is_exactly_1000_point_0(self) -> None:
        """Catch mutations: 1000.1, 999.9, 100, 10, 1, etc."""
        assert pipeline._MILLISECONDS_PER_SECOND == _EXPECTED_MILLISECONDS_PER_SECOND

    def test_milliseconds_per_second_is_float_not_int(self) -> None:
        """Catch mutation: 1000 (int instead of float)."""
        assert isinstance(pipeline._MILLISECONDS_PER_SECOND, float)

    def test_milliseconds_per_second_converts_one_second_correctly(self) -> None:
        """Catch mutations that break the conversion: 1.0 * 1000.0 == 1000.0."""
        one_second_in_ms = 1.0 * pipeline._MILLISECONDS_PER_SECOND
        assert one_second_in_ms == _EXPECTED_MILLISECONDS_PER_SECOND


class TestTempFileSuffixDict:
    """Kill mutations on lines 302-305: `_TEMP_FILE_SUFFIX` dict."""

    def test_temp_file_suffix_has_pdf_key(self) -> None:
        """Catch mutation: missing PDF key."""
        assert reader.MediaType.PDF in pipeline._TEMP_FILE_SUFFIX

    def test_temp_file_suffix_has_image_key(self) -> None:
        """Catch mutation: missing IMAGE key."""
        assert reader.MediaType.IMAGE in pipeline._TEMP_FILE_SUFFIX

    def test_temp_file_suffix_pdf_maps_to_dot_pdf(self) -> None:
        """Catch mutations: .png, .jpg, empty string, .PDF, etc."""
        assert pipeline._TEMP_FILE_SUFFIX[reader.MediaType.PDF] == ".pdf"

    def test_temp_file_suffix_image_maps_to_dot_png(self) -> None:
        """Catch mutations: .pdf, .jpg, empty string, .PNG, etc."""
        assert pipeline._TEMP_FILE_SUFFIX[reader.MediaType.IMAGE] == ".png"

    def test_temp_file_suffix_contains_exactly_two_entries(self) -> None:
        """Catch mutations: extra keys added, keys removed."""
        assert len(pipeline._TEMP_FILE_SUFFIX) == _EXPECTED_TEMP_FILE_SUFFIX_LENGTH


class TestBusinessFailureTuple:
    """Kill mutations on lines 354-359: `BUSINESS_FAILURE` tuple."""

    def test_business_failure_contains_unusable_artifact_error(self) -> None:
        """Catch mutation: removing cleaner.UnusableArtifactError."""
        assert cleaner.UnusableArtifactError in pipeline.BUSINESS_FAILURE

    def test_business_failure_contains_unreadable_document_error(self) -> None:
        """Catch mutation: removing reader.UnreadableDocumentError."""
        assert reader.UnreadableDocumentError in pipeline.BUSINESS_FAILURE

    def test_business_failure_contains_document_unreadable_error(self) -> None:
        """Catch mutation: removing parser.DocumentUnreadableError."""
        assert parser.DocumentUnreadableError in pipeline.BUSINESS_FAILURE

    def test_business_failure_contains_broken_pdf_error(self) -> None:
        """Catch mutation: removing BrokenPdfError."""
        assert BrokenPdfError in pipeline.BUSINESS_FAILURE

    def test_business_failure_contains_exactly_four_exceptions(self) -> None:
        """Catch mutations: adding extra exceptions, removing any."""
        assert len(pipeline.BUSINESS_FAILURE) == _EXPECTED_BUSINESS_FAILURE_LENGTH

    def test_business_failure_is_tuple_not_list(self) -> None:
        """Catch mutation: changed to list."""
        assert isinstance(pipeline.BUSINESS_FAILURE, tuple)

    def test_business_failure_all_members_are_exception_types(self) -> None:
        """Catch mutations: wrong types substituted."""
        for exc_type in pipeline.BUSINESS_FAILURE:
            assert isinstance(exc_type, type)
            assert issubclass(exc_type, Exception)


class TestPipelineStageErrorInit:
    """Kill mutations on lines 376-384: `PipelineStageError` initialization."""

    def test_pipeline_stage_error_stores_stage_correctly(self) -> None:
        """Catch mutation: stage assigned to wrong field or swapped with cause."""
        partial = PipelinePartialResult()
        cause = ValueError("test")
        error = PipelineStageError("reader", cause, partial)

        assert error.stage == "reader"
        assert error.stage is not None

    def test_pipeline_stage_error_stores_cause_correctly(self) -> None:
        """Catch mutation: cause assigned to wrong field or swapped with stage."""
        partial = PipelinePartialResult()
        cause = ValueError("test error")
        error = PipelineStageError("parser", cause, partial)

        assert error.cause is cause
        assert error.cause is not None

    def test_pipeline_stage_error_stores_preserved_correctly(self) -> None:
        """Catch mutation: preserved assigned to wrong field."""
        partial = PipelinePartialResult()
        cause = ValueError("test")
        error = PipelineStageError("cleaner", cause, partial)

        assert error.preserved is partial

    def test_pipeline_stage_error_message_contains_stage_name(self) -> None:
        """Catch mutation: stage name removed from message format."""
        partial = PipelinePartialResult()
        error = PipelineStageError("confidence", ValueError("fail"), partial)
        message = str(error)

        assert "confidence" in message

    def test_pipeline_stage_error_message_contains_preserved_reference(self) -> None:
        """Catch mutation: 'preserved' removed from message."""
        partial = PipelinePartialResult()
        error = PipelineStageError("reader", ValueError("fail"), partial)
        message = str(error)

        assert "preserved" in message

    def test_pipeline_stage_error_is_pipeline_error(self) -> None:
        """Catch mutation: inheritance changed."""
        partial = PipelinePartialResult()
        error = PipelineStageError("test", ValueError(), partial)

        assert isinstance(error, PipelineError)
        assert isinstance(error, RuntimeError)


class TestPipelineErrorBase:
    """Kill mutations on line 362: `PipelineError` definition."""

    def test_pipeline_error_is_runtime_error(self) -> None:
        """Catch mutation: base class changed to Exception or other."""
        error = PipelineError("test")
        assert isinstance(error, RuntimeError)

    def test_pipeline_error_can_be_raised(self) -> None:
        """Catch mutation: made non-raisable or abstract."""
        with pytest.raises(PipelineError):
            raise PipelineError("test error")


class TestPipelinePartialResult:
    """Kill mutations on line 389: `PipelinePartialResult` dataclass."""

    def test_pipeline_partial_result_is_frozen(self) -> None:
        """Catch mutation: frozen=False."""
        partial = PipelinePartialResult()

        # Attempting to mutate a frozen dataclass raises FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            partial.cleaned = None  # type: ignore[misc]

    def test_pipeline_partial_result_can_be_instantiated(self) -> None:
        """Catch mutation: constructor made broken."""
        partial = PipelinePartialResult()
        assert partial is not None
        assert partial.cleaned is None
        assert partial.reading is None
        assert partial.parsed is None
        assert partial.confidence is None
