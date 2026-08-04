"""The Input Engine stub — P3's walking skeleton for Engine 1.

A stub is the easiest place in this repository to write a false green. It is
supposed to do nothing, so almost any test of it passes, and the one failure
mode that matters is invisible to the obvious tests: a stub that emits a
plausible reading is structurally indistinguishable at the seam from a real
Engine 1, and every number measured downstream would then be measuring
invention (`ENGINE_1_INPUT_ENGINE_RULES.md:339`).

So the tests below are written to catch fabrication rather than to confirm
emptiness. Three of them are the load-bearing ones:

  - the whole artifact is swept for strings, and the set must be exactly what
    the caller gave plus the two self-descriptions the module declares. A
    detected field named `Amount`, or a `document_structure` of
    `"header / body"`, turns it red — including one added years from now by
    someone who never read this file.
  - the emitted emptiness must be DISTINGUISHABLE from a real Engine 1's honest
    reading of a blank page, which is what forces the uncertainty marker to
    exist at all.
  - the module's import list is pinned exactly, which is how "no clock, no
    randomness, no I/O, no other engine, no Application Layer" stops being a
    promise in a docstring and becomes a check.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import ModuleType

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DocumentEvidenceObject,
    DocumentId,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.engines.input_engine import stub
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

A_SOURCE_REFERENCE = "upload:invoice-481.pdf"
ANOTHER_SOURCE_REFERENCE = "email:po-77.eml"

THE_USER_WROTE = "Bought laptops for the design team."

WHEN = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)

#: Capture fidelity, not truth (`ENGINE_1_INPUT_ENGINE_RULES.md:283`) — the
#: system stored exactly what was typed. It says nothing about the statement.
CAPTURED_EXACTLY = Decimal("1.0000")

#: Fixed rather than generated, so the determinism test compares two artifacts
#: that differ in nothing at all. `DocumentId.new()` would put fresh entropy on
#: both sides and make the comparison meaningless.
A_DOCUMENT_ID = DocumentId(uuid.UUID("8f14e45f-ceea-4c2b-9e6f-1b2f3c4d5e6f"))
AN_IDENTITY = IdentityEnvelope(
    artifact_id=ArtifactId(uuid.UUID("3d2b1a0c-9e8f-4a7b-8c6d-5e4f3a2b1c0d")),
    version=1,
    parent_versions=(),
    transaction_id=TransactionId(uuid.UUID("1c2d3e4f-5a6b-4c8d-9e0f-1a2b3c4d5e6f")),
)


# ── builders and helpers ─────────────────────────────────────────────────────


def an_identity() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def a_human_note(text: str = THE_USER_WROTE) -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat message",
            evidence_reference="message 1",
            timestamp=WHEN,
            confidence=CAPTURED_EXACTLY,
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


def a_stub_reading(
    *,
    source_references: tuple[str, ...] = (A_SOURCE_REFERENCE,),
    human_business_context: HumanBusinessContext | None = None,
) -> DocumentEvidenceObject:
    return stub.read(
        identity=an_identity(),
        document_id=DocumentId.new(),
        source_references=source_references,
        human_business_context=human_business_context,
    )


def strings_inside(value: object) -> set[str]:
    """Every string anywhere inside a dumped artifact, dict KEYS excluded.

    Keys are field names chosen by the schema, not content emitted by the stub,
    and including them would drown the signal this helper exists to carry.
    """
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            found |= strings_inside(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= strings_inside(item)
    return found


def modules_imported_by(module: ModuleType) -> set[str]:
    """Every module name `module` imports, read off its source rather than run.

    A relative import is spelled with its dots (`from ..brain import stub`
    becomes `..brain`) instead of being resolved, so it cannot slip past an
    allowlist of absolute names by being written the other way round.
    """
    source = pathlib.Path(str(module.__file__)).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * node.level + (node.module or ""))
    return imported


# ── it emits the artifact, carrying only what it was given ───────────────────


def test_every_value_the_stub_emits_is_one_it_was_given() -> None:
    # BLUEPRINT:136 — P3 is done when "all artifacts valid". Constructing the
    # artifact is the validation: it is a frozen pydantic model that refuses
    # anything malformed at creation.
    identity = an_identity()
    document_id = DocumentId.new()

    evidence = stub.read(
        identity=identity,
        document_id=document_id,
        source_references=(A_SOURCE_REFERENCE, ANOTHER_SOURCE_REFERENCE),
    )

    assert isinstance(evidence, DocumentEvidenceObject)
    assert evidence.identity == identity
    assert evidence.document_id == document_id
    # Order preserved, nothing appended, nothing normalised.
    assert evidence.source_references == (A_SOURCE_REFERENCE, ANOTHER_SOURCE_REFERENCE)


def test_the_artifact_holds_no_string_the_stub_was_not_given_or_did_not_declare() -> None:
    """The anti-fabrication sweep. This is the test that has to survive.

    Every other test here asserts a field the author thought to check. This one
    asserts the complement: that no OTHER string exists anywhere in the
    artifact. A detected field named `Amount`, a `document_structure` of
    `"invoice header"`, a reliability sentence about the vendor — each of them
    adds a member to this set and turns it red, whether or not anyone remembered
    to write a test for it (`ENGINE_1_INPUT_ENGINE_RULES.md:337`).
    """
    given = (A_SOURCE_REFERENCE, ANOTHER_SOURCE_REFERENCE)

    emitted = strings_inside(a_stub_reading(source_references=given).model_dump())

    assert emitted == {
        *given,
        # `extracted_text` and `document_structure`, both deliberately empty.
        "",
        stub.NOTHING_WAS_READ.subject,
        stub.NOTHING_WAS_READ.reason,
        stub.NO_READING_HAPPENED.reliability_information,
    }


# ── it reads nothing, and fabricates nothing to cover for that ───────────────


def test_not_one_detected_field_is_emitted_not_even_an_unreadable_one() -> None:
    """The design rule, in one assertion.

    `DetectedField(name=..., value=None)` is legal and means UNREADABLE
    (`ENGINE_1_INPUT_ENGINE_RULES.md:569`), which makes it the tempting choice —
    it looks like the humblest possible output. It is not: the NAME is itself
    something read off the document, so the humble-looking version invents the
    claim that the field exists. `:565` — *"Unknown fields remain unknown."*
    """
    document = a_stub_reading().structured_document

    assert document.detected_fields == ()
    assert document.detected_tables == ()
    assert document.extracted_text == ""
    assert document.document_structure == ""


def test_no_confidence_score_and_no_risky_field_is_invented() -> None:
    # ENGINE_1:109 — only the `confidence` sub-engine turns signals into scores,
    # and no such sub-engine exists at P3. A score emitted here would have no
    # author, which is the failure INV-2 and INV-10 both name.
    report = a_stub_reading().confidence_report

    assert report.confidence_scores == ()
    assert report.risky_fields == ()


def test_an_empty_reading_is_never_a_silent_one() -> None:
    """Why the marker exists at all — and it is not decoration.

    The counterexample is built here on purpose: an artifact identical in every
    other respect, whose emptiness carries no explanation. That artifact is a
    perfectly honest reading of a blank page by a real Engine 1, and if the stub
    produced the same thing, nothing downstream could tell which one it got.
    `BLUEPRINT:136` forbids an accuracy claim at P3 precisely because that
    distinction has to survive.
    """
    report = a_stub_reading().confidence_report

    assert len(report.uncertainty_markers) == 1
    assert report.uncertainty_markers[0].reason  # `:626` — never a bare score

    a_blank_page_read_honestly = ConfidenceReport(
        confidence_scores=(),
        uncertainty_markers=(),
        reliability_information=report.reliability_information,
        risky_fields=(),
    )
    assert report != a_blank_page_read_honestly


# ── the human note: optional, verbatim, never merged, never a confidence boost ─


def test_a_human_note_is_absent_unless_the_caller_supplies_one() -> None:
    # ENGINE_1:138 — the description is OPTIONAL and the system must work
    # correctly when none is provided. Its absence is not a gap to be filled,
    # so there is deliberately nothing to fill it with.
    assert a_stub_reading().human_business_context is None


def test_a_supplied_human_note_is_carried_verbatim_and_never_becomes_a_reading() -> None:
    # ENGINE_1:233 — "Engine 1 never merges the two into a single fact." A note
    # filed among the detected fields IS that merge: it would enter the half of
    # the artifact labelled EXTRACTED wearing the authority of something read
    # off the document, and nothing downstream could tell (:341).
    note = a_human_note()

    evidence = a_stub_reading(human_business_context=note)

    assert evidence.human_business_context is not None
    assert evidence.human_business_context == note
    # `:331` and `:333` — stored verbatim, not tidied, summarised or normalised.
    assert evidence.human_business_context.original_user_text == THE_USER_WROTE
    # And not one character of it reached the extracted half.
    assert THE_USER_WROTE not in strings_inside(evidence.structured_document.model_dump())
    assert evidence.structured_document.detected_fields == ()


def test_a_human_note_changes_nothing_else_about_the_artifact() -> None:
    # ENGINE_1:289 — "A human note must never increase Evidence Reliability
    # simply because it exists." :330 forbids raising confidence "because the
    # user wrote something". The two reports must be equal, not merely close.
    without = a_stub_reading()
    with_note = a_stub_reading(human_business_context=a_human_note())

    assert with_note.confidence_report == without.confidence_report
    assert with_note.structured_document == without.structured_document


# ── it invents no origin, and papers over no refusal ─────────────────────────


def test_no_source_reference_is_invented_when_the_caller_names_none() -> None:
    # The cheap fix is a placeholder — `("stub",)`, `("unknown",)` — so the
    # artifact always builds. That is a fabricated origin (:337) and it would
    # make an untraceable artifact look traceable. Refusing is correct.
    with pytest.raises(ValidationError, match="at least one source reference"):
        a_stub_reading(source_references=())


def test_a_blank_source_reference_is_refused_rather_than_quietly_dropped() -> None:
    """MADE STRICTER after a mutation survived it. The weaker version is a trap.

    It read `source_references=("",)` and asserted only that SOME
    `ValidationError` was raised. A stub that silently stripped blanks —
    `tuple(r for r in source_references if r)` — passed it, because the strip
    emptied the tuple and the artifact then refused for having no reference at
    all. The test was green and the prohibition it names was unenforced: exactly
    the false green §J exists to prevent.

    Two changes, both narrowing. A valid reference sits beside the blank, so
    stripping would leave a buildable artifact instead of an empty one; and the
    refusal is now attributed to the blank by name (`string_too_short`) rather
    than accepted from anywhere. An empty origin is a claim of traceability the
    artifact does not have, which INV-11 treats as worse than admitting none.
    """
    with pytest.raises(ValidationError, match="string_too_short"):
        a_stub_reading(source_references=(A_SOURCE_REFERENCE, ""))


def test_a_duplicated_source_reference_is_refused_rather_than_de_duplicated() -> None:
    # Silently de-duplicating would be the stub tidying its caller's input, and
    # tidying is a transformation this module has no authority to perform.
    with pytest.raises(ValidationError, match="listed twice"):
        a_stub_reading(source_references=(A_SOURCE_REFERENCE, A_SOURCE_REFERENCE))


# ── it is a pure function, and it branches on nothing ────────────────────────


def test_two_calls_with_the_same_arguments_produce_the_same_artifact() -> None:
    """No clock, no randomness, no I/O — so P3's CI run is reproducible.

    This is the property the Document ID argument exists to protect. A stub that
    minted its own `uuid4` would fail here, and P3 would be proving a pipeline
    whose output nobody could reproduce.
    """
    arguments = {
        "identity": AN_IDENTITY,
        "document_id": A_DOCUMENT_ID,
        "source_references": (A_SOURCE_REFERENCE,),
    }

    assert stub.read(**arguments) == stub.read(**arguments)  # type: ignore[arg-type]


def test_the_stub_does_not_branch_on_anything_it_is_given() -> None:
    """`brain/stub.py` names its ignored parameter `_question` for this reason.

    A stub that varied its emptiness would have behaviour to get wrong, and a
    test asserting "it returns nothing" would start passing for the wrong reason
    the moment someone taught it one special case. Two calls sharing no argument
    values must still emit the same two components.
    """
    one = a_stub_reading(source_references=(A_SOURCE_REFERENCE,))
    other = a_stub_reading(
        source_references=(ANOTHER_SOURCE_REFERENCE, "metadata:upload-headers"),
        human_business_context=a_human_note("Advance payment to supplier."),
    )

    assert one.structured_document == other.structured_document
    assert one.confidence_report == other.confidence_report


def test_the_seam_takes_only_the_four_values_the_caller_already_holds() -> None:
    """Pins the shape of the seam, including what is deliberately missing.

    There is no parameter for the raw artifact. `DATA_FLOW.md:36` names one at
    row 0, *external* → Input, but no schema for it exists and writing a seventh
    artifact here would be an architecture change made in code. A parameter
    added later — a document, a file path, a transaction state — turns this red
    and gets read by a human before it ships.
    """
    parameters = inspect.signature(stub.read).parameters

    assert list(parameters) == [
        "identity",
        "document_id",
        "source_references",
        "human_business_context",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values()
    )


# ── the boundaries, checked rather than promised ─────────────────────────────


def test_the_stub_imports_nothing_that_could_read_branch_or_vary() -> None:
    """AL-INV-4 and AL-INV-5, enforced on this file instead of remembered.

    `APPLICATION_LAYER_INVARIANTS.md:63` — *"Every artifact passes through the
    Application Layer"*, and `:69` names the check: *"no engine module imports
    another engine."* `:51` — *"No engine may read, write, observe or infer
    transaction state"*, checked by *"no engine module imports the state store"*
    (`accountant_dad.services`).

    Asserted as an EXACT set rather than as an absence, which buys three more
    guarantees for free. `random`, `secrets` and `uuid` cannot appear, so the
    module cannot mint an identifier. `datetime` and `time` cannot appear, so it
    has no clock. `pathlib`, `io`, `socket` and `httpx` cannot appear, so it
    reads nothing and calls nobody. Each of those would otherwise rest on a
    sentence in a docstring.
    """
    assert modules_imported_by(stub) == {
        "__future__",
        "accountant_dad.artifacts.evidence",
        "accountant_dad.identity",
    }
