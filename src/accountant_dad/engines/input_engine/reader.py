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
    `cleaner`."* `cleaner` does not exist yet. This module therefore takes the
    document as bytes plus a declared `MediaType`, and does NOT define a
    `CleanedDocument` type: that type is `cleaner`'s output and belongs to
    `cleaner` (INV-10, one concept one owner). Defining it here would put a
    second owner on it before the first one is written.

    The media type is declared by the caller and never sniffed. `CLAUDE.md`
    Law 23 - external input is untrusted - and guessing a document's type from
    its bytes is a guess, which is the one thing this sub-engine may never make.
"""

from __future__ import annotations

import importlib
import io
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import cache
from typing import Protocol, TypedDict, cast

import numpy
import numpy.typing
import pymupdf
from PIL import Image, UnidentifiedImageError

#: An RGB page as PaddleOCR wants it: height x width x 3, one byte per channel.
Page = numpy.typing.NDArray[numpy.uint8]

#: One recognised line's outline: four (x, y) corners, as PaddleOCR returns them.
Quadrilateral = numpy.typing.NDArray[numpy.int16]


# ── typed facades over two untyped dependencies ───────────────────────────
#
# PyMuPDF ships `py.typed` but leaves its functions unannotated; PaddleOCR ships
# no typing at all. Under `mypy --strict` both are errors, and the repository
# runs a zero-new-suppressions gate, so silencing them per-line is unavailable -
# and would be the wrong tool regardless.
#
# Declaring the exact API surface this module uses is STRICTER than a
# suppression, not looser: mypy then checks every call below against these
# signatures, so a misspelled method or a wrong argument type is caught, where a
# silenced line would have hidden all of it. The declarations were read off the
# installed libraries (PyMuPDF 1.28.0, PaddleOCR 3.7.0), not from memory.


class _Span(TypedDict):
    text: str
    bbox: tuple[float, float, float, float]


class _Line(TypedDict):
    spans: list[_Span]


class _Block(TypedDict, total=False):
    lines: list[_Line]


class _TextPage(TypedDict):
    blocks: list[_Block]


class _Pixmap(Protocol):
    def tobytes(self, output: str) -> bytes: ...


class _PdfPage(Protocol):
    def get_text(self, option: str) -> _TextPage: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...


class _PdfDocument(Protocol):
    page_count: int

    def __getitem__(self, index: int) -> _PdfPage: ...
    def close(self) -> None: ...


class _OpenPdf(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _PdfDocument: ...


#: `pymupdf.open`, with the two keyword arguments this module actually passes.
_open_pdf = cast(_OpenPdf, pymupdf.open)


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
    ) -> _Recogniser: ...


class ReaderError(Exception):
    """Anything `reader` refuses to do quietly. Never raised for a blank page."""


class UnreadableDocumentError(ReaderError):
    """The document could not be opened or decoded at all.

    Deliberately NOT the same outcome as a blank page. A blank page is a
    successful reading of nothing; this is the absence of a reading, and the two
    must stay distinguishable for the whole life of the artifact built from them.
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


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Where on the page a piece of text sits.

    `ENGINE_1:511` - *"Source locations are emitted even for low-confidence
    extractions - that is what makes a later human check possible."* So this is
    never optional and never omitted, whatever the confidence attached to it.

    Coordinates are in the backend's own pixel or point space for the page named
    by `page_index`; they are not normalised, because normalising would discard
    the scale a human needs to find the region again.
    """

    page_index: int
    left: float
    top: float
    right: float
    bottom: float


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


def _require_positive_dpi(render_dpi: int) -> None:
    """Refuse an impossible DPI rather than substituting a workable one.

    Correcting it would mean choosing a number, which is the thing this module
    does not do. Refusing names the caller's mistake instead of hiding it.
    """
    if render_dpi <= 0:
        raise ValueError(
            f"render_dpi must be a positive number of dots per inch, got {render_dpi}. "
            "Refused rather than corrected: no document sets a render DPI, so "
            "substituting one here would invent the owner's number (Law 52)."
        )


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
        opened = _open_pdf(stream=document, filetype="pdf")
    except Exception as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be opened as a PDF: {failure}. "
            "Raised rather than returned as an empty reading, which would be "
            "indistinguishable downstream from an honest reading of a blank page."
        ) from failure

    regions: list[TextRegion] = []
    try:
        pages_read = opened.page_count
        for page_index in range(pages_read):
            page = opened[page_index]
            # "dict" gives spans with their bounding boxes. `sort=False` is the
            # default and is what we want: §1.2 forbids reordering, so the
            # backend's own order is preserved rather than re-sorted by us.
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", ()):
                    for span in line["spans"]:
                        text = span["text"]
                        if not text.strip():
                            # A whitespace-only span is not a reading. Skipping
                            # it drops nothing a human could check, and keeping
                            # it would pad the region count with non-evidence.
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
                                ),
                                extraction_confidence=None,
                            )
                        )
    finally:
        opened.close()

    return Reading(regions=tuple(regions), backend=Backend.PDF_TEXT_LAYER, pages_read=pages_read)


def _render_pdf_pages(document: bytes, *, render_dpi: int) -> list[bytes]:
    """Rasterise every page to PNG at the CALLER's DPI. Raises on an unopenable PDF."""
    try:
        opened = _open_pdf(stream=document, filetype="pdf")
    except Exception as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be opened as a PDF: {failure}"
        ) from failure

    try:
        return [
            bytes(opened[index].get_pixmap(dpi=render_dpi).tobytes("png"))
            for index in range(opened.page_count)
        ]
    finally:
        opened.close()


def _decode_image(image: bytes) -> Page:
    """Bytes to an RGB array PaddleOCR can read. Raises on anything undecodable."""
    try:
        with Image.open(io.BytesIO(image)) as opened:
            decoded: Page = numpy.asarray(opened.convert("RGB"), dtype=numpy.uint8)
            return decoded
    except (UnidentifiedImageError, OSError, ValueError) as failure:
        raise UnreadableDocumentError(
            f"the bytes supplied could not be decoded as an image: {failure}. "
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
    """
    build_recogniser = cast(_RecogniserFactory, importlib.import_module("paddleocr").PaddleOCR)
    return build_recogniser(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def read_by_ocr(pages: list[bytes]) -> Reading:
    """Recognise text on already-rasterised pages with PaddleOCR.

    Every region carries the score PaddleOCR reported for it, converted to
    `Decimal` through the number's own string form so the reported value is
    preserved exactly rather than re-rounded.

    A page with nothing recognisable on it contributes zero regions. It does not
    contribute an empty-string region, and it is not an error.
    """
    engine = _recogniser()

    regions: list[TextRegion] = []
    for page_index, page in enumerate(pages):
        for result in engine.predict(_decode_image(page)):
            # The three keys PaddleOCR 3.7.0 populates for a text-only pipeline,
            # read off a real result rather than assumed. `rec_polys` holds one
            # four-point quadrilateral per recognised line.
            texts = cast(list[str], result["rec_texts"])
            scores = cast(list[float], result["rec_scores"])
            polygons = cast(list[Quadrilateral], result["rec_polys"])
            for text, score, polygon in zip(texts, scores, polygons, strict=True):
                if not text.strip():
                    continue
                xs = [float(point[0]) for point in polygon]
                ys = [float(point[1]) for point in polygon]
                regions.append(
                    TextRegion(
                        text=text,
                        location=SourceLocation(
                            page_index=page_index,
                            left=min(xs),
                            top=min(ys),
                            right=max(xs),
                            bottom=max(ys),
                        ),
                        # `str(score)` then Decimal: `Decimal(float)` would expand
                        # the binary value into its full expansion, which is not
                        # the number PaddleOCR reported.
                        extraction_confidence=Decimal(str(score)),
                    )
                )

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

    A page with nothing on it returns zero regions. A file that cannot be opened
    raises `UnreadableDocumentError`. Those are different answers to different
    questions and this function never conflates them.
    """
    _require_positive_dpi(render_dpi)

    if media_type is MediaType.PDF:
        from_text_layer = read_pdf_text_layer(document)
        if from_text_layer.regions:
            # A real text layer needs no OCR, so no OCR confidence exists, so
            # there is nothing the fallback threshold could be below.
            return from_text_layer
        pages = _render_pdf_pages(document, render_dpi=render_dpi)
    else:
        # One image is one page. It is decoded here rather than inside the OCR
        # loop so that undecodable bytes fail before any model is loaded.
        _decode_image(document)
        pages = [document]

    recognised = read_by_ocr(pages)

    if any(
        region.extraction_confidence is not None
        and region.extraction_confidence < vision_fallback_threshold
        for region in recognised.regions
    ):
        return _vision_fallback(recognised, vision_fallback_threshold)

    return recognised
