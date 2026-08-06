"""The `cleaner` sub-engine, attacked rather than confirmed.

WHAT A PASS HERE IS ALLOWED TO MEAN. Every geometric and photometric assertion
below is checked with an oracle the module under test does not use. `cleaner`
measures skew from a rotated bounding box (`cv2.minAreaRect`); this file
measures it from the second-order central moments of the ink — a different
mathematical route to the same quantity. `cleaner` estimates noise with the
Immerkaer convolution; this file estimates it from the residual against a
median filter. A bug shared between the code and its test is the failure mode
§J.(b) names, and two independent estimators are the only cheap defence.

THE NUMBERS IN THE ASSERTION CONSTANTS WERE MEASURED, NOT CHOSEN. Each carries
the value this suite actually produced, and each bound sits strictly inside it.
None is a threshold the product uses: `cleaner` has no default anywhere, and the
settings below are this file's inputs, not the module's opinions.

THE DIFFERENTIAL TESTS ARE THE ONES THAT CANNOT BE FAKED. Asserting that
contrast rose after cleaning proves nothing on its own — cropping a white margin
raises the standard deviation whether CLAHE ran or not. So contrast and denoise
are each proven by running the SAME image through TWO settings that differ in
exactly one field, which holds every other stage identical and leaves the tested
stage as the only possible cause of the difference.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
from dataclasses import replace
from decimal import Decimal
from types import ModuleType
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt
import pytest
from authored_source import authored_source, authored_tree

from accountant_dad import pdf_backend
from accountant_dad.engines.input_engine import cleaner, reader

Image = npt.NDArray[np.uint8]
Real = npt.NDArray[np.float64]

# ── the fixtures' own constants ───────────────────────────────────────────
# Inputs to the tests, not thresholds of the product. A synthetic page is used
# rather than a real scan so the true skew, the true noise and the true contrast
# are known exactly and a residual can be stated as a number.

PAPER_INTENSITY = 235
INK_INTENSITY = 30
PAGE_HEIGHT = 600
PAGE_WIDTH = 900
FIRST_TEXT_ROW = 80
LAST_TEXT_ROW = 520
TEXT_LINE_PITCH = 40
TEXT_LINE_THICKNESS = 10
TEXT_LEFT = 60
TEXT_RIGHT = 840
PAD = 200

#: The skew the deskew test injects, and the limit the refusal test exceeds.
KNOWN_SKEW_DEGREES = 7.0
BEYOND_THE_LIMIT_DEGREES = 32.0

RNG_SEED = 20260805


def a_page(paper: int = PAPER_INTENSITY, ink: int = INK_INTENSITY) -> Image:
    """A page of horizontal text lines. Wider than tall, so the ink's principal
    axis is unambiguously horizontal and the moments oracle is well-conditioned.
    """
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), paper, dtype=np.uint8)
    for row in range(FIRST_TEXT_ROW, LAST_TEXT_ROW, TEXT_LINE_PITCH):
        sheet[row : row + TEXT_LINE_THICKNESS, TEXT_LEFT:TEXT_RIGHT] = ink
    return sheet


def padded(image: Image) -> Image:
    """Room to rotate into, so the fixture's own turn clips nothing."""
    return _u8(cv2.copyMakeBorder(image, PAD, PAD, PAD, PAD, cv2.BORDER_REPLICATE))


def turned(image: Image, degrees: float) -> Image:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), degrees, 1.0)
    return _u8(
        cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
    )


def with_gaussian_noise(image: Image, sigma: float) -> Image:
    generator = np.random.default_rng(RNG_SEED)
    noise = generator.normal(0.0, sigma, image.shape)
    return _u8(np.clip(image.astype(np.float64) + noise, 0.0, 255.0).astype(np.uint8))


def _png_bytes(image: Image) -> bytes:
    """An array as the PNG bytes an image document actually arrives as.

    Every test below that goes through `clean_artifact` — the single entry
    point — needs bytes rather than an array, and PNG is lossless for the
    8-bit one-, three- and four-channel frames this suite builds, so the
    round trip through it changes no pixel and the assertion still measures
    what it measured when the call took an array directly.
    """
    ok, buffer = cv2.imencode(".png", image)
    assert ok, "the fixture image could not be encoded; the test would prove nothing"
    return bytes(buffer.tobytes())


#: How many pages the page-order fixture carries. Three is the smallest count
#: that can distinguish "in order" from "reversed" AND from "rotated by one",
#: which two pages cannot.
PAGES_IN_THE_ORDER_FIXTURE = 3

#: The DPI `clean_artifact` is given wherever a test reaches the single entry
#: point. Reused from this file's own existing artifact-path tests rather than
#: chosen: an image path never rasterises, so the value cannot change any
#: result here, and inventing a second one would imply it could (Law 52).
RENDER_DPI = 150


def _u8(array: object) -> Image:
    return np.asarray(array, dtype=np.uint8)


def _f64(array: object) -> Real:
    return np.asarray(array, dtype=np.float64)


# ── oracles the module under test does not use ────────────────────────────


def orientation_degrees(image: Image) -> float | None:
    """Skew from the ink's second-order central moments.

    `cleaner` uses `cv2.minAreaRect`. This is the principal-axis route, and the
    sign convention is calibrated by `test_the_moments_oracle_reads_a_known_turn`
    below — an oracle nobody checked is not an oracle.
    """
    _threshold, mask = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    moments = cv2.moments(_u8(mask), binaryImage=True)
    if moments["m00"] == 0:
        return None
    mu20 = moments["mu20"] / moments["m00"]
    mu02 = moments["mu02"] / moments["m00"]
    mu11 = moments["mu11"] / moments["m00"]
    return math.degrees(0.5 * math.atan2(2.0 * mu11, mu20 - mu02))


def median_residual_sigma(image: Image) -> float:
    """Noise as the spread of what a 3x3 median filter removes.

    `cleaner` uses the Immerkaer Laplacian estimator, which is a different
    formula reading a different property of the same signal.
    """
    smoothed = _f64(cv2.medianBlur(image, 3))
    return float(np.std(_f64(image) - smoothed))


def rms_contrast(image: Image) -> float:
    return float(np.std(_f64(image)))


def ink_pixels(image: Image) -> int:
    _threshold, mask = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return int(np.count_nonzero(_u8(mask)))


# ── the settings every test supplies in full ──────────────────────────────
# `CleanerSettings` has no default for any field, so this block is unavoidable
# and that is the point: no number reaches OpenCV that a caller did not choose.

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

# ── bounds, every one of them measured by this suite ──────────────────────

#: Measured residual after deskewing a 7.000 deg turn: 0.011 deg.
MAX_RESIDUAL_SKEW_DEGREES = 0.05
#: Measured skew of the untouched synthetic page: 0.000 deg.
MAX_SKEW_OF_A_STRAIGHT_PAGE = 0.05
#: Measured ink lost by the baseline settings: 0.0000 of the ink.
MAX_BASELINE_INK_LOSS = 0.005
#: Strength that visibly erases one-pixel strokes. An input, not a threshold.
ERASING_DENOISE_STRENGTH = 90.0
GENTLE_DENOISE_STRENGTH = 3.0
STRONG_DENOISE_STRENGTH = 30.0
LOW_CLIP_LIMIT = 0.5
HIGH_CLIP_LIMIT = 40.0
INJECTED_NOISE_SIGMA = 12.0
FULL_RETENTION = 1.0
#: A cleaned page is single-channel. Named so the assertion is not a bare 2.
ONE_CHANNEL_NDIM = 2


def settings(**changes: float | int) -> cleaner.CleanerSettings:
    """The baseline with named fields replaced. Differential tests change one."""
    fields = {
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


# ── the oracle is itself checked before anything relies on it ─────────────


def test_the_moments_oracle_reads_a_known_turn() -> None:
    """Calibration. Turning the page by +7 deg must move the oracle by -7 deg.

    Without this, every deskew assertion below rests on an unverified sign
    convention, and a sign error would read as a passing test.
    """
    straight = padded(a_page())
    flat = orientation_degrees(straight)
    assert flat is not None
    assert abs(flat) < MAX_SKEW_OF_A_STRAIGHT_PAGE

    skewed = orientation_degrees(turned(straight, KNOWN_SKEW_DEGREES))
    assert skewed is not None
    assert abs(skewed - (-KNOWN_SKEW_DEGREES)) < MAX_RESIDUAL_SKEW_DEGREES


# ── settings: every field is required, and every field is checked ─────────


def test_every_setting_is_required_and_none_has_a_default() -> None:
    """The whole point of the type. A default here would be a number nobody set,
    reaching OpenCV under the authority of the specification (Law 52, Law 54).
    """
    parameters = inspect.signature(cleaner.CleanerSettings).parameters
    defaulted = sorted(
        name for name, p in parameters.items() if p.default is not inspect.Parameter.empty
    )
    assert defaulted == [], f"these settings carry an invented default: {defaulted}"
    # The exact set, so a field silently dropped or silently added is visible.
    assert set(parameters) == {
        "max_deskew_degrees",
        "denoise_strength",
        "denoise_template_window",
        "denoise_search_window",
        "contrast_clip_limit",
        "contrast_tile_grid",
        "crop_margin_pixels",
        "max_ink_loss_fraction",
    }


def test_an_even_denoise_template_window_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="odd"):
        settings(denoise_template_window=8)


def test_a_search_window_smaller_than_the_template_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="search"):
        settings(denoise_template_window=21, denoise_search_window=7)


def test_a_non_positive_denoise_strength_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="denoise_strength"):
        settings(denoise_strength=0.0)


def test_an_ink_loss_fraction_above_one_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="max_ink_loss_fraction"):
        settings(max_ink_loss_fraction=1.5)


def test_a_negative_ink_loss_fraction_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="max_ink_loss_fraction"):
        settings(max_ink_loss_fraction=-0.1)


def test_a_deskew_limit_outside_the_representable_range_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="max_deskew_degrees"):
        settings(max_deskew_degrees=0.0)
    with pytest.raises(cleaner.ImpossibleSettingError, match="max_deskew_degrees"):
        settings(max_deskew_degrees=91.0)


def test_a_negative_crop_margin_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="crop_margin_pixels"):
        settings(crop_margin_pixels=-1)


def test_a_non_positive_contrast_clip_limit_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="contrast_clip_limit"):
        settings(contrast_clip_limit=0.0)


def test_a_contrast_tile_grid_below_one_is_refused() -> None:
    with pytest.raises(cleaner.ImpossibleSettingError, match="contrast_tile_grid"):
        settings(contrast_tile_grid=0)


# ── refusing what cannot be cleaned, loudly ───────────────────────────────


#: The refusal `_receive` raises when the dtype is not 8-bit, with the dtype it
#: saw left to the caller of this helper. Written once because four tests below
#: assert it whole and a copy per test is a copy that can drift.
def a_dtype_refusal(seen: str) -> str:
    return (
        f"expected an 8-bit (uint8) image, got {seen}. A cast would "
        "change every intensity in the frame; the original is not altered."
    )


def a_size_refusal(shorter_side: int) -> str:
    return (
        f"the shorter side is {shorter_side} pixel(s) and the caller's "
        f"denoise_search_window is {BASELINE.denoise_search_window}; the "
        "search window must fit inside the image. The minimum comes from "
        "the caller's own setting, not from a size this module chose."
    )


def test_a_float_image_is_refused_rather_than_silently_cast() -> None:
    """A float32 array casts to uint8 without complaint and every intensity in
    it changes meaning. Refused, because a silent cast is a value modified.

    The message is asserted WHOLE, and it names the dtype that arrived. A
    caller told only *"not uint8"* has to guess whether they sent a 16-bit
    scan, a float export or a signed array, and those have different fixes.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((400, 400), dtype=np.float32), BASELINE)
    assert str(excinfo.value) == a_dtype_refusal("float32")


def test_a_sixteen_bit_image_is_refused() -> None:
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((400, 400), dtype=np.uint16), BASELINE)
    assert str(excinfo.value) == a_dtype_refusal("uint16")


def test_an_empty_image_is_refused() -> None:
    """An array with no pixels is refused by the SIZE guard, not the dimension
    one: it is a legitimately shaped 2-D image that happens to be zero across,
    and the number the refusal quotes is the caller's own search window.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((0, 0), dtype=np.uint8), BASELINE)
    assert str(excinfo.value) == a_size_refusal(0)


def test_a_single_pixel_image_is_refused_because_the_search_window_cannot_fit() -> None:
    """The minimum size is derived from the caller's own search window, not from
    a number this module invented — which is only checkable if the refusal says
    so, so the whole sentence is asserted rather than the digits in it.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((1, 1), dtype=np.uint8), BASELINE)
    assert str(excinfo.value) == a_size_refusal(1)


def test_an_image_with_five_channels_is_refused() -> None:
    """Whole message. The refusal has to say which channel counts ARE normalised,
    or a caller holding a four-channel scan cannot tell a refusal of their file
    from a refusal of their whole format.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((400, 400, 5), dtype=np.uint8), BASELINE)
    assert str(excinfo.value) == (
        "an image with 5 channels is not a document this module can "
        "normalise; one, three and four channel 8-bit images are."
    )


def test_a_one_dimensional_array_is_refused() -> None:
    """And a four-dimensional one, from the other side of the same guard. The
    refusal quotes the shape it was handed, which is the only thing that tells
    a caller whether they sent a raw buffer or a batch of pages.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._clean_image(np.zeros((400,), dtype=np.uint8), BASELINE)
    assert str(excinfo.value) == (
        "expected a 2-D or 3-D image, got 1 dimension(s) with shape (400,)."
    )

    with pytest.raises(cleaner.UnusableArtifactError) as too_many:
        cleaner._clean_image(np.zeros((4, 4, 4, 4), dtype=np.uint8), BASELINE)
    assert str(too_many.value) == (
        "expected a 2-D or 3-D image, got 4 dimension(s) with shape (4, 4, 4, 4)."
    )


# ── format normalisation ──────────────────────────────────────────────────


def test_decode_returns_the_pixels_that_were_encoded() -> None:
    page = a_page()
    encoded, buffer = cv2.imencode(".png", page)
    assert encoded
    decoded = cleaner.decode(bytes(bytearray(buffer)))
    assert decoded.dtype == np.uint8
    assert np.array_equal(decoded, page)


def test_decode_refuses_bytes_that_are_not_an_image() -> None:
    """The message is asserted WHOLE, not as a substring.

    `SYSTEM_BOUNDARIES.md:52` makes the reason a document was refused part of
    what crosses the boundary, and the byte count in it is the only thing that
    tells a reader whether they sent a truncated file or the wrong file at all.
    A substring match would accept any wrapping, any casing and any dropped
    clause, so the count and the reason could both vanish while this stayed
    green.
    """
    sentence = b"this is not an image, it is a sentence"
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.decode(sentence)
    assert str(excinfo.value) == (
        f"the {len(sentence)} byte(s) supplied are not a decodable image. Reported "
        "rather than replaced by a blank page, which would read as a document "
        "that genuinely had nothing on it."
    )


def test_decode_refuses_empty_bytes() -> None:
    """Whole message again, and a DIFFERENT one from the undecodable case.

    "nothing was sent" and "what was sent is not an image" are different facts
    about the caller's request, and collapsing them would leave `reader` unable
    to say which happened.
    """
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.decode(b"")
    assert str(excinfo.value) == "no bytes were supplied; there is nothing to decode."


def test_decode_refuses_a_truncated_png() -> None:
    encoded, buffer = cv2.imencode(".png", a_page())
    assert encoded
    whole = bytes(bytearray(buffer))
    truncated = whole[: len(whole) // 3]
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.decode(truncated)
    assert str(excinfo.value) == (
        f"the {len(truncated)} byte(s) supplied are not a decodable image. Reported "
        "rather than replaced by a blank page, which would read as a document "
        "that genuinely had nothing on it."
    )


def test_decode_refuses_a_sixteen_bit_png_rather_than_downconverting_it() -> None:
    """Downconverting 16-bit to 8-bit halves the tonal resolution of every
    pixel. That is content removed, so it is refused instead of performed.
    """
    deep = np.full((64, 64), 40000, dtype=np.uint16)
    encoded, buffer = cv2.imencode(".png", deep)
    assert encoded
    with pytest.raises(cleaner.UnusableArtifactError, match="uint8"):
        cleaner.decode(bytes(bytearray(buffer)))


def test_a_colour_page_is_normalised_to_one_channel() -> None:
    colour = _u8(cv2.cvtColor(a_page(), cv2.COLOR_GRAY2BGR))
    result = cleaner._clean_image(colour, BASELINE)
    assert result.cleaned.ndim == ONE_CHANNEL_NDIM
    assert result.cleaned.dtype == np.uint8


def test_a_four_channel_page_is_normalised_to_one_channel() -> None:
    with_alpha = _u8(cv2.cvtColor(a_page(), cv2.COLOR_GRAY2BGRA))
    result = cleaner._clean_image(with_alpha, BASELINE)
    assert result.cleaned.ndim == ONE_CHANNEL_NDIM


# ── deskew, measured ──────────────────────────────────────────────────────


def test_deskew_removes_a_known_seven_degree_skew() -> None:
    """THE headline number. A 7.000 deg turn goes in; the residual measured by
    an independent oracle comes out below MAX_RESIDUAL_SKEW_DEGREES.
    """
    skewed = turned(padded(a_page()), KNOWN_SKEW_DEGREES)
    before = orientation_degrees(skewed)
    assert before is not None
    assert abs(before) > KNOWN_SKEW_DEGREES / 2.0, "the fixture failed to inject any skew"

    result = cleaner._clean_image(skewed, BASELINE)
    after = orientation_degrees(result.cleaned)
    assert after is not None
    assert abs(after) < MAX_RESIDUAL_SKEW_DEGREES, (
        f"residual skew {after:.4f} deg after correcting {before:.4f} deg"
    )


def test_the_reported_skew_angle_matches_the_independent_oracle() -> None:
    skewed = turned(padded(a_page()), KNOWN_SKEW_DEGREES)
    reported = cleaner._clean_image(skewed, BASELINE).observed(
        cleaner.SKEW_ANGLE, cleaner.Stage.ORIGINAL
    )
    oracle = orientation_degrees(skewed)
    assert reported.value is not None
    assert oracle is not None
    assert reported.unit == "degrees"
    assert abs(reported.value - oracle) < MAX_RESIDUAL_SKEW_DEGREES


def test_deskew_beyond_the_callers_limit_is_refused_and_said_so() -> None:
    """The page stays as it was. A detector that reports 32 deg on a document is
    usually a detector that failed, and rotating on it damages presentation.
    """
    skewed = turned(padded(a_page()), BEYOND_THE_LIMIT_DEGREES)
    result = cleaner._clean_image(skewed, settings(max_deskew_degrees=15.0))

    applied = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED)
    assert applied.value == 0.0, "a skew beyond the limit was rotated anyway"
    assert "max_deskew_degrees" in applied.note

    residual = orientation_degrees(result.cleaned)
    assert residual is not None
    assert abs(residual) > BEYOND_THE_LIMIT_DEGREES / 2.0, (
        "the page was straightened despite the refusal"
    )


def test_the_same_skew_is_corrected_when_the_limit_allows_it() -> None:
    """The pair that proves the refusal above is the limit doing work, and not
    the detector quietly failing on a 32 deg page.
    """
    skewed = turned(padded(a_page()), BEYOND_THE_LIMIT_DEGREES)
    result = cleaner._clean_image(skewed, settings(max_deskew_degrees=45.0))
    residual = orientation_degrees(result.cleaned)
    assert residual is not None
    assert abs(residual) < MAX_RESIDUAL_SKEW_DEGREES


def test_an_already_straight_page_is_not_bent() -> None:
    straight = padded(a_page())
    result = cleaner._clean_image(straight, BASELINE)
    residual = orientation_degrees(result.cleaned)
    assert residual is not None
    assert abs(residual) < MAX_SKEW_OF_A_STRAIGHT_PAGE


def test_rotation_never_pushes_ink_off_the_canvas() -> None:
    """The canvas grows to hold the rotated frame, so no pixel leaves it. Proven
    by counting ink, not by reading the code that resizes.
    """
    skewed = turned(padded(a_page()), KNOWN_SKEW_DEGREES)
    result = cleaner._clean_image(skewed, settings(crop_margin_pixels=0))
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)
    assert kept.value == FULL_RETENTION


# ── denoise, measured, and proven differentially ──────────────────────────


def test_enough_denoising_lowers_end_to_end_noise() -> None:
    """Measured: 11.382 -> 4.160 grey levels at denoise_strength 30."""
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    before = median_residual_sigma(noisy)
    cleaned = cleaner._clean_image(
        noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH)
    ).cleaned
    after = median_residual_sigma(cleaned)
    assert after < before, f"noise sigma {before:.3f} -> {after:.3f}, no reduction"


def test_the_cost_of_contrast_enhancement_is_reported_and_not_hidden() -> None:
    """A FINDING, pinned so it can never become a silent claim.

    At `BASELINE` the cleaned page is NOISIER than the page received: 11.382 ->
    22.577 grey levels, because CLAHE at clipLimit 2.0 amplifies more than
    denoise_strength 6.0 removed. Both stage orders were measured and both raise
    it, so this is the contrast setting's cost and not a bug in the sequence.

    What makes it safe is that `cleaner` MEASURES the rise and reports it rather
    than announcing an improvement it did not make (Law 24, Law 52). This test
    fails the moment that reporting is dropped or rounded away.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    result = cleaner._clean_image(noisy, BASELINE)
    before = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.ORIGINAL)
    after = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.CLEANED)
    assert before.value is not None
    assert after.value is not None
    assert after.value > before.value, "the rise stopped being reported"
    assert median_residual_sigma(result.cleaned) > median_residual_sigma(noisy)


def test_the_reported_noise_numbers_agree_with_an_independent_estimator() -> None:
    """Cross-check, across a setting that raises noise and one that lowers it.

    Immerkaer (the module) and the median residual (this file) are different
    formulas. If they ever disagree about the DIRECTION of the change, one is
    wrong and the artifact's quality evidence cannot be trusted — which is worse
    than either number being off, because `confidence` would score on it.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    oracle_before = median_residual_sigma(noisy)
    for strength in (GENTLE_DENOISE_STRENGTH, BASELINE.denoise_strength, STRONG_DENOISE_STRENGTH):
        result = cleaner._clean_image(noisy, settings(denoise_strength=strength))
        reported_before = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.ORIGINAL).value
        reported_after = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.CLEANED).value
        assert reported_before is not None
        assert reported_after is not None
        module_rose = reported_after > reported_before
        oracle_rose = median_residual_sigma(result.cleaned) > oracle_before
        assert module_rose == oracle_rose, (
            f"at denoise_strength {strength} the module reports "
            f"{reported_before:.3f} -> {reported_after:.3f} while the independent "
            f"estimator reports {oracle_before:.3f} -> "
            f"{median_residual_sigma(result.cleaned):.3f}"
        )


def test_a_higher_clip_limit_costs_strictly_more_noise() -> None:
    """Differential, and the mechanism behind the finding above. Only
    `contrast_clip_limit` differs. Measured: 13.301 -> 22.577 grey levels.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    quiet = cleaner._clean_image(noisy, settings(contrast_clip_limit=LOW_CLIP_LIMIT))
    loud = cleaner._clean_image(noisy, settings(contrast_clip_limit=BASELINE.contrast_clip_limit))
    assert median_residual_sigma(loud.cleaned) > median_residual_sigma(quiet.cleaned)


def test_a_stronger_denoise_setting_leaves_strictly_less_noise() -> None:
    """Differential. Only `denoise_strength` differs, so every other stage runs
    identically and the difference cannot come from cropping or contrast.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    gentle = cleaner._clean_image(noisy, settings(denoise_strength=GENTLE_DENOISE_STRENGTH))
    strong = cleaner._clean_image(noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH))
    assert median_residual_sigma(strong.cleaned) < median_residual_sigma(gentle.cleaned)


def test_the_reported_noise_estimate_falls_between_the_two_stages() -> None:
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    result = cleaner._clean_image(noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH))
    original = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.ORIGINAL)
    cleaned = result.observed(cleaner.NOISE_SIGMA, cleaner.Stage.CLEANED)
    assert original.value is not None
    assert cleaned.value is not None
    assert original.unit == "grey levels"
    assert cleaned.value < original.value


# ── contrast, measured, and proven differentially ─────────────────────────


def a_low_contrast_page() -> Image:
    """Content edge to edge, so cropping cannot be what raises the contrast."""
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), 130, dtype=np.uint8)
    for row in range(0, PAGE_HEIGHT, TEXT_LINE_PITCH):
        sheet[row : row + TEXT_LINE_THICKNESS, :] = 110
    return sheet


def test_a_higher_clip_limit_produces_strictly_more_contrast() -> None:
    """Differential. Only `contrast_clip_limit` differs between the two runs."""
    flat = a_low_contrast_page()
    quiet = cleaner._clean_image(flat, settings(contrast_clip_limit=LOW_CLIP_LIMIT))
    loud = cleaner._clean_image(flat, settings(contrast_clip_limit=HIGH_CLIP_LIMIT))
    assert rms_contrast(loud.cleaned) > rms_contrast(quiet.cleaned)


def test_contrast_rises_on_a_page_that_crop_cannot_change() -> None:
    flat = a_low_contrast_page()
    result = cleaner._clean_image(flat, settings(contrast_clip_limit=HIGH_CLIP_LIMIT))
    before = rms_contrast(flat)
    after = rms_contrast(result.cleaned)
    assert after > before, f"rms contrast {before:.3f} -> {after:.3f}, no improvement"


def test_the_reported_contrast_matches_the_independent_measure() -> None:
    flat = a_low_contrast_page()
    reported = cleaner._clean_image(flat, BASELINE).observed(
        cleaner.RMS_CONTRAST, cleaner.Stage.ORIGINAL
    )
    assert reported.value is not None
    assert reported.unit == "grey levels"
    assert reported.value == pytest.approx(rms_contrast(flat), abs=1e-6)


# ── the preservation rule ─────────────────────────────────────────────────


def test_a_clean_that_loses_no_ink_reports_the_cleaned_form_as_safer() -> None:
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    lost = result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED)
    assert lost.value is not None
    assert lost.value < MAX_BASELINE_INK_LOSS
    assert result.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


def a_page_of_hairline_strokes() -> Image:
    """One-pixel strokes at low contrast. Exactly what a strong denoise erases,
    and exactly the decimal point whose loss changes a posted amount.
    """
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), 200, dtype=np.uint8)
    for row in range(20, PAGE_HEIGHT - 20, 6):
        sheet[row : row + 1, 20 : PAGE_WIDTH - 20] = 150
    return with_gaussian_noise(sheet, INJECTED_NOISE_SIGMA)


def test_a_denoise_that_erases_ink_flips_preservation_to_the_original() -> None:
    """The rule the specification states: if processing may damage information,
    preserve the original and mark it. Proven by causing the damage.
    """
    hairlines = a_page_of_hairline_strokes()
    result = cleaner._clean_image(hairlines, settings(denoise_strength=ERASING_DENOISE_STRENGTH))
    lost = result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED)
    assert lost.value is not None
    assert lost.value > BASELINE.max_ink_loss_fraction, (
        f"the fixture failed to erase any ink: loss was {lost.value:.4f}"
    )
    assert result.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER


def test_the_preservation_rule_tracks_the_callers_threshold_and_not_a_constant() -> None:
    """Differential. The same damaged clean, judged by two thresholds. If the
    module ever hard-codes a limit, exactly one of these two goes red.
    """
    hairlines = a_page_of_hairline_strokes()
    strict = cleaner._clean_image(
        hairlines,
        settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=0.0),
    )
    permissive = cleaner._clean_image(
        hairlines,
        settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=1.0),
    )
    assert strict.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    assert permissive.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


def test_the_original_is_never_discarded() -> None:
    page = padded(a_page())
    result = cleaner._clean_image(page, BASELINE)
    assert np.array_equal(result.original, page), "the original was altered"
    assert result.original is not result.cleaned


def test_the_original_is_carried_in_the_colour_it_arrived_in() -> None:
    colour = _u8(cv2.cvtColor(a_page(), cv2.COLOR_GRAY2BGR))
    result = cleaner._clean_image(colour, BASELINE)
    assert np.array_equal(result.original, colour)


# ── crop discards no content ──────────────────────────────────────────────


def test_crop_keeps_every_ink_pixel() -> None:
    """The one operation that can literally delete content. `cleaner` may not
    discard anything it judges irrelevant, so retention must be exactly 1.
    """
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)
    assert kept.value == FULL_RETENTION
    assert kept.unit == "fraction of ink pixels"


def test_crop_removes_the_blank_border_it_was_given() -> None:
    """Retention of 1.0 would also hold if crop did nothing at all, so the
    counterpart is that the 200px blank pad actually goes."""
    page = padded(a_page())
    result = cleaner._clean_image(page, settings(crop_margin_pixels=0))
    assert result.cleaned.shape[0] < page.shape[0]
    assert result.cleaned.shape[1] < page.shape[1]


def test_a_larger_crop_margin_keeps_a_larger_page() -> None:
    page = padded(a_page())
    tight = cleaner._clean_image(page, settings(crop_margin_pixels=0))
    loose = cleaner._clean_image(page, settings(crop_margin_pixels=40))
    assert loose.cleaned.shape[0] > tight.cleaned.shape[0]
    assert loose.cleaned.shape[1] > tight.cleaned.shape[1]


# ── blank pages, and everything that divides by the ink count ─────────────


def test_a_blank_page_is_reported_rather_than_crashed_on() -> None:
    blank: Image = np.full((400, 400), PAPER_INTENSITY, dtype=np.uint8)
    result = cleaner._clean_image(blank, BASELINE)
    assert result.observed(cleaner.INK_FRACTION, cleaner.Stage.ORIGINAL).value == 0.0
    assert result.observed(cleaner.SKEW_ANGLE, cleaner.Stage.ORIGINAL).value is None
    assert result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value == 0.0
    assert result.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


def test_a_blank_page_is_not_cropped_to_nothing() -> None:
    blank: Image = np.full((400, 400), PAPER_INTENSITY, dtype=np.uint8)
    result = cleaner._clean_image(blank, BASELINE)
    assert result.cleaned.shape == blank.shape


def test_an_all_black_page_is_handled_too() -> None:
    black: Image = np.zeros((400, 400), dtype=np.uint8)
    result = cleaner._clean_image(black, BASELINE)
    assert result.cleaned.size > 0


# ── the observations themselves ───────────────────────────────────────────


def test_every_observation_carries_a_reason() -> None:
    """`ENGINE_1:626` - a bare score cannot become a good question downstream."""
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    assert result.quality_observations
    for observation in result.quality_observations:
        assert observation.note.strip(), f"{observation.name} carries no reason"
        assert observation.unit.strip(), f"{observation.name} carries no unit"


def test_no_observation_is_reported_twice_for_one_stage() -> None:
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    keys = [(o.name, o.stage) for o in result.quality_observations]
    assert len(keys) == len(set(keys)), f"a measurement is reported twice: {keys}"


def test_both_stages_are_measured_so_an_improvement_can_be_stated() -> None:
    """Law 52. A claim that cleaning improved anything needs before and after."""
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    stages = {o.stage for o in result.quality_observations}
    assert stages == {cleaner.Stage.ORIGINAL, cleaner.Stage.CLEANED}
    for name in (cleaner.NOISE_SIGMA, cleaner.RMS_CONTRAST, cleaner.LAPLACIAN_VARIANCE):
        assert result.observed(name, cleaner.Stage.ORIGINAL).value is not None
        assert result.observed(name, cleaner.Stage.CLEANED).value is not None


def test_asking_for_a_measurement_that_was_not_taken_fails_loudly() -> None:
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    with pytest.raises(KeyError):
        result.observed("a measurement nobody took", cleaner.Stage.ORIGINAL)


def test_the_result_is_frozen() -> None:
    result = cleaner._clean_image(padded(a_page()), BASELINE)
    #: Named rather than written literally: `setattr` with a literal attribute
    #: is a lint violation, and a suppression comment is a gate this repo blocks.
    frozen_field = "preservation_status"
    with pytest.raises((AttributeError, TypeError)):
        setattr(result, frozen_field, cleaner.PreservationStatus.ORIGINAL_IS_SAFER)


# ── the four measurements' own size guards, called directly ───────────────
#
# `clean()` cannot reach these degenerate cases through the public API:
# `_receive` already refuses anything shorter than `denoise_search_window`
# (itself bounded below by `_MIN_SIDE_FOR_NOISE`), so the ORIGINAL grey array
# can never be small enough, and `_crop_to_ink` never produces a
# zero-pixel crop (a bounding box of at least one ink pixel always has
# positive width and height; a blank page is returned uncropped). These four
# functions' own size guards are real logic with a real, meaningful contract
# — "unmeasurable, not zero" — so they are tested directly with real,
# degenerate `numpy` arrays rather than left unexercised because the one
# caller in this file happens never to build a degenerate array itself.


def test_measure_noise_is_unmeasurable_below_the_three_pixel_minimum() -> None:
    tiny: Image = np.zeros((2, 5), dtype=np.uint8)
    assert cleaner._measure_noise(tiny) is None


def test_measure_sharpness_is_unmeasurable_below_the_three_pixel_minimum() -> None:
    tiny: Image = np.zeros((1, 10), dtype=np.uint8)
    assert cleaner._measure_sharpness(tiny) is None


def test_measure_contrast_is_unmeasurable_on_an_empty_array() -> None:
    empty: Image = np.zeros((0, 5), dtype=np.uint8)
    assert cleaner._measure_contrast(empty) is None


def test_measure_ink_fraction_is_unmeasurable_on_an_empty_array() -> None:
    empty: Image = np.zeros((5, 0), dtype=np.uint8)
    assert cleaner._measure_ink_fraction(empty) is None


def a_page_of_exactly_three_pixels_on_its_short_side(rows: int, columns: int) -> Image:
    """A page at the smallest size the estimators accept, carrying real detail.

    Seeded noise rather than a flat fill: a uniform page measures 0.0, which is
    falsy, so a guard that had wrongly refused it would be indistinguishable
    from one that measured it.
    """
    return np.asarray(
        np.random.default_rng(RNG_SEED).integers(0, 256, (rows, columns)), dtype=np.uint8
    )


def test_a_page_exactly_three_pixels_across_is_measurable_and_not_refused() -> None:
    """The minimum is a MINIMUM. Immerkaer's mask is 3x3 and its normalisation
    divides by the interior area, so three is the smallest side on which the
    estimate exists — and it does exist there.

    Refusing it instead costs a real document its evidence. A till receipt
    cropped to a single printed line, or the last strip of a scan, arrives at
    exactly this size, and `confidence` cannot account for a page that reports
    `None` when the number was available (`ENGINE_1:109`).

    Both sides are checked, because the guard has two: three rows and three
    columns are measurable, two are not.
    """
    three_rows = a_page_of_exactly_three_pixels_on_its_short_side(3, 5)
    three_columns = a_page_of_exactly_three_pixels_on_its_short_side(10, 3)

    assert cleaner._measure_noise(three_rows) is not None
    assert cleaner._measure_noise(three_columns) is not None
    assert cleaner._measure_sharpness(three_rows) is not None
    assert cleaner._measure_sharpness(three_columns) is not None

    assert cleaner._measure_noise(np.zeros((2, 5), dtype=np.uint8)) is None
    assert cleaner._measure_noise(np.zeros((10, 2), dtype=np.uint8)) is None
    assert cleaner._measure_sharpness(np.zeros((2, 5), dtype=np.uint8)) is None
    assert cleaner._measure_sharpness(np.zeros((10, 2), dtype=np.uint8)) is None


#: The 3x3 Laplacian `cv2.Laplacian` applies at its default kernel size, written
#: out so this file convolves it ITSELF rather than calling the same routine the
#: module calls and comparing it to itself.
FOUR_NEIGHBOUR_LAPLACIAN = np.asarray(
    [[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float64
)


def test_sharpness_keeps_the_negative_half_of_the_laplacian_it_measures() -> None:
    """A blur measure computed in 8 bits is a blur measure with half its signal
    thrown away.

    Every edge produces a Laplacian response that is negative on one side and
    positive on the other. Ask OpenCV for an 8-bit result and every negative one
    clamps to zero, so the variance collapses — measured on this page, 2941.75
    in floating point against 1325.89 clamped, a blurred page reported as more
    than twice as sharp as it is. `cleaner` has no deblur step, so this number
    is the ONLY thing that tells `confidence` a page was out of focus.

    Checked against this file's own convolution of the same kernel, in
    float64 — the same quantity by a different call — and then against the
    clamped figure, so the test states what the number is AND what it must not
    be.
    """
    page = a_small_banded_page()
    reported = cleaner._measure_sharpness(page)
    in_full = float(np.var(cv2.filter2D(_f64(page), -1, FOUR_NEIGHBOUR_LAPLACIAN)))
    clamped = float(np.var(_f64(cv2.Laplacian(page, -1))))

    assert reported is not None
    assert reported == pytest.approx(in_full, rel=1e-12)
    assert reported > clamped, (
        f"the reported sharpness {reported} is the clamped 8-bit figure {clamped}, "
        "so half of every edge's response has been discarded"
    )


#: The impulse page below. Every dimension of it is load-bearing: each spike
#: sits exactly two pixels from one edge, so its 3x3 response fills the outermost
#: line of the region the estimator keeps and NOTHING is left over at the border.
IMPULSE_PAGE_HEIGHT = 40
IMPULSE_PAGE_WIDTH = 60
IMPULSE_AMPLITUDE = 200
#: `|1| + |2| + |1| + |2| + |4| + |2| + |1| + |2| + |1|`, the absolute weight one
#: isolated spike puts through Immerkaer's mask.
NOISE_MASK_ABSOLUTE_WEIGHT = 16
IMPULSES_ON_THE_PAGE = 4
#: The interval the estimate of a known sigma must land in. Measured across five
#: seeds on a 400 x 400 page: -0.54% to +0.45%.
MAX_SIGMA_RECOVERY_ERROR = 0.01
KNOWN_SIGMA = 12.0
MID_GREY = 128.0
CALIBRATION_SIDE = 400
CALIBRATION_SEEDS = (1, 2, 3, 20260805, 11)


def a_page_of_four_isolated_spikes() -> Image:
    """A black page carrying one bright pixel beside each of its four edges.

    An isolated spike is the one input whose Immerkaer response can be written
    down: the mask lands on it nine times and nowhere else, so the page's total
    absolute response is the mask's absolute weight times the amplitude, times
    the number of spikes. Each spike is placed two pixels in, so the top row of
    one response, the bottom row of another and the outer column of the last two
    each sit ON the boundary of the region the estimator keeps.
    """
    page: Image = np.zeros((IMPULSE_PAGE_HEIGHT, IMPULSE_PAGE_WIDTH), dtype=np.uint8)
    page[2, 20] = IMPULSE_AMPLITUDE
    page[IMPULSE_PAGE_HEIGHT - 3, 20] = IMPULSE_AMPLITUDE
    page[20, 2] = IMPULSE_AMPLITUDE
    page[20, IMPULSE_PAGE_WIDTH - 3] = IMPULSE_AMPLITUDE
    return page


def test_the_noise_estimate_normalises_over_the_interior_it_actually_measured() -> None:
    """Immerkaer's arithmetic, on the one page where it can be written out.

    Border pixels are dropped because `filter2D` invents them by reflection, and
    what is left is normalised by the interior's area. Both halves of that are
    off-by-one country, and neither is visible on a real scan: a page-level
    tolerance wide enough for sensor noise swallows a normaliser that is one row
    short, while the resulting sigma is quietly 2.6% high on every document.

    So the page carries four isolated spikes, each two pixels from one edge.
    The total absolute response is countable — four spikes at the mask's
    absolute weight of 16 — and each spike's response reaches exactly one
    boundary of the kept region, so a slice that starts or ends one step in
    loses a measurable quarter-of-a-spike and lands nowhere near this number.
    """
    page = a_page_of_four_isolated_spikes()
    interior = (IMPULSE_PAGE_HEIGHT - 2) * (IMPULSE_PAGE_WIDTH - 2)
    total = IMPULSES_ON_THE_PAGE * NOISE_MASK_ABSOLUTE_WEIGHT * IMPULSE_AMPLITUDE

    measured = cleaner._measure_noise(page)

    assert measured is not None
    assert measured == pytest.approx(math.sqrt(math.pi / 2.0) * total / (6.0 * interior), rel=1e-12)


def test_the_noise_estimate_recovers_a_sigma_this_file_put_in() -> None:
    """Calibration, against noise whose spread is known because it was chosen.

    The test above pins the estimator's SHAPE by restating its normalisation;
    this one pins its SCALE without restating anything, by drawing Gaussian
    noise of a known standard deviation and requiring the estimate to come back
    as that number. A leading constant that is wrong by a factor — `sqrt(2 pi)`
    for `sqrt(pi / 2)` is a factor of two — cannot survive it, and no formula
    from the module appears here at all.

    Five seeds, because one seed proves nothing about a statistic. Measured
    across them on a 400 x 400 page: -0.54% to +0.45%, against a bound of 1%.
    Mid-grey and sigma 12 so that nothing clips at either end of the range,
    which would bias the spread downward and make this pass for the wrong
    reason.
    """
    for seed in CALIBRATION_SEEDS:
        generator = np.random.default_rng(seed)
        lightest = float(np.iinfo(np.uint8).max)
        noise = generator.normal(0.0, KNOWN_SIGMA, (CALIBRATION_SIDE, CALIBRATION_SIDE))
        page = _u8(np.clip(np.rint(MID_GREY + noise), 0.0, lightest))
        assert int(page.min()) > 0, "the fixture clipped at black, which narrows its spread"
        assert float(page.max()) < lightest, "the fixture clipped at white"

        estimate = cleaner._measure_noise(page)

        assert estimate is not None
        assert abs(estimate / KNOWN_SIGMA - 1.0) < MAX_SIGMA_RECOVERY_ERROR, (
            f"seed {seed} put in sigma {KNOWN_SIGMA} and got {estimate} back"
        )


#: A page two pixels tall — below the three the noise estimator needs — with a
#: mark four grey levels below its paper. Two rows so the mark's column mean is
#: displaced by exactly half of that, which is inside the allowance a sigma of
#: one would buy and outside the allowance a sigma of zero buys.
UNMEASURABLY_THIN_HEIGHT = 2
UNMEASURABLY_THIN_WIDTH = 40
FAINT_MARK_DEPTH = 4
#: Measured: rows 0 to 0, columns 5 to 29 — the mark exactly.
BOX_AROUND_THE_FAINT_MARK = (0, 0, 5, 29)


def test_a_page_too_thin_to_measure_noise_on_is_given_no_allowance_at_all() -> None:
    """`_measure_noise(grey) or 0.0` — and the zero is the whole of it.

    The allowance a line has to clear before it counts as content is scaled by
    the page's noise. When the page is too small for the estimator to say
    anything, there is no measured noise, and the honest allowance is ZERO: an
    invented one is a threshold this module chose, and every mark fainter than
    it leaves the page (Law 52).

    Two rows and a mark four grey levels down is exactly the gap. With no
    allowance the mark is content and the box closes around it; with an
    allowance of one grey level's worth the same mark is paper, the columns
    carry nothing, and `_content_box` reports a page with nothing on it —
    which `_crop_to_content` reads as *"return it whole"* and everything
    downstream reads as a blank sheet.
    """
    thin: Image = np.full(
        (UNMEASURABLY_THIN_HEIGHT, UNMEASURABLY_THIN_WIDTH), SMALL_PAPER, dtype=np.uint8
    )
    thin[0, 5:30] = SMALL_PAPER - FAINT_MARK_DEPTH
    assert cleaner._measure_noise(thin) is None, "the fixture is measurable, so it proves nothing"

    assert cleaner._content_box(thin) == BOX_AROUND_THE_FAINT_MARK


def test_the_ink_fraction_is_the_share_of_the_page_the_ink_actually_covers() -> None:
    """A number that can be counted by hand, so the arithmetic has nowhere to hide.

    `a_small_banded_page` paints a band of 10 rows by 70 columns onto a sheet of
    60 by 90: 700 pixels of 5400, which is exactly 0.12962962962962962. The
    existing blank-page test pins the numerator's zero; nothing pinned that the
    numerator is COUNTED at all, and a fraction stuck at zero reports every
    document as a blank sheet.
    """
    banded = a_small_banded_page()
    band = 10 * 70

    assert cleaner._measure_ink_fraction(banded) == pytest.approx(band / banded.size, rel=1e-12)
    assert cleaner._measure_ink_fraction(a_small_uniform_page()) == 0.0


# ── the boundary the module must never cross ──────────────────────────────


def test_the_module_reads_no_text_and_owns_no_field_names() -> None:
    """`cleaner` alters presentation. Reading is `reader`, structuring is
    `parser`, scoring is `confidence`. A field name or a confidence score
    appearing in this module is a boundary crossed in code.
    """
    source = authored_source(cleaner)
    for forbidden in ("pytesseract", "tesseract", "easyocr", "PIL", "Image.open"):
        assert forbidden not in source, f"{forbidden} is not on the approved stack"
    exported = {name for name in vars(cleaner) if not name.startswith("_")}
    for reserved in ("confidence", "Confidence", "DetectedField", "extract", "read_text"):
        assert reserved not in exported, f"{reserved} belongs to another sub-engine"


def test_cleaning_the_same_page_twice_gives_the_same_bytes() -> None:
    """Determinism. `MEASUREMENT_FRAMEWORK` cannot obtain a number from a stage
    that answers differently on two runs.

    MOVED TO THE SINGLE ENTRY POINT (F-017) AND MADE STRICTER BY THE MOVE. It
    called `clean()` twice and compared the two rasters, which is a claim about
    the pixels. What the pipeline actually carries onward is
    `CleanedArtifact.payload` — the encoded bytes `reader` and `parser` open —
    and this now compares those as well, so the assertion finally checks what
    the test has always been called: the same page twice gives the same BYTES.
    Nothing that was asserted before was dropped.
    """
    page = _png_bytes(padded(a_page()))
    first = cleaner.clean_artifact(page, cleaner.MediaKind.IMAGE, BASELINE, render_dpi=RENDER_DPI)
    second = cleaner.clean_artifact(page, cleaner.MediaKind.IMAGE, BASELINE, render_dpi=RENDER_DPI)

    assert first.artifact is not None
    assert second.artifact is not None
    assert first.artifact.payload == second.artifact.payload
    assert np.array_equal(first.cleaned, second.cleaned)
    assert first.quality_observations == second.quality_observations


# ── the media-aware migration (KNOWN_FAILURES F-017) ──────────────────────
#
# Before this, `CleanedDocument.cleaned` was `NDArray[uint8]` — a bitmap. That
# one type made "cleaned document representation" mean "cleaned raster", which
# cannot represent a PDF at all, and it caused three separate recorded failures
# that were really one defect. These tests pin the corrected contract: a cleaned
# document is still the KIND of document it started as.


def a_settings() -> cleaner.CleanerSettings:
    """Legal values so the artifact paths can be exercised. Not recommended
    operating points — every one of the sixteen confidence parameters is UNSET
    by design and these are the TEST's own numbers (Law 52)."""
    return cleaner.CleanerSettings(
        max_deskew_degrees=45.0,
        denoise_strength=10.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=10,
        max_ink_loss_fraction=0.15,
    )


def an_image_page() -> bytes:
    """A small page with real ink on it, as PNG bytes."""
    page = np.full((200, 400), 255, dtype=np.uint8)
    cv2.putText(page, "TAX INVOICE", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    ok, buffer = cv2.imencode(".png", page)
    assert ok
    return bytes(buffer.tobytes())


def a_text_layer_pdf() -> bytes:
    """A PDF whose characters are embedded — the case that must NEVER be
    rasterised, because rasterising destroys the text layer."""
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 144), "TAX INVOICE 27AAECS1234F1Z5")
        return bytes(document.tobytes())
    finally:
        document.close()


def a_scanned_pdf() -> bytes:
    """A PDF holding only an image — no text layer, so rasterising loses nothing."""
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        page = document.new_page(width=400, height=200)
        page.insert_image(fitz.Rect(0, 0, 400, 200), stream=an_image_page())
        return bytes(document.tobytes())
    finally:
        document.close()


def test_a_pdf_can_be_cleaned_at_all() -> None:
    """The headline defect. `decode` returns an Image and `cv2.imdecode` returns
    None on PDF bytes, so before this migration EVERY PDF raised — for Engine
    1's own primary input, and 61 tests missed it because all 61 feed an image.
    """
    cleaned = cleaner.clean_artifact(
        a_text_layer_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
    )

    assert cleaned.artifact is not None
    assert cleaned.artifact.kind is cleaner.MediaKind.PDF


def test_a_cleaned_pdf_is_still_a_pdf() -> None:
    """The contract in one line: cleaning preserves the media kind."""
    cleaned = cleaner.clean_artifact(
        a_text_layer_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
    )

    assert cleaned.artifact is not None
    assert cleaned.artifact.payload.startswith(b"%PDF-")


def test_a_text_layer_pdf_passes_through_byte_for_byte() -> None:
    """A digitally-generated PDF has no skew, no sensor noise and no contrast
    problem. Every transformation available would rasterise exact characters
    into pixels and destroy the text layer — information cleaning may never
    lose. Passing through unchanged is the CORRECT cleaning here, not the
    absence of it, and the observation records why.
    """
    source = a_text_layer_pdf()

    cleaned = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=150)

    assert cleaned.artifact is not None
    assert cleaned.artifact.payload == source, "a text-layer PDF must not be altered"
    assert cleaned.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    names = [observation.name for observation in cleaned.quality_observations]
    assert "text_layer_present" in names, "the reason for passing through must be recorded"


def test_a_scanned_pdf_is_rebuilt_and_is_still_a_pdf() -> None:
    """No text layer means there was never anything but pixels, so rasterising
    loses nothing. The output stays a PDF so the pipeline has ONE shape.
    """
    source = a_scanned_pdf()

    cleaned = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=150)

    assert cleaned.artifact is not None
    assert cleaned.artifact.payload.startswith(b"%PDF-")
    assert cleaned.artifact.payload != source, "a scan must actually be cleaned, not passed through"


def test_the_original_bytes_are_never_discarded() -> None:
    """`ENGINE_1:461` — a damaging transformation must always be recoverable."""
    for source, kind in (
        (an_image_page(), cleaner.MediaKind.IMAGE),
        (a_text_layer_pdf(), cleaner.MediaKind.PDF),
        (a_scanned_pdf(), cleaner.MediaKind.PDF),
    ):
        cleaned = cleaner.clean_artifact(source, kind, a_settings(), render_dpi=150)
        assert cleaned.artifact is not None
        assert cleaned.artifact.original == source


def test_a_cleaned_image_is_still_a_decodable_image() -> None:
    cleaned = cleaner.clean_artifact(
        an_image_page(), cleaner.MediaKind.IMAGE, a_settings(), render_dpi=150
    )

    assert cleaned.artifact is not None
    assert cleaned.artifact.kind is cleaner.MediaKind.IMAGE
    assert cleaner.decode(cleaned.artifact.payload).ndim == ONE_CHANNEL_NDIM, (
        "the payload must decode back to an image"
    )


def test_an_image_carries_a_raster_and_a_passed_through_pdf_does_not() -> None:
    """`raster is None` means NOTHING WAS RASTERISED. It is not a blank page and
    must never be read as one — the same distinction `reader` keeps between an
    unreadable file and an empty one.
    """
    image = cleaner.clean_artifact(
        an_image_page(), cleaner.MediaKind.IMAGE, a_settings(), render_dpi=150
    )
    assert image.artifact is not None
    assert image.artifact.raster is not None

    text_pdf = cleaner.clean_artifact(
        a_text_layer_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
    )
    assert text_pdf.artifact is not None
    assert text_pdf.artifact.raster is None


def test_empty_bytes_are_refused_rather_than_cleaned_into_a_blank_page() -> None:
    """Exact message, not a substring: a mutant that wraps the whole string in
    `XX...XX` markers still CONTAINS "nothing to clean" as a substring, so a
    loose `match` cannot tell the wrapped string from the real one.
    """
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.clean_artifact(b"", cleaner.MediaKind.PDF, a_settings(), render_dpi=150)
    assert str(excinfo.value) == "no bytes were supplied; there is nothing to clean."


# ── mutation-testing hardening (F-017 migration, cleaner.py 90.6% -> 93%) ──
#
# `fitz.open(..., filetype=...)` and `Pixmap.tobytes(fmt)` are, in the pinned
# pymupdf 1.28.0 / MuPDF 1.29.0, PROVEN to ignore their format-hint argument
# whenever the stream itself is real, recognisable content: measured directly
# against garbage bytes, a real PNG mislabelled as "pdf", an empty stream and
# four unrelated extension strings ("docx", "xps", "epub", "notarealformat"),
# every one opened identically and raised the identical exception type on the
# identical bad input. `get_text("TEXT")` was measured byte-for-byte identical
# to `get_text("text")` the same way. A mutant that swaps the case of that
# literal, or the literal itself, is therefore behaviourally IDENTICAL code —
# no test, however written, can observe a difference, because the dependency
# itself throws the argument away. Left undtested rather than faked green.


def test_render_dpi_controls_the_rasterised_scanned_pdf_size_end_to_end() -> None:
    """Differential across `render_dpi`, through the public entry point.

    `clean_artifact` hands `render_dpi` to `_clean_pdf`, which hands it to
    `_pdf_rebuilt_from_cleaned_pages`, which hands it to `get_pixmap(dpi=...)`.
    A mutant that drops it to `None` at ANY of those three hops makes every
    call render at the same fixed size regardless of what the caller asked
    for — this test changes only `render_dpi` and requires the rasterised
    page to grow with it, catching a `None` at any of the three hops.
    """
    source = a_scanned_pdf()
    low = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=72)
    high = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=300)

    assert low.artifact is not None
    assert high.artifact is not None
    assert low.artifact.raster is not None
    assert high.artifact.raster is not None
    assert high.artifact.raster.shape[0] > low.artifact.raster.shape[0], (
        "a higher render_dpi did not produce a taller raster"
    )
    assert high.artifact.raster.shape[1] > low.artifact.raster.shape[1], (
        "a higher render_dpi did not produce a wider raster"
    )


def a_zero_page_pdf() -> bytes:
    """Hand-crafted rather than built with pymupdf: pymupdf's own `tobytes()`
    refuses to save a zero-page document (`ValueError: cannot save with zero
    pages`), so the only way to reach `_pdf_rebuilt_from_cleaned_pages`'s own
    "zero pages" guard is a minimal PDF pymupdf can OPEN but never CREATES.
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"trailer\n<< /Size 3 /Root 1 0 R >>\n%%EOF\n"
    )


def test_a_zero_page_pdf_is_reported_rather_than_crashed_on() -> None:
    """No text layer on a document with no pages routes into the rebuild path,
    whose page loop runs zero times and never sets `first` — the exact branch
    the specification requires to be reported, not silently returned as a
    blank document.
    """
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.clean_artifact(
            a_zero_page_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
        )
    assert str(excinfo.value) == (
        "the PDF reports zero pages. Reported rather than returned as a blank "
        "document, which would read as a page that genuinely held nothing."
    )


def test_a_scanned_pdfs_artifact_raster_matches_the_cleaned_field_and_the_pdf_kind() -> None:
    """`_pdf_rebuilt_from_cleaned_pages` sets BOTH `CleanedDocument.cleaned` and
    `CleanedArtifact.raster` from the same `first.cleaned` array. Comparing
    them to EACH OTHER, rather than to a value chosen in this file, catches
    `kind` or `raster` silently dropping to `None` without inventing a number
    of this test's own for what the raster "should" look like.
    """
    cleaned = cleaner.clean_artifact(
        a_scanned_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
    )
    assert cleaned.artifact is not None
    assert cleaned.artifact.kind is cleaner.MediaKind.PDF
    assert cleaned.artifact.raster is not None
    assert np.array_equal(cleaned.artifact.raster, cleaned.cleaned), (
        "the artifact's raster and the document's cleaned field must be the same array"
    )


def test_a_text_layer_pdf_passed_through_reports_every_field_exactly() -> None:
    """`_pdf_passed_through` builds `CleanedDocument` and its one
    `QualityObservation` directly (not through `replace_artifact`), so nothing
    already covers it field-by-field. Every value the function sets is
    asserted here — a mutant that swaps ANY one of them, including the note's
    wording, is caught; only `raster=None`, the field's own default, is left
    to survive, because omitting it and stating it produce the identical
    object.
    """
    source = a_text_layer_pdf()
    result = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=150)

    assert result.original.shape == (1, 1)
    assert result.original.dtype == np.uint8
    assert np.array_equal(result.original, np.zeros((1, 1), dtype=np.uint8))
    assert np.array_equal(result.cleaned, np.zeros((1, 1), dtype=np.uint8))

    assert len(result.quality_observations) == 1
    observation = result.quality_observations[0]
    assert observation.name == "text_layer_present"
    assert observation.stage is cleaner.Stage.ORIGINAL
    assert observation.value == 1.0
    assert observation.unit == "boolean"
    assert observation.note == (
        "the PDF carries an embedded text layer, so its characters are already "
        "exact. Deskewing or denoising would mean rasterising them into pixels, "
        "which destroys the text layer and loses information cleaning may never "
        "lose. Passed through unchanged."
    )

    assert result.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    assert result.artifact is not None
    assert result.artifact.kind is cleaner.MediaKind.PDF
    assert result.artifact.payload == source
    assert result.artifact.original == source
    assert result.artifact.raster is None


def test_encode_png_raises_the_exact_message_when_the_encoder_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`cv2.imencode` cannot be MADE to return `ok=False` through its real
    contract on any array this module could legally pass it — measured: a
    2-channel array, a 5-channel array and a `(0, 0)` array all raise inside
    cv2 rather than returning `ok=False`. The `if not ok:` branch is real
    logic guarding a return value cv2's own Python bindings document but this
    installed build never actually produces on a legal input. Stubbed at the
    narrowest possible point — `cv2.imencode`'s return value, not its
    behaviour — so it is `_encode_png`'s OWN logic under test here (§J.7).
    """
    monkeypatch.setattr(cv2, "imencode", lambda _ext, _image: (False, np.array([], dtype=np.uint8)))
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner._encode_png(np.zeros((4, 4), dtype=np.uint8))
    assert str(excinfo.value) == (
        "the cleaned image could not be re-encoded. Reported rather than "
        "silently returning the original, which would claim a cleaning that "
        "never happened."
    )


def test_the_image_path_artifact_matches_an_independent_clean_call_field_for_field() -> None:
    """`clean_artifact`'s image path runs `_clean_image` and then calls
    `replace_artifact(document, ...)`. Comparing the result to a SEPARATE,
    direct `_clean_image` call on the same bytes and settings is an independent
    oracle for every field `replace_artifact` is responsible for copying —
    determinism (`test_cleaning_the_same_page_twice_gives_the_same_bytes`) is
    what makes the two calls comparable at all.

    ONE OF THE TWO CALLS IS DELIBERATELY THE PRIVATE ONE, and that is not a
    bypass. The claim under test is *"the entry point copies what the image
    cleaner produced, field for field"*, which cannot be checked without naming
    both sides of the copy. Every other test in this file that reaches
    `_clean_image` reaches it as the IMAGE CLEANER — the implementation
    `CLEANERS` dispatches to — and none of them is a second route into the
    module for production code, which has exactly one.
    """
    settings = a_settings()
    raw = an_image_page()
    independent = cleaner._clean_image(cleaner.decode(raw), settings)

    via_artifact = cleaner.clean_artifact(raw, cleaner.MediaKind.IMAGE, settings, render_dpi=150)

    assert np.array_equal(independent.original, via_artifact.original)
    assert np.array_equal(independent.cleaned, via_artifact.cleaned)
    assert independent.quality_observations == via_artifact.quality_observations
    assert independent.preservation_status is via_artifact.preservation_status


def test_reader_consumes_cleaner_output_and_the_text_layer_survives() -> None:
    """THE MIGRATION'S WHOLE POINT, and the test that would have caught F-012.

    Before this, `reader` re-opened the ORIGINAL document rather than consuming
    `cleaner`'s output — correctly, because the output was a bitmap and reading
    a bitmap of a PDF destroys the text layer. One pipeline is only possible if
    the cleaned artifact is still readable AS a PDF.
    """
    cleaned = cleaner.clean_artifact(
        a_text_layer_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=150
    )
    assert cleaned.artifact is not None

    reading = reader.read(
        cleaned.artifact.payload,
        media_type=reader.MediaType.PDF,
        render_dpi=150,
        vision_fallback_threshold=Decimal("0.5"),
    )

    assert reading.backend is reader.Backend.PDF_TEXT_LAYER
    recovered = " ".join(region.text for region in reading.regions)
    assert "TAX INVOICE" in recovered
    assert "27AAECS1234F1Z5" in recovered, (
        "the text layer must survive cleaning; if this fails the cleaner has "
        "rasterised a document whose characters were already exact"
    )


# ══════════════════════════════════════════════════════════════════════════
# THE DOCUMENT CLEANER — one entry point, explicit dispatch, nothing bypassed
#
# F-017, approved by the owner 2026-08-06: *"Implement a media-agnostic Document
# Cleaner as the single entry point for all supported document types. Internally
# it may dispatch to Image Cleaner, PDF Cleaner, Excel Cleaner, Email Cleaner,
# future cleaners... Remove every legacy bypass and duplicate path."*
#
# The tests below are about the DISPATCH and about what survives it. Everything
# above is about the Image Cleaner's pixels, which is a different subject.
# ══════════════════════════════════════════════════════════════════════════


def _authored_top_level_names(module: ModuleType) -> set[str]:
    """Every name `module` binds at its top level, AS AUTHORED.

    Definitions, assignments and imported aliases — the module's DECLARED
    surface, read from the authored file rather than from the loaded namespace
    so that no tool which rewrites the module can add to it (L-013).

    Imported aliases are included deliberately: `from ._legacy import clean_page`
    is exactly the bypass F-017 removed, and a scan of `def` statements alone
    would not see it.
    """
    names: set[str] = set()
    for node in authored_tree(module).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def test_the_module_offers_exactly_one_public_way_to_clean_a_document() -> None:
    """F-017's *"remove every legacy bypass"*, checked rather than asserted.

    `clean` was public, took an `NDArray`, and returned a `CleanedDocument` with
    NO `artifact` on it — an object `pipeline._payload_of` refuses and that
    `reader` and `parser` cannot consume. It had zero callers in `src/` and 67
    in `tests/`: a door held open by its own tests.

    This reads the module's public surface for ANY callable whose name says it
    cleans, so restoring the old door under a new name — `clean_image`,
    `clean_page` — fails here too. A denylist of one name would not have.

    WHICH NAMES EXIST IS A FACT ABOUT THE REPOSITORY, so it is read from the
    authored file (L-013). This asked `vars(cleaner)`, which answers a different
    question — *what is this interpreter running* — and under `mutmut` the
    answer also contains 245 injected `x__clean_image__mutmut_N` clones. Every
    one of them is public, is a function, and contains "clean", so this
    assertion went red inside mutmut's stats pass. That pass runs the whole
    suite ONCE before the first mutant and aborts on the first failure, so a
    single red test here left all 4097 mutants reported `not checked` and the
    `mutation` gate scoring nothing at all — a broken gate that reads exactly
    like an unbuilt one.

    The interpreter still decides what is a FUNCTION, because that is a fact
    about the object. It is only ever asked about names the authored file
    declares, so an injected clone cannot enter the set by construction.
    """
    declared = _authored_top_level_names(cleaner)
    public = {name for name in declared if not name.startswith("_")}
    # FUNCTIONS, not everything callable. `CleanedDocument`, `CleanerSettings`
    # and `MediaCleaner` are types whose names contain "clean" and are not doors
    # into the module; a `callable()` test would have flagged all three and this
    # assertion would have been widened until it caught nothing.
    cleaning_entry_points = {
        name
        for name in public
        if inspect.isfunction(getattr(cleaner, name, None)) and "clean" in name.lower()
    }
    assert cleaning_entry_points == {"clean_artifact"}, (
        f"the module offers {sorted(cleaning_entry_points)} as ways to clean. "
        "There is exactly one entry point, `clean_artifact`, and every media "
        "kind reaches its implementation through `CLEANERS`. A second public "
        "cleaner is the bypass F-017 removed, whatever it is called."
    )
    # BOTH directions, because neither implies the other: the authored check
    # catches `clean` being written back into the file even if something later
    # deletes it from the namespace, and the `hasattr` check catches `clean`
    # being bound at runtime by something the file does not say.
    assert "clean" not in declared, (
        "`clean` was declared again in the authored module. It is `_clean_image` "
        "— the IMAGE CLEANER the registry dispatches to — and it is private "
        "because it returns a `CleanedDocument` with no `artifact`, which the "
        "pipeline refuses by design."
    )
    assert not hasattr(cleaner, "clean"), (
        "`clean` came back as a public name. It is `_clean_image` — the IMAGE "
        "CLEANER the registry dispatches to — and it is private because it "
        "returns a `CleanedDocument` with no `artifact`, which the pipeline "
        "refuses by design."
    )


def test_every_media_kind_has_an_implementation_registered_for_it() -> None:
    """A member with no implementation is a document type that raises at the
    moment a real user submits one, not at the moment somebody adds the member.

    This is what makes "adding Excel is a member plus an implementation" a
    checked statement: add the member alone and this goes red immediately.
    """
    unregistered = sorted(kind.value for kind in cleaner.MediaKind if kind not in cleaner.CLEANERS)
    assert unregistered == [], (
        f"MediaKind member(s) with no cleaner registered: {unregistered}. Add "
        "the implementation to `CLEANERS` in the same change as the member."
    )
    assert set(cleaner.CLEANERS) == set(cleaner.MediaKind), (
        "the registry names a kind that is not a MediaKind member, so a "
        "document could be dispatched to a cleaner nothing can ask for."
    )


def test_a_kind_this_module_has_never_heard_of_dispatches_without_the_dispatcher_changing() -> None:
    """THE EXTENSIBILITY PROOF. Registration is the whole cost of a new kind.

    `"spreadsheet"` is not a `MediaKind` member and this file does not add one.
    At runtime a `StrEnum` member IS its own string — measured:
    `hash(MediaKind.PDF) == hash("pdf")` is `True` — so this string is exactly
    what a future `MediaKind.SPREADSHEET = "spreadsheet"` would hash and compare
    as. It is a faithful stand-in for a member, not a mock of one.

    NOTHING IN `cleaner.py` KNOWS THIS KIND EXISTS. If `clean_artifact` still
    branched on `kind is MediaKind.PDF`, an unknown kind could only fall into
    the image branch or raise — and either way the implementation below would
    never run. That it runs, and that its return value comes back untouched, is
    what "adding Excel later is a member plus an implementation and nothing
    else" means in code.

    NEITHER EXCEL NOR EMAIL IS IMPLEMENTED HERE, deliberately: F-017 names them
    as FUTURE cleaners and Law 16 forbids building outside the current mission.
    What this change owed them was a seam, and this is the seam being proved.
    """
    spreadsheet = cast(cleaner.MediaKind, "spreadsheet")
    seen: list[tuple[bytes, cleaner.CleanerSettings, int]] = []
    answer = cleaner.CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=cleaner.PreservationStatus.CLEANED_IS_SAFER,
        artifact=cleaner.CleanedArtifact(
            kind=spreadsheet, payload=b"cleaned workbook", original=b"workbook"
        ),
    )

    def a_spreadsheet_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        seen.append((data, settings, render_dpi))
        return answer

    settings = a_settings()
    cleaned = cleaner.clean_artifact(
        b"workbook",
        spreadsheet,
        settings,
        render_dpi=RENDER_DPI,
        cleaners={**cleaner.CLEANERS, spreadsheet: a_spreadsheet_cleaner},
    )

    assert seen == [(b"workbook", settings, RENDER_DPI)], (
        "the registered cleaner was not reached with the caller's own bytes, settings and DPI"
    )
    assert cleaned is answer, "the dispatcher altered what the implementation returned"


def test_the_registered_kinds_still_dispatch_when_a_new_one_is_added_beside_them() -> None:
    """Adding a kind must not disturb the kinds already there — otherwise
    "one member plus one implementation" costs a regression somewhere else.
    """
    spreadsheet = cast(cleaner.MediaKind, "spreadsheet")

    def never_called(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        # The full `MediaCleaner` signature, deliberately unused: this exists to
        # prove it is NEVER reached, and a narrower signature could not be
        # registered at all.
        del data, settings, render_dpi
        raise AssertionError("an image was dispatched to the spreadsheet cleaner")

    cleaned = cleaner.clean_artifact(
        an_image_page(),
        cleaner.MediaKind.IMAGE,
        a_settings(),
        render_dpi=RENDER_DPI,
        cleaners={**cleaner.CLEANERS, spreadsheet: never_called},
    )

    assert cleaned.artifact is not None
    assert cleaned.artifact.kind is cleaner.MediaKind.IMAGE


def test_a_kind_with_no_cleaner_is_refused_loudly_and_never_cleaned_as_something_else() -> None:
    """The failure that must NOT be quiet, and must NOT be a document verdict.

    Falling back to another kind's implementation would clean the document as
    something it is not. Reporting *"this document could not be read"* would be
    worse still: it asserts a fault in the user's file when the fault is a
    missing implementation in this engine (`ENGINE_1:337`). So the error sits
    outside `pipeline.BUSINESS_FAILURE` on purpose, and that is asserted here
    rather than left to the reader.
    """
    with pytest.raises(cleaner.NoCleanerRegisteredError) as raised:
        cleaner.clean_artifact(
            b"workbook",
            cast(cleaner.MediaKind, "spreadsheet"),
            a_settings(),
            render_dpi=RENDER_DPI,
        )

    assert "spreadsheet" in str(raised.value)
    assert not isinstance(raised.value, cleaner.UnusableArtifactError), (
        "a missing implementation was classified as a fault in the document"
    )


def test_the_registry_cannot_be_edited_through_the_module() -> None:
    """A registry anything could mutate is a registry that can be changed from
    under a running pipeline, and the change would be invisible to every test
    that ran before it.
    """
    editable = cast(dict[cleaner.MediaKind, cleaner.MediaCleaner], cleaner.CLEANERS)
    with pytest.raises(TypeError):
        editable[cleaner.MediaKind.IMAGE] = cleaner.CLEANERS[cleaner.MediaKind.PDF]


# ── a cleaned PDF is still a PDF (F-011, F-017's original defect) ──────────


def text_layer_of(payload: bytes) -> str:
    """Every page's embedded text, read with the backend directly.

    Read with PyMuPDF rather than through `reader` on purpose: `reader` falls
    back to OCR when it finds no text layer, so a rasterised PDF could still
    come back carrying the right words and this test would pass on exactly the
    document it exists to refuse.
    """
    document = importlib.import_module("pymupdf").open(stream=payload, filetype="pdf")
    try:
        return "\n".join(document[index].get_text("text") for index in range(document.page_count))
    finally:
        document.close()


def test_a_cleaned_text_layer_pdf_still_carries_its_text_layer() -> None:
    """F-011 AND F-017'S ORIGINAL DEFECT, TRAPPED PERMANENTLY.

    `CleanedArtifact.payload` used to be a bitmap, so cleaning a text-layer PDF
    replaced exact characters with pixels. Nothing downstream could tell: `reader`
    would OCR the raster and return plausible text, at a confidence no recogniser
    should ever have had to produce for a document whose characters were already
    exact.

    So this reads the TEXT LAYER, with the PDF library, and never through
    `reader`. A rasterised page has no text layer at all, so this assertion is
    zero on exactly the failure it guards and cannot be satisfied by an OCR
    result that happens to be right.
    """
    original = a_text_layer_pdf()
    cleaned = cleaner.clean_artifact(
        original, cleaner.MediaKind.PDF, a_settings(), render_dpi=RENDER_DPI
    )

    assert cleaned.artifact is not None
    recovered = text_layer_of(cleaned.artifact.payload)
    assert "TAX INVOICE" in recovered, (
        "the cleaned PDF carries no text layer. Cleaning rasterised a document "
        "whose characters were already exact, which is F-011/F-017 exactly: it "
        "destroys the one thing that lets the document be read with no "
        "recognition and no confidence loss at all."
    )
    assert "27AAECS1234F1Z5" in recovered
    assert text_layer_of(original) == recovered, (
        "the text layer changed. `cleaner` alters presentation and nothing "
        "else, and a digitally-generated PDF has no presentation defect to fix."
    )


def test_the_text_layer_guard_goes_red_on_a_cleaner_that_rasterises() -> None:
    """FALSIFICATION. The guard above is only worth having if it FAILS on the
    defect it names, and today's cleaner passes it by passing the PDF through —
    so on this tree it can never have been observed failing.

    A rasterising PDF cleaner is registered here, through the same public
    `cleaners` seam the extensibility test uses, and the guard is run against
    its output. This is what F-017's implementation actually did before it was
    fixed, so the red below is the historical defect reproduced rather than an
    imagined one.
    """

    def a_rasterising_pdf_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        """Render every page and rebuild — correct for a SCAN, destructive here."""
        return cleaner._pdf_rebuilt_from_cleaned_pages(data, settings, render_dpi=render_dpi)

    cleaned = cleaner.clean_artifact(
        a_text_layer_pdf(),
        cleaner.MediaKind.PDF,
        a_settings(),
        render_dpi=RENDER_DPI,
        cleaners={**cleaner.CLEANERS, cleaner.MediaKind.PDF: a_rasterising_pdf_cleaner},
    )

    assert cleaned.artifact is not None
    assert "TAX INVOICE" not in text_layer_of(cleaned.artifact.payload), (
        "a PDF rebuilt from rendered pages still reported a text layer, so the "
        "guard above cannot distinguish a preserved document from a destroyed "
        "one and proves nothing"
    )


def test_a_cleaned_text_layer_pdf_keeps_its_page_count_and_page_order() -> None:
    """Page structure and page ORDER are two of the four things F-017 requires
    preserved, and neither is visible in a text-presence check: a cleaner that
    kept every character while reversing the pages would pass that one.

    Each page prints its own number, so the recovered text is an order
    fingerprint that reads correctly only if the pages came back as they went in.
    """
    original = a_numbered_text_layer_pdf(pages=PAGES_IN_THE_ORDER_FIXTURE)
    cleaned = cleaner.clean_artifact(
        original, cleaner.MediaKind.PDF, a_settings(), render_dpi=RENDER_DPI
    )

    assert cleaned.artifact is not None
    fitz = importlib.import_module("pymupdf")
    before = fitz.open(stream=original, filetype="pdf")
    after = fitz.open(stream=cleaned.artifact.payload, filetype="pdf")
    try:
        assert after.page_count == before.page_count == PAGES_IN_THE_ORDER_FIXTURE
        for index in range(PAGES_IN_THE_ORDER_FIXTURE):
            assert f"PAGE {index + 1}" in after[index].get_text("text"), (
                f"page {index + 1} of the cleaned PDF is not page {index + 1} of "
                "the original; cleaning reordered the document"
            )
    finally:
        after.close()
        before.close()


def test_a_cleaned_text_layer_pdf_keeps_its_metadata() -> None:
    """Metadata is the fourth thing F-017 names, and the easiest to lose without
    noticing: a rebuild starts from an empty document and carries none of it.
    """
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        page = document.new_page(width=400, height=200)
        page.insert_text((40, 60), "TAX INVOICE")
        document.set_metadata({"title": "Invoice 2026-0041", "author": "Acme Traders"})
        original = bytes(document.tobytes())
    finally:
        document.close()

    cleaned = cleaner.clean_artifact(
        original, cleaner.MediaKind.PDF, a_settings(), render_dpi=RENDER_DPI
    )

    assert cleaned.artifact is not None
    opened = fitz.open(stream=cleaned.artifact.payload, filetype="pdf")
    try:
        assert opened.metadata["title"] == "Invoice 2026-0041"
        assert opened.metadata["author"] == "Acme Traders"
    finally:
        opened.close()


def a_numbered_text_layer_pdf(pages: int) -> bytes:
    """A text-layer PDF whose every page says which page it is."""
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        for number in range(1, pages + 1):
            page = document.new_page(width=400, height=200)
            page.insert_text((40, 60), f"TAX INVOICE PAGE {number}")
        return bytes(document.tobytes())
    finally:
        document.close()


def test_a_scanned_pdf_is_rasterised_because_there_was_never_a_text_layer_to_lose() -> None:
    """The other half of the rule, and the reason it is not "never rasterise".

    A scan has no text layer, so rendering its pages loses nothing — and it is
    the ONLY way its pixels can be deskewed and denoised at all. Cleaning a
    text-layer PDF and cleaning a scan are different answers to the same
    question, decided by measuring the document rather than by the caller
    declaring anything.
    """
    cleaned = cleaner.clean_artifact(
        a_scanned_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=RENDER_DPI
    )

    assert cleaned.artifact is not None
    assert cleaned.artifact.kind is cleaner.MediaKind.PDF
    assert cleaned.artifact.payload != cleaned.artifact.original, (
        "the scan came back byte-identical, so no cleaning happened to pixels "
        "that had every physical defect cleaning exists to reduce"
    )
    assert cleaned.artifact.raster is not None, (
        "a rasterised path produced no raster view, so OCR has nothing to read"
    )


# ══════════════════════════════════════════════════════════════════════════
# THE ARITHMETIC AND THE WORDING NOTHING WAS READING
#
# Everything above reaches `cleaner` through a page. That is the right way to
# ask *"does the cleaner clean?"* and it is a bad way to ask *"is the constant
# in this bound the constant the docstring names?"* — a page averages the
# helpers together, so a factor of two here and a border row there can both
# move and still land inside a tolerance chosen for the whole pipeline.
#
# Mutation testing found exactly that gap. Every test below pins ONE helper's
# stated contract with numbers small enough to check by hand, and every number
# in it was produced by running the code, never chosen to fit.
# ══════════════════════════════════════════════════════════════════════════

#: `_extreme_normal`'s guard: below two draws there is no maximum to expect.
NO_DRAWS = 0
ONE_DRAW = 1
TWO_DRAWS = 2
FOUR_DRAWS = 4
MANY_DRAWS = 1000

#: The ring page below is 6 rows by 10 columns so that its border carries
#: exactly as many dark pixels as light ones: 16 at `RING_DARK` (the two full
#: rows, less the four corners the columns claim) and 16 at `RING_LIGHT` (the
#: two full columns, plus those four corners). A median taken over a balanced
#: multiset sits between the two, so swapping any ONE of the four edges for the
#: line just inside it unbalances the count and moves the answer.
RING_HEIGHT = 6
RING_WIDTH = 10
RING_DARK = 40
RING_LIGHT = 200
RING_INTERIOR = 255
#: Measured: `(40 + 200) / 2`, the balance point of that border.
RING_BORDER_MEDIAN = 120.0

#: A four-channel fixture whose colour channels are constant and whose alpha
#: sweeps the range, so every composited value is decided by opacity alone.
ALPHA_SWEEP = ((0, 32, 64, 100, 128), (160, 191, 200, 224, 255))
MARK_INTENSITY = 64

#: `_painted_by` is asked about a frame this size; its pixels are never read.
FRAME_HEIGHT = 40
FRAME_WIDTH = 60
#: Rotation is rigid, so the region it did NOT paint is the page's own area.
#: Measured across the five turns below: 2400, 2398, 2400, 2399, 2401 against
#: an area of 2400, the shortfall being nearest-neighbour rounding on the
#: boundary. Two pixels wide; four is the bound, and INTER_LINEAR misses it by
#: 101 (measured: 2501 at seven degrees).
MAX_AREA_DISCREPANCY_PIXELS = 4
TURNS_DEGREES = (0.0, 7.0, 31.5, -12.25, 44.0)

#: A page whose only ink is a single diagonal: `minAreaRect` reports its
#: orientation as exactly 45, the one value at which the fold's comparison can
#: be observed at all.
DIAGONAL_SIDE = 80
EXACTLY_HALF_A_QUARTER_TURN = 45.0

#: The small page the crop tests use. Wider than `denoise_search_window` so it
#: would also survive `_receive`, though these call the crop directly.
SMALL_HEIGHT = 60
SMALL_WIDTH = 90
SMALL_PAPER = 235
SMALL_INK = 30
#: Measured: the turned page cropped to (21, 32) when told which pixels the
#: rotation painted, and to the whole (88, 106) canvas when not told.
TURNED_CROP_WITH_PAINTED = (21, 32)
TURNED_CROP_WITHOUT_PAINTED = (88, 106)
FILL_ONE_LEVEL_BELOW_PAPER = 234.0
CROP_TEST_TURN_DEGREES = 20.0

NO_RETENTION = 0.0

#: The line-profile fixtures. Five lines, measured over 0, 1, 2, 5 and 60
#: pixels, whose means sit 235, 35, 0, 6 and 135 grey levels below the
#: lightest of them. The line over five pixels is the interesting one: its
#: deficit of 6 lies between twice its standard error (4.81) and three times
#: it (7.22), so it is content under the rule the module states and paper
#: under a wider one.
LINE_PROFILE = (0.0, 200.0, 235.0, 229.0, 100.0)
LINE_COUNTS = (0.0, 1.0, 2.0, 5.0, 60.0)
LINE_SIGMA = 3.0
#: Measured, at both sigma 3.0 and sigma 0.0.
LINES_CARRYING_A_MARK = (False, True, False, True, True)


#: Two intensities whose product overflows an 8-bit accumulator: 200 * 200 is
#: 40000, which wraps to 64. Any measurement that multiplies without widening
#: first reports 64 and looks entirely plausible.
AN_INTENSITY_THAT_OVERFLOWS_WHEN_SQUARED = 200


def test_narrowing_to_eight_bits_refuses_rather_than_casts_and_says_which_dtype() -> None:
    """`_u8` narrows OpenCV's return, and it CHECKS rather than assuming.

    OpenCV's stubs describe every return as some integer-or-float array, so the
    narrowing has to happen somewhere; the whole value of it happening here is
    that a routine which quietly starts returning `float64` fails loudly
    instead of being cast into silence. A cast changes every intensity in the
    frame, which `ENGINE_1:453` forbids outright.

    The whole message is asserted, and it is deliberately NOT the same sentence
    `_receive` raises for the same dtype. One is about what a caller handed in
    and the other about what a library handed back, and a reader chasing a
    corrupted page needs to know which.
    """
    with pytest.raises(cleaner.UnusableArtifactError) as excinfo:
        cleaner._u8(np.zeros((2, 2), dtype=np.float32))
    assert str(excinfo.value) == (
        "expected an 8-bit (uint8) image, got float32. Casting would "
        "change every intensity in the frame, which is the original altered."
    )
    assert str(excinfo.value) != a_dtype_refusal("float32"), (
        "`_u8` and `_receive` now raise the same sentence, so nothing downstream "
        "can tell a bad input from a bad library return"
    )


def test_widening_to_float_actually_widens_or_every_later_product_wraps() -> None:
    """`_f64` exists so that arithmetic on a page happens in floating point.

    Hand it back the array unchanged and every measurement built on it computes
    in the page's own 8-bit type: 200 squared becomes 64, an ink count becomes a
    count of something else, and nothing raises. The dtype IS the behaviour
    here, so it is asserted directly and then demonstrated on the multiplication
    that would wrap.
    """
    page: Image = np.full((3, 3), AN_INTENSITY_THAT_OVERFLOWS_WHEN_SQUARED, dtype=np.uint8)

    widened = cleaner._f64(page)

    assert widened.dtype == np.float64
    assert float((widened * widened)[0, 0]) == float(AN_INTENSITY_THAT_OVERFLOWS_WHEN_SQUARED**2), (
        "the square wrapped, so the widening did not happen"
    )
    assert cleaner._f64([1, 2, 3]).dtype == np.float64, (
        "a sequence that is not already an array was left at its own integer type"
    )


def test_the_extreme_factor_is_the_expected_maximum_of_that_many_draws() -> None:
    """`sqrt(2 ln n)`, and the guard below two draws.

    The module's crop allowance is this factor times a standard error, so the
    two inside the square root decides how faint a mark has to be before the
    crop is allowed to throw it away. A page-level test cannot see it: a
    different factor moves a box by a few rows and every geometric tolerance in
    this file is wider than that.

    `draws == 1` is asserted from both sides. `log(1)` is zero, so the guarded
    branch and the arithmetic branch agree there by algebra — which is why the
    boundary has to be pinned by its VALUE and not by which branch ran.
    """
    assert cleaner._extreme_normal(TWO_DRAWS) == pytest.approx(math.sqrt(2.0 * math.log(2.0)))
    assert cleaner._extreme_normal(FOUR_DRAWS) == pytest.approx(math.sqrt(2.0 * math.log(4.0)))
    assert cleaner._extreme_normal(MANY_DRAWS) == pytest.approx(math.sqrt(2.0 * math.log(1000.0)))
    assert cleaner._extreme_normal(ONE_DRAW) == 0.0
    assert cleaner._extreme_normal(NO_DRAWS) == 0.0


def test_a_line_no_pixel_of_which_is_on_the_document_averages_to_zero_not_to_nan() -> None:
    """A row made entirely of pixels rotation painted has no mean to report.

    Dividing by its count would be dividing by zero, and the `nan` that
    produces propagates into `_lines_with_content` as a comparison that is
    False whatever the page holds — a page whose every mark silently stops
    being findable. The module substitutes one for the divisor; this checks the
    RESULT is a real zero rather than checking which divisor was used.
    """
    intensity = _f64(np.full((4, 5), 200.0))
    nothing_present = _f64(np.zeros((4, 5)))

    profile, counts = cleaner._line_profile(intensity, nothing_present, axis=1)

    assert np.array_equal(counts, np.zeros(4)), "a line of painted pixels was counted as present"
    assert np.array_equal(profile, np.zeros(4)), (
        f"a line with nothing on it reported {profile.tolist()}; `nan` here makes every "
        "later comparison False and the whole page unfindable"
    )


def test_a_profile_in_which_no_line_was_measured_is_blank_and_boolean() -> None:
    """The early return, checked for its SHAPE and its DTYPE as well as its
    emptiness. `_content_box` indexes the page with what comes back, so a
    float array of zeros is not the same answer as a boolean array of zeros
    even though both are falsy.
    """
    blank = cleaner._lines_with_content(_f64([0.0, 0.0, 0.0]), _f64(np.zeros(3)), LINE_SIGMA)

    assert blank.shape == (3,)
    assert blank.dtype == np.bool_, f"the blank answer came back as {blank.dtype}, not a mask"
    assert not blank.any()


def test_a_line_with_no_pixel_on_the_document_is_blank_whatever_its_profile_says() -> None:
    """*"A line with no unpainted pixels at all has nothing to say and is
    blank."* Asserted with a profile that SHOUTS — 300, well outside the range
    an 8-bit page can produce — so the only thing that can keep it out of the
    answer is the count beside it.
    """
    carries = cleaner._lines_with_content(_f64([300.0, 100.0, 90.0]), _f64([0.0, 9.0, 9.0]), 3.0)

    assert carries.tolist() == [False, False, True], (
        "a line measured over no pixels at all was allowed to decide the page's "
        "lightest level and then to carry a mark"
    )


def test_the_content_allowance_is_twice_the_standard_error_and_the_boundary_is_open() -> None:
    """The bound the crop is drawn with, pinned at its exact constant.

    Five lines, measured over 0, 1, 2, 5 and 60 pixels. At sigma 3.0 the line
    over five pixels sits 6 grey levels below the lightest, against an
    allowance of 2 x 2.407 = 4.81 — content. Three times the same standard
    error is 7.22, so a wider factor drops it, and this fixture is the only
    thing in the suite that can see the difference.

    Sigma 0.0 is asserted for the other edge. A page with no noise gives every
    line an allowance of exactly zero, so the LIGHTEST line's own deficit is
    exactly zero — and it must not be content, because a comparison that
    included its own reference point would call a blank page content
    everywhere. Both runs give the same answer, and they give it for opposite
    reasons.
    """
    profile = _f64(LINE_PROFILE)
    counts = _f64(LINE_COUNTS)

    assert tuple(cleaner._lines_with_content(profile, counts, LINE_SIGMA).tolist()) == (
        LINES_CARRYING_A_MARK
    )
    assert tuple(cleaner._lines_with_content(profile, counts, 0.0).tolist()) == (
        LINES_CARRYING_A_MARK
    )


def a_page_with_a_ring_the_median_balances_on() -> Image:
    """A page whose border is half dark and half light, and whose inside is
    neither. See `RING_BORDER_MEDIAN` for why the counts balance.
    """
    sheet: Image = np.full((RING_HEIGHT, RING_WIDTH), RING_INTERIOR, dtype=np.uint8)
    sheet[0, :] = RING_DARK
    sheet[-1, :] = RING_DARK
    sheet[:, 0] = RING_LIGHT
    sheet[:, -1] = RING_LIGHT
    return sheet


def test_the_rotation_fill_is_taken_from_the_page_edge_and_not_from_just_inside_it() -> None:
    """The intensity rotation paints into the corners comes off the artifact.

    A row one step inside the edge is already the document, so a fill taken
    from there is a fill taken from CONTENT — and the module then paints that
    content into a region where the document has nothing, which
    `_line_profile` reads back as a mark on a page that never carried one.

    Measured: 120.0 from the four edges; 200.0 or 40.0 from any line one step
    in, on this page.
    """
    ringed = a_page_with_a_ring_the_median_balances_on()

    assert cleaner._border_median(ringed) == RING_BORDER_MEDIAN, (
        "the fill was measured somewhere other than the page's four edges"
    )


def a_stamp_at_every_opacity() -> Image:
    """One mark intensity, ten opacities. A background remover's ordinary
    output: the colour channels say one thing everywhere and the shape lives
    entirely in alpha.
    """
    alpha: Image = np.asarray(list(ALPHA_SWEEP) * 2, dtype=np.uint8)
    grey: Image = np.full(alpha.shape, MARK_INTENSITY, dtype=np.uint8)
    return _u8(np.stack([grey, grey, grey, alpha], axis=-1))


def test_a_transparent_pixel_shows_the_paper_through_in_proportion_to_its_opacity() -> None:
    """Alpha compositing, checked against the interpolation form of itself.

    The module writes the composite as a weighted SUM — mark times opacity plus
    paper times the rest. This checks it against the LERP form — the paper,
    moved toward the mark by the opacity — which is the same quantity reached
    by different arithmetic, so a dropped minus sign or a factor on the wrong
    term cannot be shared between the code and the check.

    It matters because the whole channel is a document's content: a stamp of
    40320 visible pixels and a blank canvas used to flatten to the same page
    (`KNOWN_FAILURES.md` D4). Getting the shape back is not enough — the
    INTENSITIES have to be right, or `reader` sees strokes at the wrong weight.
    """
    stamp = a_stamp_at_every_opacity()
    opacity = _f64(stamp[..., 3]) / float(np.iinfo(np.uint8).max)
    paper = float(np.iinfo(np.uint8).max)
    lerped = _u8(np.rint(paper + (float(MARK_INTENSITY) - paper) * opacity))

    composited = cleaner._composite_over_paper(stamp)

    assert composited.dtype == np.uint8
    assert np.array_equal(composited, lerped), (
        f"composited {composited.tolist()} against {lerped.tolist()}"
    )
    # Both ends, stated separately: a fully transparent pixel IS the paper and a
    # fully opaque one IS the mark, and an equality against a formula alone
    # would still pass if both were wrong in the same direction.
    assert int(composited[0, 0]) == int(paper)
    assert int(composited[1, -1]) == MARK_INTENSITY


def test_the_region_rotation_painted_is_exactly_the_canvas_the_page_could_not_cover() -> None:
    """Rotation is rigid, so it preserves area. That is the oracle.

    The painted mask names the pixels this module invented; its complement is
    therefore the page itself, turned. A rigid turn cannot change how many
    pixels a page has, so the complement's size must be the page's area — 2400
    here — whatever the angle. Measured across the five turns: 2400, 2398,
    2400, 2399 and 2401, the shortfall being nearest-neighbour rounding along
    the new boundary.

    That single invariant catches three different ways of getting this wrong:
    an interpolated membership (INTER_LINEAR leaves the boundary ramp
    unclaimed — measured 2501 at seven degrees), a fill value the equality
    below cannot then find, and an equality testing for the wrong side of the
    membership. Each of those reports a page as larger than it is, and each
    ends with a measurement averaging in a region no document ever occupied.
    """
    frame: Image = np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)

    for degrees in TURNS_DEGREES:
        painted = cleaner._painted_by(frame, degrees)
        canvas = int(painted.size)
        invented = int(np.count_nonzero(painted))

        assert sorted(np.unique(painted).tolist()) in ([0], [0, 255]), (
            f"at {degrees} degrees the painted mask carries {np.unique(painted).tolist()}; "
            "a membership has two values"
        )
        assert abs((canvas - invented) - FRAME_HEIGHT * FRAME_WIDTH) <= (
            MAX_AREA_DISCREPANCY_PIXELS
        ), (
            f"at {degrees} degrees the unpainted region holds {canvas - invented} pixels "
            f"against the page's {FRAME_HEIGHT * FRAME_WIDTH}"
        )

    assert int(np.count_nonzero(cleaner._painted_by(frame, 0.0))) == 0, (
        "a page that was not turned has no painted region at all"
    )


def a_page_of_one_diagonal_stroke() -> Image:
    """A page whose only ink runs corner to corner.

    `minAreaRect` reports its orientation as exactly 45.0 — measured — which
    makes it the one fixture on which two separate boundaries are observable:
    the fold's half-open interval, and a caller's deskew limit set to the same
    number as the skew being judged.
    """
    diagonal: Image = np.full((DIAGONAL_SIDE, DIAGONAL_SIDE), SMALL_PAPER, dtype=np.uint8)
    np.fill_diagonal(diagonal, SMALL_INK)
    return diagonal


def test_a_skew_of_exactly_forty_five_degrees_is_reported_as_a_positive_turn() -> None:
    """The fold's boundary, and the only page on which it is observable.

    A rectangle's orientation repeats every quarter turn, so the module folds
    the measured angle into (-45, 45]. The interval is half-open, and 45 is the
    end that is IN it: a page reported at 45 and a page reported at -45 are
    turned the same way in geometry and opposite ways to a reader, and every
    other angle folds identically either way.
    """
    assert cleaner._measure_skew(a_page_of_one_diagonal_stroke()) == EXACTLY_HALF_A_QUARTER_TURN


def test_a_skew_exactly_at_the_callers_limit_is_corrected_and_not_refused() -> None:
    """`max_deskew_degrees` is a MAXIMUM, so the value itself is allowed.

    The refusal exists because *"a detector that reports 32 degrees on a
    document is usually a detector that failed"*, and the caller says where
    that begins. A limit of 45 that refuses 45 is a limit of 44.9999 — the
    caller's number silently shifted by one comparison, and the only page on
    which anyone could ever notice is one whose skew lands exactly on it.

    Both sides are asserted from the SAME page, so the difference between them
    is the setting and nothing else: at a limit of 45 it turns, at 15 it does
    not, and the refusal names the number that refused it.
    """
    diagonal = a_page_of_one_diagonal_stroke()

    _grey, _carried, painted, applied, _filled = cleaner._deskew(
        diagonal, diagonal, settings(max_deskew_degrees=EXACTLY_HALF_A_QUARTER_TURN)
    )

    assert applied.value == EXACTLY_HALF_A_QUARTER_TURN, (
        "a skew exactly at the caller's limit was refused, which makes the limit "
        "one they did not set"
    )
    assert applied.note == "rotation applied onto a canvas grown to hold the whole rotated frame."
    assert painted is not None, "a page that was turned reported no painted region"


def test_the_deskew_observations_say_exactly_what_was_done_and_why() -> None:
    """The three deskew outcomes, each pinned field by field.

    `ENGINE_1:626` — every marker carries a reason. These are the reasons a
    page came back unturned, and the two are not interchangeable: *"no ink"*
    says the page has nothing to orient, while *"the measured skew exceeds
    max_deskew_degrees"* says there was a reading and the caller's setting
    rejected it. `confidence` treats those differently, and a blank page
    reported as a rejected reading is a document described as something it is
    not (`ENGINE_1:337`).

    The refusal's wording carries BOTH numbers — what was measured and what
    refused it — so a reader can see whether to change the setting or the
    scanner. Asserting it whole is the only way that survives a rewording.

    `deskew_fill_intensity` is checked on every branch because the fill is
    reported from here on all three, and its value is asserted against a page
    whose border is one intensity by construction rather than against the
    module's own median.
    """
    blank = a_small_uniform_page()
    _g1, _c1, unpainted, applied_to_blank, filled_on_blank = cleaner._deskew(blank, blank, BASELINE)

    assert unpainted is None, "a page that was not turned reported a painted region"
    assert (applied_to_blank.name, applied_to_blank.stage, applied_to_blank.value) == (
        cleaner.DESKEW_APPLIED,
        cleaner.Stage.CLEANED,
        0.0,
    )
    assert applied_to_blank.unit == "degrees"
    assert applied_to_blank.note == (
        "no rotation: the page carries no ink, so no skew is measurable."
    )
    assert (filled_on_blank.name, filled_on_blank.stage, filled_on_blank.unit) == (
        cleaner.DESKEW_FILL_INTENSITY,
        cleaner.Stage.CLEANED,
        "grey levels",
    )
    assert filled_on_blank.value == float(SMALL_PAPER), (
        "the fill was not the intensity of the page this stage received"
    )
    assert filled_on_blank.note == (
        "the intensity rotation fills its corners with, taken as the median "
        "of the border of the page this stage received rather than chosen here."
    )

    diagonal = a_page_of_one_diagonal_stroke()
    _g2, _c2, still_unpainted, refused, filled_on_refusal = cleaner._deskew(
        diagonal, diagonal, BASELINE
    )

    assert still_unpainted is None
    assert refused.value == 0.0
    assert refused.unit == "degrees"
    assert refused.note == (
        "no rotation: the measured skew 45.0000 degrees exceeds "
        f"max_deskew_degrees ({BASELINE.max_deskew_degrees}). The page is "
        "left as received rather than turned on a reading that far out."
    )
    assert filled_on_refusal.value == float(SMALL_PAPER)


def a_small_uniform_page() -> Image:
    return np.full((SMALL_HEIGHT, SMALL_WIDTH), SMALL_PAPER, dtype=np.uint8)


def a_small_banded_page() -> Image:
    """A page with one printed band, so it has a content box to be cropped to."""
    sheet = a_small_uniform_page()
    sheet[5:15, 10:80] = SMALL_INK
    return sheet


def test_a_page_with_no_content_box_comes_back_whole_and_at_full_retention() -> None:
    """A blank sheet cropped to nothing would read downstream as a document
    that genuinely held nothing, so it is returned as it arrived — and the
    retention it reports is a FRACTION, which cannot exceed one.
    """
    blank = a_small_uniform_page()

    cropped, kept, origin = cleaner._crop_to_content(blank, BASELINE.crop_margin_pixels)

    assert np.array_equal(cropped, blank)
    assert kept == FULL_RETENTION
    assert origin == (0, 0), (
        "the page came back whole, so nothing was translated and its origin is "
        "its own; any other value would misplace every coordinate on it"
    )


def test_a_page_with_no_ink_at_all_reports_full_retention_after_a_real_crop() -> None:
    """The other zero. Here there IS a box — drawn from a second page, the way
    `_clean_image` draws it from the document's own intensities — but the page
    being cropped carries nothing Otsu calls ink, so the quotient has no
    denominator. Reporting a fraction above one instead would put a number in
    the artifact that cannot be true of any page.
    """
    blank = a_small_uniform_page()
    ink, _threshold = cleaner._ink_mask(blank)
    assert int(np.count_nonzero(ink)) == 0, "the fixture is not the no-ink case it claims to be"

    _cropped, kept, origin = cleaner._crop_to_content(blank, 0, a_small_banded_page())

    assert kept == FULL_RETENTION
    assert origin == (10, 5), "the box came from the banded page, so the origin must too"


def test_a_crop_that_throws_away_the_only_ink_pixel_reports_that_it_kept_none() -> None:
    """One ink pixel, outside the box, and the figure that has to say so.

    A single mark is the smallest thing this module can destroy and the hardest
    for a fraction to report: every rounding and every tolerance in the suite is
    wider than one pixel in a hundred thousand. Counting it as a special case
    instead — "one is as good as none" — would report full retention for a page
    whose only mark had just been deleted.
    """
    losing = a_small_uniform_page()
    losing[SMALL_HEIGHT - 2, SMALL_WIDTH - 2] = 0
    ink, _threshold = cleaner._ink_mask(losing)
    assert int(np.count_nonzero(ink)) == 1, "the fixture does not carry exactly one ink pixel"

    _cropped, kept, _origin = cleaner._crop_to_content(losing, 0, a_small_banded_page())

    assert kept == NO_RETENTION, (
        "the crop discarded the page's only ink pixel and reported that it had kept some"
    )


def test_the_crop_box_is_drawn_from_the_document_and_never_from_the_rotation_fill() -> None:
    """The failure the `painted` argument exists to stop, reproduced.

    Rotation fills the corners with the page's own border median. One grey
    level below the paper is an ordinary value for it, and to a line profile
    calibrated on noise a whole row of it reads as a faint mark — so the crop
    keeps the entire grown canvas and the page is delivered with its corners
    still on it. Measured on this page: (21, 32) when the painted region is
    named, (88, 106) when it is not, against a canvas of 88 by 106.

    The two shapes are asserted as a PAIR. The tight one alone could also be
    produced by a crop that ignored the fill because the fill happened to be
    invisible, and the pair says the fill was there and was excluded.
    """
    body = a_small_uniform_page()
    body[20:30, 30:60] = SMALL_INK
    turned_page = cleaner._rotate_whole_frame(
        body, CROP_TEST_TURN_DEGREES, FILL_ONE_LEVEL_BELOW_PAPER
    )
    painted = cleaner._painted_by(body, CROP_TEST_TURN_DEGREES)

    told, _kept, told_origin = cleaner._crop_to_content(turned_page, 0, turned_page, painted)
    untold, _also, untold_origin = cleaner._crop_to_content(turned_page, 0, turned_page, None)

    assert told.shape == TURNED_CROP_WITH_PAINTED
    assert untold.shape == TURNED_CROP_WITHOUT_PAINTED, (
        "the fixture's fill was not visible to the line profile, so this test "
        "would pass whether or not the painted region was excluded"
    )
    assert untold_origin == (0, 0), (
        "the untold crop kept the entire grown canvas, so it translated nothing"
    )
    assert told_origin != (0, 0), (
        "the told crop trimmed the fill off two sides and reported the origin of "
        "a crop that did not move — every coordinate on it would be misplaced by "
        "the inset the shape assertion above proves it took"
    )


#: Non-default values for the three settings whose baseline happens to equal
#: OpenCV's own default. Each is legal, and each is far enough from the baseline
#: to change the page — measured below.
NARROW_TEMPLATE_WINDOW = 3
NARROW_SEARCH_WINDOW = 11
COARSE_TILE_GRID = 2


def test_the_three_settings_that_match_opencvs_defaults_still_reach_opencv() -> None:
    """A FINDING, and the reason this test exists at all.

    `denoise_template_window = 7`, `denoise_search_window = 21` and
    `contrast_tile_grid = 8` — the values this file has always used — are
    EXACTLY the defaults `cv2.fastNlMeansDenoising` and `cv2.createCLAHE`
    apply when the argument is left out. So on this suite's own settings, a
    cleaner that forgot to pass all three produced byte-identical pages, and
    every existing test agreed with it.

    That is not a hypothetical. `CleanerSettings` exists so that no number
    reaches OpenCV that a caller did not choose (Law 52); a setting that is
    silently dropped is the caller's number replaced by the library's, which is
    the same defect wearing a different hat. The only way to see it is to ask
    for something OTHER than the default and require the page to change.

    Each arm differs from the baseline in ONE field, so the difference cannot
    come from anywhere else.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    baseline = cleaner._clean_image(noisy, BASELINE).cleaned

    for field, value in (
        ("denoise_template_window", NARROW_TEMPLATE_WINDOW),
        ("denoise_search_window", NARROW_SEARCH_WINDOW),
        ("contrast_tile_grid", COARSE_TILE_GRID),
    ):
        changed = cleaner._clean_image(noisy, settings(**{field: value})).cleaned
        assert not np.array_equal(baseline, changed), (
            f"{field} = {value} produced the same page as {field} = "
            f"{getattr(BASELINE, field)}, so the setting never reached OpenCV and "
            "the library's default is being used in the caller's name"
        )


#: The page on which the SECOND crop is the one that throws ink away. Measured
#: by re-running both crops separately across turns, noise levels and seeds:
#: at 12 degrees and sigma 20 on this seed the first crop keeps everything and
#: the second keeps 0.9968394735600736. Every other combination tried left the
#: second factor at exactly 1.0, where a product and a quotient agree.
SECOND_CROP_TURN_DEGREES = 12.0
SECOND_CROP_SIGMA = 20.0
SECOND_CROP_SEED = 20260805
INK_KEPT_WHEN_THE_SECOND_CROP_DISCARDS = 0.9968394735600736


def a_scan_the_second_crop_trims_into() -> Image:
    """A skewed, noisy invoice with a mark in the margin.

    Deliberately a whole page rather than a helper call: what makes it work is
    the exact combination of turn, noise and seed above, and any of the three
    changing puts the second crop's retention back to 1.0.
    """
    sheet: Image = np.full((PAGE_HEIGHT, PAGE_WIDTH), PAPER_INTENSITY, dtype=np.uint8)
    for row in range(80, 300, 40):
        sheet[row : row + 10, 60:840] = INK_INTENSITY
    sheet[560:563, 860:863] = INK_INTENSITY
    return with_gaussian_noise(
        turned(sheet, SECOND_CROP_TURN_DEGREES),
        SECOND_CROP_SIGMA,
    )


def test_the_two_crops_compound_and_the_reported_share_cannot_exceed_the_whole() -> None:
    """`ink_kept_by_crop` is a FRACTION, so it lives in [0, 1] — and the only
    page that can prove it is one whose SECOND crop discards something.

    Both crops report the share of the ink they kept, and the artifact carries
    the share that survived the pair. Compounding them is a product; anything
    else is not a share of anything. Divide instead and the number climbs ABOVE
    one on exactly the pages where the crop did damage — a document reported as
    having MORE ink than it started with, at the moment some of it was thrown
    away, which is a reassurance pointing the wrong way (Law 24).

    Every ordinary page hides it, because the second crop's factor is 1.0 and a
    product and a quotient agree at one. This page is the one that does not:
    measured 0.9968394735600736, all of the shortfall from the second crop.
    """
    result = cleaner._clean_image(
        a_scan_the_second_crop_trims_into(), settings(max_deskew_degrees=45.0)
    )
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)

    assert kept.value is not None
    assert kept.value == pytest.approx(INK_KEPT_WHEN_THE_SECOND_CROP_DISCARDS, rel=1e-9)
    assert kept.value < FULL_RETENTION, (
        "the fixture's crop discarded nothing, so it cannot tell a product from a quotient"
    )
    assert result.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER


#: `a_small_banded_page` paints one band of ten rows by seventy columns at ink
#: intensity onto paper, and nothing else, so its ink count under any split
#: between the two intensities is 700 pixels by arithmetic.
BAND_INK_PIXELS = 10 * 70


def test_the_ink_loss_note_says_what_was_counted_where_and_how_much_went() -> None:
    """The reported ink loss carries three numbers, and this pins all three.

    A bare fraction cannot become a good question downstream (`ENGINE_1:626`):
    *"0.0043 of the ink"* leaves a reader unable to tell four erased pixels out
    of a thousand from four thousand out of a million, and the note is where
    that lives. It also states WHICH split the counting used — the one taken
    from the artifact as received, never recomputed after the filter ran — and
    that the figure is a SET DIFFERENCE rather than a net, which is the whole
    of `KNOWN_FAILURES.md` D2.

    The numbers are checkable by hand: the fixture's only mark is a band of ten
    rows by seventy columns, so 700 pixels lie below any split between the two
    intensities on it, and a denoise that erases nothing leaves 700 and zero.
    """
    result = cleaner._clean_image(a_small_banded_page(), BASELINE)
    lost = result.observed(cleaner.INK_LOST_TO_DENOISE, cleaner.Stage.CLEANED)
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)

    assert lost.value == 0.0
    assert lost.unit == "fraction of original ink"
    assert lost.note == (
        f"{BAND_INK_PIXELS} ink pixel(s) before denoising, {BAND_INK_PIXELS} after, "
        "counted at the single split taken from the artifact as received. "
        "0 of them stopped being ink; that SET DIFFERENCE is the "
        "reported figure, because a net of the two counts lets ink gained "
        "in one region cancel a stroke destroyed in another. Denoising is "
        "the one step that can erase a stroke."
    )
    assert kept.unit == "fraction of ink pixels"
    assert kept.note == (
        "the ink inside both crops over the ink on the page, counted at "
        "Otsu's split while the boxes were drawn from the line profiles. "
        "Two different rules, so this AUDITS the boxes instead of "
        "restating them, and it is NOT 1.0 by construction — measured "
        "0.9998077292828302 on a noisy scan whose 3x3 margin mark the "
        "crop discarded, which is exactly that mark's share of the ink, "
        "against exactly 1.0 on the same scan without it. Below 1.0 "
        "means a mark Otsu called ink was thrown away."
    )


def test_every_measurement_carries_the_exact_name_unit_and_reason_it_was_written_with() -> None:
    """`ENGINE_1:626` — every marker carries a reason, and the reason is TEXT.

    `test_every_observation_carries_a_reason` above asks only that the strings
    are non-empty, which any wording satisfies. These notes are what
    `confidence` and, through it, a human reads to decide whether a number is
    usable: *"None when the page carries no ink to orient"* is the difference
    between a straight page and an empty one, and a unit of "grey levels
    squared" is the difference between a variance and a standard deviation.
    They are part of the contract, so they are asserted whole and in order.
    """
    observations = cleaner._observe(a_small_banded_page(), cleaner.Stage.ORIGINAL)

    assert [(o.name, o.stage, o.unit) for o in observations] == [
        (cleaner.SKEW_ANGLE, cleaner.Stage.ORIGINAL, "degrees"),
        (cleaner.NOISE_SIGMA, cleaner.Stage.ORIGINAL, "grey levels"),
        (cleaner.RMS_CONTRAST, cleaner.Stage.ORIGINAL, "grey levels"),
        (cleaner.LAPLACIAN_VARIANCE, cleaner.Stage.ORIGINAL, "grey levels squared"),
        (cleaner.INK_FRACTION, cleaner.Stage.ORIGINAL, "fraction of pixels"),
    ]
    assert [o.note for o in observations] == [
        (
            "the rotation that straightens the page, from the ink's rotated "
            "bounding box. None when the page carries no ink to orient."
        ),
        "Immerkaer's estimate of the additive noise standard deviation.",
        "root-mean-square contrast: the standard deviation of intensity.",
        (
            "variance of the Laplacian. A low value is a blurred artifact, "
            "which this module reports and does not attempt to repair."
        ),
        "pixels darker than the artifact's own Otsu split, as a fraction.",
    ]
    assert {o.page for o in observations} == {1}, (
        "a single page's measurements must all be attributed to page one"
    )


def test_every_page_of_a_scan_is_reported_under_its_own_number_and_the_worst_status_wins() -> None:
    """`KNOWN_FAILURES.md` D3, at the function that fixes it.

    `test_the_preservation_status_of_a_scan_does_not_depend_on_the_page_order`
    proves the DOCUMENT-level symptom is gone. It cannot see which field
    carried which value, because a scanned PDF's own measurements are whatever
    the pages happen to produce. This builds the page list from real
    `_clean_image` runs and then checks the join field by field:

        every observation is carried, in page order, unchanged except for the
        page number stamped on it — a value, a unit or a note dropped here is a
        page's evidence silently emptied

        the numbering is one-based and increments — page provenance is the
        whole point of the fix, and a constant number reports three pages as
        one

        `ORIGINAL_IS_SAFER` the moment ANY page says so, in both orders — a
        decimal point erased on the last page is not made safe by the first two

        the original, the raster and the artifact are the first page's own
        objects, by identity
    """
    clean_page = cleaner._clean_image(a_small_banded_page(), BASELINE)
    damaged_page = cleaner._clean_image(
        a_page_of_hairline_strokes(), settings(denoise_strength=ERASING_DENOISE_STRENGTH)
    )
    assert clean_page.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER
    assert damaged_page.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER

    carrier = cleaner.replace_artifact(
        clean_page,
        cleaner.CleanedArtifact(
            kind=cleaner.MediaKind.PDF, payload=b"%PDF-rebuilt", original=b"%PDF-source"
        ),
    )
    joined = cleaner._every_page_reported([carrier, damaged_page, clean_page])

    assert [o.page for o in joined.quality_observations] == (
        [1] * len(carrier.quality_observations)
        + [2] * len(damaged_page.quality_observations)
        + [3] * len(clean_page.quality_observations)
    ), "the pages were not numbered one, two, three in the order they were given"
    for source, number in ((carrier, 1), (damaged_page, 2), (clean_page, 3)):
        carried = [o for o in joined.quality_observations if o.page == number]
        assert carried == [replace(o, page=number) for o in source.quality_observations], (
            f"page {number}'s evidence was not carried across unchanged"
        )

    assert joined.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    assert (
        cleaner._every_page_reported([damaged_page, clean_page]).preservation_status
        is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    ), "a damaged first page was voted down by the clean page after it"
    assert (
        cleaner._every_page_reported([clean_page, clean_page]).preservation_status
        is cleaner.PreservationStatus.CLEANED_IS_SAFER
    ), "a document with no damaged page was still reported as damaged"

    assert joined.original is carrier.original
    assert joined.cleaned is carrier.cleaned
    assert joined.artifact is carrier.artifact, (
        "the first page's artifact was dropped, so nothing downstream can reach "
        "the document the pages came off"
    )


# ══════════════════════════════════════════════════════════════════════════
# WHERE ON THE SOURCE A CLEANED PIXEL CAME FROM — `KNOWN_FAILURES.md` F-030
#
# `_clean_image` applies THREE geometric operations and used to record none of
# them: a crop, a turn, and a second crop. `_crop_to_content` computed each
# crop's origin and dropped it on the next line; `_rotation` built the turn's
# matrix and handed it to `warpAffine` and to nobody else. So a coordinate on
# a cleaned page could not be placed on the document it came off.
#
# THE HALF-FIX THIS SECTION EXISTS TO REFUSE. F-030 names the crop origin, and
# recording the origin alone would look like the fix and be wrong on every
# scan. Measured through the real cleaner on a page planted DEAD STRAIGHT, the
# module still measures -0.3000 degrees of skew and turns the page, and the
# displacement no single translation can absorb is 0.9182 px; at 3 degrees it
# is 9.3618 px and at 15 degrees 48.8693 px. A translation-only record is not
# an approximation of the answer, it is a different answer.
#
# So the recorded map is the COMPOSITION of all three, and
# `test_the_map_is_not_a_translation_because_the_page_was_turned` is the test
# that goes red if anyone reduces it back to an origin.
#
# THE ORACLE IS THE INK'S CENTRE OF MASS, and it is one `cleaner` does not
# share. An affine map carries a centroid to the transform of the centroid,
# exactly — so the centroid is the one property a crop, a turn and a second
# crop cannot disturb, and `cv2.moments` is a route into it that this module
# uses nowhere in its geometry.


#: A source raster pixel. The bound on every round trip below, and DERIVED
#: rather than chosen (Law 10): a map into a pixel grid cannot answer more
#: precisely than the grid it answers in. `test_pdf_backend.py`'s F-031 guard
#: derives its own bound the same way, and this is the same pixel.
ONE_SOURCE_PIXEL = 1.0

#: The definition of a point. Arithmetic, not a setting.
POINTS_PER_INCH = 72.0

#: The two resolutions F-030 measured its disagreement across. The coarser one
#: sets the bound, because one of ITS pixels is the larger quantum.
COARSE_RENDER_DPI = 150
FINE_RENDER_DPI = 300


def ink_centroid(image: Image) -> tuple[float, float]:
    """The ink's centre of mass as (x, y), by moments.

    `cleaner` computes no centroid anywhere, so this is an oracle the module
    under test does not share (§J.(b)). `binaryImage=True` counts each ink
    pixel once, so the result is the geometric centroid of the ink SET and not
    an intensity-weighted one — the quantity an affine map preserves exactly.
    """
    _threshold, mask = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    moments = cv2.moments(_u8(mask), binaryImage=True)
    assert moments["m00"] > 0.0, "the fixture carries no ink, so it has no centroid to check"
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def a_skewed_invoice() -> Image:
    """The established skew fixture: text lines, padded to turn into, turned.

    Reused rather than invented so the turn this section maps through is the
    same turn the deskew tests above already prove the module measures.
    """
    return turned(padded(a_page()), KNOWN_SKEW_DEGREES)


def test_a_cleaned_pixel_maps_back_to_the_source_pixel_it_came_from() -> None:
    """F-030's headline, as a round trip through the real cleaner.

    The ink's centroid is located independently on the cleaned page and on the
    page as received. Mapping the first through the recorded geometry must land
    on the second, because an affine map carries a centroid to the transform of
    the centroid and the map is exactly a translation, a turn and a second
    translation composed.

    THE PREMISE IS CHECKED RATHER THAN ASSUMED. `ink_kept_by_crop` is asserted
    at full retention first: if a crop had thrown ink away, the two centroids
    would legitimately differ and this test would be measuring the discard
    instead of the map, and would fail for a reason that is not a defect in the
    map at all.

    Measured on this fixture: the page is turned -7.0013 degrees and the round
    trip lands 0.270661 px from the truth, against a bound of one pixel.

    THE RESIDUAL IS THE ORACLE'S, NOT THE MAP'S, and that was separated rather
    than assumed. Interpolation and CLAHE reclassify a few stroke-edge pixels,
    so the cleaned page's ink SET is not quite the affine image of the source's
    and the two centroids are entitled to differ slightly. On the solid-bar
    page of `a_page_of_solid_bars(0.0)`, where no turn fires and the ink set is
    the same region at every resolution, the identical round trip measures
    EXACTLY 0.000000 px at 150, 300 and 600 dpi.
    """
    source = a_skewed_invoice()
    result = cleaner._clean_image(source, BASELINE)

    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED).value
    assert kept == FULL_RETENTION, (
        "the crop discarded ink, so the two centroids are entitled to differ "
        "and this test would be measuring the discard rather than the map"
    )
    turn = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value
    assert turn is not None and abs(turn) > KNOWN_SKEW_DEGREES / 2.0, (
        "the fixture was not turned, so this test would pass on a map that "
        "knows nothing about rotation"
    )

    geometry = result.geometry_of()
    mapped = geometry.source_pixel(*ink_centroid(result.cleaned))
    truth = ink_centroid(cleaner._to_grey(result.original))

    assert math.hypot(mapped[0] - truth[0], mapped[1] - truth[1]) < ONE_SOURCE_PIXEL, (
        f"the cleaned page's ink centroid mapped to {mapped}, and on the page "
        f"as received it sits at {truth}. A cleaned coordinate cannot be placed "
        "on the document it came off."
    )


def test_the_map_is_not_a_translation_because_the_page_was_turned() -> None:
    """THE HALF-FIX, REFUSED. F-030 names the discarded crop origin, and a
    record of the origin alone would be a translation.

    Two assertions, and the second is the one that bites. The first says the
    map's linear part is not the identity — a turn is present in it at all. The
    second reconstructs the best translation-only answer there is, by taking
    the map's own offset and dropping its linear part, and requires it to MISS
    the source centroid by more than a pixel. Without it, a map whose linear
    part was some harmless near-identity would still pass.

    Measured: the translation-only answer lands 54.453481 px from the truth,
    where the real map lands 0.270661 px from it. Two hundred times the bound —
    this is not a fix that is nearly right without the rotation.
    """
    source = a_skewed_invoice()
    result = cleaner._clean_image(source, BASELINE)
    geometry = result.geometry_of()
    across, down = ink_centroid(result.cleaned)
    truth = ink_centroid(cleaner._to_grey(result.original))

    scale_x, shear_x, shift_x, shear_y, scale_y, shift_y = geometry.to_source
    assert (scale_x, shear_x, shear_y, scale_y) != (1.0, 0.0, 0.0, 1.0), (
        "the map's linear part is the identity, so the recorded geometry is a "
        "pure translation and the deskew rotation was never recorded"
    )

    as_a_translation = (across + shift_x, down + shift_y)
    missed = math.hypot(as_a_translation[0] - truth[0], as_a_translation[1] - truth[1])
    assert missed > ONE_SOURCE_PIXEL, (
        f"a translation-only map lands {missed:.4f} px from the truth, which is "
        "inside the bound the real map has to meet — so this test cannot tell "
        "the two apart and proves nothing about the rotation being recorded"
    )


#: The turn planted in the scanned fixture below. Small enough to be an
#: ordinary scan and large enough that the module measures a DIFFERENT angle at
#: each resolution — -3.8490 deg at 150 dpi against -4.0002 deg at 300 — which
#: is what stops this test passing on a map that records one angle for both.
SCANNED_SKEW_DEGREES = 4.0

#: The page F-030 measured its 4.80 pt disagreement on, in points. Stated so
#: the "is this answer even on the page?" assertion below reads as the question
#: it is rather than as two bare numbers.
SCANNED_PAGE_WIDTH_POINTS = 400
SCANNED_PAGE_HEIGHT_POINTS = 200


def a_page_of_solid_bars(degrees: float) -> bytes:
    """Bars, not text, and the reason is the ORACLE rather than the module.

    `an_image_page()` draws antialiased glyphs. A stroke's grey halo is a
    different FRACTION of the stroke at 300 dpi than at 150, so Otsu calls a
    different set of pixels ink and the centroid moves with the resolution
    before any map is consulted — measured, that oracle drifts 0.5692 pt across
    150 and 300 dpi on its own, which is already wider than the one-pixel bound
    this test has to meet. A test built on it measures the instrument.

    Solid bars thirty pixels thick have a halo that is a vanishing fraction of
    the shape, so the ink set is the same region at every resolution: measured,
    the same oracle drifts 0.0000 pt.
    """
    page: Image = np.full((200, 400), 255, dtype=np.uint8)
    page[40:70, 60:340] = 0
    page[90:120, 60:250] = 0
    page[140:170, 60:300] = 0
    matrix = cv2.getRotationMatrix2D((200.0, 100.0), degrees, 1.0)
    return _png_bytes(
        _u8(
            cv2.warpAffine(
                page,
                matrix,
                (400, 200),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255.0,
            )
        )
    )


def a_scanned_pdf_of_solid_bars(degrees: float) -> bytes:
    """The same 400x200 pt page F-030 measured, carrying bars instead of text.

    The image is placed to FILL the page, and the image is 400x200 pixels, so
    one authored pixel is exactly one point — which is what makes the authored
    ink position a ground truth in the unit the answer is wanted in.
    """
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        page = document.new_page(width=SCANNED_PAGE_WIDTH_POINTS, height=SCANNED_PAGE_HEIGHT_POINTS)
        page.insert_image(
            fitz.Rect(0, 0, SCANNED_PAGE_WIDTH_POINTS, SCANNED_PAGE_HEIGHT_POINTS),
            stream=a_page_of_solid_bars(degrees),
        )
        return bytes(document.tobytes())
    finally:
        document.close()


def test_cleaning_adds_no_disagreement_between_two_render_dpis() -> None:
    """F-030'S MEASURED CONSEQUENCE, AND THE NUMBER THIS CHANGE IS FOR.

    A 400x200 pt scan rebuilds as 219.84x35.52 pt at 150 dpi and 215.04x30.96
    pt at 300 dpi — a 4.80 pt disagreement about one document, because the
    content box lands on different pixel boundaries at each resolution. The
    cleaned PAGES are entitled to differ; what may not differ is where a mark
    on them says it is on the source page.

    TWO CLAIMS, AND THE FIRST IS THE STRICTER ONE.

        The map's own error, with the oracle's resolution-dependence removed
        entirely by comparing the mapped answer against the source answer AT
        THE SAME DPI. Measured: 0.0372 and 0.0622 px at 150 dpi, 0.0446 and
        0.0316 px at 300 — and EXACTLY 0.000000 px on the unturned page, where
        the map is two translations and nothing else.

        What cleaning ADDS to the DPI disagreement, over what rasterising the
        page already has. This is F-030's complaint stated exactly — *"two runs
        of the same document do not even agree with each other"* — and the
        honest answer is not "they agree perfectly", because the rasteriser
        itself quantises. It is that the CLEANER contributes nothing. Measured:
        -0.0071 pt on x and +0.0222 pt on y, against 4.80 pt before this
        change.

    Both bounds are one source pixel at the coarser resolution, derived exactly
    as `test_pdf_backend.py`'s F-031 guard derives its own. Neither is chosen,
    and both sit an order of magnitude above what is measured.

    THIS IS THE TEST THAT FAILS IF THE RESOLUTION IS NOT RECORDED. Source
    PIXELS at 150 and at 300 dpi are different units, and only the resolution
    converts both into the space the source page is measured in.
    """
    source = a_scanned_pdf_of_solid_bars(SCANNED_SKEW_DEGREES)
    mapped: dict[int, tuple[float, float]] = {}
    on_the_source: dict[int, tuple[float, float]] = {}
    turns: dict[int, float | None] = {}

    for dpi in (COARSE_RENDER_DPI, FINE_RENDER_DPI):
        rendered = _to_grey_page_of(source, dpi)
        truth = ink_centroid(rendered)
        result = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=dpi)
        assert result.artifact is not None
        assert result.artifact.raster is not None
        turns[dpi] = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value
        geometry = result.geometry_of()
        assert geometry.render_dpi == dpi, "the resolution that rendered the page was not recorded"

        in_pixels = geometry.source_pixel(*ink_centroid(result.artifact.raster))
        assert math.hypot(in_pixels[0] - truth[0], in_pixels[1] - truth[1]) < ONE_SOURCE_PIXEL, (
            f"at {dpi} dpi the cleaned ink maps to {in_pixels} on the rendered "
            f"page, where it actually sits at {truth}"
        )

        points = POINTS_PER_INCH / dpi
        mapped[dpi] = (in_pixels[0] * points, in_pixels[1] * points)
        on_the_source[dpi] = (truth[0] * points, truth[1] * points)

    coarse_turn, fine_turn = turns[COARSE_RENDER_DPI], turns[FINE_RENDER_DPI]
    assert coarse_turn is not None and fine_turn is not None
    assert coarse_turn != 0.0, (
        "the fixture was not turned at all, so this test would pass on a map "
        "that knows nothing about rotation"
    )
    assert coarse_turn != fine_turn, (
        "both resolutions measured the same turn, so this test would pass on a "
        "map that recorded one page's rotation and used it for the other"
    )

    one_pixel_in_points = POINTS_PER_INCH / COARSE_RENDER_DPI
    for axis, name in ((0, "x"), (1, "y")):
        after_cleaning = abs(mapped[COARSE_RENDER_DPI][axis] - mapped[FINE_RENDER_DPI][axis])
        rasterised = abs(
            on_the_source[COARSE_RENDER_DPI][axis] - on_the_source[FINE_RENDER_DPI][axis]
        )
        assert after_cleaning - rasterised <= one_pixel_in_points, (
            f"on {name}, the same ink is placed {after_cleaning:.4f} pt apart by "
            f"the two runs while rasterising alone places it {rasterised:.4f} pt "
            f"apart. Cleaning added {after_cleaning - rasterised:.4f} pt of "
            "disagreement about where the ink is."
        )


#: The bars are AUTHORED as a 400x200 PIXEL image placed on a 400x200 POINT
#: page, so one authored pixel is exactly one point and the authored ink
#: position IS the ink's position in points. That makes the authored image a
#: ground truth measured before any rasterisation, in the unit the answer is
#: wanted in, and reachable without the resolution the code under test uses.
#:
#: The bound is one authored pixel, derived the same way every other bound
#: here is: the truth is known to the resolution it was drawn at. Measured
#: error against it — 0.3430 pt at 150 dpi, 0.4665 at 300, 0.5690 at 600,
#: converging on the fraction of a pixel the PDF's own image resampling moves
#: the ink by, and not on anything the map does.
ONE_AUTHORED_POINT = 1.0


def test_a_cleaned_coordinate_lands_where_the_ink_was_authored_on_the_page() -> None:
    """`source_point` on a REAL value, against a truth from outside the module.

    `test_cleaning_adds_no_disagreement_between_two_render_dpis` compares two
    runs to each other, which is the right question for F-030 and cannot see an
    error both runs share. Measured: with that test alone, inverting the
    conversion — multiplying by the resolution instead of dividing — SURVIVED,
    because nothing ever asked `source_point` for an answer and checked it
    against a page.

    So this asks for one, and checks it against where the ink was drawn. A
    conversion inverted, dropped, or applied in the wrong direction puts the
    answer thousands of points off a page 400 points wide.
    """
    authored = ink_centroid(cleaner._to_grey(cleaner.decode(a_page_of_solid_bars(0.0))))
    source = a_scanned_pdf_of_solid_bars(0.0)

    for dpi in (COARSE_RENDER_DPI, FINE_RENDER_DPI):
        result = cleaner.clean_artifact(source, cleaner.MediaKind.PDF, a_settings(), render_dpi=dpi)
        assert result.artifact is not None
        assert result.artifact.raster is not None

        across, down = result.geometry_of().source_point(*ink_centroid(result.artifact.raster))

        assert 0.0 <= across <= SCANNED_PAGE_WIDTH_POINTS, (
            f"at {dpi} dpi the ink is reported at x={across:.4f} pt on a page "
            f"{SCANNED_PAGE_WIDTH_POINTS} pt wide, which is not on the page at all"
        )
        assert 0.0 <= down <= SCANNED_PAGE_HEIGHT_POINTS, (
            f"at {dpi} dpi the ink is reported at y={down:.4f} pt on a page "
            f"{SCANNED_PAGE_HEIGHT_POINTS} pt tall, which is not on the page at all"
        )
        assert abs(across - authored[0]) < ONE_AUTHORED_POINT, (
            f"at {dpi} dpi the ink is reported at x={across:.4f} pt; it was drawn "
            f"at x={authored[0]:.4f} pt"
        )
        assert abs(down - authored[1]) < ONE_AUTHORED_POINT, (
            f"at {dpi} dpi the ink is reported at y={down:.4f} pt; it was drawn "
            f"at y={authored[1]:.4f} pt"
        )


def _to_grey_page_of(document: bytes, dpi: int) -> Image:
    """The source raster the cleaner will be handed, rendered independently.

    Through `pdf_backend` rather than through `cleaner`, so the truth this test
    compares against is not produced by the code path under test.
    """
    opened = pdf_backend.open_pdf(document)
    try:
        rendered = pdf_backend.render_page_png(opened, 0, dpi=dpi)
    finally:
        pdf_backend.close_pdf(opened)
    decoded = cv2.imdecode(np.frombuffer(rendered, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert decoded is not None, "the backend's own PNG did not decode"
    return _u8(decoded)


def test_the_geometry_survives_the_copy_that_attaches_the_artifact() -> None:
    """`replace_artifact` rebuilds `CleanedDocument` field by field, so a field
    it forgets is silently emptied on EVERY path that produces an artifact —
    which is every path a consumer ever sees. The identity check is the point:
    a copy that rebuilt the records would also be a copy that could rebuild
    them differently.
    """
    result = cleaner._clean_image(a_skewed_invoice(), BASELINE)
    assert result.source_geometry != (), "the fixture produced no geometry to lose"

    copied = cleaner.replace_artifact(
        result,
        cleaner.CleanedArtifact(
            kind=cleaner.MediaKind.IMAGE, payload=b"png", original=b"png-source"
        ),
    )

    assert copied.source_geometry == result.source_geometry
    assert copied.geometry_of() is result.geometry_of()


def test_every_page_of_a_scan_carries_its_own_geometry_and_not_page_ones() -> None:
    """`KNOWN_FAILURES.md` D3, applied to the new field before it can repeat.

    D3 was page one's measurements standing for a whole document. Geometry has
    the identical shape and a worse consequence: every page of a multi-page
    scan is cropped and turned differently, so page one's map placed on page
    three's coordinates is not an approximation, it is another page's answer.
    """
    first = cleaner._clean_image(a_small_banded_page(), BASELINE)
    second = cleaner._clean_image(a_skewed_invoice(), BASELINE)

    joined = cleaner._every_page_reported([first, second])

    assert [record.page for record in joined.source_geometry] == [1, 2], (
        "the pages were not numbered one and two in the order they were given"
    )
    assert joined.geometry_of(1).to_source == first.geometry_of().to_source
    assert joined.geometry_of(2).to_source == second.geometry_of().to_source
    assert joined.geometry_of(1).to_source != joined.geometry_of(2).to_source, (
        "two differently cropped pages reported the same map, so the fixture "
        "cannot tell page two's geometry from page one's"
    )


def test_a_page_the_document_does_not_have_is_refused_rather_than_answered() -> None:
    """The same discipline `observed` keeps. A silent fallback to page one is
    exactly how page one's evidence came to stand for a whole document.
    """
    result = cleaner._clean_image(a_small_banded_page(), BASELINE)

    with pytest.raises(KeyError):
        result.geometry_of(2)


def test_points_are_refused_on_a_raster_this_module_did_not_render() -> None:
    """An image arrives already rasterised, at whatever resolution it was
    captured at. Its pixels ARE the document's own space and there is no page
    of points behind them, so a point is a question with no answer — and
    answering it by treating a pixel as a point would put a fabricated unit in
    the artifact (Law 24, Law 11).
    """
    result = cleaner.clean_artifact(
        _png_bytes(a_skewed_invoice()), cleaner.MediaKind.IMAGE, BASELINE, render_dpi=RENDER_DPI
    )
    geometry = result.geometry_of()

    assert geometry.render_dpi is None, (
        "an image path recorded a render resolution, but nothing rendered it — "
        "the value can only have come from the caller's unused argument"
    )
    assert geometry.source_pixel(0.0, 0.0) is not None
    with pytest.raises(cleaner.NoRenderResolutionError):
        geometry.source_point(0.0, 0.0)


def test_a_text_layer_pdf_records_no_geometry_because_nothing_was_rasterised() -> None:
    """The honest empty. A text-layer PDF passes through untouched: there is no
    raster, no crop and no turn, so there is no map — and its own coordinates
    are already the document's. Inventing an identity map here would claim a
    cleaning that never happened.
    """
    result = cleaner.clean_artifact(
        a_text_layer_pdf(), cleaner.MediaKind.PDF, a_settings(), render_dpi=RENDER_DPI
    )

    assert result.source_geometry == ()
    with pytest.raises(KeyError):
        result.geometry_of()


def test_the_recorded_source_extent_is_the_raster_the_map_answers_in() -> None:
    """The map's codomain, carried so a consumer can tell an on-page answer
    from an off-page one without holding the source array.

    Asserted against `original.shape` rather than against a number in this
    file, which turns what would otherwise be a duplicated value into a checked
    invariant (Law 19). On a multi-page scan `original` is page one's alone, so
    for every page after the first this record is the ONLY statement of the
    raster its coordinates live in.

    ALL THREE CHANNEL COUNTS, because `original` is carried in the shape it
    ARRIVED in while the extent is taken off the one-channel form. One, three
    and four channels are three different `original.shape` lengths, and a
    reading that happened to work for the grey case could transpose or truncate
    on the others without any grey fixture noticing.
    """
    grey = a_skewed_invoice()
    colour = _u8(cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR))
    opaque = _u8(cv2.cvtColor(grey, cv2.COLOR_GRAY2BGRA))

    for label, source in (("grey", grey), ("colour", colour), ("with alpha", opaque)):
        result = cleaner._clean_image(source, BASELINE)
        geometry = result.geometry_of()
        assert (geometry.source_height, geometry.source_width) == result.original.shape[:2], (
            f"the {label} page's recorded extent is not the extent of the raster "
            "the map answers in, so an off-page answer cannot be told from an "
            "on-page one"
        )


def test_the_crop_reports_the_origin_it_cropped_at() -> None:
    """The discarded quantity, at the function that used to discard it.

    Both cases, because they are different code paths: a page with a content
    box reports the box's own inset less the margin, and a uniform page — which
    is returned whole rather than cropped to nothing — reports the origin of a
    crop that did not happen.
    """
    banded = a_small_banded_page()

    _cropped, _kept, origin = cleaner._crop_to_content(banded, 0)
    assert origin == (10, 5), (
        "the banded fixture's ink starts at column 10, row 5, so a zero-margin "
        "crop starts there too"
    )

    _margined, _also, inset = cleaner._crop_to_content(banded, 3)
    assert inset == (7, 2), "the margin was not subtracted from the box's origin"

    _whole, _full, nothing = cleaner._crop_to_content(a_small_uniform_page(), 4)
    assert nothing == (0, 0), (
        "a uniform page is returned whole, so its origin is the page's own and "
        "not the margin the crop would have used"
    )


def test_the_map_is_recorded_when_the_deskew_is_refused() -> None:
    """The branch where the turn does NOT happen, which is a different answer
    and not a missing one.

    `_deskew` refuses a skew past `max_deskew_degrees` and hands the page back
    unturned. The map is then two translations and an identity, and a record
    that silently omitted itself on this branch would leave the coordinates of
    the WORST-skewed pages — the ones a human is most likely to have to go and
    check — the only ones nobody can place.
    """
    beyond = turned(padded(a_page()), BEYOND_THE_LIMIT_DEGREES)
    result = cleaner._clean_image(beyond, settings(max_deskew_degrees=15.0))

    refused = result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED)
    assert refused.value == 0.0, "the fixture was turned, so this is not the refusal branch"
    assert "exceeds" in refused.note, "the refusal was not the reason the page was left alone"

    geometry = result.geometry_of()
    scale_x, shear_x, _shift_x, shear_y, scale_y, _shift_y = geometry.to_source
    assert (scale_x, shear_x, shear_y, scale_y) == (1.0, 0.0, 0.0, 1.0), (
        "no rotation was applied, so the map's linear part must be the identity; "
        "anything else turns coordinates the page never turned"
    )
    mapped = geometry.source_pixel(*ink_centroid(result.cleaned))
    truth = ink_centroid(cleaner._to_grey(result.original))
    assert math.hypot(mapped[0] - truth[0], mapped[1] - truth[1]) < ONE_SOURCE_PIXEL


def test_a_page_with_no_ink_still_records_the_map_it_did_not_move_by() -> None:
    """A blank sheet is returned whole and unturned, so its map is the identity.

    Recorded rather than omitted, for the reason `decode` raises rather than
    returning a blank page: an absent record and an identity record are
    different statements, and a consumer that met the first would have to guess
    which one it was looking at.
    """
    result = cleaner._clean_image(a_small_uniform_page(), BASELINE)

    geometry = result.geometry_of()
    assert geometry.to_source == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    assert geometry.source_pixel(7.0, 11.0) == (7.0, 11.0), (
        "nothing moved, so every coordinate must map to itself"
    )


def a_two_page_scan(first_turn: float, second_turn: float) -> bytes:
    """Two scanned pages, each turned differently, so their maps must differ."""
    fitz = importlib.import_module("pymupdf")
    document = fitz.open()
    try:
        for degrees in (first_turn, second_turn):
            page = document.new_page(
                width=SCANNED_PAGE_WIDTH_POINTS, height=SCANNED_PAGE_HEIGHT_POINTS
            )
            page.insert_image(
                fitz.Rect(0, 0, SCANNED_PAGE_WIDTH_POINTS, SCANNED_PAGE_HEIGHT_POINTS),
                stream=a_page_of_solid_bars(degrees),
            )
        return bytes(document.tobytes())
    finally:
        document.close()


def test_a_two_page_scan_carries_both_maps_through_the_single_entry_point() -> None:
    """THE WIRING, end to end, which no test above can see.

    `test_every_page_of_a_scan_carries_its_own_geometry_and_not_page_ones`
    calls `_every_page_reported` directly. That proves the join and nothing
    else: between `_clean_image` and a consumer sit `_pdf_rebuilt_from_cleaned_
    pages`, the join, and `replace_artifact`, and the record has to survive all
    three. §J.(a) — a gate that never loads the real path is a gate that has not
    run it.

    The two pages are turned by different amounts, so a map borrowed from page
    one cannot pass for page two's.
    """
    cleaned = cleaner.clean_artifact(
        a_two_page_scan(0.0, SCANNED_SKEW_DEGREES),
        cleaner.MediaKind.PDF,
        a_settings(),
        render_dpi=COARSE_RENDER_DPI,
    )

    assert [record.page for record in cleaned.source_geometry] == [1, 2], (
        "a two-page scan did not report two pages of geometry in page order"
    )
    for page in (1, 2):
        assert cleaned.geometry_of(page).render_dpi == COARSE_RENDER_DPI, (
            f"page {page}'s resolution was lost between rendering and the artifact"
        )
    assert cleaned.geometry_of(1).to_source != cleaned.geometry_of(2).to_source, (
        "both pages reported the same map, so one of them is the other's"
    )
