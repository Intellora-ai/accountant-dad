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


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["MERGE_GATE_SHA"]
    token = os.environ["GITHUB_TOKEN"]
    timeout_minutes = float(os.environ["MERGE_GATE_POLL_TIMEOUT_MINUTES"])
    interval_seconds = float(os.environ["MERGE_GATE_POLL_INTERVAL_SECONDS"])
    workflows_dir = os.environ["MERGE_GATE_WORKFLOWS_DIR"]

    expected = check_names(workflows_dir)
    print(f"commit           {sha}")
    print(f"gates expected   {len(expected)}")
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
    failures: list[str] = []
    for name in sorted(expected):
        conclusion = _text(newest[name], "conclusion")
        if conclusion == CONCLUSION_SUCCESS:
            print(f"  ok      {name}")
        else:
            failures.append(f"  {str(conclusion).upper():7s} {name}")

    if failures:
        print()
        print("BLOCKED - not every gate succeeded")
        for line in failures:
            print(line)
        return 1

    print()
    print(f"all {len(expected)} gates succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
