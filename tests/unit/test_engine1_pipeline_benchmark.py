"""`benchmarks/engine1_pipeline_benchmark.py` — tests that attack the
INSTRUMENT, not the number it produces.

A benchmark harness has one failure mode that matters and it is not "the
number is wrong". It is **the number is right about the wrong thing**: a stage
silently reported as `0.000 s` because nobody called it, a stage list that
drifted away from what `pipeline.run` actually does, a "real pipeline" run that
is really a stand-in, or a total that quietly disagrees with the parts it is
supposed to be made of. Every one of those produces a clean, plausible,
publishable table. So every test below tries to produce exactly that table and
asserts it cannot be produced.

WHAT WOULD PROVE THIS HARNESS WRONG, TEST BY TEST.

  - the stage list is a copy someone forgot to update
    → `test_the_stage_list_is_exactly_what_pipeline_run_declares` re-derives
      the stages from `pipeline.run`'s own source with `ast` and demands
      equality, in order. Rename a stage in `pipeline.py` and this goes red.

  - the harness instruments a DIFFERENT module object than the one the
    pipeline calls, so the timings describe nothing
    → `test_every_probe_patches_the_exact_module_object_pipeline_calls`
      asserts identity (`is`) against `pipeline`'s own imported names.

  - the harness replaces a sub-engine instead of timing it (a mock proving the
    mock, §J.6)
    → `test_the_instrument_delegates_to_the_real_function_and_returns_its_
      exact_result` runs the real `cleaner.decode` through the wrapper and
      compares the array to the unwrapped call, pixel for pixel.

  - a stage that never ran is reported as zero
    → `test_a_declared_stage_that_never_runs_fails_loudly_instead_of_reporting
      _zero` declares a stage the run genuinely cannot reach and demands an
      exception naming it.

  - the parts do not add up to the whole
    → `RunTiming` refuses construction when the stages exceed the total, and
      `test_a_run_whose_stages_exceed_its_total_is_refused` proves it.

  - the percentile silently interpolates, or is really just the maximum
    → `test_the_percentile_is_nearest_rank_and_never_interpolates` pins exact
      values, including the case where p95 and the maximum differ.

  - the harness quietly becomes a GATE
    → `test_the_report_carries_no_verdict_field` pins the report's exact field
      set. There is no approved performance floor for Engine 1, so inventing
      one is forbidden (`CLAUDE.md` Law 52). A harness that measures cannot be
      allowed to grow a `passed` field by accident.

`CLAUDE.md` §J.6 — REAL + ISOLATED. Every timing test below runs the real
`cleaner`, `reader`, `parser`, `confidence_report` and `assembly` through the
real `pipeline.run`, on a real PDF this file builds with PyMuPDF, exactly as
`test_input_engine_pipeline.py` already does. Nothing is mocked. The document
loader is tested against a disposable manifest and a real PDF on disk, never
against the 42 MB corpus, so the test passes on a fresh clone that has not run
bootstrap.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import pathlib
import re
from collections.abc import Iterator
from decimal import Decimal
from typing import Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
import pymupdf
import pytest

from accountant_dad.engines.input_engine import (
    assembly,
    cleaner,
    confidence_report,
    parser,
    pipeline,
    reader,
)
from benchmarks import engine1_pipeline_benchmark as harness
from tools.evidence.registry import MANIFEST, read_manifest

# ── expected values, named so a comparison is never a bare literal ───────

#: `runs=2` everywhere a real pipeline run is needed: one cold, one warm. Each
#: run is seconds of real Docling work, and a third would buy no evidence this
#: file does not already have.
MEASURED_RUNS = 2
#: What `test_the_recorder_sums_repeat_calls_and_counts_them` records.
REPEAT_CALLS = 2
#: The smallest warm sample at which nearest-rank p95 is not simply the
#: maximum. MEASURED against `nearest_rank` itself, by
#: `test_p95_is_necessarily_the_maximum_below_twenty_samples`, over every
#: sample size on both sides of it — not asserted from an argument.
#:
#: It read 21 until 2026-08-06, from the stated ground that "p95 equals the
#: maximum for every sample of 20 or fewer". That is false at exactly one
#: value: `ceil(0.95 * 20) == 19`, so the p95 of 20 samples is the 19th of
#: them, not the 20th. An arithmetic claim inside a comment is still a claim,
#: and this one was checked only against itself.
SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX = 20
#: Fabricated run totals, in seconds, for the cold/warm split test. Chosen far
#: apart so a cold run leaking into the warm summary cannot hide in noise.
COLD_TOTAL = 20.0
FIRST_WARM_TOTAL = 3.0
SECOND_WARM_TOTAL = 4.0
#: How many documents `test_a_suite_...` measures. Two is the smallest number
#: at which "which document produced which number" is a question at all.
SUITE_DOCUMENTS = 2

#: Words that would make a manifest entry an ACCOUNTING document rather than a
#: legal one. The corpus caveat this harness prints is only true while none of
#: them appears; `test_the_repository_declares_no_invoice_receipt_bill_or_scan`
#: reads the real manifest and goes red the day one does.
ACCOUNTING_DOCUMENT_WORDS = ("invoice", "receipt", "bill", "voucher", "challan", "debit-note")
#: Extensions that would make an entry an image rather than a text-layer PDF.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".heic")

# ── a typed facade over PyMuPDF, for AUTHORING fixtures only ──────────────
#
# Same facade, same reason, as `test_input_engine_pipeline.py`'s own: PyMuPDF
# ships `py.typed` but leaves its functions unannotated, and this repository's
# suppression budget rules out silencing that per line. Module-private there,
# so not importable from here.


class _AuthoringPage(Protocol):
    def insert_text(
        self, point: tuple[float, float], text: str, *, fontname: str, fontsize: int
    ) -> int: ...


class _AuthoringDocument(Protocol):
    def new_page(self, *, width: float, height: float) -> _AuthoringPage: ...
    def tobytes(self) -> bytes: ...
    def close(self) -> None: ...


class _NewDocument(Protocol):
    def __call__(self) -> _AuthoringDocument: ...


open_pdf = cast(_NewDocument, pymupdf.open)

INVOICE_LINES: tuple[str, ...] = (
    "TAX INVOICE",
    "Acme Traders Private Limited",
    "GSTIN 27AAECS1234F1Z5",
)


def an_invoice_pdf() -> bytes:
    """A one-page PDF carrying a real text layer."""
    document = open_pdf()
    page = document.new_page(width=595, height=842)
    y = 90.0
    for line in INVOICE_LINES:
        page.insert_text((60, y), line, fontname="helv", fontsize=13)
        y += 34
    payload = bytes(document.tobytes())
    document.close()
    return payload


def a_benchmark_document(
    payload: bytes | None = None, *, name: str = "tiny-invoice.pdf"
) -> harness.BenchmarkDocument:
    body = payload if payload is not None else an_invoice_pdf()
    return harness.BenchmarkDocument(
        name=name,
        payload=body,
        sha256=hashlib.sha256(body).hexdigest(),
        page_count=1,
        kind="test",
        source_reference=f"test:{name}",
    )


def a_run_timing(index: int, total: float, per_stage: dict[str, float]) -> harness.RunTiming:
    return harness.RunTiming(
        index=index,
        total_seconds=total,
        stages=tuple(
            harness.StageTiming(stage=name, seconds=seconds, calls=1)
            for name, seconds in per_stage.items()
        ),
    )


@pytest.fixture(scope="module")
def measured() -> harness.BenchmarkReport:
    """One real end-to-end measurement, shared by every test that needs one.

    Module-scoped because each run is seconds of real Docling work and running
    it once per assertion would be the slowest thing in the suite for no extra
    evidence. `runs=2` is the arithmetic minimum the harness accepts: one cold
    run and one warm run.
    """
    return harness.measure(a_benchmark_document(), settings=harness.SETTINGS, runs=2)


# ── the stage list is the real pipeline's, not a copy ────────────────────


def stages_pipeline_declares() -> tuple[str, ...]:
    """The stage names `pipeline.run` itself names, read out of its source.

    `pipeline.run` names each stage exactly once, as the first argument of the
    `PipelineStageError` it raises for that stage. Reading them back out of the
    real source is an independent derivation — it agrees with the harness only
    when the harness is actually right, and it cannot be satisfied by editing
    the harness alone.
    """
    tree = ast.parse(inspect.getsource(pipeline.run))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != pipeline.PipelineStageError.__name__ or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.append(first.value)
    return tuple(names)


def test_the_stage_list_is_exactly_what_pipeline_run_declares() -> None:
    declared = stages_pipeline_declares()
    assert declared == ("cleaner", "reader", "parser", "confidence", "assembly"), (
        "pipeline.run's own stage names changed. The benchmark's stage list is "
        "downstream of this, and so is every number it has ever produced."
    )
    assert declared == harness.STAGE_NAMES, (
        f"the benchmark measures {harness.STAGE_NAMES} but pipeline.run runs "
        f"{declared}. A per-stage table that does not match the stages is worse "
        "than no table: it looks complete."
    )


def test_every_probe_patches_the_exact_module_object_pipeline_calls() -> None:
    imported = {
        "cleaner": cleaner,
        "reader": reader,
        "parser": parser,
        "confidence_report": confidence_report,
        "assembly": assembly,
    }
    for probe in harness.STAGES:
        short = probe.module.__name__.rsplit(".", 1)[-1]
        assert probe.module is imported[short], (
            f"probe {probe.name!r} points at a different {short} module object "
            "than pipeline imported; patching it would time nothing."
        )
        assert probe.module is getattr(pipeline, short), (
            f"probe {probe.name!r} does not patch the object `pipeline` itself "
            "resolves at call time."
        )
        assert callable(getattr(probe.module, probe.attribute)), (
            f"probe {probe.name!r} names {probe.attribute!r}, which is not callable."
        )


def test_the_probes_cover_every_declared_stage_exactly_once() -> None:
    named = [probe.name for probe in harness.STAGES]
    assert named == list(harness.STAGE_NAMES)
    assert len(set(named)) == len(named), f"a stage is probed twice: {named}"


# ── the instrument times the real function, it does not replace it ───────


def test_the_instrument_delegates_to_the_real_function_and_returns_its_exact_result() -> None:
    frame: npt.NDArray[np.uint8] = np.zeros((8, 8), dtype=np.uint8)
    frame[2:6, 2:6] = 255
    ok, encoded = cv2.imencode(".png", frame)
    assert ok
    png = bytes(encoded.tobytes())

    unwrapped = cleaner.decode(png)
    original = cleaner.decode
    recorder = harness.StageRecorder()
    probe = harness.StageProbe(name="decode", module=cleaner, attribute="decode")

    with harness.instrumented((probe,), recorder):
        assert cleaner.decode is not original, "the instrument did not install"
        through_wrapper = cleaner.decode(png)

    assert cleaner.decode is original, "the instrument did not uninstall"
    assert np.array_equal(through_wrapper, unwrapped), (
        "the wrapper changed cleaner.decode's result. It must time the real "
        "function and hand back exactly what it returned."
    )
    assert recorder.calls("decode") == 1
    assert recorder.seconds("decode") > 0.0


def test_the_instrument_uninstalls_even_when_the_timed_call_raises() -> None:
    original = cleaner.decode
    recorder = harness.StageRecorder()
    probe = harness.StageProbe(name="decode", module=cleaner, attribute="decode")

    with pytest.raises(cleaner.UndecodableArtifactError), harness.instrumented((probe,), recorder):
        cleaner.decode(b"not an image at all")

    assert cleaner.decode is original, (
        "a raising call left the real module patched. Every later measurement "
        "in the process would then be timing a wrapper of a wrapper."
    )
    assert recorder.calls("decode") == 1, "a raising call must still be counted"


# ── a stage that never ran is never reported as zero ─────────────────────


def test_a_declared_stage_that_never_runs_fails_loudly_instead_of_reporting_zero() -> None:
    """`reader.read_by_ocr` is the OCR path. `SETTINGS` sets the vision-fallback
    threshold to zero, and the fixture PDF carries a real text layer, so the
    run cannot reach it. Declaring it as a stage is exactly the shape of the
    accident this guard exists for: a stage name that no longer matches a
    called function.
    """
    never_runs = harness.StageProbe(name="ocr", module=reader, attribute="read_by_ocr")
    with pytest.raises(harness.StageDidNotRunError) as raised:
        harness.measure(
            a_benchmark_document(),
            settings=harness.SETTINGS,
            runs=2,
            stages=(*harness.STAGES, never_runs),
        )
    message = str(raised.value)
    assert "ocr" in message
    assert "read_by_ocr" in message
    assert "never ran" in message
    assert "0.0" not in message, (
        "the failure must not offer a duration as a substitute for the missing "
        f"measurement; got {message!r}"
    )


def test_the_recorder_refuses_to_report_a_stage_it_never_saw() -> None:
    recorder = harness.StageRecorder()
    recorder.record("cleaner", 0.5)
    probes = (
        harness.StageProbe(name="cleaner", module=cleaner, attribute="clean_artifact"),
        harness.StageProbe(name="reader", module=reader, attribute="read"),
    )
    with pytest.raises(harness.StageDidNotRunError, match="reader"):
        recorder.timings(probes)


def test_the_recorder_sums_repeat_calls_and_counts_them() -> None:
    recorder = harness.StageRecorder()
    recorder.record("parser", 0.25)
    recorder.record("parser", 0.75)
    probe = harness.StageProbe(name="parser", module=parser, attribute="parse")
    (timing,) = recorder.timings((probe,))
    assert timing.seconds == pytest.approx(1.0)
    assert timing.calls == REPEAT_CALLS, (
        "a stage called twice must SAY so. One number covering two calls with "
        "no count is how a per-document figure quietly becomes a per-page one."
    )


# ── the parts add up to the whole ────────────────────────────────────────


def test_a_run_whose_stages_exceed_its_total_is_refused() -> None:
    with pytest.raises(harness.ImpossibleTimingError, match=r"0\.9"):
        a_run_timing(0, 0.9, {"cleaner": 0.5, "reader": 0.6})


def test_unattributed_time_is_the_total_minus_the_stages() -> None:
    run = a_run_timing(0, 1.0, {"cleaner": 0.25, "reader": 0.25})
    assert run.unattributed_seconds == pytest.approx(0.5)


# ── percentiles ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("values", "percentile", "expected"),
    [
        ((1.0,), 50, 1.0),
        ((1.0,), 95, 1.0),
        ((1.0, 2.0), 50, 1.0),
        ((1.0, 2.0), 95, 2.0),
        ((1.0, 2.0, 3.0, 4.0), 50, 2.0),
        ((1.0, 2.0, 3.0, 4.0), 95, 4.0),
        (tuple(float(n) for n in range(1, 22)), 50, 11.0),
        # 21 samples is the smallest at which nearest-rank p95 is NOT the
        # maximum: ceil(0.95 * 21) = 20, so the 20th of 21, not the 21st.
        (tuple(float(n) for n in range(1, 22)), 95, 20.0),
    ],
)
def test_the_percentile_is_nearest_rank_and_never_interpolates(
    values: tuple[float, ...], percentile: int, expected: float
) -> None:
    assert harness.nearest_rank(values, percentile) == expected


def test_the_percentile_refuses_an_empty_sample() -> None:
    with pytest.raises(ValueError, match="no samples"):
        harness.nearest_rank((), 50)


def test_the_percentile_refuses_a_percentile_outside_its_range() -> None:
    for percentile in (0, -1, 101):
        with pytest.raises(ValueError, match="percentile"):
            harness.nearest_rank((1.0, 2.0), percentile)


def test_the_default_run_count_makes_p95_distinguishable_from_the_maximum() -> None:
    """Not taste — arithmetic. Nearest-rank p95 equals the maximum for every
    warm sample of 20 or fewer, so a default below that would publish a "p95"
    that is only ever the worst run under another name.
    """
    warm = harness.DEFAULT_RUNS - 1
    assert warm >= SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX, (
        f"{warm} warm runs makes nearest-rank p95 identical to the maximum; "
        "the column would be a second name for max."
    )
    sample = tuple(float(n) for n in range(warm))
    assert harness.nearest_rank(sample, 95) < max(sample)


# ── the summary splits the cold run from the warm ones ───────────────────


def test_the_first_run_is_reported_as_cold_and_excluded_from_the_warm_summary() -> None:
    runs = (
        a_run_timing(0, COLD_TOTAL, {"cleaner": 1.0, "reader": 1.0}),
        a_run_timing(1, FIRST_WARM_TOTAL, {"cleaner": 1.0, "reader": 1.0}),
        a_run_timing(2, SECOND_WARM_TOTAL, {"cleaner": 1.0, "reader": 1.0}),
    )
    report = harness.BenchmarkReport(
        document=a_benchmark_document(),
        machine=harness.Machine.here(),
        settings=harness.SETTINGS,
        runs=runs,
    )
    assert report.cold_run.total_seconds == COLD_TOTAL
    assert tuple(run.index for run in report.warm_runs) == (1, 2)
    total = report.total_summary()
    assert total.samples == MEASURED_RUNS
    assert total.p50_seconds == FIRST_WARM_TOTAL
    assert total.p95_seconds == SECOND_WARM_TOTAL
    assert total.max_seconds == SECOND_WARM_TOTAL, (
        "the cold run must not leak into the warm summary"
    )


def test_a_single_run_is_refused_because_cold_cannot_be_told_from_warm() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        harness.measure(a_benchmark_document(), settings=harness.SETTINGS, runs=1)


# ── a real, end-to-end measurement ───────────────────────────────────────


def test_a_real_run_produces_a_positive_duration_for_every_stage(
    measured: harness.BenchmarkReport,
) -> None:
    assert len(measured.runs) == MEASURED_RUNS
    for run in measured.runs:
        assert tuple(timing.stage for timing in run.stages) == harness.STAGE_NAMES
        for timing in run.stages:
            assert timing.seconds > 0.0, (
                f"stage {timing.stage!r} of run {run.index} timed at "
                f"{timing.seconds}. A real sub-engine that ran took real time; "
                "a zero here means the number describes nothing."
            )
            assert timing.calls >= 1
        assert run.total_seconds > 0.0
        assert run.unattributed_seconds >= 0.0


def test_the_real_run_produced_a_real_document_evidence_object(
    measured: harness.BenchmarkReport,
) -> None:
    """The harness must not be able to report a fast pipeline that produced
    nothing. Every run's artifact is checked for the text the fixture actually
    contains — the same ground-truth check `test_input_engine_pipeline.py`
    makes, so a benchmark cannot pass on a pipeline that stopped working.
    """
    assert len(measured.artifacts) == len(measured.runs)
    for artifact in measured.artifacts:
        text = artifact.structured_document.extracted_text
        for line in INVOICE_LINES:
            assert line in text, f"{line!r} never reached the artifact this run timed"


def test_the_warm_summary_covers_every_stage_plus_the_total_and_the_remainder(
    measured: harness.BenchmarkReport,
) -> None:
    summaries = measured.stage_summaries()
    assert tuple(summary.label for summary in summaries) == harness.STAGE_NAMES
    for summary in summaries:
        assert summary.samples == 1, "runs=2 leaves exactly one warm run"
        assert summary.min_seconds <= summary.p50_seconds <= summary.max_seconds
        assert summary.p95_seconds <= summary.max_seconds
    assert measured.total_summary().label == "total"
    assert measured.unattributed_summary().label == "unattributed"


# ── the report is a measurement, never a verdict ─────────────────────────


def test_the_report_carries_no_verdict_field() -> None:
    fields = {field.name for field in dataclasses.fields(harness.BenchmarkReport)}
    assert fields == {"document", "machine", "settings", "runs", "artifacts"}, (
        f"BenchmarkReport's fields changed to {sorted(fields)}. There is no "
        "approved performance floor for Engine 1, so this report may not carry "
        "a pass, a fail, a threshold or a budget (CLAUDE.md Law 52)."
    )


def test_the_rendered_report_states_the_run_count_the_machine_and_every_stage(
    measured: harness.BenchmarkReport,
) -> None:
    rendered = harness.render(measured)
    assert rendered == harness.render(measured), "render must be deterministic"
    assert re.search(rf"^runs\s\s+{len(measured.runs)}$", rendered, re.MULTILINE), (
        "the run count must be on its own line as a label and a value. A "
        "percentile whose sample size is not stated is not a percentile "
        f"anybody can judge. Report was:\n{rendered}"
    )
    assert re.search(rf"^warm runs\s\s+{len(measured.warm_runs)}$", rendered, re.MULTILINE), (
        "the WARM run count is the one p50 and p95 are actually over, and it "
        "is not the same number as the total run count"
    )
    assert measured.document.sha256 in rendered
    assert measured.machine.python_version in rendered
    assert "p50" in rendered
    assert "p95" in rendered
    for stage in harness.STAGE_NAMES:
        assert stage in rendered
    assert "no threshold" in rendered.lower(), (
        "the report must say, in words, that it asserts no threshold. A table "
        "of latencies with no such line is read as a budget by the next person."
    )


def test_the_rendered_report_states_every_setting_that_produced_the_numbers(
    measured: harness.BenchmarkReport,
) -> None:
    rendered = harness.render(measured)
    assert str(harness.SETTINGS.render_dpi) in rendered
    assert str(harness.SETTINGS.vision_fallback_threshold) in rendered
    for field in dataclasses.fields(cleaner.CleanerSettings):
        assert field.name in rendered, (
            f"{field.name} is one of the numbers that produced these timings "
            "and it is not in the report. A latency without its settings is "
            "not reproducible."
        )


def test_every_setting_is_printed_as_a_label_and_a_readable_value(
    measured: harness.BenchmarkReport,
) -> None:
    """FOUND ON THE FIRST REAL RUN, 2026-08-06. Six of the eleven settings
    lines printed as `vision_fallback_threshold0.0`, `max_deskew_degrees15.0`,
    `denoise_template_window7` — the label column was a fixed 20 characters and
    every longer label ran straight into its value with no separator.

    That is not cosmetic. `denoise_template_window7` is ambiguous between a
    window of 7 and a label ending in 7, and the entire purpose of printing the
    settings is that a reader can reproduce the run from them. A value nobody
    can read back is not a reported value, so those six numbers were not
    actually reported.

    This asserts the PROPERTY — label, then a gap, then exactly the value, then
    end of line — never the width 20. Widening a constant would satisfy a test
    that pinned the constant and would fail this one again on the next longer
    label (§J.9, fix the class).
    """
    rendered = harness.render(measured)
    printed = [
        ("render_dpi", harness.SETTINGS.render_dpi),
        ("vision_fallback_threshold", harness.SETTINGS.vision_fallback_threshold),
        ("table_structure", harness.SETTINGS.table_structure),
        *(
            (field.name, getattr(harness.SETTINGS.cleaner_settings, field.name))
            for field in dataclasses.fields(cleaner.CleanerSettings)
        ),
    ]
    for label, value in printed:
        pattern = rf"^\s*{re.escape(label)}\s\s+{re.escape(str(value))}\s*$"
        assert re.search(pattern, rendered, re.MULTILINE), (
            f"{label!r} and its value {str(value)!r} are not on one line "
            "separated by a gap. Either the setting is missing or the label "
            f"column swallowed the separator. Report was:\n{rendered}"
        )


def test_every_table_label_fits_its_column() -> None:
    """The other half of the same defect, in the one place the width is still
    fixed.

    `field_lines` derives its width; the three per-stage TABLES cannot, because
    their rows have to align with each other and with a heading. That makes
    `_LABEL_WIDTH` an assumption, and the settings block proved what an
    unchecked width assumption does. The labels that land in this column are
    not all written here — `STAGE_NAMES` is re-derived from `pipeline.run`'s
    own source — so a stage renamed to something long in the pipeline would
    silently collide with its own `calls` column.
    """
    longest_run_label = f"{harness.DEFAULT_RUNS} (cold)"
    for label in (
        *harness.STAGE_NAMES,
        harness.TOTAL_LABEL,
        harness.UNATTRIBUTED_LABEL,
        longest_run_label,
        "stage",
        "run",
    ):
        assert len(label) + 2 <= harness._LABEL_WIDTH, (
            f"{label!r} is {len(label)} characters and the table column is "
            f"{harness._LABEL_WIDTH}, so it would run into the column beside "
            "it. Widen the column or shorten the label; do not print a row "
            "whose label and value cannot be told apart."
        )


def test_a_field_block_widens_to_its_own_longest_label() -> None:
    """The class-level fix, tested directly: the column is DERIVED from the
    content, so no label can ever be long enough to collide with its value."""
    lines = harness.field_lines(
        (("short", 1), ("a_label_far_longer_than_any_column_anyone_would_guess", 2))
    )
    for line in lines:
        label, _, value = line.rpartition("  ")
        assert label.strip(), f"{line!r} has no label before its value"
        assert value.strip(), f"{line!r} has no value after its label"
    assert lines[0].startswith("short "), "the short label must be padded, not trimmed"
    assert lines[0].endswith("1")
    assert lines[1].endswith("2")


@pytest.mark.parametrize("samples", range(1, 41))
def test_p95_is_necessarily_the_maximum_below_twenty_samples(samples: int) -> None:
    """The predicate is checked against the REAL percentile at every sample
    size on both sides of the boundary — never against the argument for it.

    That distinction is the whole point of this test. The boundary constant was
    wrong by one for as long as it was justified by a sentence rather than by
    `nearest_rank`, and the sentence and the constant agreed with each other
    the entire time. Two things that were derived from one another cannot check
    one another; a third, independent source can, and here it is the function
    the report actually calls.
    """
    ascending = tuple(float(n) for n in range(samples))
    truly_the_maximum = harness.nearest_rank(ascending, 95) == max(ascending)

    assert harness.p95_is_necessarily_the_maximum(samples) is truly_the_maximum, (
        f"the predicate and the percentile disagree at {samples} samples. One "
        "of them is what the report warns from and the other is what it prints."
    )
    assert truly_the_maximum is (samples < SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX), (
        f"at {samples} samples p95 "
        f"{'is' if truly_the_maximum else 'is not'} the maximum, which puts the "
        f"boundary somewhere other than "
        f"{SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX}."
    )


def test_the_report_says_when_its_p95_column_is_only_the_maximum(
    measured: harness.BenchmarkReport,
) -> None:
    """`measured` has one warm run, so its p95 IS its max. The report must say
    so in words. A latency table whose p95 column silently equals its max
    column is read as a tail measurement by the next person, and it is not one.
    """
    assert len(measured.warm_runs) < SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX
    rendered = harness.render(measured)
    warning = [line for line in rendered.splitlines() if "p95 here is the maximum" in line]
    assert len(warning) == 1, (
        "a report whose warm sample cannot distinguish p95 from max must say "
        f"so, exactly once; {len(measured.warm_runs)} warm runs cannot. "
        f"Got:\n{rendered}"
    )
    assert str(len(measured.warm_runs)) in warning[0], (
        "the warning must state the sample size it is warning about"
    )

    quoted = re.search(r"(\d+) warm runs is the smallest", warning[0])
    assert quoted, f"the warning must say how many warm runs WOULD do: {warning[0]!r}"
    needed = int(quoted.group(1))
    assert not harness.p95_is_necessarily_the_maximum(needed), (
        f"the report tells the reader {needed} warm runs is enough, and at "
        f"{needed} the harness's own predicate still says p95 is the maximum. "
        "The advice is wrong, so acting on it would produce another sample "
        "with the same defect."
    )
    assert harness.p95_is_necessarily_the_maximum(needed - 1), (
        f"the report says {needed} is the SMALLEST sufficient sample, but "
        f"{needed - 1} is already sufficient. Over-stating it costs real runs: "
        "on an 880-page statute one extra run is minutes."
    )


def test_the_report_does_not_cry_wolf_when_the_warm_sample_is_large_enough() -> None:
    """The inverse, which is what stops the warning from being decoration: at
    21 warm runs the p95 column does carry its own information and the line
    must be absent."""
    report = a_report(
        "Only.pdf",
        tuple(1.0 + index for index in range(SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX + 1)),
    )
    assert len(report.warm_runs) == SMALLEST_SAMPLE_WHERE_P95_DIFFERS_FROM_MAX
    assert "p95 here is the maximum" not in harness.render(report).lower()


# ── more than one document, and every number attributed to one ───────────


def every_stage(parser_seconds: float) -> dict[str, float]:
    """All five stages, with `parser` given the bulk of the time.

    Every stage, not a convenient two: a suite renders `stage_summaries()`, and
    a report missing a stage raises rather than reporting a zero for it — which
    is the harness working correctly and a fixture that lies about what a real
    run looks like.
    """
    return {
        "cleaner": 0.01,
        "reader": 0.05,
        "parser": parser_seconds,
        "confidence": 0.0001,
        "assembly": 0.0001,
    }


def a_report(name: str, totals: tuple[float, ...]) -> harness.BenchmarkReport:
    return harness.BenchmarkReport(
        document=a_benchmark_document(name=name),
        machine=harness.Machine.here(),
        settings=harness.SETTINGS,
        runs=tuple(
            a_run_timing(index, total, every_stage(total * 0.9))
            for index, total in enumerate(totals)
        ),
    )


def test_a_suite_names_every_document_and_keeps_their_numbers_apart() -> None:
    """The whole reason a suite exists. One table of latencies covering several
    documents, with no column saying which document each row came from, is a
    number attributed to nothing — and an 8-page circular and an 880-page
    statute are in this corpus together.
    """
    slow = a_report("Big-Statute.pdf", (30.0, 20.0, 21.0))
    fast = a_report("Small-Circular.pdf", (3.0, 1.0, 2.0))
    suite = harness.BenchmarkSuite(reports=(slow, fast))

    assert tuple(report.document.name for report in suite.reports) == (
        "Big-Statute.pdf",
        "Small-Circular.pdf",
    )
    rendered = harness.render_suite(suite)
    for report in suite.reports:
        assert report.document.name in rendered
        assert report.document.sha256 in rendered

    big = rendered.index("Big-Statute.pdf")
    small = rendered.index("Small-Circular.pdf")
    assert big < small, "the suite must keep the order it was given"
    assert "20.0000" in rendered and "1.0000" in rendered, (
        "each document's own p50 must appear; a suite that averages across "
        "documents of different sizes reports a number no document produced"
    )


def test_only_the_first_document_s_run_one_is_called_the_process_s_cold_run() -> None:
    """FOUND ON THE FIRST REAL SUITE RUN, 2026-08-06. Every document's run 1 was
    headed *"the first pipeline.run in this process"*. That is true of exactly
    one of them.

    It is not a wording nit. Docling's models load once per process, and that
    heading tells the reader run 1 is expensive BECAUSE of model loading. By the
    second document the models are already in memory — measured: document 2's
    run 1 still cost 24.04 s against a 7.10 s warm p50 — so the heading pointed
    at a cause that had already been paid for and would have sent anyone
    investigating the remaining 17 seconds after the wrong thing.
    """
    suite = harness.BenchmarkSuite(
        reports=(a_report("First.pdf", (30.0, 3.0, 4.0)), a_report("Second.pdf", (20.0, 3.0, 4.0)))
    )
    rendered = harness.render_suite(suite)
    assert rendered.count(harness.COLD_FIRST_IN_PROCESS) == 1, (
        "exactly one document's run 1 is the process's first run, and only "
        f"that one may say so. Got {rendered.count(harness.COLD_FIRST_IN_PROCESS)}."
    )
    assert rendered.count(harness.COLD_LATER_DOCUMENT) == len(suite.reports) - 1

    first = rendered.index(harness.COLD_FIRST_IN_PROCESS)
    later = rendered.index(harness.COLD_LATER_DOCUMENT)
    assert first < later, "the process's cold run belongs to the FIRST document"
    assert "models already loaded" in harness.COLD_LATER_DOCUMENT, (
        "the later-document heading must say why it is not the same thing, or "
        "the reader is left to assume it is"
    )


def test_a_lone_report_calls_its_run_one_the_process_s_cold_run() -> None:
    """The other side: one document IS the only thing in its process, so its
    run 1 genuinely is the process's first and must keep saying so."""
    rendered = harness.render(a_report("Only.pdf", (30.0, 3.0, 4.0)))
    assert harness.COLD_FIRST_IN_PROCESS in rendered
    assert harness.COLD_LATER_DOCUMENT not in rendered


def test_a_suite_reports_the_machine_once_and_refuses_two_machines() -> None:
    """Two reports from two machines are not a comparison, and printing one
    machine block above both would be a false attribution. Refused rather than
    rendered."""
    here = a_report("A.pdf", (3.0, 1.0, 2.0))
    elsewhere = dataclasses.replace(
        a_report("B.pdf", (3.0, 1.0, 2.0)),
        machine=dataclasses.replace(here.machine, processor="a different chip"),
    )
    with pytest.raises(harness.BenchmarkError, match="machine"):
        harness.BenchmarkSuite(reports=(here, elsewhere))

    rendered = harness.render_suite(harness.BenchmarkSuite(reports=(here,)))
    assert rendered.count(here.machine.platform) == 1, (
        "the machine belongs to the suite, not to each row; repeating it "
        "invites a reader to think two rows came from two machines"
    )


def test_a_suite_refuses_two_different_settings_blocks() -> None:
    """Same reason, different axis: two documents timed under two
    configurations are two experiments, and one settings block above them would
    describe only one of them."""
    first = a_report("A.pdf", (3.0, 1.0, 2.0))
    other = dataclasses.replace(
        a_report("B.pdf", (3.0, 1.0, 2.0)),
        settings=dataclasses.replace(harness.SETTINGS, render_dpi=harness.SETTINGS.render_dpi + 1),
    )
    with pytest.raises(harness.BenchmarkError, match="settings"):
        harness.BenchmarkSuite(reports=(first, other))


def test_a_suite_of_no_documents_is_refused() -> None:
    with pytest.raises(harness.BenchmarkError, match="no documents"):
        harness.BenchmarkSuite(reports=())


def test_the_suite_index_states_pages_and_run_count_beside_every_latency() -> None:
    """A latency without its page count is not comparable to the next row, and
    a p50 without its warm-run count cannot be judged at all.

    Asserts the VALUES on the row, not the heading words. A heading survives
    the deletion of the column under it, which is exactly how a table keeps
    promising something it no longer carries.
    """
    pages = 880
    report = dataclasses.replace(
        a_report("Statute.pdf", (30.0, 20.0, 21.0)),
        document=dataclasses.replace(a_benchmark_document(name="Statute.pdf"), page_count=pages),
    )
    rendered = harness.render_suite(harness.BenchmarkSuite(reports=(report,)))
    row = next(
        line
        for line in rendered.splitlines()
        if line.startswith("Statute.pdf") and "parser" in line
    )
    assert re.search(rf"\s{pages}\s", row), (
        f"the index row carries no page count: {row!r}. Three seconds means "
        "something different at 1 page and at 880, and the row is the only "
        "place a reader can tell which."
    )
    assert re.search(rf"\s{len(report.warm_runs)}\s", row), (
        f"the index row carries no warm-run count: {row!r}. A p50 over 2 runs "
        "and a p50 over 21 are not the same kind of number."
    )
    assert "pages" in rendered and "warm" in rendered, "the columns need headings too"


# ── the corpus is legal documents, and the report says so ────────────────


def test_the_suite_states_that_no_accounting_document_was_measured() -> None:
    """The single most misleading thing this harness could produce is a latency
    table for "Engine 1" with no statement of what it ran on. Engine 1 exists to
    read invoices; this repository holds statutes, circulars and ICAI standards
    and NOT ONE invoice, receipt, bill or scan, and no image file of any format.
    A number measured on an 880-page Income-tax Act is not a claim about an
    invoice, and the report must say that where the numbers are, not in a file
    somebody may not open.
    """
    rendered = harness.render_suite(
        harness.BenchmarkSuite(reports=(a_report("Only.pdf", (9.0, 1.0, 2.0)),))
    ).lower()
    for word in ("invoice", "receipt", "not an accounting document"):
        assert word in rendered, f"the corpus caveat does not mention {word!r}. Got:\n{rendered}"
    assert "text-layer" in rendered or "text layer" in rendered, (
        "the caveat must also say what WAS measured - text-layer PDF "
        "extraction - or it only says what the number is not."
    )


def test_the_repository_declares_no_invoice_receipt_bill_or_scan() -> None:
    """The measured fact the caveat rests on, checked against the REAL manifest.

    This is the test that makes the caveat falsifiable rather than a comment.
    The day somebody adds an invoice or a scanned image to the evidence library,
    this goes red, and whoever added it has to revisit every performance
    sentence that says "legal documents, not accounting documents".
    """
    declared = read_manifest(MANIFEST)
    assert declared, "the manifest declares nothing, so the caveat is untested"
    for name, document in declared.items():
        lowered = name.lower()
        for word in ACCOUNTING_DOCUMENT_WORDS:
            assert word not in lowered, (
                f"{name} looks like an accounting document ({word!r}). The "
                "benchmark's caveat says this corpus holds none; update the "
                "caveat and every number that relies on it."
            )
        for suffix in IMAGE_SUFFIXES:
            assert not lowered.endswith(suffix), (
                f"{name} is an image. Engine 1's OCR and cleaning paths are "
                "not exercised by a text-layer PDF, so a benchmark that only "
                "measures PDFs no longer describes the corpus."
            )
        assert document.kind not in ACCOUNTING_DOCUMENT_WORDS, (
            f"{name} declares kind {document.kind!r}, which is an accounting "
            "document kind. See above."
        )


def test_the_loader_carries_each_document_s_own_manifest_kind(
    two_document_tree: pathlib.Path,
) -> None:
    """`kind` is how the report says what it measured without anybody typing a
    claim: it is the manifest's own word for the document, carried through.

    TWO documents with DIFFERENT kinds, because one document cannot tell a
    carried value from a hardcoded one — a loader that always returned
    `"guidance"` passed a single-document version of this test.
    """
    kinds = {
        name: harness.load_manifest_document(name, manifest=two_document_tree).kind
        for name in ("First.pdf", "Second.pdf")
    }
    assert kinds == {"First.pdf": "guidance", "Second.pdf": "circular"}, (
        f"the kind must come from each document's own manifest record, not be "
        f"invented at load time or shared between documents; got {kinds}"
    )


# ── the document is the one the manifest declares, or nothing ────────────


@pytest.fixture
def evidence_tree(tmp_path: pathlib.Path) -> Iterator[tuple[pathlib.Path, bytes]]:
    """A complete, disposable manifest and sources tree holding one real PDF.

    §J.6 — the loader is exercised against a real manifest and real bytes on
    disk, never against the repository's own 42 MB corpus, which is gitignored
    and absent on a fresh clone.
    """
    sources = tmp_path / "sources"
    sources.mkdir()
    payload = an_invoice_pdf()
    (sources / "Tiny-Invoice.pdf").write_bytes(payload)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "file": "Tiny-Invoice.pdf",
                "body": "test",
                "kind": "guidance",
                "url": "https://example.invalid/tiny.pdf",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    yield manifest, payload


def test_the_loader_returns_the_declared_bytes_and_counts_the_real_pages(
    evidence_tree: tuple[pathlib.Path, bytes],
) -> None:
    manifest, payload = evidence_tree
    document = harness.load_manifest_document("Tiny-Invoice.pdf", manifest=manifest)
    assert document.payload == payload
    assert document.sha256 == hashlib.sha256(payload).hexdigest()
    assert document.page_count == 1
    assert document.name == "Tiny-Invoice.pdf"


def test_the_loader_refuses_bytes_that_do_not_match_the_declared_hash(
    evidence_tree: tuple[pathlib.Path, bytes],
) -> None:
    manifest, _ = evidence_tree
    (manifest.parent / "sources" / "Tiny-Invoice.pdf").write_bytes(b"%PDF-1.4 different")
    with pytest.raises(harness.BenchmarkDocumentError) as raised:
        harness.load_manifest_document("Tiny-Invoice.pdf", manifest=manifest)
    message = str(raised.value)
    assert "Tiny-Invoice.pdf" in message
    assert hashlib.sha256(b"%PDF-1.4 different").hexdigest() in message, (
        "the failure must state the hash actually found, not only that one "
        "did not match — a timing attributed to unknown bytes is not a result."
    )


def test_the_loader_refuses_a_document_that_is_absent_and_says_how_to_get_it(
    evidence_tree: tuple[pathlib.Path, bytes],
) -> None:
    manifest, _ = evidence_tree
    (manifest.parent / "sources" / "Tiny-Invoice.pdf").unlink()
    with pytest.raises(harness.BenchmarkDocumentError) as raised:
        harness.load_manifest_document("Tiny-Invoice.pdf", manifest=manifest)
    message = str(raised.value)
    assert "Tiny-Invoice.pdf" in message
    assert "tools.evidence.bootstrap" in message


def test_the_loader_refuses_a_document_the_manifest_never_declared(
    evidence_tree: tuple[pathlib.Path, bytes],
) -> None:
    manifest, _ = evidence_tree
    with pytest.raises(harness.BenchmarkDocumentError, match=r"Not-Declared\.pdf"):
        harness.load_manifest_document("Not-Declared.pdf", manifest=manifest)


def test_the_default_document_is_one_the_repository_actually_declares() -> None:
    """The default is a real, hash-pinned government PDF in the manifest — not
    a filename someone hoped was there. This test reads the real manifest and
    does not need the PDF itself, which is gitignored.
    """
    declared = read_manifest(MANIFEST)
    assert harness.DEFAULT_DOCUMENT in declared, (
        f"{harness.DEFAULT_DOCUMENT} is not in the manifest, so no run of this "
        "benchmark can be attributed to a known document."
    )


# ── the command line ─────────────────────────────────────────────────────


def test_main_measures_the_named_document_and_exits_zero(
    evidence_tree: tuple[pathlib.Path, bytes], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _ = evidence_tree
    code = harness.main(
        [
            "--manifest",
            str(manifest),
            "--document",
            "Tiny-Invoice.pdf",
            "--runs",
            "2",
        ]
    )
    assert code == 0, "a measurement never fails on the value it measured"
    printed = capsys.readouterr().out
    assert "Tiny-Invoice.pdf" in printed
    assert re.search(r"^runs\s\s+2$", printed, re.MULTILINE), (
        f"the run count must be printed beside its label; got:\n{printed}"
    )
    for stage in harness.STAGE_NAMES:
        assert stage in printed


def test_main_reports_a_missing_document_as_a_failure_not_as_a_zero(
    evidence_tree: tuple[pathlib.Path, bytes], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _ = evidence_tree
    (manifest.parent / "sources" / "Tiny-Invoice.pdf").unlink()
    code = harness.main(
        ["--manifest", str(manifest), "--document", "Tiny-Invoice.pdf", "--runs", "2"]
    )
    assert code != 0
    printed = capsys.readouterr()
    assert "tools.evidence.bootstrap" in printed.out + printed.err


def test_main_refuses_a_run_count_below_two(
    evidence_tree: tuple[pathlib.Path, bytes], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _ = evidence_tree
    code = harness.main(
        ["--manifest", str(manifest), "--document", "Tiny-Invoice.pdf", "--runs", "1"]
    )
    assert code != 0
    printed = capsys.readouterr()
    assert "at least 2" in printed.out + printed.err


@pytest.fixture
def two_document_tree(tmp_path: pathlib.Path) -> Iterator[pathlib.Path]:
    """Two real, differently-named PDFs in one disposable manifest."""
    sources = tmp_path / "sources"
    sources.mkdir()
    lines = []
    for name, kind in (("First.pdf", "guidance"), ("Second.pdf", "circular")):
        payload = an_invoice_pdf()
        (sources / name).write_bytes(payload)
        lines.append(
            json.dumps(
                {
                    "file": name,
                    "body": "test",
                    "kind": kind,
                    "url": f"https://example.invalid/{name}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        )
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    yield manifest


def test_main_measures_every_named_document_and_attributes_each_number(
    two_document_tree: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = harness.main(
        [
            "--manifest",
            str(two_document_tree),
            "--document",
            "First.pdf",
            "--document",
            "Second.pdf",
            "--runs",
            "2",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    for name in ("First.pdf", "Second.pdf"):
        assert name in printed
    run_one_sections = printed.count(harness.COLD_FIRST_IN_PROCESS) + printed.count(
        harness.COLD_LATER_DOCUMENT
    )
    assert run_one_sections == SUITE_DOCUMENTS, (
        "each document needs its OWN run-1 section, reported apart from its "
        "warm percentiles. One shared row would attribute a cost to whichever "
        f"document happened to be printed beside it. Got {run_one_sections}."
    )
    assert printed.count(harness.COLD_FIRST_IN_PROCESS) == 1, (
        "and exactly one of them is the process's genuinely cold run"
    )
    first = printed.index("First.pdf")
    second = printed.index("Second.pdf")
    assert first < second, "the suite must report documents in the order given"


def test_main_accepts_one_run_count_per_document(
    two_document_tree: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An 880-page statute and a 1-page notification cannot honestly share a
    run count: 22 runs of the statute is hours. Per-document run counts are how
    the big document gets measured at all — and the count is printed per
    document, so a small sample can never pass as a large one.
    """
    code = harness.main(
        [
            "--manifest",
            str(two_document_tree),
            "--document",
            "First.pdf",
            "--document",
            "Second.pdf",
            "--runs",
            "3",
            "--runs",
            "2",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "runs" in printed
    assert printed.count("every run, kept") == SUITE_DOCUMENTS


def test_main_refuses_a_run_count_list_that_matches_no_document(
    two_document_tree: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Three counts for two documents has no correct pairing, and silently
    dropping the third would mean a document was measured at a count nobody
    asked for."""
    code = harness.main(
        [
            "--manifest",
            str(two_document_tree),
            "--document",
            "First.pdf",
            "--document",
            "Second.pdf",
            "--runs",
            "2",
            "--runs",
            "2",
            "--runs",
            "2",
        ]
    )
    assert code != 0
    printed = capsys.readouterr()
    assert "--runs" in printed.out + printed.err


def test_main_refuses_the_same_document_twice(
    two_document_tree: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two rows with one name is exactly the shape that makes a suite's
    per-document attribution meaningless."""
    code = harness.main(
        [
            "--manifest",
            str(two_document_tree),
            "--document",
            "First.pdf",
            "--document",
            "First.pdf",
            "--runs",
            "2",
        ]
    )
    assert code != 0
    printed = capsys.readouterr()
    assert "First.pdf" in printed.out + printed.err


# ── the settings are the repository's own, not new numbers ───────────────


def test_the_benchmark_settings_are_complete_and_named() -> None:
    """`PipelineSettings` and `CleanerSettings` both refuse an incomplete
    construction, so the harness cannot run on a half-specified configuration.
    This pins that the harness's own declared settings are exactly those two
    real objects, so every number it passes to a sub-engine is one that object
    already validated.
    """
    assert isinstance(harness.SETTINGS, pipeline.PipelineSettings)
    assert isinstance(harness.SETTINGS.cleaner_settings, cleaner.CleanerSettings)
    assert harness.SETTINGS.render_dpi > 0
    assert harness.SETTINGS.vision_fallback_threshold == Decimal("0")
    assert harness.SETTINGS.table_structure is None, (
        "parser.parse's own default is None — 'do not run the table detector'. "
        "Choosing anything else here would be this harness inventing a setting."
    )
