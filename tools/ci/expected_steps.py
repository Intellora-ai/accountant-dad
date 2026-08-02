#!/usr/bin/env python3
"""Every named step of every job, so a step cannot vanish unnoticed.

The job-level ratchet has a hole: deleting a STEP inside a job leaves the job
count untouched. A canary step, an anti-gaming assertion or a whole `run:`
block can be removed and every existing check still reports "no gate removed".

The standing rule is "never remove a gate, job, STEP, check or assertion". This
enforces the word that was previously only prose.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

MERGE_GATE_CHECK_NAME = "merge gate"
_EXPECTED_ARGV = 2


def step_names(workflows_dir: str) -> set[str]:
    """Every "<check name> :: <step name>" pair the workflows declare."""
    root = Path(workflows_dir)
    paths = sorted([*root.glob("*.yml"), *root.glob("*.yaml")])
    if not paths:
        raise SystemExit(f"no workflow files found in {workflows_dir}")

    pairs: set[str] = set()
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise SystemExit(f"{path}: top level is not a mapping")
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            raise SystemExit(f"{path}: no jobs mapping")

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                raise SystemExit(f"{path}: job {job_id!r} is not a mapping")
            check = job.get("name", job_id)
            if not isinstance(check, str):
                raise SystemExit(f"{path}: job {job_id!r} has a non-string name")
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                # An unnamed step is identified by its action or its position,
                # so removing it is still detectable.
                label = step.get("name") or step.get("uses") or f"<step {index}>"
                pairs.add(f"{check} :: {label}")
    return pairs


if __name__ == "__main__":
    if len(sys.argv) != _EXPECTED_ARGV:
        raise SystemExit("usage: expected_steps.py <workflows-dir>")
    for pair in sorted(step_names(sys.argv[1])):
        print(pair)
