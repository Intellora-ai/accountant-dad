"""The Engineering Operating System is checked by a program, not by good intentions.

── WHAT THIS FILE EXISTS TO STOP, MEASURED 2026-08-06 ──

    CLAUDE.md                     951 lines · 9,474 words
    its own header                "RE-READ THIS ENTIRE FILE, EVERY TIME"
    its own §N, same file         "a long document cannot be re-run from finite
                                   attention at every step, so compliance drifts
                                   to 'apply what's salient'"

    SYSTEM_LAWS.md                "55 numbered engineering laws"
    ENGINEERING_RULES.md          "§C the 55 laws"
    CLAUDE.md §C                  57 laws

Two claims, in two files, both wrong by two, and **nothing in the repository could
notice**. That is the defect. Not the wrong number — the absence of anything able to
see it. A count that drifts teaches the reader the document is unreliable, and an
unreliable document stops being consulted at all, which silently removes every rule
inside it.

── WHY THESE ASSERTIONS AND NOT OTHERS ──

Each one decides a question a program can decide. None of them decides whether a law
is a *good* law, or whether a gate's checklist is the *right* checklist — that is
judgement, and a test pretending to enforce judgement would be theatre, a failure mode
this repository already has a name for (`engineering/ANTI_PATTERNS.md` F3).

What they enforce is that the machine-readable spine, the prose, and the bootloader
still agree with each other.
"""

from __future__ import annotations

import json
import pathlib
import re

import engineering_os
import pytest

REPOSITORY = pathlib.Path(__file__).resolve().parents[2]
ENGINEERING = REPOSITORY / "engineering"

#: The count is asserted as a LITERAL, not read from the registry. Reading it
#: from the thing under test would make this assertion vacuous — it would pass
#: for any pair of agreeing wrong numbers, which is precisely the state that
#: existed before this file.
LAWS_IN_THE_CONSTITUTION = 57

#: Stages in engineering/METHOD.md's pipeline.
METHOD_STAGES = 12

#: Below this many sampled laws, the one-home assertion proves too little to
#: be worth having — it could pass while most of the file lived somewhere else.
MINIMUM_LAWS_SAMPLED = 40

#: The bootloader was 952 lines when its own section N explained why that
#: cannot work. Deliberately loose: this catches regrowth into a manual, not
#: a few lines of drift.
BOOTLOADER_LINE_CEILING = 700

#: CLAUDE.md must name METHOD.md, LAWS.md and registry.json. Lose any one and
#: nothing loads that document.
REQUIRED_BOOTLOADER_REFERENCES = 3

#: Every mental model that used to live in CLAUDE.md §D. If one of these loses
#: its home, the merge quietly became a deletion (§E.8 forbids subtracting
#: anything the owner specified).
MENTAL_MODELS = (
    "Perfect Outcome",
    "First Principles",
    "5 Whys",
    "Inversion",
    "Systems Thinking",
    "Bottleneck",
    "Reverse Engineer",
    "Simplicity",
    "Trade-offs",
    "Evidence",
    "Second-Order",
    "Verification",
    "Falsification",
    "Problem Transformation",
)


def registry() -> dict[str, object]:
    loaded = json.loads((ENGINEERING / "registry.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "registry.json is not a JSON object"
    return loaded


def gates() -> list[dict[str, object]]:
    found = registry()["gates"]
    assert isinstance(found, list)
    return [gate for gate in found if isinstance(gate, dict)]


# ───────────────────────────────────────────── the system is coherent right now


def test_the_operating_system_is_coherent() -> None:
    """One assertion covering every check, so a new check is enforced for free."""
    problems = engineering_os.audit()
    assert problems == [], "\n".join(str(problem) for problem in problems)


def test_the_law_count_is_the_one_the_constitution_actually_has() -> None:
    """The exact drift that created this file, asserted against a literal."""
    assert engineering_os.declared_law_count() == LAWS_IN_THE_CONSTITUTION
    assert len(engineering_os.law_numbers()) == LAWS_IN_THE_CONSTITUTION
    assert engineering_os.highest_law_heading() == LAWS_IN_THE_CONSTITUTION


def test_the_laws_live_in_exactly_one_file() -> None:
    """`git grep` for a law's own words must find one home, not four.

    Law 51 existed in four places before this. Fixing one copy left three
    lying, which is how a rule ends up meaning different things in the same
    repository (`ANTI_PATTERNS.md` F1).
    """
    openings = engineering_os._law_openings()
    assert len(openings) >= MINIMUM_LAWS_SAMPLED, (
        "too few laws sampled for this assertion to mean anything"
    )

    homes: dict[str, list[str]] = {}
    for path in REPOSITORY.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for opening in openings:
            if opening in text:
                homes.setdefault(opening, []).append(path.name)

    strays = {
        opening: found
        for opening, found in homes.items()
        if [name for name in found if name != "LAWS.md"]
    }
    assert strays == {}, (
        f"law text found outside engineering/LAWS.md: {strays}. Every other mention must be a link."
    )


@pytest.mark.parametrize("model", MENTAL_MODELS)
def test_every_mental_model_has_a_home(model: str) -> None:
    """The merge must not have been a deletion wearing a coverage table."""
    method = (ENGINEERING / "METHOD.md").read_text(encoding="utf-8")
    assert model in method, (
        f"mental model {model!r} from CLAUDE.md §D has no entry in METHOD.md's coverage "
        f"table. Merging is permitted; dropping is not (§E.8)."
    )


def test_the_method_has_all_twelve_stages_in_order() -> None:
    stages = engineering_os.method_stages()[:METHOD_STAGES]
    assert stages == list(range(1, METHOD_STAGES + 1))


@pytest.mark.parametrize("gate", gates(), ids=lambda gate: str(gate.get("id")))
def test_every_registered_gate_is_a_real_usable_document(gate: dict[str, object]) -> None:
    """A registry entry pointing at nothing is worse than no entry at all."""
    path = REPOSITORY / str(gate["path"])
    assert path.is_file(), f"gate {gate['id']} points at {path}, which does not exist"

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# GATE ·"), f"{path.name} is registered as a gate but is not one"
    assert "**Fires when:**" in text, f"{path.name} never says when it applies"
    assert "- [ ]" in text or "CHECKLIST" in text, (
        f"{path.name} has nothing actionable. A gate that cannot be walked is a "
        f"reference document, and reference documents are what this system replaced."
    )
    assert gate.get("keywords"), f"gate {gate['id']} has no keywords, so nothing can route to it"
    assert gate.get("headline"), f"gate {gate['id']} has no headline for the loader to emit"


def test_the_bootloader_routes_to_every_gate() -> None:
    """A gate nothing links to is a gate nobody opens."""
    bootloader = (REPOSITORY / "CLAUDE.md").read_text(encoding="utf-8")
    missing = [str(gate["path"]) for gate in gates() if str(gate["path"]) not in bootloader]
    assert missing == [], f"CLAUDE.md's router does not mention: {missing}"


def test_the_bootloader_stayed_short_enough_to_actually_be_read() -> None:
    """The measured cause of the redesign, guarded against silently returning.

    951 lines was the state that produced 'apply what's salient'. The bound is
    deliberately loose — this asserts the file did not grow back into a manual,
    not that it hit some ideal length.
    """
    lines = len((REPOSITORY / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    assert lines < BOOTLOADER_LINE_CEILING, (
        f"CLAUDE.md is {lines} lines. It was 952 when its own §N explained that a long "
        f"document cannot be applied from finite attention. Move the new material into "
        f"engineering/ rather than growing the bootloader."
    )


# ─────────────────────────────────────────── the checks are proven to discriminate


def test_a_law_added_without_bumping_the_count_is_caught(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guard never observed refusing is unproven, so this observes it refusing."""
    drifted = tmp_path / "LAWS.md"
    drifted.write_text(
        (ENGINEERING / "LAWS.md").read_text(encoding="utf-8")
        + "\n### 58. A law nobody counted\n\nInjected.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(engineering_os, "LAWS_PATH", drifted)

    checks = [problem.check for problem in engineering_os.check_law_count()]
    assert "law-count" in checks
    assert "law-numbering" in checks


def test_a_law_quietly_deleted_is_caught(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opposite direction. Silent subtraction is the §E.8 violation."""
    text = (ENGINEERING / "LAWS.md").read_text(encoding="utf-8")
    shortened = tmp_path / "LAWS.md"
    shortened.write_text(re.sub(r"^30\. .*$", "", text, count=1, flags=re.MULTILINE), "utf-8")
    monkeypatch.setattr(engineering_os, "LAWS_PATH", shortened)

    assert [problem.check for problem in engineering_os.check_law_count()] == ["law-count"]


def test_a_bootloader_that_stops_loading_the_system_is_caught(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If CLAUDE.md stops naming these, nothing loads them and the OS is inert."""
    severed = tmp_path / "CLAUDE.md"
    severed.write_text("# CLAUDE.md\n\nNothing here.\n", encoding="utf-8")
    monkeypatch.setattr(engineering_os, "BOOTLOADER_PATH", severed)

    problems = engineering_os.check_bootloader_points_here()
    assert len(problems) == REQUIRED_BOOTLOADER_REFERENCES
    assert all(problem.check == "bootloader" for problem in problems)


def test_a_dangling_registry_reference_is_caught(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engineering_os, "REPOSITORY", tmp_path)
    problems = engineering_os.check_every_referenced_document_exists()
    assert problems, "a registry pointing at an empty tree must not pass"
    assert all(problem.check == "dangling-reference" for problem in problems)


def test_the_duplication_check_permits_a_bootloader_that_only_links() -> None:
    """The other direction, without which the guard is just a word filter.

    A check that refused everything would be as useless as one that refused
    nothing, and would be removed within a day for getting in the way.
    """
    assert engineering_os.check_no_duplicate_law_text() == []
