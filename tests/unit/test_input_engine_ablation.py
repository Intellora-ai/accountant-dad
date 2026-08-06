"""ADVERSARIAL_TESTING.md attack 19 — ID ablation, pointed at the REAL Engine 1
pipeline for the first time.

    IDENTITY != INTELLIGENCE. IDs identify objects. They never influence
    reasoning.  (`CLAUDE.md` §O, standing architectural rules; INV-9.)

`accountant_dad.ablation` has existed, seeded and proven, since P2 — but only
ever against hand-built pydantic models. `MVP_IMPLEMENTATION_BLUEPRINT.md:135`
makes "ID ablation test passes" part of P2's definition of done, and until this
file existed nothing had ever run the harness against `pipeline.run`. The
instrument was built and never fired.

WHAT IS AT STAKE IF AN IDENTIFIER LEAKS. Engine 1's output is the evidence every
later engine reasons from. If a Document ID, an Artifact ID, a Transaction ID, a
source reference or a filename changes any extracted value, any confidence, any
region or any ordering, then two byte-identical invoices can produce two
different Document Evidence Objects — and therefore, eventually, two different
sets of books for the same transaction. That is not a cosmetic defect; it is
`CLAUDE.md` §B.8, "it must NEVER post a wrong entry", failing silently.

HOW THIS FILE AVOIDS BEING THE HOLLOW VERSION OF ITSELF. An ablation test that
compares a summary, a hash of a few fields, or a hand-written field list passes
for the wrong reason and keeps passing while the artifact grows fields nobody
compared. Four properties are what make this evidence rather than decoration:

  COMPLETE     the comparison walks `model_dump()` — every field, at every
               depth, of whatever `DocumentEvidenceObject` currently is. There
               is no field list in this file to fall out of date.

  PROVEN COMPLETE  `test_the_comparison_reports_every_single_leaf...` perturbs
               EVERY leaf the real artifact actually has, one at a time, and
               requires the comparison to name exactly that leaf. A field added
               to the schema tomorrow is covered the moment it appears, and a
               comparison that stopped looking at some subtree fails here first.

  INDEPENDENT  each identity dimension is varied ALONE — the Artifact ID, the
               Transaction ID, a PARENT version's Artifact ID, the source
               reference, and the filename — so a failure names which one
               leaked instead of reporting "something changed".

  INVERSELY CONTROLLED  three separate tests prove the comparison CAN fail:
               one character of the document changes the output; an identifier
               injected into a non-identifier field is caught by the real
               harness; and a field present on one side only is reported. A
               test that passes because nothing can vary proves nothing.

THE ONE FIELD EXEMPTED FROM EVERY COMPARISON, AND WHY IT IS FORCED RATHER THAN
CHOSEN. `assembly.assemble` mints a fresh `DocumentId` on every call
(`evidence.DocumentId.new`, a UUIDv4), so `document_id.value` differs between
ANY two runs — including two runs of byte-identical input with the same identity
envelope. `test_two_identical_runs_differ_only_in_the_freshly_minted_document_id`
measures exactly that and pins the exempt set to that ONE path; every other test
reuses the frozen set it pins. If assembly ever starts minting a second
per-run value, or stops minting this one, that test fails before any other test
can quietly widen the exemption.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import pymupdf
import pytest

from accountant_dad import ablation
from accountant_dad.artifacts.evidence import (
    Corroborated,
    DocumentEvidenceObject,
    DocumentId,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
)
from accountant_dad.engines.input_engine import cleaner, parser, pipeline, reader
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
)

# ── a typed facade over PyMuPDF, for AUTHORING fixtures only ──────────────
#
# The same facade `test_input_engine_pipeline.py` and `test_input_engine_
# reader.py` each declare over the same untyped dependency, for the same
# reason: PyMuPDF ships `py.typed` and leaves its functions unannotated, so
# `mypy --strict` refuses a bare call and this repository's zero-new-
# suppressions gate rules out silencing it per line. Not imported from those
# files — each is module-private to its own.


class _AuthoringPage(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


open_pdf = cast(_NewDocument, pymupdf.open)

# ── ground truth ────────────────────────────────────────────────────────

#: The invoice is rendered FROM this list, so the inverse control below changes
#: real document content rather than an incidental byte of PDF container.
INVOICE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
    "Invoice No INV-2026-0481",
)

#: One character of the last line, changed. Everything else is byte-identical.
ONE_CHARACTER_CHANGED: tuple[str, ...] = (
    *INVOICE_LINES[:-1],
    "Invoice No INV-2026-0482",
)

SOURCE_REFERENCES: tuple[str, ...] = ("upload:invoice-481.pdf",)
OTHER_SOURCE_REFERENCES: tuple[str, ...] = ("upload:invoice-999.pdf",)

WHEN = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)

#: The clock `pipeline.run` is GIVEN. Distinct from `WHEN`, which is the
#: human note's own provenance timestamp -- `run` reads no clock of its own,
#: so the caller must supply this, and a test asserting one while meaning the
#: other would pass by coincidence.
RECORDED_AT = datetime(2026, 8, 6, 11, 30, tzinfo=UTC)

#: A test parameter, never a product default — `pipeline.PipelineSettings`
#: still requires the caller to supply it. Mirrors the value
#: `test_input_engine_pipeline.py` chose for the identical purpose.
RENDER_DPI = 150
#: So the vision fallback never fires in a test about something else.
NO_FALLBACK = Decimal("0.0")

#: A seed, not a threshold. `ablation.ablate` is deterministic from it, so a
#: failure here is reproducible exactly (Law 44).
SEED = 20260806

#: How many runs `test_the_filename_the_parser_actually_sees...` compares. Two
#: is the smallest number that can show a filename differing between runs.
TWO_RUNS = 2

#: `ablation.ablate` numbers its trials from 1, not from 0.
FIRST_TRIAL = 1


# ── the comparison ──────────────────────────────────────────────────────
#
# Generic on purpose. Another agent is actively changing what this pipeline
# emits; a comparison written against a fixed field list would go quietly
# out of date, which is the failure mode this whole file exists to catch.

#: Stands for "this side has no such field at all". Distinct from every value
#: a `model_dump()` can produce, so "missing here, present there" is a
#: difference rather than a silent match.
ABSENT = object()

#: The replacement `perturbed_copies` writes into one leaf at a time. A fresh
#: `object()` is unequal to every real value by identity, so no leaf can
#: accidentally already hold it.
PERTURBED = object()


def differing_paths(left: object, right: object, prefix: str = "") -> frozenset[str]:
    """Every path at which two dumped artifacts disagree, at every depth.

    Structural and complete: mappings are compared key by key (a key present on
    one side only is a difference), sequences element by element (a length
    difference is a difference at the surplus index), and anything else by
    value. Nothing is summarised, hashed, or skipped.
    """
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        found: set[str] = set()
        for key in {*left, *right}:
            child = f"{prefix}.{key}" if prefix else str(key)
            found |= differing_paths(left.get(key, ABSENT), right.get(key, ABSENT), child)
        return frozenset(found)
    if isinstance(left, list | tuple) and isinstance(right, list | tuple):
        found = set()
        for index in range(max(len(left), len(right))):
            here = left[index] if index < len(left) else ABSENT
            there = right[index] if index < len(right) else ABSENT
            found |= differing_paths(here, there, f"{prefix}[{index}]")
        return frozenset(found)
    return frozenset() if left == right else frozenset({prefix})


def perturbed_copies(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """`value` copied once per leaf, each copy with exactly that leaf replaced.

    Used to prove `differing_paths` actually looks at every field of the real
    artifact rather than a subtree of it. An EMPTY container is itself a leaf —
    otherwise `parent_versions=()` and `detected_fields=()` would never be
    perturbed and a comparison blind to them would pass.
    """
    if isinstance(value, Mapping) and value:
        mapped: list[tuple[str, object]] = []
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            for path, replacement in perturbed_copies(item, child):
                copy = dict(value)
                copy[key] = replacement
                mapped.append((path, copy))
        return mapped
    if isinstance(value, list | tuple) and value:
        listed: list[tuple[str, object]] = []
        for index, item in enumerate(value):
            for path, replacement in perturbed_copies(item, f"{prefix}[{index}]"):
                copy_of_sequence = list(value)
                copy_of_sequence[index] = replacement
                listed.append((path, tuple(copy_of_sequence)))
        return listed
    return [(prefix, PERTURBED)]


# ── builders ────────────────────────────────────────────────────────────


def an_invoice_pdf(lines: tuple[str, ...] = INVOICE_LINES) -> bytes:
    """A one-page PDF carrying a real text layer, built with PyMuPDF."""
    doc = open_pdf()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    out = bytes(doc.tobytes())
    doc.close()
    return out


def a_cleaner_settings() -> cleaner.CleanerSettings:
    """Permissive enough that a small rendered page cleans without forcing
    `PreservationStatus.ORIGINAL_IS_SAFER` — this file varies identity, never
    cleaning behaviour."""
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
    """Supplied on every run so the optional half of the artifact is under
    comparison too — an identifier could just as easily leak into a field that
    is only populated when a human note exists."""
    return HumanBusinessContext(
        original_user_text="Advance paid to supplier.",
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-1",
            evidence_reference="message 1",
            timestamp=WHEN,
            confidence=Decimal("1.0000"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


def an_identity(
    *,
    artifact_id: ArtifactId | None = None,
    transaction_id: TransactionId | None = None,
    version: int = FIRST_VERSION,
    parent_versions: tuple[ParentVersion, ...] = (),
) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=artifact_id if artifact_id is not None else ArtifactId.new(),
        version=version,
        parent_versions=parent_versions,
        transaction_id=transaction_id if transaction_id is not None else TransactionId.new(),
    )


def run_pipeline(
    identity: IdentityEnvelope,
    *,
    lines: tuple[str, ...] = INVOICE_LINES,
    source_references: tuple[str, ...] = SOURCE_REFERENCES,
) -> DocumentEvidenceObject:
    """One real run of Engine 1's real pipeline. No stand-in for any stage."""
    intake = pipeline.DocumentIntake(
        document=an_invoice_pdf(lines),
        media_type=reader.MediaType.PDF,
        source_references=source_references,
    )
    return pipeline.run(
        intake,
        identity=identity,
        settings=a_pipeline_settings(),
        human_business_context=a_human_business_context(),
        recorded_at=RECORDED_AT,
    )


#: The identity every comparison starts from. Minted once, so the artifact-id
#: test and the transaction-id test vary ONE field of the SAME envelope.
BASE_IDENTITY = an_identity()

#: The single path `test_two_identical_runs...` proves varies run to run, and
#: therefore the only path any later comparison is allowed to ignore. Written
#: here once; pinned there by measurement, never assumed.
MINTED_PER_RUN = frozenset({"document_id.value"})


@pytest.fixture(scope="session")
def baseline() -> DocumentEvidenceObject:
    """One real end-to-end run, shared. Docling's model loading is the
    expensive part of `pipeline.run`, so the tests that only READ this result
    share one run rather than paying for it repeatedly."""
    return run_pipeline(BASE_IDENTITY)


# ── the comparison is complete, and it can fail ─────────────────────────


def test_the_comparison_reports_every_single_leaf_of_the_real_artifact(
    baseline: DocumentEvidenceObject,
) -> None:
    """The defence against the hollow ablation test.

    Every leaf the REAL Document Evidence Object actually has is perturbed, one
    at a time, and the comparison must name exactly that leaf and nothing else.
    A comparison that stopped walking some subtree — or that a schema change
    grew a field past — fails here, before any ablation result could be
    believed.
    """
    dumped = baseline.model_dump()
    perturbations = perturbed_copies(dumped)
    assert perturbations, "the artifact dumped to nothing; there is nothing being compared"
    for path, mutated in perturbations:
        assert differing_paths(dumped, mutated) == frozenset({path}), (
            f"perturbing {path!r} was not reported as exactly that path"
        )


def test_the_comparison_reports_a_field_present_on_one_side_only() -> None:
    """Second inverse control on the comparison itself. A dropped field is a
    difference, not a match — otherwise an engine that stopped emitting
    something would ablate clean."""
    complete = {"structured_document": {"extracted_text": "x", "document_structure": "y"}}
    truncated = {"structured_document": {"extracted_text": "x"}}
    assert differing_paths(complete, truncated) == frozenset(
        {"structured_document.document_structure"}
    )
    assert differing_paths(truncated, complete) == frozenset(
        {"structured_document.document_structure"}
    )


def test_the_comparison_reports_a_sequence_that_lost_an_element() -> None:
    """Third shape the comparison must not miss: same prefix, fewer items."""
    assert differing_paths({"source_references": ("a", "b")}, {"source_references": ("a",)}) == (
        frozenset({"source_references[1]"})
    )


# ── the identity envelope, one field at a time ──────────────────────────


def test_two_identical_runs_differ_only_in_the_freshly_minted_document_id(
    baseline: DocumentEvidenceObject,
) -> None:
    """The measurement that everything else in this file rests on.

    Same bytes, same identity envelope, same settings, run twice. The Document
    ID is minted fresh by `assembly.assemble` on every call, so it differs; if
    ANYTHING else differs, the pipeline is non-deterministic and no ablation
    result from it means anything (`ablation.py`'s own stated blind spot).
    """
    again = run_pipeline(BASE_IDENTITY)
    assert baseline.document_id != again.document_id, (
        "the Document ID did not change between two runs, so exempting it "
        "from the comparisons below would be a choice rather than a necessity"
    )
    differences = differing_paths(baseline.model_dump(), again.model_dump())
    assert differences == MINTED_PER_RUN, (
        f"two identical runs disagreed on {sorted(differences - MINTED_PER_RUN)}"
    )


def test_changing_only_the_artifact_id_changes_only_the_artifact_id(
    baseline: DocumentEvidenceObject,
) -> None:
    """Vary the Artifact ID alone. Nothing extracted, scored, ordered or
    structured may move with it."""
    varied = run_pipeline(
        an_identity(
            artifact_id=ArtifactId.new(),
            transaction_id=BASE_IDENTITY.transaction_id,
        )
    )
    differences = differing_paths(baseline.model_dump(), varied.model_dump())
    assert differences == MINTED_PER_RUN | {"identity.artifact_id.value"}, (
        f"the Artifact ID leaked into {sorted(differences - MINTED_PER_RUN)}"
    )


def test_changing_only_the_transaction_id_changes_only_the_transaction_id(
    baseline: DocumentEvidenceObject,
) -> None:
    """Vary the Transaction ID alone. INV-3 keeps it a separate type from the
    Artifact ID; INV-9 keeps it out of every reasoned value."""
    varied = run_pipeline(
        an_identity(
            artifact_id=BASE_IDENTITY.artifact_id,
            transaction_id=TransactionId.new(),
        )
    )
    differences = differing_paths(baseline.model_dump(), varied.model_dump())
    assert differences == MINTED_PER_RUN | {"identity.transaction_id.value"}, (
        f"the Transaction ID leaked into {sorted(differences - MINTED_PER_RUN)}"
    )


def test_changing_only_a_parent_versions_artifact_id_changes_only_that_parent() -> None:
    """The NESTED identifier, which a shallow ablation would silently exonerate.

    `ablation.py` names this case explicitly: a lineage-aware engine is most
    likely to read a PARENT's id, and a top-level-only swap would leave that
    real identifier in place and then report a clean pass.
    """
    parent_artifact = ArtifactId.new()
    shared_transaction = TransactionId.new()
    second_version = FIRST_VERSION + 1

    def descendant(parent: ArtifactId) -> IdentityEnvelope:
        return an_identity(
            transaction_id=shared_transaction,
            version=second_version,
            parent_versions=(ParentVersion(artifact_id=parent, version=FIRST_VERSION),),
        )

    original_identity = descendant(parent_artifact)
    original = run_pipeline(original_identity)
    varied = run_pipeline(
        an_identity(
            artifact_id=original_identity.artifact_id,
            transaction_id=shared_transaction,
            version=second_version,
            parent_versions=(ParentVersion(artifact_id=ArtifactId.new(), version=FIRST_VERSION),),
        )
    )
    differences = differing_paths(original.model_dump(), varied.model_dump())
    expected = MINTED_PER_RUN | {"identity.parent_versions[0].artifact_id.value"}
    assert differences == expected, (
        f"a parent version's Artifact ID leaked into {sorted(differences - expected)}"
    )


def test_changing_only_the_source_reference_changes_only_the_source_reference(
    baseline: DocumentEvidenceObject,
) -> None:
    """A source reference is an identifier too, and this one is not inert: it
    is handed to `parser.parse` as `source_reference`. It may be carried into
    the artifact and it may appear in a parser error, but it may not move a
    single extracted value, score or ordering.

    WHERE IT IS NOW CARRIED, AND WHY THAT IS THE DOCSTRING'S FIRST CLAUSE
    RATHER THAN A LEAK. Since Amendment 5 every mapped value becomes a
    `DetectedField`, and `Provenance.source_id` is *"WHICH artifact"* — it IS
    the source reference, recorded where INV-11 requires each fact to state its
    origin. Changing the reference therefore changes that slot, by definition:
    a run of a differently-named source whose provenance still named the old
    one would be the actual defect. Before the amendment `detected_fields` was
    empty on this input, so the sites simply did not exist to be checked.

    THE SET IS DERIVED, NEVER HARD-CODED. Writing `detected_fields[0..3]` would
    pass for the wrong reason the day the fixture yields a fifth field. The
    expectation is computed from the baseline's own field count, so a field
    appearing or disappearing changes what this test demands.

    STRICTER THAN BEFORE, NOT LOOSER. The four assertions below did not exist
    previously. Permitting `source_id` to move without pinning everything
    beside it would trade one blind spot for another, so every extracted value,
    every name, every within-artifact location, every score and the ORDER of
    all of them are asserted byte-identical across the two runs.
    """
    varied = run_pipeline(BASE_IDENTITY, source_references=OTHER_SOURCE_REFERENCES)
    differences = differing_paths(baseline.model_dump(), varied.model_dump())

    carried_into_provenance = {
        f"structured_document.detected_fields[{index}].provenance.source_id"
        for index in range(len(baseline.structured_document.detected_fields))
    }
    permitted = MINTED_PER_RUN | {"source_references[0]"} | carried_into_provenance
    assert differences == permitted, (
        f"the source reference leaked into {sorted(differences - permitted)}"
    )

    base_fields = baseline.structured_document.detected_fields
    varied_fields = varied.structured_document.detected_fields
    assert [field.name for field in varied_fields] == [field.name for field in base_fields], (
        "renaming the source moved a field name or reordered the fields"
    )
    assert [field.value for field in varied_fields] == [field.value for field in base_fields], (
        "renaming the source moved an extracted VALUE, which is the thing this "
        "ablation exists to forbid"
    )
    assert [field.provenance.evidence_reference for field in varied_fields] == [
        field.provenance.evidence_reference for field in base_fields
    ], "renaming the source moved WHERE WITHIN the document a value was found"
    assert [field.provenance.confidence for field in varied_fields] == [
        field.provenance.confidence for field in base_fields
    ], (
        "renaming the source moved a confidence. An identifier may never change "
        "a score, measured or UNMEASURED (INV-9)."
    )


def test_the_filename_the_parser_actually_sees_differs_every_run_and_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filename dimension, measured rather than assumed.

    `pipeline._parse_document` materialises the cleaned document into a
    `NamedTemporaryFile`, so the path Docling opens is a different name on
    every single run. This wraps the REAL `parser.parse` to record the paths it
    was handed — a spy around the real call, never a stand-in for it — proves
    the two names genuinely differed, and then requires the two artifacts to
    agree everywhere except the freshly-minted Document ID.
    """
    seen: list[Path] = []
    real_parse = parser.parse

    def recording_parse(
        source: Path,
        *,
        source_reference: str,
        extracted_regions: tuple[parser.ExtractedRegion, ...] = (),
        table_structure: parser.TableStructureSettings | None = None,
    ) -> parser.ParsedStructure:
        seen.append(source)
        # `extracted_regions` is forwarded, never swallowed: this spy exists to
        # watch the FILENAME, and a spy that quietly dropped reader's regions
        # would change what the real parser produces and make this test measure
        # a pipeline nobody ships.
        return real_parse(
            source,
            source_reference=source_reference,
            extracted_regions=extracted_regions,
            table_structure=table_structure,
        )

    # Patched on the `parser` MODULE, which is the same object `pipeline`
    # holds — `pipeline.py` does `from ... import parser` and then calls
    # `parser.parse(...)`, so this reaches the real call site.
    monkeypatch.setattr(parser, "parse", recording_parse)

    first = run_pipeline(BASE_IDENTITY)
    second = run_pipeline(BASE_IDENTITY)

    assert len(seen) == TWO_RUNS, f"the real parser was called {len(seen)} times, not {TWO_RUNS}"
    assert seen[0] != seen[1], (
        f"both runs parsed the same filename {seen[0]}, so this test would pass "
        "without the filename ever having varied"
    )
    differences = differing_paths(first.model_dump(), second.model_dump())
    assert differences == MINTED_PER_RUN, (
        f"the filename {seen[0].name} -> {seen[1].name} leaked into "
        f"{sorted(differences - MINTED_PER_RUN)}"
    )


# ── the real harness, fired at the real pipeline ────────────────────────


def _without_the_minted_document_id(artifact: DocumentEvidenceObject) -> DocumentEvidenceObject:
    """The artifact with its per-run Document ID replaced by a constant.

    `ablation.ablate` compares outcomes modulo the substitution it applied, and
    it maps `ArtifactId` and `TransactionId` — not `DocumentId`, which is a
    third, distinct type minted INSIDE assembly rather than passed in. Left
    alone it would differ on every trial and the harness would report a leak
    that is really just a new artifact. Pinned to a constant here, and pinned
    as the ONLY such value by
    `test_two_identical_runs_differ_only_in_the_freshly_minted_document_id`.
    """
    return artifact.model_copy(update={"document_id": DocumentId(uuid.UUID(int=0))})


def test_the_real_ablation_harness_finds_no_leak_through_the_real_pipeline() -> None:
    """Attack 19, fired. `ablation.ablate` — the seeded, exhaustive, repeated
    harness — driving `pipeline.run` end to end, `DEFAULT_TRIALS` times.

    One substitution can agree by luck; a function branching on the first hex
    digit of an id matches itself about one time in sixteen. The harness's own
    default trial count is used rather than a number chosen here.
    """
    produced: list[DocumentEvidenceObject] = []

    def derive(identity: IdentityEnvelope) -> DocumentEvidenceObject:
        artifact = run_pipeline(identity)
        produced.append(artifact)
        return _without_the_minted_document_id(artifact)

    leaks = ablation.ablate(BASE_IDENTITY, derive, seed=SEED, trials=ablation.DEFAULT_TRIALS)
    assert leaks == [], "\n".join(str(leak) for leak in leaks)
    assert len(produced) == ablation.DEFAULT_TRIALS + 1, (
        f"the harness derived {len(produced)} outcomes, not one per trial plus the original"
    )
    for artifact in produced:
        assert artifact.structured_document.extracted_text == "\n".join(INVOICE_LINES), (
            "a trial produced an artifact that had not really been through the "
            "pipeline, so an empty pass here would prove nothing"
        )


def test_the_real_harness_catches_an_identifier_that_reaches_a_reasoned_field(
    baseline: DocumentEvidenceObject,
) -> None:
    """INVERSE CONTROL on the harness itself, through the same artifact shape.

    A derive that writes the Artifact ID into `extracted_text` — a reasoned,
    non-identifier field — is exactly the leak INV-9 forbids, and the harness
    must report it. If this passed silently, the clean result above would mean
    only that `ablate` cannot see anything at all.
    """

    def leaking_derive(identity: IdentityEnvelope) -> DocumentEvidenceObject:
        structured = StructuredDocument(
            extracted_text=str(identity.artifact_id.value),
            detected_fields=baseline.structured_document.detected_fields,
            document_structure=baseline.structured_document.document_structure,
            detected_tables=baseline.structured_document.detected_tables,
        )
        return _without_the_minted_document_id(
            baseline.model_copy(update={"structured_document": structured})
        )

    leaks = ablation.ablate(
        BASE_IDENTITY, leaking_derive, seed=SEED, trials=ablation.DEFAULT_TRIALS
    )
    assert len(leaks) == ablation.DEFAULT_TRIALS, (
        "the harness cleared a function that plainly branches on an identifier"
    )
    assert leaks[0].trial == FIRST_TRIAL
    assert "outcome changed when only identifiers changed" in str(leaks[0])


# ── inverse control on the document itself ──────────────────────────────


def test_one_changed_character_of_the_document_changes_the_output(
    baseline: DocumentEvidenceObject,
) -> None:
    """The control that stops every test above from passing vacuously.

    `INV-2026-0481` becomes `INV-2026-0482` — one character of the document's
    real text layer, nothing else. If the artifact did NOT change, the pipeline
    is not reading the document at all and no ablation comparison in this file
    is capable of failing.
    """
    varied = run_pipeline(BASE_IDENTITY, lines=ONE_CHARACTER_CHANGED)
    differences = differing_paths(baseline.model_dump(), varied.model_dump())
    assert "structured_document.extracted_text" in differences, (
        "one character of the document changed and the extracted text did not; "
        "the comparison above cannot fail and proves nothing"
    )
    assert varied.structured_document.extracted_text == "\n".join(ONE_CHARACTER_CHANGED)
    assert differences > MINTED_PER_RUN
