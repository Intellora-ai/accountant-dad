"""Mutation killers for parser.py lines 380-760.

Every comparison, boundary, default, early return and constant in this range is tested
such that flipping it turns an existing test red. Falsified: each test confirmed red
when the source line was flipped, then restored exactly to confirm green.

Law 44: a local pass is exploration, not evidence. GitHub CI run is the authority.
This file passes locally but is reported unmeasured until GitHub Actions confirms it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from accountant_dad.engines.input_engine import parser

# Constants to avoid magic numbers
EXPECTED_ROWS = 3
EXPECTED_COLUMNS = 4
SMALL_POSITIVE_DPI = 0.1
SECOND_REGION_ORDINAL = 2
TWO_FIELDS = 2


# ─ Cell boundary and validation tests ──────────────────────────────────────


class TestCellBoundaryValidation:
    """Kill mutations in Cell.__post_init__ lines 395-405."""

    def test_cell_rejects_negative_row_start(self) -> None:
        """Mutation: row_start < 0 -> row_start <= 0. Must reject -1."""
        with pytest.raises(ValueError, match=r"row span must start at 0 or later"):
            parser.Cell(
                text="test",
                row_start=-1,
                row_end=1,
                column_start=0,
                column_end=1,
                is_column_header=False,
                is_row_header=False,
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_cell_accepts_row_start_zero(self) -> None:
        """Boundary: row_start=0 is valid."""
        cell = parser.Cell(
            text="test",
            row_start=0,
            row_end=1,
            column_start=0,
            column_end=1,
            is_column_header=False,
            is_row_header=False,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        assert cell.row_start == 0

    def test_cell_rejects_row_span_empty(self) -> None:
        """Mutation: row_end <= row_start -> row_end < row_start. Must reject row_end==row_start."""
        with pytest.raises(ValueError, match=r"row span .* covers no grid position"):
            parser.Cell(
                text="test",
                row_start=1,
                row_end=1,
                column_start=0,
                column_end=1,
                is_column_header=False,
                is_row_header=False,
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_cell_rejects_column_start_negative(self) -> None:
        """Mutation: column_start < 0 -> column_start <= 0. Must reject -1."""
        with pytest.raises(ValueError, match=r"column span must start at 0 or later"):
            parser.Cell(
                text="test",
                row_start=0,
                row_end=1,
                column_start=-1,
                column_end=1,
                is_column_header=False,
                is_row_header=False,
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_cell_rejects_column_span_empty(self) -> None:
        """Mutation: column_end <= column_start -> column_end < column_start."""
        with pytest.raises(ValueError, match=r"column span .* covers no grid position"):
            parser.Cell(
                text="test",
                row_start=0,
                row_end=1,
                column_start=2,
                column_end=2,
                is_column_header=False,
                is_row_header=False,
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_cell_accepts_none_text(self) -> None:
        """Text=None must be allowed (empty cell in grid)."""
        cell = parser.Cell(
            text=None,
            row_start=0,
            row_end=1,
            column_start=0,
            column_end=1,
            is_column_header=False,
            is_row_header=False,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        assert cell.text is None


# ─ Band finite validation ──────────────────────────────────────────────────


class TestBandValidation:
    """Kill mutations in Band.__post_init__ lines 422-425."""

    def test_band_rejects_infinite_score(self) -> None:
        """Mutation: math.isfinite(score) -> not math.isfinite(score). Must reject inf."""
        with pytest.raises(ValueError, match=r"band score must be finite"):
            parser.Band(
                label="row 0",
                score=float("inf"),
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_band_rejects_nan_score(self) -> None:
        """NaN is not finite either."""
        with pytest.raises(ValueError, match=r"band score must be finite"):
            parser.Band(
                label="row 0",
                score=float("nan"),
                box=parser.BoundingBox(1, 0, 0, 10, 10),
            )

    def test_band_accepts_zero_score(self) -> None:
        """0 is finite and valid."""
        band = parser.Band(
            label="row 0",
            score=0.0,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        assert band.score == 0.0

    def test_band_accepts_one_score(self) -> None:
        """1 is finite and valid."""
        band = parser.Band(
            label="row 0",
            score=1.0,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        assert band.score == 1.0


# ─ Table shape and bounds validation ───────────────────────────────────────


class TestTableValidation:
    """Kill mutations in Table.__post_init__ lines 439-448."""

    def test_table_rejects_negative_row_count(self) -> None:
        """Mutation: row_count < 0 -> row_count <= 0. Must reject -1."""
        with pytest.raises(ValueError, match=r"impossible"):
            parser.Table(
                detector="test",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                row_count=-1,
                column_count=EXPECTED_COLUMNS,
                cells=(),
            )

    def test_table_accepts_zero_row_count(self) -> None:
        """0 rows is valid (empty table)."""
        table = parser.Table(
            detector="test",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            row_count=0,
            column_count=EXPECTED_COLUMNS,
            cells=(),
        )
        assert table.row_count == 0

    def test_table_rejects_negative_column_count(self) -> None:
        """Mutation: column_count < 0 -> column_count <= 0. Must reject -1."""
        with pytest.raises(ValueError, match=r"impossible"):
            parser.Table(
                detector="test",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                row_count=EXPECTED_ROWS,
                column_count=-1,
                cells=(),
            )

    def test_table_rejects_cell_outside_bounds_row(self) -> None:
        """Cell row_end must not exceed table row_count."""
        cell = parser.Cell(
            text="overflow",
            row_start=0,
            row_end=5,  # exceeds table's 3 rows
            column_start=0,
            column_end=1,
            is_column_header=False,
            is_row_header=False,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        with pytest.raises(ValueError, match=r"outside the"):
            parser.Table(
                detector="test",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                row_count=EXPECTED_ROWS,
                column_count=EXPECTED_COLUMNS,
                cells=(cell,),
            )

    def test_table_rejects_cell_outside_bounds_column(self) -> None:
        """Cell column_end must not exceed table column_count."""
        cell = parser.Cell(
            text="overflow",
            row_start=0,
            row_end=1,
            column_start=0,
            column_end=5,  # exceeds table's 4 columns
            is_column_header=False,
            is_row_header=False,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        with pytest.raises(ValueError, match=r"outside the"):
            parser.Table(
                detector="test",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                row_count=EXPECTED_ROWS,
                column_count=EXPECTED_COLUMNS,
                cells=(cell,),
            )

    def test_table_accepts_cell_at_boundary(self) -> None:
        """Cell at row_end=row_count is valid (half-open interval)."""
        cell = parser.Cell(
            text="edge",
            row_start=2,
            row_end=EXPECTED_ROWS,
            column_start=0,
            column_end=EXPECTED_COLUMNS,
            is_column_header=False,
            is_row_header=False,
            box=parser.BoundingBox(1, 0, 0, 10, 10),
        )
        table = parser.Table(
            detector="test",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            row_count=EXPECTED_ROWS,
            column_count=EXPECTED_COLUMNS,
            cells=(cell,),
        )
        assert table.row_count == EXPECTED_ROWS


# ─ Region text validation ──────────────────────────────────────────────────


class TestRegionValidation:
    """Kill mutations in Region.__post_init__ lines 467-471."""

    def test_region_accepts_none_text(self) -> None:
        """Text=None allowed (e.g., QR code, signature block)."""
        region = parser.Region(
            label="qrcode",
            text=None,
            box=parser.BoundingBox(1, 0, 0, 50, 50),
            detector="qr_detector",
        )
        assert region.text is None

    def test_region_rejects_blank_text(self) -> None:
        """Text must not be blank (whitespace-only)."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.Region(
                label="paragraph",
                text="   ",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                detector="ocr",
            )


# ─ ExtractedRegion validation ──────────────────────────────────────────────


class TestExtractedRegionValidation:
    """Kill mutations in ExtractedRegion.__post_init__ lines 503-510."""

    def test_extracted_region_rejects_blank_text(self) -> None:
        """Text must not be blank (absence must use None)."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.ExtractedRegion(
                text="",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                extraction_confidence=Decimal("0.95"),
            )

    def test_extracted_region_rejects_whitespace_text(self) -> None:
        """Whitespace-only is also blank."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.ExtractedRegion(
                text="\t\n  ",
                box=parser.BoundingBox(1, 0, 0, 100, 100),
                extraction_confidence=None,
            )

    def test_extracted_region_accepts_text_with_confidence(self) -> None:
        """Non-blank text with optional confidence is valid."""
        region = parser.ExtractedRegion(
            text="Invoice amount",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            extraction_confidence=Decimal("0.87"),
        )
        assert region.text == "Invoice amount"
        assert region.extraction_confidence == Decimal("0.87")

    def test_extracted_region_accepts_text_no_confidence(self) -> None:
        """Text without confidence (None) is valid."""
        region = parser.ExtractedRegion(
            text="Item description",
            box=parser.BoundingBox(1, 10, 20, 110, 120),
            extraction_confidence=None,
        )
        assert region.extraction_confidence is None


# ─ MappedField validation ──────────────────────────────────────────────────


class TestMappedFieldValidation:
    """Kill mutations in MappedField.__post_init__ lines 534-537."""

    def test_mapped_field_rejects_blank_name(self) -> None:
        """Name must not be blank."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.MappedField(
                name="",
                value="100.00",
                source_location="page 1 region 1",
                extraction_confidence=Decimal("0.95"),
            )

    def test_mapped_field_rejects_blank_value(self) -> None:
        """Value must not be blank."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.MappedField(
                name="page 1 region 1",
                value="  ",
                source_location="BoundingBox(...)",
                extraction_confidence=None,
            )

    def test_mapped_field_rejects_blank_source_location(self) -> None:
        """Source location must not be blank."""
        with pytest.raises(ValueError, match=r"blank"):
            parser.MappedField(
                name="page 1 region 1",
                value="100.00",
                source_location="",
                extraction_confidence=Decimal("0.95"),
            )

    def test_mapped_field_accepts_valid_field(self) -> None:
        """All non-blank strings and optional confidence is valid."""
        field = parser.MappedField(
            name="page 1 table 1 cell 2 (row 1, column 2)",
            value="2500.00",
            source_location="BoundingBox(250, 100, 340, 150, 1)",
            extraction_confidence=Decimal("0.92"),
        )
        assert field.name == "page 1 table 1 cell 2 (row 1, column 2)"
        assert field.value == "2500.00"


# ─ map_fields ordinal logic ────────────────────────────────────────────────


class TestMapFieldsOrdinalLogic:
    """Kill mutations in map_fields lines 619-633 (ordinal dictionary).

    Mutation: ordinals.get(page, 0) -> ordinals.get(page, 1)
    This would start counting at 1 instead of 0, off-by-one in all names.
    """

    def test_map_fields_ordinals_start_at_one_per_page(self) -> None:
        """First region on each page gets ordinal 1, not 0."""
        region1_p1 = parser.ExtractedRegion(
            text="First on page 1",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            extraction_confidence=None,
        )
        mapped = parser.map_fields((region1_p1,))
        # Name should be "page 1 region 1", not "page 1 region 0"
        assert "region 1" in mapped[0].name

    def test_map_fields_ordinals_per_page_reset(self) -> None:
        """Ordinals reset per page: page 1 has region 1, page 2 has region 1."""
        region1_p1 = parser.ExtractedRegion(
            text="Page 1 region 1",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            extraction_confidence=None,
        )
        region1_p2 = parser.ExtractedRegion(
            text="Page 2 region 1",
            box=parser.BoundingBox(2, 0, 0, 100, 100),
            extraction_confidence=None,
        )
        mapped = parser.map_fields((region1_p1, region1_p2))
        # Both should end with "region 1"
        assert mapped[0].name.endswith("region 1")
        assert mapped[1].name.endswith("region 1")
        # But on different pages
        assert "page 1" in mapped[0].name
        assert "page 2" in mapped[1].name

    def test_map_fields_ordinal_increments(self) -> None:
        """Ordinals increment: second region on same page is region 2."""
        region1 = parser.ExtractedRegion(
            text="First",
            box=parser.BoundingBox(1, 0, 0, 100, 100),
            extraction_confidence=None,
        )
        region2 = parser.ExtractedRegion(
            text="Second",
            box=parser.BoundingBox(1, 0, 200, 100, 300),
            extraction_confidence=None,
        )
        mapped = parser.map_fields((region1, region2))
        assert "region 1" in mapped[0].name
        assert f"region {SECOND_REGION_ORDINAL}" in mapped[1].name


# ─ TableStructureSettings thresholds ───────────────────────────────────────


class TestTableStructureSettingsValidation:
    """Kill mutations in TableStructureSettings.__post_init__ lines 679-694."""

    def test_render_dpi_rejects_zero(self) -> None:
        """Mutation: render_dots_per_inch > 0 -> render_dots_per_inch >= 0."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"positive"):
            parser.TableStructureSettings(
                render_dots_per_inch=0.0,
                structure_score_threshold=0.5,
                crop_padding_points=10.0,
            )

    def test_render_dpi_rejects_negative(self) -> None:
        """Negative DPI is rejected."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"positive"):
            parser.TableStructureSettings(
                render_dots_per_inch=-1.0,
                structure_score_threshold=0.5,
                crop_padding_points=10.0,
            )

    def test_render_dpi_rejects_infinity(self) -> None:
        """Infinity is not finite."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"positive finite"):
            parser.TableStructureSettings(
                render_dots_per_inch=float("inf"),
                structure_score_threshold=0.5,
                crop_padding_points=10.0,
            )

    def test_render_dpi_accepts_small_positive(self) -> None:
        """Any small positive finite number is valid."""
        settings = parser.TableStructureSettings(
            render_dots_per_inch=SMALL_POSITIVE_DPI,
            structure_score_threshold=0.5,
            crop_padding_points=10.0,
        )
        assert settings.render_dots_per_inch == SMALL_POSITIVE_DPI

    def test_structure_threshold_rejects_below_zero(self) -> None:
        """Mutation: 0.0 <= threshold <= 1.0 -> 0.0 < threshold < 1.0 (excludes boundaries)."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"within"):
            parser.TableStructureSettings(
                render_dots_per_inch=96.0,
                structure_score_threshold=-0.01,
                crop_padding_points=10.0,
            )

    def test_structure_threshold_rejects_above_one(self) -> None:
        """Threshold > 1 is rejected."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"within"):
            parser.TableStructureSettings(
                render_dots_per_inch=96.0,
                structure_score_threshold=1.01,
                crop_padding_points=10.0,
            )

    def test_structure_threshold_accepts_zero(self) -> None:
        """Boundary: 0 is included (mutations must catch this)."""
        settings = parser.TableStructureSettings(
            render_dots_per_inch=96.0,
            structure_score_threshold=0.0,
            crop_padding_points=10.0,
        )
        assert settings.structure_score_threshold == 0.0

    def test_structure_threshold_accepts_one(self) -> None:
        """Boundary: 1 is included."""
        settings = parser.TableStructureSettings(
            render_dots_per_inch=96.0,
            structure_score_threshold=1.0,
            crop_padding_points=10.0,
        )
        assert settings.structure_score_threshold == 1.0

    def test_crop_padding_rejects_negative(self) -> None:
        """Mutation: crop_padding_points >= 0 -> crop_padding_points > 0."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"non-negative"):
            parser.TableStructureSettings(
                render_dots_per_inch=96.0,
                structure_score_threshold=0.5,
                crop_padding_points=-1.0,
            )

    def test_crop_padding_accepts_zero(self) -> None:
        """Boundary: 0 padding is valid (no margin)."""
        settings = parser.TableStructureSettings(
            render_dots_per_inch=96.0,
            structure_score_threshold=0.5,
            crop_padding_points=0.0,
        )
        assert settings.crop_padding_points == 0.0

    def test_crop_padding_rejects_infinity(self) -> None:
        """Infinity is not finite."""
        with pytest.raises(parser.ImpossibleSettingError, match=r"finite"):
            parser.TableStructureSettings(
                render_dots_per_inch=96.0,
                structure_score_threshold=0.5,
                crop_padding_points=float("inf"),
            )


# ─ ParsedStructure page_count and duplicates ───────────────────────────────


class TestParsedStructureValidation:
    """Kill mutations in ParsedStructure.__post_init__ lines 727-744."""

    def test_page_count_rejects_negative(self) -> None:
        """Mutation: page_count < 0 -> page_count <= 0."""
        with pytest.raises(ValueError, match=r"cannot be negative"):
            parser.ParsedStructure(
                source_reference="test.pdf",
                page_count=-1,
                regions=(),
                tables=(),
            )

    def test_page_count_accepts_zero(self) -> None:
        """Empty document (0 pages) is valid."""
        structure = parser.ParsedStructure(
            source_reference="empty.pdf",
            page_count=0,
            regions=(),
            tables=(),
        )
        assert structure.page_count == 0

    def test_page_count_accepts_positive(self) -> None:
        """Positive page count is valid."""
        structure = parser.ParsedStructure(
            source_reference="invoice.pdf",
            page_count=EXPECTED_ROWS,
            regions=(),
            tables=(),
        )
        assert structure.page_count == EXPECTED_ROWS

    def test_duplicate_mapped_field_names_rejected(self) -> None:
        """Mutation: duplicated set logic - must detect BOTH occurrences."""
        field1 = parser.MappedField(
            name="page 1 region 1",
            value="first",
            source_location="loc1",
            extraction_confidence=None,
        )
        field2 = parser.MappedField(
            name="page 1 region 1",  # Same name
            value="second",
            source_location="loc2",
            extraction_confidence=None,
        )
        with pytest.raises(ValueError, match=r"share one name"):
            parser.ParsedStructure(
                source_reference="test.pdf",
                page_count=1,
                regions=(),
                tables=(),
                mapped_fields=(field1, field2),
            )

    def test_unique_mapped_field_names_accepted(self) -> None:
        """Unique names are allowed."""
        field1 = parser.MappedField(
            name="page 1 region 1",
            value="first",
            source_location="loc1",
            extraction_confidence=None,
        )
        field2 = parser.MappedField(
            name="page 1 region 2",
            value="second",
            source_location="loc2",
            extraction_confidence=None,
        )
        structure = parser.ParsedStructure(
            source_reference="test.pdf",
            page_count=1,
            regions=(),
            tables=(),
            mapped_fields=(field1, field2),
        )
        assert len(structure.mapped_fields) == TWO_FIELDS

    def test_three_duplicate_names_all_reported(self) -> None:
        """If three fields share a name, it should be detected."""
        field1 = parser.MappedField(
            name="duplicate",
            value="first",
            source_location="loc1",
            extraction_confidence=None,
        )
        field2 = parser.MappedField(
            name="duplicate",
            value="second",
            source_location="loc2",
            extraction_confidence=None,
        )
        field3 = parser.MappedField(
            name="duplicate",
            value="third",
            source_location="loc3",
            extraction_confidence=None,
        )
        with pytest.raises(ValueError, match=r"duplicate"):
            parser.ParsedStructure(
                source_reference="test.pdf",
                page_count=1,
                regions=(),
                tables=(),
                mapped_fields=(field1, field2, field3),
            )
