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
    ReadingState,
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
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is mutmut's instrumentation rather than ours. Asserting on it "
            "measures the mutation tool, not the code under test — and a structural "
            "assertion about OUR source cannot be evaluated against a file we did "
            "not write. Skipped under mutation only; it runs in every ordinary suite."
        )
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


# ── a region can be READ and still carry no score (F-013) ────────────────────
# `reader.read_pdf_text_layer` sets `extraction_confidence=None` on EVERY region
# it produces (`reader.py:293-294`), because no recogniser ran to produce one —
# and `reader.py:255-259` says so outright: "`None` is NOT zero confidence and
# NOT full confidence - it is the absence of a measurement." A PDF text layer is
# the MVP's own primary input (`CLAUDE.md` §B.7), so refusing that shape refused
# every region the MVP actually reads. Three states exist; an invariant that
# admits two collapses one of them, which is the same defect
# `ENGINE_1_INPUT_ENGINE_RULES.md:569` and `measurement.py:41-59` already name.


def test_a_region_read_without_a_score_is_accepted_not_refused() -> None:
    """The exact shape `read_pdf_text_layer` emits, which used to raise."""
    reading = RegionReading(
        source_location="page 1, box at (72, 100)", text="TAX INVOICE", extraction_confidence=None
    )
    assert reading.text == "TAX INVOICE"
    assert reading.extraction_confidence is None
    assert reading.state is ReadingState.READ_BUT_UNSCORED


def test_the_three_reading_states_are_three_and_never_collapse_into_two() -> None:
    """Unread · read-and-scored · read-but-unscored. Distinguishable by a NAMED
    state, so no caller has to re-derive them from a bare `is None` — which is
    ambiguous now that `extraction_confidence is None` means two different
    things depending on `text`. This is `measurement.AbsentType`'s principle
    (`measurement.py:122-150`, the F-005 resolution) applied here.
    """
    unread = RegionReading(source_location="p1 footer", text=None, extraction_confidence=None)
    scored = RegionReading(source_location="p1 total", text="1180.00", extraction_confidence=HIGH)
    unscored = RegionReading(
        source_location="p1 head", text="TAX INVOICE", extraction_confidence=None
    )

    assert unread.state is ReadingState.UNREAD
    assert scored.state is ReadingState.READ_AND_SCORED
    assert unscored.state is ReadingState.READ_BUT_UNSCORED
    # Compared against the enum itself, never against the literal 3: this stays
    # true only while every member is REACHABLE and the three are DISTINCT, so
    # adding a fourth state without a reading that produces it turns it red.
    assert {unread.state, scored.state, unscored.state} == set(ReadingState)


def test_a_zero_confidence_reading_is_scored_not_unscored() -> None:
    """ABSENT is not ZERO — the exact collapse F-005 resolved, one level down.

    `Confidence`'s `MIN` is `Decimal("0")`, which is FALSY. A `state` written
    `if not self.extraction_confidence` instead of `is None` would report a
    region the recogniser scored at rock bottom as one it never scored at all —
    losing the single most alarming signal in the report, silently, and in the
    direction that looks reassuring. That is why `measurement.AbsentType`
    refuses `__bool__` (`measurement.py:122-150`) and why
    `ENGINE_1_INPUT_ENGINE_RULES.md:569` keeps absent, zero and unreadable
    apart.
    """
    at_the_floor = RegionReading(
        source_location="p1 smudge", text="118O.OO", extraction_confidence=MIN
    )
    assert at_the_floor.extraction_confidence == MIN
    assert not at_the_floor.extraction_confidence  # falsy — the trap this guards
    assert at_the_floor.state is ReadingState.READ_AND_SCORED

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(at_the_floor,),
        parsed_fields=(),
        missing_fields=(),
    )
    # it is neither unread nor unscored, so it earns NO region marker and is
    # counted in neither tally — the score itself is the signal
    assert report.uncertainty_markers == ()
    assert report.reliability_information == (
        "0 field(s) carry a confidence score from parser; "
        "0 of 1 region(s) reader attempted could not be read at all; "
        "0 of them were read but carry no per-region extraction score; "
        "0 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading; "
        "human business context capture fidelity: not supplied."
    )


def test_a_region_read_as_empty_text_is_read_not_unread() -> None:
    """EMPTY is not ABSENT, the same collapse on the other field.

    `""` is falsy exactly as `None` is. A region `reader` read and found to
    contain nothing is a DIFFERENT fact from a region `reader` could not read,
    and reporting the first as the second would claim an instrument failure
    that did not happen.
    """
    empty = RegionReading(source_location="p1 blank box", text="", extraction_confidence=None)
    assert empty.text == ""
    assert not empty.text  # falsy — the trap this guards
    assert empty.state is ReadingState.READ_BUT_UNSCORED

    # and the same falsiness trap on the REFUSAL: only `text is None` with a
    # score is incoherent. "I read this box, it is empty, and I am confident of
    # that" is a real recogniser output and an honest one — refusing it would
    # discard the signal rather than record it (§1.4, cannot hide uncertainty).
    confidently_empty = RegionReading(
        source_location="p1 blank box", text="", extraction_confidence=HIGH
    )
    assert confidently_empty.state is ReadingState.READ_AND_SCORED

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(empty,),
        parsed_fields=(),
        missing_fields=(),
    )
    assert [marker.subject for marker in report.uncertainty_markers] == ["p1 blank box"]
    assert "could not read this region at all" not in report.uncertainty_markers[0].reason
    assert "0 of 1 region(s) reader attempted could not be read at all" in (
        report.reliability_information
    )


def test_an_unscored_region_is_never_reported_as_one_reader_could_not_read() -> None:
    """The collapse that would matter most: an unscored region reported as
    unread is a lie about a region whose text WAS recovered. Their markers must
    be worded differently, and the unread COUNT must not include it.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
            RegionReading(
                source_location="p1 head", text="TAX INVOICE", extraction_confidence=None
            ),
        ),
        parsed_fields=(),
        missing_fields=(),
    )
    by_subject = {marker.subject: marker.reason for marker in report.uncertainty_markers}
    assert set(by_subject) == {"p1 footer", "p1 head"}
    assert "could not read this region at all" in by_subject["p1 footer"]
    assert "could not read this region at all" not in by_subject["p1 head"]
    # the unread tally counts one region, not both
    assert "1 of 2 region(s) reader attempted could not be read at all" in (
        report.reliability_information
    )


def test_a_read_but_unscored_region_still_raises_an_uncertainty_marker() -> None:
    """P-F3, "cannot hide uncertainty" (`ENGINE_1_ARCHITECTURE.md` G5.4). Text
    reaching the artifact with NO reliability signal behind it, and nothing
    saying so, is concealed uncertainty. The marker names it without inventing
    a score for it.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(
                source_location="p1 head", text="TAX INVOICE", extraction_confidence=None
            ),
        ),
        parsed_fields=(),
        missing_fields=(),
    )
    assert len(report.uncertainty_markers) == 1
    marker = report.uncertainty_markers[0]
    assert marker.subject == "p1 head"
    assert "no per-region extraction score" in marker.reason
    # named, never scored: no number is invented to stand in for the missing one
    assert report.confidence_scores == ()


def test_reliability_information_counts_every_region_reader_actually_attempted() -> None:
    """The regression test for the FALSE COUNT this defect emitted.

    Measured before the fix, on a real 3-region text-layer PDF, the artifact
    said *"0 of 0 region(s) reader attempted"* — `reader` had attempted three
    and read all three. A count that is wrong inside a financial artifact is
    Law 24 (never fabricate data), so the total is asserted explicitly here and
    can no longer drift back to zero silently.
    """
    regions = tuple(
        RegionReading(source_location=f"p1 line {n}", text=f"line {n}", extraction_confidence=None)
        for n in range(3)
    )
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=regions,
        parsed_fields=(),
        missing_fields=(),
    )
    # Pinned WHOLE, not by substring: a substring match cannot notice a wrong
    # number that happens to sit outside the quoted fragment, and this file's
    # own convention (commit 7e0efe2) is to pin the emitted text exactly.
    assert report.reliability_information == (
        "0 field(s) carry a confidence score from parser; "
        "0 of 3 region(s) reader attempted could not be read at all; "
        "3 of them were read but carry no per-region extraction score; "
        "0 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading; "
        "human business context capture fidelity: not supplied."
    )


def test_every_region_handed_in_is_accounted_for_in_exactly_one_state() -> None:
    """A CONSERVATION LAW, not a spot check: unread + unscored + scored must
    equal the number of regions handed in, always.

    Two quantities that must be equal need no threshold, no label and no
    judgement — they hold or they do not (`CLAUDE.md` §D.10, evidence). This is
    the check that makes the whole CLASS of counting defects impossible rather
    than the one instance F-013 happened to expose: any future branch that
    drops a region, double-counts one, or invents a fourth bucket breaks the
    sum even if every individual phrase still reads plausibly.
    """
    regions = (
        RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
        RegionReading(source_location="p1 head", text="TAX INVOICE", extraction_confidence=None),
        RegionReading(source_location="p1 sub", text="Acme Traders", extraction_confidence=None),
        RegionReading(source_location="p1 total", text="1180.00", extraction_confidence=HIGH),
    )
    by_state = [region.state for region in regions]
    unread = by_state.count(ReadingState.UNREAD)
    unscored = by_state.count(ReadingState.READ_BUT_UNSCORED)
    scored = by_state.count(ReadingState.READ_AND_SCORED)
    assert unread + unscored + scored == len(regions)

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=regions,
        parsed_fields=(ParsedField(field_name="Total", extraction_confidence=HIGH),),
        missing_fields=(),
    )
    assert report.reliability_information == (
        "1 field(s) carry a confidence score from parser; "
        f"{unread} of {len(regions)} region(s) reader attempted could not be read at all; "
        f"{unscored} of them were read but carry no per-region extraction score; "
        "0 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading; "
        "human business context capture fidelity: not supplied."
    )
    # and the region markers likewise account for every region that is not a
    # plain, scored reading — one each, never merged, never dropped (P-F3)
    region_subjects = [
        marker.subject for marker in report.uncertainty_markers if marker.subject.startswith("p1 ")
    ]
    assert sorted(region_subjects) == ["p1 footer", "p1 head", "p1 sub"]
    assert len(region_subjects) == unread + unscored


# ── a human note never raises a document-derived score ───────────────────────
# INV-11 / `ENGINE_1_INPUT_ENGINE_RULES.md:624` — "A human note may never raise
# Evidence Reliability simply by existing." The ablation shape
# `ENGINE_1_ARCHITECTURE.md` P-F7 specifies: same document signals, with and
# without a Human Business Description, every document-derived score
# byte-identical.


def test_a_human_note_never_changes_a_single_document_derived_score() -> None:
    cleaned = a_cleaned_document()
    regions = (
        RegionReading(source_location="p1 total", text="1180.00", extraction_confidence=HIGH),
    )
    fields = (ParsedField(field_name="Total", extraction_confidence=HIGH),)
    note = a_human_business_context(original_user_text="Advance paid to supplier.")

    without = record_confidence(
        cleaned=cleaned, reader_regions=regions, parsed_fields=fields, missing_fields=()
    )
    with_note = record_confidence(
        cleaned=cleaned,
        reader_regions=regions,
        parsed_fields=fields,
        missing_fields=(),
        human_capture=HumanCaptureEvidence(submitted_text="Advance paid to supplier.", stored=note),
    )
    document_scores = {
        score.field_name: score.confidence
        for score in without.confidence_scores
        if score.field_name != CAPTURE_FIDELITY_FIELD_NAME
    }
    document_scores_with_note = {
        score.field_name: score.confidence
        for score in with_note.confidence_scores
        if score.field_name != CAPTURE_FIDELITY_FIELD_NAME
    }
    assert document_scores == {"Total": HIGH}
    assert document_scores_with_note == document_scores
    # and the human-derived score stays separable from them by name, never
    # merged into an anonymous fact (INV-11)
    human_derived = [
        score
        for score in with_note.confidence_scores
        if score.field_name == CAPTURE_FIDELITY_FIELD_NAME
    ]
    assert len(human_derived) == 1
    # ORDER carries meaning in an audit artifact, so it is pinned too: the
    # document's own scores lead, in the order `parsed_fields` supplied them,
    # and the human-derived one is APPENDED. A note that arrived first would
    # read, to any consumer that takes the head of the tuple, as the
    # document's primary score — the same "raises reliability by existing"
    # failure by a positional route rather than a numeric one.
    assert [score.field_name for score in with_note.confidence_scores] == [
        "Total",
        CAPTURE_FIDELITY_FIELD_NAME,
    ]
    assert with_note.confidence_scores[: len(without.confidence_scores)] == (
        without.confidence_scores
    )


def test_the_note_s_own_words_never_move_a_document_derived_score() -> None:
    """P-F7's harder half. The ablation above removes the note entirely; this
    one keeps it and changes only WHAT IT SAYS — including a note that asserts
    a value about the document.

    "Evidence carries its origin, permanently. A human note is evidence, not
    truth" (`CLAUDE.md` §O). A note that could move a document-derived score by
    what it CLAIMS would make the note truth, and would also breach P-F4
    (business plausibility is never evidence).
    """
    cleaned = a_cleaned_document()
    regions = (
        RegionReading(source_location="p1 total", text="1180.00", extraction_confidence=LOW),
    )
    fields = (ParsedField(field_name="Total", extraction_confidence=LOW),)

    def run_with(text: str) -> tuple[tuple[str, Confidence], ...]:
        report = record_confidence(
            cleaned=cleaned,
            reader_regions=regions,
            parsed_fields=fields,
            missing_fields=(),
            human_capture=HumanCaptureEvidence(
                submitted_text=text,
                stored=a_human_business_context(original_user_text=text),
            ),
        )
        return tuple(
            (score.field_name, score.confidence)
            for score in report.confidence_scores
            if score.field_name != CAPTURE_FIDELITY_FIELD_NAME
        )

    bland = run_with("Advance paid to supplier.")
    assertive = run_with("The total is definitely 1180.00, I typed it myself, it is correct.")
    assert bland == (("Total", LOW),)
    assert assertive == bland


def test_a_human_note_never_alters_or_removes_a_document_derived_marker() -> None:
    """P-F3's executable form, applied to the note: *"markers are never dropped,
    summarised or deduplicated. Assert marker count out >= marker count in"*
    (`ENGINE_1_ARCHITECTURE.md` G5.4). A note that could silence a document's
    own doubt would raise reliability by existing, by subtraction rather than
    addition.
    """
    cleaned = a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER)
    regions = (
        RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
        RegionReading(source_location="p1 head", text="TAX INVOICE", extraction_confidence=None),
    )
    missing = (MissingField(field_name="PO Number", state="absent"),)

    def markers_of(human_capture: HumanCaptureEvidence | None) -> list[tuple[str, str]]:
        report = record_confidence(
            cleaned=cleaned,
            reader_regions=regions,
            parsed_fields=(),
            missing_fields=missing,
            human_capture=human_capture,
        )
        return [(marker.subject, marker.reason) for marker in report.uncertainty_markers]

    without = markers_of(None)
    with_match = markers_of(
        HumanCaptureEvidence(
            submitted_text="Advance paid.",
            stored=a_human_business_context(original_user_text="Advance paid."),
        )
    )
    with_mismatch = markers_of(
        HumanCaptureEvidence(
            submitted_text="Advance paid.",
            stored=a_human_business_context(original_user_text="Advance paid to supplier."),
        )
    )
    # the document's own four doubts, named rather than counted: a count of 4
    # is satisfied by any four markers, including four copies of one — the
    # subjects are what actually proves each distinct doubt is present
    assert [subject for subject, _reason in without] == [
        "the document as cleaned",  # cleaner's preservation verdict
        "p1 footer",  # the unread region
        "p1 head",  # the read-but-unscored region
        "PO Number",  # parser's missing field
    ]
    # every one of them survives, byte-identical, in the same order, both ways
    assert with_match[: len(without)] == without
    assert with_mismatch[: len(without)] == without
    # count out >= count in, never fewer
    assert len(with_match) >= len(without)
    assert len(with_mismatch) > len(without)


def test_a_human_note_never_changes_a_single_count_the_document_earned() -> None:
    """The reliability text carries counts as well as scores. A note that moved
    one of them would raise reliability by existing just as surely as a note
    that moved a score — the counts are what a reader downstream sees first.
    """
    cleaned = a_cleaned_document()
    regions = (
        RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
        RegionReading(source_location="p1 head", text="TAX INVOICE", extraction_confidence=None),
    )

    def counts_sentence(human_capture: HumanCaptureEvidence | None) -> str:
        report = record_confidence(
            cleaned=cleaned,
            reader_regions=regions,
            parsed_fields=(ParsedField(field_name="Total", extraction_confidence=HIGH),),
            missing_fields=(MissingField(field_name="PO Number", state="absent"),),
            human_capture=human_capture,
        )
        # everything up to, but excluding, the clause that is ABOUT the note
        head, _, _tail = report.reliability_information.partition(
            "; human business context capture fidelity:"
        )
        return head

    without = counts_sentence(None)
    with_note = counts_sentence(
        HumanCaptureEvidence(
            submitted_text="Advance paid.",
            stored=a_human_business_context(original_user_text="Advance paid."),
        )
    )
    assert without == (
        "1 field(s) carry a confidence score from parser; "
        "1 of 2 region(s) reader attempted could not be read at all; "
        "1 of them were read but carry no per-region extraction score; "
        "1 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading"
    )
    assert with_note == without


def test_a_note_on_a_document_with_no_signals_scores_only_itself_under_its_own_name() -> None:
    """The case where a note is most dangerous: nothing was read, so anything
    the note contributes is the ONLY score in the artifact.

    Measured: with zero regions and zero parsed fields, a matching note makes
    `confidence_scores` a one-entry collection. This test does not decide what
    an aggregator downstream may do with that — `document_score_rule` is
    UNDEFINED and pending the owner (Law 54, `ENGINE_1_ARCHITECTURE.md` G9.2) —
    it pins the only thing that is knowable without it: the entry is human-
    derived, it is named as such, and NOT ONE document-derived score was
    manufactured out of the note.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=HumanCaptureEvidence(
            submitted_text="Advance paid.",
            stored=a_human_business_context(original_user_text="Advance paid."),
        ),
    )
    names = [score.field_name for score in report.confidence_scores]
    assert names == [CAPTURE_FIDELITY_FIELD_NAME]
    # the name is namespaced so no aggregator has to guess which origin it is:
    # a parsed document field can never be called this, and a collision is
    # refused rather than resolved (see the name-collision test below).
    assert "." in CAPTURE_FIDELITY_FIELD_NAME
    assert CAPTURE_FIDELITY_FIELD_NAME.startswith("human_business_context.")
    # and nothing document-derived was invented to accompany it
    document_derived = [
        score
        for score in report.confidence_scores
        if score.field_name != CAPTURE_FIDELITY_FIELD_NAME
    ]
    assert document_derived == []


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


def test_region_reading_refuses_a_confidence_without_text() -> None:
    """The one pairing that stays incoherent: an instrument cannot score a
    reading that does not exist. Unlike text-without-a-score (a real backend
    state, see the tri-state tests below), there is no reader that produces
    this, and no honest meaning to give it.
    """
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
