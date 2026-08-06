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

  4. FIXED FOR FIELDS BY AMENDMENT 5 — AN UNSCORED READING NOW CROSSES, AND
     SAYS IT WAS NEVER SCORED. TABLES STILL DO NOT.

     `evidence.DetectedField` and `DetectedTable` each require a complete
     `Provenance` (INV-11, no optional field), a confidence value among them.
     Defect 1's fix supplies both halves for a value `reader` SCORED: `parser`
     assigns the name, `reader` measured the score, and `detected_fields` below
     builds the field from those two without inventing either. Nothing here
     mints a number — `ENGINE_1_INPUT_ENGINE_RULES.md:109` gives only
     `confidence` that authority, and this module carries the exact `Decimal`
     `reader` returned.

     THE UNSCORED READING WAS THE ONE THAT MATTERED FOR THE MVP, AND IT USED TO
     BE DROPPED. This entry read: "AN UNSCORED READING STILL CANNOT BECOME A
     FIELD." `reader.read_pdf_text_layer` sets `extraction_confidence=None` on
     every region by design (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER IS
     `None`" — the absence of a measurement, not zero and not full), and a PDF
     text layer is the MVP's primary input. `Provenance.confidence` was
     mandatory and `Confidence` had no member meaning "not measured", so there
     was no honest value to put there, and `ENGINE_1_INPUT_ENGINE_RULES.md:245`
     — *"a value carried without all three is not evidence and must not be
     emitted"* — made dropping it the only honest option available.

     `ARCHITECTURE_AMENDMENTS.md` **Amendment 5** (approved 2026-08-06) removed
     the cause rather than the symptom: `Provenance.confidence` and
     `FieldConfidence.confidence` are now `ConfidenceOrUnmeasured`, so the
     absence of a measurement is a value the schema can hold. `_recorded_
     confidence` below is the single place that decision is made — `reader`'s
     exact `Decimal` when it measured one, `UNMEASURED` when it did not — and
     `detected_fields` and `unmeasured_field_scores` both read it, so a field's
     own provenance and its Confidence Report entry cannot disagree about
     whether a measurement exists.

     STILL NO NUMBER IS INVENTED, AND THAT IS THE POINT. `1.0000` is the
     default `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids by name; `0.0000`
     asserts a measured worthlessness nobody measured; none of the sixteen
     parameters in `ENGINE_1_CONFIDENCE_PARAMETERS.md` covers the case. The
     amendment named the absence instead of filling it (Law 54), and
     `DocumentEvidenceObject`'s agreement check now REFUSES an artifact whose
     report claims a number for a reading the provenance says was never scored.

     MEASURED, BEFORE AND AFTER, ON THE TEXT-LAYER ROUTE: `detected_fields` went
     from 0 to one field per mapped region, and the artifact went from ZERO
     `Provenance` objects to one per region. Three tests that were red on
     `99f62bf` are green — the two conformance-registry provenance tests and
     the end-to-end boundary contract.

     TABLES ARE UNCHANGED, AND THE REASON IS DIFFERENT FROM THE ONE ABOVE.
     `parser.Cell` knows its row, its column and its box; it does not know it
     holds an amount, and NO SUB-ENGINE NAMES IT. Amendment 5 supplies a
     confidence state, not a name, so `parser_output` still returns
     `detected_tables=()` — every table's cells and bands still reach the
     artifact through `StructuredDocument.document_structure`.

  5. `ConfidenceReport.confidence_scores` NOW HAS TWO PRODUCERS, AND THIS IS A
     COST, NOT A DESIGN.

     `confidence_report.ParsedField.extraction_confidence` is typed
     `Confidence` — `Decimal` only — so it cannot carry `UNMEASURED`, and the
     `confidence` sub-engine therefore cannot build the report entry for an
     unscored field. `unmeasured_field_scores` below builds those entries here
     instead, and `confidence_output` appends them to what `record_confidence`
     produced.

     WHAT KEEPS THE TWO FROM DRIFTING, structurally rather than by care:
     `ConfidenceReport._each_name_is_scored_once` refuses the artifact if the
     two producers ever emit the same name, and
     `DocumentEvidenceObject._every_reading_is_scored_and_the_scores_agree`
     refuses it if any entry disagrees with its field's own provenance. Both
     guards already existed; neither was added or weakened for this.

     It is still two producers for one component, which is an INV-10 cost.
     Recorded as open item **O11** in `CONFIDENCE_SPECIFICATION.md` §9 and in
     Amendment 5 itself, with the one-annotation fix that closes it. Named
     rather than hidden (Law 26).

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
    `parsed_fields`, `unmeasured_field_scores`, `_recorded_confidence`,
    `detected_fields`, `missing_fields`) repackages a value
    into the shape the next call needs; none of them rounds, clamps,
    reinterprets or recomputes a value a sub-engine produced. `region_readings`
    drops nothing at all (see defect 3), and neither does `detected_fields` any
    more (defect 4); neither edits what it carries. `_recorded_confidence`
    turns `reader`'s `None` into `UNMEASURED`, which is the same fact written
    in the type the artifact schema can hold — the absence of a measurement on
    both sides, never a value becoming another value.
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
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.confidence import UNMEASURED, ConfidenceOrUnmeasured, UnmeasuredType
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


#: THE LINE BETWEEN "THIS DOCUMENT IS BAD" AND "THIS ENGINE IS BROKEN".
#:
#: `APPLICATION_LAYER_CONTRACTS.md:30` draws it and names both sides:
#: *"**Business** — unreadable, corrupt, zero-byte: an object is produced
#: recording the failure. **Runtime** — engine crash: nothing produced,
#: Application Layer restarts."* Every type below is a sub-engine's OWN
#: declared verdict about the DOCUMENT, read off its own docstring — none of
#: this taxonomy is invented here:
#:
#:   `cleaner.UnusableArtifactError`   *"An artifact this module cannot clean
#:                                     without changing what it contains"* —
#:                                     and its subclass `UndecodableArtifact
#:                                     Error`, *"Bytes that are not a decodable
#:                                     image"*, which is the zero-byte case
#:   `reader.UnreadableDocumentError`  *"The document could not be opened or
#:                                     decoded at all"*
#:   `parser.DocumentUnreadableError`  *"The artifact could not be parsed at
#:                                     all"* — whose docstring assigns the
#:                                     conversion to THIS module by name
#:   `pymupdf.FileDataError`           PyMuPDF's own verdict that the FILE's
#:                                     data is broken. Measured: this is what a
#:                                     corrupt PDF raises through the defect-2
#:                                     render step. It is a statement about the
#:                                     document, not a crash in our code, which
#:                                     is the whole test for membership here.
#:
#: EVERYTHING ELSE RAISES, AND THE OMISSIONS ARE DELIBERATE.
#: `VisionFallbackUnavailableError` and `ParserDependencyMissingError` mean a
#: TOOL is missing, not that the document is bad — emitting "unreadable" for
#: those would assert something false about the user's document, which is worse
#: than crashing and is the fabrication `ENGINE_1_INPUT_ENGINE_RULES.md:337`
#: forbids. `ImpossibleSettingError` is a caller mistake.
#: `MalformedSignalError` and `MissingSubEngineOutputError` are Engine 1's own
#: machinery contradicting itself. None of those is a fact about the document.
BUSINESS_FAILURE: tuple[type[Exception], ...] = (
    cleaner.UnusableArtifactError,
    reader.UnreadableDocumentError,
    parser.DocumentUnreadableError,
    pymupdf.FileDataError,
)


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
        if any(not reference.strip() for reference in self.source_references):
            raise ValueError(
                "source_references must not contain a blank entry: a reference "
                "of '' or whitespace names no source, and evidence with no "
                "stated source is not evidence (INV-11). Refused here, before "
                "any sub-engine runs, because a blank reference is invalid on "
                "every path rather than only the one that happens to notice "
                "it: parser._reject_blank refuses it later, "
                "DocumentEvidenceObject's schema refuses it later still, and "
                "on a business failure it reached UncertaintyMarker.subject, "
                "whose NonEmptyText raised out of the very except block that "
                "exists to handle failures -- producing no artifact, no named "
                "stage and no preserved work."
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
    `parser` maps it and its text is nameable and locatable. Since Amendment 5
    it also becomes a real `DetectedField` — `detected_fields` carries the
    absence of a score rather than dropping the value — so this function's
    refusal to filter is no longer merely the least-bad option here; it is what
    makes the value emittable at all.
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


def _recorded_confidence(field: parser.MappedField) -> ConfidenceOrUnmeasured:
    """What the artifact records about ONE mapped value's reliability.

    THE SINGLE PLACE THIS DECISION IS MADE, and that is the whole reason it is a
    function rather than two inline conditionals. `detected_fields` puts the
    result on the field's own `Provenance`; `unmeasured_field_scores` decides
    from the same result whether the Confidence Report needs an entry this
    module must supply. Two call sites, one rule — so the provenance and the
    report cannot disagree about whether a measurement exists, by construction
    rather than by care.

    `reader`'s `None` becomes `UNMEASURED`: the SAME fact, in the type the
    artifact schema can hold since Amendment 5. It is not a conversion of a
    value into another value — there is no value on either side. `reader.py`
    already states what its `None` means (*"NOT zero confidence and NOT full
    confidence - it is the absence of a measurement"*) and this carries exactly
    that, unchanged, across the one boundary where the old schema lost it.

    A score `reader` DID measure is returned as the identical `Decimal` object,
    never rounded, re-typed or re-derived (`ENGINE_1_INPUT_ENGINE_RULES.md:109`
    — only `confidence` may set a score, and this module sets none).
    """
    if field.extraction_confidence is None:
        return UNMEASURED
    return field.extraction_confidence


def parsed_fields(parsed: parser.ParsedStructure) -> tuple[confidence_report.ParsedField, ...]:
    """`parser`'s mapped fields that carry a score, shaped as `confidence`'s input.

    `confidence_report.record_confidence` turns each of these into one
    `FieldConfidence` under the same name, which is what makes a field's score
    findable in the Confidence Report at all. Before this existed `run` passed a
    literal `()` here (F-019, mechanism line 2 of 3) and no document field was
    ever scored.

    A mapping `reader` did not score is excluded HERE and picked up by
    `unmeasured_field_scores` below — it is no longer dropped from the artifact,
    it simply takes the other of the two routes into the same report.
    `confidence_report.ParsedField.extraction_confidence` is typed `Confidence`,
    `Decimal` only, so it cannot carry `UNMEASURED` and the `confidence`
    sub-engine cannot build that entry. See defect 5 in the module docstring,
    and open item O11: closing it is one annotation in a file this change does
    not own.

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


def unmeasured_field_scores(parsed: parser.ParsedStructure) -> tuple[FieldConfidence, ...]:
    """One Confidence Report entry per mapped value NOBODY SCORED, each saying so.

    THE ALTERNATIVE WAS SILENCE, AND SILENCE IS THE WORSE FAILURE. Every
    detected field must appear in the Confidence Report or
    `DocumentEvidenceObject` refuses the artifact (`evidence.py:337-344`).
    Since Amendment 5 an unscored reading DOES become a detected field, so
    without these entries the artifact would be refused outright — and the way
    to make it pass without them would be to exempt unscored fields from the
    check, which is concealed uncertainty about precisely the fields whose
    reliability is least established (`ENGINE_1_ARCHITECTURE.md` P-F3).

    NO NUMBER IS PRODUCED HERE AND NONE COULD BE. Every entry carries the
    `UNMEASURED` sentinel, which is not a score and cannot be compared with
    one: `UnmeasuredType.__bool__` raises rather than reading as falsy, so a
    caller writing `if not score.confidence:` gets a `TypeError` instead of
    silently treating "nobody measured this" as "this measured zero". This
    module therefore does not trespass on the `confidence` sub-engine's sole
    authority to score (`ENGINE_1_INPUT_ENGINE_RULES.md:109`) — it records that
    no score exists, which is a fact about what the sub-engines produced.

    The membership test is `_recorded_confidence`'s own result, not a second
    reading of `extraction_confidence`, so this can never disagree with what
    `detected_fields` put on the provenance.
    """
    return tuple(
        FieldConfidence(field_name=field.name, confidence=UNMEASURED)
        for field in parsed.mapped_fields
        if isinstance(_recorded_confidence(field), UnmeasuredType)
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
        confidence   `_recorded_confidence`'s answer: `reader`'s measured
                     score, the exact object, never recomputed here
                     (`ENGINE_1_INPUT_ENGINE_RULES.md:109`) — or `UNMEASURED`
                     when `reader` scored nothing. Both are statements about
                     reliability; neither is a number this module chose.
        uncertainty  answerable because the same name carries a
                     `FieldConfidence` in the Confidence Report — see
                     `parsed_fields` and `unmeasured_field_scores` above, and
                     `DocumentEvidenceObject._every_reading_is_scored_and_the_
                     scores_agree`, which refuses the artifact if a detected
                     field's name is missing from the report or its entry
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

    NOTHING IS FILTERED, AND THE FILTER THAT USED TO BE HERE IS THE DEFECT
    AMENDMENT 5 REMOVED. This function once read `if field.extraction_
    confidence is not None`, dropping every mapping `reader` had not scored.
    That was correct under the old schema and wrong about the world: it dropped
    EVERY field on the MVP's primary input, because a PDF text layer is
    transcribed rather than recognised and scores nothing at all. The artifact
    carried zero `Provenance` objects and every extracted value crossed the
    Input -> Understanding boundary as a bare `str` inside `extracted_text`,
    stripped of the three things `COMMUNICATION_RULES_INPUT_ENGINE.md:111`
    forbids stripping.

    The disjunction `ENGINE_1_INPUT_ENGINE_RULES.md:245` states — all three, or
    it is not evidence — is now satisfied by CARRYING all three rather than by
    emitting none. The third is carried honestly: "no instrument scored this"
    is what the artifact says, and it says it in a type that cannot be mistaken
    for a number.
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
                confidence=_recorded_confidence(field),
                corroborated=Corroborated.NOT_ASSESSED,
            ),
        )
        for field in parsed.mapped_fields
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
    into `StructuredDocument.extracted_text`. It is no longer the only channel
    such a region has, and no longer the last one it lost: since the
    `region_readings` filter was removed (defect 3) each also reaches the
    Confidence Report as an `UncertaintyMarker` naming its location, and since
    Amendment 5 (defect 4) each also becomes a real `DetectedField` carrying
    `UNMEASURED`. This function is now one of three routes rather than the only
    one, and it is the only one that carries the text verbatim.
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

    `detected_fields` now carries one field per mapped value, scored or not —
    see `detected_fields` above, defect 1 in the module docstring for the arrow
    that made a named value exist at all, and defect 4 for the amendment that
    let an unscored one be emitted rather than dropped.

    `detected_tables` is still always empty, and the reason is NOT the one
    defect 4 fixed: a `parser.Cell` carries no NAME, and Amendment 5 supplied a
    confidence state, not a name. Building one would still mean inventing the
    half nobody produced. `parser`'s table findings are not lost; every cell
    and band is rendered by `document_structure_text`.
    """
    return assembly.ParserOutput(
        document_structure=document_structure_text(parsed),
        detected_fields=detected_fields(parsed, recorded_at=recorded_at),
        detected_tables=(),
    )


def confidence_output(
    report: ConfidenceReport, unmeasured: tuple[FieldConfidence, ...] = ()
) -> assembly.ConfidenceOutput:
    """`confidence`'s real output, packaged for `assembly.SubEngineOutputs`,
    plus the entries for values NOBODY SCORED, which `confidence` cannot build.

    Every value `report` carries is passed through unchanged — this is the one
    place a caller might be tempted to round a score or drop a marker that
    looks redundant, and this function does neither. Nothing is removed,
    reordered or rewritten.

    `unmeasured` is APPENDED, never merged into or reconciled with what
    `record_confidence` produced. It comes from `unmeasured_field_scores`,
    which reads the same `_recorded_confidence` decision `detected_fields`
    used, and it exists here only because
    `confidence_report.ParsedField.extraction_confidence` is typed `Confidence`
    and cannot hold `UNMEASURED` — see defect 5 in the module docstring and
    open item O11. It defaults to `()` so every existing caller keeps its exact
    previous behaviour.

    THE TWO PRODUCERS CANNOT OVERLAP SILENTLY. A name emitted by both would
    make `ConfidenceReport._each_name_is_scored_once` refuse the artifact, and
    an entry disagreeing with its field's own provenance would make
    `DocumentEvidenceObject._every_reading_is_scored_and_the_scores_agree`
    refuse it. Neither guard was added or relaxed for this; both already
    existed, and both fail loudly rather than picking a winner.
    """
    return assembly.ConfidenceOutput(
        confidence_scores=report.confidence_scores + unmeasured,
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


@dataclass(frozen=True, slots=True)
class _RunInputs:
    """The three things `run` was GIVEN that do not change as it proceeds.

    Bundled for the same stated reason `DocumentIntake` above is bundled: to
    keep the two helpers below inside this repository's `PLR0913` argument
    ceiling without folding unrelated concerns together. These three are one
    concern — what the caller supplied — as distinct from `preserved`, which is
    what the run has produced so far and changes at every stage.
    """

    intake: DocumentIntake
    identity: IdentityEnvelope
    human_business_context: HumanBusinessContext | None


def _failure_artifact(
    stage: str,
    exc: Exception,
    preserved: PipelinePartialResult,
    given: _RunInputs,
) -> DocumentEvidenceObject:
    """The Document Evidence Object that RECORDS a business failure.

    `APPLICATION_LAYER_CONTRACTS.md:27` — *"a document that cannot be read
    produces an object recording that failure, never a fabricated one."* Both
    halves are load-bearing and both are honoured here: an object IS produced,
    and every slot in it is either something that genuinely happened or an
    explicit emptiness. Nothing is filled in.

    WHY THIS DOES NOT GO THROUGH `assembly.assemble`, STATED RATHER THAN
    HIDDEN (Law 14, Law 26). `assemble` requires all four sub-engine outputs to
    be present and raises `MissingSubEngineOutputError` naming the first that
    is not — that check IS its purpose: it proves all four sub-engines ran. On
    a business failure at least one did not. Reaching `assemble`'s packaging
    would mean handing it a manufactured `CleanerOutput` for a `cleaner` that
    never completed, which is precisely the fabricated object line 27 forbids,
    and it would destroy the one guarantee `assemble` exists to give. So the
    fifteen lines of packaging are written again here for a genuinely different
    event, rather than the guarantee being weakened to allow reuse. Law 14
    governs duplicated LOGIC; "combine four completed outputs" and "record that
    a document could not be read" are two different jobs with two different
    preconditions.

    WHAT EACH SLOT CARRIES, AND WHY IT IS HONEST.
        extracted_text      whatever `reader` ACTUALLY produced if `reader`
                            completed before a later stage failed — real text,
                            really read, never dropped merely because the run
                            ended badly — and `""` when `reader` never ran.
        detected_fields     always empty, and this is UNAFFECTED by Amendment 5.
                            A field needs all three of source, confidence and
                            uncertainty (`ENGINE_1_INPUT_ENGINE_RULES.md:245`),
                            and on this path `parser` never ran, so there is no
                            named value and no source location for one — the
                            missing half is the VALUE, which no sentinel
                            supplies. "Read but not scored" and "never read"
                            stay two different facts here exactly as they do
                            everywhere else.
        detected_tables     always empty, for the same reason.
        confidence_scores   always empty, and NOT because a score is missing —
                            because there is no NAMED THING to score. A failed
                            run produced no mapped field, so there is nothing
                            for an entry to be about. `UNMEASURED` would be the
                            wrong answer here rather than a safer one: it
                            asserts that a specific value was read and not
                            scored, and on this path no value was read at all.
                            Nothing is minted either — not `0.0000`, which
                            would assert a measured worthlessness nobody
                            measured, and not a default, which
                            `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids
                            outright.
        uncertainty_markers exactly one, naming the document, the stage, and
                            the sub-engine's OWN message verbatim. This is the
                            *"named uncertainty"* half of
                            `COMMUNICATION_RULES_INPUT_ENGINE.md:159`, and it
                            carries no score, only a fact — which is why it
                            does not trespass on the `confidence` sub-engine's
                            sole authority to score
                            (`ENGINE_1_INPUT_ENGINE_RULES.md:109`).
        risky_fields        empty, unchanged from every other path — deciding a
                            field is risky is interpretation this engine may
                            not do.

    `preserved` is read for WHICH stages completed and for `reader`'s real
    text. It is never edited, and nothing in it is recomputed.
    """
    completed = tuple(
        name
        for name, produced in (
            ("cleaner", preserved.cleaned),
            ("reader", preserved.reading),
            ("parser", preserved.parsed),
        )
        if produced is not None
    )
    extracted = (
        "" if preserved.reading is None else reader_output(preserved.reading).raw_extracted_text
    )

    return DocumentEvidenceObject(
        identity=given.identity,
        document_id=DocumentId.new(),
        source_references=given.intake.source_references,
        structured_document=StructuredDocument(
            extracted_text=extracted,
            detected_fields=(),
            document_structure=(
                f"not parsed: Engine 1 stopped at the {stage!r} stage because the "
                "document could not be read."
            ),
            detected_tables=(),
        ),
        human_business_context=given.human_business_context,
        confidence_report=ConfidenceReport(
            confidence_scores=(),
            uncertainty_markers=(
                UncertaintyMarker(
                    subject=given.intake.source_references[0],
                    reason=(
                        f"this document could not be read at the {stage!r} stage: "
                        f"{exc} No value was extracted from it and none is "
                        "invented in its place; this artifact records the "
                        "failure so the transaction can be routed rather than "
                        "crashing (APPLICATION_LAYER_CONTRACTS.md:30, "
                        "COMMUNICATION_RULES_INPUT_ENGINE.md:159)."
                    ),
                ),
            ),
            reliability_information=(
                f"no field was extracted: Engine 1 stopped at the {stage!r} stage "
                f"because the document could not be read ({exc}). "
                f"Stages that completed first: {', '.join(completed) if completed else 'none'}. "
                "No confidence score is reported because nothing was measured; "
                "the absence is recorded rather than filled in."
            ),
            risky_fields=(),
        ),
    )


def _stopped(
    stage: str,
    exc: Exception,
    preserved: PipelinePartialResult,
    given: _RunInputs,
) -> DocumentEvidenceObject:
    """One stage could not complete. Decide which KIND of event that was, and
    act on it — the single place the business/runtime line is applied.

    A BUSINESS failure returns an artifact recording it. A RUNTIME failure
    raises `PipelineStageError`, unchanged, carrying every earlier stage's real
    output on `preserved`. Written once rather than three times so the two
    cannot drift apart per stage, which is exactly how a boundary like this
    normally rots.
    """
    if isinstance(exc, BUSINESS_FAILURE):
        return _failure_artifact(stage, exc, preserved, given)
    raise PipelineStageError(stage, exc, preserved) from exc


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
    given = _RunInputs(
        intake=intake, identity=identity, human_business_context=human_business_context
    )

    try:
        cleaned = cleaner.clean_artifact(
            intake.document,
            _MEDIA_KIND[intake.media_type],
            settings.cleaner_settings,
            render_dpi=settings.render_dpi,
        )
    except Exception as exc:
        return _stopped("cleaner", exc, preserved, given)
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
        return _stopped("reader", exc, preserved, given)
    preserved = replace(preserved, reading=reading)

    try:
        parsed = _parse_document(cleaned_document, intake, settings, extracted_regions(reading))
    except Exception as exc:
        return _stopped("parser", exc, preserved, given)
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
            confidence=confidence_output(report, unmeasured_field_scores(parsed)),
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
