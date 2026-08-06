"""F-030's CONSUMER side: a `SourceLocation` must name the page it answers on.

`KNOWN_FAILURES.md` F-030 is stated as a producer defect — the cleaner crops and
turns a page and threw the geometry away. The producer half is fixed:
`cleaner.SourceGeometry` carries, per page, the affine from a CLEANED-raster
pixel to a SOURCE-raster pixel. `reader` ignored it, and emitted
`SourceLocation` in cleaned-image space *as though that were the document*.

    THE CONSUMER DEFECT IS NOT "THE NUMBERS ARE WRONG". It is that nothing on a
    `SourceLocation` said WHICH page its numbers answered on, so a correct
    cleaned-space coordinate and a correct source-space coordinate were the same
    five fields and could not be told apart by any reader of the artifact.

Every test below therefore asserts one of exactly two properties:

  1. WITH a map, the coordinate lands on the page AS RECEIVED, to a measured
     tolerance, and says so.
  2. WITHOUT a usable map, `reader` REFUSES to claim a source coordinate — it
     either labels the space it really answered in, or raises. It never emits
     cleaned pixels wearing the document's name.

THE COORDINATE CONTRACT, STATED ONCE HERE AND ASSERTED BELOW rather than left
implicit. Most coordinate defects are contract mismatches, not matrix errors, so
the contract gets its own tests before any tolerance is asserted — a tolerance
in an unnamed unit means nothing.

    unit               pixels, or PDF points, named by `SourceLocation.space`
    origin             the TOP-LEFT corner of the page
    x                  increases to the RIGHT
    y                  increases DOWNWARD
    transform          CLEANED pixel -> SOURCE pixel, one direction only

`test_the_coordinate_axes_run_the_way_the_contract_says` measures all four
against the real backend rather than restating them.

REAL EVERYTHING EXCEPT THE RECOGNISER (`CLAUDE.md` §J.6/§J.7). The cleaner runs
for real, the rasteriser runs for real, the affine is the one the cleaner
recorded, and `reader.read` does its own PDF round trip. The one substitution is
the `paddleocr` MODULE — the narrowest external edge there is, and the SAME
mechanism `test_input_engine_reader.py` already installs and documents, imported
rather than copied (Law 14). PaddleOCR is absent here and on CI (F-002/F-009),
which is exactly why this path was never executed and the defect stayed latent.

AND THE SUBSTITUTE DOES NOT INVENT A COORDINATE. `_MarkFinder` below is handed
the real raster and finds the planted mark's real ink in it. The only thing
faked is the *recognition* — the string. Every number in every assertion is
measured off pixels that the production code produced.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, cast

import cv2
import numpy
import pytest
from PIL import Image as PilImage
from test_input_engine_reader import (
    InstallFactory,
    a_clean_recogniser_cache,  # noqa: F401 — install_paddleocr depends on it
    install_paddleocr,  # noqa: F401 — a pytest fixture, used by name
    rectangle,
)
from test_input_engine_reader import open_pdf as author_a_pdf

from accountant_dad.engines.input_engine import cleaner, reader
from accountant_dad.pdf_backend import close_pdf, open_pdf, render_page_png, structured_text


class _Deflating(Protocol):
    """`tobytes` with the one keyword the authoring side here also needs.

    `test_input_engine_reader.py` already declares the authoring facade over
    PyMuPDF — `open_pdf`, `rectangle` and the `_Document`/`_Page` Protocols
    behind them — and those are imported rather than copied. It declares
    `tobytes()` without keywords, and widening it there to suit this file would
    loosen the signature every other fixture in that file calls. So the extra
    keyword gets its own narrow Protocol, exactly as `_EncryptingDocument` does
    there for the same reason.

    `deflate=True` IS NOT COSMETIC HERE. Without it a 600 dpi page fixture
    carries ~5.5 MB of raw pixels through every step of the test; `pdf_backend`
    measured 663x on one US Letter page.
    """

    def tobytes(self, *, deflate: bool) -> bytes: ...


# ── the page this suite plants marks on ───────────────────────────────────
#
# A PHOTOGRAPH of a page, wrapped in a PDF: no text layer, so `reader` routes it
# to OCR, which is the only path a cleaned-raster coordinate can come out of.
# The ink frame gives the cleaner a content box to crop to and a long straight
# edge to measure skew from; the small square is the thing whose position is
# known and tracked all the way through.

#: Deliberately NOT a whole number of pixels at every DPI, and not US Letter:
#: 612 x 792 divides evenly at every DPI and hides exactly the rounding F-031
#: records. 400 x 200 pt at 150 dpi is 833.33 px, which does not.
PAGE_WIDTH_POINTS = 400.0
PAGE_HEIGHT_POINTS = 200.0

#: Half the planted square's side, in source pixels. Large enough that the mark
#: survives denoising at 150 dpi, small enough that it is never mistaken for the
#: frame.
MARK_HALF = 8
MARK_SIDE = 2 * MARK_HALF + 1

#: The tolerance the owner set for this change: a coordinate that has been
#: through cleaner and reader must land within this of where it started. NOT a
#: number chosen here — the producer was measured at 0.000000 px unturned and
#: 0.270661 px on a turned invoice, and this is the bound stated with it.
ROUND_TRIP_TOLERANCE_PIXELS = 0.30

#: A threshold at the bottom of the range, so the vision fallback is never what
#: a test is measuring. `reader.read` still demands one (see the signature test
#: in `test_input_engine_reader.py`); this is a test input, not a product value.
NO_FALLBACK = Decimal("0.0")

#: The midpoint of an 8-bit range. Anything darker than this is ink for the
#: purpose of finding where the mark was drawn; the page is white and the mark
#: is black, so nothing sits near it.
INK_BELOW = 128

#: A corner count, not a magic number: `rec_polys` holds one FOUR-point outline
#: per recognised line, which is the whole reason all four have to be
#: transformed rather than two.
CORNERS_OF_A_QUADRILATERAL = 4

#: Big enough that no rounding, resampling or anti-aliasing residual could
#: account for it. Used where a test must show that the WRONG answer is wrong by
#: a landslide rather than by a hair.
UNMISTAKEABLY_WRONG_PIXELS = 100.0

#: Below this the linear part of an affine is not distinguishable from the
#: identity at float precision. Measured at 15 degrees the off-diagonal terms
#: are 0.258969, three orders of magnitude above it.
NOT_THE_IDENTITY = 0.01

#: The cleaner settings every test here supplies in full. `CleanerSettings` has
#: no default for any field on purpose, so this block is unavoidable. The deskew
#: limit is 20 degrees because one fixture is planted at 15 and a limit below
#: the planted angle would silently turn the deskew off — the stage this whole
#: file exists to prove is mapped.
CLEANER_SETTINGS = cleaner.CleanerSettings(
    max_deskew_degrees=20.0,
    denoise_strength=6.0,
    denoise_template_window=7,
    denoise_search_window=21,
    contrast_clip_limit=2.0,
    contrast_tile_grid=8,
    crop_margin_pixels=4,
    max_ink_loss_fraction=0.05,
)


def a_page_raster(*, skew_degrees: float, dpi: int) -> numpy.typing.NDArray[numpy.uint8]:
    """A white page with an ink frame and one black square at its centre."""
    width = round(PAGE_WIDTH_POINTS * dpi / 72.0)
    height = round(PAGE_HEIGHT_POINTS * dpi / 72.0)
    canvas = numpy.full((height, width), 255, dtype=numpy.uint8)
    inset = max(4, width // 20)
    thickness = max(2, width // 200)
    canvas[inset : inset + thickness, inset : width - inset] = 0
    canvas[height - inset - thickness : height - inset, inset : width - inset] = 0
    canvas[inset : height - inset, inset : inset + thickness] = 0
    canvas[inset : height - inset, width - inset - thickness : width - inset] = 0
    across, down = width // 2, height // 2
    canvas[down - MARK_HALF : down + MARK_HALF + 1, across - MARK_HALF : across + MARK_HALF + 1] = 0
    if not skew_degrees:
        return canvas
    turn = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), skew_degrees, 1.0)
    turned = cv2.warpAffine(
        canvas,
        turn,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    return numpy.asarray(turned, dtype=numpy.uint8)


def as_png(array: numpy.typing.NDArray[numpy.uint8]) -> bytes:
    buffer = io.BytesIO()
    PilImage.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def decoded(png: bytes) -> numpy.typing.NDArray[numpy.uint8]:
    with PilImage.open(io.BytesIO(png)) as opened:
        return numpy.asarray(opened.convert("L"), dtype=numpy.uint8)


def a_scanned_pdf(*, skew_degrees: float, dpi: int) -> bytes:
    """One page carrying that raster as an image. No text layer anywhere."""
    document = author_a_pdf()
    page = document.new_page(width=PAGE_WIDTH_POINTS, height=PAGE_HEIGHT_POINTS)
    page.insert_image(
        rectangle(0, 0, PAGE_WIDTH_POINTS, PAGE_HEIGHT_POINTS),
        stream=as_png(a_page_raster(skew_degrees=skew_degrees, dpi=dpi)),
    )
    built = bytes(cast(_Deflating, document).tobytes(deflate=True))
    document.close()
    return built


def a_text_layer_pdf(words: str) -> bytes:
    """One page with real embedded text, which `cleaner` passes through untouched."""
    document = author_a_pdf()
    document.new_page(width=PAGE_WIDTH_POINTS, height=PAGE_HEIGHT_POINTS).insert_text(
        (20.0, 30.0), words, fontname="helv", fontsize=8
    )
    built = bytes(document.tobytes())
    document.close()
    return built


def rendered_at(document: bytes, *, dpi: int) -> numpy.typing.NDArray[numpy.uint8]:
    """The page as a raster, through the production rasteriser."""
    opened = open_pdf(document)
    try:
        return decoded(render_page_png(opened, 0, dpi=dpi))
    finally:
        close_pdf(opened)


def the_mark_in(
    grey: numpy.typing.NDArray[numpy.uint8], *, expected_side: float
) -> tuple[float, float]:
    """Where the planted square's ink actually is, by connected components.

    NOT A WINDOW AROUND A GUESS, and the difference is measured: a window
    centred on the expected position also swallows part of the ink frame, whose
    thousands of pixels then dominate the centroid and put the answer 93 px away
    at 150 dpi. The mark is found by being the one compact component instead.

    The centroid is intensity-weighted, so an anti-aliased edge contributes in
    proportion to its darkness — which is what makes it stable to a fraction of
    a pixel through a resampling rotation.
    """
    _split, mask = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best: tuple[float, int, int, int, int] | None = None
    for index in range(1, count):
        left, top, width, height, _area = (int(value) for value in stats[index])
        if width > expected_side * 3 or height > expected_side * 3:
            continue
        closeness = abs(width - expected_side) + abs(height - expected_side)
        if best is None or closeness < best[0]:
            best = (closeness, left, top, width, height)
    assert best is not None, "the planted mark was not found at all"
    _closeness, left, top, width, height = best
    pad = 2
    x0, y0 = max(0, left - pad), max(0, top - pad)
    x1 = min(grey.shape[1], left + width + pad)
    y1 = min(grey.shape[0], top + height + pad)
    darkness = 255.0 - grey[y0:y1, x0:x1].astype(numpy.float64)
    downs, acrosses = numpy.mgrid[y0:y1, x0:x1]
    total = darkness.sum()
    return (
        float((darkness * acrosses).sum() / total),
        float((darkness * downs).sum() / total),
    )


# ── the substituted recogniser: it LOCATES, it does not invent ────────────


@dataclass(frozen=True, slots=True)
class Recognised:
    """What the substitute reports for the one thing it finds."""

    text: str
    score: float


FOUND = Recognised(text="MARK", score=0.99)


class _MarkFinder:
    """Stands in for PaddleOCR and reports the planted mark's REAL outline.

    A scripted recogniser returning a fixed box would make every assertion below
    a statement about the script. This one is handed the actual raster `reader`
    produced and measures the ink in it, so the polygon that enters the mapping
    is a real position on a real page and the round-trip number is real.
    """

    def __init__(self) -> None:
        self.rasters: list[reader.Page] = []

    def predict(self, image: reader.Page) -> list[reader._OcrResult]:
        self.rasters.append(image)
        grey = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        _split, mask = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        # COMPACT IN BOTH AXES, and the bound is derived from the fixture rather
        # than tuned. The frame spans at least 90% of the page in one direction
        # by construction; the mark spans 17 px of at least 833, under 2.1%. An
        # earlier version excluded only components as WIDE as the widest, which
        # kept the frame's two VERTICAL bars — tall, narrow, and four times the
        # mark's area — and picked one of them at 15 degrees, 186.95 px away.
        compact = max(image.shape[0], image.shape[1]) // 8
        best: tuple[int, int, int, int, int] | None = None
        for index in range(1, count):
            left, top, width, height, _area = (int(value) for value in stats[index])
            if width > compact or height > compact:
                continue
            if best is None or width * height > best[0]:
                best = (width * height, left, top, width, height)
        assert best is not None, "the substitute recogniser found no compact component"
        _area, left, top, width, height = best
        outline = numpy.array(
            [
                (left + width - 1, top + height - 1),
                (left, top + height - 1),
                (left, top),
                (left + width - 1, top),
            ],
            dtype=numpy.int16,
        )
        return [
            _Result(
                {
                    "rec_texts": [FOUND.text],
                    "rec_scores": [FOUND.score],
                    "rec_polys": [outline],
                }
            )
        ]


class _Result:
    """One PaddleOCR result, exposing exactly the three keys 3.7.0 populates."""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __getitem__(self, key: str) -> object:
        return self._payload[key]


class _Factory:
    """`paddleocr.PaddleOCR`, as `reader._recogniser` calls it."""

    def __init__(self, recogniser: _MarkFinder) -> None:
        self.recogniser = recogniser

    def __call__(
        self,
        *,
        lang: str,
        use_doc_orientation_classify: bool,
        use_doc_unwarping: bool,
        use_textline_orientation: bool,
        enable_mkldnn: bool,
    ) -> reader._Recogniser:
        del lang, use_doc_orientation_classify, use_doc_unwarping
        del use_textline_orientation, enable_mkldnn
        return self.recogniser


@pytest.fixture
def a_recogniser_that_finds_the_mark(
    install_paddleocr: InstallFactory,  # noqa: F811 — see the import block
) -> _MarkFinder:
    """The substitution, through the SAME edge `test_input_engine_reader.py` uses.

    The parameter name is how pytest resolves a fixture, so it necessarily
    shadows the import that makes the fixture visible here. That is the
    mechanism, not a mistake — hence the one suppression, which names its code
    (a bare `noqa` is itself a violation under PGH004).
    """
    finder = _MarkFinder()
    install_paddleocr(_Factory(finder))
    return finder


#: For tests that need the recogniser INSTALLED but never look at it. Declaring
#: it as a parameter would be an unused argument; this says the same thing
#: without one.
finds_the_mark = pytest.mark.usefixtures("a_recogniser_that_finds_the_mark")


# ── the cleaned page, and the map `reader` must be handed ─────────────────


@dataclass(frozen=True, slots=True)
class Planted:
    """One fixture, cleaned, with the mark's known position on the page AS RECEIVED."""

    cleaned: cleaner.CleanedDocument
    source_mark: tuple[float, float]
    drawn_mark: tuple[float, float]
    dpi: int


def plant(*, skew_degrees: float, dpi: int) -> Planted:
    authored = a_page_raster(skew_degrees=skew_degrees, dpi=dpi)
    scan = a_scanned_pdf(skew_degrees=skew_degrees, dpi=dpi)
    source = rendered_at(scan, dpi=dpi)
    return Planted(
        cleaned=cleaner.clean_artifact(
            scan, cleaner.MediaKind.PDF, CLEANER_SETTINGS, render_dpi=dpi
        ),
        source_mark=the_mark_in(source, expected_side=MARK_SIDE),
        # WHERE THE SQUARE WAS WRITTEN, as an array index, off the raster this
        # file authored — not `source.shape / 2`. The page is 400x200 pt, which
        # at 150 dpi is 833.33 px, so the rasteriser encloses it in 834 and the
        # two centres differ by a pixel. Taking the centre of the ENCLOSURE
        # would compare the measurement against a number that drifts with the
        # enclosure instead of against where the ink was put.
        drawn_mark=(float(authored.shape[1] // 2), float(authored.shape[0] // 2)),
        dpi=dpi,
    )


def a_map_for(planted: Planted, *, raster_dpi: int | None = None) -> reader.SourceMapping:
    """The contract a caller holding a `CleanedDocument` can state truthfully."""
    height, width = planted.cleaned.cleaned.shape[:2]
    return reader.SourceMapping(
        pages=(
            reader.CleanedPage(
                page_index=0,
                height=int(height),
                width=int(width),
                geometry=planted.cleaned.geometry_of(1),
            ),
        ),
        raster_dpi=planted.dpi if raster_dpi is None else raster_dpi,
        contract_version=reader.COORDINATE_CONTRACT_VERSION,
    )


def read_the_cleaned_scan(
    planted: Planted, *, mapping: reader.SourceMapping | None, render_dpi: int | None = None
) -> reader.Reading:
    """`reader.read` on the CLEANED artifact, exactly as the pipeline calls it."""
    assert planted.cleaned.artifact is not None
    return reader.read(
        planted.cleaned.artifact.payload,
        media_type=reader.MediaType.PDF,
        render_dpi=planted.dpi if render_dpi is None else render_dpi,
        vision_fallback_threshold=NO_FALLBACK,
        mapping=mapping,
    )


def centre_of(location: reader.SourceLocation) -> tuple[float, float]:
    """The mean of the four transformed corners.

    THE CENTROID AND NOT THE RECTANGLE, and the reason is the defect this file
    is about. An affine map carries the centroid of a quadrilateral to the
    centroid of its image exactly, while the axis-aligned rectangle ENCLOSING a
    turned quadrilateral is genuinely larger than the one it came from. So the
    centre is the quantity that has a right answer to compare against; the
    rectangle's growth is asserted separately, as growth.
    """
    assert location.corners, "no transformed corners were kept"
    return (
        sum(across for across, _ in location.corners) / len(location.corners),
        sum(down for _, down in location.corners) / len(location.corners),
    )


# ── 1. the contract, measured rather than restated ────────────────────────


def test_the_coordinate_axes_run_the_way_the_contract_says() -> None:
    """Origin top-left, x rightwards, y DOWNWARDS — in both spaces at once.

    A tolerance asserted in an unnamed unit means nothing, so the unit and the
    axes are measured before any tolerance below is trusted. Both halves matter:
    the PDF specification's own user space has its origin at the BOTTOM-left and
    y running UP, so a reader who assumed the specification rather than measuring
    the backend would be upside down on every page and would still see plausible
    numbers.
    """
    built = a_text_layer_pdf("TOPLEFT")

    opened = open_pdf(built)
    try:
        spans = [
            span
            for block in structured_text(opened, 0)["blocks"]
            for line in block.get("lines", ())
            for span in line["spans"]
        ]
    finally:
        close_pdf(opened)
    assert len(spans) == 1
    left, top, right, bottom = (float(edge) for edge in spans[0]["bbox"])

    assert left < right, "x does not increase to the right"
    assert top < bottom, "y does not increase downwards"
    # Drawn 20 pt from the LEFT edge and 30 pt from the TOP. A bottom-left
    # origin would put the ink near y = 200 - 30 = 170 instead.
    assert left == pytest.approx(20.0, abs=1.0), f"origin is not at the left: {left}"
    assert top == pytest.approx(21.4, abs=2.0), f"origin is not at the top: {top}"

    dpi = 150
    raster = rendered_at(built, dpi=dpi)
    ink = numpy.argwhere(raster < INK_BELOW)
    points_per_pixel = 72.0 / dpi
    highest_ink = float(ink[:, 0].min()) * points_per_pixel
    lowest_ink = float(ink[:, 0].max()) * points_per_pixel
    leftmost_ink = float(ink[:, 1].min()) * points_per_pixel

    # INSIDE the reported box, not equal to its edges: a span's box runs from the
    # font's ascender to its descender, and no glyph in "TOPLEFT" reaches either.
    # Measured at 150 dpi: box 21.400..32.392 pt, ink 24.480..29.760 pt.
    assert top <= highest_ink <= lowest_ink <= bottom, (
        f"ink at {highest_ink:.3f}..{lowest_ink:.3f} pt is outside the reported "
        f"box {top:.3f}..{bottom:.3f}; the raster and the page disagree about y"
    )
    assert left <= leftmost_ink, "the raster's columns and the page's points disagree about x"
    # The flipped reading, named so the assertion above cannot pass by accident:
    # a bottom-left origin would put this ink near 200 - 30 = 170 pt.
    flipped = PAGE_HEIGHT_POINTS - top
    assert abs(highest_ink - flipped) > UNMISTAKEABLY_WRONG_PIXELS, (
        "the axes are the PDF specification's user space, not the backend's"
    )


def test_a_text_layer_reading_names_the_space_it_answered_in() -> None:
    """A PDF text layer is read in POINTS on the page handed to this module.

    Not `UNSTATED`, and not the source page: `reader` is handed bytes and cannot
    know whether they are the document as received or a rebuild, so it names
    what it can prove — the page it read.
    """
    built = a_text_layer_pdf("TAX INVOICE")

    reading = reader.read(
        built,
        media_type=reader.MediaType.PDF,
        render_dpi=150,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert reading.regions
    assert {region.location.space for region in reading.regions} == {
        reader.CoordinateSpace.PDF_PAGE_POINTS
    }


@finds_the_mark
def test_an_unmapped_ocr_reading_says_it_is_in_the_raster_it_read_not_the_document() -> None:
    """WITHOUT a map, the reader refuses to CLAIM a source coordinate.

    This is F-030's consumer defect in one assertion. Before the fix the very
    same five numbers came back with nothing saying they were cleaned pixels,
    and every downstream consumer read them as the document's own. They still
    come back — dropping them would lose the only locator there is — but they
    now name the raster they belong to, which is a statement anyone can check.
    """
    planted = plant(skew_degrees=3.0, dpi=150)

    reading = read_the_cleaned_scan(planted, mapping=None)

    assert reading.regions
    region = reading.regions[0]
    assert region.location.space is reader.CoordinateSpace.OCR_RASTER_PIXELS
    # And the numbers really are the WRONG ones for the document, which is what
    # makes the label load-bearing rather than decorative.
    assert math.dist(centre_of(region.location), planted.source_mark) > 1.0, (
        "the cleaned raster happens to agree with the source here, so this "
        "fixture cannot tell a labelled answer from an unlabelled one"
    )


@finds_the_mark
def test_reader_never_emits_an_unstated_space() -> None:
    """`UNSTATED` is the default on a hand-built `SourceLocation` and nothing
    this module produces may carry it.

    The default exists because a location constructed by somebody else genuinely
    has not stated its space, and inventing one for them would be the fabricated
    measurement (Law 24) this whole file is about. What must never happen is
    `reader` itself leaving it unset.
    """
    planted = plant(skew_degrees=0.0, dpi=150)

    unmapped = read_the_cleaned_scan(planted, mapping=None)
    mapped = read_the_cleaned_scan(planted, mapping=a_map_for(planted))

    assert unmapped.regions and mapped.regions
    for reading in (unmapped, mapped):
        for region in reading.regions:
            assert region.location.space is not reader.CoordinateSpace.UNSTATED


# ── 2. the round trip, against a KNOWN position on the page as received ───


@pytest.mark.parametrize("dpi", [150, 300, 600])
@pytest.mark.parametrize("skew_degrees", [0.0, 3.0, 15.0])
@finds_the_mark
def test_a_cleaned_ocr_coordinate_lands_where_the_mark_was_on_the_page_as_received(
    dpi: int, skew_degrees: float
) -> None:
    """THE END-TO-END ASSERTION: cleaned OCR output -> reader -> the source page.

    The truth is not derived from the map. The mark is planted at a known place,
    the page as received is rasterised through the production rasteriser, and
    the mark's ink is found in THAT raster. Only the reader's mapping connects
    the two, so the number below measures the mapping and nothing else.

    Re-measuring the producer would prove nothing here: the cleaner's affine is
    already measured exact. What was never executed is the consumer applying it.
    """
    planted = plant(skew_degrees=skew_degrees, dpi=dpi)
    # The independently measured truth really is the planted one, so "known" is
    # a fact about the fixture and not about the machinery under test.
    assert math.dist(planted.source_mark, planted.drawn_mark) < 1.0

    reading = read_the_cleaned_scan(planted, mapping=a_map_for(planted))

    assert len(reading.regions) == 1
    location = reading.regions[0].location
    assert location.space is reader.CoordinateSpace.SOURCE_RASTER_PIXELS
    assert location.page_index == 0
    error = math.dist(centre_of(location), planted.source_mark)
    assert error <= ROUND_TRIP_TOLERANCE_PIXELS, (
        f"the mark came back {error:.6f} px from where it was on the page as "
        f"received, against a {ROUND_TRIP_TOLERANCE_PIXELS} px bound"
    )


@finds_the_mark
def test_the_map_is_a_crop_at_a_non_zero_origin_even_on_a_dead_straight_page() -> None:
    """The 0-degree fixture is not a trivial identity, and this proves it.

    A map that were the identity would pass the round-trip test above while
    doing nothing, so the fixture's own displacement is asserted: the crop
    starts well inside the page, and a reader that ignored the map would be
    exactly that far out.
    """
    planted = plant(skew_degrees=0.0, dpi=300)
    _a, _b, across, _d, _e, down = planted.cleaned.geometry_of(1).to_source
    assert across > 1.0 and down > 1.0, f"the crop origin is ({across}, {down}), not a real crop"

    reading = read_the_cleaned_scan(planted, mapping=a_map_for(planted))
    mapped = centre_of(reading.regions[0].location)

    assert math.dist(mapped, planted.source_mark) <= ROUND_TRIP_TOLERANCE_PIXELS
    unmapped = read_the_cleaned_scan(planted, mapping=None)
    assert math.dist(centre_of(unmapped.regions[0].location), planted.source_mark) == pytest.approx(
        math.hypot(across, down), abs=1.0
    ), "ignoring the map should be wrong by exactly the crop origin on a straight page"


@finds_the_mark
def test_a_rotated_crop_cannot_be_undone_by_a_translation_and_the_reader_does_not_try() -> None:
    """F-030 names a crop ORIGIN. A turn is not a translation, and here is the gap.

    The linear part of the map is asserted to be a real rotation, then the
    answer a translation-only fix would have given is computed from the map's
    own two shift terms and shown to be wrong by a large, measured amount. That
    is the difference between the fix F-030 asked for and the one that works.
    """
    planted = plant(skew_degrees=15.0, dpi=300)
    across_x, across_y, shift_x, shift_y_term, down_y, shift_y = planted.cleaned.geometry_of(
        1
    ).to_source
    assert abs(across_y) > NOT_THE_IDENTITY or abs(shift_y_term) > NOT_THE_IDENTITY, (
        "the linear part is diagonal, so this fixture carries no rotation at all"
    )
    assert across_x != pytest.approx(1.0, abs=1e-4), "the linear part is the identity"
    assert down_y != pytest.approx(1.0, abs=1e-4), "the linear part is the identity"

    reading = read_the_cleaned_scan(planted, mapping=a_map_for(planted))
    by_the_affine = centre_of(reading.regions[0].location)
    assert math.dist(by_the_affine, planted.source_mark) <= ROUND_TRIP_TOLERANCE_PIXELS

    in_cleaned = centre_of(read_the_cleaned_scan(planted, mapping=None).regions[0].location)
    by_a_translation = (in_cleaned[0] + shift_x, in_cleaned[1] + shift_y)
    missed_by = math.dist(by_a_translation, planted.source_mark)
    assert missed_by > UNMISTAKEABLY_WRONG_PIXELS, (
        f"a translation-only map missed by only {missed_by:.4f} px on a 15 degree "
        "turn, so this fixture does not separate the two fixes"
    )


@finds_the_mark
def test_all_four_corners_are_transformed_and_the_quad_is_kept() -> None:
    """A rotation turns a rectangle into a QUADRILATERAL, so four corners move.

    Transforming only the top-left and bottom-right would leave a rectangle that
    is neither the region nor its enclosure. The transformed quad is kept on the
    location, and the axis-aligned rectangle is derived from it ONLY at the
    boundary where `SourceLocation`'s four fields demand one — which is why the
    enclosure is measurably LARGER than the region it encloses.
    """
    planted = plant(skew_degrees=15.0, dpi=300)

    location = read_the_cleaned_scan(planted, mapping=a_map_for(planted)).regions[0].location

    assert len(location.corners) == CORNERS_OF_A_QUADRILATERAL, (
        "the transformed quadrilateral was discarded"
    )
    acrosses = [across for across, _ in location.corners]
    downs = [down for _, down in location.corners]
    assert len({round(value, 6) for value in acrosses}) == CORNERS_OF_A_QUADRILATERAL, (
        "the four corners share x values, so they were not each transformed"
    )
    assert location.left == pytest.approx(min(acrosses))
    assert location.right == pytest.approx(max(acrosses))
    assert location.top == pytest.approx(min(downs))
    assert location.bottom == pytest.approx(max(downs))

    # WHAT A TWO-CORNER IMPLEMENTATION WOULD HAVE PRODUCED, built here rather
    # than argued about: map the OCR box's top-left and bottom-right ONLY, and
    # enclose those two. The two DPIs are equal in this fixture, so the map is
    # `source_pixel` with no scaling and the comparison is exact.
    in_the_raster = read_the_cleaned_scan(planted, mapping=None).regions[0].location
    geometry = planted.cleaned.geometry_of(1)
    one_end = geometry.source_pixel(in_the_raster.left, in_the_raster.top)
    other_end = geometry.source_pixel(in_the_raster.right, in_the_raster.bottom)
    two_corner_left, two_corner_right = sorted((one_end[0], other_end[0]))
    two_corner_top, two_corner_bottom = sorted((one_end[1], other_end[1]))

    # ASSERTED AS CONTAINMENT, not as a width, because which DIMENSION shrinks
    # depends on the sign of the turn: at +15 degrees the diagonal happens to
    # span the full width and only the height collapses. Containment is the
    # property that holds either way — a box built from two corners of a turned
    # quadrilateral does not contain the other two.
    outside = [
        (across, down)
        for across, down in location.corners
        if not (
            two_corner_left - 1e-9 <= across <= two_corner_right + 1e-9
            and two_corner_top - 1e-9 <= down <= two_corner_bottom + 1e-9
        )
    ]
    assert outside, (
        "every transformed corner already sits inside the box two corners would "
        "have produced, so this fixture cannot tell the two implementations apart"
    )
    four_corner_area = (location.right - location.left) * (location.bottom - location.top)
    two_corner_area = (two_corner_right - two_corner_left) * (two_corner_bottom - two_corner_top)
    assert four_corner_area > two_corner_area + 1.0, (
        f"the four-corner enclosure is {four_corner_area:.4f} px^2 and a "
        f"two-corner one would be {two_corner_area:.4f} px^2"
    )


# ── 3. resolution composition, measured before it is assumed ──────────────


def test_the_cleaned_and_ocr_rasters_are_the_same_size_when_the_two_dpis_agree() -> None:
    """MEASURED, not assumed. The pipeline hands cleaner and reader the same DPI,
    so the composition is the identity there — but only because this holds, and
    it is the premise every other test in this file rests on.
    """
    planted = plant(skew_degrees=3.0, dpi=300)
    assert planted.cleaned.artifact is not None
    cleaned_height, cleaned_width = planted.cleaned.cleaned.shape[:2]

    ocr = rendered_at(planted.cleaned.artifact.payload, dpi=planted.dpi)

    assert (ocr.shape[0], ocr.shape[1]) == (cleaned_height, cleaned_width)


def test_a_reader_rendering_at_a_different_dpi_composes_instead_of_assuming(
    a_recogniser_that_finds_the_mark: _MarkFinder,
) -> None:
    """`M_ocr->source = M_cleaned->source @ M_ocr->cleaned`, and the second factor
    is NOT the identity when the two resolutions differ.

    150 and 300 dpi coordinates are not interchangeable: the same cleaned page
    re-rendered at twice the resolution is twice as many pixels, so a reader
    that skipped the composition would land at twice the offset. Asserted
    against the SAME source truth as the equal-DPI case, so the composition is
    judged by where the mark ends up rather than by its own arithmetic.
    """
    planted = plant(skew_degrees=3.0, dpi=150)
    doubled = 2 * planted.dpi

    reading = read_the_cleaned_scan(
        planted,
        mapping=a_map_for(planted, raster_dpi=doubled),
        render_dpi=doubled,
    )

    raster = a_recogniser_that_finds_the_mark.rasters[0]
    cleaned_height, cleaned_width = planted.cleaned.cleaned.shape[:2]
    assert (raster.shape[0], raster.shape[1]) == (2 * cleaned_height, 2 * cleaned_width), (
        "the recogniser was not actually shown a raster at the other resolution"
    )

    error = math.dist(centre_of(reading.regions[0].location), planted.source_mark)
    assert error <= ROUND_TRIP_TOLERANCE_PIXELS, (
        f"the composed map put the mark {error:.6f} px from where it was on the page as received"
    )


@finds_the_mark
def test_a_cleaned_image_maps_back_with_no_resolution_at_either_end() -> None:
    """THE PATH WHERE NOTHING IS RENDERED, and it must MAP rather than refuse.

    An image arrives already rasterised and leaves as the same pixels, so
    `cleaner` records `render_dpi=None` and `reader` rasterises nothing. Both
    ends agree there is no resolution, the two spaces are one, and the scale is
    1.0 — the only configuration in which `None` on both sides is a statement
    rather than a contradiction.

    It is asserted here because it is the one branch where the resolution
    refusal must NOT fire. A check written slightly too eagerly would refuse
    every image in the system, and every other test in this file is a PDF.
    """
    dpi = 150
    authored = a_page_raster(skew_degrees=3.0, dpi=dpi)
    truth = the_mark_in(authored, expected_side=MARK_SIDE)
    cleaned = cleaner.clean_artifact(
        as_png(authored), cleaner.MediaKind.IMAGE, CLEANER_SETTINGS, render_dpi=dpi
    )
    assert cleaned.artifact is not None
    assert cleaned.geometry_of(1).render_dpi is None, (
        "the cleaner claimed a render resolution for pixels it never rendered"
    )
    height, width = cleaned.cleaned.shape[:2]

    reading = reader.read(
        cleaned.artifact.payload,
        media_type=reader.MediaType.IMAGE,
        render_dpi=dpi,
        vision_fallback_threshold=NO_FALLBACK,
        mapping=reader.SourceMapping(
            pages=(
                reader.CleanedPage(
                    page_index=0,
                    height=int(height),
                    width=int(width),
                    geometry=cleaned.geometry_of(1),
                ),
            ),
            raster_dpi=None,
            contract_version=reader.COORDINATE_CONTRACT_VERSION,
        ),
    )

    location = reading.regions[0].location
    assert location.space is reader.CoordinateSpace.SOURCE_RASTER_PIXELS
    error = math.dist(centre_of(location), truth)
    assert error <= ROUND_TRIP_TOLERANCE_PIXELS, (
        f"the mark came back {error:.6f} px from where it was in the image as "
        f"received, against a {ROUND_TRIP_TOLERANCE_PIXELS} px bound"
    )


# ── 4. FAIL CLOSED: a map that cannot be honoured is refused ──────────────


@finds_the_mark
def test_a_missing_transform_refuses_rather_than_answering_in_cleaned_pixels() -> None:
    """THE MOST IMPORTANT ASSERTION IN THIS FILE. Silent-wrong is the bug.

    A caller who asked for source coordinates and got cleaned ones back has no
    way to discover it. So a map that does not cover every page read is refused
    outright — not degraded to the unmapped answer, which would be the same
    silent failure wearing a fix's name.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    empty = reader.SourceMapping(
        pages=(),
        raster_dpi=planted.dpi,
        contract_version=reader.COORDINATE_CONTRACT_VERSION,
    )

    with pytest.raises(reader.CoordinateContractError, match="1 page"):
        read_the_cleaned_scan(planted, mapping=empty)


@finds_the_mark
def test_wrong_page_dimensions_are_refused() -> None:
    """A map for a DIFFERENT raster is the failure mode a coordinate cannot survive.

    The bound is one pixel and it is derived, not chosen: the rasteriser encloses
    the scaled page in WHOLE pixels, so the raster is at most one pixel larger
    than the page it represents in each axis (`KNOWN_FAILURES.md` F-031). Two
    pixels is a different page.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)
    page = honest.pages[0]
    lying = reader.SourceMapping(
        pages=(
            reader.CleanedPage(
                page_index=page.page_index,
                height=page.height + 5,
                width=page.width + 5,
                geometry=page.geometry,
            ),
        ),
        raster_dpi=honest.raster_dpi,
        contract_version=honest.contract_version,
    )

    with pytest.raises(reader.CoordinateContractError, match="pixel"):
        read_the_cleaned_scan(planted, mapping=lying)


@finds_the_mark
def test_a_map_written_against_another_contract_version_is_refused() -> None:
    """A version nobody checks is a version that does nothing.

    The field has NO default on purpose. A default would let a producer written
    against a future contract be read as the current one, which is precisely the
    case a version exists to catch.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)
    stale = reader.SourceMapping(
        pages=honest.pages,
        raster_dpi=honest.raster_dpi,
        contract_version=reader.COORDINATE_CONTRACT_VERSION + 1,
    )

    with pytest.raises(reader.CoordinateContractError, match="contract"):
        read_the_cleaned_scan(planted, mapping=stale)


@finds_the_mark
def test_a_page_index_that_does_not_match_its_geometry_is_refused() -> None:
    """0-based here, 1-based in the geometry — and page one's map on page three's
    coordinates is another page's answer, not an approximation.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)
    page = honest.pages[0]
    misnumbered = reader.SourceMapping(
        pages=(
            reader.CleanedPage(
                page_index=3,
                height=page.height,
                width=page.width,
                geometry=page.geometry,
            ),
        ),
        raster_dpi=honest.raster_dpi,
        contract_version=honest.contract_version,
    )

    with pytest.raises(reader.CoordinateContractError, match="Pages are mapped in the order"):
        read_the_cleaned_scan(planted, mapping=misnumbered)


@finds_the_mark
def test_a_geometry_for_another_page_is_refused_even_when_its_own_index_is_right() -> None:
    """THE OTHER HALF OF THE PAGE CHECK, and it had no test until a mutation ran.

    The test above puts the WRONG index on the entry, which the ordering check
    catches before the geometry is ever consulted. So deleting the 0-based
    versus 1-based cross-check entirely left the whole suite green — measured,
    not suspected. Here the entry sits in the right place and carries page
    three's geometry, which is the shape a real off-by-one produces.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)
    page = honest.pages[0]
    from_another_page = reader.SourceMapping(
        pages=(
            reader.CleanedPage(
                page_index=0,
                height=page.height,
                width=page.width,
                geometry=_ForAnotherPage(page.geometry, page=3),
            ),
        ),
        raster_dpi=honest.raster_dpi,
        contract_version=honest.contract_version,
    )

    with pytest.raises(reader.CoordinateContractError, match="carries a geometry for page 3"):
        read_the_cleaned_scan(planted, mapping=from_another_page)


@finds_the_mark
def test_a_map_whose_resolution_is_absent_while_the_reader_rendered_one_is_refused() -> None:
    """The UNIT mismatch. `render_dpi is None` on the geometry means *these pixels
    were never rendered from a page and are already the document's own space*;
    the reader having rasterised a PDF says the opposite. One of the two is
    wrong about what the numbers measure, and neither can be silently preferred.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)
    page = honest.pages[0]
    unrendered = reader.SourceMapping(
        pages=(
            reader.CleanedPage(
                page_index=page.page_index,
                height=page.height,
                width=page.width,
                geometry=_WithoutAResolution(page.geometry),
            ),
        ),
        raster_dpi=honest.raster_dpi,
        contract_version=honest.contract_version,
    )

    with pytest.raises(reader.CoordinateContractError, match="resolution"):
        read_the_cleaned_scan(planted, mapping=unrendered)


@finds_the_mark
def test_a_map_that_states_a_resolution_the_reader_did_not_render_at_is_refused() -> None:
    """The caller says the raster is 300 dpi; the reader rendered 150. Two
    different pages, and a scale silently wrong by 2x.

    THE PATTERN IS NARROW ON PURPOSE. It was `"rasteris"`, which the raster-size
    message ALSO contains — so deleting the check under test left this green,
    passing on a refusal that came from somewhere else entirely. Measured by
    mutation, not noticed by reading.
    """
    planted = plant(skew_degrees=0.0, dpi=150)

    with pytest.raises(reader.CoordinateContractError, match="this module rasterised at 150"):
        read_the_cleaned_scan(
            planted,
            mapping=a_map_for(planted, raster_dpi=300),
            render_dpi=150,
        )


@finds_the_mark
def test_a_map_claiming_a_resolution_for_an_image_nothing_rendered_is_refused() -> None:
    """AND THE CASE NO OTHER CHECK CAN CATCH, which is why the check exists.

    An image arrives already rasterised, so `reader` renders nothing and its
    pixels have no resolution. Hand it the cleaned raster as a PNG with a map
    that claims both ends were at the same DPI, and every other check agrees:
    the scale is 1.0, the extents match to the pixel, the page numbers line up.
    Only the reader knowing what IT did tells the two apart — and without that,
    the region comes back labelled as the document as received, which is a claim
    about a page nothing ever rendered.
    """
    planted = plant(skew_degrees=0.0, dpi=150)
    honest = a_map_for(planted)

    with pytest.raises(reader.CoordinateContractError, match="this module rasterised at None"):
        reader.read(
            as_png(planted.cleaned.cleaned),
            media_type=reader.MediaType.IMAGE,
            render_dpi=planted.dpi,
            vision_fallback_threshold=NO_FALLBACK,
            mapping=honest,
        )


def test_a_map_supplied_for_a_document_read_from_its_text_layer_is_refused() -> None:
    """A text-layer PDF passes through the cleaner untouched, so it HAS no map.

    A caller supplying one is stating something the cleaner never said. Returning
    the text-layer reading anyway would answer in points on the page while the
    caller believes it holds source-raster pixels — the same class of silent
    substitution `_vision_fallback` refuses for the same reason.
    """
    built = a_text_layer_pdf("TAX INVOICE")
    planted = plant(skew_degrees=0.0, dpi=150)

    with pytest.raises(reader.CoordinateContractError, match="text layer"):
        reader.read(
            built,
            media_type=reader.MediaType.PDF,
            render_dpi=planted.dpi,
            vision_fallback_threshold=NO_FALLBACK,
            mapping=a_map_for(planted),
        )


def test_a_contract_failure_is_a_reader_error_and_not_a_verdict_on_the_document() -> None:
    """It is OUR wiring that is inconsistent, never the user's file.

    `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids asserting something false about
    a document, and `pipeline.BUSINESS_FAILURE` decides by `isinstance` which
    reader failures cross the boundary as a verdict about the document. This type
    is deliberately not among them, for the same reason `RecognitionFailedError`
    is not.
    """
    assert issubclass(reader.CoordinateContractError, reader.ReaderError)
    assert not issubclass(reader.CoordinateContractError, reader.UnreadableDocumentError)


@dataclass(frozen=True, slots=True)
class _WithoutAResolution:
    """A geometry that reports no render resolution, as an image's cleaning does.

    Typed against `reader`'s own Protocol rather than `cleaner.SourceGeometry`,
    which is the point being demonstrated: the reader names the surface it
    needs, and anything satisfying it — the real cleaner, or this — goes in.
    """

    wrapped: reader.CleanedPageGeometry

    @property
    def source_height(self) -> int:
        return self.wrapped.source_height

    @property
    def source_width(self) -> int:
        return self.wrapped.source_width

    @property
    def render_dpi(self) -> int | None:
        return None

    @property
    def page(self) -> int:
        return self.wrapped.page

    def source_pixel(self, x: float, y: float) -> tuple[float, float]:
        return self.wrapped.source_pixel(x, y)


@dataclass(frozen=True, slots=True)
class _ForAnotherPage:
    """A geometry that describes a DIFFERENT page from the one it is filed under."""

    wrapped: reader.CleanedPageGeometry
    page: int

    @property
    def source_height(self) -> int:
        return self.wrapped.source_height

    @property
    def source_width(self) -> int:
        return self.wrapped.source_width

    @property
    def render_dpi(self) -> int | None:
        return self.wrapped.render_dpi

    def source_pixel(self, x: float, y: float) -> tuple[float, float]:
        return self.wrapped.source_pixel(x, y)
