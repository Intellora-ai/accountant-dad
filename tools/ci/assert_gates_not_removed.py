#!/usr/bin/env python3
"""A change may ADD gates. It may never REMOVE one.

    DECLARED (this ref)  must be a superset of  EXPECTED (base branch)

This is the machine enforcement of a rule that would otherwise be prose: the
number of gates may only go up. Without it, a pull request could delete a gate
and the merge gate would simply stop expecting it — passing green while coverage
silently shrank.

Adding a gate is allowed and reported, so a new gate is visible in the log the
first time it appears.
"""

from __future__ import annotations

import sys

from expected_checks import check_names

_EXPECTED_ARGV = 3


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) != _EXPECTED_ARGV:
        raise SystemExit("usage: assert_gates_not_removed.py <base-dir> <head-dir>")

    base_dir, head_dir = args[1], args[2]
    expected = check_names(base_dir)
    declared = check_names(head_dir)

    removed = sorted(expected - declared)
    added = sorted(declared - expected)

    print(f"gates on base branch : {len(expected)}")
    print(f"gates on this ref    : {len(declared)}")

    for name in added:
        print(f"  ADDED   {name}")

    if removed:
        print()
        print("BLOCKED - this change removes gates. The number may only go up.")
        for name in removed:
            print(f"  REMOVED {name}")
        return 1

    print("no gate removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
