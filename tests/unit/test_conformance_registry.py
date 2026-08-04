"""The inventory, attacked.

`test_conformance.py` proves the HARNESS cannot report a pass it did not earn.
This file asks the next question: is the inventory the harness runs actually
about the documents it claims to be about, and does every control really reach
the rule it names?

Three things are checked here that nothing else in the repository checks:

  THE CLEAN HALF RUNS. Every control's clean payload is constructed against the
  real frozen schema. A control whose clean half fails is `CONTROL_INVALID` and
  is NOT a pass — the payload died of some other defect and the rule under test
  was never reached. A suite of those is all green and worth nothing.

  THE CITATIONS STILL READ THE WAY THEY ARE QUOTED. Every `source` is opened,
  the line is read, and the `quote` must appear in it verbatim. A comment
  cannot catch a citation that drifted when somebody edited a spec; only
  reading the file can. The check is itself mutation-proven below — a citation
  moved by one line must be rejected, or the check is decoration.

  THE COUNTS ARE WRITTEN DOWN. Predicates, review-only entries and controls are
  asserted as explicit numbers. Deleting a control is otherwise the cheapest
  way to make this suite green, and it would leave no trace at all.

These tests may read files. `conformance_registry` itself may not — see its
module docstring on why the payloads carry no clock and no randomness.
"""

from __future__ import annotations

import dataclasses
import pathlib
from decimal import Decimal

import pytest

import accountant_dad
from accountant_dad.conformance import (
    Attribution,
    Enforcement,
    NegativeControl,
    Prohibition,
    Registry,
    attribute,
)
from accountant_dad.conformance_registry import (
    CONTROLS,
    IMMUTABLE,
    PROHIBITIONS,
    REGISTRY,
    _journal_line,
    _validation,
)

#: Explicit, so a silent deletion is a red test rather than a smaller number
#: nobody notices. Raising these is normal; lowering one is a claim that a rule
#: stopped needing proof, and that claim has to be made out loud.
PREDICATE_COUNT = 33
REVIEW_ONLY_COUNT = 7
CONTROL_COUNT = 43

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


def _line(source: str) -> str:
    """The one line `source` names, read off disk. `path:line`, 1-based."""
    path, _, number = source.rpartition(":")
    body = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    return body[int(number) - 1]


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
