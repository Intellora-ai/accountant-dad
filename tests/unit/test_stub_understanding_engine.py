"""The Understanding Engine stub, attacked.

The stub's one job is to be **structurally valid while fabricating nothing**, so
every test here is written to catch it doing the second thing (§J.1, §J.3). The
failure this file is built to trap is not a crash — a stub that quietly invented
a party, copied a field, or emitted a plausible confidence would pass a naive
suite, look alive in CI, and make every downstream P4 number a measurement of
invention (`CLAUDE.md` Law 24, `ENGINE_2:878`).

Four tests are the load-bearing ones, and each fails for a *different* wrong
implementation:

  · `test_the_batch_content_is_invisible_to_the_output` goes red the moment the
    stub reads one field off a document.
  · `test_the_transaction_id_is_copied_and_not_hardcoded` goes red if identity
    is minted or fixed instead of carried.
  · `test_every_confidence_is_exactly_the_floor` goes red on any "plausible"
    score, and `test_a_score_above_the_floor_is_refused` shows why the floor is
    the only value available rather than a stylistic choice.
  · `test_the_module_imports_nothing_stateful_and_no_other_component` reads this
    module's own import list off disk, so a clock, a random source, an engine
    import (AL-INV-5) or an Application Layer import (AL-INV-4) fails the build
    rather than being noticed at review.
"""

from __future__ import annotations

import ast
import pathlib
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DocumentEvidenceObject,
    DocumentId,
    FieldConfidence,
    Provenance,
    SourceType,
    StructuredDocument,
)
from accountant_dad.artifacts.understanding import (
    FORBIDDEN_PLURALS,
    FORBIDDEN_VOCABULARY,
    BusinessContextResult,
    BusinessUnderstandingObject,
    ConfidenceAssessment,
    ItemUnderstandingResult,
    PartyUnderstandingResult,
    PaymentUnderstandingResult,
    TimelineUnderstandingResult,
    TransactionUnderstandingResult,
)
from accountant_dad.confidence import MIN
from accountant_dad.engines.understanding_engine import stub
from accountant_dad.identity import FIRST_VERSION, ArtifactId, IdentityEnvelope, TransactionId

#: `ENGINE_2:348` — Story Builder *"Receives all six Results."* One gap each here.
SIX = 6
ONE = 1

#: Every term the artifact's own vocabulary rule bans, plus its plural form.
_BANNED = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in (*FORBIDDEN_VOCABULARY, *FORBIDDEN_PLURALS)) + r")\b",
    re.IGNORECASE,
)

# ── builders ──────────────────────────────────────────────────────────────
# Minimal on purpose. A builder that fills in a default is a builder that can
# hide the omission a test was written to catch.


def provenance(confidence: str) -> Provenance:
    return Provenance(
        source_type=SourceType.DOCUMENT,
        source_id="scan-1",
        evidence_reference="page-1#line-2",
        timestamp=datetime(2026, 8, 4, 9, 30, tzinfo=UTC),
        confidence=Decimal(confidence),
        corroborated=Corroborated.NOT_ASSESSED,
    )


def document(
    transaction: TransactionId,
    *,
    text: str = "",
    field_name: str | None = None,
    confidence: str = "0.9900",
    reference: str = "upload-1",
) -> DocumentEvidenceObject:
    """One Document Evidence Object on the given transaction, as rich or as bare as asked."""
    fields: tuple[DetectedField, ...] = ()
    scores: tuple[FieldConfidence, ...] = ()
    if field_name is not None:
        value = f"{field_name} reads 19,800.00"
        fields = (DetectedField(name=field_name, value=value, provenance=provenance(confidence)),)
        scores = (FieldConfidence(field_name=field_name, confidence=Decimal(confidence)),)
    return DocumentEvidenceObject(
        identity=IdentityEnvelope(
            artifact_id=ArtifactId.new(),
            version=FIRST_VERSION,
            parent_versions=(),
            transaction_id=transaction,
        ),
        document_id=DocumentId.new(),
        source_references=(reference,),
        structured_document=StructuredDocument(
            extracted_text=text,
            detected_fields=fields,
            document_structure="",
            detected_tables=(),
        ),
        confidence_report=ConfidenceReport(
            confidence_scores=scores,
            uncertainty_markers=(),
            reliability_information="",
            risky_fields=(),
        ),
    )


def understood(
    evidence: tuple[DocumentEvidenceObject, ...] | None = None,
    artifact_id: ArtifactId | None = None,
) -> BusinessUnderstandingObject:
    batch = (document(TransactionId.new()),) if evidence is None else evidence
    return stub.StubUnderstandingEngine().understand(batch, artifact_id or ArtifactId.new())


def authored_strings(artifact: BusinessUnderstandingObject) -> list[str]:
    """Every string this engine composed itself. Nothing here was quoted off a document."""
    written = [artifact.transaction_story.narrative]
    for gap in artifact.identified_unknowns:
        written.extend((gap.subject, gap.why_it_matters))
    return written


# ── what it emits ─────────────────────────────────────────────────────────


def test_it_emits_a_valid_artifact_carrying_the_transaction_id_it_was_given() -> None:
    transaction = TransactionId.new()
    artifact_id = ArtifactId.new()

    artifact = understood((document(transaction),), artifact_id)

    assert isinstance(artifact, BusinessUnderstandingObject)
    assert artifact.transaction_id == transaction
    assert artifact.understanding_id == artifact_id
    assert artifact.transaction_story.narrative == stub.NARRATIVE


def test_the_transaction_id_is_copied_and_not_hardcoded() -> None:
    """A stub with a fixed Transaction ID passes any single-value assertion.

    `MVP_IMPLEMENTATION_BLUEPRINT.md:136` requires the Transaction ID intact
    through P3, and INV-4 forbids an engine creating one. Two batches on two
    transactions must therefore produce two different answers.
    """
    first, second = TransactionId.new(), TransactionId.new()

    assert understood((document(first),)).transaction_id == first
    assert understood((document(second),)).transaction_id == second


def test_the_origin_version_records_no_parent() -> None:
    """`identity.py` refuses parents on version 1, and this stub emits originals only."""
    artifact = understood()

    assert artifact.identity.version == FIRST_VERSION
    assert artifact.identity.parent_versions == ()


# ── what it must never emit ───────────────────────────────────────────────


def test_it_states_no_fact_cites_no_evidence_and_reports_no_conflict() -> None:
    """The central anti-fabrication assertion. One invented fact anywhere fails this.

    `ENGINE_2:878` — the engine fails when *"a fact is invented to complete the
    story."* A stub cannot comprehend, so any fact it stated would be invented,
    and any evidence reference would be a citation it never read.
    """
    artifact = understood()

    for result in artifact.supporting_understanding_data.results:
        assert result.facts == (), f"{type(result).__name__} states a fact it cannot have observed"
        assert result.evidence_references == ()
        assert result.conflicts_detected == ()

    assert artifact.detected_conflicts == ()


def test_each_of_the_six_results_names_exactly_one_distinct_gap() -> None:
    """Six gaps, not five. Two identical `Unknown`s collapse in the artifact's own
    `set()` check and would silently reduce what the Clarification Engine can ask."""
    results = understood().supporting_understanding_data.results

    assert len(results) == SIX
    for result in results:
        assert len(result.unknowns) == ONE
        assert result.unknowns[0].subject.strip()
        assert result.unknowns[0].why_it_matters.strip()

    subjects = [result.unknowns[0].subject for result in results]
    assert len(set(subjects)) == SIX, f"two Results name the same gap: {subjects}"


def test_every_gap_the_results_raise_reaches_identified_unknowns() -> None:
    """`ENGINE_2:645` — *"Unknowns are carried into Identified Unknowns intact."*"""
    artifact = understood()
    raised = artifact.supporting_understanding_data.all_unknowns

    assert len(artifact.identified_unknowns) == SIX
    # Equality, not the superset the schema tolerates: a stub has nothing to add
    # beyond what the Results raised, so an extra entry would be an invented gap.
    assert set(raised) == set(artifact.identified_unknowns)
    assert artifact.missing_information == artifact.identified_unknowns


def test_every_confidence_is_exactly_the_floor() -> None:
    """Not "low" — the exact `confidence.MIN`. A stub with nothing behind it that
    emitted 0.5 would be asserting a degree of support it has no basis for
    (`ENGINE_2:773`)."""
    artifact = understood()

    assert stub.CONFIDENCE_FLOOR == MIN
    assert artifact.confidence_assessment.evidence_confidence == MIN
    assert artifact.confidence_assessment.understanding_confidence == MIN
    for result in artifact.supporting_understanding_data.results:
        assert result.confidence == MIN, f"{type(result).__name__} claims support it does not have"


def test_a_score_above_the_floor_is_refused() -> None:
    """The floor is load-bearing, not decoration.

    Break it on purpose (§J.5): rebuild the same artifact with a plausible-looking
    confidence and the schema refuses it, because Story Builder cannot be more
    certain than its least certain input (`ENGINE_2:638` with INV-2). A stub that
    wanted to look alive could not, and this is the proof rather than the claim.
    """
    artifact = understood()

    with pytest.raises(ValidationError, match="exceeds the lowest Result confidence"):
        BusinessUnderstandingObject(
            identity=artifact.identity,
            transaction_story=artifact.transaction_story,
            supporting_understanding_data=artifact.supporting_understanding_data,
            identified_unknowns=artifact.identified_unknowns,
            confidence_assessment=ConfidenceAssessment(
                evidence_confidence=Decimal("0.9000"),
                understanding_confidence=Decimal("0.9000"),
            ),
        )


def test_no_string_this_engine_authored_carries_accounting_vocabulary() -> None:
    """`ENGINE_2:641`, `:852`. Not redundant with `AuthoredText`.

    The schema checks the fields that are typed `AuthoredText` today. This asserts
    the property of the *output*, so it stays red if a later edit files an engine
    sentence under `StatedText` — which is never checked and never trimmed,
    because it is supposed to be a quotation off a document.
    """
    for written in authored_strings(understood()):
        found = sorted({m.group(0).lower() for m in _BANNED.finditer(written)})
        assert found == [], f"accounting vocabulary authored by Engine 2: {found} in {written!r}"


# ── what it must not read ─────────────────────────────────────────────────


def test_the_batch_content_is_invisible_to_the_output() -> None:
    """The strongest test here: teach the stub to read one field and it goes red.

    One bare document, and a batch of three rich ones on the same Transaction ID
    (`ENGINE_2:157` — many documents, one business event), differing in extracted
    text, detected fields, field confidences and source references. Same
    Transaction ID and same Artifact ID in, so an engine that reads nothing but
    identity must return two **equal** artifacts.
    """
    transaction = TransactionId.new()
    artifact_id = ArtifactId.new()

    bare = understood((document(transaction),), artifact_id)
    rich = understood(
        (
            document(transaction, text="TAX INVOICE 19,800.00", field_name="Amount"),
            document(transaction, field_name="Vendor", reference="e-1"),
            document(transaction, text="delivery note", field_name="Date", confidence="0.4000"),
        ),
        artifact_id,
    )

    assert bare == rich


def test_two_calls_with_the_same_arguments_return_equal_artifacts() -> None:
    """No clock, no randomness, no accumulated state. `understand` is a pure function.

    Two calls on two instances, so the property survives the Application Layer
    holding one engine object for a whole run.
    """
    transaction = TransactionId.new()
    artifact_id = ArtifactId.new()
    batch = (document(transaction, field_name="Amount"),)

    first = stub.StubUnderstandingEngine().understand(batch, artifact_id)
    second = stub.StubUnderstandingEngine().understand(batch, artifact_id)

    assert first == second


# ── what it refuses ───────────────────────────────────────────────────────


def test_an_empty_batch_is_refused_rather_than_answered() -> None:
    """No batch means no Transaction ID, so the artifact could exist only by
    inventing the identity it belongs to. Fail loudly (Law 11)."""
    with pytest.raises(stub.EvidenceBatchRejectedError, match="no Document Evidence Object"):
        stub.StubUnderstandingEngine().understand((), ArtifactId.new())


def test_a_batch_spanning_two_transactions_is_refused_rather_than_resolved() -> None:
    """`ENGINE_2:673` — *"Never silently choose one answer."*

    Picking either Transaction ID would attach this artifact to one business event
    and drop the other, invisibly. The engine has no basis to choose and says so.
    """
    batch = (document(TransactionId.new()), document(TransactionId.new()))

    with pytest.raises(stub.EvidenceBatchRejectedError, match="2 Transaction IDs in one batch"):
        stub.StubUnderstandingEngine().understand(batch, ArtifactId.new())


def test_the_six_results_are_the_six_named_types() -> None:
    """`ENGINE_2:307-309` — do not add, remove or merge sub-engines. A seventh
    Result, or one Result standing in for another, is an architecture change."""
    supporting = understood().supporting_understanding_data

    assert isinstance(supporting.transaction, TransactionUnderstandingResult)
    assert isinstance(supporting.party, PartyUnderstandingResult)
    assert isinstance(supporting.item, ItemUnderstandingResult)
    assert isinstance(supporting.payment, PaymentUnderstandingResult)
    assert isinstance(supporting.timeline, TimelineUnderstandingResult)
    assert isinstance(supporting.business_context, BusinessContextResult)


# ── what it may not depend on ─────────────────────────────────────────────


def imported_modules() -> set[str]:
    """Every module `stub.py` imports, read off the file rather than the process."""
    source = pathlib.Path(str(stub.__file__)).read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_the_module_imports_nothing_stateful_and_no_other_component() -> None:
    """Four invariants at once, enforced structurally instead of remembered.

    AL-INV-5 — engines never call each other. AL-INV-4 — no engine may read,
    write, observe or infer transaction state, so `accountant_dad.services` is
    unreachable from here. And the P3 stub rules: no dependency, no AI, no I/O,
    no clock, no randomness — every one of which would arrive as an import.

    An exact set, not a substring scan. A substring scan permits a new import
    nobody looked at; this makes every addition a visible, reviewable edit.
    """
    imported = imported_modules()

    assert {name for name in imported if not name.startswith("accountant_dad")} == {
        "__future__",
        "decimal",
    }, "a stub that reads a clock, a random source or a file is not a stub"

    assert {name for name in imported if name.startswith("accountant_dad")} == {
        "accountant_dad.artifacts.evidence",
        "accountant_dad.artifacts.understanding",
        "accountant_dad.confidence",
        "accountant_dad.identity",
    }, (
        "an engine imports artifact schemas only — never another engine (AL-INV-5) "
        "and never the Application Layer (AL-INV-4)"
    )
