"""The Accounting Engine stub, attacked.

Every test here is written to catch the stub INVENTING something, not to watch
it return an object (§J.1, §J.3). The failure this file exists to trap is the
one that would look fine in CI: a stub that starts emitting a plausible ledger,
a plausible tax treatment or a balanced journal, and hands Validation an
artifact indistinguishable from a real decision.

Three groups of tests, aimed at three different ways that could happen:

  1. THE TRIPWIRES. The journal is empty, no ledger is selected, no tax
     treatment is stated, no risk and no assumption is claimed. These are exact
     assertions, so an edit that fills any of them in turns this file red.

  2. THE LEAK TEST. Two wildly different Business Understanding Objects under
     one Transaction ID must produce EQUAL decisions, and no distinctive string
     from the understanding may appear anywhere in the decision. A stub that
     started copying an item description into a ledger name would pass every
     tripwire above and fail here.

  3. THE CITATIONS. The stub's prose leans hard on specific lines of
     `ENGINE_3_ACCOUNTING_ENGINE_RULES.md` and the blueprint. Those lines are
     read off disk and checked, because a citation that drifts from the
     document it cites is a lie a comment cannot catch and a test can.

Plus the structural ones: the module imports no other engine (AL-INV-5), no
Application Layer (AL-INV-4), no Brain, and nothing that could make it
non-deterministic.
"""

from __future__ import annotations

import ast
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from authored_source import authored_path, authored_source
from pydantic import ValidationError

from accountant_dad.artifacts.decision import AccountingDecision, DecisionStatus, JournalLine
from accountant_dad.artifacts.understanding import (
    BusinessContextResult,
    BusinessUnderstandingObject,
    ConfidenceAssessment,
    ItemUnderstandingResult,
    ObservedFact,
    PartyUnderstandingResult,
    PaymentUnderstandingResult,
    SupportingUnderstandingData,
    TimelineUnderstandingResult,
    TransactionStory,
    TransactionUnderstandingResult,
    Unknown,
)
from accountant_dad.engines.accounting_engine import stub
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope, TransactionId

DOCS = Path(__file__).resolve().parents[2] / "docs"
ENGINE_3 = DOCS / "ENGINE_3_ACCOUNTING_ENGINE_RULES.md"
BLUEPRINT = DOCS / "MVP_IMPLEMENTATION_BLUEPRINT.md"

TXN_UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_TXN_UUID = uuid.UUID("55555555-5555-4555-8555-555555555555")
UNDERSTANDING_UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
DECISION_UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")

#: One doubt: the one that says nothing was decided. Two would mean the stub
#: had characterised something.
EXPECTED_DOUBTS = 1

#: The four text components no accounting was done for. Named as a set so a
#: fourteenth field or a renamed one is a visible edit, not a silent gap.
UNDECIDED_FIELDS = (
    "accounting_treatment",
    "ledger_classification",
    "journal_structure",
    "tax_treatment",
)

#: Every text component of the artifact, including the two the stub authors
#: itself. Used by the leak test — a copied item description could land in any
#: of them, not only in the four above.
ALL_TEXT_FIELDS = (*UNDECIDED_FIELDS, "supporting_reasoning")


# ── builders ──────────────────────────────────────────────────────────────
# Minimal on purpose. A builder that supplies a default is a builder that can
# hide the very omission a test was written to catch.


def fact(statement: str, *, stated: str | None = None) -> ObservedFact:
    return ObservedFact(
        statement=statement, stated_text=stated, evidence_references=("doc-1#field-1",)
    )


#: Item, party, date — the three distinctive strings the leak test hunts for in
#: the emitted decision. Carried as one tuple so the builders below stay under
#: the argument limit without dropping any of the three.
Stated = tuple[str, str, str]

DEFAULT_STATED: Stated = ("Laptop", "ABC Traders", "01/08/2026")
OTHER_STATED: Stated = ("Cement, 40 bags", "Zeta Infra Pvt Ltd", "17/11/2027")


def six(confidence: str, stated: Stated) -> SupportingUnderstandingData:
    item, party, date = stated
    return SupportingUnderstandingData(
        transaction=TransactionUnderstandingResult(
            confidence=Decimal(confidence), identified_event=(fact("a purchase of goods occurred"),)
        ),
        party=PartyUnderstandingResult(
            confidence=Decimal(confidence), identified_entities=(fact("a supplier is named"),)
        ),
        item=ItemUnderstandingResult(
            confidence=Decimal(confidence),
            descriptions=(fact("the line reads as stated", stated=item),),
        ),
        payment=PaymentUnderstandingResult(
            confidence=Decimal(confidence),
            unknown_payment_details=(
                Unknown(subject="payment status", why_it_matters="nothing states whether it moved"),
            ),
        ),
        timeline=TimelineUnderstandingResult(
            confidence=Decimal(confidence),
            dates=(fact("the line reads as stated", stated=date),),
        ),
        business_context=BusinessContextResult(
            confidence=Decimal(confidence), context_clues=(fact(f"{party} recurs monthly"),)
        ),
    )


def understanding(
    *,
    transaction: uuid.UUID = TXN_UUID,
    confidence: str = "0.6000",
    stated: Stated = DEFAULT_STATED,
    narrative: str = "Goods were supplied; whether money moved is not stated.",
) -> BusinessUnderstandingObject:
    supporting = six(confidence, stated)
    return BusinessUnderstandingObject(
        identity=IdentityEnvelope(
            artifact_id=ArtifactId(UNDERSTANDING_UUID),
            version=FIRST_VERSION,
            parent_versions=(),
            transaction_id=TransactionId(transaction),
        ),
        transaction_story=TransactionStory(narrative=narrative),
        supporting_understanding_data=supporting,
        identified_unknowns=supporting.all_unknowns,
        confidence_assessment=ConfidenceAssessment(
            evidence_confidence=Decimal("0.8000"),
            understanding_confidence=Decimal(confidence),
        ),
    )


def decided(transaction: uuid.UUID = TXN_UUID) -> AccountingDecision:
    return stub.decide(understanding(transaction=transaction), ArtifactId(DECISION_UUID))


# ── 1. the tripwires ──────────────────────────────────────────────────────


def test_the_stub_emits_no_journal_lines_at_all() -> None:
    """THE tripwire. A debit or a credit here is a fabricated entry.

    Both sides asserted separately: a one-sided journal is refused by the schema
    only on a COMPLETE decision, so an INCOMPLETE one could carry debits alone
    and still validate. Checking the pair catches that.
    """
    decision = decided()
    assert decision.debit_entries == ()
    assert decision.credit_entries == ()


def test_no_ledger_is_selected_and_no_tax_treatment_is_stated() -> None:
    """The other half of the tripwire, and the one a journal is not needed for.

    A ledger name or a GST position written here is an accounting claim even
    with an empty journal, and `CLAUDE.md` §P freezes both.
    """
    decision = decided()
    for field in UNDECIDED_FIELDS:
        assert getattr(decision, field) == stub.NOT_DECIDED, field


def test_the_four_undecided_components_are_the_same_string() -> None:
    """One constant in four places. Fill in one and this goes red.

    Written as a set-of-one so a partial edit — a real ledger name with the
    other three left alone — fails here even if someone updated `NOT_DECIDED`
    to match.
    """
    assert len({getattr(decided(), field) for field in UNDECIDED_FIELDS}) == 1


def test_the_undecided_text_says_so_in_words_a_reader_cannot_mistake() -> None:
    """A short placeholder like `-` or `TBD` would satisfy `NonEmptyText`.

    It would also sit in an artifact that Validation reads as a ledger
    classification. The string must name the absence out loud.
    """
    assert stub.NOT_DECIDED.startswith("NOT DECIDED")
    assert "no ledger" in stub.NOT_DECIDED
    assert "no tax treatment" in stub.NOT_DECIDED


def test_the_status_is_the_one_that_means_it_could_not_decide() -> None:
    """`ENGINE_3:191` — a structured answer to *can this move forward?*"""
    assert decided().decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED


def test_exactly_one_doubt_is_named_and_it_names_what_is_missing() -> None:
    doubts = decided().unresolved_doubts
    assert len(doubts) == EXPECTED_DOUBTS
    assert doubts[0].missing_fact.strip()
    assert doubts[0].required_clarification.strip()


def test_no_assumption_and_no_risk_is_claimed() -> None:
    """`ENGINE_3:669` — nothing may assume silently. Nothing assumes at all here.

    An entry in either tuple would be a sub-engine output this file did not
    produce: an Accounting Risk Analysis or a recorded assumption, both frozen
    until P4.
    """
    decision = decided()
    assert decision.accounting_assumptions == ()
    assert decision.risk_indicators == ()


def test_confidence_is_the_floor_and_is_a_decimal() -> None:
    """Any value above zero claims confidence in a treatment that does not exist."""
    decision = decided()
    assert decision.decision_confidence == Decimal("0.0000")
    assert isinstance(decision.decision_confidence, Decimal)


# ── the tripwires cannot be defeated by editing the status alone ──────────


def test_flipping_the_status_to_complete_is_refused_by_the_frozen_schema() -> None:
    """The cheapest way to fake progress, closed by `decision.py`, not by manners.

    If a future edit set `COMPLETE` while leaving the journal empty, the artifact
    would not construct at all. So making this stub *look* finished requires
    inventing amounts — a visible act — rather than changing one enum member.
    """
    with pytest.raises(ValidationError, match="empty journal balances vacuously"):
        AccountingDecision(
            **{
                **decided().model_dump(),
                "decision_status": DecisionStatus.COMPLETE,
            }
        )


def test_a_fabricated_journal_would_have_to_be_written_line_by_line() -> None:
    """Proof the tripwire above is not vacuous: a COMPLETE decision IS constructible.

    Two invented lines and the same schema accepts it. That is exactly what this
    stub must never emit, and the test states it explicitly so nobody reads
    `test_the_stub_emits_no_journal_lines_at_all` as passing because the schema
    made journals impossible.
    """
    faked = AccountingDecision(
        **{
            **decided().model_dump(),
            "decision_status": DecisionStatus.COMPLETE,
            "debit_entries": (JournalLine(ledger="Computers", amount=Decimal("50000.00")),),
            "credit_entries": (JournalLine(ledger="ABC Traders", amount=Decimal("50000.00")),),
        }
    )
    assert faked.decision_status is DecisionStatus.COMPLETE
    assert decided().debit_entries != faked.debit_entries


# ── 2. the leak test: it reads nothing but the Transaction ID ─────────────


def test_two_different_understandings_produce_equal_decisions() -> None:
    """The strongest available proof that no reasoning happens.

    Different narrative, different item, different party, different date,
    different confidence — same Transaction ID. If the stub branched on any of
    it, or copied any of it, the two artifacts would differ.
    """
    first = stub.decide(understanding(), ArtifactId(DECISION_UUID))
    second = stub.decide(
        understanding(
            confidence="0.1000",
            stated=OTHER_STATED,
            narrative="A service may have been rendered; the document is illegible.",
        ),
        ArtifactId(DECISION_UUID),
    )
    assert first == second


def test_nothing_the_understanding_said_appears_anywhere_in_the_decision() -> None:
    """Equality above would still hold if the stub copied a CONSTANT string.

    This catches the other shape: any distinctive word from the understanding
    turning up in a text component. `Laptop` landing in `ledger_classification`
    is the exact failure — a ledger name that looks derived and is not.
    """
    decision = decided()
    haystack = " ".join(getattr(decision, field) for field in ALL_TEXT_FIELDS)
    haystack += " ".join(
        doubt.missing_fact + doubt.required_clarification for doubt in decision.unresolved_doubts
    )
    for leaked in ("Laptop", "ABC Traders", "01/08/2026", "Goods were supplied"):
        assert leaked not in haystack, leaked


def test_the_transaction_id_is_carried_forward_unchanged() -> None:
    """`BLUEPRINT:136` — Transaction ID intact. Also INV-3: exactly one per artifact."""
    source = understanding()
    decision = stub.decide(source, ArtifactId(DECISION_UUID))
    assert decision.identity.transaction_id == source.identity.transaction_id
    assert decision.identity.transaction_id == TransactionId(TXN_UUID)


def test_a_different_transaction_id_travels_through_untouched() -> None:
    """Falsifies a stub that hardcoded one Transaction ID and passed the test above."""
    decision = decided(transaction=OTHER_TXN_UUID)
    assert decision.identity.transaction_id == TransactionId(OTHER_TXN_UUID)


def test_the_decision_is_a_new_artifact_not_the_understanding_relabelled() -> None:
    """INV-3 — artifact identity is separate from transaction identity."""
    decision = decided()
    assert decision.identity.artifact_id == ArtifactId(DECISION_UUID)
    assert decision.identity.artifact_id != ArtifactId(UNDERSTANDING_UUID)
    assert decision.decision_id == ArtifactId(DECISION_UUID)


def test_the_decision_is_an_origin_version_with_no_parents() -> None:
    decision = decided()
    assert decision.identity.version == FIRST_VERSION
    assert decision.identity.parent_versions == ()


def test_the_stub_never_modifies_the_understanding_it_was_given() -> None:
    """`ENGINE_3:147` — never modify the Business Understanding Object."""
    source = understanding()
    before = source.model_dump()
    stub.decide(source, ArtifactId(DECISION_UUID))
    assert source.model_dump() == before


def test_the_emitted_decision_is_frozen() -> None:
    """INV-5 — correction is a new version, never an edit in place."""
    with pytest.raises(ValidationError):
        decided().decision_status = DecisionStatus.COMPLETE


def test_repeated_calls_are_equal_so_there_is_no_clock_and_no_randomness() -> None:
    assert decided() == decided()


# ── 3. the structural boundaries ──────────────────────────────────────────


def imported_modules() -> set[str]:
    """Every module named in an import statement in the stub's own source."""
    tree = ast.parse(authored_source(stub))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_the_stub_imports_no_other_engine_no_application_layer_and_no_brain() -> None:
    """AL-INV-5 — engines never call each other. AL-INV-4 — engines never touch state.

    The Brain is excluded separately: `BLUEPRINT:87` builds the real Brain
    inside P4 and before Engine 3, so an Engine 3 that imported the Brain stub
    at P3 would be depending on a seam it does not own yet.
    """
    forbidden = sorted(
        name
        for name in imported_modules()
        if name.startswith(
            ("accountant_dad.engines", "accountant_dad.services", "accountant_dad.brain")
        )
    )
    assert forbidden == [], (
        f"the stub imports {forbidden}. Engines never call each other (AL-INV-5), "
        "never read workflow state (AL-INV-4), and Engine 3's Brain arrives at P4."
    )


def test_the_stub_imports_nothing_that_could_make_it_non_deterministic() -> None:
    """No clock, no randomness, no filesystem, no network.

    Asserted on the import list rather than by running it twice: two equal
    results prove determinism for one input, an absent `random` proves it for
    every input.
    """
    banned = {"random", "secrets", "time", "datetime", "os", "pathlib", "socket", "urllib", "uuid"}
    assert imported_modules() & banned == set()


def test_the_stub_lives_where_the_freeze_guard_permits_a_stub() -> None:
    """`test_package.py` allows `engines/accounting_engine/stub` and nothing else here.

    Named explicitly so a rename shows up as a failure in the module that owns
    the file, not only in the freeze guard.
    """
    path = authored_path(stub)
    assert path.name == "stub.py"
    assert path.parent.name == "accounting_engine"
    assert path.parent.parent.name == "engines"


# ── 4. the citations, read off disk ───────────────────────────────────────


def line_of(document: Path, number: int) -> str:
    """One 1-indexed line of a locked document."""
    return document.read_text(encoding="utf-8").splitlines()[number - 1]


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (147, "Never modify the Business Understanding Object"),
        (185, "Why this decision exists"),
        (191, "not infer one from prose"),
        (196, "The decision could not be completed"),
        (259, "Invent missing facts"),
        (265, "Pretend assumptions are confirmed facts"),
        (269, "not an exception and not a guess"),
        (277, "Never guess"),
        (582, "never a rounding line to be invented"),
        (609, "an unassessed risk is not a zero risk"),
        (659, "does not complete the decision by assumption"),
        (669, "Nothing may assume silently"),
        (713, "High confidence cannot exist when critical information is uncertain"),
        (770, "with the gap named is a **success**"),
    ],
)
def test_the_engine_3_lines_the_stub_cites_say_what_it_claims(number: int, expected: str) -> None:
    """A citation that drifts is a lie a comment cannot catch."""
    assert expected in line_of(ENGINE_3, number)


def test_the_blueprint_line_the_stub_cites_forbids_an_accuracy_claim_at_p3() -> None:
    text = line_of(BLUEPRINT, 136)
    assert "no accuracy claim permitted at this phase" in text
    assert "Transaction ID intact" in text
