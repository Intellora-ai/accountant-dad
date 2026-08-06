"""Mutation-killing tests for clean_artifact dispatcher (lines 1780-1846).

These tests guard against specific mutations:
1. Removing or weakening the `if not data:` boundary check
2. Reintroducing a branch on `kind` in the dispatcher
3. Changing exception types to confuse empty bytes with unknown kind
4. Letting unknown kinds fall through silently via .get() fallback
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pytest

from accountant_dad.engines.input_engine import cleaner

# ── Fixtures ──────────────────────────────────────────────────────────────

RENDER_DPI = 150


def a_settings() -> cleaner.CleanerSettings:
    """Minimal valid settings."""
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


def a_cleaned_doc() -> cleaner.CleanedDocument:
    """Minimal valid cleaned document for test cleaners."""
    return cleaner.CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=cleaner.PreservationStatus.CLEANED_IS_SAFER,
        artifact=cleaner.CleanedArtifact(
            kind=cleaner.MediaKind.IMAGE,
            payload=b"cleaned",
            original=b"original",
            raster=np.zeros((1, 1), dtype=np.uint8),
        ),
    )


# ── Mutation-killing tests ────────────────────────────────────────────────


def test_custom_image_cleaner_is_called_via_dispatcher() -> None:
    """Catch branch mutant like `if kind == MediaKind.IMAGE: return _clean_image_document()`.

    If clean_artifact branches on kind, a custom IMAGE implementation will never
    be reached — the hardcoded path runs instead. This test verifies dispatch
    uses the registry even for known kinds.
    """
    seen: list[tuple[bytes, cleaner.CleanerSettings, int]] = []

    def custom_image_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        seen.append((data, settings, render_dpi))
        result = a_cleaned_doc()
        return cleaner.replace_artifact(
            result,
            cleaner.CleanedArtifact(
                kind=cleaner.MediaKind.IMAGE,
                payload=b"cleaned_via_custom",
                original=data,
                raster=result.cleaned,
            ),
        )

    settings = a_settings()
    image_data = b"fake_image_data"
    cleaned = cleaner.clean_artifact(
        image_data,
        cleaner.MediaKind.IMAGE,
        settings,
        render_dpi=RENDER_DPI,
        cleaners={**cleaner.CLEANERS, cleaner.MediaKind.IMAGE: custom_image_cleaner},
    )

    # FALSIFY: If branch mutant exists, custom_image_cleaner is never called
    assert len(seen) == 1, "custom IMAGE cleaner was not called (branch mutant present)"
    assert seen[0][0] == image_data, "cleaner did not receive original bytes"
    assert seen[0][1] == settings, "cleaner did not receive exact settings"
    assert seen[0][2] == RENDER_DPI, "cleaner did not receive exact render_dpi"

    # Verify the custom cleaner's result was returned (not altered)
    assert cleaned is not None
    assert cleaned.artifact is not None
    assert cleaned.artifact.payload == b"cleaned_via_custom", (
        "dispatcher altered cleaner's return value"
    )


def test_custom_pdf_cleaner_is_called_via_dispatcher() -> None:
    """Catch branch mutant for PDF kind. Same principle as IMAGE test.

    If a branch like `elif kind == MediaKind.PDF: return _clean_pdf()`
    exists, this custom cleaner is never reached.
    """
    seen: list[tuple[bytes, cleaner.CleanerSettings, int]] = []

    def custom_pdf_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        seen.append((data, settings, render_dpi))
        result = a_cleaned_doc()
        return cleaner.replace_artifact(
            result,
            cleaner.CleanedArtifact(
                kind=cleaner.MediaKind.PDF,
                payload=b"cleaned_pdf_via_custom",
                original=data,
                raster=result.cleaned,
            ),
        )

    settings = a_settings()
    pdf_data = b"%PDF-1.4fake"
    cleaned = cleaner.clean_artifact(
        pdf_data,
        cleaner.MediaKind.PDF,
        settings,
        render_dpi=RENDER_DPI,
        cleaners={**cleaner.CLEANERS, cleaner.MediaKind.PDF: custom_pdf_cleaner},
    )

    assert len(seen) == 1, "custom PDF cleaner was not called (branch mutant present)"
    assert seen[0][0] == pdf_data
    assert cleaned is not None
    assert cleaned.artifact is not None
    assert cleaned.artifact.payload == b"cleaned_pdf_via_custom"


def test_unknown_kind_error_is_no_cleaner_registered_not_undecodable() -> None:
    """Catch exception type mutations.

    If exception type changes from NoCleanerRegisteredError to
    UndecodableArtifactError, a mutant reuses the same error for both empty
    data and unknown kind, violating §ENGINE_1_INPUT_ENGINE_RULES:337 (verdict
    must be about the engine, not the document).
    """
    unknown_kind = cast(cleaner.MediaKind, "unknown_future_kind")

    with pytest.raises(cleaner.NoCleanerRegisteredError) as excinfo:
        cleaner.clean_artifact(
            b"some_data",
            unknown_kind,
            a_settings(),
            render_dpi=RENDER_DPI,
        )

    # FALSIFY: Mutant changed to UndecodableArtifactError
    assert not isinstance(excinfo.value, cleaner.UndecodableArtifactError), (
        "exception type changed to UndecodableArtifactError (mutant present)"
    )
    # Verify it's the exact right type
    assert type(excinfo.value).__name__ == "NoCleanerRegisteredError"


def test_unknown_kind_error_message_names_the_kind() -> None:
    """Catch mutant: error message generic, doesn't name the unknown kind.

    If the error message loses the kind name, a caller can't tell what was
    unsupported. A mutant that uses a generic message still raises the right
    exception but provides no diagnostic.
    """
    unknown_kind = cast(cleaner.MediaKind, "special_spreadsheet_format")

    with pytest.raises(cleaner.NoCleanerRegisteredError) as excinfo:
        cleaner.clean_artifact(
            b"data",
            unknown_kind,
            a_settings(),
            render_dpi=RENDER_DPI,
        )

    # FALSIFY: Message was replaced with generic text
    error_text = str(excinfo.value)
    assert "special_spreadsheet_format" in error_text, (
        "error message does not name the unknown kind"
    )


def test_empty_bytes_error_type_is_undecodable_not_no_cleaner_registered() -> None:
    """Catch exception type swap mutant.

    Empty data and unknown kind are different failures (document vs engine).
    A mutant that swaps exception types is a correctness bug even if both
    exceptions are raised somewhere.
    """
    settings = a_settings()

    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.clean_artifact(
            b"",
            cleaner.MediaKind.PDF,
            settings,
            render_dpi=RENDER_DPI,
        )

    # FALSIFY: Mutant changed to NoCleanerRegisteredError
    assert not isinstance(excinfo.value, cleaner.NoCleanerRegisteredError), (
        "exception type changed to NoCleanerRegisteredError (mutant present)"
    )
    assert type(excinfo.value).__name__ == "UndecodableArtifactError"


def test_empty_bytes_boundary_is_not_none_only() -> None:
    """Catch mutant: `if not data:` changed to `if data is None:`.

    Empty bytes (b"") are falsy and must be rejected. A mutant that only
    checks for None will pass b"", which then fails downstream with a
    confusing error. This test verifies the boundary.
    """
    settings = a_settings()

    # b"" is falsy; `if not b"" == True`, so it should raise
    with pytest.raises(cleaner.UndecodableArtifactError) as excinfo:
        cleaner.clean_artifact(
            b"",
            cleaner.MediaKind.IMAGE,
            settings,
            render_dpi=RENDER_DPI,
        )

    assert "nothing to clean" in str(excinfo.value).lower(), (
        "error message does not match expected boundary check"
    )


def test_render_dpi_is_passed_through_to_cleaner() -> None:
    """Catch mutant: render_dpi dropped or passed as wrong value.

    If render_dpi is removed from the call to media_cleaner, PDF renderering
    will have the wrong DPI, producing wrong geometry. This test verifies the
    exact value is passed.
    """
    seen: list[int] = []

    def recording_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        _ = data, settings  # named to satisfy the MediaCleaner protocol
        seen.append(render_dpi)
        return a_cleaned_doc()

    settings = a_settings()
    test_dpi = 299  # Unusual value to catch constant mutations

    cleaner.clean_artifact(
        b"data",
        cast(cleaner.MediaKind, "test_kind"),
        settings,
        render_dpi=test_dpi,
        cleaners={cast(cleaner.MediaKind, "test_kind"): recording_cleaner},
    )

    assert seen == [test_dpi], f"render_dpi not passed correctly: {seen}"


def test_cleaner_receives_original_bytes_unmodified() -> None:
    """Catch mutant: bytes are transformed before passing to cleaner.

    If bytes are modified (decoded, validated, checked) before dispatch,
    the cleaner receives different data than the caller provided.
    """
    seen: list[bytes] = []

    def recording_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        _ = settings, render_dpi  # named to satisfy the MediaCleaner protocol
        seen.append(data)
        return a_cleaned_doc()

    test_bytes = b"\x89PNG\r\n\x1a\n" + b"fake_png_data"

    cleaner.clean_artifact(
        test_bytes,
        cast(cleaner.MediaKind, "test_kind"),
        a_settings(),
        render_dpi=RENDER_DPI,
        cleaners={cast(cleaner.MediaKind, "test_kind"): recording_cleaner},
    )

    assert seen == [test_bytes], "bytes were modified before dispatch"


def test_cleaner_receives_exact_settings_object() -> None:
    """Catch mutant: settings are cloned or modified before passing.

    If settings are copied or modified, the cleaner gets different operating
    points than the caller specified.
    """
    seen: list[cleaner.CleanerSettings] = []

    def recording_cleaner(
        data: bytes, settings: cleaner.CleanerSettings, *, render_dpi: int
    ) -> cleaner.CleanedDocument:
        _ = data, render_dpi  # named to satisfy the MediaCleaner protocol
        seen.append(settings)
        return a_cleaned_doc()

    original_settings = a_settings()

    cleaners_dict = {cast(cleaner.MediaKind, "test_kind"): recording_cleaner}
    cleaner.clean_artifact(
        b"data",
        cast(cleaner.MediaKind, "test_kind"),
        original_settings,
        render_dpi=RENDER_DPI,
        cleaners=cleaners_dict,
    )

    assert seen[0] is original_settings, "settings object was not passed by identity"
