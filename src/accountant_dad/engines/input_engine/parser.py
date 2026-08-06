"""Engine 1's `parser` sub-engine — structure, and nothing that means anything.

`SUB_ENGINE_RESPONSIBILITIES.md` 1.3: *"Owns the conversion of extracted
information into structure — fields, key-value pairs, tables, and line-item
rows — faithful to how the document is laid out."* Its boundary is one
sentence long and the whole module is built around it: *"Cannot decide business
meaning — it may identify a field labelled 'Supplier', it may not conclude that
party is a supplier for accounting purposes."*

So this module returns WHERE things are and HOW they are arranged. Never what
they are for. A `Cell` knows its row, its column, its page and its box; it does
not know it holds a tax rate, and there is deliberately nowhere to put that.

TOOLS, AND WHY EACH IS USED FOR EXACTLY ONE THING (`TECHNOLOGY_STACK.md`).
    Docling      "document parsing and structure"
    Table Transformer (Microsoft)   "table structure detection"

    Both are named for Engine 1 and neither is substituted. Camelot, Tabula and
    Unstructured are on that document's explicitly-not-approved list and are
    not imported here.

TABLE TRANSFORMER MAY REFINE A TABLE. IT MAY NEVER CREATE ONE.
    Measured in this worktree on 2026-08-05, with
    `microsoft/table-transformer-detection` at threshold 0.7:

        a page carrying three text lines and NO table  ->  2 tables reported
                                                           (0.7002, 0.8646)
        a completely BLANK A4 page                     ->  1 table reported
                                                           (0.8813), and the
                                                           structure model then
                                                           found a row and a
                                                           column inside it

    A detector that reports a table on an empty page at 0.88 cannot be given
    the power to add one, because no threshold separates that from a true
    positive on a poor scan. `ENGINE_1_INPUT_ENGINE_RULES.md:337` — *"When
    information is unclear, the system must report uncertainty. It must never
    invent information."* The detection model is therefore not used at all. The
    STRUCTURE model runs only inside a region Docling already located, which is
    also exactly the capability `TECHNOLOGY_STACK.md` assigns it: table
    structure detection, not table detection.

EVERY NUMBER THIS MODULE WOULD HAVE NEEDED IS THE CALLER'S.
    Table Transformer cannot run without a render resolution, a score
    threshold and a crop margin. No document in this repository states any of
    them. `TECHNOLOGY_STACK.md` records the one comparable number — the OCR
    fallback threshold — as *"UNKNOWN - REQUIRES A NUMBER FROM THE OWNER"*, and
    Law 52 forbids inventing the rest. `TableStructureSettings` therefore has
    no defaults, and `parse` defaults to not running the model at all rather
    than to running it with a number nobody set.

THREE STATES, KEPT APART (`ENGINE_1_INPUT_ENGINE_RULES.md:569`).
    Docling emits `""` for a grid position it read no text in. That is not the
    same as a read empty value, and it is not the same as unreadable — and
    Docling cannot tell those apart either. `""` therefore becomes `None`, "no
    text was reported here", because `""` would assert a reading that was never
    made. `"0"` stays `"0"`.

CONFIDENCE IS NOT PRODUCED HERE, AT ALL.
    `ENGINE_1_INPUT_ENGINE_RULES.md:109` — *"`cleaner`, `reader` and `parser`
    emit SIGNALS. Only `confidence` turns signals into scores."* A detector's
    own score travels on `Band.score` as a plain float, deliberately NOT as
    `accountant_dad.confidence.Confidence`: a value of that type would look
    like a confidence score this sub-engine had no authority to produce.

WHICH FIELDS A DOCUMENT MUST CARRY IS KNOWLEDGE, AND IT IS NOT HELD HERE.
    CGST Rules 46-55 name 86 mandatory particulars for a tax invoice, one per
    file in `Accounting_Brain/Validation_Library/`. The parser is given no
    expected-field list and hard-codes none, so `missing_field_information`
    reports nothing absent and says why. Comparing a document against a
    statutory list is applying an accounting rule inside extraction, which
    `ENGINE_1_INPUT_ENGINE_RULES.md:558-562` forbids outright.

    What the output does instead is make those particulars LOCATABLE: page
    regions carry the header and footer text where rule 46(a)-(f), (n)-(p) sit;
    table cells carry a row index, a column index and a header flag, which is
    what lets a downstream engine find the column under `HSN` for rule 46(g)
    without this module ever deciding that the column means that.

WHERE THIS DEPARTS FROM THE LOCKED SPECIFICATION, STATED NOT HIDDEN.
    `SUB_ENGINE_RESPONSIBILITIES.md` 1.3 gives the parser one input: *"Raw
    extracted information with source locations from `reader`."* `parse` also
    opens the artifact itself, to recover its LAYOUT. That is still a real
    departure and it still has a real consequence: the text on a `Cell` or a
    `Region` here was produced by Docling, not by `reader`, so this module is
    still doing a part of `reader`'s job as well as its own.

    It must not stay that way. `ENGINE_1_INPUT_ENGINE_RULES.md:113` — *"`parser`
    consumes `reader`'s extraction; it cannot re-read it."* Text must come from
    `reader`'s spans and this module must keep only the geometry, so that no
    reading has two authors. The seam is small on purpose: every text value in
    the LAYOUT output passes through `reported_text`, and the only caller of it
    is `_convert`.

    The half that IS now built is the input arrow: `parse` accepts
    `ExtractedRegion`s — reader's extraction, with its source locations — and
    maps each into a named `MappedField`. See FIELD MAPPING below.

FIELD MAPPING, AND THE NAME THIS MODULE IS ALLOWED TO ASSIGN.
    §1.3's output is *"structured fields · field mappings · missing field
    information"*, and its Failure Behaviour is explicit about what a mapping
    must keep: *"Field mappings retain the source reference for every mapped
    value, so a wrong mapping can be traced."* `MappedField` is that mapping.
    One per `ExtractedRegion`, in reader's own order, with reader's text
    verbatim, reader's location as the source reference, and reader's own
    extraction-confidence SIGNAL carried through untouched — never produced
    here (`ENGINE_1_INPUT_ENGINE_RULES.md:109`, and see CONFIDENCE IS NOT
    PRODUCED HERE above; carrying a number `reader` measured is the opposite of
    minting one, and `confidence_report.ParsedField` already models exactly
    this hand-off).

    THE NAME IS THE PLACE, AND DELIBERATELY NOTHING MORE. `_field_name` returns
    `page {p} region {n}` — reader's own page and reader's own order within
    that page. It is a locator, so it cannot be wrong about the business, which
    is the whole of §1.3's boundary: *"it may identify a field labelled
    'Supplier', it may not conclude that party is a supplier."*

    WHY DOCLING'S LAYOUT LABEL IS NOT USED AS THE NAME, MEASURED RATHER THAN
    ASSUMED. On the two-page fixture in `tests/integration/`, reader reports
    five spans and Docling reports three layout regions; the three spans on
    page 1 all fall inside ONE `section_header`. So the label is many-to-one
    and cannot name a field uniquely — and `StructuredDocument` refuses two
    detected fields sharing a name. Worse, attaching the label at all needs a
    box-to-box test, and the boxes do not nest: reader's first span on page 1
    spans top 76.025 to 93.887 while Docling's region containing it starts at
    80.666. Any rule joining them needs an overlap tolerance, and no document
    in this repository states one, so choosing one would be exactly the
    invented number Law 52 and Law 54 forbid. The layout label is therefore
    reported in full through `Region`, where it belongs, and is not smuggled
    into a field name it cannot support.

A TABLE CELL'S TEXT IS A VALUE, AND IT USED TO LEAVE HERE WITHOUT AN ORIGIN.
    THE DIAGNOSIS, and it is not the one the shape of the problem suggests. A
    `Cell` has ALWAYS carried its `box` — where on the page it was read — so
    the location was never missing. What was missing is a NAME. Every route
    out of Engine 1 that attaches a provenance to a value is keyed by name:
    `MappedField.name` becomes `DetectedField.name`, and `DetectedField.name`
    is what the Confidence Report files a reliability entry under
    (`ENGINE_1_INPUT_ENGINE_RULES.md:599-601`). A value with no name has
    nowhere for its origin to be filed, so it could only cross the Input →
    Understanding boundary the way it did: flattened into `extracted_text` as
    a bare string, stripped of the source, confidence and uncertainty that
    `COMMUNICATION_RULES_INPUT_ENGINE.md:113-119` says *"travel with the value
    permanently."*

    `map_cells` supplies the missing name and nothing else. Every cell that
    carries text becomes a `MappedField` on exactly the same terms a text
    region does — Docling's text verbatim, the cell's own box as the source
    reference, and `extraction_confidence` left exactly as Docling reported
    it, which is nothing at all. So a cell's provenance now identifies where
    on the page it came from by travelling the SAME road a text region's
    does, rather than by a second mechanism that would drift from it (Law 14,
    Law 15).

    NO CONFIDENCE IS INVENTED FOR A CELL, AND NONE COULD BE. Docling emits no
    per-cell score, so `extraction_confidence` is `None` — the absence of a
    measurement, carried verbatim, exactly as it is for a region `reader` did
    not score. What that absence MEANS is not decided here: this sub-engine
    emits signals and only `confidence` turns a signal into a state
    (`ENGINE_1_INPUT_ENGINE_RULES.md:109`). See CONFIDENCE IS NOT PRODUCED
    HERE above.

    A GRID POSITION WITH NO TEXT IS NOT MAPPED, AND IS NOT LOST EITHER. No
    value crosses the boundary from it, so there is nothing for a name or an
    origin to be about, and inventing an empty `MappedField` would assert a
    reading that was never made (the same rule `reported_text` applies). The
    position itself is still reported in full, as a `Cell` with `text=None`
    inside `ParsedStructure.tables` — where its row, its column and its box
    all survive. Absence stays visible; it simply is not a value.

    THE NAME IS THE PLACE, AGAIN, AND UNIQUE BY CONSTRUCTION. `_cell_name`
    returns `page {p} table {t} cell {n} (row {r}, column {c})`. `n` counts
    within the table in the detector's own order, which is what makes two
    names impossible to collide — the same guarantee `map_fields` gets from
    its per-page ordinal, and it matters because `ParsedStructure`,
    `StructuredDocument` and `ConfidenceReport` all refuse a repeated name
    rather than silently picking one. The row and column ride along because a
    human looking for the cell reads a grid, not an ordinal; neither says
    what the cell MEANS, so §1.3's boundary is untouched.
"""

from __future__ import annotations

import functools
import hashlib
import importlib
import importlib.metadata
import math
import os
import pathlib
import shlex
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal
    from pathlib import Path

#: The one Table Transformer checkpoint used. The DETECTION checkpoint,
#: `microsoft/table-transformer-detection`, is deliberately absent — see the
#: module docstring for the measurement that ruled it out.
TABLE_STRUCTURE_MODEL = "microsoft/table-transformer-structure-recognition"

DOCLING = "docling"
TABLE_TRANSFORMER = f"table-transformer:{TABLE_STRUCTURE_MODEL}"

_BOTTOM_LEFT = "BOTTOMLEFT"
_TOP_LEFT = "TOPLEFT"
_POINTS_PER_INCH = 72.0

#: The only conversion status that needs no further argument. Docling declares
#: six — PENDING · STARTED · FAILURE · SUCCESS · PARTIAL_SUCCESS · SKIPPED —
#: read off the installed library rather than remembered.
_SUCCESS = "SUCCESS"
#: Converted with reservations. NOT accepted on the status alone: the required
#: output is checked for real, and only a document that actually carries pages
#: continues. See `_convert`.
_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

#: Distributions that can provide the `docling` module. `docling` is a
#: meta-package and the import is served by `docling-slim` — measured on both
#: this machine and a CI runner, where the pin check prints
#: `docling version=2.118.0 pin=2.118.0 ok (delegated to ['docling-slim'])`.
#: A diagnosis that reported only one of them would omit the one that shipped
#: the code that failed.
_DOCLING_DISTRIBUTIONS = ("docling", "docling-slim", "docling-core", "docling-ibm-models")


class ParserError(Exception):
    """Anything this sub-engine refuses to do quietly."""


class ImpossibleSettingError(ValueError):
    """A setting Table Transformer or arithmetic cannot honour. Raised at construction.

    Named and raised the same way `cleaner.ImpossibleSettingError` is, for the
    same reason: a caller that wants to distinguish "you gave me a number that
    cannot be honoured" from every other `ValueError` a dataclass might raise
    needs a name to catch, not a string to grep.
    """


class ParserDependencyMissingError(ParserError):
    """A named tool is not installed. Named, so the fix is obvious."""

    def __init__(self, module_name: str) -> None:
        super().__init__(
            f"the parser needs {module_name!r} and it is not installed. It is an "
            "approved Engine 1 tool (TECHNOLOGY_STACK.md) that requirements-ci.txt "
            "does not carry, so it must be installed before this path can run."
        )
        self.module_name = module_name


class DocumentUnreadableError(ParserError):
    """The artifact could not be parsed at all, and the reason is carried.

    Raised rather than smoothed over. The Input Engine PARENT is what must not
    halt the pipeline (`COMMUNICATION_RULES_INPUT_ENGINE.md:159`); it converts
    this into low confidence and a named uncertainty. The parser cannot do that
    itself, because only the `confidence` sub-engine may produce a score
    (`ENGINE_1_INPUT_ENGINE_RULES.md:109`).
    """

    def __init__(self, source: str, reasons: tuple[str, ...]) -> None:
        detail = " | ".join(reasons) if reasons else "no reason was reported"
        super().__init__(f"{source} could not be parsed: {detail}")
        self.source = source
        self.reasons = reasons


@functools.cache
def require_module(module_name: str) -> ModuleType:
    """Import an optional tool, or say which one is missing.

    Imported by name rather than by statement so that `mypy` and `pytest` run
    in an environment without Engine 1's parsing stack — which is what CI is
    today — instead of failing on an import of something that is not there.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise ParserDependencyMissingError(module_name) from exc


def _reject_blank(value: str, what: str) -> None:
    if not value.strip():
        raise ValueError(f"{what} must not be empty or blank")


def reported_text(raw: str) -> str | None:
    """A detector's raw string, or `None` when it reported nothing at all.

    The one place any text in the output is decided, and it is a pure function
    so the rule can be tested without loading a model.

    `""` never survives. Downstream, `""` reads as A VALUE THAT WAS READ AND
    WAS EMPTY, and no detector here can tell that apart from "no text was
    reported" — `ENGINE_1_INPUT_ENGINE_RULES.md:569` keeps ABSENT, ZERO and
    UNREADABLE as three states, and collapsing two of them is invisible by the
    time anything downstream could object. `"0"` is a read zero and is kept
    exactly.
    """
    text = raw.strip()
    return text or None


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Where on the page, in PDF points, with the origin at the page's TOP-LEFT.

    One origin, always. Docling reports table cells top-left and page items
    bottom-left in the same document, and a mixed convention crossing an engine
    boundary is a location that silently means two things.

    `float`, not `Decimal`: this is a detector's estimate of where ink sits, and
    `Decimal` would dress a measurement up as an exact quantity. `Decimal` is
    reserved for money and for `Confidence`, neither of which is produced here.
    """

    page: int
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError(f"bounding box page must be 1 or greater, got {self.page}")
        for name, value in (
            ("left", self.left),
            ("top", self.top),
            ("right", self.right),
            ("bottom", self.bottom),
        ):
            if not math.isfinite(value):
                raise ValueError(f"bounding box {name} must be finite, got {value!r}")
            if value < 0:
                raise ValueError(f"bounding box {name} must not be negative, got {value!r}")
        # Degenerate is allowed — a detector really does emit a zero-width box,
        # and refusing it would drop evidence. Inverted is refused: it cannot be
        # true, and a location that cannot be true still looks traceable.
        if self.right < self.left:
            raise ValueError(f"bounding box right {self.right} is left of left {self.left}")
        if self.bottom < self.top:
            raise ValueError(f"bounding box bottom {self.bottom} is above top {self.top}")


def _to_top_left_box(
    edges: tuple[float, float, float, float],
    *,
    page: int,
    page_height: float,
    origin: str,
) -> BoundingBox:
    """`edges` are the detector's (left, top, right, bottom) in its own origin.

    `origin` is whatever the detector's own enum stringifies to, which is
    `CoordOrigin.BOTTOMLEFT` on one Docling version and `BOTTOMLEFT` on
    another. Both are read, because getting this wrong is silent: a
    bottom-left box misread as top-left still validates, still looks like a
    location, and points at the wrong part of the page.
    """
    left, top, right, bottom = edges
    token = origin.rsplit(".", 1)[-1].upper().replace("_", "").replace("-", "")
    if token == _BOTTOM_LEFT:
        top, bottom = page_height - top, page_height - bottom
    elif token != _TOP_LEFT:
        raise ValueError(
            f"unknown coordinate origin {origin!r}. Refused rather than assumed: "
            "guessing wrong produces a location that validates and is wrong."
        )
    return BoundingBox(page=page, left=left, top=top, right=right, bottom=bottom)


@dataclass(frozen=True, slots=True)
class Cell:
    """One grid position, and the text the detector reported in it.

    Row and column indices are half-open — `row_start` inclusive, `row_end`
    exclusive — so a cell spanning two rows says so instead of being duplicated.
    """

    text: str | None
    row_start: int
    row_end: int
    column_start: int
    column_end: int
    is_column_header: bool
    is_row_header: bool
    box: BoundingBox

    def __post_init__(self) -> None:
        if self.text is not None:
            _reject_blank(self.text, "cell text (use None for 'no text reported')")
        for name, start, end in (
            ("row", self.row_start, self.row_end),
            ("column", self.column_start, self.column_end),
        ):
            if start < 0:
                raise ValueError(f"cell {name} span must start at 0 or later, got {start}")
            if end <= start:
                raise ValueError(f"cell {name} span {start}..{end} covers no grid position")


@dataclass(frozen=True, slots=True)
class Band:
    """One row, column or header strip a table-structure detector reported.

    `score` is the detector's own number, carried verbatim. It is NOT a
    `Confidence`: only the `confidence` sub-engine may produce one of those
    (`ENGINE_1_INPUT_ENGINE_RULES.md:109`), and typing it as one here would
    smuggle a score past that authority.
    """

    label: str
    score: float
    box: BoundingBox

    def __post_init__(self) -> None:
        _reject_blank(self.label, "band label")
        if not math.isfinite(self.score):
            raise ValueError(f"band score must be finite, got {self.score!r}")


@dataclass(frozen=True, slots=True)
class Table:
    """A grid the document draws. Which grid position holds what, never why."""

    detector: str
    box: BoundingBox
    row_count: int
    column_count: int
    cells: tuple[Cell, ...]
    bands: tuple[Band, ...] = ()

    def __post_init__(self) -> None:
        _reject_blank(self.detector, "table detector")
        if self.row_count < 0 or self.column_count < 0:
            raise ValueError(f"table shape {self.row_count}x{self.column_count} is impossible")
        for cell in self.cells:
            if cell.row_end > self.row_count or cell.column_end > self.column_count:
                raise ValueError(
                    f"a cell spans to row {cell.row_end}, column {cell.column_end}, "
                    f"outside the {self.row_count}x{self.column_count} grid it belongs to"
                )


@dataclass(frozen=True, slots=True)
class Region:
    """One laid-out area of the page — a paragraph, a heading, a picture.

    `label` is the detector's own structural vocabulary, verbatim, and it says
    how the area is SET, not what it is about. `text` is `None` when the region
    carries no text at all: a signature block or a QR code is a region with a
    location and nothing to read, and dropping it would lose the only evidence
    that the mark is on the page.
    """

    label: str
    text: str | None
    box: BoundingBox
    detector: str

    def __post_init__(self) -> None:
        _reject_blank(self.label, "region label")
        _reject_blank(self.detector, "region detector")
        if self.text is not None:
            _reject_blank(self.text, "region text (use None for 'no text reported')")


@dataclass(frozen=True, slots=True)
class ExtractedRegion:
    """§1.3's INPUT, one region of it: *"Raw extracted information with source
    locations from `reader`."*

    Declared here rather than imported from `reader`, for the reason
    `confidence_report.RegionReading` gives about the identical hand-off: this
    is read off §1.2's OUTPUT prose — *"raw extracted information · source
    locations · extraction confidence"* — so the two sub-engines stay
    independently replaceable (`CLAUDE.md` Law 21) and neither acquires the
    other's dependencies. `pipeline` maps `reader.TextRegion` onto this, in one
    place, exactly as it already maps it onto `RegionReading`.

    `box` reuses this module's own `BoundingBox` rather than a second geometry
    type (Law 15). Note the unit: `BoundingBox.page` is the 1-based page NUMBER
    and `reader.SourceLocation.page_index` is 0-based; the conversion is
    `pipeline`'s, made once, and is not repeated here.

    `extraction_confidence` is `reader`'s own signal or `None` when the backend
    performed no recognition and therefore reported no score. `None` is not
    zero and not full — it is the absence of a measurement, and only
    `confidence` may decide what that is worth (`ENGINE_1_INPUT_ENGINE_RULES.md
    :109`). Nothing in this module reads its value; it is carried.
    """

    text: str
    box: BoundingBox
    extraction_confidence: Decimal | None

    def __post_init__(self) -> None:
        # The same rule `reported_text` applies to a laid-out region, applied to
        # an incoming one: a blank string would assert a reading that was never
        # made, and ABSENT and READ-AND-EMPTY must stay distinguishable
        # (`ENGINE_1_INPUT_ENGINE_RULES.md:569`). `reader` never emits one — it
        # skips whitespace-only spans — so this refuses a caller's mistake, not
        # a document's.
        _reject_blank(self.text, "extracted region text")


@dataclass(frozen=True, slots=True)
class MappedField:
    """One value `reader` extracted, named by `parser`, keeping where it came from.

    §1.3's *"field mappings"*, and its Failure Behaviour's requirement that they
    *"retain the source reference for every mapped value, so a wrong mapping can
    be traced."* `source_location` is that retained reference — where WITHIN the
    artifact, which is a different fact from `ParsedStructure.source_reference`,
    which names WHICH artifact.

    `value` is `reader`'s text, character for character. `extraction_confidence`
    is `reader`'s signal, carried through unchanged — see FIELD MAPPING in the
    module docstring, and `confidence_report.ParsedField`, which is the shape
    this one feeds and which already documents the same hand-off.
    """

    name: str
    value: str
    source_location: str
    extraction_confidence: Decimal | None

    def __post_init__(self) -> None:
        _reject_blank(self.name, "mapped field name")
        _reject_blank(self.value, "mapped field value")
        _reject_blank(self.source_location, "mapped field source location")


def _field_name(page: int, ordinal: int) -> str:
    """The name `parser` assigns one mapped value: where it is, and nothing else.

    A locator cannot be wrong about the business, which is precisely §1.3's
    boundary. See WHY DOCLING'S LAYOUT LABEL IS NOT USED AS THE NAME in the
    module docstring for the measurement that ruled the richer name out.
    """
    return f"page {page} region {ordinal}"


def _cell_name(page: int, table_ordinal: int, cell_ordinal: int, cell: Cell) -> str:
    """The name `parser` assigns one mapped CELL: where it is, and nothing else.

    The ordinal is what guarantees uniqueness — two cells cannot share a name
    however the detector numbers its grid — and the row and column are what a
    human reads to find the cell on the page. Neither is a claim about what
    the cell holds, which is §1.3's whole boundary.

    Half-open spans are reported by their START, the corner a reader looks at.
    The full span survives on the `Cell` itself, which is also where a spanning
    cell's `row_end` and `column_end` are, so nothing is lost by not repeating
    them in a locator.

    `page` IS THE CELL'S OWN PAGE, NEVER THE TABLE'S — found by red-team, and
    the difference is silent exactly when it matters. A table crossing a page
    break has cells on two pages while its own outline reports one, so naming
    them by the table's page would make the name and the `source_location`
    beside it point at different pages, and the name is the one a human reads
    first.
    """
    return (
        f"page {page} table {table_ordinal} cell {cell_ordinal} "
        f"(row {cell.row_start}, column {cell.column_start})"
    )


def map_cells(tables: tuple[Table, ...]) -> tuple[MappedField, ...]:
    """One `MappedField` per table cell that carries text, in the detector's order.

    See A TABLE CELL'S TEXT IS A VALUE in the module docstring for what this
    fixes and why it fixes it by supplying a NAME rather than a location — the
    location was always there.

    A pure function of `parse`'s own already-built structure, for the reason
    `map_fields` and `reported_text` are pure: the mapping is then testable
    without a document and without a model.

    Cells with no text are skipped and NOT dropped: they remain in
    `ParsedStructure.tables` with their row, column and box intact. Nothing is
    sorted, merged or renumbered — a mapping that lost a cell would lose the
    only evidence the cell was ever read.
    """
    mapped: list[MappedField] = []
    for table_index, table in enumerate(tables, start=1):
        for cell_index, cell in enumerate(table.cells, start=1):
            if cell.text is None:
                continue
            mapped.append(
                MappedField(
                    name=_cell_name(cell.box.page, table_index, cell_index, cell),
                    value=cell.text,
                    source_location=repr(cell.box),
                    extraction_confidence=None,
                )
            )
    return tuple(mapped)


def map_fields(regions: tuple[ExtractedRegion, ...]) -> tuple[MappedField, ...]:
    """One `MappedField` per extracted region, in `reader`'s own order.

    A pure function of `reader`'s output, so the mapping is testable without a
    document and without a model — the same reason `reported_text` is separate.

    `ordinal` counts within a page rather than across the document, because the
    page is where a human looking for the value will start. Nothing is sorted,
    merged, split or dropped: §1.2 forbids reordering, and a mapping that lost a
    region would lose the only evidence the region was ever read.
    """
    ordinals: dict[int, int] = {}
    mapped: list[MappedField] = []
    for region in regions:
        page = region.box.page
        ordinal = ordinals.get(page, 0) + 1
        ordinals[page] = ordinal
        mapped.append(
            MappedField(
                name=_field_name(page, ordinal),
                value=region.text,
                source_location=repr(region.box),
                extraction_confidence=region.extraction_confidence,
            )
        )
    return tuple(mapped)


@dataclass(frozen=True, slots=True)
class MissingFieldInformation:
    """What the parser can say about absence, which here is nothing, plus why."""

    absent_fields: tuple[str, ...]
    basis: str


#: The only value this module ever produces for missing fields. Absence is
#: knowable only against a list of what was expected, and this sub-engine is
#: given none — see the module docstring.
NO_EXPECTED_FIELD_LIST_WAS_SUPPLIED = MissingFieldInformation(
    absent_fields=(),
    basis=(
        "no expected-field list was supplied to `parser`, and it holds none. Which "
        "particulars a document must carry is knowledge — CGST Rules 46 to 55 name "
        "86 of them for a tax invoice — and knowledge is not this sub-engine's "
        "(SUB_ENGINE_RESPONSIBILITIES.md 1.3). Reporting a field as absent would "
        "mean applying an accounting rule inside extraction, which "
        "ENGINE_1_INPUT_ENGINE_RULES.md:558-562 forbids. Nothing is reported "
        "absent here; nothing is reported present either."
    ),
)


@dataclass(frozen=True, slots=True)
class TableStructureSettings:
    """The three numbers Table Transformer needs, all of them the caller's.

    None of them has a default, and that is the point. No document in this
    repository states any of them, so a default would be this module choosing a
    number nobody agreed (Law 52). Passing this object at all is the caller
    asserting ownership of all three.
    """

    #: Page render resolution. Table Transformer sees pixels, not text.
    render_dots_per_inch: float
    #: Below this the detector's row/column proposals are dropped, unseen.
    structure_score_threshold: float
    #: How far outside the located table to crop. The model was trained on
    #: table crops carrying some surrounding margin.
    crop_padding_points: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.render_dots_per_inch) and self.render_dots_per_inch > 0):
            raise ImpossibleSettingError(
                f"render_dots_per_inch must be a positive finite number, "
                f"got {self.render_dots_per_inch!r}"
            )
        if not 0.0 <= self.structure_score_threshold <= 1.0:
            raise ImpossibleSettingError(
                f"structure_score_threshold must be within [0.0, 1.0], "
                f"got {self.structure_score_threshold!r}"
            )
        if not (math.isfinite(self.crop_padding_points) and self.crop_padding_points >= 0):
            raise ImpossibleSettingError(
                f"crop_padding_points must be a non-negative finite number, "
                f"got {self.crop_padding_points!r}"
            )


@dataclass(frozen=True, slots=True)
class ParsedStructure:
    """What `parser` hands the Input Engine: the document's shape, and its own limits.

    A component of the Structured Document, never the artifact's name — the
    artifact is the Document Evidence Object and only the parent assembles it
    (`ENGINE_1_INPUT_ENGINE_RULES.md:257`).
    """

    source_reference: str
    page_count: int
    regions: tuple[Region, ...]
    tables: tuple[Table, ...]
    missing_field_information: MissingFieldInformation = NO_EXPECTED_FIELD_LIST_WAS_SUPPLIED
    #: Which table-structure detector ran, or `None` because the caller supplied
    #: none of the numbers it needs. Recorded rather than implied: "no bands"
    #: and "the detector was never run" are different facts.
    table_structure_detector: str | None = None
    #: §1.3's *"field mappings"* — one per region `reader` extracted, followed
    #: by one per table cell that carries text, or empty because `parse` was
    #: given no extraction to map and found no table. Regions and cells share
    #: this one collection deliberately: both are values read off the artifact
    #: that need a name so an origin can be filed against it, and a second
    #: collection would be a second road to the same destination, free to drift
    #: from this one (Law 14). Last in the field order deliberately: every
    #: earlier position is one an existing caller may already be filling
    #: positionally, and inserting into that order would silently rebind their
    #: arguments (Law 33).
    mapped_fields: tuple[MappedField, ...] = ()

    def __post_init__(self) -> None:
        _reject_blank(self.source_reference, "source reference")
        if self.page_count < 0:
            raise ValueError(f"page count cannot be negative, got {self.page_count}")
        names = [field.name for field in self.mapped_fields]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            # `StructuredDocument` keys detected fields by name and
            # `ConfidenceReport` keys scores by name, so two mappings sharing one
            # name make "which score belongs to which value?" unanswerable. Both
            # of those schemas already refuse it; refusing here too means the
            # caller learns which SUB-ENGINE produced the collision, at the point
            # it was produced, rather than three hops later.
            raise ValueError(
                f"two mapped fields share one name: {', '.join(duplicated)}. "
                "A field name is the key a confidence score is filed under, so a "
                "repeated name makes traceability unanswerable."
            )


@dataclass(frozen=True, slots=True)
class _Conversion:
    """Docling's result, reduced to primitives before anything else touches it."""

    page_count: int
    page_heights: dict[int, float]
    regions: list[Region] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)


def _running_environment(source: Path) -> tuple[str, ...]:
    """Everything about THIS PROCESS that could make one machine differ from
    another, gathered only when a conversion has already failed.

    ── WHY THIS EXISTS ──

    A conversion failed on CI and nowhere else. Three hypotheses were
    investigated and refuted — a missing `also_copy` file, `docling-slim`, the
    mutmut trampolines — using information that could have been printed at the
    moment of failure. `KNOWN_FAILURES.md` F-029 records the cost. The rule this
    encodes: **when a failure cannot be reproduced locally, the failure itself
    must carry enough to identify the environment that produced it.**

    STDLIB ONLY, AND NO SUBPROCESS. A sub-engine that shells out to `git` to
    describe itself is a sub-engine with a new dependency and a new failure
    mode, on the path that is already failing. The commit therefore comes from
    the environment variable GitHub Actions sets, and says so plainly when it is
    absent rather than inventing one (Law 24).

    Only ever called on a failure path, so it costs nothing in normal running.
    """
    versions = []
    for distribution in _DOCLING_DISTRIBUTIONS:
        try:
            versions.append(f"{distribution}=={importlib.metadata.version(distribution)}")
        except importlib.metadata.PackageNotFoundError:
            versions.append(f"{distribution}=ABSENT")

    try:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        size = source.stat().st_size
        document_bytes = f"sha256={digest} size={size}B"
    except OSError as exc:
        document_bytes = f"UNREADABLE at diagnosis time: {type(exc).__name__}: {exc}"

    return (
        f"commit={os.environ.get('GITHUB_SHA') or 'UNKNOWN (GITHUB_SHA is not set)'}",
        f"python={sys.version.replace(chr(10), ' ')}",
        f"docling distributions={', '.join(versions)}",
        # Under mutation this names the mutmut runner, which is the whole point:
        # it distinguishes a mutation run from a plain pytest run in the record.
        f"command={shlex.join(sys.argv)}",
        f"cwd={pathlib.Path.cwd()}",
        f"input {document_bytes}",
    )


def _conversion_diagnosis(
    source: Path, result: object, status: str, problem: str
) -> tuple[str, ...]:
    """Every fact Docling reported about a conversion that cannot be used.

    NOTHING IS TRUNCATED AND NOTHING IS SUMMARISED. Each `ErrorItem` is rendered
    with all five fields the installed library declares — `component_type`,
    `module_name`, `category`, `error_message`, `page_no` — because the previous
    version kept `error_message` alone and threw the rest away, and "which
    component" was exactly the question that could not be answered afterwards.

    An EMPTY error list is itself reported. Docling can end a conversion with a
    non-success status and no `ErrorItem` at all, and silence there is what
    produced a failure whose only account of itself was the stage it stopped in.
    """
    errors = getattr(result, "errors", None) or []
    document = getattr(result, "document", None)

    rendered: list[str] = []
    for index, error in enumerate(errors):
        fields = " ".join(
            f"{name}={_enum_name(getattr(error, name, None))!r}"
            for name in ("component_type", "module_name", "category", "page_no")
        )
        rendered.append(
            f"error[{index}] {fields} message={getattr(error, 'error_message', None)!r}"
        )
    if not rendered:
        rendered.append(
            "docling reported NO ErrorItem at all. The status alone is the whole "
            "of what it said, which is why the status alone is not accepted here."
        )

    return (
        f"docling conversion is unusable: {problem}",
        f"status={status}",
        f"document_present={document is not None}",
        f"error_count={len(errors)}",
        *rendered,
        *_running_environment(source),
    )


def _enum_name(value: object) -> object:
    """An enum's `name` if it has one, else the value unchanged.

    Docling types `component_type` and `category` as enums, whose `repr` is
    `<DoclingComponentType.DOCUMENT_BACKEND: 'document_backend'>` — readable,
    but noisy inside a one-line record. The name is the part that identifies it.
    """
    return getattr(value, "name", value)


def _page_heights(document: object) -> dict[int, float]:
    """`{page number: height in points}` for a converted document, or empty.

    Empty is the answer for a document that is absent, carries no `pages`, or
    carries pages this cannot read. Returning empty rather than raising keeps
    the "is this output usable?" decision in ONE place — `_convert` — instead of
    splitting it across a helper and its caller.
    """
    pages = getattr(document, "pages", None)
    if not pages:
        return {}
    try:
        return {int(number): float(page.size.height) for number, page in pages.items()}
    except (AttributeError, TypeError, ValueError):
        return {}


def _convert(source: Path) -> _Conversion:
    """Run Docling and flatten its document into this module's own types.

    Every value crossing out of this function is a `str`, `int`, `float`,
    `bool` or one of the frozen types above. Nothing from the library escapes,
    which is what keeps the tool replaceable (`TECHNOLOGY_STACK.md`, check 5).

    ── THE STATUS CONTRACT, MADE EXPLICIT (owner-approved, 2026-08-06) ──

    Docling declares six statuses. This function used to test one of them —
    `!= "SUCCESS"` — which made PENDING, STARTED, SKIPPED, FAILURE and
    PARTIAL_SUCCESS a single undifferentiated refusal carrying only whatever
    `error_message` strings happened to exist.

    ```
    SUCCESS          + usable output  ->  proceed
    PARTIAL_SUCCESS  + usable output  ->  proceed, and say so in the record
    PARTIAL_SUCCESS  + no usable output ->  refuse as a conversion failure
    anything else                     ->  refuse, with docling's own account
    ```

    **The status is never trusted on its own, in either direction.** A SUCCESS
    that carries no readable page is refused exactly as a FAILURE is: this
    engine's obligation is a truthful Document Evidence Object, and a document
    reporting zero pages is not evidence of a zero-page document — it is an
    absence of measurement. PARTIAL_SUCCESS is accepted only because the output
    is checked for real, never because the label looked close enough.
    """
    converter_module = require_module("docling.document_converter")
    text = str(source)
    try:
        result = converter_module.DocumentConverter().convert(source, raises_on_error=False)
    except Exception as exc:
        raise DocumentUnreadableError(
            text,
            (
                f"docling raised before it could report a status: {type(exc).__name__}: {exc}",
                *_running_environment(source),
            ),
        ) from exc

    status = str(getattr(result.status, "name", result.status))
    document = getattr(result, "document", None)
    heights = _page_heights(document)

    if status not in (_SUCCESS, _PARTIAL_SUCCESS):
        raise DocumentUnreadableError(
            text, _conversion_diagnosis(source, result, status, f"status is {status}")
        )
    if document is None:
        raise DocumentUnreadableError(
            text,
            _conversion_diagnosis(
                source, result, status, "the status is usable but no document came back"
            ),
        )
    if not heights:
        raise DocumentUnreadableError(
            text,
            _conversion_diagnosis(
                source,
                result,
                status,
                "a document came back carrying no readable page, so there is nothing "
                "to measure and nothing is invented in its place",
            ),
        )
    # `heights` is the one computed above and already proven non-empty. It used
    # to be recomputed here from `document.pages`, which meant the check and the
    # value could drift apart — the check could pass on one reading of the pages
    # and the conversion be built from another (Law 14, Law 19).
    conversion = _Conversion(page_count=len(heights), page_heights=heights)

    for item in list(document.texts) + list(document.pictures):
        content = reported_text(str(getattr(item, "text", "") or ""))
        for provenance in item.prov:
            page = int(provenance.page_no)
            box = provenance.bbox
            conversion.regions.append(
                Region(
                    label=str(item.label),
                    text=content,
                    box=_to_top_left_box(
                        (float(box.l), float(box.t), float(box.r), float(box.b)),
                        page=page,
                        page_height=heights[page],
                        origin=str(box.coord_origin),
                    ),
                    detector=DOCLING,
                )
            )

    for table_item in document.tables:
        data = table_item.data
        for provenance in table_item.prov:
            page = int(provenance.page_no)
            height = heights[page]
            outline = provenance.bbox
            cells = tuple(
                Cell(
                    text=reported_text(str(cell.text)),
                    row_start=int(cell.start_row_offset_idx),
                    row_end=int(cell.end_row_offset_idx),
                    column_start=int(cell.start_col_offset_idx),
                    column_end=int(cell.end_col_offset_idx),
                    is_column_header=bool(cell.column_header),
                    is_row_header=bool(cell.row_header),
                    box=_to_top_left_box(
                        (
                            float(cell.bbox.l),
                            float(cell.bbox.t),
                            float(cell.bbox.r),
                            float(cell.bbox.b),
                        ),
                        page=page,
                        page_height=height,
                        origin=str(cell.bbox.coord_origin),
                    ),
                )
                for cell in data.table_cells
            )
            conversion.tables.append(
                Table(
                    detector=DOCLING,
                    box=_to_top_left_box(
                        (
                            float(outline.l),
                            float(outline.t),
                            float(outline.r),
                            float(outline.b),
                        ),
                        page=page,
                        page_height=height,
                        origin=str(outline.coord_origin),
                    ),
                    row_count=int(data.num_rows),
                    column_count=int(data.num_cols),
                    cells=cells,
                )
            )
    return conversion


def _bands_for(source: Path, table: Table, settings: TableStructureSettings) -> tuple[Band, ...]:
    """Run Table Transformer's STRUCTURE model inside one already-located table.

    The table is a given, not a finding. This function cannot return a table
    and cannot be reached for a page Docling found no table on, which is the
    structural half of the rule the module docstring measures.
    """
    pdfium = require_module("pypdfium2")
    torch = require_module("torch")
    transformers = require_module("transformers")

    scale = settings.render_dots_per_inch / _POINTS_PER_INCH
    pad = settings.crop_padding_points
    document = pdfium.PdfDocument(source)
    try:
        # Cropped BEFORE the document closes, deliberately. `to_pil()` can hand
        # back an image viewing pdfium's own buffer, and reading it after the
        # document is freed is a use-after-free that shows up as corrupted
        # pixels rather than a crash — a wrong table structure, silently.
        page_image = document[table.box.page - 1].render(scale=scale).to_pil().convert("RGB")
        left = max(0.0, (table.box.left - pad) * scale)
        top = max(0.0, (table.box.top - pad) * scale)
        right = min(float(page_image.width), (table.box.right + pad) * scale)
        bottom = min(float(page_image.height), (table.box.bottom + pad) * scale)
        crop = page_image.crop((left, top, right, bottom)).copy()
    finally:
        document.close()

    processor = transformers.AutoImageProcessor.from_pretrained(TABLE_STRUCTURE_MODEL)
    model = transformers.TableTransformerForObjectDetection.from_pretrained(TABLE_STRUCTURE_MODEL)
    model.eval()
    with torch.no_grad():
        outputs = model(**processor(images=crop, return_tensors="pt"))
    detected = processor.post_process_object_detection(
        outputs,
        threshold=settings.structure_score_threshold,
        target_sizes=[(crop.height, crop.width)],
    )[0]

    bands: list[Band] = []
    for score, label, box in zip(
        detected["scores"], detected["labels"], detected["boxes"], strict=True
    ):
        edges = [float(edge) for edge in box]
        bands.append(
            Band(
                label=str(model.config.id2label[int(label)]),
                score=float(score),
                box=BoundingBox(
                    page=table.box.page,
                    left=max(0.0, (left + edges[0]) / scale),
                    top=max(0.0, (top + edges[1]) / scale),
                    right=max(0.0, (left + edges[2]) / scale),
                    bottom=max(0.0, (top + edges[3]) / scale),
                ),
            )
        )
    return tuple(bands)


def parse(
    source: Path,
    *,
    source_reference: str,
    extracted_regions: tuple[ExtractedRegion, ...] = (),
    table_structure: TableStructureSettings | None = None,
) -> ParsedStructure:
    """Recover the document's structure. Decide nothing about what it says.

    `source_reference` is the caller's name for the artifact and travels with
    the structure, so a value found here can be traced back to the thing it was
    read off (`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 4).

    `extracted_regions` is §1.3's own input — *"raw extracted information with
    source locations from `reader`"* — and each one becomes a `MappedField` on
    the returned structure. Empty means no extraction was supplied, so nothing
    is mapped: that is the same "this input was not given" default
    `table_structure=None` already uses, never a decision about the document.
    A caller with a reading and no wish to map it does not exist — `pipeline`
    always supplies what `reader` returned.

    Every table cell carrying text is mapped too, from this module's OWN
    conversion rather than from `extracted_regions`, because a cell's text and
    its grid position come from the table detector and reader never sees the
    grid. See A TABLE CELL'S TEXT IS A VALUE in the module docstring: the
    mapping is what gives a cell a name, and a name is what its origin gets
    filed against downstream.

    `table_structure` defaults to `None`, meaning Table Transformer does not
    run. That is not a convenience default: the model needs three numbers this
    repository does not state, and running it would require inventing them.

    Raises `DocumentUnreadable` if the artifact cannot be parsed, and
    `ParserDependencyMissingError` if an approved tool is not installed. Neither is
    swallowed — a parser that returns an empty structure for a damaged file is
    indistinguishable from one that read a blank page.
    """
    _reject_blank(source_reference, "source reference")
    if not source.is_file():
        raise DocumentUnreadableError(str(source), ("no file exists at that path",))

    conversion = _convert(source)
    tables = tuple(conversion.tables)
    detector: str | None = None

    if table_structure is not None:
        detector = TABLE_TRANSFORMER
        tables = tuple(
            Table(
                detector=table.detector,
                box=table.box,
                row_count=table.row_count,
                column_count=table.column_count,
                cells=table.cells,
                bands=_bands_for(source, table, table_structure),
            )
            for table in tables
        )

    return ParsedStructure(
        source_reference=source_reference,
        page_count=conversion.page_count,
        regions=tuple(conversion.regions),
        tables=tables,
        missing_field_information=NO_EXPECTED_FIELD_LIST_WAS_SUPPLIED,
        table_structure_detector=detector,
        # Regions first, then cells, in each producer's own order. The order is
        # not an ordering decision about importance — nothing here ranks
        # anything — it is simply reader's sequence followed by the detector's,
        # so a value's position stays traceable to where it was read.
        mapped_fields=map_fields(extracted_regions) + map_cells(tables),
    )
