"""`measurement` — tests written to catch a fabricated or collapsed signal.

`measurement.py` exists to make step 2 of `ENGINE_1_CONFIDENCE_PARAMETERS.md`'s
only calibration route honest: every document records its raw signals, and
none of them is ever silently promoted into something it is not. The tests
below are organised around the specific collapses Law 24 forbids, because a
test that only confirms "a row went in and came back out" would miss every one
of them:

  ABSENT, ZERO AND UNREADABLE MUST NOT BLUR INTO EACH OTHER.
      A category nobody attempted, a category attempted and found empty, and
      a named signal attempted and unreadable are three different facts. A
      round trip that quietly turned one into another would be exactly the
      manufactured ceiling the module's own docstring warns against.

  UNLABELLED MUST NEVER READ BACK AS CORRECT.
      `Correctness.UNLABELLED` is the only label this module may set on its
      own. A default that silently reads as a verdict is the one failure this
      whole record exists to prevent.

  A MALFORMED LINE MUST NAME ITS OWN LINE NUMBER, NOT SOME OTHER LINE'S.
      `tests/unit/...::test_a_malformed_signal_names_the_line_it_is_on` is a
      permanent regression test for a real bug found while auditing this
      module: a malformed *signal* (inside `per_region_ocr`, `per_field`,
      `classification` or `table`) raised `MalformedMeasurementRecordError`
      from `_signal_from_json` without ever being wrapped with the line
      number, while every other malformed shape in the same file already was.
      Before the fix, `read_all` on a two-line file whose SECOND line held the
      bad signal named no line number at all; the message read exactly as it
      would have for a bad signal on line one. A calibration run reading that
      message would not know which of N documents to go fix.

  INSTRUMENT AND REGION ARE THE ONLY RECORD THAT EXISTS OF THEM.
      `FieldConfidence` (`accountant_dad.artifacts.evidence`) has no slot for
      either, so this store is where they live or they do not exist anywhere.
      Losing either on a round trip would be silent data loss the caller has
      no way to detect.

REAL DEPENDENCIES, NO MOCKS (`CLAUDE.md` §J.6). Every test writes to and reads
from a real file under pytest's `tmp_path` - a fresh, disposable directory per
test - rather than a stand-in for a filesystem.
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import pytest

from accountant_dad.artifacts.evidence import DocumentId
from accountant_dad.engines.input_engine import measurement as m

# ── fixtures ────────────────────────────────────────────────────────────────


def a_document_id() -> DocumentId:
    return DocumentId(uuid.uuid4())


def signals_of(collection: m.SignalCollection) -> tuple[m.NamedSignal, ...]:
    """Narrow a `SignalCollection` for a test that already knows the category
    was attempted. Asserting the real type here, rather than casting past it,
    is itself part of the test: a category that came back ABSENT when a
    signal was expected is a failure this helper refuses to hide.
    """
    assert isinstance(collection, tuple)
    return collection


def a_full_row(document_id: DocumentId | None = None) -> m.MeasurementRow:
    """One row using every field this module can hold, non-trivially."""
    return m.MeasurementRow(
        document_id=document_id or a_document_id(),
        source_document_type="tax invoice",
        processing_time_ms=842.5,
        document_score=0.7134,
        per_region_ocr=(
            m.NamedSignal(
                name="region_0",
                value=0.9821,
                instrument="PaddleOCR",
                region="page 0: left 12.0, top 88.0, right 240.0, bottom 110.0",
            ),
            m.NamedSignal(
                name="region_1",
                value=None,
                instrument="PaddleOCR",
                region="page 0: left 12.0, top 140.0, right 240.0, bottom 160.0",
            ),
        ),
        per_field=(m.NamedSignal(name="gstin", value=0.4102, instrument="PaddleOCR", region=None),),
        classification=(
            m.NamedSignal(name="document_type", value=0.995, instrument="document-type classifier"),
        ),
        table=(
            m.NamedSignal(
                name="line_1:qty",
                value=1.0,
                instrument="table-structure detector",
                region="cell (2,3)",
            ),
        ),
        failed_fields=("place_of_supply",),
        correctness=m.Correctness.UNLABELLED,
    )


# ── round trip: the row survives exactly, every field ─────────────────────


def test_measurement_row_round_trips_every_field_exactly(tmp_path: Path) -> None:
    row = a_full_row()
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back == row


def test_document_score_is_stored_verbatim_not_recomputed(tmp_path: Path) -> None:
    """Step 2's `document_score` has no combining rule (`#13` is UNDEFINED).
    This module must store exactly what it was given, not derive one."""
    row = a_full_row()
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.document_score == row.document_score
    assert not isinstance(read_back.document_score, m.AbsentType)


# ── absent, zero and unreadable stay three distinguishable states ─────────


def test_a_category_never_attempted_reads_back_as_absent(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=10.0,
        # per_field, classification, table, document_score, failed_fields all
        # left at their default: ABSENT, never attempted.
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.per_field is m.ABSENT
    assert read_back.classification is m.ABSENT
    assert read_back.table is m.ABSENT
    assert read_back.document_score is m.ABSENT
    assert read_back.failed_fields is m.ABSENT


def test_a_category_attempted_and_empty_is_not_absent(tmp_path: Path) -> None:
    """`()` and `ABSENT` are different facts: the first says "looked, found
    nothing" (no tables on this receipt); the second says "never looked."""
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=10.0,
        table=(),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.table == ()
    assert not isinstance(read_back.table, m.AbsentType)


def test_a_signal_read_as_zero_is_not_unreadable_and_not_absent(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=10.0,
        per_field=(m.NamedSignal(name="discount", value=0.0, instrument="PaddleOCR"),),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    (signal,) = signals_of(read_back.per_field)
    assert signal.value == 0.0
    assert signal.value is not None


def test_a_signal_read_as_unreadable_is_none_not_zero(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=10.0,
        per_field=(m.NamedSignal(name="discount", value=None, instrument="PaddleOCR"),),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    (signal,) = signals_of(read_back.per_field)
    assert signal.value is None


def test_zero_and_unreadable_and_absent_are_pairwise_distinguishable_in_one_row(
    tmp_path: Path,
) -> None:
    """The three states, side by side in the same category, on the same row -
    the strongest form of the distinguishability claim."""
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=10.0,
        per_field=(
            m.NamedSignal(name="zero_field", value=0.0, instrument="PaddleOCR"),
            m.NamedSignal(name="unreadable_field", value=None, instrument="PaddleOCR"),
        ),
        # classification never attempted at all: stays ABSENT.
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    by_name = {signal.name: signal.value for signal in signals_of(read_back.per_field)}
    assert by_name["zero_field"] == 0.0
    assert by_name["unreadable_field"] is None
    assert read_back.classification is m.ABSENT


# ── correctness: UNLABELLED is the only default, and it is not CORRECT ────


def test_correctness_defaults_to_unlabelled_on_construction() -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(), source_document_type="receipt", processing_time_ms=1.0
    )
    assert row.correctness is m.Correctness.UNLABELLED


def test_unlabelled_correctness_round_trips_and_is_never_read_as_correct(
    tmp_path: Path,
) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(), source_document_type="receipt", processing_time_ms=1.0
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.correctness is m.Correctness.UNLABELLED
    assert read_back.correctness.value != m.Correctness.CORRECT.value


def test_a_human_labelled_correctness_also_round_trips(tmp_path: Path) -> None:
    """The module records a supplied label faithfully; it just never invents one."""
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="receipt",
        processing_time_ms=1.0,
        correctness=m.Correctness.WRONG,
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.correctness is m.Correctness.WRONG


# ── append is append-only: two calls, two rows ─────────────────────────────


def test_appending_twice_produces_two_rows_not_one_overwritten(tmp_path: Path) -> None:
    row = a_full_row()
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    m.append(store, row)

    first, second = m.read_all(store)
    assert first == row
    assert second == row
    lines = store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(m.read_all(store))


def test_appending_two_different_documents_preserves_both_identities(tmp_path: Path) -> None:
    first = a_full_row()
    second = a_full_row()
    store = tmp_path / "store.jsonl"

    m.append(store, first)
    m.append(store, second)

    rows = m.read_all(store)
    assert [row.document_id for row in rows] == [first.document_id, second.document_id]
    assert first.document_id != second.document_id


# ── a malformed line fails loudly, naming ITS line ─────────────────────────


def test_a_malformed_json_line_names_its_line_number(tmp_path: Path) -> None:
    store = tmp_path / "store.jsonl"
    m.append(store, a_full_row())
    with store.open("a", encoding="utf-8") as handle:
        handle.write("not json at all\n")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"line 2"):
        m.read_all(store)


def test_a_malformed_signal_names_the_line_it_is_on(tmp_path: Path) -> None:
    """Permanent regression test for a real bug found auditing this module:
    `_signal_from_json` raised `MalformedMeasurementRecordError` directly, and
    the special case in `_row_from_json` that re-raises that exact exception
    type unwrapped meant the signal-level error never gained a line number.
    A two-line file whose bad signal sits on line 2 must name line 2, not be
    silent about which line, and must not be mistaken for a line-1 failure.
    """
    good_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [{"name": "r0", "value": 0.5, "instrument": "PaddleOCR"}],
    }
    bad_row = dict(good_row)
    # The instrument is not a string - a malformed SIGNAL, not a malformed row.
    bad_row["per_region_ocr"] = [{"name": "r0", "value": 0.5, "instrument": 123}]
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(good_row) + "\n" + json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError) as excinfo:
        m.read_all(store)

    assert "line 2" in str(excinfo.value)
    assert "line 1" not in str(excinfo.value)


def test_a_malformed_category_names_its_line_number(tmp_path: Path) -> None:
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "table": "not a list",
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"line 1"):
        m.read_all(store)


def test_a_signal_that_is_not_a_json_object_names_its_line_number(tmp_path: Path) -> None:
    """`_signal_from_json`'s own type check - the caller's `per_region_ocr`
    entry is valid JSON and a valid array, but the array holds a bare number
    rather than an object with `name`/`instrument`.
    """
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [123],
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"line 1"):
        m.read_all(store)


def test_a_signal_with_a_non_string_name_is_refused(tmp_path: Path) -> None:
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [{"name": 123, "instrument": "PaddleOCR"}],
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"name.*must be a string"):
        m.read_all(store)


def test_a_signal_with_a_non_string_region_is_refused(tmp_path: Path) -> None:
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [{"name": "r0", "instrument": "PaddleOCR", "region": 123}],
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"region.*must be"):
        m.read_all(store)


def test_a_signal_value_of_true_is_refused_as_a_boolean_not_a_number(tmp_path: Path) -> None:
    """`bool` is a subclass of `int` in Python - `isinstance(True, int)` is
    true, so the boolean case must be checked, and refused, before the
    numeric-type check would silently accept it as `1.0`.
    """
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [{"name": "r0", "instrument": "PaddleOCR", "value": True}],
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"not a boolean"):
        m.read_all(store)


def test_a_signal_value_that_is_neither_a_number_nor_a_string_is_refused(
    tmp_path: Path,
) -> None:
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "per_region_ocr": [{"name": "r0", "instrument": "PaddleOCR", "value": [1, 2]}],
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(
        m.MalformedMeasurementRecordError, match=r"a number, a numeric string, or null"
    ):
        m.read_all(store)


def test_a_line_that_is_valid_json_but_not_an_object_names_its_line_number(
    tmp_path: Path,
) -> None:
    """Different from `test_a_malformed_json_line_names_its_line_number`
    above: that line is not valid JSON at all. This line parses fine — it is
    a JSON array — and is refused because `_row_from_json` needs an object.
    """
    store = tmp_path / "store.jsonl"
    store.write_text("[1, 2, 3]\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"line 1"):
        m.read_all(store)


def test_failed_fields_that_is_not_a_json_array_is_refused(tmp_path: Path) -> None:
    bad_row = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
        "failed_fields": "gstin",
    }
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    with pytest.raises(m.MalformedMeasurementRecordError, match=r"'failed_fields' must be a"):
        m.read_all(store)


def test_a_malformed_line_is_never_silently_skipped(tmp_path: Path) -> None:
    """A store that drops an unparseable row is a store lying about how many
    documents were measured - the exact failure the module's docstring names."""
    store = tmp_path / "store.jsonl"
    m.append(store, a_full_row())
    with store.open("a", encoding="utf-8") as handle:
        handle.write("{}\n")  # a JSON object, but not a recordable row

    with pytest.raises(m.MalformedMeasurementRecordError):
        m.read_all(store)


def test_read_all_on_a_store_that_was_never_written_fails_loudly(tmp_path: Path) -> None:
    missing = tmp_path / "never_written.jsonl"
    with pytest.raises(FileNotFoundError):
        m.read_all(missing)


def test_read_all_on_an_empty_file_is_zero_rows_not_an_error(tmp_path: Path) -> None:
    store = tmp_path / "store.jsonl"
    store.write_text("", encoding="utf-8")
    assert m.read_all(store) == ()


# ── unicode survives ────────────────────────────────────────────────────────


def test_unicode_survives_the_round_trip(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="चालान",  # Hindi: "invoice"
        processing_time_ms=1.0,
        per_field=(
            m.NamedSignal(
                name="व्यापारी का नाम",  # "trader's name"
                value=0.6,
                instrument="PaddleOCR — दस्तावेज़ स्कैनर",
                region="पृष्ठ 1",
            ),
        ),
        failed_fields=("राज्य",),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back == row
    assert read_back.source_document_type == "चालान"
    (field_signal,) = signals_of(read_back.per_field)
    assert field_signal.name == "व्यापारी का नाम"
    assert field_signal.instrument == "PaddleOCR — दस्तावेज़ स्कैनर"
    assert field_signal.region == "पृष्ठ 1"
    assert read_back.failed_fields == ("राज्य",)
    # Written as real UTF-8 text on disk, not an escape-sequence encoding of it.
    assert "चालान" in store.read_text(encoding="utf-8")


# ── instrument and region: the fix this task exists to make ───────────────


def test_instrument_survives_the_round_trip_and_is_required(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        per_region_ocr=(
            m.NamedSignal(name="r0", value=0.9, instrument="PaddleOCR"),
            m.NamedSignal(name="r1", value=0.9, instrument="PDF text layer"),
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    instruments = {
        signal.name: signal.instrument for signal in signals_of(read_back.per_region_ocr)
    }
    assert instruments == {"r0": "PaddleOCR", "r1": "PDF text layer"}


def test_region_survives_the_round_trip_when_present(tmp_path: Path) -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        table=(
            m.NamedSignal(
                name="line_1:amount",
                value=1.0,
                instrument="table-structure detector",
                region="cell (1,4)",
            ),
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    (table_signal,) = signals_of(read_back.table)
    assert table_signal.region == "cell (1,4)"


def test_region_absent_round_trips_as_none_not_a_missing_field_error(tmp_path: Path) -> None:
    """A document-type classification score is not tied to one page location -
    `region=None` is a real answer, not a gap this module should refuse."""
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        classification=(
            m.NamedSignal(name="document_type", value=0.9, instrument="document-type classifier"),
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    (classification_signal,) = signals_of(read_back.classification)
    assert classification_signal.region is None


def test_the_stored_json_omits_the_region_key_entirely_when_none(tmp_path: Path) -> None:
    """Readable-without-this-module: an external `jq`/pandas reader sees no
    `region` key at all for a signal that has none, rather than a JSON `null`
    it would have to special-case."""
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        classification=(m.NamedSignal(name="document_type", value=0.9, instrument="classifier"),),
    )
    store = tmp_path / "store.jsonl"
    m.append(store, row)

    (line,) = store.read_text(encoding="utf-8").splitlines()
    payload = json.loads(line)
    (signal_payload,) = payload["classification"]
    assert "region" not in signal_payload
    assert signal_payload["instrument"] == "classifier"


# ── the store is plain line-delimited JSON, readable without this module ──


def test_the_store_is_readable_with_plain_json_and_no_import_of_this_module(
    tmp_path: Path,
) -> None:
    row = a_full_row()
    store = tmp_path / "store.jsonl"
    m.append(store, row)
    m.append(store, row)

    first_line, second_line = store.read_text(encoding="utf-8").splitlines()
    lines = (first_line, second_line)
    for line in lines:
        payload = json.loads(line)  # no `measurement` functions involved
        assert payload["document_id"] == str(row.document_id.value)
        assert payload["source_document_type"] == "tax invoice"
        assert payload["correctness"] == "unlabelled"
        assert isinstance(payload["per_region_ocr"], list)
        assert payload["per_region_ocr"][0]["instrument"] == "PaddleOCR"


# ── NamedSignal: construction failures, hard edges ─────────────────────────


def test_named_signal_rejects_a_blank_name() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="   ", value=0.5, instrument="PaddleOCR")


def test_named_signal_rejects_a_blank_instrument() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="gstin", value=0.5, instrument="")


def test_named_signal_rejects_a_whitespace_only_instrument() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="gstin", value=0.5, instrument="   ")


def test_named_signal_rejects_a_blank_region_string() -> None:
    """`region=None` (not tied to a location) is legal; `region=""` is not -
    an empty string is not an honest answer to "which region"."""
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="gstin", value=0.5, instrument="PaddleOCR", region="")


def test_named_signal_accepts_region_none() -> None:
    signal = m.NamedSignal(name="gstin", value=0.5, instrument="PaddleOCR", region=None)
    assert signal.region is None


def test_named_signal_rejects_nan_value() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="gstin", value=math.nan, instrument="PaddleOCR")


def test_named_signal_rejects_infinite_value() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.NamedSignal(name="gstin", value=math.inf, instrument="PaddleOCR")


def test_named_signal_accepts_a_real_zero_value() -> None:
    signal = m.NamedSignal(name="gstin", value=0.0, instrument="PaddleOCR")
    assert signal.value == 0.0


def test_named_signal_accepts_none_as_unreadable() -> None:
    signal = m.NamedSignal(name="gstin", value=None, instrument="PaddleOCR")
    assert signal.value is None


# ── MeasurementRow: construction failures, hard edges ──────────────────────


def test_measurement_row_rejects_a_blank_source_document_type() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(), source_document_type="  ", processing_time_ms=1.0
        )


def test_measurement_row_rejects_negative_processing_time() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(), source_document_type="invoice", processing_time_ms=-0.01
        )


def test_measurement_row_accepts_zero_processing_time() -> None:
    row = m.MeasurementRow(
        document_id=a_document_id(), source_document_type="invoice", processing_time_ms=0.0
    )
    assert row.processing_time_ms == 0.0


def test_measurement_row_rejects_nan_processing_time() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(), source_document_type="invoice", processing_time_ms=math.nan
        )


def test_measurement_row_rejects_non_finite_document_score() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            document_score=math.inf,
        )


def test_measurement_row_rejects_duplicate_signal_names_in_one_category() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            per_field=(
                m.NamedSignal(name="gstin", value=0.5, instrument="PaddleOCR"),
                m.NamedSignal(name="gstin", value=0.9, instrument="PDF text layer"),
            ),
        )


def test_the_duplicate_message_names_the_category_and_the_offending_name() -> None:
    """`pytest.raises(...)` with no `match=` proves only that SOMETHING raised.

    CI's mutation run left seven survivors inside `_no_duplicate_names` for
    exactly that reason: every mutation to the message, and several to the
    detection itself, still produced *an* exception, so the test above went on
    passing. §J.2 — assert the real RESULT, not that a function ran.
    """
    with pytest.raises(m.UnrecordableMeasurementError) as raised:
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            per_field=(
                m.NamedSignal(name="gstin", value=0.5, instrument="PaddleOCR"),
                m.NamedSignal(name="gstin", value=0.9, instrument="PDF text layer"),
            ),
        )

    message = str(raised.value)
    assert "per_field" in message, "the category must be named, or the reader cannot tell which one"
    assert "gstin" in message, "the offending name must be named, or the message is unactionable"
    assert "names the same signal twice" in message


#: Six names, deliberately. `sorted()` is the thing under test, and the mutation
#: that removes it leaves `list(set(...))`, whose order is hash-randomised per
#: process. With two names that mutant escapes half the time — measured, which
#: is how it survived the first attempt at this test. With six there are 720
#: orderings and only one of them is sorted, so the mutant escapes about once in
#: 720 runs. The test never fails spuriously: with the real `sorted()` the output
#: is sorted every time.
DUPLICATED_NAMES = ("qty", "gstin", "tax", "amount", "sgst", "invoice")


def test_every_duplicated_name_is_reported_and_they_come_back_sorted() -> None:
    """Six names, each duplicated, supplied in an order that is not sorted.

    Dropping `sorted()` leaves a report whose order varies with the process's
    hash seed — so two runs over identical data would disagree about what is
    wrong, and neither could be diffed against the other.
    """
    signals = tuple(
        m.NamedSignal(name=name, value=0.1, instrument="PaddleOCR")
        for name in (*DUPLICATED_NAMES, *DUPLICATED_NAMES)
    )

    with pytest.raises(m.UnrecordableMeasurementError) as raised:
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            per_field=signals,
        )

    message = str(raised.value)
    for name in DUPLICATED_NAMES:
        assert name in message, f"{name} was duplicated and must be reported"

    positions = [message.index(name) for name in sorted(DUPLICATED_NAMES)]
    assert positions == sorted(positions), (
        "duplicates must come back sorted. Without `sorted()` the order is the "
        f"set's, which is hash-seed dependent; got {message!r}"
    )


def test_a_name_repeated_three_times_is_reported_once_not_three_times() -> None:
    """The set comprehension is doing real work. Without it a name repeated N
    times is listed N times, which reads as N separate problems.
    """
    with pytest.raises(m.UnrecordableMeasurementError) as raised:
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            per_field=(
                m.NamedSignal(name="hsn", value=0.1, instrument="PaddleOCR"),
                m.NamedSignal(name="hsn", value=0.2, instrument="PaddleOCR"),
                m.NamedSignal(name="hsn", value=0.3, instrument="PaddleOCR"),
            ),
        )

    assert str(raised.value).count("hsn") == 1


def test_names_that_each_appear_once_are_accepted() -> None:
    """The boundary on the other side. `names.count(name) > 1` mutated to
    `>= 1` makes EVERY row with any signal raise, and nothing above would
    notice, because every test there is asserting that a raise happens.
    """
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        per_field=(
            m.NamedSignal(name="gstin", value=0.5, instrument="PaddleOCR"),
            m.NamedSignal(name="hsn", value=0.9, instrument="PaddleOCR"),
        ),
    )

    assert not isinstance(row.per_field, m.AbsentType)
    assert [signal.name for signal in row.per_field] == ["gstin", "hsn"]


def test_exactly_two_occurrences_is_already_a_duplicate() -> None:
    """The other boundary: `> 1` mutated to `> 2` lets a plain pair through,
    which is the commonest duplicate there is.
    """
    with pytest.raises(m.UnrecordableMeasurementError, match="rate"):
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            classification=(
                m.NamedSignal(name="rate", value=0.1, instrument="docling"),
                m.NamedSignal(name="rate", value=0.2, instrument="docling"),
            ),
        )


def test_a_single_signal_in_a_category_never_raises() -> None:
    """One signal cannot duplicate anything. This pins the empty/singleton edge
    that `if duplicated:` inverted to `if not duplicated:` would break.
    """
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        table=(m.NamedSignal(name="total", value=0.7, instrument="table-transformer"),),
    )

    assert not isinstance(row.table, m.AbsentType)
    assert len(row.table) == 1


def test_measurement_row_rejects_a_blank_failed_field_name() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            failed_fields=("gstin", "   "),
        )


def test_measurement_row_rejects_duplicate_failed_fields() -> None:
    with pytest.raises(m.UnrecordableMeasurementError):
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type="invoice",
            processing_time_ms=1.0,
            failed_fields=("gstin", "gstin"),
        )


# ── AbsentType: the sentinel refuses to be mistaken for False ──────────────


def test_absent_has_no_truth_value() -> None:
    with pytest.raises(TypeError):
        bool(m.ABSENT)


def test_absent_cannot_be_used_in_an_if_not_check() -> None:
    """The exact collapse the sentinel exists to prevent: `not value` must
    itself explode rather than silently treating ABSENT as falsy."""
    with pytest.raises(TypeError):
        _ = not m.ABSENT


def test_absent_reprs_as_absent_not_as_the_default_object_repr() -> None:
    """A debugger or a failed-assertion message that printed
    `<accountant_dad.engines.input_engine.measurement.AbsentType object at
    0x...>` would tell an operator nothing; `ABSENT` names itself."""
    assert repr(m.ABSENT) == "ABSENT"
