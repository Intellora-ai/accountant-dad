"""Mutation-killing tests for parser.py lines 1-380.

Focus: boundaries, comparisons, constants, and transformation logic that have
no existing mutation guard. Each test is built to RED on a single flipped bit.
"""

from __future__ import annotations

import pytest

from accountant_dad.engines.input_engine import parser

# Measurement constants for bounding box tests (per location, exact values required)
_PAGE_HEIGHT = 100
_BOX_LEFT = 10
_BOX_TOP = 20  # TOPLEFT: top coordinate
_BOX_RIGHT = 90
_BOX_BOTTOM = 40  # TOPLEFT: bottom coordinate (must be > top)
# For BOTTOMLEFT tests: top=70, bottom=30 converts to top=30, bottom=70 in TOPLEFT
_BOTTOMLEFT_TOP = 70  # higher y value in BOTTOMLEFT
_BOTTOMLEFT_BOTTOM = 30  # lower y value in BOTTOMLEFT
_BOTTOMLEFT_TO_TOPLEFT_TOP = 30  # result after inversion
_BOTTOMLEFT_TO_TOPLEFT_BOTTOM = 70  # result after inversion


class TestReportedTextMutation:
    """Test the exact logic of reported_text() line 293-307."""

    def test_empty_string_becomes_none_not_empty_string(self) -> None:
        """Line 306-307: `text or None` — mutation: remove the `or None`."""
        # Empty string should become None, not stay empty.
        result = parser.reported_text("")
        assert result is None, "Empty string must become None, not empty string"

    def test_whitespace_string_becomes_none(self) -> None:
        """Line 306-307: whitespace is stripped to empty, then `or None` fires."""
        result = parser.reported_text("   ")
        assert result is None, "Whitespace string must become None"

    def test_whitespace_with_text_becomes_text(self) -> None:
        """Line 306: strip() is called — without it, this would keep spaces."""
        result = parser.reported_text("  hello  ")
        assert result == "hello", "Text must be stripped"

    def test_zero_string_survives_not_converted_to_none(self) -> None:
        """Line 307: `or None` must NOT convert "0" to None (docstring example)."""
        result = parser.reported_text("0")
        assert result == "0", '"0" must survive, not become None'

    def test_tab_and_newline_are_stripped(self) -> None:
        """Line 306: strip() removes all whitespace including tabs, newlines."""
        result = parser.reported_text("\t\n  text  \r\n")
        assert result == "text"


class TestBoundingBoxPageBoundary:
    """Test BoundingBox.__post_init__() page validation, line 330-331."""

    def test_page_zero_rejected(self) -> None:
        """Line 330: `if self.page < 1:` — mutation: use `<=` instead."""
        with pytest.raises(ValueError, match="page must be 1 or greater"):
            parser.BoundingBox(page=0, left=0, top=0, right=100, bottom=100)

    def test_page_negative_rejected(self) -> None:
        """Line 330: boundary check must reject negatives."""
        with pytest.raises(ValueError, match="page must be 1 or greater"):
            parser.BoundingBox(page=-1, left=0, top=0, right=100, bottom=100)

    def test_page_one_accepted(self) -> None:
        """Line 330: page=1 is the minimum, must be accepted."""
        box = parser.BoundingBox(page=1, left=0, top=0, right=100, bottom=100)
        assert box.page == 1


class TestBoundingBoxNonfinite:
    """Test BoundingBox finite check, line 338-339."""

    def test_left_nan_rejected(self) -> None:
        """Line 338: `if not math.isfinite(value):` — NaN must be rejected."""
        with pytest.raises(ValueError, match="left must be finite"):
            parser.BoundingBox(page=1, left=float("nan"), top=0, right=100, bottom=100)

    def test_top_inf_rejected(self) -> None:
        """Line 338: infinity must be rejected."""
        with pytest.raises(ValueError, match="top must be finite"):
            parser.BoundingBox(page=1, left=0, top=float("inf"), right=100, bottom=100)

    def test_right_neginf_rejected(self) -> None:
        """Line 338: negative infinity must be rejected."""
        with pytest.raises(ValueError, match="right must be finite"):
            parser.BoundingBox(page=1, left=0, top=0, right=float("-inf"), bottom=100)

    def test_bottom_neginf_rejected(self) -> None:
        """Line 338: bottom can also be infinite and must be rejected."""
        with pytest.raises(ValueError, match="bottom must be finite"):
            parser.BoundingBox(page=1, left=0, top=0, right=100, bottom=float("inf"))


class TestBoundingBoxNegative:
    """Test BoundingBox negative check, line 340-341."""

    def test_left_negative_rejected(self) -> None:
        """Line 340: `if value < 0:` — negative coordinates rejected."""
        with pytest.raises(ValueError, match="left must not be negative"):
            parser.BoundingBox(page=1, left=-0.1, top=0, right=100, bottom=100)

    def test_top_negative_rejected(self) -> None:
        """Line 340: top can also be negative."""
        with pytest.raises(ValueError, match="top must not be negative"):
            parser.BoundingBox(page=1, left=0, top=-1, right=100, bottom=100)

    def test_zero_coordinates_accepted(self) -> None:
        """Line 340: zero is allowed (not `<= 0`), it's a valid coordinate."""
        box = parser.BoundingBox(page=1, left=0, top=0, right=100, bottom=100)
        assert box.left == 0 and box.top == 0


class TestBoundingBoxInverted:
    """Test BoundingBox inversion checks, line 345-348."""

    def test_right_less_than_left_rejected(self) -> None:
        """Line 345: `if self.right < self.left:` — mutation: use `>` instead."""
        with pytest.raises(ValueError, match=r"right .* is left of left"):
            parser.BoundingBox(page=1, left=100, top=0, right=50, bottom=100)

    def test_bottom_less_than_top_rejected(self) -> None:
        """Line 347: `if self.bottom < self.top:` — mutation: use `>` instead."""
        with pytest.raises(ValueError, match=r"bottom .* is above top"):
            parser.BoundingBox(page=1, left=0, top=100, right=100, bottom=50)

    def test_right_equals_left_allowed(self) -> None:
        """Line 345: degenerate (zero-width) is allowed per docstring."""
        box = parser.BoundingBox(page=1, left=50, top=0, right=50, bottom=100)
        assert box.right == box.left

    def test_bottom_equals_top_allowed(self) -> None:
        """Line 347: degenerate (zero-height) is allowed per docstring."""
        box = parser.BoundingBox(page=1, left=0, top=50, right=100, bottom=50)
        assert box.bottom == box.top


class TestToTopLeftBoxOriginDetection:
    """Test _to_top_left_box() origin parsing, line 367-374."""

    def test_bottom_left_origin_inverted_correctly(self) -> None:
        """Line 368: `if token == _BOTTOM_LEFT:` — must match and invert."""
        # BOTTOMLEFT: top=70, bottom=30 (higher y is "up")
        # After inversion: new_top = 100-70=30, new_bottom = 100-30=70
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOTTOMLEFT_TOP, _BOX_RIGHT, _BOTTOMLEFT_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="CoordOrigin.BOTTOMLEFT",
        )
        msg = "y=70 from bottom should become 30 from top"
        assert box.top == _BOTTOMLEFT_TO_TOPLEFT_TOP, msg
        msg2 = "y=30 from bottom should become 70 from top"
        assert box.bottom == _BOTTOMLEFT_TO_TOPLEFT_BOTTOM, msg2

    def test_bottom_left_underscore_normalization(self) -> None:
        """Line 367: token normalization removes `_` — must work."""
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOTTOMLEFT_TOP, _BOX_RIGHT, _BOTTOMLEFT_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="BOTTOM_LEFT",
        )
        msg = "BOTTOM_LEFT token (with underscore) must normalize"
        assert box.top == _BOTTOMLEFT_TO_TOPLEFT_TOP, msg

    def test_bottom_left_lowercase_normalization(self) -> None:
        """Line 367: token normalization converts to UPPER."""
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOTTOMLEFT_TOP, _BOX_RIGHT, _BOTTOMLEFT_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="CoordOrigin.bottomleft",
        )
        msg = "lowercase must normalize to BOTTOMLEFT"
        assert box.top == _BOTTOMLEFT_TO_TOPLEFT_TOP, msg

    def test_top_left_origin_not_inverted(self) -> None:
        """Line 370: `elif token != _TOP_LEFT:` — TOPLEFT is passed through."""
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOX_TOP, _BOX_RIGHT, _BOX_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="CoordOrigin.TOPLEFT",
        )
        # TOPLEFT is NOT inverted
        assert box.top == _BOX_TOP, "TOPLEFT origin must NOT be inverted"
        assert box.bottom == _BOX_BOTTOM, "TOPLEFT origin must NOT be inverted"

    def test_top_left_normalized_passthrough(self) -> None:
        """Line 370: token normalization applies to TOPLEFT check too."""
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOX_TOP, _BOX_RIGHT, _BOX_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="top_left",
        )
        assert box.top == _BOX_TOP, "top_left (normalized) must pass through unchanged"

    def test_unknown_origin_rejected(self) -> None:
        """Line 371-373: unknown origin must raise ValueError."""
        with pytest.raises(ValueError, match="unknown coordinate origin"):
            parser._to_top_left_box(
                (_BOX_LEFT, _BOX_TOP, _BOX_RIGHT, _BOX_BOTTOM),
                page=1,
                page_height=_PAGE_HEIGHT,
                origin="UNKNOWN_ORIGIN",
            )


class TestToTopLeftBoxEdgePreservation:
    """Test that _to_top_left_box() preserves left/right correctly."""

    def test_left_and_right_preserved_from_bottom_left(self) -> None:
        """Lines 366-369: left and right are NOT transformed in BOTTOMLEFT."""
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOTTOMLEFT_TOP, _BOX_RIGHT, _BOTTOMLEFT_BOTTOM),
            page=1,
            page_height=_PAGE_HEIGHT,
            origin="BOTTOMLEFT",
        )
        assert box.left == _BOX_LEFT, "left must be preserved"
        assert box.right == _BOX_RIGHT, "right must be preserved"

    def test_page_preserved(self) -> None:
        """Line 375: page parameter is passed through to BoundingBox."""
        test_page = 5
        box = parser._to_top_left_box(
            (_BOX_LEFT, _BOX_TOP, _BOX_RIGHT, _BOX_BOTTOM),
            page=test_page,
            page_height=_PAGE_HEIGHT,
            origin="TOPLEFT",
        )
        assert box.page == test_page


class TestRejectBlankFunction:
    """Test _reject_blank() line 288-290."""

    def test_empty_string_rejected(self) -> None:
        """Line 289: `if not value.strip():` — empty string must be rejected."""
        with pytest.raises(ValueError, match="must not be empty or blank"):
            parser._reject_blank("", "test_value")

    def test_whitespace_only_rejected(self) -> None:
        """Line 289: whitespace-only must be rejected."""
        with pytest.raises(ValueError, match="must not be empty or blank"):
            parser._reject_blank("   \t\n  ", "test_value")

    def test_nonempty_accepted(self) -> None:
        """Line 289: non-empty string must not raise."""
        parser._reject_blank("hello", "test_value")  # Should not raise

    def test_what_field_in_error_message(self) -> None:
        """Line 290: error message includes the 'what' parameter."""
        with pytest.raises(ValueError, match="my_field"):
            parser._reject_blank("", "my_field")


class TestConstants:
    """Test that constants have expected values (mutation: flip value)."""

    def test_success_constant_value(self) -> None:
        """Line 216: `_SUCCESS = "SUCCESS"` — mutation: change string."""
        assert parser._SUCCESS == "SUCCESS"

    def test_partial_success_constant_value(self) -> None:
        """Line 220: `_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"` — mutation: change."""
        assert parser._PARTIAL_SUCCESS == "PARTIAL_SUCCESS"

    def test_docling_distributions_is_tuple(self) -> None:
        """Line 228: `_DOCLING_DISTRIBUTIONS` must be a tuple (not list)."""
        assert isinstance(parser._DOCLING_DISTRIBUTIONS, tuple)

    def test_docling_distributions_contains_required_entries(self) -> None:
        """Line 228: tuple must contain the documented distributions."""
        assert "docling" in parser._DOCLING_DISTRIBUTIONS
        assert "docling-slim" in parser._DOCLING_DISTRIBUTIONS
        assert "docling-core" in parser._DOCLING_DISTRIBUTIONS
        assert "docling-ibm-models" in parser._DOCLING_DISTRIBUTIONS

    def test_docling_distributions_count(self) -> None:
        """Line 228: tuple has exactly 4 entries (mutation: add/remove one)."""
        expected = 4  # docling, docling-slim, docling-core, docling-ibm-models
        assert len(parser._DOCLING_DISTRIBUTIONS) == expected


class TestPointsPerInch:
    """Test PDF constant, line 211."""

    def test_points_per_inch_value(self) -> None:
        """Line 211: `_POINTS_PER_INCH = 72.0` — mutation: change number."""
        assert parser._POINTS_PER_INCH == 72.0  # noqa: PLR2004


class TestCoordinateOriginConstants:
    """Test coordinate origin token constants, line 209-210."""

    def test_bottom_left_token(self) -> None:
        """Line 209: `_BOTTOM_LEFT = "BOTTOMLEFT"` — mutation: change string."""
        assert parser._BOTTOM_LEFT == "BOTTOMLEFT"

    def test_top_left_token(self) -> None:
        """Line 210: `_TOP_LEFT = "TOPLEFT"` — mutation: change string."""
        assert parser._TOP_LEFT == "TOPLEFT"
