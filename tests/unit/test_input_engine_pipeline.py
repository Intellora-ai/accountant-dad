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
import math
import pathlib
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf
import pytest
from authored_source import authored_function_source, authored_source
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DocumentEvidenceObject,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
)
from accountant_dad.confidence import UnmeasuredType
from accountant_dad.engines.input_engine import (
    assembly,
    classification,
    cleaner,
    config,
    measurement,
    parser,
    pipeline,
    reader,
)
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
    def insert_image(self, rect: object, *, stream: bytes) -> None: ...
    def get_pixmap(self, *, dpi: int) -> _Pixmap: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def __getitem__(self, index: int) -> _AuthoringPage: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


class _MakeRect(Protocol):
    def __call__(self, x0: float, y0: float, x1: float, y1: float) -> object: ...


open_pdf = cast(_NewDocument, pymupdf.open)
#: `pymupdf.Rect`, declared exactly as the image fixtures below call it. The
#: same facade `test_input_engine_reader.py` already declares for the same
#: dependency; that one is module-private to that file.
rectangle = cast(_MakeRect, pymupdf.Rect)

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


def a_confidence_parameters(
    vision_fallback: Decimal = NO_FALLBACK,
) -> config.ConfidenceParameters:
    """All sixteen confidence parameters, in full, because none has a default.

    `ENGINE_1_CONFIDENCE_PARAMETERS.md` marks every one of the sixteen `UNSET`,
    and `CLAUDE.md` §P forbids a default for any of them — so anything that runs
    Engine 1 must state all sixteen, and this factory is what that costs.

    These are the TEST's own numbers and not recommended operating points
    (Law 52). Only `ocr_vision_fallback` changes any behaviour today: it is the
    one parameter Engine 1's pipeline consumes, handed to `reader.read` as its
    vision-fallback threshold. The other fifteen are carried and unread, which
    `MEASUREMENT_FRAMEWORK.md:258` — *"confidence gates nothing"* — says is the
    correct state of this build.
    """
    return config.ConfidenceParameters(
        ocr_region_accept=Decimal("0.0000"),
        ocr_vision_fallback=vision_fallback,
        field_confidence_floor=Decimal("0.0000"),
        field_risky_mark=Decimal("0.0000"),
        document_confidence_floor=Decimal("0.0000"),
        human_review_trigger=Decimal("0.0000"),
        retry_trigger=Decimal("0.0000"),
        retry_max_attempts=0,
        classification_accept=Decimal("0.0000"),
        table_structure_accept=Decimal("0.0000"),
        table_cell_accept=Decimal("0.0000"),
        capture_fidelity_floor=Decimal("0.0000"),
        document_score_rule=config.DocumentScoreRule.MIN,
        document_score_weights={"the only field": Decimal("1.0000")},
        worst_k=1,
        processing_budget_ms=1,
    )


def a_pipeline_settings(
    *,
    cleaner_settings: cleaner.CleanerSettings | None = None,
    render_dpi: int = RENDER_DPI,
    confidence_parameters: config.ConfidenceParameters | None = None,
    table_structure: parser.TableStructureSettings | None = None,
    measurement_store: Path | None = None,
) -> pipeline.PipelineSettings:
    """There is ONE way to set the vision-fallback threshold here, and it is by
    passing the whole `ConfidenceParameters`.

    A second `vision_fallback` shortcut sat here briefly and was removed: it
    would have been a second representation of `ocr_vision_fallback` inside the
    tests, which is the exact defect F-018 removed from the production settings
    one line away. One source of truth on both sides (Law 19).
    """
    return pipeline.PipelineSettings(
        cleaner_settings=cleaner_settings if cleaner_settings is not None else a_cleaner_settings(),
        render_dpi=render_dpi,
        confidence_parameters=(
            confidence_parameters
            if confidence_parameters is not None
            else a_confidence_parameters()
        ),
        table_structure=table_structure,
        measurement_store=measurement_store,
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


def test_a_zero_byte_document_crosses_the_boundary_as_an_artifact_not_an_error() -> None:
    """A CORRECTED EXPECTATION (§J.4, Law 4, §M — the documents win).

    This test used to be `test_cleaner_failing_first_preserves_nothing_and_
    names_itself` and asserted that zero bytes raise `PipelineStageError`. It
    pinned behaviour that three locked documents forbid:

      `APPLICATION_LAYER_CONTRACTS.md:30` — *"**Business** — unreadable,
      corrupt, zero-byte: an object is produced recording the failure.
      **Runtime** — engine crash: nothing produced"*
      `APPLICATION_LAYER_CONTRACTS.md:27` — *"a document that cannot be read
      produces an object recording that failure, never a fabricated one"*
      `COMMUNICATION_RULES_INPUT_ENGINE.md:159` — *"The Input Engine does not
      halt the pipeline. Unreadable regions, damaged artifacts and failed
      extractions cross the boundary as low confidence and named uncertainty,
      not as errors."*

    WHY IT MATTERS RATHER THAN BEING A TECHNICALITY. Raising made a BUSINESS
    outcome — this scan is unreadable — indistinguishable from a CRASH — the
    code is broken. The Application Layer cannot route what it cannot tell
    apart, so an unreadable receipt that should become a clarification question
    looked exactly like an outage.

    THE JOB WAS ALREADY ASSIGNED TO THIS MODULE, IN WRITING.
    `parser.DocumentUnreadableError`'s own docstring: *"The Input Engine PARENT
    is what must not halt the pipeline (COMMUNICATION_RULES_INPUT_ENGINE.md:159);
    it converts this into low confidence and a named uncertainty. The parser
    cannot do that itself, because only the `confidence` sub-engine may produce
    a score."* `pipeline.run` is that parent. It never implemented its half.

    NOT A WEAKENING: the assertion count goes UP, and the artifact is checked
    for what it must NOT contain as hard as for what it must.
    """
    intake = pipeline.DocumentIntake(
        document=b"", media_type=reader.MediaType.IMAGE, source_references=("upload:empty",)
    )

    evidence = pipeline.run(
        intake,
        identity=an_identity(),
        settings=a_pipeline_settings(),
        recorded_at=RECORDED_AT,
    )

    # it crossed, as an artifact
    assert isinstance(evidence, DocumentEvidenceObject)
    assert evidence.source_references == ("upload:empty",)

    # nothing was read, and nothing was invented in its place
    assert evidence.structured_document.extracted_text == ""
    assert evidence.structured_document.detected_fields == ()
    assert evidence.structured_document.detected_tables == ()
    assert evidence.confidence_report.confidence_scores == ()
    assert evidence.confidence_report.risky_fields == ()

    # and the failure is NAMED, not merely implied by emptiness
    (marker,) = evidence.confidence_report.uncertainty_markers
    assert marker.subject == "upload:empty"
    assert marker.reason.startswith("this document could not be read at the 'cleaner' stage:")
    # the real cause travels verbatim; no summary stands in for it. Pinned to
    # cleaner's own exact words, measured, not paraphrased.
    assert "no bytes were supplied; there is nothing to clean." in marker.reason
    assert "none is invented in its place" in marker.reason

    # and the report says what happened, including which stages got as far as
    # completing — "none", here, because cleaner is the first
    reliability = evidence.confidence_report.reliability_information
    assert "Engine 1 stopped at the 'cleaner' stage" in reliability
    assert "Stages that completed first: none." in reliability
    assert "No confidence score is reported because nothing was measured" in reliability


def test_a_corrupt_pdf_crosses_as_an_artifact_too_naming_its_own_cause() -> None:
    """The second of the three conditions `APPLICATION_LAYER_CONTRACTS.md:30`
    names as business — *corrupt* — on a real corrupt PDF, not a mock of one.

    Measured: PyMuPDF raises `FileDataError` on these bytes. That class is
    PyMuPDF's own verdict about the FILE, not a crash in our code, which is why
    it counts as business here — see `pipeline.BUSINESS_FAILURE`.
    """
    intake = pipeline.DocumentIntake(
        document=b"%PDF-1.4 garbage not a pdf at all",
        media_type=reader.MediaType.PDF,
        source_references=("upload:corrupt.pdf",),
    )

    evidence = pipeline.run(
        intake,
        identity=an_identity(),
        settings=a_pipeline_settings(),
        recorded_at=RECORDED_AT,
    )

    assert evidence.structured_document.detected_fields == ()
    assert evidence.confidence_report.confidence_scores == ()
    (marker,) = evidence.confidence_report.uncertainty_markers
    assert marker.subject == "upload:corrupt.pdf"
    assert "cleaner" in marker.reason


#: The business verdict injected at the `parser.parse` seam below. A REAL
#: `parser.DocumentUnreadableError`, built through its own constructor with its
#: own two arguments, so `str(exc)` is the sentence `parser` would really have
#: produced rather than a string this file invented.
REFUSED_BY_PARSER = parser.DocumentUnreadableError(
    "upload:refused.pdf", ("Docling reported no usable layout",)
)
PARSER_REFUSAL_TEXT = "upload:refused.pdf could not be parsed: Docling reported no usable layout"


def test_a_business_failure_after_two_stages_names_both_and_keeps_what_reader_read() -> None:
    """THE BUSINESS-FAILURE PATH, ENTERED WITH WORK ALREADY DONE.

    Every other test of this path fails at `cleaner` — the FIRST stage — so
    `_failure_artifact` has only ever been observed with nothing completed,
    nothing read and no human note. Three of its four honest-emptiness claims
    were therefore unread by any test, and emptiness is exactly what a bug here
    looks like.

    Measured at `d7a8ed9`, before this test existed: twelve mutants of
    `_failure_artifact` survived the whole suite, all of them reachable only
    with an earlier stage completed —
    `completed` deleted outright (`__mutmut_1`), each of the three stage names
    rewritten (`_3` … `_8`), `reader`'s real text replaced by `None`
    (`_13`), the human note dropped (`_18`, `_24`), and the separator that
    joins the completed names rewritten (`_59`, `_60`).

    `cleaner` and `reader` are genuinely run here, on a real PDF with a real
    text layer. The refusal is injected at the `parser.parse` seam for the
    reason `test_parser_failing_after_cleaner_and_reader_preserves_both_and_
    names_parser` already states: no document this environment can process
    makes `parser` return a BUSINESS verdict after the first two stages
    succeed, and §J.7 permits faking exactly at that boundary. The verdict
    itself is a real `parser.DocumentUnreadableError`, which is why `_stopped`
    routes it to an artifact rather than raising.
    """
    note = a_human_business_context("Advance paid to supplier, invoice to follow.")
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:refused.pdf", "email:thread-9"),
    )

    seen: dict[str, object] = {}

    def refusing_parse(
        source: pathlib.Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        # Recorded, not discarded, for the same reason
        # `test_parser_failing_after_cleaner_and_reader...` records it: this
        # proves the third stage was really ENTERED, with `reader`'s real
        # regions, rather than merely that something raised.
        seen.update(
            source=source,
            source_reference=source_reference,
            extracted_regions=extracted_regions,
            table_structure=table_structure,
        )
        raise REFUSED_BY_PARSER

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(parser, "parse", refusing_parse)
        evidence = pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
            human_business_context=note,
        )

    # the third stage really ran, on the first source reference, carrying
    # `reader`'s real regions — the F-019 arrow holds on this path too
    assert seen["source_reference"] == "upload:refused.pdf"
    assert seen["extracted_regions"] != ()

    # `reader` really completed, so its real text is carried rather than
    # discarded because the run ended badly. Checked against this file's own
    # ground truth, not against whatever the run produced.
    extracted = evidence.structured_document.extracted_text
    assert extracted != ""
    for line in INVOICE_LINES:
        assert line in extracted

    # the caller's note travels the failing path untouched, exactly as it
    # travels the successful one
    assert evidence.human_business_context is note

    # nothing is invented for the stages that never ran
    assert evidence.structured_document.detected_fields == ()
    assert evidence.structured_document.detected_tables == ()
    assert evidence.confidence_report.confidence_scores == ()
    assert evidence.confidence_report.risky_fields == ()

    # and the two stages that DID complete are named, in order, by their own
    # lowercase names — "none" here would be a false statement about a run in
    # which two sub-engines really did produce something
    assert evidence.confidence_report.reliability_information == (
        f"no field was extracted: Engine 1 stopped at the 'parser' stage "
        f"because the document could not be read ({PARSER_REFUSAL_TEXT}). "
        "Stages that completed first: cleaner, reader. "
        "No confidence score is reported because nothing was measured; "
        "the absence is recorded rather than filled in."
    )

    # the marker names the FIRST source reference, carries the sub-engine's own
    # words verbatim, and states — word for word — why an artifact exists at all
    (marker,) = evidence.confidence_report.uncertainty_markers
    assert marker.subject == "upload:refused.pdf"
    assert marker.reason == (
        f"this document could not be read at the 'parser' stage: "
        f"{PARSER_REFUSAL_TEXT} No value was extracted from it and none is "
        "invented in its place; this artifact records the "
        "failure so the transaction can be routed rather than "
        "crashing (APPLICATION_LAYER_CONTRACTS.md:30, "
        "COMMUNICATION_RULES_INPUT_ENGINE.md:159)."
    )

    # `document_structure` says NOT PARSED and says which stage stopped it,
    # rather than carrying an empty string a reader would take for "no structure"
    assert evidence.structured_document.document_structure == (
        "not parsed: Engine 1 stopped at the 'parser' stage because the document could not be read."
    )


def test_the_failure_artifact_names_every_stage_that_completed_including_parser() -> None:
    """`run` cannot reach `_failure_artifact` with `parser` completed — the
    parser stage is the last one routed through `_stopped`, and at that point
    `preserved.parsed` is still `None`. So the `'parser'` entry in the
    completed-stages tuple is unobservable through `run`, and its two mutants
    (`_7`, `_8`) survived the whole suite at `d7a8ed9` for that reason.

    It is not dead code and it is not unkillable: `_failure_artifact` states
    what it does with `preserved`, and this calls it directly with all three
    stages recorded to hold it to that. Every input is a real object built by
    the module that owns it — a real `CleanedDocument`, a real `Reading` from
    `reader.read_pdf_text_layer` on a real PDF, and a real `ParsedStructure` —
    so what is asserted is the function's own behaviour, not a stand-in's.
    """
    reading = reader.read_pdf_text_layer(an_invoice_pdf())
    assert reading.regions != ()
    parsed = parser.ParsedStructure(
        source_reference="upload:late.pdf", page_count=1, regions=(), tables=()
    )
    preserved = pipeline.PipelinePartialResult(
        cleaned=a_cleaned_document(), reading=reading, parsed=parsed
    )
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:late.pdf",),
    )
    given = pipeline._RunInputs(intake=intake, identity=an_identity(), human_business_context=None)

    evidence = pipeline._failure_artifact("confidence", REFUSED_BY_PARSER, preserved, given)

    assert "Stages that completed first: cleaner, reader, parser. " in (
        evidence.confidence_report.reliability_information
    )
    # and reader's real text is still what reaches the artifact on this path
    assert evidence.structured_document.extracted_text == (
        pipeline.reader_output(reading).raw_extracted_text
    )


def test_a_blank_source_reference_is_refused_at_construction_not_deep_in_a_failure() -> None:
    """FOUND BY RED-TEAMING THE BUSINESS-FAILURE PATH, AND FIXED AT THE ROOT
    (§J.10, Law 13, §I.12 — fix the CLASS, not the instance).

    THE BUG, MEASURED. `DocumentIntake` refused an EMPTY tuple of source
    references but accepted a tuple holding a blank string. Feed that a
    business failure — `run(intake(document=b"", source_references=("",)))` —
    and `_failure_artifact` tried to build an `UncertaintyMarker` whose
    `subject` is that blank reference. `UncertaintyMarker.subject` is
    `NonEmptyText`, so pydantic raised `ValidationError` FROM INSIDE the except
    block that exists to handle failures. The result escaped every discipline
    this module has: not a `PipelineStageError`, no stage named, no `preserved`,
    and no artifact either — the one shape `run` is never supposed to produce.

    WHY THE FIX IS HERE AND NOT IN `_failure_artifact`. Catching it there would
    patch the instance. A blank source reference is invalid on EVERY path, not
    just the failing one: `parser._reject_blank` refuses it later, and
    `DocumentEvidenceObject`'s own schema refuses it later still. Refusing it at
    construction is the same job `__post_init__` already does for the empty
    tuple, one step earlier than any sub-engine, which is where garbage input
    belongs (Law 23).
    """
    with pytest.raises(ValueError, match="blank") as raised:
        pipeline.DocumentIntake(
            document=b"x", media_type=reader.MediaType.IMAGE, source_references=("",)
        )
    assert "source_references" in str(raised.value)

    # whitespace is blank too — a reference of three spaces names nothing
    with pytest.raises(ValueError, match="blank"):
        pipeline.DocumentIntake(
            document=b"x", media_type=reader.MediaType.IMAGE, source_references=("   ",)
        )

    # and a blank one hiding behind a good one is still refused
    with pytest.raises(ValueError, match="blank"):
        pipeline.DocumentIntake(
            document=b"x",
            media_type=reader.MediaType.IMAGE,
            source_references=("upload:real.png", ""),
        )

    # the valid case still constructs, so the guard is not refusing everything
    assert pipeline.DocumentIntake(
        document=b"x", media_type=reader.MediaType.IMAGE, source_references=("upload:real.png",)
    ).source_references == ("upload:real.png",)


def test_a_runtime_failure_still_raises_and_is_never_dressed_as_a_business_outcome() -> None:
    """THE OTHER SIDE OF THE LINE, AND THE ONE THAT MATTERS MOST.

    `APPLICATION_LAYER_CONTRACTS.md:30` keeps two events apart: a document that
    cannot be read (emit an artifact) and an engine that crashed (produce
    nothing). Collapsing them in the EMIT direction is the worse error of the
    two: it would report "this document is unreadable" when the truth is "our
    OCR is not installed" — a false statement about the user's document, and
    exactly the fabrication `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids.

    PaddleOCR's absence is real here (`KNOWN_FAILURES.md` F-002) and is used as
    the failure rather than mocked (§J.6). The document itself is a perfectly
    good PNG — `cleaner` succeeds on it first.
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
    assert isinstance(raised.value.cause, ModuleNotFoundError)
    # and the partial work is still preserved for the runtime case, unchanged
    assert raised.value.preserved.cleaned is not None


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
    """UNCHANGED SUBJECT, CORRECTED TRIGGER. What must hold is untouched: when
    `parser` is the stage that fails, it is NAMED, and `cleaner`'s and
    `reader`'s already-completed work survives on `preserved`.

    This used to reach `parser` with a blank source reference, relying on
    `parser._reject_blank`. `DocumentIntake` now refuses a blank reference at
    construction — the root-cause fix for the hole red-teaming found, see
    `test_a_blank_source_reference_is_refused_at_construction_not_deep_in_a_
    failure` — so that input can no longer reach `parser`, which is the point
    of the guard.

    The failure is therefore injected at the `parser.parse` SEAM, the same way
    and for the same reason `test_input_engine_pipeline_redteam.py` injects one
    at `confidence_report.record_confidence`: no real document this environment
    can process makes `parser` fail after `cleaner` and `reader` both succeed,
    and §J.7 permits faking exactly at the boundary. `cleaner` and `reader` are
    genuine here and genuinely succeed on a real PDF first, so what is under
    test — the pipeline's response to its third stage failing — is real.
    """
    injected = RuntimeError("Docling could not lay this document out")
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:invoice.pdf",),
    )

    seen: dict[str, object] = {}

    def refusing_parse(
        source: pathlib.Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        # Recorded, not discarded: what `parser` was HANDED before it failed is
        # asserted below, so this fake proves the third stage was entered
        # properly rather than merely that something raised.
        seen.update(
            source=source,
            source_reference=source_reference,
            extracted_regions=extracted_regions,
            table_structure=table_structure,
        )
        raise injected

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(parser, "parse", refusing_parse)
        with pytest.raises(pipeline.PipelineStageError) as raised:
            pipeline.run(
                intake,
                identity=an_identity(),
                settings=a_pipeline_settings(),
                recorded_at=RECORDED_AT,
            )

    assert raised.value.stage == "parser"
    assert raised.value.cause is injected
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is not None
    assert raised.value.preserved.parsed is None
    assert raised.value.preserved.confidence is None
    # cleaner and reader really ran: their preserved output holds real content,
    # not an empty placeholder that would satisfy `is not None` alone
    assert raised.value.preserved.cleaned.artifact is not None
    assert raised.value.preserved.reading.regions != ()

    # and parser was entered with the real inputs, including reader's regions —
    # the F-019 arrow still carries on the path that ends in a failure
    assert seen["source_reference"] == "upload:invoice.pdf"
    assert seen["extracted_regions"] == pipeline.extracted_regions(raised.value.preserved.reading)
    assert seen["extracted_regions"] != ()


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

    # nothing is filtered, and reader's own order is kept. Asserted against
    # reader's OWN count rather than a literal: "one carried per region reader
    # produced" is the property, and a literal would still pass if a future
    # change dropped one region and duplicated another.
    assert len(readings) == len(reading.regions)
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
    assert [marker.subject for marker in report.uncertainty_markers] == [repr(unscored.location)]
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
    """`extracted_regions` hands on EVERY region `reader` produced, scored or
    not: `parser` maps geometry and text, neither of which needs a score, and
    dropping an unscored region here would lose its name and its location as
    well as its (absent) score. What cannot be built from it is decided once,
    later, by `detected_fields`.

    A CORRECTED PREMISE, NOT AN EASED ASSERTION (§J.4, Law 4). This docstring
    used to open "`region_readings` DROPS an unscored region, because
    `confidence_report.RegionReading` cannot represent one", and the last line
    asserted that drop as the deliberate contrast. Both halves have stopped
    being true: `ReadingState.READ_BUT_UNSCORED` landed, `RegionReading`
    represents exactly that region, and `region_readings`' filter was removed
    because its only reason had expired.

    So there is no longer an asymmetry to contrast, and the corrected
    assertion is STRONGER than the one it replaces: not "one function filters
    and the other does not", but "NEITHER filters, and both keep reader's
    count and reader's order". A regression in either function now fails here,
    where before a regression in `region_readings` towards carrying MORE would
    have failed a test that was pinning the wrong behaviour.
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

    assert len(carried) == len(reading.regions)
    assert [region.text for region in carried] == ["scored by OCR", "read from a PDF text layer"]
    assert carried[1].extraction_confidence is None
    # NEITHER conversion filters: both keep reader's count and reader's order,
    # so an unscored region is nameable and locatable on both routes.
    also_carried = pipeline.region_readings(reading)
    assert len(also_carried) == len(reading.regions)
    assert [region.text for region in also_carried] == [
        "scored by OCR",
        "read from a PDF text layer",
    ]
    assert also_carried[1].extraction_confidence is None


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


def test_an_unscored_reading_is_carried_and_says_it_was_never_scored() -> None:
    """THE TEXT-LAYER GAP, CLOSED BY AMENDMENT 5 — AND PINNED AT THE EXACT
    LINE BETWEEN "CARRIED" AND "INVENTED".

    This test used to be `test_an_unscored_reading_is_skipped_rather_than_
    given_an_invented_score`, and it said: *"This test goes RED the day someone
    makes an unscored mapping produce a field, which is exactly right — that
    change needs a §M amendment to a frozen schema, and it must not arrive
    quietly."* The amendment arrived, in writing
    (`docs/ARCHITECTURE_AMENDMENTS.md` Amendment 5, approved 2026-08-06), so
    the expectation is CORRECTED rather than eased: the old one described a
    schema that no longer exists.

    `reader.read_pdf_text_layer` still scores nothing — no recogniser runs —
    and no number has become honest since. `1.0000` is still the default
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids and `0.0000` still asserts a
    measurement nobody made. What changed is that the schema can now hold the
    ABSENCE of a measurement, so
    `ENGINE_1_INPUT_ENGINE_RULES.md:245`'s disjunction is satisfied by carrying
    all three rather than by emitting none.

    WHAT WOULD PROVE THE FIX WRONG, asserted directly rather than implied:

      * a number appearing on the unscored field — `1.0000`, `0.0000` or any
        other. Asserted by TYPE, so no value can slip through: a `Decimal` of
        any magnitude fails `isinstance(..., UnmeasuredType)`.
      * the sentinel spreading onto the SCORED field beside it, which would
        destroy a real measurement. Asserted by identity — the exact object
        `reader` produced, not merely an equal one.
      * the two mappings collapsing into one shape. Both are asserted
        separately, so "carried" can never degenerate into "everything is
        unmeasured" or "nothing works".
    """
    box = parser.BoundingBox(page=1, left=0.0, top=0.0, right=1.0, bottom=1.0)
    measured = Decimal("0.7500")
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
                extraction_confidence=measured,
            ),
        ),
    )

    scored = pipeline.parsed_fields(structure)
    unmeasured = pipeline.unmeasured_field_scores(structure)
    fields = pipeline.detected_fields(structure, recorded_at=RECORDED_AT)

    # BOTH mappings are now emitted, in `reader`'s order, with their text intact.
    assert [field.name for field in fields] == ["page 1 region 1", "page 1 region 2"]
    assert [field.value for field in fields] == [
        "read from a PDF text layer",
        "scored by OCR",
    ]

    # The unscored one carries the absence of a measurement, by TYPE. A number
    # of any magnitude fails this, which is the point.
    assert isinstance(fields[0].provenance.confidence, UnmeasuredType), (
        f"an unscored reading was given {fields[0].provenance.confidence!r}. No "
        "number is honest here: 1.0000 is the default "
        "ENGINE_1_INPUT_ENGINE_RULES.md:625 forbids by name, and 0.0000 asserts "
        "a worthlessness nobody measured."
    )

    # The scored one keeps the EXACT object reader measured. Identity, not
    # equality: a re-derived Decimal that happened to compare equal would still
    # mean this module had recomputed a score it may not touch (INV-2).
    assert fields[1].provenance.confidence is measured

    # Each mapping takes exactly one of the two routes into the Confidence
    # Report, and the two routes never overlap.
    assert [field.field_name for field in scored] == ["page 1 region 2"]
    assert [entry.field_name for entry in unmeasured] == ["page 1 region 1"]
    assert all(isinstance(entry.confidence, UnmeasuredType) for entry in unmeasured)
    assert scored[0].extraction_confidence is measured


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
    tree = ast.parse(authored_source(pipeline))
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
    # STRICTER, NOT DIFFERENT (§J.4): the two assertions above read fragments,
    # and this is the only channel `parser`'s geometry has into the artifact —
    # so the LINES and the separator between them are the contract, not
    # decoration. `x_document_structure_text__mutmut_8` rewrites `"\n"` into
    # `"XX\nXX"` and both fragment reads stay green; measured at `d7a8ed9`.
    # The box repr is taken from the object rather than transcribed, so this
    # asserts THIS function's format and never re-implements `BoundingBox`'s.
    assert text == "\n".join(
        (
            "page_count=1",
            f"table[0] detector='table-transformer:test' rows=1 columns=1 box={box!r}",
            f"  band label='table row' score=0.87 box={box!r}",
        )
    )


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
    source = authored_function_source(pipeline, "run")

    after_cleaner = source.split("_payload_of(cleaned)", 1)[1]
    assert "intake.document" not in after_cleaner, (
        "no stage after `cleaner` may read the ORIGINAL document. Every one must "
        "read the cleaned artifact's payload, or there are two pipelines again."
    )


def test_a_missing_artifact_fails_loudly_rather_than_falling_back() -> None:
    """A fallback to `intake.document` would reinstate the bypass while every
    behavioural test kept passing — the exact shape of a false green (§J.(a)).

    STRICTER, NOT DIFFERENT (§J.4). `match=` reads four words of a four-sentence
    refusal, and the other three sentences are the ones that say WHY the refusal
    exists: that this pipeline reads the cleaned document, that continuing is
    unsafe, and that the alternative would reinstate the bypass F-017 removed.
    Ten mutants of `_payload_of` rewrite only those three at `d7a8ed9` — the
    `match=` reads none of them — so the whole message is pinned instead.
    """
    without_artifact = cleaner.CleanedDocument(
        original=np.zeros((1, 1), dtype=np.uint8),
        cleaned=np.zeros((1, 1), dtype=np.uint8),
        quality_observations=(),
        preservation_status=cleaner.PreservationStatus.CLEANED_IS_SAFER,
        artifact=None,
    )

    with pytest.raises(pipeline.PipelineError, match="no media-aware artifact") as raised:
        pipeline._payload_of(without_artifact)

    assert str(raised.value) == (
        "cleaner returned no media-aware artifact. The pipeline reads the "
        "CLEANED document, never the original, so there is nothing safe to "
        "continue with. Refused rather than silently re-reading the intake, "
        "which would reinstate the bypass that F-017 removed."
    )


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
    """`vision_fallback_threshold` BECAME `confidence_parameters` (F-018), and
    the requirement it carried is stricter afterwards, not looser.

    The loose `Decimal` was a second representation of
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #2, `ocr_vision_fallback`, sitting
    beside a `config` module that held the validated one and that nothing
    imported. What replaced it is that validated object, so the field still has
    no default AND the value in it has now been through `config`'s range check,
    which the bare `Decimal` never was.
    """
    parameters = inspect.signature(pipeline.PipelineSettings).parameters
    assert "vision_fallback_threshold" not in parameters, (
        "the loose threshold came back. It is `confidence_parameters."
        "ocr_vision_fallback` now, so that Engine 1 has one representation of "
        "that number rather than two (Law 19, F-018)."
    )
    for name in ("cleaner_settings", "render_dpi", "confidence_parameters"):
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
    """UNCHANGED SUBJECT, CORRECTED TRIGGER (§J.4). What this test is ABOUT —
    that `PipelineStageError` names its stage in its own message and carries
    the real cause object — is still exactly right and is asserted more
    strictly than before.

    Only the input changed, and it had to. This used to force the error with
    zero bytes, which `APPLICATION_LAYER_CONTRACTS.md:30` classifies as a
    BUSINESS failure; that input now correctly produces an artifact rather than
    an exception (`test_a_zero_byte_document_crosses_the_boundary_as_an_
    artifact_not_an_error`). A test for the RUNTIME path therefore needs a
    RUNTIME failure, and PaddleOCR's real absence is one (F-002) — a genuinely
    missing dependency, not a mock of one (§J.6). The document itself is a
    valid PNG, so `cleaner` succeeds and `reader` is unambiguously the stage
    that failed.
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

    # stricter than `stage in str(...)`: the stage is named, and it is the
    # right one — the old form passed for any stage whose name appeared at all
    assert raised.value.stage == "reader"
    assert "'reader'" in str(raised.value)
    assert isinstance(raised.value.cause, ModuleNotFoundError)
    assert isinstance(raised.value.preserved, pipeline.PipelinePartialResult)
    # a runtime failure is NOT quietly turned into an artifact: the type this
    # module chose to raise is the one that reaches the caller
    assert not isinstance(raised.value.cause, pipeline.BUSINESS_FAILURE)


def test_the_stage_error_states_every_promise_it_makes_word_for_word() -> None:
    """The message is a CONTRACT, and the test above can only read four
    characters of it — `"'reader'" in str(...)` — because the rest interpolates
    a `ModuleNotFoundError` whose wording belongs to CPython, not to this
    repository. Constructed directly here with a cause this test owns, so the
    whole sentence is pinned: which stage stopped, the cause verbatim, that
    earlier work is on `preserved`, that nothing stands in for the failed
    stage, and that no stage after it ran.

    Measured at `d7a8ed9`: `xǁPipelineStageErrorǁ__init____mutmut_5` rewrites
    the clause promising the preservation, and no test in the suite read it.
    """
    cause = RuntimeError("Docling refused the layout")
    preserved = pipeline.PipelinePartialResult(cleaned=a_cleaned_document())

    error = pipeline.PipelineStageError("parser", cause, preserved)

    assert error.stage == "parser"
    assert error.cause is cause
    assert error.preserved is preserved
    assert str(error) == (
        "Engine 1's pipeline stopped at the 'parser' stage: "
        "Docling refused the layout. "
        "Whatever earlier stages already produced is preserved on this "
        "exception's `preserved` attribute; nothing stands in for "
        "'parser', and no stage after it ran."
    )


def test_pipeline_partial_result_defaults_to_nothing_completed() -> None:
    empty = pipeline.PipelinePartialResult()
    assert empty.cleaned is None
    assert empty.reading is None
    assert empty.parsed is None
    assert empty.confidence is None
    assert empty == replace(pipeline.PipelinePartialResult())


# ══════════════════════════════════════════════════════════════════════════
# The temporary file `parser` is handed — semgrep ERROR at pipeline.py:1200
# ══════════════════════════════════════════════════════════════════════════

#: How many documents `test_two_documents_append_two_rows...` runs into one
#: store. Two is the smallest number that can show a second row failing to
#: append, or overwriting the first.
DOCUMENTS_RUN_INTO_ONE_STORE = 2

#: MEASURED by bisection on this interpreter, not chosen: a single write of
#: 4096 bytes or fewer stays entirely in `BufferedWriter`'s buffer and the file
#: on disk is ZERO bytes; 4097 and above are written through. So the DANGEROUS
#: payload is a small one, which is the opposite of the obvious guess and is
#: exactly the size this pipeline carries — the three-line text-layer invoice
#: this repository's fixtures build is 1118 bytes.
LARGEST_FULLY_BUFFERED_WRITE = 4096


def test_a_document_smaller_than_the_write_buffer_reaches_the_reader_whole() -> None:
    """THE REGRESSION TEST FOR THE FLUSH. Delete either line and this goes red.

    `_document_on_disk` yields the path while the write handle is still OPEN,
    so `flush()` and `os.fsync()` are the only things putting the bytes on the
    device before anything can read them. A reader handed the path without them
    opens a zero-byte file, and a zero-byte PDF reads as a damaged document —
    a false statement about the user's file.

    The payload is deliberately at the measured boundary rather than a large
    one: a big write goes straight through the buffer and would pass with no
    flush at all, which is how a test of this can look right and prove nothing.
    """
    document = b"%PDF-1.7 " + b"A" * (LARGEST_FULLY_BUFFERED_WRITE - len(b"%PDF-1.7 "))
    assert len(document) == LARGEST_FULLY_BUFFERED_WRITE

    with pipeline._document_on_disk(document, suffix=".pdf") as temp_path:
        # Read by PATH, as `parser.parse` does — never through the handle that
        # wrote it, which would see the buffer and not the file.
        seen = temp_path.read_bytes()
        assert temp_path.stat().st_size == len(document), (
            f"the file holds {temp_path.stat().st_size} of {len(document)} bytes "
            "at the moment its path was handed over. The write is still in "
            "Python's buffer, and any reader given this path sees a truncated "
            "document."
        )

    assert seen == document


def test_the_flush_is_what_makes_that_true_and_not_the_context_manager() -> None:
    """FALSIFICATION of the test above, by reproducing the defect beside it.

    Without the flush the same bytes leave an EMPTY file, measured here rather
    than asserted, so the assertion above is known to be checking something
    that can actually fail. Built with `tempfile` directly because the point is
    what `_document_on_disk` would do if its two lines were removed.
    """
    document = b"A" * LARGEST_FULLY_BUFFERED_WRITE
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(document)
        unflushed = pathlib.Path(handle.name)
        on_disk_before = unflushed.stat().st_size
    unflushed.unlink(missing_ok=True)

    assert on_disk_before == 0, (
        f"a {len(document)}-byte write left {on_disk_before} bytes on disk, so "
        "this interpreter's buffering has changed and the test above no longer "
        "exercises the failure it was written for — re-measure the boundary."
    )


def test_the_temporary_file_is_removed_even_when_the_reader_raises() -> None:
    """A document left behind on disk is a copy of a business's paperwork in a
    temporary directory nobody is watching. The removal is in a `finally`, so
    it happens on the failure path too — which is the path that gets forgotten.
    """
    escaped: list[pathlib.Path] = []

    with (
        pytest.raises(RuntimeError, match="parser blew up"),
        pipeline._document_on_disk(b"%PDF-1.7 tiny", suffix=".pdf") as temp_path,
    ):
        escaped.append(temp_path)
        raise RuntimeError("parser blew up")

    (left_behind,) = escaped
    assert not left_behind.exists(), f"{left_behind} survived a failed parse"


def test_the_temporary_file_carries_the_suffix_the_caller_asked_for() -> None:
    """Docling picks its backend from the file EXTENSION, so a PDF written to a
    `.png` path is parsed as an image. The suffix is the caller's and is not
    guessed from the bytes — `CLAUDE.md` Law 23, the same refusal
    `DocumentIntake.media_type` already makes.
    """
    for suffix in (".pdf", ".png"):
        with pipeline._document_on_disk(b"bytes", suffix=suffix) as temp_path:
            assert temp_path.suffix == suffix


# ══════════════════════════════════════════════════════════════════════════
# ONE PATH — every media kind, no special case, no bypass (F-017)
# ══════════════════════════════════════════════════════════════════════════


def a_scanned_pdf() -> bytes:
    """A PDF holding only an image: no text layer, so it must be rasterised."""
    document = open_pdf()
    try:
        page = document.new_page(width=400, height=200)
        page.insert_image(rectangle(0, 0, 400, 200), stream=a_tiny_png())
        return bytes(document.tobytes())
    finally:
        document.close()


def a_mixed_pdf() -> bytes:
    """One page with a text layer, one page with only an image.

    THE CASE THAT DECIDES A RULE RATHER THAN CONFIRMING ONE. `cleaner` asks
    *"does ANY page carry embedded text?"*, so a mixed document takes the
    pass-through path — which is the safe direction: the text page keeps its
    exact characters, and the image page was already going to need OCR either
    way. A per-page rule would rasterise the text page to clean the image one,
    which trades an exact reading for a recognised one.
    """
    document = open_pdf()
    try:
        text_page = document.new_page(width=400, height=200)
        text_page.insert_text((40, 60), "TAX INVOICE 27AAECS1234F1Z5", fontname="helv", fontsize=13)
        image_page = document.new_page(width=400, height=200)
        image_page.insert_image(rectangle(0, 0, 400, 200), stream=a_tiny_png())
        return bytes(document.tobytes())
    finally:
        document.close()


@dataclass
class _WhatEachStageWasHanded:
    """What `reader` and `parser` actually received, recorded on the way past."""

    cleaned_payload: bytes | None = None
    reader_document: bytes | None = None
    parser_bytes: bytes | None = None


#: The four shapes, as BUILDERS rather than bytes, so the parametrisation's
#: test ids stay readable and the fixtures are not built at import time.
#:
#: The fourth column is `reaches_parser_without_ocr` and it is a property of the
#: DOCUMENT, not of this machine: a document with an embedded text layer is read
#: by PyMuPDF and goes on to `parser`, while one without has to be recognised
#: first. `reader.read` makes exactly that split, so the two shapes with no text
#: layer stop at `reader` wherever PaddleOCR is not installed — which is the
#: default environment, by design (`requirements-engine1-ocr.txt` keeps ~2 GB of
#: ML wheels out of it). Stating it per shape keeps every assertion below
#: unconditional instead of tolerant.
MEDIA_SHAPES: tuple[tuple[str, Callable[[], bytes], reader.MediaType, bool], ...] = (
    ("image", a_tiny_png, reader.MediaType.IMAGE, False),
    ("text-layer PDF", an_invoice_pdf, reader.MediaType.PDF, True),
    ("scanned PDF", a_scanned_pdf, reader.MediaType.PDF, False),
    ("mixed PDF", a_mixed_pdf, reader.MediaType.PDF, True),
)


@pytest.mark.parametrize(
    ("name", "build", "media_type", "reaches_parser_without_ocr"),
    MEDIA_SHAPES,
    ids=[shape[0] for shape in MEDIA_SHAPES],
)
def test_every_media_kind_travels_the_same_path_and_nothing_re_opens_the_intake(
    name: str,
    build: Callable[[], bytes],
    media_type: reader.MediaType,
    reaches_parser_without_ocr: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-017's *"Remove every legacy bypass and duplicate path"*, as a measurement.

    THE BYPASS THIS TRAPS IS SPECIFIC AND WAS REAL. Before the migration
    `cleaner` emitted a bitmap, so `reader` and `parser` each RE-OPENED
    `intake.document` — correctly, because reading a bitmap of a PDF destroys
    its text layer. Two pipelines ran side by side and every test passed. The
    only way to tell them apart is to record what each stage was actually
    handed and compare it to the cleaned payload, byte for byte, which is what
    this does.

    FOUR SHAPES, ONE ASSERTION, and the four are chosen to take DIFFERENT
    internal routes: an image is decoded and re-encoded, a text-layer PDF is
    passed through untouched, a scan is rasterised and rebuilt, and a mixed
    document has to choose. If any of them reached `reader` or `parser` by a
    different road, the payload comparison below would show it.
    """
    observed = _WhatEachStageWasHanded()
    real_clean = cleaner.clean_artifact
    real_read = reader.read
    real_parse = parser.parse

    def spy_clean(
        data: bytes,
        kind: cleaner.MediaKind,
        settings: cleaner.CleanerSettings,
        *,
        render_dpi: int,
        cleaners: Mapping[cleaner.MediaKind, cleaner.MediaCleaner] = cleaner.CLEANERS,
    ) -> cleaner.CleanedDocument:
        cleaned = real_clean(data, kind, settings, render_dpi=render_dpi, cleaners=cleaners)
        assert cleaned.artifact is not None
        observed.cleaned_payload = cleaned.artifact.payload
        return cleaned

    def spy_read(
        document_bytes: bytes,
        *,
        media_type: reader.MediaType,
        render_dpi: int,
        vision_fallback_threshold: Decimal,
    ) -> reader.Reading:
        observed.reader_document = document_bytes
        return real_read(
            document_bytes,
            media_type=media_type,
            render_dpi=render_dpi,
            vision_fallback_threshold=vision_fallback_threshold,
        )

    def spy_parse(
        source: Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        observed.parser_bytes = source.read_bytes()
        return real_parse(
            source,
            source_reference=source_reference,
            extracted_regions=extracted_regions,
            table_structure=table_structure,
        )

    monkeypatch.setattr(cleaner, "clean_artifact", spy_clean)
    monkeypatch.setattr(reader, "read", spy_read)
    monkeypatch.setattr(parser, "parse", spy_parse)

    document = build()

    # THE ORACLE IS THIS RUN'S OWN CLEANED PAYLOAD, not a second `clean_artifact`
    # call on the same bytes, and the difference is not pedantry. Cleaning a
    # SCAN rebuilds the PDF, and PyMuPDF stamps a fresh random `/ID` into every
    # save — measured: two cleans of one scan produce payloads of identical
    # length whose pixels are identical and which differ in 58 bytes, all of
    # them inside `trailer <</ID[...]>>`. A second call is therefore the wrong
    # oracle for a byte comparison, and using it would make this test fail for a
    # reason that has nothing to do with the bypass it exists to catch.
    try:
        pipeline.run(
            a_document_intake(document=document, media_type=media_type),
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )
    except pipeline.PipelineStageError as stopped:
        # NOT A SKIP, AND NOT A TOLERANCE. PaddleOCR is a ~2 GB optional install
        # that `requirements-engine1-ocr.txt` keeps out of the default
        # environment, so an IMAGE stops inside `reader` wherever it is absent.
        # Every assertion below still runs and still fails on the bypass,
        # because the spy records what `reader` WAS HANDED before `reader` gets
        # as far as looking for a recogniser. Anything other than that one
        # stage, with that one cause, re-raises and fails the test.
        assert stopped.stage == "reader", f"{name}: stopped at {stopped.stage!r}"
        assert isinstance(stopped.cause, ModuleNotFoundError), (
            f"{name}: reader failed for a reason other than a missing OCR "
            f"install: {type(stopped.cause).__name__}: {stopped.cause}"
        )

    assert observed.cleaned_payload is not None, (
        f"{name}: `cleaner.clean_artifact` was never called, so the run did not "
        "go through the single entry point at all"
    )
    assert observed.reader_document == observed.cleaned_payload, (
        f"{name}: `reader` was handed bytes that are not the cleaned payload. "
        "Either it re-opened the intake — the F-017 bypass — or a second "
        "cleaning path produced something else."
    )

    if reaches_parser_without_ocr:
        assert observed.parser_bytes is not None, (
            f"{name}: `parser` never ran. This shape carries an embedded text "
            "layer, so it reaches `parser` with no recogniser involved — if it "
            "did not, either the routing changed or the fixture stopped having "
            "a text layer, and the parser half of the one-path claim is "
            "unchecked either way."
        )
    if observed.parser_bytes is not None:
        assert observed.parser_bytes == observed.cleaned_payload, (
            f"{name}: the file `parser` opened does not hold the cleaned payload."
        )
        assert observed.reader_document == observed.parser_bytes, (
            f"{name}: `reader` and `parser` read DIFFERENT documents, so every "
            "field mapping crosses a boundary between two readings of one file."
        )


def test_the_four_media_shapes_really_do_take_different_internal_routes() -> None:
    """PRECONDITION for the test above, and the thing that stops it being four
    copies of one case.

    If all four fixtures happened to be cleaned the same way, "they all travel
    the same path" would be true and would mean nothing. Measured here: the
    text-layer PDF and the mixed PDF come back byte-identical to what went in
    (passed through), while the image and the scan do not (re-encoded and
    rebuilt). Two routes, four documents, one entry point.
    """
    settings = a_cleaner_settings()
    routes: dict[str, bool] = {}
    for name, document, kind in (
        ("image", a_tiny_png(), cleaner.MediaKind.IMAGE),
        ("text-layer PDF", an_invoice_pdf(), cleaner.MediaKind.PDF),
        ("scanned PDF", a_scanned_pdf(), cleaner.MediaKind.PDF),
        ("mixed PDF", a_mixed_pdf(), cleaner.MediaKind.PDF),
    ):
        cleaned = cleaner.clean_artifact(document, kind, settings, render_dpi=RENDER_DPI)
        assert cleaned.artifact is not None
        assert cleaned.artifact.kind is kind, (
            f"{name} came back as a {cleaned.artifact.kind}; a cleaned document "
            "is still the kind of document it started as"
        )
        routes[name] = cleaned.artifact.payload == document

    assert routes == {
        "image": False,
        "text-layer PDF": True,
        "scanned PDF": False,
        "mixed PDF": True,
    }, f"the fixtures no longer exercise two different routes: {routes}"


def test_the_pipeline_reads_the_cleaned_payload_and_never_the_intake_in_source() -> None:
    """The structural half of the same claim, so a future edit that reintroduces
    the bypass fails even if no test happens to run that media kind.

    `run` may name `intake.document` exactly once — handing it to `cleaner`.
    Every later stage takes `cleaned_document`, which is `_payload_of(cleaned)`.
    """
    tree = ast.parse(authored_function_source(pipeline, "run"))
    # BY AST, NOT BY SUBSTRING. `run`'s own comment explains why nothing
    # re-opens the intake, and a text count reads that prose as a second use —
    # measured: the first version of this test failed at 2, one of which was the
    # sentence saying it must be 1. A guard that fires on its own documentation
    # is a guard somebody deletes.
    reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "document"
        and isinstance(node.value, ast.Name)
        and node.value.id == "intake"
    ]
    assert len(reads) == 1, (
        f"`run` reads `intake.document` {len(reads)} times, at lines "
        f"{sorted(node.lineno for node in reads)}. Exactly one is correct — the "
        "call into `cleaner`. A second is a stage re-opening the original, "
        "which is the F-017 bypass."
    )

    # …and the one read is the argument to the cleaner call, not to anything else.
    cleaner_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "clean_artifact"
    ]
    assert len(cleaner_calls) == 1
    assert reads[0] in ast.walk(cleaner_calls[0]), (
        "the one read of `intake.document` is no longer the cleaner call, so "
        "some other stage is being handed the raw intake"
    )


# ══════════════════════════════════════════════════════════════════════════
# F-018 — `classification`, `config` and `measurement` are CONSUMED, not just
# imported.
#
# `test_module_wiring.py` asks the cheap question — *"is this module reachable
# in the import graph from the Application Layer's entry point?"* — and that is
# the right DETECTOR, because it is exact and answers in milliseconds. It is not
# a sufficient one: an `import` nothing calls satisfies it. The tests below ask
# the expensive question about the same three modules, on one real run.
# ══════════════════════════════════════════════════════════════════════════


def test_the_vision_fallback_threshold_reader_receives_is_the_configured_parameter() -> None:
    """`config` HAS A CONSUMER, and this is it.

    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #2 is `ocr_vision_fallback` — *"the score
    below which the vision fallback replaces PaddleOCR"* — which is exactly the
    number `reader.read` requires. Until F-018 the pipeline took that number as
    a loose `Decimal` while `config` held the validated one and nothing imported
    `config` at all: two representations of one parameter, and the one in use
    had never been range-checked.

    An unmistakable value is used so the assertion cannot pass by coincidence
    with the default the factory supplies.
    """
    observed: list[Decimal] = []
    real_read = reader.read

    def spy_read(
        document: bytes,
        *,
        media_type: reader.MediaType,
        render_dpi: int,
        vision_fallback_threshold: Decimal,
    ) -> reader.Reading:
        observed.append(vision_fallback_threshold)
        return real_read(
            document,
            media_type=media_type,
            render_dpi=render_dpi,
            vision_fallback_threshold=vision_fallback_threshold,
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(reader, "read", spy_read)
        pipeline.run(
            a_document_intake(),
            identity=an_identity(),
            settings=a_pipeline_settings(
                confidence_parameters=a_confidence_parameters(Decimal("0.4242"))
            ),
            recorded_at=RECORDED_AT,
        )

    assert observed == [Decimal("0.4242")], (
        "`reader` did not receive the configured `ocr_vision_fallback`. Either "
        "the pipeline is still carrying a second copy of that number, or it is "
        "reading a different parameter."
    )


def test_the_configured_parameters_went_through_config_and_not_around_it() -> None:
    """The value is not merely carried; it arrived as a `ConfidenceParameters`,
    which is the type `config` builds and validates.

    Falsification: a `Decimal` outside `[0.0000, 1.0000]`, or one with more
    decimal places than the agreed scale, cannot become one of these at all —
    so the number reaching `reader` is inside the range `config` enforces, by
    construction rather than by review.
    """
    with pytest.raises(config.ImpossibleParameterError, match="ocr_vision_fallback"):
        a_confidence_parameters(Decimal("1.5"))
    with pytest.raises(config.ImpossibleParameterError, match="ocr_vision_fallback"):
        a_confidence_parameters(Decimal("0.123456"))

    settings = a_pipeline_settings()
    assert isinstance(settings.confidence_parameters, config.ConfidenceParameters)


def test_a_run_classifies_the_document_and_records_what_it_found(tmp_path: Path) -> None:
    """`classification` AND `measurement` BOTH HAVE CONSUMERS, and one run is
    what proves it: the classification result is what the measurement row states
    the document type to be.

    The invoice fixture prints `TAX INVOICE` as its own first line, so
    `classification` reads it as this document's own heading rather than as a
    reference to another document — which is the distinction that module exists
    to make.

    NOTHING HERE ENTERS THE DOCUMENT EVIDENCE OBJECT. `test_package.py` classes
    all three modules as FACILITIES because the artifact has no document-type
    component and gains none; the row goes to the calibration store and nowhere
    else, and `test_the_evidence_object_has_no_document_type_field` is the
    falsifier for that claim.
    """
    store = tmp_path / "measurements.jsonl"

    evidence = pipeline.run(
        a_document_intake(),
        identity=an_identity(),
        settings=a_pipeline_settings(measurement_store=store),
        recorded_at=RECORDED_AT,
    )

    (row,) = measurement.read_all(store)
    assert row.document_id == evidence.document_id, (
        "the row is keyed by a different document than the artifact it "
        "describes, so no calibration run could ever join the two"
    )
    assert row.source_document_type == classification.DocumentType.TAX_INVOICE.value, (
        f"the row records {row.source_document_type!r}. The fixture prints "
        "'TAX INVOICE' as its own heading, so `classification` should have "
        "named it — a different answer means the classifier never ran or its "
        "result never reached the row."
    )
    assert not isinstance(row.classification, measurement.AbsentType)
    assert [signal.name for signal in row.classification] == [
        classification.DocumentType.TAX_INVOICE.value
    ]


def test_the_recorded_row_invents_no_score_anywhere(tmp_path: Path) -> None:
    """The row is a RECORD, never a judgement — `measurement.py`'s own first
    rule, and the one this wiring could most easily break.

    `document_score` stays ABSENT because
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #13 is UNDEFINED; `correctness` stays
    UNLABELLED because ground truth is P1's and has not run; and every
    classification signal carries `None` rather than a number, because
    `classification` scores nothing at all and `classification_accept` is UNSET.
    """
    store = tmp_path / "measurements.jsonl"
    pipeline.run(
        a_document_intake(),
        identity=an_identity(),
        settings=a_pipeline_settings(measurement_store=store),
        recorded_at=RECORDED_AT,
    )

    (row,) = measurement.read_all(store)
    assert row.document_score is measurement.ABSENT, (
        "a document score was recorded. No rule anywhere produces one — #13 is "
        "UNDEFINED — so any value here was invented (Law 24)."
    )
    assert row.correctness is measurement.Correctness.UNLABELLED, (
        "a correctness verdict was recorded. Whether extraction was ACTUALLY "
        "correct is ground truth, which P1 has not produced."
    )
    assert not isinstance(row.classification, measurement.AbsentType)
    assert all(signal.value is None for signal in row.classification), (
        "a classification signal carries a number. `classification` produces no "
        "score by design, so a number here came from this pipeline."
    )


def test_the_recorded_row_carries_every_reading_with_its_instrument(tmp_path: Path) -> None:
    """`ConfidenceReport.FieldConfidence` is `(field_name, confidence)` — no slot
    for which tool produced the score, and none for a page region
    (`CONFIDENCE_SPECIFICATION.md` §3.3-3.4, open item O4). This store is the
    ONLY place either fact survives, so a row that dropped them would silently
    end the possibility of calibrating per instrument.
    """
    store = tmp_path / "measurements.jsonl"
    pipeline.run(
        a_document_intake(),
        identity=an_identity(),
        settings=a_pipeline_settings(measurement_store=store),
        recorded_at=RECORDED_AT,
    )

    (row,) = measurement.read_all(store)
    assert not isinstance(row.per_region_ocr, measurement.AbsentType)
    assert not isinstance(row.per_field, measurement.AbsentType)
    assert len(row.per_region_ocr) == len(INVOICE_LINES), (
        f"{len(row.per_region_ocr)} region signals for {len(INVOICE_LINES)} "
        "lines; a reading was dropped on the way into the record"
    )
    assert len(row.per_field) == len(INVOICE_LINES)

    for signal in row.per_region_ocr:
        assert signal.instrument == reader.Backend.PDF_TEXT_LAYER.value
        assert signal.region, "a region signal carries no location"
        assert signal.value is None, (
            "a text-layer region was given a score. `reader` reports `None` for "
            "these — the ABSENCE of a measurement — and turning that into a "
            "number is the fabrication the whole module docstring refuses."
        )


def test_a_row_is_recorded_for_every_run_even_with_no_store_configured() -> None:
    """`None` means NO DESTINATION, never "do not measure".

    The row is built from the same real signals either way, so a deployment
    that configures a store gets the same record an unconfigured one would have
    written. A row built only when someone is watching is a row nobody can
    trust — and it would also make this wiring dead code on the default path,
    which is F-018 all over again.
    """
    settings = a_pipeline_settings()
    assert settings.measurement_store is None

    built: list[measurement.MeasurementRow] = []
    real_row = pipeline.measurement_row

    def spy_row(
        artifact: DocumentEvidenceObject,
        reading: reader.Reading,
        parsed: parser.ParsedStructure,
        classified: classification.ClassificationResult,
        *,
        processing_time_ms: float,
    ) -> measurement.MeasurementRow:
        row = real_row(artifact, reading, parsed, classified, processing_time_ms=processing_time_ms)
        built.append(row)
        return row

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline, "measurement_row", spy_row)
        pipeline.run(
            a_document_intake(),
            identity=an_identity(),
            settings=settings,
            recorded_at=RECORDED_AT,
        )

    assert len(built) == 1, "no calibration row was built on a run with no store configured"
    assert built[0].source_document_type == classification.DocumentType.TAX_INVOICE.value


def test_the_recorded_processing_time_is_a_real_elapsed_duration(tmp_path: Path) -> None:
    """A duration, measured, and never an injected constant.

    `Sources.now` is injected everywhere else in this repository so the ARTIFACT
    is reproducible. This number never enters the artifact — it is
    `processing_time_ms` on the calibration row — and a fabricated duration
    there would be worse than none (Law 24). It is taken from a MONOTONIC clock
    so it can never come back negative because a wall clock stepped.
    """
    store = tmp_path / "measurements.jsonl"
    pipeline.run(
        a_document_intake(),
        identity=an_identity(),
        settings=a_pipeline_settings(measurement_store=store),
        recorded_at=RECORDED_AT,
    )

    (row,) = measurement.read_all(store)
    assert row.processing_time_ms > 0.0, (
        f"processing took {row.processing_time_ms} ms, which no real run does. "
        "A zero here means the duration is a constant rather than a measurement."
    )
    assert math.isfinite(row.processing_time_ms)


def test_the_evidence_object_has_no_document_type_field() -> None:
    """THE FALSIFIER for `classification` being a FACILITY rather than a fifth
    sub-engine.

    `test_package.py`: *"The moment a facility's output enters the Document
    Evidence Object it has produced a fifth part and has stopped being a
    facility."* `ENGINE_1_INPUT_ENGINE_RULES.md:353` names exactly four
    sub-engines and `:365` forbids adding one, so wiring classification into
    the artifact would break a LOCKED level-3 specification.
    """
    named = set(DocumentEvidenceObject.model_fields) | set(StructuredDocument.model_fields)
    trespassers = sorted(
        field for field in named if "document_type" in field or "classification" in field
    )
    assert trespassers == [], (
        f"the Document Evidence Object gained {trespassers}. Classification is "
        "a facility: its cues are evidence for calibration, never a part of the "
        "artifact, and a fifth part is a fifth sub-engine."
    )


def test_two_documents_append_two_rows_and_neither_overwrites_the_other(tmp_path: Path) -> None:
    """The store is append-only, and a calibration run divides by the number of
    rows in it. A run that overwrote the previous document's row would make
    every rate computed from this file wrong in the direction that looks fine.
    """
    store = tmp_path / "measurements.jsonl"
    settings = a_pipeline_settings(measurement_store=store)
    for lines in (INVOICE_LINES, ("BILL OF SUPPLY", "Vendor: Acme")):
        pipeline.run(
            a_document_intake(document=an_invoice_pdf(lines)),
            identity=an_identity(),
            settings=settings,
            recorded_at=RECORDED_AT,
        )

    rows = measurement.read_all(store)
    assert len(rows) == DOCUMENTS_RUN_INTO_ONE_STORE, (
        f"{len(rows)} row(s) for {DOCUMENTS_RUN_INTO_ONE_STORE} documents"
    )
    assert [row.source_document_type for row in rows] == [
        classification.DocumentType.TAX_INVOICE.value,
        classification.DocumentType.BILL_OF_SUPPLY.value,
    ]
    assert rows[0].document_id != rows[1].document_id


def test_a_document_naming_no_catalogued_type_is_recorded_as_unknown_not_guessed(
    tmp_path: Path,
) -> None:
    """Law 25 — *"expose uncertainty instead of guessing."* A document whose
    heading this module's catalogue does not recognise must reach the record as
    UNKNOWN, never as the nearest match, because the record is what a later
    calibration run treats as the stated type.
    """
    store = tmp_path / "measurements.jsonl"
    pipeline.run(
        a_document_intake(document=an_invoice_pdf(("MONTHLY STATEMENT", "Vendor: Acme"))),
        identity=an_identity(),
        settings=a_pipeline_settings(measurement_store=store),
        recorded_at=RECORDED_AT,
    )

    (row,) = measurement.read_all(store)
    assert row.source_document_type == classification.ClassificationStatus.UNKNOWN.name
    assert row.classification == (), (
        "an unrecognised document produced classification signals, so a type "
        "was named for a document that names none"
    )


def _end_of_pdf_literal_string(payload: bytes, opening: int) -> int:
    """Index just past the `)` closing the literal string that opens at `opening`.

    NEITHER `payload.index(b")")` NOR A NON-GREEDY REGEX FINDS THIS, and the
    difference is not academic — it is the whole reason the helper exists. A PDF
    literal string may contain BALANCED unescaped parentheses, and may escape any
    byte with a backslash (`\\375`, `\\)`, `\\\\`). A scanner that stops at the
    first `)` stops inside the string on exactly the saves this file is about,
    leaving half an identifier in the "everything else" it was supposed to
    remove — which is the original bug wearing a new hat.
    """
    depth = 0
    index = opening
    while index < len(payload):
        byte = payload[index]
        if byte == ord("\\"):
            index += 2  # an escape consumes the byte after it, whatever it is
            continue
        if byte == ord("("):
            depth += 1
        elif byte == ord(")"):
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise AssertionError("the PDF trailer holds an unterminated literal string")


def _pdf_file_identifier_span(payload: bytes) -> tuple[int, int]:
    """The byte span of the trailer's `/ID [ ... ]` array, ends included.

    Walks the array rather than pattern-matching it, because EITHER of its two
    strings may be serialised as hex (`<...>`) or as a literal (`(...)`), and a
    literal may contain `]`. Measured over 3000 saves of one document: both
    forms occur, and in three of them the FIRST string was a literal too — so an
    assumption that entry one is always hex is false, not merely fragile.
    """
    start = payload.rindex(b"/ID")
    index = payload.index(b"[", start) + 1
    while index < len(payload):
        byte = payload[index]
        if byte == ord("]"):
            return start, index + 1
        if byte == ord("("):
            index = _end_of_pdf_literal_string(payload, index)
            continue
        if byte == ord("<"):
            index = payload.index(b">", index) + 1
            continue
        index += 1
    raise AssertionError("the PDF trailer holds an unterminated /ID array")


def test_a_rebuilt_scan_differs_only_in_the_pdf_file_identifier_never_in_a_pixel() -> None:
    """A REAL FINDING, PINNED RATHER THAN FIXED, and the reason it is not a bug
    this change repairs.

    Cleaning the SAME scan twice does not produce the same bytes. The difference
    is confined to `trailer <</ID[...]>>`, PyMuPDF's per-save random file
    identifier. The rasters are `np.array_equal`.

    IT IS NOT A CONTENT DEFECT, and `CLAUDE.md`'s own standing rule says why:
    *"IDENTITY != INTELLIGENCE. IDs identify objects. They never influence
    reasoning."* Nothing reads `/ID`, and no reading changes because of it.

    ── WHY THIS TEST WAS REWRITTEN: IT PINNED AN INVARIANT THAT IS NOT TRUE ──

    It used to assert `len(first.payload) == len(second.payload)` and then, for
    the differing bytes, that they all fell after `trailer`. Both halves were
    wrong, and the first one was RED ON CI while green locally, which is how it
    was found:

        AssertionError: assert 5457 == 5465

    A PDF byte string has two legal serialisations — hex `<...>`, a fixed 34
    bytes for 16 bytes of identifier, or a literal `(...)`, which is 2 bytes
    plus one byte per content byte plus one more for every byte that needs a
    backslash escape. PyMuPDF picks per string, per save, over bytes that are
    RANDOM BY CONSTRUCTION. Measured on this exact fixture at 150 dpi, 3000
    saves, commit `3bd31e2`:

        /ID span (bytes)   66  67  68  69  70  71  72  73
        occurrences         2   2   1   1   4   1  19  2969

    Eight distinct lengths. **The old assertion compared a random variable to
    itself and passed 99% of the time**, which is the worst possible failure
    mode: rare enough to look like flakiness, frequent enough to redden the
    `coverage` gate and block everything behind it.

    A hypothesis of mine was REFUTED here and is recorded so nobody re-derives
    it: the literal form is NOT chosen only when it is strictly shorter. In 20
    of 3000 saves it was chosen at exactly 34 bytes, the same width as hex. The
    selection rule inside MuPDF is not needed to fix this and is not claimed.

    The second half was wrong differently — merely LOOSE. `trailer` is followed
    by `/Size`, `/Root` and `/ID`, so "after the trailer keyword" permitted a
    changed root object or object count to pass as identifier noise.

    ── THE INVARIANT THAT IS ACTUALLY TRUE, AND IS STRICTER ──

    Excise the `/ID` array from both payloads and *everything else is byte for
    byte identical*. That needs no equal length, and it forbids what the old
    version allowed. Measured over 300 cleans at `3bd31e2`: 3 distinct payload
    lengths, and **exactly 1 distinct remainder**.
    """
    scan = a_scanned_pdf()
    settings = a_cleaner_settings()
    first = cleaner.clean_artifact(scan, cleaner.MediaKind.PDF, settings, render_dpi=RENDER_DPI)
    second = cleaner.clean_artifact(scan, cleaner.MediaKind.PDF, settings, render_dpi=RENDER_DPI)

    assert first.artifact is not None
    assert second.artifact is not None
    assert first.artifact.raster is not None, "the rebuild produced no raster view"
    assert second.artifact.raster is not None
    assert np.array_equal(first.artifact.raster, second.artifact.raster), (
        "two cleans of one scan produced different PIXELS. That is a real "
        "determinism defect, not the known file-identifier difference, and "
        "MEASUREMENT_FRAMEWORK cannot obtain a number from a stage like that."
    )

    payloads = (first.artifact.payload, second.artifact.payload)
    # ASSERTED, NOT ASSUMED. If a future PyMuPDF stopped writing `/ID` at all,
    # both remainders would be whole payloads and would still compare equal —
    # the test would pass while checking nothing. This is what stops that.
    for payload in payloads:
        assert payload.count(b"/ID") == 1, (
            "the rebuilt PDF does not carry exactly one file identifier, so "
            "'everything except the identifier' is not a thing this test can "
            "still measure. Re-derive the span before trusting the comparison."
        )

    spans = [_pdf_file_identifier_span(payload) for payload in payloads]
    without_identifier = [
        payload[:start] + payload[end:]
        for payload, (start, end) in zip(payloads, spans, strict=True)
    ]

    assert without_identifier[0] == without_identifier[1], (
        "two cleans of one scan differ OUTSIDE the PDF file identifier. Only "
        f"`/ID` is allowed to vary. Identifier spans were {spans[0]} and "
        f"{spans[1]}; the payloads outside them must be byte for byte equal."
    )
