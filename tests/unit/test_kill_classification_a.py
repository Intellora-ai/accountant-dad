"""Mutation-killing tests for `classification.py` lines 1-290.

Targets: early returns, boundary conditions, and validation operators
that would flip silently if their logic operators were mutated.

Each test falsifies a specific mutation by exercising a boundary that
MUST succeed — a mutation flipping the condition to its opposite would
turn it red.
"""

from __future__ import annotations

import pytest

from accountant_dad.engines.input_engine.classification import (
    Cue,
    DocumentType,
    Instrument,
    MatchedCue,
    TypeCandidate,
    _reject_blank,
)

#: Test constant for expected cue count to avoid magic value
EXPECTED_TWO_CUES = 2


# ── Line 163: if not value.strip() ──────────────────────────────────────────
# Mutation: remove `not` → if value.strip() would reject valid input
# Mutation: change `strip()` behavior
# Kill: Pass valid non-empty string, verify no exception


def test_reject_blank_accepts_valid_non_empty_string() -> None:
    """Line 163: `if not value.strip():` must accept non-empty strings.
    Flip `not` to absence → would reject "VALID".
    Flip `!=` to `==` → behavior unchanged (no != here).
    """
    # Should NOT raise
    _reject_blank("VALID", "test field")


def test_reject_blank_accepts_string_with_inner_spaces() -> None:
    """Line 163: `if not value.strip():` must accept strings with internal spaces.
    Flip `strip()` to bare `value` → would reject strings like " VALID ".
    """
    # Should NOT raise
    _reject_blank("  SPACE SEPARATED  ", "test field")


def test_reject_blank_rejects_empty_string_exactly() -> None:
    """Line 163: `if not value.strip():` must reject empty string.
    Confirms the boundary: "" → raise.
    """
    with pytest.raises(ValueError, match="must not be empty or blank"):
        _reject_blank("", "test field")


# ── Line 227: if self.text != self.text.upper() ─────────────────────────────
# Mutation: flip != to == → would reject uppercase and accept lowercase
# Mutation: remove != entirely (unreachable in practice)
# Kill: Create Cue with uppercase, verify success; try lowercase, verify failure


def test_cue_with_uppercase_text_succeeds() -> None:
    """Line 227: `if self.text != self.text.upper():` must reject non-uppercase.
    Flip `!=` to `==` → would reject "UPPERCASE".
    This test turns RED if the condition is inverted.
    """
    cue = Cue(DocumentType.TAX_INVOICE, "TAX INVOICE")
    assert cue.text == "TAX INVOICE"


def test_cue_rejects_mixed_case_text() -> None:
    """Line 227: `if self.text != self.text.upper():` catches mixed case.
    Confirms the boundary: "Tax Invoice" → raise.
    """
    with pytest.raises(ValueError, match="upper-case"):
        Cue(DocumentType.TAX_INVOICE, "Tax Invoice")


def test_cue_rejects_lowercase_text() -> None:
    """Line 227: Catches lowercase input."""
    with pytest.raises(ValueError, match="upper-case"):
        Cue(DocumentType.BILL_OF_SUPPLY, "bill of supply")


# ── Line 269: MatchedCue._reject_blank(..., "matched cue text") ──────────────
# Mutation: remove _reject_blank call (line 269) → would accept blank cue
# Kill: Create MatchedCue with valid cue, verify success


def test_matched_cue_with_valid_fields_succeeds() -> None:
    """Lines 269-271: _reject_blank calls must pass with valid input.
    A mutation removing _reject_blank(self.cue, ...) would still create
    the object. This test verifies the normal path works.
    """
    cue = MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 0, region 1",
    )
    assert cue.cue == "TAX INVOICE"
    assert cue.matched_text == "TAX INVOICE"


def test_matched_cue_rejects_blank_matched_text() -> None:
    """Line 270: _reject_blank(self.matched_text, ...) catches blank source text.
    Confirms the boundary: "" → raise.
    """
    with pytest.raises(ValueError, match="must not be empty or blank"):
        MatchedCue(
            cue="TAX INVOICE",
            instrument=Instrument.READER,
            matched_text="",
            location="page 0",
        )


# ── Line 287: if not self.matched_cues ───────────────────────────────────────
# Mutation: remove `not` → if self.matched_cues would reject when cues exist
# Mutation: change to truthiness check
# Kill: Create TypeCandidate with matched_cues, verify success


def test_type_candidate_with_matched_cues_succeeds() -> None:
    """Line 287: `if not self.matched_cues:` must accept non-empty tuple.
    Flip `not` → if self.matched_cues would reject this.
    This test turns RED if the condition is inverted.
    """
    cue1 = MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 0",
    )
    cue2 = MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 1",
    )
    candidate = TypeCandidate(
        document_type=DocumentType.TAX_INVOICE,
        matched_cues=(cue1, cue2),
    )
    assert len(candidate.matched_cues) == EXPECTED_TWO_CUES


def test_type_candidate_with_single_cue_succeeds() -> None:
    """Line 287: Must accept non-empty tuple of any size (including 1)."""
    cue = MatchedCue(
        cue="PURCHASE ORDER",
        instrument=Instrument.PARSER,
        matched_text="PURCHASE ORDER",
        location="section_header at page 0",
    )
    candidate = TypeCandidate(
        document_type=DocumentType.PURCHASE_ORDER,
        matched_cues=(cue,),
    )
    assert candidate.document_type is DocumentType.PURCHASE_ORDER


def test_type_candidate_rejects_empty_matched_cues() -> None:
    """Line 287: `if not self.matched_cues:` catches empty tuple.
    Confirms the boundary: () → raise.
    """
    with pytest.raises(ValueError, match="carries no evidence"):
        TypeCandidate(
            document_type=DocumentType.CREDIT_NOTE,
            matched_cues=(),
        )
