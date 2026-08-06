"""The inventory itself — every prohibition, and the control that proves it.

`conformance.py` is the mechanism; this module is the evidence. It answers one
question with real payloads rather than prose: **do the six frozen artifact
schemas actually refuse what the locked documents say they must?**

WHY EVERY ENTRY IS BUILT TWICE.
    A `NegativeControl` here is two builders that differ in EXACTLY ONE
    prohibition. `clean()` must construct; `violating()` must be refused. Hold
    both and the difference between them is what was refused, so the rejection
    is attributable to that rule without reading a single error message.

    The clean half is the expensive half and it is the point. A control whose
    clean payload also fails is reported `CONTROL_INVALID` and is NOT a pass —
    the payload died of some other defect and the rule under test was never
    reached. Every clean builder below is executed by the suite for exactly
    that reason: an inventory of controls that were never run against a real
    schema is the false green §J exists to prevent, arriving through the front
    door.

WHY EACH PROHIBITION CARRIES A LINE AND NOT A DOCUMENT.
    `quote` is a verbatim substring of the line at `source`, and a test reads
    that line off disk and fails if the two have drifted apart. A citation is
    the only thing connecting this file to the specifications it claims to
    enforce; an uncheckable one stops describing the system the moment anybody
    edits a spec, and no comment catches that.

WHAT IS DELIBERATELY LISTED AND NOT TESTED.
    Eight prohibitions are `REVIEW_ONLY`. Each constrains a CALLER's reasoning
    or needs a judgement no artifact carries — *"confidence never changes
    because an engine reasoned harder"* has no payload that could witness it,
    because the artifact looks identical either way. Faking a predicate for one
    of these would be the worst outcome available: a green suite implying
    coverage that does not exist. Each names the phase at which it stops being
    an exemption, and `Registry` refuses one that does not.

WHAT IS NOT HERE, AND WHY THAT IS A FINDING NOT AN OMISSION.
    Only rules the frozen schemas ALREADY enforce are listed as predicates. A
    rule that turned out not to be enforced is reported to the owner, never
    quietly given a control that passes for some other reason. Nothing in this
    module edits, weakens or works around a schema.

    Until `EXCLUSIONS` existed, that paragraph was true and unverifiable: 45
    hand-listed rules against 143 prohibition clauses in `docs/`, with nothing
    anywhere comparing the two. "What is not here" was whatever nobody had
    thought of, and the suite was green about it. Every clause is now either
    cited above or listed at the bottom of this file with a reason.

WHAT THIS FILE STILL DOES NOT MEASURE.
    Whether any ENGINE emits a conformant artifact. Every control here hands a
    hand-written payload to a schema; not one of them runs Engine 1. The real
    pipeline emits zero detected fields, zero confidence scores and zero
    `Provenance` objects for a PDF it reads successfully, and nothing in this
    module notices — because this module is about schemas, and that is a
    different subject. The against-the-real-artifact predicates are in
    `tests/unit/test_conformance_registry.py`, where Engine 1 can be imported.

NO CLOCK, NO RANDOMNESS, NO I/O.
    Identifiers are fixed UUIDs and timestamps are fixed moments, so two runs
    build byte-identical payloads. A control that depended on `uuid4()` or
    `now()` could pass on one run and fail on the next, and a conformance
    result that is not reproducible is not a result.

    NO I/O is load-bearing beyond determinism: the `conformance` CI job installs
    `requirements-ci.txt` alone, so this module may import nothing from
    `engines/` — Engine 1 needs OpenCV, PyMuPDF and Docling, and importing it
    here would break that job on a dependency rather than on a finding.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel

from accountant_dad.artifacts.clarification import (
    ClarificationPriority,
    ClarificationRequest,
    ClarificationStatus,
)
from accountant_dad.artifacts.decision import (
    AccountingDecision,
    DecisionStatus,
    JournalLine,
    UnresolvedDoubt,
)
from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    Corroborated,
    DetectedField,
    DocumentEvidenceObject,
    DocumentId,
    FieldConfidence,
    HumanBusinessContext,
    Provenance,
    SourceType,
    StructuredDocument,
    UncertaintyMarker,
)
from accountant_dad.artifacts.execution import (
    AuditReference,
    ExecutionAttemptId,
    ExecutionId,
    ExecutionResult,
)
from accountant_dad.artifacts.understanding import (
    BusinessContextResult,
    BusinessUnderstandingObject,
    ConfidenceAssessment,
    Conflict,
    ItemUnderstandingResult,
    ObservedFact,
    PartyUnderstandingResult,
    PaymentUnderstandingResult,
    SupportingUnderstandingData,
    TimelineUnderstandingResult,
    TransactionStory,
    TransactionUnderstandingResult,
    Unknown,
)
from accountant_dad.artifacts.validation import (
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationFinding,
    ValidationStatus,
)
from accountant_dad.conformance import Enforcement, NegativeControl, Prohibition, Registry
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

# ── fixed material ────────────────────────────────────────────────────────
#
# Nothing below reads a clock or a random source. See the module docstring.

#: One moment, everywhere. Timezone-aware, because every schema that stores a
#: datetime refuses a naive one — a clean payload must therefore carry an
#: offset or it would die of the wrong defect.
_MOMENT = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

#: One confidence, everywhere a clean payload needs one. Four places, the scale
#: `confidence.py` fixed; Decimal, because float is refused at the type.
_CONFIDENCE = Decimal("0.9000")

#: A real UUID, hyphenated, that `decision.py`'s INV-9 pattern matches. Used as
#: hostile input, never as an identity.
_LEAKED_IDENTIFIER = "123e4567-e89b-12d3-a456-426614174000"


def _uuid(marker: str) -> uuid.UUID:
    """A fixed v4-shaped UUID built from one hex digit.

    Distinct markers give distinct identities without `uuid4()`. Version and
    variant nibbles are pinned so the value is a legal v4 — `identity.py` chose
    v4 precisely because it encodes nothing (INV-9), and a malformed stand-in
    would be a different value in a way no reader could see.
    """
    body = marker * 8
    return uuid.UUID(f"{body}-{marker * 4}-4{marker * 3}-8{marker * 3}-{marker * 12}")


def _envelope(**override: object) -> IdentityEnvelope:
    """`DATA_FLOW.md:32` — the identity envelope every artifact carries."""
    return IdentityEnvelope.model_validate(
        {
            "artifact_id": ArtifactId(_uuid("1")),
            "version": 1,
            "parent_versions": (),
            "transaction_id": TransactionId(_uuid("2")),
        }
        | override
    )


def _mutate(model: BaseModel) -> BaseModel:
    """Assign a field of an already-built artifact back to its own value.

    The assignment is the whole violation: the value does not change, so the
    only difference between this and its clean twin is that a write was
    attempted. INV-5 says a version once created is frozen, and `frozen=True`
    is what turns that into a refusal instead of a convention.
    """
    field = next(iter(type(model).model_fields))
    setattr(model, field, getattr(model, field))
    return model


# ── the builders ──────────────────────────────────────────────────────────
#
# EVERY BUILDER TAKES `**override` AND GOES THROUGH `model_validate`, for one
# reason: a control has to be able to add a field the schema does not declare.
# `extra="forbid"` is the whole enforcement for four prohibitions below, and a
# typed constructor cannot express the payload that tests it — the typechecker
# refuses the call before pydantic ever sees it, which would leave those four
# rules asserted in prose only.
#
# `model_validate` is not a loophole around the schema. It runs the identical
# core validation — field types, `extra`, and every `model_validator` — and it
# is the path an artifact actually takes when it arrives as a mapping from
# outside the process, which is where untrusted input comes from (Law 23).


# ── Document Evidence Object · Engine 1 ───────────────────────────────────


def _provenance(**override: object) -> Provenance:
    return Provenance.model_validate(
        {
            "source_type": SourceType.DOCUMENT,
            "source_id": "invoice-2026-0041.pdf",
            "evidence_reference": "page 1, line 4",
            "timestamp": _MOMENT,
            "confidence": _CONFIDENCE,
            "corroborated": Corroborated.NOT_ASSESSED,
        }
        | override
    )


def _detected_field(**override: object) -> DetectedField:
    return DetectedField.model_validate(
        {"name": "Amount", "value": "1180.00", "provenance": _provenance()} | override
    )


def _structured_document(**override: object) -> StructuredDocument:
    return StructuredDocument.model_validate(
        {
            "extracted_text": "INVOICE  Total 1,180.00",
            "detected_fields": (_detected_field(),),
            "document_structure": "header, one table, footer",
            "detected_tables": (),
        }
        | override
    )


def _confidence_report(**override: object) -> ConfidenceReport:
    return ConfidenceReport.model_validate(
        {
            "confidence_scores": (FieldConfidence(field_name="Amount", confidence=_CONFIDENCE),),
            "uncertainty_markers": (),
            "reliability_information": "typed document, clean scan",
            "risky_fields": (),
        }
        | override
    )


def _evidence(**override: object) -> DocumentEvidenceObject:
    return DocumentEvidenceObject.model_validate(
        {
            "identity": _envelope(),
            "document_id": DocumentId(_uuid("3")),
            "source_references": ("invoice-2026-0041.pdf",),
            "structured_document": _structured_document(),
            "human_business_context": None,
            "confidence_report": _confidence_report(),
        }
        | override
    )


# ── Business Understanding Object · Engine 2 ──────────────────────────────
#
# Every authored string below is checked against `FORBIDDEN_VOCABULARY`, so the
# clean payloads are written in the business register `ENGINE_2:852` requires:
# "Item description: Laptop", never "Fixed asset purchase".


def _fact(**override: object) -> ObservedFact:
    return ObservedFact.model_validate(
        {
            "statement": "The document states a total of 1,180.00.",
            "stated_text": "Total  1,180.00",
            "evidence_references": ("page 1, line 4",),
        }
        | override
    )


def _unknown(**override: object) -> Unknown:
    return Unknown.model_validate(
        {
            "subject": "the date the goods were received",
            "why_it_matters": "Without it, the period this event belongs to cannot be settled.",
        }
        | override
    )


def _conflict(**override: object) -> Conflict:
    return Conflict.model_validate(
        {
            "subject": "the total on the document",
            "competing_readings": (
                _fact(statement="The printed total reads 1,180.00."),
                _fact(statement="The lines add up to 1,180.50."),
            ),
        }
        | override
    )


def _results(**override: object) -> SupportingUnderstandingData:
    """All six Results. A missing one is a sub-engine that did not run."""
    return SupportingUnderstandingData.model_validate(
        {
            "transaction": TransactionUnderstandingResult(
                confidence=_CONFIDENCE, identified_event=(_fact(),)
            ),
            "party": PartyUnderstandingResult(
                confidence=_CONFIDENCE, identified_entities=(_fact(),)
            ),
            "item": ItemUnderstandingResult(
                confidence=_CONFIDENCE,
                identified_goods_and_services=(_fact(),),
                descriptions=(_fact(),),
            ),
            "payment": PaymentUnderstandingResult(
                confidence=_CONFIDENCE, amount_relationships=(_fact(),)
            ),
            "timeline": TimelineUnderstandingResult(confidence=_CONFIDENCE, dates=(_fact(),)),
            "business_context": BusinessContextResult(
                confidence=_CONFIDENCE, context_clues=(_fact(),)
            ),
        }
        | override
    )


def _assessment(**override: object) -> ConfidenceAssessment:
    return ConfidenceAssessment.model_validate(
        {"evidence_confidence": _CONFIDENCE, "understanding_confidence": _CONFIDENCE} | override
    )


def _understanding(**override: object) -> BusinessUnderstandingObject:
    return BusinessUnderstandingObject.model_validate(
        {
            "identity": _envelope(),
            "transaction_story": TransactionStory(
                narrative="Twelve units were delivered and paid for on the stated date."
            ),
            "supporting_understanding_data": _results(),
            "identified_unknowns": (),
            "confidence_assessment": _assessment(),
        }
        | override
    )


def _results_raising_an_unknown() -> SupportingUnderstandingData:
    """Six Results, one of which names a gap. The gap is what must survive."""
    return _results(
        transaction=TransactionUnderstandingResult(
            confidence=_CONFIDENCE,
            identified_event=(_fact(),),
            unknown_information=(_unknown(),),
        )
    )


def _results_with_a_less_certain_one() -> SupportingUnderstandingData:
    """Five Results at 0.9000 and one at 0.7000, so `min` and `max` differ."""
    return _results(
        payment=PaymentUnderstandingResult(
            confidence=Decimal("0.7000"), amount_relationships=(_fact(),)
        )
    )


# ── Accounting Decision · Engine 3 ────────────────────────────────────────


def _journal_line(**override: object) -> JournalLine:
    return JournalLine.model_validate(
        {"ledger": "Office Equipment", "amount": Decimal("1180.00")} | override
    )


def _doubt(**override: object) -> UnresolvedDoubt:
    return UnresolvedDoubt.model_validate(
        {
            "missing_fact": "the date the goods were received",
            "required_clarification": "On what date were the goods received?",
        }
        | override
    )


def _decision(**override: object) -> AccountingDecision:
    return AccountingDecision.model_validate(
        {
            "identity": _envelope(),
            "decision_status": DecisionStatus.COMPLETE,
            "accounting_treatment": "Purchase of office equipment",
            "ledger_classification": "Office Equipment",
            "debit_entries": (_journal_line(),),
            "credit_entries": (_journal_line(ledger="Bank"),),
            "journal_structure": "one debit, one credit",
            "tax_treatment": "input credit claimed at the stated rate",
            "accounting_assumptions": (),
            "risk_indicators": (),
            "decision_confidence": _CONFIDENCE,
            "supporting_reasoning": "The document names the item, the seller and the amount.",
            "unresolved_doubts": (),
        }
        | override
    )


def _incomplete_decision(**override: object) -> AccountingDecision:
    """A decision that stopped. It carries no journal, so it must name a doubt."""
    return _decision(
        **{
            "decision_status": DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
            "debit_entries": (),
            "credit_entries": (),
            "unresolved_doubts": (_doubt(),),
        }
        | override
    )


# ── Clarification Request · Engine 4 ──────────────────────────────────────


def _clarification(**override: object) -> ClarificationRequest:
    return ClarificationRequest.model_validate(
        {
            "identity": _envelope(),
            "clarification_id": ArtifactId(_uuid("4")),
            "related_decision_id": ArtifactId(_uuid("5")),
            "related_artifact_version": 1,
            "missing_information": ("the date the goods were received",),
            "detected_conflicts": (),
            "required_clarification": "On what date were the goods received?",
            "reason_clarification_is_required": "The period the entry belongs to depends on it.",
            "affected_decision": "the accounting period of the entry",
            "priority": ClarificationPriority.HIGH,
            "supporting_evidence_references": ("page 1, line 4",),
            "clarification_confidence": _CONFIDENCE,
            "status": ClarificationStatus.CREATED,
        }
        | override
    )


# ── Validation Decision · Engine 5 ────────────────────────────────────────


def _finding(**override: object) -> ValidationFinding:
    return ValidationFinding.model_validate(
        {
            "what_failed": "the claimed input credit",
            "why_it_failed": "no evidence reference names the rate it was claimed at",
            "responsible_engine": ResponsibleEngine.ACCOUNTING,
            "affected_artifact": "Accounting Decision",
            "blocking_severity": Severity.LOW,
            "recommended_next_step": "raise a clarification for the rate",
            "supporting_evidence_references": ("page 1, line 4",),
        }
        | override
    )


def _validation(**override: object) -> ValidationDecision:
    return ValidationDecision.model_validate(
        {
            "identity": _envelope(),
            "related_decision_id": ArtifactId(_uuid("5")),
            "related_artifact_version": 1,
            "validation_status": ValidationStatus.APPROVED,
            "validation_findings": (),
            "validation_errors": (),
            "validation_warnings": (),
            "validation_risks": (),
            "failed_validation_rules": (),
            "supporting_evidence_references": ("page 1, line 4",),
            "validation_confidence": _CONFIDENCE,
            "validation_reasoning": "every rule the decision was checked against passed",
            "validation_timestamp": _MOMENT,
        }
        | override
    )


# ── Execution Result · Engine 6 ───────────────────────────────────────────


def _execution(**override: object) -> ExecutionResult:
    return ExecutionResult.model_validate(
        {
            "identity": _envelope(),
            "execution_id": ExecutionId(_uuid("6")),
            "execution_attempt_id": ExecutionAttemptId(_uuid("7")),
            "accounting_decision_id": ArtifactId(_uuid("5")),
            "decision_version": 1,
            "validation_decision_id": ArtifactId(_uuid("8")),
            "destination_system": "Tally",
            "corrects_execution_result": None,
            "posting_status": "Posted",
            "external_transaction_ids": ("TALLY-88214",),
            "retry_count": 0,
            "queue_status": "Drained",
            "notification_status": "Sent",
            "classified_error": None,
            "audit_reference": AuditReference(execution_id=ExecutionId(_uuid("6"))),
            "execution_outcome": "Success",
            "execution_confidence": _CONFIDENCE,
            "execution_timestamp": _MOMENT,
        }
        | override
    )


# ── the inventory ─────────────────────────────────────────────────────────
#
# Identifier scheme: `DOC:LINE/slug`. The line is in the identifier as well as
# in `source` so a finding names the exact sentence, not only a rule's nickname.


def _predicate(identifier: str, quote: str, source: str, subject: str) -> Prohibition:
    return Prohibition(
        identifier=identifier,
        quote=quote,
        source=source,
        subject=subject,
        enforcement=Enforcement.PREDICATE,
    )


def _review_only(
    identifier: str, quote: str, source: str, subject: str, expiry: str
) -> Prohibition:
    return Prohibition(
        identifier=identifier,
        quote=quote,
        source=source,
        subject=subject,
        enforcement=Enforcement.REVIEW_ONLY,
        expiry=expiry,
    )


IMMUTABLE = "SYSTEM_INVARIANTS:142/an-artifact-is-immutable-after-creation"
LINEAGE = "SYSTEM_INVARIANTS:150/a-later-version-records-its-parents"
NO_IDENTIFIER = "SYSTEM_INVARIANTS:215/no-identifier-in-artifact-text"
ONE_OWNER = "SYSTEM_INVARIANTS:229/one-owner-per-named-field"
ORIGINS_UNMERGED = "SYSTEM_INVARIANTS:254/origins-are-never-merged"

EXTRACTED_NOT_HUMAN = "ENGINE_1:233/extracted-evidence-never-claims-a-human-origin"
READING_IS_SCORED = "ENGINE_1:245/every-reading-carries-its-confidence"
THREE_STATES = "ENGINE_1:569/absent-zero-and-unreadable-stay-distinct"
MARKER_HAS_A_REASON = "ENGINE_1:626/every-uncertainty-marker-carries-a-reason"

UNKNOWNS_INTACT = "ENGINE_2:645/unknowns-are-carried-intact"
RESULT_REPORTS = "ENGINE_2:350/no-result-reports-nothing"
DESCRIPTION_QUOTES = "ENGINE_2:472/a-description-quotes-the-document"
NO_VOCABULARY = "ENGINE_2:641/no-accounting-vocabulary-in-authored-text"
TWO_READINGS = "ENGINE_2:673/a-conflict-needs-two-competing-readings"
NO_RESOLUTION = "SYSTEM_BOUNDARIES:95/a-conflict-carries-no-resolution"
CONFIDENCE_CAPPED = "ENGINE_2:756/understanding-never-exceeds-evidence"
NO_FREE_CONFIDENCE = "SYSTEM_BOUNDARIES:101/story-builder-never-increases-confidence"
FACT_CITES_EVIDENCE = "UNDERSTANDING_INTERNAL:130/every-fact-cites-its-evidence"

PAISA = "ACCOUNTING_DEFINITIONS:45/amounts-are-exact-to-the-paisa"
BALANCE = "ENGINE_3:566/debit-equals-credit"
COMPLETE_POSTS = "ENGINE_3:770/a-complete-decision-posts-something"
INCOMPLETE_NAMES_IT = "ENGINE_3:196/an-incomplete-decision-names-its-clarification"

NO_ANSWER_FIELD = "ENGINE_4:247/no-field-holds-an-answer"
BLANK_NAMES_NOTHING = "ENGINE_4:557/a-blank-statement-names-nothing"
REQUEST_CITES_EVIDENCE = "CLARIFICATION_INTERNAL:87/a-request-cites-its-evidence"

NO_REPAIR_FIELD = "ENGINE_5:215/no-field-holds-a-repair"
NO_APPROVAL_ON_CRITICAL = "ENGINE_5:467/no-approval-while-a-critical-finding-stands"
REFUSAL_SAYS_WHY = "ENGINE_5:228/a-non-approving-decision-says-exactly-why"
FINDING_SHOWS_EVIDENCE = "ENGINE_5:571/every-finding-shows-its-evidence"
BLAME_IS_UPSTREAM = "ENGINE_5:232/every-finding-names-engine-1-to-4"

NO_SELF_CORRECTION = "ENGINE_6:210/an-execution-cannot-correct-itself"
AUDIT_POINTS_HOME = "ENGINE_6:507/the-audit-reference-points-at-its-own-execution"
TRANSPORT_ONLY = "SYSTEM_BOUNDARIES:279/an-execution-result-records-no-accounting"

PROHIBITIONS: tuple[Prohibition, ...] = (
    # ── universal, every artifact ─────────────────────────────────────────
    _predicate(
        IMMUTABLE,
        "Every artifact is immutable after creation. Correction means a new version, "
        "never an edit.",
        "docs/SYSTEM_INVARIANTS.md:142",
        "every canonical artifact",
    ),
    _predicate(
        LINEAGE,
        "Each version records the exact parent versions it derived from",
        "docs/SYSTEM_INVARIANTS.md:150",
        "the identity envelope",
    ),
    _predicate(
        NO_IDENTIFIER,
        "IDs identify objects. They do not influence reasoning.",
        "docs/SYSTEM_INVARIANTS.md:215",
        "Accounting Decision",
    ),
    _predicate(
        ONE_OWNER,
        "No responsibility exists in two places. No component owns two problems.",
        "docs/SYSTEM_INVARIANTS.md:229",
        "Document Evidence Object",
    ),
    _predicate(
        ORIGINS_UNMERGED,
        "No engine may merge these origins into a single anonymous fact.",
        "docs/SYSTEM_INVARIANTS.md:254",
        "Document Evidence Object",
    ),
    # ── Engine 1 ──────────────────────────────────────────────────────────
    _predicate(
        EXTRACTED_NOT_HUMAN,
        "Engine 1 never merges the two into a single fact.",
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:233",
        "Structured Document",
    ),
    _predicate(
        READING_IS_SCORED,
        "A value carried without all three is not evidence and must not be emitted.",
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:245",
        "Document Evidence Object",
    ),
    _predicate(
        THREE_STATES,
        '"Absent", "zero" and "unreadable" are three different states and must remain '
        "distinguishable.",
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:569",
        "Detected Field",
    ),
    _predicate(
        MARKER_HAS_A_REASON,
        "Every uncertainty marker carries a reason.",
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:626",
        "Confidence Report",
    ),
    # ── Engine 2 ──────────────────────────────────────────────────────────
    _predicate(
        UNKNOWNS_INTACT,
        "Unknowns are carried into Identified Unknowns intact.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:645",
        "Business Understanding Object",
    ),
    _predicate(
        RESULT_REPORTS,
        "No Result may omit them.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:350",
        "Understanding Result",
    ),
    _predicate(
        DESCRIPTION_QUOTES,
        "Recompute a line value the document states, nor supply one it omits.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:472",
        "Item Understanding Result",
    ),
    _predicate(
        NO_VOCABULARY,
        "Use accounting vocabulary.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:641",
        "Transaction Story",
    ),
    _predicate(
        TWO_READINGS,
        "Never silently choose one answer.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:673",
        "Conflict",
    ),
    _predicate(
        NO_RESOLUTION,
        "the engine returns known facts, conflicting facts, confidence and unknowns "
        "— never a resolution",
        "docs/SYSTEM_BOUNDARIES.md:95",
        "Conflict",
    ),
    _predicate(
        CONFIDENCE_CAPPED,
        "Understanding confidence cannot exceed evidence reliability.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:756",
        "Confidence Assessment",
    ),
    _predicate(
        NO_FREE_CONFIDENCE,
        "never removes an unknown, and never increases confidence",
        "docs/SYSTEM_BOUNDARIES.md:101",
        "Business Understanding Object",
    ),
    _predicate(
        FACT_CITES_EVIDENCE,
        "A fact with no evidence reference cannot appear in a Result.",
        "docs/COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md:130",
        "Observed Fact",
    ),
    # ── Engine 3 ──────────────────────────────────────────────────────────
    _predicate(
        PAISA,
        "Exact to the paisa. Zero tolerance.",
        "docs/ACCOUNTING_DEFINITIONS.md:45",
        "Journal Line",
    ),
    _predicate(
        BALANCE,
        "create the journal structure · ensure **debit = credit**",
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:566",
        "Accounting Decision",
    ),
    _predicate(
        COMPLETE_POSTS,
        "A `COMPLETE` decision resting on one silent assumption is a **failure**",
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:770",
        "Accounting Decision",
    ),
    _predicate(
        INCOMPLETE_NAMES_IT,
        "The decision could not be completed. Required clarification is named.",
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:196",
        "Accounting Decision",
    ),
    # ── Engine 4 ──────────────────────────────────────────────────────────
    _predicate(
        NO_ANSWER_FIELD,
        "It must never guess.",
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:247",
        "Clarification Request",
    ),
    _predicate(
        BLANK_NAMES_NOTHING,
        "An incomplete request that names what it could not determine is correct output",
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:557",
        "Clarification Request",
    ),
    _predicate(
        REQUEST_CITES_EVIDENCE,
        "A finding with no evidence reference cannot appear in a Result.",
        "docs/COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md:87",
        "Clarification Request",
    ),
    # ── Engine 5 ──────────────────────────────────────────────────────────
    _predicate(
        NO_REPAIR_FIELD,
        "it never fixes them. It reports them.",
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:215",
        "Validation Decision",
    ),
    _predicate(
        NO_APPROVAL_ON_CRITICAL,
        "No approval exists while a Critical finding remains.",
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:467",
        "Validation Decision",
    ),
    _predicate(
        REFUSAL_SAYS_WHY,
        'Never simply "Validation Failed." Always exactly why.',
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:228",
        "Validation Decision",
    ),
    _predicate(
        FINDING_SHOWS_EVIDENCE,
        "Every finding contains evidence references.",
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:571",
        "Validation Finding",
    ),
    _predicate(
        BLAME_IS_UPSTREAM,
        "Every validation issue points back to Engine 1, 2, 3 or 4.",
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:232",
        "Validation Finding",
    ),
    # ── Engine 6 ──────────────────────────────────────────────────────────
    _predicate(
        NO_SELF_CORRECTION,
        "Which execution corrected which previous execution?",
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:210",
        "Execution Result",
    ),
    _predicate(
        AUDIT_POINTS_HOME,
        "One per Execution ID. It is reached through the Execution Result's `Audit Reference`",
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:507",
        "Execution Result",
    ),
    _predicate(
        TRANSPORT_ONLY,
        "It may never choose accounts, change accounting treatment, modify tax decisions",
        "docs/SYSTEM_BOUNDARIES.md:279",
        "Execution Result",
    ),
    # ── review only ───────────────────────────────────────────────────────
    #
    # No pure function decides any of these. Each constrains a caller's
    # reasoning, or needs a second run, or asks whether a stored string is a
    # paraphrase — none of which an artifact can witness, because the artifact
    # looks identical either way. Listed, never faked, each with an end date.
    _review_only(
        "SYSTEM_INVARIANTS:51/confidence-never-rises-from-harder-reasoning",
        "Confidence never changes because an engine reasoned harder.",
        "docs/SYSTEM_INVARIANTS.md:51",
        "every engine that emits a confidence",
        # P4 is where reasoning first exists to be reviewed. Two artifacts with
        # the same score are byte-identical whether or not the second one was
        # earned, so no payload can distinguish them.
        "P4",
    ),
    _review_only(
        "SYSTEM_INVARIANTS:258/a-human-note-is-never-rewritten",
        "**never be rewritten** — it is stored verbatim.",
        "docs/SYSTEM_INVARIANTS.md:258",
        "Human Business Context",
        # The schema refuses a blank note and refuses a non-Human origin. It
        # cannot see the note the user actually typed, so it cannot tell a
        # verbatim capture from a tidied one.
        "P4",
    ),
    _review_only(
        "ENGINE_2:852/facts-never-accounting-conclusions",
        "The Understanding Engine sends facts, never accounting conclusions.",
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:852",
        "Business Understanding Object",
        # The lexical half IS a predicate (`ENGINE_2:641`, above). This is the
        # semantic half, and it is a different claim: a paraphrase carrying an
        # accounting conclusion in ordinary words walks straight through a word
        # list, and no string check closes that.
        "P4",
    ),
    _review_only(
        "CLARIFICATION_INTERNAL:89/clarification-confidence-never-exceeds-upstream",
        "Clarification Confidence may never exceed upstream confidence.",
        "docs/COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md:89",
        "Clarification Request",
        # The artifact carries no upstream confidence, so the comparison has
        # nothing to compare against. A reader who assumes the schema enforces
        # this would be quietly wrong — which is why it is written down.
        "P4",
    ),
    _review_only(
        "SYSTEM_BOUNDARIES:210/validation-reports-and-never-repairs",
        "Amend, correct or repair a decision it is judging. A defect is reported, never fixed.",
        "docs/SYSTEM_BOUNDARIES.md:210",
        "Validation Engine",
        # `ENGINE_5:215` above IS enforced, structurally: a repair has nowhere
        # to sit. This is the behavioural remainder — whether a value the
        # engine wrote into a legitimate field is a repair needs the accounting
        # reasoning Engine 5 is forbidden to do.
        "P5",
    ),
    _review_only(
        "ACCOUNTING_DEFINITIONS:194/a-doubt-is-a-fact-that-would-change-the-treatment",
        "named missing fact whose absence would change the accounting treatment",
        "docs/ACCOUNTING_DEFINITIONS.md:194",
        "Accounting Decision",
        # The measurement is "supply the fact, re-run, see whether the decision
        # changes". That needs two runs of an engine that does not exist yet;
        # the schema can only require that a doubt names both halves.
        "P5",
    ),
    _review_only(
        "ENGINE_6:561/execution-confidence-is-transport-only",
        "Execution Confidence measures transport and execution only — never "
        "accounting correctness.",
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:561",
        "Execution Result",
        # One Decimal in [0,1] looks exactly like another. What it measures is
        # a property of the producer, not of the value.
        "P6",
    ),
)

CONTROLS: tuple[NegativeControl, ...] = (
    # ── INV-5, once per artifact ──────────────────────────────────────────
    #
    # The violating half writes a field back to the value it already holds, so
    # the ONLY difference from the clean half is that a write was attempted.
    NegativeControl(IMMUTABLE, clean=_evidence, violating=lambda: _mutate(_evidence())),
    NegativeControl(IMMUTABLE, clean=_understanding, violating=lambda: _mutate(_understanding())),
    NegativeControl(IMMUTABLE, clean=_decision, violating=lambda: _mutate(_decision())),
    NegativeControl(IMMUTABLE, clean=_clarification, violating=lambda: _mutate(_clarification())),
    NegativeControl(IMMUTABLE, clean=_validation, violating=lambda: _mutate(_validation())),
    NegativeControl(IMMUTABLE, clean=_execution, violating=lambda: _mutate(_execution())),
    # ── lineage ───────────────────────────────────────────────────────────
    NegativeControl(
        LINEAGE,
        clean=lambda: _envelope(
            version=2,
            parent_versions=(ParentVersion(artifact_id=ArtifactId(_uuid("1")), version=1),),
        ),
        violating=lambda: _envelope(version=2, parent_versions=()),
    ),
    # ── INV-9, at the two places the invariant names first ────────────────
    NegativeControl(
        NO_IDENTIFIER,
        clean=lambda: _decision(supporting_reasoning="An earlier entry treated this the same way."),
        violating=lambda: _decision(
            supporting_reasoning=f"Because {_LEAKED_IDENTIFIER} existed before, "
            "choose the same treatment."
        ),
    ),
    NegativeControl(
        NO_IDENTIFIER,
        clean=lambda: _journal_line(ledger="Office Equipment"),
        violating=lambda: _journal_line(ledger=f"Office Equipment {_LEAKED_IDENTIFIER}"),
    ),
    # ── INV-10: two things claiming one name ──────────────────────────────
    NegativeControl(
        ONE_OWNER,
        clean=lambda: _structured_document(
            detected_fields=(_detected_field(name="Amount"), _detected_field(name="Vendor"))
        ),
        violating=lambda: _structured_document(
            detected_fields=(_detected_field(name="Amount"), _detected_field(name="Amount"))
        ),
    ),
    NegativeControl(
        ONE_OWNER,
        clean=lambda: _confidence_report(
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=_CONFIDENCE),
                FieldConfidence(field_name="Vendor", confidence=_CONFIDENCE),
            )
        ),
        violating=lambda: _confidence_report(
            confidence_scores=(
                FieldConfidence(field_name="Amount", confidence=_CONFIDENCE),
                FieldConfidence(field_name="Amount", confidence=_CONFIDENCE),
            )
        ),
    ),
    # ── INV-11: a human claim filed as anything else ──────────────────────
    NegativeControl(
        ORIGINS_UNMERGED,
        clean=lambda: HumanBusinessContext(
            original_user_text="bought a laptop for the office",
            provenance=_provenance(source_type=SourceType.HUMAN),
        ),
        violating=lambda: HumanBusinessContext(
            original_user_text="bought a laptop for the office",
            provenance=_provenance(source_type=SourceType.DOCUMENT),
        ),
    ),
    # ── Engine 1 ──────────────────────────────────────────────────────────
    NegativeControl(
        EXTRACTED_NOT_HUMAN,
        clean=lambda: _structured_document(
            detected_fields=(_detected_field(provenance=_provenance()),)
        ),
        violating=lambda: _structured_document(
            detected_fields=(_detected_field(provenance=_provenance(source_type=SourceType.HUMAN)),)
        ),
    ),
    NegativeControl(
        READING_IS_SCORED,
        clean=_evidence,
        # The reading survives; only its score is withdrawn.
        violating=lambda: _evidence(confidence_report=_confidence_report(confidence_scores=())),
    ),
    NegativeControl(
        THREE_STATES,
        # "0" is a zero that was read; None would be unreadable. "" collapses
        # the two, and the collapse is invisible downstream.
        clean=lambda: _detected_field(value="0"),
        violating=lambda: _detected_field(value=""),
    ),
    NegativeControl(
        MARKER_HAS_A_REASON,
        # WHAT THIS CONTROL DOES AND DOES NOT ESTABLISH. `""` is refused. A
        # PADDED blank — `"   "` — is ACCEPTED, because `evidence.py` builds its
        # `NonEmptyText` from `Field(min_length=1)` while the other five artifact
        # modules use a validator that rejects anything blank after stripping.
        # So `ENGINE_1:626` is enforced against the empty string and not against
        # whitespace, and the same asymmetry reaches `Provenance.source_id` and
        # `evidence_reference` under `ENGINE_1:245`.
        #
        # Reported, not worked around. No control is written for the padded case
        # because it would be NOT_ENFORCED, and no schema is edited from here —
        # the fix belongs to whoever owns `evidence.py` (Law 4, §J.4).
        clean=lambda: UncertaintyMarker(subject="Amount", reason="the last digit is smudged"),
        violating=lambda: UncertaintyMarker(subject="Amount", reason=""),
    ),
    # ── Engine 2 ──────────────────────────────────────────────────────────
    NegativeControl(
        UNKNOWNS_INTACT,
        clean=lambda: _understanding(
            supporting_understanding_data=_results_raising_an_unknown(),
            identified_unknowns=(_unknown(),),
        ),
        violating=lambda: _understanding(
            supporting_understanding_data=_results_raising_an_unknown(),
            identified_unknowns=(),
        ),
    ),
    NegativeControl(
        RESULT_REPORTS,
        clean=lambda: TransactionUnderstandingResult(
            confidence=_CONFIDENCE, identified_event=(_fact(),)
        ),
        violating=lambda: TransactionUnderstandingResult(confidence=_CONFIDENCE),
    ),
    NegativeControl(
        DESCRIPTION_QUOTES,
        clean=lambda: ItemUnderstandingResult(
            confidence=_CONFIDENCE, descriptions=(_fact(stated_text="Laptop, 1 unit"),)
        ),
        violating=lambda: ItemUnderstandingResult(
            confidence=_CONFIDENCE, descriptions=(_fact(stated_text=None),)
        ),
    ),
    NegativeControl(
        NO_VOCABULARY,
        clean=lambda: TransactionStory(narrative="The buyer received twelve units and paid."),
        violating=lambda: TransactionStory(
            narrative="The buyer received twelve units: a fixed asset purchase."
        ),
    ),
    NegativeControl(
        TWO_READINGS,
        clean=_conflict,
        violating=lambda: _conflict(
            competing_readings=(_fact(statement="The printed total reads 1,180.00."),)
        ),
    ),
    NegativeControl(
        TWO_READINGS,
        # Two readings that say the same thing do not disagree, so nothing here
        # is a conflict — the label without the substance.
        clean=_conflict,
        violating=lambda: _conflict(
            competing_readings=(
                _fact(statement="The printed total reads 1,180.00."),
                _fact(statement="The printed total reads 1,180.00."),
            )
        ),
    ),
    NegativeControl(
        NO_RESOLUTION,
        clean=_conflict,
        violating=lambda: _conflict(resolution="the printed total wins"),
    ),
    NegativeControl(
        CONFIDENCE_CAPPED,
        clean=lambda: _assessment(
            evidence_confidence=Decimal("0.6000"), understanding_confidence=Decimal("0.6000")
        ),
        violating=lambda: _assessment(
            evidence_confidence=Decimal("0.6000"), understanding_confidence=Decimal("0.9000")
        ),
    ),
    NegativeControl(
        CONFIDENCE_CAPPED,
        # The same rule at the second place it is enforced: a Result more
        # certain than the evidence the whole artifact rests on.
        clean=lambda: _understanding(
            confidence_assessment=_assessment(
                evidence_confidence=Decimal("0.9000"),
                understanding_confidence=Decimal("0.5000"),
            )
        ),
        violating=lambda: _understanding(
            confidence_assessment=_assessment(
                evidence_confidence=Decimal("0.5000"),
                understanding_confidence=Decimal("0.5000"),
            )
        ),
    ),
    NegativeControl(
        NO_FREE_CONFIDENCE,
        # One Result sits at 0.7000. Story Builder introduces no evidence, so
        # 0.8000 would be certainty it was never handed — and 0.8000 is still
        # under evidence reliability, so only this rule can be what refuses it.
        clean=lambda: _understanding(
            supporting_understanding_data=_results_with_a_less_certain_one(),
            confidence_assessment=_assessment(understanding_confidence=Decimal("0.7000")),
        ),
        violating=lambda: _understanding(
            supporting_understanding_data=_results_with_a_less_certain_one(),
            confidence_assessment=_assessment(understanding_confidence=Decimal("0.8000")),
        ),
    ),
    NegativeControl(
        FACT_CITES_EVIDENCE,
        clean=lambda: _fact(evidence_references=("page 1, line 4",)),
        violating=lambda: _fact(evidence_references=()),
    ),
    # ── Engine 3 ──────────────────────────────────────────────────────────
    NegativeControl(
        PAISA,
        clean=lambda: _journal_line(amount=Decimal("1180.00")),
        violating=lambda: _journal_line(amount=Decimal("1180.005")),
    ),
    NegativeControl(
        PAISA,
        # float is refused rather than converted, because the conversion IS the
        # loss and it would happen before any check could object.
        clean=lambda: _journal_line(amount=Decimal("1180.00")),
        violating=lambda: _journal_line(amount=1180.00),
    ),
    NegativeControl(
        BALANCE,
        clean=_decision,
        violating=lambda: _decision(
            credit_entries=(_journal_line(ledger="Bank", amount=Decimal("1000.00")),)
        ),
    ),
    NegativeControl(
        COMPLETE_POSTS,
        # Both halves balance. The empty one balances VACUOUSLY — 0 == 0 — and
        # would sail through a naive conservation check while asserting nothing.
        clean=_decision,
        violating=lambda: _decision(debit_entries=(), credit_entries=()),
    ),
    NegativeControl(
        INCOMPLETE_NAMES_IT,
        clean=_incomplete_decision,
        violating=lambda: _incomplete_decision(unresolved_doubts=()),
    ),
    # ── Engine 4 ──────────────────────────────────────────────────────────
    NegativeControl(
        NO_ANSWER_FIELD,
        # `extra="forbid"` is what refuses this. There is nowhere in the
        # artifact an answer could sit, so the Request cannot carry a guess.
        clean=_clarification,
        violating=lambda: _clarification(answer="the goods arrived on the 3rd"),
    ),
    NegativeControl(
        BLANK_NAMES_NOTHING,
        clean=lambda: _clarification(affected_decision="the accounting period of the entry"),
        violating=lambda: _clarification(affected_decision="   "),
    ),
    NegativeControl(
        REQUEST_CITES_EVIDENCE,
        clean=lambda: _clarification(supporting_evidence_references=("page 1, line 4",)),
        violating=lambda: _clarification(supporting_evidence_references=()),
    ),
    # ── Engine 5 ──────────────────────────────────────────────────────────
    NegativeControl(
        NO_REPAIR_FIELD,
        clean=_validation,
        violating=lambda: _validation(corrected_ledger="Office Equipment"),
    ),
    NegativeControl(
        NO_APPROVAL_ON_CRITICAL,
        # A High finding is left standing in the clean half deliberately: the
        # difference between the two payloads is the SEVERITY, not the presence
        # of a finding, so nothing but the Critical rule can be what refused it.
        clean=lambda: _validation(validation_findings=(_finding(blocking_severity=Severity.HIGH),)),
        violating=lambda: _validation(
            validation_findings=(_finding(blocking_severity=Severity.CRITICAL),)
        ),
    ),
    NegativeControl(
        REFUSAL_SAYS_WHY,
        clean=lambda: _validation(
            validation_status=ValidationStatus.REJECTED, validation_findings=(_finding(),)
        ),
        violating=lambda: _validation(
            validation_status=ValidationStatus.REJECTED, validation_findings=()
        ),
    ),
    NegativeControl(
        FINDING_SHOWS_EVIDENCE,
        clean=lambda: _finding(supporting_evidence_references=("page 1, line 4",)),
        violating=lambda: _finding(supporting_evidence_references=()),
    ),
    NegativeControl(
        BLAME_IS_UPSTREAM,
        # Validation blaming itself leaves a finding nobody can act on: the
        # engine that found the defect is the one forbidden to repair it.
        clean=lambda: _finding(responsible_engine=ResponsibleEngine.ACCOUNTING),
        violating=lambda: _finding(responsible_engine="Validation"),
    ),
    # ── Engine 6 ──────────────────────────────────────────────────────────
    NegativeControl(
        NO_SELF_CORRECTION,
        clean=lambda: _execution(corrects_execution_result=ExecutionId(_uuid("9"))),
        violating=lambda: _execution(corrects_execution_result=ExecutionId(_uuid("6"))),
    ),
    NegativeControl(
        AUDIT_POINTS_HOME,
        clean=lambda: _execution(
            audit_reference=AuditReference(execution_id=ExecutionId(_uuid("6")))
        ),
        violating=lambda: _execution(
            audit_reference=AuditReference(execution_id=ExecutionId(_uuid("9")))
        ),
    ),
    NegativeControl(
        TRANSPORT_ONLY,
        clean=_execution,
        violating=lambda: _execution(accounting_treatment="Purchase of office equipment"),
    ),
)

# ── what the inventory does NOT cover, and why ────────────────────────────
#
# `tests/unit/test_conformance_registry.py` reads every `must never` clause out
# of `docs/` and demands that each one is either cited by a rule above or listed
# here. Neither side is a hardcoded number: the clauses come off disk and the
# coverage comes off `REGISTRY`, so adding a prohibition to a specification is a
# RED test until somebody says, in writing, what happens to it.
#
# THIS LIST IS NOT PERMISSION. Forty of the entries below are `NOT_YET_A_PREDICATE`
# — witnessable rules with nothing enforcing them, each carrying the phase by
# which that stops being true. They are debts with due dates, printed by the
# suite, and they are the honest answer to "what does conformance not cover?"
#
# WHAT THE SCANNER CANNOT SEE, STATED SO IT IS NOT MISTAKEN FOR NOTHING.
#   - Only the phrase `must never` is scanned. `may never`, `never`, `cannot`
#     and `MUST NOT` are not, so this is a lower bound on the specifications'
#     prohibitions and never an upper one.
#   - A `must never` heading is expanded into the list beneath it, so the
#     numbered items are the units. A heading followed by a fenced block or a
#     table is NOT expanded, and each such heading is listed below naming the
#     clauses it hides.


def _not_a_prohibition(source: str, reason: str) -> Exclusion:
    return Exclusion(source=source, kind=Uncovered.NOT_A_PROHIBITION, reason=reason)


def _restates(source: str, identifier: str, reason: str) -> Exclusion:
    return Exclusion(source=source, kind=Uncovered.RESTATEMENT, reason=reason, restates=identifier)


def _unwitnessable(source: str, reason: str) -> Exclusion:
    return Exclusion(source=source, kind=Uncovered.UNWITNESSABLE, reason=reason)


def _not_yet(source: str, reason: str, expiry: str) -> Exclusion:
    return Exclusion(
        source=source, kind=Uncovered.NOT_YET_A_PREDICATE, reason=reason, expiry=expiry
    )


#: Reasons that are genuinely the same sentence for several clauses. Written
#: once so two copies cannot drift into saying different things about one rule
#: (Law 14); every clause still appears on its own line with its own citation.
_AN_INTERNAL_DECISION = (
    "an act inside an engine, not a value in an artifact. What a component "
    "decided and did not emit leaves no trace, so no payload can witness it. The "
    "emitted half — a conclusion of this kind appearing in the Document Evidence "
    "Object — is INPUT_ENGINE:57, which is enforced."
)
_AN_ABSENCE = (
    "hiding and removing are ABSENCES. An artifact shows what is in it; it "
    "cannot show what was taken out before it was built, and a payload with the "
    "thing removed is byte-identical to one that never had it."
)
_AN_INVENTION = (
    "ENGINE_1_INPUT_ENGINE_RULES.md:337 states the reason itself — an invented "
    "value is indistinguishable downstream from an observed one. That is what "
    "makes the rule matter and what makes it unwitnessable in one payload."
)
_NO_FIELD_FOR_IT_YET = (
    "witnessable and unwritten. The artifact has no field this could sit in, so "
    '`extra="forbid"` would refuse it and a control needs only the schemas, '
    "which exist. Nothing asserts it today."
)
_INV_8 = (
    "the check is that no Execution Result exists for a decision whose Validation "
    "Decision never considered the period — two artifacts and a company calendar. "
    "The calendar is Company Knowledge, and no Knowledge Brain answers before P4."
)
_POSTING_NEVER_REWRITES = (
    "the check is a lineage one: no Accounting Decision version may descend from "
    "an execution failure. It needs a real posting attempt against a real "
    "destination, which BLUEPRINT:137 first requires at P4."
)
_TRANSACTION_ID_NOT_A_KEY = (
    "whether Transaction ID is part of the duplicate-protection key is a property "
    "of posting_manager, not of any artifact: two Execution Results look the same "
    "whichever key admitted them. BLUEPRINT:137 posts three submissions at P4."
)

EXCLUSIONS: tuple[Exclusion, ...] = (
    # ── the Application Layer owns no canonical artifact ──────────────────
    _not_a_prohibition(
        "docs/APPLICATION_LAYER.md:379",
        "a section heading. The eleven clauses under it sit in a fenced code "
        "block, which the scanner does not read — so those eleven are invisible "
        "to this check. Named here because a blind spot nobody wrote down is the "
        "same as no blind spot at all.",
    ),
    _unwitnessable(
        "docs/APPLICATION_LAYER_FAILURE_MATRIX.md:68",
        "the Application Layer creates none of the six canonical artifacts "
        "(DATA_FLOW.md §2 gives every one an engine owner), so nothing it does "
        "appears in a payload. Repairing anything that IS an artifact is already "
        "refused by SYSTEM_INVARIANTS:142.",
    ),
    _not_a_prohibition(
        "docs/APPLICATION_LAYER_FAILURE_MATRIX.md:107",
        "a section heading over a table; the rows beneath it are the claims, and "
        "each names the invariant that prevents it rather than stating a new one.",
    ),
    _not_a_prohibition(
        "docs/APPLICATION_LAYER_FAILURE_MATRIX.md:109",
        "the header row of that table — two column names, no rule.",
    ),
    _not_a_prohibition(
        "docs/APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md:31",
        "the header row of the responsibility matrix — three column names, no rule.",
    ),
    # ── receiver responsibilities, three boundaries ───────────────────────
    _unwitnessable(
        "docs/COMMUNICATION_RULES_ACCOUNTING_ENGINE.md:51",
        "the 'modify' half is SYSTEM_INVARIANTS:142, proven for all six "
        "artifacts. The rest — hiding a conflict, removing an assumption, "
        "raising confidence without new evidence — are absences and comparisons "
        "against an upstream artifact the receiving payload does not carry.",
    ),
    _unwitnessable(
        "docs/COMMUNICATION_RULES_CLARIFICATION_ENGINE.md:49",
        "same shape as the Accounting boundary above: 'modify' is "
        "SYSTEM_INVARIANTS:142; resolving, hiding and approving-while-blocked "
        "are properties of what Validation did, not of what it emitted.",
    ),
    _unwitnessable(
        "docs/COMMUNICATION_RULES_VALIDATION_ENGINE.md:50",
        "'must never modify any upstream artifact' is SYSTEM_INVARIANTS:142. "
        "'Must preserve' is the other direction — a claim about two artifacts, "
        "and an Execution Result carries none of the upstream values to compare.",
    ),
    _not_yet("docs/COMMUNICATION_RULES_VALIDATION_ENGINE.md:81", _POSTING_NEVER_REWRITES, "P4"),
    # ── the human note, and what it may not do ────────────────────────────
    _restates(
        "docs/CONFIDENCE_SPECIFICATION.md:51",
        NOTE_RAISES_NOTHING,
        "a confidence-table row quoting ENGINE_1_INPUT_ENGINE_RULES.md:289 "
        "verbatim. Carried as a review-only entry with expiry P3 — accounted "
        "for, and NOT enforced.",
    ),
    _not_a_prohibition(
        "docs/CONFIDENCE_SPECIFICATION.md:445",
        "a hazard-table row that quotes INV-8 as its authority. The rule is at "
        "SYSTEM_INVARIANTS.md:209 and is listed there; this row cites it.",
    ),
    _restates(
        "docs/DATA_FLOW.md:565",
        NOTE_RAISES_NOTHING,
        "the same sentence as ENGINE_1_INPUT_ENGINE_RULES.md:289, repeated at the "
        "provenance section of the data-flow document.",
    ),
    _restates(
        "docs/SUB_ENGINE_RESPONSIBILITIES.md:836",
        NOTE_RAISES_NOTHING,
        "the same sentence again, in the confidence sub-engine's entry.",
    ),
    # ── IDENTITY != INTELLIGENCE, restated in seven documents ─────────────
    _restates(
        "docs/DATA_FLOW.md:67",
        NO_IDENTIFIER,
        "the Document ID form of INV-9. The controls under SYSTEM_INVARIANTS:215 "
        "refuse a UUID inside supporting reasoning and inside a ledger name, "
        "which is the artifact half of 'must never influence'.",
    ),
    _restates(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:251",
        NO_IDENTIFIER,
        "the same Document ID clause, in the Input Engine's own document.",
    ),
    _restates(
        "docs/ENGINE_RESPONSIBILITIES.md:54",
        NO_IDENTIFIER,
        "the same Document ID clause, in the per-engine summary.",
    ),
    _restates(
        "docs/SYSTEM_BOUNDARIES.md:58",
        NO_IDENTIFIER,
        "the same Document ID clause, closing the assembly-ownership paragraph.",
    ),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:202",
        NO_IDENTIFIER,
        "the Clarification ID form of INV-9, and the paragraph says so — 'the "
        "system-wide IDENTITY != INTELLIGENCE rule'.",
    ),
    _restates(
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:171",
        NO_IDENTIFIER,
        "the Validation ID form of the same rule, cross-referenced to INV-9 in the line itself.",
    ),
    _restates(
        "docs/SYSTEM_INVARIANTS.md:219",
        NO_IDENTIFIER,
        "INV-9's own elaboration, four lines below the sentence SYSTEM_INVARIANTS:215 quotes.",
    ),
    # ── observation vs reasoning, restated in four documents ──────────────
    _restates(
        "docs/COMMUNICATION_RULES_INPUT_ENGINE.md:185",
        NO_CONCLUSIONS,
        "section 5 restating Rule 1 as an absolute. The rule itself is cited at "
        "line 57 of this same document.",
    ),
    _restates(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:345",
        NO_CONCLUSIONS,
        "the same sentence in the Input Engine's own document.",
    ),
    _restates(
        "docs/ENGINE_RESPONSIBILITIES.md:70",
        NO_CONCLUSIONS,
        "the same sentence in the per-engine summary.",
    ),
    _restates(
        "docs/SYSTEM_BOUNDARIES.md:62",
        NO_CONCLUSIONS,
        "the same sentence in the system-wide boundaries document.",
    ),
    # ── the request that must not be answered against a rebuilt decision ──
    _not_yet(
        "docs/DATA_FLOW.md:142",
        "the check compares a request's related_artifact_version against the "
        "decision's live version. Both values exist and both are typed; no "
        "single payload carries both, and BLUEPRINT:136 is where one run first "
        "holds a request and a decision together.",
        "P3",
    ),
    # ── Transaction ID is never part of the duplicate key ─────────────────
    _not_yet("docs/DATA_FLOW.md:290", _TRANSACTION_ID_NOT_A_KEY, "P4"),
    _not_yet("docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:410", _TRANSACTION_ID_NOT_A_KEY, "P4"),
    _not_yet("docs/SUB_ENGINE_RESPONSIBILITIES.md:672", _TRANSACTION_ID_NOT_A_KEY, "P4"),
    # ── Engine 1's nine absolute boundaries, stated in two documents ──────
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:314", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:315", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:316", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:317", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:318", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:319", _AN_INTERNAL_DECISION),
    _unwitnessable(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:320",
        "asking happens outside every artifact. The Document Evidence Object has "
        "no channel to a user and no field a question could sit in, so a run that "
        "asked and a run that did not emit the same payload.",
    ),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:321", _AN_INVENTION),
    _unwitnessable(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:322",
        "a modified value can only be seen against the unmodified one, and the "
        "artifact carries the emitted reading alone. Nothing in it is the before.",
    ),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:35", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:36", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:37", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:38", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:39", _AN_INTERNAL_DECISION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:40", _AN_INTERNAL_DECISION),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:41",
        "the same clause as ENGINE_1_INPUT_ENGINE_RULES.md:320 — asking leaves no "
        "mark on the artifact either way.",
    ),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:42", _AN_INVENTION),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:43",
        "the same clause as ENGINE_1_INPUT_ENGINE_RULES.md:322 — the artifact "
        "carries no before to compare the after against.",
    ),
    # ── the optional Human Business Description ───────────────────────────
    _restates(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:326",
        EXTRACTED_NOT_HUMAN,
        "converting the description into fact IS filing a human claim as an "
        "extracted reading, and the control under ENGINE_1:233 refuses exactly "
        "that: a detected field carrying a Human provenance.",
    ),
    _unwitnessable(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:327",
        "overriding needs the reading as it stood before the note arrived, and "
        "the artifact holds one reading, not two.",
    ),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:328", _AN_ABSENCE),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:329", _AN_ABSENCE),
    _restates(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:330",
        NOTE_RAISES_NOTHING,
        "the numbered form of ENGINE_1_INPUT_ENGINE_RULES.md:289. Review-only "
        "with expiry P3 — listed, and NOT enforced.",
    ),
    _restates(
        "docs/ENGINE_1_INPUT_ENGINE_RULES.md:331",
        "SYSTEM_INVARIANTS:258/a-human-note-is-never-rewritten",
        "the numbered form of INV-11's verbatim-capture clause. Review-only with "
        "expiry P4 — listed, and NOT enforced.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:54",
        "the six clauses on this one line split three ways: converting to fact is "
        "ENGINE_1:233, raising confidence is ENGINE_1:289 and rewriting is "
        "SYSTEM_INVARIANTS:258, all listed; overriding, removing and hiding are "
        "absences no single payload can show.",
    ),
    _unwitnessable("docs/ENGINE_1_INPUT_ENGINE_RULES.md:337", _AN_INVENTION),
    # ── Engine 2's seven boundaries, stated in two documents ──────────────
    _not_yet("docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:268", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:269", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:270", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:271", _NO_FIELD_FOR_IT_YET, "P3"),
    _unwitnessable(
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:272",
        "posting is an action against Tally, and no Business Understanding Object "
        "records whether one happened.",
    ),
    _restates(
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:273",
        IMMUTABLE,
        "the Document Evidence Object is frozen, and INV-5 is proven once per "
        "artifact including that one.",
    ),
    _restates(
        "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:274",
        UNKNOWNS_INTACT,
        "converting uncertainty into certainty IS dropping an unknown, and the "
        "control under ENGINE_2:645 refuses a Business Understanding Object whose "
        "Result raised one and whose Identified Unknowns are empty.",
    ),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:76", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:77", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:78", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:79", _NO_FIELD_FOR_IT_YET, "P3"),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:80",
        "the same clause as ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:272 — posting "
        "is an action, and no artifact records that it happened.",
    ),
    _restates(
        "docs/SYSTEM_BOUNDARIES.md:81",
        IMMUTABLE,
        "the same clause as ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:273.",
    ),
    _restates(
        "docs/SYSTEM_BOUNDARIES.md:82",
        UNKNOWNS_INTACT,
        "the same clause as ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:274.",
    ),
    # ── Engine 3's nine boundaries, stated in two documents ───────────────
    _restates(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:257",
        IMMUTABLE,
        "modifying the Document Evidence Object is refused by frozen=True, proven "
        "against that artifact by its own INV-5 control.",
    ),
    _restates(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:258",
        IMMUTABLE,
        "same, against the Business Understanding Object.",
    ),
    _unwitnessable("docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:259", _AN_INVENTION),
    _unwitnessable("docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:260", _AN_ABSENCE),
    _unwitnessable(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:261",
        "asking a user is an action outside every artifact; ENGINE_3:196 requires "
        "a stopped decision to NAME its clarification, which is the emitted half "
        "and a different claim.",
    ),
    _unwitnessable(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:262",
        "posting is an action against Tally and no Accounting Decision records "
        "whether one happened.",
    ),
    _unwitnessable(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:263",
        "overriding by EDITING a Validation Decision is refused — that artifact "
        "is frozen under SYSTEM_INVARIANTS:142. Overriding by ignoring it and "
        "emitting a decision anyway is not: the Accounting Decision that results "
        "is well formed, and which Validation Decision preceded it is not in it.",
    ),
    _restates(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:264",
        IMMUTABLE,
        "the same clause as line 257, worded as evidence rather than as the artifact's name.",
    ),
    _unwitnessable(
        "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md:265",
        "the Accounting Decision has an accounting_assumptions field; whether "
        "something that belonged in it was written as a fact instead is a "
        "judgement about the reasoning, and both payloads are well formed.",
    ),
    _restates("docs/SYSTEM_BOUNDARIES.md:115", IMMUTABLE, "the same clause as ENGINE_3:257."),
    _restates("docs/SYSTEM_BOUNDARIES.md:116", IMMUTABLE, "the same clause as ENGINE_3:258."),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:117", _AN_INVENTION),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:118", _AN_ABSENCE),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:119",
        "the same clause as ENGINE_3_ACCOUNTING_ENGINE_RULES.md:261 — asking is "
        "an action outside every artifact.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:120",
        "the same clause as ENGINE_3_ACCOUNTING_ENGINE_RULES.md:262 — posting is "
        "an action no artifact records.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:121",
        "the same clause as ENGINE_3_ACCOUNTING_ENGINE_RULES.md:263 — editing a "
        "Validation Decision is refused, ignoring one is not visible in what the "
        "Accounting Engine emits.",
    ),
    _restates("docs/SYSTEM_BOUNDARIES.md:122", IMMUTABLE, "the same clause as ENGINE_3:264."),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:123",
        "the same clause as ENGINE_3_ACCOUNTING_ENGINE_RULES.md:265 — an "
        "assumption dressed as a fact is a well-formed payload.",
    ),
    # ── Engine 4's five receiver duties ───────────────────────────────────
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:160",
        IMMUTABLE,
        "every previous artifact is frozen, and INV-5 is proven once per artifact.",
    ),
    _unwitnessable("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:161", _AN_ABSENCE),
    _unwitnessable("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:162", _AN_ABSENCE),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:163",
        "CLARIFICATION_INTERNAL:89/clarification-confidence-never-exceeds-upstream",
        "the same comparison, against the same artifact. Review-only with expiry "
        "P4, because a Clarification Request carries no upstream confidence to "
        "compare against — listed, and NOT enforced.",
    ),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:164", _NO_FIELD_FOR_IT_YET, "P3"),
    # ── Engine 4's fifteen boundaries, stated in two documents ────────────
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:222", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:223", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:224", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:225", _NO_FIELD_FOR_IT_YET, "P3"),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:226",
        IMMUTABLE,
        "the Document Evidence Object is frozen.",
    ),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:227",
        IMMUTABLE,
        "the Business Understanding Object is frozen.",
    ),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:228",
        IMMUTABLE,
        "the Accounting Decision is frozen.",
    ),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:229", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:230", _NO_FIELD_FOR_IT_YET, "P3"),
    _unwitnessable("docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:231", _AN_INVENTION),
    _restates(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:232",
        NO_RESOLUTION,
        "the Conflict object is the same carrier whoever writes it, and the "
        "control under SYSTEM_BOUNDARIES:95 refuses one that names a resolution.",
    ),
    _unwitnessable(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:233",
        "an assumption written as a fact is a well-formed Clarification Request; "
        "which of the two the author meant is not in the payload.",
    ),
    _unwitnessable(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:234",
        "for this engine the conversion shows up as a request that was never "
        "raised, and a run that raised nothing emits nothing to inspect.",
    ),
    _unwitnessable(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:235",
        "asking is an action outside every artifact.",
    ),
    _unwitnessable(
        "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md:236",
        "bypassing is a routing property of the Application Layer's state "
        "machine; the artifacts a bypassed run produces are individually valid.",
    ),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:164", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:165", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:166", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:167", _NO_FIELD_FOR_IT_YET, "P3"),
    _restates("docs/SYSTEM_BOUNDARIES.md:168", IMMUTABLE, "the same clause as ENGINE_4:226."),
    _restates("docs/SYSTEM_BOUNDARIES.md:169", IMMUTABLE, "the same clause as ENGINE_4:227."),
    _restates("docs/SYSTEM_BOUNDARIES.md:170", IMMUTABLE, "the same clause as ENGINE_4:228."),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:171", _NO_FIELD_FOR_IT_YET, "P3"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:172", _NO_FIELD_FOR_IT_YET, "P3"),
    _unwitnessable("docs/SYSTEM_BOUNDARIES.md:173", _AN_INVENTION),
    _restates(
        "docs/SYSTEM_BOUNDARIES.md:174",
        NO_RESOLUTION,
        "the same clause as ENGINE_4_CLARIFICATION_ENGINE_RULES.md:232.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:175",
        "the same clause as ENGINE_4_CLARIFICATION_ENGINE_RULES.md:233.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:176",
        "the same clause as ENGINE_4_CLARIFICATION_ENGINE_RULES.md:234.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:177",
        "the same clause as ENGINE_4_CLARIFICATION_ENGINE_RULES.md:235.",
    ),
    _unwitnessable(
        "docs/SYSTEM_BOUNDARIES.md:178",
        "the same clause as ENGINE_4_CLARIFICATION_ENGINE_RULES.md:236.",
    ),
    # ── Engine 5 ──────────────────────────────────────────────────────────
    _unwitnessable(
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:161",
        "a downgrade can only be seen against the severity the finding started "
        "with, and a Validation Finding carries one Severity and no history of it.",
    ),
    _not_yet("docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:201", _INV_8, "P4"),
    _unwitnessable(
        "docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:209",
        "eighteen clauses on one line. 'Repair accounting mistakes' is "
        "ENGINE_5:215 and every 'modify' is SYSTEM_INVARIANTS:142, both enforced; "
        "the remainder — inventing facts, inventing confidence, asking users, "
        "bypassing an engine — are inventions, absences and actions, none of "
        "which a single well-formed payload distinguishes.",
    ),
    # ── Engine 6 ──────────────────────────────────────────────────────────
    _not_a_prohibition(
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:73",
        "the header row of the may/must-never table — two column names, no rule. "
        "The rows beneath it are prose pairs, not list items, so they are not "
        "scanned; the same clauses are stated as a list at line 241.",
    ),
    _not_yet("docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:82", _POSTING_NEVER_REWRITES, "P4"),
    _restates(
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:138",
        IMMUTABLE,
        "every upstream artifact is frozen, and INV-5 is proven once per artifact.",
    ),
    _unwitnessable(
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:241",
        "sixteen clauses on one line. Accounting reasoning inside an Execution "
        "Result is SYSTEM_BOUNDARIES:279, correcting itself is ENGINE_6:210 and "
        "every 'modify' is SYSTEM_INVARIANTS:142, all enforced; suppressing a "
        "failure, deleting history and bypassing Validation are absences and "
        "actions that leave the emitted artifact well formed.",
    ),
    _not_yet(
        "docs/ENGINE_6_EXECUTION_ENGINE_RULES.md:541",
        "the mechanism is the Execution Queue (EXECUTION_QUEUE.md), and the check "
        "is that a failed posting leaves a queued item rather than nothing. It "
        "needs a real destination that can fail, which BLUEPRINT:137 first "
        "provides at P4.",
        "P4",
    ),
    _not_yet("docs/ENGINE_RESPONSIBILITIES.md:320", _POSTING_NEVER_REWRITES, "P4"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:248", _POSTING_NEVER_REWRITES, "P4"),
    # ── INV-8, permission decided before execution ────────────────────────
    _not_yet("docs/SYSTEM_INVARIANTS.md:209", _INV_8, "P4"),
    _not_yet("docs/SUB_ENGINE_RESPONSIBILITIES.md:612", _INV_8, "P4"),
    _not_yet("docs/SYSTEM_BOUNDARIES.md:280", _INV_8, "P4"),
    _not_a_prohibition(
        "docs/FORWARD_DEPENDENCY_INVENTORY.md:34",
        "a row in the forward-dependency ledger recording that INV-8's promise "
        "was honoured and who owns it. The rule is at SYSTEM_INVARIANTS.md:209.",
    ),
    # ── the rest ──────────────────────────────────────────────────────────
    _not_yet(
        "docs/EVIDENCE_ARCHITECTURE.md:84",
        "witnessable today: parse the same bytes under two file names and compare "
        "the two Document Evidence Objects. Engine 1 exists, so this needs no new "
        "engine — only the test, which nobody has written.",
        "P3",
    ),
    _not_yet(
        "docs/EXECUTION_QUEUE.md:130",
        "'incorrect' is defined in ACCOUNTING_DEFINITIONS.md against a human "
        "ceiling, and no ceiling exists yet (CLAUDE.md section P). The measurement "
        "is the held-out evaluation BLUEPRINT:138 runs at P5.",
        "P5",
    ),
    _unwitnessable(
        "docs/MVP_ARCHITECTURE.md:49",
        "the artifact half — an Execution Result that records accounting — is "
        "SYSTEM_BOUNDARIES:279, enforced. Whether a reader CONFUSED a transport "
        "failure with an accounting error is a property of the reader.",
    ),
    _not_a_prohibition(
        "docs/MVP_BUILD_VERIFY_FIX.md:82",
        "the requirement this module exists to satisfy, not a rule about an "
        "artifact. Citing it as a prohibition would have the inventory list itself.",
    ),
    _not_a_prohibition(
        "docs/MVP_IMPLEMENTATION_BLUEPRINT.md:135",
        "P2's definition of done, which names this inventory. Same reason as "
        "MVP_BUILD_VERIFY_FIX.md:82 — a requirement on the check, not a rule for "
        "it to check.",
    ),
)

#: The inventory and its proof, built at import. `Registry` refuses a duplicate
#: identifier, a control for an unlisted rule, a control against a review-only
#: rule, a line that is both cited and excluded, and an exclusion that claims to
#: be restating a rule nobody wrote down — so an inconsistent inventory fails on
#: import rather than reporting a comfortable number.
REGISTRY = Registry(PROHIBITIONS, CONTROLS, EXCLUSIONS)
