"""The PDF Engine, and the sweep that proves Engine 1 stopped naming PyMuPDF.

F-001, approved by the owner 2026-08-06: *"Do NOT purchase an Artifex licence.
Keep PyMuPDF temporarily. Immediately abstract it behind a PDF Engine interface
so Engine 1 never depends directly on PyMuPDF. The implementation must allow
replacing the backend PDF library without changing Engine 1 architecture."*

THE TEST THAT MATTERS IS THE SWEEP, NOT THE UNIT TESTS. An adapter that exists
while three modules still import the library underneath it has abstracted
nothing — that was the state before this change, and reading the code was how it
was found rather than a gate. `test_no_engine_1_module_imports_the_pdf_library_
directly` walks every file under `engines/input_engine/` by AST, statement
imports and `importlib` alike, and fails naming the file. It reads the DIRECTORY
rather than an allowlist, for the same reason `test_package.py::test_the_content_
guard_reads_every_file_on_disk_not_the_allowlist` does: the allowlist is what
someone edits, and the disk is what ships.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Protocol, cast

import cv2
import numpy as np
import pymupdf
import pytest
from authored_source import authored_path, authored_tree

import accountant_dad
from accountant_dad import pdf_backend

# ── a typed facade over PyMuPDF, for AUTHORING fixtures only ──────────────
#
# The fixtures here must be built with the LIBRARY rather than through
# `pdf_backend`: an adapter that authors its own test documents is its own
# oracle, and a shared bug between the two would be invisible. PyMuPDF is
# unannotated, so `mypy --strict` refuses a bare call and this repository counts
# suppressions — the same facade `test_input_engine_reader.py` and
# `test_input_engine_pipeline.py` each declare, for the same reason.


class _Pixmap(Protocol):
    def tobytes(self, output: str) -> bytes: ...


class _AuthoredRect(Protocol):
    """PyMuPDF's rectangle, opaque — the fixtures only pass it straight back."""


class _MakeRect(Protocol):
    def __call__(
        self, left: float, top: float, right: float, bottom: float, /
    ) -> _AuthoredRect: ...


class _AuthoringPage(Protocol):
    def insert_text(self, point: tuple[float, float], text: str) -> int: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...
    def draw_rect(
        self, rectangle: _AuthoredRect, *, fill: tuple[float, float, float]
    ) -> object: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def __getitem__(self, index: int) -> _AuthoringPage: ...
    def set_metadata(self, metadata: dict[str, str]) -> None: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...
    def xref_length(self) -> int: ...
    def xref_get_key(self, xref: int, key: str) -> tuple[str, str]: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


class _OpenStream(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _AuthoringDocument: ...


new_pdf = cast(_NewDocument, pymupdf.open)
open_stream = cast(_OpenStream, pymupdf.open)
authored_rect = cast(_MakeRect, pymupdf.Rect)

#: Every spelling of the backend a first-party module could import. `fitz` is
#: PyMuPDF's own legacy top-level name and resolves to the same package, so a
#: sweep that looked only for `pymupdf` would miss `import fitz` entirely —
#: which is exactly the form `cleaner.py` used through `importlib` before F-001.
PDF_LIBRARY_NAMES = ("pymupdf", "fitz")

#: Functions that import by NAME rather than by statement. Engine 1 uses all
#: three (`parser.require_module("docling.document_converter")`,
#: `importlib.import_module("paddleocr")`), so a sweep reading only `import`
#: statements would be blind in the one engine that does not use them for its
#: optional stack.
IMPORTER_NAMES = ("import_module", "require_module", "__import__")

#: The DPI every render in this file uses. An input, not a threshold: no
#: document in this repository states one (Law 52), and the assertions below are
#: about WHICH bytes come back, never about their resolution.
RENDER_DPI = 150

#: How many pages the multi-page fixture carries. Two is the smallest count
#: that can show `page_count` and per-page reads addressing different pages.
PAGES_IN_THE_TWO_PAGE_FIXTURE = 2

#: What the first eight bytes of a PNG always are.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: PDF user space is 1/72 inch, fixed by the PDF specification. Declared here
#: rather than imported from `pdf_backend._POINTS_PER_INCH`: a test that took
#: the constant from the module under test would agree with it by construction,
#: including when the module is wrong. This is arithmetic, not a chosen value.
_POINTS_PER_INCH = 72


def image_filters(payload: bytes) -> list[tuple[str, str]]:
    """The `/Filter` of every image object in a PDF, as PyMuPDF reports it.

    Read with the LIBRARY rather than through `pdf_backend`, for the same reason
    the fixtures are authored with it: a check that used the adapter to inspect
    the adapter's own output would be its own oracle.

    `('name', '/FlateDecode')` for a compressed image; `('null', 'null')` when
    the key is absent, which is what raw storage looks like.
    """
    document = open_stream(stream=payload, filetype="pdf")
    try:
        return [
            document.xref_get_key(xref, "Filter")
            for xref in range(1, document.xref_length())
            if document.xref_get_key(xref, "Subtype")[1] == "/Image"
        ]
    finally:
        document.close()


def engine_1_sources() -> list[pathlib.Path]:
    """Every file on disk under `engines/input_engine/`, whatever it is called."""
    root = authored_path(accountant_dad).parent / "engines" / "input_engine"
    sources = sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    assert sources != [], (
        f"no modules found under {root}. This sweep derives everything from the "
        "tree, so reading an empty tree would pass while proving nothing."
    )
    return sources


def parsed(path: pathlib.Path) -> ast.Module:
    """One authored file, parsed.

    The paths come from `authored_path(accountant_dad)`, so they already point
    into the authored tree rather than a mutation copy — reading them here is
    reading what this repository wrote, which is the only thing a sweep about
    this repository may assert against.
    """
    return ast.parse(path.read_text(encoding="utf-8"))


def imported_names(tree: ast.Module) -> set[str]:
    """Every module name the source names, by statement OR dynamically.

    A check that read only `import` statements would be blind to exactly the
    route `cleaner.py` used to take — `importlib.import_module("pymupdf")` —
    which is the one this sweep most needs to see.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Call) and names_an_importer(node.func):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.add(first.value)
    return found


def names_an_importer(func: ast.expr) -> bool:
    """`importlib.import_module`, `require_module` or `__import__`, however it
    is spelled at the call site.

    Both an attribute (`importlib.import_module(...)`) and a bare name
    (`require_module(...)`) reach the same three functions, so asking about the
    NAME rather than about the node shape keeps one predicate where there were
    two identical bodies.
    """
    if isinstance(func, ast.Attribute):
        return func.attr in IMPORTER_NAMES
    return isinstance(func, ast.Name) and func.id in IMPORTER_NAMES


def names_the_pdf_library(imported: set[str]) -> set[str]:
    """Matched on the FIRST dotted segment, so `pymupdf.utils` counts too, and
    `pymupdf_helper` — a different distribution — does not.
    """
    return {name for name in imported if name.split(".")[0] in PDF_LIBRARY_NAMES}


# ═══════════════════════════════════════════════════════════════════════════
# The sweep — F-001's actual gate
# ═══════════════════════════════════════════════════════════════════════════


def test_no_engine_1_module_imports_the_pdf_library_directly() -> None:
    """THE F-001 GATE. Engine 1 names the PDF Engine, never the PDF library.

    Before this, three modules imported it — `reader.py` by statement,
    `pipeline.py` by statement, `cleaner.py` twice through `importlib` — so
    replacing PyMuPDF meant editing three files, one of which decided what
    counts as a document failure. The owner's ruling is that the swap must be
    possible *"without changing Engine 1 architecture"*, and that is only true
    while this stays green.
    """
    offenders = {
        path.name: sorted(named)
        for path in engine_1_sources()
        if (named := names_the_pdf_library(imported_names(parsed(path))))
    }
    assert offenders == {}, (
        f"Engine 1 module(s) importing the PDF library directly: {offenders}. "
        "F-001 requires every PDF operation to go through "
        "`accountant_dad.pdf_backend`, so that replacing the library is a "
        "rewrite of that one file. An import here is that abstraction undone."
    )


def test_the_sweep_would_catch_every_form_the_import_can_take() -> None:
    """HOLLOW-GATE DEFENCE. A sweep that finds nothing because it looks at
    nothing passes the test above forever.

    Each shape below is a real way this repository has reached PyMuPDF, built
    from an in-memory source string because the freeze forbids planting a
    sample module in the tree and a string needs no cleanup to be forgotten.
    """
    for source, expected in (
        ("import pymupdf\n", {"pymupdf"}),
        ("import fitz\n", {"fitz"}),
        ("import pymupdf.utils\n", {"pymupdf.utils"}),
        ("from pymupdf import Rect\n", {"pymupdf"}),
        ("import importlib\nfitz = importlib.import_module('pymupdf')\n", {"pymupdf"}),
        ("__import__('fitz')\n", {"fitz"}),
    ):
        found = names_the_pdf_library(imported_names(ast.parse(source)))
        assert found == expected, f"the sweep missed {source!r}: saw {found}"


def test_the_sweep_does_not_fire_on_a_name_that_merely_starts_the_same() -> None:
    """The false positive that would get this gate weakened.

    `pymupdf_helper` is a different distribution and a substring rule would
    refuse it. Matching the first DOTTED SEGMENT is what keeps the gate
    zero-tolerance without being wrong.
    """
    source = "import pymupdf_helper\nfrom fitzgerald import thing\n"
    assert names_the_pdf_library(imported_names(ast.parse(source))) == set()


def test_the_engine_1_tree_the_sweep_reads_is_the_real_one() -> None:
    """PRECONDITION. A sweep over the wrong directory is green and meaningless."""
    names = {path.name for path in engine_1_sources()}
    assert {"cleaner.py", "reader.py", "pipeline.py", "parser.py"} <= names


def test_the_adapter_itself_is_where_the_library_is_named() -> None:
    """The other direction. If NOTHING imports PyMuPDF the sweep above is
    trivially green and the repository has silently lost its PDF support.
    """
    named = names_the_pdf_library(imported_names(authored_tree(pdf_backend)))
    assert named == {"pymupdf"}, (
        f"the PDF Engine names {sorted(named)} as its backend. Exactly one "
        "library belongs here, and it must be here — a sweep over an engine "
        "whose adapter imports nothing proves nothing."
    )


# ═══════════════════════════════════════════════════════════════════════════
# The adapter's own behaviour, against real PDFs
# ═══════════════════════════════════════════════════════════════════════════


def a_text_layer_pdf(lines: tuple[str, ...] = ("TAX INVOICE",), pages: int = 1) -> bytes:
    """A PDF whose characters are embedded, built with the backend directly.

    The FIXTURE may name PyMuPDF; the sweep above covers `src/`, not `tests/`.
    Building the fixture through the adapter would make the adapter its own
    oracle, which is the property `cleaner._content_box` already had to give up.
    """
    document = new_pdf()
    try:
        for page_number in range(pages):
            page = document.new_page(width=400, height=200)
            for index, text in enumerate(lines):
                page.insert_text((40, 60 + index * 30), f"{text} p{page_number + 1}")
        return bytes(document.tobytes())
    finally:
        document.close()


def test_a_text_layer_pdf_reads_back_page_by_page() -> None:
    document = pdf_backend.open_pdf(
        a_text_layer_pdf(("TAX INVOICE", "Total 1180"), pages=PAGES_IN_THE_TWO_PAGE_FIXTURE)
    )
    try:
        assert pdf_backend.page_count(document) == PAGES_IN_THE_TWO_PAGE_FIXTURE
        assert "TAX INVOICE p1" in pdf_backend.plain_text(document, 0)
        assert "TAX INVOICE p2" in pdf_backend.plain_text(document, 1)
    finally:
        pdf_backend.close_pdf(document)


def test_structured_text_carries_each_span_with_its_box() -> None:
    """`reader` needs WHERE each piece of text sits, not just what it says —
    `ENGINE_1:511`, source locations are emitted even for low-confidence
    extractions. A shape change here would strip every region's location.
    """
    document = pdf_backend.open_pdf(a_text_layer_pdf(("TAX INVOICE",)))
    try:
        blocks = pdf_backend.structured_text(document, 0)["blocks"]
    finally:
        pdf_backend.close_pdf(document)

    spans = [span for block in blocks for line in block.get("lines", ()) for span in line["spans"]]
    assert spans != [], "no spans came back; `reader` would read this page as blank"
    assert any("TAX INVOICE" in span["text"] for span in spans)
    for span in spans:
        left, top, right, bottom = span["bbox"]
        assert right > left and bottom > top, f"span {span['text']!r} has an empty box"


def test_a_page_renders_to_png_bytes_at_the_callers_dpi() -> None:
    document = pdf_backend.open_pdf(a_text_layer_pdf())
    try:
        smaller = pdf_backend.render_page_png(document, 0, dpi=RENDER_DPI)
        larger = pdf_backend.render_page_png(document, 0, dpi=RENDER_DPI * 2)
    finally:
        pdf_backend.close_pdf(document)

    assert smaller.startswith(PNG_MAGIC)
    assert larger.startswith(PNG_MAGIC)
    assert len(larger) > len(smaller), (
        "doubling the DPI changed nothing, so the caller's DPI is not reaching "
        "the renderer and every rasterised page is at a resolution nobody chose"
    )


def test_broken_pdf_bytes_raise_the_engines_own_error_and_never_pymupdfs() -> None:
    """The single vendor exception Engine 1 depended on, renamed.

    `pipeline.BUSINESS_FAILURE` matches this type to decide a corrupt document
    produces an artifact recording the failure rather than crashing the run. If
    the backend's own class escaped instead, replacing the library would empty
    that tuple silently and every corrupt PDF would start crashing.
    """
    with pytest.raises(pdf_backend.BrokenPdfError) as raised:
        pdf_backend.open_pdf(b"this is not a pdf, it is a sentence")

    assert not isinstance(raised.value, pymupdf.FileDataError)
    assert isinstance(raised.value.__cause__, pymupdf.FileDataError)
    assert str(raised.value) == str(raised.value.__cause__), (
        "the backend's own message did not survive the rename. Naming a failure "
        "must not cost the diagnosis, and `reader` composes its message from it."
    )


def test_the_error_is_a_pdf_backend_error_so_a_caller_can_catch_the_family() -> None:
    assert issubclass(pdf_backend.BrokenPdfError, pdf_backend.PdfBackendError)


@pytest.mark.parametrize("dpi", [72, 96, 150, 300, 600])
def test_a_rebuilt_page_is_the_physical_size_its_pixels_represent_at_that_dpi(dpi: int) -> None:
    """F-028, PERMANENTLY. A page rasterised at any DPI and rebuilt must come
    back the SAME PHYSICAL SIZE, so a coordinate on it means the same thing.

    ── THE DEFECT THIS TRAPS, MEASURED AT `3bd31e2` BEFORE THE FIX ──

        render dpi      72       96      150       300
        rebuilt page   459pt   612pt   956.25pt  1912.5pt
        scale          0.7500  1.0000   1.5625    3.1250

    `cleaner._encode_png` is `cv2.imencode(".png", ...)`, which writes no `pHYs`
    chunk, so the backend inferred 96 dpi and every rebuilt page came back
    `dpi / 96` times its true size. Coordinates on a cleaned scan therefore
    described a page that did not exist, and — worse — the same document
    measured DIFFERENTLY at two DPIs, which is a reproducibility failure in an
    engine whose whole contract is a reproducible Document Evidence Object.

    ── WHY IT IS PARAMETRIZED, AND WHY 96 IS IN THE LIST ──

    96 is the value the OLD code got right BY ACCIDENT. A single-DPI test
    written at 96 passes against the bug and proves nothing, so this asserts
    across five, and the 96 case is kept deliberately as the control that must
    stay green in both worlds. Falsified before it was trusted: reverting to
    `convert_to_pdf()` reddens 72, 150, 300 and 600 and leaves 96 green.
    """
    source_width, source_height = 612.0, 792.0  # US Letter, in points
    blank = new_pdf()
    try:
        blank.new_page(width=source_width, height=source_height)
        source = bytes(blank.tobytes())
    finally:
        blank.close()

    opened = pdf_backend.open_pdf(source)
    try:
        rendered = pdf_backend.render_page_png(opened, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(opened)

    # Through the encoder the cleaner actually uses — the one that drops the
    # physical-size metadata. Rendering with the backend and rebuilding without
    # this step would test a PNG that still carried its `pHYs` chunk, and so
    # would pass while the real path failed.
    decoded = cv2.imdecode(np.frombuffer(rendered, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None, "the backend's own PNG did not decode"
    written, buffer = cv2.imencode(".png", decoded)
    assert written, "the fixture's own PNG encode failed"
    assert b"pHYs" not in buffer.tobytes(), (
        "this encoder now writes physical-size metadata, so this test no longer "
        "exercises the F-028 path. Re-derive the fixture before trusting it."
    )

    rebuilt = pdf_backend.open_pdf(pdf_backend.pdf_of_page_images([buffer.tobytes()], dpi=dpi))
    try:
        width, height = pdf_backend.page_size(rebuilt, 0)
    finally:
        pdf_backend.close_pdf(rebuilt)

    assert (round(width, 4), round(height, 4)) == (source_width, source_height), (
        f"a page rasterised at {dpi} dpi rebuilt as {width}x{height} pt instead "
        f"of {source_width}x{source_height} pt — a scale of {width / source_width:.4f}. "
        "Every coordinate reported against this page is wrong by that factor, "
        "and the factor changes with a render setting (F-028)."
    )


@pytest.mark.parametrize(
    ("label", "width", "height"),
    [
        # NOT US LETTER. 612 and 792 are whole multiples of 72, so they divide
        # evenly at every DPI tried and the rebuilt page comes back EXACT — the
        # same shape of accident as "96 dpi was right by accident". A guard
        # written only on Letter cannot see the residual at all. Measured
        # spread across 150/300/600 dpi: Letter 0.0000 pt, A4 0.3600, A5 0.3600.
        ("A4", 595.2755905511812, 841.8897637795277),
        ("A5", 419.5275590551181, 595.2755905511812),
    ],
)
@pytest.mark.parametrize("dpi", [150, 300, 600])
def test_a_page_whose_points_are_not_whole_pixels_rebuilds_within_one_pixel(
    label: str, width: float, height: float, dpi: int
) -> None:
    """THE RESIDUAL OF F-028, BOUNDED SO IT CANNOT GROW.

    A raster has a whole number of pixels, so a page whose size is not a whole
    number of pixels at this DPI cannot rebuild to its exact original size. The
    error is real and it is why the same document rebuilt at two DPIs occupies
    two slightly different coordinate spaces.

    IT IS NOT REMOVABLE BY PRESERVING THE SOURCE PAGE SIZE, and that was checked
    before being claimed: `cleaner._crop_to_content` crops to the content box, so
    a cleaned page is genuinely a DIFFERENT page from its source — measured, a
    400x200 pt scan rebuilds as 223.68x90.24 pt. Forcing the source size onto it
    would stretch cropped content to fill a page it does not occupy, which is a
    worse lie than a third of a point.

    So the honest statement is a BOUND, and the bound is derived rather than
    chosen (Law 10): one pixel is exactly `72 / dpi` points, and no rebuild may
    be further out than that. If a future change reintroduces a scale error, it
    exceeds one pixel immediately and this fails.
    """
    blank = new_pdf()
    try:
        blank.new_page(width=width, height=height)
        source = bytes(blank.tobytes())
    finally:
        blank.close()

    opened = pdf_backend.open_pdf(source)
    try:
        rendered = pdf_backend.render_page_png(opened, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(opened)
    decoded = cv2.imdecode(np.frombuffer(rendered, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None, "the backend's own PNG did not decode"
    png = cv2.imencode(".png", cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY))[1].tobytes()

    rebuilt = pdf_backend.open_pdf(pdf_backend.pdf_of_page_images([png], dpi=dpi))
    try:
        rebuilt_width, rebuilt_height = pdf_backend.page_size(rebuilt, 0)
    finally:
        pdf_backend.close_pdf(rebuilt)

    one_pixel_in_points = _POINTS_PER_INCH / dpi
    for axis, got, wanted in (
        ("width", rebuilt_width, width),
        ("height", rebuilt_height, height),
    ):
        assert abs(got - wanted) <= one_pixel_in_points, (
            f"{label} at {dpi} dpi rebuilt {axis} {got} pt against a source {wanted} pt — "
            f"out by {abs(got - wanted)} pt, more than the {one_pixel_in_points} pt that "
            "one pixel is worth. A rounding residual is bounded by one pixel; anything "
            "larger is a scale error (F-028)."
        )


@pytest.mark.parametrize("dpi", [150, 300])
def test_a_rebuilt_page_stores_its_image_compressed_not_raw(dpi: int) -> None:
    """A REGRESSION I SHIPPED, TRAPPED SO IT CANNOT BE SHIPPED AGAIN.

    The first push of the F-028 fix replaced `convert_to_pdf()` — which returns
    an already-compressed document — with `new_page` + `insert_image`, which
    writes an image object that is only Flate-compressed when the document is
    SAVED. The default save does not, so the rebuild started emitting raw
    pixels. Measured on one US Letter page:

        dpi   default save    deflate=True    old convert_to_pdf
        150    6,314,818 B       9,517 B          9,479 B
        300   25,248,570 B      27,915 B         27,873 B

    663x and 905x. Geometrically correct the whole time, which is exactly why
    the F-028 test caught nothing: it asserted the page's SIZE IN POINTS, and
    that was right in both worlds.

    ── THIS TEST'S OWN FIRST VERSION WAS A SIZE PROXY, AND IT DID NOT WORK ──

    It compared the rebuilt PDF against `width x height x channels` from a
    `cv2.IMREAD_COLOR` decode, so the bound was always three bytes per pixel.
    **`cleaner._to_grey` normalises every page to ONE channel before
    `_encode_png`**, so the shape that actually ships was never the shape being
    bounded. Measured at 150 dpi:

        input                     raw payload    w*h*3 bound   w*h bound   caught?
        blank page, 3 channels      6,314,818      6,311,250   2,103,750   both
        blank page, 1 channel         267,451      6,311,250   2,103,750   NEITHER
        REAL cleaner output            91,065      6,311,250   2,103,750   NEITHER

    **The size proxy misses the production path entirely.** A one-channel page
    stores raw at a size no derived pixel bound catches, because MuPDF's raw
    storage is not the naive `w x h x channels` this reasoned about. Tightening
    the bound to `w*h` does not rescue it either — that was measured, not
    assumed, and it still passes on both greyscale rows above.

    ── SO THE TEST ASKS THE ACTUAL QUESTION INSTEAD OF A PROXY FOR IT ──

    Every image in a PDF declares how it is encoded, in its `/Filter` key. Raw
    storage has no filter at all. That is the property, stated directly:

        raw save   ->  Filter = ('null', 'null')
        correct    ->  Filter = ('name', '/FlateDecode')

    Content-independent, channel-independent, size-independent, and needing no
    threshold and no tolerance (Law 10). Verified to separate the two on all
    three inputs in the table above, including the real cleaner output that no
    size bound could see.
    """
    blank = new_pdf()
    try:
        blank.new_page(width=612, height=792)
        source = bytes(blank.tobytes())
    finally:
        blank.close()

    opened = pdf_backend.open_pdf(source)
    try:
        rendered = pdf_backend.render_page_png(opened, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(opened)
    decoded = cv2.imdecode(np.frombuffer(rendered, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None, "the backend's own PNG did not decode"
    # ONE CHANNEL, because that is what `cleaner._to_grey` hands to `_encode_png`.
    # A three-channel fixture tests a shape this repository never rebuilds.
    grey = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
    png = cv2.imencode(".png", grey)[1].tobytes()

    filters = image_filters(pdf_backend.pdf_of_page_images([png], dpi=dpi))

    assert filters, "the rebuilt PDF carries no image at all, so there is nothing to check"
    assert all(kind == "name" and value != "null" for kind, value in filters), (
        f"a page image in the rebuilt PDF declares no compression filter: {filters}. "
        "It is stored as raw pixels. The save has lost `deflate=True` (F-028's "
        "regression), and no page-size assertion can see that."
    )


@pytest.mark.parametrize("dpi", [150, 300])
def test_a_rebuilt_page_renders_back_to_the_exact_pixels_it_was_built_from(dpi: int) -> None:
    """THE INVARIANT F-028's SIZE TEST DOES NOT REACH: the image must FILL the page
    it was given, at the origin, unresampled.

    A page can be exactly the right size in points and still carry its image
    shifted, inset or rescaled inside it — and then every coordinate is wrong
    again, for a different reason, with the size assertion still green. Found by
    mutation, not by reading: `_rectangle(0, 0, w, h)` mutated to
    `_rectangle(1, 0, w, h)` and `(0, 1, w, h)` SURVIVED the size test and the
    compression test both.

    Rendering the rebuilt page back at the DPI it was built at is the strongest
    available check, because it is decidable and needs no tolerance. Measured on
    a page carrying an asymmetric black rectangle, at 150 and 300 dpi:

        correct rect (0,0)   np.array_equal -> True    max channel diff   0
        mutant  rect (1,0)   np.array_equal -> False   max channel diff 255

    IT ALSO PROVES THE REBUILD IS LOSSLESS, which nothing else asserted. Engine 1
    may never lose information a document had; a rebuild that silently resampled,
    recompressed lossily or shifted a half pixel would satisfy every other test in
    this file. `np.array_equal` on the full raster is the honest form of that
    claim, and it holds exactly — not approximately.
    """
    blank = new_pdf()
    try:
        page = blank.new_page(width=612, height=792)
        # ASYMMETRIC ON PURPOSE. A centred or full-page mark is invariant under a
        # flip and under some shifts, so it would let the very mutants that
        # motivated this test survive again.
        page.draw_rect(authored_rect(20, 30, 120, 90), fill=(0, 0, 0))
        source = bytes(blank.tobytes())
    finally:
        blank.close()

    opened = pdf_backend.open_pdf(source)
    try:
        rendered = pdf_backend.render_page_png(opened, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(opened)
    before = cv2.imdecode(np.frombuffer(rendered, np.uint8), cv2.IMREAD_COLOR)
    assert before is not None, "the backend's own PNG did not decode"
    png = cv2.imencode(".png", before)[1].tobytes()

    rebuilt = pdf_backend.open_pdf(pdf_backend.pdf_of_page_images([png], dpi=dpi))
    try:
        returned = pdf_backend.render_page_png(rebuilt, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(rebuilt)
    after = cv2.imdecode(np.frombuffer(returned, np.uint8), cv2.IMREAD_COLOR)
    assert after is not None, "the rebuilt page's PNG did not decode"

    assert after.shape == before.shape, (
        f"the rebuilt page renders to {after.shape} pixels at {dpi} dpi, not the "
        f"{before.shape} it was built from — the image does not fill its page."
    )
    assert np.array_equal(before, after), (
        f"the rebuilt page's pixels differ from the ones it was built from at {dpi} "
        f"dpi (max channel difference "
        f"{int(np.abs(before.astype(int) - after.astype(int)).max())}). The image is "
        "shifted, rescaled or resampled inside its page, so every coordinate "
        "reported against it is wrong even though the page size is right."
    )


def test_a_dpi_that_cannot_be_a_dpi_is_refused_rather_than_corrected() -> None:
    """The guard moved down from `reader` when F-028 gave it a second caller.

    Refused, never defaulted: substituting a workable DPI here would invent the
    owner's number (Law 52) and would reintroduce exactly the silent assumption
    F-028 was.
    """
    for impossible in (0, -1, -300):
        with pytest.raises(ValueError, match="positive number of dots per inch"):
            pdf_backend.pdf_of_page_images([b""], dpi=impossible)


def test_a_dpi_that_is_not_a_number_is_refused_before_it_can_invent_a_page() -> None:
    """NaN PASSES EVERY COMPARISON, INCLUDING `<= 0`, WHICH IS WHY IT NEEDS ITS
    OWN CHECK.

    Found by adversarial review of the F-028 fix. With a NaN DPI every derived
    page dimension became NaN, and the backend then SUBSTITUTED 612 x 792 — a US
    Letter page nobody chose, on a document of unknown size, silently. That is
    the same failure F-028 itself was: a plausible number appearing where a
    measurement should be.

    `inf` is included because it raises on its own today; asserting it here
    pins that it keeps failing loudly rather than starting to be substituted
    for if the backend's behaviour changes.
    """
    # `cast`, never a suppression: the point of the test is that a value the
    # annotation forbids still reaches this function at runtime from an untyped
    # caller (Law 23), and a suppression would spend the repository's zero-new
    # budget to say something a cast says exactly.
    for impossible in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite number of dots per inch"):
            pdf_backend.pdf_of_page_images([b""], dpi=cast(int, impossible))


def test_pages_rebuilt_from_images_stay_in_the_order_they_were_given() -> None:
    """PAGE ORDER IS ONE OF THE FOUR THINGS F-017 REQUIRES CLEANING TO PRESERVE,
    and a rebuild is where it is most easily lost.

    Each page image is a different size, so the rebuilt page dimensions are an
    order fingerprint that survives the round trip and needs no OCR to read.
    """
    sizes = [(80, 40), (160, 40), (240, 40)]
    images: list[bytes] = []
    for width, height in sizes:
        one = new_pdf()
        try:
            one.new_page(width=width, height=height)
            as_pdf = open_stream(stream=one.tobytes(), filetype="pdf")
            try:
                images.append(bytes(as_pdf[0].get_pixmap(dpi=RENDER_DPI).tobytes("png")))
            finally:
                as_pdf.close()
        finally:
            one.close()

    rebuilt = pdf_backend.open_pdf(pdf_backend.pdf_of_page_images(images, dpi=RENDER_DPI))
    try:
        assert pdf_backend.page_count(rebuilt) == len(sizes)
        widths = [
            len(pdf_backend.render_page_png(rebuilt, index, dpi=RENDER_DPI))
            for index in range(len(sizes))
        ]
    finally:
        pdf_backend.close_pdf(rebuilt)

    assert widths == sorted(widths), (
        f"the rebuilt pages came back in a different order: {widths}. The "
        "images were given narrowest first, so a monotonically growing render "
        "is the only ordering that matches what was handed in."
    )


def test_rebuilding_from_no_pages_refuses_rather_than_producing_an_empty_document() -> None:
    """MEASURED, and the failure direction is the safe one.

    PyMuPDF raises `ValueError: cannot save with zero pages`, so a rebuild with
    nothing to rebuild fails loudly instead of handing back a PDF of no pages —
    which downstream is indistinguishable from a document that genuinely had
    none (`reader.py`'s own blank-page-versus-broken-file distinction).

    `cleaner._pdf_rebuilt_from_cleaned_pages` refuses a zero-page SOURCE before
    it ever reaches here, with its own message; this pins that the layer beneath
    it does not quietly cover for a caller that forgets. Asserted rather than
    assumed, because a future backend that returned an empty document instead
    would silently remove that second guard.
    """
    with pytest.raises(ValueError, match="zero pages"):
        pdf_backend.pdf_of_page_images([], dpi=RENDER_DPI)


def test_the_interface_hands_back_no_backend_object_a_caller_could_call() -> None:
    """THE DESIGN, ASSERTED. Handing callers a live `pymupdf.Document` and
    calling that an abstraction would move the import and change nothing: every
    caller would still speak PyMuPDF's method names.

    `PdfDocument` declares `close` and nothing else, so the type a caller is
    given cannot be used to reach the library even though the runtime object
    behind it is the library's own.
    """
    declared = {name for name in vars(pdf_backend.PdfDocument) if not name.startswith(("_", "__"))}
    assert declared == {"close"}, (
        f"`PdfDocument` exposes {sorted(declared)}. Every operation on a PDF is "
        "a FUNCTION in `pdf_backend`; a method here is a backend name leaking "
        "into every caller's vocabulary."
    )
