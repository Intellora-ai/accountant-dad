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

import ast
import re
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from authored_source import authored_tree
from pydantic import BaseModel, ValidationError

import accountant_dad.artifacts.evidence
import accountant_dad.engines.input_engine.assembly
import accountant_dad.engines.input_engine.confidence_report
import accountant_dad.engines.input_engine.pipeline
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
from accountant_dad.confidence import (
    UNMEASURED,
    ConfidenceOrUnmeasured,
    MeasurementFailedType,
    MeasurementState,
    NotApplicableType,
    NotMeasuredType,
    UnmeasuredType,
    measurement_state,
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
    confidence: ConfidenceOrUnmeasured = HIGH,
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
    confidence: ConfidenceOrUnmeasured = HIGH,
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
    #
    # Asserted by EQUALITY against `human_origin_reason`, not `match="Human"`.
    # `match` is a substring search, so every re-wording of the refusal below
    # the word `Human` still passed it — measured: seven mutations of this
    # message survived CI run 30946373087 while this test stayed green. The
    # message IS the contract here: it is what tells whoever debugs the refusal
    # WHICH component claimed the origin and WHERE the note actually belongs.
    with pytest.raises(ValidationError) as raised:
        a_structured_document(
            detected_fields=(a_detected_field(name="Amount", source_type=SourceType.HUMAN),),
        )

    assert messages(raised) == [human_origin_reason("detected field 'Amount'")]


def test_a_detected_table_may_never_claim_a_human_origin() -> None:
    # The table's INDEX is the only handle a reader has on which table was
    # refused — tables have no name — so the index is asserted, not just the
    # word `Human`.
    with pytest.raises(ValidationError) as raised:
        a_structured_document(
            detected_tables=(
                DetectedTable(
                    rows=(("Item", "Qty"), ("Laptop", "2")),
                    provenance=a_provenance(source_type=SourceType.HUMAN),
                ),
            ),
        )

    assert messages(raised) == [human_origin_reason("detected table 0")]


def test_the_refused_table_is_named_by_its_own_index_not_the_first() -> None:
    # Disconfirming check on the test above: with one table, index 0 is also
    # what a hard-coded 0 would print. Two tables, the SECOND one human, is the
    # case that can tell an enumeration from a constant.
    extracted = DetectedTable(
        rows=(("Item", "Qty"), ("Laptop", "2")),
        provenance=a_provenance(source_type=SourceType.DOCUMENT),
    )
    asserted = DetectedTable(
        rows=(("Note", "Advance paid to supplier"),),
        provenance=a_provenance(source_type=SourceType.HUMAN),
    )

    with pytest.raises(ValidationError) as raised:
        a_structured_document(detected_tables=(extracted, asserted))

    assert messages(raised) == [human_origin_reason("detected table 1")]


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


# ── the absence of a measurement, through the real schema — Amendment 5 ──────


def test_a_fact_may_record_that_nothing_measured_it() -> None:
    # The whole amendment, at its smallest. `reader.read_pdf_text_layer` scores
    # nothing and a PDF text layer is the MVP's primary input, so a provenance
    # that cannot say "not measured" cannot describe the MVP's own documents.
    # Identity, not equality: a schema that rebuilt the sentinel would still
    # look right under `isinstance`.
    provenance = a_provenance(confidence=UNMEASURED)
    assert provenance.confidence is UNMEASURED


def test_the_confidence_attribute_is_still_mandatory_and_none_is_still_refused() -> None:
    # INV-11 is untouched: six attributes, none optional. The sentinel makes the
    # VALUE absent, never the ATTRIBUTE. `None` is the shape the widening would
    # most plausibly have leaked in — it already means three other things in
    # this pipeline — so it must still be refused rather than quietly stored as
    # a second kind of nothing.
    payload: dict[str, object] = {
        "source_type": SourceType.DOCUMENT,
        "source_id": "invoice-481.pdf",
        "evidence_reference": "page 1",
        "timestamp": WHEN,
        "confidence": None,
        "corroborated": Corroborated.NOT_ASSESSED,
    }
    with pytest.raises(ValidationError):
        Provenance.model_validate(payload)


def test_an_unmeasured_field_crosses_when_the_report_says_the_same_thing() -> None:
    """THE STATE THAT USED TO BE UNREPRESENTABLE, END TO END.

    Both sides say "nobody measured this", so there is nothing to contradict
    and the artifact is valid. This is what makes a text-layer reading
    emittable at all — before the amendment `detected_fields` had to be empty,
    and `ENGINE_1_INPUT_ENGINE_RULES.md:245` was satisfied by dropping every
    value rather than by carrying all three.
    """
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=(a_detected_field(confidence=UNMEASURED),),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=UNMEASURED),),
        ),
    )
    field = evidence.structured_document.detected_fields[0]
    assert isinstance(field.provenance.confidence, UnmeasuredType)
    assert isinstance(evidence.confidence_report.confidence_scores[0].confidence, UnmeasuredType)


def test_an_unmeasured_field_with_no_report_entry_is_still_refused() -> None:
    # The check is EXTENDED, never exempted. "Nobody measured this" is a
    # statement about reliability and silence is not, so an unscored field
    # still has to appear in the report. Exempting it would have hidden exactly
    # the fields whose reliability is least established.
    with pytest.raises(ValidationError) as raised:
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=UNMEASURED),),
            ),
            confidence_report=a_confidence_report(confidence_scores=()),
        )
    assert messages(raised) == [
        "Value error, detected field 'Amount' carries no confidence score. "
        "A value whose reliability the artifact does not state must not be emitted."
    ]


@pytest.mark.parametrize("invented", [Decimal("1.0000"), Decimal("0.0000"), Decimal("0.4200")])
def test_a_report_that_scores_a_reading_nobody_measured_is_refused(invented: Decimal) -> None:
    """THE ATTACK THIS AMENDMENT EXISTS TO STOP, ASSERTED DIRECTLY.

    The provenance says nothing measured this value; the Confidence Report
    claims a number for it. One of the two is asserting a reading nobody took,
    and the artifact must not be emitted either way.

    `1.0000` and `0.0000` are parametrised on purpose — they are the two
    numbers a "helpful" default would produce, and the two
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` and Law 24 forbid inventing. `0.4200`
    is there so this cannot pass by testing only the extremes.

    Equality on the message, not `match=`: a refusal reworded down to "no"
    still contains "Amount" and still passes a substring check, and the wording
    is what tells the next reader that the two sides disagree about whether a
    measurement exists at all rather than about its magnitude.
    """
    with pytest.raises(ValidationError) as raised:
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=UNMEASURED),),
            ),
            confidence_report=a_confidence_report(
                confidence_scores=(FieldConfidence(field_name="Amount", confidence=invented),),
            ),
        )
    assert messages(raised) == [
        f"Value error, the Confidence Report and the provenance of 'Amount' disagree: "
        f"measured {invented} against not measured ({UNMEASURED.basis}). "
        "Refused rather than reconciled silently — only the confidence "
        "sub-engine may set a score (INV-2). Two different measurement "
        "states are a disagreement, not a special case: one of them "
        "asserts something about this reading that the other denies."
    ]


def test_a_report_that_erases_a_real_measurement_is_refused_too() -> None:
    # The same rule from the other side, and the more dangerous direction: a
    # field the reader genuinely scored at 0.4200 while the report claims
    # nobody measured it. That would hide a weak reading behind "not measured",
    # which reads as blameless. Asserted separately so a one-sided
    # implementation cannot pass.
    with pytest.raises(ValidationError) as raised:
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=LOW),),
            ),
            confidence_report=a_confidence_report(
                confidence_scores=(FieldConfidence(field_name="Amount", confidence=UNMEASURED),),
            ),
        )
    assert messages(raised) == [
        f"Value error, the Confidence Report and the provenance of 'Amount' disagree: "
        f"not measured ({UNMEASURED.basis}) against measured {LOW}. "
        "Refused rather than reconciled silently — only the confidence "
        "sub-engine may set a score (INV-2). Two different measurement "
        "states are a disagreement, not a special case: one of them "
        "asserts something about this reading that the other denies."
    ]


def test_two_separately_built_absences_agree_and_the_artifact_is_accepted() -> None:
    """FOUND BY RED-TEAM, NOT BY WRITING THE TEST ALONGSIDE THE CODE.

    Replacing `records_the_same_measurement(...)` in `evidence.py` with a plain
    `scores[name] != field.provenance.confidence` SURVIVED the whole suite —
    180 tests, all green. `!=` reaches the right answer for every case the
    other tests cover, but it reaches it BY ACCIDENT: `Decimal` and the
    sentinel each return `NotImplemented`, Python falls back to identity, and
    identity happens to be correct while one singleton is the only instance in
    play.

    It diverges in exactly one place, and this is it. Two SEPARATELY BUILT
    absences are the same fact and must agree; under `!=` they are two
    different objects and the artifact is refused — a valid document rejected
    because of which instance a caller happened to construct.

    This is reachable, not hypothetical: the validator returns whatever
    instance it was given, so anything that rebuilds a `Provenance` or a
    `FieldConfidence` from parts — a deserialiser, a second module importing
    the class rather than the singleton — produces a fresh one. Identity is
    deliberately NOT load-bearing (`confidence.py`), and this is the test that
    makes that claim true rather than merely written down.
    """
    one = NotMeasuredType(basis="the text layer was transcribed, not recognised")
    another = NotMeasuredType(basis="no recogniser ran over this region")
    assert one is not another, "two constructions must be two objects, or this proves nothing"
    assert one is not UNMEASURED
    # And the two BASES differ deliberately. Agreement is over the STATE, never
    # over the prose explaining it — otherwise rewording a reason in one module
    # would refuse an artifact that states one consistent fact (Amendment 7).
    assert one.basis != another.basis

    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=(a_detected_field(confidence=one),),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=another),),
        ),
    )
    assert evidence.structured_document.detected_fields[0].provenance.confidence is one
    assert evidence.confidence_report.confidence_scores[0].confidence is another


def test_a_measured_and_an_unmeasured_field_coexist_in_one_artifact() -> None:
    # A mixed document is the realistic case — a scanned page beside a text
    # layer — and each field must keep its own state. If the schema collapsed
    # them, one of the two facts would be lost on every real invoice.
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=(
                a_detected_field(name="Amount", confidence=HIGH),
                a_detected_field(name="Invoice No", confidence=UNMEASURED),
            ),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=HIGH),
                FieldConfidence(field_name="Invoice No", confidence=UNMEASURED),
            ),
        ),
    )
    scored, unscored = evidence.structured_document.detected_fields
    assert scored.provenance.confidence == HIGH
    assert isinstance(unscored.provenance.confidence, UnmeasuredType)


# ── all four states, through the real schema — Amendment 7 ──────────────────
#
# Amendment 5 gave the schema ONE way to say "no measurement". Amendment 7 gives
# it three, because the pipeline produces three genuinely different facts and
# collapsing them is how the last one was lost. Every test below runs through
# the real frozen models, never through the type in isolation: a state the type
# can hold and the artifact cannot is a state that does not exist.

#: The three non-measured states, each with the basis a real producer states.
#: Built here rather than imported so a test asserting a state cannot be
#: satisfied by a module-level singleton somebody else already validated.
NOT_MEASURED = NotMeasuredType(basis="the text layer was transcribed, not recognised")
NOT_APPLICABLE = NotApplicableType(basis="the grid position holds no text to score")
FAILED = MeasurementFailedType(basis="the recogniser could not read this region at all")


@pytest.mark.parametrize(
    ("absence", "expected"),
    [
        (NOT_MEASURED, MeasurementState.NOT_MEASURED),
        (NOT_APPLICABLE, MeasurementState.NOT_APPLICABLE),
        (FAILED, MeasurementState.FAILED),
    ],
)
def test_each_absent_state_survives_the_schema_as_itself(
    absence: UnmeasuredType, expected: MeasurementState
) -> None:
    """Identity AND state. A schema that rebuilt the value, or that stored one
    absence as another, would still satisfy `isinstance(x, UnmeasuredType)` —
    which is exactly the collapse the three classes exist to prevent.
    """
    provenance = a_provenance(confidence=absence)
    assert provenance.confidence is absence
    assert measurement_state(provenance.confidence) is expected


@pytest.mark.parametrize("absence", [NOT_MEASURED, NOT_APPLICABLE, FAILED])
def test_every_absent_state_reaches_the_artifact_carrying_its_reason(
    absence: UnmeasuredType,
) -> None:
    """A state with no reason is a gap that reads as a decision.

    The `basis` is what makes the artifact answer *why* rather than only
    *whether* — `ENGINE_1_INPUT_ENGINE_RULES.md:626` settles the general form:
    a bare score cannot become a good question downstream, and a bare absence
    is worse than a bare score. Asserted on the value that came OUT of the
    frozen model, so a schema that dropped the reason on the way in goes red.
    """
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=(a_detected_field(confidence=absence),),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=absence),),
        ),
    )
    carried = evidence.structured_document.detected_fields[0].provenance.confidence
    assert isinstance(carried, UnmeasuredType)
    assert carried.basis.strip() != ""
    assert carried.basis == absence.basis


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (NOT_MEASURED, NOT_APPLICABLE),
        (NOT_APPLICABLE, NOT_MEASURED),
        (NOT_MEASURED, FAILED),
        (FAILED, NOT_MEASURED),
        (NOT_APPLICABLE, FAILED),
        (FAILED, NOT_APPLICABLE),
    ],
)
def test_two_different_absences_are_a_disagreement_the_artifact_refuses(
    left: UnmeasuredType, right: UnmeasuredType
) -> None:
    """THE REFUSAL AMENDMENT 5 COULD NOT EXPRESS, AND THE REASON FOR THREE
    CLASSES RATHER THAN ONE.

    Under a single sentinel every pair here reads as "both declined to score"
    and the artifact is accepted. But one side saying *a real value is carried
    with nothing behind it* and the other saying *there is no value at all* is
    two components disagreeing about whether the document was even read there.
    That must not travel into the artifact unremarked.

    Both directions are parametrised: a one-sided implementation that checked
    only the provenance, or only the report, would otherwise pass.
    """
    with pytest.raises(ValidationError) as raised:
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=left),),
            ),
            confidence_report=a_confidence_report(
                confidence_scores=(FieldConfidence(field_name="Amount", confidence=right),),
            ),
        )
    assert messages(raised) == [
        f"Value error, the Confidence Report and the provenance of 'Amount' disagree: "
        f"{measurement_state(right).value} ({right.basis}) against "
        f"{measurement_state(left).value} ({left.basis}). "
        "Refused rather than reconciled silently — only the confidence "
        "sub-engine may set a score (INV-2). Two different measurement "
        "states are a disagreement, not a special case: one of them "
        "asserts something about this reading that the other denies."
    ]


@pytest.mark.parametrize("absence", [NOT_MEASURED, NOT_APPLICABLE, FAILED])
@pytest.mark.parametrize("invented", [Decimal("1.0000"), Decimal("0.0000"), Decimal("0.4200")])
def test_no_absent_state_may_be_scored_by_the_report(
    absence: UnmeasuredType, invented: Decimal
) -> None:
    # The measured-against-absent refusal, proven for ALL THREE absences rather
    # than only for the one that existed first. A state added later that forgot
    # to inherit the refusal would be a new hole of exactly the old shape.
    with pytest.raises(ValidationError, match="disagree"):
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=absence),),
            ),
            confidence_report=a_confidence_report(
                confidence_scores=(FieldConfidence(field_name="Amount", confidence=invented),),
            ),
        )


@pytest.mark.parametrize("absence", [NOT_MEASURED, NOT_APPLICABLE, FAILED])
def test_no_absent_state_may_be_omitted_from_the_report(absence: UnmeasuredType) -> None:
    # Silence is not a statement about reliability, for any of the three. This
    # is the check that stops a future "unscorable fields need no entry"
    # shortcut, which would hide precisely the fields least established.
    with pytest.raises(ValidationError, match="carries no confidence score"):
        an_evidence_object(
            structured_document=a_structured_document(
                detected_fields=(a_detected_field(confidence=absence),),
            ),
            confidence_report=a_confidence_report(confidence_scores=()),
        )


def test_four_fields_in_four_different_states_coexist_in_one_artifact() -> None:
    """The realistic mixed document, and the completeness claim in one object.

    A scanned block the recogniser scored, a text-layer value nobody scored, a
    blank grid position with nothing to score, and a region the recogniser
    could not read. All four are ordinary outcomes of one run over one invoice,
    and each field must keep its own state — if the schema flattened any pair,
    a fact would be lost on every real document rather than on an edge case.
    """
    states: tuple[tuple[str, ConfidenceOrUnmeasured, MeasurementState], ...] = (
        ("Amount", HIGH, MeasurementState.MEASURED),
        ("Invoice No", NOT_MEASURED, MeasurementState.NOT_MEASURED),
        ("Line 3 Rate", NOT_APPLICABLE, MeasurementState.NOT_APPLICABLE),
        ("Supplier GSTIN", FAILED, MeasurementState.FAILED),
    )
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=tuple(
                a_detected_field(name=name, confidence=value) for name, value, _ in states
            ),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=tuple(
                FieldConfidence(field_name=name, confidence=value) for name, value, _ in states
            ),
        ),
    )
    carried = {
        field.name: measurement_state(field.provenance.confidence)
        for field in evidence.structured_document.detected_fields
    }
    assert carried == {name: expected for name, _, expected in states}
    # Four fields, four DISTINCT states — asserted as a set so a schema that
    # stored every absence as the same one cannot pass by matching names.
    assert len(set(carried.values())) == len(states)


def test_no_confidence_bearing_slot_in_this_schema_carries_a_default() -> None:
    """ "Never defaulting", enforced against the real models rather than trusted.

    A default is how a fabricated confidence gets in without anyone typing a
    number: the caller says nothing and the schema supplies "good enough".
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids that by name. Asserted through
    `model_fields` so it covers every confidence slot the schema has, including
    one added after this test was written.
    """
    slots: list[tuple[type[BaseModel], str]] = [
        (Provenance, "confidence"),
        (FieldConfidence, "confidence"),
    ]
    for model, name in slots:
        assert model.model_fields[name].is_required(), (
            f"{model.__name__}.{name} has a default. A confidence slot that "
            "fills itself in is how a number nobody measured reaches a ledger."
        )
    # And the omission really is refused, not merely declared required.
    for model, name in slots:
        with pytest.raises(ValidationError, match=name):
            model.model_validate({})


# ── THE INVARIANT: no value may exist without measurable provenance ──────────
#
# Everything above proves the TYPE behaves. These two prove no code path can get
# round it — one over the source of every module that could write a confidence,
# one over a real artifact walked field by field. Both are needed and neither
# replaces the other: a source rule cannot see a value computed at runtime, and
# a runtime walk cannot see a fabrication in a branch this suite never enters.

#: The two schema slots that carry a confidence into the artifact. Named rather
#: than pattern-matched on the word "confidence": an Engine 2 result also has a
#: `confidence=`, it is a different concept with a different owner, and a rule
#: that swept it up would be enforcing this artifact's law on somebody else's.
CONFIDENCE_BEARING_CONSTRUCTORS = ("Provenance", "FieldConfidence")


def _confidence_arguments(tree: ast.Module) -> list[tuple[int, ast.expr]]:
    """Every `confidence=` handed to one of those two constructors, with its line."""
    found: list[tuple[int, ast.expr]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", None)
        if name not in CONFIDENCE_BEARING_CONSTRUCTORS:
            continue
        found.extend(
            (keyword.value.lineno, keyword.value)
            for keyword in node.keywords
            if keyword.arg == "confidence"
        )
    return found


def test_no_module_writes_a_literal_into_a_confidence_slot() -> None:
    """A fabricated confidence does not arrive as a bug. It arrives as somebody
    typing a number that looks fine.

    `1.0000` is the default `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids BY
    NAME; `0.0000` asserts a worthlessness nobody measured. Both are one
    keystroke away at every call site, and neither the type nor the schema can
    tell a literal from a measurement — by the time the value exists it is just
    a Decimal on the agreed scale.

    So the rule is about the SOURCE: a confidence entering this artifact is
    either a value some component measured (a name, an attribute, a call) or an
    explicitly named absent state. Never a constant written in place.

    Read through `authored_source`, never `inspect.getsource`: a test that
    reads what the interpreter happens to be running is reading a rewritten
    file, not the one under review (L-013).

    WHAT THIS DOES NOT CATCH, STATED SO NOBODY MISTAKES IT FOR TOTAL. It sees
    KEYWORD ARGUMENTS to the two constructors, so `Provenance.model_validate({
    "confidence": 1.0, ...})` passes it. That path is not a hole — the
    validator refuses a `float` outright — but it is refused by the TYPE and
    not by this test, and the two guards are worth keeping separate in a
    reader's mind.
    """
    modules = [
        accountant_dad.artifacts.evidence,
        accountant_dad.engines.input_engine.confidence_report,
        accountant_dad.engines.input_engine.pipeline,
        accountant_dad.engines.input_engine.assembly,
    ]
    offenders: list[str] = []
    for module in modules:
        for line, value in _confidence_arguments(authored_tree(module)):
            if isinstance(value, ast.Constant):
                offenders.append(f"{module.__name__}:{line} — confidence={value.value!r}")
    assert offenders == [], (
        "a confidence was written in as a constant:\n  "
        + "\n  ".join(offenders)
        + "\n\nA confidence is measured by a component or it is an explicitly "
        "named absent state. A literal is neither, and nothing downstream can "
        "tell it from a real reading (Law 24)."
    )


def test_the_rule_above_would_actually_catch_a_fabricated_confidence() -> None:
    # Guards the guard. A matcher that silently found nothing would leave the
    # test above green forever — it asserts an EMPTY list, which is what an
    # inert matcher also produces. So the matcher is run against source that
    # DOES fabricate one, and must find it.
    fabricated = ast.parse(
        'Provenance(source_type=x, confidence=Decimal("1.0000"), corroborated=y)\n'
        "FieldConfidence(field_name='Amount', confidence=1.0)\n"
    )
    found = _confidence_arguments(fabricated)
    assert [isinstance(value, ast.Constant) for _, value in found] == [False, True], (
        "Decimal('1.0000') is a Call and 1.0 is a Constant — the matcher must "
        "report the node it found, not a verdict of its own"
    )


def test_every_confidence_in_a_real_artifact_names_its_state_and_its_reason() -> None:
    """THE RUNTIME HALF, over an artifact carrying all four states at once.

    Walked rather than spot-checked: every `Provenance` and every
    `FieldConfidence` in the object must yield a `MeasurementState`, and every
    one that is not MEASURED must carry a non-blank reason. `measurement_state`
    RAISES on anything that is neither a Decimal nor a stated absence, so a
    `float`, a `None` or a stray string that reached a slot fails this test
    rather than being reported as a measurement.
    """
    absences: dict[str, ConfidenceOrUnmeasured] = {
        "Amount": HIGH,
        "Invoice No": NOT_MEASURED,
        "Line 3 Rate": NOT_APPLICABLE,
        "Supplier GSTIN": FAILED,
    }
    evidence = an_evidence_object(
        structured_document=a_structured_document(
            detected_fields=tuple(
                a_detected_field(name=name, confidence=value) for name, value in absences.items()
            ),
        ),
        confidence_report=a_confidence_report(
            confidence_scores=tuple(
                FieldConfidence(field_name=name, confidence=value)
                for name, value in absences.items()
            ),
        ),
    )

    carried: list[ConfidenceOrUnmeasured] = [
        field.provenance.confidence for field in evidence.structured_document.detected_fields
    ]
    carried.extend(score.confidence for score in evidence.confidence_report.confidence_scores)
    assert len(carried) == 2 * len(absences), "the walk must reach both sides, or it proves half"

    for value in carried:
        state = measurement_state(value)
        if state is not MeasurementState.MEASURED:
            assert isinstance(value, UnmeasuredType)
            assert value.basis.strip() != "", (
                f"a {state.value} confidence reached the artifact with no reason. "
                "An absence with no stated reason is a gap that reads as a decision."
            )

    # And every detected field carries a source and a location alongside it —
    # the other two thirds of what ENGINE_1_INPUT_ENGINE_RULES.md:245 requires
    # before a value counts as evidence at all.
    for field in evidence.structured_document.detected_fields:
        assert field.provenance.source_id.strip() != ""
        assert field.provenance.evidence_reference.strip() != ""


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
