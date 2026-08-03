"""The Knowledge Brain's interface contract — INV-12, and nothing else.

> **Knowledge is shared; authority is not.** (`SYSTEM_INVARIANTS.md` INV-12)

Written before the implementation. Every test names the sentence it defends,
and the dangerous direction is always the permissive one: a predicate that lets
a decision through wearing knowledge's clothing is worse than one that rejects
a well-formed answer, because nothing downstream can tell that a decision was
made outside the engine that owns it (`src/brain/README.md`, "Boundary").

Two halves, tested separately because they fail differently:

  the TYPE     makes a decision unrepresentable — `KnowledgeAnswer` is frozen,
               forbids extra fields, and has no slot a treatment, ledger, rate,
               approval, confidence or instruction could occupy.

  the PREDICATE catches what the type cannot: a Brain whose signature promises
               a `KnowledgeAnswer` and whose runtime hands back something else.
               A static signature is a promise; `_LyingBrain` below is what a
               broken promise looks like, and it is the whole point of this
               deliverable.

The last two tests assert the contract's LIMITS rather than its powers. A limit
nobody wrote down gets mistaken for coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from accountant_dad.knowledge_contract import (
    AdvisoryViolation,
    KnowledgeAnswer,
    KnowledgeBrain,
    KnowledgeQuestion,
    KnowledgeStatement,
    violates_advisory_contract,
)

#: Quoted from `src/brain/README.md`, "The distinction that matters" — the
#: worked example of a question the Brain is allowed to be asked.
A_QUESTION = "What does the standard say about capitalising a laptop?"


def statement(
    # Deliberately contentless. Real accounting knowledge is P4 and frozen, and
    # a fixture asserting what a standard actually says would be an unverified
    # accounting claim (Law 24) sitting in a P2 file.
    text: str = "what the cited paragraph says, as the source states it",
    source: str = "a citation into the source this statement came from",
) -> KnowledgeStatement:
    return KnowledgeStatement(statement=text, source_reference=source)


def answer(*statements: KnowledgeStatement) -> KnowledgeAnswer:
    return KnowledgeAnswer(statements=statements)


# ── the doubles ──────────────────────────────────────────────────────────────


class _CompliantBrain:
    """Answers the question with knowledge and a source. Nothing else."""

    def answer(self, _question: KnowledgeQuestion) -> KnowledgeAnswer:
        return answer(statement())


class _SilentBrain:
    """Knows nothing about the question and says so.

    *"Gaps stay gaps. An absent fact is marked absent until supplied. No
    defaults, no conventions, no most-common-value."* (`SYSTEM_INVARIANTS.md`,
    "Uncertainty, stated once".) An empty answer is the honest one; a contract
    that forbade it would be a contract that required invention.
    """

    def answer(self, _question: KnowledgeQuestion) -> KnowledgeAnswer:
        return answer()


@dataclass(frozen=True, slots=True)
class _DecisionShapedAnswer:
    """*"✗ Brain returns: 'Treat as Office Equipment.'"* (`src/brain/README.md`)

    Slotted on purpose: it carries no `__dict__`, so a predicate that only read
    instance dictionaries would report this object as carrying nothing at all.
    """

    decision: str
    recommended_ledger: str


class _LyingBrain:
    """Type-checks as a Brain. Returns a decision at runtime.

    mypy reads `-> KnowledgeAnswer` and is satisfied. This is the exact failure
    the runtime predicate exists for, and the reason the contract is not
    "a Protocol and nothing more".
    """

    def answer(self, _question: KnowledgeQuestion) -> KnowledgeAnswer:
        return _DecisionShapedAnswer(  # type: ignore[return-value]
            decision="capitalise it",
            recommended_ledger="Office Equipment",
        )


class _RogueAnswer:
    """Deliberately empty. Its payload is whatever a test attaches to it."""


def rogue_carrying(*fields: str) -> object:
    payload = _RogueAnswer()
    for field in fields:
        payload.__dict__[field] = "what a Brain had no business returning"
    return payload


# ── INV-12 — the Brain returns knowledge, with its source reference ──────────


def test_a_well_formed_answer_violates_nothing() -> None:
    # The false-positive guard, and the reason the predicate tokenises a field
    # name instead of matching substrings: `statements` contains the substring
    # "state", which is a forbidden workflow marker. A naive substring match
    # would report every single compliant answer as carrying workflow, and a
    # predicate that fires on everything enforces nothing.
    assert violates_advisory_contract(answer(statement())) == ()


def test_an_answer_with_no_statements_is_still_compliant() -> None:
    # "I do not know" must be expressible, or the contract forces invention.
    assert violates_advisory_contract(answer()) == ()


def test_a_statement_must_carry_its_source() -> None:
    # `src/brain/README.md`: *"The Brain returns: Knowledge, with its source
    # reference."* A sourceless statement is an assertion, and an assertion the
    # Brain made up is the hallucination this whole architecture exists to make
    # structurally impossible (CLAUDE.md §B.8).
    with pytest.raises(ValidationError):
        KnowledgeStatement(statement="anything at all", source_reference="")


def test_a_statement_must_actually_say_something() -> None:
    with pytest.raises(ValidationError):
        KnowledgeStatement(statement="", source_reference="a citation")


def test_a_question_must_actually_ask_something() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuestion(question="")


def test_an_answer_cannot_be_edited_after_it_is_returned() -> None:
    # An engine that could rewrite the answer it was given could launder its own
    # decision as Brain knowledge, and the reasoning trail would cite a source
    # that never said it.
    returned = answer(statement())
    with pytest.raises(ValidationError):
        returned.statements = ()


def test_the_statements_in_an_answer_cannot_be_appended_to() -> None:
    # `frozen=True` stops the field being rebound; it does not stop what the
    # field holds being mutated. A list would let a caller append a statement
    # to an answer the Brain already returned, and the model would be immutable
    # while its contents were not.
    #
    # Found by mutation, not by inspection: swapping the tuple for a list broke
    # nothing else in this file. The rule had been written in a comment and
    # defended by nobody.
    returned = answer(statement())
    with pytest.raises(AttributeError):
        returned.statements.append(statement())  # type: ignore[attr-defined]


def test_an_answer_refuses_a_field_the_contract_never_granted() -> None:
    # `extra="forbid"` is what makes "it may never return a ledger to use" a
    # property of the type rather than a rule under review.
    with pytest.raises(ValidationError):
        KnowledgeAnswer(statements=(), recommended_ledger="Office Equipment")  # type: ignore[call-arg]


def test_a_question_cannot_smuggle_the_transaction_it_belongs_to() -> None:
    # AL-INV-8: *"The Brain provides knowledge. It never routes, sequences,
    # retries, holds state or decides"*, and it never observes workflow. A
    # Transaction ID on the question is exactly how it would start observing.
    with pytest.raises(ValidationError):
        KnowledgeQuestion(question=A_QUESTION, transaction_id="anything")  # type: ignore[call-arg]


def test_a_question_cannot_name_who_is_asking() -> None:
    # `src/brain/README.md`: *"Identical for every engine. No engine gets a
    # privileged channel."* A Brain that knows who asked can answer one engine
    # differently from another, which is a privileged channel built out of a
    # field name. INV-9 says the same thing from the other side: identity never
    # influences reasoning.
    with pytest.raises(ValidationError):
        KnowledgeQuestion(question=A_QUESTION, asking_engine="Engine 3")  # type: ignore[call-arg]


# ── the predicate: what a Brain returned, judged at runtime ──────────────────

#: One representative payload per forbidden category, each traced to the
#: sentence that forbids it. `_LyingBrain` proves the category matters; this
#: table proves each one is named separately, so a conformance failure says
#: WHICH rule broke.
ROGUE_FIELDS: tuple[tuple[str, AdvisoryViolation], ...] = (
    ("decision", AdvisoryViolation.RETURNS_A_DECISION),
    ("recommended_treatment", AdvisoryViolation.RETURNS_A_TREATMENT),
    ("approval", AdvisoryViolation.RETURNS_AN_APPROVAL),
    ("ledger_to_use", AdvisoryViolation.RETURNS_A_LEDGER),
    ("gst_rate", AdvisoryViolation.RETURNS_A_RATE),
    ("instruction", AdvisoryViolation.RETURNS_AN_INSTRUCTION),
    ("confidence", AdvisoryViolation.RETURNS_A_CONFIDENCE),
    ("artifact_id", AdvisoryViolation.RETURNS_AN_ARTIFACT),
    ("next_stage", AdvisoryViolation.RETURNS_WORKFLOW),
    ("owner", AdvisoryViolation.RETURNS_AN_AUTHORITY_ROW),
    ("is_binding", AdvisoryViolation.BINDS_THE_CALLER),
)


@pytest.mark.parametrize(("field", "expected"), ROGUE_FIELDS)
def test_each_forbidden_payload_is_named_by_its_own_violation(
    field: str, expected: AdvisoryViolation
) -> None:
    # Equality, not `in`. `in` would pass while the predicate shouted every
    # violation at once, which names nothing.
    assert violates_advisory_contract(rogue_carrying(field)) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        expected,
    )


def test_every_violation_the_contract_defines_is_reachable() -> None:
    # A violation code nothing can produce is a rule that reads as enforced and
    # enforces nothing — the false green this file exists to prevent.
    reachable = {AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER} | {v for _, v in ROGUE_FIELDS}
    assert set(AdvisoryViolation) == reachable


def test_a_payload_carrying_two_forbidden_things_reports_both() -> None:
    found = violates_advisory_contract(rogue_carrying("ledger_to_use", "gst_rate"))
    assert found == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_LEDGER,
        AdvisoryViolation.RETURNS_A_RATE,
    )


def test_a_forbidden_payload_cannot_hide_behind_a_naming_convention() -> None:
    # `recommendedLedger` and `recommended_ledger` are the same payload. A
    # predicate that only understood snake_case would be evaded by a style
    # choice.
    assert violates_advisory_contract(rogue_carrying("recommendedLedger")) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_TREATMENT,
        AdvisoryViolation.RETURNS_A_LEDGER,
    )


def test_a_mapping_is_judged_by_its_keys() -> None:
    # A Brain that returns a plain dict is the cheapest way to dodge a schema.
    returned = {"decision": "capitalise it", "confidence": 0.91}
    assert violates_advisory_contract(returned) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_DECISION,
        AdvisoryViolation.RETURNS_A_CONFIDENCE,
    )


def test_a_slotted_payload_is_judged_by_its_slots() -> None:
    # `_DecisionShapedAnswer` has no `__dict__` at all. Reading only instance
    # dictionaries would report it as carrying nothing.
    returned = _DecisionShapedAnswer(decision="capitalise it", recommended_ledger="Office Equip")
    assert violates_advisory_contract(returned) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_DECISION,
        AdvisoryViolation.RETURNS_A_TREATMENT,
        AdvisoryViolation.RETURNS_A_LEDGER,
    )


@pytest.mark.parametrize("returned", [None, "Treat as Office Equipment.", 42, (), object()])
def test_anything_that_is_not_a_knowledge_answer_is_rejected(returned: object) -> None:
    # The complete half of the predicate, and the only half that cannot be
    # evaded by renaming a field: exactly one type may cross this boundary.
    assert violates_advisory_contract(returned) == (AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,)


def test_a_subclass_of_the_answer_is_not_an_answer() -> None:
    # The inheritance escape hatch. `isinstance` would accept this: it IS a
    # KnowledgeAnswer, with a decision bolted on. Exact-type matching is what
    # closes it, and it closes it for every field name, including ones no
    # denylist anticipated.
    class _WidenedAnswer(KnowledgeAnswer):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
        recommended_ledger: str

    widened = _WidenedAnswer(statements=(statement(),), recommended_ledger="Office Equipment")
    assert violates_advisory_contract(widened) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_TREATMENT,
        AdvisoryViolation.RETURNS_A_LEDGER,
    )


def test_a_private_attribute_is_machinery_and_not_part_of_the_payload() -> None:
    # Underscore names are implementation, by Python convention: a caller
    # cannot read `_decision` as returned data. Without this rule pydantic's own
    # `__dict__` and `__pydantic_extra__` slots would be scanned as though the
    # Brain had returned them.
    #
    # It is not a hole. The complete check still rejects the object; only the
    # diagnosis is silent, and the diagnosis never claimed completeness.
    assert violates_advisory_contract(rogue_carrying("_decision")) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
    )


# ── the interface, exercised end to end ──────────────────────────────────────


def test_a_compliant_brain_satisfies_the_interface_and_the_predicate() -> None:
    # The Protocol is structural: `_CompliantBrain` inherits nothing, and mypy
    # checks this assignment. The predicate then judges what actually came back.
    brain: KnowledgeBrain = _CompliantBrain()
    assert violates_advisory_contract(brain.answer(KnowledgeQuestion(question=A_QUESTION))) == ()


def test_a_brain_that_knows_nothing_satisfies_the_interface_and_the_predicate() -> None:
    brain: KnowledgeBrain = _SilentBrain()
    assert violates_advisory_contract(brain.answer(KnowledgeQuestion(question=A_QUESTION))) == ()


def test_a_brain_that_returns_a_decision_is_caught_through_the_real_call() -> None:
    # The deliverable, in one test. The signature promised a KnowledgeAnswer;
    # the runtime handed back a decision and a ledger to use. The predicate is
    # called on exactly what the caller received, and it names both.
    brain: KnowledgeBrain = _LyingBrain()
    returned = brain.answer(KnowledgeQuestion(question=A_QUESTION))
    assert violates_advisory_contract(returned) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
        AdvisoryViolation.RETURNS_A_DECISION,
        AdvisoryViolation.RETURNS_A_TREATMENT,
        AdvisoryViolation.RETURNS_A_LEDGER,
    )


def test_the_returned_violations_are_ordered_and_carry_stable_names() -> None:
    # A conformance report is read by a human and diffed by a machine. Both
    # need the same run to produce the same tuple in the same order.
    found = violates_advisory_contract(rogue_carrying("owner", "confidence"))
    assert [str(v) for v in found] == [
        "not_a_knowledge_answer",
        "returns_a_confidence",
        "returns_an_authority_row",
    ]


# ── the limits, asserted so they cannot be mistaken for coverage ─────────────


def test_an_unanticipated_field_name_is_rejected_but_not_diagnosed() -> None:
    # A rogue that names its decision `x` gets caught by the type rule and
    # diagnosed by nothing. The denylist is diagnosis; the allowlist is the
    # enforcement, and only the allowlist is complete.
    assert violates_advisory_contract(rogue_carrying("x")) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
    )


def test_a_decision_written_as_prose_is_not_caught_and_that_is_the_known_hole() -> None:
    # `src/brain/README.md`: *"✗ Brain returns: 'Treat as Office Equipment.'"*
    # Written into a well-formed statement, that sentence passes — no type can
    # read English, and reading it would require the very reasoning the Brain is
    # forbidden to do (Law 53: the hard problem was transformed, not solved).
    #
    # Asserted rather than described, so the day someone believes this predicate
    # proves the Brain never decides, this test says otherwise in writing.
    laundered = KnowledgeAnswer(
        statements=(
            KnowledgeStatement(
                statement="Treat as Office Equipment.",
                source_reference="a citation that says no such thing",
            ),
        )
    )
    assert violates_advisory_contract(laundered) == ()
