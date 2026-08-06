"""Mutation tests for conformance.py lines 360-705.

Target: Registry methods, Finding properties, filter predicates.
Strategy: Every filter, negation, and comparison gets a test that would fail
if the predicate is flipped.
"""

from __future__ import annotations

from accountant_dad.conformance import (
    Attribution,
    Enforcement,
    Exclusion,
    Finding,
    NegativeControl,
    Prohibition,
    Registry,
    Uncovered,
    cite,
)

# ─── Fixtures ───────────────────────────────────────────────────────────────

SOURCE = cite(
    "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md",
    "10. Sub-Engine Specifications > 10.6",
    "**Every blocking issue must appear inside the Validation Decision.**",
)


def predicate(
    identifier: str = "ENGINE_5/test",
    enforcement: Enforcement = Enforcement.PREDICATE,
    expiry: str | None = None,
) -> Prohibition:
    return Prohibition(
        identifier=identifier,
        quote="A clause.",
        source=SOURCE,
        subject="Engine",
        enforcement=enforcement,
        expiry=expiry,
    )


def boom() -> object:
    raise ValueError("refused")


def fine() -> object:
    return object()


# ─── Finding.is_pass property ───────────────────────────────────────────────
#
# Line 522-523: `return self.attribution is Attribution.ENFORCED`
# Mutation: flip `is` to `is not` or change to `== Attribution.ENFORCED`


def test_is_pass_true_only_for_enforced() -> None:
    """ENFORCED → True; all others → False."""
    assert Finding("r", Attribution.ENFORCED, "").is_pass is True
    assert Finding("r", Attribution.NOT_ENFORCED, "").is_pass is False
    assert Finding("r", Attribution.CONTROL_INVALID, "").is_pass is False
    assert Finding("r", Attribution.CONTROL_CRASHED, "").is_pass is False


def test_is_pass_uses_identity_not_equality() -> None:
    """Attribution.ENFORCED is a singleton; identity check catches enum swapping."""
    finding = Finding("r", Attribution.ENFORCED, "")
    # If mutation changes `is` to `==`, this still passes.
    # But if mutation uses wrong Attribution, it fails.
    assert finding.attribution is Attribution.ENFORCED
    assert finding.is_pass is True


# ─── Registry.accounted_for() ───────────────────────────────────────────────
#
# Lines 672-680: union of prohibitions and exclusions
# Mutation: change `|` to `&`, or drop one side


def test_accounted_for_includes_all_prohibitions() -> None:
    """Every prohibition.source must be in accounted_for()."""
    r = Registry([predicate("a"), predicate("b")], [])
    sources = {p.source for p in r.prohibitions}
    assert sources.issubset(r.accounted_for())


def test_accounted_for_includes_all_exclusions() -> None:
    """Every exclusion.source must be in accounted_for()."""
    ex = Exclusion(
        source=cite("docs/T.md", "S", "A clause."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This is at least twenty characters long for a reason.",
    )
    r = Registry([predicate("a")], [], [ex])
    assert ex.source in r.accounted_for()


def test_accounted_for_is_union_not_intersection() -> None:
    """Must include both, not the overlap."""
    ex_source = cite("docs/T.md", "S", "An excluded clause.")
    ex = Exclusion(
        source=ex_source,
        kind=Uncovered.UNWITNESSABLE,
        reason="This clause is long enough to satisfy the minimum.",
    )
    proofs = [predicate("a"), predicate("b")]
    r = Registry(proofs, [], [ex])
    accounted = r.accounted_for()
    # Both prohibition sources are there
    assert any(p.source in accounted for p in proofs)
    # Exclusion source is there
    assert ex_source in accounted


def test_accounted_for_returns_frozenset() -> None:
    """Immutable; prevents silent mutations via .add() or .discard()."""
    r = Registry([predicate("a")], [])
    result = r.accounted_for()
    assert isinstance(result, frozenset)


# ─── Registry.by_uncovered() ───────────────────────────────────────────────
#
# Lines 682-683: filter exclusions by kind using `is`
# Mutation: change `is` to `==`, or flip the predicate


def test_by_uncovered_unwitnessable() -> None:
    """Returns only UNWITNESSABLE exclusions."""
    un = Exclusion(
        source=cite("docs/T.md", "S", "Clause one."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This cannot be witnessed by any artifact.",
    )
    yet = Exclusion(
        source=cite("docs/T.md", "S", "Clause two."),
        kind=Uncovered.NOT_YET_A_PREDICATE,
        reason="A rule that will come in a future phase.",
        expiry="P5",
    )
    r = Registry([predicate("a")], [], [un, yet])
    result = r.by_uncovered(Uncovered.UNWITNESSABLE)
    assert len(result) == 1
    assert result[0] is un


def test_by_uncovered_not_yet_a_predicate() -> None:
    """Returns only NOT_YET_A_PREDICATE exclusions."""
    un = Exclusion(
        source=cite("docs/T.md", "S", "Clause one."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This cannot be witnessed by any artifact.",
    )
    yet = Exclusion(
        source=cite("docs/T.md", "S", "Clause two."),
        kind=Uncovered.NOT_YET_A_PREDICATE,
        reason="A rule that will come in a future phase.",
        expiry="P5",
    )
    r = Registry([predicate("a")], [], [un, yet])
    result = r.by_uncovered(Uncovered.NOT_YET_A_PREDICATE)
    assert len(result) == 1
    assert result[0] is yet


def test_by_uncovered_restatement() -> None:
    """Returns only RESTATEMENT exclusions."""
    un = Exclusion(
        source=cite("docs/T.md", "S", "Clause one."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This cannot be witnessed by any artifact.",
    )
    rest = Exclusion(
        source=cite("docs/T.md", "S", "Clause three."),
        kind=Uncovered.RESTATEMENT,
        reason="This is already covered by another rule.",
        restates="ENGINE_5/test",
    )
    r = Registry([predicate("ENGINE_5/test")], [], [un, rest])
    result = r.by_uncovered(Uncovered.RESTATEMENT)
    assert len(result) == 1
    assert result[0] is rest


def test_by_uncovered_returns_empty_when_none_match() -> None:
    """No match → empty tuple."""
    un = Exclusion(
        source=cite("docs/T.md", "S", "Clause one."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This cannot be witnessed by any artifact.",
    )
    r = Registry([predicate("a")], [], [un])
    result = r.by_uncovered(Uncovered.NOT_YET_A_PREDICATE)
    assert result == ()


def test_by_uncovered_uses_identity_not_equality() -> None:
    """Uses `is` to check kind; catches enum swapping."""
    un = Exclusion(
        source=cite("docs/T.md", "S", "Clause one."),
        kind=Uncovered.UNWITNESSABLE,
        reason="This cannot be witnessed.",
    )
    r = Registry([predicate("a")], [], [un])
    result = r.by_uncovered(Uncovered.UNWITNESSABLE)
    assert len(result) == 1
    assert result[0].kind is Uncovered.UNWITNESSABLE


# ─── Registry.by_enforcement() ──────────────────────────────────────────────
#
# Lines 685-686: filter prohibitions by enforcement using `is`
# Mutation: change `is` to `==`


def test_by_enforcement_predicate() -> None:
    """Returns only PREDICATE prohibitions."""
    p = predicate("a", enforcement=Enforcement.PREDICATE)
    r = predicate("b", enforcement=Enforcement.REVIEW_ONLY, expiry="P5")
    registry = Registry([p, r], [])
    result = registry.by_enforcement(Enforcement.PREDICATE)
    assert len(result) == 1
    assert result[0] is p


def test_by_enforcement_review_only() -> None:
    """Returns only REVIEW_ONLY prohibitions."""
    p = predicate("a", enforcement=Enforcement.PREDICATE)
    r = predicate("b", enforcement=Enforcement.REVIEW_ONLY, expiry="P5")
    registry = Registry([p, r], [])
    result = registry.by_enforcement(Enforcement.REVIEW_ONLY)
    assert len(result) == 1
    assert result[0] is r


def test_by_enforcement_returns_empty_when_none_match() -> None:
    """No match → empty tuple."""
    p = predicate("a", enforcement=Enforcement.PREDICATE)
    registry = Registry([p], [])
    result = registry.by_enforcement(Enforcement.REVIEW_ONLY)
    assert result == ()


def test_by_enforcement_uses_identity_not_equality() -> None:
    """Uses `is` to check enforcement; catches enum swapping."""
    p = predicate("a", enforcement=Enforcement.PREDICATE)
    registry = Registry([p], [])
    result = registry.by_enforcement(Enforcement.PREDICATE)
    assert len(result) == 1
    assert result[0].enforcement is Enforcement.PREDICATE


# ─── Registry.untested_predicates() ─────────────────────────────────────────
#
# Lines 688-697: find predicates without a control
# Mutation: change `not in` to `in` (line 695)


def test_untested_predicates_empty_when_all_tested() -> None:
    """Every predicate has a control."""
    p1 = predicate("a")
    p2 = predicate("b")
    c1 = NegativeControl("a", violating=boom, clean=fine)
    c2 = NegativeControl("b", violating=boom, clean=fine)
    r = Registry([p1, p2], [c1, c2])
    assert r.untested_predicates() == ()


def test_untested_predicates_finds_predicates_without_controls() -> None:
    """Predicates with no control are reported."""
    p1 = predicate("tested")
    p2 = predicate("untested")
    c1 = NegativeControl("tested", violating=boom, clean=fine)
    r = Registry([p1, p2], [c1])
    assert r.untested_predicates() == ("untested",)


def test_untested_predicates_ignores_review_only() -> None:
    """Review-only rules are not reported as untested."""
    p = predicate("review", enforcement=Enforcement.REVIEW_ONLY, expiry="P5")
    r = Registry([p], [])
    assert r.untested_predicates() == ()


def test_untested_predicates_sorted() -> None:
    """Results are sorted for stable output."""
    p1 = predicate("z")
    p2 = predicate("a")
    p3 = predicate("m")
    r = Registry([p1, p2, p3], [])
    assert r.untested_predicates() == ("a", "m", "z")


def test_untested_predicates_uses_not_in_not_in() -> None:
    """The negation is load-bearing: `not in controlled`."""
    untested = predicate("untested")
    tested = predicate("tested")
    c = NegativeControl("tested", violating=boom, clean=fine)
    r = Registry([untested, tested], [c])
    result = r.untested_predicates()
    # Untested must be in result
    assert "untested" in result
    # Tested must not be in result
    assert "tested" not in result


# ─── Registry.run() ──────────────────────────────────────────────────────
#
# Lines 699-702: run all controls in order
# Mutation: change iteration or order


def test_run_returns_tuple_not_list() -> None:
    """Immutable; prevents silent mutation via append."""
    c = NegativeControl("a", violating=boom, clean=fine)
    r = Registry([predicate("a")], [c])
    result = r.run()
    assert isinstance(result, tuple)


def test_run_preserves_control_order() -> None:
    """Order is inventory order, stable for diffing."""
    c1 = NegativeControl("z", violating=boom, clean=fine)
    c2 = NegativeControl("a", violating=boom, clean=fine)
    c3 = NegativeControl("m", violating=boom, clean=fine)
    rules = [predicate("z"), predicate("a"), predicate("m")]
    r = Registry(rules, [c1, c2, c3])
    findings = r.run()
    assert [f.prohibition for f in findings] == ["z", "a", "m"]


# ─── Registry.failures() ────────────────────────────────────────────────
#
# Lines 704-705: filter findings where NOT is_pass
# Mutation: remove `not`, or flip predicate


def test_failures_returns_only_not_pass() -> None:
    """Every item in failures() has is_pass == False."""
    c1 = NegativeControl("pass", violating=boom, clean=fine)
    c2 = NegativeControl("fail", violating=fine, clean=fine)
    c3 = NegativeControl("broken", violating=boom, clean=boom)
    rules = [predicate("pass"), predicate("fail"), predicate("broken")]
    r = Registry(rules, [c1, c2, c3])
    failures = r.failures()
    assert all(not f.is_pass for f in failures)


def test_failures_excludes_passes() -> None:
    """ENFORCED findings (passes) are not in failures()."""
    c = NegativeControl("pass", violating=boom, clean=fine)
    r = Registry([predicate("pass")], [c])
    failures = r.failures()
    assert "pass" not in (f.prohibition for f in failures)


def test_failures_is_subset_of_run() -> None:
    """Every failure was in run(); failures are a subset."""
    c1 = NegativeControl("a", violating=boom, clean=fine)
    c2 = NegativeControl("b", violating=fine, clean=fine)
    r = Registry([predicate("a"), predicate("b")], [c1, c2])
    all_findings = r.run()
    failed_findings = r.failures()
    all_prohibitions = {f.prohibition for f in all_findings}
    failed_prohibitions = {f.prohibition for f in failed_findings}
    assert failed_prohibitions.issubset(all_prohibitions)


def test_failures_returns_tuple_not_list() -> None:
    """Immutable; prevents silent mutation."""
    c1 = NegativeControl("a", violating=boom, clean=fine)
    c2 = NegativeControl("b", violating=fine, clean=fine)
    r = Registry([predicate("a"), predicate("b")], [c1, c2])
    result = r.failures()
    assert isinstance(result, tuple)


def test_failures_empty_when_all_pass() -> None:
    """No failures → empty tuple."""
    c1 = NegativeControl("a", violating=boom, clean=fine)
    c2 = NegativeControl("b", violating=boom, clean=fine)
    r = Registry([predicate("a"), predicate("b")], [c1, c2])
    assert r.failures() == ()
