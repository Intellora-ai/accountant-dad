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

import importlib
import inspect
import math
from decimal import Decimal

import cv2
import numpy as np
import numpy.typing as npt
import pytest

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


def test_a_float_image_is_refused_rather_than_silently_cast() -> None:
    """A float32 array casts to uint8 without complaint and every intensity in
    it changes meaning. Refused, because a silent cast is a value modified.
    """
    with pytest.raises(cleaner.UnusableArtifactError, match="uint8"):
        cleaner.clean(np.zeros((400, 400), dtype=np.float32), BASELINE)


def test_a_sixteen_bit_image_is_refused() -> None:
    with pytest.raises(cleaner.UnusableArtifactError, match="uint8"):
        cleaner.clean(np.zeros((400, 400), dtype=np.uint16), BASELINE)


def test_an_empty_image_is_refused() -> None:
    with pytest.raises(cleaner.UnusableArtifactError):
        cleaner.clean(np.zeros((0, 0), dtype=np.uint8), BASELINE)


def test_a_single_pixel_image_is_refused_because_the_search_window_cannot_fit() -> None:
    """The minimum size is derived from the caller's own search window, not from
    a number this module invented.
    """
    with pytest.raises(cleaner.UnusableArtifactError, match="21"):
        cleaner.clean(np.zeros((1, 1), dtype=np.uint8), BASELINE)


def test_an_image_with_five_channels_is_refused() -> None:
    with pytest.raises(cleaner.UnusableArtifactError, match="channel"):
        cleaner.clean(np.zeros((400, 400, 5), dtype=np.uint8), BASELINE)


def test_a_one_dimensional_array_is_refused() -> None:
    with pytest.raises(cleaner.UnusableArtifactError):
        cleaner.clean(np.zeros((400,), dtype=np.uint8), BASELINE)


# ── format normalisation ──────────────────────────────────────────────────


def test_decode_returns_the_pixels_that_were_encoded() -> None:
    page = a_page()
    encoded, buffer = cv2.imencode(".png", page)
    assert encoded
    decoded = cleaner.decode(bytes(bytearray(buffer)))
    assert decoded.dtype == np.uint8
    assert np.array_equal(decoded, page)


def test_decode_refuses_bytes_that_are_not_an_image() -> None:
    with pytest.raises(cleaner.UndecodableArtifactError):
        cleaner.decode(b"this is not an image, it is a sentence")


def test_decode_refuses_empty_bytes() -> None:
    with pytest.raises(cleaner.UndecodableArtifactError):
        cleaner.decode(b"")


def test_decode_refuses_a_truncated_png() -> None:
    encoded, buffer = cv2.imencode(".png", a_page())
    assert encoded
    whole = bytes(bytearray(buffer))
    with pytest.raises(cleaner.UndecodableArtifactError):
        cleaner.decode(whole[: len(whole) // 3])


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
    result = cleaner.clean(colour, BASELINE)
    assert result.cleaned.ndim == ONE_CHANNEL_NDIM
    assert result.cleaned.dtype == np.uint8


def test_a_four_channel_page_is_normalised_to_one_channel() -> None:
    with_alpha = _u8(cv2.cvtColor(a_page(), cv2.COLOR_GRAY2BGRA))
    result = cleaner.clean(with_alpha, BASELINE)
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

    result = cleaner.clean(skewed, BASELINE)
    after = orientation_degrees(result.cleaned)
    assert after is not None
    assert abs(after) < MAX_RESIDUAL_SKEW_DEGREES, (
        f"residual skew {after:.4f} deg after correcting {before:.4f} deg"
    )


def test_the_reported_skew_angle_matches_the_independent_oracle() -> None:
    skewed = turned(padded(a_page()), KNOWN_SKEW_DEGREES)
    reported = cleaner.clean(skewed, BASELINE).observed(cleaner.SKEW_ANGLE, cleaner.Stage.ORIGINAL)
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
    result = cleaner.clean(skewed, settings(max_deskew_degrees=15.0))

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
    result = cleaner.clean(skewed, settings(max_deskew_degrees=45.0))
    residual = orientation_degrees(result.cleaned)
    assert residual is not None
    assert abs(residual) < MAX_RESIDUAL_SKEW_DEGREES


def test_an_already_straight_page_is_not_bent() -> None:
    straight = padded(a_page())
    result = cleaner.clean(straight, BASELINE)
    residual = orientation_degrees(result.cleaned)
    assert residual is not None
    assert abs(residual) < MAX_SKEW_OF_A_STRAIGHT_PAGE


def test_rotation_never_pushes_ink_off_the_canvas() -> None:
    """The canvas grows to hold the rotated frame, so no pixel leaves it. Proven
    by counting ink, not by reading the code that resizes.
    """
    skewed = turned(padded(a_page()), KNOWN_SKEW_DEGREES)
    result = cleaner.clean(skewed, settings(crop_margin_pixels=0))
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)
    assert kept.value == FULL_RETENTION


# ── denoise, measured, and proven differentially ──────────────────────────


def test_enough_denoising_lowers_end_to_end_noise() -> None:
    """Measured: 11.382 -> 4.160 grey levels at denoise_strength 30."""
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    before = median_residual_sigma(noisy)
    cleaned = cleaner.clean(noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH)).cleaned
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
    result = cleaner.clean(noisy, BASELINE)
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
        result = cleaner.clean(noisy, settings(denoise_strength=strength))
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
    quiet = cleaner.clean(noisy, settings(contrast_clip_limit=LOW_CLIP_LIMIT))
    loud = cleaner.clean(noisy, settings(contrast_clip_limit=BASELINE.contrast_clip_limit))
    assert median_residual_sigma(loud.cleaned) > median_residual_sigma(quiet.cleaned)


def test_a_stronger_denoise_setting_leaves_strictly_less_noise() -> None:
    """Differential. Only `denoise_strength` differs, so every other stage runs
    identically and the difference cannot come from cropping or contrast.
    """
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    gentle = cleaner.clean(noisy, settings(denoise_strength=GENTLE_DENOISE_STRENGTH))
    strong = cleaner.clean(noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH))
    assert median_residual_sigma(strong.cleaned) < median_residual_sigma(gentle.cleaned)


def test_the_reported_noise_estimate_falls_between_the_two_stages() -> None:
    noisy = with_gaussian_noise(padded(a_page()), INJECTED_NOISE_SIGMA)
    result = cleaner.clean(noisy, settings(denoise_strength=STRONG_DENOISE_STRENGTH))
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
    quiet = cleaner.clean(flat, settings(contrast_clip_limit=LOW_CLIP_LIMIT))
    loud = cleaner.clean(flat, settings(contrast_clip_limit=HIGH_CLIP_LIMIT))
    assert rms_contrast(loud.cleaned) > rms_contrast(quiet.cleaned)


def test_contrast_rises_on_a_page_that_crop_cannot_change() -> None:
    flat = a_low_contrast_page()
    result = cleaner.clean(flat, settings(contrast_clip_limit=HIGH_CLIP_LIMIT))
    before = rms_contrast(flat)
    after = rms_contrast(result.cleaned)
    assert after > before, f"rms contrast {before:.3f} -> {after:.3f}, no improvement"


def test_the_reported_contrast_matches_the_independent_measure() -> None:
    flat = a_low_contrast_page()
    reported = cleaner.clean(flat, BASELINE).observed(cleaner.RMS_CONTRAST, cleaner.Stage.ORIGINAL)
    assert reported.value is not None
    assert reported.unit == "grey levels"
    assert reported.value == pytest.approx(rms_contrast(flat), abs=1e-6)


# ── the preservation rule ─────────────────────────────────────────────────


def test_a_clean_that_loses_no_ink_reports_the_cleaned_form_as_safer() -> None:
    result = cleaner.clean(padded(a_page()), BASELINE)
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
    result = cleaner.clean(hairlines, settings(denoise_strength=ERASING_DENOISE_STRENGTH))
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
    strict = cleaner.clean(
        hairlines,
        settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=0.0),
    )
    permissive = cleaner.clean(
        hairlines,
        settings(denoise_strength=ERASING_DENOISE_STRENGTH, max_ink_loss_fraction=1.0),
    )
    assert strict.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER
    assert permissive.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


def test_the_original_is_never_discarded() -> None:
    page = padded(a_page())
    result = cleaner.clean(page, BASELINE)
    assert np.array_equal(result.original, page), "the original was altered"
    assert result.original is not result.cleaned


def test_the_original_is_carried_in_the_colour_it_arrived_in() -> None:
    colour = _u8(cv2.cvtColor(a_page(), cv2.COLOR_GRAY2BGR))
    result = cleaner.clean(colour, BASELINE)
    assert np.array_equal(result.original, colour)


# ── crop discards no content ──────────────────────────────────────────────


def test_crop_keeps_every_ink_pixel() -> None:
    """The one operation that can literally delete content. `cleaner` may not
    discard anything it judges irrelevant, so retention must be exactly 1.
    """
    result = cleaner.clean(padded(a_page()), BASELINE)
    kept = result.observed(cleaner.INK_KEPT_BY_CROP, cleaner.Stage.CLEANED)
    assert kept.value == FULL_RETENTION
    assert kept.unit == "fraction of ink pixels"


def test_crop_removes_the_blank_border_it_was_given() -> None:
    """Retention of 1.0 would also hold if crop did nothing at all, so the
    counterpart is that the 200px blank pad actually goes."""
    page = padded(a_page())
    result = cleaner.clean(page, settings(crop_margin_pixels=0))
    assert result.cleaned.shape[0] < page.shape[0]
    assert result.cleaned.shape[1] < page.shape[1]


def test_a_larger_crop_margin_keeps_a_larger_page() -> None:
    page = padded(a_page())
    tight = cleaner.clean(page, settings(crop_margin_pixels=0))
    loose = cleaner.clean(page, settings(crop_margin_pixels=40))
    assert loose.cleaned.shape[0] > tight.cleaned.shape[0]
    assert loose.cleaned.shape[1] > tight.cleaned.shape[1]


# ── blank pages, and everything that divides by the ink count ─────────────


def test_a_blank_page_is_reported_rather_than_crashed_on() -> None:
    blank: Image = np.full((400, 400), PAPER_INTENSITY, dtype=np.uint8)
    result = cleaner.clean(blank, BASELINE)
    assert result.observed(cleaner.INK_FRACTION, cleaner.Stage.ORIGINAL).value == 0.0
    assert result.observed(cleaner.SKEW_ANGLE, cleaner.Stage.ORIGINAL).value is None
    assert result.observed(cleaner.DESKEW_APPLIED, cleaner.Stage.CLEANED).value == 0.0
    assert result.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER


def test_a_blank_page_is_not_cropped_to_nothing() -> None:
    blank: Image = np.full((400, 400), PAPER_INTENSITY, dtype=np.uint8)
    result = cleaner.clean(blank, BASELINE)
    assert result.cleaned.shape == blank.shape


def test_an_all_black_page_is_handled_too() -> None:
    black: Image = np.zeros((400, 400), dtype=np.uint8)
    result = cleaner.clean(black, BASELINE)
    assert result.cleaned.size > 0


# ── the observations themselves ───────────────────────────────────────────


def test_every_observation_carries_a_reason() -> None:
    """`ENGINE_1:626` - a bare score cannot become a good question downstream."""
    result = cleaner.clean(padded(a_page()), BASELINE)
    assert result.quality_observations
    for observation in result.quality_observations:
        assert observation.note.strip(), f"{observation.name} carries no reason"
        assert observation.unit.strip(), f"{observation.name} carries no unit"


def test_no_observation_is_reported_twice_for_one_stage() -> None:
    result = cleaner.clean(padded(a_page()), BASELINE)
    keys = [(o.name, o.stage) for o in result.quality_observations]
    assert len(keys) == len(set(keys)), f"a measurement is reported twice: {keys}"


def test_both_stages_are_measured_so_an_improvement_can_be_stated() -> None:
    """Law 52. A claim that cleaning improved anything needs before and after."""
    result = cleaner.clean(padded(a_page()), BASELINE)
    stages = {o.stage for o in result.quality_observations}
    assert stages == {cleaner.Stage.ORIGINAL, cleaner.Stage.CLEANED}
    for name in (cleaner.NOISE_SIGMA, cleaner.RMS_CONTRAST, cleaner.LAPLACIAN_VARIANCE):
        assert result.observed(name, cleaner.Stage.ORIGINAL).value is not None
        assert result.observed(name, cleaner.Stage.CLEANED).value is not None


def test_asking_for_a_measurement_that_was_not_taken_fails_loudly() -> None:
    result = cleaner.clean(padded(a_page()), BASELINE)
    with pytest.raises(KeyError):
        result.observed("a measurement nobody took", cleaner.Stage.ORIGINAL)


def test_the_result_is_frozen() -> None:
    result = cleaner.clean(padded(a_page()), BASELINE)
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


# ── the boundary the module must never cross ──────────────────────────────


def test_the_module_reads_no_text_and_owns_no_field_names() -> None:
    """`cleaner` alters presentation. Reading is `reader`, structuring is
    `parser`, scoring is `confidence`. A field name or a confidence score
    appearing in this module is a boundary crossed in code.
    """
    source = inspect.getsource(cleaner)
    for forbidden in ("pytesseract", "tesseract", "easyocr", "PIL", "Image.open"):
        assert forbidden not in source, f"{forbidden} is not on the approved stack"
    exported = {name for name in vars(cleaner) if not name.startswith("_")}
    for reserved in ("confidence", "Confidence", "DetectedField", "extract", "read_text"):
        assert reserved not in exported, f"{reserved} belongs to another sub-engine"


def test_cleaning_the_same_page_twice_gives_the_same_bytes() -> None:
    """Determinism. `MEASUREMENT_FRAMEWORK` cannot obtain a number from a stage
    that answers differently on two runs.
    """
    page = padded(a_page())
    first = cleaner.clean(page, BASELINE)
    second = cleaner.clean(page, BASELINE)
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
    """`clean_artifact`'s image path builds `document` with `clean()` and then
    calls `replace_artifact(document, ...)`. Comparing the result to a
    SEPARATE, direct `clean()` call on the same bytes and settings is an
    independent oracle for every field `replace_artifact` is responsible for
    copying — determinism (`test_cleaning_the_same_page_twice_gives_the_same_bytes`)
    is what makes the two calls comparable at all.
    """
    settings = a_settings()
    raw = an_image_page()
    independent = cleaner.clean(cleaner.decode(raw), settings)

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
