"""Engine 1, end to end, as a test CI runs — the proof that used to die with the
session that produced it.

`ROADMAP.md:151` makes *"a real document runs end to end"* a completion
criterion for Engine 1. It had been done once, by hand, on an 8-page CBIC
government PDF. A result nobody can re-run is not a result (Law 44), so this
file re-runs it every build.

WHERE THE DOCUMENTS COME FROM, AND WHY THEY ARE AUTHORED RATHER THAN SHIPPED.
    Measured, not assumed: `git ls-files` matches ZERO files with a `.pdf`,
    `.png`, `.jpg`, `.tif` or `.webp` extension anywhere in this repository,
    and `.gitignore` deliberately excludes
    `Accounting_Brain/Evidence_Library/sources/*.pdf` — only the extracted
    `.txt` of each primary source is tracked. There is no real fixture
    document to point at, and a CI runner may not download one (a gate that
    depends on a network fetch is a gate that fails for reasons unrelated to
    the code).

    So each document below is BUILT here, from the ground truth above it, with
    the same real libraries the engine itself uses — PyMuPDF for the PDFs,
    OpenCV for the raster. That is strictly stronger than an opaque downloaded
    file for the thing these tests check: because the exact characters drawn
    onto the page are known, "did every one of them survive to the artifact,
    and did anything appear that was never drawn?" is answerable. Against a
    downloaded PDF neither question is.

WHAT THIS FILE PROVES THAT `tests/unit/test_input_engine_pipeline.py` DOES NOT.
    That file already proves a ONE-page text-layer PDF completes, that a stage
    failure names itself, and that no conversion function edits a value. It is
    not repeated here. New ground, all of it end to end through the real
    `pipeline.run`:

      - a MULTI-page document: both pages' text, in page order, and
        `page_count=2` in the structure — a first-page-only pipeline passes
        every single-page test ever written and fails this one
      - the scanned (no text layer) route through `cleaner`'s
        rasterise-and-rebuild path, on a real PDF, measured to the byte
      - the image route, to the same real wall
      - Rule 1: nothing that could be wrong about the BUSINESS crosses
      - Rule 4 / §5: the traceability contract, asserted as the documents
        state it — see the last test in this file
      - that `reader` and `parser` consumed a document with its text layer
        intact, proven BEHAVIOURALLY rather than by reading `run`'s source

WHAT IS GENUINELY UNAVAILABLE, AND IS NOT MOCKED AROUND.
    PaddleOCR is absent from this environment and from CI on purpose
    (`requirements-engine1-ocr.txt` — it cannot share an environment with
    `requirements-engine1.txt`, and the two OpenCV distributions that result
    are `KNOWN_FAILURES.md` F-002). Every route that needs recognition
    therefore stops, for real, at `reader`. That real absence is used as the
    failure; nothing stands in for it (§J.6).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf
import pytest

from accountant_dad.artifacts.evidence import (
    Corroborated,
    DocumentEvidenceObject,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine import cleaner, confidence_report, pipeline, reader
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope, TransactionId

Image = npt.NDArray[np.uint8]

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

#: The clock `pipeline.run` is GIVEN, and the instant every detected field's
#: provenance must therefore carry. Deliberately not `WHEN`: that one is the
#: human note's own timestamp, and a test asserting one while meaning the other
#: would pass by coincidence. `run` reads no clock of its own — a module that
#: called `datetime.now()` could not produce the same artifact twice.
RECORDED_AT = datetime(2026, 8, 6, 11, 30, tzinfo=UTC)

#: This file's own choice, not a product default — `PipelineSettings` requires
#: the caller to supply it and `pipeline.py` invents no number of its own.
RENDER_DPI = 150
#: The vision fallback must never fire in a test about something else.
NO_FALLBACK = Decimal("0.0")

#: The human note. Deliberately a sentence that a careless engine would be
#: tempted to promote from "the user said this" to "this is so"
#: (`COMMUNICATION_RULES_INPUT_ENGINE.md:71` — the row this engine most easily
#: gets wrong).
HUMAN_NOTE = "Advance paid to supplier."


# ── ground truth ─────────────────────────────────────────────────────────
# Every document below is rendered FROM these tuples, so "did it all arrive?"
# and "did anything arrive that was never sent?" are both decidable.

PAGE_ONE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
)
PAGE_TWO_LINES: tuple[str, ...] = (
    "Invoice No INV-2026-0481",
    "Amount 19800.00",
)
ALL_LINES: tuple[str, ...] = PAGE_ONE_LINES + PAGE_TWO_LINES

#: Every whitespace-separated token that was ever drawn on the document. Used
#: to prove nothing the engine emitted was invented — a token in the artifact
#: that is not in here came from the engine, not from the page.
GROUND_TRUTH_TOKENS: frozenset[str] = frozenset(
    token for line in ALL_LINES for token in line.split()
)

EXPECTED_PAGE_COUNT = 2
#: The scanned fixture's raster, in pixels. Big enough that `cleaner`'s deskew
#: and crop have real ink to work on, small enough that denoising two pages
#: stays cheap on a CI runner.
SCAN_HEIGHT = 400
SCAN_WIDTH = 700

#: The eight bytes that begin every PNG. `cleaner` re-encodes a cleaned image
#: as PNG (`_encode_png`), so this is what an IMAGE artifact's payload must
#: start with — checked rather than assumed.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: Words that assert something about the BUSINESS rather than about the
#: DOCUMENT. `COMMUNICATION_RULES_INPUT_ENGINE.md:71` — *"If a sentence in the
#: output could be wrong about the business rather than wrong about the
#: document, it is an interpretation and does not belong in the Document
#: Evidence Object."* None of them appears in the ground truth above, so any
#: occurrence in the artifact was written by the engine.
BUSINESS_CONCLUSIONS: tuple[str, ...] = (
    "purchase",
    "sale of",
    "expense",
    "asset",
    "liability",
    "revenue",
    "payable",
    "receivable",
    "debit",
    "credit",
    "vendor",
    "customer",
    "supplier",
    "advance",
    "capital",
    "input tax",
    "gstin is",
    "voucher",
    "ledger",
)


# ── a typed facade over PyMuPDF, for AUTHORING and INSPECTING fixtures ────
#
# PyMuPDF ships `py.typed` and leaves its functions unannotated, so under
# `mypy --strict` a bare call is an error and this repository's suppression
# budget is zero-new. Declaring the surface actually used is STRICTER than a
# suppression, not looser: every call below is then checked. Same choice
# `reader.py`, `pipeline.py` and `tests/unit/test_input_engine_pipeline.py`
# each made about the same untyped dependency; those declarations are private
# to their own modules and are not importable from here.


class _AuthoringPage(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...


class _ReadablePage(Protocol):
    def get_text(self, option: str) -> str: ...


class _Document(Protocol):
    page_count: int

    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def __getitem__(self, index: int) -> _ReadablePage: ...
    def insert_pdf(self, source: _Document) -> None: ...
    def convert_to_pdf(self) -> bytes: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _Document: ...


class _OpenStream(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _Document: ...


class _OpenTyped(Protocol):
    def __call__(self, filetype: str, stream: bytes, /) -> _Document: ...


new_pdf = cast(_NewDocument, pymupdf.open)
open_stream = cast(_OpenStream, pymupdf.open)
open_typed = cast(_OpenTyped, pymupdf.open)


# ── the documents ────────────────────────────────────────────────────────


def a_two_page_text_layer_pdf() -> bytes:
    """A real PDF whose characters are embedded, across two pages.

    The MVP's own input shape: `CLAUDE.md` §B.7 puts this system inside the
    Indian GST regime, whose documents are overwhelmingly PDF, and a real one
    is rarely one page.
    """
    document = new_pdf()
    for lines in (PAGE_ONE_LINES, PAGE_TWO_LINES):
        page = document.new_page(width=595, height=842)
        top = 90.0
        for line in lines:
            page.insert_text((60, top), line, fontname="helv", fontsize=13)
            top += 34
        # `insert_text` returns the number of lines written; nothing to assert
        # here beyond the artifact it produces, which every test below reads.
    authored = bytes(document.tobytes())
    document.close()
    return authored


def a_scanned_page_png() -> bytes:
    """One page of pixels with real ink on it. No characters, only shapes."""
    frame: Image = np.full((SCAN_HEIGHT, SCAN_WIDTH), 255, dtype=np.uint8)
    cv2.putText(frame, "SCANNED", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,), 4)
    encoded_ok, encoded = cv2.imencode(".png", frame)
    assert encoded_ok, "OpenCV could not encode the scanned fixture; the test cannot proceed"
    return bytes(encoded.tobytes())


def a_scanned_pdf(pages: int = EXPECTED_PAGE_COUNT) -> bytes:
    """A real PDF carrying only images — what a flatbed scanner produces.

    Built the same way `cleaner._pdf_rebuilt_from_cleaned_pages` builds its
    output, because that is the shape proven to work with this PyMuPDF build:
    a PNG, converted to PDF bytes, reopened, then inserted.
    """
    document = new_pdf()
    raster = a_scanned_page_png()
    for _ in range(pages):
        as_image = open_stream(stream=raster, filetype="png")
        try:
            as_pdf = open_typed("pdf", as_image.convert_to_pdf())
            try:
                document.insert_pdf(as_pdf)
            finally:
                as_pdf.close()
        finally:
            as_image.close()
    authored = bytes(document.tobytes())
    document.close()
    return authored


def text_layer_of(document: bytes) -> str:
    """Every embedded character in a PDF, measured here rather than asked of
    the code under test. `cleaner` has a private helper that answers the same
    question; using it would make the test agree with the implementation by
    construction instead of checking it.
    """
    opened = open_stream(stream=document, filetype="pdf")
    try:
        return "".join(opened[index].get_text("text") for index in range(opened.page_count))
    finally:
        opened.close()


def page_count_of(document: bytes) -> int:
    opened = open_stream(stream=document, filetype="pdf")
    try:
        return opened.page_count
    finally:
        opened.close()


# ── builders ─────────────────────────────────────────────────────────────


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_cleaner_settings() -> cleaner.CleanerSettings:
    """Permissive enough that a normal page cleans without `cleaner` deciding
    the original was safer. Every value is this test's own parameter; none is
    a product default, and `CleanerSettings` supplies none of its own.
    """
    return cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=3.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=10,
        max_ink_loss_fraction=1.0,
    )


def a_pipeline_settings() -> pipeline.PipelineSettings:
    return pipeline.PipelineSettings(
        cleaner_settings=a_cleaner_settings(),
        render_dpi=RENDER_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )


def a_human_business_context() -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=HUMAN_NOTE,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-1",
            evidence_reference="message 1",
            timestamp=WHEN,
            confidence=Decimal("1.0000"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


def document_origin_text(artifact: DocumentEvidenceObject) -> tuple[str, ...]:
    """Every free-text field the engine emits ABOUT THE DOCUMENT.

    The Human Business Context is excluded on purpose: it is the user's own
    words, quoted, and quoting is exactly what Rule 1 requires. Everything
    below is the ENGINE speaking, and everything below must therefore be an
    observation about the artifact rather than a claim about the business.
    """
    report = artifact.confidence_report
    return (
        artifact.structured_document.extracted_text,
        artifact.structured_document.document_structure,
        report.reliability_information,
        *(marker.subject for marker in report.uncertainty_markers),
        *(marker.reason for marker in report.uncertainty_markers),
        *(score.field_name for score in report.confidence_scores),
        *report.risky_fields,
    )


# ── one real multi-page PDF, run once, read by several tests ─────────────
# Session-scoped because Docling loads its models on the first `parser.parse`
# and that dominates the cost; the tests below only READ this result.


@pytest.fixture(scope="session")
def engine1_artifact() -> DocumentEvidenceObject:
    intake = pipeline.DocumentIntake(
        document=a_two_page_text_layer_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:invoice-two-page.pdf",),
    )
    return pipeline.run(
        intake,
        identity=an_identity(),
        settings=a_pipeline_settings(),
        recorded_at=RECORDED_AT,
        human_business_context=a_human_business_context(),
    )


# ── 1. a real document goes in, a Document Evidence Object comes out ─────


def test_a_real_pdf_with_a_text_layer_produces_an_object_carrying_that_text_layers_content(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """The ROADMAP criterion itself, with the artifact's content pinned to the
    ground truth it was rendered from — not merely "something came back".

    Exact equality, not containment: containment passes for an engine that
    also appended a sentence of its own, and that sentence is precisely what
    Rule 1 forbids.
    """
    assert isinstance(engine1_artifact, DocumentEvidenceObject)
    assert engine1_artifact.source_references == ("upload:invoice-two-page.pdf",)
    assert engine1_artifact.structured_document.extracted_text == "\n".join(ALL_LINES)


def test_the_pages_after_the_first_are_not_silently_dropped(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """The failure a one-page fixture cannot see. Every test in
    `tests/unit/test_input_engine_pipeline.py` uses a single-page PDF, so a
    pipeline that read page one and stopped would pass all of them.

    Both halves are asserted because they come from different sub-engines:
    page two's TEXT is `reader`'s, and `page_count` plus a region located on
    page 2 is `parser`'s.
    """
    structure = engine1_artifact.structured_document.document_structure
    for line in PAGE_TWO_LINES:
        assert line in engine1_artifact.structured_document.extracted_text
    assert f"page_count={EXPECTED_PAGE_COUNT}" in structure
    assert f"page={EXPECTED_PAGE_COUNT}" in structure


# ── 2. a scanned PDF: the rasterise-and-rebuild path, on a real document ──


def test_a_scanned_pdf_is_rebuilt_as_a_pdf_then_stops_at_reader_without_ocr() -> None:
    """A no-text-layer PDF takes `cleaner._pdf_rebuilt_from_cleaned_pages`:
    every page rasterised at the caller's DPI, cleaned, and rebuilt into a
    PDF so the pipeline keeps one shape for every input.

    IT DOES NOT PRODUCE A DOCUMENT EVIDENCE OBJECT, and this test says so
    rather than pretending otherwise. `reader` routes a PDF with no text layer
    to PaddleOCR, which is genuinely absent from this environment and from CI
    — measured below as the real `ModuleNotFoundError`, never a mock. What IS
    provable end to end is asserted in full: the rebuild ran, on the real
    document, and produced a real PDF.
    """
    scanned = a_scanned_pdf()
    # precondition, measured independently of the code under test
    assert text_layer_of(scanned).strip() == "", "the scanned fixture must carry no text layer"

    intake = pipeline.DocumentIntake(
        document=scanned,
        media_type=reader.MediaType.PDF,
        source_references=("upload:scan.pdf",),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

    assert raised.value.stage == "reader"
    cause = raised.value.cause
    assert isinstance(cause, ModuleNotFoundError)
    assert cause.name == "paddleocr"

    cleaned = raised.value.preserved.cleaned
    assert cleaned is not None
    # the rebuild path's own verdict, not the pass-through path's
    assert cleaned.preservation_status is cleaner.PreservationStatus.CLEANED_IS_SAFER
    artifact = cleaned.artifact
    assert artifact is not None
    assert artifact.kind is cleaner.MediaKind.PDF
    # a PDF in, a PDF out — a DIFFERENT one, so the rebuild genuinely happened
    assert artifact.payload != scanned
    assert artifact.original == scanned
    assert page_count_of(artifact.payload) == EXPECTED_PAGE_COUNT
    assert text_layer_of(artifact.payload).strip() == ""
    # nothing after the failing stage ran, and nothing was invented for it
    assert raised.value.preserved.reading is None
    assert raised.value.preserved.parsed is None
    assert raised.value.preserved.confidence is None


# ── 3. an image ──────────────────────────────────────────────────────────


def test_an_image_is_cleaned_into_an_image_then_stops_at_reader_without_ocr() -> None:
    """An image has no text layer by definition, so `reader` has only the OCR
    route and the same real absence stops it. `cleaner`'s half completes for
    real and is asserted for real: the cleaned artifact is still an IMAGE, is
    a valid PNG, and is not the bytes that went in.
    """
    raster = a_scanned_page_png()
    intake = pipeline.DocumentIntake(
        document=raster,
        media_type=reader.MediaType.IMAGE,
        source_references=("upload:scan.png",),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

    assert raised.value.stage == "reader"
    cause = raised.value.cause
    assert isinstance(cause, ModuleNotFoundError)
    assert cause.name == "paddleocr"

    cleaned = raised.value.preserved.cleaned
    assert cleaned is not None
    artifact = cleaned.artifact
    assert artifact is not None
    # an image stays an image — the whole point of `CleanedArtifact`
    assert artifact.kind is cleaner.MediaKind.IMAGE
    assert artifact.payload.startswith(PNG_MAGIC)
    assert artifact.payload != raster
    assert artifact.original == raster


# ── 4. the cleaned artifact is what reader and parser consumed ───────────


def test_reader_and_parser_consumed_a_pdf_whose_text_layer_was_still_intact(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """Commit `412eed6` / `KNOWN_FAILURES.md` F-017, proven BEHAVIOURALLY.

    Before it, `cleaner`'s output was a BITMAP, so `run` could only have handed
    `reader` and `parser` pixels — and a bitmap of a PDF has no text layer, so
    `reader` would have routed to PaddleOCR and `parser` would have seen one
    rasterised page. Both consequences are observable in the artifact, and both
    are asserted here:

      `extracted_text` equals the drawn ground truth. The only backend that
      can produce that is the PDF text layer: OCR is genuinely absent from
      this environment, measured twice above as `ModuleNotFoundError`, so a
      run that reached OCR could not have returned an artifact at all.

      `page_count=2` and a region on page 2. `parser` received the whole
      multi-page PDF. A rasterised first page is one page, every time.

    This is as far as behaviour reaches, and the next test says exactly why.
    """
    assert engine1_artifact.structured_document.extracted_text == "\n".join(ALL_LINES)
    structure = engine1_artifact.structured_document.document_structure
    assert f"page_count={EXPECTED_PAGE_COUNT}" in structure
    assert f"page={EXPECTED_PAGE_COUNT}" in structure


def test_on_the_text_layer_path_the_cleaned_payload_is_the_intake_bytes_themselves() -> None:
    """WHY the test above is the strongest behavioural form available, stated
    as a measurement instead of an excuse.

    `cleaner._pdf_passed_through` returns `payload=data` — the caller's own
    object — because rasterising a text-layer PDF to deskew it would destroy
    the exact characters that make it readable without recognition. So on the
    ONE route that completes end to end, the cleaned document and the intake
    are not merely equal, they are the same object, and no experiment can tell
    "reader read the cleaned artifact" from "reader read the original".

    Exhaustively, from the two routes where they DO differ: an image always
    goes to OCR, and a rebuilt scan still has no text layer so it also goes to
    OCR. Neither completes while PaddleOCR is absent. That is why
    `tests/unit/test_input_engine_pipeline.py` asserts on `run`'s source text
    — necessity, not laziness — and this pins the fact that makes it so.
    """
    document = a_two_page_text_layer_pdf()

    cleaned = cleaner.clean_artifact(
        document, cleaner.MediaKind.PDF, a_cleaner_settings(), render_dpi=RENDER_DPI
    )

    artifact = cleaned.artifact
    assert artifact is not None
    assert artifact.payload == document
    assert artifact.payload is document
    assert cleaned.preservation_status is cleaner.PreservationStatus.ORIGINAL_IS_SAFER


# ── 5. no interpretation crosses the boundary ────────────────────────────


def test_nothing_the_engine_emitted_about_the_document_asserts_anything_about_the_business(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """`COMMUNICATION_RULES_INPUT_ENGINE.md:55` Rule 1 — *"The Input Engine
    sends observations. It does not send interpretations."*

    None of the banned words appears in the ground truth, so an occurrence in
    any engine-written field could only have been added by the engine — and
    every one of them would be a claim that could be wrong about the BUSINESS
    while the document itself was read perfectly.
    """
    for text in document_origin_text(engine1_artifact):
        lowered = text.lower()
        for conclusion in BUSINESS_CONCLUSIONS:
            assert conclusion not in lowered, (
                f"the Input Engine emitted {conclusion!r} in {text!r}. That is a "
                "claim about the business, not an observation about the document "
                "(COMMUNICATION_RULES_INPUT_ENGINE.md:71)."
            )


def test_no_token_reaches_the_structure_that_was_never_drawn_on_the_document(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """The other half of Rule 1, and the one a banned-word list cannot catch:
    an interpretation nobody thought to ban.

    Every piece of text `parser` reported is checked token by token against
    what was actually drawn. A label the engine assigned, a summary it wrote,
    a normalised amount it produced — each introduces a token that was never
    on the page, and each fails here.
    """
    structure = engine1_artifact.structured_document.document_structure
    region_texts: list[str] = re.findall(r"text='([^']*)'", structure)

    assert region_texts, (
        "no region text was found in document_structure. Either parser reported "
        "nothing, or its rendering changed shape — this test must not pass "
        "vacuously, so it fails instead."
    )
    for region_text in region_texts:
        for token in region_text.split():
            assert token in GROUND_TRUTH_TOKENS, (
                f"parser reported the token {token!r}, which was never drawn on "
                "the document. Engine 1 may report what it observed and nothing else."
            )


def test_the_human_note_crosses_as_a_quotation_and_is_never_merged_into_document_evidence(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """`ENGINE_1_INPUT_ENGINE_RULES.md:233` — *"Engine 1 never merges the two
    into a single fact."* The hardest row of Rule 1's own table: recording
    THAT a user said something is an observation; recording WHAT they said as
    true is an interpretation, and once the quotation marks are gone nothing
    downstream can tell which happened.

    So the note must appear verbatim in its own component and in no
    document-origin field at all — not the extracted text, not the structure,
    not the reliability sentence, not a marker's reason.
    """
    context = engine1_artifact.human_business_context
    assert context is not None
    assert context.original_user_text == HUMAN_NOTE
    assert context.provenance.source_type is SourceType.HUMAN
    # `ENGINE_1_INPUT_ENGINE_RULES.md:295` — Engine 1 cannot assess whether a
    # note and a document field mean the same thing; that IS interpretation.
    assert context.provenance.corroborated is Corroborated.NOT_ASSESSED

    for text in document_origin_text(engine1_artifact):
        assert HUMAN_NOTE not in text, (
            f"the user's own sentence appeared in {text!r}, a field labelled as "
            "read off the document. A human assertion wearing the authority of "
            "an extracted reading is the merge ENGINE_1:233 forbids."
        )


def test_the_human_note_is_scored_for_capture_fidelity_and_never_for_truth(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """`ENGINE_1_INPUT_ENGINE_RULES.md` §5A — *"capture confidence is not truth
    confidence."* A perfect score here means the system stored exactly what was
    typed. It must never be readable as "and it is true", so the only score the
    note earns is the one named for capture fidelity, and it is the only score
    in this artifact at all.
    """
    scores = engine1_artifact.confidence_report.confidence_scores
    assert [score.field_name for score in scores] == [confidence_report.CAPTURE_FIDELITY_FIELD_NAME]
    assert scores[0].confidence == confidence_report.CAPTURE_FIDELITY_ON_EXACT_MATCH


# ── 6. the traceability contract ─────────────────────────────────────────


def test_reader_produced_a_source_location_for_every_region_and_the_boundary_dropped_them_all(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """WHERE traceability is lost, measured, so the next test's failure has an
    address rather than a shrug.

    `reader` does its job: `ENGINE_1_INPUT_ENGINE_RULES.md:511` — *"source
    locations are emitted even for low-confidence extractions"* — and it emits
    one per region. `pipeline.reader_output` carries them into
    `assembly.ReaderOutput.source_locations`. `assembly.assemble` then builds
    `StructuredDocument` from `raw_extracted_text` ALONE: the schema has no
    slot for a location, so every one of them stops at the engine boundary.

    WHAT CHANGED WITH THE F-019 FIX, AND WHY THIS STILL READS THE SAME. The
    `reader → parser` pipe now exists: `parser` maps every region `reader`
    extracted, keeps its source location, and `pipeline.detected_fields` turns
    each SCORED mapping into a real `DetectedField` carrying that location on
    its provenance —
    `test_an_ocr_reading_crosses_the_boundary_with_all_three_intact` proves it
    against the real modules. This document is a PDF TEXT LAYER, and
    `reader.read_pdf_text_layer` scores nothing: no recogniser ran, so there is
    no measurement (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER IS `None`").
    `Provenance.confidence` is mandatory, `1.0000` is the default
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids and `0.0000` is a lie the other
    way, so `ENGINE_1_INPUT_ENGINE_RULES.md:245` leaves exactly one honest
    option and the pipeline takes it: no field is emitted for an unscored value.

    So the loss is no longer "the boundary drops locations". It is now exactly
    one thing, named: **this schema cannot say "read, and not measured"**, which
    is a §M amendment to a frozen P2 schema and the owner's to make.

    Pinned in this direction deliberately, and the pin is now SHARPER: it
    asserts the absence of a score is the reason, so a change that gives the
    text-layer path a fabricated confidence turns this red rather than green.
    """
    reading = reader.read(
        a_two_page_text_layer_pdf(),
        media_type=reader.MediaType.PDF,
        render_dpi=RENDER_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )
    carried = pipeline.reader_output(reading)

    assert len(reading.regions) == len(ALL_LINES)
    assert len(carried.source_locations) == len(ALL_LINES)
    assert all("SourceLocation(" in location for location in carried.source_locations)
    # and the PDF text layer scores nothing, honestly: no recogniser ran
    assert set(carried.extraction_confidence) == {"None"}

    # the pipe to `parser` DOES exist now, and it carries every region across
    # with its location intact — the mapping is not where anything is lost
    mapped = parser.map_fields(pipeline.extracted_regions(reading))
    assert len(mapped) == len(ALL_LINES)
    assert [field.value for field in mapped] == list(ALL_LINES)
    assert all(field.source_location.startswith("BoundingBox(") for field in mapped)

    # what stops is the FIELD, and for exactly one stated reason: no score
    assert all(field.extraction_confidence is None for field in mapped)
    emitted = engine1_artifact.structured_document
    assert "SourceLocation(" not in emitted.extracted_text
    assert "SourceLocation(" not in emitted.document_structure
    assert emitted.detected_fields == ()


def test_every_extracted_value_that_crosses_the_boundary_carries_source_confidence_and_uncertainty(
    engine1_artifact: DocumentEvidenceObject,
) -> None:
    """THE BOUNDARY CONTRACT, ASSERTED AS THE LOCKED DOCUMENTS STATE IT.

    `COMMUNICATION_RULES_INPUT_ENGINE.md:111` Rule 4 — Traceability:
    *"Every extracted value must maintain: 1. Source ... 2. Confidence ...
    3. Uncertainty ... They are not stripped at the engine boundary."*

    `ENGINE_1_INPUT_ENGINE_RULES.md:239,245` — *"Every extracted value must
    preserve ... A value carried without all three is not evidence and must
    not be emitted."*

    The contract is therefore a disjunction, and it is written below as one:
    either every extracted value carries all three, or no extracted value is
    emitted. `DetectedField` is the only slot in the frozen schema that can
    carry them — `name`, `value`, and a complete `Provenance` whose
    `evidence_reference` is where within the source and whose `confidence` is
    how reliable the reading was.

    THIS ASSERTION IS NOT WEAKENED TO MATCH THE CODE. If it fails, the code is
    wrong and the document wins (`CLAUDE.md` §M).
    """
    emitted = engine1_artifact.structured_document
    values_crossed = emitted.extracted_text != ""

    assert emitted.detected_fields or not values_crossed, (
        f"{len(ALL_LINES)} extracted values crossed the Input -> Understanding "
        f"boundary inside extracted_text ({emitted.extracted_text!r}) while "
        "detected_fields is empty, so not one of them carries a source "
        "location, a confidence or an uncertainty marker of its own. "
        "COMMUNICATION_RULES_INPUT_ENGINE.md:111 forbids stripping the three "
        "at the boundary; ENGINE_1_INPUT_ENGINE_RULES.md:245 forbids emitting "
        "the value at all without them."
    )

    scored = {score.field_name for score in engine1_artifact.confidence_report.confidence_scores}
    for field in emitted.detected_fields:
        assert field.provenance.evidence_reference.strip(), (
            f"detected field {field.name!r} names no place within its source; "
            "that is requirement 1 of Rule 4, and it is missing."
        )
        assert field.provenance.source_type is SourceType.DOCUMENT
        assert field.name in scored, (
            f"detected field {field.name!r} carries no entry in the Confidence "
            "Report, so requirement 3 of Rule 4 — whether, and why, doubt "
            "exists — is unanswerable for it."
        )


def test_an_ocr_reading_crosses_the_boundary_with_all_three_intact() -> None:
    """THE SAME CONTRACT, ON THE ONE ROUTE THAT CAN SATISFY IT TODAY, AND THE
    EXACT INPUT `KNOWN_FAILURES.md` F-019 WAS RECORDED FROM.

    F-019's demonstration: an OCR reading whose two regions scored 0.3100 and
    0.2800 — one of them `Total 1,18,OOO.00`, letter-O where zeros belong,
    which is what a 28%-confidence misread looks like — produced an artifact
    with `confidence_scores=()`, `uncertainty_markers=()` and
    `risky_fields=()`. The doubt was gone by the time anything downstream could
    see it. That is the whole of the *"never post a wrong entry"* non-goal
    failing at the source.

    THE ABSENT THING IS THE RECOGNISER, AND NOTHING STANDS IN FOR IT (§J.6).
    PaddleOCR is genuinely unavailable here and in CI — this file measures that
    twice above as a real `ModuleNotFoundError` — so `reader.read` cannot
    produce a scored reading in this environment and no amount of test wiring
    can make it. The reading below is therefore built from `reader`'s OWN real
    types and pushed through the real `pipeline`, the real `parser`, the real
    `confidence_report` and the real `assembly`, including every
    `DocumentEvidenceObject` validator. Mocking PaddleOCR would have proved the
    mock; this proves the boundary.

    WHAT WOULD PROVE THIS WRONG: a field arriving without its location, a score
    arriving different from the one measured, or the two copies of the score
    disagreeing. All three are asserted, by identity where identity is the
    stronger claim.
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
    cleaned = cleaner.clean_artifact(
        a_scanned_page_png(), cleaner.MediaKind.IMAGE, a_cleaner_settings(), render_dpi=RENDER_DPI
    )
    structure = parser.ParsedStructure(
        source_reference="upload:scan.png",
        page_count=1,
        regions=(),
        tables=(),
        mapped_fields=parser.map_fields(pipeline.extracted_regions(reading)),
    )

    report = confidence_report.record_confidence(
        cleaned,
        pipeline.region_readings(reading),
        pipeline.parsed_fields(structure),
        pipeline.missing_fields(structure),
    )
    artifact = assembly.assemble(
        parts=assembly.SubEngineOutputs(
            cleaner=pipeline.cleaner_output(cleaned),
            reader=pipeline.reader_output(reading),
            parser=pipeline.parser_output(structure, recorded_at=RECORDED_AT),
            confidence=pipeline.confidence_output(report),
        ),
        identity=an_identity(),
        source_references=("upload:scan.png",),
    )

    emitted = artifact.structured_document
    assert emitted.extracted_text != ""
    assert emitted.detected_fields, (
        "values crossed inside extracted_text and not one became a detected "
        "field, which is the F-019 state this test exists to keep closed."
    )

    scores = {
        score.field_name: score.confidence for score in artifact.confidence_report.confidence_scores
    }
    for field in emitted.detected_fields:
        # 1. SOURCE — where in the artifact it came from
        assert field.provenance.source_id == "upload:scan.png"
        assert field.provenance.evidence_reference.startswith("BoundingBox(page=1")
        assert field.provenance.source_type is SourceType.DOCUMENT
        # 2. CONFIDENCE — how reliable the extraction is, and the same number twice
        assert scores[field.name] == field.provenance.confidence
        # 3. UNCERTAINTY — answerable, because the name is in the report at all
        assert field.name in scores

    # the exact values F-019 recorded as lost, in the artifact, on the right values
    by_value = {field.value: field.provenance.confidence for field in emitted.detected_fields}
    assert by_value == {misread: higher, "GSTIN 27AAEC": lower}
    assert by_value[misread] is higher  # the object reader measured, not an equal copy
