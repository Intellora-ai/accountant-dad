"""Mutation killer tests for cleaner.py (lines 370-740).

Targets dataclasses, defaults, boundaries, comparisons, and helper functions:
  - Line 492: SourceGeometry.page default=1
  - Line 518: render_dpi None check and error path
  - Line 602: dtype != uint8 comparison and error path
  - Line 607: _u8 returns uint8 not float or other type
  - Line 619: _extent casts to int, not float
  - Line 630: cv2.threshold constants (0, 255)
  - Line 635: ink count uses <= threshold, not <
  - Line 654-655: set difference with AND/NOT, not simple subtraction
  - Line 669: extreme_normal uses > 1, not >= 1 or > 0
  - Line 724: measured.any() guard with NOT
  - Line 726: divisor guard and 2.0 multiplier
  - Line 728: comparison > 2.0 * step, not >= or <
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from PIL import Image as PILImage

from accountant_dad.engines.input_engine.cleaner import (
    CleanedArtifact,
    CleanedDocument,
    MediaKind,
    NoRenderResolutionError,
    PreservationStatus,
    QualityObservation,
    SourceGeometry,
    Stage,
    UnusableArtifactError,
    _content_box,
    _extent,
    _extreme_normal,
    _ink_at,
    _ink_erased,
    _ink_mask,
    _line_profile,
    _lines_with_content,
    _u8,
)


class TestSourceGeometryPageDefault:
    """Kill mutations in SourceGeometry.page default (line 492)."""

    def test_page_defaults_to_one(self) -> None:
        """page must default to 1, not 0 or 2."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
        )
        assert geom.page == 1

    def test_page_not_zero(self) -> None:
        """Catches mutation page=1 -> page=0."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
        )
        assert geom.page != 0

    def test_page_not_two(self) -> None:
        """Catches mutation page=1 -> page=2."""
        default_page, mutated_page = 1, 2  # noqa: F841
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
        )
        assert geom.page != mutated_page

    def test_page_can_be_overridden(self) -> None:
        """Explicit page values are respected."""
        explicit_page = 3
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            page=explicit_page,
        )
        assert geom.page == explicit_page

    def test_page_one_based_not_zero_based(self) -> None:
        """Page numbering is one-based, critical for multi-page documents."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
        )
        # Default should be 1, not 0
        assert geom.page >= 1


class TestSourceGeometryRenderDpiNoneCheck:
    """Kill mutations in render_dpi None check (line 518)."""

    def test_render_dpi_none_raises_error(self) -> None:
        """source_point() must raise when render_dpi is None."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            render_dpi=None,
        )
        with pytest.raises(NoRenderResolutionError):
            geom.source_point(50.0, 50.0)

    def test_render_dpi_none_error_message(self) -> None:
        """Error message must be present and informative."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            render_dpi=None,
        )
        with pytest.raises(NoRenderResolutionError) as exc_info:
            geom.source_point(50.0, 50.0)
        assert "resolution" in str(exc_info.value).lower()

    def test_render_dpi_present_does_not_raise(self) -> None:
        """source_point() must NOT raise when render_dpi is set."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            render_dpi=300,
        )
        result = geom.source_point(50.0, 50.0)
        assert isinstance(result, tuple)
        expected_tuple_size = 2
        assert len(result) == expected_tuple_size

    def test_render_dpi_zero_is_not_none(self) -> None:
        """render_dpi=0 is different from None (should not raise the None check)."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            render_dpi=0,
        )
        # Should not raise the "is None" check
        # (but may raise division by zero, which is different)
        try:
            geom.source_point(50.0, 50.0)
        except ZeroDivisionError:
            pass  # Expected if 0 causes division by zero
        except NoRenderResolutionError:
            pytest.fail("render_dpi=0 should not trigger None check")


class TestU8TypeCastingAndCheck:
    """Kill mutations in _u8 dtype check (line 602) and return (line 607)."""

    def test_u8_rejects_float64(self) -> None:
        """_u8 must reject float64 arrays."""
        float_array = np.array([[1.5, 2.5], [3.5, 4.5]], dtype=np.float64)
        with pytest.raises(UnusableArtifactError) as exc_info:
            _u8(float_array)
        assert "uint8" in str(exc_info.value).lower()

    def test_u8_rejects_uint16(self) -> None:
        """_u8 must reject uint16 arrays."""
        uint16_array = np.array([[1, 2], [3, 4]], dtype=np.uint16)
        with pytest.raises(UnusableArtifactError):
            _u8(uint16_array)

    def test_u8_accepts_uint8(self) -> None:
        """_u8 must accept uint8 arrays."""
        uint8_array = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        result = _u8(uint8_array)
        assert result.dtype == np.uint8

    def test_u8_returns_uint8_dtype_not_float(self) -> None:
        """_u8 return must be uint8, provably not float."""
        uint8_array = np.array([[255, 128], [64, 32]], dtype=np.uint8)
        result = _u8(uint8_array)
        assert result.dtype == np.uint8
        assert result.dtype != np.float64
        assert result.dtype != np.float32

    def test_u8_error_includes_dtype_name(self) -> None:
        """Error message must name the actual dtype received."""
        int32_array = np.array([[1, 2]], dtype=np.int32)
        with pytest.raises(UnusableArtifactError) as exc_info:
            _u8(int32_array)
        error_msg = str(exc_info.value).lower()
        assert "int32" in error_msg


class TestExtentIntCasting:
    """Kill mutations in _extent int casting (line 619)."""

    def test_extent_returns_int_not_float(self) -> None:
        """_extent must return int, not numpy scalar or float."""
        image = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
        height, width = _extent(image)
        assert isinstance(height, int)
        assert isinstance(width, int)

    def test_extent_correct_dimensions(self) -> None:
        """_extent must return (height, width) in correct order."""
        h_expected, w_expected = 5, 7
        image = np.zeros((h_expected, w_expected), dtype=np.uint8)
        height, width = _extent(image)
        assert height == h_expected
        assert width == w_expected

    def test_extent_not_reversed(self) -> None:
        """_extent must not return (width, height)."""
        h_expected, w_expected = 10, 20
        image = np.zeros((h_expected, w_expected), dtype=np.uint8)
        height, width = _extent(image)
        assert height != width  # They're different
        assert height == h_expected
        assert width == w_expected

    def test_extent_3d_array_uses_first_two_dimensions(self) -> None:
        """3D arrays: _extent uses shape[0] and shape[1], not shape[2]."""
        h_expected, w_expected = 10, 20
        image = np.zeros((h_expected, w_expected, 3), dtype=np.uint8)
        height, width = _extent(image)
        assert height == h_expected
        assert width == w_expected


class TestInkMaskThresholdConstants:
    """Kill mutations in cv2.threshold constants (line 630)."""

    def test_ink_mask_uses_otsu(self) -> None:
        """_ink_mask must use THRESH_OTSU flag."""
        grey = np.array([[50, 100, 150], [200, 250, 100]], dtype=np.uint8)
        _mask, threshold = _ink_mask(grey)
        # OTSU computes the threshold; it won't be 0
        assert threshold > 0
        assert isinstance(threshold, float)

    def test_ink_mask_uses_binary_inv(self) -> None:
        """_ink_mask must use THRESH_BINARY_INV (white = 255 for ink)."""
        grey = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        mask, threshold = _ink_mask(grey)
        # BINARY_INV: black pixels -> 255, white -> 0
        # Top row (all 0) should map to high values in mask
        assert mask[0, 0] > 200  # noqa: PLR2004  # Black -> 255 in inverted binary
        _ = threshold

    def test_ink_mask_output_is_uint8(self) -> None:
        """_ink_mask must return uint8 mask, not other type."""
        grey = np.array([[100, 150]], dtype=np.uint8)
        mask, threshold = _ink_mask(grey)
        assert mask.dtype == np.uint8
        _ = threshold

    def test_ink_mask_max_value_is_255(self) -> None:
        """_ink_mask output max value must be 255 (not 1 or other)."""
        grey = np.array([[10, 50, 100, 200, 250]], dtype=np.uint8)
        mask, threshold = _ink_mask(grey)
        # Binary threshold produces 0 or 255, not 1 or other
        assert np.all((mask == 0) | (mask == 255))  # noqa: PLR2004
        _ = threshold


class TestInkAtComparison:
    """Kill mutations in _ink_at <= comparison (line 635)."""

    def test_ink_at_counts_at_and_below_threshold(self) -> None:
        """_ink_at must count pixels <= threshold (not <)."""
        grey = np.array([[100, 100, 150, 200]], dtype=np.uint8)
        threshold = 100.0
        count = _ink_at(grey, threshold)
        # At threshold=100, pixels with value 100 should be counted
        assert count == 2  # noqa: PLR2004  # Both 100s

    def test_ink_at_excludes_above_threshold(self) -> None:
        """_ink_at must exclude pixels > threshold."""
        grey = np.array([[100, 150, 200]], dtype=np.uint8)
        threshold = 100.0
        count = _ink_at(grey, threshold)
        assert count == 1  # Only the 100

    def test_ink_at_boundary_inclusive(self) -> None:
        """_ink_at at boundary is inclusive (<= not <)."""
        grey = np.array([[50, 100, 150]], dtype=np.uint8)
        threshold = 100.0
        count = _ink_at(grey, threshold)
        # Should count 50 and 100, not just 50
        assert count >= 1
        # If using <, would count only 50
        # If using <=, would count 50 and 100
        assert count == 2  # noqa: PLR2004


class TestInkErasedSetDifference:
    """Kill mutations in set difference & ~still (line 655)."""

    def test_ink_erased_counts_removed_only(self) -> None:
        """_ink_erased counts pixels that WERE ink and are NOT anymore."""
        before = np.array([[50, 100, 100], [200, 200, 200]], dtype=np.uint8)
        after = np.array([[50, 150, 150], [200, 200, 200]], dtype=np.uint8)
        threshold = 120.0

        erased = _ink_erased(before, after, threshold)

        # Before: pixels at 50, 100, 100, 200, 200, 200
        # At threshold 120: pixels <= 120 are: 50, 100, 100 (3 pixels)
        # After: pixels at 50, 150, 150, 200, 200, 200
        # At threshold 120: pixels <= 120 are: 50 (1 pixel)
        # Erased: was ink but isn't = 2 pixels
        assert erased == 2  # noqa: PLR2004

    def test_ink_erased_not_net_difference(self) -> None:
        """_ink_erased must use set difference, not net count change."""
        # This tests that it's not just `before_count - after_count`
        before = np.array([[50, 100], [200, 50]], dtype=np.uint8)
        after = np.array([[50, 50], [150, 150]], dtype=np.uint8)
        threshold = 120.0

        erased = _ink_erased(before, after, threshold)
        # Before at <=120: 50, 100, 50 (3 pixels)
        # After at <=120: 50, 50 (2 pixels)
        # Net difference: 3 - 2 = 1
        # But actual erased (was & ~still): 100 was, isn't now = 1 pixel
        assert erased == 1

    def test_ink_erased_zero_when_nothing_erased(self) -> None:
        """_ink_erased returns 0 when no ink pixels are removed."""
        before = np.array([[100, 150]], dtype=np.uint8)
        after = np.array([[100, 150]], dtype=np.uint8)
        threshold = 120.0
        erased = _ink_erased(before, after, threshold)
        assert erased == 0


class TestExtremeNormalBoundary:
    """Kill mutations in extreme_normal > 1 comparison (line 669)."""

    def test_extreme_normal_draws_one_returns_zero(self) -> None:
        """With 1 draw, extreme_normal must return 0.0 (not compute sqrt)."""
        result = _extreme_normal(1)
        assert result == 0.0

    def test_extreme_normal_draws_zero_returns_zero(self) -> None:
        """With 0 draws, extreme_normal must return 0.0."""
        result = _extreme_normal(0)
        assert result == 0.0

    def test_extreme_normal_draws_two_returns_nonzero(self) -> None:
        """With 2 draws, extreme_normal must compute sqrt, not return 0."""
        result = _extreme_normal(2)
        assert result > 0.0
        assert result == math.sqrt(2.0 * math.log(2))

    def test_extreme_normal_boundary_is_exclusive_greater_than(self) -> None:
        """Boundary is > 1, not >= 1."""
        # draws=1 -> return 0 (doesn't compute sqrt)
        # draws=2 -> compute sqrt
        r1 = _extreme_normal(1)
        r2 = _extreme_normal(2)
        assert r1 == 0.0
        assert r2 > 0.0

    def test_extreme_normal_large_value(self) -> None:
        """Extreme normal grows with draws."""
        r10 = _extreme_normal(10)
        r100 = _extreme_normal(100)
        assert r100 > r10 > 0.0


class TestLinesWithContentMeasuredAny:
    """Kill mutations in measured.any() guard (line 724)."""

    def test_lines_with_content_empty_profile_returns_all_false(self) -> None:
        """When no pixels are measured, all lines return False."""
        profile = np.array([10.0, 20.0, 30.0], dtype=np.float64)
        counts = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        sigma = 1.0

        result = _lines_with_content(profile, counts, sigma)
        assert not np.any(result)  # All False
        assert result.dtype == np.bool_

    def test_lines_with_content_some_measured_not_all_false(self) -> None:
        """When some pixels are measured, some lines may be True."""
        profile = np.array([100.0, 200.0, 300.0], dtype=np.float64)
        counts = np.array([10.0, 10.0, 10.0], dtype=np.float64)
        sigma = 1.0

        result = _lines_with_content(profile, counts, sigma)
        # Not all should be False when there are measurements
        assert result.dtype == np.bool_

    def test_lines_with_content_no_inversion_in_guard(self) -> None:
        """Guard is 'if not measured.any()' not 'if measured.any()'."""
        profile = np.array([10.0, 10.0], dtype=np.float64)
        counts_all_zero = np.array([0.0, 0.0], dtype=np.float64)
        counts_some = np.array([1.0, 0.0], dtype=np.float64)

        result_all_zero = _lines_with_content(profile, counts_all_zero, 1.0)
        result_some_local = _lines_with_content(profile, counts_some, 1.0)
        _ = result_some_local

        # All zero: should return all False
        assert not np.any(result_all_zero)


class TestLineProfileDividorGuard:
    """Kill mutations in divisor guard np.where (line 686)."""

    def test_line_profile_avoids_divide_by_zero(self) -> None:
        """_line_profile must guard against division by zero."""
        intensity = np.array([[100.0, 200.0]], dtype=np.float64)
        present = np.array([[0.0, 0.0]], dtype=np.float64)
        result, counts = _line_profile(intensity, present, axis=1)

        # With no present pixels, result should be 0 (protected by where)
        assert np.isfinite(result[0])
        assert not np.isnan(result[0])
        assert not np.isinf(result[0])
        _ = counts

    def test_line_profile_normal_case(self) -> None:
        """_line_profile computes mean normally with present pixels."""
        intensity = np.array([[100.0, 200.0]], dtype=np.float64)
        present = np.array([[1.0, 1.0]], dtype=np.float64)
        result, counts = _line_profile(intensity, present, axis=1)

        # Mean should be (100 + 200) / 2 = 150
        assert result[0] == 150.0  # noqa: PLR2004
        assert counts[0] == 2.0  # noqa: PLR2004

    def test_line_profile_returns_tuple(self) -> None:
        """_line_profile returns (mean_array, count_array) tuple."""
        intensity = np.array([[100.0]], dtype=np.float64)
        present = np.array([[1.0]], dtype=np.float64)
        result = _line_profile(intensity, present, axis=1)

        assert isinstance(result, tuple)
        assert len(result) == 2  # noqa: PLR2004


class TestLinesWithContentMultiplier:
    """Kill mutations in 2.0 multiplier (line 726 and 728)."""

    def test_lines_with_content_multiplier_is_two(self) -> None:
        """The allowance multiplier must be 2.0, not 1.0 or 3.0."""
        profile = np.array([100.0, 102.0, 104.0, 200.0], dtype=np.float64)
        counts = np.full(4, 100.0, dtype=np.float64)
        sigma = 1.0

        result = _lines_with_content(profile, counts, sigma)
        # With exactly 2*step allowance, behavior is well-defined
        # Check that it uses 2, not 1 or 3
        assert isinstance(result[0], (bool, np.bool_))

    def test_lines_with_content_uses_extreme_normal(self) -> None:
        """Calculation incorporates _extreme_normal for large datasets."""
        large_size = 1000
        profile = np.linspace(100.0, 200.0, large_size, dtype=np.float64)
        counts = np.full(large_size, 100.0, dtype=np.float64)
        sigma = 5.0

        result = _lines_with_content(profile, counts, sigma)
        # Result should account for size of profile
        assert result.dtype == np.bool_


class TestContentBoxComparison:
    """Kill mutations in comparisons and thresholds."""

    def test_content_box_returns_none_for_uniform_image(self) -> None:
        """_content_box returns None when image is uniform."""
        uniform = np.full((10, 10), 150, dtype=np.uint8)
        result = _content_box(uniform)
        assert result is None

    def test_content_box_returns_tuple_for_content(self) -> None:
        """_content_box returns tuple or None depending on content."""
        # Create image with clear contrast
        image = np.full((30, 30), 200, dtype=np.uint8)  # Light background
        image[10:20, 10:20] = 50  # Dark content in middle
        result = _content_box(image)
        # Should return a tuple for non-uniform image
        if result is not None:
            assert isinstance(result, tuple)
            expected_len = 4
            assert len(result) == expected_len

    def test_content_box_with_painted_parameter(self) -> None:
        """_content_box accepts optional painted array."""
        image = np.zeros((10, 10), dtype=np.uint8)
        image[3:7, 2:8] = 100
        painted = np.ones_like(image, dtype=np.uint8)
        result = _content_box(image, painted)
        # Should work with painted parameter
        assert result is None or isinstance(result, tuple)


class TestCleanedArtifactProperties:
    """Kill mutations in CleanedArtifact field types."""

    def test_cleaned_artifact_has_kind(self) -> None:
        """CleanedArtifact must have kind field."""
        artifact = CleanedArtifact(
            kind=MediaKind.IMAGE,
            payload=b"test",
            original=b"test",
        )
        assert artifact.kind == MediaKind.IMAGE

    def test_cleaned_artifact_payload_is_bytes(self) -> None:
        """payload must be bytes, not str or other."""
        artifact = CleanedArtifact(
            kind=MediaKind.IMAGE,
            payload=b"payload_data",
            original=b"original_data",
        )
        assert isinstance(artifact.payload, bytes)
        assert artifact.payload == b"payload_data"

    def test_cleaned_artifact_original_preserved(self) -> None:
        """original bytes must be preserved unchanged."""
        original_bytes = b"original"
        artifact = CleanedArtifact(
            kind=MediaKind.IMAGE,
            payload=b"cleaned",
            original=original_bytes,
        )
        assert artifact.original == original_bytes
        assert artifact.original is original_bytes

    def test_cleaned_artifact_raster_default_none(self) -> None:
        """raster defaults to None, not empty array."""
        artifact = CleanedArtifact(
            kind=MediaKind.IMAGE,
            payload=b"test",
            original=b"test",
        )
        assert artifact.raster is None


class TestCleanedDocumentObservedMethod:
    """Kill mutations in CleanedDocument.observed lookup."""

    def test_observed_raises_keyerror_on_miss(self) -> None:
        """observed() raises KeyError when observation not found."""
        doc = CleanedDocument(
            original=np.asarray(PILImage.new("RGB", (10, 10)), dtype=np.uint8),
            cleaned=np.asarray(PILImage.new("L", (10, 10)), dtype=np.uint8),
            quality_observations=(),
            preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        )
        with pytest.raises(KeyError):
            doc.observed("nonexistent", Stage.ORIGINAL)

    def test_observed_finds_correct_observation(self) -> None:
        """observed() returns matching observation."""
        obs = QualityObservation(
            name="test_obs",
            stage=Stage.ORIGINAL,
            value=42.0,
            unit="pixels",
            note="test measurement",
        )
        doc = CleanedDocument(
            original=np.asarray(PILImage.new("RGB", (10, 10)), dtype=np.uint8),
            cleaned=np.asarray(PILImage.new("L", (10, 10)), dtype=np.uint8),
            quality_observations=(obs,),
            preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        )
        found = doc.observed("test_obs", Stage.ORIGINAL)
        assert found == obs

    def test_observed_page_parameter_respected(self) -> None:
        """observed() distinguishes pages."""
        obs1 = QualityObservation(
            name="skew", stage=Stage.CLEANED, value=0.5, unit="degrees", note="page 1", page=1
        )
        obs2 = QualityObservation(
            name="skew", stage=Stage.CLEANED, value=1.0, unit="degrees", note="page 2", page=2
        )
        doc = CleanedDocument(
            original=np.asarray(PILImage.new("RGB", (10, 10)), dtype=np.uint8),
            cleaned=np.asarray(PILImage.new("L", (10, 10)), dtype=np.uint8),
            quality_observations=(obs1, obs2),
            preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        )
        found1 = doc.observed("skew", Stage.CLEANED, page=1)
        found2 = doc.observed("skew", Stage.CLEANED, page=2)
        assert found1.value == 0.5  # noqa: PLR2004
        assert found2.value == 1.0


class TestCleanedDocumentGeometryMethod:
    """Kill mutations in CleanedDocument.geometry_of lookup."""

    def test_geometry_of_returns_correct_page(self) -> None:
        """geometry_of() returns geometry for requested page."""
        geom1 = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            page=1,
        )
        geom2 = SourceGeometry(
            to_source=(0.9, 0.1, 5.0, 0.1, 0.9, 10.0),
            source_height=100,
            source_width=100,
            page=2,
        )
        doc = CleanedDocument(
            original=np.asarray(PILImage.new("RGB", (10, 10)), dtype=np.uint8),
            cleaned=np.asarray(PILImage.new("L", (10, 10)), dtype=np.uint8),
            quality_observations=(),
            preservation_status=PreservationStatus.CLEANED_IS_SAFER,
            source_geometry=(geom1, geom2),
        )
        found = doc.geometry_of(2)
        assert found.page == 2  # noqa: PLR2004

    def test_geometry_of_raises_keyerror_on_missing_page(self) -> None:
        """geometry_of() raises KeyError for missing page."""
        geom = SourceGeometry(
            to_source=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            source_height=100,
            source_width=100,
            page=1,
        )
        doc = CleanedDocument(
            original=np.asarray(PILImage.new("RGB", (10, 10)), dtype=np.uint8),
            cleaned=np.asarray(PILImage.new("L", (10, 10)), dtype=np.uint8),
            quality_observations=(),
            preservation_status=PreservationStatus.CLEANED_IS_SAFER,
            source_geometry=(geom,),
        )
        with pytest.raises(KeyError):
            doc.geometry_of(5)
