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

import ast
import inspect
import pathlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf
import pytest
from pydantic import ValidationError

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

#: The clock `run` is GIVEN. A distinct instant from `WHEN` on purpose: `WHEN`
#: is the human note's own provenance timestamp, this is the pipeline's, and a
#: test that asserted one while meaning the other would pass by coincidence.
#: `pipeline.run` takes this rather than reading a clock — see
#: `test_run_reads_no_clock_of_its_own` for what that buys.
RECORDED_AT = datetime(2026, 8, 6, 11, 30, tzinfo=UTC)

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
        recorded_at=RECORDED_AT,
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

    result = pipeline.run(
        intake, identity=an_identity(), settings=strict_settings, recorded_at=RECORDED_AT
    )

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
    first = pipeline.run(
        intake, identity=first_identity, settings=settings, recorded_at=RECORDED_AT
    )

    second_identity = an_identity(
        version=CORRECTED_VERSION,
        parent_versions=(
            ParentVersion(artifact_id=first_identity.artifact_id, version=FIRST_VERSION),
        ),
    )
    second = pipeline.run(
        intake, identity=second_identity, settings=settings, recorded_at=RECORDED_AT
    )

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
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

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
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

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
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

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
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

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
    genuine reading — it is simply inert to `confidence_scores`.

    STILL TRUE AFTER THE F-019 FIX, AND THAT IS THE POINT OF KEEPING IT. The
    route that DOES produce a document field's score is `parsed_fields`, built
    from `parser`'s mapped fields, and it is passed as the THIRD argument here.
    This call passes `()` there deliberately: it proves the score still cannot
    arrive by the `reader_regions` door, so the fix went through the arrow the
    specification draws rather than round the back.
    `test_a_scored_reading_reaches_the_artifact_with_its_score_on_both_sides`
    is the same modules with that argument supplied, and it is the contrast.
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


# ── defect 3, proven directly: an unscored region is CARRIED and MARKED ────


def test_region_readings_carries_an_unscored_text_layer_region_and_marks_it() -> None:
    """A CORRECTED EXPECTATION, NOT AN EASED ONE (§J.4, Law 4).

    This test used to be named `..._excludes_a_text_layer_region_but_keeps_a_
    scored_one` and to assert `len(readings) == 1` for a two-region reading.
    That expectation was WRONG, and it was wrong in the dangerous direction: it
    pinned as correct the behaviour of dropping every region a PDF text layer
    produces — which is every region on the MVP's primary input.

    WHY IT WAS EVER WRITTEN, AND WHY THE REASON EXPIRED.
    `confidence_report.RegionReading` once refused text with no score outright,
    so `region_readings` could not construct one and dropping it was the least
    dishonest option then available. `ReadingState` has since gained its third
    member, `READ_BUT_UNSCORED`, and the refusal is gone. The filter outlived
    its cause; the assertion outlived it too.

    THE CORRECTION IS STRICTLY STRONGER. The old test made four assertions and
    admitted any behaviour that kept the scored region. This one pins the
    count, BOTH regions' states by name, reader's own ORDER, the scored
    `Decimal` by IDENTITY rather than equality, and — the assertion that
    actually catches the regression — that the unscored region reaches the
    Confidence Report as a real `UncertaintyMarker` naming its own location.
    Restoring the filter now fails five ways instead of passing.

    MEASURED, WHY THIS MATTERS RATHER THAN BEING TIDINESS. On three text-layer
    regions the filter suppressed three `UncertaintyMarker`s (3 -> 0) and made
    `reliability_information` publish "0 of 0 region(s) reader attempted" for a
    document holding three: concealed uncertainty
    (`ENGINE_1_ARCHITECTURE.md` P-F3) on top of a fabricated denominator
    (Law 24).
    """
    score = Decimal("0.7500")
    scored = reader.TextRegion(
        text="scored by OCR",
        location=reader.SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
        extraction_confidence=score,
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

    # nothing is filtered, and reader's own order is kept
    assert len(readings) == 2
    assert [carried.text for carried in readings] == [
        "scored by OCR",
        "read from a PDF text layer",
    ]
    assert [carried.state for carried in readings] == [
        confidence_report_module.ReadingState.READ_AND_SCORED,
        confidence_report_module.ReadingState.READ_BUT_UNSCORED,
    ]

    # the scored region keeps the exact object reader measured
    assert readings[0].extraction_confidence is score
    # and the unscored one is given NO number in its place (ENGINE_1:337)
    assert readings[1].extraction_confidence is None

    # the absence is REPORTED, not merely tolerated: one marker, naming the
    # unscored region's own location, and none for the scored one.
    report = confidence_report_module.record_confidence(a_cleaned_document(), readings, (), ())
    assert [marker.subject for marker in report.uncertainty_markers] == [
        repr(unscored.location)
    ]
    assert "no per-region extraction score" in report.uncertainty_markers[0].reason
    # and the count it publishes has the true denominator, not 0 of 0
    assert "0 of 2 region(s) reader attempted" in report.reliability_information
    assert "1 of them were read but carry no per-region" in report.reliability_information

    # the unscored region's text is not lost from the artifact either: it still
    # reaches `raw_extracted_text` through `reader_output`, independently.
    assert "read from a PDF text layer" in pipeline.reader_output(reading).raw_extracted_text


# ── F-019: the reader -> parser pipe, and what now crosses the boundary ───
#
# `parser.py`'s own types are exercised here rather than in
# `tests/unit/test_input_engine_parser.py` because THIS is the pipe: every one
# of them exists to carry `reader`'s output into `parser` and out the far side
# as evidence, and a test that built an `ExtractedRegion` in isolation would
# prove the dataclass, not the arrow.


def test_extracted_regions_carries_readers_text_location_and_score_unchanged() -> None:
    """The arrow itself. Every value is `reader`'s, and the score is asserted
    by IDENTITY, not equality — an equal-but-recomputed `Decimal` would mean
    something in between had touched it (INV-2).
    """
    score = Decimal("0.3100")
    region = reader.TextRegion(
        text="Total 1,18,OOO.00",
        location=reader.SourceLocation(page_index=0, left=60.0, top=76.0, right=142.0, bottom=94.0),
        extraction_confidence=score,
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.OCR, pages_read=1)

    (carried,) = pipeline.extracted_regions(reading)

    assert carried.text == "Total 1,18,OOO.00"
    assert carried.box.left == region.location.left
    assert carried.box.top == region.location.top
    assert carried.box.right == region.location.right
    assert carried.box.bottom == region.location.bottom
    assert carried.extraction_confidence is score


def test_extracted_regions_converts_a_zero_based_page_index_into_a_one_based_page() -> None:
    """The one number this pipeline changes, and it is a UNIT not a value:
    `reader.SourceLocation.page_index` counts from 0, `parser.BoundingBox.page`
    counts from 1. Page three must arrive as page three.
    """
    third_page_index = 2
    third_page_number = 3
    region = reader.TextRegion(
        text="Amount 19800.00",
        location=reader.SourceLocation(
            page_index=third_page_index, left=1.0, top=2.0, right=3.0, bottom=4.0
        ),
        extraction_confidence=None,
    )
    reading = reader.Reading(regions=(region,), backend=reader.Backend.PDF_TEXT_LAYER, pages_read=3)

    (carried,) = pipeline.extracted_regions(reading)

    assert carried.box.page == third_page_number


def test_extracted_regions_hands_on_an_unscored_region_rather_than_filtering_it_out() -> None:
    """`region_readings` DROPS an unscored region, because
    `confidence_report.RegionReading` cannot represent one. `extracted_regions`
    must NOT: `parser` maps geometry and text, neither of which needs a score,
    and dropping it here would lose the region's name and location as well as
    its (absent) score. What cannot be built from it is decided once, later.
    """
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

    carried = pipeline.extracted_regions(reading)
    both_regions = 2

    assert len(carried) == both_regions
    assert [region.text for region in carried] == ["scored by OCR", "read from a PDF text layer"]
    assert carried[1].extraction_confidence is None
    # and the contrast that makes the asymmetry deliberate rather than accidental
    assert len(pipeline.region_readings(reading)) == 1


def test_parser_numbers_mapped_fields_within_each_page_in_readers_own_order() -> None:
    """`parser` assigns the name, and the name is the place. The ordinal
    restarts on each page: two pages, two "region 1"s, and no collision.

    `reader`'s order is preserved exactly — §1.2 forbids reordering, and a
    mapping that sorted would attach page 2's score to page 1's value.
    """
    regions = tuple(
        parser.ExtractedRegion(
            text=text,
            box=parser.BoundingBox(page=page, left=0.0, top=top, right=10.0, bottom=top + 5.0),
            extraction_confidence=None,
        )
        for text, page, top in (
            ("TAX INVOICE", 1, 0.0),
            ("GSTIN 27AAECS1234F1Z5", 1, 10.0),
            ("Amount 19800.00", 2, 0.0),
        )
    )

    mapped = parser.map_fields(regions)

    assert [field.name for field in mapped] == [
        "page 1 region 1",
        "page 1 region 2",
        "page 2 region 1",
    ]
    assert [field.value for field in mapped] == [
        "TAX INVOICE",
        "GSTIN 27AAECS1234F1Z5",
        "Amount 19800.00",
    ]
    # the source reference §1.3 requires every mapping to retain
    assert mapped[2].source_location == repr(regions[2].box)


def test_a_mapped_field_name_names_no_business_concept() -> None:
    """§1.3's boundary: *"it may identify a field labelled 'Supplier', it may
    not conclude that party is a supplier."* The name `parser` assigns is a
    locator, so it cannot be wrong about the business at all — asserted against
    the same forbidden vocabulary `test_input_engine_parser.py` applies to
    parser's own output types.
    """
    forbidden = (
        "account",
        "ledger",
        "debit",
        "credit",
        "supplier",
        "vendor",
        "customer",
        "total",
        "tax",
        "gst",
        "amount",
        "invoice",
    )
    region = parser.ExtractedRegion(
        text="Supplier: Acme Traders",
        box=parser.BoundingBox(page=1, left=0.0, top=0.0, right=10.0, bottom=10.0),
        extraction_confidence=None,
    )

    (mapped,) = parser.map_fields((region,))

    for word in forbidden:
        assert word not in mapped.name.lower(), (
            f"the mapped field name {mapped.name!r} contains {word!r}. parser reports "
            "structure; what a value MEANS is the Understanding Engine's."
        )
    # ... while the value it names is the document's own text, untouched
    assert mapped.value == "Supplier: Acme Traders"


def test_two_mapped_fields_sharing_a_name_are_refused_at_the_structure() -> None:
    """A repeated name makes "which score belongs to which value?" unanswerable.
    `StructuredDocument` and `ConfidenceReport` each already refuse it; this
    refuses it at the sub-engine that produced it, which is where the mistake
    is fixable.
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0)
    twice = tuple(
        parser.MappedField(
            name="page 1 region 1",
            value=value,
            source_location=repr(box),
            extraction_confidence=None,
        )
        for value in ("first", "second")
    )

    with pytest.raises(ValueError, match="two mapped fields share one name"):
        parser.ParsedStructure(
            source_reference="upload:x.pdf",
            page_count=1,
            regions=(),
            tables=(),
            mapped_fields=twice,
        )


@pytest.mark.parametrize(
    ("name", "value", "source_location"),
    [
        ("   ", "Amount 19800.00", "BoundingBox(page=1)"),
        ("page 1 region 1", "   ", "BoundingBox(page=1)"),
        ("page 1 region 1", "Amount 19800.00", "   "),
    ],
)
def test_a_mapped_field_missing_any_of_name_value_or_source_is_refused(
    name: str, value: str, source_location: str
) -> None:
    """`ENGINE_1_INPUT_ENGINE_RULES.md:245` — a value carried without all three
    is not evidence. Blank-after-stripping counts as missing: a padded blank
    claims a traceability it does not have, which is worse than admitting none.
    """
    with pytest.raises(ValueError, match="must not be empty or blank"):
        parser.MappedField(
            name=name, value=value, source_location=source_location, extraction_confidence=None
        )


def test_an_extracted_region_with_no_text_is_refused_rather_than_mapped_as_empty() -> None:
    """ABSENT and READ-AND-EMPTY are two states
    (`ENGINE_1_INPUT_ENGINE_RULES.md:569`). `reader` never emits a blank span,
    so this refuses a caller's mistake before it becomes an evidence value that
    asserts a reading nobody made.
    """
    with pytest.raises(ValueError, match="must not be empty or blank"):
        parser.ExtractedRegion(
            text="   ",
            box=parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0),
            extraction_confidence=None,
        )


def test_parsed_fields_mirrors_the_exact_score_object_and_the_name_parser_gave() -> None:
    score = Decimal("0.2800")
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0)
    structure = parser.ParsedStructure(
        source_reference="upload:scan.png",
        page_count=1,
        regions=(),
        tables=(),
        mapped_fields=(
            parser.MappedField(
                name="page 1 region 1",
                value="GSTIN 27AAEC",
                source_location=repr(box),
                extraction_confidence=score,
            ),
        ),
    )

    (built,) = pipeline.parsed_fields(structure)

    assert built.field_name == "page 1 region 1"
    assert built.extraction_confidence is score


def test_an_unscored_reading_is_skipped_rather_than_given_an_invented_score() -> None:
    """THE TEXT-LAYER GAP, PINNED AS THE HONEST STATE IT IS.

    `reader.read_pdf_text_layer` scores nothing — no recogniser ran — and
    `Provenance.confidence` is mandatory with no member meaning "not measured".
    `1.0000` is the default `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids and
    `0.0000` asserts a measurement nobody made, so
    `ENGINE_1_INPUT_ENGINE_RULES.md:245` applies: not all three, therefore not
    emitted.

    This test goes RED the day someone makes an unscored mapping produce a
    field, which is exactly right — that change needs a §M amendment to a
    frozen schema, and it must not arrive quietly. Until then the SCORED
    mapping beside it must still come through, so "skipped" can never
    degenerate into "nothing works".
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0)
    structure = parser.ParsedStructure(
        source_reference="upload:mixed.pdf",
        page_count=1,
        regions=(),
        tables=(),
        mapped_fields=(
            parser.MappedField(
                name="page 1 region 1",
                value="read from a PDF text layer",
                source_location=repr(box),
                extraction_confidence=None,
            ),
            parser.MappedField(
                name="page 1 region 2",
                value="scored by OCR",
                source_location=repr(box),
                extraction_confidence=Decimal("0.7500"),
            ),
        ),
    )

    scored = pipeline.parsed_fields(structure)
    fields = pipeline.detected_fields(structure, recorded_at=RECORDED_AT)

    assert [field.field_name for field in scored] == ["page 1 region 2"]
    assert [field.name for field in fields] == ["page 1 region 2"]
    assert [field.value for field in fields] == ["scored by OCR"]


def test_detected_fields_carry_the_source_the_score_and_the_callers_own_clock() -> None:
    """Rule 4's three requirements, each asserted against the sub-engine that
    owns it — and the timestamp asserted against the caller's instant, because
    a clock read inside `pipeline` would make two identical runs differ.
    """
    score = Decimal("0.3100")
    box = parser.BoundingBox(page=2, left=60.0, top=76.0, right=142.0, bottom=94.0)
    structure = parser.ParsedStructure(
        source_reference="upload:scan.png",
        page_count=2,
        regions=(),
        tables=(),
        mapped_fields=(
            parser.MappedField(
                name="page 2 region 1",
                value="Total 1,18,OOO.00",
                source_location=repr(box),
                extraction_confidence=score,
            ),
        ),
    )

    (field,) = pipeline.detected_fields(structure, recorded_at=RECORDED_AT)

    assert field.name == "page 2 region 1"
    assert field.value == "Total 1,18,OOO.00"
    assert field.provenance.source_type is SourceType.DOCUMENT
    assert field.provenance.source_id == "upload:scan.png"
    assert field.provenance.evidence_reference == repr(box)
    assert field.provenance.confidence is score
    assert field.provenance.timestamp == RECORDED_AT
    assert field.provenance.corroborated is Corroborated.NOT_ASSESSED


def test_a_scored_reading_reaches_the_artifact_with_its_score_on_both_sides() -> None:
    """`KNOWN_FAILURES.md` F-019, ITS OWN DEMONSTRATION, RUN THE OTHER WAY.

    F-019 recorded this exact input — an OCR reading whose two regions scored
    0.3100 and 0.2800, one of them the classic low-confidence misread
    `1,18,OOO.00` with letter-O where zeros belong — producing an artifact with
    `confidence_scores=()`, `uncertainty_markers=()` and `risky_fields=()`. The
    reading arrived confident and empty and nothing downstream could tell it
    had ever been doubtful.

    Every module below is the real one. PaddleOCR is genuinely absent here
    (F-002), so `reader.read` cannot produce this reading in this environment —
    the reading is therefore CONSTRUCTED from `reader`'s own real types and run
    through the real `parser`, `confidence_report` and `assembly`, including
    `DocumentEvidenceObject`'s own validators. That is the honest maximum: the
    absent thing is the recogniser, and nothing stands in for it (§J.6).
    """
    lower, higher = Decimal("0.2800"), Decimal("0.3100")
    misread = "Total 1,18,OOO.00"
    reading = reader.Reading(
        regions=(
            reader.TextRegion(
                text=misread,
                location=reader.SourceLocation(
                    page_index=0, left=60.0, top=76.0, right=142.0, bottom=94.0
                ),
                extraction_confidence=higher,
            ),
            reader.TextRegion(
                text="GSTIN 27AAEC",
                location=reader.SourceLocation(
                    page_index=0, left=60.0, top=110.0, right=231.0, bottom=128.0
                ),
                extraction_confidence=lower,
            ),
        ),
        backend=reader.Backend.OCR,
        pages_read=1,
    )

    structure = parser.ParsedStructure(
        source_reference="upload:scan.png",
        page_count=1,
        regions=(),
        tables=(),
        mapped_fields=parser.map_fields(pipeline.extracted_regions(reading)),
    )
    report = confidence_report_module.record_confidence(
        a_cleaned_document(),
        pipeline.region_readings(reading),
        pipeline.parsed_fields(structure),
        pipeline.missing_fields(structure),
    )
    artifact = assembly.assemble(
        parts=assembly.SubEngineOutputs(
            cleaner=pipeline.cleaner_output(a_cleaned_document()),
            reader=pipeline.reader_output(reading),
            parser=pipeline.parser_output(structure, recorded_at=RECORDED_AT),
            confidence=pipeline.confidence_output(report),
        ),
        identity=an_identity(),
        source_references=("upload:scan.png",),
    )

    # the two scores are IN the artifact, on the values they were measured on
    fields = artifact.structured_document.detected_fields
    assert [field.value for field in fields] == [misread, "GSTIN 27AAEC"]
    assert [field.provenance.confidence for field in fields] == [higher, lower]
    # ... and the same two numbers, under the same two names, in the report
    assert [
        (score.field_name, score.confidence)
        for score in artifact.confidence_report.confidence_scores
    ] == [("page 1 region 1", higher), ("page 1 region 2", lower)]
    # every one of them locatable on the page it was read from
    for field in fields:
        assert "BoundingBox(page=1" in field.provenance.evidence_reference
    # and the count reader actually attempted, not the "0 of 0" F-019 recorded
    assert "0 of 2 region(s) reader attempted" in (
        artifact.confidence_report.reliability_information
    )
    assert "2 field(s) carry a confidence score from parser" in (
        artifact.confidence_report.reliability_information
    )


def test_a_field_whose_provenance_disagrees_with_the_report_is_refused_by_the_schema() -> None:
    """FALSIFICATION: the agreement above must be enforced, not merely produced.

    `evidence.py`'s `_every_reading_is_scored_and_the_scores_agree` had never
    executed one iteration before this fix, because `detected_fields` was always
    empty (F-019). It is live now, so it is attacked here: a field built with
    one score and a report built with another must be refused, loudly, rather
    than reconciled.
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0)
    structure = parser.ParsedStructure(
        source_reference="upload:scan.png",
        page_count=1,
        regions=(),
        tables=(),
        mapped_fields=(
            parser.MappedField(
                name="page 1 region 1",
                value="Amount 19800.00",
                source_location=repr(box),
                extraction_confidence=Decimal("0.3100"),
            ),
        ),
    )
    disagreeing = ConfidenceReport(
        confidence_scores=(
            FieldConfidence(field_name="page 1 region 1", confidence=Decimal("0.9900")),
        ),
        uncertainty_markers=(),
        reliability_information="a report whose score disagrees with the field's own",
        risky_fields=(),
    )

    with pytest.raises(ValidationError, match="disagree"):
        assembly.assemble(
            parts=assembly.SubEngineOutputs(
                cleaner=pipeline.cleaner_output(a_cleaned_document()),
                reader=pipeline.reader_output(
                    reader.Reading(regions=(), backend=reader.Backend.OCR, pages_read=0)
                ),
                parser=pipeline.parser_output(structure, recorded_at=RECORDED_AT),
                confidence=pipeline.confidence_output(disagreeing),
            ),
            identity=an_identity(),
            source_references=("upload:scan.png",),
        )


def test_pipeline_reads_no_clock_of_its_own() -> None:
    """The structural half of the reproducibility claim. A behavioural test
    cannot see a `datetime.now()` called once per run and compared against
    nothing, so the module's own CODE is read — the same technique
    `test_the_pipeline_reads_the_cleaned_document_not_the_original` uses, for
    the same reason.

    Parsed rather than grepped, deliberately: this module's docstrings discuss
    `datetime.now()` at length precisely because it is forbidden, and a string
    search would fail on the explanation instead of on a call. The AST sees
    code only.
    """
    tree = ast.parse(pathlib.Path(inspect.getfile(pipeline)).read_text(encoding="utf-8"))
    clocks = sorted(
        {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in {"now", "utcnow", "today"}
        }
    )

    assert clocks == [], (
        f"`pipeline` reaches for a clock ({clocks}). Every timestamp it writes into "
        "a Provenance must be the caller's, or two runs of one document produce two "
        "different artifacts (services/pipeline.py, `Sources`)."
    )


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

    output = pipeline.parser_output(structure, recorded_at=RECORDED_AT)

    # LAYOUT ALONE NAMES NOTHING. This structure has a region carrying text and
    # a table carrying a cell, and no `mapped_fields` at all — because no
    # reading was supplied to map. A detected field here could only have been
    # invented, and none is.
    assert structure.mapped_fields == ()
    assert output.detected_fields == ()
    assert output.detected_tables == ()
    # but nothing found is lost: it is rendered into the one channel available
    assert "Amount 4500.00" in output.document_structure
    assert "4500.00" in output.document_structure


def test_a_table_cell_still_becomes_no_detected_table_however_well_it_is_laid_out() -> None:
    """The half of defect 4 the F-019 fix did NOT close, pinned so it cannot
    quietly change. A `parser.Cell` carries a row, a column and a box; no
    sub-engine gives it a name or a score, so a `DetectedTable` — which needs a
    complete `Provenance` (INV-11) — could only be built by inventing both.

    A mapped, SCORED field is present here on purpose: it proves the empty
    `detected_tables` is a fact about tables rather than about this structure
    being empty.
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=10.0, bottom=10.0)
    structure = parser.ParsedStructure(
        source_reference="upload:x.pdf",
        page_count=1,
        regions=(),
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
        mapped_fields=(
            parser.MappedField(
                name="page 1 region 1",
                value="4500.00",
                source_location=repr(box),
                extraction_confidence=Decimal("0.9100"),
            ),
        ),
    )

    output = pipeline.parser_output(structure, recorded_at=RECORDED_AT)

    assert len(output.detected_fields) == 1
    assert output.detected_tables == ()
    assert "cell rows=0:1" in output.document_structure


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


# ── ONE pipeline: every stage reads the CLEANED artifact ──────────────────
#
# These replace two tests of `rasterise_first_page_for_cleaning`, a legacy
# adapter that existed only because `cleaner` emitted a bitmap and could not
# take a PDF. The F-017 migration removed the reason for it, so the adapter is
# deleted and these pin the architecture that replaced it.


def test_the_pipeline_reads_the_cleaned_document_not_the_original() -> None:
    """The bypass F-012 recorded, now impossible to reintroduce silently.

    `run` hands `reader` and `parser` the CLEANED artifact's payload. Before
    the migration each re-opened `intake.document`, correctly, because the
    cleaned form was a bitmap and reading a bitmap of a PDF destroys its text
    layer. This asserts on the source text of `run` itself, because the defect
    is structural: a future edit passing `intake.document` to a later stage
    would restore two pipelines while every behavioural test still passed.
    """
    source = inspect.getsource(pipeline.run)
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is the instrumentation rather than ours. Skipped under mutation "
            "only; it runs in every ordinary suite."
        )

    after_cleaner = source.split("_payload_of(cleaned)", 1)[1]
    assert "intake.document" not in after_cleaner, (
        "no stage after `cleaner` may read the ORIGINAL document. Every one must "
        "read the cleaned artifact's payload, or there are two pipelines again."
    )


def test_a_missing_artifact_fails_loudly_rather_than_falling_back() -> None:
    """A fallback to `intake.document` would reinstate the bypass while every
    behavioural test kept passing — the exact shape of a false green (§J.(a)).
    """
    without_artifact = cleaner.CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=cleaner.PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    with pytest.raises(pipeline.PipelineError, match="no media-aware artifact"):
        pipeline._payload_of(without_artifact)


def test_the_legacy_rasterisation_adapter_is_gone() -> None:
    """It existed only because `cleaner` could not take a PDF. That is fixed,
    so the adapter is dead code and dead code that still imports cleanly is the
    kind that gets called again by mistake.
    """
    assert not hasattr(pipeline, "rasterise_first_page_for_cleaning")


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
        recorded_at: datetime = ...,
        human_business_context: HumanBusinessContext | None = ...,
    ) -> DocumentEvidenceObject: ...


run_as_a_careless_caller_would = cast(_LooseRun, pipeline.run)


def test_omitting_settings_raises_naming_settings_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="settings"):
        run_as_a_careless_caller_would(
            a_document_intake(), identity=an_identity(), recorded_at=RECORDED_AT
        )


def test_omitting_identity_raises_naming_identity_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="identity"):
        run_as_a_careless_caller_would(
            a_document_intake(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )


def test_omitting_intake_raises_naming_intake_before_any_stage_runs() -> None:
    with pytest.raises(TypeError, match="intake"):
        run_as_a_careless_caller_would(
            identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )


def test_omitting_recorded_at_raises_naming_it_before_any_stage_runs() -> None:
    """The clock is the caller's, and omitting it must fail rather than fall
    back to `datetime.now()`. A "now" default would look harmless in the
    signature and would silently make two runs of the same document differ —
    see `detected_fields` in `pipeline.py` for the measured consequence.
    """
    with pytest.raises(TypeError, match="recorded_at"):
        run_as_a_careless_caller_would(
            a_document_intake(), identity=an_identity(), settings=a_pipeline_settings()
        )


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
    assert parameters["recorded_at"].default is inspect.Parameter.empty
    # the one parameter that IS allowed a default, and only because
    # ENGINE_1_INPUT_ENGINE_RULES.md:138 requires Engine 1 to work without one
    assert parameters["human_business_context"].default is None
    # ... and it is the ONLY one. Enumerated rather than spot-checked, so a
    # parameter added later with a quiet default cannot slip past this test.
    defaulted = [
        name
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty
    ]
    assert defaulted == ["human_business_context"]


# ── PipelineStageError names the actual failing stage, not a generic one ──


def test_pipeline_stage_error_message_names_the_stage_and_carries_the_cause() -> None:
    intake = pipeline.DocumentIntake(
        document=b"", media_type=reader.MediaType.IMAGE, source_references=("upload:empty",)
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

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
