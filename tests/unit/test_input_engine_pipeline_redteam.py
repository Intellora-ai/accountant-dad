"""`pipeline` — a second, adversarial pass, aimed at the two failures that a
suite written alongside the code cannot see (`CLAUDE.md` §J.(b), §J.10).

THE FIRST: THE BYPASS COMING BACK WITHOUT ANY TEST NOTICING.
    Commit `412eed6` rewired every stage to read the CLEANED artifact; before
    it, `reader` and `parser` each re-opened the raw document and cleaning
    changed nothing downstream (`KNOWN_FAILURES.md` F-012/F-017). The existing
    suite guards that with `test_the_pipeline_reads_the_cleaned_document_not_
    the_original`, which reads `run`'s SOURCE TEXT. A source assertion is a
    real guard and it is not a behavioural one: it cannot fail for a pipeline
    that is genuinely wired wrong, only for one that is spelled wrong.

    So this file proves it by observation instead, and the awkward fact that
    makes that hard is stated rather than worked around:

        ON EVERY INPUT THAT COMPLETES THE PIPELINE TODAY, THE CLEANED PAYLOAD
        IS BYTE-IDENTICAL TO THE INTAKE.

    Measured, not assumed. `cleaner.clean_artifact` passes a text-layer PDF
    through untouched (`payload is data`), and that is the only input reader
    can finish on in this environment, because the rebuilt form of a scanned
    PDF carries no text layer and PaddleOCR is genuinely absent
    (`KNOWN_FAILURES.md` F-002). A byte comparison on the happy path therefore
    proves nothing at all — it passes whichever document each stage read.

    Two attacks get past that, and both are here:

      - `test_a_scanned_pdf_hands_reader_the_rebuilt_cleaned_bytes...` uses the
        one real input where the cleaner's payload genuinely differs from the
        intake. Reader dies on it (no OCR), which is fine: the assertion is
        about what reader was HANDED, captured by a spy that records and then
        calls the real function.

      - `substituted_cleaning_run` makes cleaning visibly change the content.
        The real `cleaner.clean_artifact` runs, and its result is then re-issued
        through cleaner's own public `replace_artifact` carrying a DIFFERENT,
        real, text-layer PDF. Every later stage is the genuine module. If any
        of them re-opened `intake.document`, the final Document Evidence Object
        would carry the intake's text; it carries the substitute's, line for
        line, through both `reader` and `parser`.

THE SECOND: A FAILURE THAT LOOKS LIKE A SUCCESS.
    `ENGINE_1_INPUT_ENGINE_RULES.md` §9 — *"Information is invented"* is a
    failure of this engine, and `CLAUDE.md` Law 11 forbids failing silently. A
    half-assembled Document Evidence Object presented as whole is the worst
    available outcome, so every failure test below asserts not only WHICH stage
    stopped but that NO artifact of any kind came back with it — walking the
    exception's own attributes for one rather than trusting that none is there.
    The `confidence` stage, which no existing test makes fail, is made to fail
    here.

WHAT THIS FILE FOUND AND DID NOT FIX. `_payload_of`'s refusal is raised OUTSIDE
every `try`, so it escapes as a bare `PipelineError` and `cleaner`'s completed
work is discarded — which contradicts the module's own stated contract that
"nothing already produced is thrown away". It is unreachable through any real
input today, so it is pinned as observed behaviour rather than left red; see
`test_a_missing_cleaned_artifact_escapes_as_a_bare_pipeline_error...`.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import numpy.typing as npt
import pymupdf
import pytest

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DocumentEvidenceObject,
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
    TransactionId,
)

Image = npt.NDArray[np.uint8]

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)

#: The clock `pipeline.run` is GIVEN. Distinct from `WHEN`, which is the
#: human note's own provenance timestamp -- `run` reads no clock of its own,
#: so the caller must supply this, and a test asserting one while meaning the
#: other would pass by coincidence.
RECORDED_AT = datetime(2026, 8, 6, 11, 30, tzinfo=UTC)

#: This file's own choice, not a product default — `PipelineSettings` requires
#: the caller to supply it and `pipeline` invents no number of its own.
RENDER_DPI = 150
#: Low enough that the vision fallback can never fire in a test about anything
#: else, matching `test_input_engine_reader.py`'s own `NO_FALLBACK`.
NO_FALLBACK = Decimal("0.0")

#: The text drawn onto the document the caller submits.
INTAKE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "Invoice No INV-2026-0481",
)
#: The text drawn onto the document the substituted cleaner hands downstream.
#: Deliberately shares no word with `INTAKE_LINES`, so "which document did this
#: stage read" has a one-token answer either way.
CLEANED_LINES: tuple[str, ...] = (
    "DELIVERY CHALLAN",
    "Borealis Works Limited",
    "Challan No DC-2026-9137",
)
#: One token from each, present in exactly one of the two documents.
INTAKE_ONLY = "INV-2026-0481"
CLEANED_ONLY = "DC-2026-9137"

#: A note whose text must never reach `cleaner`, `reader` or `parser`.
HUMAN_NOTE = "Advance paid to supplier against this document."


# ── a typed facade over PyMuPDF, for AUTHORING fixtures only ──────────────
# Same facade, same reason, as `test_input_engine_pipeline.py`'s: PyMuPDF ships
# `py.typed` but leaves its functions unannotated, and this repository's
# zero-new-suppressions gate rules out silencing that per line. Not imported
# from there — it is module-private to that file.


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
    def convert_to_pdf(self) -> bytes: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _OpenDocument(Protocol):
    def __call__(
        self, *args: str | bytes, stream: bytes = ..., filetype: str = ...
    ) -> _AuthoringDocument: ...


open_document = cast(_OpenDocument, pymupdf.open)


def a_text_layer_pdf(lines: tuple[str, ...]) -> bytes:
    """One page carrying a real, embedded text layer."""
    doc = open_document()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    out = bytes(doc.tobytes())
    doc.close()
    return out


def a_scanned_pdf() -> bytes:
    """A PDF with NO text layer: a page rasterised and re-wrapped as a PDF.

    The one real input for which `cleaner.clean_artifact` produces a payload
    that genuinely differs from the intake — it takes the rebuild branch rather
    than the pass-through one, so "which bytes did the next stage get" has an
    observable answer.
    """
    source = open_document()
    page = source.new_page(width=300, height=200)
    page.insert_text((20, 60), "SCANNED", fontname="helv", fontsize=20)
    rendered = source[0].get_pixmap(dpi=100).tobytes("png")
    source.close()

    as_image = open_document(stream=rendered, filetype="png")
    as_pdf = open_document("pdf", as_image.convert_to_pdf())
    out = bytes(as_pdf.tobytes())
    as_pdf.close()
    as_image.close()
    return out


def a_blank_pdf() -> bytes:
    """A valid container with nothing in it — one page, no ink, no text."""
    doc = open_document()
    doc.new_page(width=300, height=200)
    out = bytes(doc.tobytes())
    doc.close()
    return out


# ── builders ────────────────────────────────────────────────────────────


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_cleaner_settings() -> cleaner.CleanerSettings:
    """Permissive enough that a small rendered page cleans without tripping
    `PreservationStatus.ORIGINAL_IS_SAFER` for a reason unrelated to the test.
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
        table_structure=None,
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


# ── the observation apparatus ───────────────────────────────────────────
# Every spy below RECORDS and then calls the real sub-engine. None of them
# stands in for one, so `CLAUDE.md` §J.6 (REAL + ISOLATED) still holds: the
# genuine `cleaner`, `reader`, `parser`, `confidence_report` and `assembly`
# all run. What is added is a note of what each was handed.


@dataclass
class StagesObserved:
    """What each stage was actually given, and what it actually returned."""

    cleaner_data: bytes | None = None
    cleaned: cleaner.CleanedDocument | None = None
    reader_document: bytes | None = None
    reader_media_type: reader.MediaType | None = None
    reader_render_dpi: int | None = None
    reading: reader.Reading | None = None
    parser_path: Path | None = None
    parser_bytes: bytes | None = None
    parser_source_reference: str | None = None
    #: `reader`'s regions as `parser` actually received them — the F-019 arrow,
    #: observed rather than assumed. `None` means `parse` was never called;
    #: `()` would mean it was called with nothing, and the two are different.
    parser_regions: tuple[parser.ExtractedRegion, ...] | None = None
    parsed: parser.ParsedStructure | None = None
    result: DocumentEvidenceObject | None = None


def _install_spies(patch: pytest.MonkeyPatch, observed: StagesObserved) -> None:
    """Wrap all three sub-engines the pipeline calls, recording their inputs."""
    real_clean = cleaner.clean_artifact
    real_read = reader.read
    real_parse = parser.parse

    def spy_clean(
        data: bytes,
        kind: cleaner.MediaKind,
        settings: cleaner.CleanerSettings,
        *,
        render_dpi: int,
    ) -> cleaner.CleanedDocument:
        observed.cleaner_data = data
        observed.cleaned = real_clean(data, kind, settings, render_dpi=render_dpi)
        return observed.cleaned

    def spy_read(
        document: bytes,
        *,
        media_type: reader.MediaType,
        render_dpi: int,
        vision_fallback_threshold: Decimal,
    ) -> reader.Reading:
        observed.reader_document = document
        observed.reader_media_type = media_type
        observed.reader_render_dpi = render_dpi
        observed.reading = real_read(
            document,
            media_type=media_type,
            render_dpi=render_dpi,
            vision_fallback_threshold=vision_fallback_threshold,
        )
        return observed.reading

    def spy_parse(
        source: Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        observed.parser_path = source
        # Read the file AS PARSER SEES IT, at the moment parser sees it: the
        # bytes on disk are the only evidence of which document was handed on.
        observed.parser_bytes = source.read_bytes()
        observed.parser_source_reference = source_reference
        # `extracted_regions` is `reader`'s output reaching `parser` — the F-019
        # arrow. A spy that dropped it would let a regression that stopped
        # passing regions through go unnoticed here, so it is forwarded
        # verbatim rather than defaulted away.
        observed.parser_regions = extracted_regions
        observed.parsed = real_parse(
            source,
            source_reference=source_reference,
            extracted_regions=extracted_regions,
            table_structure=table_structure,
        )
        return observed.parsed

    patch.setattr(cleaner, "clean_artifact", spy_clean)
    patch.setattr(reader, "read", spy_read)
    patch.setattr(parser, "parse", spy_parse)


@pytest.fixture(scope="module")
def observed_run() -> StagesObserved:
    """One real, complete run with every stage watched.

    Module-scoped because `parser.parse` loads Docling's models, which is the
    expensive part of every run; the patches are removed inside this function,
    before any test executes, so no other test in this module ever sees a
    patched module.
    """
    observed = StagesObserved()
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:observed.pdf",),
    )
    with pytest.MonkeyPatch.context() as patch:
        _install_spies(patch, observed)
        observed.result = pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            human_business_context=a_human_business_context(),
            recorded_at=RECORDED_AT,
        )
    return observed


@pytest.fixture(scope="module")
def substituted_cleaning_run() -> StagesObserved:
    """The decisive bypass experiment: cleaning that VISIBLY changes content.

    The real `cleaner.clean_artifact` runs on the intake. Its result is then
    re-issued through `cleaner.replace_artifact` — cleaner's own public API,
    not a hand-built object — carrying a different, real, text-layer PDF as the
    payload. Every measurement `cleaner` actually made survives untouched; only
    the artifact handed downstream differs.

    Everything after that is the genuine module. Whatever the final Document
    Evidence Object says, some stage read the document it says it read.
    """
    observed = StagesObserved()
    substitute = a_text_layer_pdf(CLEANED_LINES)
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:substituted.pdf",),
    )
    real_clean = cleaner.clean_artifact

    def substituting_clean(
        data: bytes,
        kind: cleaner.MediaKind,
        settings: cleaner.CleanerSettings,
        *,
        render_dpi: int,
    ) -> cleaner.CleanedDocument:
        observed.cleaner_data = data
        real = real_clean(data, kind, settings, render_dpi=render_dpi)
        observed.cleaned = cleaner.replace_artifact(
            real,
            cleaner.CleanedArtifact(
                kind=cleaner.MediaKind.PDF, payload=substitute, original=data, raster=None
            ),
        )
        return observed.cleaned

    with pytest.MonkeyPatch.context() as patch:
        _install_spies(patch, observed)
        patch.setattr(cleaner, "clean_artifact", substituting_clean)
        observed.result = pipeline.run(
            intake, identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )
    return observed


# ── ATTACK 1: the bypass, proven gone by observation ────────────────────


def test_a_scanned_pdf_hands_reader_the_rebuilt_cleaned_bytes_not_the_intake() -> None:
    """The one REAL input whose cleaned payload differs from the intake.

    A PDF with no text layer takes `cleaner`'s rebuild branch, so the payload
    is a newly-built PDF rather than the bytes that arrived. Reader cannot
    finish on it — the rebuilt form has no text layer either and PaddleOCR is
    genuinely absent — and that is beside the point: what is asserted is which
    bytes reader was HANDED, which is exactly what the F-012 bypass got wrong.
    """
    observed = StagesObserved()
    scanned = a_scanned_pdf()
    intake = pipeline.DocumentIntake(
        document=scanned, media_type=reader.MediaType.PDF, source_references=("upload:scan.pdf",)
    )

    with pytest.MonkeyPatch.context() as patch:
        _install_spies(patch, observed)
        with pytest.raises(pipeline.PipelineStageError) as raised:
            pipeline.run(
                intake,
                identity=an_identity(),
                settings=a_pipeline_settings(),
                recorded_at=RECORDED_AT,
            )

    assert raised.value.stage == "reader"
    cleaned = raised.value.preserved.cleaned
    assert cleaned is not None
    assert cleaned.artifact is not None
    # the experiment is only valid if cleaning genuinely changed the bytes
    assert cleaned.artifact.payload != scanned
    # ... and this is the assertion the bypass would break: reader was handed
    # the cleaned artifact's own payload object, not the document that arrived.
    assert observed.reader_document is cleaned.artifact.payload
    assert observed.reader_document != intake.document


def test_reader_reads_the_substituted_cleaned_document_and_the_artifact_proves_it(
    substituted_cleaning_run: StagesObserved,
) -> None:
    """Cleaning made a visible difference; the final artifact carries it.

    `extracted_text` is `reader`'s own output, joined in `reader`'s own order.
    It matches the SUBSTITUTED document line for line and contains no token
    from the intake. A `reader` that re-opened `intake.document` would produce
    the exact opposite, and this assertion would fail.
    """
    result = substituted_cleaning_run.result
    assert result is not None

    assert result.structured_document.extracted_text == "\n".join(CLEANED_LINES)
    assert INTAKE_ONLY not in result.structured_document.extracted_text
    assert CLEANED_ONLY in result.structured_document.extracted_text


def test_parser_parses_the_substituted_cleaned_document_and_the_artifact_proves_it(
    substituted_cleaning_run: StagesObserved,
) -> None:
    """The same proof for the stage that opens the document a third time.

    `document_structure` is built entirely from `parser.ParsedStructure`, so a
    token that appears in it came through Docling. The substitute's token is
    there; the intake's is not.
    """
    result = substituted_cleaning_run.result
    assert result is not None

    assert CLEANED_ONLY in result.structured_document.document_structure
    assert INTAKE_ONLY not in result.structured_document.document_structure


def test_the_file_parser_was_given_holds_the_cleaned_payload_byte_for_byte(
    substituted_cleaning_run: StagesObserved,
) -> None:
    """One level below the artifact: the bytes actually on disk when `parser`
    was called. `_parse_document` materialises the cleaned payload to a
    temporary file, and writing `intake.document` there instead is the exact
    shape the F-017 migration removed.
    """
    observed = substituted_cleaning_run
    assert observed.cleaned is not None
    assert observed.cleaned.artifact is not None

    assert observed.parser_bytes == observed.cleaned.artifact.payload
    assert observed.parser_bytes != observed.cleaner_data


def test_reader_and_parser_were_handed_the_same_cleaned_bytes_as_each_other(
    substituted_cleaning_run: StagesObserved,
) -> None:
    """One pipeline, not two. Two stages reading two different documents is
    precisely what F-012 recorded, and it is invisible in any artifact that
    happens to agree.
    """
    observed = substituted_cleaning_run

    assert observed.reader_document == observed.parser_bytes


def test_the_temporary_file_carries_the_media_type_and_is_removed_afterwards(
    observed_run: StagesObserved,
) -> None:
    """Docling picks its backend from the extension, so a cleaned PDF written
    to a `.png` path would be parsed by the wrong reader entirely. And the file
    is a filesystem detail of one call, not state: it must not outlive the run.
    """
    path = observed_run.parser_path
    assert path is not None

    assert path.suffix == ".pdf"
    assert not path.exists()


def test_the_temporary_file_is_removed_even_when_parser_refuses() -> None:
    """The `finally` that matters: `_parse_document` writes the cleaned payload
    to a temporary file BEFORE calling `parser.parse`, so a parser that raises
    is exactly the case that could leak one.

    CORRECTED TRIGGER, UNCHANGED SUBJECT. This used to pass a blank source
    reference, relying on `parser.parse` refusing it. `DocumentIntake` now
    refuses a blank reference at construction (the root-cause fix for the hole
    red-teaming the business-failure path exposed), so the failure is injected
    at the `parser.parse` seam instead — the same pattern this file already
    uses for `confidence_report.record_confidence`. The temporary file is still
    written by the real `_parse_document` before the seam is reached, so what
    is under test is untouched.
    """
    before = set(Path(tempfile.gettempdir()).glob("*.pdf"))
    injected = RuntimeError("parser refuses, after the temporary file exists")
    seen: dict[str, object] = {}
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:leak-check.pdf",),
    )

    def refusing_parse(
        source: Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        # Everything parser was handed is recorded and asserted below. The file
        # must EXIST at the moment parser is called, or this test would pass
        # without ever exercising the cleanup it is named for.
        seen.update(
            source=source,
            existed=source.exists(),
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
    # the temporary file really existed when parser saw it, and is gone now
    handed = seen["source"]
    assert isinstance(handed, Path)
    assert handed.suffix == ".pdf"
    assert seen["existed"] is True, "the file was already gone, so cleanup proves nothing"
    assert not handed.exists()
    assert set(Path(tempfile.gettempdir()).glob("*.pdf")) - before == set()
    # parser was entered with the real inputs, not a stripped-down call
    assert seen["source_reference"] == "upload:leak-check.pdf"
    assert seen["extracted_regions"] != ()
    assert seen["table_structure"] is None


# ── ATTACK 2: order, and side effects between stages ────────────────────


def test_reader_produces_the_same_reading_when_run_before_nothing_at_all(
    observed_run: StagesObserved,
) -> None:
    """`reader` must depend on its declared input and on nothing a previous
    stage left behind. Called here in isolation, with no cleaner run before it,
    on the same bytes the pipeline handed it.
    """
    document = observed_run.reader_document
    assert document is not None

    isolated = reader.read(
        document,
        media_type=reader.MediaType.PDF,
        render_dpi=RENDER_DPI,
        vision_fallback_threshold=NO_FALLBACK,
    )

    assert isolated == observed_run.reading


def test_parser_produces_the_same_structure_when_run_first_instead_of_third(
    observed_run: StagesObserved, tmp_path: Path
) -> None:
    """The order attack proper: `parser` runs THIRD in the pipeline, and here
    it runs alone, from a file this test wrote, with no cleaner and no reader
    before it. An identical `ParsedStructure` is what proves the third position
    carries no hidden dependency on the first two.

    THE COMPARISON IS NOW LIKE-FOR-LIKE, WHICH IT SILENTLY WAS NOT. `parser` has
    a second input since the F-019 fix — `extracted_regions`, `reader`'s output —
    and this test used to call it without them while the pipeline called it with
    five. The structures then differed in `mapped_fields` for a reason that had
    nothing to do with ORDER, which is what this test is about.

    Giving both calls the same input is what makes the assertion mean what its
    name says, and it makes the test STRONGER rather than weaker: `mapped_fields`
    is now part of what must match, so a `parser` that mapped reader's regions
    differently depending on what ran before it would now be caught. The regions
    are the ones the spy OBSERVED being passed, not a set this test invented, so
    the pipeline's real input is what gets replayed.
    """
    document = observed_run.parser_bytes
    assert document is not None
    in_pipeline = observed_run.parsed
    assert in_pipeline is not None
    regions = observed_run.parser_regions
    assert regions is not None, "parse was never called, so there is no order to compare"
    assert regions, "parse was called with no regions at all, which would make this test vacuous"
    source = tmp_path / "isolated.pdf"
    source.write_bytes(document)

    isolated = parser.parse(
        source,
        source_reference="upload:observed.pdf",
        extracted_regions=regions,
        table_structure=None,
    )

    assert isolated == in_pipeline
    # and the mapped fields specifically — the part that only exists because
    # reader's output reached parser at all
    assert isolated.mapped_fields == in_pipeline.mapped_fields


def test_the_conversion_functions_give_the_same_answer_in_any_order(
    observed_run: StagesObserved,
) -> None:
    """`pipeline`'s six packaging functions are called in a fixed order inside
    `run`. Called here in the reverse order, twice each, on the real objects
    the real sub-engines produced — a different answer would mean one of them
    mutates what it was given.
    """
    reading = observed_run.reading
    parsed = observed_run.parsed
    cleaned = observed_run.cleaned
    assert reading is not None
    assert parsed is not None
    assert cleaned is not None
    report = confidence_report_module.record_confidence(
        cleaned, pipeline.region_readings(reading), (), pipeline.missing_fields(parsed)
    )

    reversed_order = (
        pipeline.confidence_output(report),
        pipeline.parser_output(parsed, recorded_at=RECORDED_AT),
        pipeline.reader_output(reading),
        pipeline.region_readings(reading),
        pipeline.missing_fields(parsed),
        pipeline.document_structure_text(parsed),
    )
    forward_order = (
        pipeline.document_structure_text(parsed),
        pipeline.missing_fields(parsed),
        pipeline.region_readings(reading),
        pipeline.reader_output(reading),
        pipeline.parser_output(parsed, recorded_at=RECORDED_AT),
        pipeline.confidence_output(report),
    )

    assert reversed_order == tuple(reversed(forward_order))


def test_packaging_the_cleaner_output_twice_never_changes_what_it_reports(
    observed_run: StagesObserved,
) -> None:
    """`cleaner_output` is compared field by field rather than as a whole:
    `CleanerOutput.cleaned_document_representation` holds a pixel array, and
    comparing two of those with `==` yields an array, not a truth value.
    """
    cleaned = observed_run.cleaned
    assert cleaned is not None

    first = pipeline.cleaner_output(cleaned)
    second = pipeline.cleaner_output(cleaned)

    assert first.preservation_status == second.preservation_status
    assert first.quality_issues_detected == second.quality_issues_detected
    assert first.cleaned_document_representation is second.cleaned_document_representation
    assert first.cleaned_document_representation is cleaned.cleaned


# ── ATTACK 3: the human note never reaches an extraction sub-engine ─────


def test_no_extraction_sub_engine_is_ever_handed_the_human_note(
    observed_run: StagesObserved,
) -> None:
    """§1.1/§1.2/§1.3 all say the same thing: *"a provided source passes
    through untouched"*. The existing suite checks the note's text is absent
    from the final artifact's extracted text. This checks the stronger, earlier
    fact — that no extraction sub-engine was ever given it at all, so it could
    not be read, structured or scored even by accident.
    """
    note = HUMAN_NOTE.encode()
    handed_to_extraction = (
        observed_run.cleaner_data,
        observed_run.reader_document,
        observed_run.parser_bytes,
    )

    for given in handed_to_extraction:
        assert given is not None
        assert note not in given

    # ... and it still reaches the artifact, verbatim, by the channel it should
    result = observed_run.result
    assert result is not None
    assert result.human_business_context is not None
    assert result.human_business_context.original_user_text == HUMAN_NOTE


def test_the_settings_the_caller_supplied_reach_reader_unchanged(
    observed_run: StagesObserved,
) -> None:
    """`render_dpi` is reused for two physical purposes inside `run`. Reuse is
    correct; quietly substituting a second number would not be, and only an
    observation at the boundary can tell the two apart.
    """
    assert observed_run.reader_render_dpi == RENDER_DPI
    assert observed_run.reader_media_type is reader.MediaType.PDF
    assert observed_run.parser_source_reference == "upload:observed.pdf"


# ── ATTACK 4: a stage fails — loudly, and with nothing half-built ───────


def _artifacts_reachable_from(error: pipeline.PipelineStageError) -> list[object]:
    """Every object the caller can reach through the raised exception.

    A Document Evidence Object hiding on any of them would be a partial
    artifact presented as a whole one — the failure this attack exists for. The
    exception's own attributes, its `args`, and every field of the preserved
    result are all walked, so a future attribute cannot quietly carry one.
    """
    reachable: list[object] = [*error.args, error.cause, error.preserved]
    reachable.extend(vars(error).values())
    reachable.extend(getattr(error.preserved, field.name) for field in fields(error.preserved))
    return reachable


def test_the_confidence_stage_failing_names_itself_and_keeps_all_three_before_it() -> None:
    """The one stage no existing test makes fail.

    `confidence_report.record_confidence` cannot be made to raise by any real
    document this environment can process, so the failure is injected at that
    exact seam — `CLAUDE.md` §I.9, break it on purpose. `cleaner`, `reader` and
    `parser` are all genuine and all genuinely succeed first, so what is being
    tested is the pipeline's response to a real stage boundary failing.
    """
    injected = RuntimeError("the confidence sub-engine could not complete")
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:confidence.pdf",),
    )

    def refusing_record(
        cleaned: cleaner.CleanedDocument,
        reader_regions: tuple[confidence_report_module.RegionReading, ...],
        parsed_fields: tuple[confidence_report_module.ParsedField, ...],
        missing_fields: tuple[confidence_report_module.MissingField, ...],
        human_capture: confidence_report_module.HumanCaptureEvidence | None = None,
    ) -> ConfidenceReport:
        raise injected

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(confidence_report_module, "record_confidence", refusing_record)
        with pytest.raises(pipeline.PipelineStageError) as raised:
            pipeline.run(
                intake,
                identity=an_identity(),
                settings=a_pipeline_settings(),
                recorded_at=RECORDED_AT,
            )

    assert raised.value.stage == "confidence"
    assert raised.value.cause is injected
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is not None
    assert raised.value.preserved.parsed is not None
    # the stage that failed left nothing behind, and assembly never ran
    assert raised.value.preserved.confidence is None
    assert not any(
        isinstance(reachable, DocumentEvidenceObject)
        for reachable in _artifacts_reachable_from(raised.value)
    )


@pytest.fixture(scope="module")
def assembly_failure() -> pipeline.PipelineStageError:
    """All four sub-engines succeed for real; `assembly.assemble` is the one
    that refuses, on two identical source references its own schema forbids.
    The most dangerous moment for a half-built artifact: everything needed to
    fabricate one exists by then.
    """
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:dup.pdf", "upload:dup.pdf"),
    )
    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake, identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )
    return raised.value


def test_a_failing_assembly_returns_no_document_evidence_object_at_all(
    assembly_failure: pipeline.PipelineStageError,
) -> None:
    assert assembly_failure.stage == "assembly"
    assert not any(
        isinstance(reachable, DocumentEvidenceObject)
        for reachable in _artifacts_reachable_from(assembly_failure)
    )


def test_a_failing_assembly_still_preserves_every_earlier_stage_unmodified(
    assembly_failure: pipeline.PipelineStageError,
) -> None:
    """Nothing already produced is thrown away — and what is kept is the real
    object, not a summary of it. Each preserved part is checked for content
    that only the genuine sub-engine could have produced.
    """
    preserved = assembly_failure.preserved
    assert preserved.cleaned is not None
    assert preserved.reading is not None
    assert preserved.parsed is not None
    assert preserved.confidence is not None

    assert preserved.cleaned.artifact is not None
    assert [region.text for region in preserved.reading.regions] == list(INTAKE_LINES)
    assert preserved.parsed.source_reference == "upload:dup.pdf"
    assert preserved.confidence.reliability_information != ""


# ── ATTACK 5: empty and degenerate inputs, end to end ───────────────────


@pytest.mark.parametrize(
    ("name", "document", "media_type", "expected_stage", "expected_cause"),
    [
        ("zero bytes, PDF", b"", reader.MediaType.PDF, "cleaner", cleaner.UndecodableArtifactError),
        (
            "zero bytes, image",
            b"",
            reader.MediaType.IMAGE,
            "cleaner",
            cleaner.UndecodableArtifactError,
        ),
        ("one byte, PDF", b"%", reader.MediaType.PDF, "cleaner", pymupdf.FileDataError),
        (
            "one byte, image",
            b"%",
            reader.MediaType.IMAGE,
            "cleaner",
            cleaner.UndecodableArtifactError,
        ),
        (
            "prose declared as a PDF",
            b"this is not a pdf, it is a sentence",
            reader.MediaType.PDF,
            "cleaner",
            pymupdf.FileDataError,
        ),
    ],
)
def test_a_degenerate_document_is_named_as_unread_never_absorbed_as_an_empty_reading(
    name: str,
    document: bytes,
    media_type: reader.MediaType,
    expected_stage: str,
    expected_cause: type[Exception],
) -> None:
    """Empty, nearly-empty and mistyped input, run through the real pipeline.

    THE ATTACK THIS DEFENDS AGAINST IS UNCHANGED AND IS NOW SHARPER. None of
    these may be absorbed into an empty reading, because downstream that is
    indistinguishable from an honest reading of a page that genuinely had
    nothing on it (`ENGINE_1_INPUT_ENGINE_RULES.md` §1.2's own words).

    WHAT CHANGED, AND WHY THE ASSERTION MOVED RATHER THAN RELAXED. This used to
    require `PipelineStageError`. All five inputs here are BUSINESS failures —
    `APPLICATION_LAYER_CONTRACTS.md:30`, *"unreadable, corrupt, zero-byte: an
    object is produced recording the failure"* — so raising was itself the
    defect, and they now cross as artifacts.

    That makes this test MORE necessary, not less: an emitted artifact is
    exactly the shape that could masquerade as a successful read of a blank
    page. So the assertion is no longer "it raised" but the thing actually at
    stake — the artifact must be DISTINGUISHABLE from an honest empty reading,
    and the only thing that distinguishes them is the named uncertainty marker.
    An implementation that emitted a silent empty artifact would have satisfied
    neither the old test nor this one, but only this one says why.
    """
    intake = pipeline.DocumentIntake(
        document=document, media_type=media_type, source_references=(f"upload:{name}",)
    )

    evidence = pipeline.run(
        intake, identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
    )

    # nothing was read, and nothing was invented to stand in for it
    assert evidence.structured_document.extracted_text == ""
    assert evidence.structured_document.detected_fields == ()
    assert evidence.structured_document.detected_tables == ()
    assert evidence.confidence_report.confidence_scores == ()

    # and it is NOT silent: the failure is named, at the right stage, carrying
    # the real cause's own words — this is the whole difference between this
    # artifact and one produced by honestly reading a blank page
    (marker,) = evidence.confidence_report.uncertainty_markers
    assert marker.subject == f"upload:{name}"

    # each parametrised cause is classified BUSINESS — that classification is
    # the reason an artifact exists here at all instead of an exception, so it
    # is asserted rather than assumed
    assert issubclass(expected_cause, pipeline.BUSINESS_FAILURE)

    # the sub-engine's OWN message travelled into the marker. Checked by
    # extracting whatever sits between the template's two fixed halves rather
    # than by hardcoding two different libraries' wording, so this stays true
    # if either message is reworded and still fails if the cause is dropped.
    prefix = f"this document could not be read at the {expected_stage!r} stage: "
    assert marker.reason.startswith(prefix)
    cause_text = marker.reason[len(prefix) :].split(" No value was extracted")[0]
    assert cause_text.strip(), "the sub-engine's own message did not reach the marker"

    assert expected_stage in evidence.confidence_report.reliability_information
    assert "nothing was measured" in evidence.confidence_report.reliability_information


def test_a_valid_container_holding_nothing_is_cleaned_then_refused_not_returned_empty() -> None:
    """A one-page PDF with no ink and no text — a valid container with no
    content, which is the case most likely to be quietly absorbed.

    `cleaner` succeeds on it, which is correct: an unmarked page is a real
    page. `reader` then cannot finish, because there is no text layer to read
    and OCR is genuinely absent — so the pipeline stops rather than emitting a
    Document Evidence Object whose `extracted_text` is `""`. That empty string
    would be indistinguishable downstream from a page that was read and held
    nothing.
    """
    intake = pipeline.DocumentIntake(
        document=a_blank_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:blank.pdf",),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake, identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )

    assert raised.value.stage == "reader"
    assert isinstance(raised.value.cause, ModuleNotFoundError)
    # cleaner's real work on the blank page survives; nothing later exists
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is None
    assert raised.value.preserved.parsed is None
    assert raised.value.preserved.confidence is None


def test_a_pdf_whose_only_text_is_whitespace_is_refused_rather_than_read_as_empty() -> None:
    """Whitespace is not text. `cleaner` treats the page as having no text
    layer and rebuilds it; `reader` skips whitespace-only spans and finds
    nothing to read. Neither may turn that into a successful empty reading.
    """
    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(("   ", "\t")),
        media_type=reader.MediaType.PDF,
        source_references=("upload:whitespace.pdf",),
    )

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.run(
            intake, identity=an_identity(), settings=a_pipeline_settings(), recorded_at=RECORDED_AT
        )

    assert raised.value.stage == "reader"
    assert raised.value.preserved.cleaned is not None
    assert raised.value.preserved.reading is None


# ── ATTACK 6: the refusal that loses what it promised to preserve ───────


def test_a_missing_cleaned_artifact_escapes_as_a_bare_pipeline_error_losing_the_cleaner_work() -> (
    None
):
    """A GAP FOUND BY THIS PASS, PINNED RATHER THAN FIXED (`CLAUDE.md` §E.7).

    `_payload_of`'s refusal is raised OUTSIDE every `try` in `run`, so unlike
    all five stages it does not become a `PipelineStageError` and carries no
    `preserved`. `cleaner` has already completed at that point and its real
    output is discarded — which is the opposite of the module's own stated
    contract that "nothing already produced is thrown away".

    Two things make this a pinned observation rather than a red test. It is
    unreachable through any real input: `clean_artifact` sets `artifact` on
    both of its branches, so only an injected `CleanedDocument` gets here. And
    the refusal itself is right — falling back to `intake.document` would
    silently reinstate the two-pipeline architecture F-017 removed, which is
    far worse than losing a preserved value.

    If a later change wraps this as a stage error carrying `preserved`, that is
    an improvement and this test is what forces the update to be deliberate.
    """
    real_clean = cleaner.clean_artifact

    def clean_without_an_artifact(
        data: bytes,
        kind: cleaner.MediaKind,
        settings: cleaner.CleanerSettings,
        *,
        render_dpi: int,
    ) -> cleaner.CleanedDocument:
        real = real_clean(data, kind, settings, render_dpi=render_dpi)
        return cleaner.CleanedDocument(
            original=real.original,
            cleaned=real.cleaned,
            quality_observations=real.quality_observations,
            preservation_status=real.preservation_status,
            artifact=None,
        )

    intake = pipeline.DocumentIntake(
        document=a_text_layer_pdf(INTAKE_LINES),
        media_type=reader.MediaType.PDF,
        source_references=("upload:no-artifact.pdf",),
    )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cleaner, "clean_artifact", clean_without_an_artifact)
        with pytest.raises(pipeline.PipelineError, match="no media-aware artifact") as raised:
            pipeline.run(
                intake,
                identity=an_identity(),
                settings=a_pipeline_settings(),
                recorded_at=RECORDED_AT,
            )

    # it refuses rather than falling back to the intake — the property that matters
    assert "reinstate the bypass" in str(raised.value)
    # ... and the gap: no stage is named, and cleaner's completed work is gone
    assert not isinstance(raised.value, pipeline.PipelineStageError)
    assert not hasattr(raised.value, "preserved")


# ── ATTACK 7: nothing downstream of a refusal is ever fabricated ────────


def test_no_stage_after_a_failure_ever_runs(observed_run: StagesObserved) -> None:
    """The counterpart to every "preserved" assertion above, stated as the
    positive control it needs: on a run that SUCCEEDS, all three watched stages
    genuinely ran and produced real output. Without this, "reading is None"
    after a failure could equally mean the spy simply never records anything.
    """
    assert observed_run.cleaned is not None
    assert observed_run.reading is not None
    assert observed_run.parsed is not None
    assert observed_run.reading.regions != ()
    assert observed_run.parsed.page_count != 0


def test_a_reader_failure_leaves_parser_uncalled_entirely() -> None:
    """Directly observed rather than inferred from `preserved`: the spy on
    `parser.parse` records every call it receives, and on a run that stops at
    `reader` it must record none at all.
    """
    observed = StagesObserved()
    intake = pipeline.DocumentIntake(
        document=a_scanned_pdf(),
        media_type=reader.MediaType.PDF,
        source_references=("upload:scan.pdf",),
    )

    with pytest.MonkeyPatch.context() as patch:
        _install_spies(patch, observed)
        with pytest.raises(pipeline.PipelineStageError) as raised:
            pipeline.run(
                intake,
                identity=an_identity(),
                settings=a_pipeline_settings(),
                recorded_at=RECORDED_AT,
            )

    assert raised.value.stage == "reader"
    assert observed.reader_document is not None
    assert observed.parser_path is None
    assert observed.parsed is None


def test_a_cleaner_failure_leaves_both_reader_and_parser_uncalled() -> None:
    """UNCHANGED SUBJECT, CORRECTED SHAPE. What this test guards — that no stage
    after a failed one is ever entered — is untouched and is still asserted by
    direct observation through the spies, not inferred from `preserved`.

    Only the failure's SHAPE changed. Zero bytes is a business failure
    (`APPLICATION_LAYER_CONTRACTS.md:30`), so the run now returns an artifact
    recording it instead of raising. The risk that creates is precisely that
    emitting could be implemented by letting the rest of the pipeline run over
    empty values — so "reader and parser were never called" matters MORE once
    an artifact comes back, and it is asserted on the same real spies as before.
    """
    observed = StagesObserved()
    intake = pipeline.DocumentIntake(
        document=b"", media_type=reader.MediaType.PDF, source_references=("upload:empty.pdf",)
    )

    with pytest.MonkeyPatch.context() as patch:
        _install_spies(patch, observed)
        evidence = pipeline.run(
            intake,
            identity=an_identity(),
            settings=a_pipeline_settings(),
            recorded_at=RECORDED_AT,
        )

    # cleaner was reached and refused; nothing after it ran at all
    assert observed.cleaner_data == b""
    assert observed.cleaned is None
    assert observed.reader_document is None
    assert observed.parser_path is None
    assert observed.parser_regions is None

    # and the artifact that came back is the failure record, not a run over
    # empty values dressed up as a reading
    assert evidence.structured_document.extracted_text == ""
    assert evidence.structured_document.detected_fields == ()
    (marker,) = evidence.confidence_report.uncertainty_markers
    assert "'cleaner'" in marker.reason


# ── ATTACK 8: the artifact a successful run returns is whole ────────────


def test_a_successful_run_returns_one_complete_artifact_and_no_placeholder(
    observed_run: StagesObserved,
) -> None:
    """The success case attacked from the same direction as the failures: an
    artifact that is present but hollow is the same defect as a partial one.
    Every part is checked against what the real sub-engine actually produced.
    """
    result = observed_run.result
    reading = observed_run.reading
    parsed = observed_run.parsed
    assert result is not None
    assert reading is not None
    assert parsed is not None

    assert result.structured_document.extracted_text == "\n".join(
        region.text for region in reading.regions
    )
    assert result.structured_document.document_structure == pipeline.document_structure_text(parsed)
    assert result.source_references == ("upload:observed.pdf",)
    assert result.confidence_report.reliability_information != ""


def test_the_pipeline_returns_a_document_evidence_object_only_through_assembly(
    observed_run: StagesObserved,
) -> None:
    """`assembly.assemble` is the only creator of this artifact — an artifact
    built anywhere else would bypass every schema check INV-11 depends on.
    Rebuilding it here from the SAME real parts must reproduce it exactly,
    except for the identity, which is minted per run.
    """
    result = observed_run.result
    reading = observed_run.reading
    parsed = observed_run.parsed
    cleaned = observed_run.cleaned
    assert result is not None
    assert reading is not None
    assert parsed is not None
    assert cleaned is not None

    report = confidence_report_module.record_confidence(
        cleaned,
        pipeline.region_readings(reading),
        (),
        pipeline.missing_fields(parsed),
        confidence_report_module.HumanCaptureEvidence(
            submitted_text=HUMAN_NOTE, stored=a_human_business_context()
        ),
    )
    rebuilt = assembly.assemble(
        parts=assembly.SubEngineOutputs(
            cleaner=pipeline.cleaner_output(cleaned),
            reader=pipeline.reader_output(reading),
            parser=pipeline.parser_output(parsed, recorded_at=RECORDED_AT),
            confidence=pipeline.confidence_output(report),
        ),
        identity=an_identity(),
        source_references=("upload:observed.pdf",),
        human_business_context=a_human_business_context(),
    )

    assert rebuilt.structured_document == result.structured_document
    assert rebuilt.confidence_report == result.confidence_report
    assert rebuilt.document_id != result.document_id
