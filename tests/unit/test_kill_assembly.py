"""`assembly` mutation killer — tests designed to die if specific source lines flip.

Every test below is written to catch a specific class of mutation:
  1. None check flip (`is None` → `is not None`)
  2. Field assignment swap (using wrong sub-engine output)
  3. Skipped field in artifact construction
  4. Object identity vs equality (pass-through without rebuild)

Each test is falsified against the source mutation before being accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from accountant_dad.artifacts.evidence import (
    Corroborated,
    DetectedField,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine.assembly import (
    CleanerOutput,
    ConfidenceOutput,
    ParserOutput,
    ReaderOutput,
    SubEngineOutputs,
    assemble,
)
from accountant_dad.identity import (
    ArtifactId,
    IdentityEnvelope,
    TransactionId,
)

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
HIGH = Decimal("0.9800")


# ── the cleaner present, none check not flipped ──────────────────────────────


def test_cleaner_present_accepts_all_four_parts() -> None:
    """If the None check for cleaner flipped to `is not None`, this fails.
    A present cleaner must not raise; the test passes only when cleaner is
    successfully unpacked and used to construct the artifact.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text="ACME TRADERS\nAmount 4500.00",
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure="header/body",
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    # The artifact was created, proving cleaner was accepted, not rejected.
    assert result is not None


# ── reader's text field used for structured_document.extracted_text ────────


def test_structured_document_extracted_text_comes_from_reader_not_parser() -> None:
    """If parser.document_structure got assigned to extracted_text, this detects it.
    extracted_text must be reader's raw_extracted_text.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    reader_text = "INVOICE FROM ACME\nTotal: 5000.00"
    parser_structure = "header / items / footer"

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text=reader_text,
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure=parser_structure,
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    assert result.structured_document.extracted_text == reader_text
    assert result.structured_document.extracted_text != parser_structure


# ── parser's document_structure field assigned and not skipped ──────────────


def test_document_structure_is_assigned_from_parser_not_defaulted() -> None:
    """If document_structure was omitted from StructuredDocument construction,
    it would get its schema default (empty string). A real value must pass through.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    unique_structure = "UNIQUE_STRUCTURE_f0a2b1d8"

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text="ACME TRADERS\nAmount 4500.00",
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure=unique_structure,
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    assert result.structured_document.document_structure == unique_structure


# ── confidence_scores assigned from confidence, not defaulted ───────────────


def test_confidence_scores_assigned_from_confidence_output() -> None:
    """If confidence_scores was omitted, the report would carry an empty tuple.
    A real score must reach the artifact.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text="ACME TRADERS\nAmount 4500.00",
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure="header/body",
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    assert len(result.confidence_report.confidence_scores) == 1
    assert result.confidence_report.confidence_scores[0].field_name == "Amount"


# ── identity passed through as same object ────────────────────────────────


def test_identity_envelope_is_passed_through_as_same_object() -> None:
    """If identity was rebuilt instead of passed through, it would be == but
    not is the original. Assembly must not rebuild; it must hand through the
    exact object.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text="ACME TRADERS\nAmount 4500.00",
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure="header/body",
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    assert result.identity is identity


# ── human_business_context passed through as same object when supplied ─────


def test_human_business_context_is_same_object_when_supplied() -> None:
    """If the human note was rebuilt, it would == but not is. Assembly must
    pass the exact object through.
    """
    provenance = Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="invoice-900.pdf",
        evidence_reference="page 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    field = DetectedField(name="Amount", value="4500.00", provenance=provenance)
    score = FieldConfidence(field_name="Amount", confidence=HIGH)

    human_provenance = Provenance(
        source_type=SourceType.HUMAN,
        source_id="chat:1",
        evidence_reference="message 1",
        timestamp=WHEN,
        confidence=HIGH,
        corroborated=Corroborated.NOT_ASSESSED,
    )
    note = HumanBusinessContext(original_user_text="Advance paid.", provenance=human_provenance)

    parts = SubEngineOutputs(
        cleaner=CleanerOutput(
            cleaned_document_representation=object(),
            quality_issues_detected=("noise=2.1",),
            preservation_status="safe",
        ),
        reader=ReaderOutput(
            raw_extracted_text="ACME TRADERS\nAmount 4500.00",
            source_locations=("page 1",),
            extraction_confidence=("0.98",),
        ),
        parser=ParserOutput(
            document_structure="header/body",
            detected_fields=(field,),
            detected_tables=(),
        ),
        confidence=ConfidenceOutput(
            confidence_scores=(score,),
            uncertainty_markers=(),
            reliability_information="legible",
            risky_fields=(),
        ),
    )

    identity = IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )

    result = assemble(
        parts=parts,
        identity=identity,
        source_references=("upload:x.pdf",),
        human_business_context=note,
    )

    assert result.human_business_context is note
