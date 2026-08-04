#!/usr/bin/env python3
"""A change may ADD steps. It may never REMOVE one — with one narrow exception.

Closes the hole in the job-level ratchet: a canary step or an anti-gaming
assertion could be deleted while the job count stayed identical, so every
existing check still reported "no gate removed".

The standard comes from the BASE BRANCH, which the change under judgement
cannot edit. That separation is the whole point - a PR must not be able to
rewrite the rule it is being measured against.

THE EXCEPTION, AND WHY IT HAD TO EXIST
--------------------------------------
The first version of this file said "never remove a step", full stop. That is
right about canaries and assertions and wrong about exactly one case, and the
wrong case is the one that matters most: a placeholder gate is implemented by
DELETING its `not implemented` step and putting real steps in its place.

So the rule as first written made it impossible to ever implement any of the
declared placeholder gates. It did not protect them - it froze them. A ratchet
that blocks the only direction of travel is not strict, it is stuck.

The exception is the narrowest one that unblocks that path:

    a step named exactly `not implemented` may be removed
    ONLY IF the same check gains at least one step in the same change

Both halves carry weight. Without the name restriction, any step could be
deleted by adding a decoy. Without the same-check restriction, a placeholder
could be deleted in one gate while an unrelated gate grew - laundering a
removal through someone else's work. A check must pay for its own deletion.

What this still refuses, unchanged:
  - removing a canary, an assertion, or any other named step
  - removing `not implemented` and leaving that check with nothing new
  - removing `not implemented` from check A while only check B grows
"""

from __future__ import annotations

import sys

from expected_steps import step_names

#: The one step name that may be removed, and only under the condition above.
#: Every unimplemented gate uses this exact text, so it identifies a
#: placeholder rather than a piece of enforcement. Anything else is real work.
PLACEHOLDER_STEP = "not implemented"

#: `expected_steps.step_names` emits "<check name> :: <step name>".
SEPARATOR = " :: "

_EXPECTED_ARGV = 3


def split_pair(pair: str) -> tuple[str, str]:
    """ "<check> :: <step>" -> (check, step). Partition once, from the left.

    Check names come first and none contains the separator; a STEP label could,
    so partitioning from the left keeps the check intact and leaves any stray
    separator inside the step label, where it belongs.
    """
    check, _, step = pair.partition(SEPARATOR)
    return check, step


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

    # Which checks gained at least one step. A placeholder deletion is excused
    # only inside a check that appears here.
    grew = {split_pair(name)[0] for name in added}

    blocked: list[str] = []
    upgraded: list[str] = []
    for name in removed:
        check, step = split_pair(name)
        if step == PLACEHOLDER_STEP and check in grew:
            upgraded.append(name)
        else:
            blocked.append(name)

    for name in upgraded:
        print(f"  UPGRADED {name} -> real steps replaced it in the same gate")

    if blocked:
        print()
        print("BLOCKED - this change removes gate steps. They may only be added.")
        for name in blocked:
            check, step = split_pair(name)
            print(f"  REMOVED {name}")
            if step == PLACEHOLDER_STEP:
                print(f"          {check!r} gained no step to replace it.")
        return 1

    print("no step removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
