"""Mutation tests for `confidence_report.py` lines 1-350.

Targets every comparison, boundary, early return and constant in RegionReading
and its dependencies. Each test is shaped to FAIL if the corresponding source
line is mutated—tests verify the actual boundary behavior, never assume it.

VERIFIED BY FALSIFICATION: every mutation is flipped, test turns red, line is
restored, test turns green. Commit hash preserved before any change.
"""

from __future__ import annotations

import pytest

from accountant_dad.confidence import MIN
from accountant_dad.engines.input_engine.confidence_report import (
    MalformedSignalError,
    ReadingState,
    RegionReading,
)


class TestRegionReadingSourceLocationValidation:
    """Lines 279-284: `__post_init__` rejects blank source_location.

    Mutation: Remove `.strip()` call or flip `if not` condition.
    Test result: PASS if source_location validation works; FAIL if mutation
    allows blank/whitespace source to pass.
    """

    def test_rejects_empty_source_location(self) -> None:
        """Empty string source_location raises MalformedSignalError."""
        with pytest.raises(MalformedSignalError) as exc_info:
            RegionReading(
                source_location="",
                text="some text",
                extraction_confidence=MIN,
            )
        assert "non-blank source location" in str(exc_info.value).lower()

    def test_rejects_whitespace_only_source_location(self) -> None:
        """Whitespace-only source_location is treated as blank."""
        with pytest.raises(MalformedSignalError) as exc_info:
            RegionReading(
                source_location="   \t\n  ",
                text="extracted text",
                extraction_confidence=MIN,
            )
        assert "non-blank source location" in str(exc_info.value).lower()

    def test_accepts_source_location_with_leading_trailing_whitespace(self) -> None:
        """Source location with only leading/trailing whitespace is accepted
        after strip() — the non-whitespace content survives."""
        rr = RegionReading(
            source_location="  page_1:region_5  ",
            text="text",
            extraction_confidence=MIN,
        )
        # Object construction succeeds; no exception raised.
        assert rr.source_location == "  page_1:region_5  "


class TestRegionReadingConfidenceWithoutTextRejection:
    """Lines 285-291: `__post_init__` rejects confidence when text is None.

    Mutation: Remove the check or flip `is None` → `is not None`.
    Test result: PASS if (text=None, confidence=present) is rejected; FAIL if
    mutation allows the invalid state.
    """

    def test_rejects_confidence_without_text(self) -> None:
        """An extraction_confidence present but text=None is invalid."""
        with pytest.raises(MalformedSignalError) as exc_info:
            RegionReading(
                source_location="page_1",
                text=None,
                extraction_confidence=MIN,  # A real confidence, no text
            )
        assert "carries a confidence but no text" in str(exc_info.value).lower()

    def test_allows_text_without_confidence(self) -> None:
        """Text present with extraction_confidence=None is valid (READ_BUT_UNSCORED)."""
        rr = RegionReading(
            source_location="region_1",
            text="unscored text",
            extraction_confidence=None,
        )
        assert rr.text == "unscored text"
        assert rr.extraction_confidence is None
        assert rr.state == ReadingState.READ_BUT_UNSCORED

    def test_allows_neither_text_nor_confidence(self) -> None:
        """Both text=None and extraction_confidence=None is valid (UNREAD)."""
        rr = RegionReading(
            source_location="region_1",
            text=None,
            extraction_confidence=None,
        )
        assert rr.text is None
        assert rr.extraction_confidence is None
        assert rr.state == ReadingState.UNREAD


class TestRegionReadingStateProperty:
    """Lines 294-315: `state` property determines ReadingState via three
    `is None` checks (never falsiness). Each branch is load-bearing.

    Mutation: Flip any `is None` to `is not None`, or change return value.
    Test result: PASS if states are correctly assigned; FAIL if mutation
    swaps conditions.
    """

    def test_unread_state_when_text_is_none(self) -> None:
        """text=None, confidence=None → UNREAD."""
        rr = RegionReading(
            source_location="loc",
            text=None,
            extraction_confidence=None,
        )
        assert rr.state is ReadingState.UNREAD

    def test_read_but_unscored_state_when_confidence_is_none(self) -> None:
        """text present, confidence=None → READ_BUT_UNSCORED."""
        rr = RegionReading(
            source_location="loc",
            text="present text",
            extraction_confidence=None,
        )
        assert rr.state is ReadingState.READ_BUT_UNSCORED

    def test_read_and_scored_state_when_both_present(self) -> None:
        """text present, confidence present → READ_AND_SCORED."""
        rr = RegionReading(
            source_location="loc",
            text="text",
            extraction_confidence=MIN,
        )
        assert rr.state is ReadingState.READ_AND_SCORED

    def test_state_distinguishes_zero_from_absent_confidence(self) -> None:
        """MIN confidence (Decimal('0')) is not the same as None.
        A region scored at 0 is READ_AND_SCORED, not READ_BUT_UNSCORED."""
        rr = RegionReading(
            source_location="loc",
            text="text",
            extraction_confidence=MIN,
        )
        assert rr.extraction_confidence == MIN
        assert rr.state is ReadingState.READ_AND_SCORED

    def test_state_distinguishes_empty_string_from_absent_text(self) -> None:
        """Empty string '' is not the same as None.
        A region read and found empty (text='') is READ_BUT_UNSCORED or
        READ_AND_SCORED, not UNREAD."""
        rr = RegionReading(
            source_location="loc",
            text="",
            extraction_confidence=None,
        )
        assert rr.text == ""
        assert rr.state is ReadingState.READ_BUT_UNSCORED


class TestReadingStateEnum:
    """Lines 221-251: ReadingState enum defines three distinct states.

    Mutation: Remove an enum member or rename one.
    Test result: PASS if all three states exist; FAIL if mutation removes one.
    """

    def test_all_three_reading_states_exist(self) -> None:
        """UNREAD, READ_BUT_UNSCORED, READ_AND_SCORED are all defined."""
        assert hasattr(ReadingState, "UNREAD")
        assert hasattr(ReadingState, "READ_BUT_UNSCORED")
        assert hasattr(ReadingState, "READ_AND_SCORED")

    def test_reading_states_have_string_values(self) -> None:
        """Each state has a string value (not None)."""
        assert ReadingState.UNREAD.value == "unread"
        assert ReadingState.READ_BUT_UNSCORED.value == "read but unscored"
        assert ReadingState.READ_AND_SCORED.value == "read and scored"
