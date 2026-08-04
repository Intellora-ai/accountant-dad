"""Engine 4's P3 stub — it emits a Clarification Request, and it judges nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` — P3 permits **no accuracy claim at all**.
`MVP_IMPLEMENTATION_BLUEPRINT.md:86`, written for the Brain stub and binding on
every stub in this phase: it *"proves the seam without knowledge … nothing is
faked as accounting truth."* Those two sentences are the whole design.

IT EMITS. The output is a structurally valid Clarification Request, so the
Accounting → Clarification → Validation seam is exercised before any reasoning
exists behind it, and an Application Layer written against this needs no change
when P4 replaces it.

IT JUDGES NOTHING, AND THAT IS THE HARD HALF.
    Engine 4's real work is two judgements — *which* doubts block
    (`stop_decision`, `ENGINE_4:473-499`) and *what* to ask so a human can
    answer it (`question_generator`, `ENGINE_4:533-557`). A stub can do neither.

    The tempting stub composes a plausible accounting question so the pipeline
    looks alive. At the seam that is **indistinguishable from real judgement** —
    a reader, a test and a downstream engine would all take it for detection
    that happened. `CLAUDE.md` Law 24: never fabricate data. So every field that
    would carry a judgement carries, instead, a stated sentence saying no
    judgement was made. The absence is the content.

WHY A REQUEST EXISTS AT ALL, GIVEN THAT NOTHING WAS DETECTED.
    Not because a doubt was found to block — that is the claim this module must
    never make. `ENGINE_4:499`: *"If necessity cannot be determined safely,
    default to Clarification Required. Never silently ignore uncertainty."* The
    stub cannot run `stop_decision`, so necessity is UNDETERMINED, and the
    specification's documented default for an undetermined necessity is to
    raise one. Emitting is transcription of that rule, not an assessment.

    `ENGINE_4:557` closes the other half: *"An incomplete request that names
    what it could not determine is correct output; a complete-looking request
    that dropped an issue is not."* This request is incomplete and says so in
    every field. That is the shape the specification calls correct.

THE THREE VALUES THAT COULD NOT BE OMITTED, AND WHY NEITHER IS AN ASSESSMENT.

  priority = High           `ENGINE_4:529` — *"Unknown priority defaults to High
                            until sufficient information exists."* The field is
                            mandatory and all four levels imply a severity
                            ranking, so it cannot be left blank. Priority here
                            is UNKNOWN, and High is the value the specification
                            assigns to an unknown one. Read off `:529`, not
                            chosen: the stub ran no `answer_understanding` and
                            has no severity opinion to express.

  clarification_confidence  `ENGINE_4:593` — clarification confidence answers
      = 0.0000              exactly one question: *"How confident is the system
                            that every decision-blocking uncertainty has been
                            correctly identified?"* Nothing was looked for, so
                            the confidence that everything was found is zero.
                            That is the accurate answer, not a floor picked for
                            safety. It also satisfies `ENGINE_4:612` —
                            *"Clarification Confidence may never exceed upstream
                            confidence"* — by construction and at the minimum,
                            which matters because `clarification.py` records
                            that this schema CANNOT enforce that rule.

  supporting_evidence       `min_length=1`, from `COMM_CLARIFICATION_INTERNAL:
      _references           83-87` — a finding with no evidence reference cannot
                            appear in a Result. The stub made no finding, so
                            there is no finding to support; the schema still
                            demands an entry. The one thing available that is
                            not invented is the input artifact itself, named as
                            what it is. See `THE_ONLY_HONEST_REFERENCE`.

STATUS IS `Created`, NOT `Open`.
    The owner ruled six values (`clarification.py`, module docstring):
    `Created · Open · Answered · Resolved · Superseded · Cancelled`. `Created`
    is *"record created, not yet presented."* `Open` means the Request was
    handed to an external actor (`ENGINE_4:262`) — a claim about a delivery that
    has not happened, and `ENGINE_4:214` puts delivery outside this engine
    entirely: *"Engine 4 never asks users directly."* `Answered` and `Resolved`
    would assert an outcome; `Superseded` and `Cancelled` would assert a
    lifecycle judgement. `Created` is the only value that asserts nothing beyond
    the fact that the record exists.

IT READS IDENTITY, AND NOTHING ELSE, AND THAT IS ENFORCED BY WHAT IT TOUCHES.
    Three fields are copied off the Accounting Decision: its Decision ID, its
    version, and its Transaction ID. `INV-9` (`ENGINE_4:200-202`) says
    identifiers carry zero accounting meaning, so nothing this stub read could
    have influenced what it emitted.

    `accounting_treatment`, `decision_confidence`, `unresolved_doubts` and the
    journal are never touched. A stub that echoed `unresolved_doubts` into
    `missing_information` would look exactly like working detection — the
    failure mode this module exists to refuse — so a test builds two decisions
    that differ in every content field and asserts the emitted Requests are
    equal.

IT INVENTS NO IDENTIFIER EITHER. Both artifact ids are parameters. A stub that
minted them would be non-deterministic, and *"it fabricated nothing"* would stop
being testable: injection is what lets two calls be compared for exact equality
rather than compared with the ids excused.

WHAT THIS MODULE MAY NEVER DO — `ENGINE_4:220-236`, verified by reading, the
prohibitions that bear on a stub rather than all fifteen: `:231` invent facts ·
`:232` silently resolve conflicts · `:233` convert assumptions into facts ·
`:234` convert uncertainty into certainty · `:235` ask users directly · `:229`
approve execution · `:230` reject execution · `:228` modify accounting
decisions. `ENGINE_4:247`: *"It must never guess."* The Accounting Decision is
read-only here and frozen anyway; there is no field on a Clarification Request
in which an answer could be placed, and `extra="forbid"` makes that a refusal.

`AL-INV-5` — engines never call each other. `AL-INV-4` — no engine may read,
write, observe or infer transaction state. Both are checked structurally: a test
parses this module's imports and fails on any import of another engine, of
`accountant_dad.services`, or of the Knowledge Brain.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from accountant_dad.artifacts.clarification import (
    ClarificationPriority,
    ClarificationRequest,
    ClarificationStatus,
)
from accountant_dad.artifacts.decision import AccountingDecision
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope

#: The question, unasked. Named so the emptiness is a stated fact rather than a
#: sentence a reader has to notice is hollow.
NO_QUESTION_WAS_COMPOSED: Final = (
    "NO QUESTION WAS COMPOSED. This Request was emitted by the Engine 4 P3 stub, "
    "which runs no missing_information, no uncertainty_detection, no understanding "
    "and no answer_understanding. What information is required has therefore not "
    "been determined by anything, and this field states that absence rather than "
    "filling it. ENGINE_4:247 — it must never guess."
)

#: Why a Request exists when nothing was detected. The rule, quoted, so the
#: reason cannot be mistaken for a finding.
NECESSITY_WAS_NOT_DETERMINED: Final = (
    "NECESSITY WAS NOT DETERMINED. The stub cannot run stop_decision, so whether "
    "clarification is required at all is unknown. ENGINE_4:499 — 'If necessity "
    "cannot be determined safely, default to Clarification Required. Never "
    "silently ignore uncertainty.' This Request exists because that is the "
    "documented default for an undetermined necessity, NOT because any doubt was "
    "judged to block a decision."
)

#: Which decision depends on it. The dependency is a typed fact elsewhere on the
#: artifact; this field refuses to restate it as prose, because prose carrying an
#: identifier is the exact failure INV-9 names.
AFFECTED_DECISION_WAS_NOT_ANALYSED: Final = (
    "The Accounting Decision recorded in this Request's related_decision_id, at "
    "related_artifact_version. WHICH PART of that decision depends on this Request "
    "was not analysed — the stub performed no impact analysis. The dependency is "
    "recorded structurally, in typed fields, and is asserted nowhere in prose."
)

#: `supporting_evidence_references` is `min_length=1` and the stub has no
#: evidence. Naming the input artifact is the only entry available that points at
#: something real; anything else here would be invented.
THE_ONLY_HONEST_REFERENCE: Final = (
    "The Accounting Decision supplied as this stub's input, recorded in "
    "related_decision_id at related_artifact_version. NO EVIDENCE WAS READ and no "
    "finding was made, so there is no finding for a reference to support. The "
    "schema requires at least one entry (COMM_CLARIFICATION_INTERNAL:83-87); this "
    "names the input rather than inventing a source."
)

SUPPORTING_EVIDENCE_REFERENCES: Final = (THE_ONLY_HONEST_REFERENCE,)

#: `ENGINE_4:190` asks *"what was unclear?"* and `:191` *"why did it matter?"*.
#: Nothing was found to be unclear, because nothing was looked at. `Gaps stay
#: gaps` — an empty tuple is the accurate answer from something that detected
#: nothing, and `clarification.py` records that no document requires either
#: sequence to be non-empty.
NOTHING_WAS_DETECTED: Final[tuple[str, ...]] = ()

#: `ENGINE_4:593`. Zero confidence that every decision-blocking uncertainty was
#: found — because none was sought. Decimal, never float: `confidence.py`.
FOUND_NOTHING: Final = Decimal("0.0000")

#: `ENGINE_4:529` — *"Unknown priority defaults to High until sufficient
#: information exists."* Transcribed, not assessed. See the module docstring.
UNKNOWN_PRIORITY: Final = ClarificationPriority.HIGH


def emit_clarification_request(
    decision: AccountingDecision,
    /,
    *,
    artifact_id: ArtifactId,
    clarification_id: ArtifactId,
) -> ClarificationRequest:
    """Emit a Clarification Request that states, in every field, that it decided nothing.

    Named *emit*, not *clarify*: `ENGINE_4:24` — the engine emits a request
    "without ever resolving it", and `ENGINE_4:255` — owning the status is not
    owning the outcome. A function called `clarify` would name the one thing
    Engine 4 is forbidden to do.

    Pure. No clock, no randomness, no I/O, no cache, no Brain. Two calls with
    equal arguments return equal Requests, and two calls with decisions that
    differ only in content return equal Requests too — which is what makes
    "it performed no detection" an assertion a test can make rather than a claim
    in a comment.

    `artifact_id` and `clarification_id` are separate parameters on purpose.
    `clarification.py` records that no document states whether the Clarification
    ID and the Artifact ID are one value or two, so nothing here binds them; a
    stub that passed one value twice would assert a relationship the documents
    never define.

    The emitted Request is always `FIRST_VERSION` with no parents: it is a new
    artifact, and `identity.py` forbids version 1 from recording a parent. The
    link upstream is carried by `related_decision_id` and
    `related_artifact_version`, which is where `ENGINE_4:196-198` puts it — that
    pair is what makes a stale request detectable when the decision is rebuilt.
    """
    return ClarificationRequest(
        identity=IdentityEnvelope(
            artifact_id=artifact_id,
            version=FIRST_VERSION,
            parent_versions=(),
            # Copied, never minted. INV-3/INV-4 — the Application Layer creates
            # the Transaction ID and engines consume it. One business event
            # keeps one Transaction ID for its entire lifecycle.
            transaction_id=decision.identity.transaction_id,
        ),
        clarification_id=clarification_id,
        related_decision_id=decision.decision_id,
        related_artifact_version=decision.identity.version,
        missing_information=NOTHING_WAS_DETECTED,
        detected_conflicts=NOTHING_WAS_DETECTED,
        required_clarification=NO_QUESTION_WAS_COMPOSED,
        reason_clarification_is_required=NECESSITY_WAS_NOT_DETERMINED,
        affected_decision=AFFECTED_DECISION_WAS_NOT_ANALYSED,
        priority=UNKNOWN_PRIORITY,
        supporting_evidence_references=SUPPORTING_EVIDENCE_REFERENCES,
        clarification_confidence=FOUND_NOTHING,
        status=ClarificationStatus.CREATED,
    )
