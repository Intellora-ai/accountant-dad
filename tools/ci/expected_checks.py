#!/usr/bin/env python3
"""Extract every GitHub Actions job name from a directory of workflow files.

A job's `name:` becomes its Check Run name — proven empirically against this
repository: gate.yml declares `name: typecheck · lint · tests · build`, and the
check-runs API returns that string byte-for-byte. When `name:` is absent GitHub
falls back to the job id, so this mirrors that.

The merge gate excludes itself. Waiting on your own check run never terminates.
"""

from __future__ import annotations

import glob
import os
import sys

import yaml

MERGE_GATE_CHECK_NAME = "merge gate"


def check_names(workflows_dir: str) -> set[str]:
    """Every Check Run name the workflows in this directory will produce."""
    paths = sorted(
        glob.glob(os.path.join(workflows_dir, "*.yml"))
        + glob.glob(os.path.join(workflows_dir, "*.yaml"))
    )
    if not paths:
        raise SystemExit(f"no workflow files found in {workflows_dir}")

    names: set[str] = set()
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        if not isinstance(document, dict):
            raise SystemExit(f"{path}: top level is not a mapping")

        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            raise SystemExit(f"{path}: no jobs mapping")

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                raise SystemExit(f"{path}: job {job_id!r} is not a mapping")
            names.add(job.get("name", job_id))

    names.discard(MERGE_GATE_CHECK_NAME)
    return names


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: expected_checks.py <workflows-dir>")
    for name in sorted(check_names(sys.argv[1])):
        print(name)
