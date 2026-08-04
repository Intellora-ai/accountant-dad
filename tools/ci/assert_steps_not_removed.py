#!/usr/bin/env python3
"""A change may ADD steps. It may never REMOVE one.

Closes the hole in the job-level ratchet: a canary step or an anti-gaming
assertion could be deleted while the job count stayed identical, so every
existing check still reported "no gate removed".

The standard comes from the BASE BRANCH, which the change under judgement
cannot edit. That separation is the whole point - a PR must not be able to
rewrite the rule it is being measured against.
"""

from __future__ import annotations

import sys

from expected_steps import step_names

_EXPECTED_ARGV = 3


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) != _EXPECTED_ARGV:
        raise SystemExit("usage: assert_steps_not_removed.py <base-dir> <head-dir>")

    expected = step_names(args[1])
    declared = step_names(args[2])

    removed = sorted(expected - declared)
    added = sorted(declared - expected)

    print(f"steps on base branch : {len(expected)}")
    print(f"steps on this ref    : {len(declared)}")
    for name in added:
        print(f"  ADDED   {name}")

    if removed:
        print()
        print("BLOCKED - this change removes gate steps. They may only be added.")
        for name in removed:
            print(f"  REMOVED {name}")
        return 1

    print("no step removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
