"""Engine 1's `reader` — the tests are written to catch invention, not to confirm reading.

`SUB_ENGINE_RESPONSIBILITIES.md` §1.2 gives `reader` one job: get the characters
off the page, with where each piece sits and how confident the extraction was.
The interesting failures are not "it read nothing" — they are the three ways a
reader can look like it worked while lying:

  A BLANK PAGE AND A BROKEN FILE MUST NOT LOOK THE SAME.
      Both are tempting to return as "zero regions". `ENGINE_1:509` — a region
      that could not be read *"is reported as unread, not omitted silently."* A
      corrupt file that returns an empty reading is a silent failure wearing the
      costume of an honest one (`CLAUDE.md` Law 11). So the two are tested
      against each other, not just individually.

  A CONFIDENCE NOBODY MEASURED MUST NOT BECOME A NUMBER.
      The PDF text-layer path runs no recogniser, so no recogniser reports a
      score. `1.0` is the seductive answer and it is an invented measurement
      (Law 24). `None` is the true one, and the tests below refuse any reading
      that fills it in.

  A THRESHOLD NOBODY SET MUST NOT ACQUIRE A DEFAULT.
      `TECHNOLOGY_STACK.md` records the vision-fallback threshold as
      `UNKNOWN - REQUIRES A NUMBER FROM THE OWNER`. The signature is therefore
      inspected directly: a default appearing on any of the three unset
      parameters turns these tests red, including one added later by someone who
      never read this file.

REAL DEPENDENCIES, NO MOCKS (`CLAUDE.md` §J.6). Every fixture is built with
PyMuPDF at test time and read with the real PaddleOCR. A mock of an OCR engine
proves only that the mock returns what it was told to.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
from decimal import Decimal
from typing import Protocol, cast

import pymupdf
import pytest

from accountant_dad.engines.input_engine import reader

# ── which tests can run here ──────────────────────────────────────────────
#
# PaddleOCR cannot be installed beside `requirements-engine1.txt`: paddlex
# requires `numpy<2.4` against a pinned `numpy==2.5.1`, and it also drags in a
# second OpenCV that silently wins `import cv2`. It therefore lives in
# `requirements-engine1-ocr.txt`, in its own environment.
#
# `reader.py` resolves it lazily, so the module imports without it and every
# test below that does not perform real recognition still runs. These do
# perform it, so they are guarded the same way `test_input_engine_parser.py`
# guards its Docling measurements.

_MISSING_OCR = [
    name for name in ("paddleocr", "paddlepaddle") if importlib.util.find_spec(name) is None
]
needs_the_real_ocr = pytest.mark.skipif(
    bool(_MISSING_OCR),
    reason=(
        f"not installed: {', '.join(_MISSING_OCR)}. PaddleOCR cannot share an "
        "environment with requirements-engine1.txt (numpy and cv2 both conflict), so "
        "these measurements are LOCAL and are NOT CI evidence (CLAUDE.md Law 44). "
        "See KNOWN_FAILURES.md F-009."
    ),
)


# ── a typed facade for AUTHORING fixtures ─────────────────────────────────
#
# PyMuPDF ships `py.typed` with unannotated functions, so `mypy --strict`
# rejects every call. Declaring the surface used here keeps the typecheck gate
# green without a suppression, and makes the fixture builders checked rather
# than merely tolerated. This is the authoring half of the API; `reader.py`
# declares the reading half, and the two deliberately do not overlap.


class _Pixmap(Protocol):
    def tobytes(self, output: str) -> bytes: ...


class _Page(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...
    def insert_image(self, rect: object, *, stream: bytes) -> None: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...


class _Document(Protocol):
    def new_page(self, *, width: float, height: float) -> _Page: ...
    def __getitem__(self, index: int) -> _Page: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self, *, stream: bytes | None = ..., filetype: str | None = ...) -> _Document: ...


class _MakeRect(Protocol):
    def __call__(self, x0: float, y0: float, x1: float, y1: float) -> object: ...


open_pdf = cast(_NewDocument, pymupdf.open)
rectangle = cast(_MakeRect, pymupdf.Rect)

# ── ground truth ──────────────────────────────────────────────────────────
# The synthetic invoice is rendered FROM this list, so it is genuine ground
# truth rather than a transcription of whatever the OCR happened to say.
INVOICE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
    "Invoice No INV-2026-0481",
    "Date 05-08-2026",
    "Laptop Dell Latitude 5450",
    "Quantity 3",
    "Taxable Value 165000.00",
    "CGST 9 percent 14850.00",
    "SGST 9 percent 14850.00",
    "Total 194700.00",
)

#: The DPI the OCR fixtures render at. A test parameter, not a product default -
#: `reader.read` still requires the caller to supply one (see the signature test).
FIXTURE_DPI = 300

#: Likewise: a value chosen so the fallback does NOT trigger in tests that are
#: about something else. It is not a product threshold and reader.py holds no
#: copy of it.
NO_FALLBACK = Decimal("0.0")


def an_invoice_pdf() -> bytes:
    """A one-page PDF carrying a real text layer, built from INVOICE_LINES."""
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in INVOICE_LINES:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    out = bytes(doc.tobytes())
    doc.close()
    return out


def a_blank_pdf() -> bytes:
    doc = open_pdf()
    doc.new_page(width=595, height=842)
    out = bytes(doc.tobytes())
    doc.close()
    return out


def an_invoice_png(dpi: int = FIXTURE_DPI) -> bytes:
    """The same invoice, rasterised - so no text layer exists and OCR must run."""
    doc = open_pdf(stream=an_invoice_pdf(), filetype="pdf")
    png = bytes(doc[0].get_pixmap(dpi=dpi).tobytes("png"))
    doc.close()
    return png


def a_blank_png(dpi: int = FIXTURE_DPI) -> bytes:
    doc = open_pdf(stream=a_blank_pdf(), filetype="pdf")
    png = bytes(doc[0].get_pixmap(dpi=dpi).tobytes("png"))
    doc.close()
    return png


def an_image_only_pdf() -> bytes:
    """A PDF whose page is one image. Looks like an invoice, carries no text layer."""
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    page.insert_image(rectangle(0, 0, 595, 842), stream=an_invoice_png())
    out = bytes(doc.tobytes())
    doc.close()
    return out


def character_accuracy(expected: str, actual: str) -> float:
    """Levenshtein-based character accuracy, in [0, 1]. No third-party dependency."""
    previous = list(range(len(actual) + 1))
    for i, want in enumerate(expected, start=1):
        current = [i]
        for j, got in enumerate(actual, start=1):
            if want == got:
                current.append(previous[j - 1])
            else:
                current.append(1 + min(previous[j - 1], previous[j], current[j - 1]))
        previous = current
    distance = previous[-1]
    return 1.0 - distance / max(len(expected), 1)


# ── the threshold, the DPI: numbers nobody set ────────────────────────────


@pytest.mark.parametrize(
    "parameter",
    ["media_type", "render_dpi", "vision_fallback_threshold"],
)
def test_no_unset_number_acquires_a_default(parameter: str) -> None:
    """`TECHNOLOGY_STACK.md`: the fallback threshold is UNKNOWN. So is the DPI.

    A default here would be this module inventing a number the owner never gave
    (Law 52). The signature is the enforcement, so the signature is the test.
    """
    signature = inspect.signature(reader.read)
    assert signature.parameters[parameter].default is inspect.Parameter.empty, (
        f"{parameter} has acquired a default. TECHNOLOGY_STACK.md records the "
        "vision-fallback threshold as 'UNKNOWN - REQUIRES A NUMBER FROM THE "
        "OWNER'; no number here may be chosen by this module."
    )


class _LooseRead(Protocol):
    """`reader.read` with every argument declared optional.

    Only so the two tests below can make the call a careless caller would make -
    omitting a number - and observe what happens AT RUNTIME. Inspecting the
    signature instead would test `inspect`, not the function.
    """

    def __call__(
        self,
        document: bytes,
        *,
        media_type: reader.MediaType = ...,
        render_dpi: int = ...,
        vision_fallback_threshold: Decimal = ...,
    ) -> reader.Reading: ...


read_as_a_careless_caller_would = cast(_LooseRead, reader.read)


def test_omitting_the_threshold_raises_rather_than_picking_one() -> None:
    with pytest.raises(TypeError, match="vision_fallback_threshold"):
        read_as_a_careless_caller_would(
            an_invoice_pdf(),
            media_type=reader.MediaType.PDF,
            render_dpi=FIXTURE_DPI,
        )


def test_omitting_the_dpi_raises_rather_than_picking_one() -> None:
    with pytest.raises(TypeError, match="render_dpi"):
        read_as_a_careless_caller_would(
            an_invoice_pdf(),
            media_type=reader.MediaType.PDF,
            vision_fallback_threshold=NO_FALLBACK,
        )


def test_the_module_declares_no_threshold_constant_anywhere() -> None:
    """Falsification: a default removed from the signature could reappear as a constant."""
    suspicious = {
        name: value
        for name, value in vars(reader).items()
        if not name.startswith("_") and isinstance(value, Decimal | float) and name.upper() == name
    }
    assert suspicious == {}, (
        f"module-level numeric constants found: {suspicious}. The vision-fallback "
        "threshold and the render DPI are the owner's numbers, not this module's."
    )


# ── the PDF text-layer path (PyMuPDF) ─────────────────────────────────────


def test_a_pdf_text_layer_is_read_verbatim_and_completely() -> None:
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.backend is reader.Backend.PDF_TEXT_LAYER
    assert tuple(region.text for region in reading.regions) == INVOICE_LINES


def test_the_text_layer_path_reports_no_confidence_because_it_recognised_nothing() -> None:
    """The load-bearing honesty test. `1.0` here would be an invented measurement.

    No recogniser ran, so no recogniser scored anything. `ENGINE_1:109` leaves
    scoring to the `confidence` sub-engine; `reader` emits the signal it actually
    has, and for a text layer that signal is 'none was produced'.
    """
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert [region.extraction_confidence for region in reading.regions] == [None] * len(
        INVOICE_LINES
    )


def test_every_text_layer_region_carries_a_source_location() -> None:
    """`ENGINE_1:511` - locations are emitted even for low-confidence extractions."""
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    for region in reading.regions:
        assert region.location.page_index == 0
        assert region.location.right > region.location.left
        assert region.location.bottom > region.location.top


def test_reading_order_is_the_page_order_and_is_never_rearranged() -> None:
    """§1.2 - `reader` 'cannot reorder or restructure the text'."""
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    tops = [region.location.top for region in reading.regions]
    assert tops == sorted(tops)


def test_an_image_only_pdf_yields_zero_characters_from_the_text_layer_path() -> None:
    """The text-layer path must not hallucinate a text layer that is not there."""
    reading = reader.read_pdf_text_layer(an_image_only_pdf())

    assert reading.regions == ()
    assert "".join(region.text for region in reading.regions) == ""


# ── blank pages: zero regions, never invented text ────────────────────────


@needs_the_real_ocr
def test_a_blank_pdf_returns_zero_regions_and_no_invented_text() -> None:
    reading = reader.read(
        a_blank_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.regions == ()


@needs_the_real_ocr
def test_a_blank_image_returns_zero_regions_and_no_invented_text() -> None:
    """`CLAUDE.md` §B.8 - it must NEVER hallucinate. For a reader, this is the test."""
    reading = reader.read(
        a_blank_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.backend is reader.Backend.OCR
    assert reading.regions == ()


# ── the OCR path (PaddleOCR), on a real render ────────────────────────────


@needs_the_real_ocr
def test_ocr_reads_the_rendered_invoice_and_reports_a_real_per_region_confidence() -> None:
    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.backend is reader.Backend.OCR
    assert tuple(region.text for region in reading.regions) == INVOICE_LINES

    for region in reading.regions:
        assert isinstance(region.extraction_confidence, Decimal)
        assert Decimal("0") <= region.extraction_confidence <= Decimal("1")


@needs_the_real_ocr
def test_the_ocr_confidences_are_measured_not_a_fabricated_constant() -> None:
    """Falsification: a hard-coded score would be identical on every region.

    A real recogniser produces a different number per line. Asserting only
    'is a Decimal in [0,1]' would pass happily against `Decimal("1.0")` returned
    unconditionally, which is precisely the invention this engine forbids.
    """
    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    scores = {region.extraction_confidence for region in reading.regions}
    assert len(scores) > 1, f"every region reported the same score {scores}; that is a constant"
    assert scores != {Decimal("1")}


@needs_the_real_ocr
def test_an_image_only_pdf_falls_through_to_ocr_and_reads_it() -> None:
    """A PDF with no text layer is an image. The router must reach OCR, not give up."""
    reading = reader.read(
        an_image_only_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.backend is reader.Backend.OCR
    assert tuple(region.text for region in reading.regions) == INVOICE_LINES


@needs_the_real_ocr
def test_ocr_character_accuracy_on_the_synthetic_invoice_is_total() -> None:
    """Measured, with a unit: characters correct / characters expected."""
    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    expected = "\n".join(INVOICE_LINES)
    actual = "\n".join(region.text for region in reading.regions)
    assert character_accuracy(expected, actual) == 1.0


# ── corrupt input: a NAMED error, never a silent empty reading ────────────


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(an_invoice_pdf()[:400], id="truncated pdf"),
        pytest.param(b"this is plainly not a PDF", id="not a pdf at all"),
        pytest.param(b"", id="empty bytes"),
    ],
)
def test_a_corrupt_pdf_raises_a_named_error_rather_than_returning_nothing(
    payload: bytes,
) -> None:
    """The distinction a blank page would otherwise destroy.

    `CLAUDE.md` Law 11 - always fail loudly, never silently. An empty reading
    from a broken file is indistinguishable downstream from an honest reading of
    an empty page, and the Confidence Report built on it would be a confident
    statement about a file nobody could open.
    """
    with pytest.raises(reader.UnreadableDocumentError):
        reader.read(
            payload,
            media_type=reader.MediaType.PDF,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(an_invoice_png()[:400], id="truncated png"),
        pytest.param(b"this is plainly not an image", id="not an image at all"),
        pytest.param(b"", id="empty bytes"),
    ],
)
def test_a_corrupt_image_raises_a_named_error_rather_than_returning_nothing(
    payload: bytes,
) -> None:
    with pytest.raises(reader.UnreadableDocumentError):
        reader.read(
            payload,
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )


@needs_the_real_ocr
def test_a_broken_file_and_a_blank_page_are_distinguishable() -> None:
    """States that must never collapse into each other, asserted side by side."""
    blank = reader.read(
        a_blank_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )
    assert blank.regions == ()

    with pytest.raises(reader.UnreadableDocumentError):
        reader.read(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )


def test_an_unreadable_document_error_is_a_reader_error() -> None:
    assert issubclass(reader.UnreadableDocumentError, reader.ReaderError)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(an_invoice_pdf()[:400], id="truncated pdf"),
        pytest.param(b"this is plainly not a PDF", id="not a pdf at all"),
        pytest.param(b"", id="empty bytes"),
    ],
)
def test_the_text_layer_path_itself_raises_rather_than_returning_empty(payload: bytes) -> None:
    """Each entry point is tested on its own, not only through the router.

    Added after a mutation run: making `read_pdf_text_layer` swallow a corrupt
    PDF and return an empty reading kept the whole suite GREEN, because
    `reader.read` then fell through to the rasteriser, which raised for its own
    reasons. The router's safety was standing in for this function's, so this
    function's was untested. `parser` and `confidence` will call it directly.
    """
    with pytest.raises(reader.UnreadableDocumentError):
        reader.read_pdf_text_layer(payload)


# ── the vision fallback: stubbed, and it refuses loudly ───────────────────


@needs_the_real_ocr
def test_the_vision_fallback_refuses_loudly_when_confidence_is_below_threshold() -> None:
    """There is no API key and no agreed threshold, so the path cannot silently work.

    `TECHNOLOGY_STACK.md`: 'Until it exists, the fallback path cannot be
    implemented, only stubbed.' A stub that returned a reading anyway would be
    the worst outcome in this file - an invented document.
    """
    with pytest.raises(reader.VisionFallbackUnavailableError):
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            # Above any achievable score, so every region is 'below threshold'.
            vision_fallback_threshold=Decimal("1"),
        )


@needs_the_real_ocr
def test_the_fallback_never_silently_degrades_to_another_backend() -> None:
    """Inversion: the dangerous failure is a fallback that quietly returns OCR output."""
    with pytest.raises(reader.VisionFallbackUnavailableError):
        reader.read(
            an_image_only_pdf(),
            media_type=reader.MediaType.PDF,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=Decimal("1"),
        )


@needs_the_real_ocr
def test_the_fallback_is_not_triggered_when_every_region_meets_the_threshold() -> None:
    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=Decimal("0.5"),
    )

    assert reading.backend is reader.Backend.OCR
    assert len(reading.regions) == len(INVOICE_LINES)


@needs_the_real_ocr
def test_a_blank_page_never_triggers_the_fallback_because_nothing_scored_low() -> None:
    """A page with no regions has no region below the threshold. Zero is not low."""
    reading = reader.read(
        a_blank_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=Decimal("1"),
    )

    assert reading.regions == ()


def test_the_text_layer_path_never_triggers_the_fallback() -> None:
    """No recogniser ran, so there is no OCR confidence to be below anything."""
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=Decimal("1"),
    )

    assert reading.backend is reader.Backend.PDF_TEXT_LAYER


def test_a_vision_fallback_error_is_a_reader_error() -> None:
    assert issubclass(reader.VisionFallbackUnavailableError, reader.ReaderError)


# ── the reader stays inside its boundary ──────────────────────────────────


def test_an_invalid_dpi_is_refused_rather_than_corrected() -> None:
    for bad in (0, -1):
        with pytest.raises(ValueError, match="render_dpi"):
            reader.read(
                an_image_only_pdf(),
                media_type=reader.MediaType.PDF,
                render_dpi=bad,
                vision_fallback_threshold=NO_FALLBACK,
            )


#: `TECHNOLOGY_STACK.md`, Engine 1: "Explicitly NOT approved - do not install
#: without a later, explicit approval."
NOT_APPROVED = frozenset(
    {"pytesseract", "tesserocr", "tesseract", "easyocr", "camelot", "tabula", "unstructured"}
)


def top_level_imports(module_path: str) -> set[str]:
    """Every distribution `module_path` imports, by AST rather than by text.

    An earlier version of this test searched the source for the banned names and
    was red on the docstring that explains why they are banned - it asserted
    'the file does not mention them', which was never the property that matters.
    Reading the import statements asserts the real one: nothing unapproved is
    actually reachable from this module.
    """
    source = pathlib.Path(module_path).read_text(encoding="utf-8")
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is mutmut's instrumentation rather than ours. Asserting on it "
            "measures the mutation tool, not the code under test — and a structural "
            "assertion about OUR source cannot be evaluated against a file we did "
            "not write. Skipped under mutation only; it runs in every ordinary suite."
        )
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    return imported


def test_the_reader_imports_no_unapproved_ocr_engine() -> None:
    """`TECHNOLOGY_STACK.md`: Tesseract and EasyOCR are explicitly NOT approved."""
    imported = top_level_imports(reader.__file__)
    offenders = {name for name in imported if name.lower() in NOT_APPROVED}
    assert offenders == set(), f"{sorted(offenders)} not approved by TECHNOLOGY_STACK.md"


def test_the_reader_imports_only_the_approved_stack() -> None:
    """Stricter than a denylist: the whole import list is pinned.

    A denylist only catches the engines someone thought to ban. This turns red
    for ANY third-party import added later, approved or not, which is what makes
    a silent technology swap impossible rather than merely discouraged.
    """
    assert top_level_imports(reader.__file__) == {
        # standard library
        "__future__",
        "importlib",
        "io",
        "dataclasses",
        "decimal",
        "enum",
        "functools",
        "typing",
        # TECHNOLOGY_STACK.md, Engine 1
        "pymupdf",
        # transitive requirements of the approved two, for decoding and arrays
        "numpy",
        "PIL",
    }


def test_the_only_dynamically_imported_module_is_the_approved_ocr() -> None:
    """PaddleOCR is reached through `importlib`, so the AST test cannot see it.

    Falsification of the test above: routing an import through
    `importlib.import_module` would hide a technology swap from a check that
    only reads `import` statements. So the string literals are pinned too, and
    the two tests together cover both ways a dependency can enter this module.
    """
    source = pathlib.Path(reader.__file__).read_text(encoding="utf-8")
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is mutmut's instrumentation rather than ours. Asserting on it "
            "measures the mutation tool, not the code under test — and a structural "
            "assertion about OUR source cannot be evaluated against a file we did "
            "not write. Skipped under mutation only; it runs in every ordinary suite."
        )
    tree = ast.parse(source)
    dynamic: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            dynamic.add(node.args[0].value)
    assert dynamic == {"paddleocr"}, (
        f"dynamically imported modules are {sorted(dynamic)}; TECHNOLOGY_STACK.md "
        "names PaddleOCR as THE OCR and nothing else may arrive this way."
    )


def test_no_unapproved_ocr_engine_is_even_installed() -> None:
    """The stack says 'do not install', not merely 'do not import'."""
    installed = {name for name in NOT_APPROVED if importlib.util.find_spec(name) is not None}
    assert installed == set(), f"{sorted(installed)} is installed and is not approved"


def test_the_reader_assigns_no_meaning_to_what_it_extracts() -> None:
    """§1.2 - it may extract `27AAECS1234F1Z5`, it may not conclude it is a GSTIN.

    The reading carries text and position. It carries no field name, no type, no
    label - because every one of those is an interpretation, and interpretation
    is Engine 2's (`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 1).
    """
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    region_attributes = set(
        vars(reading.regions[0])
        if not hasattr(reading.regions[0], "__slots__")
        else reading.regions[0].__slots__
    )
    assert region_attributes == {"text", "location", "extraction_confidence"}, (
        f"a region carries {region_attributes}; anything naming or typing the "
        "value would be interpretation, which reader is forbidden."
    )


def test_a_reading_is_immutable_once_produced() -> None:
    reading = reader.read(
        an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    # Through `setattr` so the assignment is a runtime fact rather than
    # something the typechecker refuses to compile. A frozen dataclass must
    # actually raise, not merely be annotated as if it would.
    attribute = "text"
    with pytest.raises((AttributeError, TypeError)):
        setattr(reading.regions[0], attribute, "something else")
