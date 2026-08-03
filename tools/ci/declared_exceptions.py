#!/usr/bin/env python3
"""Parse the declared-placeholder-gates file and enforce its three ratchets.

`merge gate` cannot distinguish a gate that examined something and rejected it
from a gate that had nothing to examine. Both surface as a red check run. That
conflation is why the merge gate could never pass, could therefore never be a
required check, and therefore bound nothing.

This module supplies the missing distinction, and refuses to supply it cheaply:

  UNKNOWN PLACEHOLDERS ARE FORBIDDEN
      Every entry carries an id, an owner, a milestone, a removal condition and
      a blocker. A line missing any field is a parse error, never a lenient
      default, because the lenient direction is the one that excuses a real
      failure.

  CANNOT EXECUTE
      Enforced, not promised. A declared gate's job must contain exactly one
      `run:` step whose script ends in `exit 1`. A "placeholder" that actually
      runs something could emit a pass, and would then be excused into the
      bargain.

  SHRINK-ONLY
      A name may be deleted, never added. Deleting is how a gate becomes
      binding: a commit, in a diff, reviewable, versioned.

The merge gate reads the BASE branch's copy, so a pull request cannot excuse the
gate it just broke.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

import yaml

_FIELDS_PER_LINE = 6
_EXPECTED_ARGV_RATCHET = 3
_EXPECTED_ARGV_EXECUTE = 3
_EXPECTED_ARGV_CANNOT_EXECUTE = 4
_USAGE = (
    "usage: declared_exceptions.py <base-file> <head-file>\n"
    "   or: declared_exceptions.py --cannot-execute <workflows-dir> <declared-file>"
)


class Declared(NamedTuple):
    """One declared placeholder gate. Every field is mandatory."""

    id: str
    owner: str
    milestone: str
    removal_condition: str
    blocker: str


def parse(path: str) -> dict[str, Declared]:
    """Every declared placeholder gate, keyed by its Check Run name.

    Raises SystemExit on any malformed line, duplicate name or duplicate id.
    """
    file = Path(path)
    if not file.is_file():
        raise SystemExit(f"declared-exceptions file not found: {path}")

    declared: dict[str, Declared] = {}
    seen_ids: dict[str, str] = {}

    for number, raw in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = [field.strip() for field in line.split("|")]
        if len(parts) != _FIELDS_PER_LINE:
            raise SystemExit(
                f"{path}:{number}: expected six fields "
                f"'<id> | <check> | <owner> | <milestone> | <removal> | <blocker>', "
                f"got {len(parts)} in {line!r}"
            )

        identifier, name, owner, milestone, removal, blocker = parts
        if not all(parts):
            raise SystemExit(f"{path}:{number}: empty field in {line!r}")
        if name in declared:
            raise SystemExit(f"{path}:{number}: duplicate check name {name!r}")
        if identifier in seen_ids:
            raise SystemExit(
                f"{path}:{number}: id {identifier!r} already used by {seen_ids[identifier]!r}"
            )

        seen_ids[identifier] = name
        declared[name] = Declared(identifier, owner, milestone, removal, blocker)

    return declared


def assert_cannot_execute(workflows_dir: str, declared: dict[str, Declared]) -> int:
    """A declared gate's job must be incapable of doing anything.

    Exactly one `run:` step, whose script ends in `exit 1`. `uses:` steps
    (checkout, setup) are allowed and ignored.

    Without this, "placeholder" is a claim rather than a property: a job could
    be declared red-by-design and still execute product code, and any pass it
    emitted would be excused rather than examined.
    """
    root = Path(workflows_dir)
    offenders: list[str] = []
    found: set[str] = set()

    for path in sorted([*root.glob("*.yml"), *root.glob("*.yaml")]):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            continue

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            name = job.get("name", job_id)
            if name not in declared:
                continue

            found.add(name)
            steps = job.get("steps", [])
            runs = [s for s in steps if isinstance(s, dict) and "run" in s]

            if len(runs) != 1:
                offenders.append(f"  {name}: has {len(runs)} run steps, expected exactly 1")
                continue
            script = str(runs[0]["run"]).strip()
            if not script.endswith("exit 1"):
                offenders.append(f"  {name}: run step does not end in 'exit 1'")

    missing = sorted(set(declared) - found)
    for name in missing:
        offenders.append(f"  {name}: declared, but no job in {workflows_dir} produces it")

    if offenders:
        print("BLOCKED - a declared placeholder is capable of executing")
        for line in offenders:
            print(line)
        print()
        print("A declared gate must contain exactly one run step ending in 'exit 1'.")
        print("Anything else could emit a pass, which this list would then excuse.")
        return 1

    print(f"all {len(declared)} declared gates are exit-1-only and cannot execute")
    return 0


def assert_shrink_only(base_path: str, head_path: str) -> int:
    """The pull request's declared set must be a subset of the base branch's.

    Adding a name would let a pull request excuse a gate it just broke. Removing
    one is promotion and is always allowed.

    BOOTSTRAP: if the base branch has no copy at all, this is the pull request
    that introduces the mechanism. There is nothing to compare against, so the
    comparison is skipped and said out loud. This can only ever happen once:
    afterwards the file is on the base branch, and a pull request deleting it
    fails at `parse` instead.
    """
    if not Path(base_path).is_file():
        bootstrap = parse(head_path)
        print("BOOTSTRAP - the base branch has no declared-exceptions file")
        print(f"  this ref declares {len(bootstrap)} gates")
        print("  nothing to compare against; the shrink-only ratchet starts at the")
        print("  next pull request, once this file exists on the base branch.")
        return 0

    base = set(parse(base_path))
    head = set(parse(head_path))

    added = sorted(head - base)
    removed = sorted(base - head)

    print(f"declared on base branch : {len(base)}")
    print(f"declared on this ref    : {len(head)}")

    for name in removed:
        print(f"  PROMOTED  {name}  (no longer excused - it must now pass)")

    if added:
        print()
        print("BLOCKED - the declared-exceptions list may only shrink")
        for name in added:
            print(f"  ADDED {name}")
        print()
        print("A gate that can run and does not pass is a real failure.")
        print("Excusing it here would silence the thing the gate exists to catch.")
        return 1

    print("no gate was newly excused")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == _EXPECTED_ARGV_EXECUTE and argv[1] == "--cannot-execute":
        raise SystemExit(_USAGE)
    if len(argv) == _EXPECTED_ARGV_RATCHET:
        return assert_shrink_only(argv[1], argv[2])
    if len(argv) == _EXPECTED_ARGV_CANNOT_EXECUTE and argv[1] == "--cannot-execute":
        return assert_cannot_execute(argv[2], parse(argv[3]))
    raise SystemExit(_USAGE)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
