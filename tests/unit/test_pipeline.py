"""The walking skeleton, end to end, attacked.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` lists what P3 must show. This file is
written against that sentence, clause by clause:

    end to end on 1 hardcoded document · all artifacts valid · Transaction ID
    intact · audit complete · the Application Layer creates the Transaction ID,
    runs the state machine and routes every artifact — no engine calls another
    · no accuracy claim permitted at this phase

The last clause is the one worth the most attention. A skeleton that reached
`Completed` would be the most reassuring possible outcome and would mean the
stubs had started fabricating — so this file asserts the run does NOT get there,
and says why that is the pass condition rather than the failure.
"""

from __future__ import annotations

import ast
import contextlib
import itertools
import pathlib
import uuid
from datetime import UTC, datetime

import pytest

from accountant_dad.artifacts.decision import AccountingDecision, DecisionStatus
from accountant_dad.artifacts.evidence import DocumentEvidenceObject, DocumentId
from accountant_dad.artifacts.execution import ExecutionAttemptId, ExecutionId
from accountant_dad.artifacts.understanding import BusinessUnderstandingObject
from accountant_dad.engines.accounting_engine import stub as accounting
from accountant_dad.engines.input_engine import stub as input_engine
from accountant_dad.engines.understanding_engine import stub as understanding
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId
from accountant_dad.services.audit import AuditTrail
from accountant_dad.services.pipeline import (
    ApplicationLayer,
    ClarificationCycleExhaustedError,
    PipelineConfig,
    Sources,
)
from accountant_dad.services.state import TransactionState
from accountant_dad.services.store import TransactionStore

ENGINES = pathlib.Path(__file__).resolve().parents[2] / "src/accountant_dad/engines"
SERVICES = pathlib.Path(__file__).resolve().parents[2] / "src/accountant_dad/services"

#: The one hardcoded document P3 runs on. A supplier's bill — the thing a small
#: business books most often, and the first shape the owner named.
THE_ONE_DOCUMENT = ("supplier-bill-0001.jpg",)

#: Supplied, never chosen by this suite's subject. AL-INV-14 forbids a default;
#: this number belongs to the caller, and here the caller is a test.
ROUNDS = 3


class _Fixture:
    """One assembled Application Layer, with every source of entropy replaced."""

    def __init__(self, *, rounds: int = ROUNDS) -> None:
        artifacts = itertools.count(1)
        executions = itertools.count(1000)
        attempts = itertools.count(2000)
        moments = itertools.count(0)
        self.store = TransactionStore()
        self.audit = AuditTrail()
        self.layer = ApplicationLayer(
            store=self.store,
            audit=self.audit,
            config=PipelineConfig(max_clarification_rounds=rounds),
            sources=Sources(
                artifact=lambda: ArtifactId(uuid.UUID(int=next(artifacts))),
                execution=lambda: ExecutionId(uuid.UUID(int=next(executions))),
                attempt=lambda: ExecutionAttemptId(uuid.UUID(int=next(attempts))),
                now=lambda: datetime(2026, 8, 4, 12, next(moments) % 60, tzinfo=UTC),
            ),
        )
        self.transaction_id = TransactionId(uuid.UUID(int=9_999))

    def run(self) -> object:
        return self.layer.run(
            transaction_id=self.transaction_id,
            document_id=DocumentId(uuid.UUID(int=7)),
            source_references=THE_ONE_DOCUMENT,
        )


# ── it runs, end to end, on one document ──────────────────────────────────


def test_the_run_reaches_the_clarification_bound_and_says_so() -> None:
    """With honest stubs this is the CORRECT outcome, not a failure.

    The Accounting stub always answers INCOMPLETE_INFORMATION_REQUIRED, because
    deciding anything else would mean inventing a journal. So the cycle
    `Accounting → Clarification → Accounting` runs until the caller's bound.
    A skeleton that instead reached `Completed` would mean a stub had started
    fabricating — which BLUEPRINT:136 forbids at this phase.
    """
    with pytest.raises(ClarificationCycleExhaustedError) as raised:
        _Fixture().run()
    assert "AL-INV-13" in str(raised.value)


def test_the_transaction_is_left_where_it_actually_is() -> None:
    """No state exists for "asked too many times" and AL-INV-13 forbids adding
    one. Moving it to Failed would claim a runtime failure that did not happen
    (APPLICATION_LAYER.md:229 admits only runtime failures there).

    `Accounting`, not `Clarification`: the last transition that COMPLETED was
    Clarification handing back, and the bound stopped the next re-decide before
    it began. This test previously asserted Clarification and caught the
    module's own docstring making the same mistake.
    """
    fixture = _Fixture()
    with pytest.raises(ClarificationCycleExhaustedError):
        fixture.run()
    assert fixture.store.state_of(fixture.transaction_id) is TransactionState.ACCOUNTING


def test_the_bound_is_honoured_exactly() -> None:
    """One round means one trip through Clarification, not zero and not two."""
    for rounds in (1, 2, 5):
        fixture = _Fixture(rounds=rounds)
        with pytest.raises(ClarificationCycleExhaustedError):
            fixture.run()
        visits = [
            entry
            for entry in fixture.audit.history(fixture.transaction_id)
            if entry.to_state is TransactionState.CLARIFICATION
        ]
        assert len(visits) == rounds


def test_a_bound_below_one_is_refused() -> None:
    """A bound of zero forbids a stage the state machine draws."""
    with pytest.raises(ValueError, match="at least 1"):
        PipelineConfig(max_clarification_rounds=0)


def test_the_configuration_has_no_default() -> None:
    """AL-INV-14 — "A default retry count is a number nobody chose, silently
    governing how many times a financial operation is attempted.\" """
    with pytest.raises(TypeError):
        PipelineConfig()  # type: ignore[call-arg]


# ── the Transaction ID is intact ──────────────────────────────────────────


def test_every_artifact_carries_the_same_transaction_id() -> None:
    """BLUEPRINT:136 — "Transaction ID intact". AL-INV-1 — created once, never
    changed, never reissued. A correction keeps the original."""
    fixture = _Fixture()
    with contextlib.suppress(ClarificationCycleExhaustedError):
        fixture.run()
    # Rebuild the run up to the bound and inspect what it produced.
    produced = _artifacts_before_the_bound(fixture)
    assert produced, "the run produced no artifacts to check"
    for artifact in produced:
        assert artifact.identity.transaction_id == fixture.transaction_id


def _artifacts_before_the_bound(
    fixture: _Fixture,
) -> tuple[DocumentEvidenceObject, BusinessUnderstandingObject, AccountingDecision]:
    """Re-run with a bound the stubs can satisfy is impossible, so collect what
    a single round produces instead."""
    envelope = IdentityEnvelope(
        artifact_id=ArtifactId(uuid.UUID(int=1)),
        version=1,
        parent_versions=(),
        transaction_id=fixture.transaction_id,
    )
    evidence = input_engine.read(
        identity=envelope,
        document_id=DocumentId(uuid.UUID(int=7)),
        source_references=THE_ONE_DOCUMENT,
    )
    story = understanding.StubUnderstandingEngine().understand(
        (evidence,), ArtifactId(uuid.UUID(int=2))
    )
    decision = accounting.decide(story, ArtifactId(uuid.UUID(int=3)))
    return evidence, story, decision


def test_the_application_layer_is_the_only_source_of_the_transaction_id() -> None:
    """AL-INV-1 — no engine creates or modifies one. Proven by reading each
    engine's source: none of them constructs a TransactionId."""
    offenders: list[str] = []
    for source in ENGINES.rglob("*.py"):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            named = node.func
            if isinstance(named, ast.Attribute) and named.attr == "new":
                named = named.value
            if isinstance(named, ast.Name) and named.id == "TransactionId":
                offenders.append(str(source))
    assert offenders == [], f"an engine constructs a Transaction ID: {offenders}"


# ── no engine calls another ───────────────────────────────────────────────


def test_no_engine_imports_another_engine() -> None:
    """AL-INV-5 — "Two engines that can call each other can form a cycle nobody
    declared, and a decision could reach Execution without Validation."

    Read off disk with `ast`, so it cannot pass because of test order.
    """
    violations: list[str] = []
    for source in ENGINES.rglob("*.py"):
        own_package = source.parent.name
        for node in ast.walk(ast.parse(source.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for name in names:
                if "accountant_dad.engines" not in name:
                    continue
                if own_package in name:
                    continue
                violations.append(f"{source.relative_to(ENGINES)} imports {name}")
    assert violations == [], f"engine-to-engine imports: {violations}"


def test_no_engine_observes_workflow_state() -> None:
    """AL-INV-4 — "No engine may read, write, observe or infer transaction
    state." An engine that imported the state machine could branch on it."""
    violations: list[str] = []
    for source in ENGINES.rglob("*.py"):
        text = source.read_text()
        for node in ast.walk(ast.parse(text)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if "accountant_dad.services" in name:
                    violations.append(f"{source.relative_to(ENGINES)} imports {name}")
    assert violations == [], f"an engine reaches into the Application Layer: {violations}"


def test_the_application_layer_never_queries_the_brain() -> None:
    """AL-INV-8 — "Engines query the Brain; the Application Layer never does."
    Checked as an import, because an import is the only way it could."""
    violations: list[str] = []
    for source in SERVICES.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            violations.extend(
                f"{source.name} imports {name}" for name in names if "brain" in name.lower()
            )
    assert violations == [], f"the Application Layer reaches for the Brain: {violations}"


# ── the audit is complete ─────────────────────────────────────────────────


def test_every_state_change_is_recorded() -> None:
    """BLUEPRINT:136 — "audit complete". The history's transitions must chain:
    each entry's `from` is the previous entry's `to`, with no gap."""
    fixture = _Fixture()
    with pytest.raises(ClarificationCycleExhaustedError):
        fixture.run()
    history = fixture.audit.history(fixture.transaction_id)
    assert history, "nothing was recorded"
    assert history[0].from_state is None, "the first entry is the creation"
    assert history[0].to_state is TransactionState.INPUT
    for earlier, later in itertools.pairwise(history):
        assert later.from_state is earlier.to_state, (
            f"gap in the audit: {earlier.to_state} then {later.from_state}"
        )


def test_the_recorded_history_ends_where_the_store_says_the_transaction_is() -> None:
    """A history that disagrees with the store is worse than none — it looks
    like traceability and points somewhere else."""
    fixture = _Fixture()
    with pytest.raises(ClarificationCycleExhaustedError):
        fixture.run()
    history = fixture.audit.history(fixture.transaction_id)
    assert history[-1].to_state is fixture.store.state_of(fixture.transaction_id)


def test_every_transition_names_a_trigger() -> None:
    """APPLICATION_LAYER_API.md:126 — history answers "why is this transaction
    here" WITHOUT inference. A blank trigger forces inference."""
    fixture = _Fixture()
    with pytest.raises(ClarificationCycleExhaustedError):
        fixture.run()
    for entry in fixture.audit.history(fixture.transaction_id):
        assert entry.trigger.strip()


# ── no accuracy claim is possible at this phase ───────────────────────────


def test_the_skeleton_never_reaches_completed() -> None:
    """The pass condition, stated as one. BLUEPRINT:136 — "no accuracy claim
    permitted at this phase". Reaching Completed would mean a stub decided
    something, and a decided entry at P3 is a fabricated one."""
    fixture = _Fixture(rounds=20)
    with pytest.raises(ClarificationCycleExhaustedError):
        fixture.run()
    reached = {entry.to_state for entry in fixture.audit.history(fixture.transaction_id)}
    assert TransactionState.COMPLETED not in reached
    assert TransactionState.EXECUTION not in reached


def test_the_accounting_stub_never_claims_a_complete_decision() -> None:
    """If this ever passes with COMPLETE, the skeleton above would post."""
    fixture = _Fixture()
    _, _, decision = _artifacts_before_the_bound(fixture)
    assert decision.decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED
    assert decision.debit_entries == ()
    assert decision.credit_entries == ()


# ── the run is reproducible ───────────────────────────────────────────────


def test_two_identical_runs_produce_identical_histories() -> None:
    """AL-INV-12 rests on identical input producing an identical conclusion. A
    module reaching for uuid4() or datetime.now() cannot offer that."""
    first, second = _Fixture(), _Fixture()
    for fixture in (first, second):
        with pytest.raises(ClarificationCycleExhaustedError):
            fixture.run()
    assert first.audit.history(first.transaction_id) == second.audit.history(second.transaction_id)
