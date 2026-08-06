"""The `cleaner` sub-engine, attacked for the one thing it can never undo.

WHY THIS FILE EXISTS SEPARATELY FROM `test_input_engine_cleaner.py`. That file
proves the cleaner DOES what it says: it deskews, it denoises, it raises
contrast, it keeps the ink. This file asks the opposite question and only the
opposite question — **what did the cleaner DESTROY?** — because a cleaner is the
one stage in Engine 1 whose mistakes are unrecoverable. `reader` can misread a
character and `parser` can miss a field, and in both cases the evidence is still
on the page for the next attempt. A pixel the cleaner removed is gone, the
output looks immaculate, and every engine downstream reasons confidently from
the damage. `ENGINE_1:450` — cleaner *"cannot remove important evidence"* — and
`ENGINE_1:457` — *"if processing may damage information: preserve the original
input and mark uncertainty."* Those two lines are what this file tries to break.

THE ORACLE IS DELIBERATELY NOT THE MODULE'S OWN. `cleaner` decides what "ink"
is with Otsu's threshold, and every guarantee it states about the crop is stated
in terms of that same threshold. Measuring the crop with Otsu therefore proves
nothing: it checks the box against the rule that drew the box. So this file
measures CONTENT instead — any pixel meaningfully darker than the page's modal
intensity, which is the paper. The paper mode is computed from a histogram peak,
never from a threshold, so it agrees with a human squinting at the page and it
does not agree with Otsu by construction. That single change of oracle is what
makes the first defect below visible at all.

EIGHT TESTS IN THIS FILE WERE RED, AND WERE SUPPOSED TO BE. ALL ARE NOW GREEN.
    Two per defect, because each defect destroys something AND misreports it,
    and those are separate failures with separate fixes. They were not
    aspirational, not future work and not a style preference. Each one names a
    measured quantity of real document content that this module destroyed or
    failed to report, and each failed for exactly that reason. They were written
    before any fix and left visible on purpose: `CLAUDE.md` Law 3 (every
    discovered bug gets a permanent regression test BEFORE the fix is complete)
    and Law 12 (never ignore unexpected behaviour). A quiet patch would have
    hidden four defects behind one commit; a red test put each one in front of
    whoever owned `cleaner.py`.

    THE FOUR DEFECTS ARE FIXED AND NO TEST HERE IS EXPECTED TO FAIL ANY MORE.
    That sentence is the reason this paragraph was rewritten rather than left
    standing: a file whose header says its reds are expected is a file where a
    REAL red gets waved through, which is Law 12 failing by way of a stale
    comment. Every test below is green, and a red one now means a regression.

    Each attack was kept pointed at the defect rather than retired with it, and
    where a fix made the original attack unconstructible the test was rewritten
    to hold BOTH halves — the damage must not recur, AND the figure that would
    report the damage must remain able to report it. See D1 below: a crop that
    keeps the GSTIN and a retention figure hardwired to 1.0 look identical from
    the GSTIN page alone, so that page alone can no longer be the whole test.

    D1  the crop discards every mark Otsu does not call ink. A faint GSTIN line
        at the foot of an invoice — 4080 pixels, 30 grey levels darker than the
        paper, plainly readable — leaves the page entirely, and the module
        reports `ink_kept_by_crop = 1.0` and `the cleaned representation is the
        safer basis for reading`, with RMS contrast up from 57.66 to 90.92 as
        though the page had been improved.

    D2  `ink_lost_to_denoise` is a NET DIFFERENCE OF TWO COUNTS, not the ink
        that was lost. Where denoising erases strokes in one place and pushes
        other pixels across the split in another, the reported figure goes
        NEGATIVE while ink is being destroyed: measured -0.014868 while 1094
        ink pixels (0.005628 of the ink) were erased and a decimal point was
        wiped out — at `max_ink_loss_fraction = 0.0`, the strictest value the
        setting accepts.

    D3  a multi-page scanned PDF reports PAGE ONE ONLY. The same two pages in
        the opposite order produce the opposite preservation status, which
        proves the reported status is a property of page order rather than of
        the document. Every page after the first contributes no evidence at all.

    D4  `_to_grey` discards the alpha channel, so a document whose visible
        content lives in alpha flattens to a single grey. Two RGBA pages with
        entirely different content clean to byte-identical output, and every
        measurement reports zero loss.

EVERY NUMBER BELOW WAS MEASURED BY RUNNING IT. None is a threshold the product
uses — `cleaner` has no default anywhere — and none was chosen because it looked
reasonable. Where a bound is inexact it sits strictly inside the value this
suite actually produced, and the measured value is named beside it.
"""

from __future__ import annotations

import importlib
import math

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from accountant_dad.engines.input_engine import cleaner

Image = npt.NDArray[np.uint8]

# ── the fixtures' own constants, not the product's ────────────────────────

PAPER = 235
INK = 30
#: A faint carbon-copy total: 21 grey levels below the paper. Readable.
FAINT_TOTAL = 214
#: A faint printed GSTIN line: 30 grey levels below the paper. Readable.
FAINT_GSTIN = 205
PAGE_HEIGHT = 600
PAGE_WIDTH = 900

#: A pixel this far below the paper's modal intensity is content, not paper.
#: Six levels, because the synthetic pages here carry no gradient at all and the
#: faintest mark any of them uses sits 21 levels down.
CONTENT_TOLERANCE = 6
#: The band the faint marks occupy. Wide enough to survive denoising's smoothing
#: and far enough from both 235 and 30 that neither the paper nor the print can
#: land in it.
FAINT_BAND_LOW = 190
FAINT_BAND_HIGH = 228

#: An inverted scan: a dark field carrying light writing. Halfway between the
#: two is where "is this a stroke" is decided, and it is nowhere near either.
INVERTED_FIELD = 15
INVERTED_STROKE = 245
MID_GREY = 128

RNG_SEED = 11
INJECTED_SIGMA = 14.0

# ── the settings every test supplies in full ──────────────────────────────
# `CleanerSettings` has no default for any field. Supplying all eight, every
# time, is the point: no number reaches OpenCV that a caller did not choose.

BASELINE = cleaner.CleanerSettings(
    max_deskew_degrees=15.0,
    denoise_strength=6.0,
    denoise_template_window=7,
    denoise_search_window=21,
    contrast_clip_limit=2.0,
    contrast_tile_grid=8,
    crop_margin_pixels=4,
    max_ink_loss_fraction=0.05,
)

#: A strength that visibly erases isolated marks. An input, never a threshold.
ERASING_DENOISE_STRENGTH = 40.0
#: The strictest value the setting accepts: no ink loss is tolerable at all.
NO_INK_LOSS_TOLERATED = 0.0
#: The skew this file injects, in degrees.
INJECTED_SKEW_DEGREES = 7.0
FULL_RETENTION = 1.0
#: Rasterisation resolution for the PDF attacks. The caller's, with no default.
RENDER_DPI = 100

# ── measured bounds ───────────────────────────────────────────────────────

#: Measured: 12480 white stroke pixels in, 12448 out, at strength 40.0.
MIN_INVERTED_STROKE_RETENTION = 0.99
#: Measured: 62262 of 64080 content pixels survive a real 7 degree correction,
#: the shortfall being resampling at the stroke edges, not clipping.
MIN_ROTATED_CONTENT_RETENTION = 0.95
#: Measured: a solid ink frame turned 7 degrees onto the grown canvas keeps
#: 538597 of 540000 dark pixels, 0.99740. The shortfall is the interpolation
#: ramp along the new edge; a clipped corner would cost whole percent.
MIN_ROTATED_INK_RETENTION = 0.995
#: Measured: the faint GSTIN is 4080 pixels; the faint total is 1680.
FAINT_GSTIN_PIXELS = 4080
FAINT_TOTAL_PIXELS = 1680
#: Measured: the faint-GSTIN page carries 50880 content pixels, and the same
#: 50880 come through the cleaning. Nothing is discarded.
GSTIN_PAGE_CONTENT_PIXELS = 50880
#: `a_printed_body` paints six 10-row bands across 780 columns.
PRINTED_BODY_INK_PIXELS = 6 * 10 * (PAGE_WIDTH - 120)
#: A margin initial, three pixels square, 480 rows below the printed body.
CORNER_MARK_SIDE = 3
CORNER_MARK_ROW = 560
CORNER_MARK_COLUMN = 860
CORNER_MARK_PIXELS = CORNER_MARK_SIDE * CORNER_MARK_SIDE
#: Measured: a crop keeping the body AND the mark spans rows 76..566, so any
#: page delivered shorter than this cannot still be carrying the mark.
HEIGHT_THAT_HOLDS_BODY_AND_MARK = 491
#: Measured: a decimal point of 4 ink pixels, and 1094 ink pixels erased in all.
TRUE_ERASED_FRACTION = 0.005
#: Measured: 3 separate marks on the edge page, before and after.
MARKS_ON_THE_EDGE_PAGE = 3
#: Measured: the hairline page carries 22620 pixels at or below Otsu's split.
HAIRLINE_INK_PIXELS = 22620
#: Measured: 4520 content pixels on the edge page, all three marks intact.
EDGE_PAGE_CONTENT_PIXELS = 4520

# ── the page that is destroyed outright, for the fraction invariant ───────

#: A strength that removes the hairline rules ENTIRELY rather than thinning
#: them. `ERASING_DENOISE_STRENGTH` above is the weaker attack that erases
#: isolated marks; this one leaves nothing. An input, never a threshold.
ANNIHILATING_DENOISE_STRENGTH = 60.0
#: Mid-scale, so it sits far below the paper at 235 and far above anything a
#: smoothed page produces. Only real marks are this dark, and unlike Otsu it is
#: a FIXED intensity, so it cannot move with the content of the page.
DARK_MARK = 128
#: Measured: the hairline page carries 22620 pixels at or below `DARK_MARK`, and
#: at strength 60.0 it delivers 0 of them. Numerically equal to
#: `HAIRLINE_INK_PIXELS` and kept separate anyway: the two are arrived at by
#: different rules and only coincide because every rule on this page is painted
#: at intensity 20, far below both. A page where they diverged would need two
#: names, and a constant shared for today's arithmetic is a constant that hides
#: tomorrow's disagreement.
HAIRLINE_DARK_PIXELS = 22620


def settings(**changes: float | int) -> cleaner.CleanerSettings:
    """The baseline with named fields replaced, so one attack changes one thing."""
    fields: dict[str, float | int] = {
        "max_deskew_degrees": BASELINE.max_deskew_degrees,
        "denoise_strength": BASELINE.denoise_strength,
        "denoise_template_window": BASELINE.denoise_template_window,
        "denoise_search_window": BASELINE.denoise_search_window,
        "contrast_clip_limit": BASELINE.contrast_clip_limit,
        "contrast_tile_grid": BASELINE.contrast_tile_grid,
        "crop_margin_pixels": BASELINE.crop_margin_pixels,
        "max_ink_loss_fraction": BASELINE.max_ink_loss_fraction,
    }
    fields.update(changes)
    return cleaner.CleanerSettings(
        max_deskew_degrees=float(fields["max_deskew_degrees"]),
        denoise_strength=float(fields["denoise_strength"]),
        denoise_template_window=int(fields["denoise_template_window"]),
        denoise_search_window=int(fields["denoise_search_window"]),
        contrast_clip_limit=float(fields["contrast_clip_limit"]),
        contrast_tile_grid=int(fields["contrast_tile_grid"]),
        crop_margin_pixels=int(fields["crop_margin_pixels"]),
        max_ink_loss_fraction=float(fields["max_ink_loss_fraction"]),
    )


# ── oracles the module under test does not use ────────────────────────────


def paper_mode(image: Image) -> int:
    """The paper's intensity, from the histogram's peak rather than a threshold.

    `cleaner` decides what is paper with Otsu, and Otsu's split moves with the
    content of the page — on an invoice of black print plus a light-grey line it
    lands at 30.0, so a plainly readable grey mark is classified as paper. The
    mode does not move: whatever covers most of a document is the paper. Two
    different routes to the same physical quantity, which is the only defence
    against a bug shared by the code and its test (§J.(b)).
    """
    return int(np.bincount(image.ravel()).argmax())


def content_pixels(image: Image, tolerance: int = CONTENT_TOLERANCE) -> int:
    """Every pixel a human would see as a mark on the paper. No Otsu anywhere."""
    return int(np.count_nonzero(image.astype(np.int16) < paper_mode(image) - tolerance))


def pixels_in_band(image: Image, low: int, high: int) -> int:
    """Pixels inside an intensity band, so a faint mark can be counted alone."""
    return int(np.count_nonzero((image >= low) & (image <= high)))


def separate_marks(image: Image, tolerance: int = CONTENT_TOLERANCE) -> int:
    """How many disconnected marks the page carries.

    A structural measure, not a photometric one: it survives resampling and
    re-encoding, and it goes down the moment a whole mark is removed. That makes
    it the right oracle for "did the corner stamp leave the page", which a pixel
    count alone could hide behind a change of shape.
    """
    mark: Image = np.asarray(
        (image.astype(np.int16) < paper_mode(image) - tolerance).astype(np.uint8) * 255,
        dtype=np.uint8,
    )
    found, _labels = cv2.connectedComponents(mark)
    return int(found) - 1


def ink_erased_between(before: Image, after: Image, threshold: float) -> int:
    """Pixels that WERE ink and are no longer. The set difference, not a net.

    This is the honest form of the quantity `cleaner` reports as
    `ink_lost_to_denoise`. The module subtracts one count from another, which
    lets ink gained in one region cancel ink destroyed in another; this counts
    only destruction, so the two disagree exactly when destruction is being
    masked.
    """
    was = before.astype(np.float64) <= threshold
    still = after.astype(np.float64) <= threshold
    return int(np.count_nonzero(was & ~still))


# ── the pages the attacks are made of ─────────────────────────────────────


def a_printed_body(height: int = PAGE_HEIGHT, width: int = PAGE_WIDTH) -> Image:
    """Black print in the upper half, leaving a foot the crop can reach into."""
    sheet: Image = np.full((height, width), PAPER, dtype=np.uint8)
    for row in range(80, 300, 40):
        sheet[row : row + 10, 60 : width - 60] = INK
    return sheet


def a_page_with_a_faint_gstin() -> Image:
    """An invoice whose registration number is printed faintly at the foot.

    This is not a contrived input. A GSTIN reproduced by a worn ribbon, a carbon
    copy, a low-toner laser or a second-generation photocopy lands exactly here:
    clearly visible, and nowhere near as dark as the body print.
    """
    sheet = a_printed_body()
    sheet[560:572, 60:400] = FAINT_GSTIN
    return sheet


def scanned(sheet: Image) -> Image:
    """The same page as it comes off a scanner: seeded Gaussian sensor noise.

    The noise is not decoration. `_lines_with_content` scales its allowance by
    the page's noise, so on a NOISELESS page the allowance is zero and every
    mark, however small, moves its line's mean past it. Sensor noise is what
    gives the line profile a detection floor at all — and a floor is what lets
    a mark be small enough to fall through the box while still being ink.
    """
    rng = np.random.default_rng(RNG_SEED)
    noisy = sheet.astype(np.int16) + rng.normal(0, INJECTED_SIGMA, sheet.shape)
    return np.asarray(np.clip(noisy, 0, 255), dtype=np.uint8)


def a_scan_of_a_printed_body() -> Image:
    """The CONTROL for the corner-mark page: identical, with nothing in the margin."""
    return scanned(a_printed_body())


def a_scan_with_an_isolated_corner_mark() -> Image:
    """A scanned invoice initialled in the margin, far below the printed body.

    A tick, a set of initials, a "PAID" stamp or a hand-written cheque number in
    the bottom corner of an invoice is ordinary, and it is exactly the thing a
    crop tightened around the printed body will throw away. Three pixels square
    displaces its row's mean by 0.683 grey levels against the line profile's
    3.338 allowance at this noise, so the box cannot see it; Otsu splits the
    page at 85.0 and counts all nine of its pixels as ink. That gap between the
    two rules is the whole reason `ink_kept_by_crop` is able to say anything.
    """
    sheet = a_printed_body()
    sheet[
        CORNER_MARK_ROW : CORNER_MARK_ROW + CORNER_MARK_SIDE,
        CORNER_MARK_COLUMN : CORNER_MARK_COLUMN + CORNER_MARK_SIDE,
    ] = INK
    return scanned(sheet)


def a_shaded_invoice() -> Image:
    """Body print, a shaded panel, an isolated decimal point, and sensor noise.

    The shaded panel is what makes the attack work: denoising pulls it toward
    its own mean and a mass of its pixels crosses the split INTO ink, while the
    decimal point is smoothed out of existence. A net count cannot see both.
    """
    rng = np.random.default_rng(RNG_SEED)
    page: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    for row in range(80, 520, 40):
        page[row : row + 10, 60:500] = INK
    page[60:560, 560:860] = 150
    page[300:302, 520:522] = INK
    blurred = page.astype(np.int16) + rng.normal(0, INJECTED_SIGMA, page.shape)
    return np.asarray(np.clip(blurred, 0, 255), dtype=np.uint8)


def a_thickly_printed_page() -> Image:
    """Twenty-pixel strokes. Nothing a denoise at strength 40 can erase."""
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    for row in range(80, 520, 40):
        sheet[row : row + 20, 60 : PAGE_WIDTH - 60] = INK
    return sheet


def a_hairline_page() -> Image:
    """One-pixel rules. Exactly what a strong denoise destroys."""
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    for row in range(60, PAGE_HEIGHT - 60, 17):
        sheet[row : row + 1, 60 : PAGE_WIDTH - 60] = INK
    return sheet


def a_scanned_pdf(pages: list[Image]) -> bytes:
    """Pages with no text layer, so `cleaner` takes the rasterising branch."""
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        for page in pages:
            ok, buffer = cv2.imencode(".png", page)
            assert ok
            image_document = fitz.open(stream=buffer.tobytes(), filetype="png")
            try:
                as_pdf = fitz.open("pdf", image_document.convert_to_pdf())
                try:
                    document.insert_pdf(as_pdf)
                finally:
                    as_pdf.close()
            finally:
                image_document.close()
        return bytes(document.tobytes())
    finally:
        document.close()


def an_alpha_carried_mark() -> Image:
    """A stamp exported with a transparent background.

    The colour channels are zero everywhere — which is what every background
    remover, every premultiplied export and every `convert -transparent` leaves
    behind — and the shape of the mark exists only in the alpha channel.
    """
    page: Image = np.zeros((400, 600, 4), dtype=np.uint8)
    alpha: Image = np.zeros((400, 600), dtype=np.uint8)
    for row in range(60, 340, 40):
        alpha[row : row + 12, 60:540] = 255
    page[..., 3] = alpha
    return page


def a_fully_transparent_page() -> Image:
    """The same canvas carrying nothing at all. Zero alpha, zero colour."""
    return np.zeros((400, 600, 4), dtype=np.uint8)


# ── the oracles are checked before anything is asserted with them ─────────


def test_the_paper_mode_oracle_disagrees_with_otsu_on_a_faintly_printed_page() -> None:
    """Calibration, and the reason this file exists.

    If the mode oracle agreed with Otsu, every measurement below would be the
    module marking its own work. On the faint-GSTIN page they disagree by 175
    grey levels, and the faint mark falls on opposite sides of the two.
    """
    page = a_page_with_a_faint_gstin()
    _mask, otsu_split = cleaner._ink_mask(page)

    assert paper_mode(page) == PAPER
    assert otsu_split == float(INK)
    # The mark is content to the oracle and paper to the module.
    assert paper_mode(page) - CONTENT_TOLERANCE > FAINT_GSTIN
    assert otsu_split < FAINT_GSTIN


def test_the_separate_marks_oracle_counts_what_is_actually_on_the_page() -> None:
    """Three disconnected blocks must read as three, not as one and not as four."""
    page: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    page[0:8, 0:220] = INK
    page[592:600, 680:900] = INK
    page[300:310, 400:500] = INK

    assert separate_marks(page) == MARKS_ON_THE_EDGE_PAGE


# ══ PART ONE — attacks the cleaner SURVIVES ═══════════════════════════════
# Each of these is a genuine attempt to make the module lose content. It did
# not, and the number that proves it is asserted so a future change cannot
# quietly start losing what these inputs currently keep.


def test_a_gstin_flush_to_the_frame_edge_and_a_corner_stamp_both_stay_on_the_page() -> None:
    """Content with no margin at all: row zero, column zero, and the far corner.

    A crop that trimmed by a fixed inset, or a bounding box computed before the
    edge pixels were considered, would take one of these and leave a page that
    still looks like a complete invoice.
    """
    page: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    page[0:8, 0:220] = INK  # a GSTIN printed hard against the top-left corner
    page[592:600, 680:900] = INK  # a stamp in the bottom-right corner
    page[300:310, 400:500] = INK  # and a body stroke, so the box is not trivial

    assert content_pixels(page) == EDGE_PAGE_CONTENT_PIXELS

    result = cleaner._clean_image(page, settings())

    assert content_pixels(result.cleaned) == EDGE_PAGE_CONTENT_PIXELS
    assert separate_marks(result.cleaned) == MARKS_ON_THE_EDGE_PAGE
    assert result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED).value == FULL_RETENTION


def test_a_real_deskew_of_a_page_whose_ink_reaches_every_edge_clips_nothing() -> None:
    """Rotation is the step that can throw content out of the frame.

    The page is turned before cleaning so the correction is genuinely applied,
    and the ink runs to all four edges so any canvas that failed to grow would
    cut it. Retention is asserted against a measured floor rather than exact
    equality because rotation resamples: measured 62262 of 64080 content pixels,
    0.9716, and the shortfall is the ramp at each stroke edge, not clipping.
    """
    straight = a_printed_body()
    straight[400:410, 0:PAGE_WIDTH] = INK
    turned: Image = np.asarray(
        cv2.warpAffine(
            straight,
            cv2.getRotationMatrix2D((PAGE_WIDTH / 2.0, PAGE_HEIGHT / 2.0), 0.0, 1.0),
            (PAGE_WIDTH, PAGE_HEIGHT),
            borderMode=cv2.BORDER_REPLICATE,
        ),
        dtype=np.uint8,
    )
    padded: Image = np.asarray(
        cv2.copyMakeBorder(turned, 200, 200, 200, 200, cv2.BORDER_REPLICATE), dtype=np.uint8
    )
    skewed: Image = np.asarray(
        cv2.warpAffine(
            padded,
            cv2.getRotationMatrix2D(
                (padded.shape[1] / 2.0, padded.shape[0] / 2.0), INJECTED_SKEW_DEGREES, 1.0
            ),
            (padded.shape[1], padded.shape[0]),
            borderMode=cv2.BORDER_REPLICATE,
        ),
        dtype=np.uint8,
    )

    result = cleaner._clean_image(skewed, settings())

    applied = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value
    assert applied is not None
    assert applied != 0.0, "the attack is void unless a rotation was actually applied"
    retained = content_pixels(result.cleaned) / content_pixels(skewed)
    assert retained >= MIN_ROTATED_CONTENT_RETENTION


def test_the_rotation_canvas_is_the_exact_bounding_box_of_the_turned_corners() -> None:
    """The claim that rotation *"cannot lose a pixel"*, checked by arithmetic.

    `clean` reports a residual skew of a fraction of a degree whether or not the
    canvas grew, because the ink of an ordinary page sits well inside the frame
    and clipping its corners changes the principal axis very little. So the
    end-to-end test above cannot see this failure and a direct one is needed.

    The oracle is trigonometry the module does not share: a frame of h by w
    turned through t occupies exactly ceil(h*sin+w*cos) by ceil(h*cos+w*sin).
    A rotation left on the original canvas would keep h by w, which is smaller
    for every angle that is not a multiple of a quarter turn — and everything
    outside it has been cut off the document.
    """
    page: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    page[0:PAGE_HEIGHT, 0:PAGE_WIDTH] = INK  # ink to all four corners

    for degrees in (INJECTED_SKEW_DEGREES, 30.0, 44.0):
        turned = cleaner._rotate_whole_frame(page, degrees, float(PAPER))
        radians = math.radians(degrees)
        expected_width = math.ceil(
            PAGE_HEIGHT * abs(math.sin(radians)) + PAGE_WIDTH * abs(math.cos(radians))
        )
        expected_height = math.ceil(
            PAGE_HEIGHT * abs(math.cos(radians)) + PAGE_WIDTH * abs(math.sin(radians))
        )
        assert turned.shape == (expected_height, expected_width)
        assert expected_height > PAGE_HEIGHT
        assert expected_width > PAGE_WIDTH
        # And what left the frame is only the interpolation ramp along the edge
        # where ink now meets the fill, never a clipped corner. Counted directly
        # against the ink's own intensity rather than with the paper-mode
        # oracle, because on a page that is entirely ink the modal intensity IS
        # the ink and the oracle would call a solid black page empty.
        # Measured at 7 degrees: 538597 of 540000, a retention of 0.99740.
        dark = int(np.count_nonzero(turned <= INK + CONTENT_TOLERANCE))
        assert dark / (PAGE_HEIGHT * PAGE_WIDTH) >= MIN_ROTATED_INK_RETENTION


def test_a_deskewed_page_is_left_tight_around_its_content_and_not_around_the_fill() -> None:
    """Rotation grows the canvas and fills the new corners. Something must take
    that fill back off, and this asserts that something does.

    The fill is a flat grey painted into the frame by the module. It is not on
    the document, and a cleaned page delivered with a 99-pixel band of it around
    the edge hands `reader` a border that was never there — the geometry of a
    scan is evidence too, and a margin the printer did not print is fabricated
    evidence (Law 24).

    MEASURED on a page turned 7 degrees, `crop_margin_pixels = 4`:
        with the second crop     content inset  4, 4, 4, 4      page 418 x 788
        without the second crop  content inset 99, 54, 54, 99   page 608 x 888

    The inset is asserted against the caller's own margin, so it is exact and
    it comes from the setting rather than from a number chosen here.
    """
    plain = a_printed_body()
    for row in range(300, 520, 40):
        plain[row : row + 10, 60 : PAGE_WIDTH - 60] = INK
    bordered: Image = np.asarray(
        cv2.copyMakeBorder(plain, 200, 200, 200, 200, cv2.BORDER_CONSTANT, value=PAPER),
        dtype=np.uint8,
    )
    height, width = bordered.shape
    skewed: Image = np.asarray(
        cv2.warpAffine(
            bordered,
            cv2.getRotationMatrix2D((width / 2.0, height / 2.0), INJECTED_SKEW_DEGREES, 1.0),
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=PAPER,
        ),
        dtype=np.uint8,
    )

    result = cleaner._clean_image(skewed, settings())

    applied = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value
    assert applied is not None
    assert applied != 0.0, "the attack is void unless a rotation was actually applied"

    margin = BASELINE.crop_margin_pixels
    marked: Image = np.asarray(
        (result.cleaned.astype(np.int16) < paper_mode(result.cleaned) - CONTENT_TOLERANCE).astype(
            np.uint8
        ),
        dtype=np.uint8,
    )
    left, top, box_width, box_height = cv2.boundingRect(marked)
    rows, columns = result.cleaned.shape
    insets = (top, left, rows - (top + box_height), columns - (left + box_width))
    # One pixel of slack, and one only: this file's content oracle catches the
    # outermost step of the rotation's interpolation ramp that Otsu's split does
    # not, so the content box is a pixel wider than the box the crop was drawn
    # around. Measured: 3, 3, 3, 3 against a margin of 4.
    for inset in insets:
        assert margin - 1 <= inset <= margin


def test_a_till_receipt_twenty_one_pixels_tall_keeps_its_printed_line() -> None:
    """An extreme aspect ratio, which is what a thermal receipt actually is.

    Every measurement in the module divides by a page dimension or an interior
    area, and a 21 x 3000 strip is the shape that finds an off-by-one in any of
    them.
    """
    strip: Image = np.full((21, 3000), PAPER, dtype=np.uint8)
    strip[8:12, 100:2900] = INK

    result = cleaner._clean_image(strip, settings())

    assert content_pixels(result.cleaned) == content_pixels(strip)


def test_the_smallest_page_the_callers_window_allows_keeps_its_ink() -> None:
    """21 x 21 — exactly `denoise_search_window`. One pixel less is refused."""
    tiny: Image = np.full((21, 21), PAPER, dtype=np.uint8)
    tiny[8:12, 4:17] = INK

    result = cleaner._clean_image(tiny, settings())

    assert content_pixels(result.cleaned) == content_pixels(tiny)


def test_a_page_carrying_exactly_one_ink_pixel_still_carries_it() -> None:
    """The near-empty page. One pixel is the smallest thing a crop can lose."""
    page: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER, dtype=np.uint8)
    page[300, 450] = INK

    result = cleaner._clean_image(page, settings())

    assert content_pixels(result.cleaned) == 1
    assert result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED).value == 0.0


def test_a_hairline_table_rule_survives_the_denoise_strength_it_was_given() -> None:
    """One-pixel rules at the baseline strength: nothing may be removed.

    The note is pinned to a count this file computes itself, at the same split,
    with the boundary INCLUSIVE. That last word is the whole assertion: a page
    whose ink sits exactly on Otsu's split — which is what a two-tone synthetic
    page always produces — reports 22620 ink pixels when the comparison includes
    the split and 0 when it excludes it. A test that only checked the loss was
    zero would read both as correct, because 0 lost out of 0 is still 0.
    """
    page = a_hairline_page()
    _mask, split = cleaner._ink_mask(page)
    ink_at_the_split = int(np.count_nonzero(page.astype(np.float64) <= split))
    assert ink_at_the_split == HAIRLINE_INK_PIXELS

    result = cleaner._clean_image(page, settings())

    assert content_pixels(result.cleaned) == content_pixels(page)
    loss = result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED)
    assert loss.value == 0.0
    assert loss.note.startswith(
        f"{ink_at_the_split} ink pixel(s) before denoising, {ink_at_the_split} after,"
    )


def test_an_inverted_white_on_black_scan_keeps_its_strokes() -> None:
    """The polarity the module's docstring names as an assumption, attacked.

    Ink darker than paper is stated there as an assumption rather than a fact,
    so the question is whether an inverted scan silently loses its writing. It
    does not: measured 12480 white stroke pixels in and 12448 out at strength
    40.0, a retention of 0.99744.

    What the module reports about that page is a different matter, and it is in
    the findings rather than in an assertion here: the ink-loss guard measures
    the black FIELD, not the white writing, so it contributes no evidence about
    the strokes either way.
    """
    inverted: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), INVERTED_FIELD, dtype=np.uint8)
    for row in range(80, 520, 60):
        inverted[row : row + 2, 60:840] = INVERTED_STROKE
    strokes_before = int(np.count_nonzero(inverted > MID_GREY))

    result = cleaner._clean_image(inverted, settings(denoise_strength=ERASING_DENOISE_STRENGTH))

    strokes_after = int(np.count_nonzero(result.cleaned > MID_GREY))
    assert strokes_after / strokes_before >= MIN_INVERTED_STROKE_RETENTION


def test_a_faint_total_inside_the_printed_bodys_box_survives_every_stage() -> None:
    """The CONTROL for D1, and the thing that proves the crop is the culprit.

    The identical faint mark, at the identical intensity, placed INSIDE the ink
    bounding box instead of below it, comes through untouched — 1680 pixels in,
    1680 out. Denoising did not erase it and contrast did not merge it into the
    paper. Only its POSITION changes the outcome, which leaves exactly one stage
    that can be responsible.
    """
    page = a_printed_body()
    page[200:212, 700:840] = FAINT_TOTAL

    result = cleaner._clean_image(page, settings())

    assert pixels_in_band(page, FAINT_BAND_LOW, FAINT_BAND_HIGH) == FAINT_TOTAL_PIXELS
    assert pixels_in_band(result.cleaned, FAINT_BAND_LOW, FAINT_BAND_HIGH) == FAINT_TOTAL_PIXELS


# ══ PART TWO — D1: the crop discards content Otsu does not call ink ═══════
# Both tests below were RED; the measurement in each is the defect they guard.


def test_a_faint_gstin_below_the_printed_body_is_not_cropped_off_the_page() -> None:
    """D1 — was RED.The registration number leaves the document silently.

    `_crop_to_ink` takes the bounding box of `_ink_mask`, and `_ink_mask` is
    Otsu. On this page Otsu splits at 30.0, so the only pixels it calls ink are
    the near-black body print; a GSTIN at intensity 205 — thirty grey levels
    below the paper and perfectly readable — is classified as paper and falls
    outside the box.

    MEASURED, at the baseline settings:
        page              600 x 900  ->  cleaned 218 x 788
        faint GSTIN       4080 pixels  ->  0 pixels
        ink_kept_by_crop  1.0
        preservation      the cleaned representation is the safer basis
        rms_contrast      57.66  ->  90.92   (reported as an improvement)

    `ENGINE_1:450` — cleaner *"cannot remove important evidence."* A GSTIN is
    the field that decides which registered person a tax invoice belongs to.
    """
    page = a_page_with_a_faint_gstin()
    assert pixels_in_band(page, FAINT_BAND_LOW, FAINT_BAND_HIGH) == FAINT_GSTIN_PIXELS

    result = cleaner._clean_image(page, settings())

    assert pixels_in_band(result.cleaned, FAINT_BAND_LOW, FAINT_BAND_HIGH) == FAINT_GSTIN_PIXELS


def test_content_the_crop_discarded_is_reported_instead_of_being_called_full_retention() -> None:
    """D1 — the crop keeps the GSTIN, AND the figure that would report losing it
    is still able to report one.

    THIS TEST HAS TWO HALVES AND NEITHER IS OPTIONAL. When D1 was live, this
    attack showed the GSTIN leaving the page while `ink_kept_by_crop` said 1.0.
    The crop was then fixed, and the attack stopped being constructible on that
    page — the mark stays, so there is no discard left to misreport.

    Asserting only the first half would be the trap. `ink_kept_by_crop` counted
    the ink inside the crop and divided by the ink on the page using the SAME
    Otsu mask that chose the crop, which made it 1.0 by algebra whatever the
    crop removed; the module's own note conceded it was *"1.0 by construction."*
    A page that merely keeps its GSTIN cannot tell that quotient apart from a
    working measurement, so a test that checked only that would go green and
    leave the guard hollow — exactly the defect, one layer up. This repository
    has shipped that shape twice: a mutation gate that reported 0.0%
    structurally, and a capture-fidelity check comparing an object to itself.

    So the second half puts a mark somewhere the crop genuinely does discard it
    and requires the figure to MOVE — by exactly the mark, not merely somewhere.
    The two rules are what make that possible: the box is drawn from the line
    profiles and the retention counted at Otsu's split, so the number marks work
    it did not do. If either half of that separation is ever undone, this fails.

    MEASURED, at the baseline settings:
        the faint-GSTIN page      50880 content pixels in, 50880 out
        the corner-mark scan      ink_kept_by_crop  0.9998077292828302
                                  = 46800/46809 to the bit, the mark's nine
                                    pixels and nothing else
                                  preservation: the original is the safer basis
                                  delivered 218 rows; 491 would be needed to
                                    hold the printed body and the mark together
        the same scan, no mark    ink_kept_by_crop  exactly 1.0
                                  preservation: the cleaned page is safer

    PROVEN BY BREAKING IT (§J.5). Four mutations of `cleaner.py`, this test run
    against each: retention hardwired to 1.0 -> RED (`assert 1.0 < 1.0`); the
    box drawn from the Otsu mask that audits it, which is D1 itself -> RED
    (`46800 == 50880`); `preservation_status` stops consulting the retention
    figure -> RED. The fourth, dropping `kept_by_second_crop` from the product,
    SURVIVES, and is recorded rather than papered over: across 28 pages spanning
    0-12 degrees of skew and sigma 0-20 of noise the second crop's factor was
    1.0 on every one, because rotation's interpolation smooths the page and so
    LOWERS the line profile's allowance — the second box is never tighter than
    the first. No page is known that would kill it, and none was invented to.

    `ENGINE_1:450` — cleaner *"cannot remove important evidence."* A number that
    cannot take any other value is not a measurement, and this one is the only
    thing standing between a discarded mark and `preservation_status`.
    """
    page = a_page_with_a_faint_gstin()

    result = cleaner._clean_image(page, settings())

    assert content_pixels(page) == GSTIN_PAGE_CONTENT_PIXELS
    assert content_pixels(result.cleaned) == GSTIN_PAGE_CONTENT_PIXELS

    # The retention figure can still fall, and falls by exactly what was thrown
    # away. Without this the assertion above passes on a constant.
    marked = a_scan_with_an_isolated_corner_mark()

    discarded = cleaner._clean_image(marked, settings())

    assert discarded.cleaned.shape[0] < HEIGHT_THAT_HOLDS_BODY_AND_MARK, (
        "the attack is void unless the crop actually discarded the mark"
    )
    retention = discarded.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED).value
    assert retention is not None
    assert retention < FULL_RETENTION
    assert retention == PRINTED_BODY_INK_PIXELS / (PRINTED_BODY_INK_PIXELS + CORNER_MARK_PIXELS)
    assert discarded.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER

    # ...and does NOT fall on the identical scan with nothing to discard, so the
    # figure is answering the crop rather than the sensor noise.
    intact = cleaner._clean_image(a_scan_of_a_printed_body(), settings())

    kept = intact.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED).value
    assert kept == FULL_RETENTION
    assert intact.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


# ══ PART TWO — D2: a net count cannot see a local erasure ════════════════


def test_the_reported_ink_loss_is_never_smaller_than_the_ink_actually_erased() -> None:
    """D2 — was RED.Accretion in one region cancels destruction in another.

    `clean` computes `lost = (ink_before - ink_after) / ink_before` from two
    COUNTS. On a page carrying a shaded panel, denoising pulls the panel's
    pixels toward its mean and a mass of them crosses the Otsu split into ink,
    while isolated marks elsewhere are smoothed away. The counts move in
    opposite directions and the reported figure goes NEGATIVE.

    MEASURED at strength 40.0 on the shaded invoice:
        ink 194382 -> 197272
        reported ink_lost_to_denoise   -0.014868   (ink apparently GAINED)
        pixels that truly stopped being ink        1094   =  0.005628
        the isolated decimal point       4 pixels  ->  0 pixels

    The honest quantity is the SET DIFFERENCE — pixels that were ink and are not
    — which cannot be cancelled by anything happening elsewhere on the page.
    """
    page = a_shaded_invoice()
    _mask, split = cleaner._ink_mask(page)
    denoised: Image = np.asarray(
        cv2.fastNlMeansDenoising(
            page,
            None,
            ERASING_DENOISE_STRENGTH,
            BASELINE.denoise_template_window,
            BASELINE.denoise_search_window,
        ),
        dtype=np.uint8,
    )
    truly_erased = ink_erased_between(page, denoised, split)
    ink_before = int(np.count_nonzero(page.astype(np.float64) <= split))
    truly_erased_fraction = truly_erased / ink_before
    assert truly_erased_fraction > TRUE_ERASED_FRACTION, "the attack erased too little to judge"

    result = cleaner._clean_image(page, settings(denoise_strength=ERASING_DENOISE_STRENGTH))

    reported = result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED).value
    assert reported is not None
    assert reported >= truly_erased_fraction


def test_a_decimal_point_erased_by_denoising_makes_the_original_the_safer_basis() -> None:
    """D2 — was RED.The strictest possible setting still calls the damage safe.

    `max_ink_loss_fraction = 0.0` says: tolerate no loss of ink whatsoever. The
    denoise then erases 1094 ink pixels including an entire isolated decimal
    point, and because the reported figure is -0.014868 the comparison
    `lost > max_ink_loss_fraction` is false and the module answers *"the cleaned
    representation is the safer basis for reading."*

    A decimal point is not a rounding error. `1234.56` and `123456` differ by
    two orders of magnitude, and `ENGINE_1:449` forbids changing numbers.
    """
    page = a_shaded_invoice()
    _mask, split = cleaner._ink_mask(page)
    denoised: Image = np.asarray(
        cv2.fastNlMeansDenoising(
            page,
            None,
            ERASING_DENOISE_STRENGTH,
            BASELINE.denoise_template_window,
            BASELINE.denoise_search_window,
        ),
        dtype=np.uint8,
    )
    point_before = int(np.count_nonzero(page[300:302, 520:522].astype(np.float64) <= split))
    point_after = int(np.count_nonzero(denoised[300:302, 520:522].astype(np.float64) <= split))
    assert point_before > 0, "the attack is void unless the decimal point started as ink"
    assert point_after == 0, "the attack is void unless the decimal point was erased"

    result = cleaner._clean_image(
        page,
        settings(
            denoise_strength=ERASING_DENOISE_STRENGTH,
            max_ink_loss_fraction=NO_INK_LOSS_TOLERATED,
        ),
    )

    assert result.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER


# ══ PART TWO — D3: a scanned PDF reports page one and discards the rest ══


def test_the_preservation_status_of_a_scan_does_not_depend_on_the_page_order() -> None:
    """D3 — was RED.The same two pages, reordered, get the opposite answer.

    `_pdf_rebuilt_from_cleaned_pages` cleans every page but keeps only `first`,
    so the returned `preservation_status` and every quality observation belong
    to page one alone. Page order is not a property of a document's physical
    quality, so an answer that changes with it is an answer about the wrong
    thing.

    MEASURED at strength 40.0, tolerance 0.10, 100 dpi:
        thick page alone         ink_lost 0.0043   cleaned is safer
        hairline page alone      ink_lost 0.6389   ORIGINAL is safer
        thick THEN hairline      ink_lost 0.0043   cleaned is safer   <-- wrong
        hairline THEN thick      ink_lost 0.6389   ORIGINAL is safer

    Both rebuilt PDFs contain two pages, so the damage to the hairline page is
    in the output either way; only the evidence about it moves.
    """
    thick = a_thickly_printed_page()
    hairline = a_hairline_page()
    tolerant = settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=0.10)

    thick_first = cleaner.clean_artifact(
        a_scanned_pdf([thick, hairline]), cleaner.MediaKind.PDF, tolerant, render_dpi=RENDER_DPI
    )
    hairline_first = cleaner.clean_artifact(
        a_scanned_pdf([hairline, thick]), cleaner.MediaKind.PDF, tolerant, render_dpi=RENDER_DPI
    )

    assert thick_first.preservation_status is hairline_first.preservation_status


def test_every_page_of_a_scanned_pdf_contributes_quality_evidence() -> None:
    """D3 — was RED.Pages two onward are cleaned and then measured by nobody.

    `confidence` is the only component allowed to turn cleaner's signals into a
    score (`ENGINE_1:109`). If a page produces no signal, `confidence` cannot
    account for it, and the damage to it becomes invisible for the rest of the
    pipeline.

    MEASURED: a one-page scan reports 14 observations. A two-page scan reports
    14. A twenty-page scan would report 14.
    """
    one_page = a_scanned_pdf([a_thickly_printed_page()])
    two_pages = a_scanned_pdf([a_thickly_printed_page(), a_hairline_page()])
    tolerant = settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=0.10)

    single = cleaner.clean_artifact(
        one_page, cleaner.MediaKind.PDF, tolerant, render_dpi=RENDER_DPI
    )
    double = cleaner.clean_artifact(
        two_pages, cleaner.MediaKind.PDF, tolerant, render_dpi=RENDER_DPI
    )

    assert len(double.quality_observations) > len(single.quality_observations)


# ══ PART TWO — D4: the alpha channel, and the content carried in it ══════


def test_two_rgba_documents_with_different_content_do_not_clean_to_the_same_page() -> None:
    """D4 — was RED.A stamp and a blank canvas produce identical output.

    `_to_grey` sends a four-channel image through `cv2.COLOR_BGRA2GRAY`, which
    computes a luma from B, G and R and drops A. When a mark's shape lives in
    the alpha channel — the ordinary result of any background removal, any
    premultiplied export, any `convert -transparent` — the colour channels are
    zero everywhere and the luma is uniform.

    MEASURED: a stamp of 40320 visible pixels and a fully transparent canvas
    both clean to a constant page, standard deviation 0.0, RMS contrast 0.0 at
    BOTH stages, `ink_lost_to_denoise` 0.0, `preservation` cleaned-is-safer.

    A normalisation that maps two different documents onto the same output has
    destroyed the difference between them, and `ENGINE_1:457` required the
    original to be preserved and the uncertainty marked instead.
    """
    stamped = cleaner._clean_image(an_alpha_carried_mark(), settings())
    blank = cleaner._clean_image(a_fully_transparent_page(), settings())

    assert not np.array_equal(stamped.cleaned, blank.cleaned)


def test_a_document_whose_content_lives_in_alpha_is_not_flattened_to_one_grey() -> None:
    """D4 — was RED.40320 visible pixels become a page with zero variance.

    Stated as variance rather than as a comparison so it holds regardless of
    which grey the flattening happens to land on, and so it fails for the right
    reason: information, not colour.
    """
    page = an_alpha_carried_mark()
    visible = int(np.count_nonzero(page[..., 3]))
    assert visible > 0, "the attack is void unless the alpha channel carries a mark"

    result = cleaner._clean_image(page, settings())

    assert float(np.std(result.cleaned.astype(np.float64))) > 0.0


# ══ PART THREE — the byte path carries the same damage ═══════════════════


def test_the_encoded_payload_carries_whatever_the_raster_lost() -> None:
    """Not a separate defect: proof that D1 reaches every consumer.

    `clean_artifact` re-encodes `document.cleaned` as the payload, so a crop
    that removed the GSTIN removes it from the bytes `reader` and `parser` will
    open. This test asserts the payload and the raster agree, which they do —
    the point being that there is no second, undamaged copy anywhere except the
    `original` field.
    """
    ok, buffer = cv2.imencode(".png", a_page_with_a_faint_gstin())
    assert ok
    data = bytes(buffer.tobytes())

    result = cleaner.clean_artifact(
        data, cleaner.MediaKind.IMAGE, settings(), render_dpi=RENDER_DPI
    )

    assert result.artifact is not None
    decoded = cleaner.decode(result.artifact.payload)
    assert np.array_equal(decoded, result.cleaned)
    assert result.artifact.original == data
    # The original bytes still carry the GSTIN, which is the only reason this
    # defect is recoverable at all.
    assert (
        pixels_in_band(cleaner.decode(result.artifact.original), FAINT_BAND_LOW, FAINT_BAND_HIGH)
        == FAINT_GSTIN_PIXELS
    )


def test_the_module_still_exposes_no_way_to_read_what_it_removed() -> None:
    """There is no observation naming content lost to any stage but denoising.

    The three outputs §1.1 names are all present, and none of them can carry
    "what the crop removed" because no such measurement is taken. Asserted so
    that adding one is a deliberate act rather than an accident.
    """
    result = cleaner._clean_image(a_page_with_a_faint_gstin(), settings())

    names = {observation.name for observation in result.quality_observations}
    assert cleaner.INK_LOST_TO_DENOISE in names
    assert cleaner.INK_KEPT_BY_CROP in names
    with pytest.raises(KeyError):
        result.observed("content_lost_to_crop", cleaner.Stage.CLEANED)


# ══ the content box's own degenerate case, called directly ══════════════
#
# `clean()` cannot reach this through the public API — `_receive` refuses
# anything shorter than `denoise_search_window`, so the grey array is never
# empty. The guard is real logic with a real contract — "no box, so crop
# nothing" — and the module answers `None` rather than raising on the maximum
# of an empty profile. Tested directly with real degenerate arrays, exactly as
# this module's other measurement guards are, rather than left unexercised
# because one caller happens never to build a degenerate array.


def test_a_page_with_no_pixels_at_all_has_no_content_box() -> None:
    """Zero rows and zero columns, both ways round. `None`, never a crash and
    never a box of nothing that would crop a document out of existence."""
    assert cleaner._content_box(np.zeros((0, 5), dtype=np.uint8)) is None
    assert cleaner._content_box(np.zeros((5, 0), dtype=np.uint8)) is None


# ══ PART FOUR — a figure that lies in the REASSURING direction ═══════════
#
# The three defects above are each a quantity that under-reports damage. This
# one is the general case of that, and it is stated as an INVARIANT over every
# observation this module emits rather than as a test of one name, because the
# instance was cheap to delete and the CLASS is what recurs (§J.9).


def test_no_fraction_this_module_reports_can_exceed_the_whole_it_is_a_fraction_of() -> None:
    """A retention above 1.0 is a number lying in the reassuring direction.

    THE DEFECT THIS TRAPS, MEASURED. `content_kept` counted the pixels departing
    from a page's median by more than that page's own noise, before against
    after. Denoising COLLAPSES the noise, which collapses the bound, so the
    count rose as the page was smoothed — whatever the smoothing cost the
    document. Across 189 page-and-setting combinations it exceeded 1.0 in 162,
    peaking at 36.9934: a quantity carrying the unit *"fraction of content
    pixels"* reported at 3699%. On the six runs where every mark had genuinely
    been erased from the page it read between 15.04 and 18.09.

    WHY THIS IS WORSE THAN NO MEASUREMENT AT ALL. `preservation_status` exists
    so a caller can be told the original is the safer basis for reading. A
    figure that goes UP as a page is destroyed does not merely fail to raise
    that flag — it argues against it, inside the artifact, in the caller's own
    units. Law 24: never fabricate a metric. A metric that is real arithmetic
    over a quantity the pipeline does not conserve is fabricated all the same.

    STATED OVER EVERY OBSERVATION, NOT OVER ONE NAME. Deleting `content_kept`
    fixes the instance and guards nothing. What must not recur is any figure
    denominated as a share of a whole that is free to exceed that whole, and
    `unit` is where this module declares that intent — so `unit` is what this
    reads. A new observation reporting a fraction is covered the day it is
    added, without this test being touched.

    THE PAGE IS ONE BEING ACTIVELY DESTROYED, because that is where the sign of
    the error matters and where the deleted figure was at its worst. Asserted
    first, from an oracle this module never sees: at strength 60 the hairline
    rules are entirely gone — every pixel a human could read as a mark, zero
    left — so no honest retention here has any business being above 1.0.
    """
    page = a_hairline_page()
    destroyed = cleaner._clean_image(page, settings(denoise_strength=ANNIHILATING_DENOISE_STRENGTH))

    # The oracle is this file's own: a fixed intensity the paper never reaches,
    # so it needs neither Otsu nor the module's noise estimate to be believed.
    assert int(np.count_nonzero(page <= DARK_MARK)) == HAIRLINE_DARK_PIXELS
    assert int(np.count_nonzero(destroyed.cleaned <= DARK_MARK)) == 0, (
        "the attack is void unless the page really was destroyed"
    )

    fractions = [
        observation
        for observation in destroyed.quality_observations
        if observation.unit.startswith("fraction")
    ]
    assert fractions, "no fraction is reported at all, so this invariant guards nothing"
    for observation in fractions:
        assert observation.value is not None
        assert 0.0 <= observation.value <= 1.0, (
            f"{observation.name} reports {observation.value} of a whole — a share above "
            "1.0 tells the caller more survived than existed"
        )
