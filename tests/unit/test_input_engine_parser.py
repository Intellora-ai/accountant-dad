"""Engine 1's `parser` sub-engine — tests written to break it, not to bless it.

The parser's whole job is STRUCTURE, and the failure that matters is not a
crash. It is a parser that returns a plausible table nobody wrote. `ENGINE_1_
INPUT_ENGINE_RULES.md:339` — *"An invented value is indistinguishable
downstream from an observed one, and the entire trustworthiness of the system
rests on that distinction holding."*

So the load-bearing tests below are the ones that hunt invention:

  - EVERY emitted text is checked against the exact set of strings drawn into
    the PDF. A cell whose text the document does not carry turns it red, and
    that is the only test that can catch a model that helpfully "corrects" a
    reading.
  - A page with no table must yield ZERO tables, and a BLANK page must yield
    zero regions. Measured, not assumed: Microsoft Table Transformer's
    detection model reported a table on a blank A4 page at score 0.8813 during
    this build, which is exactly why `parse` never lets that model create a
    table (see `test_table_transformer_is_never_allowed_to_create_a_table`).
  - Every number the specification does not supply must stay ABSENT from the
    code. `test_table_structure_settings_supplies_no_number_of_its_own` goes
    red the day somebody gives one of them a default, which is the only way an
    invented threshold can enter this module.

The PDF is written by hand, byte by byte, so the ground truth is not a second
tool's opinion — it is the literal list of strings and coordinates this file
drew. A fixture built with a PDF library would be measuring two libraries
against each other.

WHAT RUNS IN CI AND WHAT DOES NOT. `requirements-ci.txt` does not carry Docling
or Transformers, and this agent may not add them. Tests needing them are marked
and skip; the contract, refusal and no-invention-by-construction tests run
everywhere. Law 44 applies to the rest: the extraction numbers in the report
are LOCAL, and they are not CI evidence until the dependency manifest exists.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from accountant_dad.engines.input_engine import parser

if TYPE_CHECKING:
    from collections.abc import Iterator

# ── the ground truth, drawn by hand ───────────────────────────────────────

PAGE_WIDTH_POINTS = 595
PAGE_HEIGHT_POINTS = 842

#: (x, y, size, text) in PDF user space — origin BOTTOM-left, as PDF defines it.
HEADER_LINES: tuple[tuple[int, int, int, str], ...] = (
    (50, 780, 12, "ACME TRADERS PRIVATE LIMITED"),
    (50, 762, 10, "Invoice No: INV-2026-0481"),
    (50, 746, 10, "Date: 05/08/2026"),
)
FOOTER_LINES: tuple[tuple[int, int, int, str], ...] = (
    (50, 545, 10, "Place of supply: Maharashtra"),
)

COLUMN_X: tuple[int, ...] = (50, 250, 340, 410, 545)
ROW_Y: tuple[int, ...] = (680, 654, 628, 602, 576)

#: The table, exactly as it is drawn. Row 0 is the header row.
#:
#: `NOTHING_DRAWN` marks a ruled grid position with no ink in it at all. It is
#: here because of a MUTANT THAT SURVIVED: replacing the parser's
#: `... or None` with `... or "0.00"` — inventing a value for a position
#: nothing was read from — passed every test in this file, for the only reason
#: that mattered, which is that the fixture had no empty cell to invent into.
#: A missing HSN code is an ordinary real invoice, and it is the exact shape
#: the invention prohibition exists for (`ENGINE_1:337`).
NOTHING_DRAWN = ""

TABLE: tuple[tuple[str, ...], ...] = (
    ("Description", "HSN", "Qty", "Amount"),
    ("Laptop computer", "8471", "2", "120000.00"),
    ("Optical mouse", "8471", "5", "2500.00"),
    ("USB cable", NOTHING_DRAWN, "10", "900.00"),
)

#: The one grid position this file deliberately leaves blank.
BLANK_POSITION = (3, 1)

EXPECTED_ROWS = 4
EXPECTED_COLUMNS = 4
EXPECTED_GRID_POSITIONS = 16
#: Fifteen, not sixteen. MEASURED: Docling reports no cell at all for a ruled
#: position with no ink in it, and it does NOT re-index the row — see
#: `test_a_blank_grid_position_is_a_hole_and_shifts_nothing`.
EXPECTED_CELLS = 15
ONE_PAGE = 1
NO_TABLES = 0

#: Every string this file writes onto the page. Nothing else may come back out.
EVERY_DRAWN_STRING: frozenset[str] = frozenset(
    [line[3] for line in HEADER_LINES + FOOTER_LINES]
    + [cell for row in TABLE for cell in row if cell != NOTHING_DRAWN]
)


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(*, with_table: bool) -> str:
    parts: list[str] = []
    for x, y, size, text in HEADER_LINES:
        parts.append(f"BT /F1 {size} Tf {x} {y} Td ({_escape(text)}) Tj ET")
    if with_table:
        parts.append("0.6 w")
        parts += [f"{COLUMN_X[0]} {y} m {COLUMN_X[-1]} {y} l S" for y in ROW_Y]
        parts += [f"{x} {ROW_Y[0]} m {x} {ROW_Y[-1]} l S" for x in COLUMN_X]
        for row_index, row in enumerate(TABLE):
            baseline = ROW_Y[row_index] - 17
            for column_index, cell in enumerate(row):
                if cell == NOTHING_DRAWN:
                    continue
                left = COLUMN_X[column_index] + 5
                parts.append(f"BT /F1 10 Tf {left} {baseline} Td ({_escape(cell)}) Tj ET")
    for x, y, size, text in FOOTER_LINES:
        parts.append(f"BT /F1 {size} Tf {x} {y} Td ({_escape(text)}) Tj ET")
    return "\n".join(parts)


def _pdf_bytes(*, with_table: bool = True, blank: bool = False) -> bytes:
    """A minimal, valid PDF 1.4. Hand-built so the ground truth has no dependency."""
    stream = b"" if blank else _content_stream(with_table=with_table).encode("ascii")
    media_box = f"{PAGE_WIDTH_POINTS} {PAGE_HEIGHT_POINTS}".encode()
    objects: tuple[bytes, ...] = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
        + media_box
        + b"] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    out += trailer.encode()
    return bytes(out)


# ── which tests can run here ──────────────────────────────────────────────

_MISSING = [
    name
    for name in ("docling", "transformers", "torch", "pypdfium2")
    if importlib.util.find_spec(name) is None
]
needs_the_real_tools = pytest.mark.skipif(
    bool(_MISSING),
    reason=(
        f"not installed: {', '.join(_MISSING)}. `requirements-ci.txt` does not carry "
        "Engine 1's parsing stack, so these measurements are LOCAL and are not CI "
        "evidence (CLAUDE.md Law 44)."
    ),
)

A_REFERENCE = "upload:invoice-481.pdf"


@pytest.fixture(scope="session")
def documents(tmp_path_factory: pytest.TempPathFactory) -> dict[str, pathlib.Path]:
    directory = tmp_path_factory.mktemp("parser-documents")
    written = {
        "with_table": _pdf_bytes(with_table=True),
        "without_table": _pdf_bytes(with_table=False),
        "blank": _pdf_bytes(blank=True),
    }
    paths = {}
    for name, data in written.items():
        path = directory / f"{name}.pdf"
        path.write_bytes(data)
        paths[name] = path
    corrupt = directory / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.4\nthis is not a pdf body at all\n")
    paths["corrupt"] = corrupt
    return paths


@pytest.fixture(scope="session")
def invoice(documents: dict[str, pathlib.Path]) -> parser.ParsedStructure:
    """Parsed once. Loading Docling's models costs seconds; the result is frozen."""
    return parser.parse(documents["with_table"], source_reference=A_REFERENCE)


def _cell_grid(table: parser.Table) -> dict[tuple[int, int], str | None]:
    return {(cell.row_start, cell.column_start): cell.text for cell in table.cells}


def _every_emitted_text(structure: parser.ParsedStructure) -> Iterator[str]:
    for region in structure.regions:
        if region.text is not None:
            yield region.text
    for table in structure.tables:
        for cell in table.cells:
            if cell.text is not None:
                yield cell.text


# ── the numbers this module refuses to invent ─────────────────────────────


def test_table_structure_settings_supplies_no_number_of_its_own() -> None:
    """Every threshold is the caller's. A default here would be an invented number.

    `TECHNOLOGY_STACK.md` records the OCR fallback threshold as *"UNKNOWN —
    REQUIRES A NUMBER FROM THE OWNER"* for exactly this reason. The same holds
    for every number Table Transformer needs, and none of them is written down
    anywhere in this repository.
    """
    parameters = inspect.signature(parser.TableStructureSettings).parameters
    assert parameters, "settings with no parameters would hide the numbers, not remove them"
    with_defaults = [
        name
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty
    ]
    assert with_defaults == [], (
        f"these numbers were given a default: {with_defaults}. No document in this "
        "repository supplies them; a default is this module inventing one (Law 52)."
    )


def _table_structure_settings(**changes: float) -> parser.TableStructureSettings:
    """A valid baseline with named fields replaced. Mirrors `cleaner`'s `settings()`
    helper so a settings-validation test changes exactly one field at a time.
    """
    fields: dict[str, float] = {
        "render_dots_per_inch": 200.0,
        "structure_score_threshold": 0.6,
        "crop_padding_points": 12.0,
    }
    fields.update(changes)
    return parser.TableStructureSettings(
        render_dots_per_inch=fields["render_dots_per_inch"],
        structure_score_threshold=fields["structure_score_threshold"],
        crop_padding_points=fields["crop_padding_points"],
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("render_dots_per_inch", 0.0),
        ("render_dots_per_inch", -1.0),
        ("render_dots_per_inch", float("nan")),
        ("render_dots_per_inch", float("inf")),
        ("structure_score_threshold", -0.1),
        ("structure_score_threshold", 1.1),
        ("crop_padding_points", -1.0),
        ("crop_padding_points", float("nan")),
    ],
)
def test_an_impossible_table_structure_setting_is_refused_by_name(field: str, value: float) -> None:
    """Refused as `parser.ImpossibleSettingError`, not a bare `ValueError`.

    Mirrors `cleaner.ImpossibleSettingError`: a caller that wants to catch
    "you gave me a number that cannot be honoured" specifically needs a name,
    not a string every other `ValueError` in this module could also raise.
    A bare `pytest.raises(ValueError, ...)` here would pass even if this
    settings object shared its error type with an unrelated bug elsewhere in
    the module, which is exactly the ambiguity the dedicated class removes.
    """
    with pytest.raises(parser.ImpossibleSettingError, match=field):
        _table_structure_settings(**{field: value})


def test_parse_runs_the_table_structure_detector_only_when_asked() -> None:
    """The optional argument defaults to OFF, never to a number."""
    default = inspect.signature(parser.parse).parameters["table_structure"].default
    assert default is None, (
        "the default must be None — 'do not run it'. Any settings object here would "
        "carry thresholds nobody set."
    )


def test_missing_field_information_is_empty_and_names_its_basis() -> None:
    """The parser must not know which fields a document is required to carry.

    CGST Rules 46-55 name 86 mandatory particulars for a tax invoice, and every
    one of them lives in `Accounting_Brain/Validation_Library/`. That list is
    KNOWLEDGE. `SUB_ENGINE_RESPONSIBILITIES.md` 1.3 gives the parser structure
    and nothing else, so a hard-coded statutory field list here would be an
    accounting rule applied inside extraction — forbidden by
    `ENGINE_1_INPUT_ENGINE_RULES.md:558-562`.
    """
    information = parser.NO_EXPECTED_FIELD_LIST_WAS_SUPPLIED
    assert information.absent_fields == ()
    assert "knowledge" in information.basis.lower()
    assert information.basis.strip() != ""


def test_no_output_type_carries_a_name_that_means_something() -> None:
    """Structure only. A field called `total` or `supplier` is Engine 2's job taken.

    `COMMUNICATION_RULES_INPUT_ENGINE.md:71` — if it could be *"wrong about the
    business rather than wrong about the document"*, it is interpretation. This
    goes red the day someone adds `Cell.is_total`.
    """
    forbidden = {
        "account",
        "ledger",
        "debit",
        "credit",
        "supplier",
        "vendor",
        "customer",
        "total",
        "subtotal",
        "tax",
        "gst",
        "hsn",
        "amount",
        "invoice",
        "voucher",
        "currency",
        "quantity",
        "rate",
        "meaning",
        "confidence",
    }
    for kind in (
        parser.ParsedStructure,
        parser.Table,
        parser.Cell,
        parser.Region,
        parser.Band,
        parser.BoundingBox,
    ):
        for field in fields(kind):
            words = set(field.name.split("_"))
            assert not words & forbidden, (
                f"{kind.__name__}.{field.name} names a business concept. The parser "
                "reports structure; what a value MEANS is the Understanding Engine's."
            )


def test_the_module_reaches_for_no_other_engine_and_no_accounting_knowledge() -> None:
    """Pinned imports. A dependency on the Brain or another engine is a boundary breach."""
    source = pathlib.Path(inspect.getfile(parser)).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    offenders = sorted(
        name
        for name in imported
        if name.startswith("accountant_dad")
        and not name.startswith("accountant_dad.engines.input_engine")
    )
    assert offenders == [], (
        f"parser imports {offenders}. Engine 1 communicates with exactly one engine, "
        "by sending one artifact (COMMUNICATION_RULES_INPUT_ENGINE.md:14)."
    )


# ── refusals that need no model ───────────────────────────────────────────


def test_a_missing_dependency_is_named_not_swallowed() -> None:
    with pytest.raises(parser.ParserDependencyMissingError) as raised:
        parser.require_module("a_module_that_is_definitely_not_installed")
    assert "a_module_that_is_definitely_not_installed" in str(raised.value)


@pytest.mark.parametrize(
    ("page", "left", "top", "right", "bottom"),
    [
        (0, 1.0, 1.0, 2.0, 2.0),
        (-1, 1.0, 1.0, 2.0, 2.0),
        (1, 5.0, 1.0, 2.0, 2.0),
        (1, 1.0, 9.0, 2.0, 2.0),
        (1, -1.0, 1.0, 2.0, 2.0),
        (1, 1.0, -1.0, 2.0, 2.0),
        (1, float("nan"), 1.0, 2.0, 2.0),
        (1, 1.0, 1.0, float("inf"), 2.0),
    ],
)
def test_a_bounding_box_that_cannot_be_true_is_refused(
    page: int, left: float, top: float, right: float, bottom: float
) -> None:
    """A location that cannot exist is worse than no location: it looks traceable."""
    with pytest.raises(ValueError, match="bounding box"):
        parser.BoundingBox(page=page, left=left, top=top, right=right, bottom=bottom)


def test_a_degenerate_but_possible_bounding_box_is_accepted() -> None:
    """Zero width is something a detector really emits. Refusing it would drop evidence."""
    box = parser.BoundingBox(page=1, left=10.0, top=10.0, right=10.0, bottom=20.0)
    assert box.right == box.left


def _a_box() -> parser.BoundingBox:
    return parser.BoundingBox(page=1, left=1.0, top=1.0, right=2.0, bottom=2.0)


def test_a_cell_may_not_report_an_empty_string() -> None:
    """Absent, zero and unreadable are three states (`ENGINE_1:569`).

    `None` means the detector reported no text. `"0"` means a zero was read.
    `""` collapses the first into the second and the collapse is invisible
    downstream, so it is refused here rather than explained later.
    """
    with pytest.raises(ValueError, match="empty"):
        parser.Cell(
            text="",
            row_start=0,
            row_end=1,
            column_start=0,
            column_end=1,
            is_column_header=False,
            is_row_header=False,
            box=_a_box(),
        )


def test_a_cell_reporting_a_read_zero_is_kept() -> None:
    cell = parser.Cell(
        text="0",
        row_start=0,
        row_end=1,
        column_start=0,
        column_end=1,
        is_column_header=False,
        is_row_header=False,
        box=_a_box(),
    )
    assert cell.text == "0"


@pytest.mark.parametrize(
    ("row_start", "row_end", "column_start", "column_end"),
    [(1, 1, 0, 1), (0, 1, 2, 2), (-1, 1, 0, 1), (0, 1, -1, 1), (2, 1, 0, 1)],
)
def test_a_cell_spanning_no_grid_position_is_refused(
    row_start: int, row_end: int, column_start: int, column_end: int
) -> None:
    with pytest.raises(ValueError, match="span"):
        parser.Cell(
            text="x",
            row_start=row_start,
            row_end=row_end,
            column_start=column_start,
            column_end=column_end,
            is_column_header=False,
            is_row_header=False,
            box=_a_box(),
        )


def test_a_region_may_not_report_an_empty_string_either() -> None:
    with pytest.raises(ValueError, match="empty"):
        parser.Region(label="text", text="", box=_a_box(), detector="docling")


def test_a_region_must_say_which_detector_produced_it() -> None:
    with pytest.raises(ValueError, match="detector"):
        parser.Region(label="text", text="x", box=_a_box(), detector="  ")


# ── the measurement: real Docling, real PDF, exact counts ─────────────────


@needs_the_real_tools
def test_the_known_table_comes_back_exactly_as_it_was_drawn(
    invoice: parser.ParsedStructure,
) -> None:
    """Row count, column count, cell count and every cell string, against the source.

    This is the only test in the file that can measure extraction. It asserts
    the whole grid, not a sample: a parser that got fifteen of sixteen cells
    right would pass a spot check and be wrong on a real invoice line.
    """
    assert len(invoice.tables) == 1
    table = invoice.tables[0]
    assert table.row_count == EXPECTED_ROWS
    assert table.column_count == EXPECTED_COLUMNS
    assert len(table.cells) == EXPECTED_CELLS

    grid = _cell_grid(table)
    expected: dict[tuple[int, int], str | None] = {
        (row, column): value
        for row, cells in enumerate(TABLE)
        for column, value in enumerate(cells)
        if value != NOTHING_DRAWN
    }
    assert grid == expected


@needs_the_real_tools
def test_a_blank_grid_position_is_a_hole_and_shifts_nothing(
    invoice: parser.ParsedStructure,
) -> None:
    """The measured behaviour, pinned — because getting it wrong is silent.

    MEASURED 2026-08-05: for a ruled position with no ink in it, Docling emits
    NO CELL, and it leaves every other cell in the row on its own column index.
    Absence is therefore represented as a missing grid position, which stays
    distinct from `text=None` (a cell was located, no text reported) and from
    `text="0"` (a zero was read) — the three states `ENGINE_1:569` requires.

    The load-bearing half is the second assertion. If a missing HSN code
    re-indexed the row, the quantity would arrive under the HSN column and the
    parser would have corrupted the structure while looking perfectly healthy.
    """
    grid = _cell_grid(invoice.tables[0])
    assert BLANK_POSITION not in grid
    assert grid[(3, 2)] == "10"
    assert grid[(3, 3)] == "900.00"
    assert invoice.tables[0].row_count * invoice.tables[0].column_count == EXPECTED_GRID_POSITIONS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", None), ("   ", None), ("\n\t ", None), ("0", "0"), (" 900.00 ", "900.00")],
)
def test_nothing_reported_never_becomes_a_value(raw: str, expected: str | None) -> None:
    """The whole invention prohibition, as one pure function, run in CI.

    This test exists because a MUTANT SURVIVED: turning the parser's `or None`
    into `or "0.00"` passed every model-driven test in this file, since the
    fixture happened to give Docling no empty string to hand back. Pushing the
    rule into `reported_text` made it reachable without a model, so the
    guard now runs everywhere instead of only where a fixture cooperates.
    """
    assert parser.reported_text(raw) == expected


@needs_the_real_tools
def test_the_header_row_is_marked_and_nothing_else_is(invoice: parser.ParsedStructure) -> None:
    """Which row is the header is STRUCTURE, and it is what makes a column locatable.

    Without it nothing downstream can tell which column carries the HSN code
    required by CGST rule 46(g) — and the parser is forbidden from telling it.
    """
    table = invoice.tables[0]
    headers = {(cell.row_start, cell.column_start) for cell in table.cells if cell.is_column_header}
    assert headers == {(0, column) for column in range(EXPECTED_COLUMNS)}
    assert not any(cell.is_row_header for cell in table.cells)


@needs_the_real_tools
def test_not_one_emitted_string_is_absent_from_the_document(
    invoice: parser.ParsedStructure,
) -> None:
    """The anti-invention test. Every character out must be a character in.

    Docling merges adjacent lines into one region, so a region's text is
    checked as a concatenation of drawn strings rather than an exact match —
    but no fragment may appear that was never written.
    """
    for text in _every_emitted_text(invoice):
        remaining = text
        for drawn in sorted(EVERY_DRAWN_STRING, key=len, reverse=True):
            remaining = remaining.replace(drawn, " ")
        assert remaining.strip() == "", (
            f"the parser emitted {text!r}, which contains {remaining.strip()!r} — "
            "text that was never written on the document."
        )


@needs_the_real_tools
def test_every_cell_is_located_inside_its_own_table_on_page_one(
    invoice: parser.ParsedStructure,
) -> None:
    """A location that does not contain the value is not traceability, it is decoration."""
    table = invoice.tables[0]
    assert table.box.page == ONE_PAGE
    for cell in table.cells:
        assert cell.box.page == ONE_PAGE
        assert table.box.left <= cell.box.left
        assert cell.box.right <= table.box.right
        assert table.box.top <= cell.box.top
        assert cell.box.bottom <= table.box.bottom


@needs_the_real_tools
def test_the_page_header_survives_as_a_located_region(invoice: parser.ParsedStructure) -> None:
    """Twenty-odd statutory particulars sit OUTSIDE the line-item table.

    Supplier identity, serial number and date of issue (CGST rule 46(a)-(c))
    are page text, not table cells. If the parser returned tables only, those
    would be unreachable downstream.
    """
    assert invoice.regions
    texts = [region.text for region in invoice.regions if region.text is not None]
    assert any("ACME TRADERS PRIVATE LIMITED" in text for text in texts)
    assert any("INV-2026-0481" in text for text in texts)
    for region in invoice.regions:
        assert region.box.page == ONE_PAGE


@needs_the_real_tools
def test_a_document_with_no_table_yields_no_table(documents: dict[str, pathlib.Path]) -> None:
    """Zero, not a guess."""
    structure = parser.parse(documents["without_table"], source_reference=A_REFERENCE)
    assert len(structure.tables) == NO_TABLES
    assert structure.regions


@needs_the_real_tools
def test_a_blank_page_yields_an_empty_structure(documents: dict[str, pathlib.Path]) -> None:
    """Nothing on the page means nothing in the output. Never an invented row."""
    structure = parser.parse(documents["blank"], source_reference=A_REFERENCE)
    assert structure.page_count == ONE_PAGE
    assert structure.tables == ()
    assert structure.regions == ()


@needs_the_real_tools
def test_a_corrupt_file_fails_loudly_and_by_name(documents: dict[str, pathlib.Path]) -> None:
    """`CLAUDE.md` Law 11 — fail loudly, never silently.

    A sub-engine raises; the Input Engine PARENT is what must not halt the
    pipeline (`COMMUNICATION_RULES_INPUT_ENGINE.md:159`). The parser cannot
    convert this into low confidence itself: only the `confidence` sub-engine
    may produce a score (`ENGINE_1:109`).
    """
    with pytest.raises(parser.DocumentUnreadableError) as raised:
        parser.parse(documents["corrupt"], source_reference=A_REFERENCE)
    message = str(raised.value)
    assert "corrupt.pdf" in message
    assert message.strip() != "corrupt.pdf"


@needs_the_real_tools
def test_the_table_structure_detector_stays_off_unless_the_numbers_are_given(
    invoice: parser.ParsedStructure,
) -> None:
    assert invoice.table_structure_detector is None
    assert all(table.bands == () for table in invoice.tables)


@needs_the_real_tools
def test_table_transformer_reports_bands_when_the_caller_supplies_the_numbers(
    documents: dict[str, pathlib.Path],
) -> None:
    """Microsoft Table Transformer, run for real, on the table Docling located.

    The three numbers below are the TEST's, chosen by this file and belonging
    to nothing else. They are not defaults, they are not a system setting, and
    no accuracy claim rests on them.
    """
    structure = parser.parse(
        documents["with_table"],
        source_reference=A_REFERENCE,
        table_structure=parser.TableStructureSettings(
            render_dots_per_inch=200.0,
            structure_score_threshold=0.6,
            crop_padding_points=12.0,
        ),
    )
    assert structure.table_structure_detector is not None
    table = structure.tables[0]
    assert table.bands, "the structure model ran and reported nothing"
    labels = [band.label for band in table.bands]
    assert labels.count("table row") == EXPECTED_ROWS
    assert labels.count("table column") == EXPECTED_COLUMNS
    for band in table.bands:
        assert band.box.page == ONE_PAGE
        assert 0.0 <= band.score <= 1.0


@needs_the_real_tools
def test_table_transformer_is_never_allowed_to_create_a_table(
    documents: dict[str, pathlib.Path],
) -> None:
    """The regression test for a measured defect in the approved tool.

    Measured 2026-08-05 in this worktree: `microsoft/table-transformer-
    detection` reported TWO tables on `without_table.pdf` (0.7002, 0.8646) and
    ONE on a completely blank A4 page (0.8813). A page-level detector that
    hallucinates a table on an empty page cannot be permitted to add one, at
    any threshold, so `parse` only ever runs the STRUCTURE model inside a
    region Docling already found. This test fails the moment that changes.
    """
    settings = parser.TableStructureSettings(
        render_dots_per_inch=200.0,
        structure_score_threshold=0.6,
        crop_padding_points=12.0,
    )
    for name in ("without_table", "blank"):
        structure = parser.parse(
            documents[name], source_reference=A_REFERENCE, table_structure=settings
        )
        assert len(structure.tables) == NO_TABLES, (
            f"{name}.pdf has no table, and the structure detector invented one."
        )


@needs_the_real_tools
def test_the_source_reference_travels_with_the_structure(
    invoice: parser.ParsedStructure,
) -> None:
    assert invoice.source_reference == A_REFERENCE


@needs_the_real_tools
def test_the_parser_reports_no_missing_field_whatever_the_document(
    documents: dict[str, pathlib.Path],
) -> None:
    """Not even for a blank page. Absence is only knowable against an expected list."""
    for name in ("with_table", "without_table", "blank"):
        structure = parser.parse(documents[name], source_reference=A_REFERENCE)
        assert structure.missing_field_information.absent_fields == ()
