"""The PDF Engine — every PDF operation this repository performs, in one file.

WHAT FORCED IT (`KNOWN_FAILURES.md` F-001). PyMuPDF is AGPL, and the owner ruled
on 2026-08-06: *"Do NOT purchase an Artifex licence. Keep PyMuPDF temporarily.
Immediately abstract it behind a PDF Engine interface so Engine 1 never depends
directly on PyMuPDF. The implementation must allow replacing the backend PDF
library without changing Engine 1 architecture."*

Before this module, three Engine 1 modules reached PyMuPDF independently:

    reader.py    `import pymupdf`, plus its own `_PdfDocument`/`_OpenPdf`
                 Protocols and a `cast` over `pymupdf.open`
    cleaner.py   `importlib.import_module("pymupdf")`, twice, plus a
                 three-step open/convert/reopen dance to turn a PNG into a PDF
    pipeline.py  `import pymupdf`, a SECOND copy of the same Protocols that
                 nothing called, and `pymupdf.FileDataError` named directly in
                 `BUSINESS_FAILURE` — a vendor exception type load-bearing in
                 Engine 1's own business/runtime taxonomy

Replacing the backend therefore meant editing three modules, one of which
decided what counts as a document failure. That is the definition of a
dependency that is not abstracted.

THE INTERFACE IS OPERATIONS, NOT OBJECTS, AND THAT IS THE WHOLE DESIGN.
    Handing callers a live `pymupdf.Document` and calling that an abstraction
    would move the import and change nothing: every caller would still speak
    PyMuPDF's method names, its `get_text("dict")` dictionary shape and its
    `get_pixmap(dpi=...)` keyword. `PdfDocument` below is therefore an OPAQUE
    handle — a Protocol with `close()` and nothing else — and everything a
    caller does to a PDF is a FUNCTION in this module.

    The test of the design is stated so it can be checked rather than believed:
    a different backend is a rewrite of this file and of nothing else. No
    caller names a PyMuPDF type, a PyMuPDF method, a PyMuPDF keyword or a
    PyMuPDF exception. `test_pdf_backend.py` proves the last part by walking
    every Engine 1 module's AST and failing if any of them imports `pymupdf`,
    by statement or by `importlib`.

WHY THE Protocols LOOK LIKE `reader.py`'s DID. They are `reader.py`'s, moved
    (Law 14, Law 15). PyMuPDF ships `py.typed` and leaves its functions
    unannotated, so `mypy --strict` refuses a bare call and this repository's
    zero-new-suppressions gate rules out silencing it per line. Declaring the
    exact surface used is STRICTER than a suppression: mypy then checks every
    call below against these signatures. The declarations were read off the
    installed library (PyMuPDF 1.28.0), not from memory, and they were already
    correct in `reader.py` — this file is where they stop being duplicated.

ONE VENDOR EXCEPTION IS RENAMED, AND ONLY ONE, DELIBERATELY.
    `pymupdf.FileDataError` was the single PyMuPDF name Engine 1 depended on
    for BEHAVIOUR: `pipeline.BUSINESS_FAILURE` lists it, which is what makes a
    corrupt PDF produce an artifact recording the failure instead of crashing
    the run (`APPLICATION_LAYER_CONTRACTS.md:30`). `BrokenPdfError` is this
    module's own name for that verdict, so the taxonomy belongs to Engine 1 and
    the backend keeps its exceptions to itself.

    `BrokenPdfError` carries the backend's message VERBATIM and the original as
    `__cause__`. Naming a failure must not cost the diagnosis — the same rule
    `reader.RecognitionFailedError` already states — and it also means every
    message a caller composes from `{failure}` reads exactly as it did before.

    Nothing else is converted. A boundary that enumerated more vendor
    exceptions would be an allowlist over a set this repository does not own,
    which is the general defect `reader._decode_image` already names: *"A
    BOUNDARY THAT NAMES EXCEPTION TYPES IS AN ALLOWLIST OVER A SET THE VENDOR
    CONTROLS."* Every caller of this module already wraps its calls in a
    boundary that catches `Exception` and states where it is, so an
    unconverted backend failure is named by the caller's own boundary rather
    than escaping unnamed.

WHAT THIS MODULE DOES NOT DO. It does not clean, read, parse, classify or
    score anything. It opens PDFs, counts pages, hands back text and pixels,
    and builds a PDF out of page images. Every decision about what that text
    or those pixels MEAN belongs to the sub-engine that asked for them.
"""

from __future__ import annotations

from typing import Protocol, TypedDict, cast

import pymupdf

# ── the shape of a page's structured text ─────────────────────────────────
#
# PyMuPDF's `get_text("dict")` return, declared exactly as far as this
# repository reads into it and no further. `TextBlock` is `total=False` because
# an image block carries no `lines` key at all, which is why `reader.py` reads
# it with `.get("lines", ())` rather than by subscript.


class TextSpan(TypedDict):
    """One run of text with a single style, and the box it occupies."""

    text: str
    bbox: tuple[float, float, float, float]


class TextLine(TypedDict):
    spans: list[TextSpan]


class TextBlock(TypedDict, total=False):
    lines: list[TextLine]


class StructuredText(TypedDict):
    blocks: list[TextBlock]


class PdfDocument(Protocol):
    """An open PDF. Deliberately opaque: `close()` and nothing else.

    Every other operation is a function in this module, so that a caller
    holding one of these cannot reach a backend method by accident and cannot
    be broken by a backend that names its methods differently.
    """

    def close(self) -> None: ...


class PdfBackendError(Exception):
    """This module's base error. Never raised for an empty or blank PDF."""


class BrokenPdfError(PdfBackendError):
    """The FILE's data is broken — a verdict on the DOCUMENT, not on this code.

    The one PyMuPDF failure Engine 1 depends on behaviourally: it is what
    `pipeline.BUSINESS_FAILURE` matches to decide that a document could not be
    read, so that an artifact recording the failure is produced rather than the
    run crashing. Renamed here so that decision names no vendor type.
    """


# ── the private facade over the untyped backend ───────────────────────────


class _Pixmap(Protocol):
    #: In PIXELS, and read for exactly that reason — see `pdf_of_page_images`.
    #: An image's pixel count is a fact about the bytes; its physical size is
    #: metadata that an encoder is free not to write.
    width: int
    height: int

    def tobytes(self, output: str) -> bytes: ...


class _Rect(Protocol):
    """A rectangle in PDF user space. Opaque, like `PdfDocument`."""


class _Rectangle(Protocol):
    width: float
    height: float


class _Page(Protocol):
    rect: _Rectangle

    def get_text(self, option: str) -> object: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...
    def insert_image(self, rectangle: _Rect, *, stream: bytes) -> None: ...


class _Document(Protocol):
    page_count: int

    def __getitem__(self, index: int) -> _Page: ...
    def close(self) -> None: ...
    def insert_pdf(self, source: _Document) -> None: ...
    def tobytes(self) -> bytes: ...
    def new_page(self, *, width: float, height: float) -> _Page: ...


class _OpenStream(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _Document: ...


class _OpenEmpty(Protocol):
    def __call__(self) -> _Document: ...


class _MakePixmap(Protocol):
    def __call__(self, source: bytes, /) -> _Pixmap: ...


class _MakeRect(Protocol):
    def __call__(self, left: float, top: float, right: float, bottom: float, /) -> _Rect: ...


_open_stream = cast(_OpenStream, pymupdf.open)
_open_empty = cast(_OpenEmpty, pymupdf.open)
_pixmap_of = cast(_MakePixmap, pymupdf.Pixmap)
_rectangle = cast(_MakeRect, pymupdf.Rect)

#: PDF user space is 1/72 inch, fixed by the PDF specification. This is a UNIT
#: CONVERSION, not a tuning value and not a default: no threshold, policy or
#: preference is expressed by it, and no other number would be arithmetically
#: correct. Named once so no line below spells a bare 72.
_POINTS_PER_INCH = 72

#: What `get_text` is asked for. PyMuPDF's own option strings, named once here
#: so no caller ever types one — a backend that spelled them differently would
#: change this file and nothing else.
_PLAIN = "text"
_STRUCTURED = "dict"

#: The image format pages are rendered to and rebuilt from. PNG because it is
#: lossless: a lossy re-encode would lose information the original had, which
#: is the one thing cleaning may never do (`cleaner._encode_png` states the
#: same rule for the same reason).
_RENDER_FORMAT = "png"


def require_positive_dpi(render_dpi: int) -> None:
    """Refuse an impossible DPI rather than substituting a workable one.

    Correcting it would mean choosing a number, which is the thing this module
    does not do. Refusing names the caller's mistake instead of hiding it.

    MOVED HERE FROM `reader._require_positive_dpi` WHEN F-028 ADDED A SECOND
    CALLER (Law 14). `pdf_of_page_images` needs the same check and `reader`
    imports this module, so keeping the original where it was would have meant
    either an inverted dependency or two copies of one rule — and two copies is
    how the two drift apart. `reader` now imports this one.
    """
    if render_dpi <= 0:
        raise ValueError(
            f"render_dpi must be a positive number of dots per inch, got {render_dpi}. "
            "Refused rather than corrected: no document sets a render DPI, so "
            "substituting one here would invent the owner's number (Law 52)."
        )


def _as_broken(failure: pymupdf.FileDataError) -> BrokenPdfError:
    """The backend's own verdict, wearing this module's name and its message.

    The message is copied verbatim rather than decorated, so a caller that
    composes `f"...: {failure}"` — and both `reader` and `cleaner` do — reads
    exactly as it did when the backend's exception reached it directly.
    """
    return BrokenPdfError(str(failure))


def open_pdf(data: bytes) -> PdfDocument:
    """Open PDF bytes. Raises `BrokenPdfError` when the file's data is broken.

    Never returns an empty document in place of an unopenable one: a PDF that
    could not be opened and a PDF with nothing on it are different answers, and
    `reader.py` is built on that distinction.
    """
    try:
        return _open_stream(stream=data, filetype="pdf")
    except pymupdf.FileDataError as failure:
        raise _as_broken(failure) from failure


def page_count(document: PdfDocument) -> int:
    """How many pages the open document has."""
    return int(cast(_Document, document).page_count)


def plain_text(document: PdfDocument, index: int) -> str:
    """Page `index`'s embedded text as one string, or `""` when it has none."""
    return str(cast(_Document, document)[index].get_text(_PLAIN))


def structured_text(document: PdfDocument, index: int) -> StructuredText:
    """Page `index`'s embedded text as spans carrying their bounding boxes.

    In the backend's OWN order. `SUB_ENGINE_RESPONSIBILITIES.md` §1.2 forbids
    `reader` reordering text, so nothing here sorts, and the option asked for
    is the one whose documented default is unsorted.
    """
    return cast(StructuredText, cast(_Document, document)[index].get_text(_STRUCTURED))


def render_page_png(document: PdfDocument, index: int, *, dpi: int) -> bytes:
    """Rasterise page `index` at `dpi`, as PNG bytes.

    `dpi` is required and has no default here for the same reason it has none
    in `reader.read` and `cleaner.clean_artifact`: no document in this
    repository states a render DPI, and choosing one would answer a question
    put to the owner (Law 52).
    """
    return bytes(cast(_Document, document)[index].get_pixmap(dpi=dpi).tobytes(_RENDER_FORMAT))


def page_size(document: PdfDocument, index: int) -> tuple[float, float]:
    """The page's width and height in POINTS — its physical size, not its pixels.

    A FUNCTION RATHER THAN A HANDED-OUT RECTANGLE, like everything else here. A
    caller given the backend's rectangle object would be speaking PyMuPDF, and
    the whole design of this module is that no caller does.

    Added with the F-028 fix, which needed a way to assert that a rebuilt page
    is the size its pixels represent. That assertion had no way to be written
    without either this function or a caller reaching into the backend.
    """
    rectangle = cast(_Document, document)[index].rect
    return float(rectangle.width), float(rectangle.height)


def pdf_of_page_images(pages: list[bytes], *, dpi: int) -> bytes:
    """One PDF whose pages are these PNG images, in the order given, each page
    sized to the physical size those pixels represent AT `dpi`.

    THE ORDER IS THE CALLER'S AND IS NEVER SORTED. A rebuilt PDF whose pages
    came back in a different order is a different document, and page order is
    one of the four things F-017 requires cleaning to preserve.

    ── WHY `dpi` IS REQUIRED, AND WHY IT HAS NO DEFAULT (`KNOWN_FAILURES.md`
       F-028) ──

    This function used to take pixels alone and let the backend decide what
    they measured. `convert_to_pdf()` reads the physical size out of the PNG's
    `pHYs` chunk, and `cleaner._encode_png` is `cv2.imencode(".png", ...)`,
    which does not write one — OpenCV's PNG encoder has no parameter for it.
    With no `pHYs`, MuPDF falls back to 96 dpi. Measured at `3bd31e2` on a
    612x792 pt (US Letter) source page, rasterised and rebuilt:

        render dpi      72       96      150       300
        rebuilt page   459pt   612pt   956.25pt  1912.5pt
        scale          0.7500  1.0000   1.5625    3.1250

    Correct at exactly one DPI, by accident, and wrong everywhere else by
    `dpi / 96`. Two consequences, and the second is the serious one:

      1. Coordinates on a cleaned scan did not describe the source page.
         `reader.SourceLocation` promises *"the backend's own pixel or point
         space for the page"*, kept unnormalised precisely so *"a human can
         find the region again"* — and at 300 dpi the region was 3.125x away
         from where it is.
      2. THE SAME DOCUMENT MEASURED DIFFERENTLY AT TWO DPIs. Engine 1 owes a
         truthful, measurable and REPRODUCIBLE Document Evidence Object; a
         page whose coordinate space is a function of a render setting is not
         reproducible, and that failure needs no downstream engine to exist
         before it is real.

    THE FIX IS TO STOP INFERRING IT, NOT TO WRITE THE MISSING METADATA. A
    `pHYs` chunk would restore correctness and leave the defect's SHAPE intact:
    physical size would still travel as optional metadata inside an image, and
    the next re-encode that dropped it would silently reintroduce 96 dpi. Here
    the DPI travels as a required argument, so a caller that does not know it
    fails to typecheck instead of quietly rendering at the wrong scale.

    That also makes this function consistent with the module it lives in.
    `render_page_png` above already refuses a default for exactly the stated
    reason — *"no document in this repository states a render DPI, and choosing
    one would answer a question put to the owner (Law 52)"* — as do
    `reader.read` and `cleaner.clean_artifact`. This was the one place that
    silently answered that question, and it answered it wrongly.

    The old three-step open/convert/reopen dance is gone with it: pages are now
    created at a known size and the image drawn into them, which is both
    correct and fewer moving parts.
    """
    require_positive_dpi(dpi)
    rebuilt = _open_empty()
    try:
        for page in pages:
            # PIXELS, read off the decoded image rather than off the page a
            # backend would infer. This is the number that is a fact.
            pixels = _pixmap_of(page)
            width = pixels.width * _POINTS_PER_INCH / dpi
            height = pixels.height * _POINTS_PER_INCH / dpi
            rebuilt.new_page(width=width, height=height).insert_image(
                _rectangle(0, 0, width, height), stream=page
            )
        return bytes(rebuilt.tobytes())
    finally:
        rebuilt.close()


def close_pdf(document: PdfDocument) -> None:
    """Release the open document. Separate from `open_pdf` on purpose.

    Named `close_pdf` rather than `close` because callers import these
    functions by name — see the import note in `reader.py` — and a bare `close`
    landing in a sub-engine's namespace says nothing about what it closes.

    `reader.py` nests its `try/finally` INSIDE its converting `try` so that a
    failing close is named by the same boundary as a failing read. A context
    manager here would take that choice away from the caller and put the close
    outside the boundary it belongs in.
    """
    document.close()
