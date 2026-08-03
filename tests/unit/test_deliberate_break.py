"""DELIBERATE BREAK — proof artifact. Never merged."""

from accountant_dad._deliberate_break import add


def test_add_is_deliberately_wrong() -> None:
    # `expected` is a named binding on purpose: `== 5` inline trips ruff
    # PLR2004 (magic value), which would fail the LINT leg and prove nothing
    # about the TESTS leg. That mistake is what proof 3 actually made.
    expected = 5
    assert add(2, 2) == expected
