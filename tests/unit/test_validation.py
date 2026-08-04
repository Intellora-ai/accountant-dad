"""The Validation Decision — Engine 5's only outbound artifact.

Written before the implementation. Every test names the rule it defends and
quotes the line that states it, and the dangerous direction is always the
permissive one:

  - a finding that does not name its responsible engine turns a rejection back
    into *"Validation failed."* (`ENGINE_5:235` · `VALIDATION_INTERNAL:121`)
  - an approval that stands while a Critical finding stands breaks INV-8 —
    permission to execute is decided BEFORE execution, and something
    unapproved would cross to Tally.
  - a field that could carry a corrected ledger turns the reviewer into an
    author (`ENGINE_5:213` — *"Validation cannot repair"*).

Each of those is asserted from the outside, through the real model, with the
real `Confidence` and the real `IdentityEnvelope` — never a stand-in (§J.6).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.validation import (
    APPROVING_STATUSES,
    CANNOT_APPROVE_STATUSES,
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationFinding,
    ValidationStatus,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

FIRST_VERSION = 1
SECOND_VERSION = 2

#: Four statuses, four severities, four blameable engines. Each count is read
#: off a document, never chosen here.
EXPECTED_STATUSES = 4
EXPECTED_SEVERITIES = 4
EXPECTED_ENGINES = 4

AWARE = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
NAIVE = datetime(2026, 8, 3, 12, 0, 0)

#: The four collections the Validation Decision tree names (`ENGINE_5:130-133`).
#: Every predicate below is checked against all four, because a rule that only
#: scanned `validation_findings` could be evaded by filing the same issue under
#: `validation_errors`.
ISSUE_LISTS = (
    "validation_findings",
    "validation_errors",
    "validation_warnings",
    "validation_risks",
)

#: Tokens that would mean this artifact had grown a slot for a repair. Read as
#: whole underscore-separated words off the real model's field names, so adding
#: `corrected_ledger` to either model turns this red without anyone editing the
#: test.
REPAIR_MARKERS = frozenset(
    {
        "corrected",
        "correction",
        "corrects",
        "fix",
        "fixed",
        "repair",
        "repaired",
        "replacement",
        "replaces",
        "revised",
        "override",
        "patch",
        "amended",
        "ledger",
        "ledgers",
        "debit",
        "debits",
        "credit",
        "credits",
        "journal",
        "entry",
        "entries",
        "amount",
        "amounts",
        "treatment",
        "rate",
        "rates",
        "voucher",
        "posting",
        "post",
    }
)


def envelope(**overrides: object) -> IdentityEnvelope:
    base: dict[str, object] = {
        "artifact_id": ArtifactId.new(),
        "version": FIRST_VERSION,
        "parent_versions": (),
        "transaction_id": TransactionId.new(),
    }
    base.update(overrides)
    return IdentityEnvelope(**base)  # type: ignore[arg-type]


def finding(**overrides: object) -> ValidationFinding:
    base: dict[str, object] = {
        "what_failed": "The ITC claim carries no supporting evidence.",
        "why_it_failed": "No evidence reference supports the claimed input tax credit.",
        "responsible_engine": ResponsibleEngine.ACCOUNTING,
        "affected_artifact": "Accounting Decision v1",
        "blocking_severity": Severity.LOW,
        "recommended_next_step": "Return to the Accounting Engine for a new decision version.",
        "supporting_evidence_references": ("Document Evidence Object v1 / field tax_amount",),
    }
    base.update(overrides)
    return ValidationFinding(**base)  # type: ignore[arg-type]


def decision(**overrides: object) -> ValidationDecision:
    base: dict[str, object] = {
        "identity": envelope(),
        "related_decision_id": ArtifactId.new(),
        "related_artifact_version": FIRST_VERSION,
        "validation_status": ValidationStatus.APPROVED,
        "validation_findings": (),
        "validation_errors": (),
        "validation_warnings": (),
        "validation_risks": (),
        "failed_validation_rules": (),
        "supporting_evidence_references": (),
        "validation_confidence": Decimal("0.9000"),
        "validation_reasoning": "Every rule category passed; no blocking finding stands.",
        "validation_timestamp": AWARE,
    }
    base.update(overrides)
    return ValidationDecision(**base)  # type: ignore[arg-type]


# ── Validation Status — enumerated, and identically in eight places ──────────


def test_the_four_statuses_are_exactly_the_four_the_documents_name() -> None:
    # `ENGINE_5:128-129` · `ENGINE_5:145-148` · `DATA_FLOW:43` ·
    # `ENGINE_RESPONSIBILITIES:248`. All four agree; the schema agrees with
    # them, verbatim, so no translation layer can drift.
    assert {status.value for status in ValidationStatus} == {
        "Approved",
        "Approved With Warning",
        "Clarification Required",
        "Rejected",
    }
    assert len(ValidationStatus) == EXPECTED_STATUSES


def test_a_status_the_documents_do_not_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(validation_status="Approved Conditionally")


def test_a_status_that_differs_only_in_case_is_refused() -> None:
    # The spelling is the contract. `approved` would round-trip through JSON as
    # a fifth value nothing else in the system recognises.
    with pytest.raises(ValidationError):
        decision(validation_status="approved")


def test_a_missing_status_is_refused() -> None:
    # There is no default. A Validation Decision that forgot to say what it
    # decided is the silent approval `ENGINE_5:547` names as failure.
    base = {
        "identity": envelope(),
        "related_decision_id": ArtifactId.new(),
        "related_artifact_version": FIRST_VERSION,
        "validation_findings": (),
        "validation_errors": (),
        "validation_warnings": (),
        "validation_risks": (),
        "failed_validation_rules": (),
        "supporting_evidence_references": (),
        "validation_confidence": Decimal("0.9000"),
        "validation_reasoning": "…",
        "validation_timestamp": AWARE,
    }
    with pytest.raises(ValidationError):
        ValidationDecision(**base)  # type: ignore[arg-type]


def test_the_status_reaches_the_wire_spelled_as_the_documents_spell_it() -> None:
    # The four names must survive serialisation unchanged — Engine 6 and the
    # Application Layer both read this value.
    dumped = decision(validation_status=ValidationStatus.APPROVED_WITH_WARNING).model_dump(
        mode="json"
    )
    assert dumped["validation_status"] == "Approved With Warning"


def test_approved_with_warning_counts_as_an_approval() -> None:
    # `COMMUNICATION_RULES_VALIDATION_ENGINE:61` — it goes forward, after the
    # Application Layer releases it. Grouping it with `Rejected` would make the
    # Critical predicate below check the wrong thing.
    assert (
        frozenset({ValidationStatus.APPROVED, ValidationStatus.APPROVED_WITH_WARNING})
        == APPROVING_STATUSES
    )
    assert (
        frozenset({ValidationStatus.REJECTED, ValidationStatus.CLARIFICATION_REQUIRED})
        == CANNOT_APPROVE_STATUSES
    )
    assert set(ValidationStatus) == APPROVING_STATUSES | CANNOT_APPROVE_STATUSES


# ── Validation Severity — four values, no ordering, no blocking semantics ────


def test_the_four_severities_are_exactly_the_four_the_documents_name() -> None:
    assert {level.value for level in Severity} == {"Critical", "High", "Medium", "Low"}
    assert len(Severity) == EXPECTED_SEVERITIES


def test_an_unknown_severity_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(blocking_severity="Severe")


def test_severities_cannot_be_ordered() -> None:
    # `ENGINE_5:442` — *"Unknown risk defaults to higher severity"* — presupposes
    # an ordering that NO document defines. A `StrEnum` would have silently
    # supplied a lexicographic one (Critical < High < Low < Medium), which is
    # not the ordering anybody means. Refusing the comparison keeps the missing
    # definition visible instead of answering it wrongly.
    with pytest.raises(TypeError):
        _ = Severity.CRITICAL < Severity.HIGH  # type: ignore[operator]


def test_a_severity_is_not_a_string() -> None:
    # The structural reason the comparison above raises.
    assert not isinstance(Severity.CRITICAL, str)


# ── Every finding names the responsible engine — DATA_FLOW:43, required ──────


def test_a_finding_without_a_responsible_engine_is_refused() -> None:
    # `DATA_FLOW:43` — *"Every finding names the responsible engine."*
    # `VALIDATION_INTERNAL:118` — *"A finding without an owner cannot be acted
    # on."* No default, no None, no optional.
    with pytest.raises(ValidationError):
        ValidationFinding(  # type: ignore[call-arg]
            what_failed="x",
            why_it_failed="y",
            affected_artifact="Accounting Decision v1",
            blocking_severity=Severity.LOW,
            recommended_next_step="z",
            supporting_evidence_references=("ref",),
        )


def test_a_responsible_engine_of_none_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(responsible_engine=None)


def test_the_blameable_engines_are_exactly_engines_one_to_four() -> None:
    # `ENGINE_5:232` and `VALIDATION_INTERNAL:118` — *"Every one points back to
    # Engine 1, 2, 3 or 4."*
    assert {engine.value for engine in ResponsibleEngine} == {
        "Input",
        "Understanding",
        "Accounting",
        "Clarification",
    }
    assert len(ResponsibleEngine) == EXPECTED_ENGINES


@pytest.mark.parametrize("blamed", ["Validation", "Execution", "Tally", "Knowledge Brain"])
def test_a_finding_cannot_blame_a_stage_outside_engines_one_to_four(blamed: str) -> None:
    # Validation blaming itself would leave a finding nobody can act on: the
    # engine that found the defect cannot repair it (`ENGINE_5:213`). Blaming
    # Execution would point backwards past the last boundary in the system.
    with pytest.raises(ValidationError):
        finding(responsible_engine=blamed)


@pytest.mark.parametrize("field", ISSUE_LISTS)
def test_a_bare_string_cannot_be_filed_in_any_issue_list(field: str) -> None:
    # The evasion path. If any of the four lists accepted plain text, an issue
    # could be recorded with no responsible engine simply by choosing a
    # different list.
    with pytest.raises(ValidationError):
        decision(**{field: ("something went wrong",)})


@pytest.mark.parametrize("field", ISSUE_LISTS)
def test_every_entry_in_every_issue_list_names_a_responsible_engine(field: str) -> None:
    made = decision(**{field: (finding(responsible_engine=ResponsibleEngine.INPUT),)})
    assert all(issue.responsible_engine in set(ResponsibleEngine) for issue in made.issues)


def test_issues_gathers_all_four_lists_and_loses_nothing() -> None:
    # `VALIDATION_INTERNAL:108` — *"No validation finding may disappear inside
    # the pipeline."* A gatherer that dropped a list would hide exactly the
    # findings the Critical predicate below has to see.
    made = decision(
        validation_status=ValidationStatus.REJECTED,
        validation_findings=(finding(what_failed="a"),),
        validation_errors=(finding(what_failed="b"),),
        validation_warnings=(finding(what_failed="c"),),
        validation_risks=(finding(what_failed="d"),),
    )
    assert [issue.what_failed for issue in made.issues] == ["a", "b", "c", "d"]


# ── Every finding carries evidence references — ENGINE_5:571 ────────────────


def test_a_finding_with_no_evidence_reference_is_refused() -> None:
    # `ENGINE_5:571` — *"Every finding contains evidence references."* Stated
    # without exception, so an empty tuple is refused rather than tolerated.
    with pytest.raises(ValidationError):
        finding(supporting_evidence_references=())


def test_a_blank_evidence_reference_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(supporting_evidence_references=("   ",))


def test_a_finding_keeps_every_evidence_reference_it_was_given() -> None:
    refs = ("Document Evidence Object v1 / tax_amount", "Business Understanding Object v2")
    assert finding(supporting_evidence_references=refs).supporting_evidence_references == refs


# ── INV-8 · ENGINE_5:467 — no approval while a Critical finding stands ───────


@pytest.mark.parametrize("field", ISSUE_LISTS)
@pytest.mark.parametrize(
    "status", [ValidationStatus.APPROVED, ValidationStatus.APPROVED_WITH_WARNING]
)
def test_a_critical_entry_in_any_list_forbids_any_approval(
    field: str, status: ValidationStatus
) -> None:
    # `ENGINE_5:467` — *"No approval exists while a Critical finding remains."*
    # `VALIDATION_INTERNAL:146` — `validation_decision` CANNOT *"Approve while a
    # Critical finding stands."* INV-8: permission is decided here, before
    # execution, so nothing unapproved reaches Tally.
    with pytest.raises(ValidationError):
        decision(
            validation_status=status,
            **{field: (finding(blocking_severity=Severity.CRITICAL),)},
        )


@pytest.mark.parametrize(
    "status", [ValidationStatus.REJECTED, ValidationStatus.CLARIFICATION_REQUIRED]
)
def test_a_critical_finding_is_allowed_on_a_status_that_blocks_execution(
    status: ValidationStatus,
) -> None:
    # Both of these block execution, so neither can break INV-8. The schema
    # does not force Critical to mean exactly `Rejected`: `VALIDATION_INTERNAL`
    # §4 reads that way only if its rows are first-match, and §5.1 does not say
    # so. Reported, not resolved here.
    made = decision(
        validation_status=status,
        validation_findings=(finding(blocking_severity=Severity.CRITICAL),),
    )
    assert made.validation_status is status


@pytest.mark.parametrize("level", [Severity.HIGH, Severity.MEDIUM, Severity.LOW])
def test_a_non_critical_finding_does_not_block_approval(level: Severity) -> None:
    # Deliberate boundary. `ENGINE_5:157-158` says High is *"normally blocked"*
    # and Medium is *"policy dependent"*; `ENGINE_RESPONSIBILITIES:249` says
    # only Critical blocks and High/Medium/Low are non-blocking. The two
    # contradict, so no blocking semantics beyond Critical are encoded.
    made = decision(
        validation_status=ValidationStatus.APPROVED,
        validation_findings=(finding(blocking_severity=level),),
    )
    assert made.validation_status is ValidationStatus.APPROVED


def test_an_approved_decision_may_still_record_a_low_finding() -> None:
    # `ENGINE_5:159` — Low is *"Non-blocking. Still recorded permanently."* A
    # schema that dropped it would be hiding a finding.
    made = decision(validation_findings=(finding(blocking_severity=Severity.LOW),))
    assert made.validation_findings[0].blocking_severity is Severity.LOW


# ── ENGINE_5:219-228 — a decision that cannot approve says exactly why ───────


@pytest.mark.parametrize(
    "status", [ValidationStatus.REJECTED, ValidationStatus.CLARIFICATION_REQUIRED]
)
def test_a_decision_that_cannot_approve_and_records_no_issue_is_refused(
    status: ValidationStatus,
) -> None:
    # `ENGINE_5:219` — *"If it cannot approve, it returns: what failed · why it
    # failed · the responsible engine · the affected artifact · blocking
    # severity · the recommended next step."* `ENGINE_5:228` — *"Never simply
    # 'Validation Failed.' Always exactly why."* With every list empty there is
    # no responsible engine anywhere in the artifact.
    with pytest.raises(ValidationError):
        decision(validation_status=status)


@pytest.mark.parametrize("field", ISSUE_LISTS)
def test_one_entry_in_any_single_list_satisfies_the_why(field: str) -> None:
    made = decision(validation_status=ValidationStatus.REJECTED, **{field: (finding(),)})
    assert len(made.issues) == 1


def test_an_approved_decision_needs_no_issues() -> None:
    # The inverse must stay legal: a clean approval records nothing wrong.
    assert decision(validation_status=ValidationStatus.APPROVED).issues == ()


# ── Explainability — ENGINE_5:544, §15 ──────────────────────────────────────


def test_a_decision_with_empty_reasoning_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(validation_reasoning="")


def test_a_decision_with_whitespace_only_reasoning_is_refused() -> None:
    # A space is not an explanation. `ENGINE_5:556` — *"Every approval and every
    # rejection must be explainable."*
    with pytest.raises(ValidationError):
        decision(validation_reasoning="   \n\t ")


@pytest.mark.parametrize(
    "field",
    ["what_failed", "why_it_failed", "affected_artifact", "recommended_next_step"],
)
def test_a_blank_component_of_a_finding_is_refused(field: str) -> None:
    with pytest.raises(ValidationError):
        finding(**{field: " "})


def test_text_is_stored_verbatim_and_never_trimmed() -> None:
    # Refuse rather than rewrite — the same rule `confidence.py` states for a
    # value with too many decimal places. An artifact records what its producer
    # asserted; silently editing it would falsify the record.
    given = "  the ITC claim has no evidence  "
    assert decision(validation_reasoning=given).validation_reasoning == given


# ── Validation only validates — it cannot carry a correction ────────────────


def test_an_extra_field_cannot_be_bolted_on() -> None:
    # `extra="forbid"`. Without it, `corrected_ledger` would be accepted and
    # silently ignored — the worst of both, because the caller would believe it
    # was carried.
    with pytest.raises(ValidationError):
        decision(corrected_ledger="Office Equipment")


def test_an_extra_field_cannot_be_bolted_onto_a_finding() -> None:
    with pytest.raises(ValidationError):
        finding(corrected_amount="19000.00")


@pytest.mark.parametrize("model", [ValidationDecision, ValidationFinding])
def test_no_field_on_this_artifact_could_hold_a_repair(
    model: type[ValidationDecision] | type[ValidationFinding],
) -> None:
    # `ENGINE_5:213` — *"Validation cannot repair."* `VALIDATION_INTERNAL:132` —
    # *"No sub-engine may fix what it detects."* The transform (Law 53): rather
    # than judge whether a value IS a repair, give a repair nowhere to sit, then
    # check the shape. Adding `corrected_ledger`, `debit_entries` or
    # `revised_treatment` to either model turns this red.
    carried: set[str] = set()
    for name in model.model_fields:
        carried |= set(name.split("_"))
    assert carried & REPAIR_MARKERS == set()


def test_a_decision_cannot_be_mutated_after_creation() -> None:
    # INV-5 — history is never modified. Correction is a new version.
    made = decision()
    with pytest.raises(ValidationError):
        made.validation_status = ValidationStatus.REJECTED


def test_a_finding_cannot_be_mutated_after_creation() -> None:
    made = finding()
    with pytest.raises(ValidationError):
        made.blocking_severity = Severity.LOW


@pytest.mark.parametrize("field", [*ISSUE_LISTS, "failed_validation_rules"])
def test_the_collections_are_tuples_a_caller_cannot_append_to(field: str) -> None:
    # A list would let a caller add a finding to a frozen decision, or remove
    # one, and `frozen=True` would never see it. The model would be immutable
    # while its findings were not.
    made = decision(validation_status=ValidationStatus.REJECTED, validation_findings=(finding(),))
    carried = getattr(made, field)
    assert isinstance(carried, tuple)
    with pytest.raises(AttributeError):
        carried.append(None)  # type: ignore[attr-defined]


# ── Confidence — the one canonical type, imported, never redeclared ─────────


def test_a_float_confidence_is_refused() -> None:
    # The discriminator. A locally redeclared `Annotated[Decimal, Field(ge=0,
    # le=1)]` would ACCEPT 0.9 by coercing it — and `Decimal(0.9)` is
    # 0.90000000000000002220446…, the precision loss the canonical type exists
    # to prevent. Only the real `Confidence` refuses the type outright.
    with pytest.raises(ValidationError):
        decision(validation_confidence=0.9)


def test_an_integer_confidence_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(validation_confidence=1)


@pytest.mark.parametrize("bad", [Decimal("1.0001"), Decimal("-0.0001"), Decimal("2")])
def test_a_confidence_outside_the_agreed_range_is_refused(bad: Decimal) -> None:
    with pytest.raises(ValidationError):
        decision(validation_confidence=bad)


def test_a_confidence_with_five_decimal_places_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(validation_confidence=Decimal("0.12345"))


def test_a_confidence_is_stored_exactly_as_the_producer_wrote_it() -> None:
    assert decision(validation_confidence=Decimal("0.5")).validation_confidence == Decimal("0.5")


def test_the_boundary_values_of_the_agreed_range_are_accepted() -> None:
    assert decision(validation_confidence=Decimal("0.0000")).validation_confidence == Decimal("0")
    assert decision(validation_confidence=Decimal("1.0000")).validation_confidence == Decimal("1")


def test_a_missing_confidence_is_refused() -> None:
    # `VALIDATION_INTERNAL:98` — *"Every Result carries confidence. No Result
    # may omit it."*
    base: dict[str, object] = {
        "identity": envelope(),
        "related_decision_id": ArtifactId.new(),
        "related_artifact_version": FIRST_VERSION,
        "validation_status": ValidationStatus.APPROVED,
        "validation_findings": (),
        "validation_errors": (),
        "validation_warnings": (),
        "validation_risks": (),
        "failed_validation_rules": (),
        "supporting_evidence_references": (),
        "validation_reasoning": "clean",
        "validation_timestamp": AWARE,
    }
    with pytest.raises(ValidationError):
        ValidationDecision(**base)  # type: ignore[arg-type]


# ── Timestamp — timezone-aware only ─────────────────────────────────────────


def test_a_naive_timestamp_is_refused() -> None:
    # An audit record whose times cannot be ordered across zones is not an
    # audit record. `ENGINE_5:138` carries the timestamp; nothing says which
    # clock, so the offset must be in the value.
    with pytest.raises(ValidationError):
        decision(validation_timestamp=NAIVE)


def test_an_aware_timestamp_is_carried_verbatim() -> None:
    assert decision(validation_timestamp=AWARE).validation_timestamp == AWARE


# ── Identity — INV-3, INV-5, INV-9, one envelope and no second identity ─────


def test_the_validation_id_is_the_envelope_s_artifact_id() -> None:
    # `DATA_FLOW:32` — *"the identity envelope is universal and not repeated."*
    # A second stored identifier could disagree with the first, and then no
    # reader could tell which one traced the artifact.
    made = envelope()
    assert decision(identity=made).validation_id is made.artifact_id


def test_the_transaction_id_is_the_envelope_s() -> None:
    # INV-3 — *"Every artifact references exactly one."* Carried verbatim, not
    # regenerated: the Application Layer creates it and engines consume it.
    made = envelope()
    assert decision(identity=made).transaction_id is made.transaction_id


def test_a_decision_without_an_identity_envelope_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(identity=None)


def test_a_transaction_id_cannot_stand_in_for_the_related_decision_id() -> None:
    # INV-3 — three identity concepts, three distinct types. Same underlying
    # UUID, different jobs; if one could be passed where the other belongs the
    # separation is decorative.
    shared = uuid.uuid4()
    with pytest.raises(ValidationError):
        decision(related_decision_id=TransactionId(shared))


def test_the_related_decision_id_is_carried_verbatim() -> None:
    referenced = ArtifactId.new()
    assert decision(related_decision_id=referenced).related_decision_id is referenced


@pytest.mark.parametrize("bad", [0, -1])
def test_a_related_artifact_version_below_one_is_refused(bad: int) -> None:
    # Versions start at 1 (`identity.FIRST_VERSION`). A zero would make *"raised
    # against no version"* indistinguishable from *"unset"*.
    with pytest.raises(ValidationError):
        decision(related_artifact_version=bad)


def test_a_later_related_artifact_version_is_carried() -> None:
    # `DATA_FLOW:142` — a request raised against `v3` is superseded once `v4`
    # exists. The exact version must therefore be expressible, not just `v1`.
    assert decision(related_artifact_version=SECOND_VERSION).related_artifact_version == (
        SECOND_VERSION
    )


def test_a_decision_derived_from_an_earlier_version_records_its_parents() -> None:
    # INV-5 — the chain traces back to the raw artifact. Re-validation after a
    # clarification loop produces a new Validation Decision version, and the
    # envelope is what carries the lineage.
    same = ArtifactId.new()
    made = decision(
        identity=envelope(
            artifact_id=same,
            version=SECOND_VERSION,
            parent_versions=({"artifact_id": same, "version": FIRST_VERSION},),
        )
    )
    assert made.identity.parent_versions[0].version == FIRST_VERSION


# ── Failed validation rules and decision-level evidence references ──────────


def test_a_blank_failed_rule_name_is_refused() -> None:
    # `VALIDATION_INTERNAL:110` — a finding is *"never merged into a summary
    # that loses its rule identity."* An empty name is that loss.
    with pytest.raises(ValidationError):
        decision(failed_validation_rules=("",))


def test_failed_validation_rules_are_carried_in_the_order_given() -> None:
    rules = ("accounting correctness validation", "tax correctness validation")
    made = decision(
        validation_status=ValidationStatus.REJECTED,
        validation_findings=(finding(),),
        failed_validation_rules=rules,
    )
    assert made.failed_validation_rules == rules


def test_a_blank_decision_level_evidence_reference_is_refused() -> None:
    with pytest.raises(ValidationError):
        decision(supporting_evidence_references=(" ",))
