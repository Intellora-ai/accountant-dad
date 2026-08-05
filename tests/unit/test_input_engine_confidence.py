"""`confidence_report` — attacked rather than confirmed.

CONFIDENCE_SPECIFICATION.md §2: *"Each line below is written so it can become
a test."* This file is that conversion for the `confidence` sub-engine: for
every prohibition the module is bound by, there is a test here that tries to
OBSERVE the violation rather than take the docstring's word for it.

WHAT WOULD PROVE THIS MODULE WRONG, AND WHY EACH TEST IS SHAPED THE WAY IT IS.
    A document-level scalar (§4) can arrive two ways: a function that returns
    one, or a schema field that carries one. Both are checked STRUCTURALLY —
    by inspecting the module's own functions and the frozen `ConfidenceReport`
    schema with `inspect`, rather than by reading the source and trusting it —
    so a scalar added later under an innocuous name still turns the test red.

    A hardcoded threshold (`ENGINE_1_CONFIDENCE_PARAMETERS.md`: *"No numeric
    literal used as a threshold ... No comparison against a constant that is
    not loaded from configuration"*) is checked by walking the module's own
    AST for ANY numeric comparison at all, not by grepping for suspicious
    numbers — a differently-spelled cutoff would evade a grep and cannot
    evade a parse of every `Compare` node in the file.

    Everything else is exercised through the real, frozen dependency this
    module was built against — `ConfidenceReport`, `FieldConfidence`,
    `UncertaintyMarker` and `DocumentEvidenceObject` from
    `accountant_dad.artifacts.evidence` — never a stand-in. A test that mocks
    everything the module under test touches proves the mock, not the module
    (`CLAUDE.md` §J.6).
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DocumentEvidenceObject,
    DocumentId,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.confidence import MAX, MIN, Confidence
from accountant_dad.engines.input_engine import confidence_report as confidence_report_module
from accountant_dad.engines.input_engine.cleaner import CleanedDocument, PreservationStatus
from accountant_dad.engines.input_engine.confidence_report import (
    CAPTURE_FIDELITY_FIELD_NAME,
    CAPTURE_FIDELITY_ON_EXACT_MATCH,
    HumanCaptureEvidence,
    MalformedSignalError,
    MissingField,
    ParsedField,
    RegionReading,
    capture_fidelity,
    record_confidence,
)
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope, TransactionId

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

HIGH = Decimal("0.9800")
LOW = Decimal("0.0100")


# ── builders ─────────────────────────────────────────────────────────────────
# Deliberately explicit, matching test_evidence.py's convention. Nothing under
# test is defaulted away: every builder takes the value the test cares about
# as an argument and supplies the rest with an unremarkable default.


def a_cleaned_document(
    *, preservation_status: PreservationStatus = PreservationStatus.CLEANED_IS_SAFER
) -> CleanedDocument:
    frame = np.zeros((2, 2), dtype=np.uint8)
    return CleanedDocument(
        original=frame,
        cleaned=frame,
        quality_observations=(),
        preservation_status=preservation_status,
    )


def a_provenance(
    *, source_type: SourceType = SourceType.DOCUMENT, confidence: Decimal = HIGH
) -> Provenance:
    return Provenance(
        source_type=source_type,
        source_id="invoice-481.pdf",
        evidence_reference="page 1, box at (240, 118)",
        timestamp=WHEN,
        confidence=confidence,
        corroborated=Corroborated.NOT_ASSESSED,
    )


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_human_business_context(
    *, original_user_text: str = "Paid rent for June in cash."
) -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=original_user_text,
        # The confidence carried here is unrelated to capture_fidelity's own
        # computation, which is a string-equality check and never reads it —
        # see the module docstring, CAPTURE FIDELITY IS SCORED ONLY WHERE IT
        # IS ACTUALLY DEFINED.
        provenance=a_provenance(source_type=SourceType.HUMAN, confidence=HIGH),
    )


# ── §4 · there is no document-level confidence scalar ─────────────────────────
# CONFIDENCE_SPECIFICATION.md §4: "There is NO document-level confidence
# scalar. None." Checked two ways: no function in this module may RETURN a
# bare confidence, and the artifact it assembles may not CARRY one.


def test_no_function_in_the_module_returns_a_bare_document_level_confidence() -> None:
    """`from __future__ import annotations` keeps annotations as the strings
    they were written as, so `inspect.signature(...).return_annotation`
    reads exactly what a future author typed — including a new function
    written `def document_confidence(...) -> Confidence:`. That function
    would turn this red the moment it exists, before anyone calls it.
    """
    forbidden_bare_returns = {"Confidence", "Decimal"}
    offenders = [
        (name, inspect.signature(function).return_annotation)
        for name, function in inspect.getmembers(confidence_report_module, inspect.isfunction)
        if function.__module__ == confidence_report_module.__name__
        and inspect.signature(function).return_annotation in forbidden_bare_returns
    ]
    assert offenders == [], (
        f"function(s) returning a bare confidence value: {offenders}. A single "
        "value combined from more than one field, region or instrument is "
        "exactly the document-level scalar CONFIDENCE_SPECIFICATION.md §4 "
        "forbids — Marichal & Mesiar Corollary 5.7, cited there, rules out "
        "every aggregation that is not an order statistic on ONE scale."
    )


def test_the_confidence_report_schema_carries_no_document_level_score_field() -> None:
    """The artifact this module assembles, inspected the same structural way:
    by field annotation, not by name. A field renamed from something obvious
    to something bland still shows up here if its type is a bare confidence.
    """
    offenders = [
        name
        for name, info in ConfidenceReport.model_fields.items()
        if info.annotation in (Confidence, Decimal)
    ]
    assert offenders == [], (
        f"ConfidenceReport field(s) typed as a single confidence value: "
        f"{offenders}. `confidence_scores`, `uncertainty_markers` and "
        "`risky_fields` are all tuples for exactly this reason."
    )


# ── no hardcoded threshold ─────────────────────────────────────────────────────
# ENGINE_1_CONFIDENCE_PARAMETERS.md: "No numeric literal used as a threshold
# anywhere in engines/input_engine/ ... No comparison against a constant that
# is not loaded from configuration ... A mutation that inserts a default must
# turn [this] red."


def _is_a_hardcoded_confidence_operand(node: ast.AST) -> bool:
    """True for anything that could supply an invented cutoff to a `Compare`.

    Not just a bare numeric literal (`0.5`): `Confidence` values in this
    codebase are always written `Decimal("0.5000")` — a `Call`, not a
    `Constant` — because `confidence.py` refuses the `float` a bare literal
    would produce. A check for `ast.Constant` alone was tried first and MISSED
    exactly that shape; red-teaming this test (injecting
    `extraction_confidence < Decimal("0.5")` into a throwaway copy of the
    module) proved the miss before this function existed. `MIN` and `MAX` are
    included too: they are the scale's own identity elements, not thresholds,
    but ENGINE_1_CONFIDENCE_PARAMETERS.md's rule is "no comparison against a
    constant that is not loaded from configuration" — MIN and MAX are exactly
    that, and this module has no legitimate need to compare against either.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return not isinstance(node.value, bool)
    if isinstance(node, ast.Name) and node.id in {"Decimal", "MIN", "MAX"}:
        return True
    return isinstance(node, ast.Attribute) and node.attr in {"Decimal", "MIN", "MAX"}


def test_no_numeric_comparison_appears_anywhere_in_the_module() -> None:
    """This module has no configuration (module docstring, NO CONFIGURATION
    IS DEFINED HERE), so it must never compare anything against a number at
    all — every real branch is `is None`, string equality or an enum
    identity check. Counting occurrences (`sum(1 for ... )`) is fine and
    stays green; a mutation such as
    `if x.extraction_confidence < Decimal("0.5"):` is a `Compare` node
    carrying a hardcoded operand and turns this red the moment it is written
    — walking the WHOLE comparison subtree, not just its immediate operands,
    is what catches the constant nested inside the `Decimal(...)` call.
    """
    source = inspect.getsource(confidence_report_module)
    tree = ast.parse(source)
    offending_lines = sorted(
        {
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Compare)
            for descendant in ast.walk(node)
            if _is_a_hardcoded_confidence_operand(descendant)
        }
    )
    assert offending_lines == [], (
        f"numeric comparison(s) found at line(s) {offending_lines} of "
        "confidence_report.py. A recorder that gates nothing needs no cutoffs."
    )


# ── §2.3 · confidence never conceals; every marker carries a reason ───────────


def test_an_uncertainty_marker_with_no_reason_is_refused() -> None:
    """P14: 'Every uncertainty marker carries a reason.' Exercised against the
    REAL dependency this module imports and relies on — `evidence.py`'s
    `NonEmptyText` validator — not a re-implementation of the same rule here.
    """
    with pytest.raises(ValidationError):
        UncertaintyMarker(subject="Amount", reason="")


def test_an_uncertainty_marker_with_a_whitespace_only_reason_is_refused() -> None:
    """A padded blank is a blank (`evidence.py`'s `_meaningful_text`) —
    stripping happens before the emptiness check, so three spaces is refused
    exactly as `""` is, not accepted because it is technically non-empty.
    """
    with pytest.raises(ValidationError):
        UncertaintyMarker(subject="Amount", reason="   ")


# ── confidence cannot be raised ────────────────────────────────────────────────
# §1.4 boundary: "Cannot increase confidence without evidence." INV-2:
# "Confidence changes only when evidence changes." record_confidence must
# mirror reader's own reading, never adjust it.


def test_a_low_confidence_score_survives_record_confidence_unchanged() -> None:
    field = ParsedField(field_name="GSTIN", extraction_confidence=LOW)
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(field,),
        missing_fields=(),
    )
    assert len(report.confidence_scores) == 1
    assert report.confidence_scores[0].field_name == "GSTIN"
    assert report.confidence_scores[0].confidence == LOW


def test_the_scales_minimum_confidence_survives_unchanged() -> None:
    field = ParsedField(field_name="Total", extraction_confidence=MIN)
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(field,),
        missing_fields=(),
    )
    assert report.confidence_scores[0].confidence == MIN


def test_the_scales_maximum_confidence_survives_unchanged() -> None:
    field = ParsedField(field_name="Total", extraction_confidence=MAX)
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(field,),
        missing_fields=(),
    )
    assert report.confidence_scores[0].confidence == MAX


# ── tri-state distinguishability: absent, zero, unreadable ───────────────────
# ENGINE_1_INPUT_ENGINE_RULES.md:569 — "absent", "zero" and "unreadable" must
# remain three distinguishable states. This module never sees a field's
# VALUE (its boundary forbids reading one), so "zero" is represented exactly
# like any other successfully-read field: a score, and no marker at all.


def test_absent_zero_and_unreadable_produce_three_distinguishable_outcomes() -> None:
    # "zero": parser DID read a value (here, the "0" the document stated) and
    # reader attached a confidence to it — an ordinary ParsedField.
    zero_field = ParsedField(field_name="Discount Amount", extraction_confidence=HIGH)
    # "absent": parser's structure calls for the field and it is not there.
    absent_field = MissingField(field_name="PO Number", state="absent")
    # "unreadable": reader attempted a region and could not read it at all.
    unreadable_region = RegionReading(
        source_location="page 1, footer strip", text=None, extraction_confidence=None
    )

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(unreadable_region,),
        parsed_fields=(zero_field,),
        missing_fields=(absent_field,),
    )

    # "zero" reached confidence_scores and raised no uncertainty about itself.
    scored_names = {score.field_name for score in report.confidence_scores}
    assert scored_names == {"Discount Amount"}
    marker_subjects = {marker.subject for marker in report.uncertainty_markers}
    assert "Discount Amount" not in marker_subjects

    # "absent" and "unreadable" both produced markers, keyed differently and
    # worded differently — never collapsed into one shared state.
    assert marker_subjects == {"PO Number", "page 1, footer strip"}
    by_subject = {marker.subject: marker.reason for marker in report.uncertainty_markers}
    assert "absent" in by_subject["PO Number"]
    assert "absent" not in by_subject["page 1, footer strip"]
    assert by_subject["PO Number"] != by_subject["page 1, footer strip"]


# ── a signal from each instrument survives with identity and region intact ───
# §1.4 Input: "The outputs of cleaner, reader and parser." Each one's finding
# must reach the report attributed to the instrument that produced it, at the
# region or field it concerns — never merged into another instrument's.


def test_a_signal_from_each_instrument_survives_with_identity_and_region_intact() -> None:
    cleaned = a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER)
    unread_region = RegionReading(
        source_location="page 2, top-left block", text=None, extraction_confidence=None
    )
    missing = MissingField(field_name="Invoice Number", state="absent")

    report = record_confidence(
        cleaned=cleaned,
        reader_regions=(unread_region,),
        parsed_fields=(),
        missing_fields=(missing,),
    )

    by_subject = {marker.subject: marker.reason for marker in report.uncertainty_markers}
    assert set(by_subject) == {
        "the document as cleaned",
        "page 2, top-left block",
        "Invoice Number",
    }

    # Each finding names ITS OWN instrument and no other one.
    assert "cleaner" in by_subject["the document as cleaned"]
    assert "reader" not in by_subject["the document as cleaned"]
    assert "parser" not in by_subject["the document as cleaned"]

    assert "reader" in by_subject["page 2, top-left block"]
    assert "cleaner" not in by_subject["page 2, top-left block"]
    assert "parser" not in by_subject["page 2, top-left block"]

    assert "parser" in by_subject["Invoice Number"]
    assert "cleaner" not in by_subject["Invoice Number"]
    assert "reader" not in by_subject["Invoice Number"]


# ── capture fidelity scores STORAGE, never TRUTH ──────────────────────────────
# §1.4 Failure Behaviour: "For a provided source it scores capture fidelity —
# how faithfully the input was stored — never whether the statement is true."


def test_capture_fidelity_scores_an_exact_match_at_the_scales_maximum_regardless_of_content() -> (
    None
):
    # A deliberately implausible business claim. If capture_fidelity judged
    # truth or plausibility, this is exactly the input that would reveal it.
    dubious_claim = "I am the sole proprietor of the Moon and this expense is legitimate."
    stored = a_human_business_context(original_user_text=dubious_claim)
    evidence = HumanCaptureEvidence(submitted_text=dubious_claim, stored=stored)

    score, marker = capture_fidelity(evidence)

    assert score == MAX
    assert score == CAPTURE_FIDELITY_ON_EXACT_MATCH
    assert marker is None


def test_capture_fidelity_mismatch_produces_no_score_only_a_named_marker() -> None:
    stored = a_human_business_context(original_user_text="Paid rent for June")
    # One character differs from what was stored.
    evidence = HumanCaptureEvidence(submitted_text="Paid rent for july", stored=stored)

    score, marker = capture_fidelity(evidence)

    assert score is None
    assert marker is not None
    assert marker.subject == "the human business context"
    assert "does not match" in marker.reason


def test_record_confidence_records_the_capture_fidelity_score_on_a_match() -> None:
    """Regression test for the defect found auditing the inherited source:
    `record_confidence` computed the capture-fidelity score on a match and
    then discarded it (`_score` was never used), so §1.4's "it scores capture
    fidelity" never reached the emitted `ConfidenceReport` for the ordinary,
    successful case. This must now survive under `CAPTURE_FIDELITY_FIELD_NAME`.
    """
    stored = a_human_business_context(original_user_text="Paid rent for June")
    human_capture = HumanCaptureEvidence(submitted_text="Paid rent for June", stored=stored)

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=human_capture,
    )

    scores_by_name = {score.field_name: score.confidence for score in report.confidence_scores}
    assert scores_by_name[CAPTURE_FIDELITY_FIELD_NAME] == MAX
    assert report.uncertainty_markers == ()


def test_record_confidence_adds_no_score_on_a_capture_fidelity_mismatch() -> None:
    stored = a_human_business_context(original_user_text="Paid rent for June")
    human_capture = HumanCaptureEvidence(submitted_text="paid rent for june", stored=stored)

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=human_capture,
    )

    assert report.confidence_scores == ()
    assert len(report.uncertainty_markers) == 1
    assert report.uncertainty_markers[0].subject == "the human business context"


def test_record_confidence_without_a_human_capture_adds_no_capture_fidelity_score() -> None:
    """`human_capture` defaults to `None` — a document with no Human Business
    Description is ordinary, not an error (`ENGINE_1_INPUT_ENGINE_RULES.md:138`).
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
    )
    assert report.confidence_scores == ()
    assert report.uncertainty_markers == ()


# ── malformed signals are refused, never guessed into shape ──────────────────
# §1.4 Boundary: cannot re-read, re-parse or correct anything. A caller
# handing this module a self-contradictory signal is refused at construction,
# loudly, never silently repaired.


def test_region_reading_refuses_a_blank_source_location() -> None:
    with pytest.raises(MalformedSignalError):
        RegionReading(source_location="   ", text=None, extraction_confidence=None)


def test_region_reading_refuses_text_without_a_confidence() -> None:
    with pytest.raises(MalformedSignalError):
        RegionReading(source_location="page 1", text="Total", extraction_confidence=None)


def test_region_reading_refuses_a_confidence_without_text() -> None:
    with pytest.raises(MalformedSignalError):
        RegionReading(source_location="page 1", text=None, extraction_confidence=MAX)


def test_parsed_field_refuses_a_blank_name() -> None:
    with pytest.raises(MalformedSignalError):
        ParsedField(field_name="   ", extraction_confidence=MAX)


def test_missing_field_refuses_a_blank_name() -> None:
    with pytest.raises(MalformedSignalError):
        MissingField(field_name="", state="absent")


def test_missing_field_refuses_a_blank_state() -> None:
    with pytest.raises(MalformedSignalError):
        MissingField(field_name="GSTIN", state="   ")


# ── record_confidence never rejects a document or halts the pipeline ─────────
# §1.4 Boundary: "Cannot reject a document or halt the pipeline." Even the
# maximally uninformative input — nothing read, nothing parsed, nothing
# missing, no human context — still produces a valid, empty report.


def test_record_confidence_never_halts_on_a_maximally_uninformative_signal_set() -> None:
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
    )
    assert report.confidence_scores == ()
    assert report.uncertainty_markers == ()
    assert report.risky_fields == ()
    assert report.reliability_information != ""


# ── risky_fields stays empty, always ──────────────────────────────────────────
# ENGINE_1_CONFIDENCE_PARAMETERS.md gap #4: "what makes a field risky" is
# undefined, not merely unset. This module invents no threshold-based answer,
# so `risky_fields` must stay `()` even under the worst combination of
# signals this module can be handed.


def test_risky_fields_stays_empty_even_when_every_signal_is_bad() -> None:
    report = record_confidence(
        cleaned=a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER),
        reader_regions=(
            RegionReading(source_location="page 1, totals", text=None, extraction_confidence=None),
        ),
        parsed_fields=(ParsedField(field_name="Total", extraction_confidence=MIN),),
        missing_fields=(MissingField(field_name="GSTIN", state="absent"),),
    )
    assert report.risky_fields == ()


# ── name collisions are refused, never silently resolved ──────────────────────
# `ConfidenceReport._each_name_is_scored_once` (INV-10) is the structural
# guard `record_confidence`'s own docstring says it relies on rather than
# repeats. Exercised for real, twice: an ordinary duplicate, and the specific
# collision this file's own CAPTURE_FIDELITY_FIELD_NAME could create.


def test_two_parsed_fields_sharing_one_name_are_refused_not_silently_resolved() -> None:
    duplicate_a = ParsedField(field_name="Total", extraction_confidence=HIGH)
    duplicate_b = ParsedField(field_name="Total", extraction_confidence=LOW)
    with pytest.raises(ValidationError):
        record_confidence(
            cleaned=a_cleaned_document(),
            reader_regions=(),
            parsed_fields=(duplicate_a, duplicate_b),
            missing_fields=(),
        )


def test_a_parsed_field_colliding_with_the_capture_fidelity_name_is_refused_not_merged() -> None:
    colliding_field = ParsedField(field_name=CAPTURE_FIDELITY_FIELD_NAME, extraction_confidence=LOW)
    stored = a_human_business_context(original_user_text="Paid rent")
    human_capture = HumanCaptureEvidence(submitted_text="Paid rent", stored=stored)
    with pytest.raises(ValidationError):
        record_confidence(
            cleaned=a_cleaned_document(),
            reader_regions=(),
            parsed_fields=(colliding_field,),
            missing_fields=(),
            human_capture=human_capture,
        )


# ── real interoperability with the frozen artifact ────────────────────────────
# REAL + ISOLATED (CLAUDE.md §J.6): the exact production dependency, not a
# mock. `record_confidence`'s output must actually assemble into a real
# DocumentEvidenceObject, and P5 (no component may raise or lower a score
# `confidence` produced) must actually be enforced by that assembly, not
# merely asserted in a docstring.


def test_record_confidence_output_assembles_into_a_real_document_evidence_object() -> None:
    confidence_value = Decimal("0.9500")
    detected_field = DetectedField(
        name="Invoice Number",
        value="INV-001",
        provenance=a_provenance(confidence=confidence_value),
    )
    structured_document = StructuredDocument(
        extracted_text="Invoice Number: INV-001",
        detected_fields=(detected_field,),
        document_structure="single page, one field",
        detected_tables=(),
    )
    parsed_field = ParsedField(field_name="Invoice Number", extraction_confidence=confidence_value)
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(parsed_field,),
        missing_fields=(),
    )

    document = DocumentEvidenceObject(
        identity=an_identity(),
        document_id=DocumentId.new(),
        source_references=("scan-001.pdf",),
        structured_document=structured_document,
        confidence_report=report,
    )

    assert document.confidence_report.confidence_scores[0].confidence == confidence_value


def test_document_evidence_object_refuses_a_confidence_report_that_disagrees_with_provenance() -> (
    None
):
    """P5: no component — parent Input Engine included — may raise or lower a
    score `confidence` produced. Attacked directly: feed `record_confidence`
    a DIFFERENT value than the field's own provenance carries, and confirm
    the frozen artifact refuses to reconcile the disagreement rather than
    silently picking one side.
    """
    detected_field = DetectedField(
        name="Invoice Number",
        value="INV-001",
        provenance=a_provenance(confidence=Decimal("0.9500")),
    )
    structured_document = StructuredDocument(
        extracted_text="Invoice Number: INV-001",
        detected_fields=(detected_field,),
        document_structure="single page, one field",
        detected_tables=(),
    )
    # A DIFFERENT confidence than the field's own provenance.
    parsed_field = ParsedField(field_name="Invoice Number", extraction_confidence=Decimal("0.1000"))
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(parsed_field,),
        missing_fields=(),
    )

    with pytest.raises(ValidationError):
        DocumentEvidenceObject(
            identity=an_identity(),
            document_id=DocumentId.new(),
            source_references=("scan-001.pdf",),
            structured_document=structured_document,
            confidence_report=report,
        )
