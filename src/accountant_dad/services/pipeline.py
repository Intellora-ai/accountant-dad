"""The walking skeleton — the Application Layer running one transaction end to end.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` — P3 is done when the Application Layer
*"creates the Transaction ID, runs the state machine and routes every artifact —
no engine calls another."* This module is that sentence, executed.

IT ROUTES. IT DOES NOT REASON.
    `DATA_FLOW.md` §14 gives the Application Layer creating the Transaction ID,
    starting engines, routing artifacts, lifecycle, retrying and coordinating
    state transitions — and gives it *"any decision · any artifact · any
    confidence · any reasoning"* in the column of things it never owns.

    So every engine here is called as a function whose output is passed onward
    unread. This module never inspects a confidence, never compares a status to
    decide whether something is good, and never edits an artifact in flight
    (AL-INV-7). The one thing it reads out of an artifact is the Accounting
    Decision's *status*, because `DATA_FLOW.md:113` says that field exists
    precisely *"so a downstream engine can ask can this move forward? and get a
    structured answer rather than infer one from prose."* Reading the field the
    architecture created for routing is routing; reading the journal would be
    reasoning.

NO ENGINE CALLS ANOTHER (AL-INV-5).
    Every artifact passes through here. The six engines are imported by this
    module and by nothing else, and a test parses each engine's imports off
    disk to prove none of them imports a sibling. *"Two engines that can call
    each other can form a cycle nobody declared, and a decision could reach
    Execution without Validation."*

THE CLARIFICATION CYCLE HAS NO DOCUMENTED BOUND, SO THE CALLER SUPPLIES ONE.
    `APPLICATION_LAYER.md:223-224` draws `Accounting → Clarification` when a
    blocking doubt exists and `Clarification → Accounting` because *"Engine 3
    must re-decide first."* That is a cycle, and no locked document says how
    many times it may go round.

    With honest P3 stubs the cycle is not hypothetical: the Accounting stub
    always answers `INCOMPLETE_INFORMATION_REQUIRED`, because deciding anything
    else would be fabricating a journal. So the skeleton would spin forever.

    `max_clarification_rounds` is therefore REQUIRED with no default, exactly as
    `AL-INV-14` requires of every configuration value — *"A default retry count
    is a number nobody chose, silently governing how many times a financial
    operation is attempted."* Picking one here would also break the standing
    instruction never to set a number the owner did not give.

    **What happens at the bound is reported, not invented.** No locked document
    names a state for "asked too many times", and `AL-INV-13` forbids adding
    one. `ClarificationCycleExhaustedError` is raised and the transaction is
    left in `Clarification`, where it genuinely is. Moving it to `Failed` would
    claim a runtime failure that did not occur — `APPLICATION_LAYER.md:229`
    admits only *"a runtime failure that exhausted retries"* — and moving it
    onward would skip a stage.

    **Every artifact already produced is preserved on the exception.**
    `APPLICATION_LAYER.md:153` and `:313` both say the same thing about a run
    that cannot finish — *"Completed artifacts PRESERVED"*, *"Nothing
    fabricated"* — and this module used to discard all four on the way out,
    which is the one thing a run that fails is not allowed to do. The bound now
    raises carrying the same `RunResult` a completed pass returns, with
    `validation` and `execution` honestly `None` because neither engine ran.
    Engine 1's own `PipelineStageError.preserved` is the identical shape for
    the identical reason.

ENGINE 1 IS THE REAL ENGINE, AND IT READS THE CALLER'S ACTUAL DOCUMENT.
    `APPLICATION_LAYER.md:251` — step 1 of engine sequencing passes *"raw
    document(s) + Transaction ID"*. `APPLICATION_LAYER_CONTRACTS.md:24` names
    the same input artifact and `:28` makes *"at least one document supplied"* a
    precondition. Until this module was migrated it supplied no document at all:
    it called `engines/input_engine/stub.py`, whose own docstring records that
    it accepts no raw artifact, so the arrow the architecture draws carried
    nothing across it. `engines/input_engine/pipeline.py` — `cleaner` →
    `reader` → `parser` → `confidence` → `assembly` — takes the bytes and is
    what that arrow now carries.

    The Application Layer never looks inside `intake`. It does not sniff the
    media type, does not read the bytes, and does not pre-classify anything:
    `APPLICATION_LAYER_CONTRACTS.md:31` forbids all three, so `DocumentIntake`
    arrives already built by the caller and is handed on untouched.

ENGINE 1'S SETTINGS ARE THE CALLER'S, AND THIS MODULE HAS NO OPINION ON THEM.
    `input_engine.PipelineSettings` carries ten numbers — eight in
    `cleaner_settings`, plus `render_dpi` and `vision_fallback_threshold`. Not
    one of them has a value anywhere in this repository or in any locked
    document. `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md` names sixteen parameters
    and marks every one `UNSET`; `render_dpi` and the eight cleaner numbers are
    not among the sixteen at all.

    So `PipelineConfig.input_engine_settings` is **required with no default**,
    exactly like `max_clarification_rounds` and for the reason
    `APPLICATION_LAYER.md:326` gives — *"A missing required value is a startup
    failure, never a silent default."* Choosing a plausible `render_dpi` here
    would be this module inventing a number the owner never set, which
    `CLAUDE.md` §P forbids outright.

ARTIFACT IDS: ENGINE 1 NOW MINTS ITS OWN; THE OTHER FIVE STILL DO NOT.
    Every P3 stub takes its own artifact id as a parameter rather than minting
    one, so that each is a pure function and the suite can assert *same input,
    equal artifact*. Something has to supply them, and for Engines 2-6 that is
    still this module.

    `ENGINE_1:95` and `:253` assign intake identity to Engine 1, and the real
    Engine 1 honours it — `assembly.assemble` mints the Document ID itself, so
    `run` no longer takes one. One consequence is stated rather than left to be
    found: two runs of the same bytes no longer produce equal Document Evidence
    Objects, because that id is fresh each time. Nothing downstream may depend
    on it either way — `INV-9`, *"carries no accounting meaning and must never
    influence accounting decisions"* — and the audit trail this module owns
    holds no artifact id, so `AL-INV-12`'s reproducibility claim is untouched.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from accountant_dad.artifacts.clarification import ClarificationRequest
from accountant_dad.artifacts.decision import AccountingDecision, DecisionStatus
from accountant_dad.artifacts.evidence import DocumentEvidenceObject, HumanBusinessContext
from accountant_dad.artifacts.execution import ExecutionAttemptId, ExecutionId, ExecutionResult
from accountant_dad.artifacts.understanding import BusinessUnderstandingObject

# `APPROVING_STATUSES` is imported rather than retyped, so this module and the
# artifact cannot disagree about which statuses go forward (Law 19).
from accountant_dad.artifacts.validation import APPROVING_STATUSES, ValidationDecision
from accountant_dad.engines.accounting_engine import stub as accounting
from accountant_dad.engines.clarification_engine import stub as clarification

# THE REAL ENGINE 1, not `input_engine.stub`. See the module docstring,
# "ENGINE 1 IS THE REAL ENGINE". The alias keeps every call site reading as the
# engine it addresses rather than as the file that happens to implement it.
from accountant_dad.engines.input_engine import pipeline as input_engine
from accountant_dad.engines.tally_engine import stub as execution_engine
from accountant_dad.engines.understanding_engine import stub as understanding
from accountant_dad.engines.validation_engine import stub as validation
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId
from accountant_dad.services.audit import AuditTrail, Transition
from accountant_dad.services.state import TransactionState
from accountant_dad.services.store import TransactionStore


class ClarificationCycleExhaustedError(Exception):
    """The Accounting ↔ Clarification cycle hit the caller's bound.

    Deliberately not a state. `AL-INV-13` — *"If a state is not in the locked
    state machine, it does not exist."* The transaction is left in `Accounting`,
    which is where it actually is.

    `preserved` carries every artifact the run had already produced —
    `APPLICATION_LAYER.md:153`, *"Completed artifacts PRESERVED"*. Discarding
    them would throw away a real Document Evidence Object because a later stage
    could not finish, which is the one thing §8 says a stopped run must not do.
    """

    def __init__(self, message: str, preserved: RunResult) -> None:
        self.preserved = preserved
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Every value required, none defaulted (AL-INV-14)."""

    #: How many times `Accounting → Clarification → Accounting` may go round
    #: before the run gives up. No default: see the module docstring.
    max_clarification_rounds: int

    #: Every number Engine 1 needs, supplied by the caller. No default, because
    #: not one of the ten has a value in any locked document — see the module
    #: docstring, "ENGINE 1'S SETTINGS ARE THE CALLER'S".
    input_engine_settings: input_engine.PipelineSettings

    def __post_init__(self) -> None:
        if self.max_clarification_rounds < 1:
            raise ValueError(
                "max_clarification_rounds must be at least 1; a bound of zero "
                "forbids the Clarification stage the state machine draws"
            )


@dataclass(frozen=True, slots=True)
class Sources:
    """Every source of entropy the run needs, supplied rather than reached for.

    Not a testing convenience. `AL-INV-12` rests on identical input producing an
    identical conclusion, and a module calling `uuid4()` or `datetime.now()`
    cannot offer that — two runs of the same document would differ, and nothing
    downstream could tell a real difference from a fresh random number.
    """

    artifact: Callable[[], ArtifactId]
    execution: Callable[[], ExecutionId]
    attempt: Callable[[], ExecutionAttemptId]
    now: Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class RunResult:
    """What one pass produced. Artifacts in the order they were created."""

    transaction_id: TransactionId
    final_state: TransactionState
    evidence: DocumentEvidenceObject
    understanding: BusinessUnderstandingObject
    decisions: tuple[AccountingDecision, ...]
    clarifications: tuple[ClarificationRequest, ...]
    validation: ValidationDecision | None
    execution: ExecutionResult | None

    @property
    def artifacts(self) -> tuple[object, ...]:
        """Every artifact this run produced, in creation order."""
        made: list[object] = [self.evidence, self.understanding]
        made.extend(self.decisions)
        made.extend(self.clarifications)
        if self.validation is not None:
            made.append(self.validation)
        if self.execution is not None:
            made.append(self.execution)
        return tuple(made)


class ApplicationLayer:
    """Creates the Transaction ID, runs the state machine, routes every artifact.

    Every identifier and the clock are injected rather than called, so a run is
    reproducible
    and the tests need no clock and no randomness. That is not a testing
    convenience: `AL-INV-12` rests on identical input producing an identical
    conclusion, and a module reaching for `uuid4()` or `datetime.now()` cannot
    offer that.
    """

    def __init__(
        self,
        *,
        store: TransactionStore,
        audit: AuditTrail,
        config: PipelineConfig,
        sources: Sources,
    ) -> None:
        self._store = store
        self._audit = audit
        self._config = config
        self._sources = sources

    # ── identity ──────────────────────────────────────────────────────────

    def start_transaction(self, transaction_id: TransactionId) -> TransactionState:
        """`APPLICATION_LAYER_API.md:25` — the ONLY way a Transaction ID comes
        into existence, and `:32` — the postcondition is state `Input`.

        The id is passed in for the same reproducibility reason as `mint`. It is
        still created here in the sense that matters (AL-INV-1): no engine ever
        makes one, and nothing reuses one.
        """
        state = self._store.create(transaction_id)
        self._audit.record(
            transaction_id,
            Transition(
                from_state=None,
                to_state=state,
                at=self._sources.now(),
                trigger="start_transaction",
                engine=None,
                attempt=1,
            ),
        )
        return state

    def _advance(
        self, transaction_id: TransactionId, target: TransactionState, *, engine: str, attempt: int
    ) -> None:
        """One validated transition, recorded only after it completed (AL-INV-3)."""
        origin = self._store.state_of(transaction_id)
        self._store.move(transaction_id, target)
        self._audit.record(
            transaction_id,
            Transition(
                from_state=origin,
                to_state=target,
                at=self._sources.now(),
                trigger=f"{engine} produced its artifact",
                engine=engine,
                attempt=attempt,
            ),
        )

    # ── the run ───────────────────────────────────────────────────────────

    def run(
        self,
        *,
        transaction_id: TransactionId,
        intake: input_engine.DocumentIntake,
        human_business_context: HumanBusinessContext | None = None,
    ) -> RunResult:
        """One document, all the way through, artifact by artifact.

        Every engine is called exactly once per stage entry, its output is
        carried to the next stage by this method, and no engine is given
        another engine's address (AL-INV-5).

        `intake` is the caller's — the raw bytes, the media type the caller
        DECLARES, and the source references — handed to Engine 1 unread
        (`APPLICATION_LAYER_CONTRACTS.md:24,31`). `human_business_context` is
        optional because the locked contract calls it optional, and it is
        likewise passed through without being looked at: a human note is
        evidence, and reading it here to decide anything would be reasoning.

        Engine 1 failing raises out of this method rather than being turned
        into a state. Retry is `APPLICATION_LAYER.md` §8's, its three
        configuration values are required-with-no-default and none of them
        exists yet, so nothing here has exhausted anything; moving the
        transaction to `Failed` would claim a retry policy ran (`:229`) and
        swallowing the exception is forbidden outright (`§12`). The transaction
        is left in `Input`, which is where it is.
        """
        self.start_transaction(transaction_id)

        evidence = input_engine.run(
            intake,
            identity=self._envelope(transaction_id),
            settings=self._config.input_engine_settings,
            # The injected clock, never `datetime.now()` — the same rule the rest
            # of this class already follows, and the reason a run is reproducible.
            recorded_at=self._sources.now(),
            human_business_context=human_business_context,
        )

        self._advance(transaction_id, TransactionState.UNDERSTANDING, engine="input", attempt=1)
        story = understanding.StubUnderstandingEngine().understand(
            (evidence,), self._sources.artifact()
        )

        self._advance(
            transaction_id, TransactionState.ACCOUNTING, engine="understanding", attempt=1
        )

        decisions: list[AccountingDecision] = []
        requests: list[ClarificationRequest] = []

        for attempt in range(1, self._config.max_clarification_rounds + 1):
            decision = accounting.decide(story, self._sources.artifact())
            decisions.append(decision)

            if decision.decision_status is not DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED:
                break

            # The status field exists for exactly this question (DATA_FLOW:113).
            self._advance(
                transaction_id, TransactionState.CLARIFICATION, engine="accounting", attempt=attempt
            )
            requests.append(
                clarification.emit_clarification_request(
                    decision,
                    artifact_id=self._sources.artifact(),
                    clarification_id=self._sources.artifact(),
                )
            )
            self._advance(
                transaction_id,
                TransactionState.ACCOUNTING,
                engine="clarification",
                attempt=attempt,
            )
        else:
            raise ClarificationCycleExhaustedError(
                f"the Accounting-Clarification cycle ran "
                f"{self._config.max_clarification_rounds} times and the decision is "
                f"still {DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED.value}. No "
                "locked document names a state for this, and AL-INV-13 forbids "
                "inventing one, so the transaction is left in Accounting, which is "
                "where it is: Clarification handed back and the bound stopped the "
                "next re-decide. Every artifact already produced is on this "
                "exception's `preserved` attribute; nothing is discarded and "
                "nothing stands in for the stages that never ran.",
                RunResult(
                    transaction_id=transaction_id,
                    final_state=self._store.state_of(transaction_id),
                    evidence=evidence,
                    understanding=story,
                    decisions=tuple(decisions),
                    clarifications=tuple(requests),
                    validation=None,
                    execution=None,
                ),
            )

        self._advance(transaction_id, TransactionState.VALIDATION, engine="accounting", attempt=1)
        verdict = validation.validate(
            decisions[-1],
            identity=self._envelope(transaction_id),
            validation_timestamp=self._sources.now(),
        )

        # An engine's conclusion decides the route; this module does not judge it.
        if verdict.validation_status not in APPROVING_STATUSES:
            self._advance(transaction_id, TransactionState.FAILED, engine="validation", attempt=1)
            return RunResult(
                transaction_id=transaction_id,
                final_state=self._store.state_of(transaction_id),
                evidence=evidence,
                understanding=story,
                decisions=tuple(decisions),
                clarifications=tuple(requests),
                validation=verdict,
                execution=None,
            )

        self._advance(transaction_id, TransactionState.EXECUTION, engine="validation", attempt=1)
        posted = execution_engine.report_nothing_posted(
            identity=self._envelope(transaction_id),
            execution_id=self._sources.execution(),
            execution_attempt_id=self._sources.attempt(),
            validation=verdict,
            execution_timestamp=self._sources.now(),
        )
        self._advance(transaction_id, TransactionState.COMPLETED, engine="execution", attempt=1)
        return RunResult(
            transaction_id=transaction_id,
            final_state=self._store.state_of(transaction_id),
            evidence=evidence,
            understanding=story,
            decisions=tuple(decisions),
            clarifications=tuple(requests),
            validation=verdict,
            execution=posted,
        )

    # ── helpers ───────────────────────────────────────────────────────────

    def _envelope(self, transaction_id: TransactionId) -> IdentityEnvelope:
        return IdentityEnvelope(
            artifact_id=self._sources.artifact(),
            version=1,
            parent_versions=(),
            transaction_id=transaction_id,
        )
