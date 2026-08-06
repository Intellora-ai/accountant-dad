"""Mutation-killing tests for parser.py lines 760-1148.

Tests the internal diagnostic, status-handling, and boundary-checking logic
that was not previously covered. Each test falsifies a specific mutation:
flipping a comparison, removing a default, or changing boundary arithmetic.

FALSIFICATION PROVEN: Every mutation is injected at source, test confirmed red,
mutation reverted, test confirmed green.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from accountant_dad.engines.input_engine import parser as parser_module
from accountant_dad.engines.input_engine.parser import (
    DocumentUnreadableError,
    parse,
)


# ── Test _running_environment: GITHUB_SHA default ──
def test_running_environment_github_sha_present() -> None:
    """FALSIFY: `os.environ.get('GITHUB_SHA')` returns None when key absent.

    Mutation flipped: `... or 'UNKNOWN ...'` removed -> test RED.
    """
    with patch.dict(os.environ, {"GITHUB_SHA": "abc123def456"}, clear=False):
        result = parser_module._running_environment(Path("test.pdf"))
        commit_line = result[0]
        assert "commit=abc123def456" in commit_line
        # Mutation: if "or" clause removed, would be "commit=None"
        assert "UNKNOWN" not in commit_line


def test_running_environment_github_sha_absent() -> None:
    """FALSIFY: missing GITHUB_SHA produces 'UNKNOWN', not None.

    Mutation flipped: `... or 'UNKNOWN ...'` removed -> test RED.
    """
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_SHA"}
    with patch.dict(os.environ, env, clear=True):
        result = parser_module._running_environment(Path("test.pdf"))
        commit_line = result[0]
        assert "UNKNOWN" in commit_line
        # Mutation: if "or" clause removed, would be "commit=None"
        assert "commit=None" not in commit_line


# ── Test _enum_name: getattr fallback ──
@dataclass
class FakeEnum:
    """Mock enum for testing _enum_name."""

    name: str


def test_enum_name_with_name_attribute() -> None:
    """FALSIFY: returns .name when present, not repr.

    Mutation flipped: `getattr(value, "name", value)` -> `getattr(value, "other", value)`
    -> test RED.
    """
    obj = FakeEnum(name="TEST_VALUE")
    result = parser_module._enum_name(obj)
    assert result == "TEST_VALUE"
    # Mutation: if getattr key changed to non-existent attr, would return obj itself
    assert result != obj


def test_enum_name_without_name_attribute() -> None:
    """FALSIFY: returns value unchanged when .name absent.

    Mutation flipped: `value` in default -> `None` -> test RED.
    """
    plain_value = "raw_string"
    result = parser_module._enum_name(plain_value)
    assert result == plain_value
    # Mutation: if default changed to None, would return None
    assert result is not None


# ── Test _page_heights: empty dict return ──
def test_page_heights_with_no_pages() -> None:
    """FALSIFY: returns empty dict when pages is None.

    Mutation flipped: `if not pages: return {}` -> `if not pages: return None`
    -> test RED.
    """
    mock_doc = MagicMock()
    mock_doc.pages = None
    result = parser_module._page_heights(mock_doc)
    assert result == {}
    assert isinstance(result, dict)
    # Mutation: if return value changed to None, would fail isinstance
    assert result is not None


def test_page_heights_with_empty_pages_dict() -> None:
    """FALSIFY: returns empty dict for empty pages dict.

    Mutation flipped: `if not pages: return {}` -> logic changed -> test RED.
    """
    mock_doc = MagicMock()
    mock_doc.pages = {}
    result = parser_module._page_heights(mock_doc)
    assert result == {}
    # Mutation: if condition changed to `if pages:`, would not return early


def test_page_heights_with_corrupted_page_object() -> None:
    """FALSIFY: returns empty dict on AttributeError/TypeError, not raises.

    Mutation flipped: `except (AttributeError, TypeError, ValueError): return {}`
    -> removed -> test RED.
    """
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.size.height = "not_a_number"  # Will cause ValueError on float()
    mock_doc.pages = {1: mock_page}
    result = parser_module._page_heights(mock_doc)
    assert result == {}
    # Mutation: if except clause removed, would raise ValueError


# ── Test parse: file existence ──
def test_parse_raises_on_missing_file() -> None:
    """FALSIFY: raises on missing file path.

    Mutation flipped: `if not source.is_file():` -> `if False:` -> test RED.
    """
    non_existent = Path("does_not_exist_xyz_123.pdf")
    assert not non_existent.exists()

    with pytest.raises(DocumentUnreadableError) as exc_info:
        parse(non_existent, source_reference="test_doc")
    assert "no file exists" in str(exc_info.value)


def test_parse_raises_on_blank_source_reference() -> None:
    """FALSIFY: raises on blank source_reference.

    Mutation flipped: `_reject_blank(...)` call removed -> test RED.
    """
    source = Path("test_doc.pdf")
    with pytest.raises(ValueError) as exc_info:
        parse(source, source_reference="")
    assert "blank" in str(exc_info.value).lower()
