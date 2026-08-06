"""`assembly`, red-teamed — the seven places a number could go wrong quietly.

`tests/unit/test_input_engine_assembly.py` establishes that assembly WORKS.
This file exists to try to prove it does not, and it attacks a different
class of defect: not "does assembly produce an artifact", but **"could a
number, an origin or a doubt change on its way through assembly without any
existing test noticing?"**

Every test below is written against a specific locked sentence, and every one
of them was checked for the failure mode `CLAUDE.md` §J.1 names — a test that
passes first try is a test that was never able to fail. Where an assertion
looked tautological it was replaced by a stricter one; the four that matter
most are recorded here because they are the ones a reviewer would otherwise
read as duplicates of the existing suite:

  `==` ON A `Decimal` DOES NOT SEE A RE-SCALING. `Decimal("0.9800")` and
      `Decimal("0.98")` compare EQUAL, so every existing test asserting
      `score == LOW` would stay green if assembly quantised, normalised or
      round-tripped a confidence through `float`. The tests below compare
      `str(...)`, which is the only comparison that can see it. INV-2 says
      confidence changes only when EVIDENCE changes; a change of scale is a
      change nobody made.

  EQUALITY DOES NOT SEE A REBUILD. A pydantic model rebuilt field-for-field
      is `==` to the original and is not the original. `assemble` is
      specified to combine, never to author (`ENGINE_1_INPUT_ENGINE_RULES.md`
      — *"The parent assembles what its sub-engines produced; it does not
      correct, second-guess, or improve any of it"*), so the tests assert
      `is` identity for every reading and every provenance that crosses it.

  A MISSING VALUE AND A MERGED ONE LOOK THE SAME DOWNSTREAM. INV-11's last
      line — *"No engine may merge these origins into a single anonymous
      fact"* — is attacked by putting two facts of genuinely different origin
      through one assembly and asserting each keeps its own six attributes,
      rather than by asserting one fact keeps its own.

  "NOTHING WAS ADDED" IS WEAKER THAN "NOTHING MOVED". The human-note tests
      run the SAME sub-engine outputs twice, once with a note and once
      without, and assert every confidence value is identical between the
      two. That is `SYSTEM_INVARIANTS.md` INV-11 — *"A human note may never
      raise Evidence Reliability simply by existing"* — as an observation
      instead of a claim.

Everything runs against the real frozen schema in
`accountant_dad.artifacts.evidence`, never a stand-in (`CLAUDE.md` §J.6).
"""

from __future__ import annotations

import ast
import inspect
import typing
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from authored_source import authored_source
from pydantic import BaseModel, ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DetectedTable,
    DocumentEvidenceObject,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    UncertaintyMarker,
)
from accountant_dad.confidence import MAX, MIN, Confidence
from accountant_dad.engines.input_engine import assembly as assembly_module
from accountant_dad.engines.input_engine.assembly import (
    CleanerOutput,
    ConfidenceOutput,
    ParserOutput,
    ReaderOutput,
    SubEngineOutputs,
    assemble,
)
from accountant_dad.engines.input_engine.config import PARAMETER_CATALOG
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
#: A zone that is neither UTC nor a whole number of hours from it. India
#: Standard Time is the MVP's own regime (`CLAUDE.md` §B.7), and its half-hour
#: offset is what makes a silent normalisation to UTC visible.
IST = timezone(timedelta(hours=5, minutes=30))

HIGH = Decimal("0.9800")
LOW = Decimal("0.1000")

#: The two names in the whole artifact tree whose value IS a single
#: confidence, and both are per-thing rather than per-document: one score for
#: one fact's origin, one score for one named field. Anything else typed the
#: same way is the document-level scalar `CONFIDENCE_SPECIFICATION.md` §4
#: eliminated by theorem.
PER_THING_CONFIDENCE_FIELDS = frozenset(
    {("Provenance", "confidence"), ("FieldConfidence", "confidence")}
)

#: `DATA_FLOW.md` §12 and `SYSTEM_INVARIANTS.md` INV-11, in the order both
#: tables write them. Six, none optional.
PROVENANCE_ATTRIBUTES = (
    "source_type",
    "source_id",
    "evidence_reference",
    "timestamp",
    "confidence",
    "corroborated",
)

#: Five readings is enough to tell "every one survived" from "one survived",
#: and enough that a hidden filter would have something to drop.
FIVE_READINGS = 5

#: Two facts, two origins. The assertion is that they stay two.
TWO_ORIGINS = 2

#: One marker per doubt. Three doubts about one subject stay three, because
#: collapsing them is exactly the summarisation Rule 4 forbids.
THREE_DOUBTS = 3

#: Ten repeats of one assembly. A module-level accumulator, a cached value or
#: a counter feeding a score would drift within this many calls; one repeat
#: could not see it.
TEN_REPEATS = 10


# ── builders ─────────────────────────────────────────────────────────────────


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_provenance(
    *,
    source_type: SourceType = SourceType.DOCUMENT,
    source_id: str = "invoice-900.pdf",
    evidence_reference: str = "page 1, box (10, 10)",
    timestamp: datetime = WHEN,
    confidence: Decimal = HIGH,
) -> Provenance:
    return Provenance(
        source_type=source_type,
        source_id=source_id,
        evidence_reference=evidence_reference,
        timestamp=timestamp,
        confidence=confidence,
        corroborated=Corroborated.NOT_ASSESSED,
    )


def a_detected_field(
    *,
    name: str = "Amount",
    value: str | None = "4500.00",
    provenance: Provenance | None = None,
) -> DetectedField:
    return DetectedField(
        name=name, value=value, provenance=provenance if provenance is not None else a_provenance()
    )


def a_cleaner_output() -> CleanerOutput:
    return CleanerOutput(
        cleaned_document_representation=object(),
        quality_issues_detected=("noise_sigma=2.1",),
        preservation_status="the cleaned representation is the safer basis for reading",
    )


def a_reader_output(*, raw_extracted_text: str = "ACME TRADERS\nAmount 4500.00") -> ReaderOutput:
    return ReaderOutput(
        raw_extracted_text=raw_extracted_text,
        source_locations=("page 1, box (10, 10)",),
        extraction_confidence=("Amount: 0.98",),
    )


def a_parser_output(
    *,
    detected_fields: tuple[DetectedField, ...] = (),
    detected_tables: tuple[DetectedTable, ...] = (),
) -> ParserOutput:
    return ParserOutput(
        document_structure="header / body / totals",
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


def parts_carrying(
    *,
    detected_fields: tuple[DetectedField, ...] = (),
    detected_tables: tuple[DetectedTable, ...] = (),
    confidence_scores: tuple[FieldConfidence, ...] = (),
    uncertainty_markers: tuple[UncertaintyMarker, ...] = (),
    confidence: ConfidenceOutput | None = None,
) -> SubEngineOutputs:
    """The four parts almost every test varies, flat; anything else via
    `confidence=a_confidence_output(...)`.

    `reliability_information` and `risky_fields` used to sit here too, which put
    six parameters on one builder. They are passed at two call sites out of
    twenty-seven, so they moved behind the escape hatch rather than being
    silenced with a suppression — this repository's suppression budget is a
    ratchet and spending one to keep a convenience is the wrong trade.
    """
    if confidence is not None and (confidence_scores or uncertainty_markers):
        # Both routes at once would make the flat arguments silently useless.
        raise TypeError("pass the flat confidence arguments or `confidence=`, not both")
    return SubEngineOutputs(
        cleaner=a_cleaner_output(),
        reader=a_reader_output(),
        parser=a_parser_output(detected_fields=detected_fields, detected_tables=detected_tables),
        confidence=confidence
        or a_confidence_output(
            confidence_scores=confidence_scores,
            uncertainty_markers=uncertainty_markers,
        ),
    )


def a_field_and_its_score(name: str, confidence: Decimal) -> tuple[DetectedField, FieldConfidence]:
    """A detected field and the Confidence Report entry that must agree with
    it. `DocumentEvidenceObject` refuses the artifact when the two disagree,
    so every test that wants a VALID artifact has to build both halves.
    """
    return (
        a_detected_field(name=name, provenance=a_provenance(confidence=confidence)),
        FieldConfidence(field_name=name, confidence=confidence),
    )


def every_confidence_as_written(document: DocumentEvidenceObject) -> dict[str, str]:
    """Every confidence in the artifact, keyed by where it lives, as the exact
    string its `Decimal` renders — not as a number.

    `Decimal("0.98") == Decimal("0.9800")` is `True`, so a comparison of
    values cannot see a re-scaling. A comparison of their written forms can,
    and a re-scaled confidence is a confidence that changed without any
    evidence changing (INV-2).
    """
    written = {
        f"provenance:{field.name}": str(field.provenance.confidence)
        for field in document.structured_document.detected_fields
    }
    for index, table in enumerate(document.structured_document.detected_tables):
        written[f"provenance:table-{index}"] = str(table.provenance.confidence)
    for score in document.confidence_report.confidence_scores:
        written[f"score:{score.field_name}"] = str(score.confidence)
    if document.human_business_context is not None:
        written["provenance:human_business_context"] = str(
            document.human_business_context.provenance.confidence
        )
    return written


def models_reachable_from(root: type[BaseModel]) -> set[type[BaseModel]]:
    """Every pydantic model reachable from `root` through its field
    annotations, including through `tuple[...]` and `X | None`.

    Written as a traversal rather than a hand-written list so that a model
    added to the artifact tree later is inspected automatically. A list would
    have to be remembered, and the thing being guarded against is exactly a
    field nobody remembered to look at.
    """
    found: set[type[BaseModel]] = set()
    pending: list[type[BaseModel]] = [root]
    while pending:
        model = pending.pop()
        if model in found:
            continue
        found.add(model)
        for info in model.model_fields.values():
            annotations = [info.annotation]
            while annotations:
                annotation = annotations.pop()
                annotations.extend(typing.get_args(annotation))
                if (
                    inspect.isclass(annotation)
                    and issubclass(annotation, BaseModel)
                    and annotation not in found
                ):
                    pending.append(annotation)
    return found


# ═══════════════════════════════════════════════════════════════════════════
# INV-2 · confidence changes only when evidence changes
# `SYSTEM_INVARIANTS.md` INV-2 — "Confidence never changes because an engine
# reasoned harder." Assembly does no reasoning at all, so nothing it does may
# move a number. Attacked by running it again, running it more, and running
# its independent inputs in a different order.
# ═══════════════════════════════════════════════════════════════════════════


def test_assembling_the_same_parts_twice_moves_no_number_not_even_its_written_scale() -> None:
    field, score = a_field_and_its_score("Amount", HIGH)
    parts = parts_carrying(detected_fields=(field,), confidence_scores=(score,))
    identity = an_identity()

    first = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))
    second = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))

    assert every_confidence_as_written(first) == every_confidence_as_written(second)
    # And the written form is the one the sub-engine supplied, unrescaled.
    assert every_confidence_as_written(first)["score:Amount"] == "0.9800"
    assert every_confidence_as_written(first)["provenance:Amount"] == "0.9800"


def test_assembling_the_same_parts_ten_times_never_moves_a_number() -> None:
    """A second run cannot see an accumulator that needs several runs to
    drift. Ten can. Assembly holds no state, and this is what says so.
    """
    field, score = a_field_and_its_score("Amount", LOW)
    parts = parts_carrying(detected_fields=(field,), confidence_scores=(score,))
    identity = an_identity()

    written = [
        every_confidence_as_written(
            assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))
        )
        for _ in range(TEN_REPEATS)
    ]

    assert written.count(written[0]) == TEN_REPEATS
    assert written[0]["score:Amount"] == "0.1000"


def test_reordering_two_independent_scores_changes_no_value_and_is_not_sorted_away() -> None:
    """The two fields are independent: neither depends on the other's score.
    Reordering them must reorder the output identically — never sort it, and
    never change a value. A sort would be a transformation assembly is not
    authorised to perform, and it would silently destroy the order the
    `confidence` sub-engine chose.
    """
    zebra, zebra_score = a_field_and_its_score("Zebra Total", HIGH)
    alpha, alpha_score = a_field_and_its_score("Alpha Total", LOW)

    given_zebra_first = assemble(
        parts=parts_carrying(
            detected_fields=(zebra, alpha), confidence_scores=(zebra_score, alpha_score)
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )
    given_alpha_first = assemble(
        parts=parts_carrying(
            detected_fields=(alpha, zebra), confidence_scores=(alpha_score, zebra_score)
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    # order follows the input, and is not sorted
    assert [s.field_name for s in given_zebra_first.confidence_report.confidence_scores] == [
        "Zebra Total",
        "Alpha Total",
    ]
    assert [s.field_name for s in given_alpha_first.confidence_report.confidence_scores] == [
        "Alpha Total",
        "Zebra Total",
    ]
    # and no value moved between the two orderings
    assert every_confidence_as_written(given_zebra_first) == every_confidence_as_written(
        given_alpha_first
    )


def test_an_extra_uncertainty_marker_carrying_no_new_evidence_moves_no_confidence_score() -> None:
    """A marker is a description of doubt, not evidence about a reading.
    Adding one is the closest thing assembly has to "an extra stage that ran";
    INV-2 says it may not move a number, and this observes that it does not.
    """
    field, score = a_field_and_its_score("Amount", HIGH)
    without = assemble(
        parts=parts_carrying(detected_fields=(field,), confidence_scores=(score,)),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )
    with_marker = assemble(
        parts=parts_carrying(
            detected_fields=(field,),
            confidence_scores=(score,),
            uncertainty_markers=(
                UncertaintyMarker(subject="Amount", reason="the totals block is faint"),
            ),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert every_confidence_as_written(without) == every_confidence_as_written(with_marker)
    assert with_marker.confidence_report.uncertainty_markers[0].subject == "Amount"


def test_assembly_never_rebuilds_a_reading_it_was_given() -> None:
    """`==` cannot tell a passed-through object from a rebuilt one. `is` can.

    A rebuild is where a value gets quietly re-derived — a `Provenance`
    reconstructed with a "tidied" confidence would still be `==` to the
    original if the tidy were a no-op today, and would stop being one the
    first time it was not.
    """
    field, score = a_field_and_its_score("Amount", HIGH)
    table = DetectedTable(rows=(("Item", "Qty"), ("Bolt", "3")), provenance=a_provenance())
    marker = UncertaintyMarker(subject="Date", reason="two readings are possible")

    result = assemble(
        parts=parts_carrying(
            detected_fields=(field,),
            detected_tables=(table,),
            confidence_scores=(score,),
            uncertainty_markers=(marker,),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert result.structured_document.detected_fields[0] is field
    assert result.structured_document.detected_fields[0].provenance is field.provenance
    assert result.structured_document.detected_tables[0] is table
    assert result.structured_document.detected_tables[0].provenance is table.provenance
    assert result.confidence_report.confidence_scores[0] is score
    assert result.confidence_report.uncertainty_markers[0] is marker


# ═══════════════════════════════════════════════════════════════════════════
# A5 · there is no document-level scalar, and assembly is where one would be
# born. `CONFIDENCE_SPECIFICATION.md` §4.4 — "No `document_confidence` field
# is created, in any artifact, in any engine" and "No aggregation of
# confidences is computed."
# ═══════════════════════════════════════════════════════════════════════════


def test_no_function_in_assembly_returns_a_bare_confidence() -> None:
    """`from __future__ import annotations` keeps return annotations as the
    strings they were written as, so a future `def document_confidence(...)
    -> Confidence:` turns this red the moment it is written, before anything
    calls it.
    """
    forbidden = {"Confidence", "Decimal", "Confidence | None", "Decimal | None"}
    offenders = [
        (name, inspect.signature(function).return_annotation)
        for name, function in inspect.getmembers(assembly_module, inspect.isfunction)
        if function.__module__ == assembly_module.__name__
        and inspect.signature(function).return_annotation in forbidden
    ]
    assert offenders == [], (
        f"assembly function(s) returning one confidence value: {offenders}. "
        "A single number combined from more than one field, region or "
        "instrument is the document-level scalar CONFIDENCE_SPECIFICATION.md "
        "§4 eliminated by Marichal & Mesiar Corollary 5.7."
    )


def test_no_sub_engine_input_contract_declares_a_document_level_confidence() -> None:
    """The four input contracts are where a scalar would arrive from outside
    rather than be computed inside. `ConfidenceOutput.confidence_scores` is a
    tuple of per-field scores for exactly this reason; a sibling field typed
    as one `Confidence` would be the whole-document number under a new name.
    """
    forbidden = {"Confidence", "Decimal", "Confidence | None", "Decimal | None"}
    offenders = [
        (contract.__name__, field.name, field.type)
        for contract in (
            CleanerOutput,
            ReaderOutput,
            ParserOutput,
            ConfidenceOutput,
            SubEngineOutputs,
        )
        for field in dataclass_fields(contract)
        if field.type in forbidden
    ]
    assert offenders == [], f"input contract field(s) typed as one confidence: {offenders}"


def test_no_model_reachable_from_the_evidence_object_carries_a_document_level_confidence() -> None:
    """The artifact assembly emits, walked whole rather than one class at a
    time. Two fields are legitimately one confidence — a fact's own
    provenance and one named field's score — and every other one would be a
    scalar over something larger than the thing that produced the signal.
    """
    offenders = sorted(
        (model.__name__, name)
        for model in models_reachable_from(DocumentEvidenceObject)
        for name, info in model.model_fields.items()
        if info.annotation in (Confidence, Decimal)
        and (model.__name__, name) not in PER_THING_CONFIDENCE_FIELDS
    )
    assert offenders == [], (
        f"model field(s) carrying a confidence that is not per-fact or "
        f"per-field: {offenders}. CONFIDENCE_SPECIFICATION.md §4.4: every "
        "constraint on confidence is expressed at the level the signal was "
        "produced."
    )
    # And the walk actually reached the tree it claims to; an empty traversal
    # would report no offenders for the wrong reason.
    reached = {model.__name__ for model in models_reachable_from(DocumentEvidenceObject)}
    assert {"Provenance", "FieldConfidence", "ConfidenceReport", "StructuredDocument"} <= reached


def test_assembly_performs_no_arithmetic_at_all() -> None:
    """`assemble`'s own docstring claims *"Nothing here performs arithmetic on
    a confidence value"*. Read off the parse tree rather than believed: the
    only binary operators in the file are `|` type unions in annotations, so
    an `+`, `-`, `*` or `/` appearing anywhere turns this red — including one
    written inside an f-string or a comprehension, which a grep would miss.
    """
    source = authored_source(assembly_module)
    arithmetic = sorted(
        {
            (node.lineno, type(node.op).__name__)
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.BinOp) and not isinstance(node.op, ast.BitOr)
        }
    )
    assert arithmetic == [], (
        f"arithmetic found in assembly at {arithmetic}. Assembly combines; it "
        "does not compute. A number produced here belongs to no sub-engine "
        "and has no owner (INV-10)."
    )


def test_assembly_calls_no_aggregation_function() -> None:
    """`min`, `max`, `sum`, `statistics.mean` — the shapes A5 rules out.
    `CONFIDENCE_SPECIFICATION.md`'s own Objection 1 predicts exactly this
    failure: *"the first engineer who needs one number will write `min(...)`
    at the call site, and it will be invisible because it is not a schema
    field anyone reviews."* This is the review it would otherwise escape.
    """
    aggregations = {"min", "max", "sum", "mean", "median", "fmean", "fsum", "prod", "average"}
    called = {
        node.func.id
        for node in ast.walk(ast.parse(authored_source(assembly_module)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(ast.parse(authored_source(assembly_module)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called & aggregations == set(), (
        f"assembly calls aggregation function(s): {sorted(called & aggregations)}"
    )


def test_assembly_compares_only_against_none() -> None:
    """Every branch in the file is "did this sub-engine produce anything".
    A comparison against anything else is a decision, and assembly has no
    decision to make (`SUB_ENGINE_RESPONSIBILITIES.md` — the parent "owns the
    internal assembly of its own sub-engines' outputs and nothing more").
    """
    comparisons = [
        (node.lineno, [ast.dump(comparator) for comparator in node.comparators])
        for node in ast.walk(ast.parse(authored_source(assembly_module)))
        if isinstance(node, ast.Compare)
        and not all(
            isinstance(comparator, ast.Constant) and comparator.value is None
            for comparator in node.comparators
        )
    ]
    assert comparisons == [], f"assembly compares against something other than None: {comparisons}"


# ═══════════════════════════════════════════════════════════════════════════
# Assembly is not a gate either. It has no configuration, reads none, and
# drops nothing on the strength of a value.
# ═══════════════════════════════════════════════════════════════════════════


def test_assembly_reads_no_confidence_configuration() -> None:
    """Sixteen parameters exist and every one is `UNSET`
    (`ENGINE_1_CONFIDENCE_PARAMETERS.md`). Assembly importing the loader
    would be the first step toward a threshold living here, where INV-10 says
    no decision lives at all. The names come from the catalog itself, so a
    seventeenth parameter is covered without editing this test.
    """
    source = authored_source(assembly_module)
    imported = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any("input_engine.config" in module for module in imported), (
        f"assembly imports the confidence configuration loader: {sorted(imported)}"
    )
    mentioned = sorted(spec.name for spec in PARAMETER_CATALOG if spec.name in source)
    assert mentioned == [], f"assembly names confidence parameter(s): {mentioned}"


def test_every_reading_survives_assembly_at_the_scales_minimum_confidence() -> None:
    """A gate would drop the worst readings. `MIN` is the worst there is, and
    all five come out — `COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 5: low
    confidence creates a marker, never "a silently omitted field".
    """
    pairs = [a_field_and_its_score(f"Field {index}", MIN) for index in range(FIVE_READINGS)]
    result = assemble(
        parts=parts_carrying(
            detected_fields=tuple(field for field, _ in pairs),
            confidence_scores=tuple(score for _, score in pairs),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert len(result.structured_document.detected_fields) == FIVE_READINGS
    assert len(result.confidence_report.confidence_scores) == FIVE_READINGS
    assert set(every_confidence_as_written(result).values()) == {str(MIN)}


def three_readings_all_at(confidence: Decimal) -> SubEngineOutputs:
    """Three readings, all at one confidence. A helper rather than a fixture
    so the two calls below are visibly the same input at two values.
    """
    pairs = [a_field_and_its_score(f"Field {index}", confidence) for index in range(THREE_DOUBTS)]
    return parts_carrying(
        detected_fields=tuple(field for field, _ in pairs),
        confidence_scores=tuple(score for _, score in pairs),
    )


def test_the_assembled_artifact_has_the_same_shape_at_minimum_and_maximum_confidence() -> None:
    """The strongest statement available without a threshold to point at: the
    artifact's SHAPE does not depend on the values inside it. If any cutoff
    existed anywhere in assembly, the worst-possible and best-possible inputs
    would not produce the same counts.
    """
    at_min = assemble(
        parts=three_readings_all_at(MIN),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )
    at_max = assemble(
        parts=three_readings_all_at(MAX),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert len(at_min.structured_document.detected_fields) == len(
        at_max.structured_document.detected_fields
    )
    assert len(at_min.confidence_report.confidence_scores) == len(
        at_max.confidence_report.confidence_scores
    )
    assert at_min.confidence_report.risky_fields == at_max.confidence_report.risky_fields
    assert at_min.confidence_report.uncertainty_markers == (
        at_max.confidence_report.uncertainty_markers
    )
    # ... and the only difference is the number itself.
    assert set(every_confidence_as_written(at_min).values()) == {str(MIN)}
    assert set(every_confidence_as_written(at_max).values()) == {str(MAX)}


# ═══════════════════════════════════════════════════════════════════════════
# Rule 4 · uncertainty is only ever described more precisely, never removed.
# `COMMUNICATION_RULES_INPUT_ENGINE.md` §3 Rule 4 — traceability "not
# stripped at the engine boundary, not summarised into a single score, and
# not dropped by any downstream engine"; §4 item 8 — "Uncertainty is only ever
# described more precisely — never removed."
# ═══════════════════════════════════════════════════════════════════════════


def test_three_doubts_about_one_subject_cross_assembly_as_three_not_as_one() -> None:
    """Deduplicating by subject is the cheapest possible summarisation, and
    it is invisible: the artifact still has a marker for the subject, so
    nothing downstream can tell that two reasons were thrown away.
    """
    doubts = tuple(
        UncertaintyMarker(subject="Date", reason=reason)
        for reason in (
            "reads as 12/03/2026 under one interpretation",
            "reads as 03/12/2026 under the other interpretation",
            "the separator itself is ambiguous between '/' and '.'",
        )
    )
    result = assemble(
        parts=parts_carrying(uncertainty_markers=doubts),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert result.confidence_report.uncertainty_markers == doubts
    assert len(result.confidence_report.uncertainty_markers) == THREE_DOUBTS
    assert len({marker.reason for marker in result.confidence_report.uncertainty_markers}) == (
        THREE_DOUBTS
    )


def test_a_reason_crosses_assembly_verbatim_and_is_never_shortened() -> None:
    """A truncated reason is still a reason, so nothing structural refuses
    it. `ENGINE_1_INPUT_ENGINE_RULES.md` — *"a bare score cannot become a good
    question downstream"* — and half a reason is most of the way to a bare
    score.
    """
    long_reason = (
        "the amount column and the tax column are printed at the same x offset "
        "on this template, so 19,800.00 in the right-hand column could belong to "
        "either; both readings are recorded and neither is preferred here. "
    ) * 4
    marker = UncertaintyMarker(subject="Amount", reason=long_reason)

    result = assemble(
        parts=parts_carrying(uncertainty_markers=(marker,)),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert result.confidence_report.uncertainty_markers[0].reason == long_reason


def test_reliability_information_crosses_assembly_byte_for_byte() -> None:
    """Including its whitespace. Normalising free text is the kind of tidy-up
    that looks harmless and quietly rewrites what an engine said it observed.
    """
    stated = "  scan legible;\n\ttotals block unclear  "
    result = assemble(
        parts=parts_carrying(confidence=a_confidence_output(reliability_information=stated)),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )
    assert result.confidence_report.reliability_information == stated


def test_a_duplicated_risky_field_is_refused_rather_than_silently_deduplicated() -> None:
    """If assembly quietly deduplicated to keep the schema happy, the caller's
    second listing would vanish with no error and no record. The schema
    refuses the artifact instead, and assembly must let it — Law 19, one
    source of truth for that rule.
    """
    with pytest.raises(ValidationError):
        assemble(
            parts=parts_carrying(confidence=a_confidence_output(risky_fields=("Amount", "Amount"))),
            identity=an_identity(),
            source_references=("upload:x.pdf",),
        )


def test_an_unreadable_field_keeps_none_and_is_never_filled_in() -> None:
    """`ENGINE_1_INPUT_ENGINE_RULES.md` — "absent", "zero" and "unreadable"
    stay three states. `None` becoming `""` or `"0"` on the way through would
    convert an admitted unknown into a read value, which is the invention
    prohibition exactly.
    """
    unreadable = a_detected_field(name="Date", value=None, provenance=a_provenance(confidence=MIN))
    result = assemble(
        parts=parts_carrying(
            detected_fields=(unreadable,),
            confidence_scores=(FieldConfidence(field_name="Date", confidence=MIN),),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    assert result.structured_document.detected_fields[0].value is None
    assert result.structured_document.detected_fields[0].value != ""
    assert result.structured_document.detected_fields[0].value != "0"


# ═══════════════════════════════════════════════════════════════════════════
# INV-11 · evidence carries its origin, permanently.
# `DATA_FLOW.md` §12 — six attributes, and "No engine may merge these origins
# into a single anonymous fact."
# ═══════════════════════════════════════════════════════════════════════════


def test_the_six_provenance_attributes_are_still_the_six_data_flow_12_names() -> None:
    """The list this file asserts against, checked against the schema itself.
    A seventh attribute, or a renamed one, is an architecture change and must
    surface here rather than in a downstream engine that stopped receiving it.
    """
    assert tuple(Provenance.model_fields) == PROVENANCE_ATTRIBUTES


def test_every_provenance_attribute_survives_assembly_unchanged() -> None:
    origin = a_provenance(
        source_id="scan-2026-08-05-0001.tiff",
        evidence_reference="page 2, box (412, 96)-(560, 118)",
        confidence=LOW,
    )
    field = a_detected_field(name="GSTIN", value="27AAECS1234F1Z5", provenance=origin)
    result = assemble(
        parts=parts_carrying(
            detected_fields=(field,),
            confidence_scores=(FieldConfidence(field_name="GSTIN", confidence=LOW),),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    carried = result.structured_document.detected_fields[0].provenance
    for attribute in PROVENANCE_ATTRIBUTES:
        assert getattr(carried, attribute) == getattr(origin, attribute), attribute
    assert str(carried.confidence) == str(origin.confidence)
    assert carried.corroborated is Corroborated.NOT_ASSESSED


def test_two_facts_of_different_origin_keep_their_own_provenance_and_are_never_merged() -> None:
    """The failure INV-11's last line names. Two facts, two source ids, two
    references, two confidences, two source TYPES — one artifact. If assembly
    ever hoisted a shared provenance, one of these would be wearing the
    other's origin and nothing downstream could tell.
    """
    read_off_the_page = a_detected_field(
        name="Amount",
        value="19800.00",
        provenance=a_provenance(
            source_type=SourceType.DOCUMENT,
            source_id="invoice-900.pdf",
            evidence_reference="page 1, box (10, 10)",
            confidence=HIGH,
        ),
    )
    supplied_by_the_uploader = a_detected_field(
        name="Upload Channel",
        value="email-ingest",
        provenance=a_provenance(
            source_type=SourceType.STRUCTURED_METADATA,
            source_id="ingest-service",
            evidence_reference="envelope header",
            confidence=LOW,
        ),
    )
    result = assemble(
        parts=parts_carrying(
            detected_fields=(read_off_the_page, supplied_by_the_uploader),
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=HIGH),
                FieldConfidence(field_name="Upload Channel", confidence=LOW),
            ),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    origins = [field.provenance for field in result.structured_document.detected_fields]
    assert len({origin.source_type for origin in origins}) == TWO_ORIGINS
    assert len({origin.source_id for origin in origins}) == TWO_ORIGINS
    assert len({origin.evidence_reference for origin in origins}) == TWO_ORIGINS
    assert len({str(origin.confidence) for origin in origins}) == TWO_ORIGINS
    assert origins[0].source_type is SourceType.DOCUMENT
    assert origins[1].source_type is SourceType.STRUCTURED_METADATA


def test_a_timestamp_in_a_non_utc_zone_crosses_assembly_with_its_own_offset() -> None:
    """Normalising to UTC preserves the instant and destroys the record of
    where it was recorded. The MVP's regime is Indian (`CLAUDE.md` §B.7), and
    +05:30 is the offset a UTC conversion would silently erase.
    """
    recorded_locally = datetime(2026, 8, 5, 14, 30, tzinfo=IST)
    field = a_detected_field(provenance=a_provenance(timestamp=recorded_locally))
    result = assemble(
        parts=parts_carrying(
            detected_fields=(field,),
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=HIGH),),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    carried = result.structured_document.detected_fields[0].provenance.timestamp
    assert carried == recorded_locally
    assert carried.utcoffset() == timedelta(hours=5, minutes=30)
    assert carried.tzinfo is recorded_locally.tzinfo


def test_a_detected_table_keeps_its_own_provenance_and_its_rows_verbatim() -> None:
    """Tables are the second kind of fact in the Structured Document and they
    carry their own origin. A row list rebuilt "for consistency" would be a
    quiet rewrite of what the document says.
    """
    rows = (("Item", "Qty", "Amount"), ("Bolt M8", "3", "0"), ("Washer", "", "12.50"))
    table = DetectedTable(rows=rows, provenance=a_provenance(evidence_reference="page 1, table 1"))
    result = assemble(
        parts=parts_carrying(detected_tables=(table,)),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
    )

    carried = result.structured_document.detected_tables[0]
    assert carried.rows == rows
    assert carried.provenance.evidence_reference == "page 1, table 1"
    assert carried.provenance.source_type is SourceType.DOCUMENT


# ═══════════════════════════════════════════════════════════════════════════
# INV-11 · a human note is evidence, not truth.
# "It may never be treated as confirmed fact ... A human note may never raise
# Evidence Reliability simply by existing."
# ═══════════════════════════════════════════════════════════════════════════


def a_human_note(*, text: str = "Advance paid to supplier.") -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=text,
        provenance=a_provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-42",
            evidence_reference="message 3",
            confidence=MAX,
        ),
    )


def test_a_human_note_crosses_assembly_verbatim_including_its_surrounding_whitespace() -> None:
    """*"Stored verbatim"* (INV-11). Trimming is the smallest possible edit
    and it is still an edit to a piece of evidence about what a person wrote.
    """
    typed = "  This payment settles Invoice 481.\n"
    note = a_human_note(text=typed)
    result = assemble(
        parts=parts_carrying(),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
        human_business_context=note,
    )

    assert result.human_business_context is not None
    assert result.human_business_context.original_user_text == typed
    assert result.human_business_context.provenance.source_type is SourceType.HUMAN


def test_a_human_note_is_recorded_as_a_human_claim_and_never_inside_the_reading() -> None:
    """`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 1's last row: recording THAT
    a user said something is an observation; recording WHAT they said as true
    is an interpretation, and *"once the quotation marks are gone, nothing
    downstream can tell which happened."*

    The quotation marks here are structural — the note lives in its own
    field, under its own `Human` origin. The attack is a sentinel: if a single
    character of the note reached the Structured Document, it would be
    indistinguishable from something read off the artifact.
    """
    sentinel = "SENTINEL-4f2a-this-sentence-was-typed-by-a-person"
    result = assemble(
        parts=parts_carrying(
            detected_fields=(a_detected_field(),),
            confidence_scores=(FieldConfidence(field_name="Amount", confidence=HIGH),),
        ),
        identity=an_identity(),
        source_references=("upload:x.pdf",),
        human_business_context=a_human_note(text=sentinel),
    )

    assert sentinel not in result.structured_document.model_dump_json()
    assert sentinel not in result.confidence_report.model_dump_json()
    assert result.human_business_context is not None
    assert result.human_business_context.original_user_text == sentinel
    # The reading itself never claims a human origin.
    assert all(
        field.provenance.source_type is not SourceType.HUMAN
        for field in result.structured_document.detected_fields
    )


def test_supplying_a_human_note_raises_no_confidence_anywhere_in_the_artifact() -> None:
    """The same sub-engine outputs, twice, differing only in whether a note
    was supplied. Every confidence must be identical, and so must every
    marker — a note that made the reading look better, or made a doubt look
    smaller, is the failure INV-11's last line exists to forbid.
    """
    field, score = a_field_and_its_score("Amount", LOW)
    doubt = UncertaintyMarker(subject="Amount", reason="the totals block is faint")
    parts = parts_carrying(
        detected_fields=(field,), confidence_scores=(score,), uncertainty_markers=(doubt,)
    )
    identity = an_identity()

    without_note = assemble(parts=parts, identity=identity, source_references=("upload:x.pdf",))
    with_note = assemble(
        parts=parts,
        identity=identity,
        source_references=("upload:x.pdf",),
        human_business_context=a_human_note(),
    )

    reading_scores = {
        key: value
        for key, value in every_confidence_as_written(with_note).items()
        if key != "provenance:human_business_context"
    }
    assert reading_scores == every_confidence_as_written(without_note)
    assert with_note.confidence_report == without_note.confidence_report
    assert with_note.structured_document == without_note.structured_document
    assert without_note.human_business_context is None


def test_a_human_claim_filed_as_a_detected_field_is_refused_by_assembly_not_relabelled() -> None:
    """The merge INV-11 forbids, attempted through the front door. Assembly's
    correct behaviour is to let the artifact refuse it — relabelling the
    origin to `Document` to make it fit would be the merge, performed
    silently, by the one component that is not allowed to author anything.
    """
    laundered = a_detected_field(
        name="Settles Invoice",
        value="481",
        provenance=a_provenance(source_type=SourceType.HUMAN, source_id="chat:session-42"),
    )
    with pytest.raises(ValidationError):
        assemble(
            parts=parts_carrying(
                detected_fields=(laundered,),
                confidence_scores=(FieldConfidence(field_name="Settles Invoice", confidence=HIGH),),
            ),
            identity=an_identity(),
            source_references=("upload:x.pdf",),
        )


# ═══════════════════════════════════════════════════════════════════════════
# P5 · no component, parent Input Engine included, may raise or lower a score
# the `confidence` sub-engine produced. Attacked through `assemble` itself,
# rather than through the schema directly, because assembly is the component
# P5 names and reconciling here is what it forbids.
# ═══════════════════════════════════════════════════════════════════════════


def test_assembly_refuses_a_disagreement_rather_than_picking_a_side() -> None:
    field = a_detected_field(name="Amount", provenance=a_provenance(confidence=HIGH))
    disagreeing = FieldConfidence(field_name="Amount", confidence=LOW)

    with pytest.raises(ValidationError) as raised:
        assemble(
            parts=parts_carrying(detected_fields=(field,), confidence_scores=(disagreeing,)),
            identity=an_identity(),
            source_references=("upload:x.pdf",),
        )

    # The refusal names BOTH numbers, so a reader can see which two sources
    # disagreed rather than being told one is wrong.
    message = str(raised.value)
    assert "0.9800" in message
    assert "0.1000" in message


def test_a_reading_with_no_score_at_all_is_refused_rather_than_scored_by_assembly() -> None:
    """The other half of P5. A field arriving without a Confidence Report
    entry has no reliability the artifact can state; assembly inventing one
    would be the parent authoring a sub-engine's output (INV-10).
    """
    with pytest.raises(ValidationError) as raised:
        assemble(
            parts=parts_carrying(detected_fields=(a_detected_field(name="Amount"),)),
            identity=an_identity(),
            source_references=("upload:x.pdf",),
        )
    assert "Amount" in str(raised.value)


def test_the_four_input_contracts_are_frozen_so_assembly_cannot_edit_one_in_place() -> None:
    """Immutability is what makes "assembly changed nothing" checkable at all:
    a mutable input could be edited before use and the test would compare the
    edited value against itself.

    `setattr` with the name in a variable rather than a literal attribute
    assignment, because a literal one is a static type error and would have
    to be silenced — and a silenced check is not a check (`CLAUDE.md` §J.4).
    """
    contracts = (CleanerOutput, ReaderOutput, ParserOutput, ConfidenceOutput, SubEngineOutputs)
    for contract in contracts:
        assert is_dataclass(contract), contract.__name__

    instances_and_attributes = (
        (a_cleaner_output(), "preservation_status"),
        (a_reader_output(), "raw_extracted_text"),
        (a_parser_output(), "document_structure"),
        (a_confidence_output(), "reliability_information"),
        (parts_carrying(), "cleaner"),
    )
    for instance, attribute in instances_and_attributes:
        with pytest.raises((AttributeError, TypeError)):
            setattr(instance, attribute, "rewritten")


def test_the_confidence_report_component_is_frozen_after_assembly() -> None:
    """`COMMUNICATION_RULES_INPUT_ENGINE.md` §4 item 6 — a downstream engine
    may not "remove uncertainty from, or change confidence in" the artifact.
    Enforced by the type, not by the receiving engine's good behaviour.
    """
    result = assemble(
        parts=parts_carrying(), identity=an_identity(), source_references=("upload:x.pdf",)
    )
    assert isinstance(result.confidence_report, ConfidenceReport)
    for attribute, value in (("risky_fields", ("Amount",)), ("reliability_information", "rosy")):
        with pytest.raises(ValidationError):
            setattr(result.confidence_report, attribute, value)
