"""The Clarification Request — written before the schema it tests.

Every test names the document line it defends, and every test is written to
BREAK the schema rather than to confirm it. The dangerous direction here is
always the permissive one: a schema that accepts a request with no evidence
reference, or that lets `Open` jump straight to `Resolved`, produces a cleaner
pipeline than the honest version — which is exactly why those are the cases
asserted hardest.

Three failures are structurally impossible if these pass:

  a request that carries the answer      extra="forbid" refuses the field
  a question that went silently unasked  Open -> Resolved is not a transition
  a finding with no evidence behind it   supporting evidence is min_length 1
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.clarification import (
    PERMITTED_TRANSITIONS,
    TERMINAL_STATUSES,
    ClarificationPriority,
    ClarificationRequest,
    ClarificationStatus,
    may_transition,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

FIRST_VERSION = 1
SECOND_VERSION = 2
DECISION_VERSION = 3

#: The status set the owner ruled on. Spelled here independently of the module
#: so the module cannot silently redefine it and stay green.
RULED_STATUS_VALUES = frozenset(
    {"Created", "Open", "Answered", "Resolved", "Superseded", "Cancelled"}
)

#: What DATA_FLOW.md:138-139, ENGINE_4:261-266 and
#: COMMUNICATION_RULES_CLARIFICATION_ENGINE.md:64 carry. Five values, no
#: `Created`. The owner's ruling overrides all three.
DOCUMENTED_FIVE_STATUS_VALUES = frozenset(
    {"Open", "Answered", "Resolved", "Superseded", "Cancelled"}
)

#: ENGINE_4:182 and ENGINE_4:520.
RULED_PRIORITY_VALUES = frozenset({"Critical", "High", "Medium", "Low"})

BLANK = ["", " ", "   ", "\t", "\n", " \t\n "]


def envelope(**overrides: object) -> IdentityEnvelope:
    base: dict[str, object] = {
        "artifact_id": ArtifactId.new(),
        "version": FIRST_VERSION,
        "parent_versions": (),
        "transaction_id": TransactionId.new(),
    }
    base.update(overrides)
    return IdentityEnvelope(**base)  # type: ignore[arg-type]


def request(**overrides: object) -> ClarificationRequest:
    base: dict[str, object] = {
        "identity": envelope(),
        "clarification_id": ArtifactId.new(),
        "related_decision_id": ArtifactId.new(),
        "related_artifact_version": DECISION_VERSION,
        "missing_information": ("The supplier's GSTIN is absent from the invoice.",),
        "detected_conflicts": ("The invoice total and the line-item sum disagree.",),
        "required_clarification": "Which figure is the agreed invoice total?",
        "reason_clarification_is_required": (
            "Two irreconcilable totals cannot both be posted, and neither may be chosen here."
        ),
        "affected_decision": "The purchase invoice booking for this transaction.",
        "priority": ClarificationPriority.CRITICAL,
        "supporting_evidence_references": ("invoice.pdf#page=1/field=total",),
        "clarification_confidence": Decimal("0.7200"),
        "status": ClarificationStatus.CREATED,
    }
    base.update(overrides)
    return ClarificationRequest(**base)  # type: ignore[arg-type]


# ── The status set — the owner's ruling, which overrides three documents ─────


def test_the_status_set_is_exactly_the_six_values_the_owner_ruled() -> None:
    assert {member.value for member in ClarificationStatus} == set(RULED_STATUS_VALUES)


def test_created_is_present_although_three_documents_omit_it() -> None:
    # DATA_FLOW.md:138-139, ENGINE_4:261-266 and
    # COMMUNICATION_RULES_CLARIFICATION_ENGINE.md:64 all carry five values and
    # no `Created`. The owner ruled six. Without this test the schema could
    # drift back to the documented five and every other test would still pass.
    assert ClarificationStatus.CREATED.value == "Created"


def test_the_documented_five_are_a_strict_subset_of_what_is_implemented() -> None:
    implemented = {member.value for member in ClarificationStatus}
    assert implemented > DOCUMENTED_FIVE_STATUS_VALUES


@pytest.mark.parametrize(
    "bad",
    ["Withdrawn", "open", "OPEN", "Open ", " Open", "Pending", "Closed", "", "Resolved."],
)
def test_an_unrecognised_status_is_rejected(bad: str) -> None:
    # A status the engine does not own is a state nothing tracks. Validation
    # reads status first (COMM_CLARIFICATION_ENGINE:69-76); an unknown value
    # there is an unreadable blocking condition.
    with pytest.raises(ValidationError):
        request(status=bad)


def test_the_status_is_stored_as_the_enum_not_a_bare_string() -> None:
    assert isinstance(request(status="Open").status, ClarificationStatus)


# ── Priority — ENGINE_4:182, ENGINE_4:520 ────────────────────────────────────


def test_the_priority_set_is_exactly_the_four_engine_4_enumerates() -> None:
    assert {member.value for member in ClarificationPriority} == set(RULED_PRIORITY_VALUES)


@pytest.mark.parametrize("bad", ["Urgent", "critical", "CRITICAL", "Highest", "None", "", "1"])
def test_an_unrecognised_priority_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        request(priority=bad)


def test_the_priority_is_stored_as_the_enum_not_a_bare_string() -> None:
    assert isinstance(request(priority="Low").priority, ClarificationPriority)


# ── The §7 state machine ─────────────────────────────────────────────────────


def test_the_three_terminal_states_have_no_successor() -> None:
    # ENGINE_4:277 — "Resolved, Superseded and Cancelled are terminal."
    assert (
        frozenset(
            {
                ClarificationStatus.RESOLVED,
                ClarificationStatus.SUPERSEDED,
                ClarificationStatus.CANCELLED,
            }
        )
        == TERMINAL_STATUSES
    )
    for terminal in TERMINAL_STATUSES:
        assert PERMITTED_TRANSITIONS[terminal] == frozenset()


def test_open_may_never_go_straight_to_resolved() -> None:
    # ENGINE_4:279 — "Nothing may go from Open straight to Resolved."
    # ENGINE_4:281 — collapsing Superseded into Resolved "would hide the fact
    # that a question went unanswered." This is the single most expensive
    # permissive bug available in this state machine.
    assert not may_transition(ClarificationStatus.OPEN, ClarificationStatus.RESOLVED)


def test_resolution_is_reachable_only_through_answered() -> None:
    reaching_resolved = {
        state
        for state, allowed in PERMITTED_TRANSITIONS.items()
        if ClarificationStatus.RESOLVED in allowed
    }
    assert reaching_resolved == {ClarificationStatus.ANSWERED}


def test_answered_reaches_resolved() -> None:
    assert may_transition(ClarificationStatus.ANSWERED, ClarificationStatus.RESOLVED)


@pytest.mark.parametrize(
    "state",
    [ClarificationStatus.CREATED, ClarificationStatus.OPEN, ClarificationStatus.ANSWERED],
)
def test_superseded_and_cancelled_are_reachable_from_every_non_terminal_state(
    state: ClarificationStatus,
) -> None:
    # ENGINE_4:278 — "Superseded and Cancelled may be entered from any state."
    assert may_transition(state, ClarificationStatus.SUPERSEDED)
    assert may_transition(state, ClarificationStatus.CANCELLED)


def test_created_precedes_open() -> None:
    # COMM_CLARIFICATION_INTERNAL:148 — Created when question_generator
    # assembles the Request; :149 — Open once it is handed to the external
    # actor. Presentation is the transition.
    assert may_transition(ClarificationStatus.CREATED, ClarificationStatus.OPEN)


def test_a_request_cannot_be_answered_before_it_has_been_presented() -> None:
    # Created means "record created, not yet presented". An answer to a
    # question nobody was shown is an answer the system invented.
    assert not may_transition(ClarificationStatus.CREATED, ClarificationStatus.ANSWERED)


def test_a_request_cannot_be_resolved_before_it_has_been_presented() -> None:
    assert not may_transition(ClarificationStatus.CREATED, ClarificationStatus.RESOLVED)


def test_open_does_not_go_back_to_created() -> None:
    assert not may_transition(ClarificationStatus.OPEN, ClarificationStatus.CREATED)


def test_nothing_transitions_back_into_created() -> None:
    # Creation happens once. A path back into Created would let a request be
    # un-presented, and the audit trail would show a question that was asked
    # and then never asked.
    for allowed in PERMITTED_TRANSITIONS.values():
        assert ClarificationStatus.CREATED not in allowed


@pytest.mark.parametrize("state", list(ClarificationStatus))
def test_no_state_transitions_to_itself(state: ClarificationStatus) -> None:
    # ENGINE_4:270-275 lists the permitted transitions exhaustively and none is
    # a self-loop. A self-transition would be a status change that changed
    # nothing while producing a new version and a new audit entry.
    assert not may_transition(state, state)


def test_the_transition_table_covers_every_status_and_names_only_known_ones() -> None:
    assert set(PERMITTED_TRANSITIONS) == set(ClarificationStatus)
    for allowed in PERMITTED_TRANSITIONS.values():
        assert allowed <= set(ClarificationStatus)


def test_the_transition_table_cannot_be_extended_at_runtime() -> None:
    # A module-level dict is editable by any importer. The state machine is a
    # transcription of a locked document; it is not a runtime setting.
    with pytest.raises(TypeError):
        PERMITTED_TRANSITIONS[ClarificationStatus.RESOLVED] = frozenset(  # type: ignore[index]
            {ClarificationStatus.OPEN}
        )


# ── The twelve components (ENGINE_4:172-186, DATA_FLOW.md:40) ────────────────


def test_a_request_carries_every_component_the_specification_lists() -> None:
    clarification_id = ArtifactId.new()
    decision_id = ArtifactId.new()
    identity = envelope()
    made = ClarificationRequest(
        identity=identity,
        clarification_id=clarification_id,
        related_decision_id=decision_id,
        related_artifact_version=DECISION_VERSION,
        missing_information=("The place of supply is not stated.",),
        detected_conflicts=("The stated date precedes the purchase order.",),
        required_clarification="What is the place of supply?",
        reason_clarification_is_required="GST treatment depends on it and it is absent.",
        affected_decision="The GST treatment of this purchase.",
        priority=ClarificationPriority.HIGH,
        supporting_evidence_references=("invoice.pdf#page=1", "po.pdf#page=1"),
        clarification_confidence=Decimal("0.6100"),
        status=ClarificationStatus.OPEN,
    )

    assert made.identity == identity
    assert made.clarification_id == clarification_id
    assert made.related_decision_id == decision_id
    assert made.related_artifact_version == DECISION_VERSION
    assert made.missing_information == ("The place of supply is not stated.",)
    assert made.detected_conflicts == ("The stated date precedes the purchase order.",)
    assert made.required_clarification == "What is the place of supply?"
    assert made.reason_clarification_is_required == "GST treatment depends on it and it is absent."
    assert made.affected_decision == "The GST treatment of this purchase."
    assert made.priority is ClarificationPriority.HIGH
    assert made.supporting_evidence_references == ("invoice.pdf#page=1", "po.pdf#page=1")
    assert made.clarification_confidence == Decimal("0.6100")
    assert made.status is ClarificationStatus.OPEN


def test_a_missing_component_is_rejected_rather_than_defaulted() -> None:
    # "Gaps stay gaps. An absent fact is marked absent until supplied. No
    # defaults" — SYSTEM_INVARIANTS.md:295. A defaulted component would be an
    # assertion the engine never made.
    for absent in ClarificationRequest.model_fields:
        supplied = {name: value for name, value in _valid_payload().items() if name != absent}
        with pytest.raises(ValidationError):
            ClarificationRequest(**supplied)  # type: ignore[arg-type]


def _valid_payload() -> dict[str, object]:
    return {
        "identity": envelope(),
        "clarification_id": ArtifactId.new(),
        "related_decision_id": ArtifactId.new(),
        "related_artifact_version": DECISION_VERSION,
        "missing_information": (),
        "detected_conflicts": (),
        "required_clarification": "What is the place of supply?",
        "reason_clarification_is_required": "GST treatment depends on it.",
        "affected_decision": "The GST treatment of this purchase.",
        "priority": ClarificationPriority.LOW,
        "supporting_evidence_references": ("invoice.pdf#page=1",),
        "clarification_confidence": Decimal("0.5"),
        "status": ClarificationStatus.CREATED,
    }


def test_the_collections_are_tuples_not_lists() -> None:
    # A list would let a caller append a finding to a frozen artifact and
    # `frozen=True` would not see it — the model immutable, its content not.
    made = request(
        missing_information=["a"],
        detected_conflicts=["b"],
        supporting_evidence_references=["c"],
    )
    assert isinstance(made.missing_information, tuple)
    assert isinstance(made.detected_conflicts, tuple)
    assert isinstance(made.supporting_evidence_references, tuple)


# ── INV-5 — history is never modified ────────────────────────────────────────


def test_a_request_cannot_be_mutated_after_creation() -> None:
    made = request()
    with pytest.raises(ValidationError):
        made.required_clarification = "something else"


def test_the_status_cannot_be_reassigned_in_place() -> None:
    # A transition is a new version, never an edit — ENGINE_4:210,
    # DATA_FLOW.md:486. In-place status assignment is the single edit that
    # would look most reasonable and destroy the audit trail most completely.
    made = request(status=ClarificationStatus.OPEN)
    with pytest.raises(ValidationError):
        made.status = ClarificationStatus.RESOLVED


def test_a_finding_cannot_be_appended_after_creation() -> None:
    made = request()
    with pytest.raises(AttributeError):
        made.missing_information.append("late addition")  # type: ignore[attr-defined]


# ── ENGINE_4:43, :231, :247 — it never resolves and never guesses ────────────


@pytest.mark.parametrize(
    "field",
    ["answer", "clarification_answer", "resolved_value", "suggested_answer", "resolution"],
)
def test_an_answer_cannot_be_attached_to_the_request(field: str) -> None:
    # DATA_FLOW.md:42 — a Clarification Answer "never returns to Engine 4; the
    # responsible upstream engine emits a new artifact version." There is no
    # field for an answer, and extra="forbid" is what makes that structural
    # rather than a naming convention.
    with pytest.raises(ValidationError):
        request(**{field: "18% IGST"})


@pytest.mark.parametrize(
    "field",
    ["ledger", "journal_entries", "debit_entries", "tax_treatment", "accounting_treatment"],
)
def test_an_accounting_field_cannot_be_attached_to_the_request(field: str) -> None:
    # ENGINE_4:222-225 — the Clarification Engine may never create journal
    # entries, choose ledgers, or decide accounting or tax treatment.
    with pytest.raises(ValidationError):
        request(**{field: "Purchases"})


def test_an_unknown_field_is_rejected_rather_than_ignored() -> None:
    with pytest.raises(ValidationError):
        request(clarifcation_confidence=Decimal("0.9"))


# ── INV-3 / INV-9 — identity is typed, opaque, and carries no meaning ────────


@pytest.mark.parametrize("field", ["clarification_id", "related_decision_id"])
def test_a_bare_uuid_is_not_accepted_where_a_typed_identifier_belongs(field: str) -> None:
    with pytest.raises(ValidationError):
        request(**{field: uuid.uuid4()})


@pytest.mark.parametrize("field", ["clarification_id", "related_decision_id"])
def test_a_string_is_not_accepted_where_a_typed_identifier_belongs(field: str) -> None:
    with pytest.raises(ValidationError):
        request(**{field: "CLR-000123"})


def test_a_transaction_id_is_not_accepted_where_an_artifact_id_belongs() -> None:
    # INV-3 — three concepts, three types. Same underlying UUID, different job.
    shared = uuid.uuid4()
    with pytest.raises(ValidationError):
        request(clarification_id=TransactionId(shared))


def test_the_request_carries_exactly_one_transaction_id_verbatim() -> None:
    shared = TransactionId.new()
    assert request(identity=envelope(transaction_id=shared)).identity.transaction_id == shared


def test_two_requests_differing_only_in_identifiers_carry_identical_bodies() -> None:
    # INV-9 — IDs identify objects, they do not influence reasoning. If any
    # component were derived from an identifier, these two would differ.
    body_fields = set(ClarificationRequest.model_fields) - {
        "identity",
        "clarification_id",
        "related_decision_id",
    }
    payload = _valid_payload()
    # Through `request`, whose signature is `**overrides: object`, so a
    # `dict[str, object]` unpacks cleanly. Calling the model constructor
    # directly needs a blanket arg-type ignore per field, which would suppress
    # exactly the kind of mistake this test exists to catch.
    first = request(**payload)
    # Merged, not passed alongside: `payload` already carries these three keys,
    # and passing both raises TypeError before any assertion could run.
    swapped: dict[str, object] = {
        **payload,
        "identity": envelope(),
        "clarification_id": ArtifactId.new(),
        "related_decision_id": ArtifactId.new(),
    }
    second = request(**swapped)

    assert first.clarification_id != second.clarification_id
    for name in body_fields:
        assert getattr(first, name) == getattr(second, name)


def test_a_second_version_of_a_request_must_record_the_parent_it_derived_from() -> None:
    # Proves the identity envelope is embedded rather than re-implemented: the
    # lineage rule enforced in identity.py has to reach through this artifact.
    with pytest.raises(ValidationError):
        request(identity=envelope(version=SECOND_VERSION, parent_versions=()))


def test_a_second_version_with_its_parent_recorded_is_accepted() -> None:
    same = ArtifactId.new()
    made = request(
        identity=envelope(
            artifact_id=same,
            version=SECOND_VERSION,
            parent_versions=(ParentVersion(artifact_id=same, version=FIRST_VERSION),),
        )
    )
    assert made.identity.parent_versions[0].version == FIRST_VERSION


# ── Related Artifact Version — ENGINE_4:196-198, DATA_FLOW.md:142 ────────────


def test_the_related_artifact_version_is_recorded_exactly() -> None:
    # It is what makes a stale request detectable. A request raised against
    # decision v3 is Superseded the moment v4 exists.
    assert request(related_artifact_version=DECISION_VERSION).related_artifact_version == (
        DECISION_VERSION
    )


@pytest.mark.parametrize("bad", [0, -1, -100])
def test_a_related_artifact_version_below_one_is_rejected(bad: int) -> None:
    # Versions start at 1. A version 0 makes "raised against nothing"
    # indistinguishable from "raised against the origin".
    with pytest.raises(ValidationError):
        request(related_artifact_version=bad)


def test_a_non_integer_related_artifact_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        request(related_artifact_version="3")


# ── INV-2 — the one Confidence representation, imported, never redefined ─────


def test_confidence_must_be_a_decimal_not_a_float() -> None:
    # The message is confidence.py's own. If this module had defined a local
    # confidence type, this assertion would not match — which is the point.
    with pytest.raises(ValidationError) as caught:
        request(clarification_confidence=0.72)
    assert "float and int are refused rather than converted" in str(caught.value)


@pytest.mark.parametrize("bad", [Decimal("-0.0001"), Decimal("1.0001"), Decimal("2")])
def test_confidence_outside_the_agreed_range_is_rejected(bad: Decimal) -> None:
    with pytest.raises(ValidationError):
        request(clarification_confidence=bad)


def test_confidence_beyond_the_agreed_four_places_is_rejected() -> None:
    with pytest.raises(ValidationError) as caught:
        request(clarification_confidence=Decimal("0.72001"))
    assert "the agreed scale is 4" in str(caught.value)


def test_confidence_is_stored_verbatim_and_not_rescaled() -> None:
    assert str(request(clarification_confidence=Decimal("0.5")).clarification_confidence) == "0.5"


def test_a_non_finite_confidence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        request(clarification_confidence=Decimal("NaN"))


# ── COMM_CLARIFICATION_INTERNAL:83-87 — no Result omits evidence references ──


def test_a_request_with_no_supporting_evidence_reference_is_rejected() -> None:
    # "A finding with no evidence reference cannot appear in a Result. There is
    # no mechanism for producing one, and that is deliberate: it is the
    # structural reason this engine cannot invent uncertainty."
    # question_generator publishes the Clarification Request as its Result
    # (COMM_CLARIFICATION_INTERNAL:78), so the rule binds this artifact.
    with pytest.raises(ValidationError):
        request(supporting_evidence_references=())


@pytest.mark.parametrize("blank", BLANK)
def test_a_blank_supporting_evidence_reference_is_rejected(blank: str) -> None:
    # An empty string satisfies "at least one reference" while pointing at
    # nothing. That is the cheapest way past the rule above.
    with pytest.raises(ValidationError):
        request(supporting_evidence_references=(blank,))


# ── ENGINE_4:188-194 — every request must actually answer five questions ─────


@pytest.mark.parametrize("blank", BLANK)
def test_a_blank_required_clarification_is_rejected(blank: str) -> None:
    with pytest.raises(ValidationError):
        request(required_clarification=blank)


@pytest.mark.parametrize("blank", BLANK)
def test_a_blank_reason_is_rejected(blank: str) -> None:
    with pytest.raises(ValidationError):
        request(reason_clarification_is_required=blank)


@pytest.mark.parametrize("blank", BLANK)
def test_a_blank_affected_decision_is_rejected(blank: str) -> None:
    with pytest.raises(ValidationError):
        request(affected_decision=blank)


@pytest.mark.parametrize("field", ["missing_information", "detected_conflicts"])
def test_a_blank_entry_in_a_finding_collection_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        request(**{field: ("a real finding", "  ")})


def test_text_is_stored_verbatim_and_never_stripped() -> None:
    # An artifact records what its producer asserted. Silently rewriting a
    # value is the same class of falsification confidence.py refuses.
    assert request(affected_decision="  the purchase booking  ").affected_decision == (
        "  the purchase booking  "
    )


def test_a_non_string_finding_is_rejected() -> None:
    with pytest.raises(ValidationError):
        request(missing_information=(42,))


# ── Documented silences — kept open on purpose ───────────────────────────────


def test_missing_information_and_detected_conflicts_may_both_be_empty() -> None:
    # No document states that a request must carry at least one of these. A
    # request driven purely by uncertainty severity (uncertainty_detection,
    # ENGINE_4:417-441) carries neither, and the Request has no uncertainty
    # field to put it in. Adding a constraint the documents never state would
    # be inventing one. This test pins the absence so a future change is a
    # visible decision rather than a quiet tightening.
    made = request(missing_information=(), detected_conflicts=())
    assert made.missing_information == ()
    assert made.detected_conflicts == ()
