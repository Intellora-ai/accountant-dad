"""Can `KNOWN_FAILURES.md` still say something the repository contradicts? (R5)

WHAT FORCED THIS. On 2026-08-06 three of the tracker's claims were checked by
hand against the tree. Two were false:

    F-024  "the repository does not build at HEAD"   `Exclusion` imports fine
    F-026  "24 commits carry zero CI evidence"       0 ahead, the tip is pushed
    F-018  "FIXED, all three have real consumers"    true

Neither false entry was careless. Both were TRUE when written and neither was
re-read after the defect it described was fixed. A tracker entry is a claim with
no expiry date, and this repository held 33 of them, none wired to anything that
could contradict them. The cost is not untidiness: one of those unmeasured
claims was carried into a root-cause analysis as if it were evidence.

THE TRANSFORM (Law 53). *"Is this entry's prose true?"* is a reading-
comprehension problem over 2,600 lines of English needing a human who knows the
whole system. *"Does the predicate this entry names still hold in the tree?"* is
a question about text and file existence, answers in milliseconds, and fails in
the same place. So every entry names its own predicate, and this module
evaluates it.

THE VOCABULARY IS DELIBERATELY TINY. Six verbs, all decidable by reading the
repository — no imports executed, no subprocess, no network. A verb needing any
of those would make the guard slower than the suite it guards and would put the
guard's own reliability in question.

    exists PATH             absent PATH
    defines PATH NAME       not-defines PATH NAME
    contains PATH TEXT      not-contains PATH TEXT

and one escape hatch, which is an admission rather than a pass:

    UNVERIFIABLE <reason>

WHAT THIS CANNOT DO, STATED HERE RATHER THAN DISCOVERED LATER.

1. It cannot tell whether a predicate is the RIGHT predicate for the status
   beside it. `exists README.md` under a status about the mutation gate would
   pass. What it does enforce is that the predicate is not circular
   (`_must_not_cite_the_tracker`), not vacuous (a negative verb naming a file
   that is not there FAILS rather than passing over nothing), and that a status
   claiming CLOSED, FIXED or RESOLVED carries at least one mechanical
   predicate — so the escape hatch cannot be used to retire an entry.

2. It does not RUN the tests an entry names. `defines <test file> <test name>`
   proves the guard exists; the suite proves it passes. The two compose — a
   named guard that was deleted fails here, a named guard that went red fails
   there — but neither half is the other's evidence, and this module never
   claims a test passed.

3. It is a statement about the working tree, never about GitHub. Anything whose
   truth lives in a check run, a ruleset or a remote ref is UNVERIFIABLE here by
   construction (Law 44), and has to say so in its own words.
"""

from __future__ import annotations

import re
import shlex
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import first_party

#: The tracker, relative to the repository root.
TRACKER = "KNOWN_FAILURES.md"

#: Info string of the fenced block that carries an entry's predicates.
CHECK_LANGUAGE = "check"

#: Info string of the single block carrying the file's own self-count.
TOTALS_LANGUAGE = "totals"

#: The escape hatch's keyword. First word of the line, reason after it.
UNVERIFIABLE = "UNVERIFIABLE"

#: An admission shorter than this tells a reader nothing they can act on, and
#: "too hard" is not a reason. The number is a floor on effort, not on truth —
#: it cannot make a reason honest, only make an empty one visible.
FEWEST_WORDS_IN_A_REASON = 5

#: Argument count per verb. The vocabulary is CLOSED and this table is it: a
#: verb absent from here is refused by name rather than skipped, so a typo can
#: never become an entry that quietly checks nothing.
ARITY = {
    "exists": 1,
    "absent": 1,
    "defines": 2,
    "not-defines": 2,
    "contains": 2,
    "not-contains": 2,
}

#: `## F-024 · Title`, and the one range heading the file already carries under
#: the identifiers its own source code cites. The separator is the middle dot
#: this file already uses; requiring it is what makes a heading an ENTRY rather
#: than a section, and the exhaustive-heading rule below closes the alternative.
#: Both dash forms are accepted because the range heading is typed with an EN
#: DASH and a hyphen alone would silently stop matching it. It is written as the
#: escape backslash-u-2013 rather than as itself: a literal en dash in source is
#: indistinguishable from a hyphen at a glance, which is exactly how it would
#: come to be "tidied" into one.
ENTRY_HEADING = re.compile(
    r"^## (?P<identifier>F-\d{3}|D\d+(?:\s*[\u2013-]\s*D\d+)?) · (?P<title>.+)$"
)

#: The entry's own status cell. The cell opens with a STATE TOKEN and the prose
#: follows it, because a state a program can read is the only half of a status
#: two people cannot disagree about. Free prose alone is what let F-024 read
#: "OPEN" in this row while its own body two paragraphs down read "SYMPTOM
#: RESOLVED" — the file contradicting itself with nothing able to notice.
STATUS_ROW = re.compile(
    r"^\|\s*\*\*Status\*\*\s*\|\s*`(?P<state>[A-Z]+)`\s*·\s*(?P<prose>.*?)\s*\|\s*$"
)

#: An unmarked `| **Status** |` row — matched only to refuse it by name, so a
#: status written the old way fails loudly instead of being skipped as if the
#: entry had no status at all.
UNMARKED_STATUS_ROW = re.compile(r"^\|\s*\*\*Status\*\*\s*\|")

#: The closed set of states. `CLOSED` is the only one that asserts the work
#: landed, and it is the only one carrying an extra obligation.
STATES = ("OPEN", "PARTIAL", "BLOCKED", "CLOSED")

#: The state that asserts the work landed. Such an entry must carry at least one
#: mechanical predicate — a change that landed left a trace in the tree, and if
#: it left none there is nothing to close.
SETTLED = "CLOSED"

#: The file's self-count, machine-checked so it cannot go stale in silence.
TOTALS_LINE = re.compile(
    r"^entries=(?P<entries>\d+) predicates=(?P<predicates>\d+) unverifiable=(?P<unverifiable>\d+)$"
)

#: Headings that are sections of the file rather than tracked failures. The set
#: is EXHAUSTIVE: any other `## ` heading must parse as an entry, so a new entry
#: cannot escape the predicate requirement by being titled differently.
NON_ENTRY_HEADINGS = frozenset(
    {
        "Measurement state of this file — Law 56",
        "How an entry is checked — the predicate vocabulary",
        "Closed",
    }
)

#: Below this the parser is describing a different file. Guards against a regex
#: that silently stops matching and then reports nothing wrong.
FEWEST_ENTRIES_THAT_CAN_BE_REAL = 30


class TrackerDefectError(Exception):
    """Raised when the tracker itself is malformed.

    Deliberately distinct from a failing predicate. A false claim is a fact
    about the repository; an entry with no predicate, a duplicate identifier or
    an unknown verb is a fact about the FILE, and the two need different fixes.
    """


class Verdict(Enum):
    """What the repository says about one entry's claim."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class Check:
    """One predicate line, as written."""

    line: int
    verb: str
    arguments: tuple[str, ...]

    @property
    def mechanical(self) -> bool:
        """Whether the repository can decide this line."""
        return self.verb != UNVERIFIABLE

    def __str__(self) -> str:
        return " ".join((self.verb, *self.arguments))


@dataclass(frozen=True)
class Entry:
    """One tracked failure: its identifier, its state, and its predicates."""

    identifier: str
    title: str
    line: int
    state: str
    status: str
    checks: tuple[Check, ...]

    @property
    def settled(self) -> bool:
        """Whether the state asserts the work landed."""
        return self.state == SETTLED


@dataclass(frozen=True)
class Finding:
    """The result of evaluating one predicate."""

    identifier: str
    check: Check
    holds: bool
    detail: str


@dataclass(frozen=True)
class Totals:
    """The file's own self-count."""

    entries: int
    predicates: int
    unverifiable: int


@dataclass(frozen=True)
class Line:
    """One line of the tracker, with the fence context it sits in."""

    number: int
    text: str
    language: str | None
    fence: bool


def tracker_path(root: Path | None = None) -> Path:
    """Where the tracker lives, in the AUTHORED tree.

    `first_party.repo_root()` rather than `Path(__file__)`: under `mutmut run`
    this module is imported out of `mutants/`, which holds no
    `KNOWN_FAILURES.md` at all, so a `__file__`-derived root would report the
    tracker missing for every mutant (L-013, F-016).
    """
    return (root if root is not None else first_party.repo_root()) / TRACKER


def lines_of(text: str) -> Iterator[Line]:
    """Every line, tagged with the fenced block it belongs to.

    A fence marker carries the language of the block it opens or closes, and
    content inside a fence carries that language — so a heading or a table row
    quoted inside a code block is never mistaken for markup. Fences may be
    indented; two in this file already are.
    """
    language: str | None = None
    for number, text_of_line in enumerate(text.splitlines(), start=1):
        stripped = text_of_line.strip()
        if not stripped.startswith("```"):
            yield Line(number, stripped, language, fence=False)
            continue
        opened = stripped.removeprefix("```").strip()
        yield Line(number, stripped, language if language is not None else opened, fence=True)
        language = None if language is not None else opened


# ── parsing ───────────────────────────────────────────────────────────────


def parse(text: str) -> tuple[Entry, ...]:
    """Every entry in the tracker, with its status and its predicates.

    Raises `TrackerDefectError` for a malformed file: an unrecognised heading, a
    duplicate identifier, a missing or repeated `check` block, an entry with no
    status, or a settled status carrying no mechanical predicate.
    """
    entries: list[Entry] = []
    heading: re.Match[str] | None = None
    at_line = 0
    status: re.Match[str] | None = None
    checks: list[Check] = []
    blocks = 0

    for line in lines_of(text):
        if line.language == CHECK_LANGUAGE:
            if not at_line:
                raise TrackerDefectError(
                    f"{TRACKER}:{line.number} — a ```{CHECK_LANGUAGE} block before the first "
                    "heading belongs to no entry, so nothing would ever evaluate it."
                )
            if line.fence:
                blocks += 1
            else:
                checks.append(_check_from(line))
            continue
        if line.language is not None:
            continue
        if line.text.startswith("## "):
            if heading is not None or at_line:
                entries.append(_entry(heading, at_line, status, tuple(checks), blocks // 2))
            heading, at_line, status, checks, blocks = _heading(line), line.number, None, [], 0
            continue
        if at_line and status is None:
            status = _status(line)
    if at_line:
        entries.append(_entry(heading, at_line, status, tuple(checks), blocks // 2))
    _must_be_unique(entries)
    return tuple(entries)


def _status(line: Line) -> re.Match[str] | None:
    """The status row's state token and prose, or `None` if this is not it."""
    found = STATUS_ROW.match(line.text)
    if found is None:
        if UNMARKED_STATUS_ROW.match(line.text):
            raise TrackerDefectError(
                f"{TRACKER}:{line.number} — a status row with no state token: {line.text!r}. "
                f"It must open `| **Status** | `STATE` · prose |` with STATE one of "
                f"{', '.join(STATES)}, so a program can read the claim and not only a human."
            )
        return None
    if found.group("state") not in STATES:
        raise TrackerDefectError(
            f"{TRACKER}:{line.number} — unknown state {found.group('state')!r}. The set is "
            f"closed: {', '.join(STATES)}."
        )
    return found


def _heading(line: Line) -> re.Match[str] | None:
    """The heading's identifier and title, or `None` for a declared section.

    Anything that is neither is refused, and that is what makes the predicate
    requirement inescapable for an entry added later.
    """
    found = ENTRY_HEADING.match(line.text)
    if found is not None:
        return found
    if line.text.removeprefix("## ").strip() in NON_ENTRY_HEADINGS:
        return None
    raise TrackerDefectError(
        f"{TRACKER}:{line.number} — {line.text!r} is neither an entry heading "
        "(`## F-000 · Title`) nor one of the file's declared sections. Every entry has to "
        "be recognisable, or it carries no predicate and nothing can contradict it."
    )


def _entry(
    heading: re.Match[str] | None,
    line: int,
    status: re.Match[str] | None,
    checks: tuple[Check, ...],
    blocks: int,
) -> Entry:
    if heading is None:
        if checks or blocks:
            raise TrackerDefectError(
                f"{TRACKER}:{line} — a declared section carries a ```{CHECK_LANGUAGE} block. "
                "Only entries make claims."
            )
        return Entry(identifier="", title="", line=line, state="", status="", checks=())
    identifier = heading.group("identifier")
    if status is None:
        raise TrackerDefectError(
            f"{TRACKER}:{line} — {identifier} has no `| **Status** |` row. An entry with no "
            "status makes no claim, and a claim nobody made cannot be checked."
        )
    if blocks != 1:
        raise TrackerDefectError(
            f"{TRACKER}:{line} — {identifier} has {blocks} ```{CHECK_LANGUAGE} block(s); "
            "exactly one is required. An entry with no predicate is an assertion the "
            "repository can never contradict, which is why this file has a verifier."
        )
    if not checks:
        raise TrackerDefectError(f"{TRACKER}:{line} — {identifier}'s check block is empty.")
    entry = Entry(
        identifier=identifier,
        title=heading.group("title"),
        line=line,
        state=status.group("state"),
        status=status.group("prose"),
        checks=checks,
    )
    if entry.settled and not any(check.mechanical for check in checks):
        raise TrackerDefectError(
            f"{TRACKER}:{line} — {identifier} is recorded {SETTLED} while every check is "
            f"{UNVERIFIABLE}. Work that landed left a trace in the tree; if it left none, "
            "there is nothing to close."
        )
    return entry


def _check_from(line: Line) -> Check:
    words = shlex.split(line.text)
    if not words:
        raise TrackerDefectError(f"{TRACKER}:{line.number} — blank line inside a check block.")
    verb, arguments = words[0], tuple(words[1:])
    if verb == UNVERIFIABLE:
        if not arguments:
            raise TrackerDefectError(
                f"{TRACKER}:{line.number} — {UNVERIFIABLE} with no reason. An admission that "
                "does not say WHY the repository cannot decide it is indistinguishable from "
                "an entry nobody wanted to check."
            )
        if len(arguments) < FEWEST_WORDS_IN_A_REASON:
            raise TrackerDefectError(
                f"{TRACKER}:{line.number} — {UNVERIFIABLE} reason is too short: "
                f"{' '.join(arguments)!r}. Say what would have to change for the repository "
                "to be able to decide it."
            )
        return Check(line.number, verb, arguments)
    if verb not in ARITY:
        raise TrackerDefectError(
            f"{TRACKER}:{line.number} — unknown check verb {verb!r}. The vocabulary is "
            f"closed: {', '.join(sorted(ARITY))}, or {UNVERIFIABLE} with a reason."
        )
    if len(arguments) != ARITY[verb]:
        raise TrackerDefectError(
            f"{TRACKER}:{line.number} — {verb!r} takes {ARITY[verb]} argument(s), "
            f"{len(arguments)} given: {line.text!r}"
        )
    _must_not_cite_the_tracker(line, verb, arguments[0])
    return Check(line.number, verb, arguments)


def _must_not_cite_the_tracker(line: Line, verb: str, path: str) -> None:
    """A tracker entry may not prove itself out of the tracker's own text.

    Without this the cheapest way to satisfy every entry is
    `contains KNOWN_FAILURES.md "..."`, which asserts only that the file says
    what it says. That is the exact shape of the failure this module exists to
    stop, one level up.
    """
    if Path(path) == Path(TRACKER):
        raise TrackerDefectError(
            f"{TRACKER}:{line.number} — {verb!r} names the tracker itself. An entry proved "
            "out of its own text is circular and checks nothing."
        )


def _must_be_unique(entries: Iterable[Entry]) -> None:
    seen: dict[str, int] = {}
    for entry in entries:
        if not entry.identifier:
            continue
        first = seen.get(entry.identifier)
        if first is not None:
            raise TrackerDefectError(
                f"{TRACKER}:{entry.line} — identifier {entry.identifier} is already used at "
                f"line {first}. Two entries under one number make every citation of that "
                "number ambiguous, and a citation nobody can resolve is one nobody checks."
            )
        seen[entry.identifier] = entry.line


def entries_of(text: str) -> tuple[Entry, ...]:
    """The tracked failures — parsed sections that are entries, not headings."""
    return tuple(entry for entry in parse(text) if entry.identifier)


# ── the file's own self-count ─────────────────────────────────────────────


def declared_totals(text: str) -> Totals:
    """The self-count the file states, read out of its ```totals block."""
    stated = [
        line.text for line in lines_of(text) if line.language == TOTALS_LANGUAGE and not line.fence
    ]
    if len(stated) != 1:
        raise TrackerDefectError(
            f"{TRACKER} — expected exactly one line in one ```{TOTALS_LANGUAGE} block, "
            f"found {len(stated)}."
        )
    found = TOTALS_LINE.match(stated[0])
    if found is None:
        raise TrackerDefectError(
            f"{TRACKER} — the {TOTALS_LANGUAGE} line must read "
            f"`entries=N predicates=N unverifiable=N`, not {stated[0]!r}."
        )
    return Totals(
        entries=int(found.group("entries")),
        predicates=int(found.group("predicates")),
        unverifiable=int(found.group("unverifiable")),
    )


def counted_totals(entries: Sequence[Entry]) -> Totals:
    """What the self-count would have to say to be right."""
    return Totals(
        entries=len(entries),
        predicates=sum(1 for entry in entries for check in entry.checks if check.mechanical),
        unverifiable=sum(
            1 for entry in entries if any(not check.mechanical for check in entry.checks)
        ),
    )


# ── evaluating a predicate ────────────────────────────────────────────────


def _resolve(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise TrackerDefectError(
            f"{TRACKER} — {raw!r} leaves the repository. A predicate about a path this "
            "repository does not own proves nothing about this repository."
        )
    return root / candidate


def _defined(path: Path) -> frozenset[str]:
    return first_party.defined_names(
        first_party.parse_text(path.read_text(encoding="utf-8"), str(path))
    )


def _evaluate(check: Check, root: Path) -> tuple[bool, str]:
    shown = check.arguments[0]
    target = _resolve(root, shown)
    there = target.exists()
    if check.verb == "exists":
        return there, f"{shown} {'exists' if there else 'is not there'}"
    if check.verb == "absent":
        return not there, f"{shown} {'exists' if there else 'is not there'}"
    if not target.is_file():
        # A negative verb over a missing file would otherwise be vacuously true,
        # which is how a typo'd path becomes a green claim about nothing.
        return False, f"{shown} is not a file, so nothing about its contents is decidable"
    if check.verb in {"defines", "not-defines"}:
        return _evaluate_definition(check, target, shown)
    held = check.arguments[1] in target.read_text(encoding="utf-8")
    return held is (check.verb == "contains"), (
        f"{shown} {'contains' if held else 'does not contain'} {check.arguments[1]!r}"
    )


def _evaluate_definition(check: Check, target: Path, shown: str) -> tuple[bool, str]:
    if target.suffix != ".py":
        raise TrackerDefectError(
            f"{TRACKER}:{check.line} — {check.verb!r} needs a Python file, not {shown!r}."
        )
    held = check.arguments[1] in _defined(target)
    return held is (check.verb == "defines"), (
        f"{shown} {'defines' if held else 'does not define'} {check.arguments[1]} at module scope"
    )


def findings(entries: Sequence[Entry], root: Path | None = None) -> tuple[Finding, ...]:
    """Evaluate every mechanical predicate in every entry."""
    where = root if root is not None else first_party.repo_root()
    return tuple(
        Finding(entry.identifier, check, *_evaluate(check, where))
        for entry in entries
        for check in entry.checks
        if check.mechanical
    )


def verdict(entry: Entry, results: Sequence[Finding]) -> Verdict:
    """What the repository says about one entry, given its findings."""
    mine = [found for found in results if found.identifier == entry.identifier]
    if any(not found.holds for found in mine):
        return Verdict.FALSE
    if any(not check.mechanical for check in entry.checks):
        return Verdict.UNVERIFIABLE
    return Verdict.TRUE


def contradicted(root: Path | None = None) -> tuple[Finding, ...]:
    """Every predicate in the tracker that the repository contradicts."""
    where = root if root is not None else first_party.repo_root()
    entries = entries_of(tracker_path(where).read_text(encoding="utf-8"))
    return tuple(found for found in findings(entries, where) if not found.holds)


def main(argv: Sequence[str] | None = None) -> int:
    """Print every entry's verdict; exit non-zero if the repository contradicts one."""
    given = list(argv) if argv is not None else sys.argv[1:]
    root = Path(given[0]).resolve() if given else first_party.repo_root()
    text = tracker_path(root).read_text(encoding="utf-8")
    entries = entries_of(text)
    results = findings(entries, root)
    broken = [found for found in results if not found.holds]
    totals = counted_totals(entries)
    for entry in entries:
        print(f"{verdict(entry, results).value:<13} {entry.identifier}  {entry.title}")
    print(
        f"\n{totals.entries} entries · {totals.predicates} predicates · "
        f"{totals.unverifiable} carrying an {UNVERIFIABLE} admission · "
        f"{len(broken)} contradicted"
    )
    for found in broken:
        print(f"  {TRACKER}:{found.check.line} {found.identifier} — {found.detail}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
