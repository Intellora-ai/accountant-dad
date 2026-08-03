"""The Business Understanding Object, attacked.

Every test here is written to BREAK `understanding.py`, not to watch it work
(§J.1, §J.3). The ones that matter most are the ones that would let Engine 2
commit its defining sin: turning an uncertainty into a certainty quietly.

Three tests read the REAL specification off disk rather than trusting a comment:
the vocabulary citations, the four-component artifact shape and the six-Result
set. A citation that drifts from the document it cites is a lie that a comment
cannot catch and a test can.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from accountant_dad.artifacts.understanding import (
    FORBIDDEN_PLURALS,
    FORBIDDEN_VOCABULARY,
    MINIMUM_COMPETING_READINGS,
    SPEC_GAPS,
    BusinessContextResult,
    BusinessUnderstandingObject,
    ConfidenceAssessment,
    Conflict,
    ItemUnderstandingResult,
    ObservedFact,
    PartyUnderstandingResult,
    PaymentUnderstandingResult,
    SupportingUnderstandingData,
    TimelineUnderstandingResult,
    TransactionStory,
    TransactionUnderstandingResult,
    UnderstandingResult,
    Unknown,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

DOCS = Path(__file__).resolve().parents[2] / "docs"

#: A disagreement needs two sides; two Results each raising one gap make two.
TWO = 2
THREE = 3
#: Every entry in SPEC_GAPS. A gap silently deleted is a gap silently filled.
DECLARED_GAPS = 6

# ── builders ──────────────────────────────────────────────────────────────
# Deliberately minimal. A helper that fills in a default is a helper that can
# hide the omission a test was written to catch.


def fact(
    statement: str = "the document names a party on the supplying side",
    *,
    references: tuple[str, ...] = ("doc-1#field-7",),
    stated: str | None = None,
) -> ObservedFact:
    return ObservedFact(statement=statement, stated_text=stated, evidence_references=references)


def quoted(
    text: str = "ABC Traders", *, references: tuple[str, ...] = ("doc-1#field-7",)
) -> ObservedFact:
    return ObservedFact(
        statement="the line reads as stated", stated_text=text, evidence_references=references
    )


def unknown(subject: str = "who the buyer is") -> Unknown:
    return Unknown(subject=subject, why_it_matters="nothing downstream can name the other side")


def conflict() -> Conflict:
    return Conflict(
        subject="the stated amount",
        competing_readings=(
            fact("the document states one amount", references=("doc-1#total",)),
            fact("the bank line states another", references=("doc-2#line-3",)),
        ),
    )


def score(value: str) -> Decimal:
    return Decimal(value)


def six(
    confidence: str = "0.6000", **overrides: UnderstandingResult
) -> SupportingUnderstandingData:
    made: dict[str, UnderstandingResult] = {
        "transaction": TransactionUnderstandingResult(
            confidence=score(confidence), identified_event=(fact("a purchase of goods occurred"),)
        ),
        "party": PartyUnderstandingResult(
            confidence=score(confidence), identified_entities=(fact(),)
        ),
        "item": ItemUnderstandingResult(
            confidence=score(confidence), descriptions=(quoted("Laptop"),)
        ),
        "payment": PaymentUnderstandingResult(
            confidence=score(confidence), unknown_payment_details=(unknown("payment status"),)
        ),
        "timeline": TimelineUnderstandingResult(
            confidence=score(confidence), dates=(quoted("01/08/2026"),)
        ),
        "business_context": BusinessContextResult(
            confidence=score(confidence), context_clues=(fact("this party recurs"),)
        ),
    }
    made.update(overrides)
    return SupportingUnderstandingData(**made)  # type: ignore[arg-type]


def envelope() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def artifact(
    *,
    data: SupportingUnderstandingData | None = None,
    unknowns: tuple[Unknown, ...] | None = None,
    evidence: str = "0.8000",
    understanding: str = "0.5000",
    narrative: str = "Goods were supplied; whether money moved is not stated.",
) -> BusinessUnderstandingObject:
    supporting = six() if data is None else data
    return BusinessUnderstandingObject(
        identity=envelope(),
        transaction_story=TransactionStory(narrative=narrative),
        supporting_understanding_data=supporting,
        identified_unknowns=supporting.all_unknowns if unknowns is None else unknowns,
        confidence_assessment=ConfidenceAssessment(
            evidence_confidence=score(evidence), understanding_confidence=score(understanding)
        ),
    )


# ── the vocabulary boundary ───────────────────────────────────────────────


def test_the_worked_failure_from_the_specification_is_refused() -> None:
    """ENGINE_2:852 — ✗ "Fixed asset purchase" · ✓ "Item description: Laptop.\" """
    with pytest.raises(ValidationError) as raised:
        TransactionStory(narrative="Fixed asset purchase from a recurring supplier")
    assert "accounting vocabulary" in str(raised.value)


def test_the_worked_success_from_the_specification_is_accepted() -> None:
    assert TransactionStory(narrative="Item description: Laptop.").narrative


@pytest.mark.parametrize("term", sorted({*FORBIDDEN_VOCABULARY, *FORBIDDEN_PLURALS}))
def test_every_declared_forbidden_term_is_actually_refused(term: str) -> None:
    """A blocklist entry that does not block is decoration."""
    with pytest.raises(ValidationError):
        TransactionStory(narrative=f"the supplier {term} was involved")


@pytest.mark.parametrize("term", sorted({*FORBIDDEN_VOCABULARY, *FORBIDDEN_PLURALS}))
def test_the_refusal_names_the_term_it_found(term: str) -> None:
    with pytest.raises(ValidationError) as raised:
        TransactionStory(narrative=f"the supplier {term} was involved")
    assert term in str(raised.value).lower()


@pytest.mark.parametrize("term", ["Ledger", "LEDGER", "LeDgEr", "Accounting", "TAX"])
def test_capitalising_a_forbidden_term_does_not_evade_the_check(term: str) -> None:
    with pytest.raises(ValidationError):
        TransactionStory(narrative=f"posted to the {term} for the period")


@pytest.mark.parametrize(
    "permitted",
    [
        "a debit note was issued",
        "a credit note was issued",
        "the stated payment method is credit",
        "the event is an expense reimbursement",
        "the two amounts do not tally",
        "the taxi fare is stated on the receipt",
        "an assessment of the party was not possible",
        "the goods were delivered to the assembly line",
        "the syntax of the document is unusual",
        "the reassessment of the delivery note is pending",
    ],
)
def test_words_the_specification_permits_are_not_refused(permitted: str) -> None:
    """ENGINE_2:380 names `expense`, `credit note` and `debit note` as EVENT
    KINDS this engine may identify, and :502 names `credit` as a payment method.
    Banning them would refuse exactly what the specification permits.

    The rest are the word-boundary cases, and they need BOTH boundaries:
    `taxi`, `assessment` and `assembly` start with a banned term and need the
    TRAILING `\\b`; `syntax` and `reassessment` end with one and need the
    LEADING `\\b`. A mutation run with only the first three left the leading
    boundary untested — it could be deleted and every test stayed green.
    """
    assert TransactionStory(narrative=permitted).narrative == permitted


def test_a_forbidden_word_is_caught_mid_sentence_not_only_at_the_start() -> None:
    with pytest.raises(ValidationError):
        TransactionStory(narrative="the supply happened and the ledger was chosen afterwards")


def test_every_forbidden_term_cites_a_line_that_says_what_the_citation_claims() -> None:
    """Read the REAL specification. A citation drifting from its document is a
    lie a comment cannot catch (§E.1, repository-is-reality).
    """
    spec = (DOCS / "ENGINE_2_UNDERSTANDING_ENGINE_RULES.md").read_text().splitlines()
    for term, citation in FORBIDDEN_VOCABULARY.items():
        lines = citation.split("ENGINE_2:", 1)[1].split("—")[0]
        numbers = [int(n) for n in re.findall(r"\d+", lines)]
        assert numbers, f"{term} cites no line"
        assert any(term in spec[n - 1].lower() for n in numbers), (
            f"{term!r} cites {numbers} and no cited line contains it"
        )


def test_every_plural_form_has_a_cited_singular_behind_it() -> None:
    """A plural carries no separate citation because it makes no separate claim
    — so every one must reduce to a term that does."""
    for plural in FORBIDDEN_PLURALS:
        stems = {plural[:-1], plural[:-2], plural[:-3] + "y"}
        assert stems & set(FORBIDDEN_VOCABULARY), f"{plural!r} has no cited singular"


def test_a_stated_quotation_is_never_vocabulary_checked() -> None:
    """A party genuinely named "Ledger Solutions" is a fact about a document.

    Filtering it would modify evidence (ENGINE_2:190) — the exact prohibition
    the vocabulary rule exists beside, not instead of.
    """
    kept = quoted("Ledger Solutions Pvt Ltd")
    assert kept.stated_text == "Ledger Solutions Pvt Ltd"


def test_a_stated_quotation_is_not_trimmed() -> None:
    assert quoted("  Laptop  ").stated_text == "  Laptop  "


def test_a_blank_quotation_is_still_refused() -> None:
    with pytest.raises(ValidationError):
        quoted("   ")


@pytest.mark.parametrize("bad", [7, 3.5, b"Laptop", ["Laptop"], True])
def test_a_non_string_quotation_is_refused(bad: object) -> None:
    with pytest.raises(ValidationError):
        ObservedFact(statement="x", stated_text=bad, evidence_references=("d#1",))  # type: ignore[arg-type]


def test_an_absent_quotation_is_allowed_and_is_not_an_empty_string() -> None:
    """`None` means this fact quotes nothing. `""` would mean it quotes an empty
    document — two different states, and collapsing them is invisible
    downstream."""
    assert fact("an interpretation, quoting nothing").stated_text is None
    with pytest.raises(ValidationError):
        ObservedFact(statement="x", stated_text="", evidence_references=("d#1",))


@pytest.mark.parametrize("bad", [None, 7, 3.5, b"text", ["text"], True])
def test_a_non_string_authored_statement_is_refused(bad: object) -> None:
    with pytest.raises(ValidationError):
        ObservedFact(statement=bad, evidence_references=("d#1",))  # type: ignore[arg-type]


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n  \n"])
def test_a_blank_authored_statement_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError):
        ObservedFact(statement=blank, evidence_references=("d#1",))


def test_the_vocabulary_check_reaches_an_unknowns_prose() -> None:
    with pytest.raises(ValidationError):
        Unknown(subject="the ledger to use", why_it_matters="it cannot be chosen")


def test_the_vocabulary_check_reaches_a_conflicts_subject() -> None:
    with pytest.raises(ValidationError):
        Conflict(subject="which ledger", competing_readings=(fact("a"), fact("b")))


# ── every fact names its evidence ─────────────────────────────────────────


def test_a_fact_with_no_evidence_reference_is_refused() -> None:
    """UNDERSTANDING_INTERNAL:130 — the structural reason this engine cannot
    hallucinate."""
    with pytest.raises(ValidationError) as raised:
        ObservedFact(statement="the supplier is recurring", evidence_references=())
    assert "evidence reference" in str(raised.value)


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_evidence_reference_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError):
        ObservedFact(statement="a fact", evidence_references=(blank,))


def test_a_result_publishes_the_union_of_what_its_facts_cite() -> None:
    result = PartyUnderstandingResult(
        confidence=score("0.5000"),
        identified_entities=(fact("the seller", references=("doc-1#a", "doc-2#b")),),
        relationships=(fact("they are related", references=("doc-2#b", "doc-3#c")),),
    )
    assert result.evidence_references == ("doc-1#a", "doc-2#b", "doc-3#c")


def test_the_evidence_union_preserves_first_appearance_order() -> None:
    result = PartyUnderstandingResult(
        confidence=score("0.5000"),
        identified_entities=(fact("z first", references=("z", "a")),),
        relationships=(fact("a again", references=("a", "m")),),
    )
    assert result.evidence_references == ("z", "a", "m")


def test_a_conflicts_competing_readings_carry_their_evidence_into_the_union() -> None:
    """A conflict is where evidence disagrees. Its readings ARE facts, and a
    Result that hid their references would understate what it looked at."""
    result = TransactionUnderstandingResult(
        confidence=score("0.5000"), conflicts_detected=(conflict(),)
    )
    assert result.evidence_references == ("doc-1#total", "doc-2#line-3")


@pytest.mark.parametrize(
    ("result_type", "alias"),
    [
        (TransactionUnderstandingResult, "supporting_evidence_references"),
        (PartyUnderstandingResult, "supporting_evidence"),
        (BusinessContextResult, "supporting_evidence"),
    ],
)
def test_the_specifications_own_name_for_the_evidence_component_resolves(
    result_type: type[UnderstandingResult], alias: str
) -> None:
    """ENGINE_2:342-347 spells this component three different ways."""
    made = result_type(confidence=score("0.5000"), conflicts_detected=(conflict(),))
    assert getattr(made, alias) == made.evidence_references


@pytest.mark.parametrize(
    "result_type",
    [PaymentUnderstandingResult, TimelineUnderstandingResult],
)
def test_the_two_results_the_table_forgot_still_carry_evidence_references(
    result_type: type[UnderstandingResult],
) -> None:
    """ENGINE_2:350 — "Every Result carries confidence, unknowns and evidence
    references. No Result may omit them." The §7 table omits the component for
    these two; :350 does not.
    """
    made = result_type(confidence=score("0.5000"), conflicts_detected=(conflict(),))
    assert made.evidence_references == ("doc-1#total", "doc-2#line-3")


# ── what is recorded as stated, is stated ─────────────────────────────────


@pytest.mark.parametrize(
    ("result_type", "component"),
    [
        (ItemUnderstandingResult, "descriptions"),
        (PaymentUnderstandingResult, "payment_references"),
        (TimelineUnderstandingResult, "dates"),
    ],
)
def test_an_as_stated_component_refuses_a_paraphrase(
    result_type: type[UnderstandingResult], component: str
) -> None:
    """ENGINE_2:462, :504, :557 — these components record what the document
    states. A paraphrase of a stated line value is arithmetic in quotation
    marks."""
    with pytest.raises(ValidationError) as raised:
        result_type(confidence=score("0.5000"), **{component: (fact("about ten laptops"),)})  # type: ignore[arg-type]
    assert "stated_text" in str(raised.value)


@pytest.mark.parametrize(
    ("result_type", "component"),
    [
        (ItemUnderstandingResult, "descriptions"),
        (PaymentUnderstandingResult, "payment_references"),
        (TimelineUnderstandingResult, "dates"),
    ],
)
def test_an_as_stated_component_accepts_the_documents_own_words(
    result_type: type[UnderstandingResult], component: str
) -> None:
    made = result_type(
        confidence=score("0.5000"),
        **{component: (quoted("Laptop x 10"),)},  # type: ignore[arg-type]
    )
    assert getattr(made, component)[0].stated_text == "Laptop x 10"


def test_a_date_is_never_parsed_into_a_datetime() -> None:
    """ENGINE_2:557 — "Where a date format is genuinely ambiguous, the ambiguity
    travels rather than being silently normalised." Parsing `01/08/2026` picks a
    reading and destroys the evidence that two existed."""
    made = TimelineUnderstandingResult(confidence=score("0.5000"), dates=(quoted("01/08/2026"),))
    assert made.dates[0].stated_text == "01/08/2026"
    assert isinstance(made.dates[0].stated_text, str)


def test_a_component_that_is_not_as_stated_accepts_an_interpretation() -> None:
    made = ItemUnderstandingResult(
        confidence=score("0.5000"),
        identified_goods_and_services=(fact("a portable computer was supplied"),),
    )
    assert made.identified_goods_and_services[0].stated_text is None


# ── conflicts survive ─────────────────────────────────────────────────────


def test_a_conflict_with_one_reading_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        Conflict(subject="the amount", competing_readings=(fact("only one"),))
    assert "at least two" in str(raised.value)


def test_a_conflict_with_no_readings_is_refused() -> None:
    with pytest.raises(ValidationError):
        Conflict(subject="the amount", competing_readings=())


def test_two_identical_readings_are_not_a_conflict() -> None:
    same = "the document states fifty thousand"
    with pytest.raises(ValidationError) as raised:
        Conflict(
            subject="the amount",
            competing_readings=(fact(same, references=("a",)), fact(same, references=("b",))),
        )
    assert "same thing" in str(raised.value)


def test_the_minimum_is_two_and_the_constant_says_so() -> None:
    assert MINIMUM_COMPETING_READINGS == TWO


def test_a_conflict_has_nowhere_to_record_a_resolution() -> None:
    """ENGINE_2:673 — "Never silently choose one answer."

    Reads the model's OWN field names, so adding `resolution` or
    `preferred_reading` turns this red without anyone editing the test.
    """
    forbidden = {
        "resolution",
        "resolved",
        "preferred",
        "chosen",
        "winner",
        "correct",
        "selected",
        "answer",
    }
    words = {word for name in Conflict.model_fields for word in name.split("_")}
    assert not (words & forbidden), f"a field name could hold a resolution: {words & forbidden}"


def test_a_conflict_cannot_have_a_resolution_bolted_on() -> None:
    with pytest.raises(ValidationError):
        Conflict(  # type: ignore[call-arg]
            subject="the amount",
            competing_readings=(fact("a"), fact("b")),
            resolution="the first one",
        )


def test_a_conflict_raised_by_a_result_reaches_the_artifacts_detected_conflicts() -> None:
    data = six(
        item=ItemUnderstandingResult(
            confidence=score("0.6000"),
            descriptions=(quoted("Laptop"),),
            conflicts_detected=(conflict(),),
        )
    )
    assert artifact(data=data).detected_conflicts == (conflict(),)


def test_detected_conflicts_is_derived_so_it_cannot_be_set_to_hide_one() -> None:
    """Story Builder cannot resolve a conflict by omitting it from the summary,
    because the summary is not a thing anyone writes (ENGINE_2:638)."""
    assert "detected_conflicts" not in ConfidenceAssessment.model_fields
    assert "detected_conflicts" not in BusinessUnderstandingObject.model_fields
    assert isinstance(BusinessUnderstandingObject.detected_conflicts, property)


def test_conflicts_from_every_result_are_gathered_not_only_the_first() -> None:
    other = Conflict(
        subject="the stated date",
        competing_readings=(
            fact("the invoice says one date", references=("doc-1#date",)),
            fact("the note says another", references=("doc-4#date",)),
        ),
    )
    data = six(
        transaction=TransactionUnderstandingResult(
            confidence=score("0.6000"),
            identified_event=(fact("a purchase occurred"),),
            conflicts_detected=(conflict(),),
        ),
        timeline=TimelineUnderstandingResult(
            confidence=score("0.6000"), dates=(quoted("01/08/2026"),), conflicts_detected=(other,)
        ),
    )
    assert len(artifact(data=data).detected_conflicts) == TWO


# ── unknowns survive ──────────────────────────────────────────────────────


def test_an_unknown_raised_by_a_result_may_not_be_dropped_from_the_artifact() -> None:
    """ENGINE_2:645 — "Unknowns are carried into Identified Unknowns intact."

    This is the single most important test in the file. Engine 2 exists to stop
    uncertainty being converted into certainty; dropping an unknown IS that
    conversion, and it is silent.
    """
    data = six()
    with pytest.raises(ValidationError) as raised:
        artifact(data=data, unknowns=())
    assert "missing from identified_unknowns" in str(raised.value)


def test_the_refusal_names_the_unknown_that_went_missing() -> None:
    data = six()
    with pytest.raises(ValidationError) as raised:
        artifact(data=data, unknowns=())
    assert "payment status" in str(raised.value)


def test_dropping_one_of_several_unknowns_is_refused() -> None:
    data = six(
        party=PartyUnderstandingResult(
            confidence=score("0.6000"),
            identified_entities=(fact(),),
            unknown_parties=(unknown("which party is this business"),),
        )
    )
    kept = (data.payment.unknowns[0],)
    with pytest.raises(ValidationError) as raised:
        artifact(data=data, unknowns=kept)
    assert "which party is this business" in str(raised.value)


def test_story_builder_may_add_an_unknown_no_sub_engine_raised() -> None:
    """ENGINE_2:645 also requires Story Builder report an incoherence that no
    sub-engine could have raised. A superset is allowed; a subset is not."""
    data = six()
    extra = Unknown(
        subject="whether these six accounts describe one event",
        why_it_matters="the readings cannot be made into one coherent story",
    )
    made = artifact(data=data, unknowns=(*data.all_unknowns, extra))
    assert extra in made.identified_unknowns


def test_reordering_the_unknowns_is_not_dropping_them() -> None:
    data = six(
        party=PartyUnderstandingResult(
            confidence=score("0.6000"),
            identified_entities=(fact(),),
            unknown_parties=(unknown("which party is this business"),),
        )
    )
    made = artifact(data=data, unknowns=tuple(reversed(data.all_unknowns)))
    assert set(made.identified_unknowns) == set(data.all_unknowns)


def test_missing_information_and_identified_unknowns_are_one_list() -> None:
    """§11 names Missing Information; §5 names Identified Unknowns. One concept,
    one owner (INV-10) — so one is a view of the other, never a second store."""
    made = artifact()
    assert made.missing_information == made.identified_unknowns
    assert "missing_information" not in BusinessUnderstandingObject.model_fields


def test_an_unknown_must_say_what_its_absence_prevents() -> None:
    """ENGINE_2:794 — the engine may explain WHY understanding is incomplete. A
    gap with no consequence cannot become a good question downstream."""
    with pytest.raises(ValidationError):
        Unknown(subject="the buyer", why_it_matters="")


def test_an_unknown_must_name_a_subject() -> None:
    with pytest.raises(ValidationError):
        Unknown(subject="  ", why_it_matters="nothing can be said about it")


def test_unknowns_are_gathered_from_every_component_of_a_result() -> None:
    made = PaymentUnderstandingResult(
        confidence=score("0.5000"),
        unknown_payment_details=(unknown("payment status"), unknown("instrument reference")),
    )
    assert len(made.unknowns) == TWO


def test_unknowns_are_gathered_from_every_one_of_the_six_results() -> None:
    data = six(
        transaction=TransactionUnderstandingResult(
            confidence=score("0.6000"), unknown_information=(unknown("the event kind"),)
        ),
        business_context=BusinessContextResult(
            confidence=score("0.6000"), unknown_context=(unknown("the branch"),)
        ),
    )
    assert len(data.all_unknowns) == THREE


# ── confidence never exceeds the evidence ─────────────────────────────────


def test_understanding_confidence_above_evidence_reliability_is_refused() -> None:
    """ENGINE_2:756, with the worked example at :765-770."""
    with pytest.raises(ValidationError) as raised:
        ConfidenceAssessment(
            evidence_confidence=score("0.4000"), understanding_confidence=score("0.9500")
        )
    assert "cannot exceed evidence reliability" in str(raised.value)


def test_understanding_confidence_equal_to_evidence_reliability_is_allowed() -> None:
    """`≤`, not `<`. Refusing equality would forbid a perfectly honest reading."""
    made = ConfidenceAssessment(
        evidence_confidence=score("0.4000"), understanding_confidence=score("0.4000")
    )
    assert made.understanding_confidence == score("0.4000")


def test_a_barely_higher_understanding_confidence_is_still_refused() -> None:
    with pytest.raises(ValidationError):
        ConfidenceAssessment(
            evidence_confidence=score("0.4000"), understanding_confidence=score("0.4001")
        )


def test_a_result_more_confident_than_the_evidence_is_refused() -> None:
    data = six(
        item=ItemUnderstandingResult(confidence=score("0.9000"), descriptions=(quoted("Laptop"),))
    )
    with pytest.raises(ValidationError) as raised:
        artifact(data=data, evidence="0.8000", understanding="0.5000")
    assert "ItemUnderstandingResult" in str(raised.value)


def test_a_result_exactly_as_confident_as_the_evidence_is_allowed() -> None:
    data = six(confidence="0.8000")
    assert artifact(data=data, evidence="0.8000", understanding="0.8000")


def test_the_assembled_confidence_cannot_exceed_the_least_confident_result() -> None:
    """ENGINE_2:638 with INV-2 — Story Builder introduces no evidence, so it
    cannot be more certain than its least certain input."""
    data = six(
        payment=PaymentUnderstandingResult(
            confidence=score("0.3000"), unknown_payment_details=(unknown("payment status"),)
        )
    )
    with pytest.raises(ValidationError) as raised:
        artifact(data=data, evidence="0.9000", understanding="0.6000")
    assert "lowest Result confidence" in str(raised.value)


def test_the_assembled_confidence_may_equal_the_least_confident_result() -> None:
    data = six(
        payment=PaymentUnderstandingResult(
            confidence=score("0.3000"), unknown_payment_details=(unknown("payment status"),)
        )
    )
    assert artifact(data=data, evidence="0.9000", understanding="0.3000")


def test_the_floor_is_the_minimum_not_the_maximum() -> None:
    """If the rule were `max`, this would pass. It is `min`, so it must not."""
    data = six(
        payment=PaymentUnderstandingResult(
            confidence=score("0.2000"), unknown_payment_details=(unknown("payment status"),)
        )
    )
    with pytest.raises(ValidationError):
        artifact(data=data, evidence="0.9000", understanding="0.5500")


@pytest.mark.parametrize("bad", [0.6, "0.6", 1, None])
def test_confidence_refuses_anything_that_is_not_a_decimal(bad: object) -> None:
    """One representation of Confidence, from confidence.py. A float here would
    be a second one."""
    with pytest.raises(ValidationError):
        ConfidenceAssessment(
            evidence_confidence=bad,  # type: ignore[arg-type]
            understanding_confidence=score("0.1000"),
        )


@pytest.mark.parametrize("bad", ["1.5000", "-0.0001"])
def test_confidence_outside_the_unit_range_is_refused(bad: str) -> None:
    with pytest.raises(ValidationError):
        ConfidenceAssessment(
            evidence_confidence=score(bad), understanding_confidence=score("0.1000")
        )


def test_confidence_scores_compare_as_numbers_not_as_strings() -> None:
    """`0.5` and `0.5000` are one number. Comparing their text would make the
    padding of a score change what it means."""
    data = six(confidence="0.5")
    assert artifact(data=data, evidence="0.5000", understanding="0.5000")


# ── a Result reports something ────────────────────────────────────────────


@pytest.mark.parametrize(
    "result_type",
    [
        TransactionUnderstandingResult,
        PartyUnderstandingResult,
        ItemUnderstandingResult,
        PaymentUnderstandingResult,
        TimelineUnderstandingResult,
        BusinessContextResult,
    ],
)
def test_a_result_that_states_nothing_at_all_is_refused(
    result_type: type[UnderstandingResult],
) -> None:
    """A Result carrying no fact, no unknown and no conflict cannot be
    distinguished from a sub-engine that never ran."""
    with pytest.raises(ValidationError) as raised:
        result_type(confidence=score("0.5000"))
    assert "reports nothing" in str(raised.value)


def test_a_result_that_only_names_a_gap_is_a_valid_result() -> None:
    """ENGINE_2:435 — an unidentifiable party is recorded, not omitted. An
    honest empty Result must remain constructible."""
    made = PartyUnderstandingResult(
        confidence=score("0.5000"), unknown_parties=(unknown("every party"),)
    )
    assert made.evidence_references == ()


def test_a_result_that_only_records_a_conflict_is_a_valid_result() -> None:
    assert TransactionUnderstandingResult(
        confidence=score("0.5000"), conflicts_detected=(conflict(),)
    )


def test_a_payment_result_may_record_the_status_the_specification_requires() -> None:
    """ENGINE_2:517 requires `unstated` be recordable; :503's list omits it."""
    made = PaymentUnderstandingResult(
        confidence=score("0.5000"),
        payment_status="unstated",
        unknown_payment_details=(unknown("payment status"),),
    )
    assert made.payment_status == "unstated"


def test_payment_method_and_status_are_absent_by_default() -> None:
    """ENGINE_2:514 — payment may never be inferred from silence."""
    made = PaymentUnderstandingResult(
        confidence=score("0.5000"), unknown_payment_details=(unknown("payment"),)
    )
    assert made.payment_method is None
    assert made.payment_status is None


def test_a_blank_payment_method_is_refused() -> None:
    with pytest.raises(ValidationError):
        PaymentUnderstandingResult(
            confidence=score("0.5000"),
            payment_method="  ",
            unknown_payment_details=(unknown("payment"),),
        )


# ── the artifact's shape ──────────────────────────────────────────────────


def test_the_artifact_has_exactly_the_four_components_the_documents_draw() -> None:
    """DATA_FLOW.md §2.2 and ENGINE_2:218-234, plus the universal identity
    envelope DATA_FLOW.md:32 does not repeat inside an artifact."""
    assert set(BusinessUnderstandingObject.model_fields) == {
        "identity",
        "transaction_story",
        "supporting_understanding_data",
        "identified_unknowns",
        "confidence_assessment",
    }


def test_the_four_components_are_the_ones_the_real_document_names() -> None:
    """Read DATA_FLOW.md off disk. A shape that drifts from the frozen
    architecture is a defect in the code, never in the document (§G)."""
    flow = (DOCS / "DATA_FLOW.md").read_text()
    tree = flow.split("### 2.2 Business Understanding Object", 1)[1].split("###", 1)[0]
    for named in (
        "Transaction Story",
        "Supporting Understanding Data",
        "Identified Unknowns",
        "Confidence Assessment",
    ):
        assert named in tree


def test_the_supporting_data_holds_exactly_the_six_results() -> None:
    assert set(SupportingUnderstandingData.model_fields) == {
        "transaction",
        "party",
        "item",
        "payment",
        "timeline",
        "business_context",
    }


@pytest.mark.parametrize(
    "absent", ["transaction", "party", "item", "payment", "timeline", "business_context"]
)
def test_a_missing_result_is_refused(absent: str) -> None:
    """Six sub-engines produce six Results. A missing one is a sub-engine that
    did not run, and ENGINE_2:645 requires that be reported, not absorbed."""
    made = six()
    supplied = {
        name: getattr(made, name)
        for name in SupportingUnderstandingData.model_fields
        if name != absent
    }
    with pytest.raises(ValidationError):
        SupportingUnderstandingData(**supplied)


def test_a_seventh_result_cannot_be_added() -> None:
    """ENGINE_2:307 — do not add new sub-engines."""
    made = six()
    with pytest.raises(ValidationError):
        SupportingUnderstandingData(  # type: ignore[call-arg]
            **{name: getattr(made, name) for name in SupportingUnderstandingData.model_fields},
            story_builder=made.transaction,
        )


def test_no_field_anywhere_could_hold_an_accounting_conclusion() -> None:
    """ENGINE_2:268-272 — no journal, ledger, debit/credit, tax or posting field
    exists anywhere in this artifact, and `extra` is forbidden everywhere, so
    one cannot be bolted on.

    Reads every model's OWN field names, so a new field naming any of them turns
    this red without anyone editing the test.
    """
    forbidden = {
        "journal",
        "ledger",
        "debit",
        "credit",
        "voucher",
        "tax",
        "posting",
        "account",
        "treatment",
        "entry",
        "entries",
    }
    models: list[type[BaseModel]] = [
        ObservedFact,
        Unknown,
        Conflict,
        UnderstandingResult,
        TransactionUnderstandingResult,
        PartyUnderstandingResult,
        ItemUnderstandingResult,
        PaymentUnderstandingResult,
        TimelineUnderstandingResult,
        BusinessContextResult,
        SupportingUnderstandingData,
        TransactionStory,
        ConfidenceAssessment,
        BusinessUnderstandingObject,
    ]
    for model in models:
        words = {word for name in model.model_fields for word in name.split("_")}
        assert not (words & forbidden), f"{model.__name__} has {words & forbidden}"


@pytest.mark.parametrize(
    "model",
    [
        ObservedFact,
        Unknown,
        Conflict,
        UnderstandingResult,
        SupportingUnderstandingData,
        TransactionStory,
        ConfidenceAssessment,
        BusinessUnderstandingObject,
    ],
)
def test_every_model_is_frozen_and_forbids_extra_fields(model: type[BaseModel]) -> None:
    """Artifacts are immutable after creation. Correction is a new version."""
    assert model.model_config.get("frozen") is True
    assert model.model_config.get("extra") == "forbid"


def test_the_artifact_cannot_be_mutated_after_creation() -> None:
    made = artifact()
    with pytest.raises(ValidationError):
        made.identified_unknowns = ()


def test_a_result_cannot_be_mutated_after_creation() -> None:
    made = six().payment
    with pytest.raises(ValidationError):
        made.confidence = score("1.0000")


def test_the_artifact_cannot_carry_a_field_the_documents_do_not_name() -> None:
    with pytest.raises(ValidationError):
        BusinessUnderstandingObject(  # type: ignore[call-arg]
            identity=envelope(),
            transaction_story=TransactionStory(narrative="a story"),
            supporting_understanding_data=six(),
            identified_unknowns=six().all_unknowns,
            confidence_assessment=ConfidenceAssessment(
                evidence_confidence=score("0.9000"), understanding_confidence=score("0.5000")
            ),
            recommended_treatment="capitalise it",
        )


# ── identity ──────────────────────────────────────────────────────────────


def test_the_understanding_id_is_the_artifact_id() -> None:
    """DATA_FLOW.md:32 — a second stored identifier could disagree with the
    first, and then no reader could tell which one traced the artifact."""
    made = artifact()
    assert made.understanding_id is made.identity.artifact_id
    assert "understanding_id" not in BusinessUnderstandingObject.model_fields


def test_the_transaction_id_comes_from_the_envelope() -> None:
    made = artifact()
    assert made.transaction_id is made.identity.transaction_id


def test_two_artifacts_carry_different_artifact_ids() -> None:
    assert artifact().understanding_id != artifact().understanding_id


def test_an_artifact_without_an_identity_envelope_is_refused() -> None:
    with pytest.raises(ValidationError):
        BusinessUnderstandingObject(  # type: ignore[call-arg]
            transaction_story=TransactionStory(narrative="a story"),
            supporting_understanding_data=six(),
            identified_unknowns=six().all_unknowns,
            confidence_assessment=ConfidenceAssessment(
                evidence_confidence=score("0.9000"), understanding_confidence=score("0.5000")
            ),
        )


# ── the gaps are declared, not filled ─────────────────────────────────────


def test_the_open_vocabularies_are_declared_rather_than_invented() -> None:
    """Law 54. A schema that invented four enums would look authoritative and
    would be wrong."""
    assert len(SPEC_GAPS) == DECLARED_GAPS
    assert any("payment_status" in gap for gap in SPEC_GAPS)
    assert any("conflicts_detected" in gap for gap in SPEC_GAPS)


def test_the_event_kind_is_open_text_and_not_an_enumeration() -> None:
    """ENGINE_2:380 lists nine kinds and declares none of them closed."""
    made = TransactionUnderstandingResult(
        confidence=score("0.5000"),
        identified_event=(fact("a consignment transfer between two of this business's locations"),),
    )
    assert made.identified_event[0].statement.startswith("a consignment")
