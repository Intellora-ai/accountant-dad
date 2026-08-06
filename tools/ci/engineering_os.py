"""Consistency checker for the Engineering Operating System.

WHY THIS EXISTS
    Prose cannot be checked, so prose drifts. Measured 2026-08-06:
    `SYSTEM_LAWS.md` claimed *"55 numbered engineering laws"* while `CLAUDE.md`
    contained **57**, and `ENGINEERING_RULES.md` repeated the same wrong count.
    Nothing in the repository could notice.

    A count that drifts is worse than a missing one. It teaches the reader that
    the document is unreliable, and an unreliable document stops being
    consulted at all — which silently removes every rule inside it.

WHAT IT CHECKS, AND WHY EACH CHECK EARNS ITS PLACE
    Each function below answers one question a program can decide. None of them
    can decide whether a law is a GOOD law; that is judgement, and a checker
    pretending to do it would be theatre. What they decide is whether the
    machine-readable spine, the prose, and the bootloader still agree.

WHAT IT DELIBERATELY CANNOT DO — stated here, not discovered later
    1. It cannot tell whether a gate's headline is the RIGHT summary of its gate.
    2. It does not run the hook; `tests/unit/test_engineering_method_enforced.py`
       does that, by observing it refuse and then permit.
    3. It says nothing about GitHub. Anything whose truth lives in a check run
       or a ruleset is outside this module by construction (Law 44).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPOSITORY / "engineering" / "registry.json"
LAWS_PATH = REPOSITORY / "engineering" / "LAWS.md"
METHOD_PATH = REPOSITORY / "engineering" / "METHOD.md"
BOOTLOADER_PATH = REPOSITORY / "CLAUDE.md"

#: A law heading in `LAWS.md`. Two shapes exist because the constitution grew
#: that way: short laws are list items (`4. Never weaken...`), and the ones that
#: needed an explanation were promoted to sub-headings (`### 52. Nothing is...`).
#: Matching only one shape would silently miss six laws — which is the class of
#: error this whole module exists to catch, so it is matched explicitly.
LAW_HEADING = re.compile(r"^(?:### )?(\d{1,2})\. ", re.MULTILINE)

#: A stage line in `METHOD.md`'s pipeline block, e.g. " 7 INVERT".
METHOD_STAGE = re.compile(r"^\s*(\d{1,2}) [A-Z]", re.MULTILINE)

#: How many stages the method has. Not a preference — it is the number the
#: bootloader, the hook text and the prose must all agree on.
EXPECTED_STAGES = 12


@dataclass(frozen=True)
class Problem:
    """One disagreement, named precisely enough to fix without re-deriving it."""

    check: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.check}: {self.detail}"


def registry() -> dict[str, object]:
    loaded = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{REGISTRY_PATH} is not a JSON object")
    return loaded


def declared_law_count() -> int:
    laws = registry().get("laws")
    if not isinstance(laws, dict):
        raise ValueError("registry.json has no 'laws' object")
    count = laws.get("count")
    if not isinstance(count, int):
        raise ValueError("registry.json 'laws.count' is not an integer")
    return count


def law_numbers() -> list[int]:
    """The contiguous law sequence in `LAWS.md`, in file order.

    A match is accepted only when it continues the run: 1, then 2, then 3.
    That rule is not a convenience — it is the only way to separate a LAW from
    an ordinary numbered list, because both are `N. ` at column zero and the
    laws themselves contain sub-lists that restart at 1. Measured: a naive
    match found 69 headings where 57 laws exist, four of them duplicated.

    A missing or duplicated law truncates the run, which `check_law_count`
    then reports as a count mismatch. So this is strict, not lenient.
    """
    accepted: list[int] = []
    for match in LAW_HEADING.findall(LAWS_PATH.read_text(encoding="utf-8")):
        number = int(match)
        if number == len(accepted) + 1:
            accepted.append(number)
    return accepted


def highest_law_heading() -> int:
    """The largest law number written anywhere in `LAWS.md`, contiguous or not.

    Catches the opposite error to a truncated run: a law appended as 58 while
    the declared count still says 57.
    """
    found = [int(match) for match in LAW_HEADING.findall(LAWS_PATH.read_text(encoding="utf-8"))]
    return max(found) if found else 0


def method_stages() -> list[int]:
    return [int(match) for match in METHOD_STAGE.findall(METHOD_PATH.read_text(encoding="utf-8"))]


def referenced_paths() -> list[str]:
    """Every repository path the registry points at."""
    found: list[str] = []
    data = registry()
    for key in ("always_loaded",):
        value = data.get(key)
        if isinstance(value, list):
            found.extend(item for item in value if isinstance(item, str))
    for key in ("core_documents", "gates"):
        value = data.get(key)
        if isinstance(value, list):
            found.extend(
                entry["path"]
                for entry in value
                if isinstance(entry, dict) and isinstance(entry.get("path"), str)
            )
    laws = data.get("laws")
    if isinstance(laws, dict) and isinstance(laws.get("home"), str):
        found.append(str(laws["home"]))
    return found


def check_law_count() -> list[Problem]:
    """The exact failure that created this module."""
    problems: list[Problem] = []
    present = law_numbers()
    declared = declared_law_count()

    if len(present) != declared:
        problems.append(
            Problem(
                "law-count",
                f"registry.json declares {declared} laws; LAWS.md contains {len(present)}. "
                f"Adding a law means updating both.",
            )
        )

    highest = highest_law_heading()
    if highest > declared:
        problems.append(
            Problem(
                "law-numbering",
                f"LAWS.md contains a law numbered {highest} but registry.json declares only "
                f"{declared}. Bump the count — never renumber a law, because its number is "
                f"cited across DECISION_LOG.md, KNOWN_FAILURES.md and CI code.",
            )
        )

    stated = LAWS_PATH.read_text(encoding="utf-8")
    if f"laws={declared}" not in stated:
        problems.append(
            Problem(
                "law-count-self-report",
                f"LAWS.md does not carry its own machine-checked count 'laws={declared}'.",
            )
        )
    return problems


def check_most_broken_are_real_laws() -> list[Problem]:
    laws = registry().get("laws")
    highlighted = laws.get("most_broken") if isinstance(laws, dict) else None
    if not isinstance(highlighted, list):
        return [Problem("most-broken", "registry.json 'laws.most_broken' is missing or not a list")]
    present = set(law_numbers())
    strays = [n for n in highlighted if n not in present]
    if strays:
        return [Problem("most-broken", f"laws highlighted but not present in LAWS.md: {strays}")]
    return []


def check_every_referenced_document_exists() -> list[Problem]:
    return [
        Problem("dangling-reference", f"registry.json points at {path}, which does not exist")
        for path in referenced_paths()
        if not (REPOSITORY / path).is_file()
    ]


def check_method_pipeline() -> list[Problem]:
    stages = method_stages()
    if stages[:EXPECTED_STAGES] != list(range(1, EXPECTED_STAGES + 1)):
        return [
            Problem(
                "method-stages",
                f"METHOD.md's pipeline must open with stages 1..{EXPECTED_STAGES} in order; "
                f"found {stages[:EXPECTED_STAGES]}",
            )
        ]
    return []


def check_bootloader_points_here() -> list[Problem]:
    """CLAUDE.md is the ONLY surface measured to load in every session.

    The hook is a repository-local backstop, but `.claude/hooks/` is
    write-protected by the harness, so the bootloader is what must carry the
    router. If it stops naming these documents, nothing loads them.
    """
    text = BOOTLOADER_PATH.read_text(encoding="utf-8")
    required = ("engineering/METHOD.md", "engineering/LAWS.md", "engineering/registry.json")
    return [
        Problem("bootloader", f"CLAUDE.md no longer references {name}; the OS would never load")
        for name in required
        if name not in text
    ]


def check_no_duplicate_law_text() -> list[Problem]:
    """One rule, one home. Duplication was the measured defect (anti-pattern F1).

    The check is deliberately narrow: it looks for whole laws re-stated in the
    bootloader, not for any sentence that resembles one. A broad check would
    fire on prose ABOUT a law and train the reader to ignore the result, which
    destroys the only enforcement there is.
    """
    bootloader = BOOTLOADER_PATH.read_text(encoding="utf-8")
    restated = [text for text in _law_openings() if text and text in bootloader]
    if restated:
        return [
            Problem(
                "duplicated-laws",
                f"CLAUDE.md restates the text of {len(restated)} law(s) that live in "
                f"engineering/LAWS.md — first: {restated[0]!r}. A rule lives in exactly one "
                f"file; every other mention is a link. Duplication was the measured defect: "
                f"Law 51 existed in four places and the law count in two of them was stale.",
            )
        ]
    return []


def _law_openings(sample_size: int = 40) -> list[str]:
    """The opening words of a sample of laws, for verbatim-duplication detection.

    Counting numbered headings was tried first and rejected on measurement: it
    reported 37 "restated laws" in a bootloader that restated none, because
    `CLAUDE.md` legitimately contains a 16-item pointer list and several
    numbered amendment lists. A heuristic that fires on correct content trains
    the reader to ignore it, which destroys the only enforcement there is.

    Matching the actual TEXT has no such failure mode: a law's own words
    appearing in the bootloader IS the duplication, by definition.
    """
    lines = LAWS_PATH.read_text(encoding="utf-8").split("\n")
    openings: list[str] = []
    for line in lines:
        match = LAW_HEADING.match(line)
        if not match:
            continue
        remainder = line[match.end() :].strip()
        if len(remainder) >= sample_size:
            openings.append(remainder[:sample_size])
    return openings


def audit() -> list[Problem]:
    """Every check, run together, so one command answers 'is the OS coherent?'."""
    problems: list[Problem] = []
    for check in (
        check_law_count,
        check_most_broken_are_real_laws,
        check_every_referenced_document_exists,
        check_method_pipeline,
        check_bootloader_points_here,
        check_no_duplicate_law_text,
    ):
        problems.extend(check())
    return problems


def main() -> int:  # pragma: no cover - exercised as a script, asserted via audit()
    problems = audit()
    for problem in problems:
        print(problem)
    if not problems:
        print(
            f"engineering OS coherent: {declared_law_count()} laws, "
            f"{EXPECTED_STAGES} method stages, "
            f"{len(referenced_paths())} referenced documents all present"
        )
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
