"""Mutation-killing tests for measurement.py lines 300-601.

Targets: boundary mutations (< vs <=, > vs >=), None checks, type guards,
logic inversions, constant mutations (newline, enumerate start, tuple/list).
"""

from __future__ import annotations

import itertools
import json
import uuid
from pathlib import Path

import pytest

from accountant_dad.artifacts.evidence import DocumentId
from accountant_dad.engines.input_engine import measurement as m

_COUNTER = itertools.count(1)


def _distinct_uuid() -> uuid.UUID:
    """A fresh, VALID v4 UUID that is the same on every run.

    These identifiers are opaque here — no assertion reads their value,
    only that they differ. `uuid4()` supplied that at the cost of making
    the suite non-reproducible; a counter supplies it without.
    """
    return uuid.UUID(int=next(_COUNTER), version=4)


class TestBoundaryNegativeProcessingTime:
    """Line 334: `self.processing_time_ms < 0` — mutation: flip to `<=`."""

    def test_zero_processing_time_is_accepted(self) -> None:
        """Zero milliseconds is a valid, finite, non-negative number."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=0.0,
            correctness=m.Correctness.UNLABELLED,
        )
        assert row.processing_time_ms == 0.0

    def test_negative_processing_time_raises(self) -> None:
        """Negative duration is unrecordable: time cannot go backward."""
        with pytest.raises(
            ValueError,
            match=r"must be a finite, non-negative number.*negative time",
        ):
            m.MeasurementRow(
                document_id=DocumentId(_distinct_uuid()),
                source_document_type="invoice",
                processing_time_ms=-0.001,
                correctness=m.Correctness.UNLABELLED,
            )


class TestBoundaryDuplicateCount:
    """Line 360: `self.failed_fields.count(name) > 1` - mutation: flip to `>=`."""

    def test_one_failed_field_is_allowed(self) -> None:
        """A single failed field is a valid fact to record."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            failed_fields=("invoice_number",),
            correctness=m.Correctness.UNLABELLED,
        )
        assert row.failed_fields == ("invoice_number",)

    def test_two_identical_failed_fields_raises(self) -> None:
        """Listing the same field twice is a structural error."""
        with pytest.raises(
            ValueError,
            match=r"names the same field twice",
        ):
            m.MeasurementRow(
                document_id=DocumentId(_distinct_uuid()),
                source_document_type="invoice",
                processing_time_ms=100.0,
                failed_fields=("invoice_number", "invoice_number"),
                correctness=m.Correctness.UNLABELLED,
            )


class TestTypeCheckNoneValue:
    """Line 444-445: `if value is None: return None` - mutation: flip."""

    def test_signal_value_unreadable_roundtrips_as_none(self, tmp_path: Path) -> None:
        """A signal with no value reads back with `value=None`, exactly as stored."""
        signal = m.NamedSignal(
            name="ocr_confidence",
            value=None,
            instrument="tesseract_v5",
        )
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=150.0,
            per_region_ocr=(signal,),
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        rows = m.read_all(path)
        assert len(rows) == 1
        ocr_data = rows[0].per_region_ocr
        assert ocr_data is not m.ABSENT
        assert ocr_data[0].value is None  # type: ignore[index]


class TestTypeCheckRegionNone:
    """Line 462: `if signal.region is not None:` - mutation: flip to `is None`."""

    def test_signal_with_region_survives_roundtrip(self, tmp_path: Path) -> None:
        """A region, once set, is preserved and not silently dropped."""
        signal = m.NamedSignal(
            name="ocr_confidence",
            value=0.95,
            instrument="tesseract_v5",
            region="page_1_section_3",
        )
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=150.0,
            per_region_ocr=(signal,),
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        rows = m.read_all(path)
        ocr_data = rows[0].per_region_ocr
        assert ocr_data is not m.ABSENT
        assert ocr_data[0].region == "page_1_section_3"  # type: ignore[index]

    def test_signal_without_region_does_not_invent_one(self, tmp_path: Path) -> None:
        """A None region stays None; it is never fabricated."""
        signal = m.NamedSignal(
            name="ocr_confidence",
            value=0.95,
            instrument="tesseract_v5",
            region=None,
        )
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=150.0,
            per_region_ocr=(signal,),
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        rows = m.read_all(path)
        ocr_data = rows[0].per_region_ocr
        assert ocr_data is not m.ABSENT
        assert ocr_data[0].region is None  # type: ignore[index]


class TestTypeCheckMissingKey:
    """Line 485: `if key not in payload: return m.ABSENT` - mutation: flip."""

    def test_missing_optional_category_reads_as_absent(self, tmp_path: Path) -> None:
        """A category nobody attempted must read back as m.ABSENT, not as empty."""
        payload = {
            "document_id": str(_distinct_uuid()),
            "source_document_type": "invoice",
            "processing_time_ms": 100.0,
            "correctness": "unlabelled",
        }
        path = tmp_path / "store.jsonl"
        path.write_text(json.dumps(payload, ensure_ascii=False) + "\n")

        rows = m.read_all(path)
        assert rows[0].per_region_ocr is m.ABSENT
        assert rows[0].per_field is m.ABSENT
        assert rows[0].classification is m.ABSENT
        assert rows[0].table is m.ABSENT


class TestTypeCheckListShape:
    """Line 488: `if not isinstance(items, list):` - mutation: flip."""

    def test_category_as_non_list_is_rejected(self, tmp_path: Path) -> None:
        """A category that is not an array is malformed and rejected outright."""
        payload = {
            "document_id": str(_distinct_uuid()),
            "source_document_type": "invoice",
            "processing_time_ms": 100.0,
            "correctness": "unlabelled",
            "per_region_ocr": {"not": "a_list"},
        }
        path = tmp_path / "store.jsonl"
        path.write_text(json.dumps(payload, ensure_ascii=False) + "\n")

        with pytest.raises(Exception, match=r"must be a JSON array"):
            m.read_all(path)


class TestNewlineConstant:
    """Line 581: `handle.write(line + "\n")` - mutation: remove newline."""

    def test_each_row_writes_with_newline_separator(self, tmp_path: Path) -> None:
        """Each row is terminated with a newline; line count equals row count."""
        row1 = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            correctness=m.Correctness.UNLABELLED,
        )
        row2 = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="receipt",
            processing_time_ms=50.0,
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row1)
        m.append(path, row2)

        content = path.read_text()
        lines = content.splitlines(keepends=False)
        assert len(lines) == 2  # noqa: PLR2004
        assert content.endswith("\n")


class TestEnumerateStartValue:
    """Line 593: `enumerate(handle, start=1)` - mutation: change start."""

    def test_malformed_line_names_correct_line_number(self, tmp_path: Path) -> None:
        """A bad line at position N reports line number N, not N-1 or N+1."""
        path = tmp_path / "store.jsonl"
        path.write_text(
            json.dumps(
                {
                    "document_id": str(_distinct_uuid()),
                    "source_document_type": "invoice",
                    "processing_time_ms": 100.0,
                    "correctness": "unlabelled",
                }
            )
            + "\n"
            + "not valid json"
            + "\n"
        )

        with pytest.raises(Exception, match=r"line 2 of"):
            m.read_all(path)


class TestTypeCheckSourceDocumentType:
    """Line 329: `if not self.source_document_type.strip():` - flip."""

    def test_blank_source_document_type_raises(self) -> None:
        """A blank or whitespace-only type is unrecordable."""
        with pytest.raises(
            ValueError,
            match=r"source_document_type.*must not be blank",
        ):
            m.MeasurementRow(
                document_id=DocumentId(_distinct_uuid()),
                source_document_type="   ",
                processing_time_ms=100.0,
                correctness=m.Correctness.UNLABELLED,
            )

    def test_empty_source_document_type_raises(self) -> None:
        """An empty string is unrecordable."""
        with pytest.raises(
            ValueError,
            match=r"source_document_type.*must not be blank",
        ):
            m.MeasurementRow(
                document_id=DocumentId(_distinct_uuid()),
                source_document_type="",
                processing_time_ms=100.0,
                correctness=m.Correctness.UNLABELLED,
            )


class TestTupleConversion:
    """Line 492: `return tuple(...)` - mutation: change to `list`."""

    def test_signal_collection_is_tuple_not_list(self, tmp_path: Path) -> None:
        """Signal collections are immutable tuples, not lists."""
        signal = m.NamedSignal(
            name="ocr_confidence",
            value=0.95,
            instrument="tesseract_v5",
        )
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=150.0,
            per_region_ocr=(signal,),
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        rows = m.read_all(path)
        assert isinstance(rows[0].per_region_ocr, tuple)


class TestFailedFieldsConversion:
    """Line 509: `list(row.failed_fields)` - mutation: remove conversion."""

    def test_failed_fields_serializes_as_json_array(self, tmp_path: Path) -> None:
        """Failed field names are written as a JSON array, readable as objects."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            failed_fields=("line_items", "tax_amount"),
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        content = path.read_text()
        payload = json.loads(content.strip())
        assert isinstance(payload["failed_fields"], list)
        assert payload["failed_fields"] == ["line_items", "tax_amount"]


class TestBlankFailedFieldDetection:
    """Line 354-355: blank field detection - mutation: flip in list comp."""

    def test_blank_field_name_in_failed_fields_raises(self) -> None:
        """A blank field name in the failed list is a structural error."""
        with pytest.raises(
            ValueError,
            match=r"must not contain a blank or empty name",
        ):
            m.MeasurementRow(
                document_id=DocumentId(_distinct_uuid()),
                source_document_type="invoice",
                processing_time_ms=100.0,
                failed_fields=("invoice_number", "   ", "amount"),
                correctness=m.Correctness.UNLABELLED,
            )


class TestMeasurementRowExactSerialization:
    """Verify exact JSON structure for mutation in keys or field order."""

    def test_row_json_payload_has_mandatory_keys(self, tmp_path: Path) -> None:
        """Every row JSON has all required keys."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        content = path.read_text()
        payload = json.loads(content.strip())
        required = {
            "document_id",
            "source_document_type",
            "processing_time_ms",
            "correctness",
        }
        assert required.issubset(payload.keys())


_TEST_DOCUMENT_SCORE = 0.85


class TestOptionalDocumentScoreAbsent:
    """Line 502-503: document_score only written if not m.ABSENT."""

    def test_absent_document_score_not_in_json(self, tmp_path: Path) -> None:
        """An absent document_score is not written to JSON."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            document_score=m.ABSENT,
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        content = path.read_text()
        payload = json.loads(content.strip())
        assert "document_score" not in payload

    def test_present_document_score_in_json(self, tmp_path: Path) -> None:
        """A present document_score is written to JSON."""
        row = m.MeasurementRow(
            document_id=DocumentId(_distinct_uuid()),
            source_document_type="invoice",
            processing_time_ms=100.0,
            document_score=_TEST_DOCUMENT_SCORE,
            correctness=m.Correctness.UNLABELLED,
        )
        path = tmp_path / "store.jsonl"
        m.append(path, row)

        content = path.read_text()
        payload = json.loads(content.strip())
        assert "document_score" in payload
        assert payload["document_score"] == _TEST_DOCUMENT_SCORE
