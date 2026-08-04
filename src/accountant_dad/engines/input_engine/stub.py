"""The Input Engine stub — it emits the artifact, and it reads nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:100` schedules `Engine stubs 1-6` at P3, the
phase whose whole job is `:72` — *"proves the pipeline."* Two of `:136`'s finish
conditions shape every line below: *"all artifacts valid"* and *"no accuracy
claim permitted at this phase."*

IT EMITS. Every call returns a `DocumentEvidenceObject` that satisfies its own
schema, so the Application Layer can carry a real artifact across the
Engine 1 → Engine 2 seam before any reading exists behind it. Whatever calls
this needs no change when P4 replaces the body.

IT READS NOTHING, AND SAYS SO IN THE ONLY HONEST WAY AVAILABLE.
    Engine 1's job is reading — `ENGINE_1_INPUT_ENGINE_RULES.md:24`, *"convert
    raw human accounting artifacts into reliable, structured evidence."* A stub
    cannot read. So the artifact carries zero readings, and the only thing it
    asserts is that no reading happened.

    The alternative — a plausible vendor, an amount, a confidence score that
    looks like a real extraction — is the single most dangerous thing this file
    could do. `:339`: *"An invented value is indistinguishable downstream from
    an observed one, and the entire trustworthiness of the system rests on that
    distinction holding."* Every number measured downstream of a stub that
    invented would be measuring the invention. `CLAUDE.md` Law 24.

NOT ONE DETECTED FIELD IS EMITTED — NOT EVEN AN UNREADABLE ONE.
    `DetectedField.value` may be `None`, and `:569` makes that mean UNREADABLE,
    a state distinct from `"0"` and from `""`. It is available here and it is
    still wrong, because a field's NAME is itself something read off the
    document. `DetectedField(name="Amount", value=None, ...)` looks maximally
    humble while inventing the claim that a field called `Amount` exists on an
    artifact this module never saw. `:565` — *"Unknown fields remain unknown.
    Never fabricate values."* The honest field count for something that did not
    read is zero.

    The same reasoning empties the rest. No confidence score, because `:109`
    gives only the `confidence` sub-engine authority to produce one and there is
    no sub-engine here. No risky field, because naming one is a judgement about
    a reading. `extracted_text` and `document_structure` stay empty rather than
    carrying a sentence about the document: by
    `COMMUNICATION_RULES_INPUT_ENGINE.md:71`, anything that *"could be wrong
    about the business rather than wrong about the document"* is interpretation,
    and a description of a document nobody read could be wrong about both.

THE ONE CLAIM IT DOES MAKE, AND WHY THE ARTIFACT IS DISHONEST WITHOUT IT.
    An artifact that was empty and silent would be indistinguishable from a real
    Engine 1's honest reading of a blank page. The seam would then hide which of
    the two produced it — and `:136` forbids any accuracy claim at P3 precisely
    because that distinction has to survive to be enforceable.

    So one uncertainty marker is emitted, carrying its reason (`:626` — *"Every
    uncertainty marker carries a reason. A bare score cannot become a good
    question downstream."*). It states this module's own behaviour, which is the
    one thing this module knows for certain, and it is the only claim in the
    artifact.

WHAT IT IS GIVEN IT PASSES THROUGH; WHAT IT IS NOT GIVEN STAYS ABSENT.
    The identity envelope, the Document ID, the source references and an
    optional Human Business Context are all supplied by the caller and emitted
    unchanged. A Human Business Context passes through untouched for the reason
    `:459` and `:508` give — there is nothing to clean and nothing to extract
    from typed text — and it never enters the Structured Document, because
    `:233` says *"Engine 1 never merges the two into a single fact."*

    Supplying one changes nothing else at all: the Confidence Report emitted
    with a note is the same object as the one emitted without. `:289` — *"A
    human note must never increase Evidence Reliability simply because it
    exists"* — and `:330` forbids raising confidence *"because the user wrote
    something."*

    Given no source reference, this module invents no placeholder. The
    artifact's own validator refuses, loudly, and that is the correct outcome
    rather than a rough edge: `:337` — *"When information is unclear, the system
    must report uncertainty. It must never invent information."*

WHAT IT DOES NOT ACCEPT, AND WHY THAT IS NOT AN OVERSIGHT.
    No raw artifact. `DATA_FLOW.md:36` names one — row 0, *external* → Input,
    *"the document as received: scan, photograph, PDF, digital file"* — but no
    schema for it exists. `artifacts/` holds the six that cross ENGINE
    boundaries, and row 0 crosses the system's outer boundary instead. Writing a
    seventh here would be an architecture change made in code, which `CLAUDE.md`
    §O forbids outright. The gap is reported, not filled — and this module could
    not read the thing anyway.

WHERE THIS STUB DEPARTS FROM THE LOCKED SPECIFICATION, STATED NOT HIDDEN.
    `ENGINE_1:95` gives the parent engine *"creation of the Document ID"* and
    `:253` says *"It is assigned by the Input Engine at intake."* This module
    takes it as an argument instead. Minting one needs `uuid4`, and a stub
    holding an entropy source is not a pure function of its arguments — P3's CI
    run would stop being reproducible, which is the one property a walking
    skeleton exists to establish. Nothing else is lost: `:249-251` says the
    Document ID *"carries no accounting meaning and must never influence
    accounting decisions"* (INV-9), so which component mints it changes no
    reasoning anywhere. **The real Engine 1 assigns it at intake, and P4 must
    restore that.**
"""

from __future__ import annotations

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    DocumentEvidenceObject,
    DocumentId,
    HumanBusinessContext,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.identity import IdentityEnvelope

#: The artifact's only claim. Without it an empty artifact is indistinguishable
#: from a real reading of a blank page — see THE ONE CLAIM IT DOES MAKE above.
NOTHING_WAS_READ = UncertaintyMarker(
    subject="the entire reading",
    reason=(
        "the P3 walking-skeleton stub performs no reading, so nothing in this "
        "artifact was observed on any document. Not one detected field is "
        "listed, because a field's name is itself something read off the "
        "document (ENGINE_1_INPUT_ENGINE_RULES.md:239-245); a named field with "
        "an unreadable value would invent the claim that the field exists."
    ),
)

#: Read nothing, so record nothing. Shared by every call, and frozen, so two
#: artifacts cannot disagree about what an absent reading looks like.
NOTHING_WAS_EXTRACTED = StructuredDocument(
    extracted_text="",
    detected_fields=(),
    document_structure="",
    detected_tables=(),
)

#: No score for anything (`ENGINE_1:109` — only the `confidence` sub-engine may
#: produce one, and there is none here), and one marker saying why.
NO_READING_HAPPENED = ConfidenceReport(
    confidence_scores=(),
    uncertainty_markers=(NOTHING_WAS_READ,),
    reliability_information=(
        "No reading was performed. This artifact came from the P3 stub "
        "(MVP_IMPLEMENTATION_BLUEPRINT.md:100) and no accuracy claim may be "
        "made from it (:136)."
    ),
    risky_fields=(),
)


def read(
    *,
    identity: IdentityEnvelope,
    document_id: DocumentId,
    source_references: tuple[str, ...],
    human_business_context: HumanBusinessContext | None = None,
) -> DocumentEvidenceObject:
    """Emit the Document Evidence Object that says nothing was read.

    Every emitted value is one of the caller's, except the two constants above,
    which describe this module rather than any document. No branch reads any
    argument, so the emptiness cannot start varying with the input the way it
    would if this file ever learned one special case.

    Keyword-only, and the four names are the whole seam. There is deliberately
    no parameter for the raw artifact — see WHAT IT DOES NOT ACCEPT above.

    Raises `pydantic.ValidationError` if the caller supplies no source
    reference, a blank one, or the same one twice. The artifact's own validator
    decides that (one owner, INV-10); nothing here re-checks it, defaults it, or
    quietly de-duplicates it.
    """
    return DocumentEvidenceObject(
        identity=identity,
        document_id=document_id,
        source_references=source_references,
        structured_document=NOTHING_WAS_EXTRACTED,
        human_business_context=human_business_context,
        confidence_report=NO_READING_HAPPENED,
    )
