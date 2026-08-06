"""`assembly` — the Input Engine's own combination of its four sub-engines.

Written against `accountant_dad.artifacts.evidence` and
`accountant_dad.identity` exactly as `tests/unit/test_evidence.py` does, using
local builders shaped the same way — every value the test cares about is an
explicit argument, nothing under test is defaulted away.

The boundary tests matter more than the happy path (the task that produced
this file said so, and `ENGINE_1_INPUT_ENGINE_RULES.md:105` makes it a rule,
not a preference): a missing part must fail loudly and name itself, a low
confidence must survive unchanged, an unknown must survive unchanged, and two
disagreeing readings must both survive — assembly picks no winner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    Corroborated,
    DetectedField,
    DetectedTable,
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    UncertaintyMarker,
)
from accountant_dad.engines.input_engine.assembly import (
    CleanerOutput,
    ConfidenceOutput,
    MissingSubEngineOutputError,
    ParserOutput,
    ReaderOutput,
    SubEngineOutputs,
    assemble,
)
from accountant_dad.identity import (
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
)

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

#: Two readings disagree and BOTH must come out the far side. Named rather
#: than written as a bare `2` because the number is the assertion: assembly
#: resolving the conflict would leave one, and one is what this catches.
BOTH_DISAGREEING_READINGS = 2

#: A correction is a NEW version, never an edit of the first. The second
#: assembly must therefore be version 2 and the first must still read 1.
CORRECTED_VERSION = 2
HIGH = Decimal("0.9800")
LOW = Decimal("0.1000")


# ── builders ─────────────────────────────────────────────────────────────────


def an_identity(
    *, version: int = 1, parent_versions: tuple[ParentVersion, ...] = ()
) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=version,
        parent_versions=parent_versions,
        transaction_id=TransactionId.new(),
    )


def a_provenance(
    *, confidence: Decimal = HIGH, evidence_reference: str = "page 1, box (10, 10)"
) -> Provenance:
    return Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference=evidence_reference,
        timestamp=WHEN,
        confidence=confidence,
        corroborated=Corroborated.NOT_ASSESSED,
    )


def a_detected_field(
    *, name: str = "Amount", value: str | None = "4500.00", confidence: Decimal = HIGH
) -> DetectedField:
    return DetectedField(name=name, value=value, provenance=a_provenance(confidence=confidence))


def a_cleaner_output(
    *,
    quality_issues_detected: tuple[str, ...] = ("noise_sigma=2.1",),
    preservation_status: str = "the cleaned representation is the safer basis for reading",
) -> CleanerOutput:
    return CleanerOutput(
        cleaned_document_representation=object(),
        quality_issues_detected=quality_issues_detected,
        preservation_status=preservation_status,
    )


def a_reader_output(
    *,
    raw_extracted_text: str = "ACME TRADERS\nInvoice 900\nAmount 4500.00",
    source_locations: tuple[str, ...] = ("page 1, box (10, 10)",),
    extraction_confidence: tuple[str, ...] = ("Amount: 0.98",),
) -> ReaderOutput:
    return ReaderOutput(
        raw_extracted_text=raw_extracted_text,
        source_locations=source_locations,
        extraction_confidence=extraction_confidence,
    )


def a_parser_output(
    *,
    document_structure: str = "header / body / totals",
    detected_fields: tuple[DetectedField, ...] = (),
    detected_tables: tuple[DetectedTable, ...] = (),
) -> ParserOutput:
    return ParserOutput(
        document_structure=document_structure,
        detected_fields=detected_fields,
        detected_tables=detected_tables,
    )


def a_confidence_output(
    *,
    confidence_scores: tuple[FieldConfidence, ...] = (),
    uncertainty_markers: tuple[UncertaintyMarker, ...] = (),
    reliability_information: str = "scan legible; totals block unclear",
    risky_fields: tuple[str, ...] = (),
) -> ConfidenceOutput:
    return ConfidenceOutput(
        confidence_scores=confidence_scores,
        uncertainty_markers=uncertainty_markers,
        reliability_information=reliability_information,
        risky_fields=risky_fields,
    )


def complete_parts(
    *,
    detected_fields: tuple[DetectedField, ...] = (),
    confidence_scores: tuple[FieldConfidence, ...] = (),
    uncertainty_markers: tuple[UncertaintyMarker, ...] = (),
) -> SubEngineOutputs:
    return SubEngineOutputs(
        cleaner=a_cleaner_output(),
        reader=a_reader_output(),
        parser=a_parser_output(detected_fields=detected_fields),
        confidence=a_confidence_output(
            confidence_scores=confidence_scores, uncertainty_markers=uncertainty_markers
        ),
    )


# ── all four parts present ─────────────────────────────────────────────────


def test_all_four_parts_present_produce_a_complete_object_traceable_to_each_sub_engine() -> None:
    field = a_detected_field()
    reader = a_reader_output()
    parser = a_parser_output(detected_fields=(field,))
    confidence = a_confidence_output(
        confidence_scores=(FieldConfidence(field_name="Amount", confidence=HIGH),),
        uncertainty_markers=(UncertaintyMarker(subject="Amount", reason="clearly legible"),),
        risky_fields=("Amount",),
    )
    parts = SubEngineOutputs(
        cleaner=a_cleaner_output(), reader=reader, parser=parser, confidence=confidence
    )
    identity = an_identity()

    result = assemble(parts=parts, identity=identity, source_references=("upload:invoice-900.pdf",))

    # traceable to reader
    assert result.structured_document.extracted_text == reader.raw_extracted_text
    # traceable to parser
    assert result.structured_document.detected_fields == (field,)
    assert result.structured_document.document_structure == parser.document_structure
    assert result.structured_document.detected_tables == parser.detected_tables
    # traceable to confidence
    assert result.confidence_report.confidence_scores == confidence.confidence_scores
    assert result.confidence_report.uncertainty_markers == confidence.uncertainty_markers
    assert result.confidence_report.reliability_information == confidence.reliability_information
    assert result.confidence_report.risky_fields == confidence.risky_fields
    # passed straight through, unread
    assert result.identity == identity
    assert result.source_references == ("upload:invoice-900.pdf",)
    assert result.human_business_context is None
    # the Document ID is assigned, by assembly, at intake
    assert isinstance(result.document_id, DocumentId)


# ── one part missing → fails loudly, names it, preserves the rest ─────────


def test_a_missing_cleaner_output_fails_loudly_and_preserves_the_rest() -> None:
    reader, parser, confidence = a_reader_output(), a_parser_output(), a_confidence_output()
    parts = SubEngineOutputs(cleaner=None, reader=reader, parser=parser, confidence=confidence)

    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert raised.value.missing_part == "cleaner"
    assert "cleaner" in str(raised.value)
    assert raised.value.parts.cleaner is None
    assert raised.value.parts.reader is reader
    assert raised.value.parts.parser is parser
    assert raised.value.parts.confidence is confidence


def test_a_missing_reader_output_fails_loudly_and_preserves_the_rest() -> None:
    cleaner, parser, confidence = a_cleaner_output(), a_parser_output(), a_confidence_output()
    parts = SubEngineOutputs(cleaner=cleaner, reader=None, parser=parser, confidence=confidence)

    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert raised.value.missing_part == "reader"
    assert "reader" in str(raised.value)
    assert raised.value.parts.cleaner is cleaner
    assert raised.value.parts.reader is None
    assert raised.value.parts.parser is parser
    assert raised.value.parts.confidence is confidence


def test_a_missing_parser_output_fails_loudly_and_preserves_the_rest() -> None:
    cleaner, reader, confidence = a_cleaner_output(), a_reader_output(), a_confidence_output()
    parts = SubEngineOutputs(cleaner=cleaner, reader=reader, parser=None, confidence=confidence)

    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert raised.value.missing_part == "parser"
    assert "parser" in str(raised.value)
    assert raised.value.parts.cleaner is cleaner
    assert raised.value.parts.reader is reader
    assert raised.value.parts.parser is None
    assert raised.value.parts.confidence is confidence


def test_a_missing_confidence_output_fails_loudly_and_preserves_the_rest() -> None:
    cleaner, reader, parser = a_cleaner_output(), a_reader_output(), a_parser_output()
    parts = SubEngineOutputs(cleaner=cleaner, reader=reader, parser=parser, confidence=None)

    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert raised.value.missing_part == "confidence"
    assert "confidence" in str(raised.value)
    assert raised.value.parts.cleaner is cleaner
    assert raised.value.parts.reader is reader
    assert raised.value.parts.parser is parser
    assert raised.value.parts.confidence is None


@pytest.mark.parametrize(
    ("missing", "parts"),
    [
        (
            "cleaner",
            SubEngineOutputs(
                cleaner=None,
                reader=a_reader_output(),
                parser=a_parser_output(),
                confidence=a_confidence_output(),
            ),
        ),
        (
            "reader",
            SubEngineOutputs(
                cleaner=a_cleaner_output(),
                reader=None,
                parser=a_parser_output(),
                confidence=a_confidence_output(),
            ),
        ),
        (
            "parser",
            SubEngineOutputs(
                cleaner=a_cleaner_output(),
                reader=a_reader_output(),
                parser=None,
                confidence=a_confidence_output(),
            ),
        ),
        (
            "confidence",
            SubEngineOutputs(
                cleaner=a_cleaner_output(),
                reader=a_reader_output(),
                parser=a_parser_output(),
                confidence=None,
            ),
        ),
    ],
)
def test_the_refusal_states_every_promise_it_makes_word_for_word(
    missing: str, parts: SubEngineOutputs
) -> None:
    """The message is a CONTRACT, not decoration, so it is pinned whole.

    `MissingSubEngineOutputError`'s own docstring makes three promises and the
    message is where a caller reads all three: WHICH sub-engine produced
    nothing, that the other parts are still reachable on `parts`, and that
    nothing was discarded or invented to stand in for the missing one
    (`ENGINE_1_INPUT_ENGINE_RULES.md:337`, the invention prohibition).

    Asserting only `missing in str(exc)` reads one of those three and leaves
    the other two unread — measured, not supposed: at `d7a8ed9` six mutants
    rewrote the two unread clauses and every existing test stayed green
    (`xǁMissingSubEngineOutputErrorǁ__init____mutmut_4` … `_9`). A promise no
    test reads is a promise the code is free to stop keeping.
    """
    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert str(raised.value) == (
        f"Engine 1 assembly cannot build a Document Evidence Object: the "
        f"{missing!r} sub-engine produced no output. The other parts "
        "supplied are preserved on this exception's `parts` attribute; "
        "none of them was discarded and nothing was invented to stand in "
        "for the missing one."
    )


def test_multiple_missing_parts_report_only_the_first_in_fixed_order() -> None:
    # cleaner is checked before reader, parser and confidence (assemble()'s
    # own docstring states the order). Both cleaner and reader are absent
    # here; only cleaner is named, because assembly stops at the first
    # defect rather than continuing on broken input (CLAUDE.md Law 11).
    parts = SubEngineOutputs(
        cleaner=None, reader=None, parser=a_parser_output(), confidence=a_confidence_output()
    )
    with pytest.raises(MissingSubEngineOutputError) as raised:
        assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))
    assert raised.value.missing_part == "cleaner"


# ── confidence cannot be raised by assembly ────────────────────────────────


def test_a_low_confidence_score_survives_assembly_unchanged() -> None:
    field = a_detected_field(name="Amount", confidence=LOW)
    parts = complete_parts(
        detected_fields=(field,),
        confidence_scores=(FieldConfidence(field_name="Amount", confidence=LOW),),
    )

    result = assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert result.structured_document.detected_fields[0].provenance.confidence == LOW
    assert result.confidence_report.confidence_scores[0].confidence == LOW


# ── an unknown survives assembly ────────────────────────────────────────────


def test_an_unreadable_field_survives_assembly_as_unknown_not_dropped() -> None:
    unreadable = a_detected_field(name="Date", value=None, confidence=LOW)
    parts = complete_parts(
        detected_fields=(unreadable,),
        confidence_scores=(FieldConfidence(field_name="Date", confidence=LOW),),
    )

    result = assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert len(result.structured_document.detected_fields) == 1
    assert result.structured_document.detected_fields[0].name == "Date"
    assert result.structured_document.detected_fields[0].value is None


# ── two disagreeing inputs are both preserved ──────────────────────────────


def test_two_disagreeing_uncertainty_markers_about_the_same_subject_are_both_preserved() -> None:
    reading_one = UncertaintyMarker(
        subject="Date", reason="reads as 12/03/2026 under one interpretation"
    )
    reading_two = UncertaintyMarker(
        subject="Date", reason="reads as 03/12/2026 under the other interpretation"
    )
    parts = complete_parts(uncertainty_markers=(reading_one, reading_two))

    result = assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    assert result.confidence_report.uncertainty_markers == (reading_one, reading_two)
    assert len(result.confidence_report.uncertainty_markers) == BOTH_DISAGREEING_READINGS


# ── cleaner's and reader's raw signal content never leaks into the artifact ─


def test_cleaner_and_reader_raw_signal_content_never_enters_the_artifact() -> None:
    # Cleaner's quality issues/preservation status and reader's source
    # locations/extraction-confidence signal have no destination field in
    # `DocumentEvidenceObject` (SUB_ENGINE_RESPONSIBILITIES.md §8.4 —
    # `confidence` already receives and synthesises them). Two calls
    # differing ONLY in that raw content, with `raw_extracted_text` held
    # identical, must produce identical artifacts (aside from the freshly
    # minted Document ID) — proving assembly never leaks that content in.
    fixed_text = "ACME TRADERS\nInvoice 900\nAmount 4500.00"
    identity = an_identity()
    parts_one = SubEngineOutputs(
        cleaner=a_cleaner_output(
            quality_issues_detected=("noise_sigma=0.4",), preservation_status="A"
        ),
        reader=a_reader_output(
            raw_extracted_text=fixed_text, source_locations=("p1",), extraction_confidence=("x",)
        ),
        parser=a_parser_output(),
        confidence=a_confidence_output(),
    )
    parts_two = SubEngineOutputs(
        cleaner=a_cleaner_output(
            quality_issues_detected=("noise_sigma=9.9", "blurred"), preservation_status="B"
        ),
        reader=a_reader_output(
            raw_extracted_text=fixed_text,
            source_locations=("p1", "p2"),
            extraction_confidence=("y", "z"),
        ),
        parser=a_parser_output(),
        confidence=a_confidence_output(),
    )

    result_one = assemble(parts=parts_one, identity=identity, source_references=("upload:x.pdf",))
    result_two = assemble(parts=parts_two, identity=identity, source_references=("upload:x.pdf",))

    assert result_one.structured_document == result_two.structured_document
    assert result_one.confidence_report == result_two.confidence_report
    assert result_one.source_references == result_two.source_references
    assert result_one.identity == result_two.identity


# ── determinism, versioning, and the Document ID ────────────────────────────


def test_the_same_sub_engine_outputs_assembled_twice_are_identical_content_with_different_ids() -> (
    None
):
    field = a_detected_field()
    scores = (FieldConfidence(field_name="Amount", confidence=HIGH),)
    parts_one = complete_parts(detected_fields=(field,), confidence_scores=scores)
    parts_two = complete_parts(detected_fields=(field,), confidence_scores=scores)
    identity = an_identity()

    result_one = assemble(parts=parts_one, identity=identity, source_references=("upload:x.pdf",))
    result_two = assemble(parts=parts_two, identity=identity, source_references=("upload:x.pdf",))

    # deterministic content ...
    assert result_one.structured_document == result_two.structured_document
    assert result_one.confidence_report == result_two.confidence_report
    assert result_one.source_references == result_two.source_references
    assert result_one.identity == result_two.identity
    # ... but each assembly mints its own Document ID, and changing only the
    # ID changes nothing else about the object.
    assert result_one.document_id != result_two.document_id


def test_changing_only_the_document_id_changes_nothing_else_about_the_object() -> None:
    parts = complete_parts()
    result = assemble(parts=parts, identity=an_identity(), source_references=("upload:x.pdf",))

    recast = result.model_copy(update={"document_id": DocumentId.new()})

    assert recast.document_id != result.document_id
    assert recast.structured_document == result.structured_document
    assert recast.confidence_report == result.confidence_report
    assert recast.source_references == result.source_references
    assert recast.human_business_context == result.human_business_context
    assert recast.identity == result.identity


def test_a_second_assembly_with_a_bumped_version_is_a_new_object_the_first_is_unchanged() -> None:
    # INV-5: correction is a new version, never an edit. A "second assembly"
    # is simply the caller supplying a new `identity` — assembly performs no
    # version bookkeeping of its own.
    parts = complete_parts()
    first_identity = an_identity(version=1)
    first = assemble(parts=parts, identity=first_identity, source_references=("upload:x.pdf",))

    second_identity = an_identity(
        version=2,
        parent_versions=(ParentVersion(artifact_id=first_identity.artifact_id, version=1),),
    )
    second = assemble(parts=parts, identity=second_identity, source_references=("upload:x.pdf",))

    assert first.identity.version == 1
    assert second.identity.version == CORRECTED_VERSION
    assert second.identity.parent_versions[0].artifact_id == first_identity.artifact_id
    assert first.document_id != second.document_id
    # the first artifact is untouched by the second assembly
    assert first.identity.version == 1


# ── pass-through of the engine-level intake facts ──────────────────────────


def test_human_business_context_passes_through_untouched_when_supplied() -> None:
    note = HumanBusinessContext(
        original_user_text="Advance paid to supplier.",
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-42",
            evidence_reference="message 3",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )
    parts = complete_parts()

    result = assemble(
        parts=parts,
        identity=an_identity(),
        source_references=("upload:x.pdf",),
        human_business_context=note,
    )

    assert result.human_business_context is note


def test_source_references_pass_through_unread() -> None:
    parts = complete_parts()
    refs = ("upload:invoice-900.pdf", "email:thread-77")

    result = assemble(parts=parts, identity=an_identity(), source_references=refs)

    assert result.source_references == refs


# ── assembly does not duplicate the artifact's own validation ─────────────


def test_an_empty_source_reference_tuple_is_refused_by_the_artifacts_own_schema() -> None:
    # Assembly does not re-implement DocumentEvidenceObject's own validation
    # (Law 19, one source of truth); the refusal comes from the schema, not
    # from a second check duplicated here.
    parts = complete_parts()
    with pytest.raises(ValidationError):
        assemble(parts=parts, identity=an_identity(), source_references=())
