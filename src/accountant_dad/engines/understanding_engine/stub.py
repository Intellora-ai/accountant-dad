"""The Understanding Engine stub — it emits an artifact, and it comprehends nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` — P3 is done when the pipeline runs end to
end with *"all artifacts valid"*, *"Transaction ID intact"* and **"no accuracy
claim permitted at this phase."* Those clauses pull in opposite directions, and
the resolution is the whole design of this module.

IT EMITS A STRUCTURALLY VALID BUSINESS UNDERSTANDING OBJECT.
    Every rule `artifacts/understanding.py` enforces is satisfied, so the
    Application Layer can route a real artifact across the Engine 2 seam before
    any comprehension exists behind it. Code written against this output needs
    no change when P4 replaces the body.

IT COMPREHENDS NOTHING, AND SAYS SO IN THE ONLY HONEST WAY THE SCHEMA ALLOWS.
    Six Results, each carrying exactly one named gap and zero facts.

    `understanding.py` made that legal on purpose — `_a_result_reports_something`
    accepts a Result that only names an unknown, because *"an honest empty Result
    records the gap"*. `ENGINE_2:435` records an unidentifiable party as an
    unknown *"not omitted and not guessed"*; `:476`, `:517`, `:557` and `:598` say
    the same for item detail, payment status, dates and context. Naming the gap
    is the specified behaviour when nothing could be established, not a fallback.

    The alternative — inventing a party, an item, an amount or a date so the
    pipeline looks alive at P3 — is the single most dangerous thing this file
    could do. At the seam it would be indistinguishable from a real Engine 2, and
    every downstream number would be measuring invention. `CLAUDE.md` Law 24:
    never fabricate data. `ENGINE_2:878` — the engine fails when *"a fact is
    invented to complete the story"*, and `:884` states the asymmetry this module
    leans on: *"a story that is incomplete and honestly marked is a success. A
    complete, coherent story built on one quiet assumption is a failure, even
    when the assumption is correct."*

THE ONLY CLAIM IT MAKES IS TRUE BY CONSTRUCTION.
    Each gap below asserts that a component established nothing, and no code path
    here reads a field off the evidence, so the absence is real rather than
    reported. There is no statement about the business anywhere in the output —
    `facts` is empty on all six Results, and `evidence_references` derives off the
    facts, so it is empty too. Nothing here can cite evidence it did not use.

CONFIDENCE AT THE FLOOR, NOT AT A PLAUSIBLE NUMBER.
    Every score in the artifact is `Decimal("0.0000")` — the exact `confidence.MIN`.

    `ENGINE_2:734` carries evidence confidence in from the Confidence Report,
    which invites this stub to copy it. It does not, for two reasons. One batch
    holds many documents and each holds many field scores (`ENGINE_2:157`), so
    "the" evidence confidence would need an aggregation rule that no document
    defines — choosing one is Law 54's undefined term settled silently by the
    engineer. Two, a carried-forward 0.98 would read downstream as *this
    understanding rests on a reliable reading*, which is a claim about an
    understanding that does not exist. `:773` — *"a confident interpretation of an
    unreliable reading is not understanding; it is invention with a score
    attached."* The floor asserts nothing, which is exactly what this component
    has to assert.

    The floor is also not a coincidence that happens to satisfy the validators.
    It is the only value that satisfies all three orderings — understanding ≤
    evidence (`:756`), every Result ≤ evidence, and understanding ≤ the lowest
    Result (`:638` with INV-2) — while the six Results sit where an engine that
    understood nothing must put them. A test proves a raised score is refused.

IT READS NOTHING OUT OF THE EVIDENCE EXCEPT IDENTITY.
    The Transaction ID is copied from the batch, never chosen and never minted:
    `ENGINE_2:157` — this engine receives *all* Document Evidence Objects sharing
    one Transaction ID, and INV-4 gives the Application Layer sole authority to
    create it. INV-9 makes the copy safe to describe as reading nothing: a v4
    UUID encodes no information, so no identifier here can influence an output.

    Nothing else crosses from input to output. A stub that read one field would
    have behaviour to get wrong, and a test asserting *"nothing was understood"*
    would start passing for the wrong reason the moment someone taught it a
    special case. Two entirely different batches sharing one Transaction ID
    therefore produce **equal** artifacts, and a test asserts exactly that.

IT REFUSES RATHER THAN INVENTS.
    Two batches cannot produce an artifact, and neither is defaulted around
    (Law 11). An empty batch carries no Transaction ID, so the artifact could
    only exist by inventing identity. A batch spanning several Transaction IDs
    would force this engine to pick one — `ENGINE_2:673`, *"Never silently choose
    one answer."* Both raise `EvidenceBatchRejectedError`.

WHAT IT DELIBERATELY DOES NOT DO.
    No Brain. `BLUEPRINT:99` names the Brain stub as required by engine stubs 2
    through 6, while `:100`'s own row for the engine stubs names only the
    Application Layer and the artifact schemas. The two rows disagree, and
    nothing is resolved here: this stub has no question to ask, and a question
    invented so the seam gets exercised is the fabrication this module exists to
    avoid. Recorded, not decided.

    No engine import (AL-INV-5) and no `accountant_dad.services` import
    (AL-INV-4) — an engine that could observe workflow state could branch on it.
    No clock, no randomness, no file I/O, no dependency beyond the artifact
    schemas. `understand` is a pure function of its two arguments; a test parses
    this file's own import list and fails on anything outside `decimal`.
"""

from __future__ import annotations

from decimal import Decimal

from accountant_dad.artifacts.evidence import DocumentEvidenceObject
from accountant_dad.artifacts.understanding import (
    BusinessContextResult,
    BusinessUnderstandingObject,
    ConfidenceAssessment,
    ItemUnderstandingResult,
    PartyUnderstandingResult,
    PaymentUnderstandingResult,
    SupportingUnderstandingData,
    TimelineUnderstandingResult,
    TransactionStory,
    TransactionUnderstandingResult,
    Unknown,
)
from accountant_dad.confidence import Confidence
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope, TransactionId

#: `confidence.MIN`, written as the literal it must equal. Every score this
#: module emits is this one value — see CONFIDENCE AT THE FLOOR above.
CONFIDENCE_FLOOR: Confidence = Decimal("0.0000")

#: Story Builder's narrative when there is nothing to narrate. Authored text, so
#: `understanding.py` vocabulary-checks it (`ENGINE_2:641`); it is phrased in
#: business terms and says only what this component did, never what happened.
NARRATIVE = (
    "No business story was assembled. This artifact was produced by a component "
    "that performs no comprehension, so nothing about the event, the parties, the "
    "goods or services, the movement of money, the dates or the operating context "
    "has been established from the evidence. Every gap named here is unfilled "
    "rather than looked for and not found, and no statement about this business "
    "appears anywhere in this artifact."
)


class EvidenceBatchRejectedError(Exception):
    """The batch handed to this engine is not the batch `ENGINE_2:157` defines.

    Raised rather than absorbed. Both cases below would require this engine to
    invent identity or to choose between Transaction IDs, and an engine that did
    either quietly would hand a plausible artifact to Engine 3 (Law 11).
    """


def _gap(subject: str, why_it_matters: str) -> tuple[Unknown]:
    """One named gap, in the single-entry shape every Result's unknown field takes.

    `Unknown` requires `why_it_matters` because `ENGINE_2:794` lets this engine
    *"explain why understanding is incomplete"*, and a gap with no stated
    consequence cannot become a good question in the Clarification Engine.
    """
    return (Unknown(subject=subject, why_it_matters=why_it_matters),)


def _understood_nothing() -> SupportingUnderstandingData:
    """The six Results of `ENGINE_2:342-347`, each naming what it did not establish.

    `:350` — *"Every Result carries confidence, unknowns and evidence references.
    No Result may omit them."* Confidence and unknowns are what these six carry;
    evidence references derive off facts, and there are none.

    Zero facts, zero conflicts, confidence at the floor. Each Result puts its gap
    in its own specified component — `unknown information`, `unknown parties`,
    `unknown item details`, `unknown payment details`, `missing dates`, `unknown
    context` — because that is where `ENGINE_2:394`, `:435`, `:476`, `:517`,
    `:557` and `:598` each say an unestablished thing belongs.
    """
    return SupportingUnderstandingData(
        transaction=TransactionUnderstandingResult(
            confidence=CONFIDENCE_FLOOR,
            unknown_information=_gap(
                "what kind of business event occurred",
                "nothing downstream can tell a purchase from a sale, a return or a receipt",
            ),
        ),
        party=PartyUnderstandingResult(
            confidence=CONFIDENCE_FLOOR,
            unknown_parties=_gap(
                "who took part and what role each played",
                "neither side of the event is named, so nothing can say who dealt with whom",
            ),
        ),
        item=ItemUnderstandingResult(
            confidence=CONFIDENCE_FLOOR,
            unknown_item_details=_gap(
                "what goods or services moved",
                "nothing states what was supplied, so the exchange cannot be described",
            ),
        ),
        payment=PaymentUnderstandingResult(
            confidence=CONFIDENCE_FLOOR,
            unknown_payment_details=_gap(
                "whether money moved, and by what means",
                # ENGINE_2:517 — unstated is recorded as unstated, "never assumed
                # to be credit, and never assumed to be paid".
                "the status is unstated; it is neither settled nor outstanding until "
                "a document says so",
            ),
        ),
        timeline=TimelineUnderstandingResult(
            confidence=CONFIDENCE_FLOOR,
            missing_dates=_gap(
                "when each part of the event happened",
                "no date is established, so nothing can be placed in time or ordered",
            ),
        ),
        business_context=BusinessContextResult(
            confidence=CONFIDENCE_FLOOR,
            unknown_context=_gap(
                "how this event sits in this business's own operating reality",
                "nothing indicates whether this is usual for this business or unlike it",
            ),
        ),
    )


def _the_one_transaction(evidence: tuple[DocumentEvidenceObject, ...]) -> TransactionId:
    """The Transaction ID every Document Evidence Object in the batch shares.

    Copied, never chosen. `ENGINE_2:157` — *"The Understanding Engine receives all
    Document Evidence Objects sharing one Transaction ID"* — so a batch carrying
    two of them is a routing fault in the caller, not an ambiguity for this engine
    to settle.
    """
    if not evidence:
        raise EvidenceBatchRejectedError(
            "no Document Evidence Object was supplied. There is no Transaction ID to "
            "carry and nothing to understand, so an artifact could only be produced "
            "by inventing the identity it belongs to (ENGINE_2:157, INV-4)."
        )

    transaction_ids = {document.identity.transaction_id for document in evidence}
    if len(transaction_ids) > 1:
        raise EvidenceBatchRejectedError(
            f"{len(transaction_ids)} Transaction IDs in one batch. The Understanding "
            "Engine receives the Document Evidence Objects sharing ONE Transaction ID "
            "(ENGINE_2:157); picking one of several would be this engine silently "
            "choosing an answer (ENGINE_2:673)."
        )
    return transaction_ids.pop()


class StubUnderstandingEngine:
    """Engine 2's P3 seam. Produces the artifact; comprehends nothing.

    A class rather than a bare function so the Application Layer holds one object
    per engine and the call site survives P4, where the real engine needs state
    this one has none of. It holds no state today — two instances are
    interchangeable, and `understand` reads nothing but its arguments.
    """

    def understand(
        self,
        evidence: tuple[DocumentEvidenceObject, ...],
        artifact_id: ArtifactId,
        /,
    ) -> BusinessUnderstandingObject:
        """Emit the Business Understanding Object that reports understanding nothing.

        `artifact_id` is supplied rather than minted here. `ArtifactId.new()` is
        the one non-deterministic call this module could make, and it would cost
        the property the tests rest on — *same arguments, equal artifact*. INV-9
        makes the choice free of consequence: a v4 UUID encodes nothing, so no
        reasoning can depend on where it came from.

        Always version 1 with no parent: `identity.py` refuses parents on the
        origin version, and a correction (version ≥ 2) would require knowing which
        artifact it corrects — an input this stub is not given and may not guess.
        """
        transaction_id = _the_one_transaction(evidence)
        supporting = _understood_nothing()
        return BusinessUnderstandingObject(
            identity=IdentityEnvelope(
                artifact_id=artifact_id,
                version=FIRST_VERSION,
                parent_versions=(),
                transaction_id=transaction_id,
            ),
            transaction_story=TransactionStory(narrative=NARRATIVE),
            supporting_understanding_data=supporting,
            # Derived from the Results, never listed by hand. `ENGINE_2:645` —
            # "Unknowns are carried into Identified Unknowns intact"; taking the
            # union off the Results is how dropping one stops being expressible.
            identified_unknowns=supporting.all_unknowns,
            confidence_assessment=ConfidenceAssessment(
                evidence_confidence=CONFIDENCE_FLOOR,
                understanding_confidence=CONFIDENCE_FLOOR,
            ),
        )
