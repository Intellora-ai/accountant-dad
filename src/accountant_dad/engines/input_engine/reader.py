"""Engine 1's `reader` — get the characters off the page, and nothing more.

`SUB_ENGINE_RESPONSIBILITIES.md` §1.2: *"Somebody must actually get the
characters off the page."* This module owns that, together with where on the
page each piece of text sits and how confident the extraction was. It owns
nothing else, and several of the decisions below exist only to keep it that way.

TWO PATHS, BECAUSE THE STACK NAMES TWO TOOLS FOR TWO DIFFERENT PROBLEMS.
    `TECHNOLOGY_STACK.md` (LOCKED 2026-08-05) gives Engine 1 PyMuPDF for *"PDF
    text layer - no OCR needed when a PDF carries real text"* and PaddleOCR as
    **the** OCR, *"text extraction with per-region confidence."*

        PDF carrying a real text layer  ->  PyMuPDF        no recognition
        image, or PDF with no text layer ->  PaddleOCR      per-region score

    Tesseract, EasyOCR, Camelot, Tabula and Unstructured are *"explicitly NOT
    approved"* there and appear nowhere in this file or its dependencies.

    PyMuPDF is reached through `accountant_dad.pdf_backend` and never directly.
    The owner's F-001 ruling (2026-08-06) is *"abstract it behind a PDF Engine
    interface so Engine 1 never depends directly on PyMuPDF"*, and this module
    now names no PyMuPDF type, method, keyword or exception. Which library
    sits behind that interface is the stack's decision, not this file's.

THE CONFIDENCE OF A TEXT LAYER IS `None`, AND THAT IS THE WHOLE POINT.
    A PDF text layer is not recognised, it is *read* - the characters are the
    ones the producer embedded. No recogniser ran, so no recogniser scored
    anything, so there is no score to report.

    `1.0` is the tempting answer and it is a fabricated measurement (Law 24).
    It would also be a lie of a specific and dangerous kind: a text layer can be
    wrong (a scanned page with a bad OCR layer baked in by some other tool), and
    a confident 1.0 would tell every downstream engine that the reading was
    perfect when nothing checked it. `None` says the true thing - *no confidence
    signal was produced here* - and leaves `confidence`, the sub-engine that
    actually owns scoring, free to decide what that is worth.

    This is not `reader` being coy. `ENGINE_1_INPUT_ENGINE_RULES.md:109`:
    *"`cleaner`, `reader` and `parser` emit SIGNALS. Only `confidence` turns
    signals into scores."* What this module emits is the signal the backend
    reported, verbatim, or the honest absence of one.

NUMBERS THIS MODULE REFUSES TO CHOOSE.
    `TECHNOLOGY_STACK.md` records the vision-fallback threshold as
    `UNKNOWN - REQUIRES A NUMBER FROM THE OWNER`, and says plainly that until it
    exists *"the fallback path cannot be implemented, only stubbed."* The render
    DPI is in the same position: no document sets one.

    Both are therefore REQUIRED keyword arguments with no default, and no
    module-level constant holds a copy. Omitting one raises `TypeError` from the
    interpreter before any reading happens. A default would be this file
    answering a question the owner was asked and has not answered (Law 52).

A BLANK PAGE AND A BROKEN FILE ARE DIFFERENT ANSWERS.
    A blank page reads as zero regions - honestly, and it is not an error.
    A file that cannot be opened raises `UnreadableDocumentError` - loudly, and
    it is never an empty reading.

    Collapsing the two is the silent failure this engine cannot afford
    (`CLAUDE.md` Law 11). Downstream, an empty reading of a corrupt file is
    indistinguishable from an honest reading of an empty page, and the
    Confidence Report assembled from it would be a confident statement about a
    document nobody managed to open.

WHAT IT DOES NOT DO, AND WHY EACH ABSENCE IS DELIBERATE.
    No field names, no types, no labels. §1.2: it *"may extract
    `27AAECS1234F1Z5`, it may not conclude that this is a GSTIN."* A `TextRegion`
    carries text, position and the backend's confidence signal - naming it
    `gstin` would be the interpretation `parser` and Engine 2 own.

    No reordering. §1.2: *"Cannot reorder or restructure the text."* Regions come
    back in the order the backend reported them, which for both paths is page
    order.

    No guessing. §1.2 again - it cannot *"guess unclear words."* A region the
    recogniser scored badly is emitted with its bad score, not dropped and not
    improved.

    No Document Evidence Object. That artifact is assembled by the PARENT Input
    Engine from all four sub-engines (`ENGINE_1:62`), and only it may create one.
    `Reading` is an internal, sub-engine-level result and deliberately is not one
    of the six named artifacts.

WHERE THE INPUT COMES FROM, STATED RATHER THAN ASSUMED.
    §1.2 says `reader` receives *"the cleaned document representation from
    `cleaner`."* This module takes it as bytes plus a declared `MediaType`, and
    does NOT define a `CleanedDocument` type: that type is `cleaner`'s output
    and belongs to `cleaner` (INV-10, one concept one owner). Defining one here
    would put a second owner on it. When `cleaner` was still unwritten that was
    a statement about the future; it is now a statement about ownership, and it
    is why `CleanedPageGeometry` below is a structural Protocol rather than an
    import.

    The media type is declared by the caller and never sniffed. `CLAUDE.md`
    Law 23 - external input is untrusted - and guessing a document's type from
    its bytes is a guess, which is the one thing this sub-engine may never make.

A COORDINATE MUST SAY WHICH PAGE IT ANSWERS ON (`KNOWN_FAILURES.md` F-030).
    `cleaner` CROPS and DESKEWS a scanned page, so a coordinate on the cleaned
    raster is not a coordinate on the document. This module used to emit one as
    though it were: `SourceLocation` carried five numbers and nothing that named
    the space they lived in, so nothing downstream had a question it could ask.

        no map supplied   ->  `OCR_RASTER_PIXELS`, an honest statement about the
                              raster read, and no claim about the document
        map supplied      ->  `SOURCE_RASTER_PIXELS`, the document as received
        map unusable      ->  `CoordinateContractError`, and NO reading at all

    The third line is the one that matters. Degrading a bad map to the second
    line's answer would reproduce the original defect with a fix's name on it —
    see `CoordinateContractError`. The map itself belongs to `cleaner`; this
    module names the surface it needs and applies it, and owns neither the
    geometry nor the pixels it describes.
"""

from __future__ import annotations

import importlib
import io
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import cache
from typing import Protocol, cast

import numpy
import numpy.typing
from PIL import Image

# THE PDF ENGINE, BY NAME AND NOT BY MODULE, and the reason is a gate rather
# than a preference. `test_package.py::test_engine_1_reaches_for_nothing_
# outside_its_own_boundary` reads the module an import NAMES: this form records
# `accountant_dad.pdf_backend`, while `from accountant_dad import pdf_backend`
# would record a bare `accountant_dad` the guard cannot tell apart from a reach
# into `artifacts.decision`. The dotted `import a.b as b` records the right name
# too and is refused by ruff's PLR0402, so this is the one form both gates
# accept. Function names are unambiguous on their own for the same reason.
from accountant_dad.pdf_backend import (
    close_pdf,
    open_pdf,
    page_count,
    render_page_png,
    require_positive_dpi,
    structured_text,
)

#: An RGB page as PaddleOCR wants it: height x width x 3, one byte per channel.
Page = numpy.typing.NDArray[numpy.uint8]

#: One recognised line's outline: four (x, y) corners, as PaddleOCR returns them.
Quadrilateral = numpy.typing.NDArray[numpy.int16]


# ── a typed facade over one untyped dependency ────────────────────────────
#
# PaddleOCR ships no typing at all. Under `mypy --strict` that is an error, and
# the repository runs a zero-new-suppressions gate, so silencing it per-line is
# unavailable - and would be the wrong tool regardless.
#
# Declaring the exact API surface this module uses is STRICTER than a
# suppression, not looser: mypy then checks every call below against these
# signatures, so a misspelled method or a wrong argument type is caught, where a
# silenced line would have hidden all of it. The declarations were read off the
# installed library (PaddleOCR 3.7.0), not from memory.
#
# THE SECOND FACADE THAT USED TO SIT HERE HAS MOVED, AND THAT IS F-001. This
# module declared `_Span`, `_Line`, `_Block`, `_TextPage`, `_Pixmap`,
# `_PdfPage`, `_PdfDocument` and `_OpenPdf` over PyMuPDF, and `pipeline.py`
# declared a second copy of four of them. `accountant_dad.pdf_backend` now owns
# every one, so replacing the PDF library is a rewrite of that file and of
# nothing in Engine 1 - which is exactly what the owner's F-001 ruling asked
# for. This module names no PyMuPDF type, method, keyword or exception.


class _OcrResult(Protocol):
    def __getitem__(self, key: str) -> object: ...


class _Recogniser(Protocol):
    def predict(self, image: Page) -> list[_OcrResult]: ...


class _RecogniserFactory(Protocol):
    def __call__(
        self,
        *,
        lang: str,
        use_doc_orientation_classify: bool,
        use_doc_unwarping: bool,
        use_textline_orientation: bool,
        enable_mkldnn: bool,
    ) -> _Recogniser: ...


class ReaderError(Exception):
    """Anything `reader` refuses to do quietly. Never raised for a blank page."""


class UnreadableDocumentError(ReaderError):
    """The document could not be opened or decoded at all.

    Deliberately NOT the same outcome as a blank page. A blank page is a
    successful reading of nothing; this is the absence of a reading, and the two
    must stay distinguishable for the whole life of the artifact built from them.
    """


class RecognitionFailedError(ReaderError):
    """The recogniser was reached, was asked to read a page, and could not.

    NOT A STATEMENT ABOUT THE DOCUMENT, AND THE DISTINCTION IS THE WHOLE REASON
    THIS CLASS EXISTS. `UnreadableDocumentError` means *this file is broken*.
    This means *our OCR engine is broken* - the page may be a perfectly good
    invoice. `pipeline.BUSINESS_FAILURE` decides by `isinstance` which failures
    cross the Engine 1 boundary as a verdict about the document, and this type is
    deliberately absent from that list for the same reason
    `VisionFallbackUnavailableError` is: telling a user their document is
    damaged when our tool is the thing that broke asserts something false about
    their document, which `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids outright.

    WHAT FORCED IT, MEASURED RATHER THAN IMAGINED. At commit `c4fbb5f` the
    `ocr tests` job ran Engine 1's OCR path on CI for the first time in the
    project's history, and all twelve tests died with

        NotImplementedError: (Unimplemented) ConvertPirAttribute2Runtime
        Attribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
        (at .../new_executor/instruction/onednn/onednn_instruction.cc:116)

    raised inside PaddlePaddle's C++ executor. `read_by_ocr` had no failure
    boundary at all, so that left this module wearing PaddlePaddle's name and a
    C++ file path. Two things are wrong with that and neither is cosmetic:

      * `NotImplementedError` is a Python builtin that already means *this
        abstract method is unimplemented*. Any caller anywhere up the stack that
        catches it for its OWN purposes silently swallows a dead OCR engine -
        the exact silent failure Law 11 forbids.
      * `COMMUNICATION_RULES_INPUT_ENGINE.md` §4 item 9 requires failed
        extractions to cross the boundary as NAMED uncertainty. A C++ message is
        not a name, and nothing downstream can branch on one without matching a
        string that upstream is free to reword.

    The upstream exception is preserved entire - its type and text in the
    message, the object itself as `__cause__`. Naming a failure must not cost
    the diagnosis.
    """


class CoordinateContractError(ReaderError):
    """A source map was supplied and cannot be honoured, so NOTHING is claimed.

    THE FAILURE THIS TYPE EXISTS TO MAKE IMPOSSIBLE IS THE QUIET ONE.
    `KNOWN_FAILURES.md` F-030: `cleaner` crops and turns a scanned page, and this
    module emitted `SourceLocation` in the CLEANED image's pixel space as though
    that were the document. The numbers were plausible, the artifact was
    well-formed, and every coordinate on it was somewhere the document does not
    have. Nothing raised, because nothing was asked.

    So when a caller hands over a map and any part of it cannot be trusted —
    the page count, the page number, the raster's size, the resolution, the
    contract version — the reading is REFUSED rather than returned in the space
    the caller did not ask for. Degrading to the unmapped answer would reproduce
    the original defect exactly, wearing a fix's name: the caller asked where
    the text is ON THE DOCUMENT and would receive, silently, where it is on a
    crop of a rotation of it.

    A VERDICT ON OUR WIRING, NEVER ON THE DOCUMENT, and that is why it is not
    an `UnreadableDocumentError`. The user's file may be perfect; what is
    inconsistent is the contract between two of our own components.
    `pipeline.BUSINESS_FAILURE` decides by `isinstance` which reader failures
    cross the Engine 1 boundary as a statement about the document, and this type
    is deliberately absent from it for the same reason `RecognitionFailedError`
    is — `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids asserting something false
    about a document outright.
    """


class VisionFallbackUnavailableError(ReaderError):
    """The vision fallback was reached and cannot run.

    `TECHNOLOGY_STACK.md` lists Gemini 2.5 Flash Vision as **fallback only** and
    then records two blockers against it: the API key (*"credential"*) and the
    trigger threshold (*"a number nobody has set"*). Raising is the only correct
    behaviour - see `_vision_fallback` for why silently returning the OCR result
    would be worse than failing.
    """


class MediaType(StrEnum):
    """What the caller declares the document to be. Never inferred from bytes."""

    PDF = "PDF"
    IMAGE = "image"


class Backend(StrEnum):
    """Which tool produced a reading. Recorded so a reading can be traced to it."""

    PDF_TEXT_LAYER = "PDF text layer"
    OCR = "OCR"


#: The one coordinate contract this module can honour, as a whole number that a
#: producer states explicitly. There is no default anywhere for it: a default
#: would let a map built against a DIFFERENT contract be read as this one, which
#: is precisely the case a version exists to catch.
COORDINATE_CONTRACT_VERSION = 1


class CoordinateSpace(StrEnum):
    """WHICH page a `SourceLocation`'s four numbers answer on, and in what unit.

    `KNOWN_FAILURES.md` F-030's consumer half, in one field. The producer defect
    was that `cleaner` discarded its geometry; the CONSUMER defect is that a
    `SourceLocation` in cleaned-image pixels and one on the document as received
    were the same five numbers with nothing to tell them apart. A downstream
    reader had no question it could ask, so it assumed — and the assumption was
    wrong on every cropped or deskewed scan.

    ORIGIN AND AXIS DIRECTION ARE THE SAME IN ALL OF THEM, AND ARE MEASURED
    RATHER THAN ASSUMED. The origin is the TOP-LEFT corner of the page, `x`
    increases to the RIGHT and `y` increases DOWNWARD. Measured at `00c6b8d` on
    a page carrying text drawn with its baseline at y = 30 pt on a 400x200 pt
    page: the backend reported the span's box as 21.400..32.392 pt and the same
    page rasterised at 150 dpi put that ink at 24.480..29.760 pt — inside the
    box, and 140 pt away from where the PDF specification's own BOTTOM-left user
    space would have put it. A module that took the specification's word for it
    would be upside down on every page and would still produce plausible
    numbers. `test_source_location_maps_to_source.py` makes that measurement.

    THE TRANSFORM RUNS ONE WAY ONLY: a CLEANED pixel to a SOURCE pixel. There is
    no inverse here and none is offered, because a consumer that could ask for
    either direction is a consumer that can pick the wrong one.
    """

    #: Nobody said. The default on a `SourceLocation` built by hand, and never
    #: a value this module emits — inventing a space for somebody else's
    #: coordinates would be exactly the fabricated measurement Law 24 forbids.
    UNSTATED = "unstated"
    #: POINTS on the PDF page THIS MODULE WAS HANDED. Not knowably the document
    #: as received: this module is handed bytes and cannot tell an original from
    #: a rebuild, so it names what it can prove.
    PDF_PAGE_POINTS = "points on the PDF page this module was handed"
    #: PIXELS of the raster the recogniser was shown. On a cleaned scan that is
    #: a crop of a rotation of the page, so it is NOT the document.
    OCR_RASTER_PIXELS = "pixels of the raster the recogniser was shown"
    #: PIXELS of the raster rendered from the document AS RECEIVED. The only
    #: member that is a claim about the user's own page, and the only one
    #: reachable by supplying a map that survives every check in `_placements`.
    SOURCE_RASTER_PIXELS = "pixels of the raster rendered from the document as received"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Where on the page a piece of text sits.

    `ENGINE_1:511` - *"Source locations are emitted even for low-confidence
    extractions - that is what makes a later human check possible."* So this is
    never optional and never omitted, whatever the confidence attached to it.

    Coordinates are in the space `space` NAMES, for the page named by
    `page_index`; they are not normalised, because normalising would discard the
    scale a human needs to find the region again. `space` used to be absent and
    the docstring said *"the backend's own pixel or point space"* — true, and
    unusable: a consumer could not tell which of the two it held, nor whether
    the page in question was the user's document or a crop of a rotation of it.
    """

    page_index: int
    left: float
    top: float
    right: float
    bottom: float
    #: WHICH page these numbers answer on. Defaults to `UNSTATED` because a
    #: location constructed anywhere else genuinely has not stated one; every
    #: location THIS module produces sets it, and a test proves it.
    space: CoordinateSpace = CoordinateSpace.UNSTATED
    #: The four corners the backend reported, IN `space`, in the backend's own
    #: order. Empty when the backend reported a rectangle rather than an outline.
    #:
    #: KEPT RATHER THAN DISCARDED, and that is not redundancy with the four
    #: edges above. A rotation carries a rectangle to a QUADRILATERAL, so the
    #: four edges are its axis-aligned ENCLOSURE and are strictly larger than
    #: the region itself. The enclosure is derived here, at the one boundary
    #: whose shape demands it; throwing the quad away would make the loss
    #: permanent and unrecoverable one line after it happened.
    corners: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True, slots=True)
class TextRegion:
    """One piece of text, where it was, and how confident the backend was.

    Three attributes exactly. Anything that named or typed the value would be
    interpretation, which §1.2 forbids this sub-engine outright.
    """

    text: str
    location: SourceLocation
    #: The backend's own score, verbatim, or `None` when the backend performed no
    #: recognition and therefore reported no score. `None` is NOT zero confidence
    #: and NOT full confidence - it is the absence of a measurement, and only
    #: `confidence` may decide what that is worth. See the module docstring.
    extraction_confidence: Decimal | None


@dataclass(frozen=True, slots=True)
class Reading:
    """What `reader` hands to `parser` and `confidence`. Not a system artifact."""

    regions: tuple[TextRegion, ...]
    backend: Backend
    pages_read: int


class CleanedPageGeometry(Protocol):
    """The map from ONE cleaned page's pixels back to the page as received.

    STRUCTURAL, AND THAT IS A DELIBERATE CHOICE ABOUT OWNERSHIP. The affine is
    `cleaner`'s — it computed it, it owns it, and `cleaner.SourceGeometry`
    satisfies this Protocol without either module knowing about the other. So
    the arithmetic that inverts a crop and a turn lives in exactly one place
    (Law 14, Law 19), this module keeps the property its docstring already
    claims — *"does NOT define a `CleanedDocument` type: that type is
    `cleaner`'s"* — and neither is `import cleaner` needed here, which would put
    OpenCV behind `import reader` for a module that never touches a pixel array
    except through Pillow (Law 21).

    The same facade pattern `_Recogniser` uses for PaddleOCR and `PdfDocument`
    for the PDF engine, for the same reason: declare the surface actually used,
    and let `mypy --strict` check every call against it.
    """

    @property
    def source_height(self) -> int: ...

    @property
    def source_width(self) -> int: ...

    @property
    def render_dpi(self) -> int | None: ...

    @property
    def page(self) -> int: ...

    def source_pixel(self, x: float, y: float) -> tuple[float, float]: ...


@dataclass(frozen=True, slots=True)
class CleanedPage:
    """One cleaned page as this module must be told about it, to map off it.

    `height` and `width` are the CLEANED raster's extent in pixels, and they are
    here because the geometry alone cannot supply them: without the extent this
    module has nothing to compare the raster it actually rasterised against, and
    a map for a different page would be applied in silence.
    """

    #: 0-BASED, this module's own convention, and checked against the geometry's
    #: 1-based `page`. The two conventions meeting is exactly where an off-by-one
    #: puts page one's map on page two's coordinates.
    page_index: int
    height: int
    width: int
    geometry: CleanedPageGeometry


@dataclass(frozen=True, slots=True)
class SourceMapping:
    """Everything this module must be told before it may name a coordinate on
    the document AS RECEIVED instead of on the raster it was handed.

    Supplying one is the caller saying *"I know where these cleaned pixels came
    from."* It is optional because a caller may honestly not know — a text-layer
    PDF passes through `cleaner` untouched and has no map at all — and because
    the answer to not knowing is to say so, never to guess.
    """

    #: One per page read, in page order. A page without one is refused, not
    #: answered in another space.
    pages: tuple[CleanedPage, ...]
    #: The resolution at which THIS module rasterised those pages, or `None`
    #: when it rasterised nothing and read the artifact's own pixels. It is
    #: stated by the caller and CHECKED against what actually happened, rather
    #: than taken from `render_dpi`: on the image path `render_dpi` is supplied
    #: and ignored, so reading it would silently invent a resolution for pixels
    #: nothing rendered.
    raster_dpi: int | None
    #: `COORDINATE_CONTRACT_VERSION`, stated. No default — see that constant.
    contract_version: int


def read_pdf_text_layer(document: bytes) -> Reading:
    """Read a PDF's embedded text layer with PyMuPDF. No OCR, and no recognition.

    Returns zero regions when the PDF carries no text layer - a scan, a
    photograph wrapped in a PDF, a blank page. That is a real answer and the
    caller decides what to do with it; this function never rasterises and never
    escalates on its own.

    Every region's `extraction_confidence` is `None`. Nothing was recognised, so
    nothing was scored.

    Raises `UnreadableDocumentError` if the bytes are not an openable PDF.
    """
    try:
        opened = open_pdf(document)
    except Exception as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be opened as a PDF: {failure}. "
            "Raised rather than returned as an empty reading, which would be "
            "indistinguishable downstream from an honest reading of a blank page."
        ) from failure

    regions: list[TextRegion] = []
    # THE CLEANUP IS INSIDE THE BOUNDARY, NOT BESIDE IT. `close()` is a PyMuPDF
    # call like any other and can raise like any other; with `finally` as a
    # sibling of `except` it would escape unconverted. Nesting the `try/finally`
    # INSIDE the converting `try` keeps the guarantee that the document is always
    # closed while putting the close itself under the same boundary as the read.
    try:
        try:
            pages_read = page_count(opened)
            for page_index in range(pages_read):
                # `structured_text` gives spans with their bounding boxes, in
                # the backend's OWN order: §1.2 forbids reordering, so nothing
                # here re-sorts and the backend is asked not to either.
                for block in structured_text(opened, page_index)["blocks"]:
                    for line in block.get("lines", ()):
                        for span in line["spans"]:
                            text = span["text"]
                            if not text.strip():
                                # A whitespace-only span is not a reading.
                                # Skipping it drops nothing a human could check,
                                # and keeping it would pad the region count with
                                # non-evidence.
                                continue
                            left, top, right, bottom = span["bbox"]
                            regions.append(
                                TextRegion(
                                    text=text,
                                    location=SourceLocation(
                                        page_index=page_index,
                                        left=float(left),
                                        top=float(top),
                                        right=float(right),
                                        bottom=float(bottom),
                                        # POINTS on the page handed to this
                                        # module. Not `SOURCE_RASTER_PIXELS`:
                                        # `cleaner` does pass a text-layer PDF
                                        # through untouched, so these usually
                                        # ARE the document's own coordinates —
                                        # but this module is handed bytes and
                                        # cannot prove which, and a claim it
                                        # cannot check is the whole defect.
                                        space=CoordinateSpace.PDF_PAGE_POINTS,
                                    ),
                                    extraction_confidence=None,
                                )
                            )
        finally:
            close_pdf(opened)
    except Exception as failure:
        # A PDF THAT OPENS CAN STILL BREAK ON PAGE 3, AND THIS USED TO LEAK.
        # Only the `_open_pdf` call above had a boundary; everything after it
        # ran under `try/finally` with no `except`, so a malformed page, a
        # damaged content stream or a span PyMuPDF could not lay out escaped
        # wearing PyMuPDF's name. Found by the structural validator in
        # `test_input_engine_reader.py`, not by reading — which is the whole
        # argument for having it.
        #
        # `UnreadableDocumentError` and not `RecognitionFailedError`: PyMuPDF
        # failing on a page's own content is a statement about the DOCUMENT,
        # the same verdict the open failure above produces, and no recogniser
        # is involved in this path at all.
        raise UnreadableDocumentError(
            f"the PDF opened but its text layer could not be read: "
            f"{type(failure).__name__}: {failure}. Raised rather than returned "
            "as a partial reading — a document read up to the point it broke is "
            "indistinguishable downstream from a document that ended there."
        ) from failure

    return Reading(regions=tuple(regions), backend=Backend.PDF_TEXT_LAYER, pages_read=pages_read)


def _render_pdf_pages(document: bytes, *, render_dpi: int) -> list[bytes]:
    """Rasterise every page to PNG at the CALLER's DPI. Raises on an unopenable PDF."""
    try:
        opened = open_pdf(document)
    except Exception as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be opened as a PDF: {failure}"
        ) from failure

    try:
        try:
            return [
                render_page_png(opened, index, dpi=render_dpi)
                for index in range(page_count(opened))
            ]
        finally:
            close_pdf(opened)
    except Exception as failure:
        # Same gap as `read_pdf_text_layer`: the open had a boundary, the
        # rasterisation did not. A page whose content stream is damaged, or one
        # whose dimensions overflow at this DPI, failed here with PyMuPDF's own
        # exception. It is a verdict on the DOCUMENT, so it converts the same
        # way the open failure above does. The close is nested inside for the
        # same reason it is in `read_pdf_text_layer`.
        raise UnreadableDocumentError(
            f"the PDF opened but a page could not be rasterised at {render_dpi} "
            f"dpi: {type(failure).__name__}: {failure}"
        ) from failure


def _decode_image(image: bytes) -> Page:
    """Bytes to an RGB array PaddleOCR can read. Raises on anything undecodable.

    CATCHES `Exception`, NOT A LIST OF PILLOW'S EXCEPTION TYPES. This used to
    enumerate `UnidentifiedImageError`, `OSError` and `ValueError`, which is an
    allowlist over a set this module does not own: Pillow and numpy are free to
    raise anything, at any version, on any input, and the three names here were
    chosen from the failures somebody imagined rather than measured. Pillow's
    own `DecompressionBombError`, a `struct.error` from a truncated header, an
    `EOFError`, a `MemoryError` on a hostile size field — every one of those is
    the same event, *these bytes are not a usable image*, and every one of them
    used to escape this module wearing Pillow's name instead of Engine 1's.

    That is the general defect, and it is the same one that let PaddlePaddle's
    C++ `NotImplementedError` out of `read_by_ocr`: A BOUNDARY THAT NAMES
    EXCEPTION TYPES IS AN ALLOWLIST OVER A SET THE VENDOR CONTROLS. The boundary
    is named by WHERE IT IS, never by what happens to cross it. `Exception` and
    not `BaseException` is the one deliberate limit: `KeyboardInterrupt` and
    `SystemExit` are the operator stopping the process, not a verdict on a page.
    """
    try:
        with Image.open(io.BytesIO(image)) as opened:
            decoded: Page = numpy.asarray(opened.convert("RGB"), dtype=numpy.uint8)
            return decoded
    except Exception as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be decoded as an image: "
            f"{type(failure).__name__}: {failure}. "
            "Raised rather than returned as an empty reading - a file that could "
            "not be opened and a page with nothing on it are different answers."
        ) from failure


@cache
def _recogniser() -> _Recogniser:
    """The one PaddleOCR instance, built on first use and reused after.

    Constructing it loads model weights, so a fresh instance per call would make
    every read pay for it. `@cache` rather than a module-level global: the
    caching is then a property of the function instead of a mutable name any
    other code could rebind.

    The three preprocessing stages are off: `cleaner` owns document preprocessing
    (`ENGINE_1` §8.1), and running a second, invisible cleanup inside `reader`
    would put one responsibility in two places.

    PADDLEOCR IS RESOLVED HERE, NOT AT MODULE SCOPE. It is reached through
    `importlib` because PaddleOCR carries no `py.typed`, so a plain
    `import paddleocr` is itself a `mypy --strict` error — but doing that
    lookup at import time made the whole Input Engine unimportable without a
    ~500 MB ML package present. Every gate that merely imports the package
    then fails at collection, which is what CI caught. Resolving it inside the
    `@cache`d builder costs nothing (it already runs once) and restores the
    property the `importlib` route was chosen for: the dependency is needed to
    RUN OCR, never to import the module that offers it.

    The literal string stays in the file, so the AST test that pins this
    module's dynamic imports still sees it — moving the call does not hide a
    technology swap from the stack check.

    ONEDNN IS SWITCHED OFF, AND THE DEFAULT IS WHY. PaddleOCR 3.7.0 ships
    `DEFAULT_ENABLE_MKLDNN = True` (`paddleocr/_constants.py:18`), which on a CPU
    device routes inference through PaddlePaddle's oneDNN instruction path. At
    commit `c4fbb5f` that path raised `NotImplementedError` out of
    `onednn_instruction.cc:116` for EVERY page, on every one of the twelve OCR
    tests, on CI's x86-64 runner — the first time this code had ever executed
    where proof lives. `paddleocr/_common_args.py:90-94` is the entire
    mechanism: on a CPU device, `enable_mkldnn=False` sets `run_mode="paddle"`
    and the oneDNN instruction path is never constructed. Both lines were read
    out of the pinned 3.7.0 wheel, not recalled.

    This is a KERNEL selection, not a tool swap: same PaddleOCR, same pinned
    version, same models, same arithmetic — a different implementation of it.
    `TECHNOLOGY_STACK.md`'s lock is untouched. Two consequences are stated
    rather than left to be discovered:

      * Kernel implementations differ in accumulation order, so a per-region
        confidence MAY differ in its low-order digits from what oneDNN would
        have reported. There is no "before" to compare against — oneDNN reports
        nothing on this runner, it raises — so this replaces no measurement.
      * oneDNN exists to be faster. Switching it off costs latency, by an amount
        NOBODY HAS MEASURED. It is accepted here because an unmeasured slowdown
        beats an engine that does not run, and it is flagged rather than
        quietly absorbed.
    """
    try:
        build_recogniser = cast(_RecogniserFactory, importlib.import_module("paddleocr").PaddleOCR)
    except ModuleNotFoundError:
        # THE ONE FAILURE THAT CROSSES UNCONVERTED, AND IT IS NOT A VENDOR
        # ERROR. Everything else this boundary catches is PaddleOCR failing;
        # this is the INTERPRETER stating there is no PaddleOCR to fail — a
        # deployment fact, knowable before any document arrives, raised by
        # CPython with a stable type and an exact message. Converting it would
        # replace a precise statement with a vaguer one, and three other test
        # modules measure it as the real error.
        #
        # This is a single closed case, not the beginning of a list. Anything
        # else — a vendor `__init__` raising on import, a broken C extension, a
        # missing shared library — is PaddleOCR failing and is converted below.
        raise
    except Exception as failure:
        raise RecognitionFailedError(
            f"the OCR recogniser could not be imported: "
            f"{type(failure).__name__}: {failure}. PaddleOCR is installed but "
            "importing it failed, which is a failure of OUR tool and not a "
            "verdict on any document."
        ) from failure

    # Constructing the recogniser downloads model weights over the network, so
    # it fails for real reasons and gets its own boundary.
    try:
        return build_recogniser(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    except Exception as failure:
        raise RecognitionFailedError(
            f"the OCR recogniser could not be constructed: "
            f"{type(failure).__name__}: {failure}. This is a failure of OUR tool, "
            "not a verdict on any document — no document had been read when it "
            "happened. Raised as a named reader failure rather than passed on as "
            "the backend's own exception, which downstream code cannot tell apart "
            "from a damaged file."
        ) from failure


#: How much larger, in pixels, the raster this module rasterised may be than the
#: cleaned page it represents, before the two are declared to be different
#: pages. DERIVED, NEVER CHOSEN: a rasteriser scales the page and then encloses
#: the result in WHOLE pixels, so the enclosure can add strictly less than one
#: pixel per axis and nothing else may. `KNOWN_FAILURES.md` F-031 records the
#: same one-pixel bound from the other direction. Measured at `00c6b8d` over
#: 150/300/600 dpi against reader resolutions of 0.5x, 1x and 2x: every
#: disagreement was exactly 0.0 or 0.5 px, and never 1.
_ENCLOSURE_SLACK_PIXELS = 1.0


def _placements(
    pages: list[bytes], mapping: SourceMapping | None
) -> tuple[tuple[CleanedPage, float], ...] | None:
    """One `(page, scale)` per page read, or `None` when no map was supplied.

    RUN BEFORE THE RECOGNISER IS EVEN BUILT. An inconsistent contract is
    knowable from the contract alone, so it is refused before model weights are
    loaded and before a single page is decoded — and, usefully, it is then
    refusable on a machine with no OCR installed at all, which is where this
    path has always been (`KNOWN_FAILURES.md` F-002, F-009).

    `scale` is CLEANED pixels per raster pixel, and it is the resolution ratio
    rather than the extent ratio. Both are measured at `00c6b8d`: rasterising a
    1511 px cleaned page at half its resolution gives 756 px, not 755.5, so the
    extent ratio carries the enclosure's rounding into every coordinate on the
    page while `cleaned_dpi / raster_dpi` does not. Where the two disagreed the
    ratio form was wrong by 0.708 px and the resolution form by 0.501 px, and
    `cleaner.SourceGeometry.source_point` rejects the extent ratio for the same
    arithmetic one step earlier.
    """
    if mapping is None:
        return None
    if mapping.contract_version != COORDINATE_CONTRACT_VERSION:
        raise CoordinateContractError(
            f"the source map states coordinate contract version "
            f"{mapping.contract_version}; this module can honour only "
            f"{COORDINATE_CONTRACT_VERSION}. Refused rather than applied on the "
            "assumption that the fields still mean what they used to."
        )
    if len(mapping.pages) != len(pages):
        raise CoordinateContractError(
            f"the source map covers {len(mapping.pages)} page(s) and "
            f"{len(pages)} page(s) were read. Refused rather than mapping the "
            "pages it does cover and answering for the rest in the cleaned "
            "raster's own space, which no consumer could tell apart."
        )

    placed: list[tuple[CleanedPage, float]] = []
    for index, page in enumerate(mapping.pages):
        if page.page_index != index:
            raise CoordinateContractError(
                f"the source map's entry {index} names page_index "
                f"{page.page_index}. Pages are mapped in the order they were "
                "read, and another page's map is not an approximation of this "
                "one — every page of a scan is cropped and turned differently."
            )
        if page.geometry.page != index + 1:
            raise CoordinateContractError(
                f"the source map's entry for page_index {index} carries a "
                f"geometry for page {page.geometry.page}. This module counts "
                "pages from 0 and the geometry counts from 1, so these two "
                "disagree about which page they describe."
            )
        placed.append((page, _scale_of(page, mapping.raster_dpi)))
    return tuple(placed)


def _scale_of(page: CleanedPage, raster_dpi: int | None) -> float:
    """Cleaned pixels per raster pixel, or a refusal."""
    cleaned_dpi = page.geometry.render_dpi
    if cleaned_dpi is None and raster_dpi is None:
        # Nothing was rendered at either end: an image arrives already
        # rasterised and leaves as the same pixels, so the two spaces are one.
        return 1.0
    if cleaned_dpi is None or raster_dpi is None:
        raise CoordinateContractError(
            f"the cleaned page for page_index {page.page_index} reports render "
            f"resolution {cleaned_dpi} and the raster this module read reports "
            f"{raster_dpi}. One of the two says its pixels were never rendered "
            "from a page and are already the document's own space, and the "
            "other says the opposite; there is no scale between them that is "
            "not invented."
        )
    require_positive_dpi(cleaned_dpi)
    require_positive_dpi(raster_dpi)
    return cleaned_dpi / raster_dpi


def _agrees_with_the_raster(page: CleanedPage, scale: float, height: int, width: int) -> None:
    """Refuse a map whose cleaned page is not the raster that was just read."""
    expected_width = page.width / scale
    expected_height = page.height / scale
    if (
        abs(width - expected_width) >= _ENCLOSURE_SLACK_PIXELS
        or abs(height - expected_height) >= _ENCLOSURE_SLACK_PIXELS
    ):
        raise CoordinateContractError(
            f"the source map describes a {page.width}x{page.height} px cleaned "
            f"page, which at this resolution is {expected_width:.4f}x"
            f"{expected_height:.4f} px, and the raster read for page_index "
            f"{page.page_index} is {width}x{height} px. A rasteriser encloses a "
            f"scaled page in whole pixels, so at most {_ENCLOSURE_SLACK_PIXELS} "
            "pixel of that may be rounding; more than that is a map for a "
            "different page."
        )


def _placed(
    corners: tuple[tuple[float, float], ...],
    page_index: int,
    placement: tuple[CleanedPage, float] | None,
) -> SourceLocation:
    """One recognised outline, on the page it truly sits on, and named as such.

    ALL FOUR CORNERS MOVE. A rotation carries a rectangle to a quadrilateral, so
    transforming the top-left and bottom-right alone would produce a rectangle
    that is neither the region nor its enclosure. The enclosure is taken here
    and ONLY here, because `SourceLocation`'s four edges are axis-aligned and
    something has to give up the quad's shape at that boundary — which is why
    the quad itself is carried on `corners` rather than dropped.

    THE HALF-PIXEL IS NOT DECORATION, and it is measured rather than reasoned
    into place. A pixel INDEX names a cell, and a cell's centre sits half a
    pixel inside it, so resampling to another resolution maps centre to centre
    and not index to index. Measured at `00c6b8d` on a planted mark, reading a
    150 dpi cleaned page at 300: index-to-index put it 0.353553 px out at every
    skew, and centre-to-centre 0.000409 px.

    AT `scale == 1.0` — which is the pipeline's own configuration, since it
    hands the same DPI to `cleaner` and to `read` — the algebra cancels to
    `x`, subject to one rounding of `x + 0.5` in IEEE754. That residual is
    bounded by an ulp of a pixel coordinate, about 1e-13 px at page scale, and
    is 13 orders of magnitude under the 0.30 px this change is held to. Stated
    rather than called exact, because it is not exact.
    """
    if placement is None:
        return _enclosing(corners, page_index, CoordinateSpace.OCR_RASTER_PIXELS)
    page, scale = placement
    on_the_source = tuple(
        page.geometry.source_pixel((across + 0.5) * scale - 0.5, (down + 0.5) * scale - 0.5)
        for across, down in corners
    )
    return _enclosing(on_the_source, page_index, CoordinateSpace.SOURCE_RASTER_PIXELS)


def _enclosing(
    corners: tuple[tuple[float, float], ...], page_index: int, space: CoordinateSpace
) -> SourceLocation:
    """The axis-aligned box around an outline, keeping the outline."""
    acrosses = [across for across, _ in corners]
    downs = [down for _, down in corners]
    return SourceLocation(
        page_index=page_index,
        left=min(acrosses),
        top=min(downs),
        right=max(acrosses),
        bottom=max(downs),
        space=space,
        corners=corners,
    )


def read_by_ocr(pages: list[bytes], *, mapping: SourceMapping | None = None) -> Reading:
    """Recognise text on already-rasterised pages with PaddleOCR.

    Every region carries the score PaddleOCR reported for it, converted to
    `Decimal` through the number's own string form so the reported value is
    preserved exactly rather than re-rounded.

    A page with nothing recognisable on it contributes zero regions. It does not
    contribute an empty-string region, and it is not an error.

    `mapping`, when given, is where these rasters came from, and every region is
    then located on the document AS RECEIVED rather than on the raster. Omitting
    it is honest and produces `OCR_RASTER_PIXELS`; supplying one that cannot be
    honoured raises `CoordinateContractError` and produces NOTHING — see that
    class for why a degraded answer is worse than no answer here.

    Raises `UnreadableDocumentError` if a page's bytes cannot be decoded — a
    verdict on the PAGE. Raises `RecognitionFailedError` if the recogniser
    itself fails — a verdict on OUR TOOL. Those are different answers and this
    function never conflates them; see `RecognitionFailedError` for what forced
    the distinction.
    """
    placements = _placements(pages, mapping)
    engine = _recogniser()

    regions: list[TextRegion] = []
    for page_index, page in enumerate(pages):
        # DECODED OUTSIDE THE BOUNDARY BELOW, DELIBERATELY. `_decode_image`
        # raises `UnreadableDocumentError`, which is a statement about this
        # page's bytes and is one of the few failures the pipeline is allowed to
        # carry across the Engine 1 boundary as a document verdict. Drawing the
        # boundary one line wider would relabel a genuinely broken page as a
        # broken engine and lose exactly the distinction this module exists to
        # keep.
        decoded = _decode_image(page)
        # ALSO OUTSIDE THE BOUNDARY, AND FOR THE MIRROR-IMAGE REASON.
        # `_agrees_with_the_raster` raises `CoordinateContractError`, a verdict
        # on OUR CONTRACT. Inside the handler below it would be relabelled
        # `RecognitionFailedError` — the recogniser blamed for a map the caller
        # got wrong, and a third meaning loaded onto one exception type.
        placement = None if placements is None else placements[page_index]
        if placement is not None:
            _agrees_with_the_raster(placement[0], placement[1], *decoded.shape[:2])
        try:
            for result in engine.predict(decoded):
                # The three keys PaddleOCR 3.7.0 populates for a text-only
                # pipeline, read off a real result rather than assumed.
                # `rec_polys` holds one four-point quadrilateral per recognised
                # line. A later PaddleOCR renaming one of them is recognition
                # failing, so the lookups sit inside the boundary too: a bare
                # `KeyError('rec_scores')` says nothing about what went wrong.
                texts = cast(list[str], result["rec_texts"])
                scores = cast(list[float], result["rec_scores"])
                polygons = cast(list[Quadrilateral], result["rec_polys"])
                for text, score, polygon in zip(texts, scores, polygons, strict=True):
                    if not text.strip():
                        continue
                    outline = tuple((float(point[0]), float(point[1])) for point in polygon)
                    regions.append(
                        TextRegion(
                            text=text,
                            location=_placed(outline, page_index, placement),
                            # `str(score)` then Decimal: `Decimal(float)` would
                            # expand the binary value into its full expansion,
                            # which is not the number PaddleOCR reported.
                            extraction_confidence=Decimal(str(score)),
                        )
                    )
        except Exception as failure:
            raise RecognitionFailedError(
                f"the OCR recogniser failed on page {page_index}: "
                f"{type(failure).__name__}: {failure}. This is a failure of OUR "
                "recogniser, not a verdict on the document — the page decoded "
                "cleanly and may be perfectly readable. Raised as a named reader "
                "failure rather than passed on as the backend's own exception, "
                "which downstream code cannot tell apart from a damaged file."
            ) from failure

    return Reading(regions=tuple(regions), backend=Backend.OCR, pages_read=len(pages))


def _vision_fallback(reading: Reading, threshold: Decimal) -> Reading:
    """The Gemini Vision fallback. Stubbed, and it refuses rather than pretends.

    `TECHNOLOGY_STACK.md` names Gemini 2.5 Flash Vision *"fallback only, when OCR
    confidence is below threshold"*, then records both of its blockers: there is
    no API key, and the threshold is *"a number nobody has set."*

    Returning the OCR reading unchanged would be the quiet, convenient failure -
    the caller asked for a better reading, got a worse one, and nothing said so.
    Every number measured downstream would then be measuring the wrong backend.
    Raising is the only behaviour that keeps the caller's request and the
    system's capability honest with each other (Law 11).
    """
    lowest = min(
        (
            region.extraction_confidence
            for region in reading.regions
            if region.extraction_confidence is not None
        ),
        default=None,
    )
    raise VisionFallbackUnavailableError(
        f"OCR returned a region scored {lowest}, below the supplied vision-fallback "
        f"threshold {threshold}, so the Gemini Vision fallback was reached. It cannot "
        "run: TECHNOLOGY_STACK.md records no API key for it, and records the trigger "
        "threshold as 'UNKNOWN - REQUIRES A NUMBER FROM THE OWNER'. The OCR reading is "
        "deliberately NOT returned in its place - a caller who asked for the fallback "
        "and silently received the reading it was meant to replace would have no way "
        "to know which backend produced the evidence."
    )


def read(
    document: bytes,
    *,
    media_type: MediaType,
    render_dpi: int,
    vision_fallback_threshold: Decimal,
    mapping: SourceMapping | None = None,
) -> Reading:
    """Route a document to a backend and return what that backend read.

        PDF with a text layer   ->  PyMuPDF, returned as-is
        PDF with none           ->  rasterise at `render_dpi`, then PaddleOCR
        image                   ->  PaddleOCR

    `render_dpi` and `vision_fallback_threshold` are REQUIRED and have no
    defaults. Neither number exists in any specification, and choosing one here
    would be this module answering a question put to the owner (Law 52,
    `TECHNOLOGY_STACK.md`). Omitting either raises `TypeError`.

    The fallback triggers when ANY recognised region scores below
    `vision_fallback_threshold` - the strictest reading of *"when OCR confidence
    is below threshold"*, chosen because it escalates more often rather than
    less. **The aggregation rule is not written down in any specification and is
    flagged for the owner alongside the threshold itself.** It then raises
    `VisionFallbackUnavailableError`; the fallback is a stub with no API key.

    `mapping` is where the CLEANED pixels in `document` came from, and it is
    optional because a caller may honestly not know. With it, every region is
    located on the document as received; without it, on the raster that was
    read, and the region says which. It is never guessed — see
    `CoordinateContractError`.

    A page with nothing on it returns zero regions. A file that cannot be opened
    raises `UnreadableDocumentError`. Those are different answers to different
    questions and this function never conflates them.
    """
    require_positive_dpi(render_dpi)

    if media_type is MediaType.PDF:
        from_text_layer = read_pdf_text_layer(document)
        if from_text_layer.regions:
            # A real text layer needs no OCR, so no OCR confidence exists, so
            # there is nothing the fallback threshold could be below.
            if mapping is not None:
                raise CoordinateContractError(
                    "a source map was supplied and this document was read from "
                    "its PDF text layer, whose coordinates are points on that "
                    "page and not pixels of any cleaned raster. `cleaner` passes "
                    "a text-layer PDF through untouched and records NO geometry "
                    "for it, so a map here describes something that did not "
                    "happen. Refused rather than returning the text-layer "
                    "reading, which a caller expecting source-raster pixels "
                    "cannot tell apart from one."
                )
            return from_text_layer
        pages = _render_pdf_pages(document, render_dpi=render_dpi)
        rasterised_at: int | None = render_dpi
    else:
        # One image is one page. It is decoded here rather than inside the OCR
        # loop so that undecodable bytes fail before any model is loaded.
        _decode_image(document)
        pages = [document]
        # NOT `render_dpi`, WHICH THIS BRANCH NEVER USED. An image arrives
        # already rasterised, so nothing here rendered it and it has no
        # resolution this module knows. Passing `render_dpi` on would attach a
        # number nothing measured to pixels nothing rendered — the same
        # fabrication `cleaner.SourceGeometry.render_dpi`'s `None` refuses.
        rasterised_at = None

    if mapping is not None and mapping.raster_dpi != rasterised_at:
        raise CoordinateContractError(
            f"the source map states the rasters it describes are at "
            f"{mapping.raster_dpi} dpi; this module rasterised at "
            f"{rasterised_at}. Refused rather than scaled by the caller's "
            "number, which would put every coordinate out by the ratio of the "
            "two while looking entirely reasonable."
        )

    recognised = read_by_ocr(pages, mapping=mapping)

    if any(
        region.extraction_confidence is not None
        and region.extraction_confidence < vision_fallback_threshold
        for region in recognised.regions
    ):
        return _vision_fallback(recognised, vision_fallback_threshold)

    return recognised
