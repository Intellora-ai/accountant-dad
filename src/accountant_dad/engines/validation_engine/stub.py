"""Engine 5's P3 stub — it emits a Validation Decision, and it validates nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` — P3 is the walking skeleton, and it ends
with *"no accuracy claim permitted at this phase."* So this module has exactly
one job, and it is two requirements pulling against each other: produce a
STRUCTURALLY VALID artifact while FABRICATING NOTHING. Everything below is the
resolution of that tension, and none of it is stylistic.

IT CANNOT APPROVE. THIS IS THE WHOLE DESIGN.
    `SYSTEM_INVARIANTS.md` INV-8 puts permission to execute HERE, before
    execution. What is downstream of this artifact is Engine 6, and downstream
    of Engine 6 is Tally — so an approval this artifact carries wrongly is never
    caught later, because later is someone's actual books. A stub that emitted
    `Approved` would have fabricated permission to post, which is categorically
    the worst thing a file in this repository can do (Law 24, non-goal B.8).

    `Rejected` is not a guess about the Accounting Decision either.
    `ACCOUNTING_DEFINITIONS.md:128-133` defines safe as an **iff** over four
    conditions — correct · every fact traceable to an evidence reference · no
    Critical finding standing · the period open and posting permitted. This
    module establishes NONE of the four. Under an iff, none-established is
    not-safe, and `ENGINE_5:148` is what not-safe is called: *"Rejected |
    Unsafe. | Prohibited."* The status is therefore derived from the definition,
    not chosen for convenience.

    `Clarification Required` was the other non-approving status, and it would be
    a fabrication. `ENGINE_5:147` — it means *"the decision may become correct
    with additional information."* The stub reads nothing about the decision, so
    that is a claim it is in no position to make. `ENGINE_5:528` also routes it
    back through the clarification loop for a fresh Accounting Decision, which
    this stub would reject identically — a P3 skeleton that never terminates.

IT NAMES NO DEFECT IT DID NOT DETECT.
    Naming a fake defect is the same fabrication as a fake approval, pointed the
    other way. So the finding says the one thing that is true — that no
    validation was performed — and says in its own text that no defect in the
    Accounting Decision was detected and none is alleged.

    A finding is required at all because `ENGINE_5:228` refuses the bare
    *"Validation Failed."* — *"Always exactly why"* — and `validation.py`
    enforces it: a non-approving status with all four issue lists empty is
    rejected by the model. `ENGINE_5:219-226` fixes the six things a finding
    must carry, and `ENGINE_5:571` requires evidence references on every one.

    `failed_validation_rules` is deliberately EMPTY. A named failed rule asserts
    that a rule ran and did not hold. No rule ran. Filling that tuple to look
    thorough would be inventing the very evidence the finding disclaims.

    `Severity.CRITICAL`, from `ENGINE_5:156` — *"Execution prohibited. Must be
    resolved before Engine 6."* That is the literal state of affairs. Anything
    lower would be a downgrade, and `ENGINE_5:161` — *"Severity must never be
    hidden or downgraded without evidence."* `ENGINE_5:442` points the same way:
    *"Unknown risk defaults to higher severity. An unassessed risk is never a
    zero risk."* `Severity` is an unordered plain `Enum` on purpose, so nothing
    here compares severities; the value is picked from a rule, not ranked.

THE RESPONSIBLE ENGINE IS THE LEAST-INVENTIVE FIELD AVAILABLE, AND IS STATED.
    `ENGINE_5:232` — *"Every validation issue points back to Engine 1, 2, 3 or
    4"* — and `validation.py` makes `responsible_engine` required with no
    default and no `None`. There is no "nobody" value, and the real cause here
    is that Engine 5 is unimplemented, which is not on the blameable list
    (Validation blaming itself leaves a finding nobody can act on).

    So the field is filled with the owner of the artifact under validation:
    Engine 3 produced the Accounting Decision this decision relates to, and the
    routing pointer has to point somewhere the work can resume. It is a ROUTING
    field here, not an allegation, and the finding's own prose says so, in
    words, so no reader can mistake the two.

IT VALIDATES NOTHING, AND CANNOT ACCIDENTALLY START.
    The finding and the reasoning are module-level constants, built once, at
    import, from nothing. They cannot vary with the input because there is no
    input in scope where they are built. That is the same construction as
    `brain/stub.py`'s `KNOWS_NOTHING`, for the same reason: a stub that branched
    would have behaviour to get wrong, and a test asserting "it decides nothing"
    would start passing for the wrong reason the moment someone taught it a
    special case.

    The Accounting Decision is read for exactly two things, both identity:
    `related_decision_id` and `related_artifact_version` (`ENGINE_5:126-127`).
    No accounting field is read, so no accounting content can reach the output.
    Copying an identifier forward is not reasoning about it — INV-9 forbids an
    identifier INFLUENCING a decision, and nothing here branches on one.

VALIDATION ONLY VALIDATES — AND CANNOT REPAIR, STRUCTURALLY.
    `ENGINE_5:209` lists *"repair accounting mistakes"* among the MUST NEVERs;
    `ENGINE_5:211` — *"Validation only validates"*; `ENGINE_5:213-215` — *"it
    never fixes them. It reports them."* Nothing here mitigates that by
    discipline. The only value this function constructs is a `ValidationDecision`,
    and `validation.py` gives a repair nowhere to sit — no corrected ledger, no
    revised amount, `extra` forbidden. The input is never modified and never
    returned; artifacts are frozen (INV-5), so it could not be.

CONFIDENCE IS THE FLOOR, AND THAT IS A DERIVED VALUE.
    `confidence.py` — the score is *"the system's degree of confidence in an
    artifact's correctness."* Here it grades the validation, and no validation
    happened, so the honest score is the bottom of the scale. `ENGINE_5:209`
    forbids inventing confidence and `ENGINE_5:558` requires validation
    confidence never exceed upstream confidence — the floor satisfies that
    against every possible upstream value, which no other constant does.

NO CLOCK, NO RANDOMNESS, NO I/O, NO DEPENDENCY, NO AI.
    The identity envelope and the timestamp are parameters, not minted here.
    `ArtifactId.new()` is a UUID4 and `datetime.now()` is a clock; both would
    make this function's output unreproducible and its tests unable to assert
    equality. The Application Layer owns lifecycle (INV-4, AL-INV-4) and is
    where those values come from. Two calls with the same arguments return
    equal artifacts, and that is asserted.

    Nothing here imports another engine (AL-INV-5 — engines never call each
    other) or `accountant_dad.services` (AL-INV-4 — the Application Layer calls
    engines, never the reverse). Both are asserted from the module's own import
    graph rather than trusted.
"""

from __future__ import annotations

from datetime import datetime

from accountant_dad.artifacts.decision import AccountingDecision
from accountant_dad.artifacts.validation import (
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationFinding,
    ValidationStatus,
)
from accountant_dad.confidence import MIN as CONFIDENCE_FLOOR
from accountant_dad.identity import IdentityEnvelope

#: The only evidence behind the only claim this module makes: that no validation
#: was performed. The module IS the proof — read it and there is no validation
#: rule in it. Derived from `__name__` rather than written out, so the reference
#: stays true if the module ever moves instead of quietly going stale.
STUB_EVIDENCE_REFERENCE = f"module:{__name__}"

#: Built once, from nothing, at import. It cannot describe the Accounting
#: Decision because no Accounting Decision is in scope here — which is what
#: makes "this stub inspected nothing" a structural fact rather than a promise.
NO_VALIDATION_PERFORMED = ValidationFinding(
    what_failed="No validation was performed on the related Accounting Decision.",
    why_it_failed=(
        "Engine 5 is a P3 walking-skeleton stub. It applies no validation rule and "
        "reads no accounting field, so none of the four conditions an entry must "
        "satisfy to be safe to post has been established. No defect in the "
        "Accounting Decision was detected, and none is alleged."
    ),
    # A routing pointer to the owner of the artifact under validation, not an
    # accusation against Engine 3. See THE RESPONSIBLE ENGINE above.
    responsible_engine=ResponsibleEngine.ACCOUNTING,
    # The artifact TYPE. Its identifier travels in `related_decision_id`, where
    # it is a typed field rather than prose an engine could later read (INV-9).
    affected_artifact="Accounting Decision",
    blocking_severity=Severity.CRITICAL,
    recommended_next_step=(
        "Do not post. Implement Engine 5 and validate this Accounting Decision "
        "before any approval is issued."
    ),
    supporting_evidence_references=(STUB_EVIDENCE_REFERENCE,),
)

#: `ENGINE_5:556` — every rejection must be explainable. This is the explanation,
#: and it explains the stub rather than the decision, because the stub is the
#: only thing it knows anything about.
STUB_REASONING = (
    "Rejected because validation has not been implemented, not because a defect was "
    "found. An entry is safe to post only if it is correct, every fact it rests on is "
    "traceable, no Critical finding stands and the period is open. This stub "
    "establishes none of those, so the entry is not safe and must not proceed to "
    "execution."
)


def validate(
    decision: AccountingDecision,
    /,
    *,
    identity: IdentityEnvelope,
    validation_timestamp: datetime,
) -> ValidationDecision:
    """Emit a Validation Decision that cannot approve, for any input, ever.

    `decision` is read for its identity only — the decision id and version the
    result relates to (`ENGINE_5:126-127`). It is never modified and never
    returned; artifacts are immutable (INV-5) and validation cannot repair
    (`ENGINE_5:213`).

    `identity` and `validation_timestamp` are supplied by the caller because a
    UUID4 and a wall clock would make this function irreproducible. The
    Application Layer owns lifecycle (INV-4).

    Raises `ValueError` if the two artifacts do not share a Transaction ID. That
    mismatch cannot be reported as a finding — the fault would lie with the
    Application Layer, which is not on the blameable list (`ENGINE_5:232`) — and
    emitting the artifact anyway would break the one-transaction-one-id chain
    that P3 exists to prove intact. Failing loudly is the only honest option
    left (Law 11).
    """
    if identity.transaction_id != decision.identity.transaction_id:
        raise ValueError(
            "the Validation Decision and the Accounting Decision it relates to must "
            "carry the same Transaction ID; a Validation Decision filed against a "
            "different business event breaks the audit chain (INV-2, INV-3)"
        )

    return ValidationDecision(
        identity=identity,
        related_decision_id=decision.identity.artifact_id,
        related_artifact_version=decision.identity.version,
        validation_status=ValidationStatus.REJECTED,
        validation_findings=(NO_VALIDATION_PERFORMED,),
        validation_errors=(),
        validation_warnings=(),
        validation_risks=(),
        # Empty on purpose. No rule ran, so no rule failed.
        failed_validation_rules=(),
        supporting_evidence_references=(STUB_EVIDENCE_REFERENCE,),
        validation_confidence=CONFIDENCE_FLOOR,
        validation_reasoning=STUB_REASONING,
        validation_timestamp=validation_timestamp,
    )
