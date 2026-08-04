"""The Knowledge Brain's interface contract. The interface only — never the Brain.

`SYSTEM_INVARIANTS.md` INV-12: *"Knowledge is shared; authority is not. …
**Advisory, never binding.** Any engine may ignore it, recording why. It may
never return a decision, recommendation, approval, ledger, rate or instruction,
and owns no decisions, artifacts, confidence or workflow."*

    Knowledge flows into engines. Decision authority never leaves engines.

`MVP_IMPLEMENTATION_BLUEPRINT.md` §2 schedules this at P2 because *"the Brain
never returns a decision"* is a pure predicate — no AI, no ground truth, no
cost — and because engines call the interface from P3, so leaving it undefined
would be a forward dependency. The Brain's *knowledge* is P4 and is frozen.
**There is no knowledge in this module and there must never be any.**

## The transform (Law 53)

The hard problem is *"is this English sentence a decision?"* — unsolvable
without the very reasoning the Brain is forbidden to do. The equivalent easier
problem: **make a decision structurally unrepresentable, then check structure.**

    the TYPE      `KnowledgeAnswer` is frozen, forbids extra fields, and has no
                  slot a treatment, ledger, rate, approval, confidence,
                  instruction, artifact, workflow step or authority row could
                  occupy. A decision has nowhere to sit.

    the PROTOCOL  structural, so any Brain implementation is checked by mypy
                  with no inheritance coupling — and it declares exactly one
                  method. A Brain cannot approve, post, route or retry, because
                  the interface has no verb for it.

    the PREDICATE `violates_advisory_contract` judges what a Brain actually
                  returned. A signature is a promise; an implementation that
                  promises `KnowledgeAnswer` and hands back a decision at
                  runtime is the failure this catches.

## What the predicate can and cannot see — stated, not implied

**Complete:** exactly one type may cross the boundary. Anything else is
rejected, whatever its fields are called. That check cannot be evaded.

**Diagnostic, therefore incomplete:** the named categories below are matched on
payload *field names*, so a rogue Brain that calls its decision `x` is rejected
and diagnosed as nothing more specific. Nesting is not searched either. That is
the honest limit, and `test_knowledge_contract.py` asserts it rather than
leaving it to be discovered.

**Outside the contract entirely:** prose. `statement="Post it to Office
Equipment"` is a decision wearing knowledge's clothing and no type can see it.
Requiring every statement to carry a source reference raises the cost of that
lie — a standard has a citation, an invention does not — but does not close it.
Closing it is a conformance and review concern, not a schema one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from enum import StrEnum, auto
from typing import Annotated, Protocol

from pydantic import BaseModel, Field

#: Text that must actually say something. Declared here rather than imported
#: from an artifact module on purpose: the Brain owns no artifacts (INV-12), so
#: its contract must not depend on one. An alias is a shape, not logic.
NonEmptyText = Annotated[str, Field(min_length=1)]


class KnowledgeQuestion(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What an engine asks. One field, and the omissions are the point.

    **No asker.** *"Identical for every engine. No engine gets a privileged
    channel"* (`src/brain/README.md`, Interface). A Brain that knows who asked
    can answer one engine differently from another, and the privileged channel
    is then built out of a field name. INV-9 says the same from the other side:
    identity never influences reasoning.

    **No Transaction ID.** AL-INV-8: *"The Brain provides knowledge. It never
    routes, sequences, retries, holds state or decides"*, and it never observes
    workflow. A Transaction ID is how observing workflow would start.

    `extra="forbid"` is what makes both of those structural rather than
    remembered.
    """

    # A dict literal, not ConfigDict(...): ConfigDict is a TypedDict carrying
    # Any, and disallow_any_explicit is on. Same config, no suppression.
    model_config = {"frozen": True, "extra": "forbid"}

    question: NonEmptyText


class KnowledgeStatement(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One thing the Brain knows, and where it came from.

    `src/brain/README.md`: *"The Brain returns: Knowledge, with its source
    reference."* Both fields are non-empty by construction. A statement with no
    source is not knowledge — it is an assertion, and an assertion the Brain
    produced from nothing is the hallucination the six-engine split exists to
    make structurally impossible (CLAUDE.md §B.8).

    The Brain *"may state what a rule says and what it implies; it may never
    state what should be done."* Which side of that line a given sentence falls
    on is not decidable from its shape — see the module docstring on prose.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    statement: NonEmptyText
    source_reference: NonEmptyText


class KnowledgeAnswer(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Everything the Brain may return, and nothing else.

    Deliberately allowed to be empty. *"Gaps stay gaps. An absent fact is
    marked absent until supplied. No defaults, no conventions, no
    most-common-value"* (`SYSTEM_INVARIANTS.md`, "Uncertainty, stated once").
    A contract that required at least one statement would be a contract that
    required invention whenever the Brain knew nothing.

    Carries no confidence. INV-12 is explicit that the Brain *"owns no
    decisions, artifacts, confidence or workflow"*, and
    `ENGINE_5_VALIDATION_ENGINE_RULES.md` §8 that it may never *"change
    confidence"*. `src/brain/README.md` says something narrower — that the
    Brain returns *"the Brain's own confidence in the knowledge"* — and the two
    disagree. The System Invariants outrank a README (CLAUDE.md §O,
    precedence), and "Confidence" is one of the seven load-bearing undefined
    terms (Law 54), so a confidence field here would be an undefined quantity
    added against the highest authority. It is left out and the contradiction
    is reported rather than resolved in code (CLAUDE.md §M).
    """

    model_config = {"frozen": True, "extra": "forbid"}

    #: A tuple, not a list. A list would let a caller append a statement to a
    #: frozen answer and `frozen=True` would never see it.
    statements: tuple[KnowledgeStatement, ...]


class KnowledgeBrain(Protocol):
    """The whole interface. One verb: it answers.

    A `Protocol`, so any implementation is checked structurally by mypy with no
    inheritance coupling — `src/brain/` never imports this to subclass it, and
    engines depend on the shape rather than on a class.

    The single method is the structural half of *"advisory, never binding"*.
    There is no `approve`, no `post`, no `route`, no `retry`, no callback the
    caller must honour: a Brain cannot bind anyone because the interface gives
    it no way to act. The caller receives a value and is free to ignore it,
    recording why in its own reasoning.

    Deliberately **not** `@runtime_checkable`. `isinstance` against a Protocol
    checks method names only, so a Brain that returns a decision would pass it
    — a false green in the exact place this contract is load-bearing. What a
    Brain returned is judged by `violates_advisory_contract`, on the value.

    The parameter is positional-only so implementations may name it anything,
    including `_question` when they do not read it.
    """

    def answer(self, question: KnowledgeQuestion, /) -> KnowledgeAnswer: ...


class AdvisoryViolation(StrEnum):
    """One name per rule, so a failure says WHICH rule broke.

    Values are lowercase member names: stable, machine-readable, diffable
    across runs. Conformance reads these; humans read them too.
    """

    #: The complete check. `src/brain/README.md`, Interface — a Knowledge
    #: Answer, carrying knowledge and its source reference, is the only thing
    #: permitted to cross this boundary.
    NOT_A_KNOWLEDGE_ANSWER = auto()

    #: INV-12 · `SYSTEM_BOUNDARIES.md` §16 · `src/brain/README.md` — *"may
    #: never return a decision"*. `ENGINE_6` §7: never *"make execution
    #: decisions"*.
    RETURNS_A_DECISION = auto()

    #: `src/brain/README.md` · AL-INV-8 — *"a recommended treatment"*. The
    #: worked counter-example is *"✗ Brain returns: 'Treat as Office
    #: Equipment.'"*
    RETURNS_A_TREATMENT = auto()

    #: `src/brain/README.md` — *"an approval"*. `ENGINE_5` §8: never *"approve
    #: validation"* or *"reject validation"*. `ENGINE_4` §8: never *"approve
    #: clarification"*.
    RETURNS_AN_APPROVAL = auto()

    #: `src/brain/README.md` — *"a ledger to use"*. Chart-of-accounts
    #: *references* are knowledge it may provide; the ledger to post to is the
    #: engine's decision.
    RETURNS_A_LEDGER = auto()

    #: `src/brain/README.md` — *"a rate to use"*. GST *rules* are knowledge;
    #: the rate to apply is the decision.
    RETURNS_A_RATE = auto()

    #: `src/brain/README.md` — *"an instruction of any kind"*, and the failure
    #: the boundary exists to prevent: *"knowledge shaped as an instruction"*.
    RETURNS_AN_INSTRUCTION = auto()

    #: INV-12 — owns no *"confidence"*. `ENGINE_5` §8: never *"change
    #: confidence"*. `src/brain/README.md`: the confidence types belong to the
    #: engines.
    RETURNS_A_CONFIDENCE = auto()

    #: INV-12 — owns no *"artifacts"*. `src/brain/README.md`: *"it creates
    #: none, owns none, and versions none."* `ENGINE_5` §8 and `ENGINE_6` §7:
    #: never create Validation Decisions or Execution Results.
    RETURNS_AN_ARTIFACT = auto()

    #: INV-12 — owns no *"workflow"*. `src/brain/README.md`: *"it never routes,
    #: orchestrates or sequences anything."* AL-INV-8: never *"routes,
    #: sequences, retries, holds state"*.
    RETURNS_WORKFLOW = auto()

    #: `src/brain/README.md` — *"Ownership stays countable. Every decision has
    #: exactly one owner. A service that decides would be an owner appearing in
    #: no authority table."* INV-12: *"Decision authority never leaves
    #: engines."*
    RETURNS_AN_AUTHORITY_ROW = auto()

    #: INV-12 — *"Advisory, never binding."* `src/brain/README.md`: *"The Brain
    #: informs; it does not constrain"*, and may never *"override engine
    #: outputs"*.
    BINDS_THE_CALLER = auto()


#: The diagnostic layer: one marker set per forbidden category. Order is the
#: order violations are reported in, so a conformance report reads the same way
#: on every run. Markers are whole tokens, never substrings — `statements`
#: contains "state", and a substring match would report every compliant answer
#: as carrying workflow.
_FORBIDDEN_PAYLOADS: tuple[tuple[AdvisoryViolation, frozenset[str]], ...] = (
    (
        AdvisoryViolation.RETURNS_A_DECISION,
        frozenset({"decision", "decisions", "decide", "decided", "verdict"}),
    ),
    (
        AdvisoryViolation.RETURNS_A_TREATMENT,
        frozenset(
            {
                "treatment",
                "treat",
                "recommendation",
                "recommendations",
                "recommended",
                "suggestion",
                "suggested",
            }
        ),
    ),
    (
        AdvisoryViolation.RETURNS_AN_APPROVAL,
        frozenset({"approval", "approve", "approved", "approves", "rejected"}),
    ),
    (AdvisoryViolation.RETURNS_A_LEDGER, frozenset({"ledger", "ledgers"})),
    (AdvisoryViolation.RETURNS_A_RATE, frozenset({"rate", "rates"})),
    (
        AdvisoryViolation.RETURNS_AN_INSTRUCTION,
        frozenset({"instruction", "instructions", "action", "actions", "command", "commands"}),
    ),
    (
        AdvisoryViolation.RETURNS_A_CONFIDENCE,
        frozenset({"confidence", "confidences", "certainty", "score", "scores", "probability"}),
    ),
    (AdvisoryViolation.RETURNS_AN_ARTIFACT, frozenset({"artifact", "artifacts"})),
    (
        AdvisoryViolation.RETURNS_WORKFLOW,
        frozenset(
            {
                "workflow",
                "route",
                "routing",
                "next",
                "stage",
                "state",
                "sequence",
                "retry",
                "retries",
            }
        ),
    ),
    (
        AdvisoryViolation.RETURNS_AN_AUTHORITY_ROW,
        frozenset({"authority", "owner", "owns", "ownership"}),
    ),
    (
        AdvisoryViolation.BINDS_THE_CALLER,
        frozenset({"binding", "binds", "mandatory", "must", "required", "override", "overrides"}),
    ),
)

#: `recommendedLedger` and `recommended_ledger` are the same payload. A rogue
#: Brain does not get to hide one behind a naming convention.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NOT_A_TOKEN = re.compile(r"[^a-z0-9]+")


def _tokens(name: str) -> frozenset[str]:
    split = _CAMEL_BOUNDARY.sub("_", name).lower()
    return frozenset(token for token in _NOT_A_TOKEN.split(split) if token)


def _payload_names(value: object) -> frozenset[str]:
    """Every name under which `value` carries something.

    Three shapes, because a Brain that wanted to dodge a schema would reach for
    whichever one is not covered: a mapping (keys are the payload), an ordinary
    object (its instance dictionary), and a slotted object (no instance
    dictionary at all — reading only `__dict__` would report it as empty).
    """
    names: set[str] = set()

    if isinstance(value, Mapping):
        names.update(str(key) for key in value)
    else:
        attributes = getattr(value, "__dict__", None)
        if isinstance(attributes, Mapping):
            names.update(str(key) for key in attributes)
        for klass in type(value).__mro__:
            declared: object = getattr(klass, "__slots__", ())
            if isinstance(declared, str):
                names.add(declared)
            elif isinstance(declared, Iterable):
                names.update(str(slot) for slot in declared)

    # A private or dunder name is machinery, not payload — pydantic's own
    # __slots__ would otherwise appear in the name set of every answer.
    return frozenset(name for name in names if not name.startswith("_"))


def violates_advisory_contract(answer: object) -> tuple[AdvisoryViolation, ...]:
    """Every way `answer` breaks the Brain's contract, named. Empty means clean.

    Takes `object`, not `KnowledgeAnswer`, on purpose: the thing worth catching
    is a Brain whose signature says `KnowledgeAnswer` and whose runtime says
    otherwise. A parameter that could only accept a valid answer would only
    ever prove that valid answers are valid.

    Returns a tuple so a caller can report all of it at once. Conformance
    asserts `violates_advisory_contract(returned) == ()`; a human reads the
    names to learn which rule broke.
    """
    found: list[AdvisoryViolation] = []

    # The complete check, and the only one that cannot be evaded by renaming a
    # field. `type(...) is`, not `isinstance`: a subclass IS a KnowledgeAnswer
    # with extra fields bolted on, which is precisely the shape a decision
    # would arrive in.
    if type(answer) is not KnowledgeAnswer:
        found.append(AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER)

    # Run the payload scan unconditionally, including on a genuine
    # KnowledgeAnswer. If this contract is ever widened with a `confidence` or
    # `recommended_ledger` field, the predicate reports it instead of blessing
    # it.
    carried: set[str] = set()
    for name in _payload_names(answer):
        carried |= _tokens(name)

    found.extend(violation for violation, markers in _FORBIDDEN_PAYLOADS if carried & markers)
    return tuple(found)
