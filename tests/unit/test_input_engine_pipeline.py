"""`pipeline` — the first thing that has ever run Engine 1's four sub-engines
together, on a real document, and the tests are written to catch exactly the
failure that matters here: a pipeline that LOOKS wired but quietly drops,
inflates or invents something on the way from one real sub-engine to the next.

`CLAUDE.md` §J.6 — REAL + ISOLATED. Every test below exercises the actual
`cleaner`, `reader`, `parser`, `confidence_report` and `assembly` modules,
never a stand-in for one. The one thing genuinely unavailable in this
environment is PaddleOCR (`KNOWN_FAILURES.md` F-002), so every test that needs
a completed reading uses the PDF text-layer path, exactly as
`test_input_engine_reader.py` and `test_input_engine_parser.py` already do,
and the one test that DOES reach the OCR path uses that real, measured absence
as its failure — not a mock standing in for one.

WHAT WOULD PROVE THIS WRONG, AND WHY EACH TEST IS SHAPED THE WAY IT IS.
    A pipeline that silently drops a region, silently raises a confidence
    score, or silently continues after a stage fails would still produce
    SOMETHING that "looks like" a Document Evidence Object. So the tests below
    do not just assert success — they assert the WITHOUT-LOSS shape of that
    success:

      - every string this file drew onto the fixture PDF is checked against
        the final artifact by name (`test_every_stage_output_is_traceable...`)
      - a confidence value is checked for EXACT equality across every hop
        that actually carries one, never "did not go down"
        (`test_a_document_level_confidence_score_is_not_raised...`) — and the
        hop that turns out NOT to carry one at all is pinned as its own
        regression test (`test_a_real_region_reading_with_a_score_still_
        carries_no_document_level_score`)
      - a genuine uncertainty marker, forced by a real, strict cleaner
        setting, is checked for its exact reason text surviving to the final
        artifact (`test_an_unknown_survives...`)
      - a stage failure is checked by attribute — which stage, what it
        preserved — not by "it raised something"
        (`test_cleaner_failing_first...`, `test_reader_failing_after_
        cleaner...`, `test_parser_failing_after_cleaner_and_reader...`)
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf
import pytest

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DocumentEvidenceObject,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine import assembly, cleaner, parser, pipeline, reader
from accountant_dad.engines.input_engine import confidence_report as confidence_report_module
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
)

Image = npt.NDArray[np.uint8]

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

#: A test parameter, not a product default: `pipeline.PipelineSettings` still
#: requires the caller to supply this, and this is this file's own choice of
#: value for it — reused for both `cleaner`'s page rendering and `reader`'s
#: own OCR-fallback rendering, exactly as `pipeline.py` reuses it internally.
RENDER_DPI = 150
#: Chosen so the vision fallback never triggers in a test about something
#: else — mirrors `test_input_engine_reader.py`'s own `NO_FALLBACK`.
NO_FALLBACK = Decimal("0.0")

# ── a typed facade over PyMuPDF, for AUTHORING fixtures only ──────────────
#
# Identical in spirit to `test_input_engine_reader.py`'s own facade, over the
# same untyped dependency, for the same reason (`mypy --strict` + this
# repository's zero-new-suppressions gate). Not imported from there: it is
# module-private to that file.


class _Pixmap(Protocol):
    def tobytes(self, output: str) -> bytes: ...


class _AuthoringPage(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def __getitem__(self, index: int) -> _AuthoringPage: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


open_pdf = cast(_NewDocument, pymupdf.open)

# ── ground truth ────────────────────────────────────────────────────────
# The synthetic invoice is rendered FROM this list, so checking that every
# line reached the artifact is checking against real ground truth, not a
# transcription of whatever a run happened to produce.

INVOICE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
    "Invoice No INV-2026-0481",
)


def an_invoice_pdf(lines: tuple[str, ...] = INVOICE_LINES) -> bytes:
    """A one-page PDF carrying a real text layer. Built by hand with PyMuPDF,
    the same way `test_input_engine_reader.py` builds its own fixtures."""
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    out = bytes(doc.tobytes())
    doc.close()
    return out


def a_tiny_png() -> bytes:
    """A small, real, decodable raster image — used only to prove `cleaner`
    can succeed on `MediaType.IMAGE` input before `reader` fails for a reason
    that has nothing to do with `cleaner`.
    """
    frame: Image = np.full((60, 60), 255, dtype=np.uint8)
    cv2.putText(frame, "HI", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,), 2)
    ok, encoded = cv2.imencode(".png", frame)
    assert ok
    return bytes(encoded.tobytes())


# ── builders ────────────────────────────────────────────────────────────


def an_identity(
    *, version: int = FIRST_VERSION, parent_versions: tuple[ParentVersion, ...] = ()
) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=version,
        parent_versions=parent_versions,
        transaction_id=TransactionId.new(),
    )


def a_cleaner_settings(**changes: float | int) -> cleaner.CleanerSettings:
    """A baseline permissive enough that a normal, small rendered page cleans
    without forcing `PreservationStatus.ORIGINAL_IS_SAFER` — differential
    tests override exactly the fields that need to change.
    """
    fields: dict[str, float | int] = {
        "max_deskew_degrees": 15.0,
        "denoise_strength": 3.0,
        "denoise_template_window": 7,
        "denoise_search_window": 21,
        "contrast_clip_limit": 2.0,
        "contrast_tile_grid": 8,
        "crop_margin_pixels": 10,
        "max_ink_loss_fraction": 1.0,
    }
    fields.update(changes)
    return cleaner.CleanerSettings(
        max_deskew_degrees=float(fields["max_deskew_degrees"]),
        denoise_strength=float(fields["denoise_strength"]),
        denoise_template_window=int(fields["denoise_template_window"]),
        denoise_search_window=int(fields["denoise_search_window"]),
        contrast_clip_limit=float(fields["contrast_clip_limit"]),
        contrast_tile_grid=int(fields["contrast_tile_grid"]),
        crop_margin_pixels=int(fields["crop_margin_pixels"]),
        max_ink_loss_fraction=float(fields["max_ink_loss_fraction"]),
    )


def a_pipeline_settings(
    *,
    cleaner_settings: cleaner.CleanerSettings | None = None,
    render_dpi: int = RENDER_DPI,
    vision_fallback_threshold: Decimal = NO_FALLBACK,
    table_structure: parser.TableStructureSettings | None = None,
) -> pipeline.PipelineSettings:
    return pipeline.PipelineSettings(
        cleaner_settings=cleaner_settings if cleaner_settings is not None else a_cleaner_settings(),
        render_dpi=render_dpi,
        vision_fallback_threshold=vision_fallback_threshold,
        table_structure=table_structure,
    )


def a_document_intake(
    *,
    document: bytes | None = None,
    media_type: reader.MediaType = reader.MediaType.PDF,
    source_references: tuple[str, ...] = ("upload:invoice-481.pdf",),
) -> pipeline.DocumentIntake:
    return pipeline.DocumentIntake(
        document=document if document is not None else an_invoice_pdf(),
        media_type=media_type,
        source_references=source_references,
    )


def a_cleaned_document(
    *, preservation_status: cleaner.PreservationStatus = cleaner.PreservationStatus.CLEANED_IS_SAFER
) -> cleaner.CleanedDocument:
    frame: Image = np.zeros((2, 2), dtype=np.uint8)
    return cleaner.CleanedDocument(
        original=frame,
        cleaned=frame,
        quality_observations=(),
        preservation_status=preservation_status,
    )


def a_human_business_context(text: str = "Advance paid to supplier.") -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-1",
            evidence_reference="message 1",
            timestamp=WHEN,
            confidence=Decimal("1.0000"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


# ── one real PDF, end to end ────────────────────────────────────────────
# Session-scoped: Docling's model loading is the expensive part of every
# `parser.parse` call, so the tests that only READ this result share one run
# rather than paying for it repeatedly.


@pytest.fixture(scope="session")
def end_to_end_result() -> DocumentEvidenceObject:
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:invoice-481.pdf",),
    )
    return pipeline.run(
        intake,
        identity=an_identity(),
        settings=a_pipeline_settings(),
        human_business_context=a_human_business_context(),
    )


def test_a_real_pdf_with_a_text_layer_runs_end_to_end(
    end_to_end_result: DocumentEvidenceObject,
) -> None:
    """The one thing this engine has never done before this module existed."""
    assert isinstance(end_to_end_result, DocumentEvidenceObject)
    assert end_to_end_result.source_references == ("upload:invoice-481.pdf",)
    assert end_to_end_result.structured_document.extracted_text != ""
    assert end_to_end_result.confidence_report is not None


def test_every_stage_output_is_traceable_in_the_final_artifact(
    end_to_end_result: DocumentEvidenceObject,
) -> None:
    """Reader's exact regions, in order, and parser's exact structure, both
    findable in the one artifact Engine 1 emits — not summarised away.
    """
    # traceable to reader: every drawn line, in the order it was drawn
    assert end_to_end_result.structured_document.extracted_text == "\n".join(INVOICE_LINES)
    # traceable to parser: every drawn line still present in its structure
    for line in INVOICE_LINES:
        assert line in end_to_end_result.structured_document.document_structure
    # traceable to cleaner: its preservation verdict is in the reliability text
    assert (
        "cleaned representation is the safer basis for reading"
        in end_to_end_result.confidence_report.reliability_information
        or "original is the safer basis for reading"
        in end_to_end_result.confidence_report.reliability_information
    )


def test_a_provided_source_passes_through_untouched(
    end_to_end_result: DocumentEvidenceObject,
) -> None:
    """§1.2/§1.3 — a Human Business Description is never cleaned, read or
    structured; it travels verbatim and is scored only for capture fidelity.
    """
    assert end_to_end_result.human_business_context is not None
    assert end_to_end_result.human_business_context.original_user_text == (
        "Advance paid to supplier."
    )
    # never merged into the extracted, document-origin evidence
    assert "Advance paid to supplier." not in end_to_end_result.structured_document.extracted_text
    # scored for capture fidelity only — an exact match earns MAX, never more
    capture_scores = [
        score.confidence
        for score in end_to_end_result.confidence_report.confidence_scores
        if score.field_name == confidence_report_module.CAPTURE_FIDELITY_FIELD_NAME
    ]
    assert capture_scores == [confidence_report_module.CAPTURE_FIDELITY_ON_EXACT_MATCH]


# ── an unknown survives the whole pipeline ─────────────────────────────


def test_an_unknown_survives_the_whole_pipeline_and_is_not_silently_dropped() -> None:
    """A real, strict `cleaner` setting forces `PreservationStatus.
    ORIGINAL_IS_SAFER` on a real rendered page — measured: `denoise_strength`
    of 40 against `max_ink_loss_fraction` of 0.0 erodes real ink on this
    fixture. The resulting uncertainty marker's exact reason must survive,
    unedited, all the way to the final artifact.
    """
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:strict.pdf",),
    )
    strict_settings = a_pipeline_settings(
        cleaner_settings=a_cleaner_settings(denoise_strength=40.0, max_ink_loss_fraction=0.0)
    )

    result = pipeline.run(intake, identity=an_identity(), settings=strict_settings)

    markers = result.confidence_report.uncertainty_markers
    assert any(marker.subject == "the document as cleaned" for marker in markers)
    matching = [marker for marker in markers if marker.subject == "the document as cleaned"]
    assert "could have lost" in matching[0].reason
    assert "PreservationStatus.ORIGINAL_IS_SAFER" in matching[0].reason


# ── determinism, versioning: same input, same content, new version ────

#: A correction is a NEW version, never an edit of the first — named rather
#: than a bare `2` because the number IS the assertion (mirrors
#: `test_input_engine_assembly.py`'s own `CORRECTED_VERSION`).
CORRECTED_VERSION = 2


def test_the_same_input_twice_is_identical_content_but_the_second_run_is_a_new_version() -> None:
    document = an_invoice_pdf()
    intake = pipeline.DocumentIntake(
        document=document, media_type=reader.MediaType.PDF, source_references=("upload:v.pdf",)
    )
    settings = a_pipeline_settings()

    first_identity = an_identity(version=FIRST_VERSION)
    first = pipeline.run(intake, identity=first_identity, settings=settings)

    second_identity = an_identity(
        version=CORRECTED_VERSION,
        parent_versions=(
            ParentVersion(artifact_id=first_identity.artifact_id, version=FIRST_VERSION),
        ),
    )
    second = pipeline.run(intake, identity=second_identity, settings=settings)

    assert first.structured_document == second.structured_document
    assert first.confidence_report == second.confidence_report
    assert first.source_references == second.source_references
    # ... but each run mints its own Document ID, and correction is a new
    # version, never an edit of the first.
    assert first.document_id != second.document_id
    assert first.identity.version == FIRST_VERSION
    assert second.identity.version == CORRECTED_VERSION
    assert second.identity.parent_versions[0].artifact_id == first_identity.artifact_id


# ── a stage failing mid-pipeline: named, loud, and nothing later runs ──


def test_cleaner_failing_first_preserves_nothing_and_names_itself() -> None:
    intake = pipeline.DocumentIntake(
        document=b"", media_type=reader.MediaType.IMAGE, source_references=("upload:empty",)
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(intake, identity=an_identity(), settings=a_pipeline_settings())

    assert raised.value.stage == "cleaner"
    assert "cleaner" in str(raised.value)
    assert raised.value.preserved == pipeline.PipelinePartialResult()


def test_reader_failing_after_cleaner_preserves_cleaners_work_and_names_reader() -> None:
    """`MediaType.IMAGE` reaches `reader`'s OCR path, which needs PaddleOCR —
    genuinely absent in this environment (`KNOWN_FAILURES.md` F-002). `cleaner`
    succeeds on the same real bytes first, so this proves both halves: a real
    dependency's real absence stops the pipeline, and it stops it AT reader,
    with cleaner's already-completed work intact.
    """
    intake = pipeline.DocumentIntake(
        document=a_tiny_png(),
        media_type=reader.MediaType.IMAGE,
        source_references=("upload:hi.png",),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(intake, identity=an_identity(), settings=a_pipeline_settings())

    assert raised.value.stage == "reader"
    assert "reader" in str(raised.value)
    assert isinstance(raised.value.cause, ModuleNotFoundError)
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is None
    assert raised.value.preserved.parsed is None
    assert raised.value.preserved.confidence is None


def test_parser_failing_after_cleaner_and_reader_preserves_both_and_names_parser() -> None:
    """A blank source reference is real, caller-supplied bad input: `parser.
    parse` refuses it (`_reject_blank`) before it ever touches Docling.
    `cleaner` and `reader` both already succeeded on the same valid PDF, so
    their real output must be preserved when parser is the one that fails.
    """
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(), media_type=reader.MediaType.PDF, source_references=("",)
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(intake, identity=an_identity(), settings=a_pipeline_settings())

    assert raised.value.stage == "parser"
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is not None
    assert raised.value.preserved.parsed is None
    assert raised.value.preserved.confidence is None


def test_assembly_failing_last_preserves_every_earlier_stage_and_names_assembly() -> None:
    """`cleaner`, `reader`, `parser` and `confidence` all genuinely succeed on
    a real PDF - `assembly.assemble` is the one that fails, on a real caller
    mistake `DocumentIntake` does not itself refuse: two identical source
    references. `DocumentIntake.__post_init__` only checks for AT LEAST ONE
    (`test_a_document_intake_with_no_source_reference_fails_at_construction`);
    the duplicate check belongs to `DocumentEvidenceObject`'s own schema
    (`accountant_dad.artifacts.evidence`, INV-11), reached only inside
    `assembly.assemble`, so this is the one input shape that runs all four
    sub-engines for real and still fails at the last stage.
    """
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:dup.pdf", "upload:dup.pdf"),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(intake, identity=an_identity(), settings=a_pipeline_settings())

    assert raised.value.stage == "assembly"
    assert "assembly" in str(raised.value)
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is not None
    assert raised.value.preserved.parsed is not None
    assert raised.value.preserved.confidence is not None


# ── confidence is never raised anywhere along the chain ────────────────


def test_a_real_region_reading_with_a_score_still_carries_no_document_level_score() -> None:
    """FALSIFICATION of the obvious assumption, pinned as a permanent
    regression test. It would be reasonable to expect a scored `RegionReading`
    to become a `confidence_scores` entry — measured directly: it does not.

    `confidence_report.record_confidence`'s own `_field_confidence_scores`
    reads ONLY `parsed_fields`; `reader_regions` feeds `_unread_region_markers`
    exclusively (fires only when `text is None`, never true for a real
    reading). So a `RegionReading` carrying real text AND a real score is a
    genuine reading — it is simply inert to `confidence_scores`, on either
    side of the boundary this pipeline builds. Combined with defect 4 (no
    `ParsedField` is buildable from today's real `reader` + `parser`), this is
    why the end-to-end fixture's `confidence_scores` carries only the optional
    Human Business Context's capture-fidelity entry, never a document field.
    """
    region = reader.TextRegion(
        text="Amount 100.00",
        location=reader.SourceLocation(page_index=0, left=1.0, top=2.0, right=3.0, bottom=4.0),
        extraction_confidence=Decimal("0.1000"),
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.OCR, pages_read=1)
    readings = pipeline.region_readings(reading)

    report = confidence_report_module.record_confidence(a_cleaned_document(), readings, (), ())

    assert report.confidence_scores == ()
    assert report.uncertainty_markers == ()


def test_a_document_level_confidence_score_is_not_raised_on_its_way_to_the_final_artifact() -> None:
    """The half of the chain that DOES carry a document-level score: once
    `confidence_report` produces one (today, only the optional Human Business
    Context's capture-fidelity entry can), it must survive `confidence_output`
    and the real `assembly.assemble` byte-for-byte — never rounded, clamped,
    or raised because it looked low.
    """
    low = Decimal("0.1000")
    report = ConfidenceReport(
        confidence_scores=(FieldConfidence(field_name="Amount", confidence=low),),
        uncertainty_markers=(),
        reliability_information="a synthetic report for this test only",
        risky_fields=(),
    )

    output = pipeline.confidence_output(report)
    assert output.confidence_scores[0].confidence == low

    parts = assembly.SubEngineOutputs(
        cleaner=pipeline.cleaner_output(a_cleaned_document()),
        reader=pipeline.reader_output(
            reader.Reading(regions=(), backend=reader.Backend.PDF_TEXT_LAYER, pages_read=0)
        ),
        parser=assembly.ParserOutput(document_structure="", detected_fields=(), detected_tables=()),
        confidence=output,
    )
    result = assembly.assemble(
        parts=parts, identity=an_identity(), source_references=("upload:x.pdf",)
    )

    assert result.confidence_report.confidence_scores[0].confidence == low


def test_region_readings_never_raises_or_lowers_a_score_it_was_given() -> None:
    high = Decimal("0.9999")
    region = reader.TextRegion(
        text="GSTIN 27AAECS1234F1Z5",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=high,
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.OCR, pages_read=1)

    (built,) = pipeline.region_readings(reading)

    assert built.extraction_confidence == high
    assert built.extraction_confidence is high  # the exact object, not a recomputed equal one


# ── defect 3, proven directly: an unscored region is excluded, not invented ─


def test_region_readings_excludes_a_text_layer_region_but_keeps_a_scored_one() -> None:
    scored = reader.TextRegion(
        text="scored by OCR",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=Decimal("0.7500"),
    )
    unscored = reader.TextRegion(
        text="read from a PDF text layer",
        location=reader.SourceLocation(page_index=0, left=0.0, top=2.0, right=1.0, bottom=3.0),
        extraction_confidence=None,
    )
    reading = reader.Reading(
        regions=(scored, unscored), backend=reader.Backend.PDF_TEXT_LAYER, pages_read=1
    )

    readings = pipeline.region_readings(reading)

    assert len(readings) == 1
    assert readings[0].text == "scored by OCR"
    assert readings[0].extraction_confidence == Decimal("0.7500")
    # the unscored region's text is not lost from the artifact: it still
    # reaches `raw_extracted_text` through `reader_output`, independently.
    assert "read from a PDF text layer" in pipeline.reader_output(reading).raw_extracted_text


# ── table bands render too, when a table structure detector found any ─────


def test_document_structure_text_renders_every_band_a_table_structure_detector_found() -> None:
    """`table.bands` is the one collection `document_structure_text` had no
    fixture exercising: through THIS pipeline `parser.parse` never receives a
    `table_structure` setting (defect 1 - every number here is the caller's,
    and this pipeline supplies none), so a `Table` carrying a band is built
    directly, the same way `test_table_transformer_reports_bands_when_the_
    caller_supplies_the_numbers` proves the real detector produces one.
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=10.0, bottom=10.0)
    structure = parser.ParsedStructure(
        source_reference="upload:x.pdf",
        page_count=1,
        regions=(),
        tables=(
            parser.Table(
                detector="table-transformer:test",
                box=box,
                row_count=1,
                column_count=1,
                cells=(),
                bands=(parser.Band(label="table row", score=0.87, box=box),),
            ),
        ),
    )

    text = pipeline.document_structure_text(structure)

    assert "band label='table row'" in text
    assert "score=0.87" in text


# ── defect 4, proven directly: no invented field name or confidence ───


def test_parser_output_never_invents_a_named_field_even_when_parser_found_structure() -> None:
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=10.0, bottom=10.0)
    structure = parser.ParsedStructure(
        source_reference="upload:x.pdf",
        page_count=1,
        regions=(parser.Region(label="text", text="Amount 4500.00", box=box, detector="docling"),),
        tables=(
            parser.Table(
                detector="docling",
                box=box,
                row_count=1,
                column_count=1,
                cells=(
                    parser.Cell(
                        text="4500.00",
                        row_start=0,
                        row_end=1,
                        column_start=0,
                        column_end=1,
                        is_column_header=False,
                        is_row_header=False,
                        box=box,
                    ),
                ),
            ),
        ),
    )

    output = pipeline.parser_output(structure)

    assert output.detected_fields == ()
    assert output.detected_tables == ()
    # but nothing found is lost: it is rendered into the one channel available
    assert "Amount 4500.00" in output.document_structure
    assert "4500.00" in output.document_structure


def test_missing_fields_maps_what_parser_actually_reports_absent() -> None:
    """Always empty against the real `parser` today (it is given no expected-
    field list), proven here by feeding the mapping function a
    `MissingFieldInformation` that DOES name an absent field — showing the
    mapping is a real, working translation, not a hard-coded empty return.
    """
    structure = parser.ParsedStructure(
        source_reference="upload:x.pdf",
        page_count=1,
        regions=(),
        tables=(),
        missing_field_information=parser.MissingFieldInformation(
            absent_fields=("HSN Code",), basis="a synthetic test list, not parser's own"
        ),
    )

    result = pipeline.missing_fields(structure)

    assert result == (confidence_report_module.MissingField(field_name="HSN Code", state="absent"),)


def test_parser_produces_no_expected_field_list_so_missing_fields_is_always_empty_today() -> None:
    structure = parser.ParsedStructure(
        source_reference="upload:x.pdf", page_count=1, regions=(), tables=()
    )
    assert structure.missing_field_information == parser.NO_EXPECTED_FIELD_LIST_WAS_SUPPLIED
    assert pipeline.missing_fields(structure) == ()


# ── rasterisation for cleaner: identity for an image, a real render for a PDF ─


def test_rasterise_is_the_identity_function_for_an_image() -> None:
    raw = a_tiny_png()
    intake = a_document_intake(document=raw, media_type=reader.MediaType.IMAGE)

    assert pipeline.rasterise_first_page_for_cleaning(intake, render_dpi=RENDER_DPI) == raw


def test_rasterise_produces_bytes_cleaner_can_decode_for_a_pdf() -> None:
    intake = a_document_intake(document=an_invoice_pdf(), media_type=reader.MediaType.PDF)

    rasterised = pipeline.rasterise_first_page_for_cleaning(intake, render_dpi=RENDER_DPI)

    # defect 2, the positive side: cleaner.decode raises on the raw PDF bytes
    # (proven separately below) and succeeds on what this function returns.
    image = cleaner.decode(rasterised)
    assert image.ndim in (2, 3)


def test_cleaner_cannot_decode_a_raw_pdf_directly() -> None:
    """The measured defect this module works around, pinned as a permanent
    regression test: if a future OpenCV build ever learns to decode PDFs,
    this test — not a silent behaviour change — is what notices first.
    """
    with pytest.raises(cleaner.UndecodableArtifactError):
        cleaner.decode(an_invoice_pdf())


# ── conversion functions carry values through unchanged ────────────────


def test_cleaner_output_carries_the_real_preservation_status_and_observations() -> None:
    cleaned = a_cleaned_document(preservation_status=cleaner.PreservationStatus.ORIGINAL_IS_SAFER)

    output = pipeline.cleaner_output(cleaned)

    assert output.preservation_status == "the original is the safer basis for reading"
    assert output.cleaned_document_representation is cleaned.cleaned


def test_reader_output_joins_regions_in_reader_order_without_reordering() -> None:
    first = reader.TextRegion(
        text="first",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=None,
    )
    second = reader.TextRegion(
        text="second",
        location=reader.SourceLocation(page_index=0, left=0.0, top=2.0, right=1.0, bottom=3.0),
        extraction_confidence=None,
    )
    reading = reader.Reading(
        regions=(first, second), backend=reader.Backend.PDF_TEXT_LAYER, pages_read=1
    )

    output = pipeline.reader_output(reading)

    two_regions = 2
    assert output.raw_extracted_text == "first\nsecond"
    assert len(output.source_locations) == two_regions
    assert len(output.extraction_confidence) == two_regions


def test_confidence_output_carries_every_field_through_unchanged() -> None:
    cleaned = a_cleaned_document()
    report = confidence_report_module.record_confidence(cleaned, (), (), ())

    output = pipeline.confidence_output(report)

    assert output.confidence_scores == report.confidence_scores
    assert output.uncertainty_markers == report.uncertainty_markers
    assert output.reliability_information == report.reliability_information
    assert output.risky_fields == report.risky_fields


# ── a missing required setting fails at the start, before any work ────


class _LooseRun(Protocol):
    def __call__(
        self,
        intake: pipeline.DocumentIntake = ...,
        *,
        identity: IdentityEnvelope = ...,
        settings: pipeline.PipelineSettings = ...,
        human_business_context: HumanBusinessContext | None = ...,
    ) -> DocumentEvidenceObject: ...


run_as_a_careless_caller_would = cast(_LooseRun, pipeline.run)


def test_omitting_settings_raises_naming_settings_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="settings"):
        run_as_a_careless_caller_would(a_document_intake(), identity=an_identity())


def test_omitting_identity_raises_naming_identity_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="identity"):
        run_as_a_careless_caller_would(a_document_intake(), settings=a_pipeline_settings())


def test_omitting_intake_raises_naming_intake_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="intake"):
        run_as_a_careless_caller_would(identity=an_identity(), settings=a_pipeline_settings())


def test_a_document_intake_with_no_source_reference_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="source_references"):
        pipeline.DocumentIntake(
            document=an_invoice_pdf(), media_type=reader.MediaType.PDF, source_references=()
        )


def test_pipeline_settings_required_fields_have_no_default() -> None:
    parameters = inspect.signature(pipeline.PipelineSettings).parameters
    for name in ("cleaner_settings", "render_dpi", "vision_fallback_threshold"):
        assert parameters[name].default is inspect.Parameter.empty, (
            f"{name} acquired a default. Every number `pipeline` passes to a "
            "sub-engine must be the caller's, never invented here (Law 52)."
        )


def test_table_structure_still_defaults_to_none_not_a_chosen_number() -> None:
    """Mirrors `parser.parse`'s own contract exactly — see the module
    docstring, `PipelineSettings`. Not this module's default; `parser`'s.
    """
    parameters = inspect.signature(pipeline.PipelineSettings).parameters
    assert parameters["table_structure"].default is None


def test_run_requires_a_document_intake_a_settings_object_and_an_identity() -> None:
    """Falsification of the whole "no defaults" claim above: inspect the real
    signature directly, not just the two runtime calls that omit one each.
    """
    parameters = inspect.signature(pipeline.run).parameters
    assert parameters["intake"].default is inspect.Parameter.empty
    assert parameters["identity"].default is inspect.Parameter.empty
    assert parameters["settings"].default is inspect.Parameter.empty
    # the one parameter that IS allowed a default, and only because
    # ENGINE_1_INPUT_ENGINE_RULES.md:138 requires Engine 1 to work without one
    assert parameters["human_business_context"].default is None


# ── PipelineStageError names the actual failing stage, not a generic one ──


def test_pipeline_stage_error_message_names_the_stage_and_carries_the_cause() -> None:
    intake = pipeline.DocumentIntake(
        document=b"", media_type=reader.MediaType.IMAGE, source_references=("upload:empty",)
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(intake, identity=an_identity(), settings=a_pipeline_settings())

    assert raised.value.stage in str(raised.value)
    assert isinstance(raised.value.cause, cleaner.UndecodableArtifactError)
    assert isinstance(raised.value.preserved, pipeline.PipelinePartialResult)


def test_pipeline_partial_result_defaults_to_nothing_completed() -> None:
    empty = pipeline.PipelinePartialResult()
    assert empty.cleaned is None
    assert empty.reading is None
    assert empty.parsed is None
    assert empty.confidence is None
    assert empty == replace(pipeline.PipelinePartialResult())
