"""`measurement` red-team — attacks on the only place the raw signal lives.

Nothing downstream reconstructs an instrument, a region, a per-field score or a
processing time once a row has been written. This store is not a copy of the
measurement; it IS the measurement. So the questions worth asking are not "does
a row go in and come back out" — `tests/unit/test_input_engine_measurement.py`
already answers that — but:

    can a number get into this store that nobody measured?
    can a number that was measured quietly fail to come back?

────────────────────────────────────────────────────────────────────────────
ONE DEFECT, FOUR SHAPES. ITS TESTS ARE LEFT RED ON PURPOSE. READ THIS FIRST.
────────────────────────────────────────────────────────────────────────────

`_row_from_json` COERCES where `_signal_from_json` TYPE-CHECKS.

Inside one file, two functions read untrusted JSON. One asks `isinstance` and
refuses anything else, by name:

    _signal_from_json:  "signal 'g''s value must be a number, not a boolean"

The other calls `float(...)` and `str(...)` on whatever it finds:

    _row_from_json:     processing_time_ms = float(payload["processing_time_ms"])
                        source_document_type = str(payload["source_document_type"])
                        failed_fields = tuple(str(item) for item in raw_failed)
                        document_score = float(payload["document_score"])

`float(True)` is `1.0`. `str(None)` is `"None"`. So, measured on the real
module, against a real file, today:

    stored                              read back as
    ─────────────────────────────────   ────────────────────────────────────
    "document_score": true              document_score = 1.0   (the maximum)
    "processing_time_ms": true          processing_time_ms = 1.0 ms
    "source_document_type": null        source_document_type = "None"
    "failed_fields": [null, 1, true]    ("None", "1", "True")

None of those raised. None was logged. Every one of them is a value this
module's own `_row_to_json` could never have written — and the module docstring
states the contract they violate, in its own words:

    "`read_all()` raises loudly, naming the exact line, on anything that is not
     a row this module could have written"

The `document_score` case is the worst of the four and the reason this is filed
as a defect rather than a nit. `document_score` is the single number stage 3 of
`ENGINE_1_CONFIDENCE_PARAMETERS.md` calibrates every threshold against, and the
value fabricated from `true` is `1.0` — a perfect score, on a document nobody
scored. `MEASUREMENT_FRAMEWORK.md` §0 exists to stop a number being decided
after the fact; this is a number decided by `float()`.

The four tests below state the correct behaviour and fail. Fixing them belongs
in `src/`, which this file does not touch.

PROBLEM PRINCIPLE (`CLAUDE.md` §J.9), so the class cannot recur rather than the
four instances being patched: **a reader of untrusted JSON must ask what a value
IS, never ask what it can be TURNED INTO.** `float` and `str` are total
functions on almost everything; that totality is precisely what makes them
unable to reject anything.

────────────────────────────────────────────────────────────────────────────
WHAT ELSE WAS ATTACKED, AND HELD
────────────────────────────────────────────────────────────────────────────

Provenance — a signal cannot be constructed or read without an instrument, and
a region survives every category, so an untraceable number cannot be created.

Round-tripping — embedded newlines, embedded whole rows of JSON, NUL, emoji,
combining marks, a 20 000-character field, and every float at the limits of the
type, including the smallest denormal. All exact, and a row full of newlines
still occupies exactly one line.

Malformed rows — an unknown correctness label, a missing correctness key, a
blank line, a bad UUID, a NaN written as a string, a literal that overflows to
infinity, duplicate signal names. All refused, naming file, line and cause.

Append — the bytes of every earlier row are unchanged by a later append; fifty
appends read back as fifty rows in order; a store not ending in a newline fails
loudly instead of merging two rows into one; and an append that cannot be
encoded leaves the store byte-for-byte as it was.

The format — pinned, character for character, for a minimal row; and a row read
back and written again reproduces identical bytes.

REAL DEPENDENCIES, NO MOCKS (`CLAUDE.md` §J.6). Every attack writes to and reads
from a real file under pytest's `tmp_path`.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import sys
import uuid
from pathlib import Path

import pytest

from accountant_dad.artifacts.evidence import DocumentId
from accountant_dad.engines.input_engine import measurement as m

# ── fixtures ────────────────────────────────────────────────────────────────

#: A fixed identifier, so the byte-for-byte format assertions below can be
#: written out in full rather than assembled from whatever `uuid4` produced.
FIXED_DOCUMENT_ID = DocumentId(uuid.UUID("00000000-0000-4000-8000-000000000001"))

#: How many rows the append-order attack writes. Large enough that an off-by-one
#: or a reordering shows up, small enough to stay a unit test.
MANY_ROWS = 50

#: The line the malformed row sits on in the position-independence attack — not
#: 1 and not 2, which are the only positions the existing suite exercises.
BAD_LINE_NUMBER = 7
TOTAL_LINES = 10

LONG_TEXT_LENGTH = 20000

#: The smallest positive number a Python float can hold — the last denormal
#: before zero. Named because it is asserted on as well as written, and a bare
#: `5e-324` in the assertion says nothing about why that value is interesting:
#: it is the one reading that a serialiser rounding to fewer than seventeen
#: significant digits would silently turn into `0.0`, which this store must
#: never do (a measured zero and the smallest measurable reading are different
#: facts).
SMALLEST_DENORMAL_FLOAT = 5e-324


def a_document_id() -> DocumentId:
    return DocumentId(uuid.uuid4())


def signals_of(collection: m.SignalCollection) -> tuple[m.NamedSignal, ...]:
    """Narrow a category a test already knows was attempted. The assertion is
    part of the test: a category that came back ABSENT where a signal was
    expected is a failure this helper refuses to hide.
    """
    assert isinstance(collection, tuple)
    return collection


def a_score(collection: m.NumericSignal) -> float:
    """The same narrowing for the row-level score. ABSENT where a number was
    expected is the exact collapse Law 24 forbids, so it fails here.
    """
    assert not isinstance(collection, m.AbsentType)
    return collection


def a_stored_row(**overrides: object) -> dict[str, object]:
    """A payload with every key `_row_to_json` always writes, ready to be
    corrupted one key at a time. Built as raw JSON rather than through
    `MeasurementRow`, because the attacks below are on what an EXTERNAL writer
    can put in the store — a hand-edited line, another tool, a partial write.
    """
    payload: dict[str, object] = {
        "document_id": str(uuid.uuid4()),
        "source_document_type": "invoice",
        "processing_time_ms": 1.0,
        "correctness": "unlabelled",
    }
    payload.update(overrides)
    return payload


def write_lines(store: Path, *payloads: dict[str, object]) -> None:
    store.write_text("".join(json.dumps(payload) + "\n" for payload in payloads), encoding="utf-8")


def a_full_row(document_id: DocumentId | None = None) -> m.MeasurementRow:
    """One row using every field the module can hold, all four categories
    populated, with and without a region.
    """
    return m.MeasurementRow(
        document_id=document_id or a_document_id(),
        source_document_type="tax invoice",
        processing_time_ms=842.5,
        document_score=0.7134,
        per_region_ocr=(
            m.NamedSignal(name="region_0", value=0.9821, instrument="PaddleOCR", region="page 0"),
        ),
        per_field=(m.NamedSignal(name="gstin", value=0.4102, instrument="PaddleOCR"),),
        classification=(
            m.NamedSignal(name="document_type", value=0.995, instrument="document-type classifier"),
        ),
        table=(
            m.NamedSignal(
                name="line_1:qty", value=1.0, instrument="table detector", region="cell (2,3)"
            ),
        ),
        failed_fields=("place_of_supply",),
        correctness=m.Correctness.UNLABELLED,
    )


# ══════════════════════════════════════════════════════════════════════════
# DEFECT — LEFT RED. Four shapes of one root cause. See the module docstring.
# ══════════════════════════════════════════════════════════════════════════


def test_a_stored_document_score_of_true_is_refused_not_read_as_a_perfect_score(
    tmp_path: Path,
) -> None:
    """RED BY DESIGN — a real defect in `src/`, not a broken test.

    `float(True)` is `1.0`, so a stored boolean becomes the HIGHEST document
    score the scale has, on a document nobody scored. `_signal_from_json`
    refuses a boolean by name, one function away, for exactly this reason.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(document_score=True))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "document_score" in str(raised.value)


def test_a_stored_processing_time_of_true_is_refused_not_read_as_one_millisecond(
    tmp_path: Path,
) -> None:
    """RED BY DESIGN. The same coercion, on the field
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #16 calibrates `processing_budget_ms`
    against. A boolean becomes a document that took one millisecond.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(processing_time_ms=True))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "processing_time_ms" in str(raised.value)


def test_a_stored_source_document_type_of_null_is_refused_not_read_as_the_text_none(
    tmp_path: Path,
) -> None:
    """RED BY DESIGN. `str(None)` is `"None"`, which is four non-blank
    characters, so `MeasurementRow.__post_init__`'s `.strip()` check passes and
    the row asserts a source document type of `None` — a type no classifier
    ever produced. Stage 2 records "source document type" precisely so
    calibration can be split by it; a phantom type creates a phantom cohort.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(source_document_type=None))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "source_document_type" in str(raised.value)


def test_a_stored_failed_field_of_null_is_refused_not_read_as_a_field_named_none(
    tmp_path: Path,
) -> None:
    """RED BY DESIGN. `tuple(str(item) for item in raw_failed)` turns
    `[null, 1, true]` into `("None", "1", "True")` — three field names that do
    not exist on any document. `_signal_from_json` requires a signal's name to
    BE a string; `failed_fields` accepts anything that can be printed.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(failed_fields=[None, 1, True]))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "failed_fields" in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
# THE SAME DEFECT'S REMAINING SURFACE
#
# The four tests above are the four shapes that were MEASURED fabricating a
# value. They are instances. The tests below hold the rest of the class down,
# so a later edit cannot reintroduce a coercion at a site that happened not to
# be one of the four — `document_id`, which only escaped because `uuid.UUID` is
# strict enough to refuse `"None"` on its own, and the numeric-string forms,
# which `float()` accepted for fields this module's own writer only ever emits
# as JSON numbers.
# ══════════════════════════════════════════════════════════════════════════


def test_a_stored_document_id_that_is_not_a_string_is_refused_before_uuid_sees_it(
    tmp_path: Path,
) -> None:
    """`str(payload["document_id"])` was the same coercion as the other four,
    and survived only because `uuid.UUID` happens to reject the `"None"` and
    `"123"` it manufactures. That is luck, not a guard: the refusal must come
    from the reader asking what the value IS, so it stays a refusal if the
    identifier type ever becomes anything more forgiving than a UUID.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(document_id=None))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "`document_id` must be a string; got None." in str(raised.value)


def test_a_document_score_written_as_a_numeric_string_is_refused(tmp_path: Path) -> None:
    """`"0.9"` is not a number, it is text that looks like one. `_row_to_json`
    writes `document_score` as a JSON number and has no branch that could ever
    emit a string, so a string here is by definition not a row this module could
    have written — the exact contract `read_all` claims to enforce. Accepting it
    would mean the store's type is decided by whoever wrote the line last.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(document_score="0.9"))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "`document_score` must be a number; got '0.9'." in str(raised.value)


def test_a_processing_time_written_as_a_numeric_string_is_refused(tmp_path: Path) -> None:
    """The same for the field `ENGINE_1_CONFIDENCE_PARAMETERS.md` #16 calibrates
    `processing_budget_ms` against. Separate from the `document_score` case
    above because they are separate call sites, and a fix applied to one and
    forgotten at the other is precisely how this defect had four shapes.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(processing_time_ms="1.0"))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert "`processing_time_ms` must be a number; got '1.0'." in str(raised.value)


def test_a_signal_value_string_that_is_not_a_number_names_the_signal_and_the_line(
    tmp_path: Path,
) -> None:
    """A numeric string is a DECLARED shape for `NamedSignal.value` alone, so
    this is the one place text legitimately becomes a number — which makes it
    the one place a non-numeric string can arrive. `"gstin"` must be refused
    naming the signal, the line and the file, not raised as a bare
    `could not convert string to float` with no idea which document it came
    from (Law 11).
    """
    store = tmp_path / "store.jsonl"
    write_lines(
        store,
        a_stored_row(),
        a_stored_row(per_field=[{"name": "gstin", "instrument": "PaddleOCR", "value": "eight"}]),
    )

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (
        f"line 2 of {store}: signal 'gstin''s value must be a number, a numeric "
        "string, or null; got 'eight', which is not a number."
    )


# ══════════════════════════════════════════════════════════════════════════
# A SIGNAL CANNOT EXIST WITHOUT ITS INSTRUMENT
#
# `ConfidenceReport.FieldConfidence` has no slot for an instrument or a region,
# so this store is the only place either fact exists. A signal that could be
# created without one would be a number with no traceable origin — which is
# indistinguishable from an invented one.
# ══════════════════════════════════════════════════════════════════════════


def test_instrument_has_no_default_and_region_defaults_to_not_tied_to_a_location() -> None:
    """Not "a blank instrument is refused" — that is already covered. This is
    the weaker-looking and more likely route to an untraceable number: a
    default on the field, so a caller that simply omits an instrument gets one
    invented for it. Every existing blank-instrument test would keep passing.

    The two fields are asserted together because they must differ, and the
    difference is the module's own claim: an instrument always exists, so
    omitting one is an error; a region genuinely may not, so `None` is a real
    answer rather than a missing one.
    """
    fields = {field.name: field for field in dataclasses.fields(m.NamedSignal)}

    assert fields["instrument"].default is dataclasses.MISSING
    assert fields["instrument"].default_factory is dataclasses.MISSING
    assert fields["region"].default is None


def test_a_stored_signal_with_no_instrument_key_is_refused_naming_line_and_path(
    tmp_path: Path,
) -> None:
    """The read side of the same claim. An external writer that omits the key
    entirely must be refused as loudly as one that writes the wrong type — the
    existing suite only covers a non-string instrument, which is the case an
    external writer is LEAST likely to produce.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(per_field=[{"name": "gstin", "value": 0.5}]))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (
        f"line 1 of {store}: signal 'gstin''s instrument must be a string; got None."
    )


def test_a_stored_signal_with_no_name_key_is_refused_naming_line_and_path(
    tmp_path: Path,
) -> None:
    """The same for the name. An unnamed signal is a number attached to nothing."""
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(per_field=[{"instrument": "PaddleOCR", "value": 0.5}]))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (f"line 1 of {store}: a signal's name must be a string; got None.")


def test_every_category_keeps_its_instrument_and_its_region_through_the_store(
    tmp_path: Path,
) -> None:
    """All four categories at once, each with a DIFFERENT instrument and a
    DIFFERENT region. The existing suite checks one category at a time with
    shared values, so a serialiser that read the instrument from the wrong
    signal, or applied one category's regions to another, would survive it.
    """
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        per_region_ocr=(
            m.NamedSignal(name="r0", value=0.1, instrument="PaddleOCR", region="page 0"),
        ),
        per_field=(m.NamedSignal(name="gstin", value=0.2, instrument="PDF text layer"),),
        classification=(m.NamedSignal(name="document_type", value=0.3, instrument="classifier"),),
        table=(
            m.NamedSignal(name="qty", value=0.4, instrument="table detector", region="cell (1,1)"),
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert [
        (signal.name, signal.instrument, signal.region)
        for category in m._SIGNAL_CATEGORIES
        for signal in signals_of(getattr(read_back, category))
    ] == [
        ("r0", "PaddleOCR", "page 0"),
        ("gstin", "PDF text layer", None),
        ("document_type", "classifier", None),
        ("qty", "table detector", "cell (1,1)"),
    ]


def test_a_stored_region_written_as_explicit_null_reads_back_as_not_tied_to_a_location(
    tmp_path: Path,
) -> None:
    """`_signal_to_json` omits the key; an external writer will often emit
    `"region": null` instead. Both must mean the same thing — the signal is not
    tied to one page location — because the alternative is a reader that treats
    two spellings of the same fact as two different facts.
    """
    store = tmp_path / "store.jsonl"
    write_lines(
        store,
        a_stored_row(
            classification=[
                {"name": "document_type", "value": 0.9, "instrument": "classifier", "region": None}
            ]
        ),
    )

    (read_back,) = m.read_all(store)

    (signal,) = signals_of(read_back.classification)
    assert signal.region is None
    assert signal.instrument == "classifier"


# ══════════════════════════════════════════════════════════════════════════
# ROUND-TRIPPING UNDER HOSTILE CONTENT
# ══════════════════════════════════════════════════════════════════════════


def test_a_row_whose_every_string_holds_newlines_stays_one_line_and_survives_exactly(
    tmp_path: Path,
) -> None:
    """The attack the whole line-delimited format rests on. If a newline inside
    a value reached the file unescaped, ONE document would become TWO lines,
    `read_all` would report a count nobody measured, and the second half would
    be a malformed row blamed on the wrong document.

    Carriage returns are attacked too, because text mode's universal-newline
    translation would turn a bare `\\r` into a line break on the way back in.
    """
    nasty = "tax\ninvoice\r\nline three\rline four"
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type=nasty,
        processing_time_ms=1.0,
        per_field=(m.NamedSignal(name=nasty, value=0.5, instrument=nasty, region=nasty),),
        failed_fields=(nasty,),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)

    raw = store.read_text(encoding="utf-8")
    assert raw.count("\n") == 1, "one document must occupy exactly one line"
    assert raw.endswith("\n")
    (read_back,) = m.read_all(store)
    assert read_back == row


def test_a_string_that_is_itself_a_row_of_json_survives_as_text_not_as_structure(
    tmp_path: Path,
) -> None:
    """A source document type that spells out a complete, valid measurement row
    — the injection shape. It must come back as those characters, and it must
    not change what the reader believes the row's own fields are.
    """
    injected = json.dumps(
        {
            "document_id": str(uuid.uuid4()),
            "source_document_type": "forged",
            "processing_time_ms": 999.0,
            "correctness": "correct",
        }
    )
    row = m.MeasurementRow(
        document_id=FIXED_DOCUMENT_ID,
        source_document_type=injected,
        processing_time_ms=1.0,
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back.source_document_type == injected
    assert read_back.document_id == FIXED_DOCUMENT_ID
    assert read_back.processing_time_ms == 1.0
    assert read_back.correctness is m.Correctness.UNLABELLED


def test_values_at_the_limits_of_a_python_float_survive_exactly(tmp_path: Path) -> None:
    """The largest float, the smallest normal, the smallest denormal, the most
    negative, and a value whose decimal expansion needs all seventeen
    significant digits. A serialiser that formatted with anything less than
    full round-trip precision would lose the last digits of a real reading, and
    every ordinary test value (`0.5`, `0.9821`) is far too short to notice.
    """
    limits = (
        sys.float_info.max,
        -sys.float_info.max,
        sys.float_info.min,
        SMALLEST_DENORMAL_FLOAT,
        0.1 + 0.2,
    )
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=sys.float_info.max,
        document_score=SMALLEST_DENORMAL_FLOAT,
        per_field=tuple(
            m.NamedSignal(name=f"f{index}", value=value, instrument="probe")
            for index, value in enumerate(limits)
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert tuple(signal.value for signal in signals_of(read_back.per_field)) == limits
    assert read_back.processing_time_ms == sys.float_info.max
    assert a_score(read_back.document_score) == SMALLEST_DENORMAL_FLOAT


def test_a_twenty_thousand_character_field_survives_exactly(tmp_path: Path) -> None:
    """A region description of a dense page, or an instrument string carrying a
    full model identifier, is not small. Length must not be where the format
    starts truncating.
    """
    long_text = "स" * LONG_TEXT_LENGTH
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type=long_text,
        processing_time_ms=1.0,
        per_field=(
            m.NamedSignal(name=long_text, value=0.5, instrument=long_text, region=long_text),
        ),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back == row
    assert len(read_back.source_document_type) == LONG_TEXT_LENGTH


def test_emoji_combining_marks_and_a_null_character_survive_exactly(tmp_path: Path) -> None:
    """Beyond the Devanagari the existing suite covers: a character outside the
    Basic Multilingual Plane (a surrogate pair in UTF-16 terms), a base letter
    plus a combining mark that must not be normalised away, a right-to-left
    mark, and a NUL — the one character a C-style writer would truncate at.
    """
    # Every non-ASCII character is written as an escape rather than embedded
    # literally. The STRING IS UNCHANGED — the escapes denote exactly the same
    # code points, so the attack is identical — but the SOURCE no longer
    # carries an invisible right-to-left mark (U+200F), which is precisely how
    # a reviewer gets shown one thing and the parser handed another (PLE2502).
    # Escaping it also un-hid a second finding: with the bidi mark present,
    # ruff stopped reporting the Arabic alef as a Latin-lookalike (RUF001).
    # U+1F9FE receipt . e + U+0301 combining acute . U+200F right-to-left mark
    # . U+0627..U+0629 Arabic for 'the invoice' . U+0000 NUL
    exotic = "\U0001f9fe e\u0301 \u200f\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \x00 end"
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type=exotic,
        processing_time_ms=1.0,
        per_field=(m.NamedSignal(name=exotic, value=0.5, instrument=exotic, region=exotic),),
        failed_fields=(exotic,),
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)
    (read_back,) = m.read_all(store)

    assert read_back == row
    assert read_back.source_document_type == exotic
    (signal,) = signals_of(read_back.per_field)
    assert signal.region == exotic


def test_a_document_score_of_zero_survives_as_zero_and_never_as_absent(
    tmp_path: Path,
) -> None:
    """The row-level half of Law 24's three states, and the one the existing
    suite never exercises: every `document_score` it round-trips is non-zero.
    `_row_to_json` writes the key when the value is not ABSENT — a mutation to
    a truthiness test there would drop a measured zero on the floor, and the
    row would come back claiming nobody scored the document.
    """
    row = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=0.0,
        document_score=0.0,
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)

    assert "document_score" in json.loads(store.read_text(encoding="utf-8"))
    (read_back,) = m.read_all(store)
    assert read_back.document_score is not m.ABSENT
    assert a_score(read_back.document_score) == 0.0
    assert read_back.processing_time_ms == 0.0


def test_an_empty_failed_fields_tuple_is_not_the_same_fact_as_absent(
    tmp_path: Path,
) -> None:
    """`()` says "every field was read"; ABSENT says "nobody looked". The
    existing suite draws that distinction for `table` only. On `failed_fields`
    it is the difference between a clean document and an unexamined one.
    """
    examined = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
        failed_fields=(),
    )
    unexamined = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="invoice",
        processing_time_ms=1.0,
    )
    store = tmp_path / "store.jsonl"

    m.append(store, examined)
    m.append(store, unexamined)

    first, second = m.read_all(store)
    assert first.failed_fields == ()
    assert first.failed_fields is not m.ABSENT
    assert second.failed_fields is m.ABSENT


# ══════════════════════════════════════════════════════════════════════════
# A MALFORMED ROW FAILS LOUDLY, NAMING FILE, LINE AND CAUSE
# ══════════════════════════════════════════════════════════════════════════


def test_an_unknown_correctness_label_is_refused_not_quietly_unlabelled(
    tmp_path: Path,
) -> None:
    """The most dangerous silent read in the module if it were ever added: a
    label the enum does not know falling back to `UNLABELLED` would erase a
    human's verdict, and `Correctness`'s own docstring says the distinction
    between "nobody has checked" and "this was right" is the whole value of the
    record.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(correctness="probably"))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (
        f"line 1 of {store} is not a recordable measurement row: "
        "'probably' is not a valid Correctness"
    )


def test_a_row_with_no_correctness_key_is_refused_not_defaulted_to_unlabelled(
    tmp_path: Path,
) -> None:
    """`Correctness.UNLABELLED` is the default at CONSTRUCTION, on purpose. It
    must NOT become a default on READ: a row whose label was lost in transit
    would come back looking exactly like one that was honestly never labelled,
    and the two are different facts about the same document.
    """
    store = tmp_path / "store.jsonl"
    payload = a_stored_row()
    del payload["correctness"]
    write_lines(store, payload)

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (
        f"line 1 of {store} is not a recordable measurement row: 'correctness'"
    )


def test_a_document_id_that_is_not_a_uuid_is_refused_naming_line_path_and_cause(
    tmp_path: Path,
) -> None:
    """Identity is what joins this store to the documents it measured. A row
    whose identifier cannot be parsed cannot be joined to anything, and must
    not be read as a row with some other identifier.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(document_id="not-a-uuid"))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value) == (
        f"line 1 of {store} is not a recordable measurement row: "
        "badly formed hexadecimal UUID string"
    )


def test_a_null_document_score_is_refused_rather_than_read_as_absent(
    tmp_path: Path,
) -> None:
    """`"document_score": null` is a fourth spelling nobody agreed to: the
    module writes the key or omits it, and there is no rule saying an explicit
    null means ABSENT. Reading it as ABSENT would be this module deciding what
    a writer meant.
    """
    store = tmp_path / "store.jsonl"
    write_lines(store, a_stored_row(document_score=None))

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert f"line 1 of {store} is not a recordable measurement row:" in str(raised.value)


def test_a_signal_value_written_as_the_string_nan_is_refused(tmp_path: Path) -> None:
    """`"NaN"` passes `_signal_from_json`'s type check — it is a string, and
    strings are legal there — then `float("NaN")` produces a value for which
    every comparison is false. `NamedSignal.__post_init__` catches it, and the
    error must reach the caller carrying the line and the file, not as a bare
    construction error with no idea which document it came from.
    """
    store = tmp_path / "store.jsonl"
    write_lines(
        store,
        a_stored_row(),
        a_stored_row(per_field=[{"name": "gstin", "instrument": "PaddleOCR", "value": "NaN"}]),
    )

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    message = str(raised.value)
    assert f"line 2 of {store}" in message
    assert "not a measurement (Law 24)" in message


def test_a_signal_value_that_overflows_to_infinity_is_refused(tmp_path: Path) -> None:
    """`json.loads("1e400")` does not raise — it returns `inf`. A store written
    by a tool with a wider numeric type would deliver exactly this, and an
    infinite reading is not a reading.
    """
    store = tmp_path / "store.jsonl"
    store.write_text(
        '{"document_id": "00000000-0000-4000-8000-000000000001", '
        '"source_document_type": "invoice", "processing_time_ms": 1.0, '
        '"correctness": "unlabelled", '
        '"per_field": [{"name": "gstin", "instrument": "PaddleOCR", "value": 1e400}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(m.MalformedMeasurementRecordError, match="not a measurement"):
        m.read_all(store)


def test_two_signals_sharing_a_name_in_a_stored_row_are_refused_on_read(
    tmp_path: Path,
) -> None:
    """`_no_duplicate_names` is tested only through direct construction. The
    store is the side that matters for calibration: a hand-edited or
    concatenated line carrying two values for one field leaves no authority for
    which one a later run should read, and must be refused with the line named.
    """
    store = tmp_path / "store.jsonl"
    write_lines(
        store,
        a_stored_row(
            per_field=[
                {"name": "gstin", "instrument": "PaddleOCR", "value": 0.1},
                {"name": "gstin", "instrument": "PDF text layer", "value": 0.9},
            ]
        ),
    )

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    message = str(raised.value)
    assert f"line 1 of {store}" in message
    assert "names the same signal twice: gstin" in message


def test_a_blank_line_between_two_rows_is_refused_naming_that_line(
    tmp_path: Path,
) -> None:
    """A blank line is what a hand-edit, a concatenation or an interrupted copy
    leaves behind. Skipping it would be indistinguishable from skipping a real
    row, and the store would report a document count it cannot justify.
    """
    store = tmp_path / "store.jsonl"
    m.append(store, a_full_row())
    with store.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    m.append(store, a_full_row())

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert f"line 2 of {store} is not valid JSON:" in str(raised.value)


def test_a_malformed_row_in_the_middle_of_a_long_store_names_its_own_line(
    tmp_path: Path,
) -> None:
    """Line 1 and line 2 are the only positions the existing suite reaches, and
    both survive an enumerator that started at the wrong place by a plausible
    amount. Line 7 of 10 does not: an operator handed the wrong line number
    goes and re-runs the wrong document.
    """
    store = tmp_path / "store.jsonl"
    payloads = [
        a_stored_row(source_document_type=f"doc-{index}") for index in range(1, TOTAL_LINES + 1)
    ]
    payloads[BAD_LINE_NUMBER - 1] = a_stored_row(correctness="probably")
    write_lines(store, *payloads)

    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)

    assert str(raised.value).startswith(f"line {BAD_LINE_NUMBER} of {store} ")


# ══════════════════════════════════════════════════════════════════════════
# APPEND NEVER LOSES, REORDERS OR OVERWRITES
# ══════════════════════════════════════════════════════════════════════════


def test_the_bytes_of_every_earlier_row_are_unchanged_by_a_later_append(
    tmp_path: Path,
) -> None:
    """The direct form of "append-only", and stronger than counting rows: after
    every append the file must still START with exactly the bytes it held
    before. Any rewrite, re-sort or truncation of earlier content breaks the
    prefix property even when the row count stays right.
    """
    store = tmp_path / "store.jsonl"
    snapshots: list[bytes] = [b""]

    for index in range(5):
        m.append(
            store,
            m.MeasurementRow(
                document_id=a_document_id(),
                source_document_type=f"doc-{index}",
                processing_time_ms=float(index),
            ),
        )
        snapshots.append(store.read_bytes())

    for earlier, later in itertools.pairwise(snapshots):
        assert later.startswith(earlier)
        assert len(later) > len(earlier)


def test_fifty_appends_read_back_as_fifty_rows_in_the_order_written(
    tmp_path: Path,
) -> None:
    """Order is not decoration: stage 3 splits these rows by processing time
    and by document type, and a store that reordered silently would make two
    calibration runs over the same data disagree.
    """
    store = tmp_path / "store.jsonl"
    written = [
        m.MeasurementRow(
            document_id=a_document_id(),
            source_document_type=f"doc-{index}",
            processing_time_ms=float(index),
        )
        for index in range(MANY_ROWS)
    ]
    for row in written:
        m.append(store, row)

    read_back = m.read_all(store)

    assert list(read_back) == written
    assert len(store.read_text(encoding="utf-8").splitlines()) == MANY_ROWS


def test_appending_to_a_store_that_does_not_end_in_a_newline_fails_loudly(
    tmp_path: Path,
) -> None:
    """`append` writes `line + "\\n"`, so a store it wrote always ends in one.
    A store that does NOT — truncated by a full disk, or produced by another
    tool — would have its last row and the new row concatenated onto one line.

    That corrupts both. What must not happen is corrupting them QUIETLY: the
    reader has to refuse, naming the line, rather than parse the first object
    and drop the second. It does, and this pins it.
    """
    store = tmp_path / "store.jsonl"
    store.write_text(json.dumps(a_stored_row(source_document_type="first")), encoding="utf-8")

    m.append(store, a_full_row())

    assert store.read_text(encoding="utf-8").count("\n") == 1
    with pytest.raises(m.MalformedMeasurementRecordError) as raised:
        m.read_all(store)
    assert f"line 1 of {store} is not valid JSON:" in str(raised.value)


def test_an_append_that_cannot_be_encoded_leaves_the_store_exactly_as_it_was(
    tmp_path: Path,
) -> None:
    """A lone surrogate is a `str` Python permits and UTF-8 cannot represent.
    It passes every `NamedSignal` and `MeasurementRow` check — none of them is
    about encodability — and fails inside `append`.

    The question is whether the failure is atomic. A partially written line
    would leave the store unreadable from that point on, so ONE bad row would
    destroy every row already recorded. It does not: the encode fails before
    any byte reaches the file, and the earlier rows still read.
    """
    store = tmp_path / "store.jsonl"
    m.append(store, a_full_row())
    before = store.read_bytes()

    unencodable = m.MeasurementRow(
        document_id=a_document_id(),
        source_document_type="\ud800",
        processing_time_ms=1.0,
    )

    with pytest.raises(UnicodeEncodeError):
        m.append(store, unencodable)

    assert store.read_bytes() == before
    assert len(m.read_all(store)) == 1


def test_appending_into_a_directory_that_does_not_exist_fails_loudly(
    tmp_path: Path,
) -> None:
    """`append` creates the FILE, never the directory. A caller that mistyped a
    path must be told, not have a store quietly created somewhere nobody looks
    — a measurement written to the wrong place is a measurement never taken.
    """
    with pytest.raises(FileNotFoundError):
        m.append(tmp_path / "no_such_directory" / "store.jsonl", a_full_row())


# ══════════════════════════════════════════════════════════════════════════
# THE STORED FORMAT IS STABLE AND SELF-DESCRIBING
#
# `MEASUREMENT_FRAMEWORK.md` §8: "A measurement nobody else can regenerate is
# an anecdote." A format that drifts silently makes every row written before
# the drift unreadable by whatever reads the rows written after it.
# ══════════════════════════════════════════════════════════════════════════


def test_a_minimal_row_is_written_as_exactly_this_line(tmp_path: Path) -> None:
    """Character for character, with a fixed identifier. Nothing else in the
    suite states what the on-disk format actually IS — the round-trip tests all
    read through this module's own reader, so a format change on both sides at
    once is invisible to every one of them, and to every external `jq` or
    pandas reader it is a breaking change delivered without notice.
    """
    row = m.MeasurementRow(
        document_id=FIXED_DOCUMENT_ID,
        source_document_type="invoice",
        processing_time_ms=12.5,
    )
    store = tmp_path / "store.jsonl"

    m.append(store, row)

    assert store.read_text(encoding="utf-8") == (
        '{"correctness": "unlabelled", '
        '"document_id": "00000000-0000-4000-8000-000000000001", '
        '"processing_time_ms": 12.5, '
        '"source_document_type": "invoice"}\n'
    )


def test_a_full_row_writes_exactly_these_keys_and_no_others(tmp_path: Path) -> None:
    """The ten row keys and the four signal keys, pinned as sets. A key added
    without a decision is a schema change; a key dropped is data loss that no
    round-trip test can see, because the reader would stop looking for it at
    the same moment the writer stopped writing it.
    """
    store = tmp_path / "store.jsonl"
    m.append(store, a_full_row())

    payload = json.loads(store.read_text(encoding="utf-8"))

    assert set(payload) == {
        "document_id",
        "source_document_type",
        "processing_time_ms",
        "correctness",
        "document_score",
        "per_region_ocr",
        "per_field",
        "classification",
        "table",
        "failed_fields",
    }
    assert set(payload["per_region_ocr"][0]) == {"name", "value", "instrument", "region"}
    assert set(payload["per_field"][0]) == {"name", "value", "instrument"}


def test_a_row_read_back_and_written_again_produces_identical_bytes(
    tmp_path: Path,
) -> None:
    """Serialisation is a fixed point, not merely reversible. If reading and
    re-writing changed a single byte, a store rewritten by any maintenance step
    would stop matching the one it replaced, and no two copies of the same
    measurement could be compared by hash.
    """
    original = tmp_path / "original.jsonl"
    rewritten = tmp_path / "rewritten.jsonl"
    m.append(original, a_full_row(FIXED_DOCUMENT_ID))

    for row in m.read_all(original):
        m.append(rewritten, row)

    assert rewritten.read_bytes() == original.read_bytes()


def test_a_store_written_with_windows_line_endings_still_reads(tmp_path: Path) -> None:
    """A store that travelled through a Windows editor, or a checkout with
    `core.autocrlf`, arrives with `\\r\\n`. The rows are unchanged and must
    still be readable — refusing them would make the format depend on which
    machine last touched the file.
    """
    store = tmp_path / "store.jsonl"
    store.write_bytes(
        b"".join(
            json.dumps(a_stored_row(source_document_type=name)).encode("utf-8") + b"\r\n"
            for name in ("invoice", "receipt")
        )
    )

    read_back = m.read_all(store)

    assert [row.source_document_type for row in read_back] == ["invoice", "receipt"]


# ══════════════════════════════════════════════════════════════════════════
# THE SENTINEL
# ══════════════════════════════════════════════════════════════════════════


def test_a_fresh_absent_instance_is_neither_the_sentinel_nor_equal_to_it() -> None:
    """`AbsentType` defines no `__eq__`, so two instances compare by identity
    and a second one is a different object from `ABSENT`. That is why the
    reader returns the module-level singleton rather than constructing one, and
    why `is ABSENT` is the documented check.

    Pinned because the failure mode is silent in the other direction: if the
    reader ever returned a fresh instance, every `is m.ABSENT` assertion in the
    suite would break at once — and if `__eq__` were added without thought,
    every one of them would keep passing while `==` started disagreeing with
    `is`.
    """
    fresh = m.AbsentType()

    assert fresh is not m.ABSENT
    assert fresh != m.ABSENT
    assert m.ABSENT is m.ABSENT


def test_the_sentinel_cannot_grow_an_attribute() -> None:
    """`__slots__ = ()` is the reason, and nothing tests it. A sentinel that
    could carry state would stop being a sentinel — two ABSENTs meaning
    different things is the collapse the type exists to prevent, one level up.
    """
    attribute = "measured_after_all"

    with pytest.raises(AttributeError):
        setattr(m.ABSENT, attribute, True)
