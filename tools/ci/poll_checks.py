#!/usr/bin/env python3
"""Wait for every declared gate to finish, then assert all of them succeeded.

Only `success` passes. `failure`, `cancelled`, `skipped`, `timed_out`, `neutral`,
`action_required` and `stale` all fail, and so does a check that never appeared.

The explicit rejection of `skipped` is deliberate and is NOT redundant. GitHub
treats a skipped job as satisfying a required check, so a skipped gate would
otherwise merge a failed pipeline. No gate job declares `needs:` or `if:`, and no
gate workflow has a path filter, so nothing should ever be skipped — this rejects
it anyway rather than trusting that invariant holds forever.

Absence is failure too: the poll loop only exits once every expected gate is
present and completed, so a gate that never reports fails as a timeout.

Every value read from the API is narrowed before use. The response is untrusted
input, and a malformed field must not be able to turn a red gate green.

Reads only. No token scope beyond `checks: read` is required or requested.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping

from declared_exceptions import Declared
from declared_exceptions import parse as parse_declared
from expected_checks import check_names

CONCLUSION_SUCCESS = "success"
_MAX_NAMES_IN_PROGRESS_LINE = 5
API_ROOT = "https://api.github.com"

CheckRun = dict[str, object]


def _text(run: CheckRun, key: str) -> str | None:
    value = run.get(key)
    return value if isinstance(value, str) else None


def _identifier(run: CheckRun) -> int:
    value = run.get("id")
    return value if isinstance(value, int) else 0


def fetch_check_runs(repo: str, sha: str, token: str) -> list[CheckRun]:
    """Every check run on this commit, following pagination."""
    url: str | None = f"{API_ROOT}/repos/{repo}/commits/{sha}/check-runs?per_page=100"
    runs: list[CheckRun] = []

    while url:
        # The pagination URL arrives in a remote Link header. Treat it as untrusted.
        if not url.startswith(f"{API_ROOT}/"):
            raise SystemExit(f"refusing non-GitHub URL from Link header: {url}")

        request = urllib.request.Request(  # noqa: S310 - scheme validated above
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "accountant-dad-merge-gate",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.load(response)
            link_header = str(response.headers.get("Link", ""))

        if isinstance(payload, dict):
            found = payload.get("check_runs")
            if isinstance(found, list):
                runs.extend(entry for entry in found if isinstance(entry, dict))

        url = None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")

    return runs


def latest_per_name(runs: list[CheckRun]) -> dict[str, CheckRun]:
    """A name can have several runs (re-runs, push plus pull_request). Take the newest.

    Taking the wrong one is how a stale green masks a fresh red.
    """
    newest: dict[str, CheckRun] = {}
    for run in runs:
        name = _text(run, "name")
        if name is None:
            continue
        seen = newest.get(name)
        if seen is None or _identifier(run) > _identifier(seen):
            newest[name] = run
    return newest


def verdict(
    expected: set[str],
    # Mapping, not dict: both are read-only here, and dict is invariant in its
    # value type, which makes callers pass a needlessly exact shape.
    declared: Mapping[str, Declared],
    conclusions: Mapping[str, str | None],
) -> tuple[int, list[str]]:
    """Decide the merge gate's outcome. Pure — no network, no environment.

    GitHub reports one bit per check: did it succeed. That cannot distinguish a
    gate that examined something and rejected it from a gate that had nothing to
    examine. Conflating them is why this job could never pass, could therefore
    never be required, and therefore bound nothing.

    Four states, not two:

        red   + declared    EXCUSED  a placeholder, waiting on its subject
        red   + undeclared  FAILURE  a real gate rejected something. BLOCK.
        green + declared    STALE    it passes now, so it must stop being
                                     excused. BLOCK, and name it.
        green + undeclared  ok

    STALE is the rule that keeps this permanent. Without it the list rots and
    silently covers a real gate forever.

    Returns (exit code, lines to print).
    """
    lines: list[str] = []
    failures: list[str] = []
    stale: list[str] = []
    excused: list[str] = []

    for name in sorted(expected):
        conclusion = conclusions.get(name)
        succeeded = conclusion == CONCLUSION_SUCCESS
        is_declared = name in declared

        if succeeded and not is_declared:
            lines.append(f"  ok       {name}")
        elif succeeded and is_declared:
            stale.append(f"  STALE   {name}")
        elif is_declared:
            e = declared[name]
            excused.append(f"  EXCUSED {name}  [{e.id} · {e.milestone} · {e.owner}] {e.blocker}")
        else:
            failures.append(f"  {str(conclusion).upper():7s} {name}")

    lines.extend(excused)

    if failures:
        lines.append("")
        lines.append("BLOCKED - a gate that is NOT declared a placeholder did not succeed")
        lines.extend(failures)
        lines.append("")
        lines.append("These gates can run. They ran, and they did not pass.")
        lines.append("Fix the code. Do not add the name to the declared-exceptions file:")
        lines.append("that list is shrink-only and adding to it is blocked separately.")
        return 1, lines

    if stale:
        lines.append("")
        lines.append("BLOCKED - a declared placeholder is now PASSING")
        lines.extend(stale)
        lines.append("")
        lines.append("A gate that passes must not stay excused. Delete its line from")
        lines.append("tools/ci/declared_placeholder_gates.txt. That deletion IS the")
        lines.append("promotion: a commit, in a diff, reviewable, versioned.")
        return 1, lines

    lines.append("")
    lines.append(f"all {len(expected)} gates accounted for")
    lines.append(f"  {len(expected) - len(excused)} passed")
    lines.append(f"  {len(excused)} red by declaration, each with a stated blocker")
    return 0, lines


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["MERGE_GATE_SHA"]
    token = os.environ["GITHUB_TOKEN"]
    timeout_minutes = float(os.environ["MERGE_GATE_POLL_TIMEOUT_MINUTES"])
    interval_seconds = float(os.environ["MERGE_GATE_POLL_INTERVAL_SECONDS"])
    workflows_dir = os.environ["MERGE_GATE_WORKFLOWS_DIR"]
    # The BASE branch's copy. Read from the pull request's checkout, a pull
    # request could excuse the gate it just broke. os.environ[...] and not
    # .get(...): a missing path must abort, never default to "nothing is
    # excused" (which fails everything) or "everything is excused" (worse).
    declared_path = os.environ["MERGE_GATE_DECLARED_EXCEPTIONS"]

    expected = check_names(workflows_dir)
    declared = parse_declared(declared_path)

    unknown = sorted(set(declared) - expected)
    if unknown:
        # A declared name that matches no real check is dead weight at best and
        # a typo shadowing a live gate at worst. Either way the list is wrong.
        print("BLOCKED - declared-exceptions names a check that does not exist")
        for name in unknown:
            print(f"  UNKNOWN {name}")
        print()
        print("Every declared name must match a Check Run name byte for byte.")
        return 1

    print(f"commit           {sha}")
    print(f"gates expected   {len(expected)}")
    print(f"declared red     {len(declared)}  ({declared_path})")
    print(f"must be green    {len(expected) - len(declared)}")
    print(f"poll timeout     {timeout_minutes} minutes")
    print(f"poll interval    {interval_seconds} seconds")
    print()

    deadline = time.monotonic() + timeout_minutes * 60.0
    newest: dict[str, CheckRun] = {}

    while True:
        try:
            newest = latest_per_name(fetch_check_runs(repo, sha, token))
        except (urllib.error.URLError, TimeoutError) as error:
            # A transient API failure must not decide the outcome. Retry until the
            # deadline; the deadline itself is what fails the build.
            print(f"  api error, retrying: {error}")

        outstanding = [
            name
            for name in sorted(expected)
            if name not in newest or _text(newest[name], "status") != "completed"
        ]

        if not outstanding:
            print("every expected gate has completed")
            break

        if time.monotonic() >= deadline:
            print()
            print(f"BLOCKED - timed out after {timeout_minutes} minutes")
            for name in outstanding:
                run = newest.get(name)
                state = _text(run, "status") if run else None
                print(f"  WAITING {name}  ({state or 'never appeared'})")
            return 1

        shown = ", ".join(outstanding[:_MAX_NAMES_IN_PROGRESS_LINE])
        more = " ..." if len(outstanding) > _MAX_NAMES_IN_PROGRESS_LINE else ""
        print(f"  waiting on {len(outstanding)} gate(s): {shown}{more}")
        time.sleep(interval_seconds)

    print()
    # Absence is handled by the poll loop above: it only exits once every
    # expected name is present AND completed, otherwise it times out. A gate
    # that never reports therefore fails as a timeout, never as a silent pass.
    conclusions = {name: _text(run, "conclusion") for name, run in newest.items()}
    code, lines = verdict(expected, declared, conclusions)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
