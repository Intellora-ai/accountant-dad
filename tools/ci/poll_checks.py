#!/usr/bin/env python3
"""Wait for every declared gate to finish, then assert all of them succeeded.

Only `success` passes. `failure`, `cancelled`, `skipped`, `timed_out`, `neutral`,
`action_required` and `stale` all fail, and so does a check that never appeared.

The explicit rejection of `skipped` is deliberate and is NOT redundant. GitHub
treats a skipped job as satisfying a required check, so a skipped gate would
otherwise merge a failed pipeline. No gate job declares `needs:` or `if:`, and no
gate workflow has a path filter, so nothing should ever be skipped — this rejects
it anyway rather than trusting that invariant holds forever.

Absence is failure too. A gate that never starts cannot pass by omission.

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

TERMINAL_PASS = "success"
API_ROOT = "https://api.github.com"


def fetch_check_runs(repo: str, sha: str, token: str) -> list[dict]:
    """Every check run on this commit, following pagination."""
    url = f"{API_ROOT}/repos/{repo}/commits/{sha}/check-runs?per_page=100"
    runs: list[dict] = []

    while url:
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "accountant-dad-merge-gate",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
            link_header = response.headers.get("Link", "")

        runs.extend(payload.get("check_runs", []))

        url = None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")

    return runs


def latest_per_name(runs: list[dict]) -> dict[str, dict]:
    """A name can have several runs (re-runs, push plus pull_request). Take the newest."""
    newest: dict[str, dict] = {}
    for run in runs:
        name = run.get("name")
        if name is None:
            continue
        seen = newest.get(name)
        if seen is None or run.get("id", 0) > seen.get("id", 0):
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
    newest: dict[str, dict] = {}

    while True:
        try:
            newest = latest_per_name(fetch_check_runs(repo, sha, token))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            # A transient API failure must not decide the outcome. Retry until the
            # deadline; the deadline itself is what fails the build.
            print(f"  api error, retrying: {error}")

        outstanding = [
            name
            for name in sorted(expected)
            if name not in newest or newest[name].get("status") != "completed"
        ]

        if not outstanding:
            print("every expected gate has completed")
            break

        if time.monotonic() >= deadline:
            print()
            print(f"BLOCKED - timed out after {timeout_minutes} minutes")
            for name in outstanding:
                state = newest.get(name, {}).get("status", "never appeared")
                print(f"  WAITING {name}  ({state})")
            return 1

        print(f"  waiting on {len(outstanding)} gate(s): {', '.join(outstanding[:5])}"
              + (" ..." if len(outstanding) > 5 else ""))
        time.sleep(interval_seconds)

    print()
    failures: list[str] = []
    for name in sorted(expected):
        run = newest.get(name)
        if run is None:
            failures.append(f"  ABSENT  {name}")
            continue
        conclusion = run.get("conclusion")
        if conclusion == TERMINAL_PASS:
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
