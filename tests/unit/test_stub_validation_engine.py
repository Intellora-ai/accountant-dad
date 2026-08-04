"""Engine 5's P3 stub — the tests that stop it fabricating permission to post.

Written to BREAK the stub, not to watch it pass (§J.1, §J.10). The dangerous
direction here is only ever one: INV-8 decides permission BEFORE execution, so
an approval this artifact carries wrongly is never caught downstream, because
downstream is Tally. Every test below leans against that one edge.

Three properties are asserted STRUCTURALLY rather than by sampling outputs,
because a sampled property holds for the inputs someone thought of:

  - the module's code references exactly one `ValidationStatus` member, and it
    is `REJECTED`. Adding an approving branch turns this red without anyone
    editing the assertion.
  - the module imports no other engine (AL-INV-5) and no Application Layer
    (AL-INV-4), and calls no clock. Read off its own import graph.
  - two Accounting Decisions that share an identity and differ in every
    accounting field produce EQUAL Validation Decisions — so no accounting
    content can reach the output, for any content whatsoever.

The schema-level guards this stub relies on are also broken on purpose here
(§J.5), so the tests never assume a rule is live that has quietly stopped being
enforced.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.decision import (
    AccountingDecision,
    DecisionStatus,
    JournalLine,
    UnresolvedDoubt,
)
from accountant_dad.artifacts.validation import (
    APPROVING_STATUSES,
    CANNOT_APPROVE_STATUSES,
    ResponsibleEngine,
    Severity,
    ValidationDecision,
    ValidationStatus,
)
from accountant_dad.confidence import MIN as CONFIDENCE_FLOOR
from accountant_dad.engines.validation_engine import stub
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

FIRST_VERSION = 1

#: One finding, and exactly one: the single true statement the stub can make.
EXPECTED_FINDINGS = 1

AT = datetime(2026, 8, 4, 9, 30, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 4, 17, 45, 0, tzinfo=UTC)

#: Anything that would make the stub unreproducible or reach outside itself.
#: `datetime` is imported for an annotation, which is why the ban is on the
#: CALL, not on the import.
CLOCK_CALLS = frozenset({"now", "utcnow", "today", "time", "monotonic"})
FORBIDDEN_IMPORTS = frozenset(
    {"random", "secrets", "time", "uuid", "urllib", "requests", "httpx", "openai", "anthropic"}
)


def _envelope(transaction: TransactionId) -> IdentityEnvelope:
    """A fresh version-1 envelope on a caller-chosen transaction.

    Real, never a stand-in (§J.6) — the same `IdentityEnvelope` the pipeline
    uses, so its own lineage rules run on every artifact these tests build.
    """
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=transaction,
    )


def _complete_decision(
    identity: IdentityEnvelope,
    *,
    ledger: str = "Office Supplies",
    amount: str = "1500.00",
    treatment: str = "Purchase of office supplies, expensed in the period.",
) -> AccountingDecision:
    """A COMPLETE, balanced decision — the shape a real Engine 5 would approve."""
    return AccountingDecision(
        identity=identity,
        decision_status=DecisionStatus.COMPLETE,
        accounting_treatment=treatment,
        ledger_classification="Indirect Expenses",
        debit_entries=(JournalLine(ledger=ledger, amount=Decimal(amount)),),
        credit_entries=(JournalLine(ledger="Cash", amount=Decimal(amount)),),
        journal_structure="One debit, one credit.",
        tax_treatment="No input tax credit claimed.",
        accounting_assumptions=(),
        risk_indicators=(),
        decision_confidence=Decimal("0.9900"),
        supporting_reasoning="The supplier invoice states the amount, the date and the payee.",
        unresolved_doubts=(),
    )


def _incomplete_decision(identity: IdentityEnvelope) -> AccountingDecision:
    """An INCOMPLETE decision with no journal at all — the opposite extreme."""
    return AccountingDecision(
        identity=identity,
        decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
        accounting_treatment="Undetermined.",
        ledger_classification="Undetermined.",
        debit_entries=(),
        credit_entries=(),
        journal_structure="Not yet formed.",
        tax_treatment="Undetermined.",
        accounting_assumptions=(),
        risk_indicators=(),
        decision_confidence=Decimal("0.0100"),
        supporting_reasoning="The document does not state who supplied the goods.",
        unresolved_doubts=(
            UnresolvedDoubt(
                missing_fact="The supplier is not named on the document.",
                required_clarification="Ask the business who supplied these goods.",
            ),
        ),
    )


def _module_tree() -> ast.Module:
    """The stub's own source, parsed. Read off disk, not off a memory of it."""
    return ast.parse(pathlib.Path(str(stub.__file__)).read_text(encoding="utf-8"))


# ── the one that must never go quiet ───────────────────────────────────────


def test_the_emitted_status_is_not_an_approving_one() -> None:
    """INV-8. If this ever passes with an approving status, the stub has
    fabricated permission to post into a real ledger."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )

    assert result.validation_status not in APPROVING_STATUSES
    assert result.validation_status in CANNOT_APPROVE_STATUSES
    assert result.validation_status is ValidationStatus.REJECTED


def test_no_input_shape_reaches_an_approving_status() -> None:
    """Both decision statuses, balanced and empty journals, both versions."""
    transaction = TransactionId.new()
    identity = _envelope(transaction)
    decisions = (
        _complete_decision(identity),
        _complete_decision(identity, ledger="Rent", amount="0.01"),
        _incomplete_decision(identity),
    )

    for decision in decisions:
        result = stub.validate(decision, identity=_envelope(transaction), validation_timestamp=AT)
        assert result.validation_status not in APPROVING_STATUSES


def test_the_module_names_exactly_one_validation_status_and_it_is_rejected() -> None:
    """The output tests above only cover inputs someone thought of. This covers
    the code, so a new `if ...: return Approved` branch is red on arrival."""
    referenced = {
        node.attr
        for node in ast.walk(_module_tree())
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ValidationStatus"
    }
    assert referenced == {"REJECTED"}, (
        f"the stub references {sorted(referenced)}. A P3 stub that can reach an "
        "approving status has fabricated permission to post (INV-8)."
    )


# ── it fabricates nothing ──────────────────────────────────────────────────


def test_the_finding_disclaims_a_defect_instead_of_alleging_one() -> None:
    """Naming a fake defect is the same fabrication as a fake approval."""
    finding = stub.NO_VALIDATION_PERFORMED
    said = f"{finding.what_failed} {finding.why_it_failed}".lower()

    assert "no validation was performed" in said
    assert "no defect in the accounting decision was detected" in said
    assert "none is alleged" in said


def test_the_finding_is_a_constant_so_it_cannot_describe_any_decision() -> None:
    """Built at import from nothing. Two unrelated decisions get the identical
    finding object — which is what makes "it inspected nothing" structural."""
    transaction = TransactionId.new()
    identity = _envelope(transaction)
    first = stub.validate(
        _complete_decision(identity), identity=_envelope(transaction), validation_timestamp=AT
    )
    second = stub.validate(
        _incomplete_decision(identity), identity=_envelope(transaction), validation_timestamp=AT
    )

    assert first.validation_findings == (stub.NO_VALIDATION_PERFORMED,)
    assert second.validation_findings == (stub.NO_VALIDATION_PERFORMED,)
    assert first.validation_findings[0] is second.validation_findings[0]


def test_no_failed_validation_rule_is_named() -> None:
    """A named failed rule asserts a rule ran and did not hold. None ran."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )
    assert result.failed_validation_rules == ()


def test_confidence_is_the_floor_of_the_scale() -> None:
    """`ENGINE_5:558` — validation confidence never exceeds upstream confidence.
    The upstream decisions here carry 0.9900 and 0.0100; the floor is under both,
    which is the property no other constant has."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )
    assert result.validation_confidence == CONFIDENCE_FLOOR
    assert result.validation_confidence == Decimal("0.0000")


def test_the_evidence_reference_names_this_module_and_nothing_else() -> None:
    """The claim is "no validation was performed"; the module is the proof."""
    derived_from_the_module_itself = f"module:{stub.__name__}"
    assert derived_from_the_module_itself == stub.STUB_EVIDENCE_REFERENCE
    assert stub.STUB_EVIDENCE_REFERENCE.endswith("engines.validation_engine.stub")
    assert stub.NO_VALIDATION_PERFORMED.supporting_evidence_references == (
        stub.STUB_EVIDENCE_REFERENCE,
    )


# ── the contract the schema demands of a non-approving decision ────────────


def test_every_finding_names_a_responsible_engine_and_carries_evidence() -> None:
    """`ENGINE_5:228` — never simply "Validation Failed." Always exactly why."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )

    assert len(result.issues) == EXPECTED_FINDINGS
    for finding in result.issues:
        assert finding.responsible_engine in set(ResponsibleEngine)
        assert finding.supporting_evidence_references != ()
        assert finding.what_failed.strip()
        assert finding.why_it_failed.strip()
        assert finding.affected_artifact.strip()
        assert finding.recommended_next_step.strip()

    assert result.validation_findings[0].responsible_engine is ResponsibleEngine.ACCOUNTING
    assert result.validation_findings[0].blocking_severity is Severity.CRITICAL


def test_the_schema_would_refuse_this_decision_with_its_finding_removed() -> None:
    """Break it on purpose (§J.5). Proves the guard the stub leans on is LIVE —
    otherwise every test above passes against a rule that stopped enforcing."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )
    fields = result.model_dump()
    fields["validation_findings"] = ()

    with pytest.raises(ValidationError, match="Never simply"):
        ValidationDecision(**fields)


def test_the_schema_would_refuse_this_finding_under_an_approving_status() -> None:
    """The Critical finding is not decoration: it makes an approving status
    structurally impossible on this artifact, not merely absent from it."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )
    fields = result.model_dump()

    for approving in APPROVING_STATUSES:
        fields["validation_status"] = approving
        with pytest.raises(ValidationError, match="Critical finding"):
            ValidationDecision(**fields)


# ── nothing about the accounting reaches the output ────────────────────────


def test_accounting_content_cannot_reach_the_output() -> None:
    """Same identity, every accounting field different, results EQUAL.

    This is the general statement of "it reads no accounting field" — it holds
    for content nobody wrote a case for, which sampling never does.
    """
    transaction = TransactionId.new()
    shared = _envelope(transaction)
    validation_identity = _envelope(transaction)

    modest = _complete_decision(shared, ledger="Office Supplies", amount="1500.00")
    lavish = _complete_decision(
        shared,
        ledger="Capital Work In Progress",
        amount="9999999.99",
        treatment="Capitalised as an asset under construction.",
    )
    assert modest != lavish

    assert stub.validate(
        modest, identity=validation_identity, validation_timestamp=AT
    ) == stub.validate(lavish, identity=validation_identity, validation_timestamp=AT)


def test_the_identity_of_the_related_decision_is_copied_verbatim() -> None:
    transaction = TransactionId.new()
    decision_identity = _envelope(transaction)
    result = stub.validate(
        _complete_decision(decision_identity),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )

    assert result.related_decision_id == decision_identity.artifact_id
    assert result.related_artifact_version == decision_identity.version
    assert result.transaction_id == transaction


def test_the_input_decision_is_not_modified() -> None:
    """`ENGINE_5:213` — validation cannot repair, and `:554` — it never rewrites
    upstream artifacts."""
    transaction = TransactionId.new()
    decision = _complete_decision(_envelope(transaction))
    before = decision.model_copy(deep=True)

    stub.validate(decision, identity=_envelope(transaction), validation_timestamp=AT)

    assert decision == before


# ── no clock, no randomness, no forbidden neighbour ────────────────────────


def test_the_same_arguments_always_produce_the_same_artifact() -> None:
    """A clock or a UUID minted inside would break this immediately."""
    transaction = TransactionId.new()
    decision = _complete_decision(_envelope(transaction))
    identity = _envelope(transaction)

    first = stub.validate(decision, identity=identity, validation_timestamp=AT)
    second = stub.validate(decision, identity=identity, validation_timestamp=AT)

    assert first == second


def test_the_timestamp_and_identity_come_from_the_caller_verbatim() -> None:
    transaction = TransactionId.new()
    decision = _complete_decision(_envelope(transaction))
    identity = _envelope(transaction)

    assert (
        stub.validate(decision, identity=identity, validation_timestamp=AT).validation_timestamp
        == AT
    )
    later = stub.validate(decision, identity=identity, validation_timestamp=LATER)
    assert later.validation_timestamp == LATER
    assert later.identity is identity
    assert later.validation_id == identity.artifact_id


def test_the_module_calls_no_clock() -> None:
    called = {
        node.func.attr
        for node in ast.walk(_module_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & CLOCK_CALLS, f"the stub calls a clock: {sorted(called & CLOCK_CALLS)}"


def test_the_module_imports_no_other_engine_and_no_application_layer() -> None:
    """AL-INV-5 — engines never call each other. AL-INV-4 — the Application
    Layer calls engines, never the reverse."""
    imported: set[str] = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    assert not any(name.startswith("accountant_dad.engines") for name in imported), (
        f"an engine imports another engine (AL-INV-5): {sorted(imported)}"
    )
    assert not any(name.startswith("accountant_dad.services") for name in imported), (
        f"an engine imports the Application Layer (AL-INV-4): {sorted(imported)}"
    )
    roots = {name.split(".")[0] for name in imported}
    assert not roots & FORBIDDEN_IMPORTS, f"forbidden import: {sorted(roots & FORBIDDEN_IMPORTS)}"


# ── the one failure it is allowed to raise ─────────────────────────────────


def test_a_transaction_id_mismatch_is_refused_loudly() -> None:
    """It cannot be a finding — the fault is the Application Layer's, and that
    is not on the blameable list (`ENGINE_5:232`). So it fails loudly (Law 11)
    rather than emitting an artifact that breaks the audit chain."""
    decision = _complete_decision(_envelope(TransactionId.new()))
    foreign = _envelope(TransactionId.new())

    with pytest.raises(ValueError, match="same Transaction ID"):
        stub.validate(decision, identity=foreign, validation_timestamp=AT)


def test_a_matching_transaction_id_is_accepted() -> None:
    """The other half of the control: without this, the test above could pass
    because the function raises for everything."""
    transaction = TransactionId.new()
    result = stub.validate(
        _complete_decision(_envelope(transaction)),
        identity=_envelope(transaction),
        validation_timestamp=AT,
    )
    assert result.transaction_id == transaction
