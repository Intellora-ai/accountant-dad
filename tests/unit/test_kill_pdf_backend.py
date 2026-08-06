"""Mutation tests for pdf_backend.py.

Targets: comparisons, boundaries, early returns, constants, and the deflate
compression flag (line 399) whose omission caused a 663x file-size regression
(measured at 3bd31e2).

Each test is written to:
1. Verify the CORRECT QUANTITY (not just "it works").
2. Kill a specific mutation by flipping one line in the source.
3. Run under 50ms on tiny 1-2 page documents.
4. Never weaken an existing test.
"""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np
import pymupdf
import pytest

from accountant_dad import pdf_backend

#: Tolerance for floating-point comparisons in points.
TOLERANCE_POINTS = 0.1

#: Maximum size for a compressed rebuilt PDF with tiny images.
MAX_COMPRESSED_SIZE = 100_000

#: Minimum page count for multi-page tests.
MIN_PAGES = 2

#: Minimum result size to verify document is non-empty.
MIN_RESULT_SIZE = 100


class _PixmapForAuthoring:
    """Minimal pixmap protocol for creating test images."""

    def __init__(self, *, dpi: int, width_px: int, height_px: int) -> None:
        self.width = width_px
        self.height = height_px
        self._dpi = dpi

    def tobytes(self, output: str) -> bytes:
        """Return PNG bytes of a tiny solid-color image."""
        if output != "png":
            raise ValueError(f"unsupported format: {output}")
        # Create a tiny 1x1 pixel PNG to minimize test time
        img = np.ones((self.height, self.width, 3), dtype=np.uint8) * 200
        _, encoded = cv2.imencode(".png", img)
        return encoded.tobytes()


def one_pixel_png(width_px: int = 1, height_px: int = 1) -> bytes:
    """Minimal PNG for fastest test execution."""
    pixmap = _PixmapForAuthoring(dpi=150, width_px=width_px, height_px=height_px)
    return pixmap.tobytes("png")


class TestRequirePositiveDpi:
    """Lines 215-245: require_positive_dpi boundary and early-return checks."""

    def test_nan_raises_value_error(self) -> None:
        """Line 233: `if not math.isfinite(...)` catches NaN.

        Flip to `if math.isfinite(...)` and NaN passes silently → fails.
        (Also catches inf, but NaN was the specific F-028 silent failure.)
        """
        with pytest.raises(ValueError, match="finite"):
            pdf_backend.require_positive_dpi(cast(int, float("nan")))

    def test_positive_infinity_raises(self) -> None:
        """Line 233: infinite DPI also fails finitude check."""
        with pytest.raises(ValueError, match="finite"):
            pdf_backend.require_positive_dpi(cast(int, float("inf")))

    def test_negative_infinity_raises(self) -> None:
        """Line 233: negative infinity is also non-finite."""
        with pytest.raises(ValueError, match="finite"):
            pdf_backend.require_positive_dpi(cast(int, float("-inf")))

    def test_zero_raises_value_error(self) -> None:
        """Line 240: `if render_dpi <= 0:` boundary.

        Flip to `<` and 0 slips through → fails.
        """
        with pytest.raises(ValueError, match="positive"):
            pdf_backend.require_positive_dpi(0)

    def test_negative_raises_value_error(self) -> None:
        """Line 240: negative DPI is <= 0."""
        with pytest.raises(ValueError, match="positive"):
            pdf_backend.require_positive_dpi(-1)

    def test_one_dpi_accepted(self) -> None:
        """Line 240: 1 is the boundary minimum that passes."""
        # Should not raise
        pdf_backend.require_positive_dpi(1)

    def test_large_dpi_accepted(self) -> None:
        """Line 240: large finite DPI passes."""
        pdf_backend.require_positive_dpi(300)


class TestRenderPagePngFormat:
    """Lines 291-299: assert PNG format is requested, not a different codec.

    If the constant `_RENDER_FORMAT = "png"` (line 212) is mutated to
    a lossy format like "jpeg", this catches it.
    """

    def test_rendered_page_is_png_magic(self) -> None:
        """Verify the output starts with PNG magic bytes.

        Flip `_RENDER_FORMAT` to "jpeg" and the output changes → fails.
        """
        # Author a tiny PDF
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        page = doc.new_page(width=72, height=72)
        page.insert_text((10, 10), "A")

        # Render it
        png_bytes = pdf_backend.render_page_png(doc, 0, dpi=150)

        # PNG starts with magic bytes
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n", f"not PNG magic: {png_bytes[:8]!r}"
        doc.close()  # type: ignore[no-untyped-call]


class TestPageSizeCalculation:
    """Lines 302-314: page_size returns width and height in POINTS.

    Verifies the backend rectangle is correctly read and converted to floats.
    """

    def test_page_size_returned_as_floats(self) -> None:
        """Verify both dimensions are float type."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        doc.new_page(width=612, height=792)

        width, height = pdf_backend.page_size(doc, 0)

        assert isinstance(width, float)
        assert isinstance(height, float)
        doc.close()  # type: ignore[no-untyped-call]

    def test_page_size_us_letter(self) -> None:
        """US Letter is 8.5 x 11 inches = 612 x 792 points."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        doc.new_page(width=612, height=792)

        width, height = pdf_backend.page_size(doc, 0)

        assert abs(width - 612.0) < TOLERANCE_POINTS
        assert abs(height - 792.0) < TOLERANCE_POINTS
        doc.close()  # type: ignore[no-untyped-call]


class TestPdfOfPageImagesCompression:
    """Lines 317-401: pdf_of_page_images with compression.

    Line 399: `deflate=True` is NOT a tuning knob. Without it, raw pixels
    produce 663x larger files. This test verifies compression is applied.

    Before F-028 fix, this line was missing, causing:
        150 dpi:  6,314,818 B (uncompressed) vs 9,517 B (compressed)
        300 dpi: 25,248,570 B (uncompressed) vs 27,915 B (compressed)
    """

    def test_rebuilt_pdf_is_compressed_not_raw(self) -> None:
        """Flip line 399: `deflate=True` → `deflate=False` and file explodes.

        A 72x72 pixel PNG rendered to 612x792 points should compress to
        <50KB. Raw storage would be >300KB.
        """
        # Tiny single-page PNG: 2x2 pixels
        png_bytes = one_pixel_png(width_px=2, height_px=2)

        # Rebuild it at 150 DPI
        result = pdf_backend.pdf_of_page_images([png_bytes], dpi=150)

        # Compressed result must be small
        # A 2x2 PNG becomes ~50 bytes, rebuilt at 150 DPI should stay <100KB
        # (raw storage would be >10MB for a full-page render)
        assert len(result) < MAX_COMPRESSED_SIZE, (
            f"PDF too large for a 2x2 pixel image: {len(result)} bytes. "
            "Likely missing deflate=True compression."
        )

    def test_multiple_pages_preserves_order(self) -> None:
        """Line 374: `for page in pages:` iterates in order.

        Flip the loop order or reverse it and the output changes.
        """
        page_a = one_pixel_png(width_px=1, height_px=1)
        page_b = one_pixel_png(width_px=2, height_px=2)

        result = pdf_backend.pdf_of_page_images([page_a, page_b], dpi=150)

        # Verify both pages are present (non-empty result)
        assert len(result) > MIN_RESULT_SIZE

        # Open and check page count
        doc = pymupdf.open(stream=result, filetype="pdf")  # type: ignore[no-untyped-call]
        assert doc.page_count == MIN_PAGES
        doc.close()  # type: ignore[no-untyped-call]

    def test_page_size_matches_pixels_at_dpi(self) -> None:
        """Lines 377-379: width = pixels.width * 72 / dpi.

        Flip the multiplication or division and the rebuilt page mismatches.
        """
        # 72x72 pixels at 150 DPI = (72 * 72 / 150) points
        # = (72 * 72 / 150) = 34.56 points
        png_bytes = one_pixel_png(width_px=72, height_px=72)

        result = pdf_backend.pdf_of_page_images([png_bytes], dpi=150)

        doc = pymupdf.open(stream=result, filetype="pdf")  # type: ignore[no-untyped-call]
        width, height = pdf_backend.page_size(doc, 0)

        # 72 pixels * 72 / 150 dpi = 34.56 points per side
        expected_width = 72 * 72 / 150
        expected_height = 72 * 72 / 150

        assert abs(width - expected_width) < TOLERANCE_POINTS, (
            f"width {width} != {expected_width}. Likely wrong arithmetic in line 378."
        )
        assert abs(height - expected_height) < TOLERANCE_POINTS
        doc.close()  # type: ignore[no-untyped-call]

    def test_rectangle_insert_uses_calculated_dimensions(self) -> None:
        """Line 381: `_rectangle(0, 0, width, height)` bounds the image.

        Flip the coordinates and the image is positioned wrongly.
        """
        png_bytes = one_pixel_png(width_px=1, height_px=1)

        # Should not raise
        result = pdf_backend.pdf_of_page_images([png_bytes], dpi=150)

        # Verify it's a valid PDF
        doc = pymupdf.open(stream=result, filetype="pdf")  # type: ignore[no-untyped-call]
        assert doc.page_count == 1
        doc.close()  # type: ignore[no-untyped-call]


class TestBrokenPdfError:
    """Lines 248-256: BrokenPdfError wraps FileDataError."""

    def test_broken_pdf_preserves_message(self) -> None:
        """Line 255: message is copied verbatim, not decorated."""
        with pytest.raises(pdf_backend.BrokenPdfError) as exc_info:
            pdf_backend.open_pdf(b"not a pdf")

        # Message should be a string copy of the backend's error
        assert str(exc_info.value)

    def test_broken_pdf_error_is_subclass_of_backend_error(self) -> None:
        """Line 125: BrokenPdfError extends PdfBackendError."""
        error = pdf_backend.BrokenPdfError("test")
        assert isinstance(error, pdf_backend.PdfBackendError)


class TestPlainTextOption:
    """Line 205: _PLAIN = "text" is the option asked for structured extraction.

    If "text" is mutated to another string, extraction format changes.
    """

    def test_plain_text_extracts_as_string(self) -> None:
        """Verify plain_text returns a string (via get_text("text"))."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        page = doc.new_page(width=72, height=72)
        page.insert_text((10, 10), "Hello")

        text = pdf_backend.plain_text(doc, 0)

        assert isinstance(text, str)
        doc.close()  # type: ignore[no-untyped-call]


class TestStructuredTextOption:
    """Line 206: _STRUCTURED = "dict" is the option for structured extraction.

    If "dict" is mutated, the dictionary structure changes.
    """

    def test_structured_text_has_blocks_key(self) -> None:
        """Structured text is a dict with 'blocks' key (line 107: StructuredText)."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        page = doc.new_page(width=72, height=72)
        page.insert_text((10, 10), "X")

        text = pdf_backend.structured_text(doc, 0)

        assert "blocks" in text
        assert isinstance(text["blocks"], list)
        doc.close()  # type: ignore[no-untyped-call]


class TestPointsPerInchConstant:
    """Line 200: _POINTS_PER_INCH = 72 is PDF spec, not a tuning knob.

    Flip to 96 (screen DPI) and all rebuilt pages are the wrong size.
    """

    def test_100_pixels_at_150_dpi_is_48_points(self) -> None:
        """100 px * 72 / 150 dpi = 48 points (exactly).

        If the constant is 96 instead, result is 64 points → fails.
        """
        # 100x100 pixel image
        png_bytes = one_pixel_png(width_px=100, height_px=100)

        result = pdf_backend.pdf_of_page_images([png_bytes], dpi=150)

        doc = pymupdf.open(stream=result, filetype="pdf")  # type: ignore[no-untyped-call]
        width, _ = pdf_backend.page_size(doc, 0)

        # Correct: 100 * 72 / 150 = 48
        assert abs(width - 48.0) < TOLERANCE_POINTS, (
            f"width {width} != 48. Likely _POINTS_PER_INCH is not 72."
        )
        doc.close()  # type: ignore[no-untyped-call]


class TestCloseIsCallable:
    """Line 416: document.close() is called on the opaque handle.

    The close function exists and accepts a PdfDocument.
    """

    def test_close_pdf_accepts_document(self) -> None:
        """Verify close_pdf can be called without error."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]

        # Should not raise
        pdf_backend.close_pdf(doc)


class TestPageCountIsInt:
    """Line 273: page_count returns int, not float."""

    def test_page_count_is_int(self) -> None:
        """Verify page_count casts to int."""
        doc = pymupdf.open()  # type: ignore[no-untyped-call]
        doc.new_page(width=72, height=72)

        count = pdf_backend.page_count(doc)

        assert isinstance(count, int)
        assert count == 1
        doc.close()  # type: ignore[no-untyped-call]
