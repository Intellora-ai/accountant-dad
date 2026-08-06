"""The inventory, attacked.

`test_conformance.py` proves the HARNESS cannot report a pass it did not earn.
This file asks the next question: is the inventory the harness runs actually
about the documents it claims to be about, and does every control really reach
the rule it names?

Five things are checked here that nothing else in the repository checks:

  THE CLEAN HALF RUNS. Every control's clean payload is constructed against the
  real frozen schema. A control whose clean half fails is `CONTROL_INVALID` and
  is NOT a pass — the payload died of some other defect and the rule under test
  was never reached. A suite of those is all green and worth nothing.

  THE CITATIONS STILL READ THE WAY THEY ARE QUOTED. Every `source` is opened,
  the line is read, and the `quote` must appear in it verbatim. A comment
  cannot catch a citation that drifted when somebody edited a spec; only
  reading the file can. The check is itself mutation-proven below — a citation
  moved by one line must be rejected, or the check is decoration.

  THE COUNTS ARE WRITTEN DOWN. Predicates, review-only entries, controls and
  exclusions are asserted as explicit numbers. Deleting a control is otherwise
  the cheapest way to make this suite green, and it would leave no trace at all.

  EVERY PROHIBITION CLAUSE IN `docs/` IS ACCOUNTED FOR. Both sides are derived
  at run time — the clauses are read off disk, the coverage off `REGISTRY` — so
  neither is a number anyone can edit. A rule added to a specification is RED
  until somebody writes down what happens to it. Before this existed, the
  inventory carried 40 hand-listed rules against 62 `must never` lines and
  nothing anywhere compared the two: the omission was silent and green, which
  is the most dangerous shape a registry can have.

  WHAT THE ENGINE ACTUALLY EMITS. Everything above tests SCHEMAS — whether six
  pydantic models refuse a hand-written payload. That is a different subject
  from whether any engine emits a conformant one, and a suite that only tests
  the first while sounding like it tests the second is worse than no suite. The
  last section runs the REAL Engine 1 pipeline on a REAL PDF and reads the
  artifact it produces. Those tests are RED. They are supposed to be.

These tests may read files and import Engine 1. `conformance_registry` itself
may do neither: it runs in the `conformance` job, which installs
`requirements-ci.txt` only, so an Engine 1 import there would break that job on
a missing OpenCV. This module runs under `unit tests`, where the dependencies
exist — which is why the against-the-real-artifact predicates live here.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import pymupdf
import pytest
from pydantic import BaseModel, ValidationError, create_model

import accountant_dad
from accountant_dad.artifacts.decision import DecisionStatus
from accountant_dad.artifacts.evidence import (
    Corroborated,
    DocumentEvidenceObject,
    DocumentId,
    SourceType,
)
from accountant_dad.artifacts.execution import ExecutionAttemptId, ExecutionId
from accountant_dad.conformance import (
    PHASES,
    Attribution,
    Enforcement,
    Exclusion,
    NegativeControl,
    Prohibition,
    Registry,
    Uncovered,
    attribute,
)
from accountant_dad.conformance_registry import (
    _CONFIDENCE,
    _UNSURE,
    CONTROLS,
    EXCLUSIONS,
    IMMUTABLE,
    PROHIBITIONS,
    REGISTRY,
    _clarification,
    _confidence_report,
    _conflict,
    _control,
    _decision,
    _detected_field,
    _doubt,
    _envelope,
    _evidence,
    _execution,
    _fact,
    _finding,
    _incomplete_decision,
    _journal_line,
    _mutate,
    _not_a_prohibition,
    _not_yet,
    _predicate,
    _provenance,
    _restates,
    _results,
    _results_raising_an_unknown,
    _results_with_a_less_certain_one,
    _review_only,
    _structured_document,
    _understanding,
    _unknown,
    _unwitnessable,
    _uuid,
    _validation,
)
from accountant_dad.engines.input_engine import cleaner, parser, pipeline, reader
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

#: Explicit, so a silent deletion is a red test rather than a smaller number
#: nobody notices. Raising these is normal; lowering one is a claim that a rule
#: stopped needing proof, and that claim has to be made out loud.
PREDICATE_COUNT = 37
REVIEW_ONLY_COUNT = 8
CONTROL_COUNT = 47
EXCLUSION_COUNT = 140

#: `DATA_FLOW.md` §2 — six canonical artifacts, six proofs of immutability.
CANONICAL_ARTIFACTS = frozenset(
    {
        "DocumentEvidenceObject",
        "BusinessUnderstandingObject",
        "AccountingDecision",
        "ClarificationRequest",
        "ValidationDecision",
        "ExecutionResult",
    }
)

#: A quote shorter than this cannot identify a sentence. `"the"` appears on
#: every page, so a citation built from it would pass the disk check while
#: pointing at nothing in particular.
SHORTEST_USEFUL_QUOTE = 20

_REPO_ROOT = pathlib.Path(str(accountant_dad.__file__)).parent.parent.parent


#: The phrase the specifications use for an absolute prohibition. Deliberately
#: ONE phrase and not a clever pattern: `never`, `cannot` and `may never` also
#: appear, so what this scanner finds is a LOWER BOUND on what `docs/` forbids
#: and never an upper one. Widening it is a one-line change and will turn the
#: completeness test red until the new clauses are triaged, which is correct.
_PROHIBITION_MARKER = re.compile(r"must never", re.IGNORECASE)

#: A markdown list item — `- x`, `* x`, `1. x`. Used to expand a `must never`
#: HEADER into the clauses beneath it, because "The Input Engine MUST NEVER:"
#: is a label and the nine numbered lines under it are the rules. Without the
#: expansion this check would triage headings and miss every actual clause.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\S")


def _line(source: str) -> str:
    """The one line `source` names, read off disk. `path:line`, 1-based."""
    path, _, number = source.rpartition(":")
    body = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    return body[int(number) - 1]


def _prohibition_clauses(root: pathlib.Path) -> tuple[tuple[str, str], ...]:
    """Every prohibition clause in `root/docs`, as `(path:line, text)`.

    Derived, never listed. A count written down here would be a second source
    of truth about the specifications, and the moment somebody edited a
    document the two would disagree with no test able to say which was right.

    Three shapes, in order of precedence:

      HEADER + LIST   `It **MUST NEVER**:` followed by numbered or bulleted
                      items — every item is its own clause, at its own line.
      HEADER + PROSE  the same header followed by a `·`-separated sentence —
                      that sentence is the clause, so the citation lands on the
                      words rather than on the label.
      PLAIN           any other line carrying the marker.

    A `#` heading is expanded only when a list follows it. `## 12. What the
    Application Layer must never do` is followed by a fenced block, so the
    heading stays the clause — and the exclusion list says so out loud rather
    than letting eleven clauses vanish.
    """
    found: list[tuple[str, str]] = []
    for document in sorted(root.glob("docs/**/*.md")):
        lines = document.read_text(encoding="utf-8").splitlines()
        relative = document.relative_to(root).as_posix()
        for number, line in enumerate(lines, 1):
            if not _PROHIBITION_MARKER.search(line):
                continue
            stripped = line.rstrip()
            introduces = stripped.endswith(":")
            if not (introduces or stripped.startswith("#")):
                found.append((f"{relative}:{number}", stripped.strip()))
                continue
            cursor = number
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            items: list[int] = []
            while cursor < len(lines) and _LIST_ITEM.match(lines[cursor]):
                items.append(cursor + 1)
                cursor += 1
            if items:
                found.extend((f"{relative}:{at}", lines[at - 1].strip()) for at in items)
            elif introduces and cursor < len(lines):
                found.append((f"{relative}:{cursor + 1}", lines[cursor].strip()))
            else:
                found.append((f"{relative}:{number}", stripped.strip()))
    return tuple(found)


def _quotes_its_source(prohibition: Prohibition) -> bool:
    return prohibition.quote in _line(prohibition.source)


def _identify(prohibition: Prohibition) -> str:
    return prohibition.identifier


# ── the two conditions P2 is done under ───────────────────────────────────


def test_every_predicate_has_a_negative_control() -> None:
    """`BLUEPRINT:135` — every `MUST NEVER` is a predicate or on the review-only
    list. A rule declared enforced with nothing exercising it is a claim, not an
    enforcement, and it is indistinguishable from an enforced one until someone
    deletes the code."""
    assert REGISTRY.untested_predicates() == ()


def test_no_control_is_a_false_green() -> None:
    """Every control ENFORCED. Not NOT_ENFORCED, and not CONTROL_INVALID.

    The second is the one that matters. `CONTROL_INVALID` means the clean
    payload was refused too, so the violating payload's rejection cannot be
    attributed to the rule under test — the control looked green and proved
    nothing about the schema.
    """
    reported = [
        f"{finding.prohibition}: {finding.attribution.value} — {finding.detail}"
        for finding in REGISTRY.failures()
    ]
    assert reported == []


@pytest.mark.parametrize("control", CONTROLS, ids=lambda control: control.prohibition)
def test_each_control_reaches_the_rule_it_names(control: NegativeControl) -> None:
    """Per control, so a failure names the rule instead of a count."""
    finding = attribute(control)
    assert finding.attribution is Attribution.ENFORCED, finding.detail


# ── a crash is not an enforcement ─────────────────────────────────────────
#
# `attribute` used to read ANY exception out of a violating payload as proof
# that a rule was enforced. Deleting the missing-score branch of `evidence.py`
# left the next line reaching into a dict without the key, and the gate said
#
#     ENGINE_1:245/every-reading-carries-its-confidence -> enforced
#     :: refused by KeyError                                  GATE: GREEN
#
# The enforcement was gone and the number went up. `NegativeControl.refusal`
# closes it — but only for controls that DECLARE one, and the harness keeps the
# old permissive default deliberately (see its module docstring). These two
# tests are what make the declaration mandatory for the live inventory.


@pytest.mark.parametrize("control", CONTROLS, ids=lambda control: control.prohibition)
def test_every_control_declares_how_its_payload_is_refused(control: NegativeControl) -> None:
    """`ValidationError`, and nothing broader. A control that kept the default
    `(Exception,)` would still score a `KeyError` from inside a validator as
    enforcement, which is the defect, not a milder version of it."""
    assert control.refusal == (ValidationError,), (
        f"{control.prohibition} does not declare its refusal type. Build it with "
        "`_control(...)`, which declares ValidationError for the whole inventory."
    )


def _a_missing_key() -> object:
    """What the deleted enforcement branch actually left behind: the next line
    reached into `scores[field.name]` for a key that was no longer there."""
    scores: dict[str, Decimal] = {}
    return scores["Amount"]


def _a_renamed_helper() -> object:
    """The other shape of a broken control — a builder calling a name that
    moved out from under it."""
    raise AttributeError("module 'evidence' has no attribute 'moved'")


def test_a_control_that_crashes_instead_of_being_refused_is_not_a_pass() -> None:
    """The regression test for the defect itself, at the shape it had. Before
    `refusal` existed this reported `enforced :: refused by KeyError`, so
    DELETING an enforcement made the gate greener."""
    finding = attribute(_control("invented", clean=_evidence, violating=_a_missing_key))
    assert finding.attribution is Attribution.CONTROL_CRASHED
    assert not finding.is_pass
    assert "KeyError is not how this payload is refused (ValidationError)" in finding.detail


def test_a_clean_payload_that_crashes_is_reported_as_broken_not_as_refused() -> None:
    """The same distinction on the other half. `CONTROL_INVALID` accuses the
    SCHEMA of refusing a legitimate payload; a crash accuses the control. Both
    fail, and telling a maintainer the wrong one sends them to the wrong file."""
    finding = attribute(_control("invented", clean=_a_renamed_helper, violating=_evidence))
    assert finding.attribution is Attribution.CONTROL_CRASHED
    assert "the clean payload did not fail, it BROKE" in finding.detail


def test_a_genuine_refusal_still_reads_as_enforcement() -> None:
    """The other side of the same coin, and the reason this fix is not simply
    'catch less'. Narrowing the catch is only correct if a REAL refusal still
    scores — otherwise every one of the 47 controls would go red together and
    the change would be a deletion wearing a fix's name."""
    finding = attribute(
        _control(
            "invented",
            clean=_evidence,
            violating=lambda: _evidence(confidence_report=_confidence_report(confidence_scores=())),
        )
    )
    assert finding.attribution is Attribution.ENFORCED
    assert finding.detail == "refused by ValidationError"


# ── the citations, read off disk ──────────────────────────────────────────


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_quote_is_still_on_the_line_it_cites(prohibition: Prohibition) -> None:
    """A citation that drifted from its document is a lie a comment cannot catch.

    Verbatim substring, not a fuzzy match: a quote that has to be normalised to
    match is a quote that has already started to diverge.
    """
    assert _quotes_its_source(prohibition), (
        f"{prohibition.identifier} quotes {prohibition.quote!r}, but "
        f"{prohibition.source} now reads {_line(prohibition.source)!r}"
    )


def test_the_citation_check_notices_a_line_that_drifted() -> None:
    """Mutation proof for the test above. Without this, a check that always
    returned True would pass the whole suite and prove nothing about any
    document."""
    real = next(item for item in PROHIBITIONS if item.identifier == IMMUTABLE)
    assert _quotes_its_source(real)

    path, _, number = real.source.rpartition(":")
    moved = dataclasses.replace(real, source=f"{path}:{int(number) + 1}")
    assert not _quotes_its_source(moved)


def test_the_citation_check_notices_a_quote_that_was_never_there() -> None:
    """The other direction: right line, invented sentence."""
    real = next(item for item in PROHIBITIONS if item.identifier == IMMUTABLE)
    invented = dataclasses.replace(real, quote="Artifacts may be edited in place when convenient.")
    assert not _quotes_its_source(invented)


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_source_names_a_line_in_a_document_that_exists(prohibition: Prohibition) -> None:
    path, _, number = prohibition.source.rpartition(":")
    assert path.startswith("docs/"), f"{prohibition.identifier} cites {path}, outside docs/"
    assert (_REPO_ROOT / path).is_file(), f"{prohibition.identifier} cites a missing file: {path}"
    assert int(number) >= 1


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_quote_is_long_enough_to_identify_a_sentence(prohibition: Prohibition) -> None:
    assert len(prohibition.quote) >= SHORTEST_USEFUL_QUOTE


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_the_identifier_carries_the_line_its_source_names(prohibition: Prohibition) -> None:
    """`DOC:LINE/slug`. The line is in both halves so a finding names the exact
    sentence, and so the two cannot drift apart silently."""
    path, _, number = prohibition.source.rpartition(":")
    document = path.removeprefix("docs/").removesuffix(".md")
    cited, separator, slug = prohibition.identifier.partition("/")
    assert separator == "/", f"{prohibition.identifier} has no slug"
    assert slug, f"{prohibition.identifier} has an empty slug"
    assert cited.endswith(f":{number}"), f"{prohibition.identifier} does not name line {number}"
    # The identifier abbreviates the filename (`ENGINE_1`, not
    # `ENGINE_1_INPUT_ENGINE_RULES`); it may shorten the name, never change it.
    assert cited.rpartition(":")[0] in document


def test_no_two_prohibitions_cite_the_same_line() -> None:
    """One line, one rule. Two entries on one sentence is the same prohibition
    counted twice, which inflates coverage without adding any."""
    sources = [item.source for item in PROHIBITIONS]
    assert sorted(sources) == sorted(set(sources))


# ── every clause in docs/ is accounted for ────────────────────────────────
#
# WHY THIS IS THE MOST IMPORTANT TEST IN THE FILE.
#     Everything above judges the inventory against ITSELF: are the citations
#     real, do the controls reach their rules, are the counts what they were.
#     None of it can see a rule that was never listed. The inventory held 40
#     entries while `docs/` held 62 `must never` lines, and no test compared
#     the two — so the answer to "what is missing?" was "nobody knows", and it
#     was GREEN.
#
#     Both sides here are derived at run time. Neither 62 nor 40 appears
#     anywhere: the clauses come off disk on every run and the coverage comes
#     off `REGISTRY`. Add a prohibition to any specification and this goes red
#     until somebody writes down, in the registry, what happens to it.


def test_every_prohibition_clause_in_the_documents_is_covered_or_listed() -> None:
    """No clause may be merely absent. Covered by a rule, or excluded with a
    reason — those are the two legal states, and silence is not one of them."""
    accounted = REGISTRY.accounted_for()
    unaccounted = [
        f"{source} — {text[:120]}"
        for source, text in _prohibition_clauses(_REPO_ROOT)
        if source not in accounted
    ]
    assert unaccounted == [], (
        f"{len(unaccounted)} prohibition clause(s) in docs/ are neither cited by a "
        "rule nor listed as excluded. Add a Prohibition, or add an Exclusion saying "
        "why not — an omission is the one state this inventory may not be in."
    )


def test_no_exclusion_excuses_a_line_that_is_not_a_clause() -> None:
    """The other direction, and it matters as much. An exclusion for a line
    nobody prohibits inflates the accounted-for set with nothing, and it is
    exactly what a stale entry looks like after somebody edits a document."""
    clauses = {source for source, _ in _prohibition_clauses(_REPO_ROOT)}
    stale = sorted(item.source for item in EXCLUSIONS if item.source not in clauses)
    assert stale == [], (
        "these exclusions name a line that no longer carries a prohibition; the "
        "document moved and the exclusion did not"
    )


# ── an exclusion has to be a real admission ───────────────────────────────
#
# Every guard below refuses at CONSTRUCTION, so a malformed exclusion cannot
# reach the list at all. That matters more here than for a prohibition: a
# prohibition that is wrong makes a control fail, and a control failing is
# loud. An exclusion that is wrong makes a clause LOOK accounted for, and
# nothing downstream ever runs it.


def test_an_exclusion_with_no_reason_is_refused() -> None:
    """An unexplained exclusion is an omission with a nicer name."""
    with pytest.raises(ValueError, match="needs a reason"):
        _unwitnessable("docs/DATA_FLOW.md:1", "   ")


def test_an_exclusion_with_no_source_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a source"):
        _unwitnessable("   ", _A_REASON)


def test_an_exclusion_attributed_to_a_whole_document_is_refused() -> None:
    """Same rule a prohibition lives under: without a line it cannot be
    re-checked when the document changes."""
    with pytest.raises(ValueError, match="must name a line"):
        _unwitnessable("docs/DATA_FLOW.md", _A_REASON)


def test_a_restatement_that_names_no_rule_is_refused() -> None:
    """'Covered somewhere else' is not a citation, and it is the single
    easiest way to make a clause disappear while looking handled."""
    with pytest.raises(ValueError, match="must name the rule"):
        _restates("docs/DATA_FLOW.md:1", "   ", _A_REASON)


def test_only_a_restatement_may_name_a_rule_that_carries_it() -> None:
    """An `UNWITNESSABLE` clause pointing at a rule would be claiming coverage
    and denying it in the same entry."""
    with pytest.raises(ValueError, match="only a restatement"):
        Exclusion(
            source="docs/DATA_FLOW.md:1",
            kind=Uncovered.UNWITNESSABLE,
            reason=_A_REASON,
            restates=IMMUTABLE,
        )


def test_a_debt_with_no_due_date_is_refused() -> None:
    """A debt with no due date is a decision never to pay it — the same
    reasoning that makes a review-only prohibition carry an expiry."""
    with pytest.raises(ValueError, match="must name the phase"):
        Exclusion(
            source="docs/DATA_FLOW.md:1",
            kind=Uncovered.NOT_YET_A_PREDICATE,
            reason=_A_REASON,
        )


@pytest.mark.parametrize("bad", ["P1", "P7", "later", "soon", "", "p4"])
def test_a_debt_due_at_something_that_is_not_a_phase_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="is not a phase"):
        _not_yet("docs/DATA_FLOW.md:1", _A_REASON, bad)


def test_a_clause_no_artifact_can_witness_cannot_come_due() -> None:
    """`UNWITNESSABLE` is permanent by definition. An expiry on one is a
    promise nobody can keep, quietly aging in a list."""
    with pytest.raises(ValueError, match="only a clause that is 'not yet a predicate'"):
        Exclusion(
            source="docs/DATA_FLOW.md:1",
            kind=Uncovered.UNWITNESSABLE,
            reason=_A_REASON,
            expiry="P4",
        )


def test_two_exclusions_may_not_name_the_same_line() -> None:
    """The second is invisible, and a reason nobody reads is not a reason."""
    with pytest.raises(ValueError, match="two exclusions name the line"):
        Registry(
            PROHIBITIONS,
            CONTROLS,
            (*EXCLUSIONS, EXCLUSIONS[0]),
        )


def test_a_line_may_not_be_both_cited_by_a_rule_and_excluded() -> None:
    """One of the two is false — either the rule is enforced or it is not — and
    a reader believing the wrong one is exactly the state this refuses."""
    with pytest.raises(ValueError, match="both cited by a prohibition and listed"):
        Registry(
            PROHIBITIONS,
            CONTROLS,
            (*EXCLUSIONS, _unwitnessable(PROHIBITIONS[0].source, _A_REASON)),
        )


def test_an_exclusion_may_not_be_excused_by_a_rule_nobody_wrote_down() -> None:
    """Built against the REAL inventory, so the guard is proven against 45 live
    entries rather than a toy pair."""
    with pytest.raises(ValueError, match="which is not in the inventory"):
        Registry(
            PROHIBITIONS,
            CONTROLS,
            (*EXCLUSIONS, _restates("docs/DATA_FLOW.md:1", "a rule nobody wrote", _A_REASON)),
        )


def test_the_accounted_for_set_is_every_cited_line_and_every_excluded_one() -> None:
    """The set the completeness check reads. Built from both halves, so a
    registry that quietly dropped its exclusions would report every excluded
    clause as missing rather than as fine."""
    assert REGISTRY.accounted_for() == frozenset(
        {item.source for item in PROHIBITIONS} | {item.source for item in EXCLUSIONS}
    )


def test_an_inventory_with_no_exclusions_accounts_only_for_what_it_cites() -> None:
    """The default. `Registry` must be constructible before any clause has been
    triaged, or the list could never be built one entry at a time."""
    registry = Registry(PROHIBITIONS, CONTROLS)
    assert registry.exclusions == ()
    assert registry.accounted_for() == {item.source for item in PROHIBITIONS}
    for kind in Uncovered:
        assert registry.by_uncovered(kind) == ()


def test_the_registry_separates_the_four_reasons_a_clause_is_uncovered() -> None:
    """`by_uncovered` is what publishes the shape of the gap. A version that
    ignored its argument would report every clause under every heading and the
    debt would read as forty times its real size."""
    for kind in Uncovered:
        assert all(item.kind is kind for item in REGISTRY.by_uncovered(kind))
    assert {item.kind for item in EXCLUSIONS} == set(Uncovered)


def test_the_clause_scanner_reads_the_documents_and_not_a_fixture() -> None:
    """A scanner that returned `()` would make the completeness test pass
    vacuously and prove nothing about any document. Pinned against two clauses
    whose text is asserted verbatim — one plain, one expanded out of a header."""
    found = dict(_prohibition_clauses(_REPO_ROOT))
    assert found["docs/SYSTEM_INVARIANTS.md:209"] == (
        "**Execution must never discover that posting was impossible.**"
    )
    # Line 314 carries no marker of its own. It is here only because line 312,
    # `The Input Engine **MUST NEVER**:`, was expanded into its list.
    assert found["docs/ENGINE_1_INPUT_ENGINE_RULES.md:314"] == "1. Decide transaction type."


def test_the_clause_scanner_finds_a_prohibition_a_document_did_not_have_before(
    tmp_path: pathlib.Path,
) -> None:
    """Mutation proof for the completeness check. Without this, a scanner that
    always returned the same fixed list would keep the suite green while a new
    `MUST NEVER` entered the specifications unnoticed — the precise failure the
    check exists to stop."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INVENTED.md").write_text(
        "# A document nobody wrote\n"
        "\n"
        "The Invented Engine **MUST NEVER**:\n"
        "\n"
        "1. Do the first forbidden thing.\n"
        "2. Do the second forbidden thing.\n"
        "\n"
        "A closing line that must never be read as a list item.\n",
        encoding="utf-8",
    )
    assert _prohibition_clauses(tmp_path) == (
        ("docs/INVENTED.md:5", "1. Do the first forbidden thing."),
        ("docs/INVENTED.md:6", "2. Do the second forbidden thing."),
        (
            "docs/INVENTED.md:8",
            "A closing line that must never be read as a list item.",
        ),
    )


def test_the_clause_scanner_takes_the_sentence_when_a_header_introduces_prose(
    tmp_path: pathlib.Path,
) -> None:
    """`ENGINE_5_VALIDATION_ENGINE_RULES.md:207` is a header over a
    `·`-separated sentence, not a list. The clause must land on the sentence:
    citing the label would let the words beneath it be rewritten freely."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PROSE.md").write_text(
        "Validation **MUST NEVER**:\n\ninvent facts · ask users · post transactions.\n",
        encoding="utf-8",
    )
    assert _prohibition_clauses(tmp_path) == (
        ("docs/PROSE.md:3", "invent facts · ask users · post transactions."),
    )


def test_the_clause_scanner_keeps_a_heading_that_introduces_no_list(
    tmp_path: pathlib.Path,
) -> None:
    """`APPLICATION_LAYER.md:379` is a heading over a fenced block. Nothing
    beneath it is a list item, so the heading itself stays the clause and the
    exclusion list is what records the eleven clauses inside the block."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "FENCED.md").write_text(
        "## What it must never do\n\n```text\nSomething forbidden\n```\n",
        encoding="utf-8",
    )
    assert _prohibition_clauses(tmp_path) == (("docs/FENCED.md:1", "## What it must never do"),)


@pytest.mark.parametrize("exclusion", EXCLUSIONS, ids=lambda item: item.source)
def test_every_exclusion_names_a_line_that_exists_in_the_document_it_cites(
    exclusion: Exclusion,
) -> None:
    """The same re-checkability a prohibition owes. An exclusion citing a file
    that moved, or a line past the end of one, excuses a clause nobody can find.

    That the line is a real CLAUSE is the neighbouring test's job — some are
    the prose sentence under a `MUST NEVER:` header and carry no marker of
    their own, which is exactly why the scanner reaches for them."""
    path, _, number = exclusion.source.rpartition(":")
    assert path.startswith("docs/"), f"{exclusion.source} cites {path}, outside docs/"
    assert (_REPO_ROOT / path).is_file(), f"{exclusion.source} cites a missing file"
    assert int(number) >= 1
    assert _line(exclusion.source).strip(), f"{exclusion.source} names a blank line"


@pytest.mark.parametrize("exclusion", EXCLUSIONS, ids=lambda item: item.source)
def test_every_exclusion_gives_a_reason_long_enough_to_argue_with(
    exclusion: Exclusion,
) -> None:
    """ "Out of scope" is not a reason. The threshold is the same one a quote has
    to clear to identify a sentence: below it, the text names nothing."""
    assert len(exclusion.reason) >= SHORTEST_USEFUL_QUOTE, exclusion.source


def test_every_restatement_names_a_rule_that_is_actually_in_the_inventory() -> None:
    """`Registry` refuses this at construction; asserted here against the REAL
    list so the guard is proven against 40 live entries rather than a toy one.
    A clause excused by a rule nobody wrote down is excused by nothing."""
    known = {item.identifier for item in PROHIBITIONS}
    dangling = sorted(
        f"{item.source} -> {item.restates}"
        for item in REGISTRY.by_uncovered(Uncovered.RESTATEMENT)
        if item.restates not in known
    )
    assert dangling == []


def test_every_debt_names_the_phase_it_comes_due() -> None:
    """A `NOT_YET_A_PREDICATE` exclusion is a promise to write a predicate. A
    promise with no date is a decision never to keep it — the same reasoning
    that makes a review-only entry carry an expiry."""
    for item in REGISTRY.by_uncovered(Uncovered.NOT_YET_A_PREDICATE):
        assert item.expiry in PHASES, item.source


def test_nothing_but_a_debt_carries_an_expiry() -> None:
    """An `UNWITNESSABLE` clause does not become witnessable at P5. An expiry on
    one would be a promise nobody can keep, quietly aging in a list."""
    for item in EXCLUSIONS:
        if item.kind is not Uncovered.NOT_YET_A_PREDICATE:
            assert item.expiry is None, item.source


def test_the_inventory_lists_exactly_this_many_uncovered_clauses() -> None:
    """Same reasoning as the counts above, in the other direction: quietly
    DELETING an exclusion would make the completeness test red, but quietly
    reclassifying a debt as unwitnessable would not, and this is where the
    shape of the gap is written down."""
    assert len(REGISTRY.exclusions) == EXCLUSION_COUNT
    assert sum(len(REGISTRY.by_uncovered(kind)) for kind in Uncovered) == EXCLUSION_COUNT


# ── the counts, written down ──────────────────────────────────────────────


def test_the_inventory_holds_exactly_this_many_predicates() -> None:
    assert len(REGISTRY.by_enforcement(Enforcement.PREDICATE)) == PREDICATE_COUNT


def test_the_inventory_holds_exactly_this_many_review_only_entries() -> None:
    assert len(REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY)) == REVIEW_ONLY_COUNT


def test_the_inventory_holds_exactly_this_many_controls() -> None:
    assert len(REGISTRY.controls) == CONTROL_COUNT


def test_the_prohibitions_are_only_ever_predicates_or_review_only() -> None:
    assert len(PROHIBITIONS) == PREDICATE_COUNT + REVIEW_ONLY_COUNT


# ── the review-only list, kept honest ─────────────────────────────────────


def test_every_review_only_entry_names_the_phase_it_stops_being_one() -> None:
    """An exemption with no end date is a deletion written politely. `Registry`
    refuses one at construction; this asserts none slipped in as `None`."""
    for item in REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY):
        assert item.expiry is not None, item.identifier


def test_no_review_only_entry_has_a_negative_control() -> None:
    """If it can be tested it is not review-only, and if it cannot the control
    does not test it. Either way one of the two labels is wrong."""
    exempt = {item.identifier for item in REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY)}
    assert not exempt & {control.prohibition for control in REGISTRY.controls}


def test_no_predicate_carries_an_expiry() -> None:
    """A predicate is enforced now. An expiry on one means the label is wrong."""
    for item in REGISTRY.by_enforcement(Enforcement.PREDICATE):
        assert item.expiry is None, item.identifier


# ── coverage of the thing the inventory is about ──────────────────────────


def test_all_six_canonical_artifacts_are_proven_immutable() -> None:
    """INV-5 is asserted once per artifact, not once in general. Five proofs and
    a gap would read identically in a summary count."""
    proven = {
        type(control.clean()).__name__
        for control in REGISTRY.controls
        if control.prohibition == IMMUTABLE
    }
    assert proven == CANONICAL_ARTIFACTS


def test_running_the_registry_twice_reports_the_same_thing() -> None:
    """No clock, no randomness. A conformance result that changes between two
    runs of the same commit is not a result."""
    first = [(finding.prohibition, finding.attribution) for finding in REGISTRY.run()]
    second = [(finding.prohibition, finding.attribution) for finding in REGISTRY.run()]
    assert first == second


# ── break it on purpose (§J.5) ────────────────────────────────────────────
#
# The suite above is green. These two prove it is CAPABLE of being red against
# the real schemas — that the builders can express a payload the schema accepts
# and one it refuses for the wrong reason, and that both are reported as
# failures rather than absorbed.


def test_a_control_whose_violating_payload_is_legal_is_reported_not_enforced() -> None:
    """A payment of exactly one paisa breaks nothing, so nothing refuses it."""
    finding = attribute(
        NegativeControl(
            "invented",
            clean=lambda: _journal_line(amount=Decimal("1180.00")),
            violating=lambda: _journal_line(amount=Decimal("0.01")),
        )
    )
    assert finding.attribution is Attribution.NOT_ENFORCED


def test_a_control_whose_clean_payload_is_refused_is_reported_invalid() -> None:
    """Both halves bolt a field onto a frozen schema, so BOTH are refused and
    the rejection cannot be attributed to anything the control claims to test.
    Reported loudly instead of counted as a pass."""
    finding = attribute(
        NegativeControl(
            "invented",
            clean=lambda: _validation(corrected_ledger="Office Equipment"),
            violating=lambda: _validation(corrected_amount="1180.00"),
        )
    )
    assert finding.attribution is Attribution.CONTROL_INVALID


def test_the_registry_refuses_a_control_for_a_rule_nobody_wrote_down() -> None:
    """Rebuilt from this module's own inventory, so the guard is proven against
    the real list rather than a toy one."""
    with pytest.raises(ValueError, match="not in the inventory"):
        Registry(
            PROHIBITIONS,
            (*CONTROLS, NegativeControl("unlisted", clean=_journal_line, violating=_journal_line)),
        )


# ── the fixed material, pinned ────────────────────────────────────────────
#
# WHY EVERY LITERAL IN EVERY BUILDER IS ASSERTED HERE.
#     A negative control only proves what the difference between its two halves
#     is. Everything the two halves SHARE is unexamined: change "Tally" to
#     "TALLY", `retry_count` from 0 to 1, or an identity from `_uuid("5")` to
#     `None`, and both halves move together, so the control still reports
#     ENFORCED and the suite stays green. Mutation testing found exactly that —
#     the shared payload was the largest unasserted surface in the repository.
#
#     The module docstring promises payloads that are FIXED: no clock, no
#     randomness, byte-identical across runs. That promise is only a promise
#     until something reads the values back. These tests read them back.
#
# WHAT THIS IS NOT.
#     Not a restatement of the schema — the schema is what refuses a payload,
#     and it is exercised by the controls. This is the fixture itself: the
#     specific words a clean payload is written in, the specific identities it
#     carries, and the specific numbers. Those are choices, and a choice that
#     nothing checks is a choice anybody can silently reverse.

_EVIDENCE_REFERENCE = "page 1, line 4"
_SOURCE_FILE = "invoice-2026-0041.pdf"
_RECEIPT_DATE = "the date the goods were received"
_RECEIPT_QUESTION = "On what date were the goods received?"
_OFFICE_EQUIPMENT = "Office Equipment"

#: `identity.py` chose v4 precisely because it encodes nothing (INV-9).
_UUID_VERSION_4 = 4


def test_the_envelope_carries_the_two_fixed_identities() -> None:
    """`_uuid("1")` and `_uuid("2")`, not `None` and not each other.

    `ArtifactId` is a frozen dataclass, and pydantic accepts an already-built
    dataclass instance without revalidating its field — so `ArtifactId(None)`
    reaches an artifact intact. Nothing but reading the value back catches it.
    """
    envelope = _envelope()
    assert envelope.artifact_id == ArtifactId(_uuid("1"))
    assert envelope.transaction_id == TransactionId(_uuid("2"))
    assert envelope.version == 1
    assert envelope.parent_versions == ()


def test_the_fixed_uuid_is_a_legal_v4_built_from_one_digit() -> None:
    """The version and variant nibbles are pinned deliberately; a stand-in that
    was not a legal v4 would be a different value no reader could see."""
    value = _uuid("a")
    assert value.version == _UUID_VERSION_4
    assert value.variant == uuid.RFC_4122
    assert str(value) == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert _uuid("b") != value


def test_the_provenance_names_the_document_and_the_line() -> None:
    provenance = _provenance()
    assert provenance.source_type is SourceType.DOCUMENT
    assert provenance.source_id == _SOURCE_FILE
    assert provenance.evidence_reference == _EVIDENCE_REFERENCE
    assert provenance.timestamp == datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    assert provenance.confidence == Decimal("0.9000")
    assert provenance.corroborated is Corroborated.NOT_ASSESSED


def test_the_detected_field_carries_the_amount_it_claims_to() -> None:
    field = _detected_field()
    assert field.name == "Amount"
    assert field.value == "1180.00"
    assert field.provenance == _provenance()


def test_the_structured_document_quotes_the_text_it_was_read_from() -> None:
    document = _structured_document()
    assert document.extracted_text == "INVOICE  Total 1,180.00"
    assert document.document_structure == "header, one table, footer"
    assert document.detected_tables == ()
    assert tuple(item.name for item in document.detected_fields) == ("Amount",)


def test_the_two_fixed_confidences_are_far_enough_apart_to_be_an_upgrade() -> None:
    """`NO_UPGRADED_SCORE` contrasts a reading's own confidence with what the
    Confidence Report claims about it, so the two numbers must differ — set
    them equal and both halves of that control become the same payload, which
    reports ENFORCED for nothing at all."""
    assert Decimal("0.9000") == _CONFIDENCE
    assert Decimal("0.4000") == _UNSURE
    assert _UNSURE < _CONFIDENCE


def test_the_confidence_report_says_why_the_reading_is_reliable() -> None:
    report = _confidence_report()
    assert report.reliability_information == "typed document, clean scan"
    assert report.uncertainty_markers == ()
    assert report.risky_fields == ()
    assert tuple(score.field_name for score in report.confidence_scores) == ("Amount",)


def test_the_evidence_object_names_its_document_and_its_source() -> None:
    evidence = _evidence()
    assert evidence.document_id == DocumentId(_uuid("3"))
    assert evidence.source_references == (_SOURCE_FILE,)
    assert evidence.human_business_context is None


def test_the_observed_fact_states_what_the_document_says_and_cites_it() -> None:
    fact = _fact()
    assert fact.statement == "The document states a total of 1,180.00."
    assert fact.stated_text == "Total  1,180.00"
    assert fact.evidence_references == (_EVIDENCE_REFERENCE,)


def test_the_unknown_names_the_gap_and_why_it_matters() -> None:
    unknown = _unknown()
    assert unknown.subject == _RECEIPT_DATE
    assert unknown.why_it_matters == (
        "Without it, the period this event belongs to cannot be settled."
    )


def test_the_conflict_carries_two_readings_that_actually_disagree() -> None:
    """Two DIFFERENT statements. Collapse them to one wording and the payload
    stops being a conflict, which is the whole thing `TWO_READINGS` tests."""
    conflict = _conflict()
    assert conflict.subject == "the total on the document"
    assert tuple(reading.statement for reading in conflict.competing_readings) == (
        "The printed total reads 1,180.00.",
        "The lines add up to 1,180.50.",
    )


def test_all_six_results_report_the_facts_they_are_supposed_to() -> None:
    """`RESULT_REPORTS` — no Result may omit what it found. A Result silently
    emptied here still constructs, because the control that tests the rule
    builds its own payload rather than reading this one."""
    results = _results()
    assert results.transaction.identified_event == (_fact(),)
    assert results.party.identified_entities == (_fact(),)
    assert results.item.identified_goods_and_services == (_fact(),)
    assert results.item.descriptions == (_fact(),)
    assert results.payment.amount_relationships == (_fact(),)
    assert results.timeline.dates == (_fact(),)
    assert results.business_context.context_clues == (_fact(),)
    assert results.transaction.unknown_information == ()
    for result in (
        results.transaction,
        results.party,
        results.item,
        results.payment,
        results.timeline,
        results.business_context,
    ):
        assert result.confidence == Decimal("0.9000")


def test_the_results_that_raise_an_unknown_keep_everything_else_intact() -> None:
    """The gap is ADDED, nothing is dropped for it. A Result that lost its facts
    while gaining an unknown would still satisfy `UNKNOWNS_INTACT`."""
    results = _results_raising_an_unknown()
    assert results.transaction.unknown_information == (_unknown(),)
    assert results.transaction.identified_event == (_fact(),)
    assert results.transaction.confidence == Decimal("0.9000")


def test_the_less_certain_results_differ_from_the_rest_in_exactly_one_place() -> None:
    """Five at 0.9000 and one at 0.7000, so `min` and `max` cannot coincide —
    which is the only reason `NO_FREE_CONFIDENCE` has anything to refuse."""
    results = _results_with_a_less_certain_one()
    assert results.payment.confidence == Decimal("0.7000")
    scores = {
        results.transaction.confidence,
        results.party.confidence,
        results.item.confidence,
        results.timeline.confidence,
        results.business_context.confidence,
    }
    assert scores == {Decimal("0.9000")}


def test_the_transaction_story_is_written_in_the_business_register() -> None:
    understanding = _understanding()
    assert understanding.transaction_story.narrative == (
        "Twelve units were delivered and paid for on the stated date."
    )
    assert understanding.identified_unknowns == ()


def test_the_journal_line_names_a_ledger_and_an_exact_amount() -> None:
    line = _journal_line()
    assert line.ledger == _OFFICE_EQUIPMENT
    assert line.amount == Decimal("1180.00")


def test_the_doubt_names_both_the_missing_fact_and_the_question() -> None:
    doubt = _doubt()
    assert doubt.missing_fact == _RECEIPT_DATE
    assert doubt.required_clarification == _RECEIPT_QUESTION


def test_the_decision_carries_the_treatment_and_the_two_sides_it_posts() -> None:
    decision = _decision()
    assert decision.decision_status is DecisionStatus.COMPLETE
    assert decision.accounting_treatment == "Purchase of office equipment"
    assert decision.ledger_classification == _OFFICE_EQUIPMENT
    assert decision.journal_structure == "one debit, one credit"
    assert decision.tax_treatment == "input credit claimed at the stated rate"
    assert decision.supporting_reasoning == (
        "The document names the item, the seller and the amount."
    )
    assert tuple(line.ledger for line in decision.debit_entries) == (_OFFICE_EQUIPMENT,)
    assert tuple(line.ledger for line in decision.credit_entries) == ("Bank",)
    assert decision.unresolved_doubts == ()


def test_the_incomplete_decision_posts_nothing_and_names_its_doubt() -> None:
    decision = _incomplete_decision()
    assert decision.decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED
    assert decision.debit_entries == ()
    assert decision.credit_entries == ()
    assert decision.unresolved_doubts == (_doubt(),)


def test_the_clarification_asks_one_question_about_one_decision() -> None:
    request = _clarification()
    assert request.clarification_id == ArtifactId(_uuid("4"))
    assert request.related_decision_id == ArtifactId(_uuid("5"))
    assert request.related_artifact_version == 1
    assert request.missing_information == (_RECEIPT_DATE,)
    assert request.required_clarification == _RECEIPT_QUESTION
    assert request.reason_clarification_is_required == (
        "The period the entry belongs to depends on it."
    )
    assert request.affected_decision == "the accounting period of the entry"
    assert request.supporting_evidence_references == (_EVIDENCE_REFERENCE,)
    assert request.detected_conflicts == ()


def test_the_finding_says_what_failed_why_and_what_to_do_next() -> None:
    finding = _finding()
    assert finding.what_failed == "the claimed input credit"
    assert finding.why_it_failed == "no evidence reference names the rate it was claimed at"
    assert finding.affected_artifact == "Accounting Decision"
    assert finding.recommended_next_step == "raise a clarification for the rate"
    assert finding.supporting_evidence_references == (_EVIDENCE_REFERENCE,)


def test_the_validation_decision_points_at_the_decision_it_judged() -> None:
    validation = _validation()
    assert validation.related_decision_id == ArtifactId(_uuid("5"))
    assert validation.related_artifact_version == 1
    assert validation.supporting_evidence_references == (_EVIDENCE_REFERENCE,)
    assert validation.validation_reasoning == ("every rule the decision was checked against passed")
    assert validation.validation_findings == ()


def test_the_execution_result_records_one_posting_to_one_destination() -> None:
    """Every one of these is a value a control shares with its violating twin,
    so nothing else in the suite would notice any of them changing."""
    execution = _execution()
    assert execution.execution_id == ExecutionId(_uuid("6"))
    assert execution.execution_attempt_id == ExecutionAttemptId(_uuid("7"))
    assert execution.accounting_decision_id == ArtifactId(_uuid("5"))
    assert execution.decision_version == 1
    assert execution.validation_decision_id == ArtifactId(_uuid("8"))
    assert execution.destination_system == "Tally"
    assert execution.corrects_execution_result is None
    assert execution.posting_status == "Posted"
    assert execution.external_transaction_ids == ("TALLY-88214",)
    assert execution.retry_count == 0
    assert execution.queue_status == "Drained"
    assert execution.notification_status == "Sent"
    assert execution.classified_error is None
    assert execution.audit_reference.execution_id == ExecutionId(_uuid("6"))
    assert execution.execution_outcome == "Success"


def test_the_execution_audit_reference_points_at_its_own_execution_by_default() -> None:
    """`AUDIT_POINTS_HOME` is only testable because the clean payload's audit
    reference and execution id are the SAME id. Drift them apart and the
    control's clean half becomes the violation it is supposed to contrast."""
    execution = _execution()
    assert execution.audit_reference.execution_id == execution.execution_id


# ── the immutability violation, examined directly ─────────────────────────
#
# `_mutate` is the violating half of all six INV-5 controls, and against a
# frozen model EVERY way of breaking it produces the same outcome: an
# exception. `setattr(None, ...)`, `getattr(model, None)`, writing `None`
# instead of the field's own value — all six controls stay green through all of
# them, because the control only asks WHETHER the payload was refused.
#
# So `_mutate` is exercised here against a model that is NOT frozen, where the
# three things it promises are separately visible: it writes the FIRST declared
# field, it writes that field's OWN value, and it returns the same object.


#: Deliberately mutable, so a write SUCCEEDS and can be inspected — every real
#: artifact is `frozen=True`, which refuses the write before it can be observed.
#:
#: Built with `create_model` rather than a `class` statement on purpose. A
#: subclass of `BaseModel` re-inherits `Any` from its base signature, and this
#: repository runs `disallow_any_explicit` and separately COUNTS suppressions,
#: blocking on any increase. A `type: ignore[explicit-any]` here would buy one
#: test at the cost of a gate.
_Writable = create_model("_Writable", first=(str, ...), second=(str, ...))


def test_mutate_writes_the_first_declared_field_back_to_its_own_value() -> None:
    model = _Writable(first="kept", second="untouched")
    returned = _mutate(model)
    assert returned is model
    # The whole model state, not two fields: a write that also touched
    # something else would slip past a pair of per-field checks.
    assert model.model_dump() == {"first": "kept", "second": "untouched"}


def test_mutate_writes_the_first_field_and_not_a_later_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `_mutate` that picked a different field would still trip `frozen=True`
    on all six artifacts, so only a direct probe can tell the two apart.

    `_mutate` assigns a field back to its OWN value, so no comparison of values
    can see it — the write itself is the only observable. Recorded by patching
    `__setattr__` on the existing class rather than by subclassing it: a
    subclass of a pydantic model re-inherits `Any` from its base signature and
    would need a `type: ignore[explicit-any]`, and this repository counts
    suppressions and blocks on any increase.

    The instance is built BEFORE the patch, so construction is not recorded and
    the single entry that remains is the one `_mutate` performed.
    """
    written: list[tuple[str, object]] = []
    model = _Writable(first="kept", second="untouched")
    original = type(model).__setattr__

    def record(instance: BaseModel, name: str, value: object) -> None:
        written.append((name, value))
        original(instance, name, value)

    monkeypatch.setattr(_Writable, "__setattr__", record)
    _mutate(model)

    assert written == [("first", "kept")], (
        "`_mutate` must write the FIRST declared field, once. Any other field, "
        "or more than one write, and the six INV-5 controls are probing "
        "something other than what they claim to probe."
    )


def test_mutate_still_refuses_to_write_a_frozen_artifact() -> None:
    """The property the six INV-5 controls actually rest on."""
    with pytest.raises(ValidationError):
        _mutate(_evidence())


# ── the two builders every entry in the inventory is made of ──────────────
#
# WHY THESE NEED THEIR OWN TESTS, WHEN 40 PROHIBITIONS ALREADY RUN THROUGH THEM.
#     They do not run through them — not while a test is running. `_predicate`
#     and `_review_only` are called exactly once each per entry, at MODULE
#     IMPORT, and `PROHIBITIONS` is a tuple of the results. By the time any test
#     executes, both functions are finished and nothing calls them again. Every
#     assertion in this file reads the tuple they already built.
#
#     That is invisible until the code inside them is changed, and then it is
#     total: swap `Enforcement.PREDICATE` for `None`, drop the `source=` keyword
#     entirely, and the whole suite stays green, because the altered line never
#     runs a second time. Measured, not assumed — 22 mutations of these two
#     functions survived a full mutation run with every other test in place.
#
#     So they are called here, directly, and the Prohibition they return is
#     compared field for field. A builder is a promise about what an entry is
#     made of, and this is the only place that promise is read back.

#: Deliberately unlike anything in the real inventory: a builder that ignored an
#: argument and substituted a constant would still match a fixture that happened
#: to resemble the entries around it.
_A_QUOTE = "a quote long enough to name the sentence it came from"
_ANOTHER_QUOTE = "a different sentence, quoted from a different line"
_A_REASON = "a reason no real exclusion gives, long enough to clear the floor"


def test_the_predicate_builder_keeps_every_field_and_marks_it_enforced_now() -> None:
    """`enforcement` is the field with no argument behind it — it is the whole
    reason this builder exists rather than a bare `Prohibition(...)`. Nothing
    else in the repository would notice it becoming `None`: a predicate carries
    no expiry, so `__post_init__` has nothing to object to and the malformed
    entry is filed silently."""
    assert _predicate(
        "SYSTEM_INVARIANTS:1/a-slug-no-real-entry-uses",
        _A_QUOTE,
        "docs/SYSTEM_INVARIANTS.md:1",
        "a subject no real entry names",
    ) == Prohibition(
        identifier="SYSTEM_INVARIANTS:1/a-slug-no-real-entry-uses",
        quote=_A_QUOTE,
        source="docs/SYSTEM_INVARIANTS.md:1",
        subject="a subject no real entry names",
        enforcement=Enforcement.PREDICATE,
        expiry=None,
    )


def test_the_review_only_builder_keeps_every_field_including_the_end_date() -> None:
    """The expiry is the only thing separating a review-only entry from a
    deletion written politely, and it is the one field the predicate builder
    does not take. It is asserted as the value passed in, not merely as
    not-None: an expiry pinned to a constant phase would outlive every entry
    that named a later one."""
    assert _review_only(
        "SYSTEM_BOUNDARIES:2/another-slug-no-real-entry-uses",
        _ANOTHER_QUOTE,
        "docs/SYSTEM_BOUNDARIES.md:2",
        "another subject no real entry names",
        "P5",
    ) == Prohibition(
        identifier="SYSTEM_BOUNDARIES:2/another-slug-no-real-entry-uses",
        quote=_ANOTHER_QUOTE,
        source="docs/SYSTEM_BOUNDARIES.md:2",
        subject="another subject no real entry names",
        enforcement=Enforcement.REVIEW_ONLY,
        expiry="P5",
    )


@pytest.mark.parametrize("expiry", sorted(PHASES))
def test_the_review_only_builder_passes_each_phase_through_unchanged(expiry: str) -> None:
    """Every declared phase, so no single hard-coded one can impersonate the
    argument."""
    assert _review_only("D:3/s", _A_QUOTE, "docs/DATA_FLOW.md:3", "a subject", expiry).expiry == (
        expiry
    )


def test_the_two_builders_disagree_about_exactly_one_field() -> None:
    """The enforcement, and nothing else. If they ever diverged elsewhere, the
    inventory would hold two shapes of entry and the counts above would be
    counting different things."""
    enforced = _predicate("D:4/s", _A_QUOTE, "docs/DATA_FLOW.md:4", "a subject")
    exempt = _review_only("D:4/s", _A_QUOTE, "docs/DATA_FLOW.md:4", "a subject", "P3")
    differing = {
        field.name
        for field in dataclasses.fields(enforced)
        if getattr(enforced, field.name) != getattr(exempt, field.name)
    }
    assert differing == {"enforcement", "expiry"}
    assert enforced.enforcement is Enforcement.PREDICATE
    assert exempt.enforcement is Enforcement.REVIEW_ONLY


def test_the_control_builder_keeps_both_payloads_and_declares_the_refusal() -> None:
    """`_control` runs 47 times at import and never again, so every mutation
    inside it survives unless something calls it directly. `refusal` is the
    field with no argument behind it — replace `(ValidationError,)` with
    `(Exception,)` and every control silently goes back to scoring crashes as
    enforcement while all 47 stay green."""
    clean = _evidence
    violating = _journal_line
    built = _control("D:5/s", clean=clean, violating=violating)
    assert built == NegativeControl(
        "D:5/s", clean=clean, violating=violating, refusal=(ValidationError,)
    )
    assert built.clean is clean
    assert built.violating is violating


def test_the_four_exclusion_builders_each_produce_their_own_kind() -> None:
    """Same import-time-only problem as the two prohibition builders. Each is
    asserted whole, by equality: a builder that dropped `reason` or swapped a
    kind would still produce a legal `Exclusion`, and 140 entries would quietly
    change meaning without one test going red."""
    assert _not_a_prohibition("docs/DATA_FLOW.md:6", _A_REASON) == Exclusion(
        source="docs/DATA_FLOW.md:6",
        kind=Uncovered.NOT_A_PROHIBITION,
        reason=_A_REASON,
        restates=None,
        expiry=None,
    )
    assert _restates("docs/DATA_FLOW.md:7", IMMUTABLE, _A_REASON) == Exclusion(
        source="docs/DATA_FLOW.md:7",
        kind=Uncovered.RESTATEMENT,
        reason=_A_REASON,
        restates=IMMUTABLE,
        expiry=None,
    )
    assert _unwitnessable("docs/DATA_FLOW.md:8", _A_REASON) == Exclusion(
        source="docs/DATA_FLOW.md:8",
        kind=Uncovered.UNWITNESSABLE,
        reason=_A_REASON,
        restates=None,
        expiry=None,
    )
    assert _not_yet("docs/DATA_FLOW.md:9", _A_REASON, "P6") == Exclusion(
        source="docs/DATA_FLOW.md:9",
        kind=Uncovered.NOT_YET_A_PREDICATE,
        reason=_A_REASON,
        restates=None,
        expiry="P6",
    )


@pytest.mark.parametrize("expiry", sorted(PHASES))
def test_the_debt_builder_passes_each_phase_through_unchanged(expiry: str) -> None:
    """Every declared phase, so no single hard-coded one can impersonate the
    argument and make every debt come due at the same time."""
    assert _not_yet("docs/DATA_FLOW.md:10", _A_REASON, expiry).expiry == expiry


def test_every_exclusion_in_the_real_list_matches_what_its_builder_produces() -> None:
    """Ties the direct tests above back to the live tuple, the same way the
    prohibitions are tied to theirs — so a builder that started dropping a field
    is caught against all 140 real entries, not only against the fixture."""
    rebuild = {
        Uncovered.NOT_A_PROHIBITION: lambda item: _not_a_prohibition(item.source, item.reason),
        Uncovered.RESTATEMENT: lambda item: _restates(
            item.source, item.restates or "", item.reason
        ),
        Uncovered.UNWITNESSABLE: lambda item: _unwitnessable(item.source, item.reason),
        Uncovered.NOT_YET_A_PREDICATE: lambda item: _not_yet(
            item.source, item.reason, item.expiry or ""
        ),
    }
    for item in EXCLUSIONS:
        assert rebuild[item.kind](item) == item, item.source


def test_every_entry_in_the_real_inventory_matches_what_its_builder_produces() -> None:
    """Ties the direct tests above back to the live tuple. Rebuilding each entry
    from its own recorded fields must reproduce it exactly — so a builder that
    started dropping a field would be caught against all 40 real entries, not
    only against the fixtures here."""
    for item in PROHIBITIONS:
        rebuilt = (
            _predicate(item.identifier, item.quote, item.source, item.subject)
            if item.enforcement is Enforcement.PREDICATE
            else _review_only(
                item.identifier,
                item.quote,
                item.source,
                item.subject,
                # `Registry` refuses a review-only entry with no expiry, so by
                # construction this is never None here.
                item.expiry or "",
            )
        )
        assert rebuilt == item, item.identifier


# ── the subject the rest of this file does not test ───────────────────────
#
# WHAT EVERY TEST ABOVE ACTUALLY MEASURES.
#     Whether six pydantic models refuse hand-written payloads. That is real —
#     the controls break the schema rules and the schemas say no — and it is a
#     DIFFERENT QUESTION from the one the gate's name implies. Nothing above
#     ever runs an engine. `conformance` can be green while the only engine
#     that exists emits an artifact that violates the contract governing it,
#     and on this commit that is exactly what happens.
#
# MEASURED, ON `pipeline.run`, ON THE EXACT FIXTURE BELOW — a real one-page PDF
# with a real text layer, run through cleaner, reader, parser, confidence and
# assembly:
#
#     detected_fields    : 0     detected_tables    : 0
#     confidence_scores  : 0     Provenance objects : 0
#     uncertainty_markers: 1
#     extracted_text     : 'TAX INVOICE\nVendor: Acme Traders\nTotal  1,180.00'
#
#     Three values reached the artifact. Not one carries where it came from or
#     how reliable it is, which is what
#     `COMMUNICATION_RULES_INPUT_ENGINE.md:113-119` requires of every extracted
#     value, permanently and at every boundary. `conformance` is GREEN.
#
# THESE TESTS ARE RED, AND THAT IS THE POINT.
#     The document wins (CLAUDE.md section M). The assertions state what the
#     contract requires, not what the pipeline currently produces, and they stay
#     that way until the emission side carries provenance. Weakening one to
#     match the code would convert a visible defect into a green gate, which is
#     the whole failure this file exists to prevent (Law 4, section J.4).
#
# WHY THEY LIVE HERE AND NOT IN THE REGISTRY.
#     `conformance_registry` is imported by the `conformance` job, which
#     installs `requirements-ci.txt` alone. Engine 1 needs OpenCV, PyMuPDF and
#     Docling; importing it there would break that job on a missing dependency
#     rather than on a real finding. This module runs under `unit tests`, where
#     those dependencies are installed.


class _AuthoringPage(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


_open_pdf = cast(_NewDocument, pymupdf.open)

#: The invoice is rendered FROM this list, so what reached the artifact can be
#: checked against real ground truth rather than against whatever a run
#: happened to produce.
_INVOICE_LINES = (
    "TAX INVOICE",
    "Vendor: Acme Traders",
    "Total  1,180.00",
)

#: `reader.read`'s own required threshold, at the value that means "never fall
#: back to vision". Zero, not a number chosen to look reasonable: the point of
#: this fixture is a PDF whose text layer is read directly, and any fallback
#: would make the result a statement about OCR instead.
_NO_VISION_FALLBACK = Decimal("0.0")

#: Mirrors `test_input_engine_pipeline.py`'s `RENDER_DPI`, which is the value
#: Engine 1's own end-to-end test renders at. Reusing an existing constant is
#: not choosing a number (CLAUDE.md Law 52), and rendering at a different one
#: would make this fixture a different experiment from that one.
_RENDER_DPI = 150


def _an_invoice_pdf() -> bytes:
    document = _open_pdf()
    page = document.new_page(width=595, height=842)
    height = 90.0
    for text in _INVOICE_LINES:
        page.insert_text((60, height), text, fontname="helv", fontsize=13)
        height += 34
    payload = bytes(document.tobytes())
    document.close()
    return payload


@pytest.fixture(scope="module")
def emitted_evidence() -> DocumentEvidenceObject:
    """One real run of Engine 1, shared by the tests below. Module-scoped
    because Docling's model load is the expensive part and the tests only read
    the result."""
    return pipeline.run(
        pipeline.DocumentIntake(
            document=_an_invoice_pdf(),
            media_type=reader.MediaType.PDF,
            source_references=("upload:invoice-2026-0041.pdf",),
        ),
        identity=IdentityEnvelope(
            artifact_id=ArtifactId(_uuid("1")),
            version=1,
            parent_versions=cast(tuple[ParentVersion, ...], ()),
            transaction_id=TransactionId(_uuid("2")),
        ),
        settings=pipeline.PipelineSettings(
            cleaner_settings=cleaner.CleanerSettings(
                max_deskew_degrees=15.0,
                denoise_strength=3.0,
                denoise_template_window=7,
                denoise_search_window=21,
                contrast_clip_limit=2.0,
                contrast_tile_grid=8,
                crop_margin_pixels=10,
                max_ink_loss_fraction=1.0,
            ),
            render_dpi=_RENDER_DPI,
            vision_fallback_threshold=_NO_VISION_FALLBACK,
            table_structure=cast(parser.TableStructureSettings | None, None),
        ),
    )


def test_the_engine_reads_the_document_at_all(
    emitted_evidence: DocumentEvidenceObject,
) -> None:
    """The precondition for everything below. If the engine read nothing, the
    two red tests that follow would be red for the wrong reason and would keep
    being red after the emission side was fixed."""
    text = emitted_evidence.structured_document.extracted_text
    for line in _INVOICE_LINES:
        assert line in text, f"the engine did not read {line!r}; it read {text!r}"


def test_every_value_the_engine_extracted_carries_where_it_came_from(
    emitted_evidence: DocumentEvidenceObject,
) -> None:
    """`COMMUNICATION_RULES_INPUT_ENGINE.md:113-117` — every extracted value
    maintains its Source, its Confidence and its Uncertainty, and :119 says
    those travel with the value permanently.

    RED. The engine reads the invoice and emits its text with no detected
    field behind any of it, so there is no value carrying a source at all.
    Fixing this means emitting provenance, never relaxing the assertion.
    """
    document = emitted_evidence.structured_document
    assert document.extracted_text.strip(), "nothing was read, so nothing is being judged"
    assert document.detected_fields, (
        "the engine stated extracted text but emitted zero detected fields, so not "
        "one extracted value carries a Source, a Confidence or an Uncertainty. "
        f"COMMUNICATION_RULES_INPUT_ENGINE.md:113. Text emitted: "
        f"{document.extracted_text[:120]!r}"
    )
    scored = {score.field_name for score in emitted_evidence.confidence_report.confidence_scores}
    for field in document.detected_fields:
        assert field.provenance.source_id.strip(), f"{field.name} names no source document"
        assert field.provenance.evidence_reference.strip(), f"{field.name} names no location"
        assert field.name in scored, f"{field.name} carries no confidence score"


def test_the_artifact_carries_provenance_for_the_evidence_it_states(
    emitted_evidence: DocumentEvidenceObject,
) -> None:
    """`COMMUNICATION_RULES_INPUT_ENGINE.md:158` item 8 — evidence provenance
    crosses intact, with every fact.

    RED. The emitted artifact contains zero `Provenance` objects when no human
    note is supplied: there is nothing for the Understanding Engine to carry
    intact, so the boundary contract's uncertainty-movement clause is vacuous
    on this commit.
    """
    provenances = [
        field.provenance for field in emitted_evidence.structured_document.detected_fields
    ]
    provenances += [
        table.provenance for table in emitted_evidence.structured_document.detected_tables
    ]
    if emitted_evidence.human_business_context is not None:
        provenances.append(emitted_evidence.human_business_context.provenance)
    assert provenances, (
        "the artifact carries no Provenance anywhere, so nothing crosses the "
        "Input -> Understanding boundary with an origin attached. "
        "COMMUNICATION_RULES_INPUT_ENGINE.md:158."
    )
    for provenance in provenances:
        assert provenance.source_type is SourceType.DOCUMENT
        assert provenance.corroborated is Corroborated.NOT_ASSESSED
