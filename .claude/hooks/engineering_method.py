#!/usr/bin/env python3
"""Repository-local enforcement of the engineering method. One script, three events.

WHY THIS FILE IS IN THE REPOSITORY AND NOT IN `~/.claude/`
    Measured 2026-08-06: `.gitignore:50` ignored `.claude/` wholesale, so
    `git ls-files .claude/` returned NOTHING. Every hook enforcing this
    project's rules lived in one laptop's home directory. A fresh clone got
    zero enforcement. That was the real reason "CLAUDE.md is insufficient" —
    not that the document was weak, but that nothing in the repository read it.

WHAT EACH EVENT CAN ACTUALLY DO — MEASURED, NOT ASSUMED
    Every claim below was observed in a real session on 2026-08-06.

    SessionStart      stdout is prepended once per session.        ADVISORY
    UserPromptSubmit  stdout is prepended to EVERY prompt.         ADVISORY
    PreToolUse        a non-zero exit BLOCKS the tool call.        BINDING

    Only PreToolUse can refuse. Not a guess: the Law 56 metrics hook refused a
    `Write` in this repository on 2026-08-06 and the write did not land. So the
    one rule that CAN be mechanised is enforced there, and the rest are
    re-stated where they are cheapest to see.

THE REDUNDANCY IS DELIBERATE, AND SO IS ITS LIMIT
    Three independent surfaces in this repository, plus `CLAUDE.md` and the
    user-level hooks. A deleted home directory, a new machine, or a session
    that never opens `CLAUDE.md` each leave the others standing.

    THE HONEST BOUNDARY: a hook can force the rules to be SEEN and can refuse
    specific mechanical violations. It cannot make a model reason well. Claiming
    otherwise would be exactly the unmeasured assertion this method exists to
    prevent. What it removes is the failure where the method was never loaded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

METHOD_DOCUMENT = "ENGINEERING_METHOD.md"

METHOD = """\
ENGINEERING METHOD — MANDATORY, MEASURED, NOT ADVISORY

  1 DEFINE     Current State -> Desired State -> Gap. No gap, no engineering.
  2 MEASURE    Every claim is MEASURED / DERIVED / INFERRED / UNKNOWN.
               A document is a HYPOTHESIS, never evidence. Read the code.
  3 ROOT CAUSE Ask WHY up to the highest layer you can change; then HOW down
               to the smallest executable step. Both directions, every time.
  4 INVERT     "How would I make this fail forever?" Whatever already matches
               is a real bottleneck. Remove those first.
  5 ALL CAUSES List every candidate. Measure each. Reject only with evidence.
  6 PARALLEL   Independent work is dispatched concurrently, never serially.
  7 FINISH     Stop only when the cause is ELIMINATED, or an external blocker
               is PROVEN. Never stop at an explanation.
  8 FUTURE     Every fix states the new failure it could create.

  REJECTED hypotheses stay rejected unless NEW evidence appears.
"""

#: Phrases that assert a fact without having measured one. Deliberately short
#: and literal: a broad pattern would fire on prose ABOUT the rule and train
#: the reader to ignore this block, destroying the only enforcement there is.
UNMEASURED_CLAIMS = (
    "probably ",
    "i think ",
    "should work",
    "should be fine",
    "likely because",
    "presumably ",
    "i assume ",
)

#: Files whose content is engineering TRUTH: a false statement in one of these
#: is read later as evidence. Measured 2026-08-06 — two of three testable
#: claims in `KNOWN_FAILURES.md` were FALSE, and one was carried into a
#: root-cause analysis as if verified.
TRUTH_DOCUMENTS = ("KNOWN_FAILURES.md", "PROGRESS.md", "STATE.md", "BLOCKERS.md")


def writing_to_a_truth_document(payload: dict[str, object]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    path = tool_input.get("file_path")
    if not isinstance(path, str):
        return None
    name = Path(path).name
    return name if name in TRUTH_DOCUMENTS else None


def unmeasured_claims_in(payload: dict[str, object]) -> list[str]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    written = " ".join(
        value
        for key, value in tool_input.items()
        if key in {"content", "new_string"} and isinstance(value, str)
    ).lower()
    return [phrase.strip() for phrase in UNMEASURED_CLAIMS if phrase in written]


def on_pre_tool_use(payload: dict[str, object]) -> int:
    """The ONE binding surface. A non-zero exit refuses the tool call.

    It refuses exactly one thing, mechanically: a hedge written into a document
    whose whole purpose is to be trusted later. Everything else the method asks
    for is judgement, and a hook pretending to enforce judgement would be
    theatre — a failure mode this repository already has a name for.
    """
    document = writing_to_a_truth_document(payload)
    if document is None:
        return 0
    found = unmeasured_claims_in(payload)
    if not found:
        return 0

    quoted = ", ".join(repr(phrase) for phrase in found)
    print(
        f"BLOCKED - an unmeasured claim is being written into {document}.\n\n"
        f"    found: {quoted}\n\n"
        f"{document} is read later AS EVIDENCE. Measured 2026-08-06: two of "
        f"three testable claims in KNOWN_FAILURES.md were FALSE, and one was "
        f"carried into a root-cause analysis as if verified. It produced a root "
        f"cause (R4) that measurement later destroyed.\n\n"
        f"Write what you MEASURED, with the command or observation that "
        f"produced it. If it is not measured, write UNKNOWN or UNMEASURED - "
        f"both are correct answers. A hedge is not.\n",
        file=sys.stderr,
    )
    return 2


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    event = payload.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")

    if event == "SessionStart":
        print(METHOD)
        print(
            f"Full method: {METHOD_DOCUMENT}. Enforced by "
            ".claude/hooks/engineering_method.py, which is IN THIS REPOSITORY "
            "and depends on no home directory."
        )
    elif event == "UserPromptSubmit":
        print(METHOD)
    elif event == "PreToolUse":
        sys.exit(on_pre_tool_use(payload))


if __name__ == "__main__":
    main()
