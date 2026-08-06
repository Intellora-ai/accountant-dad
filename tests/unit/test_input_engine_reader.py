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

ONE EXCEPTION, NAMED HERE RATHER THAN LEFT TO BE DISCOVERED. `reader.read`'s
ESCALATION BRANCH - the decision that a reading is too unsure to stand and must
go to the vision fallback - had never executed, in either direction. It sits
after `read_by_ocr`, and `read_by_ocr` calls PaddleOCR before it does anything
else, so no argument to `reader.read` reaches it while PaddleOCR is absent
(`KNOWN_FAILURES.md` F-009). That branch is the one thing standing between
Engine 1 and a confident wrong answer, so the last section of this file
substitutes the `paddleocr` MODULE - the narrowest external edge there is
(`CLAUDE.md` §J.7) - and substitutes nothing else. PyMuPDF, PIL, numpy, the
score conversion, the polygon arithmetic, the routing and the comparison itself
all run for real. Those tests measure `reader`'s OWN logic and measure NOTHING
about PaddleOCR's accuracy; the `@needs_the_real_ocr` tests above remain the
only place that is measured, and none of them is changed.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import io
import math
import pathlib
import sys
import types
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, cast

import numpy
import pymupdf
import pytest
from authored_source import authored_path, authored_source, authored_tree
from PIL import Image

from accountant_dad import pdf_backend
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

# `find_spec` takes a MODULE name, not a distribution name. `paddlepaddle` is
# what you `pip install`; the module it ships is `paddle`. Asking for a spec
# named `paddlepaddle` therefore returned `None` in EVERY environment that can
# exist — including one with the full OCR stack installed — so this guard
# skipped unconditionally and the eleven tests below had never run anywhere.
#
# That is the second half of F-009, and the environment conflict hid it: the
# dependency fix alone would have changed nothing, because the skip never
# depended on the dependency.
_MISSING_OCR = [name for name in ("paddleocr", "paddle") if importlib.util.find_spec(name) is None]
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


class _EncryptingDocument(Protocol):
    """`_Document.tobytes` with the encryption keywords PyMuPDF also accepts.

    Declared separately rather than widened into `_Document` so that the plain
    `tobytes()` every other fixture calls keeps its narrow signature: only the
    one fixture that builds an encrypted PDF may reach these three keywords.
    """

    def tobytes(self, *, encryption: int, owner_pw: str, user_pw: str) -> bytes: ...


class _NewDocument(Protocol):
    def __call__(self, *, stream: bytes | None = ..., filetype: str | None = ...) -> _Document: ...


class _MakeRect(Protocol):
    def __call__(self, x0: float, y0: float, x1: float, y1: float) -> object: ...


open_pdf = cast(_NewDocument, pymupdf.open)
rectangle = cast(_MakeRect, pymupdf.Rect)

#: PyMuPDF's own AES-256 encryption selector, read out of the module rather than
#: written as the integer it happens to be. The constant EXISTS at runtime -
#: `pymupdf.PDF_ENCRYPT_AES_256` is `5` in the pinned 1.28.0 - but PyMuPDF ships
#: `py.typed` without declaring it, so a plain attribute reference is a
#: `mypy --strict` error and this repository allows no per-line suppression.
#:
#: Through `__dict__` and a `cast`, for the same reason every other facade in
#: this file exists: it is STRICTER than silencing the line, because the value
#: is now typed `int` everywhere it is used, and it keeps the vendor's name for
#: the vendor's number instead of hard-coding a 5 that means nothing on sight.
AES_256_ENCRYPTION = cast(int, pymupdf.__dict__["PDF_ENCRYPT_AES_256"])

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

#: RGB, not RGBA and not greyscale. The recogniser is handed a real
#: three-channel array, never the PNG bytes PyMuPDF produced.
RGB_CHANNELS = 3
#: A two-page document must reach the recogniser as two pages — one page
#: would mean the second was silently dropped.
BOTH_PAGES = 2

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


def test_a_whitespace_only_span_is_skipped_not_emitted_as_an_empty_region() -> None:
    """PyMuPDF really does report a span for text that is nothing but spaces
    (measured directly against a fixture built the same way `an_invoice_pdf`
    is) - it is not a reading, so `read_pdf_text_layer` must drop it rather
    than emit a region carrying no evidence between two real ones.
    """
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 90), "HELLO", fontname="helv", fontsize=13)
    page.insert_text((60, 130), "   ", fontname="helv", fontsize=13)
    page.insert_text((60, 170), "WORLD", fontname="helv", fontsize=13)
    data = bytes(doc.tobytes())
    doc.close()

    reading = reader.read_pdf_text_layer(data)

    assert tuple(region.text for region in reading.regions) == ("HELLO", "WORLD")


def test_a_whitespace_span_skips_only_itself_and_never_the_rest_of_its_line() -> None:
    """`continue`, not `break` - and the fixture above cannot tell them apart.

    In that fixture every whitespace span is the ONLY span on its line, because
    the three insert_text calls sit on three different baselines. Skipping the
    span and abandoning the line therefore produce the identical reading, and a
    mutation run proved it: `continue` rewritten to `break` left that test green.

    Here the whitespace span and a REAL span share one line. PyMuPDF groups
    spans by geometry, so they have to be adjacent on the same baseline in
    different fonts to land in one line - measured, not assumed: this exact
    fixture reports `block 0 / line 0 / spans ['   ', 'AFTER']`.

    With `break`, `AFTER` is never emitted. Nothing raises, nothing warns, and
    the page comes back short by everything that followed a run of spaces -
    which is a leading-indented table cell, a padded amount column, or any line
    a producer chose to align with spaces. `ENGINE_1:509`: a region that could
    not be read *"is reported as unread, not omitted silently."* Dropping the
    rest of a line silently is the failure that rule exists to forbid.
    """
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    blank = "   "
    page.insert_text((60, 90), blank, fontname="helv", fontsize=13)
    # A different font, starting exactly where the spaces end, so PyMuPDF reads
    # one line carrying two spans rather than two lines carrying one each.
    page.insert_text(
        (60 + pymupdf.get_text_length(blank, fontname="helv", fontsize=13), 90),
        "AFTER",
        fontname="tiro",
        fontsize=13,
    )
    data = bytes(doc.tobytes())
    doc.close()

    reading = reader.read_pdf_text_layer(data)

    assert tuple(region.text for region in reading.regions) == ("AFTER",), (
        "the whitespace span took the rest of its line with it; `continue` skips "
        "one span, `break` abandons every span after it"
    )


def test_a_text_layer_reading_names_its_backend_and_counts_every_page() -> None:
    """The two fields of `Reading` the text-layer path never asserted.

    `backend` is what makes a reading traceable to the tool that produced it,
    and `pages_read` is the only statement anywhere that page two was looked at
    at all. A mutation run found both unasserted on this path: `backend=None`
    and `pages_read=None` both survived, and a `Reading` that names no backend
    is evidence with no provenance (`CLAUDE.md` §O - *"Evidence carries its
    origin, permanently"*).

    Two pages, not one, because `pages_read=1` is indistinguishable from a
    hard-coded 1 and from `len(pages)` on a single-page document.
    """
    doc = open_pdf()
    for index in range(BOTH_PAGES):
        doc.new_page(width=595, height=842).insert_text(
            (60, 90), f"PAGE {index}", fontname="helv", fontsize=13
        )
    data = bytes(doc.tobytes())
    doc.close()

    reading = reader.read_pdf_text_layer(data)

    assert reading.backend is reader.Backend.PDF_TEXT_LAYER
    assert reading.pages_read == BOTH_PAGES, (
        f"a two-page PDF reported {reading.pages_read} pages read; the second "
        "page was either never opened or never counted"
    )
    assert tuple(region.text for region in reading.regions) == ("PAGE 0", "PAGE 1")
    assert [region.location.page_index for region in reading.regions] == [0, 1]


# ── `_render_pdf_pages`: PyMuPDF only, reachable without a recogniser ──────
#
# `reader.read` only reaches this function after the text layer comes back
# empty, and it is followed immediately by `read_by_ocr`, which needs
# PaddleOCR (absent here). Called directly, `_render_pdf_pages` performs no
# recognition at all - it rasterises with PyMuPDF, exactly as `cleaner`'s own
# PDF workaround does - so it is real logic tested for real, without the OCR
# guard.


def test_render_pdf_pages_rasterises_every_page_to_a_real_png() -> None:
    pages = reader._render_pdf_pages(an_image_only_pdf(), render_dpi=FIXTURE_DPI)

    assert len(pages) == 1
    assert pages[0].startswith(b"\x89PNG\r\n\x1a\n"), "not a real, decodable PNG"


def test_render_pdf_pages_raises_on_an_unopenable_pdf() -> None:
    """Tested on its own, not only through the router - the same falsification
    `test_the_text_layer_path_itself_raises_rather_than_returning_empty`
    above already applies to `read_pdf_text_layer`.
    """
    with pytest.raises(reader.UnreadableDocumentError):
        reader._render_pdf_pages(b"not a pdf at all", render_dpi=FIXTURE_DPI)


def test_render_pdf_pages_error_message_names_the_reason_completely() -> None:
    """§J.2 - assert the real result, not merely that SOME error fired."""
    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader._render_pdf_pages(b"not a pdf at all", render_dpi=FIXTURE_DPI)

    assert str(raised.value).startswith("the bytes supplied could not be opened as a PDF: ")


#: A DPI at which a 595x842pt page is 826,389 x 1,169,444 pixels - about 2.9 TB
#: of RGB. MuPDF refuses it with `FzErrorLimit: code=5: Overly large image`,
#: which is a REAL backend failure on a REAL, perfectly openable PDF: nothing is
#: faked, nothing is monkeypatched, and the refusal costs milliseconds because
#: the limit is checked before any allocation. Measured directly against this
#: exact fixture at 100000, 1000000 and 10^9 dpi - all three raise the same
#: error, so the number is not balanced on a threshold.
#:
#: It is a TEST INPUT, not a product number: `reader.read` still demands a DPI
#: from its caller and this file's `FIXTURE_DPI` is unchanged.
DPI_TOO_LARGE_TO_RASTERISE = 100_000


def test_a_page_that_opens_and_then_cannot_be_rasterised_names_the_dpi_and_the_cause() -> None:
    """The second boundary in `_render_pdf_pages`, which had never executed.

    `test_render_pdf_pages_raises_on_an_unopenable_pdf` above only reaches the
    OPEN failure. The rasterisation failure is a different `raise` on a
    different line, and it was reachable only in theory - so every literal in
    its message, and the upstream type it interpolates, were unasserted. A
    mutation run proved it: replacing that whole message with `None`, and
    replacing `type(failure).__name__` with `type(None).__name__`, both left the
    entire suite green.

    The message is pinned WHOLE and composed from the cause rather than from a
    copy of MuPDF's wording, so this asserts `reader`'s contract - *name the
    DPI, name the upstream type, keep the upstream text* - without pinning a
    vendor string the vendor is free to reword.

    `UnreadableDocumentError` and not `RecognitionFailedError` is the load-bearing
    half: a page MuPDF cannot draw is a verdict on the DOCUMENT, and no
    recogniser is involved on this path at all.
    """
    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader._render_pdf_pages(a_blank_pdf(), render_dpi=DPI_TOO_LARGE_TO_RASTERISE)

    cause = raised.value.__cause__
    assert cause is not None, "the backend's own failure was dropped instead of preserved"
    assert str(raised.value) == (
        "the PDF opened but a page could not be rasterised at "
        f"{DPI_TOO_LARGE_TO_RASTERISE} dpi: {type(cause).__name__}: {cause}"
    )
    # The document opened cleanly, so this is NOT the open-failure message.
    assert "could not be opened as a PDF" not in str(raised.value)
    assert not isinstance(raised.value, reader.RecognitionFailedError)


def test_render_pdf_pages_declares_pdf_the_callers_dpi_and_png_to_pymupdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PyMuPDF tolerates ANY filetype string and either case of the output
    format for a real stream - measured directly against this exact fixture:
    'pdf', 'PDF' and 'XXpdfXX' all open it identically, and 'png'/'PNG' render
    byte-identical output. A wrong literal is therefore invisible in the return
    value, and the corrupt-DPI case is likewise invisible - PyMuPDF accepts
    `dpi=None` without raising. The only way to prove the CALLER's DPI, 'pdf'
    and 'png' are the exact values actually used is to record what reaches the
    real, unmocked PyMuPDF call - every one of the three still runs for real
    underneath (`CLAUDE.md` §J.6/§J.7 - fake only at the narrowest I/O edge,
    and even here nothing is faked, only observed on the way through).

    THE SPY MOVED WITH THE LITERALS (F-001). `reader` no longer writes 'pdf' or
    'png' anywhere: `accountant_dad.pdf_backend` owns every PyMuPDF option
    string, which is what makes the library replaceable at all. So the recorder
    now wraps the ADAPTER's own handle on PyMuPDF, and the assertion is
    unchanged in what it proves — that a real `reader._render_pdf_pages` call,
    with the caller's DPI, reaches the real PyMuPDF with exactly 'pdf', that
    DPI and 'png'. Reader's path is still the thing under test; only the place
    the literals live has changed.
    """
    filetype_calls: list[str] = []
    dpi_calls: list[int] = []
    format_calls: list[str] = []
    real_open_stream = pdf_backend._open_stream

    class _RecordedPixmap:
        def __init__(self, real: pdf_backend._Pixmap) -> None:
            self._real = real

        def tobytes(self, output: str) -> bytes:
            format_calls.append(output)
            return self._real.tobytes(output)

    class _RecordedPage:
        def __init__(self, real: pdf_backend._Page) -> None:
            self._real = real

        def get_pixmap(self, *, dpi: int) -> _RecordedPixmap:
            dpi_calls.append(dpi)
            return _RecordedPixmap(self._real.get_pixmap(dpi=dpi))

    class _RecordedDocument:
        def __init__(self, real: pdf_backend._Document) -> None:
            self._real = real

        @property
        def page_count(self) -> int:
            return self._real.page_count

        def __getitem__(self, index: int) -> _RecordedPage:
            return _RecordedPage(self._real[index])

        def close(self) -> None:
            self._real.close()

    def spy_open_stream(*, stream: bytes, filetype: str) -> _RecordedDocument:
        filetype_calls.append(filetype)
        return _RecordedDocument(real_open_stream(stream=stream, filetype=filetype))

    monkeypatch.setattr(pdf_backend, "_open_stream", spy_open_stream)

    pages = reader._render_pdf_pages(an_image_only_pdf(), render_dpi=FIXTURE_DPI)

    assert filetype_calls == ["pdf"]
    assert dpi_calls == [FIXTURE_DPI]
    assert format_calls == ["png"]
    assert pages[0].startswith(b"\x89PNG\r\n\x1a\n")


# ── `_decode_image`: PIL/numpy only, reachable without a recogniser ───────
#
# Like `_render_pdf_pages` above, `reader.read` only reaches `_decode_image`'s
# result on the OCR path (needs PaddleOCR, absent here) - but the IMAGE branch
# of `reader.read` also calls it directly, before OCR, purely to fail fast on
# undecodable bytes. Called directly it performs no recognition at all, so it
# is real logic tested for real, without the OCR guard.


def an_rgba_png() -> bytes:
    """A real PNG carrying a genuine alpha channel.

    PIL decodes this natively as RGBA (4 channels), not RGB - measured
    directly: `Image.open(...).convert(None)` on this exact fixture returns
    the ORIGINAL 4-channel data unchanged. So this is the fixture that actually
    exercises `.convert("RGB")` rather than accepting it for free; an RGB
    source would decode to 3 channels whether or not the conversion ran.
    """
    image = Image.new("RGBA", (4, 3), color=(200, 50, 25, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_decode_image_converts_every_native_mode_to_true_three_channel_rgb() -> None:
    """§1.2/module docstring - PaddleOCR is handed 'an RGB array'. Not RGBA."""
    decoded = reader._decode_image(an_rgba_png())

    assert decoded.shape == (3, 4, 3), (
        f"expected height=3, width=4, 3 channels (true RGB); got shape {decoded.shape}"
    )
    # `reader.Page` declares `NDArray[numpy.uint8]` - "one byte per channel" -
    # and that half of the contract was asserted nowhere. A 16-bit or float
    # array has the same three-channel SHAPE and is not the array the module
    # promises its caller.
    #
    # STATED HONESTLY: this does NOT kill the surviving `dtype=numpy.uint8`
    # mutants. `Image.convert("RGB")` yields PIL mode RGB, which numpy always
    # materialises as `uint8` - measured across all fourteen PIL modes - so
    # dropping that argument cannot change the result. Those two mutants are
    # equivalent, and this assertion pins the contract rather than pretending
    # to have killed them.
    assert decoded.dtype == numpy.uint8, (
        f"reader.Page promises one byte per channel; got dtype {decoded.dtype}"
    )


def test_a_corrupt_image_error_message_names_every_reason_completely() -> None:
    """§J.2 - assert the real result, not merely that SOME error fired."""
    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader._decode_image(b"this is plainly not an image")

    message = str(raised.value)
    assert message.startswith("the bytes supplied could not be decoded as an image: ")
    assert message.endswith(
        "Raised rather than returned as an empty reading - a file that could "
        "not be opened and a page with nothing on it are different answers."
    )

    # THE MIDDLE WAS THE HOLE, AND A MUTATION RUN FOUND IT. `startswith` and
    # `endswith` together pin both ENDS of the message and say nothing about
    # what sits between them - which is exactly where the diagnosis lives.
    # Replacing `type(failure).__name__` with `type(None).__name__` left both
    # assertions above green while every corrupt image reported its cause as
    # "NoneType", so the one segment that tells a human WHICH Pillow failure
    # happened was untested. Pinned whole, and composed from the cause rather
    # than from a copy of Pillow's wording, so this asserts `reader`'s contract
    # without pinning a vendor string the vendor is free to reword.
    cause = raised.value.__cause__
    assert cause is not None, "Pillow's own failure was dropped instead of preserved"
    assert message == (
        "the bytes supplied could not be decoded as an image: "
        f"{type(cause).__name__}: {cause}. "
        "Raised rather than returned as an empty reading - a file that could "
        "not be opened and a page with nothing on it are different answers."
    )


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


def test_an_image_only_pdf_reaches_the_ocr_path_before_failing_on_missing_paddleocr(
    paddleocr_is_absent: list[str],
) -> None:
    """Falsification of the router, run WITHOUT the OCR guard: a PDF with no
    text layer must not just stop at the text-layer path - it must actually
    rasterise and call the recogniser. The failure asserted is
    `ModuleNotFoundError`, which is never reached if the router gave up at the
    text-layer stage instead of continuing to the rasteriser.

    THE ABSENCE IS NOW CREATED RATHER THAN INHERITED. This test used to depend
    on PaddleOCR simply not being installed (`KNOWN_FAILURES.md` F-002). That
    held for as long as F-009 held, and stopped holding the moment CI grew an
    interpreter with the real OCR stack in it - where this test failed at commit
    `c4fbb5f` for a reason that had nothing to do with the router it measures.
    See the `paddleocr_is_absent` fixture for the general principle.
    """
    with pytest.raises(ModuleNotFoundError, match="paddleocr"):
        reader.read(
            an_image_only_pdf(),
            media_type=reader.MediaType.PDF,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )

    # Stronger than the raise alone: the router did not merely fail, it got as
    # far as ASKING for the recogniser. A router that stopped at the text-layer
    # stage would raise nothing and this list would be empty.
    assert "paddleocr" in paddleocr_is_absent


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


def test_the_text_layer_open_failure_names_every_reason_completely() -> None:
    """§J.2 - the test above asserts only that SOME `UnreadableDocumentError` fired.

    A mutation run showed what that leaves open: this message's whole body
    replaced by `None`, and each of its literal fragments blanked, upper-cased or
    case-flipped - six mutations, all of them green, because nothing anywhere
    reads what `read_pdf_text_layer` actually says when a PDF will not open.

    That message is not decoration. It is the sentence that tells whoever is
    holding a rejected document WHY it was rejected, and the clause that records
    the decision this whole module is built on - *raised rather than returned as
    an empty reading*. Pinned whole, and composed from the cause rather than from
    a copy of MuPDF's wording, so the backend stays free to reword its half.

    Note what is deliberately NOT here: this message interpolates the failure but
    not `type(failure).__name__`, unlike the other two boundaries in this module.
    The comparison is exact, so a later edit that quietly aligns them turns this
    red rather than passing unnoticed.
    """
    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader.read_pdf_text_layer(b"this is plainly not a PDF")

    cause = raised.value.__cause__
    assert cause is not None, "the backend's own failure was dropped instead of preserved"
    assert str(raised.value) == (
        f"the bytes supplied could not be opened as a PDF: {cause}. "
        "Raised rather than returned as an empty reading, which would be "
        "indistinguishable downstream from an honest reading of a blank page."
    )


def a_password_protected_pdf() -> bytes:
    """A REAL PDF that opens, reports its page count, and refuses to be read.

    Not a corruption and not a fake. `pymupdf.open` succeeds on an encrypted
    document and `page_count` answers 1, because the trailer and the page tree
    are readable without the password; only the page CONTENT is not. Asking for
    its structured text then raises `ValueError: document closed or encrypted` -
    measured against this exact fixture, not assumed.

    It is also the realistic case, which is why it is the fixture rather than a
    mangled byte string: businesses email password-protected invoices and bank
    statements routinely, and this is precisely what one looks like arriving at
    Engine 1 without its password.
    """
    doc = open_pdf()
    doc.new_page(width=595, height=842).insert_text(
        (60, 90), "CONFIDENTIAL INVOICE", fontname="helv", fontsize=13
    )
    encrypted = bytes(
        cast(_EncryptingDocument, doc).tobytes(
            encryption=AES_256_ENCRYPTION, owner_pw="owner", user_pw="user"
        )
    )
    doc.close()
    return encrypted


def test_a_pdf_that_opens_but_cannot_be_read_is_never_a_partial_reading() -> None:
    """The SECOND boundary in `read_pdf_text_layer`, which had never executed.

    Every corrupt-PDF test above fails at `open_pdf`. This one gets past it: the
    document opens, `page_count` answers 1, and the read fails afterwards - the
    exact case the module's nested `try/finally` inside the converting `try` was
    written for, and the exact case nothing exercised. A mutation run measured
    the cost: this message replaced entirely by `None`, its upstream type
    replaced by `type(None).__name__`, and each of its fragments mutated - six
    survivors, on the boundary that decides whether a half-read document is
    reported or returned.

    The dangerous outcome is not the raise, it is the alternative: a partial
    reading. A document read up to the page it broke on is indistinguishable
    downstream from a document that simply ended there, and Engine 1 would hand
    on an invoice with its last pages missing and no signal that anything was
    lost (`CLAUDE.md` Law 11).

    `UnreadableDocumentError` and not `RecognitionFailedError`: an encrypted PDF
    is a fact about the DOCUMENT, and no recogniser is involved on this path.
    """
    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader.read_pdf_text_layer(a_password_protected_pdf())

    cause = raised.value.__cause__
    assert cause is not None, "the backend's own failure was dropped instead of preserved"
    assert str(raised.value) == (
        "the PDF opened but its text layer could not be read: "
        f"{type(cause).__name__}: {cause}. Raised rather than returned "
        "as a partial reading — a document read up to the point it broke is "
        "indistinguishable downstream from a document that ended there."
    )
    # It got PAST the open. Reporting the open-failure message here would mean
    # the two boundaries had been collapsed into one.
    assert "could not be opened as a PDF" not in str(raised.value)
    assert not isinstance(raised.value, reader.RecognitionFailedError)


# ── the vision fallback: stubbed, and it refuses loudly ───────────────────
#
# `reader.read` only reaches `_vision_fallback` after a real OCR pass that
# actually found a region below threshold - unreachable here without
# PaddleOCR. Called directly with a synthetic `Reading`, it takes no
# recogniser at all: real `Decimal` arithmetic (a genuine `min()` over real
# scores) and a real message, so it is tested for real without the OCR guard.


def test_vision_fallback_names_the_lowest_score_and_the_threshold() -> None:
    low = reader.TextRegion(
        text="a",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=Decimal("0.2000"),
    )
    high = reader.TextRegion(
        text="b",
        location=reader.SourceLocation(page_index=0, left=0.0, top=2.0, right=1.0, bottom=3.0),
        extraction_confidence=Decimal("0.9000"),
    )
    reading = reader.Reading(regions=(low, high), backend=reader.Backend.OCR, pages_read=1)

    with pytest.raises(reader.VisionFallbackUnavailableError) as raised:
        reader._vision_fallback(reading, Decimal("0.5000"))

    # the LOWEST score, not the first, not the highest, not an average
    assert "0.2000" in str(raised.value)
    assert "0.5000" in str(raised.value)


def test_the_vision_fallback_message_names_every_reason_completely() -> None:
    """§J.2 - the exact result, not merely that VisionFallbackUnavailableError fired.

    Pins every one of the five literal segments the message is assembled from,
    so a mutation to any one of them - a changed word, a flipped case, a
    fragment silently dropped or wrapped - turns this test red, not merely
    'some `VisionFallbackUnavailableError` was raised'.
    """
    low = reader.TextRegion(
        text="a",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=Decimal("0.2000"),
    )
    reading = reader.Reading(regions=(low,), backend=reader.Backend.OCR, pages_read=1)

    with pytest.raises(reader.VisionFallbackUnavailableError) as raised:
        reader._vision_fallback(reading, Decimal("0.5000"))

    assert str(raised.value) == (
        "OCR returned a region scored 0.2000, below the supplied vision-fallback "
        "threshold 0.5000, so the Gemini Vision fallback was reached. It cannot "
        "run: TECHNOLOGY_STACK.md records no API key for it, and records the trigger "
        "threshold as 'UNKNOWN - REQUIRES A NUMBER FROM THE OWNER'. The OCR reading is "
        "deliberately NOT returned in its place - a caller who asked for the fallback "
        "and silently received the reading it was meant to replace would have no way "
        "to know which backend produced the evidence."
    )


def test_vision_fallback_reports_no_lowest_score_when_no_region_scored() -> None:
    """`min(..., default=None)` on an empty reading - the router never actually
    calls this with zero regions (nothing would be 'below threshold'), but the
    function's own contract is real logic and is tested directly rather than
    only through a caller that happens never to exercise it this way.
    """
    reading = reader.Reading(regions=(), backend=reader.Backend.OCR, pages_read=1)

    with pytest.raises(reader.VisionFallbackUnavailableError, match="None"):
        reader._vision_fallback(reading, Decimal("0.5000"))


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


def top_level_imports(module_path: pathlib.Path) -> set[str]:
    """Every distribution `module_path` imports, by AST rather than by text.

    An earlier version of this test searched the source for the banned names and
    was red on the docstring that explains why they are banned - it asserted
    'the file does not mention them', which was never the property that matters.
    Reading the import statements asserts the real one: nothing unapproved is
    actually reachable from this module.
    """
    source = module_path.read_text(encoding="utf-8")
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
    imported = top_level_imports(authored_path(reader))
    offenders = {name for name in imported if name.lower() in NOT_APPROVED}
    assert offenders == set(), f"{sorted(offenders)} not approved by TECHNOLOGY_STACK.md"


def test_the_reader_imports_only_the_approved_stack() -> None:
    """Stricter than a denylist: the whole import list is pinned.

    A denylist only catches the engines someone thought to ban. This turns red
    for ANY third-party import added later, approved or not, which is what makes
    a silent technology swap impossible rather than merely discouraged.
    """
    assert top_level_imports(authored_path(reader)) == {
        # standard library
        "__future__",
        "importlib",
        "io",
        "dataclasses",
        "decimal",
        "enum",
        "functools",
        "typing",
        # TECHNOLOGY_STACK.md, Engine 1 — reached through the PDF Engine, never
        # directly. This entry was `pymupdf` until F-001, and the swap is the
        # whole point of that ruling: *"Engine 1 never depends directly on
        # PyMuPDF."* If `pymupdf` ever reappears in this set, that ruling has
        # been undone, and this test is one of the two places it shows
        # (`test_pdf_backend.py` sweeps the whole engine for the same thing).
        "accountant_dad",
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
    source = authored_source(reader)
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


# ── the boundary is structural, and a new call site cannot skip it ────────
#
# THE CLASS, NOT THE INSTANCE (§I.12, §J.9). PaddlePaddle's C++
# `NotImplementedError` escaping `read_by_ocr` was one symptom. The defect is
# general and `reader.py` had it in three places at once:
#
#     AN ERROR BOUNDARY THAT NAMES EXCEPTION TYPES IS AN ALLOWLIST OVER A SET
#     THE VENDOR CONTROLS.
#
# `_decode_image` enumerated three Pillow/builtin types; the import and the
# recogniser call had no boundary at all. Every one of those was written against
# the failures somebody IMAGINED — "the library is missing" — rather than the
# one that happened: the library is present and breaks at runtime, on this CPU,
# at this version. A vendor may raise anything, and paddle proved the set is open.
#
# The behavioural tests further down prove today's call sites convert today's
# failures. They cannot prove anything about a call site added next year. This
# one reads the structure, so a new vendor call without a boundary is red before
# anyone has to think of the exception type it might raise.


#: Every name in `reader.py` through which a third-party library is entered.
#: `predict` is PaddleOCR, `open`/`get_pixmap`/`get_text`/`tobytes` are PyMuPDF,
#: `Image.open`/`convert` are Pillow, `asarray` is numpy, `import_module` is how
#: PaddleOCR arrives at all. Adding a vendor call under a NEW name is the one
#: hole here, and `test_the_reader_imports_only_the_approved_stack` above is what
#: closes it: no new third-party name can enter this module unnoticed.
VENDOR_CALLS = frozenset(
    {
        "import_module",
        "predict",
        "get_text",
        "get_pixmap",
        "tobytes",
        "asarray",
        "convert",
        # `close` is here because CLEANUP IS A VENDOR CALL TOO. It sat in a
        # `finally` beside the converting `except`, which does not guard it —
        # a PyMuPDF failure while closing a damaged document would have escaped
        # through the one place nobody thinks to look. Both call sites now nest
        # the `try/finally` inside the converting `try`.
        "close",
    }
)


def _enclosing_handlers(tree: ast.AST) -> dict[ast.AST, list[ast.ExceptHandler]]:
    """Map every node to the `except` handlers of every `try` enclosing it.

    Walked downwards from each `try` rather than upwards from each call, because
    `ast` nodes carry no parent pointer and a call can sit many levels inside a
    `with`, a comprehension or a nested loop.
    """
    handlers: dict[ast.AST, list[ast.ExceptHandler]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for guarded in node.body:
            for descendant in ast.walk(guarded):
                handlers.setdefault(descendant, []).extend(node.handlers)
    return handlers


def _catches_every_exception(handler: ast.ExceptHandler) -> bool:
    """True for `except Exception` and bare `except:`, false for a named subset.

    `except Exception` and not `except BaseException` is the deliberate limit:
    `KeyboardInterrupt` and `SystemExit` are the operator stopping the process,
    never a verdict on a document, and converting those would make the engine
    unkillable-looking rather than honest.
    """
    if handler.type is None:
        return True
    return isinstance(handler.type, ast.Name) and handler.type.id in {
        "Exception",
        "BaseException",
    }


def test_every_vendor_call_in_the_reader_sits_inside_a_total_error_boundary() -> None:
    """No third-party call may run outside a handler that catches `Exception`.

    This is the test that makes the class non-recurring. It does not care WHICH
    exception a vendor raises — that is exactly the question the old code got
    wrong by trying to answer it in advance.

    Falsify it by deleting any `except Exception` in `reader.py`, or by
    narrowing one back to a named type: this turns red and names the call.
    """
    tree = authored_tree(reader)
    handlers = _enclosing_handlers(tree)

    unguarded: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if called not in VENDOR_CALLS:
            continue
        if not any(_catches_every_exception(h) for h in handlers.get(node, ())):
            unguarded.append(f"{called}() at line {node.lineno}")

    assert unguarded == [], (
        f"these third-party calls in reader.py are not inside a handler that "
        f"catches Exception: {unguarded}. A boundary that names exception types "
        "is an allowlist over a set the vendor controls — PaddlePaddle raised a "
        "C++ NotImplementedError through exactly such a gap. Wrap the call and "
        "convert whatever crosses into this module's own named error."
    )


def test_the_boundary_validator_can_actually_fail() -> None:
    """Falsification of the test above (§D.13): a validator that passes
    everything is worse than no validator, because it reports safety.

    Both halves are asserted on source this test writes itself, so the check is
    proved on a known-bad and a known-good input rather than trusted.
    """
    unguarded = ast.parse("def f(engine, page):\n    return engine.predict(page)\n")
    enumerated = ast.parse(
        "def f(engine, page):\n"
        "    try:\n"
        "        return engine.predict(page)\n"
        "    except ValueError as e:\n"
        "        raise RecognitionFailedError() from e\n"
    )
    total = ast.parse(
        "def f(engine, page):\n"
        "    try:\n"
        "        return engine.predict(page)\n"
        "    except Exception as e:\n"
        "        raise RecognitionFailedError() from e\n"
    )

    def guarded(tree: ast.AST) -> bool:
        handlers = _enclosing_handlers(tree)
        return all(
            any(_catches_every_exception(h) for h in handlers.get(node, ()))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in VENDOR_CALLS
        )

    assert not guarded(unguarded), "the validator accepted a vendor call with no try at all"
    assert not guarded(enumerated), "the validator accepted an ENUMERATED handler - the whole bug"
    assert guarded(total), "the validator rejects a correct total boundary; it would never pass"


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


# ── the escalation branch, driven both ways ───────────────────────────────
#
# `reader.read` decides, on the OCR path, whether a reading is too unsure to
# stand: ANY region scored below the caller's threshold goes to the vision
# fallback; everything else comes back as read. Neither outcome had ever
# executed. Everything on that path runs after `read_by_ocr`, and
# `read_by_ocr` calls `_recogniser()` before it does anything else, so with
# PaddleOCR absent (F-009) there is no argument to `reader.read` that reaches
# the comparison at all.
#
# So the recogniser is substituted at the narrowest edge available - the
# `paddleocr` module - and nothing else is. `reader._recogniser` still runs for
# real, including its `importlib` lookup, its factory call and its cache; so
# does every line of `read_by_ocr`, the rasteriser, the image decode and the
# comparison under test.
#
# NO THRESHOLD IS INVENTED HERE. `TECHNOLOGY_STACK.md` records the real
# vision-fallback threshold as "UNKNOWN - REQUIRES A NUMBER FROM THE OWNER" and
# it stays unknown. Every threshold below is one of the scores the recogniser
# just reported, reached with `min`, `max` or `sorted`, and the properties
# asserted are orderings that hold for ANY numbers: nothing is strictly below
# the minimum, and the minimum is strictly below the maximum.

Corner = tuple[int, int]
Outline = tuple[Corner, Corner, Corner, Corner]


@dataclass(frozen=True, slots=True)
class ScriptedLine:
    """One line a substituted recogniser will report: text, score, outline."""

    text: str
    score: float
    box: Outline


def a_box_at(row: int) -> Outline:
    """A 100x20 outline whose FIRST corner is the bottom-right one.

    Deliberately not top-left-first. A real recogniser returns the corners in
    the order it found them, and a rotated or skewed line genuinely arrives
    like this. The order is what tells `min`/`max` over the whole polygon apart
    from "take the first point", which a tidy axis-aligned box would hide.
    """
    top = 10 + 20 * row
    return ((110, top + 20), (10, top + 20), (10, top), (110, top))


#: What the substituted recogniser reports. These are RECOGNISER OUTPUT - test
#: input - and every threshold used below is derived from them.
SCRIPTED_LINES: tuple[ScriptedLine, ...] = (
    ScriptedLine(text="TAX INVOICE", score=0.9, box=a_box_at(0)),
    ScriptedLine(text="Taxable Value 165000.00", score=0.2, box=a_box_at(1)),
    ScriptedLine(text="Total 194700.00", score=0.55, box=a_box_at(2)),
)

SCRIPTED_TEXTS: tuple[str, ...] = tuple(line.text for line in SCRIPTED_LINES)
SCRIPTED_SCORES: tuple[Decimal, ...] = tuple(Decimal(str(line.score)) for line in SCRIPTED_LINES)

#: Derived, never chosen. Nothing is strictly below the lowest score reported,
#: and the lowest is strictly below both of the others - true of any three
#: distinct numbers, which is why these are thresholds and not a threshold.
LOWEST_SCORE_REPORTED = min(SCRIPTED_SCORES)
MIDDLE_SCORE_REPORTED = sorted(SCRIPTED_SCORES)[1]
HIGHEST_SCORE_REPORTED = max(SCRIPTED_SCORES)


class _ScriptedResult:
    """One PaddleOCR result, exposing exactly the keys 3.7.0 populates.

    A plain dict would serve, but recording which keys were read pins the three
    `reader` documents. A fourth arriving later would be a field the real
    backend may not populate at all, and it would be invisible in the output.
    """

    def __init__(self, payload: dict[str, object], asked: list[str]) -> None:
        self._payload = payload
        self._asked = asked

    def __getitem__(self, key: str) -> object:
        self._asked.append(key)
        return self._payload[key]


class _ScriptedRecogniser:
    """Reports `lines` for every page it is shown, and records what it was shown."""

    def __init__(self, lines: tuple[ScriptedLine, ...]) -> None:
        self._lines = lines
        self.pages_seen: list[reader.Page] = []
        self.keys_asked: list[str] = []

    def predict(self, image: reader.Page) -> list[reader._OcrResult]:
        self.pages_seen.append(image)
        payload: dict[str, object] = {
            "rec_texts": [line.text for line in self._lines],
            "rec_scores": [line.score for line in self._lines],
            "rec_polys": [numpy.array(line.box, dtype=numpy.int16) for line in self._lines],
        }
        return [_ScriptedResult(payload, self.keys_asked)]


#: How `reader` asked for a recogniser: language, the three preprocessing
#: switches, and the kernel. Recorded whole rather than field by field, so an
#: argument added later cannot go unnoticed.
BuildRequest = tuple[str, bool, bool, bool, bool]


class _RecordingFactory[R: reader._Recogniser]:
    """Stands in for `paddleocr.PaddleOCR`, and records how `reader` builds it.

    Generic in the recogniser it hands back, so the SAME recording factory
    serves a recogniser that succeeds, one that explodes and one that answers
    with the wrong shape. A second copy of it per failure mode would be a second
    place for the construction contract to drift (Law 14).
    """

    def __init__(self, recogniser: R) -> None:
        self.recogniser: R = recogniser
        self.languages: list[str] = []
        self.preprocessing: list[tuple[bool, bool, bool]] = []
        self.onednn: list[bool] = []

    def __call__(
        self,
        *,
        lang: str,
        use_doc_orientation_classify: bool,
        use_doc_unwarping: bool,
        use_textline_orientation: bool,
        enable_mkldnn: bool,
    ) -> R:
        self.languages.append(lang)
        self.preprocessing.append(
            (use_doc_orientation_classify, use_doc_unwarping, use_textline_orientation)
        )
        self.onednn.append(enable_mkldnn)
        return self.recogniser


class _UnbuildableFactory:
    """A `PaddleOCR` that raises instead of returning. Model weights are fetched
    over the network during construction, so this is not a hypothetical."""

    def __init__(self, failure: Exception) -> None:
        self._failure = failure
        self.attempts: list[BuildRequest] = []

    def __call__(
        self,
        *,
        lang: str,
        use_doc_orientation_classify: bool,
        use_doc_unwarping: bool,
        use_textline_orientation: bool,
        enable_mkldnn: bool,
    ) -> reader._Recogniser:
        self.attempts.append(
            (
                lang,
                use_doc_orientation_classify,
                use_doc_unwarping,
                use_textline_orientation,
                enable_mkldnn,
            )
        )
        raise self._failure


class _FailingRecogniser:
    """A recogniser that is built fine and then explodes on the page."""

    def __init__(self, failure: Exception) -> None:
        self._failure = failure
        self.pages_seen: list[reader.Page] = []

    def predict(self, image: reader.Page) -> list[reader._OcrResult]:
        self.pages_seen.append(image)
        raise self._failure


class _RaggedRecogniser:
    """A recogniser whose three documented lists are not the same length.

    A DIFFERENT DEFECT FROM `_MisshapenRecogniser`, AND A QUIETER ONE. A missing
    key raises `KeyError` the moment it is read. Three lists of unequal length
    raise NOTHING: `zip` simply stops at the shortest one, so a result carrying
    three texts and two scores yields two regions and the third line vanishes
    with no error anywhere. `reader` passes `strict=True` precisely to turn that
    silence into a failure, and nothing measured it.

    Real, not hypothetical: `rec_texts`, `rec_scores` and `rec_polys` are three
    separate arrays a pinned-but-living dependency assembles independently, and
    any version that filters one of them without filtering the others produces
    exactly this shape.
    """

    def __init__(self, short_key: str) -> None:
        self._short_key = short_key
        self.pages_seen: list[reader.Page] = []

    def predict(self, image: reader.Page) -> list[reader._OcrResult]:
        self.pages_seen.append(image)
        payload: dict[str, object] = {
            "rec_texts": [line.text for line in SCRIPTED_LINES],
            "rec_scores": [line.score for line in SCRIPTED_LINES],
            "rec_polys": [numpy.array(line.box, dtype=numpy.int16) for line in SCRIPTED_LINES],
        }
        # One element short. Which one is the parameter, because `zip` stops at
        # the shortest whichever position it is in.
        payload[self._short_key] = cast(list[object], payload[self._short_key])[:-1]
        return [_ScriptedResult(payload, [])]


class _MisshapenRecogniser:
    """A recogniser that returns a result missing one of the three documented keys.

    PaddleOCR is a pinned but living dependency; a renamed key is a real way for
    recognition to stop working without anything raising inside `reader` itself.
    """

    def __init__(self, drop: str) -> None:
        self._drop = drop
        self.pages_seen: list[reader.Page] = []

    def predict(self, image: reader.Page) -> list[reader._OcrResult]:
        self.pages_seen.append(image)
        payload: dict[str, object] = {
            "rec_texts": [line.text for line in SCRIPTED_LINES],
            "rec_scores": [line.score for line in SCRIPTED_LINES],
            "rec_polys": [numpy.array(line.box, dtype=numpy.int16) for line in SCRIPTED_LINES],
        }
        del payload[self._drop]
        return [_ScriptedResult(payload, [])]


class _FakePaddleOcr(types.ModuleType):
    """A real module object carrying one attribute, so `import_module` finds it."""

    PaddleOCR: reader._RecogniserFactory


InstallRecogniser = Callable[[tuple[ScriptedLine, ...]], _RecordingFactory[_ScriptedRecogniser]]
InstallFactory = Callable[[reader._RecogniserFactory], None]
ForgetTheRecogniser = Callable[[], None]


@pytest.fixture
def a_clean_recogniser_cache() -> Iterator[ForgetTheRecogniser]:
    """Empty `reader._recogniser`'s cache on the way IN and again on the way OUT,
    and hand out the means to empty it in between.

    `reader._recogniser` is `@cache`d, so anything a test puts behind it would
    otherwise silently answer every LATER test in the process - including the
    `@needs_the_real_ocr` ones wherever PaddleOCR is genuinely installed, whose
    whole value is that they run against the real backend. That is a false
    green of exactly the kind §J exists to prevent, so it is closed by
    construction rather than by remembering (§J.6).

    Written once and depended on by every fixture below (Law 14). A second copy
    of this discipline is a second place for it to be got wrong, and getting it
    wrong is invisible - it leaks into a later test rather than failing this one.
    """
    reader._recogniser.cache_clear()
    yield reader._recogniser.cache_clear
    reader._recogniser.cache_clear()


@pytest.fixture
def install_paddleocr(
    monkeypatch: pytest.MonkeyPatch, a_clean_recogniser_cache: ForgetTheRecogniser
) -> InstallFactory:
    """Put ANY factory behind `importlib.import_module("paddleocr")`."""

    def install(factory: reader._RecogniserFactory) -> None:
        module = _FakePaddleOcr("paddleocr")
        module.PaddleOCR = factory
        monkeypatch.setitem(sys.modules, "paddleocr", module)
        a_clean_recogniser_cache()

    return install


@pytest.fixture
def paddleocr_is_absent(
    monkeypatch: pytest.MonkeyPatch, a_clean_recogniser_cache: ForgetTheRecogniser
) -> Iterator[list[str]]:
    """Make the dynamic import fail the way a deployment with no OCR installed does.

    Yields the list of module names the code under test actually tried to
    import, which is what lets a caller assert that the OCR path was REACHED
    rather than merely that nothing came back.

    THE ABSENCE IS CREATED, NEVER ASSUMED, AND THAT IS THE WHOLE POINT.
    The tests using this fixture used to rely on PaddleOCR simply not being
    installed on the machine running them (`KNOWN_FAILURES.md` F-002, F-009).
    That is not a test fixture, it is an environmental accident, and the moment
    F-009 was fixed and CI grew an interpreter that DOES have PaddleOCR, those
    tests asserted something that was no longer true and turned red - measured
    at commit `c4fbb5f`, not predicted.

    The general principle, so the class cannot recur (§J.9): A TEST THAT NEEDS A
    DEPENDENCY TO BE ABSENT MUST CREATE THE ABSENCE. Otherwise it is really a
    test of the environment, it silently changes meaning when the environment
    changes, and it is at its least trustworthy exactly when someone has just
    improved the environment.

    `importlib.import_module` is the narrowest possible edge to fake here
    (§J.7): it is the single call `reader._recogniser` makes to reach PaddleOCR,
    everything else in the path stays real, and a module that resolves under a
    different name is not quietly accepted.
    """
    real_import_module = importlib.import_module
    attempted: list[str] = []

    def refuse(name: str) -> types.ModuleType:
        attempted.append(name)
        if name == "paddleocr":
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", refuse)
    # Cleared AFTER the refusal is in place, so a recogniser built by anything
    # earlier in this process cannot answer from the cache and make the import
    # look as though it never happened.
    a_clean_recogniser_cache()

    yield attempted


@pytest.fixture
def substitute_the_recogniser(install_paddleocr: InstallFactory) -> InstallRecogniser:
    """A scripted recogniser that SUCCEEDS, and records how `reader` built it."""

    def install(lines: tuple[ScriptedLine, ...]) -> _RecordingFactory[_ScriptedRecogniser]:
        factory = _RecordingFactory(_ScriptedRecogniser(lines))
        install_paddleocr(factory)
        return factory

    return install


def test_no_region_below_the_threshold_returns_the_reading_exactly_as_read(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """The branch's other outcome, and the strict-comparison boundary at once.

    The threshold IS the lowest score reported, so the lowest-scored region sits
    exactly ON it. `<` is strict, so nothing is below it and nothing escalates.
    A comparison loosened to `<=` escalates here and turns this red - which is
    the only way to tell the two apart from outside.

    `COMMUNICATION_RULES_INPUT_ENGINE.md` §3 Rule 5: low confidence creates no
    guessed value, no default value, no silently omitted field and no upgraded
    score. So all three lines come back, in order, carrying the score the
    backend reported - including the low one, which is the one Rule 5 is about.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert reading.backend is reader.Backend.OCR
    assert tuple(region.text for region in reading.regions) == SCRIPTED_TEXTS
    assert tuple(region.extraction_confidence for region in reading.regions) == SCRIPTED_SCORES
    assert reading.pages_read == 1
    assert len(factory.recogniser.pages_seen) == 1, "the recogniser was never actually reached"


#: PDF user space is 1/72 inch, fixed by the PDF specification. A UNIT
#: CONVERSION, not a tuning value and not a default - `pdf_backend` names the
#: same constant for the same reason. No other number is arithmetically correct.
POINTS_PER_INCH = 72


def test_the_callers_dpi_decides_the_raster_the_recogniser_actually_sees(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """`read` forwards the caller's DPI to the rasteriser, and nothing checked it.

    A mutation run found this one, and it is the most dangerous survivor in the
    module: rewriting `_render_pdf_pages(document, render_dpi=render_dpi)` to
    `render_dpi=None` inside `reader.read` left ALL 83 covering tests green.
    PyMuPDF accepts `dpi=None` without raising and falls back to 72 - so a
    caller asking for 300 dpi silently got a page rendered at 72, OCR ran on it,
    and a full reading came back with every coordinate in a space 4.17x smaller
    than the one requested. Nothing raises, nothing warns, and the regions look
    perfectly plausible.

    `test_render_pdf_pages_declares_pdf_the_callers_dpi_and_png_to_pymupdf` does
    not cover it: that one calls `_render_pdf_pages` DIRECTLY, so it proves the
    rasteriser honours the DPI it is given and says nothing about which DPI
    `read` gives it. The gap was exactly one function call wide.

    This is the F-028 defect class arriving by another route. `pdf_backend`
    states it: *"a page whose coordinate space is a function of a render setting
    is not reproducible"*, and `reader.SourceLocation` promises the backend's own
    space kept unnormalised precisely so *"a human can find the region again."*

    ASSERTED ON THE PIXELS, NOT ON THE CALL. A recorded argument proves what was
    passed; the raster's own dimensions prove what was DONE with it, and they are
    what the recogniser actually saw. The expected size is computed from the
    page's real point size, so no magic number stands in for the fixture.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)
    document = an_image_only_pdf()

    reader.read(
        document,
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    opened = pdf_backend.open_pdf(document)
    width_points, height_points = pdf_backend.page_size(opened, 0)
    pdf_backend.close_pdf(opened)

    height_pixels, width_pixels = factory.recogniser.pages_seen[0].shape[:2]
    scale = FIXTURE_DPI / POINTS_PER_INCH
    assert (height_pixels, width_pixels) == (
        math.ceil(height_points * scale),
        math.ceil(width_points * scale),
    ), (
        f"a {width_points}x{height_points}pt page rendered for OCR at "
        f"{FIXTURE_DPI} dpi reached the recogniser as {width_pixels}x"
        f"{height_pixels}px; the caller's DPI was not the one used"
    )
    # The falsifier, named rather than implied: 72 dpi is what PyMuPDF silently
    # substitutes when the DPI goes missing, and at 72 dpi the raster is exactly
    # the page's point size. That is the reading this test exists to refuse.
    assert (height_pixels, width_pixels) != (
        math.ceil(height_points),
        math.ceil(width_points),
    ), "the page was rendered at PyMuPDF's 72 dpi fallback, not at the DPI asked for"


def test_one_region_below_the_threshold_escalates_instead_of_returning_the_reading(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """The branch that decides "OCR was too unsure" - never executed until now.

    The threshold is the HIGHEST score reported, so the lowest is strictly below
    it and the highest is not: `any` is true, `all` is false. A comparison
    rewritten to demand every region be below the threshold returns a reading
    here and turns this red.

    The escalation is a raise, not a quieter reading. `TECHNOLOGY_STACK.md`
    records no API key and no threshold for the Gemini fallback, so the only
    honest outcome is refusal - and the refusal is what a caller must be unable
    to mistake for evidence.
    """
    substitute_the_recogniser(SCRIPTED_LINES)

    with pytest.raises(reader.VisionFallbackUnavailableError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=HIGHEST_SCORE_REPORTED,
        )

    assert str(LOWEST_SCORE_REPORTED) in str(raised.value)
    assert str(HIGHEST_SCORE_REPORTED) in str(raised.value)


def test_the_escalation_names_the_lowest_score_and_the_threshold_it_was_given(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """The uncertainty is RECORDED and NAMED, not merely signalled by a type.

    With the threshold set to the middle score, exactly one region is below it.
    The message must say which score triggered the escalation - the lowest one -
    and against which threshold. Asserting only that the error fired would stay
    green through a message that named the wrong number, and a human reading
    that message is the whole reason the number is in it (`ENGINE_1:511`).

    The highest score must NOT appear: reporting it would mean the fallback was
    handed the wrong end of the reading.
    """
    substitute_the_recogniser(SCRIPTED_LINES)

    with pytest.raises(reader.VisionFallbackUnavailableError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=MIDDLE_SCORE_REPORTED,
        )

    assert str(raised.value).startswith(
        f"OCR returned a region scored {LOWEST_SCORE_REPORTED}, below the supplied "
        f"vision-fallback threshold {MIDDLE_SCORE_REPORTED}, "
    )
    assert str(HIGHEST_SCORE_REPORTED) not in str(raised.value)


def test_the_escalation_carries_no_reading_out_with_it(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """Inversion: the dangerous kindness is attaching the OCR reading to the error.

    `reader.py` states the OCR reading is *"deliberately NOT returned in its
    place"*, and a caller who received it anyway - as an argument, or as an
    attribute someone added later to be helpful - would have no way to know
    which backend produced the evidence it went on to use. Returning it is
    already impossible because the function raises; smuggling it is not, so it
    is asserted rather than assumed.
    """
    substitute_the_recogniser(SCRIPTED_LINES)

    with pytest.raises(reader.VisionFallbackUnavailableError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=HIGHEST_SCORE_REPORTED,
        )

    smuggled = [item for item in raised.value.args if isinstance(item, reader.Reading)]
    smuggled += [item for item in vars(raised.value).values() if isinstance(item, reader.Reading)]
    assert smuggled == [], f"the OCR reading left the failure inside the error: {smuggled}"


def test_a_pdf_with_no_text_layer_is_rasterised_and_then_recognised(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """The whole PDF route, end to end, for the first time.

    `test_an_image_only_pdf_reaches_the_ocr_path_before_failing_on_missing_paddleocr`
    proves the router GETS to the recogniser; it cannot prove what happens after,
    because the process dies there. This one runs the rest: rasterise, decode,
    recognise, compare against the threshold, return.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    reading = reader.read(
        an_image_only_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert reading.backend is reader.Backend.OCR
    assert tuple(region.text for region in reading.regions) == SCRIPTED_TEXTS
    assert len(factory.recogniser.pages_seen) == 1
    # The rasterised page reached the recogniser as a real three-channel RGB
    # array, not as the PNG bytes PyMuPDF produced.
    assert factory.recogniser.pages_seen[0].shape[2] == RGB_CHANNELS


def test_a_recognised_line_that_is_only_whitespace_is_dropped_not_emitted(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """A blank recognition is not a reading, and must not pad the region count.

    The same property the text-layer path is already held to
    (`test_a_whitespace_only_span_is_skipped_not_emitted_as_an_empty_region`),
    asserted for the OCR path, where it had never run. An empty region carries
    no evidence a human could check and would still count as something read.
    """
    lines = (
        SCRIPTED_LINES[0],
        ScriptedLine(text="   ", score=0.5, box=a_box_at(1)),
        SCRIPTED_LINES[2],
    )
    substitute_the_recogniser(lines)

    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert tuple(region.text for region in reading.regions) == (
        SCRIPTED_LINES[0].text,
        SCRIPTED_LINES[2].text,
    )


def test_the_reported_score_is_carried_verbatim_and_never_re_expanded(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """`Decimal(str(score))`, not `Decimal(score)` - and the difference is visible.

    None of these three scores is exactly representable in binary, so
    `Decimal(0.2)` is `0.200000000000000011102230246251565404236316680908203125`
    - a number PaddleOCR never reported. Pinning the STRING form catches that
    substitution; pinning only "is a Decimal in [0, 1]" would not.
    """
    substitute_the_recogniser(SCRIPTED_LINES)

    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert [str(region.extraction_confidence) for region in reading.regions] == [
        "0.9",
        "0.2",
        "0.55",
    ]


def test_a_recognised_region_is_located_by_its_whole_outline_not_its_first_corner(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """`a_box_at` puts the bottom-right corner first, so the two differ.

    `ENGINE_1:511` - source locations are emitted even for low-confidence
    extractions, because that is what makes a later human check possible. A
    location taken from `polygon[0]` would put every box's left edge at its
    right edge, and a human sent to check the value would be sent to the wrong
    place while every other assertion in this file stayed green.
    """
    substitute_the_recogniser(SCRIPTED_LINES)

    reading = reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    corners = [
        (region.location.left, region.location.top, region.location.right, region.location.bottom)
        for region in reading.regions
    ]
    assert corners == [
        (10.0, 10.0, 110.0, 30.0),
        (10.0, 30.0, 110.0, 50.0),
        (10.0, 50.0, 110.0, 70.0),
    ]
    assert all(region.location.page_index == 0 for region in reading.regions)


def test_the_recogniser_is_built_with_every_preprocessing_stage_switched_off(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """`ENGINE_1` §8.1 - `cleaner` owns document preprocessing, and only `cleaner`.

    Orientation classification, unwarping and text-line orientation are all
    document cleanup. Running them inside `reader` would put one responsibility
    in two places (INV-10) and would make `cleaner`'s output not the thing the
    recogniser actually saw. The construction is invisible in the reading, so it
    is asserted on the call rather than on the result.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert factory.preprocessing == [(False, False, False)]
    assert factory.languages == ["en"]


def test_the_recogniser_is_built_once_and_reused_for_every_later_read(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """Constructing it loads model weights; a fresh one per read pays for it again.

    Two reads, one construction. A `@cache` removed from `_recogniser` would
    build it twice and turn this red - and would otherwise be invisible, because
    every reading returned would be identical.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    for _ in range(2):
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=LOWEST_SCORE_REPORTED,
        )

    assert factory.languages == ["en"], "the recogniser was rebuilt rather than reused"
    assert len(factory.recogniser.pages_seen) == BOTH_PAGES


def test_the_reader_asks_the_recogniser_for_exactly_the_three_documented_keys(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """`reader.py` names the three keys PaddleOCR 3.7.0 populates for a text-only
    pipeline, read off a real result rather than assumed. A fourth key read
    later would be a field the real backend may not populate at all, and the
    reading would be missing or wrong in a way no assertion on text would see.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert set(factory.recogniser.keys_asked) == {"rec_texts", "rec_scores", "rec_polys"}


def test_the_recogniser_is_built_with_the_onednn_kernel_path_disabled(
    substitute_the_recogniser: InstallRecogniser,
) -> None:
    """Pins the kernel `reader` asks PaddleOCR for, because the default breaks.

    PaddleOCR 3.7.0 defaults `enable_mkldnn` to `True` (`_constants.py:18`), and
    on CI's x86-64 runner that routes every convolution through Paddle's oneDNN
    instruction path, which raised on all twelve OCR tests at commit `c4fbb5f`:

        NotImplementedError: (Unimplemented) ConvertPirAttribute2Runtime
        Attribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
        (at .../new_executor/instruction/onednn/onednn_instruction.cc:116)

    `_common_args.py:90-94` is the whole mechanism: on a CPU device
    `enable_mkldnn=False` sets `run_mode="paddle"`, the plain kernels, and the
    oneDNN instruction path is never built. Both facts were read out of the
    pinned 3.7.0 wheel, not recalled.

    This is asserted on the CALL because it is invisible in the reading - the
    two kernels compute the same function, so nothing downstream reveals which
    one ran. Delete the argument and the local suite still passes while CI
    returns to twelve red; this test is what stands in that gap.
    """
    factory = substitute_the_recogniser(SCRIPTED_LINES)

    reader.read(
        an_invoice_png(),
        media_type=reader.MediaType.IMAGE,
        render_dpi=FIXTURE_DPI,
        vision_fallback_threshold=LOWEST_SCORE_REPORTED,
    )

    assert factory.onednn == [False]


# ── the recogniser failing is NOT the document being bad ──────────────────
#
# Every test below exists because of one measured defect. `read_by_ocr` called
# `engine.predict` with no failure boundary at all, so whatever PaddleOCR raised
# left `reader` wearing PaddleOCR's name. On CI that was a `NotImplementedError`
# carrying a C++ file path, which is a Python builtin meaning "this abstract
# method is unimplemented" - so any caller anywhere up the stack with an
# `except NotImplementedError` for its OWN purposes swallows a dead OCR engine.
#
# `COMMUNICATION_RULES_INPUT_ENGINE.md` §4 item 9 requires failed extractions to
# cross the boundary as NAMED uncertainty. A C++ message is not a name.


#: The upstream failure `ocr tests` actually produced, verbatim, at commit
#: `c4fbb5f`. Copied from the CI log rather than paraphrased: the point of these
#: tests is that `reader` survives THIS, and a tidied-up message would be a
#: different input than the one that broke it.
ONEDNN_FAILURE_MESSAGE = (
    "(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support "
    "[pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/"
    "new_executor/instruction/onednn/onednn_instruction.cc:116)"
)


def a_paddle_onednn_failure() -> NotImplementedError:
    """A FRESH instance per call. A shared exception object accumulates
    `__traceback__` and `__context__` from whichever test raised it first, so
    reusing one silently couples these tests to their execution order."""
    return NotImplementedError(ONEDNN_FAILURE_MESSAGE)


def test_a_recogniser_that_explodes_raises_a_named_reader_error(
    install_paddleocr: InstallFactory,
) -> None:
    """The CI failure, reproduced exactly, then required to arrive named."""
    install_paddleocr(_RecordingFactory(_FailingRecogniser(a_paddle_onednn_failure())))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )

    assert isinstance(raised.value, reader.ReaderError)


def test_the_recognition_failure_preserves_the_upstream_error_completely(
    install_paddleocr: InstallFactory,
) -> None:
    """Naming the failure must not COST the diagnosis.

    Wrapping is only an improvement if the thing wrapped survives. The upstream
    type, its exact text and the original exception object all have to reach
    whoever has to debug it - a named error that eats the C++ file and line has
    replaced an unhelpful message with a differently unhelpful one.
    """
    original = a_paddle_onednn_failure()
    install_paddleocr(_RecordingFactory(_FailingRecogniser(original)))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    message = str(raised.value)
    assert "NotImplementedError" in message
    assert ONEDNN_FAILURE_MESSAGE in message
    assert raised.value.__cause__ is original


def test_the_recognition_failure_names_which_page_failed(
    install_paddleocr: InstallFactory,
) -> None:
    """A multi-page document that dies on page 2 must not report page 1's number.

    The first page recognises normally; only the second raises. Without the
    index in the message, every page of a fifty-page scan produces the identical
    error and nothing says where to look.
    """

    class _FailsOnTheSecondPage:
        def __init__(self) -> None:
            self.pages_seen: list[reader.Page] = []

        def predict(self, image: reader.Page) -> list[reader._OcrResult]:
            self.pages_seen.append(image)
            if len(self.pages_seen) == 1:
                return [_ScriptedResult({"rec_texts": [], "rec_scores": [], "rec_polys": []}, [])]
            raise a_paddle_onednn_failure()

    recogniser = _FailsOnTheSecondPage()
    install_paddleocr(_RecordingFactory(recogniser))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png(), an_invoice_png()])

    assert len(recogniser.pages_seen) == BOTH_PAGES, "page 0 did not recognise cleanly"
    assert "page 1" in str(raised.value)


def test_a_recognition_failure_is_never_reported_as_an_unreadable_document(
    install_paddleocr: InstallFactory,
) -> None:
    """THE point of the whole section, and the one assertion with teeth.

    `pipeline.BUSINESS_FAILURE` decides by `isinstance` which failures cross the
    Engine 1 boundary as "this document is bad" rather than crashing, and
    `reader.UnreadableDocumentError` is on that list. A broken OCR engine
    reported as an unreadable document would tell a user their invoice is
    damaged when the invoice is fine and our recogniser is not - the exact
    fabrication `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids, and the reason
    `pipeline.py:337-344` already keeps `VisionFallbackUnavailableError` off
    that list. A tool being broken is not a fact about the document.
    """
    install_paddleocr(_RecordingFactory(_FailingRecogniser(a_paddle_onednn_failure())))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )

    assert not isinstance(raised.value, reader.UnreadableDocumentError)
    assert "document" in str(raised.value).lower()


def test_a_genuinely_undecodable_page_is_still_an_unreadable_document(
    install_paddleocr: InstallFactory,
) -> None:
    """Falsification of the test above: the new wrapper must not swallow the
    verdict it was built to sit beside.

    Both failures happen inside `read_by_ocr`. If the boundary were drawn one
    line too wide it would catch `_decode_image`'s `UnreadableDocumentError` and
    relabel a genuinely broken page as a broken engine - losing the distinction
    the module's whole docstring is about. Passing this AND the test above is
    what proves the boundary sits in the right place.

    The recogniser installed here would explode if it were ever reached. It must
    not be: the page is undecodable, so the verdict is reached before any
    recognition is attempted.
    """
    install_paddleocr(_RecordingFactory(_FailingRecogniser(a_paddle_onednn_failure())))

    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader.read_by_ocr([b"this is plainly not an image"])

    assert not isinstance(raised.value, reader.RecognitionFailedError)


#: Exception types deliberately chosen to be ones NOBODY enumerated. The old
#: boundaries listed `UnidentifiedImageError`, `OSError` and `ValueError`, and
#: the OCR path listed nothing at all. A vendor is free to raise any of these
#: and the contract must not depend on having guessed which.
#:
#: `NotImplementedError` is first because it is the one paddle actually raised;
#: the rest are the falsification — if the boundary only survives the measured
#: failure, it was fitted to the instance rather than the class.
UNGUESSABLE_VENDOR_FAILURES = [
    NotImplementedError("(Unimplemented) some future C++ kernel"),
    RuntimeError("CUDA driver version is insufficient"),
    MemoryError("cannot allocate 4.2 GiB for tensor"),
    AttributeError("'NoneType' object has no attribute 'shape'"),
    KeyError("a key nobody documented"),
    ZeroDivisionError("division by zero in a rescale"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    SystemError("PyEval_EvalFrameEx returned a result with an error set"),
]


@pytest.mark.parametrize("failure", UNGUESSABLE_VENDOR_FAILURES, ids=lambda f: type(f).__name__)
def test_any_exception_a_recogniser_raises_becomes_the_named_reader_error(
    failure: Exception, install_paddleocr: InstallFactory
) -> None:
    """The boundary is named by WHERE it is, never by what crosses it.

    The old code enumerated exception types, which is an allowlist over a set
    PaddleOCR controls. Eight unrelated types go in here and exactly one type
    comes out - and the original is never lost.
    """
    install_paddleocr(_RecordingFactory(_FailingRecogniser(failure)))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    assert raised.value.__cause__ is failure
    assert type(failure).__name__ in str(raised.value)


@pytest.mark.parametrize("failure", UNGUESSABLE_VENDOR_FAILURES, ids=lambda f: type(f).__name__)
def test_any_exception_pillow_raises_becomes_the_named_document_error(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same rule at the OTHER vendor boundary, which used to enumerate three types.

    `Image.open` is faked here because Pillow cannot be made to raise a
    `ZeroDivisionError` on demand - the point is precisely that we do not get to
    choose what it raises. Everything else in the path stays real.
    """

    opened: list[object] = []

    def explode(stream: object) -> object:
        opened.append(stream)
        raise failure

    # `Image` here is the very module object `reader` holds in its own globals -
    # both files did `from PIL import Image` - so this replaces the exact
    # function `reader` calls, at the narrowest edge, and nothing else.
    monkeypatch.setattr(Image, "open", explode)

    with pytest.raises(reader.UnreadableDocumentError) as raised:
        reader._decode_image(an_invoice_png())

    assert opened, "Pillow was never reached, so nothing was actually converted"

    assert raised.value.__cause__ is failure
    assert not isinstance(raised.value, reader.RecognitionFailedError)


def test_an_import_failure_that_is_not_a_missing_module_becomes_a_named_reader_error(
    monkeypatch: pytest.MonkeyPatch, a_clean_recogniser_cache: ForgetTheRecogniser
) -> None:
    """PaddleOCR present but failing to import is OUR tool breaking, not a missing one.

    A broken C extension, a missing shared library or a vendor `__init__` that
    raises all arrive here. Only `ModuleNotFoundError` crosses unconverted, and
    the test above pins that; this is its other half.
    """
    failure = ImportError("libgomp.so.1: cannot open shared object file")
    attempted: list[str] = []

    def explode(name: str) -> object:
        attempted.append(name)
        raise failure

    monkeypatch.setattr(importlib, "import_module", explode)
    a_clean_recogniser_cache()

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    assert attempted == ["paddleocr"]
    assert raised.value.__cause__ is failure
    assert not isinstance(raised.value, ModuleNotFoundError)


def test_a_recogniser_that_cannot_be_built_raises_a_named_reader_error(
    install_paddleocr: InstallFactory,
) -> None:
    """Construction downloads model weights over the network, so it fails too.

    Measured on CI at `c4fbb5f`: `PP-OCRv6_medium_det` and `PP-OCRv6_medium_rec`
    are each fetched as five files at first use. A refused connection there is
    the same class of event as a dead kernel - the recogniser did not run - and
    it must not arrive as a bare `OSError` either.
    """
    install_paddleocr(_UnbuildableFactory(OSError("connection refused fetching PP-OCRv6")))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read(
            an_invoice_png(),
            media_type=reader.MediaType.IMAGE,
            render_dpi=FIXTURE_DPI,
            vision_fallback_threshold=NO_FALLBACK,
        )

    assert "connection refused fetching PP-OCRv6" in str(raised.value)


@pytest.mark.parametrize("dropped", ["rec_texts", "rec_scores", "rec_polys"])
def test_a_result_missing_a_documented_key_raises_a_named_reader_error(
    dropped: str, install_paddleocr: InstallFactory
) -> None:
    """A renamed key in a later PaddleOCR is recognition failing, not a crash.

    `reader` documents exactly three keys read off a real 3.7.0 result. If a
    future version renames one, a bare `KeyError('rec_scores')` escapes with no
    statement about what it means - and `KeyError` is the single most commonly
    caught-and-ignored builtin there is.
    """
    install_paddleocr(_RecordingFactory(_MisshapenRecogniser(dropped)))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    assert dropped in str(raised.value)


@pytest.mark.parametrize("short_key", ["rec_texts", "rec_scores", "rec_polys"])
def test_a_result_whose_three_lists_disagree_in_length_refuses_to_read_it_short(
    short_key: str, install_paddleocr: InstallFactory
) -> None:
    """`strict=True` on the `zip`, and it is the only thing standing here.

    THE FAILURE THIS PREVENTS IS SILENT, WHICH IS WHY IT MATTERS. Three texts
    and two scores is not an error to `zip` - it is a two-element iteration.
    Without `strict=True` the reading comes back with a line missing, carrying
    no error, no warning and nothing to distinguish it from an honest reading of
    a page with two lines on it. Every downstream engine would then reason about
    an invoice with a row deleted, and the Confidence Report assembled from it
    would be a confident statement about evidence that was thrown away
    (`CLAUDE.md` Law 11; `ENGINE_1:509` - a region that could not be read *"is
    reported as unread, not omitted silently"*).

    A mutation run is what proved it untested: `strict=True` weakened to
    `strict=False`, to `strict=None` and deleted outright all left the whole
    suite green. So all three lengths are shortened in turn, because `zip` stops
    at the shortest whichever of the three it is.

    The recogniser is scripted at the `paddleocr` MODULE edge, the same
    substitution the section above already uses and for the same reason
    (`CLAUDE.md` §J.7): the property under test is `reader`'s OWN handling of a
    result it does not control, not PaddleOCR's accuracy. Everything else -
    the rasterisation, the decode, the boundary, the conversion - runs for real.
    """
    recogniser = _RaggedRecogniser(short_key)
    install_paddleocr(_RecordingFactory(recogniser))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    assert recogniser.pages_seen, "the recogniser was never reached, so nothing was ragged"
    # `zip(strict=True)` is what refuses; anything else silently truncated.
    assert isinstance(raised.value.__cause__, ValueError), (
        f"the ragged result was not refused by zip(strict=True); the reading was "
        f"cut short instead. Cause: {raised.value.__cause__!r}"
    )
    assert not isinstance(raised.value, reader.UnreadableDocumentError), (
        "a recogniser handing back mismatched lists is OUR tool failing, never a "
        "verdict on the document"
    )


def test_the_recognition_failure_message_names_every_reason_completely(
    install_paddleocr: InstallFactory,
) -> None:
    """§J.2 - the exact result, not merely that `RecognitionFailedError` fired.

    The same discipline `test_the_vision_fallback_message_names_every_reason_
    completely` already applies to the other named failure, applied here because
    a mutation run showed this message had none of it. Nine separate mutations
    of its literal segments - fragments blanked, fragments upper-cased, a single
    letter's case flipped - every one of them left the suite green, because the
    tests above assert only that the upstream TYPE and the page NUMBER appear
    somewhere in it.

    The message is the entire product of this boundary. `pipeline.BUSINESS_FAILURE`
    decides by type; a human deciding whether their invoice is damaged or our OCR
    is dead has only these words. Pinning them whole is what makes them a
    contract rather than a comment.

    The two interpolated segments are composed from the cause rather than copied,
    so this pins `reader`'s contract - *name the page, name the upstream type,
    keep the upstream text* - without pinning a vendor string.
    """
    original = a_paddle_onednn_failure()
    install_paddleocr(_RecordingFactory(_FailingRecogniser(original)))

    with pytest.raises(reader.RecognitionFailedError) as raised:
        reader.read_by_ocr([an_invoice_png()])

    assert raised.value.__cause__ is original
    assert str(raised.value) == (
        "the OCR recogniser failed on page 0: "
        f"{type(original).__name__}: {original}. This is a failure of OUR "
        "recogniser, not a verdict on the document — the page decoded "
        "cleanly and may be perfectly readable. Raised as a named reader "
        "failure rather than passed on as the backend's own exception, "
        "which downstream code cannot tell apart from a damaged file."
    )


def test_a_missing_paddleocr_is_deliberately_left_as_a_plain_import_error(
    paddleocr_is_absent: list[str],
) -> None:
    """The ONE upstream failure that is deliberately NOT wrapped, pinned so it stays that way.

    `ModuleNotFoundError: No module named 'paddleocr'` is already precise, and
    it says something different from every error above: not "recognition
    failed" but "this deployment has no OCR at all", which is knowable before
    any document arrives. Three test modules outside this one measure it as the
    real, unwrapped error - `test_input_engine_pipeline.py`,
    `test_input_engine_pipeline_redteam.py` and `test_engine1_end_to_end.py` -
    so widening the boundary to swallow it would silently break six assertions
    nobody editing `reader.py` is looking at.

    Without this test that asymmetry is an undocumented accident that the next
    person tidies away. With it, tidying it away turns something red HERE,
    beside the reason.
    """
    with pytest.raises(ModuleNotFoundError, match="paddleocr"):
        reader.read_by_ocr([an_invoice_png()])

    assert "paddleocr" in paddleocr_is_absent
