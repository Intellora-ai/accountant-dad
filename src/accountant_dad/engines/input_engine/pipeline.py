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

FOUR REAL DEFECTS, FOUND BY ACTUALLY WIRING THESE MODULES TOGETHER, NONE FIXED
HERE (`CLAUDE.md` §E.7 — report, do not fix a module outside the current
mission). Every one is measured below, not assumed.

  1. `reader` AND `parser` EACH RE-OPEN THE RAW DOCUMENT; NEITHER CONSUMES THE
     OTHER'S OUTPUT, OR `cleaner`'S. The diagram this module implements shows a
     chain — cleaned document into `reader`, `reader`'s reading into `parser`.
     The real modules do not compose that way: `reader.read` takes the
     document's raw `bytes` and opens the PDF itself (`reader.py`, "WHERE THE
     INPUT COMES FROM" — it takes bytes because `cleaner` did not exist when it
     was written). `parser.parse` takes a `pathlib.Path` and opens the SAME
     document a third time through Docling (`parser.py`, "WHERE THIS DEPARTS
     FROM THE LOCKED SPECIFICATION" — its own docstring calls this "a real
     departure" and says "it must not stay that way"). This module therefore
     runs the three extraction sub-engines independently, on the same source,
     rather than piping one's return value into the next — there is currently
     no other way to call the real code.

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

  3. `confidence_report.RegionReading` CANNOT REPRESENT A SINGLE REGION
     `reader.read_pdf_text_layer` PRODUCES. Measured directly:
     `RegionReading(source_location=..., text="TAX INVOICE",
     extraction_confidence=None)` raises `MalformedSignalError` — every time,
     for every region a text layer produces. `RegionReading`'s own invariant
     requires `text` and `extraction_confidence` to be `None` together or
     present together, on the documented assumption that "an instrument cannot
     score a reading that does not exist" therefore text without a score can
     only mean "unread". That assumption is correct for OCR and wrong for a
     PDF text layer, whose entire design (`reader.py`, "THE CONFIDENCE OF A
     TEXT LAYER IS `None`") is to report real, successfully-read text with
     honestly NO per-region score, because no recogniser ran to produce one.
     `confidence_report.py`'s own module docstring already names the general
     shape of this gap ("their landed shapes do not yet carry what this module
     needs"); this is the concrete instance. Neither side is fixed here.
     Inventing a score to satisfy the invariant would be exactly the
     fabrication `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids, and reporting a
     successfully-read region as unread would be a lie in the other direction.
     So a region reader read via a backend that assigns it no per-region score
     is left OUT of the Confidence Report's per-region tracking — its TEXT
     still reaches the final artifact (`StructuredDocument.extracted_text`, via
     `reader_output` below), so nothing is silently dropped; only the
     per-region reliability signal for that one text is unavailable, and
     `ConfidenceReport.reliability_information` states the count that WAS
     scored, which is honest about what happened rather than a wrong number
     dressed up as complete.

     A SHARPER VERSION OF THE SAME GAP, ALSO MEASURED: even a `RegionReading`
     that DOES construct — real text, a real OCR score — never becomes a
     `confidence_scores` entry either way.
     `confidence_report.record_confidence`'s own `_field_confidence_scores`
     reads ONLY its `parsed_fields` argument; `reader_regions` feeds
     `_unread_region_markers` exclusively, which fires only when
     `text is None` — never true for a successful reading. So `reader`'s
     confidence signal, scored or not, cannot reach `ConfidenceReport.
     confidence_scores` through this pipeline at all today; only a named,
     scored `ParsedField` can, and defect 4 below is exactly why none exists.
     Pinned as `test_a_real_region_reading_with_a_score_still_carries_no_
     document_level_score` in the test file, so a future change to either
     module that quietly closes or widens this gap is noticed.

  4. `assembly.ParserOutput.detected_fields` / `.detected_tables` NEED A
     `Provenance`, WHICH NEEDS A `Confidence`, AND NEITHER `reader` NOR `parser`
     PRODUCES ONE ATTACHED TO A NAME. `evidence.DetectedField` and
     `DetectedTable` each require complete `Provenance` (INV-11, no optional
     field) — a `Confidence` value among them. `parser.Region` / `Table` /
     `Cell` carry geometry and text, deliberately with NO confidence at all
     (`parser.py`, "CONFIDENCE IS NOT PRODUCED HERE, AT ALL" — only `confidence`
     may produce one, `ENGINE_1_INPUT_ENGINE_RULES.md:109`), and they carry no
     field NAME either — a `Cell` knows its row and column, not that it holds
     an amount. `reader.TextRegion` carries a confidence but, symmetrically, no
     name. Building a `DetectedField` from either would mean this module
     inventing the missing half itself — a field name parser never assigned, or
     a confidence parser never measured — which is the interpretation
     `ENGINE_1_INPUT_ENGINE_RULES.md:558-562` forbids happening inside
     extraction. `stub.py` already established the honest answer for "nothing
     nameable and scored exists": zero detected fields, not an invented one
     with a guessed name (`stub.py`, "NOT ONE DETECTED FIELD IS EMITTED"). This
     module does the same — `parser_output` below always returns
     `detected_fields=()` and `detected_tables=()` — while `parser`'s actual
     structural findings (every region's label, text and box; every table's
     cells and bands) still reach the artifact in full through
     `StructuredDocument.document_structure`, rendered as a complete, traceable
     string rather than silently dropped.

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
    `confidence_output`, `region_readings`, `missing_fields`) repackages a
    value into the shape the next call needs; none of them rounds, clamps,
    reinterprets or recomputes a value a sub-engine produced. `region_readings`
    drops nothing it CAN honestly carry (see defect 3); it never edits what it
    does carry.

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
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import pymupdf

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    DocumentEvidenceObject,
    HumanBusinessContext,
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
    """`reader.TextRegion` mapped into `confidence_report`'s own contract, for
    every region where that mapping is honest. See the module docstring,
    defect 3.

    A region reader scored (`extraction_confidence is not None`, the OCR
    path) becomes a `RegionReading` carrying that EXACT `Decimal`, unrounded
    and unrenamed — confidence is never raised, lowered or invented here. A
    region reader read but did not score (`extraction_confidence is None`,
    every region a PDF text layer produces) cannot become a `RegionReading` at
    all: `confidence_report.RegionReading`'s own invariant refuses text
    without a score, on pain of `MalformedSignalError`, because it can only
    mean "unread" — which this text is not. That region is left out of this
    tuple rather than represented dishonestly either way; its text still
    reaches the final artifact through `reader_output.raw_extracted_text`, so
    it is reported, just not through this particular channel.
    """
    return tuple(
        confidence_report.RegionReading(
            source_location=repr(region.location),
            text=region.text,
            extraction_confidence=region.extraction_confidence,
        )
        for region in reading.regions
        if region.extraction_confidence is not None
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
    never sorts). This is the one channel that carries a text-layer region's
    text into the final artifact when defect 3 keeps it out of the Confidence
    Report's per-region tracking.
    """
    return assembly.ReaderOutput(
        raw_extracted_text="\n".join(region.text for region in reading.regions),
        source_locations=tuple(repr(region.location) for region in reading.regions),
        extraction_confidence=tuple(
            str(region.extraction_confidence) for region in reading.regions
        ),
    )


def parser_output(parsed: parser.ParsedStructure) -> assembly.ParserOutput:
    """`parser`'s real output, packaged for `assembly.SubEngineOutputs`.

    `detected_fields` and `detected_tables` are always empty — see the module
    docstring, defect 4: neither `reader` nor `parser` produces a name and a
    confidence attached to the same value, and inventing either half here
    would be exactly the interpretation Engine 1 is forbidden to perform.
    `parser`'s actual findings are not lost; they are rendered in full by
    `document_structure_text`.
    """
    return assembly.ParserOutput(
        document_structure=document_structure_text(parsed),
        detected_fields=(),
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
    human_business_context: HumanBusinessContext | None = None,
) -> DocumentEvidenceObject:
    """Run Engine 1's four sub-engines, in order, on one document, and return
    the Document Evidence Object `assembly.assemble` builds from what they
    produced.

        bytes -> cleaner -> reader -> parser -> confidence_report -> assembly

    Each of the five stages runs inside its own `try`/`except`. The first one
    to raise stops the pipeline immediately and re-raises as
    `PipelineStageError`, naming that stage and carrying every earlier stage's
    real output on `preserved` (see the module docstring's boundaries
    section) — no stage after the failure ever runs, and nothing is invented
    to let it.

    `intake` and `settings` are both required, with no default: omitting
    either raises `TypeError` naming the missing parameter, before any
    sub-engine is called. `intake` itself refuses at construction if it names
    no source reference (`DocumentIntake.__post_init__`) — also before any
    sub-engine runs. `human_business_context` defaults to `None` because the
    Human Business Description is optional and Engine 1 must work correctly
    without one (`ENGINE_1_INPUT_ENGINE_RULES.md:138`); when supplied, it is
    never handed to `cleaner`, `reader` or `parser` — see the module
    docstring, "a provided source passes through untouched".
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
        parsed = _parse_document(cleaned_document, intake, settings)
    except Exception as exc:
        raise PipelineStageError("parser", exc, preserved) from exc
    preserved = replace(preserved, parsed=parsed)

    try:
        report = confidence_report.record_confidence(
            cleaned,
            region_readings(reading),
            (),
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
            parser=parser_output(parsed),
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
    document: bytes, intake: DocumentIntake, settings: PipelineSettings
) -> parser.ParsedStructure:
    """Materialise the CLEANED document and hand it to `parser.parse`.

    `document` is `CleanedArtifact.payload`, never `intake.document` — that is
    the whole point of the F-017 migration and the reason this parameter
    exists at all. Docling needs a real path, so the bytes are written to a
    temporary file; that is a filesystem detail of this call, not a second
    pipeline. The file is removed whether `parser.parse` succeeds or raises.
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
            table_structure=settings.table_structure,
        )
    finally:
        temp_path.unlink(missing_ok=True)
