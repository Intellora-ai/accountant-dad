"""The `cleaner` sub-engine — it alters presentation, and it alters nothing else.

`SUB_ENGINE_RESPONSIBILITIES.md` §1.1 gives this module one job: *"the physical
quality of the artifact — deskewing, rotation, denoising, cropping, contrast, and
normalisation of file format and character encoding."* `ENGINE_1:436-453` states
the same in permissions and prohibitions: it may reduce visual noise, improve
readability, normalise appearance and improve image quality; it may not change
numbers, remove important evidence, interpret text, correct accounting
information, or alter original meaning.

THREE OUTPUTS, NOT FOUR, AND NOT ONE. `ENGINE_1:405` and §1.1 both name exactly
*"cleaned document representation · quality issues detected · preservation
status."* `CleanedDocument` carries those three and the original, and nothing
else. There is no extracted text on it, no field, no confidence score: those
belong to `reader`, `parser` and `confidence`, and `ENGINE_1:113` — *"no
sub-engine overrides another."*

    `source_geometry` IS PART OF THE FIRST OF THE THREE, NOT A FOURTH, and the
    reasoning is written down here rather than assumed because the count above
    is the module's own rule. A raster with no statement of what it is a raster
    OF is not a representation of the artifact; it is a different picture that
    happens to have come from it. `COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 4
    requires every extracted value to keep *"Source — where in the artifact it
    came from"*, permanently and *"not stripped at the engine boundary"* — and
    `reader` CANNOT honour that for a cleaned scan unless this module says
    where the cleaned page sits on the page it was given. It did not, which is
    `KNOWN_FAILURES.md` F-030. So this field does not add a product; it makes
    the first product satisfy a locked rule it was silently failing.

    WHERE THAT READING COULD BE WRONG, stated rather than buried: whether the
    owner regards a source map as part of *"cleaned document representation"*
    or as a fourth named product is a decision about the locked documents, and
    no code change can take it. If it is the latter, `ENGINE_1:405`, §1.1 and
    this paragraph are what need revising — the field is still required either
    way, because Rule 4 is not optional.

IT REPORTS MEASUREMENTS; IT DOES NOT JUDGE THEM.
    §1.1 — quality issues are *"reported as evidence for `confidence`, never
    repaired by guesswork."* `ENGINE_1:109` — `cleaner` emits SIGNALS and only
    `confidence` turns a signal into a score. So every quality finding here is a
    NUMBER WITH A UNIT and no verdict attached. There is no "the contrast is
    poor" anywhere in this module, because "poor" is a judgement and the
    component that owns judgements about reliability is a different one.

    That also removed every threshold this module would otherwise have had to
    invent. A measurement needs no cut-off; only a verdict does (Law 52, 54).

NOT ONE NUMBER IN THIS MODULE WAS CHOSEN BY IT.
    `CleanerSettings` has EIGHT fields and NO DEFAULTS. Nothing in any locked
    document states a deskew limit, a denoise strength, a CLAHE clip limit, a
    crop margin, or how much ink may be lost before the original is the safer
    basis for reading. A default here would be a number nobody set, arriving
    downstream wearing the specification's authority — `CLAUDE.md` Law 52:
    *"Never infer it. Never pick one yourself and proceed."*

    The only bounds this module enforces on those settings come from OpenCV's
    own contract (a denoise window is odd; the search window is not smaller than
    the template) or from arithmetic (a fraction lies in [0, 1]; a rectangle's
    orientation is only defined modulo 90 degrees). None is a preference.

THE ONE DECISION IT DOES MAKE, AND THE MEASUREMENT BEHIND IT.
    `ENGINE_1:457` — *"If processing may damage information: preserve the
    original input and mark uncertainty."* That is a decision, so it needs a
    number, so the number is the caller's: `max_ink_loss_fraction`.

    What is measured against it is INK LOST TO DENOISING — the pixels that WERE
    ink before the denoise step and are NOT ink after it, counted as a set
    difference at the single threshold computed from the artifact as received.
    A NET of two counts was the earlier form and it was wrong: a filter that
    erases strokes in one region while pushing a shaded panel across the split
    in another reported ink GAINED while a decimal point was being wiped out
    (`_ink_erased`). Denoising is the one step that can erase a stroke; the
    hairline of a decimal point is exactly what a strong filter removes, and a
    decimal point removed is a financial misstatement. Rotation cannot lose a
    pixel because the canvas is grown to hold the whole rotated frame, and
    neither crop can lose one because each box is the bounding box of all the
    CONTENT — both are structural, and both are measured anyway rather than
    asserted.

    NEITHER STRUCTURAL GUARANTEE IS ALLOWED TO BE ITS OWN AUDITOR. A retention
    counted with the mask that drew the box is 1.0 by algebra whatever the box
    removed, which is how a readable GSTIN left an invoice while the module
    reported full retention. The crop's box comes from line profiles
    (`_content_box`) and its retention is counted with Otsu (`_ink_mask`) — two
    different rules, so the quotient is free to move, and measured it does:
    0.9998077292828302 on a noisy scan whose nine-pixel margin mark the crop
    discarded, against exactly 1.0 on the same scan without the mark.

    A THIRD, END-TO-END RETENTION FIGURE WAS TRIED HERE AND IS DELETED, because
    it did not measure what it claimed to. `content_kept` counted pixels
    departing from the page's median by more than the page's own noise, before
    against after. Denoising COLLAPSES that noise — which collapses the bound —
    so the count rose as the page was smoothed, whatever the smoothing cost the
    document. Measured across 189 page-and-setting combinations: it exceeded 1.0
    in 162 of them, reaching 36.99 — a "fraction of content pixels" reported at
    3699%. On the six runs where every mark had genuinely been erased from the
    page (true retention 0.000000) it reported between 15.04 and 18.09. It fell
    below 1.0 in 15 runs and NOT ONE of them had lost anything. A number that
    rises when content is destroyed and falls when it is not is worse than no
    number: it is a reassurance, shipped inside the artifact, pointing the wrong
    way (Law 24). The two figures that remain are each audited by a rule that
    did not produce them, which is the property this one never had.

WHAT IT DOES NOT ACCEPT, AND WHY REFUSING IS THE HONEST ANSWER.
    A float or 16-bit array is refused rather than cast. Casting `float32` to
    `uint8` changes every intensity in the frame silently, and `ENGINE_1:453`
    forbids altering original meaning. A 16-bit scan halves its tonal
    resolution on the way down; that is content removed, and §1.1 forbids
    discarding content.

    `decode` raises on bytes that are not an image. `SYSTEM_BOUNDARIES.md:52`
    says the Input Engine may not reject a document or halt the pipeline — that
    binds the ENGINE at its boundary, and it is the parent's obligation:
    `COMMUNICATION_RULES_INPUT_ENGINE.md` §4.9 requires a damaged artifact to
    cross as *"low confidence and named uncertainty, not as errors."* A
    sub-engine that returned a blank image instead would hand `reader` a page
    that reads as empty, which is the invention prohibition broken quietly.
    Loud here, named uncertainty at the boundary (`CLAUDE.md` Law 11).

A PROVIDED SOURCE CANNOT BE TOUCHED, BECAUSE THERE IS NO PATH THAT COULD.
    §1.1 and `ENGINE_1:459` — a Human Business Description *"passes through
    untouched"*; any transformation would be a rewrite, and `ENGINE_1:333` makes
    rewriting the user's wording absolute. This module accepts `bytes` and
    `uint8` arrays and has no function that takes or returns text. That is a
    stronger guarantee than an identity function, which could later grow a
    `.strip()`.

STATED ASSUMPTION, BECAUSE IT IS AN ASSUMPTION AND NOT A FACT.
    Ink is darker than paper. Otsu's inverse threshold encodes it, and every ink
    count here rests on it. A white-on-black artifact would be measured with the
    ink and the paper swapped. No locked document describes such an artifact and
    inventing a polarity detector would be inventing behaviour, so the
    assumption is named here instead of hidden in a helper.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

import cv2
import numpy as np
import numpy.typing as npt

# THE PDF ENGINE, by name — see the import note in `reader.py` for why the
# names and not the module: the Engine 1 boundary guard reads what an import
# NAMES, and only this form names `accountant_dad.pdf_backend`.
from accountant_dad.pdf_backend import (
    close_pdf,
    open_pdf,
    page_count,
    pdf_of_page_images,
    plain_text,
    render_page_png,
)

#: An 8-bit image. One channel after normalisation; one, three or four on input.
Image = npt.NDArray[np.uint8]
Real = npt.NDArray[np.float64]

# ── the names of the measurements ─────────────────────────────────────────
# Constants rather than bare strings so a caller cannot mistype a lookup into a
# silent miss, and so `reader` and `confidence` read the same names this writes.

SKEW_ANGLE = "skew_angle"
NOISE_SIGMA = "noise_sigma"
RMS_CONTRAST = "rms_contrast"
LAPLACIAN_VARIANCE = "laplacian_variance"
INK_FRACTION = "ink_fraction"
DESKEW_APPLIED = "deskew_applied"
DESKEW_FILL_INTENSITY = "deskew_fill_intensity"
INK_LOST_TO_DENOISE = "ink_lost_to_denoise"
INK_KEPT_BY_CROP = "ink_kept_by_crop"

_DEGREES = "degrees"
_GREY_LEVELS = "grey levels"

#: A rectangle's orientation repeats every 90 degrees, so a skew is only
#: representable in (-45, 45]. Arithmetic, not a preference.
_QUARTER_TURN = 90.0
_HALF_QUARTER_TURN = 45.0

#: Immerkaer's noise mask needs a 3x3 neighbourhood, and its normalisation
#: divides by the interior area.
_MIN_SIDE_FOR_NOISE = 3
_NOISE_MASK = np.array([[1.0, -2.0, 1.0], [-2.0, 4.0, -2.0], [1.0, -2.0, 1.0]], dtype=np.float64)
_NOISE_NORMALISER = 6.0

_GREY_NDIM = 2
_COLOUR_NDIM = 3
_BGR_CHANNELS = 3
_BGRA_CHANNELS = 4
_ALPHA_CHANNEL = 3

#: The largest value an 8-bit channel can hold: full opacity, and the lightest
#: intensity there is. Arithmetic, not a level anyone picked. It is the paper a
#: transparent region shows through to (`_composite_over_paper`) and the "yes"
#: of a mask, so that a mask prints and inspects like the image it accompanies.
_FULL_SCALE = 255

#: The definition of a typographic point. Arithmetic, not a setting: it is what
#: converts a pixel counted at a known resolution into the unit a PDF page is
#: measured in. `pdf_backend` derives its own one-pixel bound from the same
#: constant, and this is the same pixel.
_POINTS_PER_INCH = 72.0


class ImpossibleSettingError(ValueError):
    """A setting OpenCV or arithmetic cannot honour. Raised at construction."""


class UnusableArtifactError(ValueError):
    """An artifact this module cannot clean without changing what it contains."""


class UndecodableArtifactError(UnusableArtifactError):
    """Bytes that are not a decodable image. Never a blank page in its place."""


class NoRenderResolutionError(LookupError):
    """A point asked of a raster this module did not render from a page.

    DELIBERATELY NOT AN `UnusableArtifactError`, for the reason
    `NoCleanerRegisteredError` is not one either: an `UnusableArtifactError` is
    a verdict about the DOCUMENT, and the document here is fine. An image
    arrives already rasterised at whatever resolution it was captured at, so
    its pixels ARE its own space and there is no page of points behind them.
    Answering anyway — treating a pixel as a point — would put a unit in the
    artifact that nothing measured (Law 11, Law 24).
    """


class Stage(StrEnum):
    """Which of the two forms a measurement was taken on."""

    ORIGINAL = "original"
    CLEANED = "cleaned"


class PreservationStatus(StrEnum):
    """§1.1 — *"whether the cleaned representation or the original is the safer
    basis for reading."* Two states, named as the sentence names them."""

    CLEANED_IS_SAFER = "the cleaned representation is the safer basis for reading"
    ORIGINAL_IS_SAFER = "the original is the safer basis for reading"


@dataclass(frozen=True, slots=True)
class QualityObservation:
    """One measured quantity, its unit, and why it was taken.

    `value` is `None` when the quantity could not be measured at all — a skew
    angle on a page with no ink on it. `None` and `0.0` are different states and
    collapsing them would report a blank page as a perfectly straight one.
    """

    name: str
    stage: Stage
    value: float | None
    unit: str
    #: `ENGINE_1:626` — every marker carries a reason; a bare number cannot
    #: become a good question downstream.
    note: str
    #: WHICH PAGE THIS WAS MEASURED ON, one-based.
    #:
    #: A single-page artifact has exactly one, so the default is the whole
    #: answer for every image and every one-page scan. It exists because a
    #: multi-page scan used to report page one's measurements and silently drop
    #: every other page's: the same two pages in the opposite order produced the
    #: opposite `preservation_status`, which made the reported quality a
    #: property of the page ORDER rather than of the document
    #: (`KNOWN_FAILURES.md` D3). Page provenance is what makes the accumulated
    #: measurements readable instead of merely numerous — without it, twenty
    #: pages of `skew_angle` are twenty numbers nobody can attribute.
    page: int = 1


@dataclass(frozen=True, slots=True)
class CleanerSettings:
    """Eight numbers, all required, none of them this module's opinion.

    Every bound checked below comes from OpenCV's contract or from arithmetic.
    Where a locked document had stated a value it would appear here as that
    document's value; none does, so all eight stay the caller's.
    """

    #: Above this, the correction is refused and the page is left as received.
    max_deskew_degrees: float
    #: `h` in `cv2.fastNlMeansDenoising`.
    denoise_strength: float
    denoise_template_window: int
    denoise_search_window: int
    #: `clipLimit` in `cv2.createCLAHE`.
    contrast_clip_limit: float
    #: `tileGridSize` is (n, n).
    contrast_tile_grid: int
    crop_margin_pixels: int
    #: Ink lost to denoising above this fraction makes the original safer.
    max_ink_loss_fraction: float

    def __post_init__(self) -> None:
        if not 0.0 < self.max_deskew_degrees <= _QUARTER_TURN:
            raise ImpossibleSettingError(
                f"max_deskew_degrees must lie in (0, {_QUARTER_TURN}]; got "
                f"{self.max_deskew_degrees}. A rectangle's orientation repeats "
                "every quarter turn, so nothing outside that range is representable."
            )
        if self.denoise_strength <= 0.0:
            raise ImpossibleSettingError(
                f"denoise_strength must be positive; got {self.denoise_strength}."
            )
        for name, window in (
            ("denoise_template_window", self.denoise_template_window),
            ("denoise_search_window", self.denoise_search_window),
        ):
            if window < _MIN_SIDE_FOR_NOISE or window % 2 == 0:
                raise ImpossibleSettingError(
                    f"{name} must be odd and at least {_MIN_SIDE_FOR_NOISE}; got "
                    f"{window}. An even window has no centre pixel."
                )
        if self.denoise_search_window < self.denoise_template_window:
            raise ImpossibleSettingError(
                f"denoise_search_window ({self.denoise_search_window}) is smaller "
                f"than denoise_template_window ({self.denoise_template_window}); "
                "the search area must contain the template it searches for."
            )
        if self.contrast_clip_limit <= 0.0:
            raise ImpossibleSettingError(
                f"contrast_clip_limit must be positive; got {self.contrast_clip_limit}."
            )
        if self.contrast_tile_grid < 1:
            raise ImpossibleSettingError(
                f"contrast_tile_grid must be at least 1; got {self.contrast_tile_grid}."
            )
        if self.crop_margin_pixels < 0:
            raise ImpossibleSettingError(
                f"crop_margin_pixels must not be negative; got {self.crop_margin_pixels}."
            )
        if not 0.0 <= self.max_ink_loss_fraction <= 1.0:
            raise ImpossibleSettingError(
                f"max_ink_loss_fraction must lie in [0, 1]; got "
                f"{self.max_ink_loss_fraction}. It is a fraction of the ink."
            )


class MediaKind(StrEnum):
    """What the artifact IS, carried alongside it so cleaning never has to guess.

    §1.1's input list is *"photo, camera capture, image upload, PDF, scan,
    handwritten note, Excel file, email content, structured metadata, or other
    digital file."* Those are not interchangeable, and the whole point of
    `CleanedArtifact` is that the cleaned form of each is still ITS OWN KIND.

    Declared by the caller and never sniffed from the bytes — `reader.MediaType`
    takes the same position for the same reason (Law 23: external input is
    untrusted, and guessing a document's type from its bytes is a guess).
    """

    IMAGE = "image"
    PDF = "pdf"


@dataclass(frozen=True, slots=True, eq=False)
class CleanedArtifact:
    """A cleaned document that is still the kind of document it started as.

    THIS TYPE EXISTS BECAUSE THE PREVIOUS ONE WAS WRONG, and the way it was
    wrong is worth stating so it is not reintroduced. `cleaned` used to be
    `NDArray[uint8]` — a bitmap. That made "cleaned document representation"
    mean "cleaned raster", which the specification never said and which cannot
    represent a PDF, a workbook or an email at all.

    Three failures followed from that one line, and all three were symptoms
    rather than separate bugs (`KNOWN_FAILURES.md` F-017):

        a PDF could not be decoded at all, because the return type left nowhere
        for it to go — Engine 1's own primary input

        `reader` and `parser` refused to consume cleaner's output, CORRECTLY:
        handing either a bitmap of a PDF destroys the text layer, which is the
        one thing that makes a text-layer PDF readable without OCR. They
        re-opened the original because doing so was strictly better

        OCR became the only consumer the output fitted, and OCR is the one path
        CI cannot run

    `payload` is therefore the cleaned artifact IN ITS OWN FORMAT: a cleaned
    image stays image bytes, a cleaned PDF stays a PDF with its text layer
    intact. `raster` is an additional VIEW for consumers that need pixels
    (OCR), never a replacement for the payload.

    CLEANING MAY NEVER REDUCE THE INFORMATION AVAILABLE. That is why a
    text-layer PDF passes through untouched rather than being "improved": a
    digitally-generated PDF has no skew, no sensor noise and no contrast
    problem, so every transformation available would be a rewrite that could
    only lose something. §1.1's own failure behaviour says the same of a
    provided source — *"any transformation would be a rewrite."*
    """

    kind: MediaKind
    #: The cleaned artifact, in its native format. What every downstream
    #: sub-engine consumes, so there is one pipeline rather than two.
    payload: bytes
    #: `ENGINE_1:461` — never discarded, so a damaging transformation is always
    #: recoverable. The bytes exactly as received.
    original: bytes
    #: A rendered view, when one was produced. `None` when nothing was
    #: rasterised — which is NOT "a blank page" and must never be read as one.
    #: Set at construction by every path that produces one; there is deliberately
    #: no `with_raster` copier, because a second way to populate a field is a
    #: second thing to keep honest and nothing ever called it (Law 49).
    raster: Image | None = None


@dataclass(frozen=True, slots=True)
class SourceGeometry:
    """Where a cleaned page's pixels came from on the page as received.

    `KNOWN_FAILURES.md` F-030: `_clean_image` applies THREE geometric
    operations and recorded NONE of them — a crop, a turn, and a second crop.
    `_crop_to_content` computed each crop's origin and dropped it on the next
    line; `_rotation` built the turn's matrix and handed it to `warpAffine` and
    to nobody else. A coordinate on a cleaned page therefore could not be
    placed on the document it came off, which is the traceability contract —
    Rule 4 of `COMMUNICATION_RULES_INPUT_ENGINE.md`, *a value must be traceable
    back to the thing it was read off*.

    WHY THIS IS A MAP AND NOT A CROP ORIGIN, WHICH IS WHAT F-030 NAMES.
        A crop is a translation, so an origin describes it completely. The
        deskew is a ROTATION about the centre of a frame whose canvas is then
        grown, and no translation approximates a rotation. Measured through the
        real cleaner: on a page planted DEAD STRAIGHT the module still measures
        -0.3000 degrees and turns it, and the displacement no single
        translation can absorb is 0.9182 px; at 3 degrees it is 9.3618 px and
        at 15 degrees 48.8693 px. The turn is not an edge case that a crop
        origin would be nearly right about — it fires on essentially every
        scan, and an origin alone would be confidently wrong on all of them
        while LOOKING like the fix F-030 asked for.

        So the record is the composition of all three, as one affine. That also
        makes it stage-agnostic: a stage added, removed or reordered inside
        `_clean_image` multiplies into the same six numbers and no consumer
        changes (Law 21, Law 32).

        THE LIMIT, STATED RATHER THAN LEFT TO BE DISCOVERED. Affine covers
        every operation §1.1 permits — *"deskewing, rotation, denoising,
        cropping, contrast"* — because translation, rotation and scale are all
        affine. A PERSPECTIVE de-warp is not, and would need a nine-number
        homography. §1.1 does not name one and none is implemented; if one is
        ever added, these six numbers cannot carry it and truncating it to them
        would silently misplace every coordinate on the page.

    SIX FLOATS RATHER THAN AN ARRAY, and that is not a storage detail. A frozen
    dataclass holding an `ndarray` is frozen only at the top level: anything
    handed the array can rewrite the map in place, and `CLAUDE.md` §O requires
    an artifact to be immutable after creation. Six floats cannot be rewritten
    by a consumer, and no consumer needs the matrix anyway — `source_pixel` and
    `source_point` are the whole interface, which is also why the conversion
    arithmetic lives in ONE place instead of at every call site (Law 14).
    """

    #: The affine that carries a CLEANED-page pixel to a SOURCE-raster pixel,
    #: row-major: `(a, b, c, d, e, f)` meaning
    #:
    #:     source_x = a * x + b * y + c
    #:     source_y = d * x + e * y + f
    #:
    #: Read it with `source_pixel`; the tuple is public so a test can prove the
    #: linear part is not the identity, which is what refuses a translation.
    to_source: tuple[float, float, float, float, float, float]
    #: The extent of the raster this map ANSWERS IN, so a consumer can tell an
    #: on-page answer from an off-page one without holding the source array. On
    #: a multi-page scan `CleanedDocument.original` is page one's alone, so for
    #: every page after the first this is the only statement of it.
    source_height: int
    source_width: int
    #: The resolution at which THIS MODULE rendered that raster from a PDF
    #: page. `None` means no rendering happened here — the raster is the
    #: artifact as supplied, and its pixels are already the document's own
    #: space. That is NOT "unknown": it is "there is nothing further to
    #: convert", the same distinction `CleanedArtifact.raster`'s `None` keeps.
    render_dpi: int | None = None
    #: WHICH PAGE this describes, one-based, exactly as `QualityObservation`
    #: carries it and for the identical reason (`KNOWN_FAILURES.md` D3). Every
    #: page of a scan is cropped and turned differently, so page one's map
    #: placed on page three's coordinates is not an approximation — it is
    #: another page's answer.
    page: int = 1

    def source_pixel(self, x: float, y: float) -> tuple[float, float]:
        """The pixel on the page as received that this cleaned pixel came from."""
        across, shear_across, shift_across, shear_down, down, shift_down = self.to_source
        return (
            across * x + shear_across * y + shift_across,
            shear_down * x + down * y + shift_down,
        )

    def source_point(self, x: float, y: float) -> tuple[float, float]:
        """The same location in the SOURCE PAGE's own point space.

        `_POINTS_PER_INCH / render_dpi` and never `page_points / raster_pixels`,
        and the difference is measured rather than argued. A rasteriser scales
        the page by `dpi / 72` and then encloses the result in whole pixels, so
        the enclosure grows the canvas without rescaling anything on it — which
        makes `72 / dpi` exact and the ratio systematically wrong. Measured on
        a 400x200 pt page carrying a mark at (300, 150) pt: `72/dpi` reports
        the mark at x = 299.5200 pt at 150, 300 AND 600 dpi, while the ratio
        drifts 299.2806 -> 299.4601 -> 299.4601. The ratio's error is exactly
        the DPI-dependence F-030 exists to remove.

        Raises rather than falling back when nothing rendered this raster: see
        `NoRenderResolutionError`.
        """
        if self.render_dpi is None:
            raise NoRenderResolutionError(
                "this raster was not rendered from a page by this module, so it "
                "has no resolution and its pixels are not points. Refused rather "
                "than returning the pixel coordinate wearing a unit nothing "
                "measured."
            )
        across, down = self.source_pixel(x, y)
        points_per_pixel = _POINTS_PER_INCH / self.render_dpi
        return across * points_per_pixel, down * points_per_pixel


@dataclass(frozen=True, slots=True, eq=False)
class CleanedDocument:
    """The three outputs §1.1 names, plus the original it may never discard.

    `eq=False` because members hold arrays: the generated comparison would
    evaluate an array in a boolean context and raise. Identity comparison is the
    honest default for something holding a megabyte of pixels.
    """

    #: `ENGINE_1:461` — never discarded, so a damaging transformation is always
    #: recoverable. Carried in the shape and channel count it arrived in.
    original: Image
    #: The cleaned document representation. Single channel, 8-bit.
    cleaned: Image
    #: Quality issues detected, as measurements. Evidence for `confidence`.
    quality_observations: tuple[QualityObservation, ...]
    preservation_status: PreservationStatus
    #: The media-aware form of the same cleaning, carrying the artifact in its
    #: OWN format so `reader` and `parser` can consume it without the text
    #: layer being destroyed. `None` only on the raster-only path that predates
    #: `clean_artifact`; every path that knows its media kind sets it.
    artifact: CleanedArtifact | None = None
    #: WHERE THE CLEANED PIXELS CAME FROM, one record per page, in page order.
    #: `KNOWN_FAILURES.md` F-030. Empty when no raster exists to have a map at
    #: all — a text-layer PDF passes through untouched, so there is no crop and
    #: no turn, and its own coordinates are already the document's. An identity
    #: map there would claim a cleaning that never happened (Law 24).
    source_geometry: tuple[SourceGeometry, ...] = ()

    def observed(self, name: str, stage: Stage, page: int = 1) -> QualityObservation:
        """The measurement, or `KeyError`. A miss is never a `None` in disguise.

        `page` is one-based and defaults to the first, which is the whole
        document for an image and for a one-page scan. Asking for a page a
        multi-page scan does not have raises rather than falling back to page
        one — a silent fallback is how page one's quality came to stand for a
        whole document in the first place.
        """
        for observation in self.quality_observations:
            if observation.name == name and observation.stage is stage and observation.page == page:
                return observation
        raise KeyError(
            f"no measurement named {name!r} was taken on the {stage} form of page {page}"
        )

    def geometry_of(self, page: int = 1) -> SourceGeometry:
        """Where page `page`'s cleaned pixels came from, or `KeyError`.

        The same discipline `observed` keeps, for the same reason: a silent
        fallback to page one is exactly how page one's evidence came to stand
        for a whole document (`KNOWN_FAILURES.md` D3), and a map is the one
        field where borrowing page one's answer misplaces every coordinate on
        the page rather than merely mis-attributing a number.
        """
        for geometry in self.source_geometry:
            if geometry.page == page:
                return geometry
        raise KeyError(
            f"no source geometry was recorded for page {page}. A cleaned "
            "coordinate on it cannot be placed on the document it came off."
        )


def _u8(array: object) -> Image:
    """Narrow an OpenCV return to 8-bit, checking rather than assuming.

    OpenCV's stubs describe every return as some integer-or-float array, so the
    narrowing has to happen somewhere. It happens here, with a real runtime
    check, so a routine that quietly starts returning `float64` fails loudly
    instead of being cast into silence.
    """
    seen = np.asarray(array)
    if seen.dtype != np.uint8:
        raise UnusableArtifactError(
            f"expected an 8-bit (uint8) image, got {seen.dtype}. Casting would "
            "change every intensity in the frame, which is the original altered."
        )
    return np.asarray(seen, dtype=np.uint8)


def _f64(array: object) -> Real:
    return np.asarray(array, dtype=np.float64)


def _extent(image: Image) -> tuple[int, int]:
    """Height and width as real `int`s. `ndarray.shape` is untyped in numpy's
    stubs, so every arithmetic result derived from it would otherwise be `Any`
    and the typechecker would stop guarding this module's arithmetic.
    """
    return int(image.shape[0]), int(image.shape[1])


def _ink_mask(grey: Image) -> tuple[Image, float]:
    """Ink pixels, and the threshold that separated them from paper.

    Otsu, so the split comes from the artifact's own histogram rather than from
    a level this module picked. Returns the threshold too, because measuring ink
    lost to denoising needs the SAME split applied to both forms — recomputing
    it would let the threshold move and report a change that never happened.
    """
    threshold, mask = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return _u8(mask), float(threshold)


def _ink_at(grey: Image, threshold: float) -> int:
    return int(np.count_nonzero(_f64(grey) <= threshold))


def _ink_erased(before: Image, after: Image, threshold: float) -> int:
    """Pixels that WERE ink and are not any more. A SET DIFFERENCE, not a net.

    Subtracting one count from another was the defect (`KNOWN_FAILURES.md` D2):
    a filter that erases strokes in one region while pushing a shaded panel
    across the split in another moves the two counts in opposite directions, and
    the difference cancels. Measured on a shaded invoice at strength 40: 194382
    ink pixels before, 197272 after, so the net reported -0.014868 — ink
    apparently GAINED — while 1094 pixels stopped being ink and an isolated
    decimal point was wiped out entirely. `1234.56` and `123456` differ by two
    orders of magnitude, so a cancelled erasure is a misstatement waiting.

    A set difference cannot be cancelled by anything happening elsewhere on the
    page, which is the whole property the reported number needed and lacked.
    """
    was = _f64(before) <= threshold
    still = _f64(after) <= threshold
    return int(np.count_nonzero(was & ~still))


def _extreme_normal(draws: int) -> float:
    """`sqrt(2 ln n)` — the leading term of the expected maximum of `n` standard
    normal draws. Arithmetic, and the only reason an extreme needs its own
    factor: a bounding box is the LARGEST excursion in a profile, never a
    typical one, and a bound set for a typical value is exceeded by definition.

    It sits slightly BELOW the true expected maximum, so every bound built from
    it is a little tight and every box a little large. That is the safe
    direction here: over-including costs a margin, under-including costs a
    document a mark.
    """
    return math.sqrt(2.0 * math.log(draws)) if draws > 1 else 0.0


def _line_profile(intensity: Real, present: Real, axis: int) -> tuple[Real, Real]:
    """Each line's mean intensity, and how many pixels it was taken over.

    `present` is 1 where a pixel came off the document and 0 where this module
    PAINTED it — the corners rotation fills. Those are excluded rather than
    averaged in, because a measurement of a region this module invented is a
    measurement of something that never happened (Law 24), and because it is
    wrong by exactly enough to matter: measured on a page turned 7 degrees, the
    fill sat at 236 while the contrast-enhanced paper around it sat at 237, so
    every fill-only row read as faint content and the second crop stopped
    cropping — insets of 98 where the content box wanted 4.
    """
    counts = _f64(present.sum(axis=axis))
    totals = _f64((intensity * present).sum(axis=axis))
    return _f64(totals / np.where(counts > 0.0, counts, 1.0)), counts


def _lines_with_content(profile: Real, counts: Real, sigma: float) -> npt.NDArray[np.bool_]:
    """Which rows (or columns) carry a mark, from the profile of their means.

    THIS IS THE TRANSFORM THE CROP NEEDED (Law 53). Asking *"is this PIXEL a
    mark?"* cannot be answered on a real scan: over a million pixels the largest
    noise excursion is enormous, so a box drawn from per-pixel deviations is the
    whole frame — measured, a page of paper at 235 carrying sigma 11.6 gave
    (0, 999, 0, 1299) on a 1000 x 1300 frame whose content occupied
    (280, 689, 260, 1039). Averaged along a line the same noise falls by
    sqrt(1300) to 0.32 grey levels, while a faint 340-pixel GSTIN thirty levels
    down displaces its row's mean by 7.8. Same question, signal-to-noise better
    by the square root of the line's length, and now answerable.

    The paper's own level is the LIGHTEST line — under this module's stated
    polarity, the line carrying least ink is the one closest to bare paper. A
    median was tried and is wrong: on a page padded with a blank border 780 of
    1300 columns carry print, so the median column is a PRINTED one, every blank
    column reads as the deviant, and the crop stops cropping. The lightest line
    cannot be outvoted that way.

    THE ALLOWANCE IS TWICE THE STANDARD ERROR OF A LINE'S MEAN, TIMES
    `_extreme_normal`, AND THE TWO IS ARITHMETIC. The observed maximum sits
    about one such step ABOVE the true paper level, being itself an extreme; a
    blank line sits at most one step BELOW it; their difference is therefore at
    most two, and anything further down carries something the paper cannot
    account for. A line with no unpainted pixels at all has nothing to say and
    is blank.

    ON AN INVERTED SCAN THE LIGHTEST LINE IS A STROKE, so every line of the dark
    field reads as content and nothing is cropped at all. That is the failure
    direction a destructive step is allowed to have: the page comes through
    whole. Polarity is named as an assumption in this module's docstring, and
    this is what the assumption costs when it does not hold.
    """
    measured = counts > 0.0
    if not measured.any():
        return np.zeros(profile.shape, dtype=np.bool_)
    step = sigma / np.sqrt(np.where(measured, counts, 1.0)) * _extreme_normal(int(profile.size))
    lightest = float(np.max(profile[measured]))
    return np.asarray(measured & (lightest - profile > 2.0 * step), dtype=np.bool_)


def _content_box(grey: Image, painted: Image | None = None) -> tuple[int, int, int, int] | None:
    """The rows and columns that carry a mark. `None` when the page is uniform.

    THE RULE THAT DREW THIS BOX IS NOT THE RULE THAT AUDITS IT, and that
    separation is the whole point. `_ink_mask` is DISCRIMINATIVE: Otsu separates
    the darkest mode from the rest, which is right for measuring skew because it
    wants the strongest signal on the page, and wrong for deciding what to
    DELETE because it was never designed to be exhaustive. Driving the crop with
    it took a readable GSTIN off an invoice — 4080 pixels, thirty grey levels
    below the paper, Otsu's split at 30.0 — and then reported full retention,
    because the retention was counted with that same mask (`KNOWN_FAILURES.md`
    D1). A number that cannot take any other value is not a measurement.

    So the box comes from line profiles and `ink_kept_by_crop` is counted with
    the Otsu mask. Two different rules, and neither one marks its own work.

    `painted` names the pixels rotation filled in, and is `None` before any
    geometry has been applied — every pixel is then the document's own.
    """
    if grey.size == 0:
        return None
    sigma = _measure_noise(grey) or 0.0
    intensity = _f64(grey)
    present = (
        _f64(np.ones_like(intensity))
        if painted is None
        else _f64((painted == 0).astype(np.float64))
    )
    row_profile, row_counts = _line_profile(intensity, present, axis=1)
    column_profile, column_counts = _line_profile(intensity, present, axis=0)
    rows = _lines_with_content(row_profile, row_counts, sigma)
    columns = _lines_with_content(column_profile, column_counts, sigma)
    if not rows.any() or not columns.any():
        return None
    marked_rows = np.nonzero(rows)[0]
    marked_columns = np.nonzero(columns)[0]
    return (
        int(marked_rows[0]),
        int(marked_rows[-1]),
        int(marked_columns[0]),
        int(marked_columns[-1]),
    )


def _measure_skew(grey: Image) -> float | None:
    """The rotation, in degrees, that straightens the page. `None` if no ink.

    The angle is folded into (-45, 45] by arithmetic rather than by trusting
    OpenCV's reported range: `minAreaRect` changed its convention at 4.5, and a
    normalisation written for one release is a silent 90-degree error on the
    other. A rectangle's orientation is defined modulo a quarter turn, so
    folding is exact for every convention there could be.
    """
    mask, _threshold = _ink_mask(grey)
    # The ink count, not `findNonZero() is None`: OpenCV's own stubs declare
    # that return non-optional, so a None check reads as dead code to the
    # typechecker while being the live branch every blank page takes.
    if not np.any(mask):
        return None
    folded = float(cv2.minAreaRect(cv2.findNonZero(mask))[2]) % _QUARTER_TURN
    return folded - _QUARTER_TURN if folded > _HALF_QUARTER_TURN else folded


def _measure_noise(grey: Image) -> float | None:
    """Immerkaer's estimator: sigma from the response to a Laplacian-like mask.

    Parameter-free, which is why it is here rather than a filtered-residual
    measure that would need a filter size this module has no authority to pick.
    Border pixels are dropped because `filter2D` invents them by reflection.
    """
    height, width = _extent(grey)
    if height < _MIN_SIDE_FOR_NOISE or width < _MIN_SIDE_FOR_NOISE:
        return None
    response = _f64(cv2.filter2D(grey, cv2.CV_64F, _NOISE_MASK))[1:-1, 1:-1]
    interior = (height - 2) * (width - 2)
    total = float(np.absolute(response).sum())
    return math.sqrt(math.pi / 2.0) * total / (_NOISE_NORMALISER * interior)


def _measure_contrast(grey: Image) -> float | None:
    if grey.size == 0:
        return None
    return float(np.std(_f64(grey)))


def _measure_sharpness(grey: Image) -> float | None:
    """Variance of the Laplacian. Low means blurred, and this module has no
    deblur step — the number exists so `confidence` can see the blur, which is
    §1.1's *"reported as evidence, never repaired by guesswork."*
    """
    height, width = _extent(grey)
    if height < _MIN_SIDE_FOR_NOISE or width < _MIN_SIDE_FOR_NOISE:
        return None
    return float(np.var(_f64(cv2.Laplacian(grey, cv2.CV_64F))))


def _measure_ink_fraction(grey: Image) -> float | None:
    if grey.size == 0:
        return None
    mask, _threshold = _ink_mask(grey)
    return float(np.count_nonzero(mask)) / float(grey.size)


def _border_median(grey: Image) -> float:
    """The paper's own intensity, taken from the four edges.

    Rotation has to fill the corners with something. A constant this module
    chose would be a value invented and painted onto the artifact; replicating
    the edges would smear streaks that `reader` could take for a table rule. The
    measured border median is neither: it is flat, so it is obviously not
    content, and it came off the artifact rather than out of this file.
    """
    edges = np.concatenate(
        [
            _f64(grey[0, :]).ravel(),
            _f64(grey[-1, :]).ravel(),
            _f64(grey[:, 0]).ravel(),
            _f64(grey[:, -1]).ravel(),
        ]
    )
    return float(np.median(edges))


def _composite_over_paper(image: Image) -> Image:
    """Flatten a four-channel page ONTO THE PAGE, rather than dropping alpha.

    `cv2.COLOR_BGRA2GRAY` computes a luma from B, G and R and DISCARDS A. When a
    mark's shape lives in the alpha channel — the ordinary result of a
    background removal, a premultiplied export, a `convert -transparent` — the
    colour channels are zero everywhere and the luma is uniform. Measured: a
    stamp of 40320 visible pixels and a fully transparent canvas both flattened
    to a constant page, standard deviation 0.0, and every measurement reported
    zero loss (`KNOWN_FAILURES.md` D4). Two different documents mapped onto one
    output is the difference between them destroyed, by the NORMALISATION step,
    before any cleaning has happened at all.

    A transparent pixel is not black and it is not "no information": it is the
    page showing through. Compositing over the page is what a renderer does,
    what a printer does and what a human sees, and it is the only reading under
    which the alpha channel carries what it was written to carry.

    `_FULL_SCALE` is the paper composited onto. It is the maximum an 8-bit
    channel holds — arithmetic, not a level chosen here — and it is the one
    value that cannot itself be mistaken for a mark under this module's stated
    polarity assumption. Taking it from the artifact instead would make two
    documents composite differently and destroy the comparison this fix exists
    to restore.
    """
    colour = _f64(cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY))
    opacity = _f64(image[..., _ALPHA_CHANNEL]) / float(_FULL_SCALE)
    composited = colour * opacity + float(_FULL_SCALE) * (1.0 - opacity)
    return _u8(np.rint(composited).astype(np.uint8))


def _to_grey(image: Image) -> Image:
    """Format normalisation. One channel, so every later stage sees one shape.

    NORMALISATION MAY NOT REDUCE THE INFORMATION AVAILABLE — it is the first
    thing that touches the artifact and everything after it reasons from what it
    hands on. Three channels carry their content in luma, so a luma conversion
    keeps it. Four channels carry part of it in opacity, so the fourth is
    composited rather than dropped; see `_composite_over_paper`.
    """
    if image.ndim == _GREY_NDIM:
        return image
    channels = image.shape[2]
    if channels == _BGR_CHANNELS:
        return _u8(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    if channels == _BGRA_CHANNELS:
        return _composite_over_paper(image)
    raise UnusableArtifactError(
        f"an image with {channels} channels is not a document this module can "
        "normalise; one, three and four channel 8-bit images are."
    )


def _receive(image: object, settings: CleanerSettings) -> Image:
    """Check what actually arrived, then narrow it. Every refusal names its cause.

    Typed `object` rather than `Image` on purpose. An annotation is a promise a
    caller can break — untyped callers, deserialised input, a downstream engine
    written later — and with `Image` here the typechecker would rule the dtype
    branch unreachable and the one guard that stops a `float32` array being cast
    into silence would be dead code (§J.6: guarded by construction, not by care).
    """
    received = np.asarray(image)
    if received.dtype != np.uint8:
        raise UnusableArtifactError(
            f"expected an 8-bit (uint8) image, got {received.dtype}. A cast would "
            "change every intensity in the frame; the original is not altered."
        )
    if received.ndim not in (_GREY_NDIM, _COLOUR_NDIM):
        raise UnusableArtifactError(
            f"expected a 2-D or 3-D image, got {received.ndim} dimension(s) with "
            f"shape {received.shape}."
        )
    narrowed: Image = np.asarray(received, dtype=np.uint8)
    height, width = _extent(narrowed)
    smallest = min(height, width)
    if smallest < settings.denoise_search_window:
        raise UnusableArtifactError(
            f"the shorter side is {smallest} pixel(s) and the caller's "
            f"denoise_search_window is {settings.denoise_search_window}; the "
            "search window must fit inside the image. The minimum comes from "
            "the caller's own setting, not from a size this module chose."
        )
    return narrowed


def _rotation(height: int, width: int, degrees: float) -> tuple[Real, int, int]:
    """The affine map that turns an h by w frame, and the canvas it needs.

    Factored out because the PAGE and its CONTENT MASK must move together: two
    copies of this arithmetic would be two chances for the mask to describe a
    geometry the page no longer has (Law 14, Law 19).
    """
    matrix = _f64(cv2.getRotationMatrix2D((width / 2.0, height / 2.0), degrees, 1.0))
    cosine = abs(float(matrix[0, 0]))
    sine = abs(float(matrix[0, 1]))
    grown_width = math.ceil(height * sine + width * cosine)
    grown_height = math.ceil(height * cosine + width * sine)
    matrix[0, 2] += grown_width / 2.0 - width / 2.0
    matrix[1, 2] += grown_height / 2.0 - height / 2.0
    return matrix, grown_width, grown_height


def _shift(across: float, down: float) -> Real:
    """A translation, as the 3x3 that composes by multiplication."""
    return np.array([[1.0, 0.0, across], [0.0, 1.0, down], [0.0, 0.0, 1.0]], dtype=np.float64)


def _composable(affine: Real) -> Real:
    """A 2x3 affine as the 3x3 that composes by multiplication.

    OpenCV's affines are 2x3, which cannot be multiplied together. The bottom
    row of a 3x3 affine is always `(0, 0, 1)`, so adding it changes nothing and
    lets a chain of transforms be composed by `@` rather than by hand-derived
    algebra — which is the difference between a composition a reader can check
    and one they have to re-derive (Law 31).
    """
    return np.vstack([_f64(affine), np.array([[0.0, 0.0, 1.0]], dtype=np.float64)])


def _cleaned_to_source(
    first_crop: tuple[int, int],
    turned_extent: tuple[int, int],
    degrees: float,
    second_crop: tuple[int, int],
) -> tuple[float, float, float, float, float, float]:
    """The whole of `_clean_image`'s geometry, inverted, as one affine.

    `_clean_image` moves a page three times and only three times — crop, turn,
    crop — so going back is those three undone in reverse:

        p_straightened = p_cleaned      + second_crop
        p_trimmed      = rotation^-1 . p_straightened
        p_source       = p_trimmed      + first_crop

    which composes to `shift(first) . rotation^-1 . shift(second)`, read right
    to left. Denoising and CLAHE are absent from it because neither moves a
    pixel; they remap intensities, and that is why the stage order in
    `_clean_image` puts every intensity change before the geometry is set.

    `_rotation` IS THE FUNCTION `_rotate_whole_frame` CALLED, with the same
    extent and the same angle, so the turn is inverted from the arithmetic that
    applied it rather than from a second copy of it. That is the reason
    `_rotation` was factored out in the first place — see its docstring: two
    copies would be two chances to describe a geometry the page no longer has
    (Law 14, Law 19). `cv2.invertAffineTransform` is OpenCV's own inverse of
    OpenCV's own matrix, for the same reason.
    """
    height, width = turned_extent
    matrix, _grown_width, _grown_height = _rotation(height, width, degrees)
    straightened_to_trimmed = _composable(_f64(cv2.invertAffineTransform(matrix)))
    composed = _shift(*first_crop) @ straightened_to_trimmed @ _shift(*second_crop)
    return (
        float(composed[0, 0]),
        float(composed[0, 1]),
        float(composed[0, 2]),
        float(composed[1, 0]),
        float(composed[1, 1]),
        float(composed[1, 2]),
    )


def _rotate_whole_frame(grey: Image, degrees: float, fill: float) -> Image:
    """Rotate onto a canvas grown to hold the rotated frame.

    The growth is what makes the step incapable of losing a pixel: the new
    extent is the exact bounding box of the rotated corners, so nothing can pass
    outside it. `INTER_LINEAR` rather than a cubic kernel because cubic
    interpolation overshoots at a stroke edge and manufactures intensities that
    were never on the page.
    """
    height, width = _extent(grey)
    matrix, grown_width, grown_height = _rotation(height, width, degrees)
    return _u8(
        cv2.warpAffine(
            grey,
            matrix,
            (grown_width, grown_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=fill,
        )
    )


def _crop_to_content(
    grey: Image, margin: int, source: Image | None = None, painted: Image | None = None
) -> tuple[Image, float, tuple[int, int]]:
    """Crop to the content box plus the caller's margin. Report the INK kept,
    AND WHERE THE CROP STARTED.

    The box comes from `_content_box`, which reads line profiles. The retention
    is counted with `_ink_mask`, which reads Otsu. Two different rules, so the
    number can actually move: if the box ever failed to contain a stroke the
    quotient would fall below 1.0 and say so, which the previous form — box and
    audit from the same mask — could not do on any page whatsoever.

    MEASURED, so that "can move" is a number and not a hope (Law 52). A 600x900
    scan carrying sensor noise at sigma 14, its printed body 46800 ink pixels,
    plus a 3x3 mark in the margin 480 rows below the body: the line profile is
    blind to the mark — three ink pixels shift their row's mean by 0.683 grey
    levels against an allowance of 3.338 — so the box excludes it, while Otsu
    splits at 85.0 and counts all nine. Reported: 0.9998077292828302, which is
    46800/46809 to the bit, the mark's exact share of the ink and nothing else.
    The same page with the mark removed reports exactly 1.0, on all fourteen
    seeds tried, so the figure moves for the discard and not for the noise.

    `source` is the same page in the document's own intensities when `grey` has
    been contrast-enhanced, and `grey` itself when it has not; `painted` names
    the pixels rotation filled in. Both exist so the box is drawn from the
    document and never from this module's own handiwork — see `_deskew`.

    A uniform page has no content box, and is returned as it arrived. A blank
    sheet cropped to nothing would read downstream as a document that genuinely
    held nothing.

    THE ORIGIN IS RETURNED BECAUSE IT USED TO BE THROWN AWAY, and that was
    `KNOWN_FAILURES.md` F-030's root cause: `left_kept` and `top_kept` were
    computed on the two lines below, consumed by the slice on the next one, and
    never seen again. A crop is a translation of every coordinate on the page,
    so discarding where it started discards the only record of where the pixels
    that survived it used to be. It is `(left, top)` — the order a coordinate
    is written in, not the order a numpy index is.
    """
    ink, _threshold = _ink_mask(grey)
    total = int(np.count_nonzero(ink))
    box = _content_box(grey if source is None else source, painted)
    if box is None:
        # Returned WHOLE, so the crop that did not happen moved nothing and the
        # origin is the page's own. Reporting the margin here instead would
        # describe an inset the slice below never took.
        return grey, 1.0, (0, 0)
    top, bottom, left, right = box
    rows, columns = _extent(grey)
    top_kept = max(top - margin, 0)
    left_kept = max(left - margin, 0)
    bottom_kept = min(bottom + 1 + margin, rows)
    right_kept = min(right + 1 + margin, columns)
    cropped: Image = grey[top_kept:bottom_kept, left_kept:right_kept]
    origin = (left_kept, top_kept)
    if total == 0:
        return cropped, 1.0, origin
    kept = int(np.count_nonzero(ink[top_kept:bottom_kept, left_kept:right_kept]))
    return cropped, kept / total, origin


def _observe(grey: Image, stage: Stage) -> tuple[QualityObservation, ...]:
    """The four quantities measured identically on both forms.

    Both stages, always, because `CLAUDE.md` Law 52 forbids claiming an
    improvement without a before and an after. Nothing here decides whether a
    value is good: that is `confidence`'s, and `ENGINE_1:109` gives it to no one
    else.
    """
    return (
        QualityObservation(
            name=SKEW_ANGLE,
            stage=stage,
            value=_measure_skew(grey),
            unit=_DEGREES,
            note=(
                "the rotation that straightens the page, from the ink's rotated "
                "bounding box. None when the page carries no ink to orient."
            ),
        ),
        QualityObservation(
            name=NOISE_SIGMA,
            stage=stage,
            value=_measure_noise(grey),
            unit=_GREY_LEVELS,
            note="Immerkaer's estimate of the additive noise standard deviation.",
        ),
        QualityObservation(
            name=RMS_CONTRAST,
            stage=stage,
            value=_measure_contrast(grey),
            unit=_GREY_LEVELS,
            note="root-mean-square contrast: the standard deviation of intensity.",
        ),
        QualityObservation(
            name=LAPLACIAN_VARIANCE,
            stage=stage,
            value=_measure_sharpness(grey),
            unit="grey levels squared",
            note=(
                "variance of the Laplacian. A low value is a blurred artifact, "
                "which this module reports and does not attempt to repair."
            ),
        ),
        QualityObservation(
            name=INK_FRACTION,
            stage=stage,
            value=_measure_ink_fraction(grey),
            unit="fraction of pixels",
            note="pixels darker than the artifact's own Otsu split, as a fraction.",
        ),
    )


def _painted_by(grey: Image, degrees: float) -> Image:
    """WHICH pixels the rotation filled in, as against which came off the page.

    A frame of ones put through the identical transform: everything that lands
    outside it is fill this module painted. Nearest-neighbour, because this is a
    membership and interpolating one produces pixels that are partly document.

    It exists so that no later measurement averages in a region that is not on
    any document — see `_line_profile`.
    """
    height, width = _extent(grey)
    matrix, grown_width, grown_height = _rotation(height, width, degrees)
    frame: Image = np.full((height, width), _FULL_SCALE, dtype=np.uint8)
    inside = _u8(
        cv2.warpAffine(
            frame,
            matrix,
            (grown_width, grown_height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        )
    )
    return _u8((inside == 0).astype(np.uint8) * _FULL_SCALE)


def _deskew(
    grey: Image, carried: Image, settings: CleanerSettings
) -> tuple[Image, Image, Image | None, QualityObservation, QualityObservation]:
    """Straighten, or refuse and say which setting refused.

    Returns the rotation actually applied, the fill intensity actually used, and
    WHICH PIXELS that fill went into — `None` on both refusal paths, because a
    page that was not turned has no painted region and every pixel on it is the
    document's own. The fill is reported from here rather than from the caller
    so the reported number is the number that was painted into the corners; a
    fill reported from a different form of the page would be a measurement of
    something that never happened (Law 24).

    `carried` is the SAME PAGE BEFORE THE CONTRAST STAGE, put through the
    identical turn so the next crop has the document's own intensities to draw
    its box from. It exists because CLAHE varies the paper SPATIALLY: measured
    on a page turned 7 degrees, the enhanced paper stood at 237.05 in the middle
    of the frame and 235.03 at its corner, a 2.0 grey level swing that is not
    noise and that a bound calibrated on noise reads as a faint mark on every
    outer row. The crop then kept the whole fill — insets of 98 where the box
    wanted 4. The content box is a property of the DOCUMENT, so it is measured
    on the document's own intensities and never on an enhanced view of them.
    """
    fill = _border_median(grey)
    filled = QualityObservation(
        name=DESKEW_FILL_INTENSITY,
        stage=Stage.CLEANED,
        value=fill,
        unit=_GREY_LEVELS,
        note=(
            "the intensity rotation fills its corners with, taken as the median "
            "of the border of the page this stage received rather than chosen here."
        ),
    )
    measured = _measure_skew(grey)
    if measured is None:
        return (
            grey,
            carried,
            None,
            QualityObservation(
                name=DESKEW_APPLIED,
                stage=Stage.CLEANED,
                value=0.0,
                unit=_DEGREES,
                note="no rotation: the page carries no ink, so no skew is measurable.",
            ),
            filled,
        )
    if abs(measured) > settings.max_deskew_degrees:
        return (
            grey,
            carried,
            None,
            QualityObservation(
                name=DESKEW_APPLIED,
                stage=Stage.CLEANED,
                value=0.0,
                unit=_DEGREES,
                note=(
                    f"no rotation: the measured skew {measured:.4f} degrees exceeds "
                    f"max_deskew_degrees ({settings.max_deskew_degrees}). The page is "
                    "left as received rather than turned on a reading that far out."
                ),
            ),
            filled,
        )
    return (
        _rotate_whole_frame(grey, measured, fill),
        _rotate_whole_frame(carried, measured, _border_median(carried)),
        _painted_by(grey, measured),
        QualityObservation(
            name=DESKEW_APPLIED,
            stage=Stage.CLEANED,
            value=measured,
            unit=_DEGREES,
            note="rotation applied onto a canvas grown to hold the whole rotated frame.",
        ),
        filled,
    )


def decode(data: bytes) -> Image:
    """Bytes to pixels. Format normalisation, and the one place bytes enter.

    `IMREAD_UNCHANGED`, then an 8-bit check, so nothing is downconverted behind
    the caller's back. Raises rather than returning a blank page: a blank page
    would reach `reader` as a document that legitimately has nothing on it.
    """
    if not data:
        raise UndecodableArtifactError("no bytes were supplied; there is nothing to decode.")
    buffer = np.frombuffer(data, dtype=np.uint8)
    decoded = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise UndecodableArtifactError(
            f"the {len(data)} byte(s) supplied are not a decodable image. Reported "
            "rather than replaced by a blank page, which would read as a document "
            "that genuinely had nothing on it."
        )
    return _u8(decoded)


def replace_artifact(document: CleanedDocument, artifact: CleanedArtifact) -> CleanedDocument:
    """A copy of `document` carrying `artifact`. Nothing measured is touched.

    FIELD BY FIELD, so a field added to `CleanedDocument` and forgotten here is
    silently emptied on every path that produces an artifact — which is every
    path a consumer ever sees. `source_geometry` is carried for that reason and
    `test_the_geometry_survives_the_copy_that_attaches_the_artifact` is what
    notices if the next field is not.
    """
    return CleanedDocument(
        original=document.original,
        cleaned=document.cleaned,
        quality_observations=document.quality_observations,
        preservation_status=document.preservation_status,
        artifact=artifact,
        source_geometry=document.source_geometry,
    )


def _encode_png(image: Image) -> bytes:
    """Lossless, deliberately. A lossy re-encode would lose information that
    the original had, which is the one thing cleaning may never do."""
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise UndecodableArtifactError(
            "the cleaned image could not be re-encoded. Reported rather than "
            "silently returning the original, which would claim a cleaning that "
            "never happened."
        )
    return bytes(buffer.tobytes())


def _pdf_has_text_layer(data: bytes) -> bool:
    """True when any page carries embedded text. Measured, never assumed."""
    document = open_pdf(data)
    try:
        return any(plain_text(document, index).strip() for index in range(page_count(document)))
    finally:
        close_pdf(document)


def _clean_pdf(data: bytes, settings: CleanerSettings, *, render_dpi: int) -> CleanedDocument:
    """A PDF in, a PDF out — always. The text layer decides how.

    THE PDF CLEANER, as F-017 names it. Registered against `MediaKind.PDF` in
    `CLEANERS` below; nothing calls it by name from outside this module.
    """
    if _pdf_has_text_layer(data):
        return _pdf_passed_through(data)
    return _pdf_rebuilt_from_cleaned_pages(data, settings, render_dpi=render_dpi)


def _pdf_passed_through(data: bytes) -> CleanedDocument:
    """A text-layer PDF, untouched, with the reason recorded as a measurement.

    `original` and `cleaned` are the same single-pixel placeholder because
    there is no raster on this path and inventing one would be a fabricated
    observation (Law 24). Everything a consumer needs is on `artifact`.
    """
    placeholder: Image = np.zeros((1, 1), dtype=np.uint8)
    observation = QualityObservation(
        name="text_layer_present",
        stage=Stage.ORIGINAL,
        value=1.0,
        unit="boolean",
        note=(
            "the PDF carries an embedded text layer, so its characters are already "
            "exact. Deskewing or denoising would mean rasterising them into pixels, "
            "which destroys the text layer and loses information cleaning may never "
            "lose. Passed through unchanged."
        ),
    )
    return CleanedDocument(
        original=placeholder,
        cleaned=placeholder,
        quality_observations=(observation,),
        preservation_status=PreservationStatus.ORIGINAL_IS_SAFER,
        artifact=CleanedArtifact(kind=MediaKind.PDF, payload=data, original=data, raster=None),
    )


def _every_page_reported(per_page: list[CleanedDocument]) -> CleanedDocument:
    """One `CleanedDocument` carrying EVERY page's evidence, not page one's.

    The raster stays page one's, because `CleanedDocument` holds exactly one
    array and the rebuilt PDF payload is where all the pages live. What changes
    is that no page's measurements are dropped and no page's damage is voted
    down: `page` on each observation says which sheet it describes, and the
    status is the worst any page reported.
    """
    combined: list[QualityObservation] = []
    placed: list[SourceGeometry] = []
    for number, document in enumerate(per_page, start=1):
        for observation in document.quality_observations:
            combined.append(
                QualityObservation(
                    name=observation.name,
                    stage=observation.stage,
                    value=observation.value,
                    unit=observation.unit,
                    note=observation.note,
                    page=number,
                )
            )
        # STAMPED THE SAME WAY THE OBSERVATIONS ARE, because the geometry has
        # D3's exact shape and a worse consequence: every page of a scan is
        # cropped and turned differently, so page one's map placed on page
        # three's coordinates is not an approximation of page three's answer —
        # it is page one's, applied to the wrong page.
        for geometry in document.source_geometry:
            placed.append(
                SourceGeometry(
                    to_source=geometry.to_source,
                    source_height=geometry.source_height,
                    source_width=geometry.source_width,
                    render_dpi=geometry.render_dpi,
                    page=number,
                )
            )
    damaged = any(
        document.preservation_status is PreservationStatus.ORIGINAL_IS_SAFER
        for document in per_page
    )
    first = per_page[0]
    return CleanedDocument(
        original=first.original,
        cleaned=first.cleaned,
        quality_observations=tuple(combined),
        preservation_status=(
            PreservationStatus.ORIGINAL_IS_SAFER if damaged else PreservationStatus.CLEANED_IS_SAFER
        ),
        artifact=first.artifact,
        source_geometry=tuple(placed),
    )


def _pdf_rebuilt_from_cleaned_pages(
    data: bytes, settings: CleanerSettings, *, render_dpi: int
) -> CleanedDocument:
    """A scanned PDF: every page rasterised, cleaned, and rebuilt into a PDF.

    Information is not lost by rasterising here, because there was never
    anything but pixels to begin with — that is what "no text layer" means.
    The output stays a PDF so the pipeline has one shape for every input.

    EVERY PAGE CONTRIBUTES EVIDENCE, AND THE ANSWER IS THE WORST OF THEM.
        This used to clean every page and then keep page one's measurements and
        page one's `preservation_status`, discarding the rest. Measured at
        strength 40, tolerance 0.10, 100 dpi: a thick page then a hairline page
        reported ink lost 0.0043 and *"cleaned is safer"*; THE SAME TWO PAGES IN
        THE OPPOSITE ORDER reported 0.6389 and *"the original is safer."* Both
        rebuilt PDFs contained both damaged pages — only the evidence about them
        moved. A quality that changes with the page ORDER is a measurement of
        the wrong thing (`KNOWN_FAILURES.md` D3).

        So every page's observations are carried, each stamped with the page it
        came from, and the document's status is `ORIGINAL_IS_SAFER` the moment
        ANY page says so. `ENGINE_1:457` is about damage, not about averages: a
        decimal point erased on page nine is not made safe by eight clean pages,
        and `confidence` — the only component allowed to turn these signals into
        a score (`ENGINE_1:109`) — cannot account for a page that emits nothing.
    """
    source = open_pdf(data)
    cleaned_pages: list[Image] = []
    per_page: list[CleanedDocument] = []
    try:
        for index in range(page_count(source)):
            rendered = render_page_png(source, index, dpi=render_dpi)
            # `render_dpi` REACHES THE GEOMETRY, not just the rasteriser. These
            # pixels exist only because this line rendered them at this
            # resolution, so it is the exact conversion from a source pixel
            # back to the point space the PDF page is measured in — and
            # without it a coordinate mapped at 150 dpi and the same
            # coordinate mapped at 300 dpi are different units that cannot be
            # compared (`KNOWN_FAILURES.md` F-030).
            document = _clean_image(decode(rendered), settings, render_dpi=render_dpi)
            cleaned_pages.append(document.cleaned)
            per_page.append(document)
    finally:
        close_pdf(source)

    if not per_page:
        raise UndecodableArtifactError(
            "the PDF reports zero pages. Reported rather than returned as a blank "
            "document, which would read as a page that genuinely held nothing."
        )
    first = _every_page_reported(per_page)

    # IN THE ORDER THE PAGES CAME OFF THE SOURCE, never sorted. `cleaned_pages`
    # is appended to inside the loop above, so page n of the rebuilt PDF is the
    # cleaned page n of the original — the property F-017 requires and the one a
    # rebuild is most likely to lose.
    # `dpi=render_dpi` IS THE F-028 FIX AT ITS CALL SITE. These pages were
    # rasterised at `render_dpi` a few lines above; handing the pixels on
    # without saying so let the backend infer 96 and resize every page by
    # `render_dpi / 96`. The DPI was known here the whole time.
    payload = pdf_of_page_images([_encode_png(page) for page in cleaned_pages], dpi=render_dpi)

    return replace_artifact(
        first,
        CleanedArtifact(kind=MediaKind.PDF, payload=payload, original=data, raster=first.cleaned),
    )


def _clean_image(
    image: Image, settings: CleanerSettings, *, render_dpi: int | None = None
) -> CleanedDocument:
    """THE IMAGE CLEANER. Improve the pixels' physical quality; change nothing
    they contain.

    PRIVATE SINCE F-017, AND THAT IS THE POINT OF THIS NAME. It was `clean`,
    public, and it was a SECOND ENTRY POINT into this module: it took an
    `NDArray` and returned a `CleanedDocument` with no `artifact` on it, so a
    caller who reached it directly got an object `pipeline._payload_of` refuses
    and `reader`/`parser` cannot consume. Nothing in `src/` ever called it —
    measured: zero call sites outside this file, against sixty-seven in
    `tests/` — so it was a door kept open by its own tests and by nothing else.

    F-017's ruling is *"Remove every legacy bypass and duplicate path."* The
    coverage those sixty-seven tests bought is not a bypass and was not
    removed: each one still runs, either through `clean_artifact` (the single
    entry point) or against this function under its private name, which is
    what it now is — one of the implementations `CLEANERS` dispatches to, and
    the one `_clean_image_document` and `_pdf_rebuilt_from_cleaned_pages` both
    call for the pixels of a single page.

    The order is normalise, measure, denoise, crop, contrast, deskew, crop.
    Denoising is first so every later stage sees a page whose strokes are
    intact. GEOMETRY IS LAST, and that placement is the whole of this function's
    accuracy — see below. The second crop is the same operation as the first,
    re-applied because rotation grows the canvas to hold the rotated frame.

    NO STAGE MAY REMAP INTENSITIES AFTER THE GEOMETRY IS SET.
        Rotation resamples, so a stroke edge that was a step from ink to paper
        becomes a ramp one or two pixels wide, carrying intermediate intensities.
        Otsu's split — the split every downstream reader will take — sits at the
        midpoint of the ink and paper modes, which is exactly where a linear
        blend of ink and paper lands. The ramp therefore piles up ON the split,
        by construction rather than by accident: measured at a 32 degree skew,
        4.27% of the ink sat within three grey levels of it.

        CLAHE is a SPATIALLY VARYING map — a different transfer curve per tile.
        Run after the rotation, it moves those balanced-on-the-split pixels
        across it by different amounts in different parts of the page, so the
        ink boundary shifts NON-UNIFORMLY and the page's principal axis turns.
        Measured: 2827 ink pixels reclassified at 32 degrees, and a straightened
        page read as 0.0496 degrees out when the rotation had left it 0.0084
        degrees out. A uniform shift would have been harmless — dilating a shape
        does not rotate it — and it is the per-tile variation that is not.

        With contrast moved ahead of the rotation nothing touches an intensity
        afterwards, so the output's ink boundary is whatever the rotation's own
        symmetric ramp put there. Measured across 50 injected skews from 0.25 to
        44 degrees, worst residual falls from 0.0740 to 0.0224 degrees.

    The skew is measured on the artifact AS RECEIVED, not on the denoised
    intermediate. A more robust estimate is available from the denoised form,
    and reporting it would describe something this module produced rather than
    the document it was given — and what Engine 1 reports is what it observed.

    THE CONTENT MASK IS TAKEN ONCE AND CARRIED, AND IT IS WHY THE CROP IS SAFE.
        It is computed on the artifact as received, before any stage of this
        function has touched an intensity, and it is then moved through exactly
        the geometry the page is moved through. Both crops read it and nothing
        else. A page that arrives with a mark on it therefore cannot be cropped
        past that mark, whatever a threshold would have said about how dark it
        was — the defect this replaced took a readable GSTIN off an invoice and
        reported full retention, twice over, because the audit consulted the
        rule that drew the box (`_content_mask`, `_crop_to_content`).

    WHAT IS AUDITED WITH WHAT, BECAUSE THAT IS THE PART THAT WENT WRONG.
        `ink_kept_by_crop` is counted at Otsu's split while the box it audits is
        drawn from the line profiles, so it marks work it did not do and is free
        to fall — measured 0.9998077292828302 on a noisy scan whose nine-pixel
        margin mark the crop discarded, and exactly 1.0 on the same scan without
        the mark. `ink_lost_to_denoise` is measured at the Otsu split taken from
        the artifact as received — the rule the denoise did not consult — as a
        SET DIFFERENCE, so a stroke destroyed cannot be cancelled by ink gained
        elsewhere. Neither figure marks its own work.

        NEITHER OF THE TWO IS 1.0 BY CONSTRUCTION, and an earlier form of this
        docstring said the first one was. That was false, and saying it was
        worse than the error itself: a reader told a number is a constant stops
        reading it, and this is the number that reports a mark the crop threw
        away. A guarantee described as unbreakable is a guarantee nobody checks.

        A THIRD FIGURE, `content_kept`, USED TO SIT HERE AND HAS BEEN DELETED.
        It counted pixels departing from the page's median by more than the
        page's own noise. Denoising collapses that noise and so collapses the
        bound, which made the count rise as the page was smoothed — measured
        above 1.0 in 162 of 189 page-and-setting combinations, peaking at 36.99,
        and reading between 15.04 and 18.09 on runs where every mark had in fact
        been erased. It never once fell for a real loss. It is deleted rather
        than repaired because the quantity it divided was not conserved by the
        stages it spanned, which is a defect of the question and not of the
        arithmetic (Law 24, Law 49).

    WHERE THE CLEANED PIXELS CAME FROM IS NOW RECORDED (`KNOWN_FAILURES.md`
    F-030). Exactly three stages below move a pixel — the crop, the turn and
    the second crop — and every one of them used to compute its geometry, use
    it, and discard it. `_cleaned_to_source` composes the three into one affine
    and `SourceGeometry` carries it, so a coordinate on the page this function
    returns can be placed on the page it was handed.

    `render_dpi` DEFAULTS TO `None`, AND THAT IS NOT A NUMBER LEFT UNCHOSEN.
    Every field of `CleanerSettings` is required because each is an operating
    point (Law 52); this is not one. It says whether THIS MODULE rasterised
    these pixels from a page, and for an array handed straight in the answer is
    no — the pixels arrived at whatever resolution the capture had, and they
    are already the document's own space. `_pdf_rebuilt_from_cleaned_pages`
    passes the resolution it actually rendered at; nothing else has one to
    pass.
    """
    received = _receive(image, settings)
    grey = _to_grey(received)

    before = _observe(grey, Stage.ORIGINAL)
    _mask, split = _ink_mask(grey)
    ink_before = _ink_at(grey, split)

    denoised = _u8(
        cv2.fastNlMeansDenoising(
            grey,
            None,
            settings.denoise_strength,
            settings.denoise_template_window,
            settings.denoise_search_window,
        )
    )
    ink_after = _ink_at(denoised, split)
    erased = _ink_erased(grey, denoised, split)
    lost = 0.0 if ink_before == 0 else erased / ink_before

    trimmed, kept_by_first_crop, first_crop = _crop_to_content(
        denoised, settings.crop_margin_pixels
    )
    contrasted = _u8(
        cv2.createCLAHE(
            clipLimit=settings.contrast_clip_limit,
            tileGridSize=(settings.contrast_tile_grid, settings.contrast_tile_grid),
        ).apply(trimmed)
    )
    straightened, straight_source, painted, rotation, filled = _deskew(
        contrasted, trimmed, settings
    )
    cleaned, kept_by_second_crop, second_crop = _crop_to_content(
        straightened, settings.crop_margin_pixels, straight_source, painted
    )
    # THE ANGLE IS READ FROM THE MEASUREMENT THAT REPORTS IT, not passed
    # alongside it, so the turn this map undoes and the turn the artifact
    # claims are the same number by construction — a report that drifted from
    # what was done would break the map loudly instead of describing a page
    # that does not exist. `_deskew` sets a float on all three of its branches;
    # `None` is unreachable and would mean "no rotation", which is 0.0, so the
    # fallback is the right answer on every path that could reach it rather
    # than a guess (Law 25).
    turned = rotation.value or 0.0
    source_height, source_width = _extent(grey)
    # Each crop's box is drawn from the line profiles and audited with the Otsu
    # mask, so neither factor is 1.0 by algebra; the product is the ink that
    # survived the pair of them.
    retained = kept_by_first_crop * kept_by_second_crop

    observations = (
        *before,
        *_observe(cleaned, Stage.CLEANED),
        rotation,
        filled,
        QualityObservation(
            name=INK_LOST_TO_DENOISE,
            stage=Stage.CLEANED,
            value=lost,
            unit="fraction of original ink",
            note=(
                f"{ink_before} ink pixel(s) before denoising, {ink_after} after, "
                "counted at the single split taken from the artifact as received. "
                f"{erased} of them stopped being ink; that SET DIFFERENCE is the "
                "reported figure, because a net of the two counts lets ink gained "
                "in one region cancel a stroke destroyed in another. Denoising is "
                "the one step that can erase a stroke."
            ),
        ),
        QualityObservation(
            name=INK_KEPT_BY_CROP,
            stage=Stage.CLEANED,
            value=retained,
            unit="fraction of ink pixels",
            note=(
                "the ink inside both crops over the ink on the page, counted at "
                "Otsu's split while the boxes were drawn from the line profiles. "
                "Two different rules, so this AUDITS the boxes instead of "
                "restating them, and it is NOT 1.0 by construction — measured "
                "0.9998077292828302 on a noisy scan whose 3x3 margin mark the "
                "crop discarded, which is exactly that mark's share of the ink, "
                "against exactly 1.0 on the same scan without it. Below 1.0 "
                "means a mark Otsu called ink was thrown away."
            ),
        ),
    )

    safer = (
        PreservationStatus.ORIGINAL_IS_SAFER
        if lost > settings.max_ink_loss_fraction or retained < 1.0
        else PreservationStatus.CLEANED_IS_SAFER
    )
    return CleanedDocument(
        original=received,
        cleaned=cleaned,
        quality_observations=observations,
        preservation_status=safer,
        source_geometry=(
            SourceGeometry(
                to_source=_cleaned_to_source(first_crop, _extent(contrasted), turned, second_crop),
                source_height=source_height,
                source_width=source_width,
                render_dpi=render_dpi,
            ),
        ),
    )


class MediaCleaner(Protocol):
    """What every per-kind cleaner IS: bytes in, a `CleanedDocument` out.

    One signature for every media kind, so the dispatcher below needs to know
    nothing about which kind it is calling. `render_dpi` is passed to all of
    them, including those that never rasterise: a cleaner that ignores it
    ignores it, and a signature that varied per kind would put a branch back
    into the dispatcher, which is the whole thing being removed.
    """

    def __call__(
        self, data: bytes, settings: CleanerSettings, *, render_dpi: int
    ) -> CleanedDocument: ...


def _clean_image_document(
    data: bytes, settings: CleanerSettings, *, render_dpi: int
) -> CleanedDocument:
    """THE IMAGE CLEANER. Decode, clean the pixels, re-encode losslessly.

    `render_dpi` is accepted and unused: an image arrives already rasterised at
    whatever resolution it was captured at, so there is nothing to render. It is
    in the signature because `MediaCleaner` is one signature for every kind —
    see that Protocol for why that matters.
    """
    del render_dpi
    document = _clean_image(decode(data), settings)
    return replace_artifact(
        document,
        CleanedArtifact(
            kind=MediaKind.IMAGE,
            payload=_encode_png(document.cleaned),
            original=data,
            raster=document.cleaned,
        ),
    )


#: WHICH IMPLEMENTATION CLEANS WHICH KIND. The whole of the dispatcher's
#: knowledge, as data.
#:
#: F-017's ruling is *"a media-agnostic Document Cleaner as the single entry
#: point for all supported document types. Internally it may dispatch to Image
#: Cleaner, PDF Cleaner, Excel Cleaner, Email Cleaner, future cleaners."* This
#: table is that dispatch, and it is a table rather than a chain of `if kind is
#: ...` so that adding Excel later is a `MediaKind` member plus one entry here
#: and NOTHING ELSE — `clean_artifact` below contains no branch on kind at all.
#:
#: `MappingProxyType` because a registry anything could mutate is a registry
#: that can be changed from under a running pipeline. A caller that needs a
#: different table passes one to `clean_artifact`; it never edits this one.
#:
#: NEITHER EXCEL NOR EMAIL IS IMPLEMENTED HERE. F-017 names them as future
#: cleaners and `CLAUDE.md` Law 16 forbids building outside the current
#: mission. What this change owes them is a seam, and the seam is proved by a
#: test that registers a kind this module has never heard of and shows dispatch
#: reaches it without a line of this file changing.
CLEANERS: Mapping[MediaKind, MediaCleaner] = MappingProxyType(
    {
        MediaKind.IMAGE: _clean_image_document,
        MediaKind.PDF: _clean_pdf,
    }
)


class NoCleanerRegisteredError(LookupError):
    """A media kind with no implementation behind it.

    DELIBERATELY NOT AN `UnusableArtifactError`, and the distinction is the same
    one `reader.RecognitionFailedError` draws. `UnusableArtifactError` is a
    verdict about the DOCUMENT, and `pipeline.BUSINESS_FAILURE` turns it into an
    artifact that records *"this document could not be read."* A kind nobody
    registered is a verdict about THIS ENGINE — the user's file may be perfect —
    so saying otherwise would assert something false about their document, which
    `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids outright.
    """


def clean_artifact(
    data: bytes,
    kind: MediaKind,
    settings: CleanerSettings,
    *,
    render_dpi: int,
    cleaners: Mapping[MediaKind, MediaCleaner] = CLEANERS,
) -> CleanedDocument:
    """THE DOCUMENT CLEANER — the one entry point, for every supported kind.

    F-017, approved by the owner 2026-08-06: *"Implement a media-agnostic
    Document Cleaner as the single entry point for all supported document
    types... Reader, Parser, Pipeline, Assembly, Validation and all downstream
    modules must consume the Document Cleaner output. Remove every legacy
    bypass and duplicate path."* This function is that entry point, and
    `_clean_image` — which used to be the public `clean` — is now one of the
    implementations it dispatches to rather than a second door into the module.

        IMAGE                 decode, clean the pixels, re-encode as an image
        PDF with a text layer PASS THROUGH UNTOUCHED, and say so
        PDF without one       rasterise each page, clean, rebuild a PDF

    THERE IS NO BRANCH ON `kind` IN THIS FUNCTION. The mapping is `CLEANERS`
    above; this looks the kind up and calls what it finds. That is what makes
    "adding Excel is a member plus an implementation" true rather than merely
    intended, and it is what
    `test_input_engine_cleaner.py::test_a_kind_this_module_has_never_heard_of_
    dispatches_without_the_dispatcher_changing` checks by registering a kind
    that does not exist.

    WHY A TEXT-LAYER PDF IS NOT CLEANED, which looks like a gap and is the
    opposite. `cleaner` owns *"deskewing, rotation, denoising, cropping,
    contrast"* — every one of them a defect of a PHOTOGRAPH. A
    digitally-generated PDF has none of them: its characters are already
    exact. Rasterising it to apply a deskew would replace exact characters with
    pixels and destroy the text layer, which is the single thing that lets it
    be read with no recognition and no confidence loss at all.

    §1.1 forbids exactly that: cleaner *"cannot discard content"* and
    *"alters presentation only"*. Passing through is not the absence of
    cleaning; it is the correct cleaning of a document with no physical defect,
    and `preservation_status` records which basis is safer either way.

    `render_dpi` is the caller's, with no default, for the same reason
    `reader.read` demands it: no document in this repository states one, and
    choosing here would answer a question put to the owner (Law 52).

    `cleaners` defaults to the registry above and exists so a caller can supply
    a different table WITHOUT this module being edited. It is not a mock seam:
    every value in it is a real `MediaCleaner` run for real, which is why the
    extensibility test is a proof about dispatch rather than about a stand-in
    (`CLAUDE.md` §J.6).
    """
    if not data:
        raise UndecodableArtifactError("no bytes were supplied; there is nothing to clean.")

    try:
        media_cleaner = cleaners[kind]
    except KeyError as missing:
        raise NoCleanerRegisteredError(
            f"no cleaner is registered for media kind {kind!r}. Registered: "
            f"{sorted(str(known) for known in cleaners)}. Refused rather than "
            "falling back to another kind's implementation, which would clean "
            "the document as something it is not."
        ) from missing

    return media_cleaner(data, settings, render_dpi=render_dpi)
