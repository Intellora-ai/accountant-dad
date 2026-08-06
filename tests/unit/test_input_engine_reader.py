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
from authored_source import authored_path, authored_source
from PIL import Image

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
    """
    filetype_calls: list[str] = []
    dpi_calls: list[int] = []
    format_calls: list[str] = []
    real_open_pdf = reader._open_pdf

    class _RecordedPixmap:
        def __init__(self, real: reader._Pixmap) -> None:
            self._real = real

        def tobytes(self, output: str) -> bytes:
            format_calls.append(output)
            return self._real.tobytes(output)

    class _RecordedPage:
        def __init__(self, real: reader._PdfPage) -> None:
            self._real = real

        def get_pixmap(self, *, dpi: int) -> _RecordedPixmap:
            dpi_calls.append(dpi)
            return _RecordedPixmap(self._real.get_pixmap(dpi=dpi))

    class _RecordedDocument:
        def __init__(self, real: reader._PdfDocument) -> None:
            self._real = real

        @property
        def page_count(self) -> int:
            return self._real.page_count

        def __getitem__(self, index: int) -> _RecordedPage:
            return _RecordedPage(self._real[index])

        def close(self) -> None:
            self._real.close()

    def spy_open_pdf(*, stream: bytes, filetype: str) -> _RecordedDocument:
        filetype_calls.append(filetype)
        return _RecordedDocument(real_open_pdf(stream=stream, filetype=filetype))

    monkeypatch.setattr(reader, "_open_pdf", spy_open_pdf)

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
