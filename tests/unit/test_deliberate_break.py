"""DELIBERATE BREAK — proof artifact. Never merged."""

from accountant_dad._deliberate_break import add


def test_add_is_deliberately_wrong() -> None:
    assert add(2, 2) == 5
