"""The Document Evidence Object — the Input Engine's one output artifact.

`DATA_FLOW.md` §2 row 1 names it and §2.1 fixes its name: *"The Input Engine's
output has one name. `Structured Document` and `Confidence Report` are its two
components, never the name of the artifact itself."*

WHAT ENGINE 1 IS FOR, AND WHAT IT IS FORBIDDEN. It reads. It does not
interpret. Everything below exists to make the second half structural rather
than remembered, because an artifact that quietly interprets is not a bug that
crashes — it is a posted entry nobody can defend.

Three rules do most of the work:

  EVERY FACT CARRIES ITS ORIGIN, PERMANENTLY (INV-11).
      `ENGINE_1_INPUT_ENGINE_RULES.md:245` — *"A value carried without all
      three is not evidence and must not be emitted."* So `Provenance` has no
      optional field. An empty source id or evidence reference is refused, not
      defaulted: a value claiming traceability it does not have is worse than
      one that admits it has none.

  EXTRACTED AND HUMAN NEVER MERGE.
      `ENGINE_1_INPUT_ENGINE_RULES.md:233` — *"Engine 1 never merges the two
      into a single fact."* A human assertion filed as a detected field IS
      that merge: it enters the Structured Document, which is labelled
      EXTRACTED, wearing the authority of something read off the artifact.
      The Human Business Context is therefore a sibling field, and there is
      deliberately nowhere to put a note among the detected fields.

  ABSENT, ZERO AND UNREADABLE ARE THREE STATES.
      `ENGINE_1_INPUT_ENGINE_RULES.md:569`. `None` is unreadable; `"0"` is a
      read value; `""` is refused, because it collapses the first into the
      second and the collapse is invisible downstream.

CONFIDENCE HAS A SINGLE AUTHORITY (INV-2, `ENGINE_1:109`). Only the
`confidence` sub-engine turns signals into scores, and no component — parent
included — may raise or lower one. The type comes from `confidence.py` and is
never redeclared here: `Decimal`, 0.0000-1.0000, float refused.

  A MEASUREMENT AND THE ABSENCE OF ONE ARE TWO FACTS (Amendment 5).
      `Provenance.confidence` and `FieldConfidence.confidence` are
      `ConfidenceOrUnmeasured`: a `Confidence`, or the single `UNMEASURED`
      sentinel. Nothing else in this file changed, and `Confidence` itself
      did not change — it still admits only a `Decimal` on the agreed scale.

      A PDF text layer is transcribed rather than recognised, so
      `reader.read_pdf_text_layer` scores nothing (`reader.py:255-259`), and
      a PDF text layer is the MVP's primary input. Under the old schema those
      readings could not be emitted at all, and the artifact carried ZERO
      `Provenance` objects on the one input the MVP exists to read. No honest
      number was available to fill the slot — `1.0000` is the default
      `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids by name, `0.0000` asserts a
      worthlessness nobody measured — so the absence is named instead of
      filled in (Law 54).

      THIS DOES NOT WEAKEN INV-11. Six attributes, none optional, `extra`
      still forbidden. The sentinel makes the VALUE absent, never the
      ATTRIBUTE — the artifact still states, for every fact, what is known
      about its reliability. "Not measured" is one of the things that can be
      known, and saying so is not the same as saying nothing.

A GAP REPORTED RATHER THAN FILLED (Law 54). `SYSTEM_INVARIANTS.md:252`
describes `Corroborated` as *"whether another source supports it"* — which
reads as a boolean. `ENGINE_1_INPUT_ENGINE_RULES.md:295` and
`DATA_FLOW.md:573` instead have Engine 1 record the literal `not assessed`,
*"honestly, because it cannot assess it."* No document anywhere enumerates a
verdict set. So exactly one member is modelled — the only one Engine 1 is
permitted to write — and `True` is refused. Inventing a three-member enum here
would put a decision in code that the specification never made.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from accountant_dad.confidence import ConfidenceOrUnmeasured, records_the_same_measurement
from accountant_dad.identity import IdentityEnvelope


def _meaningful_text(value: str) -> str:
    """Non-empty AFTER stripping. A padded blank is a blank.

    This was `Field(min_length=1)`, which refuses `""` and accepts `"   "`. The
    other five artifact schemas reject blank-after-strip, so one concept had two
    behaviours (Law 14, INV-10) and the looser one lived in the artifact that
    carries the system's only evidence.

    Found by the conformance registry, empirically, not by reading:

        UncertaintyMarker(subject="Amount", reason="   ")   was ACCEPTED
        UnresolvedDoubt(missing_fact="   ", ...)            already refused

    `ENGINE_1:626` — *"Every uncertainty marker carries a reason. A bare score
    cannot become a good question downstream."* A marker whose reason is three
    spaces carries no reason, and `ENGINE_1:245` — a value without a real source
    id and evidence reference *"is not evidence and must not be emitted."*
    """
    if not value.strip():
        raise ValueError("must not be empty or blank")
    return value


#: Non-empty after stripping. Used wherever a blank string would be a claim
#: rather than a value — a source id, an evidence reference, a field name.
NonEmptyText = Annotated[str, Field(min_length=1), AfterValidator(_meaningful_text)]

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class SourceType(StrEnum):
    """The three origins, exactly as `SYSTEM_INVARIANTS.md:247` writes them.

    The spellings are the contract. A fourth member, or `Metadata` in place of
    `Structured Metadata`, is a silent architecture change (INV-1).
    """

    DOCUMENT = "Document"
    HUMAN = "Human"
    STRUCTURED_METADATA = "Structured Metadata"


class Corroborated(StrEnum):
    """The only verdict Engine 1 is permitted to write. See the module docstring."""

    NOT_ASSESSED = "not assessed"


class Provenance(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Where a fact came from. Six attributes, none optional (INV-11)."""

    model_config = _FROZEN

    source_type: SourceType
    source_id: NonEmptyText
    evidence_reference: NonEmptyText
    #: Timezone-aware only. A naive timestamp in an audit trail is a defect:
    #: it cannot be ordered against anything recorded elsewhere.
    timestamp: datetime
    #: A measured score, or `UNMEASURED` — the stated absence of one
    #: (Amendment 5). Still MANDATORY: the attribute is never optional, and
    #: `None` is refused here exactly as it always was. See the module
    #: docstring for why no number would have been honest.
    confidence: ConfidenceOrUnmeasured
    corroborated: Corroborated

    @field_validator("timestamp")
    @classmethod
    def _must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError(
                "timestamp must be timezone-aware; a naive datetime cannot be "
                "ordered against anything recorded elsewhere in the audit trail"
            )
        return value


class DetectedField(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One field read off the document, with where it was read from."""

    model_config = _FROZEN

    name: NonEmptyText
    #: `None` means unreadable. `"0"` means a zero was read. `""` is refused —
    #: see ABSENT, ZERO AND UNREADABLE in the module docstring.
    value: NonEmptyText | None
    provenance: Provenance


class DetectedTable(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One table read off the document, rows verbatim, with its origin."""

    model_config = _FROZEN

    rows: tuple[tuple[str, ...], ...]
    provenance: Provenance


def _reject_human_origin(provenance: Provenance, what: str) -> None:
    """The EXTRACTED/HUMAN boundary, enforced rather than documented.

    Forbids `Human` specifically, not "anything that is not Document" —
    `DATA_FLOW.md:544` lists upload metadata and file attributes as real
    sources, and the artifact tree gives `Structured Metadata` no other home.
    """
    if provenance.source_type is SourceType.HUMAN:
        raise ValueError(
            f"{what} claims a Human origin. Engine 1 never merges an extracted "
            "reading with a human assertion (ENGINE_1_INPUT_ENGINE_RULES.md:233); "
            "a human note belongs in human_business_context, beside this "
            "component and never inside it."
        )


class StructuredDocument(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What was read off the artifact. A component, never the artifact's name."""

    model_config = _FROZEN

    extracted_text: str
    detected_fields: tuple[DetectedField, ...]
    document_structure: str
    detected_tables: tuple[DetectedTable, ...]

    @model_validator(mode="after")
    def _only_extracted_evidence_lives_here(self) -> StructuredDocument:
        for field in self.detected_fields:
            _reject_human_origin(field.provenance, f"detected field {field.name!r}")
        for index, table in enumerate(self.detected_tables):
            _reject_human_origin(table.provenance, f"detected table {index}")

        names = [field.name for field in self.detected_fields]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            # The Confidence Report keys scores by field name
            # (ENGINE_1:599-601), so two fields called `Amount` make "which
            # score belongs to which value?" unanswerable.
            raise ValueError(
                f"two detected fields share one name: {', '.join(duplicated)}. "
                "The Confidence Report keys scores by name, so a repeated name "
                "makes traceability unanswerable."
            )
        return self


class FieldConfidence(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What is known about one named thing's reliability. The name need not be
    a detected field.

    Since Amendment 5 that is *either* a score *or* `UNMEASURED`, and the
    widening is what lets a value nobody scored still be REPORTED rather than
    omitted. Omitting it would have been concealed uncertainty about precisely
    the fields whose reliability is least established.
    """

    model_config = _FROZEN

    field_name: NonEmptyText
    confidence: ConfidenceOrUnmeasured


class UncertaintyMarker(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """A named doubt and why it exists.

    `ENGINE_1_INPUT_ENGINE_RULES.md:626` — *"Every uncertainty marker carries a
    reason. A bare score cannot become a good question downstream."* A marker
    with an empty reason is a bare score wearing a label.
    """

    model_config = _FROZEN

    subject: NonEmptyText
    reason: NonEmptyText


class ConfidenceReport(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """How reliable the reading was. A component, never the artifact's name."""

    model_config = _FROZEN

    confidence_scores: tuple[FieldConfidence, ...]
    uncertainty_markers: tuple[UncertaintyMarker, ...]
    reliability_information: str
    risky_fields: tuple[str, ...]

    @model_validator(mode="after")
    def _each_name_is_scored_once(self) -> ConfidenceReport:
        scored = [score.field_name for score in self.confidence_scores]
        duplicated = sorted({name for name in scored if scored.count(name) > 1})
        if duplicated:
            # INV-10, one concept one owner. Two scores for one field means no
            # score is authoritative and a reader silently picks the first.
            raise ValueError(
                f"two confidence scores for one field: {', '.join(duplicated)}. "
                "Neither would be authoritative, so a reader would silently pick one."
            )

        risky = list(self.risky_fields)
        repeated = sorted({name for name in risky if risky.count(name) > 1})
        if repeated:
            raise ValueError(f"a risky field is listed twice: {', '.join(repeated)}")
        return self


class HumanBusinessContext(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What the user said, verbatim, filed as a human claim and never as a reading.

    `ENGINE_1_INPUT_ENGINE_RULES.md:138` — the description is OPTIONAL and the
    system must work correctly when none is provided. Nothing downstream may
    require one, and its absence is not a gap to be clarified.
    """

    model_config = _FROZEN

    #: Verbatim. Not trimmed, not normalised, not corrected — a human note is
    #: evidence of what was said, and editing it destroys what it evidences.
    original_user_text: NonEmptyText
    provenance: Provenance

    @model_validator(mode="after")
    def _must_declare_a_human_origin(self) -> HumanBusinessContext:
        if self.provenance.source_type is not SourceType.HUMAN:
            raise ValueError(
                "human business context must carry source_type Human. A human "
                "claim filed under any other origin is indistinguishable "
                "downstream from something read off the document (INV-11)."
            )
        return self


@dataclass(frozen=True, slots=True)
class DocumentId:
    """Identifies one source document. Not an Artifact ID, and not a bare UUID.

    A distinct type for the same reason `identity.py` separates `TransactionId`
    from `ArtifactId` (INV-3): passing one where the other belongs is refused
    by the type system, not noticed at a code review that might not happen.

    UUIDv4 for the reason `identity.py` gives — a ULID encodes creation time
    and a sequence encodes order, and both are information an engine could
    read out of an identifier (INV-9).
    """

    value: uuid.UUID

    @classmethod
    def new(cls) -> DocumentId:
        return cls(uuid.uuid4())


class DocumentEvidenceObject(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Engine 1 → Engine 2. `DATA_FLOW.md` §2 row 1."""

    model_config = _FROZEN

    identity: IdentityEnvelope
    document_id: DocumentId
    source_references: tuple[NonEmptyText, ...]
    structured_document: StructuredDocument
    #: Optional, and the system must work when it is absent (ENGINE_1:138).
    human_business_context: HumanBusinessContext | None = None
    confidence_report: ConfidenceReport

    @model_validator(mode="after")
    def _every_reading_is_scored_and_the_scores_agree(self) -> DocumentEvidenceObject:
        if not self.source_references:
            raise ValueError(
                "an evidence object must name at least one source reference; "
                "evidence with no stated source is not evidence (INV-11)"
            )
        references = list(self.source_references)
        repeated = sorted({ref for ref in references if references.count(ref) > 1})
        if repeated:
            raise ValueError(f"a source reference is listed twice: {', '.join(repeated)}")

        scores = {
            score.field_name: score.confidence for score in self.confidence_report.confidence_scores
        }
        for field in self.structured_document.detected_fields:
            if field.name not in scores:
                # ENGINE_1:239-245. A value with no ENTRY is a value whose
                # reliability the artifact does not state. Note that an entry
                # reading UNMEASURED satisfies this and an absent entry does
                # not: "nobody measured this" is a statement about reliability,
                # and silence is not (Amendment 5).
                raise ValueError(
                    f"detected field {field.name!r} carries no confidence score. "
                    "A value whose reliability the artifact does not state must not be emitted."
                )
            # `records_the_same_measurement` decides what agreement MEANS, in
            # one place (confidence.py). It is not loosened for an unmeasured
            # field, it is stricter: measured-against-unmeasured is a NEW
            # refusal, because one side asserts a number the other says was
            # never taken. Numbers are still compared as numbers, so 0.98 and
            # 0.9800 remain one value.
            if not records_the_same_measurement(scores[field.name], field.provenance.confidence):
                raise ValueError(
                    f"the Confidence Report and the provenance of {field.name!r} disagree: "
                    f"{scores[field.name]} against {field.provenance.confidence}. "
                    "Refused rather than reconciled silently — only the confidence "
                    "sub-engine may set a score (INV-2). A measured score on one side "
                    "and UNMEASURED on the other is a disagreement, not a special case: "
                    "one of them asserts a reading nobody took."
                )
        return self
