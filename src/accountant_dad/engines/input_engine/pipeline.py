"""The Input Engine's own runner — the box the assembly diagram draws around
`cleaner`, `reader`, `parser` and `confidence`, made real.

`SUB_ENGINE_RESPONSIBILITIES.md`, the boxed note above §1.1: *"The four
sub-engines below produce four parts. The Input Engine itself combines them
into the Document Evidence Object and assigns the Document ID. It owns the
internal assembly of its own sub-engines' outputs and nothing more — not
system-wide orchestration, engine routing, downstream reasoning, accounting
decisions, or workflow control."* `assembly.py` already does the mechanical
half of that — combining four already-produced parts into one artifact. This
module is the other half: it actually CALLS the four sub-engines, in the order
`ENGINE_1_INPUT_ENGINE_RULES.md:372-382` draws them, on one real document, and
hands what they produced to `assembly.assemble`. Nothing here reasons about a
transaction, routes to another engine, or decides anything `cleaner`, `reader`,
`parser` or `confidence` did not already decide.

FOUR REAL DEFECTS, FOUND BY ACTUALLY WIRING THESE MODULES TOGETHER. DEFECT 1 IS
NOW FIXED AND DEFECT 4 IS HALF FIXED; 2 AND 3 STAND. Every one is measured
below, not assumed.

  1. FIXED — `reader`'S READING IS NOW `parser`'S INPUT (`KNOWN_FAILURES.md`
     F-019, the unfixed half of F-012). It used to read: "`reader` AND `parser`
     EACH RE-OPEN THE RAW DOCUMENT; NEITHER CONSUMES THE OTHER'S OUTPUT", and
     the consequence was that no producer in Engine 1 held a NAME and a
     CONFIDENCE for the same value — `reader.TextRegion` had the score and no
     name, `parser.Region` had a label and no score — so `parser_output`
     returned `detected_fields=()` and every extracted value crossed the
     Input → Understanding boundary as a bare `str` inside `extracted_text`,
     carrying no source, no confidence and no uncertainty of its own. That is
     what `COMMUNICATION_RULES_INPUT_ENGINE.md:111` forbids stripping and what
     `ENGINE_1_INPUT_ENGINE_RULES.md:245` forbids emitting.

     `run` now converts `reader`'s regions with `extracted_regions` below and
     hands them to `parser.parse`, which is `SUB_ENGINE_RESPONSIBILITIES.md`
     §1.3's stated input — *"raw extracted information with source locations
     from `reader`"* — and `parser` maps each into a named `MappedField` that
     *"retains the source reference for every mapped value"* (§1.3 Failure
     Behaviour). `detected_fields` below then builds a real
     `evidence.DetectedField` per mapped value, and `parsed_fields` builds the
     matching `confidence_report.ParsedField`, so the score on a field's own
     provenance and the score in the Confidence Report are the SAME object.
     `DocumentEvidenceObject._every_reading_is_scored_and_the_scores_agree`
     refuses the artifact if they ever stop being.

     WHAT IS STILL NOT PIPED, STATED PLAINLY: `parser.parse` still ALSO opens
     the document, because `reader` reports spans and Docling reports layout,
     and only Docling reports the layout. `reader.read` still takes `bytes`
     rather than `cleaner`'s object. Neither costs traceability any more — the
     values that cross now carry their own origin — and both are recorded in
     `parser.py`'s own docstring as work outstanding.

  2. `cleaner.decode` CANNOT DECODE A PDF AT ALL. Measured directly against a
     PDF built the same way `test_input_engine_parser.py` builds its fixtures:
     `cv2.imdecode` returns `None` for real PDF bytes (PDF is not a format
     OpenCV's image codecs recognise), so `cleaner.decode` raises
     `UndecodableArtifactError` on every PDF, unconditionally. `cleaner`'s own
     specification lists PDF as an accepted input (`SUB_ENGINE_RESPONSIBILITIES.md`
     §1.1, `ENGINE_1_INPUT_ENGINE_RULES.md` §4), but its actual format
     normalisation only covers the raster formats OpenCV's codecs understand.
     Without a workaround, no PDF could ever complete this pipeline, which
     would make Engine 1 unable to process its own MVP input (`CLAUDE.md` §B.7,
     "MVP: integrated into Tally, Indian GST regime" — Indian GST documents are
     overwhelmingly PDF). This module works around it the smallest way that
     uses only already-approved tools: for a PDF it renders the FIRST page to a
     PNG with PyMuPDF (`TECHNOLOGY_STACK.md` already names PyMuPDF for Engine 1,
     and `reader.py` already depends on it for the identical operation on its
     own OCR-fallback path) at the caller's own `render_dpi` — never a second,
     invented number — and hands `cleaner` that. `cleaner` then genuinely
     cleans real pixels rendered from the real document; it does not receive a
     placeholder. Multi-page PDFs are cleaned on their first page only — a
     second, narrower limit, forced by `confidence_report.record_confidence`
     itself accepting exactly one `CleanedDocument`, not one per page.

  3. FIXED ON BOTH SIDES — AN UNSCORED REGION IS NOW CARRIED AND MARKED,
     NOT DROPPED. This entry used to read: "`confidence_report.RegionReading`
     CANNOT REPRESENT A SINGLE REGION `reader.read_pdf_text_layer` PRODUCES",
     because `RegionReading` required `text` and `extraction_confidence` to be
     absent together or present together — so text with no score raised
     `MalformedSignalError`, every time, for every region a text layer
     produces. That invariant was correct for OCR and wrong for a PDF text
     layer, whose entire design (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER
     IS `None`") is to report real, successfully-read text with honestly NO
     per-region score, because no recogniser ran to produce one.

     `confidence_report.ReadingState` now names three states rather than two —
     `UNREAD`, `READ_AND_SCORED`, `READ_BUT_UNSCORED` — the same
     absent/zero/unread discipline `measurement.AbsentType` established for
     F-005. `RegionReading` refuses only the one pairing that has no honest
     meaning, a confidence with no text.

     `region_readings` below therefore filters NOTHING any more, and its own
     docstring carries the before/after measurement. What the removed filter
     cost, measured on three text-layer regions: three `UncertaintyMarker`s
     that `_unscored_region_markers` was ready to produce never reached the
     artifact, and `reliability_information` published "0 of 0 region(s)
     reader attempted" for a document holding three of them. The first is
     concealed uncertainty (`ENGINE_1_ARCHITECTURE.md` P-F3); the second is a
     fabricated denominator (Law 24). Both are now carried. Still no score is
     invented for those regions — `ENGINE_1_INPUT_ENGINE_RULES.md:337` — the
     absence is named instead.

     A SHARPER VERSION OF THE ORIGINAL GAP SURVIVES AND IS UNCHANGED. Even a
     `RegionReading` that carries a real OCR score never becomes a
     `confidence_scores` entry by that route: `record_confidence`'s
     `_field_confidence_scores` reads ONLY its `parsed_fields` argument, and
     `reader_regions` feeds the marker functions exclusively. So a document
     level score still reaches the report only through a named, scored
     `ParsedField` — which defect 1's fix is what finally makes exist. Pinned
     as `test_a_real_region_reading_with_a_score_still_carries_no_document_
     level_score`, so a future change that quietly closes or widens that gap
     is noticed.

  4. HALF FIXED — A NAMED, SCORED FIELD NOW EXISTS. A TABLE STILL DOES NOT, AND
     NEITHER DOES AN UNSCORED READING.

     `evidence.DetectedField` and `DetectedTable` each require a complete
     `Provenance` (INV-11, no optional field), a `Confidence` value among them.
     Defect 1's fix supplies both halves for a value `reader` SCORED: `parser`
     assigns the name, `reader` measured the score, and `detected_fields` below
     builds the field from those two without inventing either. Nothing here
     mints a number — `ENGINE_1_INPUT_ENGINE_RULES.md:109` gives only
     `confidence` that authority, and this module carries the exact `Decimal`
     `reader` returned.

     TABLES ARE UNCHANGED. `parser.Cell` knows its row, its column and its box;
     it does not know it holds an amount, and no sub-engine scores it. So
     `parser_output` still returns `detected_tables=()`, for exactly the reason
     it used to return no fields, and every table's cells and bands still reach
     the artifact through `StructuredDocument.document_structure`.

     AN UNSCORED READING STILL CANNOT BECOME A FIELD, AND THIS IS THE ONE THAT
     MATTERS FOR THE MVP. `reader.read_pdf_text_layer` sets
     `extraction_confidence=None` on every region by design (`reader.py`, "THE
     CONFIDENCE OF A TEXT LAYER IS `None`" — the absence of a measurement, not
     zero and not full), and a PDF text layer is the MVP's primary input.
     `Provenance.confidence` is mandatory and `accountant_dad.confidence
     .Confidence` has no member meaning "not measured", so there is no honest
     value to put there: `1.0000` is the default
     `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids ("never to a default 'good
     enough' value") and `0.0000` asserts a measured worthlessness nobody
     measured. `ENGINE_1_INPUT_ENGINE_RULES.md:245` settles what to do about it
     — *"a value carried without all three is not evidence and must not be
     emitted"* — so `detected_fields` and `parsed_fields` below both skip an
     unscored mapping rather than guess a number for it. `ENGINE_1_CONFIDENCE_
     PARAMETERS.md` lists sixteen parameters awaiting a value and none of them
     covers this case, so the number cannot be looked up either.

     THE CONSEQUENCE, STATED RATHER THAN HIDDEN: on the text-layer route the
     text still crosses inside `extracted_text` while `detected_fields` is
     empty, which is the state `KNOWN_FAILURES.md` F-019 names and which this
     module cannot close on its own. Closing it needs a §M amendment to a frozen
     P2 schema — an absent-measurement state on `Provenance.confidence`,
     mirroring the `measurement.AbsentType` precedent that resolved F-005 — and
     that is the owner's decision, not this module's. Pinned as
     `test_an_unscored_reading_is_skipped_rather_than_given_an_invented_score`.

THE BOUNDARIES THIS MODULE HOLDS ITSELF TO.
    Internal orchestration only. This file calls Engine 1's own four
    sub-engines, in order, on one document, and hands their real return values
    to `assembly.assemble`. It never calls another engine, never decides
    accounting treatment, and never routes a workflow — that is the
    Application Layer's, per `CLAUDE.md` §O, "Reasoning is separate from
    workflow. Orchestration belongs to the Application Layer." Running one
    engine's own four stages is not that.

    Transforms nothing. Every function below that touches a sub-engine's real
    output (`cleaner_output`, `reader_output`, `parser_output`,
    `confidence_output`, `region_readings`, `extracted_regions`,
    `parsed_fields`, `detected_fields`, `missing_fields`) repackages a value
    into the shape the next call needs; none of them rounds, clamps,
    reinterprets or recomputes a value a sub-engine produced. `region_readings`
    drops nothing at all (see defect 3); it never edits what it carries.
    `extracted_regions` performs the one conversion in this file
    that changes a number — `page_index + 1` — and that is a change of UNITS
    between two modules' conventions, not a change of value; it is made once,
    and `parser.BoundingBox` refuses a page below 1 so omitting it fails loudly.
    `detected_fields` and `parsed_fields` put the identical `Decimal` object
    `reader` measured on both the field's provenance and the Confidence Report,
    so the two agree by construction rather than by care.

    No numeric literal is used as a threshold anywhere in this file.
    `PipelineSettings` carries every number this module passes to a
    sub-engine — `cleaner_settings`, `render_dpi`, `vision_fallback_threshold`,
    `table_structure` — and none of them has a default here that is not
    already that sub-engine's own established default (`table_structure=None`
    mirrors `parser.parse`'s own signature, tested there as "do not run the
    detector", never a chosen number).

    A provided source passes through untouched. The optional
    `human_business_context` is never handed to `cleaner`, `reader` or
    `parser` — those three sub-engines only ever see the primary document's
    `bytes`. It travels, verbatim, straight into `confidence_report`'s capture
    fidelity check and into `assembly.assemble`, exactly as
    `ENGINE_1_INPUT_ENGINE_RULES.md` §1.2/§1.3 require for a typed note.

    Never fabricates, never continues on partial reasoning. Each of the five
    stages below (`cleaner`, `reader`, `parser`, `confidence`, `assembly`) is
    wrapped in its own `try`/`except`. The first one that raises stops the
    pipeline immediately: `PipelineStageError` names exactly which stage
    failed and carries a `PipelinePartialResult` holding every earlier stage's
    real output, unmodified — nothing already produced is thrown away, and
    nothing later in the chain is invented to paper over the gap.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import pymupdf

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DocumentEvidenceObject,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine import assembly, cleaner, confidence_report, parser, reader
from accountant_dad.identity import IdentityEnvelope

# ── a typed facade over PyMuPDF's untyped API ─────────────────────────────
#
# `reader.py` already declares an identical facade for the identical reason:
# PyMuPDF ships `py.typed` but leaves its functions unannotated, so
# `mypy --strict` refuses a bare call, and this repository's zero-new-
# suppressions gate rules out silencing it per line. `reader._PdfDocument`
# and friends are module-private to `reader.py` and are not imported here —
# duplicating the few lines a second untyped dependency-boundary needs is the
# same choice `reader.py` itself made about PyMuPDF, not a second definition
# of a shared concept (Law 14 governs LOGIC; a type declaration for an
# external library's surface is not logic).


class _Pixmap(Protocol):
    def tobytes(self, output: str) -> bytes: ...


class _Page(Protocol):
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...


class _PdfDocument(Protocol):
    def __getitem__(self, index: int) -> _Page: ...
    def close(self) -> None: ...


class _OpenPdf(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _PdfDocument: ...


_open_pdf = cast(_OpenPdf, pymupdf.open)

#: `parser.parse` opens the file Docling receives by its extension; Docling
#: reads that extension to pick a backend. Two entries only, matching
#: `reader.MediaType`'s own two members exactly.
_TEMP_FILE_SUFFIX: dict[reader.MediaType, str] = {
    reader.MediaType.PDF: ".pdf",
    reader.MediaType.IMAGE: ".png",
}


class PipelineError(RuntimeError):
    """The base of every error this module raises on the caller's behalf."""


class PipelineStageError(PipelineError):
    """One named Engine 1 stage could not complete.

    Names the stage, carries the underlying exception as `cause`, and
    preserves every earlier stage's real, unmodified output on `preserved` —
    the same "name it, keep what already exists" shape
    `assembly.MissingSubEngineOutputError` already uses for the same reason:
    nothing already produced is thrown away, and no later stage ever runs.
    """

    def __init__(self, stage: str, cause: Exception, preserved: PipelinePartialResult) -> None:
        self.stage = stage
        self.cause = cause
        self.preserved = preserved
        super().__init__(
            f"Engine 1's pipeline stopped at the {stage!r} stage: {cause}. "
            "Whatever earlier stages already produced is preserved on this "
            f"exception's `preserved` attribute; nothing stands in for "
            f"{stage!r}, and no stage after it ran."
        )


@dataclass(frozen=True, slots=True)
class PipelinePartialResult:
    """Whichever of the four sub-engines' real outputs completed before a
    stage failed. Every field starts `None`, meaning that stage never ran;
    `run` fills each in, in order, only once the stage it names has actually
    returned — never before, and never with a placeholder.
    """

    cleaned: cleaner.CleanedDocument | None = None
    reading: reader.Reading | None = None
    parsed: parser.ParsedStructure | None = None
    confidence: ConfidenceReport | None = None


@dataclass(frozen=True, slots=True)
class PipelineSettings:
    """Every number and setting this module passes to a sub-engine.

    All four are the caller's. None acquires a value here: `cleaner_settings`
    and `table_structure` are the exact settings objects `cleaner.clean` and
    `parser.parse` already require and validate themselves; `render_dpi` is
    the one number reused for two purposes — rasterising a PDF page for
    `cleaner` (defect 2 above) and, unchanged, handed on to `reader.read` for
    its own OCR-fallback rasterisation — never two different numbers invented
    for what is the same physical quantity; `vision_fallback_threshold` is
    `reader.read`'s own required threshold, passed straight through.

    `table_structure` defaults to `None` because `parser.parse` itself
    defaults it to `None`, tested there as "the default must be None — 'do not
    run it'" — mirroring an existing default is not choosing a number.
    """

    cleaner_settings: cleaner.CleanerSettings
    render_dpi: int
    vision_fallback_threshold: Decimal
    table_structure: parser.TableStructureSettings | None = None


@dataclass(frozen=True, slots=True)
class DocumentIntake:
    """The engine-boundary facts about one document: its bytes, its declared
    media type, and the source references it will be filed under.

    Bundled into one object so `run`'s own argument count stays inside this
    repository's `PLR0913` ceiling without folding two unrelated concerns
    (what the document IS, versus how it should be processed) into one
    parameter. `media_type` is declared by the caller and never sniffed from
    the bytes (`CLAUDE.md` Law 23 — external input is untrusted, and guessing
    a document's type from its bytes is exactly the guess `reader.py` already
    refuses to make).
    """

    document: bytes
    media_type: reader.MediaType
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_references:
            raise ValueError(
                "source_references must name at least one source: parser "
                "needs exactly one to say what it parsed, and "
                "DocumentEvidenceObject's own schema refuses an empty tuple "
                "regardless. Refused here, before any sub-engine runs."
            )


#: The caller declares a `reader.MediaType`; `cleaner` speaks `MediaKind`. One
#: mapping, in one place, so the two vocabularies cannot drift.
_MEDIA_KIND: dict[reader.MediaType, cleaner.MediaKind] = {
    reader.MediaType.PDF: cleaner.MediaKind.PDF,
    reader.MediaType.IMAGE: cleaner.MediaKind.IMAGE,
}


def _payload_of(cleaned: cleaner.CleanedDocument) -> bytes:
    """The cleaned artifact's own bytes, or a loud failure.

    `clean_artifact` always sets `artifact`; this refuses rather than falling
    back to the original, because falling back is precisely the bypass this
    migration removed. A silent fallback would restore the two-pipeline
    architecture while every test still passed (Law 11, §J.(a)).
    """
    if cleaned.artifact is None:
        raise PipelineError(
            "cleaner returned no media-aware artifact. The pipeline reads the "
            "CLEANED document, never the original, so there is nothing safe to "
            "continue with. Refused rather than silently re-reading the intake, "
            "which would reinstate the bypass that F-017 removed."
        )
    return cleaned.artifact.payload


def region_readings(reading: reader.Reading) -> tuple[confidence_report.RegionReading, ...]:
    """EVERY `reader.TextRegion`, mapped into `confidence_report`'s own
    contract. Nothing is filtered. See the module docstring, defect 3.

    A region `reader` scored becomes a `RegionReading` carrying that EXACT
    `Decimal`, unrounded and unrenamed — confidence is never raised, lowered
    or invented here. A region `reader` read but did NOT score
    (`extraction_confidence is None`, every region a PDF text layer produces)
    now becomes one too, in state `READ_BUT_UNSCORED`, and
    `confidence_report._unscored_region_markers` turns each into an
    `UncertaintyMarker` naming its location.

    THIS FUNCTION USED TO DROP EXACTLY THOSE REGIONS, AND THE REASON IT GAVE
    HAS SINCE STOPPED BEING TRUE. `RegionReading` once refused text without a
    score outright — text-with-no-confidence could only mean "unread", so
    building one raised `MalformedSignalError` — and dropping the region was
    the least dishonest option available. `confidence_report.ReadingState`
    gained its third state and that constraint is gone: text with no score is
    now a named, constructible fact rather than a contradiction. The filter
    outlived its cause, and a filter whose reason has expired is a silent
    suppression.

    MEASURED, BEFORE AND AFTER, ON THREE TEXT-LAYER REGIONS:

        with the filter     region_readings -> 0    markers -> 0
                            "0 of 0 region(s) reader attempted..."
        without it          region_readings -> 3    markers -> 3
                            "0 of 3 ... 3 ... read but carry no per-region
                             extraction score"

    Three genuine uncertainty signals were being suppressed, and the count
    `reliability_information` published said `0 of 0` for a document with
    three regions in it — a true-looking sentence about a document that was
    never read that way. `ENGINE_1_ARCHITECTURE.md` P-F3 forbids hiding
    uncertainty and Law 24 forbids the fabricated denominator; this carries
    both instead. No score is invented for these regions and none is implied:
    `extraction_confidence` stays exactly the `None` `reader` reported.
    """
    return tuple(
        confidence_report.RegionReading(
            source_location=repr(region.location),
            text=region.text,
            extraction_confidence=region.extraction_confidence,
        )
        for region in reading.regions
    )


def extracted_regions(reading: reader.Reading) -> tuple[parser.ExtractedRegion, ...]:
    """`reader`'s regions, in `reader`'s own order, shaped as `parser`'s input.

    THE ARROW F-019 SAYS WAS NEVER BUILT. `SUB_ENGINE_RESPONSIBILITIES.md` §1.3
    gives `parser` one input — *"raw extracted information with source locations
    from `reader`"* — and this is it, mapped in exactly one place, the same way
    `region_readings` above maps the same objects onto `confidence_report`'s own
    contract.

    Every value is `reader`'s, unchanged: the text character for character, the
    four edges as floats already are, and `extraction_confidence` as the exact
    `Decimal` object or the exact `None`. Nothing is rounded, clamped or
    defaulted.

    The ONE conversion is a unit, not a value: `reader.SourceLocation.page_index`
    is a 0-based index and `parser.BoundingBox.page` is a 1-based page number, so
    `page_index + 1` is the same page written in the other module's units.
    `parser.BoundingBox` refuses `page < 1`, which makes a forgotten `+ 1` a
    loud failure rather than an off-by-one nobody notices.

    Nothing is filtered. Even a region `reader` scored `None` is handed on, so
    `parser` maps it and its text is nameable and locatable; what cannot be built
    from it is a `DetectedField`, and that decision is made once, later, by
    `detected_fields` — not silently here by dropping the region.
    """
    return tuple(
        parser.ExtractedRegion(
            text=region.text,
            box=parser.BoundingBox(
                page=region.location.page_index + 1,
                left=region.location.left,
                top=region.location.top,
                right=region.location.right,
                bottom=region.location.bottom,
            ),
            extraction_confidence=region.extraction_confidence,
        )
        for region in reading.regions
    )


def parsed_fields(parsed: parser.ParsedStructure) -> tuple[confidence_report.ParsedField, ...]:
    """`parser`'s mapped fields that carry a score, shaped as `confidence`'s input.

    `confidence_report.record_confidence` turns each of these into one
    `FieldConfidence` under the same name, which is what makes a field's score
    findable in the Confidence Report at all. Before this existed `run` passed a
    literal `()` here (F-019, mechanism line 2 of 3) and no document field was
    ever scored.

    A mapping `reader` did not score is EXCLUDED rather than given a number —
    see defect 4 in the module docstring for why no honest number exists, and
    why inventing one is forbidden rather than merely undesirable. Its text is
    not lost: it still reaches `StructuredDocument.extracted_text` through
    `reader_output`.

    The confidence carried is the identical object `reader` produced.
    `_field_confidence_scores` then mirrors it into the report unmodified, and
    `detected_fields` below puts the SAME object on the field's own provenance,
    so the two can never disagree by construction rather than by care.
    """
    return tuple(
        confidence_report.ParsedField(
            field_name=field.name, extraction_confidence=field.extraction_confidence
        )
        for field in parsed.mapped_fields
        if field.extraction_confidence is not None
    )


def detected_fields(
    parsed: parser.ParsedStructure, *, recorded_at: datetime
) -> tuple[DetectedField, ...]:
    """`parser`'s mapped fields that carry a score, as real Document Evidence.

    THE THREE THINGS RULE 4 REQUIRES, EACH FROM THE SUB-ENGINE THAT OWNS IT:

        source       `provenance.source_id` is `parser`'s own
                     `source_reference` — WHICH artifact — and
                     `provenance.evidence_reference` is the mapped field's
                     `source_location`, `reader`'s own coordinates — WHERE
                     within it. `ENGINE_1_INPUT_ENGINE_RULES.md:511`: a source
                     location is emitted even for a low-confidence extraction,
                     "that is what makes a later human check possible."
        confidence   `reader`'s measured score, the exact object, never
                     recomputed here (`ENGINE_1_INPUT_ENGINE_RULES.md:109`).
        uncertainty  answerable because the same name carries a
                     `FieldConfidence` in the Confidence Report — see
                     `parsed_fields` above, and
                     `DocumentEvidenceObject._every_reading_is_scored_and_the_
                     scores_agree`, which refuses the artifact if a detected
                     field's name is missing from the report or its score
                     disagrees with the report's.

    `source_type` is `Document` because every one of these was read off the
    artifact. A human note is never routed here: `StructuredDocument`'s own
    `_reject_human_origin` refuses a `Human` provenance among detected fields,
    which is `ENGINE_1_INPUT_ENGINE_RULES.md:233`'s no-merge rule made
    structural.

    `corroborated` is `not assessed`, verbatim, because Engine 1 cannot assess
    whether another source supports a value — deciding that is interpretation
    (`ENGINE_1_INPUT_ENGINE_RULES.md:295`).

    `recorded_at` is the caller's clock, never `datetime.now()` reached for
    here. `services/pipeline.py`'s `Sources` already fixed that rule for this
    repository — *"a module calling `uuid4()` or `datetime.now()` cannot offer
    [reproducibility], and nothing downstream could tell a real difference from
    a fresh random number."* Measured consequence, not a stylistic one: with a
    clock read inside this function, two runs of the identical document produce
    two different `StructuredDocument`s, and
    `test_the_same_input_twice_is_identical_content_but_the_second_run_is_a_
    new_version` goes red.

    A mapping with no score yields no field at all, for the reason defect 4
    gives. That is the disjunction `ENGINE_1_INPUT_ENGINE_RULES.md:245` states:
    all three, or it is not evidence.
    """
    return tuple(
        DetectedField(
            name=field.name,
            value=field.value,
            provenance=Provenance(
                source_type=SourceType.DOCUMENT,
                source_id=parsed.source_reference,
                evidence_reference=field.source_location,
                timestamp=recorded_at,
                confidence=field.extraction_confidence,
                corroborated=Corroborated.NOT_ASSESSED,
            ),
        )
        for field in parsed.mapped_fields
        if field.extraction_confidence is not None
    )


def missing_fields(parsed: parser.ParsedStructure) -> tuple[confidence_report.MissingField, ...]:
    """`parser`'s missing field information, mapped into `confidence_report`'s
    own contract.

    `parser.parse` is given no expected-field list (`parser.py`,
    "WHICH FIELDS A DOCUMENT MUST CARRY IS KNOWLEDGE") and today always
    reports zero absent fields — this always returns an empty tuple as a
    consequence of that fact, not a choice made here, and stays ready for the
    day `parser`'s real `absent_fields` carries something.
    """
    return tuple(
        confidence_report.MissingField(field_name=name, state="absent")
        for name in parsed.missing_field_information.absent_fields
    )


def document_structure_text(parsed: parser.ParsedStructure) -> str:
    """`parser`'s real structural findings, rendered as one traceable string.

    `StructuredDocument.document_structure` is a plain `str`; there is no
    named-field slot for `parser`'s geometry to land in (defect 4). Every
    region's label, text and box, and every table's cells and bands, are
    written into this string rather than dropped — the one channel available
    that keeps them present, and searchable, in the final artifact.
    """
    lines = [f"page_count={parsed.page_count}"]
    for region in parsed.regions:
        lines.append(f"region label={region.label!r} text={region.text!r} box={region.box!r}")
    for index, table in enumerate(parsed.tables):
        lines.append(
            f"table[{index}] detector={table.detector!r} "
            f"rows={table.row_count} columns={table.column_count} box={table.box!r}"
        )
        for cell in table.cells:
            lines.append(
                f"  cell rows={cell.row_start}:{cell.row_end} "
                f"columns={cell.column_start}:{cell.column_end} text={cell.text!r}"
            )
        for band in table.bands:
            lines.append(f"  band label={band.label!r} score={band.score!r} box={band.box!r}")
    return "\n".join(lines)


def cleaner_output(cleaned: cleaner.CleanedDocument) -> assembly.CleanerOutput:
    """`cleaner`'s real output, packaged for `assembly.SubEngineOutputs`.

    `preservation_status` and every quality observation are `cleaner`'s own
    values, carried through as strings unchanged — nothing here recomputes or
    reinterprets a measurement `cleaner` already made.
    """
    return assembly.CleanerOutput(
        cleaned_document_representation=cleaned.cleaned,
        quality_issues_detected=tuple(
            f"{observation.name}[{observation.stage.value}]={observation.value}"
            for observation in cleaned.quality_observations
        ),
        preservation_status=cleaned.preservation_status.value,
    )


def reader_output(reading: reader.Reading) -> assembly.ReaderOutput:
    """`reader`'s real output, packaged for `assembly.SubEngineOutputs`.

    `raw_extracted_text` joins every region's text `reader` returned, in
    `reader`'s own order (`reader.py` §1.2 — reordering is forbidden, and this
    never sorts). It is the channel that carries a text-layer region's text
    into `StructuredDocument.extracted_text`. It is no longer the ONLY one that
    mentions such a region: since the `region_readings` filter was removed
    (defect 3) each also reaches the Confidence Report as an
    `UncertaintyMarker` naming its location. What it still cannot become is a
    `DetectedField` — defect 4 — because that needs a score nobody measured.
    """
    return assembly.ReaderOutput(
        raw_extracted_text="\n".join(region.text for region in reading.regions),
        source_locations=tuple(repr(region.location) for region in reading.regions),
        extraction_confidence=tuple(
            str(region.extraction_confidence) for region in reading.regions
        ),
    )


def parser_output(
    parsed: parser.ParsedStructure, *, recorded_at: datetime
) -> assembly.ParserOutput:
    """`parser`'s real output, packaged for `assembly.SubEngineOutputs`.

    `detected_fields` now carries one field per SCORED mapped value — see
    `detected_fields` above, and defect 1 in the module docstring for the arrow
    that made a scored, named value exist at all.

    `detected_tables` is still always empty, and defect 4 says why: a
    `parser.Cell` carries no name and no score, so building one would mean
    inventing both halves. `parser`'s table findings are not lost; every cell
    and band is rendered by `document_structure_text`.
    """
    return assembly.ParserOutput(
        document_structure=document_structure_text(parsed),
        detected_fields=detected_fields(parsed, recorded_at=recorded_at),
        detected_tables=(),
    )


def confidence_output(report: ConfidenceReport) -> assembly.ConfidenceOutput:
    """`confidence`'s real output, packaged for `assembly.SubEngineOutputs`.

    Every field is `report`'s own value, carried through unchanged — this is
    the one place a caller might be tempted to round a score or drop a marker
    that looks redundant, and this function does neither.
    """
    return assembly.ConfidenceOutput(
        confidence_scores=report.confidence_scores,
        uncertainty_markers=report.uncertainty_markers,
        reliability_information=report.reliability_information,
        risky_fields=report.risky_fields,
    )


def _human_capture_evidence(
    human_business_context: HumanBusinessContext | None,
) -> confidence_report.HumanCaptureEvidence | None:
    """The one place `human_business_context.original_user_text` is read on
    its way into `confidence_report.record_confidence` — read, not rewritten;
    the same object is handed to `assembly.assemble` untouched, further down.
    """
    if human_business_context is None:
        return None
    return confidence_report.HumanCaptureEvidence(
        submitted_text=human_business_context.original_user_text,
        stored=human_business_context,
    )


def run(
    intake: DocumentIntake,
    *,
    identity: IdentityEnvelope,
    settings: PipelineSettings,
    recorded_at: datetime,
    human_business_context: HumanBusinessContext | None = None,
) -> DocumentEvidenceObject:
    """Run Engine 1's four sub-engines, in order, on one document, and return
    the Document Evidence Object `assembly.assemble` builds from what they
    produced.

        bytes -> cleaner -> reader -> parser -> confidence_report -> assembly

    `reader`'s reading is `parser`'s input, not merely something that happened
    before it: `extracted_regions(reading)` is handed to `parser.parse`, which
    is the arrow `SUB_ENGINE_RESPONSIBILITIES.md` §1.3 draws and
    `KNOWN_FAILURES.md` F-019 recorded as never built. See defect 1.

    Each of the five stages runs inside its own `try`/`except`. The first one
    to raise stops the pipeline immediately and re-raises as
    `PipelineStageError`, naming that stage and carrying every earlier stage's
    real output on `preserved` (see the module docstring's boundaries
    section) — no stage after the failure ever runs, and nothing is invented
    to let it.

    `intake`, `settings` and `recorded_at` are all required, with no default:
    omitting one raises `TypeError` naming it, before any sub-engine is called.
    `recorded_at` is the timestamp every detected field's `Provenance` carries,
    and it is the caller's clock rather than one read here — see
    `detected_fields` for the measured reason, which is reproducibility, not
    testing convenience. It is deliberately NOT given a "now" default: a
    default clock is exactly the reach-for-entropy `services/pipeline.py`
    forbids, wearing a signature that looks safe.

    `intake` itself refuses at construction if it names no source reference
    (`DocumentIntake.__post_init__`) — also before any sub-engine runs.
    `human_business_context` defaults to `None` because the Human Business
    Description is optional and Engine 1 must work correctly without one
    (`ENGINE_1_INPUT_ENGINE_RULES.md:138`); when supplied, it is never handed
    to `cleaner`, `reader` or `parser` — see the module docstring, "a provided
    source passes through untouched".
    """
    preserved = PipelinePartialResult()

    try:
        cleaned = cleaner.clean_artifact(
            intake.document,
            _MEDIA_KIND[intake.media_type],
            settings.cleaner_settings,
            render_dpi=settings.render_dpi,
        )
    except Exception as exc:
        raise PipelineStageError("cleaner", exc, preserved) from exc
    preserved = replace(preserved, cleaned=cleaned)

    # THE ONE PIPELINE. Everything below reads the CLEANED artifact, never
    # `intake.document`. Before the F-017 migration each stage re-opened the
    # original, because `cleaner` emitted a bitmap and reading a bitmap of a
    # PDF destroys its text layer — so bypassing was correct and the type was
    # wrong. `CleanedArtifact.payload` is the artifact in its own format, so
    # there is no longer any reason to bypass, and no path that does.
    cleaned_document = _payload_of(cleaned)

    try:
        reading = reader.read(
            cleaned_document,
            media_type=intake.media_type,
            render_dpi=settings.render_dpi,
            vision_fallback_threshold=settings.vision_fallback_threshold,
        )
    except Exception as exc:
        raise PipelineStageError("reader", exc, preserved) from exc
    preserved = replace(preserved, reading=reading)

    try:
        parsed = _parse_document(cleaned_document, intake, settings, extracted_regions(reading))
    except Exception as exc:
        raise PipelineStageError("parser", exc, preserved) from exc
    preserved = replace(preserved, parsed=parsed)

    try:
        report = confidence_report.record_confidence(
            cleaned,
            region_readings(reading),
            parsed_fields(parsed),
            missing_fields(parsed),
            _human_capture_evidence(human_business_context),
        )
    except Exception as exc:
        raise PipelineStageError("confidence", exc, preserved) from exc
    preserved = replace(preserved, confidence=report)

    try:
        parts = assembly.SubEngineOutputs(
            cleaner=cleaner_output(cleaned),
            reader=reader_output(reading),
            parser=parser_output(parsed, recorded_at=recorded_at),
            confidence=confidence_output(report),
        )
        return assembly.assemble(
            parts=parts,
            identity=identity,
            source_references=intake.source_references,
            human_business_context=human_business_context,
        )
    except Exception as exc:
        raise PipelineStageError("assembly", exc, preserved) from exc


def _parse_document(
    document: bytes,
    intake: DocumentIntake,
    settings: PipelineSettings,
    regions: tuple[parser.ExtractedRegion, ...],
) -> parser.ParsedStructure:
    """Materialise the CLEANED document and hand it, and `reader`'s regions, to
    `parser.parse`.

    `document` is `CleanedArtifact.payload`, never `intake.document` — that is
    the whole point of the F-017 migration and the reason this parameter
    exists at all. Docling needs a real path, so the bytes are written to a
    temporary file; that is a filesystem detail of this call, not a second
    pipeline. The file is removed whether `parser.parse` succeeds or raises.

    `regions` is what `reader` already extracted from that same cleaned
    payload. Passing it is defect 1's fix: `parser` maps `reader`'s values
    instead of only laying out a document it opened for itself.
    """
    with tempfile.NamedTemporaryFile(
        suffix=_TEMP_FILE_SUFFIX[intake.media_type], delete=False
    ) as handle:
        handle.write(document)
        temp_path = Path(handle.name)
    try:
        return parser.parse(
            temp_path,
            source_reference=intake.source_references[0],
            extracted_regions=regions,
            table_structure=settings.table_structure,
        )
    finally:
        temp_path.unlink(missing_ok=True)
