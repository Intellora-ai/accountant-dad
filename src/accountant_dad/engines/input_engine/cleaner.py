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

    What is measured against it is INK LOST TO DENOISING — the ink pixels
    present before the denoise step and absent after it, counted with the single
    threshold computed from the artifact as received. Denoising is the one step
    that can erase a stroke; the hairline of a decimal point is exactly what a
    strong filter removes, and a decimal point removed is a financial
    misstatement. Rotation cannot lose a pixel because the canvas is grown to
    hold the whole rotated frame, and neither crop can lose one because each box
    is the bounding box of all the ink — both are structural, and both are
    measured anyway rather than asserted.

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

import importlib
import math
from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np
import numpy.typing as npt

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


class ImpossibleSettingError(ValueError):
    """A setting OpenCV or arithmetic cannot honour. Raised at construction."""


class UnusableArtifactError(ValueError):
    """An artifact this module cannot clean without changing what it contains."""


class UndecodableArtifactError(UnusableArtifactError):
    """Bytes that are not a decodable image. Never a blank page in its place."""


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
    raster: Image | None = None

    def with_raster(self, raster: Image) -> CleanedArtifact:
        """A copy carrying a rendered view. The payload is never touched."""
        return CleanedArtifact(
            kind=self.kind, payload=self.payload, original=self.original, raster=raster
        )


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

    def observed(self, name: str, stage: Stage) -> QualityObservation:
        """The measurement, or `KeyError`. A miss is never a `None` in disguise."""
        for observation in self.quality_observations:
            if observation.name == name and observation.stage is stage:
                return observation
        raise KeyError(f"no measurement named {name!r} was taken on the {stage} form")


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


def _to_grey(image: Image) -> Image:
    """Format normalisation. One channel, so every later stage sees one shape."""
    if image.ndim == _GREY_NDIM:
        return image
    channels = image.shape[2]
    if channels == _BGR_CHANNELS:
        return _u8(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    if channels == _BGRA_CHANNELS:
        return _u8(cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY))
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


def _rotate_whole_frame(grey: Image, degrees: float, fill: float) -> Image:
    """Rotate onto a canvas grown to hold the rotated frame.

    The growth is what makes the step incapable of losing a pixel: the new
    extent is the exact bounding box of the rotated corners, so nothing can pass
    outside it. `INTER_LINEAR` rather than a cubic kernel because cubic
    interpolation overshoots at a stroke edge and manufactures intensities that
    were never on the page.
    """
    height, width = _extent(grey)
    matrix = _f64(cv2.getRotationMatrix2D((width / 2.0, height / 2.0), degrees, 1.0))
    cosine = abs(float(matrix[0, 0]))
    sine = abs(float(matrix[0, 1]))
    grown_width = math.ceil(height * sine + width * cosine)
    grown_height = math.ceil(height * cosine + width * sine)
    matrix[0, 2] += grown_width / 2.0 - width / 2.0
    matrix[1, 2] += grown_height / 2.0 - height / 2.0
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


def _crop_to_ink(grey: Image, margin: int) -> tuple[Image, float]:
    """Crop to the bounding box of ALL the ink, plus the caller's margin.

    The box is the bounding box, so every ink pixel is inside it by
    construction — §1.1 forbids discarding content, and a box chosen any other
    way could. The retention is counted anyway and returned, because a structural
    guarantee nobody measures is a guarantee nobody would notice breaking.
    """
    mask, _threshold = _ink_mask(grey)
    total = int(np.count_nonzero(mask))
    if total == 0:
        return grey, 1.0
    box = cv2.boundingRect(mask)
    left, top, width, height = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))
    rows, columns = _extent(grey)
    top_kept = max(top - margin, 0)
    left_kept = max(left - margin, 0)
    bottom_kept = min(top + height + margin, rows)
    right_kept = min(left + width + margin, columns)
    cropped: Image = grey[top_kept:bottom_kept, left_kept:right_kept]
    kept = int(np.count_nonzero(mask[top_kept:bottom_kept, left_kept:right_kept]))
    return cropped, kept / total


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


def _deskew(
    grey: Image, settings: CleanerSettings
) -> tuple[Image, QualityObservation, QualityObservation]:
    """Straighten, or refuse and say which setting refused.

    Returns the rotation actually applied AND the fill intensity actually used,
    both measured on the page this stage received. The fill is reported from
    here rather than from the caller so the reported number is the number that
    was painted into the corners; a fill reported from a different form of the
    page would be a measurement of something that never happened (Law 24).
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


def clean_artifact(
    data: bytes, kind: MediaKind, settings: CleanerSettings, *, render_dpi: int
) -> CleanedDocument:
    """Clean a document and hand back something that is STILL that kind of document.

    The one entry point every caller should use. `decode` + `clean` remain for
    the raster path they were written for; this is the media-aware form that
    makes a single pipeline possible.

        IMAGE                 rasterise, clean, re-encode as an image
        PDF with a text layer PASS THROUGH UNTOUCHED, and say so
        PDF without one       rasterise each page, clean, rebuild a PDF

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
    """
    if not data:
        raise UndecodableArtifactError("no bytes were supplied; there is nothing to clean.")

    if kind is MediaKind.PDF:
        return _clean_pdf(data, settings, render_dpi=render_dpi)

    image = decode(data)
    document = clean(image, settings)
    payload = _encode_png(document.cleaned)
    return replace_artifact(
        document,
        CleanedArtifact(
            kind=MediaKind.IMAGE, payload=payload, original=data, raster=document.cleaned
        ),
    )


def replace_artifact(document: CleanedDocument, artifact: CleanedArtifact) -> CleanedDocument:
    """A copy of `document` carrying `artifact`. Nothing measured is touched."""
    return CleanedDocument(
        original=document.original,
        cleaned=document.cleaned,
        quality_observations=document.quality_observations,
        preservation_status=document.preservation_status,
        artifact=artifact,
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
    fitz = importlib.import_module("pymupdf")
    document = fitz.open(stream=data, filetype="pdf")
    try:
        return any(document[index].get_text("text").strip() for index in range(document.page_count))
    finally:
        document.close()


def _clean_pdf(data: bytes, settings: CleanerSettings, *, render_dpi: int) -> CleanedDocument:
    """A PDF in, a PDF out — always. The text layer decides how."""
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


def _pdf_rebuilt_from_cleaned_pages(
    data: bytes, settings: CleanerSettings, *, render_dpi: int
) -> CleanedDocument:
    """A scanned PDF: every page rasterised, cleaned, and rebuilt into a PDF.

    Information is not lost by rasterising here, because there was never
    anything but pixels to begin with — that is what "no text layer" means.
    The output stays a PDF so the pipeline has one shape for every input.
    """
    fitz = importlib.import_module("pymupdf")
    source = fitz.open(stream=data, filetype="pdf")
    cleaned_pages: list[Image] = []
    first: CleanedDocument | None = None
    try:
        for index in range(source.page_count):
            rendered = source[index].get_pixmap(dpi=render_dpi).tobytes("png")
            document = clean(decode(rendered), settings)
            cleaned_pages.append(document.cleaned)
            if first is None:
                first = document
    finally:
        source.close()

    if first is None:
        raise UndecodableArtifactError(
            "the PDF reports zero pages. Reported rather than returned as a blank "
            "document, which would read as a page that genuinely held nothing."
        )

    rebuilt = fitz.open()
    try:
        for page in cleaned_pages:
            encoded = _encode_png(page)
            image_document = fitz.open(stream=encoded, filetype="png")
            try:
                # `convert_to_pdf` returns BYTES, not a Document, so it has to be
                # reopened before `insert_pdf` will take it. Measured, not
                # assumed: passing the bytes straight in raises
                # `AttributeError: 'bytes' object has no attribute '_graft_id'`.
                as_pdf = fitz.open("pdf", image_document.convert_to_pdf())
                try:
                    rebuilt.insert_pdf(as_pdf)
                finally:
                    as_pdf.close()
            finally:
                image_document.close()
        payload = bytes(rebuilt.tobytes())
    finally:
        rebuilt.close()

    return replace_artifact(
        first,
        CleanedArtifact(kind=MediaKind.PDF, payload=payload, original=data, raster=first.cleaned),
    )


def clean(image: Image, settings: CleanerSettings) -> CleanedDocument:
    """Improve the artifact's physical quality. Change nothing it contains.

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
    lost = 0.0 if ink_before == 0 else (ink_before - ink_after) / ink_before

    trimmed, kept_by_first_crop = _crop_to_ink(denoised, settings.crop_margin_pixels)
    contrasted = _u8(
        cv2.createCLAHE(
            clipLimit=settings.contrast_clip_limit,
            tileGridSize=(settings.contrast_tile_grid, settings.contrast_tile_grid),
        ).apply(trimmed)
    )
    straightened, rotation, filled = _deskew(contrasted, settings)
    cleaned, kept_by_second_crop = _crop_to_ink(straightened, settings.crop_margin_pixels)
    # Both crops are the bounding box of all the ink, so both are 1.0 by
    # construction; the product is what survived the pair of them.
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
                "Denoising is the one step that can erase a stroke."
            ),
        ),
        QualityObservation(
            name=INK_KEPT_BY_CROP,
            stage=Stage.CLEANED,
            value=retained,
            unit="fraction of ink pixels",
            note=(
                "each crop is the bounding box of all the ink, so this is 1.0 by "
                "construction. Counted anyway, across both crops: a guarantee "
                "nobody measures is a guarantee nobody would notice breaking."
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
    )
