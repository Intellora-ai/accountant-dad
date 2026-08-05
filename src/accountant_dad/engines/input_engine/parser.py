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
    extracted information with source locations from `reader`."* No `reader`
    exists in this repository yet, so `parse` opens the artifact itself. That
    is a real departure and it has a real consequence: the text on a `Cell` or
    a `Region` here was produced by Docling, not by `reader`, so this module is
    currently doing a part of `reader`'s job as well as its own.

    It must not stay that way. `ENGINE_1_INPUT_ENGINE_RULES.md:113` — *"`parser`
    consumes `reader`'s extraction; it cannot re-read it."* When `reader`
    lands, text must come from `reader`'s spans and this module must keep only
    the geometry, so that no reading has two authors. The seam is small on
    purpose: every text value in the output passes through `reported_text`, and
    the only caller of it is `_convert`.
"""

from __future__ import annotations

import functools
import importlib
import math
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    def __post_init__(self) -> None:
        _reject_blank(self.source_reference, "source reference")
        if self.page_count < 0:
            raise ValueError(f"page count cannot be negative, got {self.page_count}")


@dataclass(frozen=True, slots=True)
class _Conversion:
    """Docling's result, reduced to primitives before anything else touches it."""

    page_count: int
    page_heights: dict[int, float]
    regions: list[Region] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)


def _convert(source: Path) -> _Conversion:
    """Run Docling and flatten its document into this module's own types.

    Every value crossing out of this function is a `str`, `int`, `float`,
    `bool` or one of the frozen types above. Nothing from the library escapes,
    which is what keeps the tool replaceable (`TECHNOLOGY_STACK.md`, check 5).
    """
    converter_module = require_module("docling.document_converter")
    text = str(source)
    try:
        result = converter_module.DocumentConverter().convert(source, raises_on_error=False)
    except Exception as exc:
        raise DocumentUnreadableError(text, (f"{type(exc).__name__}: {exc}",)) from exc

    if str(getattr(result.status, "name", result.status)) != "SUCCESS":
        reasons = tuple(str(error.error_message) for error in result.errors)
        raise DocumentUnreadableError(text, reasons)

    document = result.document
    heights = {int(number): float(page.size.height) for number, page in document.pages.items()}
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
    table_structure: TableStructureSettings | None = None,
) -> ParsedStructure:
    """Recover the document's structure. Decide nothing about what it says.

    `source_reference` is the caller's name for the artifact and travels with
    the structure, so a value found here can be traced back to the thing it was
    read off (`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 4).

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
    )
