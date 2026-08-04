"""The inventory, attacked.

`test_conformance.py` proves the HARNESS cannot report a pass it did not earn.
This file asks the next question: is the inventory the harness runs actually
about the documents it claims to be about, and does every control really reach
the rule it names?

Three things are checked here that nothing else in the repository checks:

  THE CLEAN HALF RUNS. Every control's clean payload is constructed against the
  real frozen schema. A control whose clean half fails is `CONTROL_INVALID` and
  is NOT a pass — the payload died of some other defect and the rule under test
  was never reached. A suite of those is all green and worth nothing.

  THE CITATIONS STILL READ THE WAY THEY ARE QUOTED. Every `source` is opened,
  the line is read, and the `quote` must appear in it verbatim. A comment
  cannot catch a citation that drifted when somebody edited a spec; only
  reading the file can. The check is itself mutation-proven below — a citation
  moved by one line must be rejected, or the check is decoration.

  THE COUNTS ARE WRITTEN DOWN. Predicates, review-only entries and controls are
  asserted as explicit numbers. Deleting a control is otherwise the cheapest
  way to make this suite green, and it would leave no trace at all.

These tests may read files. `conformance_registry` itself may not — see its
module docstring on why the payloads carry no clock and no randomness.
"""

from __future__ import annotations

import dataclasses
import pathlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError, create_model

import accountant_dad
from accountant_dad.artifacts.decision import DecisionStatus
from accountant_dad.artifacts.evidence import Corroborated, DocumentId, SourceType
from accountant_dad.artifacts.execution import ExecutionAttemptId, ExecutionId
from accountant_dad.conformance import (
    PHASES,
    Attribution,
    Enforcement,
    NegativeControl,
    Prohibition,
    Registry,
    attribute,
)
from accountant_dad.conformance_registry import (
    CONTROLS,
    IMMUTABLE,
    PROHIBITIONS,
    REGISTRY,
    _clarification,
    _confidence_report,
    _conflict,
    _decision,
    _detected_field,
    _doubt,
    _envelope,
    _evidence,
    _execution,
    _fact,
    _finding,
    _incomplete_decision,
    _journal_line,
    _mutate,
    _predicate,
    _provenance,
    _results,
    _results_raising_an_unknown,
    _results_with_a_less_certain_one,
    _review_only,
    _structured_document,
    _understanding,
    _unknown,
    _uuid,
    _validation,
)
from accountant_dad.identity import ArtifactId, TransactionId

#: Explicit, so a silent deletion is a red test rather than a smaller number
#: nobody notices. Raising these is normal; lowering one is a claim that a rule
#: stopped needing proof, and that claim has to be made out loud.
PREDICATE_COUNT = 33
REVIEW_ONLY_COUNT = 7
CONTROL_COUNT = 43

#: `DATA_FLOW.md` §2 — six canonical artifacts, six proofs of immutability.
CANONICAL_ARTIFACTS = frozenset(
    {
        "DocumentEvidenceObject",
        "BusinessUnderstandingObject",
        "AccountingDecision",
        "ClarificationRequest",
        "ValidationDecision",
        "ExecutionResult",
    }
)

#: A quote shorter than this cannot identify a sentence. `"the"` appears on
#: every page, so a citation built from it would pass the disk check while
#: pointing at nothing in particular.
SHORTEST_USEFUL_QUOTE = 20

_REPO_ROOT = pathlib.Path(str(accountant_dad.__file__)).parent.parent.parent


def _line(source: str) -> str:
    """The one line `source` names, read off disk. `path:line`, 1-based."""
    path, _, number = source.rpartition(":")
    body = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    return body[int(number) - 1]


def _quotes_its_source(prohibition: Prohibition) -> bool:
    return prohibition.quote in _line(prohibition.source)


def _identify(prohibition: Prohibition) -> str:
    return prohibition.identifier


# ── the two conditions P2 is done under ───────────────────────────────────


def test_every_predicate_has_a_negative_control() -> None:
    """`BLUEPRINT:135` — every `MUST NEVER` is a predicate or on the review-only
    list. A rule declared enforced with nothing exercising it is a claim, not an
    enforcement, and it is indistinguishable from an enforced one until someone
    deletes the code."""
    assert REGISTRY.untested_predicates() == ()


def test_no_control_is_a_false_green() -> None:
    """Every control ENFORCED. Not NOT_ENFORCED, and not CONTROL_INVALID.

    The second is the one that matters. `CONTROL_INVALID` means the clean
    payload was refused too, so the violating payload's rejection cannot be
    attributed to the rule under test — the control looked green and proved
    nothing about the schema.
    """
    reported = [
        f"{finding.prohibition}: {finding.attribution.value} — {finding.detail}"
        for finding in REGISTRY.failures()
    ]
    assert reported == []


@pytest.mark.parametrize("control", CONTROLS, ids=lambda control: control.prohibition)
def test_each_control_reaches_the_rule_it_names(control: NegativeControl) -> None:
    """Per control, so a failure names the rule instead of a count."""
    finding = attribute(control)
    assert finding.attribution is Attribution.ENFORCED, finding.detail


# ── the citations, read off disk ──────────────────────────────────────────


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_quote_is_still_on_the_line_it_cites(prohibition: Prohibition) -> None:
    """A citation that drifted from its document is a lie a comment cannot catch.

    Verbatim substring, not a fuzzy match: a quote that has to be normalised to
    match is a quote that has already started to diverge.
    """
    assert _quotes_its_source(prohibition), (
        f"{prohibition.identifier} quotes {prohibition.quote!r}, but "
        f"{prohibition.source} now reads {_line(prohibition.source)!r}"
    )


def test_the_citation_check_notices_a_line_that_drifted() -> None:
    """Mutation proof for the test above. Without this, a check that always
    returned True would pass the whole suite and prove nothing about any
    document."""
    real = next(item for item in PROHIBITIONS if item.identifier == IMMUTABLE)
    assert _quotes_its_source(real)

    path, _, number = real.source.rpartition(":")
    moved = dataclasses.replace(real, source=f"{path}:{int(number) + 1}")
    assert not _quotes_its_source(moved)


def test_the_citation_check_notices_a_quote_that_was_never_there() -> None:
    """The other direction: right line, invented sentence."""
    real = next(item for item in PROHIBITIONS if item.identifier == IMMUTABLE)
    invented = dataclasses.replace(real, quote="Artifacts may be edited in place when convenient.")
    assert not _quotes_its_source(invented)


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_source_names_a_line_in_a_document_that_exists(prohibition: Prohibition) -> None:
    path, _, number = prohibition.source.rpartition(":")
    assert path.startswith("docs/"), f"{prohibition.identifier} cites {path}, outside docs/"
    assert (_REPO_ROOT / path).is_file(), f"{prohibition.identifier} cites a missing file: {path}"
    assert int(number) >= 1


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_every_quote_is_long_enough_to_identify_a_sentence(prohibition: Prohibition) -> None:
    assert len(prohibition.quote) >= SHORTEST_USEFUL_QUOTE


@pytest.mark.parametrize("prohibition", PROHIBITIONS, ids=_identify)
def test_the_identifier_carries_the_line_its_source_names(prohibition: Prohibition) -> None:
    """`DOC:LINE/slug`. The line is in both halves so a finding names the exact
    sentence, and so the two cannot drift apart silently."""
    path, _, number = prohibition.source.rpartition(":")
    document = path.removeprefix("docs/").removesuffix(".md")
    cited, separator, slug = prohibition.identifier.partition("/")
    assert separator == "/", f"{prohibition.identifier} has no slug"
    assert slug, f"{prohibition.identifier} has an empty slug"
    assert cited.endswith(f":{number}"), f"{prohibition.identifier} does not name line {number}"
    # The identifier abbreviates the filename (`ENGINE_1`, not
    # `ENGINE_1_INPUT_ENGINE_RULES`); it may shorten the name, never change it.
    assert cited.rpartition(":")[0] in document


def test_no_two_prohibitions_cite_the_same_line() -> None:
    """One line, one rule. Two entries on one sentence is the same prohibition
    counted twice, which inflates coverage without adding any."""
    sources = [item.source for item in PROHIBITIONS]
    assert sorted(sources) == sorted(set(sources))


# ── the counts, written down ──────────────────────────────────────────────


def test_the_inventory_holds_exactly_this_many_predicates() -> None:
    assert len(REGISTRY.by_enforcement(Enforcement.PREDICATE)) == PREDICATE_COUNT


def test_the_inventory_holds_exactly_this_many_review_only_entries() -> None:
    assert len(REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY)) == REVIEW_ONLY_COUNT


def test_the_inventory_holds_exactly_this_many_controls() -> None:
    assert len(REGISTRY.controls) == CONTROL_COUNT


def test_the_prohibitions_are_only_ever_predicates_or_review_only() -> None:
    assert len(PROHIBITIONS) == PREDICATE_COUNT + REVIEW_ONLY_COUNT


# ── the review-only list, kept honest ─────────────────────────────────────


def test_every_review_only_entry_names_the_phase_it_stops_being_one() -> None:
    """An exemption with no end date is a deletion written politely. `Registry`
    refuses one at construction; this asserts none slipped in as `None`."""
    for item in REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY):
        assert item.expiry is not None, item.identifier


def test_no_review_only_entry_has_a_negative_control() -> None:
    """If it can be tested it is not review-only, and if it cannot the control
    does not test it. Either way one of the two labels is wrong."""
    exempt = {item.identifier for item in REGISTRY.by_enforcement(Enforcement.REVIEW_ONLY)}
    assert not exempt & {control.prohibition for control in REGISTRY.controls}


def test_no_predicate_carries_an_expiry() -> None:
    """A predicate is enforced now. An expiry on one means the label is wrong."""
    for item in REGISTRY.by_enforcement(Enforcement.PREDICATE):
        assert item.expiry is None, item.identifier


# ── coverage of the thing the inventory is about ──────────────────────────


def test_all_six_canonical_artifacts_are_proven_immutable() -> None:
    """INV-5 is asserted once per artifact, not once in general. Five proofs and
    a gap would read identically in a summary count."""
    proven = {
        type(control.clean()).__name__
        for control in REGISTRY.controls
        if control.prohibition == IMMUTABLE
    }
    assert proven == CANONICAL_ARTIFACTS


def test_running_the_registry_twice_reports_the_same_thing() -> None:
    """No clock, no randomness. A conformance result that changes between two
    runs of the same commit is not a result."""
    first = [(finding.prohibition, finding.attribution) for finding in REGISTRY.run()]
    second = [(finding.prohibition, finding.attribution) for finding in REGISTRY.run()]
    assert first == second


# ── break it on purpose (§J.5) ────────────────────────────────────────────
#
# The suite above is green. These two prove it is CAPABLE of being red against
# the real schemas — that the builders can express a payload the schema accepts
# and one it refuses for the wrong reason, and that both are reported as
# failures rather than absorbed.


def test_a_control_whose_violating_payload_is_legal_is_reported_not_enforced() -> None:
    """A payment of exactly one paisa breaks nothing, so nothing refuses it."""
    finding = attribute(
        NegativeControl(
            "invented",
            clean=lambda: _journal_line(amount=Decimal("1180.00")),
            violating=lambda: _journal_line(amount=Decimal("0.01")),
        )
    )
    assert finding.attribution is Attribution.NOT_ENFORCED


def test_a_control_whose_clean_payload_is_refused_is_reported_invalid() -> None:
    """Both halves bolt a field onto a frozen schema, so BOTH are refused and
    the rejection cannot be attributed to anything the control claims to test.
    Reported loudly instead of counted as a pass."""
    finding = attribute(
        NegativeControl(
            "invented",
            clean=lambda: _validation(corrected_ledger="Office Equipment"),
            violating=lambda: _validation(corrected_amount="1180.00"),
        )
    )
    assert finding.attribution is Attribution.CONTROL_INVALID


def test_the_registry_refuses_a_control_for_a_rule_nobody_wrote_down() -> None:
    """Rebuilt from this module's own inventory, so the guard is proven against
    the real list rather than a toy one."""
    with pytest.raises(ValueError, match="not in the inventory"):
        Registry(
            PROHIBITIONS,
            (*CONTROLS, NegativeControl("unlisted", clean=_journal_line, violating=_journal_line)),
        )


# ── the fixed material, pinned ────────────────────────────────────────────
#
# WHY EVERY LITERAL IN EVERY BUILDER IS ASSERTED HERE.
#     A negative control only proves what the difference between its two halves
#     is. Everything the two halves SHARE is unexamined: change "Tally" to
#     "TALLY", `retry_count` from 0 to 1, or an identity from `_uuid("5")` to
#     `None`, and both halves move together, so the control still reports
#     ENFORCED and the suite stays green. Mutation testing found exactly that —
#     the shared payload was the largest unasserted surface in the repository.
#
#     The module docstring promises payloads that are FIXED: no clock, no
#     randomness, byte-identical across runs. That promise is only a promise
#     until something reads the values back. These tests read them back.
#
# WHAT THIS IS NOT.
#     Not a restatement of the schema — the schema is what refuses a payload,
#     and it is exercised by the controls. This is the fixture itself: the
#     specific words a clean payload is written in, the specific identities it
#     carries, and the specific numbers. Those are choices, and a choice that
#     nothing checks is a choice anybody can silently reverse.

_EVIDENCE_REFERENCE = "page 1, line 4"
_SOURCE_FILE = "invoice-2026-0041.pdf"
_RECEIPT_DATE = "the date the goods were received"
_RECEIPT_QUESTION = "On what date were the goods received?"
_OFFICE_EQUIPMENT = "Office Equipment"

#: `identity.py` chose v4 precisely because it encodes nothing (INV-9).
_UUID_VERSION_4 = 4


def test_the_envelope_carries_the_two_fixed_identities() -> None:
    """`_uuid("1")` and `_uuid("2")`, not `None` and not each other.

    `ArtifactId` is a frozen dataclass, and pydantic accepts an already-built
    dataclass instance without revalidating its field — so `ArtifactId(None)`
    reaches an artifact intact. Nothing but reading the value back catches it.
    """
    envelope = _envelope()
    assert envelope.artifact_id == ArtifactId(_uuid("1"))
    assert envelope.transaction_id == TransactionId(_uuid("2"))
    assert envelope.version == 1
    assert envelope.parent_versions == ()


def test_the_fixed_uuid_is_a_legal_v4_built_from_one_digit() -> None:
    """The version and variant nibbles are pinned deliberately; a stand-in that
    was not a legal v4 would be a different value no reader could see."""
    value = _uuid("a")
    assert value.version == _UUID_VERSION_4
    assert value.variant == uuid.RFC_4122
    assert str(value) == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert _uuid("b") != value


def test_the_provenance_names_the_document_and_the_line() -> None:
    provenance = _provenance()
    assert provenance.source_type is SourceType.DOCUMENT
    assert provenance.source_id == _SOURCE_FILE
    assert provenance.evidence_reference == _EVIDENCE_REFERENCE
    assert provenance.timestamp == datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    assert provenance.confidence == Decimal("0.9000")
    assert provenance.corroborated is Corroborated.NOT_ASSESSED


def test_the_detected_field_carries_the_amount_it_claims_to() -> None:
    field = _detected_field()
    assert field.name == "Amount"
    assert field.value == "1180.00"
    assert field.provenance == _provenance()


def test_the_structured_document_quotes_the_text_it_was_read_from() -> None:
    document = _structured_document()
    assert document.extracted_text == "INVOICE  Total 1,180.00"
    assert document.document_structure == "header, one table, footer"
    assert document.detected_tables == ()
    assert tuple(item.name for item in document.detected_fields) == ("Amount",)


def test_the_confidence_report_says_why_the_reading_is_reliable() -> None:
    report = _confidence_report()
    assert report.reliability_information == "typed document, clean scan"
    assert report.uncertainty_markers == ()
    assert report.risky_fields == ()
    assert tuple(score.field_name for score in report.confidence_scores) == ("Amount",)


def test_the_evidence_object_names_its_document_and_its_source() -> None:
    evidence = _evidence()
    assert evidence.document_id == DocumentId(_uuid("3"))
    assert evidence.source_references == (_SOURCE_FILE,)
    assert evidence.human_business_context is None


def test_the_observed_fact_states_what_the_document_says_and_cites_it() -> None:
    fact = _fact()
    assert fact.statement == "The document states a total of 1,180.00."
    assert fact.stated_text == "Total  1,180.00"
    assert fact.evidence_references == (_EVIDENCE_REFERENCE,)


def test_the_unknown_names_the_gap_and_why_it_matters() -> None:
    unknown = _unknown()
    assert unknown.subject == _RECEIPT_DATE
    assert unknown.why_it_matters == (
        "Without it, the period this event belongs to cannot be settled."
    )


def test_the_conflict_carries_two_readings_that_actually_disagree() -> None:
    """Two DIFFERENT statements. Collapse them to one wording and the payload
    stops being a conflict, which is the whole thing `TWO_READINGS` tests."""
    conflict = _conflict()
    assert conflict.subject == "the total on the document"
    assert tuple(reading.statement for reading in conflict.competing_readings) == (
        "The printed total reads 1,180.00.",
        "The lines add up to 1,180.50.",
    )


def test_all_six_results_report_the_facts_they_are_supposed_to() -> None:
    """`RESULT_REPORTS` — no Result may omit what it found. A Result silently
    emptied here still constructs, because the control that tests the rule
    builds its own payload rather than reading this one."""
    results = _results()
    assert results.transaction.identified_event == (_fact(),)
    assert results.party.identified_entities == (_fact(),)
    assert results.item.identified_goods_and_services == (_fact(),)
    assert results.item.descriptions == (_fact(),)
    assert results.payment.amount_relationships == (_fact(),)
    assert results.timeline.dates == (_fact(),)
    assert results.business_context.context_clues == (_fact(),)
    assert results.transaction.unknown_information == ()
    for result in (
        results.transaction,
        results.party,
        results.item,
        results.payment,
        results.timeline,
        results.business_context,
    ):
        assert result.confidence == Decimal("0.9000")


def test_the_results_that_raise_an_unknown_keep_everything_else_intact() -> None:
    """The gap is ADDED, nothing is dropped for it. A Result that lost its facts
    while gaining an unknown would still satisfy `UNKNOWNS_INTACT`."""
    results = _results_raising_an_unknown()
    assert results.transaction.unknown_information == (_unknown(),)
    assert results.transaction.identified_event == (_fact(),)
    assert results.transaction.confidence == Decimal("0.9000")


def test_the_less_certain_results_differ_from_the_rest_in_exactly_one_place() -> None:
    """Five at 0.9000 and one at 0.7000, so `min` and `max` cannot coincide —
    which is the only reason `NO_FREE_CONFIDENCE` has anything to refuse."""
    results = _results_with_a_less_certain_one()
    assert results.payment.confidence == Decimal("0.7000")
    scores = {
        results.transaction.confidence,
        results.party.confidence,
        results.item.confidence,
        results.timeline.confidence,
        results.business_context.confidence,
    }
    assert scores == {Decimal("0.9000")}


def test_the_transaction_story_is_written_in_the_business_register() -> None:
    understanding = _understanding()
    assert understanding.transaction_story.narrative == (
        "Twelve units were delivered and paid for on the stated date."
    )
    assert understanding.identified_unknowns == ()


def test_the_journal_line_names_a_ledger_and_an_exact_amount() -> None:
    line = _journal_line()
    assert line.ledger == _OFFICE_EQUIPMENT
    assert line.amount == Decimal("1180.00")


def test_the_doubt_names_both_the_missing_fact_and_the_question() -> None:
    doubt = _doubt()
    assert doubt.missing_fact == _RECEIPT_DATE
    assert doubt.required_clarification == _RECEIPT_QUESTION


def test_the_decision_carries_the_treatment_and_the_two_sides_it_posts() -> None:
    decision = _decision()
    assert decision.decision_status is DecisionStatus.COMPLETE
    assert decision.accounting_treatment == "Purchase of office equipment"
    assert decision.ledger_classification == _OFFICE_EQUIPMENT
    assert decision.journal_structure == "one debit, one credit"
    assert decision.tax_treatment == "input credit claimed at the stated rate"
    assert decision.supporting_reasoning == (
        "The document names the item, the seller and the amount."
    )
    assert tuple(line.ledger for line in decision.debit_entries) == (_OFFICE_EQUIPMENT,)
    assert tuple(line.ledger for line in decision.credit_entries) == ("Bank",)
    assert decision.unresolved_doubts == ()


def test_the_incomplete_decision_posts_nothing_and_names_its_doubt() -> None:
    decision = _incomplete_decision()
    assert decision.decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED
    assert decision.debit_entries == ()
    assert decision.credit_entries == ()
    assert decision.unresolved_doubts == (_doubt(),)


def test_the_clarification_asks_one_question_about_one_decision() -> None:
    request = _clarification()
    assert request.clarification_id == ArtifactId(_uuid("4"))
    assert request.related_decision_id == ArtifactId(_uuid("5"))
    assert request.related_artifact_version == 1
    assert request.missing_information == (_RECEIPT_DATE,)
    assert request.required_clarification == _RECEIPT_QUESTION
    assert request.reason_clarification_is_required == (
        "The period the entry belongs to depends on it."
    )
    assert request.affected_decision == "the accounting period of the entry"
    assert request.supporting_evidence_references == (_EVIDENCE_REFERENCE,)
    assert request.detected_conflicts == ()


def test_the_finding_says_what_failed_why_and_what_to_do_next() -> None:
    finding = _finding()
    assert finding.what_failed == "the claimed input credit"
    assert finding.why_it_failed == "no evidence reference names the rate it was claimed at"
    assert finding.affected_artifact == "Accounting Decision"
    assert finding.recommended_next_step == "raise a clarification for the rate"
    assert finding.supporting_evidence_references == (_EVIDENCE_REFERENCE,)


def test_the_validation_decision_points_at_the_decision_it_judged() -> None:
    validation = _validation()
    assert validation.related_decision_id == ArtifactId(_uuid("5"))
    assert validation.related_artifact_version == 1
    assert validation.supporting_evidence_references == (_EVIDENCE_REFERENCE,)
    assert validation.validation_reasoning == ("every rule the decision was checked against passed")
    assert validation.validation_findings == ()


def test_the_execution_result_records_one_posting_to_one_destination() -> None:
    """Every one of these is a value a control shares with its violating twin,
    so nothing else in the suite would notice any of them changing."""
    execution = _execution()
    assert execution.execution_id == ExecutionId(_uuid("6"))
    assert execution.execution_attempt_id == ExecutionAttemptId(_uuid("7"))
    assert execution.accounting_decision_id == ArtifactId(_uuid("5"))
    assert execution.decision_version == 1
    assert execution.validation_decision_id == ArtifactId(_uuid("8"))
    assert execution.destination_system == "Tally"
    assert execution.corrects_execution_result is None
    assert execution.posting_status == "Posted"
    assert execution.external_transaction_ids == ("TALLY-88214",)
    assert execution.retry_count == 0
    assert execution.queue_status == "Drained"
    assert execution.notification_status == "Sent"
    assert execution.classified_error is None
    assert execution.audit_reference.execution_id == ExecutionId(_uuid("6"))
    assert execution.execution_outcome == "Success"


def test_the_execution_audit_reference_points_at_its_own_execution_by_default() -> None:
    """`AUDIT_POINTS_HOME` is only testable because the clean payload's audit
    reference and execution id are the SAME id. Drift them apart and the
    control's clean half becomes the violation it is supposed to contrast."""
    execution = _execution()
    assert execution.audit_reference.execution_id == execution.execution_id


# ── the immutability violation, examined directly ─────────────────────────
#
# `_mutate` is the violating half of all six INV-5 controls, and against a
# frozen model EVERY way of breaking it produces the same outcome: an
# exception. `setattr(None, ...)`, `getattr(model, None)`, writing `None`
# instead of the field's own value — all six controls stay green through all of
# them, because the control only asks WHETHER the payload was refused.
#
# So `_mutate` is exercised here against a model that is NOT frozen, where the
# three things it promises are separately visible: it writes the FIRST declared
# field, it writes that field's OWN value, and it returns the same object.


#: Deliberately mutable, so a write SUCCEEDS and can be inspected — every real
#: artifact is `frozen=True`, which refuses the write before it can be observed.
#:
#: Built with `create_model` rather than a `class` statement on purpose. A
#: subclass of `BaseModel` re-inherits `Any` from its base signature, and this
#: repository runs `disallow_any_explicit` and separately COUNTS suppressions,
#: blocking on any increase. A `type: ignore[explicit-any]` here would buy one
#: test at the cost of a gate.
_Writable = create_model("_Writable", first=(str, ...), second=(str, ...))


def test_mutate_writes_the_first_declared_field_back_to_its_own_value() -> None:
    model = _Writable(first="kept", second="untouched")
    returned = _mutate(model)
    assert returned is model
    # The whole model state, not two fields: a write that also touched
    # something else would slip past a pair of per-field checks.
    assert model.model_dump() == {"first": "kept", "second": "untouched"}


def test_mutate_writes_the_first_field_and_not_a_later_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `_mutate` that picked a different field would still trip `frozen=True`
    on all six artifacts, so only a direct probe can tell the two apart.

    `_mutate` assigns a field back to its OWN value, so no comparison of values
    can see it — the write itself is the only observable. Recorded by patching
    `__setattr__` on the existing class rather than by subclassing it: a
    subclass of a pydantic model re-inherits `Any` from its base signature and
    would need a `type: ignore[explicit-any]`, and this repository counts
    suppressions and blocks on any increase.

    The instance is built BEFORE the patch, so construction is not recorded and
    the single entry that remains is the one `_mutate` performed.
    """
    written: list[tuple[str, object]] = []
    model = _Writable(first="kept", second="untouched")
    original = type(model).__setattr__

    def record(instance: BaseModel, name: str, value: object) -> None:
        written.append((name, value))
        original(instance, name, value)

    monkeypatch.setattr(_Writable, "__setattr__", record)
    _mutate(model)

    assert written == [("first", "kept")], (
        "`_mutate` must write the FIRST declared field, once. Any other field, "
        "or more than one write, and the six INV-5 controls are probing "
        "something other than what they claim to probe."
    )


def test_mutate_still_refuses_to_write_a_frozen_artifact() -> None:
    """The property the six INV-5 controls actually rest on."""
    with pytest.raises(ValidationError):
        _mutate(_evidence())


# ── the two builders every entry in the inventory is made of ──────────────
#
# WHY THESE NEED THEIR OWN TESTS, WHEN 40 PROHIBITIONS ALREADY RUN THROUGH THEM.
#     They do not run through them — not while a test is running. `_predicate`
#     and `_review_only` are called exactly once each per entry, at MODULE
#     IMPORT, and `PROHIBITIONS` is a tuple of the results. By the time any test
#     executes, both functions are finished and nothing calls them again. Every
#     assertion in this file reads the tuple they already built.
#
#     That is invisible until the code inside them is changed, and then it is
#     total: swap `Enforcement.PREDICATE` for `None`, drop the `source=` keyword
#     entirely, and the whole suite stays green, because the altered line never
#     runs a second time. Measured, not assumed — 22 mutations of these two
#     functions survived a full mutation run with every other test in place.
#
#     So they are called here, directly, and the Prohibition they return is
#     compared field for field. A builder is a promise about what an entry is
#     made of, and this is the only place that promise is read back.

#: Deliberately unlike anything in the real inventory: a builder that ignored an
#: argument and substituted a constant would still match a fixture that happened
#: to resemble the entries around it.
_A_QUOTE = "a quote long enough to name the sentence it came from"
_ANOTHER_QUOTE = "a different sentence, quoted from a different line"


def test_the_predicate_builder_keeps_every_field_and_marks_it_enforced_now() -> None:
    """`enforcement` is the field with no argument behind it — it is the whole
    reason this builder exists rather than a bare `Prohibition(...)`. Nothing
    else in the repository would notice it becoming `None`: a predicate carries
    no expiry, so `__post_init__` has nothing to object to and the malformed
    entry is filed silently."""
    assert _predicate(
        "SYSTEM_INVARIANTS:1/a-slug-no-real-entry-uses",
        _A_QUOTE,
        "docs/SYSTEM_INVARIANTS.md:1",
        "a subject no real entry names",
    ) == Prohibition(
        identifier="SYSTEM_INVARIANTS:1/a-slug-no-real-entry-uses",
        quote=_A_QUOTE,
        source="docs/SYSTEM_INVARIANTS.md:1",
        subject="a subject no real entry names",
        enforcement=Enforcement.PREDICATE,
        expiry=None,
    )


def test_the_review_only_builder_keeps_every_field_including_the_end_date() -> None:
    """The expiry is the only thing separating a review-only entry from a
    deletion written politely, and it is the one field the predicate builder
    does not take. It is asserted as the value passed in, not merely as
    not-None: an expiry pinned to a constant phase would outlive every entry
    that named a later one."""
    assert _review_only(
        "SYSTEM_BOUNDARIES:2/another-slug-no-real-entry-uses",
        _ANOTHER_QUOTE,
        "docs/SYSTEM_BOUNDARIES.md:2",
        "another subject no real entry names",
        "P5",
    ) == Prohibition(
        identifier="SYSTEM_BOUNDARIES:2/another-slug-no-real-entry-uses",
        quote=_ANOTHER_QUOTE,
        source="docs/SYSTEM_BOUNDARIES.md:2",
        subject="another subject no real entry names",
        enforcement=Enforcement.REVIEW_ONLY,
        expiry="P5",
    )


@pytest.mark.parametrize("expiry", sorted(PHASES))
def test_the_review_only_builder_passes_each_phase_through_unchanged(expiry: str) -> None:
    """Every declared phase, so no single hard-coded one can impersonate the
    argument."""
    assert _review_only("D:3/s", _A_QUOTE, "docs/DATA_FLOW.md:3", "a subject", expiry).expiry == (
        expiry
    )


def test_the_two_builders_disagree_about_exactly_one_field() -> None:
    """The enforcement, and nothing else. If they ever diverged elsewhere, the
    inventory would hold two shapes of entry and the counts above would be
    counting different things."""
    enforced = _predicate("D:4/s", _A_QUOTE, "docs/DATA_FLOW.md:4", "a subject")
    exempt = _review_only("D:4/s", _A_QUOTE, "docs/DATA_FLOW.md:4", "a subject", "P3")
    differing = {
        field.name
        for field in dataclasses.fields(enforced)
        if getattr(enforced, field.name) != getattr(exempt, field.name)
    }
    assert differing == {"enforcement", "expiry"}
    assert enforced.enforcement is Enforcement.PREDICATE
    assert exempt.enforcement is Enforcement.REVIEW_ONLY


def test_every_entry_in_the_real_inventory_matches_what_its_builder_produces() -> None:
    """Ties the direct tests above back to the live tuple. Rebuilding each entry
    from its own recorded fields must reproduce it exactly — so a builder that
    started dropping a field would be caught against all 40 real entries, not
    only against the fixtures here."""
    for item in PROHIBITIONS:
        rebuilt = (
            _predicate(item.identifier, item.quote, item.source, item.subject)
            if item.enforcement is Enforcement.PREDICATE
            else _review_only(
                item.identifier,
                item.quote,
                item.source,
                item.subject,
                # `Registry` refuses a review-only entry with no expiry, so by
                # construction this is never None here.
                item.expiry or "",
            )
        )
        assert rebuilt == item, item.identifier
