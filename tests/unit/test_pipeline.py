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

REAL ENGINE 1, NEVER A STAND-IN FOR IT.
    `APPLICATION_LAYER.md:251` passes Engine 1 *"raw document(s) + Transaction
    ID"*. Until this suite was migrated the Application Layer called
    `engines/input_engine/stub.py`, which accepts no raw document at all — so
    the arrow the architecture draws carried nothing, and every test here could
    pass with Engine 1 disconnected. Every run below now drives the REAL
    `cleaner → reader → parser → confidence → assembly` chain on a real PDF
    this file builds, per `CLAUDE.md` §J.6.

    `INVOICE_LINES` is ground truth: the fixture PDF is rendered FROM it, so
    checking those strings reached the artifact checks against what was
    actually put on the page, not against a transcription of whatever a run
    happened to produce.

WHAT WOULD PROVE THE MIGRATION WRONG, AND WHERE THAT IS CHECKED.
    Wiring that only LOOKS done is the failure mode. Three separate tests are
    shaped to catch it, and each one fails if the stub is restored:

      - `test_the_application_layer_routes_what_the_real_engine_read` asserts on
        the evidence THE RUN produced — reached through the exception's
        `preserved`, never rebuilt by this file, because an artifact this file
        built itself would pass whatever the Application Layer called
      - `test_engine_1_mints_the_document_id_not_the_application_layer` proves
        the id is Engine 1's: every id the Application Layer supplies comes from
        a deterministic counter here, so two runs agreeing would mean it came
        from this file
      - `test_the_application_layer_does_not_import_the_input_engine_stub` reads
        `src/accountant_dad/services/` off disk, so a re-import cannot slip back
        in behind a passing behavioural test (Law 38)
"""

from __future__ import annotations

import ast
import inspect
import itertools
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import first_party
import pymupdf
import pytest
from authored_source import authored_source

from accountant_dad.artifacts.decision import AccountingDecision, DecisionStatus, JournalLine
from accountant_dad.artifacts.evidence import (
    Corroborated,
    HumanBusinessContext,
    Provenance,
    SourceType,
)
from accountant_dad.artifacts.execution import ExecutionAttemptId, ExecutionId
from accountant_dad.artifacts.validation import ValidationDecision, ValidationStatus
from accountant_dad.engines.accounting_engine import stub as accounting_stub
from accountant_dad.engines.input_engine import cleaner, config, reader
from accountant_dad.engines.input_engine import pipeline as input_engine
from accountant_dad.engines.validation_engine import stub as validation_stub
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId
from accountant_dad.services.audit import AuditTrail, Transition
from accountant_dad.services.pipeline import (
    ApplicationLayer,
    ApprovedWithWarningHasNoStateError,
    ClarificationCycleExhaustedError,
    PipelineConfig,
    RunResult,
    Sources,
)
from accountant_dad.services.state import TransactionState
from accountant_dad.services.store import TransactionStore

#: The AUTHORED package, never this file's own location (L-013, L-006).
#:
#: These two constants used to read
#:
#:     pathlib.Path(__file__).resolve().parents[2] / "src/accountant_dad/engines"
#:
#: which is the third spelling `authored_repo_root`'s docstring names: no module
#: object and no `inspect` call, just the test file asking where IT is. Under
#: `mutmut run` this file lives in `mutants/`, so `parents[2]` is the mutation
#: copy and both constants pointed at INSTRUMENTED source — and five structural
#: guards below (`test_the_application_layer_does_not_import_the_input_engine_
#: stub`, `test_the_application_layer_is_the_only_source_of_the_transaction_id`,
#: `test_no_engine_imports_another_engine`, `test_no_engine_observes_workflow_
#: state`, `test_the_application_layer_never_queries_the_brain`) asked their
#: question about the repository and read mutmut's rewrite instead.
#:
#: They agreed anyway, because mutmut's dispatcher adds `import os` and
#: `from mutmut.__main__ import ...` and none of the five looks for those names.
#: That is luck, not design — L-013 states it about the `do_not_mutate` list in
#: exactly these words — and `engines/input_engine/*.py` and `services/state.py`
#: ARE mutated, so the luck is not even uniform across what these constants walk.
#:
#: `first_party.package_root()` resolves through `authored_source.authored_path`,
#: so the tree is authored BY CONSTRUCTION rather than by a path that happens to
#: be right. It is also read rather than restated: where the package sits on disk
#: is `first_party`'s answer, not a second copy of the layout here (Law 19).
_PACKAGE = first_party.package_root()
ENGINES = _PACKAGE / "engines"
SERVICES = _PACKAGE / "services"

#: The one hardcoded document P3 runs on. A supplier's bill — the thing a small
#: business books most often, and the first shape the owner named.
THE_ONE_DOCUMENT = ("supplier-bill-0001.pdf",)

#: Ground truth. The fixture PDF is rendered FROM this tuple, so asserting that
#: these strings reached the artifact asserts against what was drawn on the
#: page rather than against whatever a run produced.
INVOICE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
    "Invoice No INV-2026-0481",
)

#: Supplied, never chosen by this suite's subject. AL-INV-14 forbids a default;
#: this number belongs to the caller, and here the caller is a test.
ROUNDS = 3

#: Test parameters, not product defaults. `PipelineConfig.input_engine_settings`
#: still requires the caller to supply every one of them, and no locked document
#: gives any of them a value — see `services/pipeline.py`, "ENGINE 1'S SETTINGS
#: ARE THE CALLER'S". These are this file's own choices for its own fixture,
#: matching `test_input_engine_pipeline.py`'s.
RENDER_DPI = 150
NO_VISION_FALLBACK = Decimal("0.0")

#: The stub's own signature phrase, from the artifact it emitted
#: (`engines/input_engine/stub.py`, `NO_READING_HAPPENED`). Asserted ABSENT, so
#: restoring the stub turns this suite red rather than leaving it green on an
#: empty artifact.
STUB_MARKER = "P3 stub"

#: The two artifacts a run makes exactly one of before the bound: the Document
#: Evidence Object and the Business Understanding Object. Named so the
#: completeness check below reads as arithmetic rather than as a magic number.
SINGLETON_ARTIFACTS = 2

#: A document that could not be read produces exactly one marker — the one that
#: names the stage that stopped. Asserted as a count rather than a lower bound:
#: a second marker would mean something else was recorded as uncertain too, and
#: that is a change worth failing on rather than absorbing.
ONE_MARKER = 1


# ── a typed facade over PyMuPDF, for AUTHORING the fixture only ───────────
#
# Identical in spirit to the facades `test_input_engine_pipeline.py` and
# `test_input_engine_reader.py` already declare over the same untyped
# dependency, for the same reason: PyMuPDF ships `py.typed` but leaves its
# functions unannotated, `mypy --strict` refuses a bare call, and this
# repository counts suppressions and blocks on any increase. Those facades are
# module-private to their own files and are not importable from here.


class _Page(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...


class _Document(Protocol):
    def new_page(self, *, width: float, height: float) -> _Page: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _Document: ...


open_pdf = cast(_NewDocument, pymupdf.open)


def an_invoice_pdf(lines: tuple[str, ...] = INVOICE_LINES) -> bytes:
    """A one-page PDF carrying a real text layer, built from `INVOICE_LINES`."""
    document = open_pdf()
    page = document.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    drawn = bytes(document.tobytes())
    document.close()
    return drawn


def a_cleaner_settings() -> cleaner.CleanerSettings:
    """Eight numbers, all this file's own, permissive enough that a normal
    rendered page cleans without `cleaner` deciding the original is safer."""
    return cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=3.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=10,
        max_ink_loss_fraction=1.0,
    )


def a_confidence_parameters(
    vision_fallback: Decimal = NO_VISION_FALLBACK,
) -> config.ConfidenceParameters:
    """All sixteen confidence parameters, in full, because none has a default.

    `ENGINE_1_CONFIDENCE_PARAMETERS.md` marks every one of the sixteen `UNSET`,
    and `CLAUDE.md` §P forbids a default for any of them — so anything that runs
    Engine 1 must state all sixteen, and this factory is what that costs.

    These are the TEST's own numbers and not recommended operating points
    (Law 52). Only `ocr_vision_fallback` changes any behaviour today: it is the
    one parameter Engine 1's pipeline consumes, handed to `reader.read` as its
    vision-fallback threshold. The other fifteen are carried and unread, which
    `MEASUREMENT_FRAMEWORK.md:258` — *"confidence gates nothing"* — says is the
    correct state of this build.
    """
    return config.ConfidenceParameters(
        ocr_region_accept=Decimal("0.0000"),
        ocr_vision_fallback=vision_fallback,
        field_confidence_floor=Decimal("0.0000"),
        field_risky_mark=Decimal("0.0000"),
        document_confidence_floor=Decimal("0.0000"),
        human_review_trigger=Decimal("0.0000"),
        retry_trigger=Decimal("0.0000"),
        retry_max_attempts=0,
        classification_accept=Decimal("0.0000"),
        table_structure_accept=Decimal("0.0000"),
        table_cell_accept=Decimal("0.0000"),
        capture_fidelity_floor=Decimal("0.0000"),
        document_score_rule=config.DocumentScoreRule.MIN,
        document_score_weights={"the only field": Decimal("1.0000")},
        worst_k=1,
        processing_budget_ms=1,
    )


def an_input_engine_settings() -> input_engine.PipelineSettings:
    return input_engine.PipelineSettings(
        cleaner_settings=a_cleaner_settings(),
        render_dpi=RENDER_DPI,
        confidence_parameters=a_confidence_parameters(NO_VISION_FALLBACK),
    )


def an_intake(
    *,
    document: bytes | None = None,
    source_references: tuple[str, ...] = THE_ONE_DOCUMENT,
) -> input_engine.DocumentIntake:
    """The raw document the Application Layer hands Engine 1.

    The media type is DECLARED here, never sniffed from the bytes: the
    Application Layer is forbidden from pre-classifying a document
    (`APPLICATION_LAYER_CONTRACTS.md:31`), so the caller states it.
    """
    return input_engine.DocumentIntake(
        document=an_invoice_pdf() if document is None else document,
        media_type=reader.MediaType.PDF,
        source_references=source_references,
    )


def a_human_note(
    text: str = "Advance paid to the supplier before delivery.",
) -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="chat:session-1",
            evidence_reference="message 1",
            timestamp=datetime(2026, 8, 5, 9, 0, tzinfo=UTC),
            confidence=Decimal("1.0000"),
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


@dataclass(frozen=True, slots=True)
class _CanonicalRun:
    """Everything one run to the bound produced, as immutable values."""

    transaction_id: TransactionId
    preserved: RunResult
    history: tuple[Transition, ...]
    final_state: TransactionState
    message: str


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
            config=PipelineConfig(
                max_clarification_rounds=rounds,
                input_engine_settings=an_input_engine_settings(),
            ),
            sources=Sources(
                artifact=lambda: ArtifactId(uuid.UUID(int=next(artifacts))),
                execution=lambda: ExecutionId(uuid.UUID(int=next(executions))),
                attempt=lambda: ExecutionAttemptId(uuid.UUID(int=next(attempts))),
                now=lambda: datetime(2026, 8, 4, 12, next(moments) % 60, tzinfo=UTC),
            ),
        )
        self.transaction_id = TransactionId(uuid.UUID(int=9_999))

    def run(
        self,
        *,
        intake: input_engine.DocumentIntake | None = None,
        human_business_context: HumanBusinessContext | None = None,
    ) -> RunResult:
        return self.layer.run(
            transaction_id=self.transaction_id,
            intake=an_intake() if intake is None else intake,
            human_business_context=human_business_context,
        )

    def to_the_bound(
        self, *, human_business_context: HumanBusinessContext | None = None
    ) -> _CanonicalRun:
        """Run, expect the bound, and return everything the run produced.

        Read off the exception rather than rebuilt here. An artifact this file
        assembled itself would prove nothing about what the Application Layer
        routed — it would pass whether the layer called the real engine or the
        stub, which is exactly the false green this migration exists to remove.
        """
        with pytest.raises(ClarificationCycleExhaustedError) as raised:
            self.run(human_business_context=human_business_context)
        return _CanonicalRun(
            transaction_id=self.transaction_id,
            preserved=raised.value.preserved,
            history=self.audit.history(self.transaction_id),
            final_state=self.store.state_of(self.transaction_id),
            message=str(raised.value),
        )


@pytest.fixture(scope="module")
def one_run() -> _CanonicalRun:
    """One standard run, shared by the tests that only READ its outcome.

    Engine 1 now reads a real document, and Docling's inference is the expensive
    part of it — measured at roughly 12s per run under coverage instrumentation,
    against a whole-suite baseline of 78s. Nine full readings to make nine
    assertions about ONE run's outcome is the same reading paid for nine times.

    Nothing mutable is shared, so this does not weaken `CLAUDE.md` §J.6: every
    field above is frozen or already immutable — `RunResult` is a frozen
    dataclass, its artifacts are immutable by INV-5, and `AuditTrail.history`
    returns a tuple by construction. No test can disturb another's values, which
    is the property isolation exists to give. Tests that need a different bound,
    a different document, or a genuinely SECOND independent run build their own
    `_Fixture` — and three below do exactly that.

    `test_input_engine_pipeline.py`'s own session fixture makes the same trade
    for the same measured reason.
    """
    return _Fixture().to_the_bound()


@pytest.fixture(scope="module")
def second_run() -> _CanonicalRun:
    """A SECOND, genuinely independent run of the same bytes through the same
    real engines — the other half of every claim that compares two runs.

    Two tests need one and each built its own, which is three full runs to
    compare two. `test_two_identical_runs_produce_identical_histories` already
    says in words that it and `test_engine_1_mints_the_document_id...` assert
    *"about the same two runs"*; this makes that literally so, and pays for the
    second run once.

    IT IS STILL A SECOND RUN, not a copy of the first. `_Fixture()` is
    constructed fresh here and driven through `ApplicationLayer.run` again, so
    the id that must differ and the history that must not are both produced by
    an independent pass — which is the entire content of both assertions.
    """
    return _Fixture().to_the_bound()


# ── it runs, end to end, on one document ──────────────────────────────────


def test_the_run_reaches_the_clarification_bound_and_says_so(one_run: _CanonicalRun) -> None:
    """With honest stubs this is the CORRECT outcome, not a failure.

    The Accounting stub always answers INCOMPLETE_INFORMATION_REQUIRED, because
    deciding anything else would mean inventing a journal. So the cycle
    `Accounting → Clarification → Accounting` runs until the caller's bound.
    A skeleton that instead reached `Completed` would mean a stub had started
    fabricating — which BLUEPRINT:136 forbids at this phase.
    """
    assert "AL-INV-13" in one_run.message


def test_the_transaction_is_left_where_it_actually_is(one_run: _CanonicalRun) -> None:
    """No state exists for "asked too many times" and AL-INV-13 forbids adding
    one. Moving it to Failed would claim a runtime failure that did not happen
    (APPLICATION_LAYER.md:229 admits only runtime failures there).

    `Accounting`, not `Clarification`: the last transition that COMPLETED was
    Clarification handing back, and the bound stopped the next re-decide before
    it began. This test previously asserted Clarification and caught the
    module's own docstring making the same mistake.
    """
    assert one_run.final_state is TransactionState.ACCOUNTING
    assert one_run.preserved.final_state is TransactionState.ACCOUNTING


def test_the_bound_is_honoured_exactly() -> None:
    """One round means one trip through Clarification, not zero and not two."""
    for rounds in (1, 2, 5):
        fixture = _Fixture(rounds=rounds)
        run = fixture.to_the_bound()
        visits = [
            entry for entry in run.history if entry.to_state is TransactionState.CLARIFICATION
        ]
        assert len(visits) == rounds
        assert len(run.preserved.clarifications) == rounds


def test_a_bound_below_one_is_refused() -> None:
    """A bound of zero forbids a stage the state machine draws."""
    with pytest.raises(ValueError, match="at least 1"):
        PipelineConfig(max_clarification_rounds=0, input_engine_settings=an_input_engine_settings())


def test_the_configuration_has_no_default() -> None:
    """AL-INV-14 — "A default retry count is a number nobody chose, silently
    governing how many times a financial operation is attempted.\" """
    with pytest.raises(TypeError):
        PipelineConfig()  # type: ignore[call-arg]


def test_no_value_in_the_configuration_has_a_default() -> None:
    """The same rule, applied to every field including the ten Engine 1 needs.

    `cleaner_settings`, `render_dpi` and `vision_fallback_threshold` have no
    value in any locked document — `ENGINE_1_CONFIDENCE_PARAMETERS.md` marks all
    sixteen of its parameters UNSET and does not name `render_dpi` or any
    cleaner number at all. A default here would be the Application Layer
    choosing how hard to denoise somebody's invoice.

    Asserted over EVERY parameter rather than the two that exist today, so a
    field added later with a comfortable default fails this immediately.
    """
    parameters = inspect.signature(PipelineConfig).parameters
    defaulted = sorted(
        name
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty
    )
    assert defaulted == [], f"AL-INV-14: these carry a number nobody chose: {defaulted}"
    assert "input_engine_settings" in parameters


# ── it runs the REAL Engine 1 ─────────────────────────────────────────────


def test_the_application_layer_routes_what_the_real_engine_read(one_run: _CanonicalRun) -> None:
    """The migration, asserted on the artifact THE RUN produced.

    `APPLICATION_LAYER.md:251` — the Application Layer passes Engine 1 *"raw
    document(s)"*. The stub accepted none and emitted an empty
    `StructuredDocument`, so with it wired every line drawn on the page is
    missing and the stub's own reliability sentence is present instead.
    """
    evidence = one_run.preserved.evidence

    assert evidence.structured_document.extracted_text != ""
    for line in INVOICE_LINES:
        assert line in evidence.structured_document.extracted_text, (
            f"{line!r} was drawn on the fixture PDF and did not reach the artifact"
        )
    assert STUB_MARKER not in evidence.confidence_report.reliability_information
    assert evidence.source_references == THE_ONE_DOCUMENT


def test_the_five_source_readers_below_walk_the_authored_tree() -> None:
    """THE PRECONDITION FOR EVERY STRUCTURAL GUARD IN THIS FILE.

    Five tests below answer a question about THIS REPOSITORY by parsing files
    under `ENGINES` and `SERVICES`. That is only an answer about the repository
    while those two constants name the AUTHORED tree. Until this was fixed they
    read

        pathlib.Path(__file__).resolve().parents[2] / "src/accountant_dad/engines"

    — the third spelling `authored_repo_root`'s docstring names, and the one
    L-013 says cost a whole mutation run. Under `mutmut run` this file lives in
    `mutants/`, so `parents[2]` IS the mutation copy and all five guards walked
    instrumented source.

    Checked by reading this file's own AUTHORED source rather than by comparing
    paths: on an ordinary run the authored tree and the mutation copy do not
    both exist, so a path comparison could not fail and would be a test that
    cannot fail (§J.3). The assignment either mentions `__file__` or it does
    not, and that is true on every run.

    Reverting either constant to a `__file__`-rooted expression turns this red.
    """
    assignments = {
        target.id: ast.unparse(node.value)
        for node in ast.parse(authored_source(sys.modules[__name__])).body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"ENGINES", "SERVICES", "_PACKAGE"}
    }
    assert set(assignments) == {"_PACKAGE", "ENGINES", "SERVICES"}, (
        f"the constants this guard exists to pin were renamed or removed: {sorted(assignments)}"
    )
    rooted_in_this_file = sorted(
        f"{name} = {expression}"
        for name, expression in assignments.items()
        if "__file__" in expression
    )
    assert rooted_in_this_file == [], (
        "these name a source tree derived from this test file's own location, "
        "which is `mutants/` under mutation — so the five structural guards "
        "below would parse mutmut's rewrite and report about it. Use "
        "`first_party.package_root()`, which resolves through "
        "`authored_source.authored_path`:\n  " + "\n  ".join(rooted_in_this_file)
    )


def test_the_application_layer_does_not_import_the_input_engine_stub() -> None:
    """Law 38 — "Never let temporary solutions become permanent architecture."

    Read off disk, so re-importing the stub behind a still-passing behavioural
    test is impossible. The other five stubs are deliberately still allowed:
    Engines 2-6 are frozen and only Engine 1 is authorised (Amendment 3).
    """
    offenders: list[str] = []
    for source in SERVICES.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [f"{node.module}.{alias.name}" for alias in node.names]
            offenders.extend(
                f"{source.name} imports {name}"
                for name in imported
                if name == "accountant_dad.engines.input_engine.stub"
            )
    assert offenders == [], f"the Application Layer is back on the Engine 1 stub: {offenders}"


def test_engine_1_mints_the_document_id_not_the_application_layer(
    one_run: _CanonicalRun, second_run: _CanonicalRun
) -> None:
    """`ENGINE_1:95`, `:253` — the Document ID *"is assigned by the Input Engine
    at intake."*

    Every id this Application Layer supplies comes from a deterministic counter
    in `_Fixture`, so two runs of the same bytes agree on all of them. A
    Document ID that DIFFERS between those two runs therefore cannot have come
    from here — it was minted inside Engine 1, which is where the locked
    specification puts it.
    """
    assert one_run.preserved.evidence.document_id != second_run.preserved.evidence.document_id

    # The Application Layer no longer has one to give.
    assert "document_id" not in inspect.signature(ApplicationLayer.run).parameters


def test_the_human_note_reaches_engine_1_verbatim() -> None:
    """`APPLICATION_LAYER_CONTRACTS.md:24` — the input artifact includes an
    *optional human business context*, and `CLAUDE.md` §O — *"a human note is
    evidence, not truth."*

    The Application Layer must carry it without reading it. Asserted on the
    text that came back out of the artifact, character for character.
    """
    note = a_human_note()
    evidence = _Fixture().to_the_bound(human_business_context=note).preserved.evidence

    assert evidence.human_business_context is not None
    assert evidence.human_business_context.original_user_text == note.original_user_text
    # Evidence, never merged into the reading: ENGINE_1:233 — "Engine 1 never
    # merges the two into a single fact."
    assert note.original_user_text not in evidence.structured_document.extracted_text


def test_a_document_engine_1_cannot_read_crosses_as_evidence_not_as_an_exception() -> None:
    """A CORRECTED EXPECTATION, AND THE PIN THAT ASKED FOR IT IS NOW RESOLVED.

    This test used to require `PipelineStageError` for zero bytes and was
    deliberately left pinning the behaviour as it stood, because the fix
    belonged in `engines/input_engine/pipeline.py`. That fix has landed.

    `APPLICATION_LAYER_CONTRACTS.md:30` — *"**Business** — unreadable, corrupt,
    zero-byte: an object is produced recording the failure. **Runtime** —
    engine crash: nothing produced, Application Layer restarts."* Zero bytes is
    the third word in that list.

    LAW 11 IS NOT WEAKENED BY THIS, WHICH IS THE POINT WORTH STATING. Nothing
    is swallowed: the failure is louder than before, because it now arrives as
    a durable, routable artifact naming the stage and the cause instead of a
    stack trace that only a log sees. What Law 11 forbids is silence, and an
    artifact carrying a named uncertainty marker is the opposite of silence.

    The transaction still stays in `Input` — unchanged, and for the reason the
    old docstring gave: `Failed` is for *"a runtime failure that exhausted
    retries"* (`:229`), the retry policy §8 requires does not exist, and a
    business outcome was never a candidate for `Failed` in the first place.
    """
    fixture = _Fixture()

    # CORRECTED EXPECTATION, not a weakened one (§J.4). This test used to assert
    # `pytest.raises(input_engine.PipelineStageError)` with the stage `cleaner`
    # and the transaction left in `Input`. It was PINNING A DEFECT: Engine 1
    # raised where its contract says emit, so an unreadable document — a
    # BUSINESS outcome — was indistinguishable from an engine crash, and the
    # Application Layer could not route the two differently.
    #
    # `APPLICATION_LAYER_CONTRACTS.md:30` — *"Business -- unreadable, corrupt,
    # zero-byte: an object is produced recording the failure. Runtime -- engine
    # crash: nothing produced."*  `COMMUNICATION_RULES_INPUT_ENGINE.md:159` —
    # failed extractions *"cross the boundary as low confidence and named
    # uncertainty, not as errors."*  The document wins over the code (§M), the
    # code was fixed, and the pin has to follow.
    #
    # The replacement is STRICTER: the old version proved only that something
    # was raised. This one proves an artifact exists, that it NAMES the failure,
    # that NOTHING was invented to fill the gap, and that the run routed onward
    # instead of stopping — four claims where there was one.
    with pytest.raises(ClarificationCycleExhaustedError) as raised:
        fixture.run(intake=an_intake(document=b""))

    evidence = raised.value.preserved.evidence
    report = evidence.confidence_report

    # 1. An artifact was produced, and it is empty rather than fabricated.
    assert evidence.structured_document.extracted_text == ""
    # 2. It names what failed, where, and why — not a generic marker.
    assert len(report.uncertainty_markers) == ONE_MARKER
    marker = report.uncertainty_markers[0]
    assert "could not be read" in marker.reason
    assert "cleaner" in marker.reason
    assert "no bytes were supplied" in marker.reason
    # 3. Nothing stands in for the value that was never read (Law 24).
    assert "none is invented" in marker.reason
    assert report.risky_fields == ()
    assert "No confidence score is repor" in report.reliability_information
    # 4. The failure CROSSED. It did not halt the pipeline, so a document nobody
    #    could read becomes a question rather than an outage — which is the whole
    #    point of the contract above.
    reached = {entry.to_state for entry in fixture.audit.history(fixture.transaction_id)}
    assert TransactionState.UNDERSTANDING in reached
    assert fixture.store.state_of(fixture.transaction_id) is TransactionState.ACCOUNTING

    # From the other resolution of this same pin, kept because each is a claim
    # mine did not make: no field was invented, no score was invented, and a
    # BUSINESS outcome never moves the transaction to `Failed` — that state is
    # for an exhausted retry policy (`APPLICATION_LAYER.md:229`) which does not
    # exist yet, so landing there would assert a runtime failure that never
    # happened.
    assert evidence.structured_document.detected_fields == ()
    assert report.confidence_scores == ()
    assert fixture.store.state_of(fixture.transaction_id) is not TransactionState.FAILED


# ── permission to execute, and the one status that has nowhere to wait ────
#
# `services/state.py` owns a refusal — `approved_with_warning_has_no_state()` —
# written for one call site in the Application Layer and, until now, called from
# NOWHERE in `src/`. Meanwhile `run` read `APPROVING_STATUSES`, which holds
# `Approved With Warning` as well as `Approved`, and advanced straight to
# `Execution`. The guard existed; the path went round it.
#
# The P3 validation stub returns `Rejected` for every input, on purpose, so no
# test could reach the branch through the real engine — which is exactly why it
# went unnoticed. Both tests below therefore replace Engine 5's verdict, and
# only Engine 5's: Engine 1 still reads a real document, the artifacts handed
# back are real, schema-validated `ValidationDecision`s built by the same model
# the engine uses, and `test_the_application_layer_routes_what_the_real_engine_
# read` still guards the input side. The trade-off is stated rather than hidden
# (§J.6): substituting the engine is the only way to exercise a status the
# current stub cannot emit, and the alternative is not testing it at all.
#
# The pair is the point. Refusing everything would pass the first test alone.


def a_complete_decision(transaction_id: TransactionId) -> AccountingDecision:
    """A decision the clarification loop lets through — balanced, and complete.

    The accounting stub always answers `INCOMPLETE_INFORMATION_REQUIRED`, so a
    run never leaves the Accounting stage. Debit equals credit exactly, because
    `decision.py` enforces the conservation law and a decision that failed it
    would never reach Validation for a different reason than the one under test.
    """
    return AccountingDecision(
        identity=IdentityEnvelope(
            artifact_id=ArtifactId(uuid.UUID(int=7_001)),
            version=1,
            parent_versions=(),
            transaction_id=transaction_id,
        ),
        decision_status=DecisionStatus.COMPLETE,
        accounting_treatment="Laptop purchased on credit; capitalised as a fixed asset.",
        ledger_classification="Fixed Assets, Computers. The vendor is a trade creditor.",
        debit_entries=(JournalLine(ledger="Computers", amount=Decimal("50000.00")),),
        credit_entries=(JournalLine(ledger="ABC Traders", amount=Decimal("50000.00")),),
        journal_structure="One purchase voucher carrying two lines.",
        tax_treatment="GST 18 percent, input credit eligible, intra-state supply.",
        accounting_assumptions=(),
        risk_indicators=(),
        decision_confidence=Decimal("0.8200"),
        supporting_reasoning="The invoice names a laptop and a vendor, and the amount agrees.",
        unresolved_doubts=(),
    )


def a_verdict(status: ValidationStatus, transaction_id: TransactionId) -> ValidationDecision:
    """A real Validation Decision carrying `status`, built by the real model.

    No issue lists: `validation.py` requires findings only of a NON-approving
    status, and both statuses under test approve. Nothing here is constructed
    around a validator.
    """
    return ValidationDecision(
        identity=IdentityEnvelope(
            artifact_id=ArtifactId(uuid.UUID(int=7_002)),
            version=1,
            parent_versions=(),
            transaction_id=transaction_id,
        ),
        related_decision_id=ArtifactId(uuid.UUID(int=7_001)),
        related_artifact_version=1,
        validation_status=status,
        validation_findings=(),
        validation_errors=(),
        validation_warnings=(),
        validation_risks=(),
        failed_validation_rules=(),
        supporting_evidence_references=("module:test_pipeline",),
        validation_confidence=Decimal("0.9000"),
        validation_reasoning="Supplied by this test; Engine 5 is a stub that cannot approve.",
        validation_timestamp=datetime(2026, 8, 6, 9, 0, tzinfo=UTC),
    )


def _reaching_validation_with(
    monkeypatch: pytest.MonkeyPatch, status: ValidationStatus, fixture: _Fixture
) -> None:
    """Point Engines 3 and 5 at real artifacts so the run reaches the verdict.

    Patched on the engine modules the Application Layer already imports, so the
    call site under test is untouched — `run` still resolves them exactly as it
    does in production.
    """
    monkeypatch.setattr(
        accounting_stub, "decide", lambda _story, _id: a_complete_decision(fixture.transaction_id)
    )
    monkeypatch.setattr(
        validation_stub,
        "validate",
        lambda _decision, /, **_kwargs: a_verdict(status, fixture.transaction_id),
    )


def test_an_approved_with_warning_verdict_is_refused_rather_than_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-8 and `ARCHITECTURE_AMENDMENTS.md:66-69` — the work waits for a human.

    `Approved With Warning` is in `APPROVING_STATUSES`, and that set's own
    comment says it goes forward *"after the Application Layer releases it"*.
    Nothing releases it and the locked state machine has nowhere for it to wait,
    so `run` used to advance it to `Execution` on the strength of the membership
    test alone — posting unattended work, which is the outcome
    `approved_with_warning_has_no_state()` was written to prevent and was never
    called to prevent.

    Asserted on the RESULT, not on "something raised" (§J.2): the transaction is
    left where it actually is, Engine 6 never ran, and every artifact already
    produced survives the refusal.
    """
    fixture = _Fixture()
    _reaching_validation_with(monkeypatch, ValidationStatus.APPROVED_WITH_WARNING, fixture)

    with pytest.raises(ApprovedWithWarningHasNoStateError) as raised:
        fixture.run(intake=an_intake(document=b""))

    # The refusal is `services/state.py`'s, verbatim — one author, not two.
    assert "WaitingForApproval is PROPOSED, not approved" in str(raised.value)

    preserved = raised.value.preserved
    assert preserved.execution is None, "Engine 6 ran on work that must wait for a human"
    assert preserved.validation is not None
    assert preserved.validation.validation_status is ValidationStatus.APPROVED_WITH_WARNING

    # Left in Validation, which is where it is. Never `Failed` — no runtime
    # failure occurred — and never `Execution`, which is the defect itself.
    assert fixture.store.state_of(fixture.transaction_id) is TransactionState.VALIDATION
    reached = {entry.to_state for entry in fixture.audit.history(fixture.transaction_id)}
    assert TransactionState.EXECUTION not in reached
    assert TransactionState.COMPLETED not in reached

    # Nothing already produced is discarded (`APPLICATION_LAYER.md:153`).
    assert preserved.evidence is not None
    assert preserved.understanding is not None
    assert preserved.decisions, "the Accounting Decision was thrown away with the refusal"


def test_a_plain_approved_verdict_still_reaches_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE NEGATIVE CONTROL. A guard that refused both approving statuses would
    pass the test above and would have broken the only route to `Execution` the
    locked state machine draws.

    `Approved` needs no release: `COMMUNICATION_RULES_VALIDATION_ENGINE.md:61`
    attaches that condition to `Approved With Warning` alone.
    """
    fixture = _Fixture()
    _reaching_validation_with(monkeypatch, ValidationStatus.APPROVED, fixture)

    produced = fixture.run(intake=an_intake(document=b""))

    assert produced.execution is not None
    assert produced.final_state is TransactionState.COMPLETED
    assert fixture.store.state_of(fixture.transaction_id) is TransactionState.COMPLETED


# ── the Transaction ID is intact ──────────────────────────────────────────


def test_every_artifact_carries_the_same_transaction_id(one_run: _CanonicalRun) -> None:
    """BLUEPRINT:136 — "Transaction ID intact". AL-INV-1 — created once, never
    changed, never reissued. A correction keeps the original.

    Checked on every artifact the run itself produced — the Document Evidence
    Object, the Business Understanding Object, and every Accounting Decision and
    Clarification Request — not on a set this file rebuilt.
    """
    produced = one_run.preserved
    expected = one_run.transaction_id

    assert produced.evidence.identity.transaction_id == expected
    assert produced.understanding.identity.transaction_id == expected
    assert produced.decisions, "the run recorded no Accounting Decision"
    for decision in produced.decisions:
        assert decision.identity.transaction_id == expected
    assert produced.clarifications, "the run recorded no Clarification Request"
    for request in produced.clarifications:
        assert request.identity.transaction_id == expected

    # Nothing produced is left out of the count above: the two singletons plus
    # both sequences are the whole of what a run to the bound can make.
    assert len(produced.artifacts) == SINGLETON_ARTIFACTS + len(produced.decisions) + len(
        produced.clarifications
    )


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


def test_every_state_change_is_recorded(one_run: _CanonicalRun) -> None:
    """BLUEPRINT:136 — "audit complete". The history's transitions must chain:
    each entry's `from` is the previous entry's `to`, with no gap."""
    assert one_run.history, "nothing was recorded"
    assert one_run.history[0].from_state is None, "the first entry is the creation"
    assert one_run.history[0].to_state is TransactionState.INPUT
    for earlier, later in itertools.pairwise(one_run.history):
        assert later.from_state is earlier.to_state, (
            f"gap in the audit: {earlier.to_state} then {later.from_state}"
        )


def test_the_recorded_history_ends_where_the_store_says_the_transaction_is(
    one_run: _CanonicalRun,
) -> None:
    """A history that disagrees with the store is worse than none — it looks
    like traceability and points somewhere else."""
    assert one_run.history[-1].to_state is one_run.final_state


def test_every_transition_names_a_trigger(one_run: _CanonicalRun) -> None:
    """APPLICATION_LAYER_API.md:126 — history answers "why is this transaction
    here" WITHOUT inference. A blank trigger forces inference."""
    for entry in one_run.history:
        assert entry.trigger.strip()


# ── no accuracy claim is possible at this phase ───────────────────────────


def test_the_skeleton_never_reaches_completed() -> None:
    """The pass condition, stated as one. BLUEPRINT:136 — "no accuracy claim
    permitted at this phase". Reaching Completed would mean a stub decided
    something, and a decided entry at P3 is a fabricated one.

    Unchanged by the Engine 1 migration, and deliberately so: real EVIDENCE
    does not license a real DECISION. Engines 2-6 are still frozen stubs, so
    the run must still stop short. Its own run, with a far larger bound than
    the shared one, because the claim is that no number of rounds gets there.
    """
    run = _Fixture(rounds=20).to_the_bound()
    reached = {entry.to_state for entry in run.history}
    assert TransactionState.COMPLETED not in reached
    assert TransactionState.EXECUTION not in reached
    assert run.preserved.validation is None
    assert run.preserved.execution is None


def test_the_accounting_stub_never_claims_a_complete_decision(one_run: _CanonicalRun) -> None:
    """If this ever passes with COMPLETE, the skeleton above would post.

    Read off the decision the RUN produced from the REAL evidence, so "the stub
    decided nothing" is now a statement about a decision taken on a real
    reading rather than on an empty artifact.
    """
    decision = one_run.preserved.decisions[-1]
    assert decision.decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED
    assert decision.debit_entries == ()
    assert decision.credit_entries == ()


# ── the run is reproducible ───────────────────────────────────────────────


def test_two_identical_runs_produce_identical_histories(
    one_run: _CanonicalRun, second_run: _CanonicalRun
) -> None:
    """AL-INV-12 rests on identical input producing an identical conclusion. A
    module reaching for uuid4() or datetime.now() cannot offer that.

    The audit trail holds no artifact id, so Engine 1 minting a fresh Document
    ID per run (`ENGINE_1:253`) does not weaken this — the workflow the
    Application Layer owns is still bit-for-bit reproducible. That is exactly
    the pair of facts `test_engine_1_mints_the_document_id...` and this test
    assert about the same two runs: the ids differ, the histories do not.
    """
    assert second_run.history == one_run.history
