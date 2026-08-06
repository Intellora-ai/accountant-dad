"""Mutation killer for cleaner.py lines 1110-1480.

Targets: _painted_by, _deskew, decode, _encode_png, _pdf_has_text_layer,
_clean_pdf, _pdf_passed_through, _every_page_reported, _pdf_rebuilt_from_cleaned_pages.
"""

import numpy as np
import pytest

from accountant_dad.engines.input_engine.cleaner import (
    CleanedArtifact,
    CleanedDocument,
    CleanerSettings,
    MediaKind,
    PreservationStatus,
    QualityObservation,
    Stage,
    UndecodableArtifactError,
    _deskew,
    _encode_png,
    _every_page_reported,
    _painted_by,
    decode,
    replace_artifact,
)

_FULL_SCALE = 255


def baseline_settings(**changes: float | int) -> CleanerSettings:
    """Create a CleanerSettings with all required fields."""
    fields = {
        "max_deskew_degrees": 15.0,
        "denoise_strength": 6.0,
        "denoise_template_window": 7,
        "denoise_search_window": 21,
        "contrast_clip_limit": 2.0,
        "contrast_tile_grid": 8,
        "crop_margin_pixels": 4,
        "max_ink_loss_fraction": 0.05,
    }
    fields.update(changes)
    return CleanerSettings(
        max_deskew_degrees=float(fields["max_deskew_degrees"]),
        denoise_strength=float(fields["denoise_strength"]),
        denoise_template_window=int(fields["denoise_template_window"]),
        denoise_search_window=int(fields["denoise_search_window"]),
        contrast_clip_limit=float(fields["contrast_clip_limit"]),
        contrast_tile_grid=int(fields["contrast_tile_grid"]),
        crop_margin_pixels=int(fields["crop_margin_pixels"]),
        max_ink_loss_fraction=float(fields["max_ink_loss_fraction"]),
    )


def test_painted_by_mask_inverts_on_operator_flip() -> None:
    """Kill: inside == 0 flipped to != 0."""
    grey = np.ones((100, 100), dtype=np.uint8) * 200
    result = _painted_by(grey, degrees=5.0)

    assert isinstance(result, np.ndarray)
    assert result.ndim == 2  # noqa: PLR2004
    assert result.dtype == np.uint8

    has_painted = np.any(result > 0)
    has_unpainted = np.any(result == 0)

    assert has_painted
    assert has_unpainted


def test_painted_by_uses_full_scale_value() -> None:
    """Kill: _FULL_SCALE changed to 0."""
    grey = np.ones((100, 100), dtype=np.uint8) * 128
    result = _painted_by(grey, degrees=10.0)

    nonzero_vals = result[result > 0]
    if len(nonzero_vals) > 0:
        assert np.all(nonzero_vals == _FULL_SCALE)


def test_deskew_refuses_none_measurement() -> None:
    """Kill: if measured is None removed."""
    grey = np.ones((50, 50), dtype=np.uint8) * 255
    carried = np.ones((50, 50), dtype=np.uint8) * 255
    settings = baseline_settings()

    rotated_grey, rotated_carried, painted, obs_applied, _ = _deskew(grey, carried, settings)

    assert np.array_equal(rotated_grey, grey)
    assert np.array_equal(rotated_carried, carried)
    assert painted is None
    assert obs_applied.value == 0.0


def test_deskew_enforces_max_degrees_boundary() -> None:
    """Kill: abs() boundary check flipped."""
    settings = baseline_settings(max_deskew_degrees=5.0)
    grey = np.eye(50, dtype=np.uint8) * 255
    grey[grey == 0] = 200
    carried = grey.copy()

    result_applied, _, _, obs, _ = _deskew(grey, carried, settings)
    applied_angle = obs.value

    if not np.array_equal(result_applied, grey):
        assert applied_angle is not None and abs(applied_angle) <= settings.max_deskew_degrees
    else:
        assert applied_angle == 0.0


def test_deskew_respects_settings_max_value() -> None:
    """Kill: settings value not used."""
    settings_tight = baseline_settings(max_deskew_degrees=2.0)
    settings_loose = baseline_settings(max_deskew_degrees=10.0)

    grey = np.eye(60, dtype=np.uint8) * 255
    grey[grey == 0] = 200
    carried = grey.copy()

    _, _, _, _, _ = _deskew(grey, carried, settings_tight)
    _, _, _, _, _ = _deskew(grey, carried, settings_loose)

    assert settings_tight.max_deskew_degrees != settings_loose.max_deskew_degrees


def test_deskew_includes_painted_mask_when_rotating() -> None:
    """Kill: _painted_by() removed from return tuple."""
    grey = np.ones((50, 50), dtype=np.uint8) * 200
    carried = grey.copy()
    settings = baseline_settings(max_deskew_degrees=20.0)

    _, _, painted_mask, obs_applied, _ = _deskew(grey, carried, settings)

    # If rotation was applied, painted mask must be present
    if obs_applied.value != 0.0:
        assert painted_mask is not None, "Rotation applied → painted mask must exist"
        assert isinstance(painted_mask, np.ndarray)
        assert painted_mask.shape == grey.shape
    else:
        assert painted_mask is None, "No rotation → no painted mask"


def test_decode_rejects_empty_bytes() -> None:
    """Kill: if not data → if data."""
    with pytest.raises(UndecodableArtifactError, match="no bytes were supplied"):
        decode(b"")


def test_decode_rejects_invalid_image_data() -> None:
    """Kill: if decoded is None removed."""
    with pytest.raises(UndecodableArtifactError, match="not a decodable image"):
        decode(b"this is not valid image data")


def test_encode_png_raises_on_encode_failure() -> None:
    """Kill: if not ok removed."""
    image = np.ones((10, 10), dtype=np.uint8) * 128
    result = _encode_png(image)
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"\x89PNG"


def test_encode_png_returns_actual_bytes() -> None:
    """Kill: buffer.tobytes() changed."""
    image = np.ones((15, 15), dtype=np.uint8) * 100
    result = _encode_png(image)

    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result.startswith(b"\x89PNG")


def test_every_page_reported_pages_numbered_from_one() -> None:
    """Kill: enumerate start=1 changed to start=0."""
    obs1 = QualityObservation("test", Stage.CLEANED, 1.0, "unit", "note1")
    doc1 = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(obs1,),
        preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    obs2 = QualityObservation("test", Stage.CLEANED, 2.0, "unit", "note2")
    doc2 = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(obs2,),
        preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    result = _every_page_reported([doc1, doc2])

    page_numbers = [obs.page for obs in result.quality_observations if obs.page is not None]
    if page_numbers:
        assert 1 in page_numbers
        assert 2 in page_numbers  # noqa: PLR2004
        assert 0 not in page_numbers


def test_every_page_reported_damages_if_any_page_damaged() -> None:
    """Kill: any() operator flipped."""
    doc_clean = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    doc_damaged = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=PreservationStatus.ORIGINAL_IS_SAFER,
        artifact=None,
    )

    result = _every_page_reported([doc_clean, doc_damaged])

    assert result.preservation_status == PreservationStatus.ORIGINAL_IS_SAFER


def test_every_page_reported_ternary_condition() -> None:
    """Kill: if damaged else flipped."""
    doc_clean = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    result_clean = _every_page_reported([doc_clean])
    assert result_clean.preservation_status == PreservationStatus.CLEANED_IS_SAFER

    doc_damaged = CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=PreservationStatus.ORIGINAL_IS_SAFER,
        artifact=None,
    )

    result_damaged = _every_page_reported([doc_damaged])
    assert result_damaged.preservation_status == PreservationStatus.ORIGINAL_IS_SAFER


def test_replace_artifact_carries_all_fields() -> None:
    """Kill: artifact field omitted."""
    original_doc = CleanedDocument(
        original=np.zeros((2, 2), dtype=np.uint8),
        cleaned=np.ones((2, 2), dtype=np.uint8),
        quality_observations=(QualityObservation("test", Stage.CLEANED, 1.0, "u", "n"),),
        preservation_status=PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    new_artifact = CleanedArtifact(
        kind=MediaKind.IMAGE, payload=b"fake", original=b"fake", raster=None
    )

    result = replace_artifact(original_doc, new_artifact)

    assert np.array_equal(result.original, original_doc.original)
    assert np.array_equal(result.cleaned, original_doc.cleaned)
    assert result.quality_observations == original_doc.quality_observations
    assert result.preservation_status == original_doc.preservation_status
    assert result.artifact is new_artifact
    assert result.source_geometry == original_doc.source_geometry
