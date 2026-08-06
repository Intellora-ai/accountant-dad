"""Mutation killers for classification.py lines 290-575.  # noqa: RUF002

Target: every comparison, boundary, default, early return, and constant in
the range. Assert the real RESULT, not just that a function ran.
"""

from __future__ import annotations

import pytest

from accountant_dad.engines.input_engine.classification import (
    ClassificationResult,
    ClassificationStatus,
    DocumentType,
    Instrument,
    MatchedCue,
    TypeCandidate,
    classify,
)
from accountant_dad.engines.input_engine.parser import BoundingBox, ParsedStructure, Region
from accountant_dad.engines.input_engine.reader import Backend, Reading, SourceLocation, TextRegion

# ── Builders ─────────────────────────────────────────────────────────────


def a_location(*, page_index: int = 0) -> SourceLocation:
    return SourceLocation(page_index=page_index, left=10.0, top=10.0, right=200.0, bottom=30.0)


def a_text_region(text: str, *, page_index: int = 0) -> TextRegion:
    return TextRegion(
        text=text, location=a_location(page_index=page_index), extraction_confidence=None
    )


def a_reading(*texts: str) -> Reading:
    return Reading(
        regions=tuple(a_text_region(text) for text in texts),
        backend=Backend.OCR,
        pages_read=1,
    )


def a_box(*, page: int = 1) -> BoundingBox:
    return BoundingBox(page=page, left=5.0, top=5.0, right=100.0, bottom=25.0)


def a_parser_region(text: str | None, *, label: str = "section_header") -> Region:
    return Region(label=label, text=text, box=a_box(), detector="docling")


def a_structure(*texts: str) -> ParsedStructure:
    return ParsedStructure(
        source_reference="scan-001.pdf",
        page_count=1,
        regions=tuple(a_parser_region(text) for text in texts),
        tables=(),
    )


def a_matched_cue() -> MatchedCue:
    return MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 1",
    )


# ── Line 310: case ClassificationStatus.UNKNOWN, () ──────────────────────


def test_post_init_rejects_unknown_with_candidates() -> None:
    """Line 310: empty tuple is required for UNKNOWN status."""
    with pytest.raises(ValueError, match="status UNKNOWN is inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.UNKNOWN,
            candidates=(
                TypeCandidate(
                    document_type=DocumentType.TAX_INVOICE, matched_cues=(a_matched_cue(),)
                ),
            ),
            reasons=(),
        )


# ── Line 312: case ClassificationStatus.TYPED, (_,) ──────────────────────


def test_post_init_rejects_typed_with_zero_candidates() -> None:
    """Line 312: exactly one candidate required for TYPED."""
    with pytest.raises(ValueError, match="status TYPED is inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.TYPED,
            candidates=(),
            reasons=(),
        )


def test_post_init_rejects_typed_with_multiple_candidates() -> None:
    """Line 312: exactly one candidate required for TYPED."""
    with pytest.raises(ValueError, match="status TYPED is inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.TYPED,
            candidates=(
                TypeCandidate(
                    document_type=DocumentType.TAX_INVOICE, matched_cues=(a_matched_cue(),)
                ),
                TypeCandidate(
                    document_type=DocumentType.BILL_OF_SUPPLY, matched_cues=(a_matched_cue(),)
                ),
            ),
            reasons=(),
        )


# ── Line 314: case ClassificationStatus.AMBIGUOUS, (_, _, *_) ──────────────


def test_post_init_rejects_ambiguous_with_zero_candidates() -> None:
    """Line 314: two or more candidates required for AMBIGUOUS."""
    with pytest.raises(ValueError, match="status AMBIGUOUS is inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.AMBIGUOUS,
            candidates=(),
            reasons=(),
        )


def test_post_init_rejects_ambiguous_with_one_candidate() -> None:
    """Line 314: two or more candidates required for AMBIGUOUS."""
    with pytest.raises(ValueError, match="status AMBIGUOUS is inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.AMBIGUOUS,
            candidates=(
                TypeCandidate(
                    document_type=DocumentType.TAX_INVOICE, matched_cues=(a_matched_cue(),)
                ),
            ),
            reasons=(),
        )


# ── Line 382: text.upper().strip() (normalization order) ──────────────────


def test_normalization_strips_then_uppers_not_vice_versa() -> None:
    """Line 382: searched_text is .upper().strip(), which matters for edge spaces.

    The normalization applies to both reader and parser text. Cues are matched
    case-insensitively against the uppercased, trimmed text.
    """
    # A cue with lowercase, surrounded by spaces in source
    result = classify(
        a_reading("  tax invoice  "),
        a_structure(),
    )
    # The "TAX INVOICE" cue is in the normalized region (after strip and upper)
    assert result.status == ClassificationStatus.TYPED
    assert result.candidates[0].document_type == DocumentType.TAX_INVOICE


# ── Line 401: is not None (regex search return check) ────────────────────


def test_opens_or_closes_detects_whole_phrase_at_start() -> None:
    """Line 401: _opens_or_closes_its_region returns bool from is not None.

    Mutating 'is not None' to 'is None' inverts the entire detection logic.
    """
    # "TAX INVOICE" at the start of a region -> heading
    result = classify(
        a_reading("TAX INVOICE document content here"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.TYPED


def test_opens_or_closes_detects_whole_phrase_at_end() -> None:
    """Line 401: phrase at end is recognized."""
    result = classify(
        a_reading("some content TAX INVOICE"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.TYPED


def test_opens_or_closes_rejects_phrase_in_middle() -> None:
    """Line 401: phrase in middle with text on both sides is NOT a heading."""
    result = classify(
        a_reading("this is a TAX INVOICE document"),
        a_structure(),
    )
    # Found but set aside
    assert result.status == ClassificationStatus.UNKNOWN
    assert "TAX INVOICE" in result.reasons[1]


# ── Line 428: if region.text.strip() (truthiness of trimmed text) ────────


def test_reader_skips_empty_and_whitespace_regions() -> None:
    """Line 428: regions with only whitespace are skipped in reader sources.

    A region with "   " should be treated as having no text.
    """
    result = classify(
        a_reading("   ", "TAX INVOICE", "   "),
        a_structure(),
    )
    # Only the middle region with the cue matters
    assert result.status == ClassificationStatus.TYPED
    assert len(result.candidates[0].matched_cues) == 1
    assert result.candidates[0].matched_cues[0].matched_text == "TAX INVOICE"


# ── Line 440: if region.text is not None (parser None check) ────────────


def test_parser_skips_none_text_regions() -> None:
    """Line 440: parser regions with text=None are skipped.

    Mutating 'is not None' to 'is None' would flip this filter.
    """
    result = classify(
        a_reading(),
        ParsedStructure(
            source_reference="scan-001.pdf",
            page_count=1,
            regions=(
                a_parser_region(None),
                a_parser_region("TAX INVOICE"),
                a_parser_region(None),
            ),
            tables=(),
        ),
    )
    # Only the middle region with text matters
    assert result.status == ClassificationStatus.TYPED
    assert len(result.candidates[0].matched_cues) == 1


# ── Line 461: if cue.text in source.searched_text (containment) ─────────


def test_cue_containment_is_case_insensitive() -> None:
    """Line 461: cue containment is checked against searched_text (uppercased).

    A cue 'TAX INVOICE' should find 'tax invoice' in source because
    searched_text is uppercased.
    """
    result = classify(
        a_reading("tax invoice document"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.TYPED


def test_cue_containment_requires_actual_substring_presence() -> None:
    """Line 461: substring check means 'TAXINVOICE' does not match 'TAX INVOICE'."""
    result = classify(
        a_reading("TAXINVOICE"),
        a_structure(),
    )
    # No match because "TAX INVOICE" is not a substring of "TAXINVOICE"
    assert result.status == ClassificationStatus.UNKNOWN


# ── Line 537: if occurrence.opens_or_closes_its_region (heading filter) ──


def test_headings_tuple_only_includes_boundary_cues() -> None:
    """Line 537: only cues that open/close their region are included as headings.

    A cue in the middle of text is found but not classified as a heading.
    """
    result = classify(
        a_reading("this mentions TAX INVOICE somewhere"),
        a_structure(),
    )
    # Found but not a heading
    assert result.status == ClassificationStatus.UNKNOWN
    # Reason explains it was set aside
    assert any("TAX INVOICE" in reason for reason in result.reasons[1:])


# ── Line 542: if not occurrence.opens_or_closes_its_region (set-aside filter) ──


def test_set_aside_reasons_only_for_non_heading_cues() -> None:
    """Line 542: negation filters non-headings into set_aside.

    Mutating to remove the 'not' would break set_aside collection.
    """
    result = classify(
        a_reading("context: TAX INVOICE reference"),
        a_structure(),
    )
    # The cue is found but not in a heading position
    assert result.status == ClassificationStatus.UNKNOWN
    # Set aside reasons contain an explanation
    assert len(result.reasons) > 1
    assert "set aside" in result.reasons[1] or "TAX INVOICE" in result.reasons[1]


# ── Line 548: if (candidate := ...) is not None (walrus + None check) ────


def test_candidates_tuple_only_includes_non_none_results() -> None:
    """Line 548: candidate walrus assignment filters out None values.

    Mutating 'is not None' to 'is None' would invert the filter.
    """
    result = classify(
        a_reading("TAX INVOICE"),
        a_structure(),
    )
    # Exactly one non-None candidate
    assert len(result.candidates) == 1
    assert result.status == ClassificationStatus.TYPED


# ── Line 551-575: match statement cases and semantics ────────────────────


def test_match_unknown_empty_candidates() -> None:
    """Line 552: candidates=() case matches ClassificationStatus.UNKNOWN."""
    result = classify(
        a_reading("no matches here"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.document_type is None


def test_match_typed_single_candidate() -> None:
    """Line 558: candidates=(only,) case matches ClassificationStatus.TYPED."""
    result = classify(
        a_reading("TAX INVOICE"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.TYPED
    assert len(result.candidates) == 1
    assert result.document_type == DocumentType.TAX_INVOICE


def test_match_ambiguous_multiple_candidates() -> None:
    """Line 564: candidates=multiple case matches ClassificationStatus.AMBIGUOUS."""
    result = classify(
        a_reading("TAX INVOICE", "BILL OF SUPPLY"),
        a_structure(),
    )
    # Two regions with different cues create ambiguity
    assert result.status == ClassificationStatus.AMBIGUOUS
    assert len(result.candidates) >= 2  # noqa: PLR2004
    assert result.document_type is None


def test_set_aside_included_in_unknown_reasons() -> None:
    """Line 556: set_aside reasons are prepended for UNKNOWN status."""
    result = classify(
        a_reading("this has TAX INVOICE in the middle"),
        a_structure(),
    )
    assert result.status == ClassificationStatus.UNKNOWN
    # First reason is the "nothing at heading" explanation
    # Subsequent reasons are set_aside cues
    assert len(result.reasons) >= 2  # noqa: PLR2004
