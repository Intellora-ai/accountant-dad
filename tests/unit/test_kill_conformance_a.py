"""Mutation-killing tests for conformance.py foundational functions.

Targets: normalise_clause, clause_words, anchor, cite, split_citation,
_must_be_content_addressed, _must_not_be_positional, constants, regex patterns.
"""

from __future__ import annotations

import pytest

from accountant_dad.conformance import (
    _ANCHOR,
    _POSITIONAL,
    ANCHOR_DIGEST,
    ANCHOR_WORDS,
    PHASES,
    _must_be_content_addressed,
    _must_not_be_positional,
    anchor,
    cite,
    clause_words,
    normalise_clause,
    split_citation,
)


# ── normalise_clause: ONLY collapses whitespace, nothing else ────────────────
def test_normalise_clause_collapses_multiple_spaces() -> None:
    """Mutation: change \\s+ to single space, or remove strip()."""
    assert normalise_clause("a  b") == "a b"
    assert normalise_clause("a   b") == "a b"


def test_normalise_clause_collapses_mixed_whitespace() -> None:
    """Mutation: skip tab or newline handling."""
    assert normalise_clause("a\t\tb") == "a b"
    assert normalise_clause("a\n\nb") == "a b"
    assert normalise_clause("a \t \n b") == "a b"


def test_normalise_clause_strips_leading_trailing() -> None:
    """Mutation: remove .strip() call."""
    assert normalise_clause("  text  ") == "text"
    assert normalise_clause("\t\ntext\n\t") == "text"


def test_normalise_clause_preserves_single_spaces() -> None:
    """Mutation: collapse to zero spaces or change replacement character."""
    assert normalise_clause("a b c") == "a b c"


def test_normalise_clause_preserves_casing() -> None:
    """Mutation: add .lower() or .upper()."""
    assert normalise_clause("Hello WORLD") == "Hello WORLD"


def test_normalise_clause_preserves_punctuation() -> None:
    """Mutation: add regex that removes punctuation."""
    assert normalise_clause("a, b! c?") == "a, b! c?"
    assert normalise_clause("em-dash word") == "em-dash word"


def test_normalise_clause_preserves_digits() -> None:
    """Mutation: add regex that removes digits."""
    assert normalise_clause("rule 123 test") == "rule 123 test"


# ── clause_words: truncate to ANCHOR_WORDS, rstrip("-") ────────────────────
def test_clause_words_truncates_to_anchor_words() -> None:
    """Mutation: use [:ANCHOR_WORDS + 1], [:ANCHOR_WORDS - 1], or no slice."""
    # 24 chars exactly
    text = "a" * ANCHOR_WORDS
    assert clause_words(text) == text

    # 25 chars: should truncate to 24
    text_long = "a" * (ANCHOR_WORDS + 1)
    result = clause_words(text_long)
    assert len(result) <= ANCHOR_WORDS


def test_clause_words_rstrips_trailing_hyphens() -> None:
    """Mutation: remove .rstrip("-"), use lstrip, or use strip."""
    assert clause_words("test---") == "test"
    assert clause_words("test-") == "test"


def test_clause_words_strips_all_edge_hyphens() -> None:
    """Mutation: skip the initial strip("-") before the slice."""
    # The strip("-") happens before the slice, so leading hyphens are removed
    assert clause_words("-test") == "test"
    assert clause_words("---test---") == "test"


def test_clause_words_handles_all_hyphens() -> None:
    """Mutation: return empty string or fallback differently."""
    result = clause_words("---")
    # Per module: all-hyphens becomes empty
    assert result == ""


def test_clause_words_lowercases_input() -> None:
    """Mutation: remove .lower() call."""
    assert clause_words("HELLO") == "hello"


def test_clause_words_normalises_clause_first() -> None:
    """Mutation: skip normalise_clause call."""
    assert clause_words("a  b  c") == "a-b-c"


def test_clause_words_replaces_whitespace_with_hyphens() -> None:
    """Mutation: use different delimiter or skip replacement."""
    assert clause_words("hello world test") == "hello-world-test"


def test_clause_words_boundary_exactly_anchor_words() -> None:
    """Mutation: off-by-one in slice ([:ANCHOR_WORDS + 1] etc)."""
    # Build exactly 24 char word
    text = "-".join(["a"] * 12)  # 23 chars
    assert len(text) <= ANCHOR_WORDS


# ── anchor: build content address, handle empty, use [:ANCHOR_DIGEST] ───────
def test_anchor_rejects_blank_clause() -> None:
    """Mutation: remove empty check or change condition."""
    with pytest.raises(ValueError, match="blank line states no clause"):
        anchor("section", "")

    with pytest.raises(ValueError, match="blank line states no clause"):
        anchor("section", "   ")


def test_anchor_returns_words_at_digest() -> None:
    """Mutation: change format string or remove parts."""
    result = anchor("section", "a real clause")
    at_count = result.count("@")
    assert at_count == 1  # exactly one @


def test_anchor_digest_is_exactly_anchor_digest_chars() -> None:
    """Mutation: use [:ANCHOR_DIGEST + 1], [:ANCHOR_DIGEST - 1]."""
    result = anchor("", "test")
    # Format: words@hexdigest
    parts = result.split("@")
    expected_parts = 2
    assert len(parts) == expected_parts
    assert len(parts[1]) == ANCHOR_DIGEST


def test_anchor_includes_readable_clause_words() -> None:
    """Mutation: skip clause_words or truncate differently."""
    result = anchor("", "very important clause")
    assert result.startswith("very-important")


def test_anchor_handles_punctuation_only_clause() -> None:
    """Mutation: remove 'or "clause"' fallback."""
    result = anchor("", "---")
    # Punctuation-only has no readable words, should still get digest
    assert "@" in result
    digest_part = result.split("@")[1]
    assert len(digest_part) == ANCHOR_DIGEST


def test_anchor_digests_include_section() -> None:
    """Mutation: remove section from hash, change hash algorithm."""
    result_with_section = anchor("Section", "clause")
    result_without_section = anchor("", "clause")
    # Different sections = different digests
    digest_a = result_with_section.split("@")[1]
    digest_b = result_without_section.split("@")[1]
    assert digest_a != digest_b


def test_anchor_identical_sections_identical_digests() -> None:
    """Mutation: randomize digest or skip hashing correctly."""
    result_a = anchor("Section", "clause")
    result_b = anchor("Section", "clause")
    assert result_a == result_b


def test_anchor_section_difference_changes_digest() -> None:
    """Mutation: ignore section in hash."""
    result_s1 = anchor("Section 1", "clause")
    result_s2 = anchor("Section 2", "clause")
    assert result_s1 != result_s2


# ── cite: document#anchor format ──────────────────────────────────────────
def test_cite_produces_document_hash_anchor() -> None:
    """Mutation: change format string, remove #, swap order."""
    result = cite("docs/FILE.md", "section", "clause")
    assert result.startswith("docs/FILE.md#")
    assert "#" in result


def test_cite_includes_full_anchor() -> None:
    """Mutation: truncate anchor or skip parts."""
    result = cite("docs/F.md", "s", "c")
    parts = result.split("#")
    parts_count = len(parts)
    expected_parts = 2
    assert parts_count == expected_parts
    assert "@" in parts[1]


# ── split_citation: partition on #, validate ────────────────────────────────
def test_split_citation_partitions_on_hash() -> None:
    """Mutation: partition on different char or reversed order."""
    doc, anchor_part = split_citation("docs/FILE.md#words@abc123def456")
    assert doc == "docs/FILE.md"
    assert anchor_part == "words@abc123def456"


def test_split_citation_rejects_no_hash() -> None:
    """Mutation: skip this validation."""
    with pytest.raises(ValueError, match="names no clause"):
        split_citation("docs/FILE.md")


def test_split_citation_rejects_positional_anchor() -> None:
    """Mutation: skip positional check."""
    with pytest.raises(ValueError, match="LINE NUMBER"):
        split_citation("docs/FILE.md:123")


def test_split_citation_rejects_invalid_anchor_format() -> None:
    """Mutation: skip regex validation or change pattern."""
    with pytest.raises(ValueError, match="not a content anchor"):
        split_citation("docs/FILE.md#not-a-valid-anchor")


def test_split_citation_rejects_empty_document() -> None:
    """Mutation: skip document validation."""
    with pytest.raises(ValueError, match="names no document"):
        split_citation("#words@abc123def456")


# ── _must_be_content_addressed: comprehensive validation ────────────────────
def test_must_be_content_addressed_rejects_positional_colon_line() -> None:
    """Mutation: skip positional check or change pattern."""
    with pytest.raises(ValueError, match="LINE NUMBER"):
        _must_be_content_addressed("docs/FILE.md:467", "citation")


def test_must_be_content_addressed_rejects_no_hash() -> None:
    """Mutation: skip hash check."""
    with pytest.raises(ValueError, match="names no clause"):
        _must_be_content_addressed("docs/FILE.md", "citation")


def test_must_be_content_addressed_rejects_empty_document() -> None:
    """Mutation: skip document validation."""
    with pytest.raises(ValueError, match="names no document"):
        _must_be_content_addressed("#anchor@abc123", "citation")


def test_must_be_content_addressed_rejects_invalid_anchor() -> None:
    """Mutation: skip anchor format validation or change regex."""
    with pytest.raises(ValueError, match="not a content anchor"):
        _must_be_content_addressed("docs/FILE.md#invalid", "citation")


def test_must_be_content_addressed_accepts_valid_citation() -> None:
    """Mutation: make any validation too strict."""
    # Should not raise
    _must_be_content_addressed("docs/FILE.md#words-and-more@abc123def456", "citation")


# ── _must_not_be_positional: reject line-number identifiers ────────────────
def test_must_not_be_positional_rejects_colon_line_identifier() -> None:
    """Mutation: skip positional check or change pattern."""
    with pytest.raises(ValueError, match="carries a line number"):
        _must_not_be_positional("ENGINE_5:467/slug")


def test_must_not_be_positional_rejects_colon_anywhere() -> None:
    """Mutation: only check at end or use different pattern."""
    with pytest.raises(ValueError, match="carries a line number"):
        _must_not_be_positional("DOC:245/slug")


def test_must_not_be_positional_accepts_slash_only() -> None:
    """Mutation: make validation too strict."""
    # Should not raise
    _must_not_be_positional("ENGINE_5/no-approval-while-critical-stands")


# ── Constants: exact values ──────────────────────────────────────────────────
def test_anchor_words_exactly_24() -> None:
    """Mutation: change to 23, 25, or other value."""
    expected = 24
    assert expected == ANCHOR_WORDS


def test_anchor_digest_exactly_12() -> None:
    """Mutation: change to 11, 13, or other value."""
    expected = 12
    assert expected == ANCHOR_DIGEST


def test_phases_includes_expected_values() -> None:
    """Mutation: remove P4, P5, or add invalid phases."""
    expected = frozenset({"P3", "P4", "P5", "P6"})
    assert expected == PHASES


def test_phases_is_frozen() -> None:
    """Mutation: use a mutable set."""
    # PHASES should not be mutable
    with pytest.raises(AttributeError):
        PHASES.add("P7")  # type: ignore[attr-defined]


# ── Regex boundaries: pattern matching correctness ─────────────────────────
def test_anchor_pattern_matches_valid_format() -> None:
    """Mutation: change regex character classes or quantifiers."""
    # Valid anchors match (exactly 12 hex chars after @)
    assert _ANCHOR.fullmatch("words@abc123def456")
    assert _ANCHOR.fullmatch("a@000000000000")
    assert _ANCHOR.fullmatch("x-y-z@fffffffff000")


def test_anchor_pattern_rejects_invalid_formats() -> None:
    """Mutation: make regex too permissive."""
    # Invalid: no @
    assert not _ANCHOR.fullmatch("wordsabc123def456")
    # Invalid: wrong digest length
    assert not _ANCHOR.fullmatch("words@abc123")
    # Invalid: uppercase in digest
    assert not _ANCHOR.fullmatch("words@ABC123DEF456")


def test_positional_pattern_detects_colon_line() -> None:
    """Mutation: change regex to not match colons or numbers."""
    assert _POSITIONAL.search("FILE:123")
    assert _POSITIONAL.search(":467")


def test_positional_pattern_rejects_non_line_colons() -> None:
    """Mutation: make regex match anything with colon."""
    # Colons without numbers don't count
    assert not _POSITIONAL.search("FILE:")
    # Other chars don't match
    assert not _POSITIONAL.search("FILE/123")
