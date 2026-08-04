"""The conformance harness, attacked.

This module decides whether every other conformance result can be believed, so
the tests that matter most are the ones that try to make it report a PASS it
did not earn — a control that never reached the rule it names, a rule with
nothing exercising it, an exemption with no end date.
"""

from __future__ import annotations

import pytest

from accountant_dad.conformance import (
    PHASES,
    Attribution,
    Enforcement,
    Finding,
    NegativeControl,
    Prohibition,
    Registry,
    attribute,
)

SOURCE = "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:467"


def rule(
    identifier: str = "ENGINE_5:467/no-approval-while-critical-stands",
    *,
    enforcement: Enforcement = Enforcement.PREDICATE,
    expiry: str | None = None,
    source: str = SOURCE,
) -> Prohibition:
    return Prohibition(
        identifier=identifier,
        quote="No approval exists while a Critical finding remains.",
        source=source,
        subject="Validation Engine",
        enforcement=enforcement,
        expiry=expiry,
    )


def boom() -> object:
    raise ValueError("refused")


def fine() -> object:
    return object()


# ── a prohibition must be re-checkable ────────────────────────────────────


def test_a_prohibition_records_the_line_it_came_from() -> None:
    assert rule().source == SOURCE


@pytest.mark.parametrize("field", ["identifier", "quote", "source", "subject"])
def test_a_prohibition_with_a_blank_field_is_refused(field: str) -> None:
    supplied = {
        "identifier": "x",
        "quote": "y",
        "source": SOURCE,
        "subject": "z",
        "enforcement": Enforcement.PREDICATE,
    }
    supplied[field] = "   "
    with pytest.raises(ValueError, match="needs a"):
        Prohibition(**supplied)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source",
    ["docs/SYSTEM_INVARIANTS.md", "SYSTEM_BOUNDARIES", "a whole document"],
)
def test_a_prohibition_attributed_to_a_whole_document_is_refused(source: str) -> None:
    """A rule with no line cannot be re-checked when the document changes, and
    an inventory that cannot be re-checked stops describing the system the
    moment anyone edits a spec."""
    with pytest.raises(ValueError, match="must name a line"):
        rule(source=source)


def test_a_line_number_is_enough_to_be_re_checkable() -> None:
    assert rule(source="docs/DATA_FLOW.md:693").source.endswith(":693")


# ── an exemption must have an end date ────────────────────────────────────


def test_a_review_only_rule_with_no_expiry_is_refused() -> None:
    """An exemption with no end date is a deletion written politely."""
    with pytest.raises(ValueError, match="must name the phase"):
        rule(enforcement=Enforcement.REVIEW_ONLY)


@pytest.mark.parametrize("bad", ["P1", "P7", "later", "soon", "", "p4"])
def test_a_review_only_rule_with_a_non_phase_expiry_is_refused(bad: str) -> None:
    """`P1` is refused too: it is behind us, so it is not an end date."""
    with pytest.raises(ValueError, match="is not a phase"):
        rule(enforcement=Enforcement.REVIEW_ONLY, expiry=bad)


@pytest.mark.parametrize("phase", sorted(PHASES))
def test_every_declared_phase_is_accepted_as_an_expiry(phase: str) -> None:
    assert rule(enforcement=Enforcement.REVIEW_ONLY, expiry=phase).expiry == phase


def test_a_predicate_cannot_carry_an_expiry() -> None:
    """A predicate is enforced NOW. An expiry on it means one of the two labels
    is wrong, and the wrong one would be silently believed."""
    with pytest.raises(ValueError, match="cannot carry"):
        rule(expiry="P4")


def test_there_are_exactly_two_ways_to_hold_a_prohibition() -> None:
    """A third would be somewhere for an untested rule to hide."""
    assert set(Enforcement) == {Enforcement.PREDICATE, Enforcement.REVIEW_ONLY}


# ── attribution ───────────────────────────────────────────────────────────


def test_a_rule_is_enforced_when_the_clean_builds_and_the_violating_is_refused() -> None:
    finding = attribute(NegativeControl("r", violating=boom, clean=fine))
    assert finding.attribution is Attribution.ENFORCED
    assert finding.is_pass


def test_a_rule_is_not_enforced_when_the_violating_payload_is_accepted() -> None:
    finding = attribute(NegativeControl("r", violating=fine, clean=fine))
    assert finding.attribution is Attribution.NOT_ENFORCED
    assert not finding.is_pass


def test_a_control_whose_clean_payload_also_fails_is_not_a_pass() -> None:
    """The false green this module exists to stop. Both halves raise, so the
    rejection cannot be attributed to the rule under test — and a suite of such
    controls is all green and proves nothing."""
    finding = attribute(NegativeControl("r", violating=boom, clean=boom))
    assert finding.attribution is Attribution.CONTROL_INVALID
    assert not finding.is_pass


def test_an_invalid_control_says_the_clean_payload_was_the_problem() -> None:
    finding = attribute(NegativeControl("r", violating=boom, clean=boom))
    assert "clean payload was refused too" in finding.detail


# ── the detail a human acts on, pinned word for word ──────────────────────
#
# A `Finding` carries THREE things and only two of them are types. `detail` is
# the one a person reads to decide what to do next, and a substring match
# ("clean payload was refused too" in ...) leaves the rest of the sentence
# unexamined — including the part that names WHICH exception refused, which is
# the only diagnostic the finding carries. Equality is the assertion; anything
# looser lets the name of the refusing exception be replaced wholesale without
# a single test going red.


def test_an_invalid_control_names_the_exception_that_refused_the_clean_payload() -> None:
    """`type(refused).__name__`, not a fixed word. Replace the lookup with a
    constant and the finding still reads like a diagnosis while naming a class
    that never ran."""
    finding = attribute(NegativeControl("r", violating=boom, clean=boom))
    assert finding.detail == (
        "the clean payload was refused too, so a rejection cannot be "
        "attributed to this rule: ValueError: refused"
    )


def test_an_enforced_finding_names_the_exception_that_did_the_refusing() -> None:
    """The only evidence a passing control leaves behind. If this string stops
    naming the real exception, every ENFORCED finding in the suite becomes
    unattributable while staying green."""
    finding = attribute(NegativeControl("r", violating=boom, clean=fine))
    assert finding.detail == "refused by ValueError"


def test_a_finding_that_nothing_enforces_says_the_payload_was_accepted() -> None:
    finding = attribute(NegativeControl("r", violating=fine, clean=fine))
    assert finding.detail == (
        "the violating payload was accepted; nothing enforces this prohibition"
    )


def test_the_clean_payload_is_tried_before_the_violating_one() -> None:
    """Order is load-bearing. Running `violating` first would let a broken
    control report a rejection it did not cause."""
    order: list[str] = []

    def clean() -> object:
        order.append("clean")
        return object()

    def violating() -> object:
        order.append("violating")
        raise ValueError("refused")

    attribute(NegativeControl("r", violating=violating, clean=clean))
    assert order == ["clean", "violating"]


def test_a_broken_control_never_runs_the_violating_payload() -> None:
    ran: list[str] = []

    def violating() -> object:
        ran.append("violating")
        raise ValueError("refused")

    attribute(NegativeControl("r", violating=violating, clean=boom))
    assert ran == []


@pytest.mark.parametrize("blast", [TypeError, KeyError, RuntimeError, AttributeError])
def test_any_refusal_counts_as_enforcement_not_only_a_validation_error(
    blast: type[Exception],
) -> None:
    """Insisting on ValidationError would silently exempt every rule enforced by
    a frozen dataclass, which raises a plain TypeError."""

    def violating() -> object:
        raise blast("refused")

    finding = attribute(NegativeControl("r", violating=violating, clean=fine))
    assert finding.is_pass
    # The name is read off the exception that actually ran, per type. A detail
    # that named one fixed class would pass a single-exception test and lie
    # about the other three.
    assert finding.detail == f"refused by {blast.__name__}"


@pytest.mark.parametrize("blast", [TypeError, KeyError, RuntimeError])
def test_any_refusal_of_the_clean_payload_invalidates_the_control(
    blast: type[Exception],
) -> None:
    def clean() -> object:
        raise blast("refused")

    finding = attribute(NegativeControl("r", violating=boom, clean=clean))
    assert finding.attribution is Attribution.CONTROL_INVALID
    # `KeyError` renders its argument with quotes; that is the exception's own
    # repr and is asserted as-is rather than normalised away.
    assert finding.detail == (
        "the clean payload was refused too, so a rejection cannot be "
        f"attributed to this rule: {blast.__name__}: {blast('refused')}"
    )


def test_only_enforced_counts_as_a_pass() -> None:
    passes = {outcome for outcome in Attribution if Finding("r", outcome, "").is_pass}
    assert passes == {Attribution.ENFORCED}


# ── the registry keeps the inventory honest ───────────────────────────────


def test_two_prohibitions_may_not_share_an_identifier() -> None:
    """Attribution would name a rule that is not unique."""
    with pytest.raises(ValueError, match="share the identifier"):
        Registry([rule("same"), rule("same")], [])


def test_a_control_for_a_rule_not_in_the_inventory_is_refused() -> None:
    """A control for an unlisted rule proves nothing about the specification —
    and would inflate the pass count with a rule nobody wrote down."""
    with pytest.raises(ValueError, match="not in the inventory"):
        Registry([rule("listed")], [NegativeControl("unlisted", violating=boom, clean=fine)])


def test_a_control_against_a_review_only_rule_is_refused() -> None:
    """If it can be tested it is not review-only, and if it cannot the control
    does not test it. Either way one of the two labels is wrong."""
    listed = rule("r", enforcement=Enforcement.REVIEW_ONLY, expiry="P4")
    with pytest.raises(ValueError, match="review-only"):
        Registry([listed], [NegativeControl("r", violating=boom, clean=fine)])


# ── what the registry SAYS when it refuses ────────────────────────────────
#
# `pytest.raises(match=...)` above proves only that a substring survived. Each
# of these three refusals is the sole notice a maintainer gets that the
# inventory is malformed, and each names the offending rule — so the assertion
# is the whole sentence, including the identifier, by equality. Everything a
# `match=` leaves unread is a sentence anyone can rewrite into nonsense with
# the suite still green.


def test_the_duplicate_refusal_names_the_shared_identifier_and_why_it_matters() -> None:
    with pytest.raises(ValueError) as raised:
        Registry([rule("same"), rule("same")], [])
    assert str(raised.value) == (
        "two prohibitions share the identifier 'same'; "
        "attribution would name a rule that is not unique"
    )


def test_the_unlisted_control_refusal_names_the_rule_nobody_wrote_down() -> None:
    with pytest.raises(ValueError) as raised:
        Registry([rule("listed")], [NegativeControl("unlisted", violating=boom, clean=fine)])
    assert str(raised.value) == (
        "a control names 'unlisted', which is not in the inventory; a control "
        "for an unlisted rule proves nothing about the specification"
    )


def test_the_review_only_refusal_names_the_rule_and_both_ways_it_could_be_wrong() -> None:
    """Both halves of the diagnosis are load-bearing: a maintainer has to be
    told that EITHER the label or the control is wrong, or the obvious repair
    is to delete whichever one is easier to delete."""
    listed = rule("r", enforcement=Enforcement.REVIEW_ONLY, expiry="P4")
    with pytest.raises(ValueError) as raised:
        Registry([listed], [NegativeControl("r", violating=boom, clean=fine)])
    assert str(raised.value) == (
        "'r' is listed review-only but has a negative control. One of the two "
        "is wrong — either it is testable and should be a predicate, or the "
        "control does not test it."
    )


def test_a_predicate_with_no_control_is_reported_as_untested() -> None:
    """P2 is not done while this is non-empty. A rule declared enforced with
    nothing exercising it is a claim, not an enforcement."""
    registry = Registry(
        [rule("tested"), rule("bare")], [NegativeControl("tested", violating=boom, clean=fine)]
    )
    assert registry.untested_predicates() == ("bare",)


def test_review_only_rules_are_not_counted_as_untested_predicates() -> None:
    registry = Registry([rule("r", enforcement=Enforcement.REVIEW_ONLY, expiry="P4")], [])
    assert registry.untested_predicates() == ()


def test_the_registry_exposes_the_inventory_it_was_given() -> None:
    """The inventory must be readable to be published. A registry that can only
    be run, never listed, cannot produce the document P2 requires."""
    listed = [rule("a"), rule("b")]
    controls = [NegativeControl("a", violating=boom, clean=fine)]
    registry = Registry(listed, controls)
    assert [item.identifier for item in registry.prohibitions] == ["a", "b"]
    assert [item.prohibition for item in registry.controls] == ["a"]


def test_the_registry_separates_the_two_kinds() -> None:
    registry = Registry(
        [rule("a"), rule("b", enforcement=Enforcement.REVIEW_ONLY, expiry="P5")], []
    )
    assert [item.identifier for item in registry.by_enforcement(Enforcement.PREDICATE)] == ["a"]
    assert [item.identifier for item in registry.by_enforcement(Enforcement.REVIEW_ONLY)] == ["b"]


def test_running_the_registry_reports_one_finding_per_control() -> None:
    registry = Registry(
        [rule("a"), rule("b")],
        [
            NegativeControl("a", violating=boom, clean=fine),
            NegativeControl("b", violating=fine, clean=fine),
        ],
    )
    assert [finding.prohibition for finding in registry.run()] == ["a", "b"]


def test_failures_reports_only_what_did_not_pass() -> None:
    registry = Registry(
        [rule("enforced"), rule("open"), rule("broken")],
        [
            NegativeControl("enforced", violating=boom, clean=fine),
            NegativeControl("open", violating=fine, clean=fine),
            NegativeControl("broken", violating=boom, clean=boom),
        ],
    )
    assert {finding.prohibition: finding.attribution for finding in registry.failures()} == {
        "open": Attribution.NOT_ENFORCED,
        "broken": Attribution.CONTROL_INVALID,
    }


def test_the_run_order_is_the_inventory_order_so_two_runs_diff_cleanly() -> None:
    controls = [NegativeControl(name, violating=boom, clean=fine) for name in ("c", "a", "b")]
    registry = Registry([rule("c"), rule("a"), rule("b")], controls)
    assert [finding.prohibition for finding in registry.run()] == ["c", "a", "b"]


def test_an_empty_registry_is_legal_and_reports_nothing() -> None:
    """It must be constructible before the inventory exists, or the inventory
    could never be added one rule at a time."""
    registry = Registry([], [])
    assert registry.run() == ()
    assert registry.untested_predicates() == ()


def test_a_prohibition_cannot_be_edited_after_it_is_recorded() -> None:
    listed = rule()
    with pytest.raises((AttributeError, TypeError)):
        listed.enforcement = Enforcement.REVIEW_ONLY  # type: ignore[misc]


def test_a_control_cannot_be_edited_after_it_is_registered() -> None:
    control = NegativeControl("r", violating=boom, clean=fine)
    with pytest.raises((AttributeError, TypeError)):
        control.clean = boom  # type: ignore[misc]
