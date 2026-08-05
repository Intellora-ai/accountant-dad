"""The measurement recorder — step 2 of the only route a threshold may take.

`ENGINE_1_CONFIDENCE_PARAMETERS.md`, "How a value gets set — the only route":

    1  ARCHITECTURE   every parameter is named, externally configured, no default
    2  MEASUREMENT    every document records: per-region OCR . per-field .
                       classification . table . document score . whether
                       extraction was ACTUALLY correct . which fields failed .
                       processing time . source document type
    3  CALIBRATION    once a validation set exists: histograms, precision vs
                       threshold, recall vs threshold, calibration curves ...
    4  FREEZE         a report per parameter, the user approves, then the
                       value is written

Steps 3 and 4 need ground truth, which is P1 and is blocked. Step 1 already
exists (`ENGINE_1_CONFIDENCE_PARAMETERS.md` itself). This module is step 2,
and step 2 has no such blocker — sixteen parameters cannot be measured into
existence without a row for every document they would apply to, and this is
where that row comes from.

IT RECORDS. IT NEVER DECIDES.
    No threshold, no pass/fail, no document score of this module's own
    invention. `document_score` is accepted and stored exactly as given,
    because `ENGINE_1_CONFIDENCE_PARAMETERS.md` #13 — how per-field scores
    combine into one document score — is not merely unset, it is one of the
    three parameters the same file calls UNDEFINED. Computing one here would
    be this module quietly making the decision the whole file says nobody
    has made yet.

    For the same reason, every numeric signal is a plain `float`, never the
    `Confidence` type from `accountant_dad.confidence`. `Confidence` asserts a
    value lies in `[0.0000, 1.0000]` — a claim about what KIND of number a
    reading is. Laplacian variance is "grey levels squared" and can exceed
    1000; an OCR score not yet calibrated may not even be a probability
    (`MEASUREMENT_FRAMEWORK.md` §10 — "until it passes this test, confidence
    is an ordinal ranking"). Typing every signal as `Confidence` would assert
    a scale nobody has measured. A plain `float` asserts nothing it cannot
    back up, which is the honest position for a module whose entire job is
    to observe rather than judge.

ABSENT, ZERO AND UNREADABLE ARE THREE STATES, NOT TWO (Law 24).
    A signal this module was never given is ABSENT — the sentinel below,
    never a number this module invented on the caller's behalf. A signal
    that was measured and came back `0.0` is ZERO, a real reading, and must
    never collapse into ABSENT or be mistaken for it. Within a named
    collection (`per_field` and the rest), one further state exists at the
    level of a single item: `NamedSignal.value=None` records that THIS named
    thing was attempted and could not be read — UNREADABLE — which is a
    different fact from the whole category never having been attempted at
    all (ABSENT), and different again from an empty tuple, which says the
    category was attempted and legitimately found nothing (there were no
    tables). Three shapes, three facts, none of them chosen by this module.

    `AbsentType.__bool__` is refused rather than answering `False`. A
    sentinel that reads as falsy invites exactly the bug this type exists to
    prevent: `if not row.document_score:` would then be true for both
    "never produced" and "measured as zero," which is the one collapse Law
    24 forbids by name. Refusing forces every reader to say which state it
    means, with `is ABSENT` or `isinstance(x, AbsentType)`.

THE CORRECTNESS LABEL DOES NOT EXIST YET, AND SAYS SO.
    "Whether extraction was ACTUALLY correct" is ground truth — P1's job,
    not this module's, and P1 has not run. `Correctness` is three states,
    never two: `CORRECT`, `WRONG`, and `UNLABELLED`, the default every row
    starts in and the only value this module ever sets on its own. A caller
    that skips it gets `UNLABELLED`, never a default that silently reads as
    a verdict this module has no authority to give.

LINE-DELIMITED JSON, READABLE WITHOUT THIS MODULE.
    One JSON object per line, `str -> object`, exactly the field names below.
    A later calibration run — pandas, jq, a spreadsheet — reads the store
    without importing anything here. `append()` opens the file, writes one
    line, and closes; there is no buffered handle for anything to hold open
    across two calls, so "append-only" is a property of what the function
    does, not a promise about how it is used (`services/audit.py` guards its
    own append-only claim the same way). `read_all()` raises loudly, naming
    the exact line, on anything that is not a row this module could have
    written — a store that quietly drops a line one document produced is a
    store lying about how many documents were measured (Law 11).

EVERY SIGNAL CARRIES ITS INSTRUMENT, AND ITS REGION WHEN IT HAS ONE.
    `ConfidenceReport.FieldConfidence` (`accountant_dad.artifacts.evidence`)
    is `(field_name, confidence)` — no slot for which tool produced the
    score, and no slot for a page region (`CONFIDENCE_SPECIFICATION.md` §3.3,
    §3.4 open item O4). Encoding either into `NamedSignal.name` would be a
    convention, and `confidence.py`'s own docstring already records what
    happened the last time this exact kind of fact was carried by convention
    instead of a structured field: it drifted, silently, until two artifact
    schemas disagreed about what the same number meant.

    So every `NamedSignal` carries `instrument`, required and never blank —
    the tool that produced the reading (PaddleOCR, the PDF text layer, the
    table-structure detector, the document-type classifier, ...) always
    exists, whatever the signal, because something always produced it. And
    every `NamedSignal` carries `region`, `str | None`, where `None` means
    the signal is not tied to one page location — a document-type
    classification score, for instance, scores the whole document, not a
    region of it — rather than "the region was not recorded." This store is
    therefore the ONLY place either fact survives at all: nothing downstream
    reconstructs an instrument or a region once a row has been written.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from accountant_dad.artifacts.evidence import DocumentId

#: The four collections a document may report, exactly as
#: `ENGINE_1_CONFIDENCE_PARAMETERS.md` step 2 names them: per-region OCR,
#: per-field, classification, table. `document_score` is a fifth, single
#: value, and is handled apart from these.
_SIGNAL_CATEGORIES: Final = ("per_region_ocr", "per_field", "classification", "table")


class AbsentType:
    """The sentinel for "this signal was never produced for this document."

    Never a number, never `None`: `None` inside a `NamedSignal` already means
    something specific (UNREADABLE — see the module docstring), and a signal
    nobody produced must never read back as a measured zero (Law 24).

    A distinct class rather than one more `None` so `isinstance` can tell the
    three states apart without relying on identity, and `__slots__ = ()`
    because a sentinel that could grow an attribute is a sentinel that could
    stop being one.
    """

    __slots__: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return "ABSENT"

    def __bool__(self) -> bool:
        raise TypeError(
            "ABSENT has no truth value. Compare with `is ABSENT` or "
            "`isinstance(x, AbsentType)` — `if not value:` is exactly the "
            "collapse into zero this type exists to prevent."
        )


#: The one instance every row uses as its default. Compared with `is`, like
#: `None` — and, unlike `None`, refusing to be mistaken for a boolean.
ABSENT: Final[AbsentType] = AbsentType()

#: What an optional row-level signal is: something supplied, or ABSENT.
NumericSignal = float | AbsentType
SignalCollection = tuple["NamedSignal", ...] | AbsentType
NameCollection = tuple[str, ...] | AbsentType


class Correctness(StrEnum):
    """Whether extraction was ACTUALLY correct. A label, never a computation.

    `UNLABELLED` is the default and the only member this module ever sets on
    its own. The other two are produced by a human comparing the extraction
    to the source document — ground truth, which is P1's job and has not
    run. Until it has, every row stays `UNLABELLED`, and `UNLABELLED` must
    never be read as `CORRECT`: that distinction is the whole value of the
    record — a system that silently treats "nobody has checked" as "this was
    right" has manufactured the ceiling it has not yet earned.
    """

    CORRECT = "correct"
    WRONG = "wrong"
    UNLABELLED = "unlabelled"


class UnrecordableMeasurementError(ValueError):
    """A row, or a signal inside one, that cannot be recorded honestly.

    Raised at construction, never at write time — a `NamedSignal` or
    `MeasurementRow` that cannot be built cannot reach the store at all,
    including a store written by code that never read this module.
    """


class MalformedMeasurementRecordError(ValueError):
    """An existing line in the store is not a row this module could have
    written. Raised naming the exact line and file, never swallowed (Law 11)
    — a store that skips a line it cannot parse is a store that has quietly
    forgotten a document was ever measured.
    """


@dataclass(frozen=True, slots=True)
class NamedSignal:
    """One named measurement inside a category, exactly as it was supplied.

    `value=None` records UNREADABLE: this named thing was attempted and no
    number came back — a different fact from its category being ABSENT (see
    `MeasurementRow`) and a different fact from a genuine `0.0`.

    `instrument` and `region` are the raw signal's provenance — see the
    module docstring's "EVERY SIGNAL CARRIES ITS INSTRUMENT" section for why
    they live here rather than being encoded into `name`.
    """

    name: str
    value: float | None
    #: The tool that produced this reading. Required: whatever the signal,
    #: something produced it, so there is never a case where this is honestly
    #: absent — unlike `region`, which some signals genuinely have none of.
    instrument: str
    #: The page region this signal was scored on, or `None` when the signal
    #: is not tied to one location. `None` is a real answer here, not a
    #: missing one — see the module docstring.
    region: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise UnrecordableMeasurementError(
                f"a signal's name must not be blank or empty; got {self.name!r}."
            )
        if not self.instrument.strip():
            raise UnrecordableMeasurementError(
                f"signal {self.name!r} carries a blank instrument. Every "
                "signal names the tool that produced it, because "
                "ConfidenceReport.FieldConfidence has no slot for one and "
                "this store is the only place the provenance survives."
            )
        if self.region is not None and not self.region.strip():
            raise UnrecordableMeasurementError(
                f"signal {self.name!r} carries a blank region. Leave it "
                "`None` when the signal is not tied to one page location, "
                "rather than asserting an empty string for it."
            )
        if self.value is not None and not math.isfinite(self.value):
            raise UnrecordableMeasurementError(
                f"signal {self.name!r} carries {self.value}, which is not a "
                "measurement (Law 24). UNREADABLE is `None`, never NaN or "
                "an infinity wearing the shape of a number."
            )


def _no_duplicate_names(category: str, signals: tuple[NamedSignal, ...]) -> None:
    names = [signal.name for signal in signals]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise UnrecordableMeasurementError(
            f"`{category}` names the same signal twice: {', '.join(duplicated)}. "
            "Two values for one name leaves no authority for which one a "
            "later calibration run should read."
        )


@dataclass(frozen=True, slots=True)
class MeasurementRow:
    """Everything `ENGINE_1_CONFIDENCE_PARAMETERS.md` step 2 asks recorded
    about one processed document. One instance is one row in the store.

    Frozen and slotted so a row cannot be corrected in place after
    construction — the store this module writes is append-only, and a
    mutable row would let something hold a reference and edit history that
    was already recorded (the same reasoning `services/audit.py` gives its
    own `Transition`).
    """

    #: `ENGINE_1_CONFIDENCE_PARAMETERS.md` step 2: "the document identifier."
    document_id: DocumentId
    #: Step 2: "source document type." Whatever the caller states it to be —
    #: this module records the claim, it does not classify the document.
    source_document_type: str
    #: Step 2: "processing time," in milliseconds.
    processing_time_ms: float
    #: Step 2: "document score." Stored VERBATIM. `#13` in
    #: `ENGINE_1_CONFIDENCE_PARAMETERS.md` is undefined — no rule anywhere
    #: produces one — so this module computes nothing and accepts whatever
    #: the caller already has, or nothing at all.
    document_score: NumericSignal = ABSENT
    #: Step 2: "per-region OCR."
    per_region_ocr: SignalCollection = ABSENT
    #: Step 2: "per-field."
    per_field: SignalCollection = ABSENT
    #: Step 2: "classification."
    classification: SignalCollection = ABSENT
    #: Step 2: "table."
    table: SignalCollection = ABSENT
    #: Step 2: "which fields failed." Names only; why they failed belongs to
    #: whichever engine produced the reading, not to this record.
    failed_fields: NameCollection = ABSENT
    #: Step 2: "whether extraction was ACTUALLY correct." See `Correctness`.
    correctness: Correctness = Correctness.UNLABELLED

    def __post_init__(self) -> None:
        if not self.source_document_type.strip():
            raise UnrecordableMeasurementError(
                "`source_document_type` must not be blank; every row states "
                "what kind of document produced it."
            )
        if not math.isfinite(self.processing_time_ms) or self.processing_time_ms < 0:
            raise UnrecordableMeasurementError(
                f"`processing_time_ms` must be a finite, non-negative number; "
                f"got {self.processing_time_ms}. Processing cannot take "
                "negative time, and a NaN or infinite duration is not a "
                "measurement (Law 24)."
            )
        if not isinstance(self.document_score, AbsentType) and not math.isfinite(
            self.document_score
        ):
            raise UnrecordableMeasurementError(
                f"`document_score` carries {self.document_score}, which is "
                "not a measurement (Law 24). Leave it ABSENT rather than "
                "assert a value that was never produced."
            )
        for category in _SIGNAL_CATEGORIES:
            signals = getattr(self, category)
            if not isinstance(signals, AbsentType):
                _no_duplicate_names(category, signals)
        if not isinstance(self.failed_fields, AbsentType):
            blank = [name for name in self.failed_fields if not name.strip()]
            if blank:
                raise UnrecordableMeasurementError(
                    "`failed_fields` must not contain a blank or empty name."
                )
            duplicated = sorted(
                {name for name in self.failed_fields if self.failed_fields.count(name) > 1}
            )
            if duplicated:
                raise UnrecordableMeasurementError(
                    f"`failed_fields` names the same field twice: {', '.join(duplicated)}."
                )


def _signal_to_json(signal: NamedSignal) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": signal.name,
        "value": signal.value,
        "instrument": signal.instrument,
    }
    if signal.region is not None:
        payload["region"] = signal.region
    return payload


def _signal_from_json(payload: object, *, line_number: int, path: Path) -> NamedSignal:
    if not isinstance(payload, dict):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path}: a signal must be a JSON object; got {payload!r}."
        )
    name = payload.get("name")
    if not isinstance(name, str):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path}: a signal's name must be a string; got {name!r}."
        )
    instrument = payload.get("instrument")
    if not isinstance(instrument, str):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path}: signal {name!r}'s instrument must "
            f"be a string; got {instrument!r}."
        )
    region = payload.get("region")
    if region is not None and not isinstance(region, str):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path}: signal {name!r}'s region must be "
            f"a string or absent; got {region!r}."
        )
    raw_value = payload.get("value")
    if raw_value is not None:
        if isinstance(raw_value, bool):
            raise MalformedMeasurementRecordError(
                f"line {line_number} of {path}: signal {name!r}'s value must "
                f"be a number, not a boolean; got {raw_value!r}."
            )
        if not isinstance(raw_value, int | float | str):
            raise MalformedMeasurementRecordError(
                f"line {line_number} of {path}: signal {name!r}'s value must "
                f"be a number, a numeric string, or null; got {raw_value!r}."
            )
    value = None if raw_value is None else float(raw_value)
    return NamedSignal(name=name, value=value, instrument=instrument, region=region)


def _category_from_json(
    payload: dict[str, object], key: str, *, line_number: int, path: Path
) -> SignalCollection:
    if key not in payload:
        return ABSENT
    items = payload[key]
    if not isinstance(items, list):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path}: {key!r} must be a JSON array; got {items!r}."
        )
    return tuple(_signal_from_json(item, line_number=line_number, path=path) for item in items)


def _row_to_json(row: MeasurementRow) -> dict[str, object]:
    payload: dict[str, object] = {
        "document_id": str(row.document_id.value),
        "source_document_type": row.source_document_type,
        "processing_time_ms": row.processing_time_ms,
        "correctness": row.correctness.value,
    }
    if not isinstance(row.document_score, AbsentType):
        payload["document_score"] = row.document_score
    for category in _SIGNAL_CATEGORIES:
        signals = getattr(row, category)
        if not isinstance(signals, AbsentType):
            payload[category] = [_signal_to_json(signal) for signal in signals]
    if not isinstance(row.failed_fields, AbsentType):
        payload["failed_fields"] = list(row.failed_fields)
    return payload


def _row_from_json(payload: object, *, line_number: int, path: Path) -> MeasurementRow:
    if not isinstance(payload, dict):
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path} is not a JSON object; got {payload!r}."
        )
    try:
        document_id = DocumentId(uuid.UUID(str(payload["document_id"])))
        source_document_type = str(payload["source_document_type"])
        processing_time_ms = float(payload["processing_time_ms"])
        correctness = Correctness(payload["correctness"])
        document_score: NumericSignal = ABSENT
        if "document_score" in payload:
            document_score = float(payload["document_score"])
        per_region_ocr = _category_from_json(
            payload, "per_region_ocr", line_number=line_number, path=path
        )
        per_field = _category_from_json(payload, "per_field", line_number=line_number, path=path)
        classification = _category_from_json(
            payload, "classification", line_number=line_number, path=path
        )
        table = _category_from_json(payload, "table", line_number=line_number, path=path)
        failed_fields: NameCollection = ABSENT
        if "failed_fields" in payload:
            raw_failed = payload["failed_fields"]
            if not isinstance(raw_failed, list):
                raise MalformedMeasurementRecordError(
                    f"line {line_number} of {path}: 'failed_fields' must be a "
                    f"JSON array; got {raw_failed!r}."
                )
            failed_fields = tuple(str(item) for item in raw_failed)
        return MeasurementRow(
            document_id=document_id,
            source_document_type=source_document_type,
            processing_time_ms=processing_time_ms,
            document_score=document_score,
            per_region_ocr=per_region_ocr,
            per_field=per_field,
            classification=classification,
            table=table,
            failed_fields=failed_fields,
            correctness=correctness,
        )
    except MalformedMeasurementRecordError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MalformedMeasurementRecordError(
            f"line {line_number} of {path} is not a recordable measurement row: {exc}"
        ) from exc


def append(path: Path, row: MeasurementRow) -> None:
    """Add one row to the store at `path`. Creates the file if it is new.

    Opens in append mode and closes immediately: there is no handle this
    function keeps open across two calls, so nothing here could overwrite a
    line already written, by construction rather than by care.
    """
    line = json.dumps(_row_to_json(row), ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_all(path: Path) -> tuple[MeasurementRow, ...]:
    """Every row recorded at `path`, in the order recorded.

    A line that is not valid JSON, or not a row this module could have
    written, raises `MalformedMeasurementRecordError` naming the exact line —
    never skipped, never silently dropped (Law 11).
    """
    rows: list[MeasurementRow] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                payload: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MalformedMeasurementRecordError(
                    f"line {line_number} of {path} is not valid JSON: {exc}"
                ) from exc
            rows.append(_row_from_json(payload, line_number=line_number, path=path))
    return tuple(rows)
