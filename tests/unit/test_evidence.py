"""The Document Evidence Object — Engine 1's only output artifact.

Written before the implementation. Every test below names the document line it
enforces, because the artifact is not a design choice: it is a locked
specification, and a schema that quietly drifts from it is the defect
`SYSTEM_INVARIANTS.md` INV-1 exists to prevent.

The dangerous direction here is the permissive one. This artifact is what the
rest of the pipeline reasons from, so a fact that lost its origin, a value that
lost its location, or a human claim that became indistinguishable from a
document reading is not a bug that shows up as a crash — it shows up as a
posted entry nobody can defend.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DetectedTable,
    DocumentEvidenceObject,
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

#: UUID version 4 is random. Named so the assertion below reads as the claim it
#: makes — INV-9, an identifier that encodes nothing — rather than as a number.
RANDOM_UUID_VERSION = 4

WHEN = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

HIGH = Decimal("0.9800")
LOW = Decimal("0.4200")


# ── builders ─────────────────────────────────────────────────────────────────
# Deliberately explicit. Nothing under test is defaulted away: every builder
# takes the value the test cares about as an argument.


def a_provenance(
    *,
    source_type: SourceType = SourceType.DOCUMENT,
    confidence: Decimal = HIGH,
    evidence_reference: str = "page 1, box at (240, 118)",
) -> Provenance:
    return Provenance(
        source_type=source_type,
        source_id="invoice-481.pdf",
        evidence_reference=evidence_reference,
        timestamp=WHEN,
        confidence=confidence,
        corroborated=Corroborated.NOT_ASSESSED,
    )


def a_detected_field(
    *,
    name: str = "Amount",
    value: str | None = "19800.00",
    confidence: Decimal = HIGH,
    source_type: SourceType = SourceType.DOCUMENT,
) -> DetectedField:
    return DetectedField(
        name=name,
        value=value,
        provenance=a_provenance(source_type=source_type, confidence=confidence),
    )


def a_structured_document(
    *,
    detected_fields: tuple[DetectedField, ...] = (),
    detected_tables: tuple[DetectedTable, ...] = (),
) -> StructuredDocument:
    return StructuredDocument(
        extracted_text="ACME TRADERS\nInvoice 481\nAmount 19800.00",
        detected_fields=detected_fields,
        document_structure="header / body / totals",
        detected_tables=detected_tables,
    )


def a_confidence_report(
    *,
    confidence_scores: tuple[FieldConfidence, ...] = (),
    uncertainty_markers: tuple[UncertaintyMarker, ...] = (),
    risky_fields: tuple[str, ...] = (),
) -> ConfidenceReport:
    return ConfidenceReport(
        confidence_scores=confidence_scores,
        uncertainty_markers=uncertainty_markers,
        reliability_information="scan legible; totals block unclear",
        risky_fields=risky_fields,
    )


#: The exact words `_meaningful_text` refuses a blank with. Asserting only that
#: `ValidationError` was raised passes while the schema refuses for a completely
#: different reason — and a value refused for the wrong reason is a defect that
#: reports itself wrongly to whoever debugs it next.
BLANK_REASON = "must not be empty or blank"


def messages(raised: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    """Every message pydantic reported, EXACTLY as the validator worded it.

    Equality, not substring: a message padded or re-cased either side still
    CONTAINS the fragment, so a substring check is not a check on the wording.
    """
    return [str(error["msg"]) for error in raised.value.errors()]


def assert_refused_as_blank(raised: pytest.ExceptionInfo[ValidationError]) -> None:
    assert f"Value error, {BLANK_REASON}" in messages(raised)


def human_origin_reason(what: str) -> str:
    """The exact refusal `_reject_human_origin` must give, naming `what`.

    The component's own name is part of the contract: a message that named a
    fixed component, or none, still raises and still passes a bare
    `pytest.raises` while telling the reader the wrong thing about which
    detected field claimed a human origin.
    """
    return (
        f"Value error, {what} claims a Human origin. Engine 1 never merges an "
        "extracted reading with a human assertion "
        "(ENGINE_1_INPUT_ENGINE_RULES.md:233); a human note belongs in "
        "human_business_context, beside this component and never inside it."
    )


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def an_evidence_object(
    *,
    structured_document: StructuredDocument | None = None,
    confidence_report: ConfidenceReport | None = None,
    human_business_context: HumanBusinessContext | None = None,
    source_references: tuple[str, ...] = ("upload:invoice-481.pdf",),
) -> DocumentEvidenceObject:
    return DocumentEvidenceObject(
        identity=an_identity(),
        document_id=DocumentId.new(),
        source_references=source_references,
        structured_document=structured_document or a_structured_document(),
        human_business_context=human_business_context,
        confidence_report=confidence_report or a_confidence_report(),
    )


# ── INV-11 · the provenance envelope, exactly as the invariant writes it ──────


def test_the_source_types_are_exactly_the_three_the_invariant_names() -> None:
    # SYSTEM_INVARIANTS.md:247. Three, and their spellings are the contract —
    # a fourth type, or `Metadata` instead of `Structured Metadata`, is a
    # silent architecture change (INV-1).
    assert tuple(SourceType) == (
        SourceType.DOCUMENT,
        SourceType.HUMAN,
        SourceType.STRUCTURED_METADATA,
    )
    assert (SourceType.DOCUMENT, SourceType.HUMAN, SourceType.STRUCTURED_METADATA) == (
        "Document",
        "Human",
        "Structured Metadata",
    )


def test_corroborated_carries_only_the_verdict_engine_1_is_permitted_to_write() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:295 and DATA_FLOW.md:573 — Engine 1
    # records `not assessed`, because assessing corroboration is
    # interpretation and this engine is forbidden from interpreting. No
    # document anywhere enumerates a wider set, so a wider set is not modelled.
    assert tuple(Corroborated) == (Corroborated.NOT_ASSESSED,)
    assert Corroborated.NOT_ASSESSED.value == "not assessed"


@pytest.mark.parametrize("invented", ["yes", "no", "true", "corroborated", "unknown"])
def test_an_invented_corroboration_verdict_is_refused(invented: str) -> None:
    # No document enumerates a verdict set. Inventing a three-member enum here
    # would put a decision in code that the specification never made.
    with pytest.raises(ValidationError):
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice-481.pdf",
            evidence_reference="page 1",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=invented,  # type: ignore[arg-type]
        )


def test_a_boolean_corroboration_is_refused() -> None:
    # The invariant table reads like a boolean; Engine 1's rules write a
    # literal. `True` would be the tempting reading and it is not writable
    # here — the gap is reported, not resolved by guessing.
    with pytest.raises(ValidationError):
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice-481.pdf",
            evidence_reference="page 1",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=True,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "missing",
    ["source_type", "source_id", "evidence_reference", "timestamp", "confidence", "corroborated"],
)
def test_every_one_of_the_six_provenance_attributes_is_required(missing: str) -> None:
    # SYSTEM_INVARIANTS.md:243-252. "Every fact records" is six attributes, not
    # five. A fact missing any one of them is the anonymous fact INV-11:254
    # forbids, so it must be unconstructable rather than merely discouraged.
    complete: dict[str, object] = {
        "source_type": SourceType.DOCUMENT,
        "source_id": "invoice-481.pdf",
        "evidence_reference": "page 1",
        "timestamp": WHEN,
        "confidence": HIGH,
        "corroborated": Corroborated.NOT_ASSESSED,
    }
    del complete[missing]
    with pytest.raises(ValidationError, match=missing):
        Provenance(**complete)  # type: ignore[arg-type]


def test_a_naive_timestamp_is_refused() -> None:
    # "When it entered the system" (INV-11:250) is a moment, not a wall-clock
    # reading. Two artifacts stamped 12:00 in different zones would order
    # wrongly in an audit trail and nothing would say so.
    with pytest.raises(ValidationError, match="timezone"):
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice-481.pdf",
            evidence_reference="page 1",
            timestamp=datetime(2026, 8, 3, 12, 0),  # the defect under test
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
        )


def test_a_non_utc_offset_is_accepted_and_kept_exactly() -> None:
    # India is +05:30 and this is an Indian-GST product. Requiring UTC would
    # rewrite the moment the input actually carried.
    ist = timezone(timedelta(hours=5, minutes=30))
    stamped = datetime(2026, 8, 3, 17, 30, tzinfo=ist)
    assert Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-481.pdf",
        evidence_reference="page 1",
        timestamp=stamped,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    ).timestamp.utcoffset() == timedelta(hours=5, minutes=30)


def test_a_float_confidence_is_refused_by_the_shared_type() -> None:
    # Proves this module imports `accountant_dad.confidence` rather than
    # redeclaring its own. 0.98 is a legal SCORE and an illegal TYPE; if it
    # were accepted here, this artifact would have a different confidence rule
    # from its siblings — the exact divergence confidence.py was written after.
    with pytest.raises(ValidationError):
        a_provenance(confidence=0.98)  # type: ignore[arg-type]


def test_a_confidence_outside_the_agreed_range_is_refused() -> None:
    with pytest.raises(ValidationError):
        a_provenance(confidence=Decimal("1.0001"))


def test_provenance_is_frozen_and_refuses_unknown_attributes() -> None:
    # INV-5: a version, once created, is frozen. An extra attribute is a
    # second spelling of some concept, which INV-10 forbids outright.
    origin = a_provenance()
    with pytest.raises(ValidationError):
        origin.source_id = "somewhere-else.pdf"
    with pytest.raises(ValidationError):
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice-481.pdf",
            evidence_reference="page 1",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
            reliability="high",  # type: ignore[call-arg]
        )


def test_a_fact_with_no_evidence_reference_is_refused() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:245 — "A value carried without all three
    # is not evidence and must not be emitted." An empty string is not a
    # location; accepting it would let a value claim traceability it does not
    # have, which is worse than refusing it.
    with pytest.raises(ValidationError):
        a_provenance(evidence_reference="")


def test_a_fact_with_no_source_id_is_refused() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_type=SourceType.DOCUMENT,
            source_id="",
            evidence_reference="page 1",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
        )


# ── the Structured Document ──────────────────────────────────────────────────


def test_a_field_that_could_not_be_read_records_no_value_rather_than_an_empty_one() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:569 — "Absent", "zero" and "unreadable"
    # are three different states and must remain distinguishable. An empty
    # string would collapse "unreadable" into "read as nothing".
    unreadable = a_detected_field(name="Date", value=None, confidence=LOW)
    assert unreadable.value is None
    with pytest.raises(ValidationError):
        a_detected_field(name="Date", value="")


def test_zero_is_a_read_value_and_stays_distinct_from_unreadable() -> None:
    zero = a_detected_field(name="Discount", value="0")
    assert zero.value == "0"
    assert zero.value is not None


def test_a_detected_field_without_provenance_is_refused() -> None:
    with pytest.raises(ValidationError, match="provenance"):
        DetectedField(name="Amount", value="19800.00")  # type: ignore[call-arg]


def test_an_unnamed_detected_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        a_detected_field(name="")


def test_extracted_evidence_may_never_claim_a_human_origin() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:233 — "Engine 1 never merges the two into
    # a single fact." A human assertion filed as a detected field IS that
    # merge: it enters the Structured Document, which is labelled [EXTRACTED],
    # wearing the authority of something read off the artifact.
    with pytest.raises(ValidationError, match="Human"):
        a_structured_document(
            detected_fields=(a_detected_field(source_type=SourceType.HUMAN),),
        )


def test_a_detected_table_may_never_claim_a_human_origin() -> None:
    with pytest.raises(ValidationError, match="Human"):
        a_structured_document(
            detected_tables=(
                DetectedTable(
                    rows=(("Item", "Qty"), ("Laptop", "2")),
                    provenance=a_provenance(source_type=SourceType.HUMAN),
                ),
            ),
        )


def test_structured_metadata_is_still_extractable_evidence() -> None:
    # Disconfirming check on the rule above: it must forbid `Human` only, not
    # "anything that is not Document". DATA_FLOW.md:544 lists upload metadata
    # and file attributes as real sources, and the artifact tree gives them no
    # other home.
    document = a_structured_document(
        detected_fields=(a_detected_field(source_type=SourceType.STRUCTURED_METADATA),),
    )
    assert document.detected_fields[0].provenance.source_type is SourceType.STRUCTURED_METADATA


def test_two_detected_fields_may_not_share_one_name() -> None:
    # The Confidence Report keys scores by field name (ENGINE_1:599-601), so
    # two fields called `Amount` make "which score belongs to which value?"
    # unanswerable — and an unanswerable traceability question is exactly what
    # ENGINE_1:245 refuses to emit.
    with pytest.raises(ValidationError, match="Amount"):
        a_structured_document(
            detected_fields=(
                a_detected_field(name="Amount", value="19800.00"),
                a_detected_field(name="Amount", value="19,800.00"),
            ),
        )


def test_collections_become_tuples_so_the_artifact_cannot_grow_after_creation() -> None:
    # INV-5. `frozen=True` blocks attribute assignment and nothing else — a
    # list field would leave the model immutable while its contents were not.
    document = a_structured_document(detected_fields=(a_detected_field(),))
    assert isinstance(document.detected_fields, tuple)
    with pytest.raises(AttributeError):
        document.detected_fields.append(a_detected_field(name="Date"))  # type: ignore[attr-defined]


def test_a_table_keeps_its_rows_and_its_origin() -> None:
    table = DetectedTable(
        rows=(("Item", "Qty", "Rate"), ("Laptop", "2", "9900.00")),
        provenance=a_provenance(evidence_reference="page 1, table 1"),
    )
    assert table.rows[1] == ("Laptop", "2", "9900.00")
    assert table.provenance.evidence_reference == "page 1, table 1"


# ── the Confidence Report ────────────────────────────────────────────────────


def test_an_uncertainty_marker_without_a_reason_is_refused() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:626 — "Every uncertainty marker carries a
    # reason. A bare score cannot become a good question downstream." A marker
    # with an empty reason is a bare score wearing a label.
    assert UncertaintyMarker(subject="Date", reason="two candidate readings").reason
    with pytest.raises(ValidationError):
        UncertaintyMarker(subject="Date", reason="")
    with pytest.raises(ValidationError):
        UncertaintyMarker(subject="", reason="two candidate readings")


def test_one_field_may_not_carry_two_confidence_scores() -> None:
    # INV-10, one concept one owner. Two scores for one field means no score
    # is authoritative, and a reader silently picks the first.
    with pytest.raises(ValidationError, match="Amount"):
        a_confidence_report(
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=HIGH),
                FieldConfidence(field_name="Amount", confidence=LOW),
            ),
        )


def test_a_risky_field_may_not_be_listed_twice() -> None:
    with pytest.raises(ValidationError, match="Date"):
        a_confidence_report(risky_fields=("Date", "Date"))


def test_a_float_score_is_refused_in_the_confidence_report_too() -> None:
    # The constraint must travel with the type everywhere it appears, not only
    # on Provenance.
    with pytest.raises(ValidationError):
        FieldConfidence(field_name="Amount", confidence=0.98)  # type: ignore[arg-type]


# ── the Human Business Context ───────────────────────────────────────────────


def test_the_human_business_context_must_declare_a_human_origin() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:218 — `Source = Human`, written into the
    # output contract itself. A note filed as `Document` is a claim wearing an
    # observation's provenance.
    with pytest.raises(ValidationError, match="Human"):
        HumanBusinessContext(
            original_user_text="Advance paid to supplier.",
            provenance=a_provenance(source_type=SourceType.DOCUMENT),
        )


def test_the_user_text_is_stored_exactly_as_typed() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:333 — "the text is stored verbatim. Not
    # tidied, not corrected, not summarised, not normalised." Leading spaces,
    # a trailing newline and a double space are all things a helpful
    # normaliser would remove; removing them would make the stored note the
    # system's paraphrase, and nothing downstream could tell.
    typed = "  bought  laptops for the design team\nfor Invoice 481 \n"
    kept = HumanBusinessContext(
        original_user_text=typed,
        provenance=a_provenance(source_type=SourceType.HUMAN),
    )
    assert kept.original_user_text == typed


def test_an_empty_note_is_not_a_note() -> None:
    # The context is present "only when the user supplied a description"
    # (ENGINE_1:231). An empty string would be a supplied description that
    # says nothing — indistinguishable from the absent case, which has its own
    # representation.
    with pytest.raises(ValidationError):
        HumanBusinessContext(
            original_user_text="",
            provenance=a_provenance(source_type=SourceType.HUMAN),
        )


# ── the Document Evidence Object ─────────────────────────────────────────────


def test_an_evidence_object_is_complete_with_no_human_business_context() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:138 — "The Human Business Description is
    # optional. The system must work correctly when none is provided."
    assert an_evidence_object().human_business_context is None


def test_a_human_note_travels_beside_the_extracted_evidence_not_inside_it() -> None:
    # DATA_FLOW.md:65 — separate, linked entries. Linked by the artifact,
    # separate by field. There is no place to put the note among the detected
    # fields, and that absence is the design.
    note = HumanBusinessContext(
        original_user_text="This payment settles Invoice 481.",
        provenance=a_provenance(source_type=SourceType.HUMAN),
    )
    evidence = an_evidence_object(
        structured_document=a_structured_document(detected_fields=(a_detected_field(),)),
        confidence_report=a_confidence_report(
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=HIGH),),
        ),
        human_business_context=note,
    )
    assert evidence.human_business_context is not None
    assert evidence.human_business_context.original_user_text == "This payment settles Invoice 481."
    assert [field.name for field in evidence.structured_document.detected_fields] == ["Amount"]


def test_every_detected_field_must_carry_a_confidence_score() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:239-245, the traceability rule. A value
    # with no score in the Confidence Report is a value whose reliability the
    # artifact does not state, and it must not be emitted.
    with pytest.raises(ValidationError, match="Amount"):
        an_evidence_object(
            structured_document=a_structured_document(detected_fields=(a_detected_field(),)),
            confidence_report=a_confidence_report(confidence_scores=()),
        )


def test_the_confidence_report_and_the_field_provenance_may_not_disagree() -> None:
    # INV-11 puts a Confidence on every fact; the Confidence Report holds the
    # scores. They are the same number in two places, so the only safe artifact
    # is one where they agree. Refused loudly rather than reconciled silently.
    with pytest.raises(ValidationError, match="Amount"):
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=HIGH),),
            ),
            confidence_report=a_confidence_report(
                confidence_scores=(FieldConfidence(field_name="Amount", confidence=LOW),),
            ),
        )


def test_the_same_score_written_at_a_different_scale_still_agrees() -> None:
    # Disconfirming check on the rule above. confidence.py deliberately keeps
    # `0.98` as `0.98` rather than padding it, so a producer that wrote the
    # score once at each scale is not in conflict — 0.98 and 0.9800 are one
    # number. A string comparison here would reject a valid artifact.
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=(a_detected_field(confidence=Decimal("0.98")),),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=Decimal("0.9800")),),
        ),
    )
    assert evidence.confidence_report.confidence_scores[0].confidence == Decimal("0.98")


def test_an_extra_score_for_something_that_is_not_a_detected_field_is_allowed() -> None:
    # Disconfirming check the other way. `confidence` scores "per field and
    # overall" (SUB_ENGINE_RESPONSIBILITIES.md:84), so the report is permitted
    # to be wider than the field list. The rule is one-directional by design.
    evidence = an_evidence_object(
        structured_document=a_structured_document(detected_fields=(a_detected_field(),)),
        confidence_report=a_confidence_report(
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=HIGH),
                FieldConfidence(field_name="overall", confidence=LOW),
            ),
        ),
    )
    assert len(evidence.confidence_report.confidence_scores) == len(("Amount", "overall"))


def test_an_evidence_object_must_name_at_least_one_source_reference() -> None:
    # ENGINE_1_INPUT_ENGINE_RULES.md:142 — every input must preserve its
    # original source. An artifact referencing nothing has lost it.
    with pytest.raises(ValidationError):
        an_evidence_object(source_references=())


def test_a_source_reference_may_not_be_listed_twice() -> None:
    with pytest.raises(ValidationError, match=re.escape("upload:invoice-481.pdf")):
        an_evidence_object(
            source_references=("upload:invoice-481.pdf", "upload:invoice-481.pdf"),
        )


def test_the_evidence_object_is_frozen_and_refuses_unknown_attributes() -> None:
    evidence = an_evidence_object()
    with pytest.raises(ValidationError):
        evidence.document_id = DocumentId.new()
    with pytest.raises(ValidationError):
        DocumentEvidenceObject(
            identity=an_identity(),
            document_id=DocumentId.new(),
            source_references=("upload:invoice-481.pdf",),
            structured_document=a_structured_document(),
            confidence_report=a_confidence_report(),
            accounting_treatment="Purchase of machinery",  # type: ignore[call-arg]
        )


def test_the_evidence_object_carries_the_universal_identity_envelope() -> None:
    # DATA_FLOW.md:32 — Artifact ID, Version, Parent Artifact Version(s) and
    # exactly one Transaction ID, imported rather than restated.
    evidence = an_evidence_object()
    assert evidence.identity.version == 1
    assert evidence.identity.parent_versions == ()
    assert isinstance(evidence.identity.transaction_id, TransactionId)


# ── INV-9 · Document ID identifies, and does nothing else ────────────────────


def test_a_document_id_is_not_an_artifact_id() -> None:
    # INV-3 and INV-9. Two identifiers with different jobs are two types, so
    # passing one where the other belongs fails at construction rather than
    # at a code review that might not happen.
    with pytest.raises(ValidationError):
        DocumentEvidenceObject(
            identity=an_identity(),
            document_id=ArtifactId.new(),  # type: ignore[arg-type]
            source_references=("upload:invoice-481.pdf",),
            structured_document=a_structured_document(),
            confidence_report=a_confidence_report(),
        )


def test_a_bare_uuid_is_not_a_document_id() -> None:
    with pytest.raises(ValidationError):
        DocumentEvidenceObject(
            identity=an_identity(),
            document_id=uuid.uuid4(),  # type: ignore[arg-type]
            source_references=("upload:invoice-481.pdf",),
            structured_document=a_structured_document(),
            confidence_report=a_confidence_report(),
        )


def test_a_document_id_encodes_nothing_a_later_engine_could_reason_from() -> None:
    # INV-9. A ULID would encode creation time and a sequence would encode
    # order; both are real information an engine could read out of an
    # identifier. Version 4 is random, so opacity is a property of the value
    # rather than a discipline someone has to maintain.
    first, second = DocumentId.new(), DocumentId.new()
    assert first != second
    assert first.value.version == RANDOM_UUID_VERSION


def test_a_document_id_is_frozen() -> None:
    identifier = DocumentId.new()
    with pytest.raises((AttributeError, TypeError)):
        identifier.value = uuid.uuid4()  # type: ignore[misc]


# ── a padded blank is a blank ─────────────────────────────────────────────


@pytest.mark.parametrize("padded", ["   ", "\t", "\n", " \t\n "])
def test_a_padded_blank_is_refused_wherever_a_real_value_is_required(padded: str) -> None:
    """`NonEmptyText` was `Field(min_length=1)`, which refuses `""` and accepts
    `"   "`. The other five artifact schemas reject blank-after-strip, so one
    concept had two behaviours — and the looser one lived in the artifact that
    carries the system's only evidence.

    ENGINE_1:626 — "Every uncertainty marker carries a reason." A reason of
    three spaces is not a reason. ENGINE_1:245 — a value without a real source
    id and evidence reference "is not evidence and must not be emitted."

    Found empirically by the conformance registry, not by reading the code.
    """
    with pytest.raises(ValidationError) as raised:
        UncertaintyMarker(subject="Amount", reason=padded)
    assert_refused_as_blank(raised)
    with pytest.raises(ValidationError) as raised:
        UncertaintyMarker(subject=padded, reason="smudged")
    assert_refused_as_blank(raised)


def test_a_real_value_with_surrounding_space_is_still_accepted() -> None:
    """Stripping decides emptiness; it never edits the stored value. A source
    reference the caller wrote with a trailing space is still that reference."""
    marker = UncertaintyMarker(subject=" Amount ", reason="smudged")
    assert marker.subject == " Amount "
