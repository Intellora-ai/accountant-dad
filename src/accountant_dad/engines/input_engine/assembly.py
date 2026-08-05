"""assembly — the Input Engine's own combination of its four sub-engines' outputs.

`SUB_ENGINE_RESPONSIBILITIES.md`, the boxed note above §1.1, is the whole
mandate for this file, verbatim:

    Engine-level assembly. The four sub-engines below produce four parts. The
    Input Engine itself combines them into the Document Evidence Object and
    assigns the Document ID. It owns the internal assembly of its own
    sub-engines' outputs and nothing more — not system-wide orchestration,
    engine routing, downstream reasoning, accounting decisions, workflow
    control, or overriding sub-engine outputs. No assembler sub-engine
    exists, and none may be added.

So this module is not a fifth sub-engine. It is the ENGINE's own boundary
step — the box labelled "Input Engine" in the assembly diagram at
`ENGINE_1_INPUT_ENGINE_RULES.md:372-382`, sitting between the four sub-engines
and the one artifact the engine ever emits.

WHAT "COMBINE" MEANS HERE, AND ONLY HERE.
    `ENGINE_1:105` — "The parent assembles what its sub-engines produced; it
    does not correct, second-guess, or improve any of it." Concretely, this
    module:
      - packages `parser`'s structural output and `reader`'s raw text into
        the `StructuredDocument` component,
      - packages `confidence`'s output into the `ConfidenceReport` component,
      - mints the Document ID (`ENGINE_1:95,253` — assigned "by the Input
        Engine at intake"),
      - and hands the caller-supplied identity envelope, source references
        and optional Human Business Context straight through, unread.
    Nothing here performs arithmetic on a confidence value, resolves a
    disagreement, drops an unknown, or writes a fact no sub-engine produced.
    Where two sub-engine outputs would disagree, `DocumentEvidenceObject`'s
    own validators (`accountant_dad.artifacts.evidence`) are what refuse the
    artifact — this module never reconciles a disagreement itself, because
    that would BE the resolution `ENGINE_1:113` forbids ("no sub-engine
    overrides another").

THE FOUR INPUT CONTRACTS, AND WHY THEY ARE DEFINED HERE RATHER THAN IMPORTED.
    `cleaner`, `reader`, `parser` and `confidence` are being built in
    parallel elsewhere. Importing their real types would couple this module
    to implementations that do not exist yet and may change shape before
    they land. Instead, the four dataclasses below are shaped against the
    DOCUMENTED output contracts only — `SUB_ENGINE_RESPONSIBILITIES.md`
    §1.1-1.4 and `ENGINE_1_INPUT_ENGINE_RULES.md` §8.1-8.4 — never against
    any sub-engine's real implementation. A mismatch, once the real modules
    land, is cheap to find and fix here; a hidden coupling would not have
    been.

    `ParserOutput` and `ConfidenceOutput` are shaped as near-direct feeds
    into `StructuredDocument` and `ConfidenceReport` respectively, because
    both specifications use the same words for their own output: "Together
    these form the Structured Document" (§1.3) and "Together these form the
    Confidence Report" (§1.4). `ReaderOutput` contributes the one field
    `StructuredDocument` needs that `parser`'s contract does not produce —
    "raw extracted information (text...)" (§1.2) becomes `extracted_text`.

    `CleanerOutput`'s fields, and the remainder of `ReaderOutput`'s, have no
    destination slot in `DocumentEvidenceObject` at all: `confidence`
    "Receives: cleaner output, reader output, parser output" (§8.4), so by
    the time `confidence`'s own output reaches this module, cleaner's
    quality signal and reader's raw locations and extraction-confidence
    signal are already reflected in `confidence`'s Reliability Assessment.
    Carrying them here anyway, and REQUIRING them to be present, keeps this
    module able to prove that all four sub-engines actually ran — the "one
    part missing" failure mode below — without re-deriving content only
    `confidence` is authorised to produce (`ENGINE_1:109`).

A GAP THIS MODULE FOUND AND DID NOT FIX. `parser`'s documented output
    includes "missing field information" (§1.3), and `ENGINE_1:568` requires
    "absent", "zero" and "unreadable" to stay three distinguishable states.
    `accountant_dad.artifacts.evidence.StructuredDocument` — the frozen
    schema this module must conform to (Law 19) — has no field for it; an
    absent field is representable only by its absence from `detected_fields`.
    Adding one would be an unapproved change to a locked artifact schema
    (`CLAUDE.md` §O), which is outside this file's remit. Reported here, not
    silently worked around.

    A second tension, also reported rather than resolved: every
    `DetectedField.provenance` requires a `Confidence` value (INV-11 — no
    optional field), yet `ENGINE_1:109` gives only `confidence` the
    authority to set one. `ParserOutput.detected_fields` is assumed to
    already carry complete, valid `DetectedField` objects — how `parser` and
    `confidence` agree on that value between themselves is not modelled by
    any document this module answers to, so it is not modelled here either.
    This module performs no reconciliation of its own: it hands both pieces
    to `DocumentEvidenceObject`, whose own validator refuses the artifact if
    a field's provenance confidence ever disagrees with the matching score
    in the Confidence Report.

DOCUMENT ID. Minted here via `DocumentId.new()`, restoring what
    `engines/input_engine/stub.py` deliberately deferred — its own
    docstring: "the real Engine 1 assigns it at intake, and P4 must restore
    that." A caller cannot inject one, so two calls to `assemble()` on
    identical sub-engine output mint two different Document IDs while
    producing identical content everywhere else — INV-9, "Document ID...
    carries no accounting meaning", so which call minted it changes no
    reasoning anywhere downstream.

FAILURE BEHAVIOUR. If any of the four parts is absent, `assemble()` raises
    `MissingSubEngineOutputError` naming exactly which one, carrying the
    `SubEngineOutputs` it was given — including whichever of the other three
    DID arrive — so nothing already produced is thrown away. Nothing is
    filled in by guess (`ENGINE_1:337`, the invention prohibition) and no
    partial `DocumentEvidenceObject` is ever returned.
"""

from __future__ import annotations

from dataclasses import dataclass

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    DetectedField,
    DetectedTable,
    DocumentEvidenceObject,
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.identity import IdentityEnvelope


@dataclass(frozen=True, slots=True)
class CleanerOutput:
    """`SUB_ENGINE_RESPONSIBILITIES.md` §1.1's three outputs, verbatim:
    cleaned document representation · quality issues detected · preservation
    status.

    Required as an input so `assemble()` can prove `cleaner` ran at all — see
    the module docstring's "THE FOUR INPUT CONTRACTS" section for why its
    content has no destination field of its own in `DocumentEvidenceObject`.
    """

    #: Opaque here. Assembly never reads pixels; only `cleaner` and `reader` do.
    cleaned_document_representation: object
    quality_issues_detected: tuple[str, ...]
    preservation_status: str


@dataclass(frozen=True, slots=True)
class ReaderOutput:
    """§1.2's three outputs: raw extracted information · source locations ·
    extraction confidence.

    Only `raw_extracted_text` is consumed here, becoming
    `StructuredDocument.extracted_text` unchanged — the one field
    `parser`'s own contract does not produce. The other two are required for
    presence only; see the module docstring.
    """

    raw_extracted_text: str
    source_locations: tuple[str, ...]
    extraction_confidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParserOutput:
    """§1.3's output, shaped as the fields its own contract says "together
    ... form the Structured Document, a component of the Document Evidence
    Object" (`SUB_ENGINE_RESPONSIBILITIES.md:70`).

    `detected_fields` and `detected_tables` are assumed to already be
    `accountant_dad.artifacts.evidence.DetectedField` / `DetectedTable`
    objects, each carrying its own complete `Provenance` (INV-11). See the
    module docstring's "A GAP THIS MODULE FOUND AND DID NOT FIX" section for
    the confidence-authority tension this assumption carries, and for why
    "missing field information" is not modelled here.
    """

    document_structure: str
    detected_fields: tuple[DetectedField, ...]
    detected_tables: tuple[DetectedTable, ...]


@dataclass(frozen=True, slots=True)
class ConfidenceOutput:
    """§1.4's output, shaped as the fields its own contract says "together
    ... form the Confidence Report, a component of the Document Evidence
    Object" (`SUB_ENGINE_RESPONSIBILITIES.md:86`).
    """

    confidence_scores: tuple[FieldConfidence, ...]
    uncertainty_markers: tuple[UncertaintyMarker, ...]
    reliability_information: str
    risky_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubEngineOutputs:
    """The four parts named in the assembly diagram
    (`ENGINE_1_INPUT_ENGINE_RULES.md:372-382`) — one field per sub-engine,
    and no fifth field: "No new assembler sub-engine is created" (`:384`).

    Each may be `None`, meaning that sub-engine produced nothing to combine.
    `assemble()` refuses to guess a missing part; see
    `MissingSubEngineOutputError`.
    """

    cleaner: CleanerOutput | None
    reader: ReaderOutput | None
    parser: ParserOutput | None
    confidence: ConfidenceOutput | None


class MissingSubEngineOutputError(RuntimeError):
    """Raised when `cleaner`, `reader`, `parser` or `confidence` is missing.

    Names exactly which one. Carries the `SubEngineOutputs` it was given on
    the `parts` attribute — including whichever of the other three DID
    arrive — so a caller can inspect exactly what survived and where to
    restart, rather than losing it along with the failed attempt
    (`ENGINE_1_INPUT_ENGINE_RULES.md:337`, the invention prohibition:
    nothing is filled in by guess, and nothing already produced is thrown
    away either).
    """

    def __init__(self, missing_part: str, parts: SubEngineOutputs) -> None:
        self.missing_part = missing_part
        self.parts = parts
        super().__init__(
            f"Engine 1 assembly cannot build a Document Evidence Object: the "
            f"{missing_part!r} sub-engine produced no output. The other parts "
            "supplied are preserved on this exception's `parts` attribute; "
            "none of them was discarded and nothing was invented to stand in "
            "for the missing one."
        )


def assemble(
    *,
    parts: SubEngineOutputs,
    identity: IdentityEnvelope,
    source_references: tuple[str, ...],
    human_business_context: HumanBusinessContext | None = None,
) -> DocumentEvidenceObject:
    """Combine the four sub-engine outputs into one Document Evidence Object.

    Mechanical only, per the boxed note this module exists to satisfy: it
    packages `parser` and `reader` into the `StructuredDocument`, packages
    `confidence` into the `ConfidenceReport`, mints a fresh `DocumentId`, and
    passes `identity`, `source_references` and `human_business_context`
    through unread. It never changes a value, never resolves a disagreement
    between two sub-engines, never removes an unknown, and never raises or
    lowers a confidence score — `DocumentEvidenceObject`'s own validators are
    what refuse an artifact where two sub-engines disagree.

    Raises `MissingSubEngineOutputError` naming the first absent part, in
    the fixed order cleaner, reader, parser, confidence, if `parts` is
    incomplete. Raises `pydantic.ValidationError` if the resulting artifact
    itself is invalid — for instance, no source reference, or a confidence
    score that disagrees with a field's own provenance — because that
    decision belongs to `DocumentEvidenceObject`'s own schema (Law 19: one
    source of truth), not to a second check duplicated here.

    `identity`, `source_references` and `human_business_context` are the
    caller's, exactly as `engines/input_engine/stub.py` already takes them —
    this module supplies only what §1.1-1.4 puts in the ENGINE's own hands:
    the combination itself, and the Document ID.
    """
    cleaner = parts.cleaner
    if cleaner is None:
        raise MissingSubEngineOutputError("cleaner", parts)
    reader = parts.reader
    if reader is None:
        raise MissingSubEngineOutputError("reader", parts)
    parser = parts.parser
    if parser is None:
        raise MissingSubEngineOutputError("parser", parts)
    confidence = parts.confidence
    if confidence is None:
        raise MissingSubEngineOutputError("confidence", parts)

    # `cleaner` was required for presence only — see the module docstring's
    # "THE FOUR INPUT CONTRACTS" section for why its content has no
    # destination field of its own in the artifact this function returns.

    structured_document = StructuredDocument(
        extracted_text=reader.raw_extracted_text,
        detected_fields=parser.detected_fields,
        document_structure=parser.document_structure,
        detected_tables=parser.detected_tables,
    )
    confidence_report = ConfidenceReport(
        confidence_scores=confidence.confidence_scores,
        uncertainty_markers=confidence.uncertainty_markers,
        reliability_information=confidence.reliability_information,
        risky_fields=confidence.risky_fields,
    )
    return DocumentEvidenceObject(
        identity=identity,
        document_id=DocumentId.new(),
        source_references=source_references,
        structured_document=structured_document,
        human_business_context=human_business_context,
        confidence_report=confidence_report,
    )
