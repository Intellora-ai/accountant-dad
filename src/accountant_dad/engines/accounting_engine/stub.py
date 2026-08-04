"""The Accounting Engine stub — it produces a decision, and it decides nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:100` schedules engine stubs 1-6 at P3. `:136`
says what P3 is finished by — the pipeline runs end to end, every artifact is
valid, the Transaction ID is intact — and closes with **"no accuracy claim
permitted at this phase."**

Of the six stubs this is the dangerous one, and the reason belongs above the
code rather than beside it.

WHY A JOURNAL HERE WOULD BE THE WORST THING THIS FILE COULD DO.
    Engine 3 is where a wrong entry would come from. A stub that emitted
    ledgers, debits, credits and a tax treatment would produce an artifact that
    is, at the boundary, INDISTINGUISHABLE from one the real engine produced:
    the same thirteen components, the same balance, the same shape. Validation
    would validate it, Execution would transport it, and every number measured
    downstream would be measuring invention.

    `ENGINE_3:259` — the engine must never *"invent missing facts."* `:265` —
    never *"pretend assumptions are confirmed facts."* `CLAUDE.md` Law 24 —
    never fabricate data. And `CLAUDE.md` §P still freezes accounting logic and
    tax logic outright, so a journal here would cross the build freeze as well
    as the invariant.

    Note which way the balance rule cuts. `decision.py` refuses a COMPLETE
    decision with an empty journal, so "balanced" is not available for free —
    the only way to look complete is to write amounts nobody derived. That is
    the plug figure `ENGINE_3:582` forbids by name: *"an entry that will not
    balance is a doubt to be raised, never a rounding line to be invented."*

THE HONEST DECISION IS THE ONE THAT SAYS IT CANNOT DECIDE — AND THE LOCKED
SCHEMA ALREADY HAS THE WORD FOR IT.
    `ENGINE_3:191` — *"Downstream engines must be able to ask can this move
    forward? and receive a structured answer, not infer one from prose."*
    `:196` names that answer: `INCOMPLETE_INFORMATION_REQUIRED`, *"the decision
    could not be completed."*

    `:659` is the same rule written for `decision_output` in particular — where
    the sub-engine outputs do not support a complete decision it emits that
    status with the required clarification named, and *"does not complete the
    decision by assumption."* At P3 there are no sub-engine outputs at all,
    which is the extreme case of precisely that condition, not an exception to
    it.

    `:770` settles that this is a success rather than a shrug: *"a decision
    marked INCOMPLETE_INFORMATION_REQUIRED with the gap named is a success. A
    COMPLETE decision resting on one silent assumption is a failure, even when
    the assumption is correct."*

WHAT THE ARTIFACT CARRIES, COMPONENT BY COMPONENT, AND WHY EACH CLAIMS NOTHING.

    Debit entries · credit entries — EMPTY. No ledger is named and no amount is
        asserted, so there is nothing to post and nothing to get wrong.
        `decision.py` permits an empty journal only on an INCOMPLETE decision,
        and only when a doubt is named; both conditions hold below.

    Accounting treatment · ledger classification · journal structure · tax
        treatment — all four carry `NOT_DECIDED`, the same string, deliberately.
        The frozen schema types them `NonEmptyText`, so blank is not available
        and something must be written. The only string that asserts nothing is
        one that names the absence, and using ONE constant in all four places
        means a future edit that starts filling in a real ledger name breaks the
        equality a test asserts. A per-field wording would have let one of the
        four drift quietly.

    Decision confidence — the floor, `0.0000`. Confidence is required and any
        value above zero would be a claim about a treatment that does not exist.
        `ENGINE_3:713` — *"High confidence cannot exist when critical
        information is uncertain."* Here every fact is uncertain, so the floor is
        not a conservative choice, it is the only accurate one. INV-2 keeps it
        there: confidence moves when evidence changes, and this file reads no
        evidence.

    Accounting assumptions — EMPTY, and that is a true statement rather than an
        omission. `ENGINE_3:669` — *"Nothing may assume silently."* This file
        assumes nothing because it reasons about nothing; an assumption listed
        here would have to be invented to be listed.

    Risk indicators — EMPTY, and this one is a real tension worth stating rather
        than hiding. `ENGINE_3:609` says an inability to assess risk is itself
        recorded, because *"an unassessed risk is not a zero risk."* Two
        readings were available and the trade-off went this way: an empty tuple
        on an artifact whose status already says nothing was decided cannot be
        read as "this treatment carries no risk", because there is no treatment
        for a risk to attach to. Manufacturing a RiskIndicator instead would
        mean this file authored an Accounting Risk Analysis — the output of
        `risk_analysis` (`ENGINE_3` §8.7), a sub-engine that does not exist
        until P4 and that `CLAUDE.md` §P freezes. Emptiness claims less. The
        field `unresolved_doubts`
        is the one place the schema forces a statement, and that is where the
        whole reason is recorded.

    Unresolved doubts — ONE, naming what is missing and what would resolve it.
        Required by `decision.py`'s validator on an INCOMPLETE decision, and by
        `ENGINE_3:269`: insufficient information *"returns a named output, not
        an exception and not a guess."* `:277` — *"Never guess."*

WHAT IT READS: THE TRANSACTION ID, AND NOTHING ELSE.
    `BLUEPRINT:136` requires the Transaction ID intact across the pipeline, so
    the child artifact carries the parent's. It is copied out of the identity
    envelope and never looked at — INV-9 forbids an identifier INFLUENCING
    reasoning, and there is no reasoning here for one to influence.

    Nothing else in the Business Understanding Object is touched: not the
    narrative, not the six Results, not the unknowns, not the confidence
    assessment. A test feeds two wildly different understandings under one
    Transaction ID and asserts the two decisions are equal, which is the
    strongest available proof that this file reads nothing — and it would break
    the moment someone taught the stub one special case.

    `ENGINE_3:147` — the engine may never modify the Business Understanding
    Object. It cannot: the artifact is frozen, and this file only reads.

WHY THE ARTIFACT ID IS A PARAMETER RATHER THAN MINTED HERE.
    `ArtifactId.new()` is `uuid4`, and a stub that reached for randomness would
    return a different artifact on every call — untestable by equality, and
    carrying a value nobody supplied. The caller passes the identity in; the
    version is 1 and the parent list is empty because `IdentityEnvelope` refuses
    any other combination for an origin version. No clock, no randomness, no
    I/O, no dependency, no engine, no Brain: `decide` is a pure function of its
    two arguments.

    Consequence, stated because a caller needs it: an INCOMPLETE decision routes
    `Accounting → Clarification` in the locked state machine, never straight to
    Validation. Whether that loop terminates is the Application Layer's problem
    (`AL-INV-5` — every artifact passes through it), and it is not solved here.
"""

from __future__ import annotations

from decimal import Decimal

from accountant_dad.artifacts.decision import AccountingDecision, DecisionStatus, UnresolvedDoubt
from accountant_dad.artifacts.understanding import BusinessUnderstandingObject
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope

#: The one string every undecided text component carries. One constant in four
#: places, so a future edit that fills in a real ledger, treatment or tax
#: position breaks an equality rather than passing unnoticed.
NOT_DECIDED = (
    "NOT DECIDED. The P3 walking-skeleton stub applied no accounting rule and "
    "no tax rule, so no accounting treatment, no ledger, no journal structure "
    "and no tax treatment were determined for this transaction. Accounting "
    "logic and tax logic are frozen until P4 (CLAUDE.md section P)."
)

#: `ENGINE_3:185` — every decision must show why it exists. This one exists to
#: prove a seam, and says so instead of implying an accounting reason.
WHY_THIS_DECISION_EXISTS = (
    "No accounting reasoning was performed. This decision exists to prove the "
    "Engine 2 to Engine 3 boundary at P3 and for no other purpose; the nine "
    "sub-engines that would decide anything are scheduled for P4. Insufficient "
    "information returns a named output, not an exception and not a guess "
    "(ENGINE_3:269), and no accuracy claim is permitted at this phase "
    "(MVP_IMPLEMENTATION_BLUEPRINT.md:136)."
)

#: The gap, named. `ENGINE_3:659` — the status is emitted WITH the required
#: clarification, never on its own.
NOTHING_WAS_DECIDED = UnresolvedDoubt(
    missing_fact=(
        "Every fact this decision would have rested on. No transaction was "
        "analysed, no company context was consulted, no accounting rule or tax "
        "rule was applied and no journal was constructed, so nothing about the "
        "accounting treatment of this transaction has been established."
    ),
    required_clarification=(
        "None that a user can answer. What is absent is the Accounting Engine "
        "itself, whose nine sub-engines arrive at P4. Until they exist no "
        "answer to any question can complete this decision, and it must not be "
        "completed by assumption (ENGINE_3:659)."
    ),
)

#: The floor of the agreed scale. Not a placeholder and not a guess — it is the
#: only value that asserts no confidence in a treatment that does not exist.
NO_CONFIDENCE = Decimal("0.0000")


def decide(
    understanding: BusinessUnderstandingObject, decision_id: ArtifactId
) -> AccountingDecision:
    """Emit the decision that says it cannot decide. Reads nothing, invents nothing.

    Pure and total: the same two arguments always produce an equal artifact, and
    there is no input for which this returns something else, raises, or reaches
    for a default. `decision_id` is supplied rather than minted so the result
    stays deterministic (see the module docstring); `understanding` contributes
    exactly one thing, the Transaction ID it must carry forward.
    """
    return AccountingDecision(
        identity=IdentityEnvelope(
            artifact_id=decision_id,
            # An origin version: `IdentityEnvelope` rejects version 1 WITH
            # parents and any later version WITHOUT them, so this pair is the
            # only one a first decision can hold. A correction is a new version
            # (`ENGINE_3:234`) and needs the real engine to author it.
            version=FIRST_VERSION,
            parent_versions=(),
            # BLUEPRINT:136 — Transaction ID intact. Carried by construction
            # rather than checked after the fact, so there is no comparison here
            # that a later edit could get wrong or forget to run.
            transaction_id=understanding.identity.transaction_id,
        ),
        decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
        accounting_treatment=NOT_DECIDED,
        ledger_classification=NOT_DECIDED,
        # Empty on both sides. `decision.py` allows this only for an INCOMPLETE
        # decision that names a doubt, which is exactly the shape emitted here.
        debit_entries=(),
        credit_entries=(),
        journal_structure=NOT_DECIDED,
        tax_treatment=NOT_DECIDED,
        accounting_assumptions=(),
        risk_indicators=(),
        decision_confidence=NO_CONFIDENCE,
        supporting_reasoning=WHY_THIS_DECISION_EXISTS,
        unresolved_doubts=(NOTHING_WAS_DECIDED,),
    )
