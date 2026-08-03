"""The Clarification Request — the Clarification Engine's only output artifact.

`question_generator` **creates** it; the **Clarification Engine owns** it, along
with Clarification Status and Clarification History (`ENGINE_4:206-208`).

It states what prevents a decision from being safely completed, and never
resolves it. Three of this engine's absolute boundaries are structural here
rather than remembered:

  ENGINE_4:231, :247  It never invents a fact and never guesses. There is no
                      field in which an answer could be placed, and
                      `extra="forbid"` is what makes that a refusal rather
                      than a naming convention.

  DATA_FLOW.md:42     A Clarification Answer re-enters through the normal
                      pipeline and never returns to Engine 4; the responsible
                      upstream engine emits a new artifact version. So this
                      artifact carries the question, never the reply.

  ENGINE_4:214        Engine 4 never asks anyone directly. The Request goes to
                      Validation, and separately to an external actor via a
                      later system layer. Nothing here addresses a recipient,
                      because choosing one would be that later layer's job.

────────────────────────────────────────────────────────────────────────────
THE STATUS SET — an owner's ruling that OVERRIDES three locked documents.

The documents disagree with each other. Three carry a five-value set with no
`Created`:

    DATA_FLOW.md:138-139
    ENGINE_4_CLARIFICATION_ENGINE_RULES.md:261-266
    COMMUNICATION_RULES_CLARIFICATION_ENGINE.md:64

A fourth, `COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md:148-154`, carries six —
it has `Created`.

**The owner ruled: six values, spelled `Created · Open · Answered · Resolved ·
Superseded · Cancelled`.** That ruling is authoritative and is what is
implemented below. This is the owner's decision, NOT an inference drawn from
the fourth document agreeing with it. The three five-value documents are
therefore wrong and need revising under CLAUDE.md §M — reported, never fixed
from here.

DEFECT REPORTED, NOT FIXED. `COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`
lines 152 and 154 are byte-identical duplicate table rows — `Cancelled` is
listed twice with the same trigger text. Verified byte-for-byte. It is a
documentation defect and belongs to whoever owns that document.
────────────────────────────────────────────────────────────────────────────

WHAT IS DELIBERATELY ABSENT, because the documents are silent (Law 54):

  - No relationship is asserted between `clarification_id` and
    `identity.artifact_id`. `DATA_FLOW.md:32` says the identity envelope is
    universal and not repeated in the per-artifact tables, yet row 4 lists
    Clarification ID anyway. Whether they are one value or two is nowhere
    stated, so no predicate binds them.
  - No field carries upstream confidence, so *"Clarification Confidence may
    never exceed upstream confidence"* (`ENGINE_4:612`) CANNOT be enforced
    here. It is a review-only prohibition at this boundary; a reader who
    assumes this schema enforces it would be quietly wrong.
  - Nothing requires `missing_information` or `detected_conflicts` to be
    non-empty. A request driven purely by uncertainty severity carries
    neither, and no document says otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from accountant_dad.confidence import Confidence
from accountant_dad.identity import ArtifactId, IdentityEnvelope, VersionField


class ClarificationStatus(StrEnum):
    """The six states, per the owner's ruling. See the module docstring."""

    #: Record created, not yet presented. `question_generator` has assembled
    #: the Request after `stop_decision` returned *clarification required*.
    CREATED = "Created"
    #: Awaiting a response. The Request has been handed to the external actor.
    OPEN = "Open"
    #: A response was provided — recorded, never interpreted.
    ANSWERED = "Answered"
    #: No further action required; the uncertainty is gone.
    RESOLVED = "Resolved"
    #: Replaced by a newer clarification.
    SUPERSEDED = "Superseded"
    #: Closed without resolution.
    CANCELLED = "Cancelled"


class ClarificationPriority(StrEnum):
    """`ENGINE_4:182` and `ENGINE_4:520`. Four levels, enumerated by the spec."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


#: `ENGINE_4:277` — "Resolved, Superseded and Cancelled are terminal."
TERMINAL_STATUSES: Final = frozenset(
    {
        ClarificationStatus.RESOLVED,
        ClarificationStatus.SUPERSEDED,
        ClarificationStatus.CANCELLED,
    }
)

#: The §7 state machine, transcribed. Not derived, not reasoned about — every
#: row is read off `ENGINE_4:268-281` and `COMM_CLARIFICATION_INTERNAL:146-156`:
#:
#:   Created -> Open           the Request is handed to the external actor
#:   Open -> Answered          an answer arrives
#:   Answered -> Resolved      a new artifact version no longer carries it
#:   * -> Superseded           "may be entered from any state"
#:   * -> Cancelled            "may be entered from any state"
#:
#: `Open -> Resolved` is absent on purpose: ENGINE_4:279 forbids it, because
#: resolution requires a new artifact version, and ENGINE_4:281 says collapsing
#: Superseded into Resolved "would hide the fact that a question went
#: unanswered." No state transitions to itself; the permitted-transition list
#: is exhaustive and contains no self-loop.
#:
#: A MappingProxyType, not a dict: a module-level dict is editable by any
#: importer, and this table is a transcription of a locked document rather
#: than a runtime setting.
PERMITTED_TRANSITIONS: Final[Mapping[ClarificationStatus, frozenset[ClarificationStatus]]] = (
    MappingProxyType(
        {
            ClarificationStatus.CREATED: frozenset(
                {
                    ClarificationStatus.OPEN,
                    ClarificationStatus.SUPERSEDED,
                    ClarificationStatus.CANCELLED,
                }
            ),
            ClarificationStatus.OPEN: frozenset(
                {
                    ClarificationStatus.ANSWERED,
                    ClarificationStatus.SUPERSEDED,
                    ClarificationStatus.CANCELLED,
                }
            ),
            ClarificationStatus.ANSWERED: frozenset(
                {
                    ClarificationStatus.RESOLVED,
                    ClarificationStatus.SUPERSEDED,
                    ClarificationStatus.CANCELLED,
                }
            ),
            ClarificationStatus.RESOLVED: frozenset(),
            ClarificationStatus.SUPERSEDED: frozenset(),
            ClarificationStatus.CANCELLED: frozenset(),
        }
    )
)


def may_transition(current: ClarificationStatus, proposed: ClarificationStatus) -> bool:
    """Is `current -> proposed` one of the transitions §7 permits?

    A status change is a NEW VERSION of the artifact, never an edit to this one
    — the model is frozen. This predicate answers whether the new version's
    status is a legal successor; it does not perform anything.

    Indexes the table directly rather than defaulting a missing key to "not
    permitted". A default would turn a gap in the table into a silent refusal;
    a `KeyError` says the table is incomplete, out loud.
    """
    return proposed in PERMITTED_TRANSITIONS[current]


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError(
            "a blank entry names nothing. It satisfies 'this component is "
            "present' while pointing at no fact, no conflict and no evidence — "
            "which is how a request that determined nothing comes to look "
            "complete. ENGINE_4:557: an incomplete request that NAMES what it "
            "could not determine is correct output; a complete-looking one is "
            "not."
        )
    return value


#: Text that has to actually say something. Stored verbatim and never stripped:
#: an artifact records what its producer asserted, and silently rewriting that
#: falsifies the record — the same reason `confidence.py` refuses to round.
Statement = Annotated[str, AfterValidator(_not_blank)]

#: `COMM_CLARIFICATION_INTERNAL:83-87` — every Result carries confidence AND
#: evidence references; "a finding with no evidence reference cannot appear in
#: a Result. There is no mechanism for producing one, and that is deliberate."
#: `question_generator` publishes the Clarification Request as its Result
#: (`COMM_CLARIFICATION_INTERNAL:78`), so the rule binds this artifact and
#: `min_length=1` is that missing mechanism, missing by construction.
EvidenceReferences = Annotated[tuple[Statement, ...], Field(min_length=1)]


class ClarificationRequest(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """The twelve components of `ENGINE_4:172-186`, plus the identity envelope.

    Frozen, because a version once created is immutable (INV-5). Correction is
    a new version, never an edit — including a status transition, which is why
    `status` is an ordinary frozen field and not something with a setter.

    `extra="forbid"`, because the dangerous additions here are all plausible:
    an answer, a resolution, a chosen ledger. Each is refused by name at
    construction rather than caught in review.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Artifact ID · Version · Parent Artifact Version(s) · Transaction ID.
    #: Universal to every artifact — `DATA_FLOW.md:32`.
    identity: IdentityEnvelope

    #: Identity only — INV-9. Zero accounting meaning; it must never influence
    #: any decision, in this engine or any other (`ENGINE_4:200-202`).
    clarification_id: ArtifactId

    #: The Accounting Decision this was raised against. Typed as an ArtifactId
    #: because that is this repository's one type for "identity of an
    #: artifact"; no document defines a separate Decision ID type, and
    #: inventing one here would duplicate a type the Accounting Decision owns.
    related_decision_id: ArtifactId

    #: The exact decision version this was raised against. Recording it is what
    #: makes a stale request detectable: a request raised against `v3` is
    #: Superseded the moment `v4` exists (`ENGINE_4:196-198`,
    #: `DATA_FLOW.md:142`). Staleness is structural, not noticed.
    related_artifact_version: VersionField

    #: What was unclear.
    missing_information: tuple[Statement, ...]

    #: Preserved, never resolved. A Request carrying an unresolved conflict is
    #: correct output, not a failure (`ENGINE_4:639`).
    detected_conflicts: tuple[Statement, ...]

    #: What information is required. The question — never the answer.
    required_clarification: Statement

    #: Why it matters.
    reason_clarification_is_required: Statement

    #: Which decision depends on it.
    affected_decision: Statement

    #: How important it is.
    priority: ClarificationPriority

    #: Where each finding points back to. Never empty — see EvidenceReferences.
    supporting_evidence_references: EvidenceReferences

    #: THE Confidence type, imported. "No schema may define its own confidence
    #: type or scale." It answers one question and only one: has every
    #: decision-blocking uncertainty been found (`ENGINE_4:593`)? It says
    #: nothing about whether the accounting is right.
    clarification_confidence: Confidence

    #: What Validation reads first (`COMM_CLARIFICATION_ENGINE:69-76`).
    status: ClarificationStatus
