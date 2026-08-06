"""The engineering method is enforced by the REPOSITORY, not by a home directory.

── WHAT THIS FILE EXISTS TO STOP, MEASURED 2026-08-06 ──

`.gitignore:50` ignored `.claude/` wholesale. Measured:

    git ls-files .claude/   ->   (empty)

Every hook enforcing this project's engineering rules lived in `~/.claude/` on
one laptop. A fresh clone, a second machine, or a wiped home directory got
**zero** enforcement. The rules survived only because one home directory
happened to still exist.

That is the real reason "CLAUDE.md is not enough" — not that the document is
weak, but that nothing in the repository read it, and nothing in the repository
could tell you that nothing read it.

── WHY A TEST AND NOT JUST THE HOOK ──

A hook that is registered today can be unregistered tomorrow by one edit to a
JSON file nobody reads in review. These assertions make that edit RED. The
enforcement mechanism is itself now under the same rule it enforces: a claim
that is not checked is not evidence.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPOSITORY = pathlib.Path(__file__).resolve().parents[2]
SETTINGS = REPOSITORY / ".claude" / "settings.json"
HOOK = REPOSITORY / ".claude" / "hooks" / "engineering_method.py"

#: Only these three can carry the method. `Stop` runs after a turn is over and
#: cannot shape the work it follows, so it is deliberately not required here.
REQUIRED_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse")

#: A document read later AS EVIDENCE. A false claim in one of these is the
#: failure this whole mechanism exists to prevent.
A_TRUTH_DOCUMENT = "KNOWN_FAILURES.md"

#: `PreToolUse` refuses a tool call by exiting non-zero. 2 is what the hook
#: returns; the assertion is on "non-zero" so the exact code is free to change.
REFUSED = 0


def _run(argv: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    """The ONE subprocess site in this file, so there is ONE thing to justify.

    Three call sites would need three suppressions and would each have to argue
    the same point. Every `argv` below is built from `sys.executable`, an
    absolute path resolved by `shutil.which`, and literals in this file — no
    shell, no interpolation, nothing read from outside the test.
    """
    return subprocess.run(  # noqa: S603 - fixed argv, absolute paths, no shell
        argv, input=stdin, capture_output=True, text=True, check=False, cwd=REPOSITORY
    )


def git(*arguments: str) -> list[str]:
    """`git` by ABSOLUTE path, resolved rather than trusted to `PATH`.

    A partial executable name resolves against whatever `PATH` happens to hold,
    which is precisely the class of thing this repository refuses to assume.
    """
    executable = shutil.which("git")
    assert executable is not None, "git is not installed; this test cannot run"
    return _run([executable, *arguments]).stdout.split()


def run_hook(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(HOOK)], stdin=json.dumps(payload))


def test_the_hook_is_in_the_repository_not_in_a_home_directory() -> None:
    """The single point of failure that was measured, asserted away.

    `git ls-files` rather than `Path.exists()`: a file present on this disk and
    absent from the repository is exactly the state that produced the defect,
    and only the first of those two checks can tell them apart.
    """
    tracked = git("ls-files", ".claude/")

    assert ".claude/hooks/engineering_method.py" in tracked, (
        "the enforcement hook is not tracked by git. A fresh clone would carry "
        "no enforcement at all, which is the exact failure measured on "
        "2026-08-06 when `git ls-files .claude/` returned nothing."
    )
    assert ".claude/settings.json" in tracked, (
        "the hook registration is not tracked by git, so nothing in a fresh "
        "clone would ever run the hook."
    )


def test_no_worktree_or_local_state_was_committed_by_the_un_ignore() -> None:
    """The un-ignore had to be surgical, and this proves it stayed surgical.

    `.claude/worktrees/` holds agent worktrees — gigabytes of checkouts. An
    un-ignore of `.claude/` wholesale would commit them. Only `settings.json`
    and `hooks/` may be tracked.
    """
    tracked = git("ls-files", ".claude/")

    strays = sorted(
        path
        for path in tracked
        if not path.startswith(".claude/hooks/") and path != ".claude/settings.json"
    )
    assert strays == [], (
        f"local state was committed by the .gitignore un-ignore: {strays}. "
        "Only the enforcement mechanism belongs in the repository."
    )


@pytest.mark.parametrize("event", REQUIRED_EVENTS)
def test_every_event_that_can_carry_the_method_is_registered(event: str) -> None:
    """Registration is the part one careless JSON edit removes."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    commands = [
        hook.get("command", "")
        for entry in settings.get("hooks", {}).get(event, [])
        for hook in entry.get("hooks", [])
    ]
    assert any("engineering_method.py" in command for command in commands), (
        f"{event} does not run the engineering-method hook. Redundancy is the "
        f"point: each event is an independent surface, and losing one must not "
        f"silently disable enforcement."
    )


def test_the_hook_refuses_an_unmeasured_claim_in_a_truth_document() -> None:
    """THE ONLY BINDING ASSERTION IN THE WHOLE MECHANISM.

    `PreToolUse` is the one event that can refuse a tool call — measured, not
    assumed: the Law 56 metrics hook refused a `Write` in this repository and
    the write did not land.

    A guard never observed refusing is unproven, so this observes it refusing.
    """
    result = run_hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_input": {
                "file_path": f"/anywhere/{A_TRUTH_DOCUMENT}",
                "content": "This should work now.",
            },
        }
    )
    assert result.returncode != REFUSED, (
        "a hedge was written into a document that is read later as evidence, "
        "and the hook permitted it. Two of three testable claims in "
        f"{A_TRUTH_DOCUMENT} were FALSE on 2026-08-06 and one was carried into "
        "a root-cause analysis as if verified."
    )
    assert "BLOCKED" in result.stderr


def test_the_hook_permits_a_measured_statement_in_the_same_document() -> None:
    """The other direction, without which the guard is just a word filter.

    A check that refused everything would be as useless as one that refused
    nothing, and would be removed within a day for getting in the way.
    """
    result = run_hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_input": {
                "file_path": f"/anywhere/{A_TRUTH_DOCUMENT}",
                "content": "Measured: 14 failures in 400 pairs @ commit 3bd31e2.",
            },
        }
    )
    assert result.returncode == REFUSED, (
        f"a measured statement was refused: {result.stderr}. The guard must "
        "cost nothing to write the truth, or it will be removed."
    )


def test_the_hook_leaves_ordinary_files_alone() -> None:
    """Scope. The rule is about documents trusted as evidence, not about prose.

    Applying it everywhere would fire on source comments and commit messages
    and train the reader to ignore the block — which destroys the only binding
    enforcement that exists.
    """
    result = run_hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_input": {"file_path": "/anywhere/notes.txt", "content": "I think so."},
        }
    )
    assert result.returncode == REFUSED


@pytest.mark.parametrize("event", ("SessionStart", "UserPromptSubmit"))
def test_the_advisory_events_emit_the_method(event: str) -> None:
    result = run_hook({"hook_event_name": event})
    assert "ENGINEERING METHOD" in result.stdout
    assert "MEASURE" in result.stdout
    assert result.returncode == REFUSED, "an advisory event must never block a turn"
