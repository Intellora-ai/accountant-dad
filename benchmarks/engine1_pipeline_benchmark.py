"""How long Engine 1 takes, per stage, on real documents — measured, never
judged.

`ROADMAP.md` Phase E1 lists *"a measured performance number exists"* among the
completion criteria and records that **there is none today, so no performance
claim is provable** (`CLAUDE.md` Law 52). This module is the instrument that
produces that number. It is not a gate, and it must never become one.

WHAT THESE NUMBERS ARE NOT ABOUT. READ THIS BEFORE QUOTING ONE.

    This repository contains **no accounting document**: not one invoice,
    receipt, bill, voucher or challan, and **no image file of any format**. Its
    40 PDFs are statutes, rules, notifications, circulars and ICAI standards,
    every one of them carrying a real text layer.

    So every number this module produces describes **text-layer PDF extraction
    on legal documents** and nothing else. A latency measured on an 880-page
    Income-tax Act is not a claim about invoice processing, which is what
    Engine 1 exists to do (`CLAUDE.md` §B.1). Two of the paths that would
    dominate a photographed receipt never execute on this corpus at all:
    `cleaner`'s deskew, denoise and contrast work — it corrects rendered pixels,
    and a clean text-layer PDF gives it nothing to correct — and `reader`'s OCR
    fallback, which the text layer means never fires.

    Every report says so in its own output, and
    `test_the_repository_declares_no_invoice_receipt_bill_or_scan` reads the
    real manifest and goes red the day it stops being true. It is a checked
    fact, not a disclaimer somebody remembered to write.

WHAT IT MEASURES, AND WHY IT MEASURES IT THAT WAY.

    A single end-to-end duration answers "is it slow?" and nothing else. It
    cannot say WHICH of Engine 1's five stages the time went to, so it cannot
    point at the constraint (`CLAUDE.md` §D.6 — optimising a non-bottleneck
    returns exactly zero). So this harness times each stage separately.

    It does NOT re-implement `pipeline.run`'s sequence in order to time the
    steps. A copy of the production sequence would drift from it, and a
    benchmark of a copy measures the copy (§J.6 — a mock proves the mock).
    Instead the harness **wraps each sub-engine entry point in a timer that
    delegates to the real function**, then calls the real
    `pipeline.run(...)`. Everything that runs is production code; the only
    addition is a `time.perf_counter()` on either side of five calls. The
    wrapper returns exactly what the real function returned, and is removed
    again whether the run succeeds or raises.

    Five stages are timed, and they are not this file's opinion of what the
    stages are: `pipeline.run` names each of its own stages in the
    `PipelineStageError` it raises for that stage, and
    `tests/unit/test_engine1_pipeline_benchmark.py` re-derives that list from
    `pipeline.run`'s source with `ast` and demands it equal `STAGE_NAMES`.
    Rename a stage in the pipeline and the benchmark goes red rather than
    quietly reporting a table about the wrong thing.

WHAT IT REFUSES TO DO.

    **It asserts no threshold.** There is no approved performance floor for
    Engine 1. `MEASUREMENT_FRAMEWORK.md` §12 fixes a whole-system bound of
    ≤ 60 seconds per document, changeable only by amendment — that is a bound
    on the six-engine pipeline, not on Engine 1 alone, and no one has divided
    it between engines. Inventing Engine 1's share here would be this file
    answering a question that belongs to the owner (Law 52, and
    `.github/workflows/performance.yml`'s own words: *"a gate missing its
    number must never be given one"*). So `main` exits zero on every value it
    measures, and `BenchmarkReport` carries no pass, fail, budget or verdict —
    a fact pinned by `test_the_report_carries_no_verdict_field`.

    **It never reports a zero for a stage that did not run.** A stage that was
    declared and never called has no duration; printing `0.000 s` for it would
    be a fabricated measurement (Law 24) and — worse — an invisible one, since
    a fast stage and an absent stage look identical in a table. `StageRecorder`
    raises `StageDidNotRunError` naming the stage and the function nobody
    called.

    **It never lets the parts disagree with the whole.** `RunTiming` refuses
    construction when its stages sum to more than the total it belongs to.
    That is a conservation check, and it is the cheapest way to catch an
    instrument that has started double-counting.

    **It never measures bytes it has not identified.** The document is
    resolved through the repository's own manifest
    (`Accounting_Brain/Evidence_Library/manifest.jsonl`), and its sha256 is
    verified against the manifest's declaration before a single timer starts.
    A duration attributed to unknown bytes is not a result.

WHAT THE COLD RUN IS, AND WHY IT IS REPORTED SEPARATELY.

    Measured on this machine: the first `pipeline.run` in a process costs
    roughly seven times a later one, and the gap is almost entirely Docling's
    model loading, which happens once per process rather than once per
    document. Folding that into a percentile would make the reported latency a
    property of how many documents you happened to run, not of the pipeline.
    Dropping it silently would hide the real cost of the first document a
    process ever sees.

    So run 1 is reported, by name, as the cold run; runs 2..N form the warm
    sample that p50 and p95 are computed over; and **every run is kept**
    (`MEASUREMENT_FRAMEWORK.md` §8 — you may not run five times and report the
    best). Nothing is discarded, so nothing needs to be trusted.

WHY p95 IS NEAREST-RANK, AND WHEN IT MEANS NOTHING.

    `nearest_rank` picks a real observed sample — index `ceil(p/100 · n) - 1`
    of the sorted values — and never interpolates between two runs. An
    interpolated p95 is a number no run produced, and `MEASUREMENT_FRAMEWORK.md`
    §2 is explicit that the user gets one run and not the mean of several.

    That same arithmetic means nearest-rank p95 IS the maximum for any warm
    sample below 20 — `ceil(0.95n) == n` holds up to n=19 and fails first at
    n=20. Below that the p95 column carries nothing the max column does not, so
    the report says so under the table rather than letting the column imply a
    tail measurement. `DEFAULT_RUNS` is 22, which clears the boundary; a
    document too expensive to run 22 times still gets measured, and gets told
    on. See `p95_is_necessarily_the_maximum`.

WHY SEVERAL DOCUMENTS, AND WHY EACH KEEPS ITS OWN NUMBERS.

    "Engine 1's latency" is not one number. This corpus runs from a one-page
    notification to an 880-page statute, and the pipeline's cost is dominated
    by a stage that scales with pages, so a single figure covering both is a
    number no document produced. `BenchmarkSuite` measures several documents
    under one machine and one configuration — and refuses to be built from two
    of either — while keeping every timing attributed to the document that
    produced it, at that document's own run count.

HOW TO RUN IT.

    PYTHONPATH=src python3 -m benchmarks.engine1_pipeline_benchmark

    from the repository root. `--document` and `--runs` are both repeatable.
    `benchmarks/README.md` states the invocations, what each column means and
    what the numbers may and may not be used for.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import math
import os
import pathlib
import platform
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import ModuleType
from typing import Protocol, cast

import pymupdf

from accountant_dad.artifacts.evidence import DocumentEvidenceObject
from accountant_dad.engines.input_engine import (
    assembly,
    cleaner,
    confidence_report,
    parser,
    pipeline,
    reader,
)
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    TransactionId,
)
from tools.evidence.registry import BOOTSTRAP_COMMAND, MANIFEST, read_manifest

# ── typed facades over untyped dependencies ──────────────────────────────
#
# PyMuPDF ships `py.typed` and leaves its functions unannotated, so
# `mypy --strict` refuses a bare call and this repository's suppression budget
# rules out silencing it per line. `pipeline.py` and `reader.py` each declare
# the same shape for the same reason; theirs are module-private.


class _PdfDocument(Protocol):
    page_count: int

    def close(self) -> None: ...


class _OpenPdf(Protocol):
    def __call__(self, *, stream: bytes, filetype: str) -> _PdfDocument: ...


_open_pdf = cast(_OpenPdf, pymupdf.open)


class _AnyCallable(Protocol):
    """Whatever a sub-engine entry point happens to be.

    The harness never inspects the signature it wraps — it starts a clock,
    forwards everything untouched, stops the clock, and returns the result
    unchanged. A structural type is therefore honest here in a way that a
    guessed concrete signature would not be: five different functions with five
    different signatures pass through this one wrapper.
    """

    def __call__(self, *args: object, **kwargs: object) -> object: ...


# ── errors ───────────────────────────────────────────────────────────────


class BenchmarkError(RuntimeError):
    """The base of every error this harness raises."""


class StageDidNotRunError(BenchmarkError):
    """A declared stage was never called, so it has no duration to report."""


class ImpossibleTimingError(BenchmarkError):
    """A run's stages account for more time than the run itself took."""


class BenchmarkDocumentError(BenchmarkError):
    """The document to measure is missing, undeclared, or not the declared bytes."""


# ── what gets measured ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StageProbe:
    """One stage of `pipeline.run`, and the exact function that IS that stage.

    `module` is the module object itself, not its name, because `pipeline.run`
    resolves `cleaner.clean_artifact` and friends as attributes of the module
    objects it imported. Instrumenting any other object of the same name would
    time a function nobody calls.
    """

    name: str
    module: ModuleType
    attribute: str

    @property
    def target(self) -> str:
        return f"{self.module.__name__}.{self.attribute}"


#: The five stages, in the order `pipeline.run` runs them. Not a free choice:
#: `pipeline.run` names each of these in its own `PipelineStageError`, and the
#: test file re-derives the list from that source and demands equality.
STAGES: tuple[StageProbe, ...] = (
    StageProbe(name="cleaner", module=cleaner, attribute="clean_artifact"),
    StageProbe(name="reader", module=reader, attribute="read"),
    StageProbe(name="parser", module=parser, attribute="parse"),
    StageProbe(name="confidence", module=confidence_report, attribute="record_confidence"),
    StageProbe(name="assembly", module=assembly, attribute="assemble"),
)

STAGE_NAMES: tuple[str, ...] = tuple(probe.name for probe in STAGES)

#: The label the whole-run duration is reported under.
TOTAL_LABEL = "total"
#: The label for whatever `pipeline.run` spent OUTSIDE the five timed calls —
#: the temporary file `_parse_document` writes, the four small `*_output`
#: repackagings, and the wrappers' own overhead. Reported rather than
#: swallowed: a remainder that grows is a stage nobody is timing.
UNATTRIBUTED_LABEL = "unattributed"


# ── the settings these numbers belong to ─────────────────────────────────
#
# Every number below is a BENCHMARK parameter, not a product default, and it is
# printed with the results because a latency without the settings that produced
# it is not reproducible. The eight cleaner values and the render DPI are the
# ones `tests/unit/test_input_engine_pipeline.py` already uses to exercise the
# same pipeline, reused verbatim so the benchmark and the tests are measuring
# the same configuration rather than two of them. `CleanerSettings` calls all
# eight "the caller's"; this harness is a caller.
#
# `vision_fallback_threshold` is zero, which is the value that never triggers
# the fallback — the fallback is a stub with no API key, and a benchmark that
# tripped it would be timing an exception rather than a pipeline.
# `table_structure` is `None` because `parser.parse`'s own default is `None`,
# tested there as "do not run the detector". Mirroring an existing default is
# not choosing a number.

BENCHMARK_RENDER_DPI = 150

SETTINGS = pipeline.PipelineSettings(
    cleaner_settings=cleaner.CleanerSettings(
        max_deskew_degrees=15.0,
        denoise_strength=3.0,
        denoise_template_window=7,
        denoise_search_window=21,
        contrast_clip_limit=2.0,
        contrast_tile_grid=8,
        crop_margin_pixels=10,
        max_ink_loss_fraction=1.0,
    ),
    render_dpi=BENCHMARK_RENDER_DPI,
    vision_fallback_threshold=Decimal("0.0"),
    table_structure=None,
)

#: A real, hash-pinned government PDF the manifest already declares: eight
#: pages of CBIC guidance on the GST composition levy. Chosen because Indian
#: GST documents are the MVP's actual input (`CLAUDE.md` §B.7), because the
#: manifest pins its sha256 so a timing can be attributed to known bytes, and
#: because eight pages is large enough for per-page cost to show against the
#: fixed per-run cost. Any other manifest entry can be named with --document.
DEFAULT_DOCUMENT = "CBIC-FAQ-Composition-Levy.pdf"

#: 21 warm runs, which is one more than the minimum that makes the p95 column
#: mean anything. See `SMALLEST_WARM_SAMPLE_WITH_A_REAL_P95` — the boundary is
#: 20, and this default clears it. Left at 22 rather than trimmed to 21:
#: a larger sample is strictly more evidence, and reducing it would be
#: subtracting rigour to save nothing (`CLAUDE.md` §E.8).
DEFAULT_RUNS = 22

#: The smallest warm sample at which nearest-rank p95 is not simply the
#: maximum. Twenty, MEASURED against `nearest_rank` itself rather than reasoned
#: about — `ceil(0.95n) == n` holds for every n up to 19 and fails first at
#: n=20, where `ceil(19.0) == 19` picks the 19th of 20.
#:
#: This constant read 21 until 2026-08-06, on the stated ground that "p95
#: equals the maximum for every sample of 20 or fewer". That sentence is false
#: at exactly one value, n=20, and `test_p95_is_necessarily_the_maximum_...`
#: now checks every value against the real percentile function instead of
#: restating the claim, so an arithmetic argument can no longer disagree with
#: the arithmetic.
SMALLEST_WARM_SAMPLE_WITH_A_REAL_P95 = 20

#: One cold run and one warm run is the arithmetic minimum: below it the cold
#: cost cannot be told from the warm one, and a p50 over an empty sample does
#: not exist.
MINIMUM_RUNS = 2

#: A percentile is a share of a sample, so the whole sample is 100 of them.
#: Arithmetic, not a setting.
MAX_PERCENTILE = 100


# ── recording ────────────────────────────────────────────────────────────


class StageRecorder:
    """Where the wrappers put what they measured.

    Deliberately dumb: it adds up seconds and counts calls. It has exactly one
    opinion, in `timings` — a stage nobody called has no duration, and it says
    so instead of returning zero.
    """

    def __init__(self) -> None:
        self._seconds: dict[str, float] = {}
        self._calls: dict[str, int] = {}

    def record(self, stage: str, seconds: float) -> None:
        self._seconds[stage] = self._seconds.get(stage, 0.0) + seconds
        self._calls[stage] = self._calls.get(stage, 0) + 1

    def seconds(self, stage: str) -> float:
        return self._seconds[stage]

    def calls(self, stage: str) -> int:
        return self._calls.get(stage, 0)

    def timings(self, probes: Sequence[StageProbe]) -> tuple[StageTiming, ...]:
        """One `StageTiming` per probe, in probe order — or a loud failure.

        Refusing here rather than defaulting to zero is the whole point of the
        class. A stage that did not run and a stage that ran in no time are
        indistinguishable once both are printed as `0.000`, and the first of
        those two is a broken instrument while the second is a result.
        """
        collected: list[StageTiming] = []
        for probe in probes:
            if probe.name not in self._seconds:
                raise StageDidNotRunError(
                    f"benchmark stage {probe.name!r} was declared but never ran: "
                    f"nothing called {probe.target} during this run. No duration "
                    f"is reported for it, because it has none — printing a zero "
                    f"would be a measurement of something that did not happen "
                    f"(CLAUDE.md Law 24). Either the pipeline no longer calls "
                    f"{probe.target}, or this stage was declared in error."
                )
            collected.append(
                StageTiming(
                    stage=probe.name,
                    seconds=self._seconds[probe.name],
                    calls=self._calls[probe.name],
                )
            )
        return tuple(collected)


def _timed(name: str, original: _AnyCallable, recorder: StageRecorder) -> _AnyCallable:
    """`original`, wrapped in a clock. Same arguments in, same result out.

    The `finally` matters: a sub-engine that raises still consumed real time,
    and a stage that failed is exactly the stage a reader of the report needs
    the duration of.
    """

    def wrapper(*args: object, **kwargs: object) -> object:
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            recorder.record(name, time.perf_counter() - started)

    return wrapper


@contextlib.contextmanager
def instrumented(probes: Sequence[StageProbe], recorder: StageRecorder) -> Iterator[None]:
    """Install the clocks, run the caller's block, take the clocks off again.

    The `finally` is not tidiness. A run that raised while still patched would
    leave the real modules wrapped, and every later measurement in the process
    would be timing a wrapper of a wrapper — an error that grows quietly and
    makes every number after it wrong.
    """
    installed: list[tuple[StageProbe, _AnyCallable]] = [
        (probe, cast(_AnyCallable, getattr(probe.module, probe.attribute))) for probe in probes
    ]
    try:
        for probe, original in installed:
            setattr(probe.module, probe.attribute, _timed(probe.name, original, recorder))
        yield
    finally:
        for probe, original in installed:
            setattr(probe.module, probe.attribute, original)


# ── the shapes a measurement takes ───────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StageTiming:
    """What one stage cost in one run, and how many calls that covers."""

    stage: str
    seconds: float
    calls: int


@dataclass(frozen=True, slots=True)
class RunTiming:
    """One complete `pipeline.run`, timed as a whole and stage by stage."""

    index: int
    total_seconds: float
    stages: tuple[StageTiming, ...]

    def __post_init__(self) -> None:
        accounted = sum(timing.seconds for timing in self.stages)
        if accounted > self.total_seconds:
            raise ImpossibleTimingError(
                f"run {self.index}'s stages account for {accounted} seconds out "
                f"of a total of {self.total_seconds}. The stages run INSIDE the "
                "total, so this cannot happen unless the instrument is "
                "double-counting or timing something outside the run. Refused "
                "rather than published."
            )

    @property
    def unattributed_seconds(self) -> float:
        return self.total_seconds - sum(timing.seconds for timing in self.stages)

    def seconds_for(self, label: str) -> float:
        if label == TOTAL_LABEL:
            return self.total_seconds
        if label == UNATTRIBUTED_LABEL:
            return self.unattributed_seconds
        for timing in self.stages:
            if timing.stage == label:
                return timing.seconds
        raise StageDidNotRunError(
            f"run {self.index} carries no timing labelled {label!r}; it timed "
            f"{[timing.stage for timing in self.stages]}."
        )

    def calls_for(self, label: str) -> int:
        for timing in self.stages:
            if timing.stage == label:
                return timing.calls
        return 1


@dataclass(frozen=True, slots=True)
class Summary:
    """A sample of durations, reduced to observed values only."""

    label: str
    samples: int
    p50_seconds: float
    p95_seconds: float
    min_seconds: float
    max_seconds: float


@dataclass(frozen=True, slots=True)
class Machine:
    """Where the numbers came from. A latency without its hardware is not
    reproducible, and comparing two of them across machines is not a
    comparison."""

    platform: str
    processor: str
    python_version: str
    cpu_count: int | None

    @classmethod
    def here(cls) -> Machine:
        return cls(
            platform=platform.platform(),
            processor=platform.processor() or platform.machine(),
            python_version=platform.python_version(),
            cpu_count=os.cpu_count(),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkDocument:
    """The bytes being measured, and everything needed to say which bytes.

    `kind` is the manifest's OWN word for what this document is — `act`,
    `rules`, `notification`, `circular`, `guidance`, `icai_standard`. It is
    carried through rather than described here so the report can state what it
    measured without anybody typing a claim about it. It has no default: a
    document whose kind nobody declared is a document the report cannot
    characterise, and characterising it anyway is how "8 pages of CBIC
    guidance" quietly becomes "a document".
    """

    name: str
    payload: bytes
    sha256: str
    page_count: int
    kind: str
    source_reference: str
    media_type: reader.MediaType = reader.MediaType.PDF

    @property
    def byte_count(self) -> int:
        return len(self.payload)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Every run, kept. No verdict, by design.

    `runs` holds all of them including the cold one and including any that were
    slower than the rest — `MEASUREMENT_FRAMEWORK.md` §8, you may not run five
    times and report the best. `artifacts` holds what each run actually
    produced, so a report cannot describe a fast pipeline that produced
    nothing.
    """

    document: BenchmarkDocument
    machine: Machine
    settings: pipeline.PipelineSettings
    runs: tuple[RunTiming, ...]
    artifacts: tuple[DocumentEvidenceObject, ...] = field(default=())

    @property
    def cold_run(self) -> RunTiming:
        return self.runs[0]

    @property
    def warm_runs(self) -> tuple[RunTiming, ...]:
        return self.runs[1:]

    def summary_for(self, label: str) -> Summary:
        return summarise(label, tuple(run.seconds_for(label) for run in self.warm_runs))

    def stage_summaries(self) -> tuple[Summary, ...]:
        return tuple(self.summary_for(name) for name in STAGE_NAMES)

    def total_summary(self) -> Summary:
        return self.summary_for(TOTAL_LABEL)

    def unattributed_summary(self) -> Summary:
        return self.summary_for(UNATTRIBUTED_LABEL)


# ── statistics, such as they are ─────────────────────────────────────────


def nearest_rank(values: Sequence[float], percentile: int) -> float:
    """The nearest-rank percentile: a value some run actually produced.

    No interpolation, ever. An interpolated p95 is a duration no run took, and
    a report of durations nobody observed is not a report of what happened.
    """
    if not values:
        raise ValueError(
            f"cannot take the {percentile}th percentile of no samples. An empty "
            "sample has no percentile, and returning zero for one would be a "
            "fabricated measurement."
        )
    if not 0 < percentile <= MAX_PERCENTILE:
        raise ValueError(f"percentile must lie in (0, {MAX_PERCENTILE}]; got {percentile}.")
    ordered = sorted(values)
    rank = math.ceil(percentile / MAX_PERCENTILE * len(ordered))
    return ordered[rank - 1]


def summarise(label: str, values: Sequence[float]) -> Summary:
    return Summary(
        label=label,
        samples=len(values),
        p50_seconds=nearest_rank(values, 50),
        p95_seconds=nearest_rank(values, 95),
        min_seconds=min(values),
        max_seconds=max(values),
    )


def p95_is_necessarily_the_maximum(samples: int) -> bool:
    """True when a p95 column over `samples` values can only ever be the max.

    Nearest-rank p95 is element `ceil(0.95n) - 1` of the sorted sample, so it
    is the maximum exactly when `ceil(0.95n) == n` — true for every n up to 19,
    first false at n=20. Below that the p95 column carries nothing the max
    column does not already carry, and a table that prints it without saying so
    is read as a tail measurement.

    Computed from `nearest_rank`'s own rank formula rather than compared
    against a stored number, so the two cannot drift apart. The stored number
    did drift, once: it said 21.

    Stated as a function rather than as a constant so the report derives the
    warning from the sample it actually has. `DEFAULT_RUNS` exists precisely so
    the default run never trips this; a document too expensive to run 22 times
    still gets measured, and gets told on.
    """
    return math.ceil(95 / MAX_PERCENTILE * samples) >= samples


# ── running it ───────────────────────────────────────────────────────────


def _an_identity() -> IdentityEnvelope:
    """A fresh envelope per run. `CLAUDE.md` §O — IDENTITY ≠ INTELLIGENCE: an
    ID identifies an artifact and never influences anything, so reusing one
    across runs would save nothing and imply otherwise."""
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=FIRST_VERSION,
        parent_versions=(),
        transaction_id=TransactionId.new(),
    )


def time_one_run(
    document: BenchmarkDocument,
    *,
    settings: pipeline.PipelineSettings,
    stages: Sequence[StageProbe],
    index: int,
) -> tuple[RunTiming, DocumentEvidenceObject]:
    """One real `pipeline.run`, timed as a whole and stage by stage.

    The artifact comes back with the timing so the caller can check that the
    run produced something. A benchmark that cannot tell a fast pipeline from
    a broken one is not measuring the pipeline.
    """
    recorder = StageRecorder()
    intake = pipeline.DocumentIntake(
        document=document.payload,
        media_type=document.media_type,
        source_references=(document.source_reference,),
    )
    with instrumented(stages, recorder):
        started = time.perf_counter()
        artifact = pipeline.run(intake, identity=_an_identity(), settings=settings)
        total = time.perf_counter() - started
    return RunTiming(index=index, total_seconds=total, stages=recorder.timings(stages)), artifact


def measure(
    document: BenchmarkDocument,
    *,
    settings: pipeline.PipelineSettings = SETTINGS,
    runs: int = DEFAULT_RUNS,
    stages: Sequence[StageProbe] = STAGES,
) -> BenchmarkReport:
    """Run the real pipeline `runs` times on `document` and keep every run."""
    if runs < MINIMUM_RUNS:
        raise ValueError(
            f"runs must be at least {MINIMUM_RUNS}; got {runs}. The first run in "
            "a process pays for model loading that later runs do not, so a "
            "single run cannot be told apart from a warm one, and a warm "
            "percentile over an empty sample does not exist."
        )
    timings: list[RunTiming] = []
    artifacts: list[DocumentEvidenceObject] = []
    for index in range(runs):
        timing, artifact = time_one_run(document, settings=settings, stages=stages, index=index)
        timings.append(timing)
        artifacts.append(artifact)
    return BenchmarkReport(
        document=document,
        machine=Machine.here(),
        settings=settings,
        runs=tuple(timings),
        artifacts=tuple(artifacts),
    )


# ── finding the document ─────────────────────────────────────────────────


def _page_count(payload: bytes) -> int:
    document = _open_pdf(stream=payload, filetype="pdf")
    try:
        return document.page_count
    finally:
        document.close()


def load_manifest_document(name: str, *, manifest: pathlib.Path | None = None) -> BenchmarkDocument:
    """The document the manifest declares under `name`, or a loud refusal.

    The sha256 is checked against the manifest's declaration BEFORE anything is
    timed. `MEASUREMENT_FRAMEWORK.md` §0a requires that a result be
    regenerable; a duration attributed to bytes nobody identified cannot be
    regenerated by anyone, including whoever produced it.
    """
    path = MANIFEST if manifest is None else manifest
    declared = read_manifest(path, path.parent / "sources")
    document = declared.get(name)
    if document is None:
        raise BenchmarkDocumentError(
            f"{name} is not declared in {path}. The benchmark only measures "
            f"documents the repository declares, so that a timing can be "
            f"attributed to known bytes. Declared: {', '.join(sorted(declared))}."
        )
    if not document.present():
        raise BenchmarkDocumentError(
            f"{name} is declared but not on disk, so there is nothing to "
            f"measure. It is gitignored and re-fetchable:\n"
            f"      {document.missing_report()}\n"
            f"      run {BOOTSTRAP_COMMAND} from the repository root."
        )
    actual = document.actual_sha256()
    if actual != document.sha256:
        raise BenchmarkDocumentError(
            f"{name} on disk hashes to {actual}, but the manifest declares "
            f"{document.sha256}. These are not the declared bytes, so any "
            f"duration measured from them would describe an unknown document. "
            f"Re-fetch with {BOOTSTRAP_COMMAND}."
        )
    payload = document.path.read_bytes()
    return BenchmarkDocument(
        name=name,
        payload=payload,
        sha256=actual,
        page_count=_page_count(payload),
        kind=document.kind,
        source_reference=f"evidence:{name}",
    )


# ── reporting ────────────────────────────────────────────────────────────

#: Width of the leftmost column in the three per-stage tables. Fixed, unlike
#: `field_lines`' derived width, because a TABLE's rows must align with each
#: other and with a heading — a per-row width would be no table at all. It is
#: an assumption, so it is checked: `test_every_table_label_fits_its_column`
#: asserts every label that lands here, including the stage names `pipeline.run`
#: itself declares, still leaves a gap before the next column.
_LABEL_WIDTH = 20
_NUMBER_WIDTH = 12
_SECONDS = 4
#: The smallest gap that still separates a label from its value. Two, not one,
#: so a value beginning with a space-like character is still visibly a value.
_GAP = 2
#: The horizontal rule between two documents' sections in a suite.
_RULE_WIDTH = 78


def field_lines(pairs: Sequence[tuple[str, object]]) -> list[str]:
    """`label   value`, one line per pair, in a column WIDE ENOUGH FOR THESE
    LABELS.

    The width is derived from the longest label in `pairs`, never assumed.
    A fixed 20 characters was assumed here until 2026-08-06 and six of the
    eleven settings lines printed as `vision_fallback_threshold0.0` and
    `denoise_template_window7` — label and value with nothing between them,
    which is not a reported value at all, since `...window7` reads equally as a
    window of 7 and as a label ending in 7. Those settings are exactly what
    makes a latency reproducible, so six of them were silently unreadable.

    Deriving the width fixes the class rather than the instance (§J.9): no
    label can be long enough to collide, including ones nobody has written yet.
    """
    if not pairs:
        return []
    width = max(len(label) for label, _ in pairs) + _GAP
    return [f"{label:<{width}}{value}" for label, value in pairs]


def _calls_text(report: BenchmarkReport, label: str) -> str:
    counts = sorted({run.calls_for(label) for run in report.warm_runs})
    if len(counts) == 1:
        return str(counts[0])
    return f"{counts[0]}-{counts[-1]}"


def _summary_line(report: BenchmarkReport, summary: Summary) -> str:
    return f"{summary.label:<{_LABEL_WIDTH}}{_calls_text(report, summary.label):>6}" + "".join(
        f"{value:>{_NUMBER_WIDTH}.{_SECONDS}f}"
        for value in (
            summary.p50_seconds,
            summary.p95_seconds,
            summary.min_seconds,
            summary.max_seconds,
        )
    )


def _machine_lines(machine: Machine) -> list[str]:
    """Where the numbers came from. Printed ONCE per report or suite: repeating
    it per document would invite a reader to think two rows came from two
    machines, and a latency compared across machines is not a comparison."""
    return field_lines(
        (
            ("platform", machine.platform),
            ("processor", machine.processor),
            ("python", machine.python_version),
            ("cpu count", "unknown" if machine.cpu_count is None else machine.cpu_count),
        )
    )


def _document_lines(report: BenchmarkReport) -> list[str]:
    """Which bytes these numbers describe, and how many runs they cover.

    `kind` is the manifest's own word for the document, carried here unedited.
    It is on this block rather than in a footnote because it is the one field
    that says what was measured: `guidance`, `act`, `circular` — a statute, not
    an invoice.
    """
    document = report.document
    return field_lines(
        (
            ("document", document.name),
            ("kind", document.kind),
            ("sha256", document.sha256),
            ("bytes", document.byte_count),
            ("pages", document.page_count),
            ("media type", document.media_type.value),
            ("runs", len(report.runs)),
            ("cold runs", 1),
            ("warm runs", len(report.warm_runs)),
            ("percentile rule", "nearest-rank, no interpolation"),
        )
    )


def _settings_lines(settings: pipeline.PipelineSettings) -> list[str]:
    pairs: list[tuple[str, object]] = [
        ("render_dpi", settings.render_dpi),
        ("vision_fallback_threshold", settings.vision_fallback_threshold),
        ("table_structure", settings.table_structure),
    ]
    pairs.extend(
        (entry.name, getattr(settings.cleaner_settings, entry.name))
        for entry in dataclasses.fields(cleaner.CleanerSettings)
    )
    return ["", "settings that produced these numbers", *field_lines(pairs)]


#: What run 1 of the FIRST document in a process is. It carries Docling's model
#: loading, which happens once per process.
COLD_FIRST_IN_PROCESS = "cold run - the first pipeline.run in this process, reported alone"
#: What run 1 of every LATER document is. Not the same thing, and saying it was
#: would be a false claim about where the time went: by the second document the
#: models are already loaded, so whatever run 1 still costs extra is NOT model
#: loading and a reader chasing it would be chasing the wrong cause. Measured
#: 2026-08-06: document 2's run 1 cost 24.04 s against a 7.10 s warm p50, with
#: every model already in memory.
COLD_LATER_DOCUMENT = "run 1 - first run on THIS document; models already loaded, reported alone"


def _cold_lines(report: BenchmarkReport, *, first_in_process: bool) -> list[str]:
    cold = report.cold_run
    lines = [
        "",
        COLD_FIRST_IN_PROCESS if first_in_process else COLD_LATER_DOCUMENT,
        f"{'stage':<{_LABEL_WIDTH}}{'calls':>6}{'seconds':>{_NUMBER_WIDTH}}",
    ]
    for timing in cold.stages:
        lines.append(
            f"{timing.stage:<{_LABEL_WIDTH}}{timing.calls:>6}"
            f"{timing.seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
        )
    lines.append(
        f"{UNATTRIBUTED_LABEL:<{_LABEL_WIDTH}}{'':>6}"
        f"{cold.unattributed_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
    )
    lines.append(
        f"{TOTAL_LABEL:<{_LABEL_WIDTH}}{'':>6}{cold.total_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
    )
    return lines


def _warm_lines(report: BenchmarkReport) -> list[str]:
    heading = (
        f"{'stage':<{_LABEL_WIDTH}}{'calls':>6}"
        f"{'p50 s':>{_NUMBER_WIDTH}}{'p95 s':>{_NUMBER_WIDTH}}"
        f"{'min s':>{_NUMBER_WIDTH}}{'max s':>{_NUMBER_WIDTH}}"
    )
    lines = ["", f"warm runs - {len(report.warm_runs)} samples, run 1 excluded", heading]
    lines.extend(_summary_line(report, summary) for summary in report.stage_summaries())
    lines.append(_summary_line(report, report.unattributed_summary()))
    lines.append(_summary_line(report, report.total_summary()))
    if p95_is_necessarily_the_maximum(len(report.warm_runs)):
        lines.append(
            f"NOTE: p95 here is the maximum. Nearest-rank p95 of "
            f"{len(report.warm_runs)} samples IS the largest of them; the "
            f"column carries no information the max column does not. "
            f"{SMALLEST_WARM_SAMPLE_WITH_A_REAL_P95} warm runs is the smallest "
            f"sample at which it does."
        )
    return lines


def _every_run_lines(report: BenchmarkReport) -> list[str]:
    lines = [
        "",
        "every run, kept - MEASUREMENT_FRAMEWORK.md section 8",
        f"{'run':<{_LABEL_WIDTH}}{'':>6}{'seconds':>{_NUMBER_WIDTH}}",
    ]
    for run in report.runs:
        label = f"{run.index + 1}{' (cold)' if run.index == 0 else ''}"
        lines.append(
            f"{label:<{_LABEL_WIDTH}}{'':>6}{run.total_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
        )
    return lines


_NO_THRESHOLD = (
    "",
    "This harness asserts no threshold and returns no verdict. There is no",
    "approved performance floor for Engine 1; MEASUREMENT_FRAMEWORK.md section",
    "12 bounds the WHOLE six-engine pipeline at 60 seconds per document and",
    "nobody has divided that between engines. Inventing Engine 1's share here",
    "would be fabricating a number (CLAUDE.md Law 52). These figures are a",
    "local measurement: under Law 44 and MEASUREMENT_FRAMEWORK.md section 0a a",
    "result exists only if GitHub CI produced it.",
)

#: The single most misleading thing this harness could publish is a table
#: headed "Engine 1 latency" with no statement of what it ran on. Engine 1
#: exists to read invoices and receipts. This repository contains NONE — not
#: one invoice, receipt, bill, voucher or challan, and no image file of any
#: format. Its 40 PDFs are statutes, rules, notifications, circulars and ICAI
#: standards, every one of them carrying a real text layer.
#:
#: So every number here is TEXT-LAYER PDF EXTRACTION ON LEGAL DOCUMENTS, and a
#: latency measured on an 880-page Income-tax Act is not a claim about an
#: invoice. `tests/unit/test_engine1_pipeline_benchmark.py::
#: test_the_repository_declares_no_invoice_receipt_bill_or_scan` reads the real
#: manifest and goes red the day that stops being true, so this paragraph is a
#: checked fact rather than a comment.
_WHAT_WAS_ACTUALLY_MEASURED = (
    "",
    "WHAT THIS IS A MEASUREMENT OF - read before quoting any number above.",
    "",
    "Every document measured here is a legal document - a statute, rules, a",
    "notification, a circular, or an ICAI standard - each a PDF carrying a",
    "real text layer, and NOT AN ACCOUNTING DOCUMENT. This repository holds no",
    "invoice, no receipt, no bill, no voucher and no scan, and no image file of",
    "any format, so none was measured here and none could be.",
    "",
    "These numbers therefore describe TEXT-LAYER PDF EXTRACTION ON LEGAL",
    "DOCUMENTS. They are not a claim about invoice processing, which is what",
    "Engine 1 exists to do. Two of the paths that would dominate a real",
    "invoice never execute here: cleaner's deskew, denoise and contrast work on",
    "rendered pixels, and reader's OCR fallback. A photographed receipt runs",
    "both. An 880-page Income-tax Act runs neither.",
)


def render(report: BenchmarkReport) -> str:
    """One document's report as text. Same report in, same string out — every
    value here is read off the report, and nothing is sampled at render time."""
    lines: list[str] = [
        "Engine 1 pipeline latency - MEASURED, NOT JUDGED",
        "",
        *_document_lines(report),
        "",
        *_machine_lines(report.machine),
    ]
    lines.extend(_settings_lines(report.settings))
    # A lone report is always the only document in its process, so its run 1 is
    # the process's first. `render_suite` is where that stops being true.
    lines.extend(_cold_lines(report, first_in_process=True))
    lines.extend(_warm_lines(report))
    lines.extend(_every_run_lines(report))
    lines.extend(_WHAT_WAS_ACTUALLY_MEASURED)
    lines.extend(_NO_THRESHOLD)
    return "\n".join(lines)


# ── several documents, each number still attributed to one of them ───────


def refuse_duplicate_documents(names: Sequence[str]) -> None:
    """Two rows under one name make per-document attribution meaningless.

    One definition, called twice: `measure_all` calls it BEFORE any timer
    starts, so a mistyped repeat costs nothing rather than a full second
    measurement; `BenchmarkSuite` calls it again on the reports themselves, so
    a suite assembled by any other route is held to the same rule.
    """
    duplicated = sorted({name for name in names if list(names).count(name) > 1})
    if duplicated:
        raise BenchmarkError(
            f"{', '.join(duplicated)} was named more than once. Two rows under "
            "one document name is exactly the shape that makes per-document "
            "attribution meaningless: a reader cannot say which row belongs to "
            "which document, and the suite exists to answer that question."
        )


@dataclass(frozen=True, slots=True)
class BenchmarkSuite:
    """Several documents measured on one machine under one configuration.

    It exists because a single number for "Engine 1" is not one. This corpus
    runs from a 1-page notification to an 880-page statute, and the pipeline's
    cost is dominated by a stage that scales with pages — so one latency
    covering both is a number no document produced.

    The two refusals below are conservation checks, the same shape as
    `RunTiming`'s. A suite prints its machine and its settings ONCE, above every
    document, so those two facts must actually be shared. If they are not, the
    header would describe one document and be read as describing all of them,
    which is worse than printing nothing.
    """

    reports: tuple[BenchmarkReport, ...]

    def __post_init__(self) -> None:
        if not self.reports:
            raise BenchmarkError(
                "a benchmark suite of no documents has nothing to report. "
                "Refused rather than rendering an empty table, which reads as "
                "a measurement that found nothing rather than as one that "
                "never ran."
            )
        refuse_duplicate_documents([report.document.name for report in self.reports])
        first = self.reports[0]
        for report in self.reports[1:]:
            if report.machine != first.machine:
                raise BenchmarkError(
                    f"{report.document.name} was measured on a different "
                    f"machine ({report.machine}) from {first.document.name} "
                    f"({first.machine}). A suite prints one machine above every "
                    "document; two machines in one suite would attribute one "
                    "set of hardware to numbers that did not come from it, and "
                    "a latency compared across machines is not a comparison."
                )
            if report.settings != first.settings:
                raise BenchmarkError(
                    f"{report.document.name} was measured under different "
                    "settings from "
                    f"{first.document.name}. Those are two experiments, and one "
                    "settings block above them would describe only one."
                )

    @property
    def machine(self) -> Machine:
        return self.reports[0].machine

    @property
    def settings(self) -> pipeline.PipelineSettings:
        return self.reports[0].settings


def _index_lines(suite: BenchmarkSuite) -> list[str]:
    """One row per document: which document produced which number.

    Pages and the warm-run count sit beside every latency because neither
    number is judgeable without them — a p50 over 2 warm runs and a p50 over 21
    are not the same kind of number, and 3 seconds means something different at
    1 page and at 880.

    `slowest stage` is the row that makes the table worth reading: it names
    where the time went, per document, which is the only thing a latency table
    can honestly point at (§D.6 — optimising a non-bottleneck returns zero).
    """
    heading_label = "document"
    #: Derived from the names actually in this suite, for the same reason
    #: `field_lines` derives its width: this manifest declares filenames up to
    #: 77 characters, and a column assumed to be shorter does not truncate them
    #: — it pushes that one row's numbers right and quietly misaligns the
    #: table, which is how two rows get compared as though they were columns.
    width = max(len(heading_label), *(len(r.document.name) for r in suite.reports)) + _GAP
    heading = (
        f"{heading_label:<{width}}{'pages':>7}{'warm':>6}"
        f"{'p50 s':>{_NUMBER_WIDTH}}{'p95 s':>{_NUMBER_WIDTH}}"
        f"{'max s':>{_NUMBER_WIDTH}}  slowest stage"
    )
    lines = ["", "which document produced which number", heading]
    for report in suite.reports:
        total = report.total_summary()
        slowest = max(report.stage_summaries(), key=lambda summary: summary.p50_seconds)
        share = 0.0 if total.p50_seconds <= 0 else slowest.p50_seconds / total.p50_seconds
        lines.append(
            f"{report.document.name:<{width}}"
            f"{report.document.page_count:>7}{len(report.warm_runs):>6}"
            f"{total.p50_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
            f"{total.p95_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
            f"{total.max_seconds:>{_NUMBER_WIDTH}.{_SECONDS}f}"
            f"  {slowest.label} ({share:.1%} of p50)"
        )
    return lines


def render_suite(suite: BenchmarkSuite) -> str:
    """Every document's own numbers, under one machine and one settings block.

    The order is the order the suite was given, never sorted by duration: a
    table sorted by the thing being measured invites the reader to compare rows
    that differ in page count by two orders of magnitude.
    """
    lines: list[str] = [
        "Engine 1 pipeline latency - MEASURED, NOT JUDGED",
        f"{len(suite.reports)} documents, one machine, one configuration",
        "",
        *_machine_lines(suite.machine),
    ]
    lines.extend(_settings_lines(suite.settings))
    lines.extend(_index_lines(suite))
    for position, report in enumerate(suite.reports):
        lines.extend(["", "─" * _RULE_WIDTH, "", *_document_lines(report)])
        # Only the FIRST document's run 1 pays for model loading. Calling the
        # others "the first pipeline.run in this process" would attribute a
        # cost to a cause that had already been paid, and send anyone chasing
        # the remaining gap after the wrong thing.
        lines.extend(_cold_lines(report, first_in_process=position == 0))
        lines.extend(_warm_lines(report))
        lines.extend(_every_run_lines(report))
    lines.extend(_WHAT_WAS_ACTUALLY_MEASURED)
    lines.extend(_NO_THRESHOLD)
    return "\n".join(lines)


# ── the command line ─────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    described = argparse.ArgumentParser(
        prog="benchmarks.engine1_pipeline_benchmark",
        description=(
            "Measure Engine 1's pipeline latency, per stage, on real "
            "manifest-declared documents. Asserts no threshold."
        ),
    )
    described.add_argument(
        "--document",
        action="append",
        default=None,
        help=(
            "manifest filename to measure. Repeat it to measure several; every "
            f"number stays attributed to one (default: {DEFAULT_DOCUMENT})"
        ),
    )
    described.add_argument(
        "--manifest",
        default=None,
        help="manifest to resolve the documents through (default: the repository's)",
    )
    described.add_argument(
        "--runs",
        action="append",
        type=int,
        default=None,
        help=(
            "total runs, including the cold one. Give it once to apply to every "
            "document, or once per --document, in the same order - an 880-page "
            "statute and a 1-page notification cannot honestly share a run "
            f"count (default: {DEFAULT_RUNS})"
        ),
    )
    return described


def pair_runs_with_documents(names: Sequence[str], runs: Sequence[int]) -> tuple[int, ...]:
    """One run count per document, or a loud refusal.

    Two forms are accepted and no third is guessed: one count for every
    document, or exactly one count per document in the given order. Anything
    else has no correct pairing, and quietly dropping or recycling a count
    would mean a document was measured at a number nobody asked for — which is
    the same defect as inventing one.
    """
    if len(runs) == 1:
        return tuple(runs[0] for _ in names)
    if len(runs) == len(names):
        return tuple(runs)
    raise BenchmarkError(
        f"{len(runs)} --runs values were given for {len(names)} --document "
        f"values. Give --runs once to apply it to every document, or exactly "
        f"once per document in the same order. There is no correct way to pair "
        f"{len(runs)} counts with {len(names)} documents, and choosing one here "
        f"would measure a document at a run count nobody asked for."
    )


def measure_all(
    names: Sequence[str],
    runs: Sequence[int],
    *,
    manifest: pathlib.Path | None = None,
    settings: pipeline.PipelineSettings = SETTINGS,
) -> BenchmarkSuite:
    """Measure every named document, in order, at its own run count.

    Every document is resolved and hash-verified BEFORE the first timer starts.
    A suite that runs for twenty minutes and then refuses the last document has
    wasted the twenty minutes, and — worse — tempts whoever ran it to report
    the documents that did complete as though that were the measurement asked
    for.
    """
    refuse_duplicate_documents(names)
    paired = pair_runs_with_documents(names, runs)
    documents = [load_manifest_document(name, manifest=manifest) for name in names]
    return BenchmarkSuite(
        reports=tuple(
            measure(document, settings=settings, runs=count)
            for document, count in zip(documents, paired, strict=True)
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Measure, print, and exit zero on whatever was measured.

    A non-zero exit here would mean the harness had an opinion about the value,
    which it must not. The only failures are the ones that mean nothing was
    measured at all: an absent or unverifiable document, an impossible run
    count, an unpairable --runs list, or a stage that never ran.
    """
    arguments = _parser().parse_args(argv)
    names: list[str] = arguments.document or [DEFAULT_DOCUMENT]
    runs: list[int] = arguments.runs or [DEFAULT_RUNS]
    try:
        suite = measure_all(
            names,
            runs,
            manifest=None if arguments.manifest is None else pathlib.Path(arguments.manifest),
            settings=SETTINGS,
        )
    except (BenchmarkError, ValueError) as exc:
        print(f"benchmark did not run: {exc}", file=sys.stderr)
        return 1
    print(render_suite(suite))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
