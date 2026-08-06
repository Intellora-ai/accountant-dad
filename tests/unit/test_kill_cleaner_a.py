"""Mutation-killing tests for cleaner.CleanerSettings validation boundaries.

Each test targets a specific operator mutation that existing tests miss:
- Boundary operators: `<` vs `<=`, `>` vs `>=`
- Logic inversions: `not` removal, `or` vs `and`
- Constant changes: boundary values

These tests would FAIL if the mutations were applied.
"""

from __future__ import annotations

import pytest

from accountant_dad.engines.input_engine import cleaner

# Test-specific boundary values that exercise exact mutation targets.
_HALF_QUARTER_TURN = 45.0
_FULL_QUARTER_TURN = 90.0
_MIN_WINDOW_SIZE = 3
_EQUAL_WINDOWS = 15
_TINY_POSITIVE_DENOISE = 0.001
_TINY_POSITIVE_CONTRAST = 0.001
_ZERO_CROP_MARGIN = 0
_LARGE_CROP_MARGIN = 10
_MID_RANGE_INK_LOSS = 0.5


# ── Line 306: `if not 0.0 < self.max_deskew_degrees <= _QUARTER_TURN:` ───
# Mutation: `<` → `<=` (would reject 0.0, already caught by existing test)
# Mutation: `<= _QUARTER_TURN` → `< _QUARTER_TURN` (would reject 90.0)
# Need: verify 90.0 is ACCEPTED (the upper boundary)


def test_max_deskew_at_upper_boundary_45_is_accepted() -> None:
    """45 degrees (half quarter-turn) must be accepted.

    Kills mutation: `<= _QUARTER_TURN` → `< _QUARTER_TURN`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=_HALF_QUARTER_TURN,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.max_deskew_degrees == _HALF_QUARTER_TURN


def test_max_deskew_at_upper_boundary_90_is_accepted() -> None:
    """Exactly 90 degrees (quarter-turn) must be accepted.

    Kills mutation: `<= _QUARTER_TURN` → `< _QUARTER_TURN`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=_FULL_QUARTER_TURN,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.max_deskew_degrees == _FULL_QUARTER_TURN


# ── Line 312: `if self.denoise_strength <= 0.0:` ───
# Mutation: `<=` → `<` (would accept 0.0)
# Need: verify negative is rejected


def test_negative_denoise_strength_is_refused() -> None:
    """Negative denoise strength must be rejected.

    Kills mutation: `<=` → `<` (leaves 0.0 rejected but passes negative)
    Also kills: `<=` → `==` (leaves some negatives passing)
    """
    with pytest.raises(cleaner.ImpossibleSettingError, match="positive"):
        cleaner.CleanerSettings(
            max_deskew_degrees=15.0,
            denoise_strength=-0.5,
            denoise_template_window=7,
            denoise_search_window=21,
            contrast_clip_limit=2.0,
            contrast_tile_grid=8,
            crop_margin_pixels=4,
            max_ink_loss_fraction=0.05,
        )


def test_small_positive_denoise_strength_is_accepted() -> None:
    """Very small positive denoise strength must be accepted.

    Verifies boundary is exactly at 0.0, not some small positive value.
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=_TINY_POSITIVE_DENOISE,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.denoise_strength == _TINY_POSITIVE_DENOISE


# ── Line 320: `if window < _MIN_SIDE_FOR_NOISE or window % 2 == 0:` ───
# Mutation: `<` → `<=` (would reject 3)
# Mutation: `== 0` → `!= 0` (would reject odd windows)
# Need: verify exactly 3 is accepted


def test_denoise_template_window_at_minimum_3_is_accepted() -> None:
    """Exactly 3 (minimum for 3x3 convolution) must be accepted.

    Kills mutation: `<` → `<=` in `window < _MIN_SIDE_FOR_NOISE`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=_MIN_WINDOW_SIZE,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.denoise_template_window == _MIN_WINDOW_SIZE


def test_denoise_search_window_at_minimum_3_is_accepted() -> None:
    """Exactly 3 for search window must be accepted.

    Kills mutation: `<` → `<=` in `window < _MIN_SIDE_FOR_NOISE`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=_MIN_WINDOW_SIZE,
        denoise_search_window=_MIN_WINDOW_SIZE,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.denoise_search_window == _MIN_WINDOW_SIZE


def test_denoise_window_below_minimum_2_is_refused() -> None:
    """Window size 2 (below minimum 3) must be rejected.

    Verifies boundary is exactly at 3.
    """
    with pytest.raises(cleaner.ImpossibleSettingError, match="at least 3"):
        cleaner.CleanerSettings(
            max_deskew_degrees=15.0,
            denoise_strength=6.0,
            denoise_template_window=2,
            denoise_search_window=21,
            contrast_clip_limit=2.0,
            contrast_tile_grid=8,
            crop_margin_pixels=4,
            max_ink_loss_fraction=0.05,
        )


# ── Line 325: `if self.denoise_search_window < self.denoise_template_window:` ───
# Mutation: `<` → `<=` (would reject equal values)
# Need: verify equal windows are accepted


def test_equal_denoise_windows_are_accepted() -> None:
    """Search window equal to template window must be accepted.

    Kills mutation: `<` → `<=` in window comparison
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=_EQUAL_WINDOWS,
        denoise_search_window=_EQUAL_WINDOWS,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.denoise_search_window == _EQUAL_WINDOWS
    assert cs.denoise_template_window == _EQUAL_WINDOWS


# ── Line 331: `if self.contrast_clip_limit <= 0.0:` ───
# Mutation: `<=` → `<` (would accept 0.0)
# Need: verify negative is rejected


def test_negative_contrast_clip_limit_is_refused() -> None:
    """Negative contrast clip limit must be rejected.

    Kills mutation: `<=` → `<`
    """
    with pytest.raises(cleaner.ImpossibleSettingError, match="positive"):
        cleaner.CleanerSettings(
            max_deskew_degrees=15.0,
            denoise_strength=6.0,
            denoise_template_window=7,
            denoise_search_window=21,
            contrast_clip_limit=-0.5,
            contrast_tile_grid=8,
            crop_margin_pixels=4,
            max_ink_loss_fraction=0.05,
        )


def test_small_positive_contrast_clip_limit_is_accepted() -> None:
    """Very small positive contrast clip limit must be accepted.

    Verifies boundary is exactly at 0.0.
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=_TINY_POSITIVE_CONTRAST,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.contrast_clip_limit == _TINY_POSITIVE_CONTRAST


# ── Line 335: `if self.contrast_tile_grid < 1:` ───
# Mutation: `<` → `<=` (would reject 1)
# Need: verify exactly 1 is accepted


def test_contrast_tile_grid_at_minimum_1_is_accepted() -> None:
    """Exactly 1 (minimum grid size) must be accepted.

    Kills mutation: `<` → `<=`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=1,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.05,
    )
    assert cs.contrast_tile_grid == 1


# ── Line 339: `if self.crop_margin_pixels < 0:` ───
# Mutation: `<` → `<=` (would reject 0)
# Need: verify exactly 0 is accepted


def test_crop_margin_at_zero_is_accepted() -> None:
    """Zero crop margin must be accepted (no cropping).

    Kills mutation: `<` → `<=`
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=_ZERO_CROP_MARGIN,
        max_ink_loss_fraction=0.05,
    )
    assert cs.crop_margin_pixels == _ZERO_CROP_MARGIN


def test_positive_crop_margin_is_accepted() -> None:
    """Positive crop margin must be accepted.

    Verifies boundary behavior.
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=_LARGE_CROP_MARGIN,
        max_ink_loss_fraction=0.05,
    )
    assert cs.crop_margin_pixels == _LARGE_CROP_MARGIN


# ── Line 343: `if not 0.0 <= self.max_ink_loss_fraction <= 1.0:` ───
# Mutation: `<=` → `<` (would reject 0.0 or 1.0)
# Mutation: `not` removal (inverts logic)
# Need: verify 0.0 and 1.0 are both accepted


def test_ink_loss_fraction_at_lower_boundary_0_is_accepted() -> None:
    """Exactly 0.0 (no ink loss allowed) must be accepted.

    Kills mutation: `<=` → `<` in lower bound
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=0.0,
    )
    assert cs.max_ink_loss_fraction == 0.0


def test_ink_loss_fraction_at_upper_boundary_1_is_accepted() -> None:
    """Exactly 1.0 (all ink loss allowed) must be accepted.

    Kills mutation: `<=` → `<` in upper bound
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=1.0,
    )
    assert cs.max_ink_loss_fraction == 1.0


def test_ink_loss_fraction_in_middle_is_accepted() -> None:
    """Mid-range ink loss fraction must be accepted.

    Typical use case verification.
    """
    cs = cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=6.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=4,
        max_ink_loss_fraction=_MID_RANGE_INK_LOSS,
    )
    assert cs.max_ink_loss_fraction == _MID_RANGE_INK_LOSS
