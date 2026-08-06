"""The shard runner, and the five ways it could turn "no result" into a score.

WHAT IS BEING GUARDED. `tools/ci/mutation_shard_runner.py` runs one immutable
shard and writes one durable terminal result per mutant. Five failures would
make it worse than nothing, and every one is ATTACKED here rather than reasoned
about:

    a mutant that hangs is called `killed`      -> a kill nobody earned
    a mutant the copy never registered is
      called `survived`                         -> a fabricated survivor
    a worker dies and its shard's work
      disappears with it                        -> 2893 results lost, again
    a crashed or cancelled shard reads as
      finished                                  -> unattempted mutants, silently passed
    a result is retried until it is nicer       -> the answer chosen, not measured

THE ORACLE IS A REAL PYTEST, IN A REAL SUBPROCESS. Every state test below builds
a mutation copy whose module genuinely dispatches on `MUTANT_UNDER_TEST` — the
same environment variable mutmut's trampoline reads — and runs the real
interpreter against it. `killed`, `survived`, `timeout` and `error` are each
produced by a mutant that really behaves that way, not by a stubbed exit code.
`cancelled` is produced by really signalling a really running worker.

The ONLY faked thing is `AttemptRunner`, the single call that starts a process
(CLAUDE.md J.7). It is faked exclusively where the subject is the RETRY POLICY,
which is arithmetic over attempt outcomes and has no process in it.

THE ATTACK THAT MATTERS MOST. `test_an_unregistered_mutant_would_be_a_survivor_
without_the_guard` runs the invented name through the raw attempt path first and
shows pytest exiting 0 — the trampoline calling the ORIGINAL function, exactly
as `mutation_denominator`'s docstring records — and only then shows the runner
refusing it. A guard proven only in the direction it passes is not proven.

IT NEVER SKIPS. If a subprocess cannot start, this file fails. A skip here would
be the silent exclusion the whole pipeline exists to end.
"""

from __future__ import annotations

import json
import runpy
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import mutation_shard_runner as sr
import pytest
from authored_source import running_path
from mutation_denominator import MutationResultsUnavailableError

# ── the mutation copy the real runs execute against ──────────────────────────

#: A module that dispatches on `MUTANT_UNDER_TEST` the way mutmut's generated
#: trampoline does, and registers its mutants the way a generated file does —
#: `mutants_<mangled>['<name>'] = <name>`, the exact shape
#: `mutation_denominator._REGISTRATION` scans for.
#:
#: Five mutants of `x_add`, one per outcome a real subprocess can produce:
#:
#:     _1  returns a - b            the covering test fails      -> killed
#:     _2  returns b + a            the covering test passes     -> survived
#:     _3  sleeps                   never returns                -> timeout
#:     _4  raises at MODULE scope   the import fails             -> error
#:     _5  SIGKILLs its own process the interpreter dies         -> error
#:
#: `_5` uses SIGKILL rather than a null dereference on purpose: an uncatchable
#: signal is deterministic on every POSIX runner, and a segfault is not.
CALC = """\
import os
import signal
import time

MUTANT_ENV = "MUTANT_UNDER_TEST"


def _active():
    return os.environ.get(MUTANT_ENV, "").rpartition(".")[2]


# A module-scope mutant. Activating it makes `probe.calc` unimportable, which is
# what a mutated module-level statement does in a real mutation copy.
if _active() == "x_add__mutmut_4":
    raise ValueError("this mutant makes probe.calc unimportable")


def x_add__mutmut_orig(a, b):
    return a + b


def x_add__mutmut_1(a, b):
    return a - b


def x_add__mutmut_2(a, b):
    return b + a


def x_add__mutmut_3(a, b):
    time.sleep(__HANG__)
    return a + b


def x_add__mutmut_5(a, b):
    os.kill(os.getpid(), signal.SIGKILL)
    return a + b


mutants_x_add__mutmut = {}
mutants_x_add__mutmut['x_add__mutmut_1'] = x_add__mutmut_1
mutants_x_add__mutmut['x_add__mutmut_2'] = x_add__mutmut_2
mutants_x_add__mutmut['x_add__mutmut_3'] = x_add__mutmut_3
mutants_x_add__mutmut['x_add__mutmut_4'] = x_add__mutmut_orig
mutants_x_add__mutmut['x_add__mutmut_5'] = x_add__mutmut_5


def add(a, b):
    mutant = mutants_x_add__mutmut.get(_active())
    if mutant is None:
        return x_add__mutmut_orig(a, b)
    return mutant(a, b)


def x_missing__mutmut_orig():
    return 1


def x_missing__mutmut_1():
    return 2


mutants_x_missing__mutmut = {}
mutants_x_missing__mutmut['x_missing__mutmut_1'] = x_missing__mutmut_1


def x_lonely__mutmut_orig():
    return 1


def x_lonely__mutmut_1():
    return 2


mutants_x_lonely__mutmut = {}
mutants_x_lonely__mutmut['x_lonely__mutmut_1'] = x_lonely__mutmut_1
"""

TEST_CALC = """\
from probe.calc import add


def test_add():
    assert add(1, 2) == 3
"""

SOURCE = "src/probe/calc.py"
COVERING_TEST = "tests/test_calc.py::test_add"

#: mutmut's own per-test measurement, which the timing report reads rather than
#: attributing one of its own.
COVERING_TEST_SECONDS = 0.125

#: A name mutmut RECORDED but the generated file never registered — a mutation
#: copy that has drifted from the meta store beside it. Activating it runs the
#: ORIGINAL function and every test passes, so `survived` is exactly what an
#: unguarded runner would print. This is the defect under attack.
INVENTED = "probe.calc.x_add__mutmut_9999"

#: A name mutmut never recorded at all — the other direction, another refusal.
UNRECORDED = "probe.calc.x_ghost__mutmut_1"

#: Every mutant the meta store records. `x_missing__mutmut_1` is covered by a
#: test id that does not exist; `x_lonely__mutmut_1` is covered by nothing.
META_NAMES = (
    "probe.calc.x_add__mutmut_1",
    "probe.calc.x_add__mutmut_2",
    "probe.calc.x_add__mutmut_3",
    "probe.calc.x_add__mutmut_4",
    "probe.calc.x_add__mutmut_5",
    INVENTED,
    "probe.calc.x_missing__mutmut_1",
    "probe.calc.x_lonely__mutmut_1",
)

#: How long the hanging mutant sleeps. Substituted into `CALC` rather than
#: written twice, so the budgets below cannot drift from the sleep they are
#: reasoned against.
HANG_SLEEP_SECONDS = 20

#: Long enough that a real pytest start-up finishes and the sleeping mutant is
#: genuinely running when the budget expires — the timeout must be observed on a
#: HANGING TEST, not on an interpreter that had not started yet. Far shorter than
#: the sleep, so what fires is the budget and not the mutant finishing.
HANG_BUDGET_SECONDS = 3.0

#: How long a worker in the kill and cancel tests is allowed to run before it is
#: signalled. Bounded by `Popen.wait`, so NO CLOCK IS READ in this file — a test
#: that asks the machine the time behaves differently on a busy machine
#: (`test_no_test_reads_a_real_clock`).
SIGNAL_AFTER_SECONDS = 5.0

#: Generous: any of these runs that takes this long has failed at something
#: other than what it is measuring.
RESULT_BUDGET_SECONDS = 120.0

SIGKILL_NUMBER = 9
ONE_ATTEMPT = 1
TWO_ATTEMPTS = 2
THREE_ATTEMPTS = 3
ONE_THREAD = 1
THREE_THREADS = 3
#: one header line plus two records
HEADER_PLUS_TWO = 3

#: The six terminal states, spelled out as literals rather than imported from
#: the module under test. Importing them would make the assertion true by
#: construction; writing them down makes a rename fail here, which is the point.
SIX_STATES = frozenset(
    {"killed", "survived", "timeout", "error", "infrastructure_failure", "cancelled"}
)
ONLY_INFRASTRUCTURE = frozenset({"infrastructure_failure"})

#: The record's key set, stated once. A record that grows or loses a key is a
#: contract change for whatever reads the JSONL, so it is asserted, not assumed.
RECORD_KEYS = frozenset(
    {
        "id",
        "name",
        "source",
        "state",
        "exit_code",
        "signal",
        "test",
        "worker",
        "attempt",
        "duration_seconds",
        "reason",
    }
)

#: The header's key set, exactly as the aggregator was told to expect it.
HEADER_KEYS = frozenset(
    {"shard_index", "shard_count", "manifest_sha256", "commit", "dependency_lock_hash"}
)

MANIFEST_SHA = "  3F5A" + "0" * 60 + "  "
COMMIT = "0709408eaa36ffdf9dd86432a5a01bff566b1c8e"
LOCK_HASH = "sha256:9f1c"


def build_copy(tmp_path: Path) -> Path:
    """A mutation copy that really dispatches, really records, really runs."""
    root = tmp_path / "mutants"
    package = root / "src" / "probe"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calc.py").write_text(
        CALC.replace("__HANG__", str(HANG_SLEEP_SECONDS)), encoding="utf-8"
    )
    (package / "calc.py.meta").write_text(
        json.dumps({"exit_code_by_key": dict.fromkeys(META_NAMES)}), encoding="utf-8"
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(TEST_CALC, encoding="utf-8")
    (root / "mutmut-stats.json").write_text(
        # PRETTY-PRINTED, because that is how mutmut really writes it. Measured
        # on a real `mutmut run`: thirty lines, the first of which is `{`. The
        # earlier one-line fixture agreed with a bug instead of attacking it —
        # `read_test_durations` was reading this whole JSON DOCUMENT with the
        # JSONL reader meant for the RESULT files, parsed nothing, and returned
        # no durations at all without a word. `indent` is the regression test.
        json.dumps(
            {
                "tests_by_mangled_function_name": {
                    "probe.calc.x_add": [COVERING_TEST],
                    "probe.calc.x_missing": ["tests/test_calc.py::test_does_not_exist"],
                },
                "duration_by_test": {COVERING_TEST: COVERING_TEST_SECONDS},
            },
            indent=4,
        ),
        encoding="utf-8",
    )
    return root


def write_shard(tmp_path: Path, entries: Sequence[tuple[str, str]], name: str = "shard") -> Path:
    path = tmp_path / f"{name}.jsonl"
    path.write_text(
        "".join(json.dumps({"id": id_, "name": mutant}) + "\n" for id_, mutant in entries),
        encoding="utf-8",
    )
    return path


def policy(
    *,
    timeout_seconds: float = RESULT_BUDGET_SECONDS,
    max_attempts: int = ONE_ATTEMPT,
    worker: str = "worker-3",
) -> sr.Policy:
    return sr.Policy(worker=worker, max_attempts=max_attempts, timeout_seconds=timeout_seconds)


def isolation_in(tmp_path: Path, name: str = "work") -> sr.Isolation:
    made = sr.Isolation(work_dir=tmp_path / name, cpu_threads=ONE_THREAD)
    made.prepare()
    return made


def header() -> sr.Header:
    return sr.Header(
        shard_index=3,
        shard_count=16,
        manifest_sha256=MANIFEST_SHA,
        commit=COMMIT,
        dependency_lock_hash=LOCK_HASH,
    )


def argv_with(**overrides: str) -> list[str]:
    """A complete command line, so a refusal can only come from the value tested."""
    values = {
        "--shard": "s",
        "--output": "o",
        "--worker": "w",
        "--work-dir": "wd",
        "--timeout-seconds": "5",
        "--max-attempts": "1",
        "--cpu-threads": "1",
        "--shard-index": "0",
        "--shard-count": "1",
        "--manifest-sha256": MANIFEST_SHA,
        "--commit": COMMIT,
        "--dependency-lock-hash": LOCK_HASH,
    }
    values.update(overrides)
    argv = ["prog"]
    for flag, value in values.items():
        argv += [flag, value]
    return argv


def worker_argv(
    tmp_path: Path, shard: Path, output: Path, copy_dir: Path, **extra: str
) -> list[str]:
    argv = [
        sys.executable,
        str(running_path(sr)),
        "--shard",
        str(shard),
        "--output",
        str(output),
        "--worker",
        "worker-3",
        "--work-dir",
        str(tmp_path / "work"),
        "--timeout-seconds",
        str(HANG_SLEEP_SECONDS * 2),
        "--max-attempts",
        "1",
        "--cpu-threads",
        "1",
        "--shard-index",
        "3",
        "--shard-count",
        "16",
        "--manifest-sha256",
        MANIFEST_SHA,
        "--commit",
        COMMIT,
        "--dependency-lock-hash",
        LOCK_HASH,
        "--mutants-dir",
        str(copy_dir),
    ]
    for flag, value in extra.items():
        argv += [flag, value]
    return argv


def record_for(
    tmp_path: Path,
    name: str,
    *,
    timeout_seconds: float = RESULT_BUDGET_SECONDS,
    identifier: str = "M-000001",
) -> sr.Record:
    """One mutant, through the REAL path: real copy, real pytest, real result."""
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    chosen = policy(timeout_seconds=timeout_seconds)
    isolation = isolation_in(tmp_path)
    return sr.run_mutant(
        sr.ShardEntry(id=identifier, name=name),
        copy,
        chosen,
        sr.subprocess_runner(copy, chosen, isolation),
    )


def attempt(state: str, seconds: float = 0.25) -> sr.Attempt:
    return sr.Attempt(state=state, exit_code=None, signal=None, test=None, duration_seconds=seconds)


def a_record(
    identifier: str, state: str, attempts: int = ONE_ATTEMPT, reason: str = ""
) -> sr.Record:
    return sr.Record(
        id=identifier,
        name="probe.calc.x_add__mutmut_1",
        source=SOURCE,
        state=state,
        exit_code=None,
        signal=None,
        test=None,
        worker="worker-3",
        attempt=attempts,
        duration_seconds=1.0,
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE STATE SET IS THE OWNER'S, AND IT IS CLOSED.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_terminal_states_are_exactly_the_six() -> None:
    assert sr.TERMINAL_STATES == SIX_STATES


def test_unattempted_is_not_a_terminal_state() -> None:
    # It is a run-level completeness failure. Writing it into the file as though
    # it were an outcome is exactly what makes a crashed shard read as finished.
    assert sr.UNATTEMPTED == "unattempted"
    assert sr.UNATTEMPTED not in sr.TERMINAL_STATES


def test_only_infrastructure_failures_are_retryable() -> None:
    assert sr.RETRYABLE_STATES == ONLY_INFRASTRUCTURE
    assert sr.RETRYABLE_STATES < sr.TERMINAL_STATES


# ═══════════════════════════════════════════════════════════════════════════
# 2 · A TIMEOUT IS A TIMEOUT. Never killed, never survived, never dropped.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_hanging_mutant_is_recorded_as_timeout(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_3", timeout_seconds=HANG_BUDGET_SECONDS)
    assert record.state == sr.TIMEOUT, record


def test_a_hanging_mutant_is_never_scored(tmp_path: Path) -> None:
    # The whole danger, as its own assertion: 162 timeouts in the last CI run,
    # and a single one landing in `killed` inflates the score.
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_3", timeout_seconds=HANG_BUDGET_SECONDS)
    assert record.state not in (sr.KILLED, sr.SURVIVED), record


def test_a_timeout_still_produces_a_record_so_it_cannot_be_dropped(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_3", timeout_seconds=HANG_BUDGET_SECONDS)
    assert set(json.loads(record.as_json())) == RECORD_KEYS
    assert record.id == "M-000001"


def test_a_timeout_attributes_no_exit_code_and_no_signal(tmp_path: Path) -> None:
    # We killed that process, so reporting SIGKILL would attribute OUR signal to
    # the mutant. Nothing about how it ended was observed, and the record says so.
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_3", timeout_seconds=HANG_BUDGET_SECONDS)
    assert (record.exit_code, record.signal, record.test) == (None, None, None), record


def test_a_timeout_is_not_retried(tmp_path: Path) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    calls: list[str] = []

    def always_timeout(name: str, tests: Sequence[str]) -> sr.Attempt:
        calls.append(name)
        assert tuple(tests) == (COVERING_TEST,)
        return attempt(sr.TIMEOUT)

    record = sr.run_mutant(
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_3"),
        copy,
        policy(max_attempts=THREE_ATTEMPTS),
        always_timeout,
    )
    assert (record.state, record.attempt, len(calls)) == (sr.TIMEOUT, ONE_ATTEMPT, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 3 · AN UNREGISTERED MUTANT IS REFUSED, never reported as a survivor.
# ═══════════════════════════════════════════════════════════════════════════


def test_an_unregistered_mutant_would_be_a_survivor_without_the_guard(tmp_path: Path) -> None:
    # THE ATTACK, run first. The trampoline calls the ORIGINAL function for a
    # name it does not know, so the covering test passes and pytest exits 0. Any
    # runner that trusted that exit code would print a survivor that never ran.
    copy_dir = build_copy(tmp_path)
    raw = sr.run_once(
        INVENTED, [COVERING_TEST], copy_dir, RESULT_BUDGET_SECONDS, isolation_in(tmp_path)
    )
    assert (raw.exit_code, raw.state) == (0, sr.SURVIVED), raw


def test_an_unregistered_mutant_is_refused(tmp_path: Path) -> None:
    record = record_for(tmp_path, INVENTED)
    assert record.state == sr.INFRASTRUCTURE_FAILURE, record
    assert record.state != sr.SURVIVED
    assert "registers no such mutant" in record.reason, record


def test_an_unregistered_mutant_never_starts_a_process(tmp_path: Path) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    started: list[str] = []

    def never(name: str, tests: Sequence[str]) -> sr.Attempt:
        started.append(name)
        raise AssertionError(f"a process was started for {name} with {list(tests)}")

    record = sr.run_mutant(sr.ShardEntry(id="M-1", name=INVENTED), copy, policy(), never)
    assert started == []
    assert record.exit_code is None and record.signal is None, record


def test_a_mutant_mutmut_never_recorded_is_refused(tmp_path: Path) -> None:
    record = record_for(tmp_path, UNRECORDED)
    assert record.state == sr.INFRASTRUCTURE_FAILURE, record
    assert "no such mutant" in record.reason, record
    assert record.source == "", record


def test_a_mutant_with_no_covering_test_is_refused_not_survived(tmp_path: Path) -> None:
    # No test ran, so nothing passed. "Nothing failed" is not a survivor.
    record = record_for(tmp_path, "probe.calc.x_lonely__mutmut_1")
    assert record.state == sr.INFRASTRUCTURE_FAILURE, record
    assert record.state != sr.SURVIVED
    assert "no test" in record.reason, record


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE RESULTS SURVIVE THE WORKER DYING, AND THE REST STAY UNATTEMPTED.
# ═══════════════════════════════════════════════════════════════════════════


def test_results_written_before_a_sigkill_are_intact_and_readable(tmp_path: Path) -> None:
    # The measured failure this exists for: 2893 of 4429 mutants reached, then
    # the run was terminated and every one of those results went with it.
    copy_dir = build_copy(tmp_path)
    shard = write_shard(
        tmp_path,
        [
            ("M-1", INVENTED),
            ("M-2", "probe.calc.x_add__mutmut_1"),
            ("M-3", "probe.calc.x_add__mutmut_3"),
        ],
    )
    output = tmp_path / "results.jsonl"
    worker = subprocess.Popen(  # noqa: S603 - argv list, no shell, interpreter is sys.executable
        worker_argv(tmp_path, shard, output, copy_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # NO CLOCK IS READ HERE and no loop polls a file. `wait` bounds itself, and
    # the shard is ordered so the outcome cannot depend on machine speed: M-1 is
    # refused without starting a process, so its record lands almost at once,
    # while M-3 sleeps and its budget is twice that sleep — so the worker is
    # still inside M-3 when it is killed, on any machine that runs at all.
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            worker.wait(timeout=SIGNAL_AFTER_SECONDS)
        worker.kill()
    finally:
        worker.wait(timeout=RESULT_BUDGET_SECONDS)

    lines = output.read_text(encoding="utf-8").splitlines()
    head, records = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
    assert set(head) == HEADER_KEYS, head
    assert records, "nothing was flushed before the kill; the work was lost"
    assert records[0]["id"] == "M-1"
    assert all(set(record) == RECORD_KEYS for record in records), records
    assert all(record["state"] in sr.TERMINAL_STATES for record in records), records
    assert "M-3" not in {record["id"] for record in records}, records


def test_a_killed_worker_leaves_its_remaining_mutants_unattempted(tmp_path: Path) -> None:
    # ACCEPTANCE: a worker crash leaves its mutants UNRESOLVED, never silently
    # passed. `completeness` reads the disk and names them.
    output = tmp_path / "results.jsonl"
    output.write_text(
        header().as_json() + "\n" + a_record("M-1", sr.KILLED).as_json() + "\n", encoding="utf-8"
    )
    entries = (
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-2", name="probe.calc.x_add__mutmut_2"),
    )
    lines, code = sr.completeness(entries, output)
    text = "\n".join(lines)
    assert code == 1, text
    assert "INCOMPLETE RUN" in text, text
    assert "unattempted: M-2" in text, text


def test_each_record_is_on_disk_before_the_next_mutant_starts(tmp_path: Path) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    output = tmp_path / "results.jsonl"
    seen: list[list[str]] = []

    def observe(name: str, tests: Sequence[str]) -> sr.Attempt:
        assert name.startswith("probe.calc.") and tuple(tests) == (COVERING_TEST,)
        text = output.read_text(encoding="utf-8") if output.is_file() else ""
        seen.append(text.splitlines())
        return sr.Attempt(
            state=sr.KILLED, exit_code=1, signal=None, test=COVERING_TEST, duration_seconds=0.1
        )

    entries = (
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-2", name="probe.calc.x_add__mutmut_2"),
        sr.ShardEntry(id="M-3", name="probe.calc.x_add__mutmut_5"),
    )
    with sr.record_sink(output, header()) as sink:
        sr.run_shard(entries, copy, policy(), observe, sr.Reporting(sink=sink))

    # The header is line one from the very first write, so every count includes it.
    assert [len(lines) for lines in seen] == [1, 2, 3], seen
    assert [json.loads(line)["id"] for line in seen[2][1:]] == ["M-1", "M-2"]


def test_the_sink_appends_rather_than_truncating(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-1", sr.KILLED))
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-2", sr.SURVIVED))
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == HEADER_PLUS_TWO, lines
    assert [json.loads(line)["id"] for line in lines[1:]] == ["M-1", "M-2"]


def test_a_resumed_worker_does_not_write_a_second_header(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-1", sr.KILLED))
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-2", sr.SURVIVED))
    lines = output.read_text(encoding="utf-8").splitlines()
    assert sr.HEADER_FIELDS[0] in lines[0]
    assert all(sr.HEADER_FIELDS[0] not in line for line in lines[1:]), lines


# ═══════════════════════════════════════════════════════════════════════════
# 5 · CANCELLATION. A stopped shard is an INCOMPLETE run, not a short one.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_cancelled_attempt_becomes_a_cancelled_record_and_stops_the_shard(
    tmp_path: Path,
) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    output = tmp_path / "results.jsonl"
    seen: list[str] = []

    def stop_on_the_second(name: str, tests: Sequence[str]) -> sr.Attempt:
        assert tuple(tests) == (COVERING_TEST,)
        seen.append(name)
        if len(seen) == TWO_ATTEMPTS:
            raise sr.ShardCancelled("signal 15 received")
        return attempt(sr.KILLED)

    entries = (
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-2", name="probe.calc.x_add__mutmut_2"),
        sr.ShardEntry(id="M-3", name="probe.calc.x_add__mutmut_5"),
    )
    with sr.record_sink(output, header()) as sink:
        records = sr.run_shard(entries, copy, policy(), stop_on_the_second, sr.Reporting(sink=sink))

    assert [record.state for record in records] == [sr.KILLED, sr.CANCELLED]
    assert "signal 15" in records[1].reason
    lines, code = sr.completeness(entries, output)
    assert code == 1
    assert "unattempted: M-3" in "\n".join(lines)


def test_cancellation_never_runs_the_mutants_after_it(tmp_path: Path) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    seen: list[str] = []

    def stop_at_once(name: str, tests: Sequence[str]) -> sr.Attempt:
        assert tests
        seen.append(name)
        raise sr.ShardCancelled("stopped")

    entries = tuple(
        sr.ShardEntry(id=f"M-{index}", name="probe.calc.x_add__mutmut_1") for index in (1, 2, 3)
    )
    with sr.record_sink(tmp_path / "r.jsonl", header()) as sink:
        records = sr.run_shard(entries, copy, policy(), stop_at_once, sr.Reporting(sink=sink))
    assert len(seen) == 1, seen
    assert [record.id for record in records] == ["M-1"]


def test_the_signal_handler_turns_a_stop_request_into_a_cancellation() -> None:
    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(sr.ShardCancelled), sr.cancel_on_signals():
        signal.raise_signal(signal.SIGTERM)
    assert signal.getsignal(signal.SIGTERM) is previous, "the handler was not restored"


def test_a_real_sigterm_cancels_a_running_worker_and_the_run_is_incomplete(
    tmp_path: Path,
) -> None:
    # ACCEPTANCE: a cancelled shard produces an incomplete run. Real worker, real
    # signal, real pytest child — nothing here is simulated.
    copy_dir = build_copy(tmp_path)
    shard = write_shard(
        tmp_path,
        [
            ("M-1", INVENTED),
            ("M-2", "probe.calc.x_add__mutmut_3"),
            ("M-3", "probe.calc.x_add__mutmut_1"),
        ],
    )
    output = tmp_path / "results.jsonl"
    worker = subprocess.Popen(  # noqa: S603 - argv list, no shell, interpreter is sys.executable
        worker_argv(tmp_path, shard, output, copy_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            worker.wait(timeout=SIGNAL_AFTER_SECONDS)
        worker.terminate()
        stdout, _ = worker.communicate(timeout=RESULT_BUDGET_SECONDS)
    finally:
        worker.kill()

    assert worker.returncode == 1, stdout
    assert "INCOMPLETE RUN" in stdout, stdout
    assert "unattempted: M-3" in stdout, stdout
    states = sr.recorded_states(output)
    assert states["M-2"] == sr.CANCELLED, states
    assert "M-3" not in states, states


# ═══════════════════════════════════════════════════════════════════════════
# 6 · RETRY IS FOR INFRASTRUCTURE, AND IT REPLACES RATHER THAN DUPLICATES.
# ═══════════════════════════════════════════════════════════════════════════


def scripted(outcomes: Sequence[sr.Attempt], calls: list[str]) -> sr.AttemptRunner:
    """An attempt runner handing back `outcomes` in order, then repeating the last."""

    def run(name: str, tests: Sequence[str]) -> sr.Attempt:
        assert tuple(tests) == (COVERING_TEST,)
        calls.append(name)
        return outcomes[min(len(calls) - 1, len(outcomes) - 1)]

    return run


def run_with(
    tmp_path: Path, outcomes: Sequence[sr.Attempt], max_attempts: int
) -> tuple[sr.Record, list[str]]:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    calls: list[str] = []
    record = sr.run_mutant(
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        copy,
        policy(max_attempts=max_attempts),
        scripted(outcomes, calls),
    )
    return record, calls


def test_an_infrastructure_failure_is_retried_up_to_the_bound(tmp_path: Path) -> None:
    record, calls = run_with(
        tmp_path,
        [
            attempt(sr.INFRASTRUCTURE_FAILURE),
            attempt(sr.INFRASTRUCTURE_FAILURE),
            attempt(sr.SURVIVED),
        ],
        THREE_ATTEMPTS,
    )
    assert (record.state, record.attempt, len(calls)) == (sr.SURVIVED, THREE_ATTEMPTS, 3)


def test_retries_stop_at_the_bound_and_the_failure_is_reported(tmp_path: Path) -> None:
    record, calls = run_with(tmp_path, [attempt(sr.INFRASTRUCTURE_FAILURE)], TWO_ATTEMPTS)
    assert record.state == sr.INFRASTRUCTURE_FAILURE
    assert (record.attempt, len(calls)) == (TWO_ATTEMPTS, 2)


@pytest.mark.parametrize("state", ["killed", "survived", "timeout", "error", "cancelled"])
def test_a_result_is_never_retried(tmp_path: Path, state: str) -> None:
    # A survivor re-run until it dies is a kill that was chosen, not measured.
    record, calls = run_with(tmp_path, [attempt(state)], THREE_ATTEMPTS)
    assert (record.state, record.attempt, len(calls)) == (state, ONE_ATTEMPT, 1)


def test_the_recorded_duration_covers_every_attempt(tmp_path: Path) -> None:
    record, _ = run_with(
        tmp_path, [attempt(sr.INFRASTRUCTURE_FAILURE), attempt(sr.KILLED)], TWO_ATTEMPTS
    )
    # 0.25 per attempt, twice. A record reporting only the last attempt would
    # under-report what the shard actually spent.
    assert record.duration_seconds == pytest.approx(0.5), record


def test_retrying_one_mutant_replaces_its_result_rather_than_duplicating_it(
    tmp_path: Path,
) -> None:
    # ACCEPTANCE: a retry REPLACES the same mutant result. The file is append
    # only, so "replace" means the LAST record for an id is its result — and
    # `recorded_states` is the one place that rule lives.
    output = tmp_path / "results.jsonl"
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-1", sr.INFRASTRUCTURE_FAILURE))
        sink(a_record("M-2", sr.SURVIVED))
        sink(a_record("M-1", sr.KILLED))
    states = sr.recorded_states(output)
    assert states == {"M-1": sr.KILLED, "M-2": sr.SURVIVED}
    assert len(states) == TWO_ATTEMPTS, "one logical result per mutant, not one per write"


def test_only_reruns_exactly_the_named_mutants() -> None:
    entries = (
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-2", name="probe.calc.x_add__mutmut_2"),
        sr.ShardEntry(id="M-3", name="probe.calc.x_add__mutmut_5"),
    )
    done = {"M-1": sr.KILLED, "M-2": sr.INFRASTRUCTURE_FAILURE, "M-3": sr.SURVIVED}
    chosen = sr.still_to_run(entries, done, ["M-2"])
    assert [entry.id for entry in chosen] == ["M-2"], chosen


def test_only_cannot_smuggle_in_a_mutant_this_shard_does_not_own(tmp_path: Path) -> None:
    entries = (sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),)
    assert sr.still_to_run(entries, {}, ["M-999"]) == ()
    assert tmp_path.is_dir()


def test_without_only_a_resumed_worker_skips_what_the_disk_already_has() -> None:
    entries = (
        sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-2", name="probe.calc.x_add__mutmut_2"),
    )
    chosen = sr.still_to_run(entries, {"M-1": sr.KILLED}, [])
    assert [entry.id for entry in chosen] == ["M-2"]


# ═══════════════════════════════════════════════════════════════════════════
# 7 · EVERY STATE, PRODUCED BY A MUTANT THAT REALLY BEHAVES THAT WAY.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_mutant_its_covering_test_catches_is_killed(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_1")
    assert (record.state, record.exit_code, record.signal) == (sr.KILLED, 1, None), record
    assert (record.name, record.source) == ("probe.calc.x_add__mutmut_1", SOURCE), record


def test_a_killed_record_names_the_test_that_killed_it(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_1")
    assert record.test == COVERING_TEST, record


def test_an_equivalent_mutant_is_survived(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_2")
    assert (record.state, record.exit_code, record.test) == (sr.SURVIVED, 0, None), record


def test_a_mutant_that_breaks_the_import_is_an_error(tmp_path: Path) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_4")
    assert record.state == sr.ERROR, record
    assert record.state not in (sr.KILLED, sr.SURVIVED)
    # The owner's set has one `error`, so the two failures it covers are told
    # apart in words rather than smuggled in as a seventh state.
    assert "broke the import" in record.reason, record


def test_a_mutant_that_kills_the_interpreter_is_an_error_naming_the_signal(
    tmp_path: Path,
) -> None:
    record = record_for(tmp_path, "probe.calc.x_add__mutmut_5")
    assert record.state == sr.ERROR, record
    assert (record.exit_code, record.signal) == (None, SIGKILL_NUMBER), record
    assert "runtime failure" in record.reason, record
    assert signal.SIGKILL == SIGKILL_NUMBER


def test_a_covering_test_that_does_not_exist_is_an_infrastructure_failure(
    tmp_path: Path,
) -> None:
    # pytest exits 4 for BOTH a broken import and a test id it cannot find, so
    # the exit code alone cannot tell them apart. Measured: the import failure
    # prints `ERROR <file> - <exception>` on STDOUT; the missing target prints
    # `ERROR: not found:` on STDERR and `no tests ran` on stdout. Both directions
    # are asserted — this one, and `..._breaks_the_import_...` above.
    record = record_for(tmp_path, "probe.calc.x_missing__mutmut_1")
    assert record.state == sr.INFRASTRUCTURE_FAILURE, record


# ═══════════════════════════════════════════════════════════════════════════
# 8 · EXIT-CODE CLASSIFICATION, INCLUDING THE CODES NOBODY DEFINED.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("returncode", "collection_error", "expected"),
    [
        (0, False, (sr.SURVIVED, 0, None)),
        (1, False, (sr.KILLED, 1, None)),
        (2, True, (sr.ERROR, 2, None)),
        (2, False, (sr.INFRASTRUCTURE_FAILURE, 2, None)),
        (3, False, (sr.INFRASTRUCTURE_FAILURE, 3, None)),
        (4, True, (sr.ERROR, 4, None)),
        (4, False, (sr.INFRASTRUCTURE_FAILURE, 4, None)),
        (5, False, (sr.INFRASTRUCTURE_FAILURE, 5, None)),
        (-11, False, (sr.ERROR, None, 11)),
        (-9, False, (sr.ERROR, None, 9)),
        (137, False, (sr.ERROR, 137, None)),
    ],
)
def test_exit_codes_classify_the_way_they_were_measured(
    returncode: int, collection_error: bool, expected: tuple[str, int | None, int | None]
) -> None:
    assert sr.state_from_exit(returncode, collection_error=collection_error) == expected


def test_a_code_nobody_defined_never_becomes_a_result() -> None:
    for returncode in (6, 42, 255):
        state, _, _ = sr.state_from_exit(returncode, collection_error=False)
        assert state not in (sr.KILLED, sr.SURVIVED), returncode


def test_the_failing_test_is_read_off_pytests_own_summary() -> None:
    stdout = (
        "=== FAILURES ===\n"
        "=== short test summary info ===\n"
        "FAILED tests/test_parser.py::test_round_trip - assert 3 == 4\n"
        "1 failed in 0.02s\n"
    )
    assert sr.failing_test(stdout) == "tests/test_parser.py::test_round_trip"
    assert sr.had_collection_error(stdout) is False


def test_a_collection_error_is_seen_and_carries_no_failing_test() -> None:
    stdout = (
        "=== ERRORS ===\nERROR tests/test_calc.py - ValueError: unimportable\n1 error in 0.0s\n"
    )
    assert sr.had_collection_error(stdout) is True
    assert sr.failing_test(stdout) is None


def test_a_clean_run_reports_neither() -> None:
    assert sr.failing_test("1 passed in 0.01s\n") is None
    assert sr.had_collection_error("1 passed in 0.01s\n") is False


# ═══════════════════════════════════════════════════════════════════════════
# 9 · ISOLATION. Sixteen workers, one shared tree, zero collisions.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_worker_gets_its_own_temporary_pycache_and_basetemp(tmp_path: Path) -> None:
    isolation = isolation_in(tmp_path, "w1")
    other = isolation_in(tmp_path, "w2")
    assert isolation.temporary.is_dir() and isolation.pycache.is_dir()
    assert isolation.temporary != other.temporary
    assert isolation.pycache != other.pycache
    assert isolation.basetemp != other.basetemp


def test_the_child_environment_redirects_every_shared_location(tmp_path: Path) -> None:
    environment = isolation_in(tmp_path).environment()
    work = str(tmp_path / "work")
    for name in ("TMPDIR", "TEMP", "TMP", "PYTHONPYCACHEPREFIX"):
        assert environment[name].startswith(work), (name, environment[name])


def test_the_thread_budget_is_the_one_the_caller_stated(tmp_path: Path) -> None:
    environment = sr.Isolation(work_dir=tmp_path / "w", cpu_threads=THREE_THREADS).environment()
    assert {environment[name] for name in sr.THREAD_BUDGET_VARIABLES} == {str(THREE_THREADS)}
    assert environment["TOKENIZERS_PARALLELISM"] == "false"


def test_pytest_is_told_not_to_write_into_the_shared_tree(tmp_path: Path) -> None:
    arguments = isolation_in(tmp_path).pytest_arguments()
    assert "--basetemp" in arguments
    assert arguments[arguments.index("--basetemp") + 1].startswith(str(tmp_path))
    assert arguments[-2:] == ["-p", "no:cacheprovider"], arguments


def test_a_real_run_leaves_no_cache_directory_inside_the_mutation_copy(tmp_path: Path) -> None:
    # The FS-collision guard, measured rather than argued. Without
    # `-p no:cacheprovider` and PYTHONPYCACHEPREFIX, sixteen workers write
    # `.pytest_cache` and `__pycache__` into the one tree they all share.
    copy_dir = build_copy(tmp_path)
    result = sr.run_once(
        "probe.calc.x_add__mutmut_1",
        [COVERING_TEST],
        copy_dir,
        RESULT_BUDGET_SECONDS,
        isolation_in(tmp_path),
    )
    assert result.state == sr.KILLED, result
    polluted = [str(path.relative_to(copy_dir)) for path in copy_dir.rglob("__pycache__")]
    polluted += [str(path.relative_to(copy_dir)) for path in copy_dir.rglob(".pytest_cache")]
    assert polluted == [], polluted


def test_two_workers_run_the_same_copy_in_parallel_without_colliding(tmp_path: Path) -> None:
    # THE PILOT, deterministic and small: two shards of one mutation copy, run at
    # the same time, each with its own work directory. Both must finish complete,
    # agree on the manifest, and leave the shared tree clean.
    copy_dir = build_copy(tmp_path)
    shards = [
        write_shard(tmp_path, [("M-1", "probe.calc.x_add__mutmut_1")], "shard-0"),
        write_shard(tmp_path, [("M-2", "probe.calc.x_add__mutmut_2")], "shard-1"),
    ]
    outputs = [tmp_path / "out-0.jsonl", tmp_path / "out-1.jsonl"]
    workers = []
    for index, (shard, output) in enumerate(zip(shards, outputs, strict=True)):
        argv = worker_argv(tmp_path, shard, output, copy_dir)
        argv[argv.index("--work-dir") + 1] = str(tmp_path / f"work-{index}")
        argv[argv.index("--shard-index") + 1] = str(index)
        argv[argv.index("--shard-count") + 1] = "2"
        workers.append(
            subprocess.Popen(  # noqa: S603 - argv list, no shell, interpreter is sys.executable
                argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
        )
    finished = [worker.communicate(timeout=RESULT_BUDGET_SECONDS) for worker in workers]

    assert [worker.returncode for worker in workers] == [0, 0], finished
    headers = [json.loads(output.read_text(encoding="utf-8").splitlines()[0]) for output in outputs]
    assert {head["manifest_sha256"] for head in headers} == {MANIFEST_SHA}
    assert [head["shard_index"] for head in headers] == [0, 1]
    assert sr.recorded_states(outputs[0]) == {"M-1": sr.KILLED}
    assert sr.recorded_states(outputs[1]) == {"M-2": sr.SURVIVED}
    assert list(copy_dir.rglob(".pytest_cache")) == []


# ═══════════════════════════════════════════════════════════════════════════
# 10 · THE HEADER, AND THE SHARD FILE AS UNTRUSTED INPUT.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_header_carries_exactly_the_five_agreed_fields() -> None:
    loaded = json.loads(header().as_json())
    assert set(loaded) == HEADER_KEYS
    assert (loaded["shard_index"], loaded["shard_count"]) == (3, 16)


def test_the_manifest_hash_is_echoed_unmodified() -> None:
    # The aggregator refuses to combine shards whose manifest hashes disagree.
    # Trimming or lower-casing it here would silently defeat that one check.
    loaded = json.loads(header().as_json())
    assert loaded["manifest_sha256"] == MANIFEST_SHA
    assert loaded["manifest_sha256"] != MANIFEST_SHA.strip()


def test_the_command_line_echoes_the_hash_it_was_handed() -> None:
    options = sr.parse_argv(argv_with())
    assert options.header.manifest_sha256 == MANIFEST_SHA
    assert options.header.commit == COMMIT
    assert options.header.dependency_lock_hash == LOCK_HASH


def test_resuming_into_a_file_written_by_a_different_run_is_refused(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    other = sr.Header(
        shard_index=3,
        shard_count=16,
        manifest_sha256="a different manifest",
        commit=COMMIT,
        dependency_lock_hash=LOCK_HASH,
    )
    with sr.record_sink(output, other) as sink:
        sink(a_record("M-1", sr.KILLED))
    with pytest.raises(sr.ShardUnreadableError, match="different header"):
        sr.check_resumable(output, header())


def test_resuming_into_this_runs_own_file_is_allowed(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-1", sr.KILLED))
    sr.check_resumable(output, header())
    assert sr.existing_header(output) == header()


def test_a_file_with_no_header_yet_resumes_without_complaint(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    assert sr.existing_header(output) is None
    sr.check_resumable(output, header())
    output.write_text('{"id": "M-1", "state": "killed"}\n', encoding="utf-8")
    assert sr.existing_header(output) is None


def test_a_shard_reads_id_and_name_and_ignores_the_manifest_owners_extras(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shard.jsonl"
    path.write_text(
        '{"id": "M-004201", "name": "probe.calc.x_add__mutmut_1", "shard": 3, "op": "x"}\n'
        "\n"
        '{"id": "M-004202", "name": "probe.calc.x_add__mutmut_2"}\n',
        encoding="utf-8",
    )
    assert sr.read_shard(path) == (
        sr.ShardEntry(id="M-004201", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-004202", name="probe.calc.x_add__mutmut_2"),
    )


@pytest.mark.parametrize(
    ("body", "complaint"),
    [
        ("not json at all\n", "is not valid JSON"),
        ("[1, 2]\n", "is not a JSON object"),
        ('{"name": "probe.calc.x_add__mutmut_1"}\n', "id"),
        ('{"id": "M-1"}\n', "name"),
        ('{"id": "", "name": "probe.calc.x_add__mutmut_1"}\n', "id"),
        ('{"id": "M-1", "name": 7}\n', "name"),
        ('{"id": "M-1", "name": "   "}\n', "name"),
    ],
)
def test_a_malformed_shard_line_is_refused_by_line_number(
    tmp_path: Path, body: str, complaint: str
) -> None:
    path = tmp_path / "shard.jsonl"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(sr.ShardUnreadableError, match=complaint):
        sr.read_shard(path)


def test_an_empty_shard_is_refused_rather_than_reported_as_finished(tmp_path: Path) -> None:
    path = tmp_path / "shard.jsonl"
    path.write_text("\n\n", encoding="utf-8")
    with pytest.raises(sr.ShardUnreadableError, match="no mutants"):
        sr.read_shard(path)


def test_a_missing_shard_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(sr.ShardUnreadableError, match="could not be read"):
        sr.read_shard(tmp_path / "absent.jsonl")


# ═══════════════════════════════════════════════════════════════════════════
# 11 · COMPLETENESS, READ BACK OFF THE DISK.
# ═══════════════════════════════════════════════════════════════════════════


def test_states_are_read_back_off_the_disk_not_remembered(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    # The third line is a write torn in half by a kill. It contributes no id,
    # which is correct: that mutant has no durable record.
    output.write_text(
        '{"id": "M-1", "state": "killed"}\n'
        "\n"
        '{"id": "M-2", "state": "surv\n'
        "[1, 2]\n"
        '{"state": "killed"}\n'
        '{"id": 7, "state": "killed"}\n'
        '{"id": "M-3", "state": "timeout"}\n',
        encoding="utf-8",
    )
    assert sr.recorded_states(output) == {"M-1": "killed", "M-3": "timeout"}
    assert sr.recorded_states(tmp_path / "absent.jsonl") == {}


def test_a_shard_whose_records_all_reached_the_disk_is_complete(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    with sr.record_sink(output, header()) as sink:
        sink(a_record("M-1", sr.KILLED))
    entries = (sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),)
    lines, code = sr.completeness(entries, output)
    assert code == 0
    assert "every one of 1 mutants" in "\n".join(lines)


def test_a_state_outside_the_closed_set_blocks_even_when_nothing_is_missing(
    tmp_path: Path,
) -> None:
    # `no_verdict` is the exact word the old pipeline used, and it is not one of
    # the six. A defensive branch nothing can execute is a branch nobody has
    # ever seen work, so it is reachable and exercised here.
    output = tmp_path / "results.jsonl"
    output.write_text('{"id": "M-1", "state": "no_verdict"}\n', encoding="utf-8")
    entries = (sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),)
    lines, code = sr.completeness(entries, output)
    text = "\n".join(lines)
    assert code == 1
    assert "no_verdict" in text, text


def test_completeness_does_not_take_the_runners_word_for_it(tmp_path: Path) -> None:
    # FOUND BY ATTACKING THIS FILE: an earlier version asked the in-memory
    # record list instead of the disk, and every completeness test stayed green
    # because none of them held a record the runner believed in and the disk did
    # not. A shard is complete when the bytes are there — after a kill, memory is
    # the one thing gone.
    output = tmp_path / "results.jsonl"
    output.write_text("", encoding="utf-8")
    entries = (sr.ShardEntry(id="M-1", name="probe.calc.x_add__mutmut_1"),)
    lines, code = sr.completeness(entries, output)
    assert code == 1
    assert "unattempted: M-1" in "\n".join(lines)


def test_unattempted_names_every_mutant_with_no_record() -> None:
    entries = tuple(
        sr.ShardEntry(id=f"M-{index}", name="probe.calc.x_add__mutmut_1") for index in (1, 2, 3)
    )
    assert sr.unattempted(entries, {"M-2": sr.KILLED}) == ("M-1", "M-3")


# ═══════════════════════════════════════════════════════════════════════════
# 12 · REPORTING: per mutant, per shard, and the one breakdown that cannot exist.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_summary_counts_states_and_names_every_retry() -> None:
    lines = sr.summary(
        [
            a_record("M-1", sr.KILLED),
            a_record("M-2", sr.SURVIVED),
            a_record("M-3", sr.TIMEOUT),
            a_record("M-4", sr.INFRASTRUCTURE_FAILURE, TWO_ATTEMPTS, "the runner could not start"),
        ],
        elapsed_seconds=12.5,
    )
    text = "\n".join(lines)
    assert "reached a result         2" in text, text
    assert "NO RESULT                2" in text, text
    assert "shard wall time          12.500s" in text, text
    assert "M-4 took 2 attempts: the runner could not start" in text, text


def test_the_timing_report_ranks_mutants_files_and_mutmuts_own_test_durations(
    tmp_path: Path,
) -> None:
    copy_dir = build_copy(tmp_path)
    durations = sr.read_test_durations(copy_dir)
    assert durations == {COVERING_TEST: COVERING_TEST_SECONDS}
    text = "\n".join(sr.timing_report([a_record("M-1", sr.KILLED)], durations))
    assert "SLOWEST MUTANTS" in text
    assert "M-1 probe.calc.x_add__mutmut_1" in text
    assert "SLOWEST FILES" in text and SOURCE in text
    assert COVERING_TEST in text


def test_the_operator_breakdown_is_reported_unavailable_rather_than_invented() -> None:
    # Measured against mutmut 3.x: a mutant is named `...__mutmut_<index>` and
    # the `.meta` store holds `exit_code_by_key` and `hash_by_function_name`.
    # Neither records an operator, so a ranking would be a guess (Law 24).
    text = "\n".join(sr.timing_report([a_record("M-1", sr.KILLED)], {}))
    assert "SLOWEST OPERATORS: UNAVAILABLE" in text, text
    assert "by INDEX, not by" in text, text


def test_the_stats_file_is_read_as_one_document_not_as_json_lines(tmp_path: Path) -> None:
    # PERMANENT REGRESSION TEST (Law 3). Found by the pilot, not by this file:
    # `mutmut-stats.json` is a whole JSON document written across thirty lines,
    # and reading it line by line parses nothing and returns nothing — silently.
    # The class, named so it cannot recur: a JSONL reader pointed at a document
    # fails EMPTY rather than loud, so the fixture must be written the way the
    # real tool writes it, never the way the reader happens to like.
    copy_dir = build_copy(tmp_path)
    raw = (copy_dir / "mutmut-stats.json").read_text(encoding="utf-8")
    assert raw.splitlines()[0] == "{", "the fixture stopped resembling mutmut's own output"
    assert len(raw.splitlines()) > ONE_ATTEMPT, raw
    assert sr.read_test_durations(copy_dir) == {COVERING_TEST: COVERING_TEST_SECONDS}


def test_a_missing_stats_file_yields_no_durations_rather_than_a_guess(tmp_path: Path) -> None:
    assert sr.read_test_durations(tmp_path) == {}
    (tmp_path / "mutmut-stats.json").write_text('{"tests_by_mangled_function_name": {}}\n')
    assert sr.read_test_durations(tmp_path) == {}
    text = "\n".join(sr.timing_report([], sr.read_test_durations(tmp_path)))
    assert "(no test durations recorded)" in text, text


def test_progress_is_reported_by_mutant_id_not_only_by_count(tmp_path: Path) -> None:
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    seen: list[str] = []

    def killed(name: str, tests: Sequence[str]) -> sr.Attempt:
        assert name and tests
        return sr.Attempt(
            state=sr.KILLED, exit_code=1, signal=None, test=COVERING_TEST, duration_seconds=0.5
        )

    entries = (
        sr.ShardEntry(id="M-004201", name="probe.calc.x_add__mutmut_1"),
        sr.ShardEntry(id="M-004202", name="probe.calc.x_add__mutmut_2"),
    )
    with sr.record_sink(tmp_path / "r.jsonl", header()) as sink:
        sr.run_shard(entries, copy, policy(), killed, sr.Reporting(sink=sink, progress=seen.append))

    assert len(seen) == TWO_ATTEMPTS
    assert seen[0].startswith("[1/2] M-004201 probe.calc.x_add__mutmut_1 -> killed"), seen
    assert "M-004202" in seen[1], seen


# ═══════════════════════════════════════════════════════════════════════════
# 13 · THE RECORD, AND THE COMMAND LINE.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_record_serialises_to_one_json_object_per_line() -> None:
    record = sr.Record(
        id="M-004201",
        name="probe.calc.x_add__mutmut_1",
        source=SOURCE,
        state=sr.KILLED,
        exit_code=1,
        signal=None,
        test="tests/test_parser.py::test_round_trip",
        worker="worker-3",
        attempt=ONE_ATTEMPT,
        duration_seconds=2.4109,
        reason="",
    )
    line = record.as_json()
    assert "\n" not in line
    loaded = json.loads(line)
    assert set(loaded) == RECORD_KEYS
    assert loaded["state"] == "killed"
    assert loaded["signal"] is None
    assert loaded["worker"] == "worker-3"
    assert loaded["duration_seconds"] == pytest.approx(2.411)


def test_every_option_is_required_because_none_of_them_may_be_invented() -> None:
    full = argv_with()
    assert sr.parse_argv(full).timeout_seconds == pytest.approx(5.0)
    for flag in sr._REQUIRED:
        index = full.index(flag)
        with pytest.raises(SystemExit, match="usage"):
            sr.parse_argv(full[:index] + full[index + 2 :])


@pytest.mark.parametrize(
    "argv", [["prog", "--nonsense"], ["prog", "--shard"], ["prog", "--nonsense", "value"]]
)
def test_the_command_line_refuses_what_it_does_not_understand(argv: list[str]) -> None:
    with pytest.raises(SystemExit, match="usage"):
        sr.parse_argv(argv)


@pytest.mark.parametrize(
    "overrides",
    [
        {"--timeout-seconds": "not-a-number"},
        {"--timeout-seconds": "0"},
        {"--timeout-seconds": "-1"},
        {"--max-attempts": "not-a-number"},
        {"--max-attempts": "1.5"},
        {"--max-attempts": "0"},
        {"--cpu-threads": "0"},
        {"--cpu-threads": "-2"},
        {"--shard-count": "0"},
        {"--shard-index": "-1"},
        {"--shard-index": "1", "--shard-count": "1"},
    ],
)
def test_a_number_that_could_not_do_its_job_is_refused(overrides: dict[str, str]) -> None:
    # Not thresholds — the caller still chooses every one. A budget that cannot
    # elapse, fewer than one attempt or one thread, or a shard index outside its
    # own count, would each report something that measured nothing.
    with pytest.raises(SystemExit, match="usage"):
        sr.parse_argv(argv_with(**overrides))


def test_the_default_mutation_copy_is_the_one_mutmut_writes() -> None:
    options = sr.parse_argv(argv_with())
    assert options.mutants_dir == Path("mutants")
    assert options.only == ()


def test_only_is_split_on_commas_and_blanks_are_dropped() -> None:
    assert sr.parse_argv(argv_with(**{"--only": "M-1, M-2 ,, "})).only == ("M-1", " M-2 ")


def test_the_entrypoint_runs_a_real_shard_and_writes_a_record_for_every_mutant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `runpy` executes the real module top level from the real file, exactly as
    # CI invokes it. Nothing here is stubbed.
    copy_dir = build_copy(tmp_path)
    shard = write_shard(
        tmp_path,
        [
            ("M-1", "probe.calc.x_add__mutmut_1"),
            ("M-2", "probe.calc.x_add__mutmut_2"),
            ("M-3", INVENTED),
        ],
    )
    output = tmp_path / "results.jsonl"
    previous = sys.argv
    sys.argv = ["mutation_shard_runner.py", *worker_argv(tmp_path, shard, output, copy_dir)[2:]]
    try:
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(running_path(sr)), run_name="__main__")
    finally:
        sys.argv = previous
    printed = capsys.readouterr().out
    assert excinfo.value.code == 0, printed

    lines = output.read_text(encoding="utf-8").splitlines()
    assert set(json.loads(lines[0])) == HEADER_KEYS
    records = [json.loads(line) for line in lines[1:]]
    assert [record["id"] for record in records] == ["M-1", "M-2", "M-3"]
    assert [record["state"] for record in records] == [
        sr.KILLED,
        sr.SURVIVED,
        sr.INFRASTRUCTURE_FAILURE,
    ]
    assert all(set(record) == RECORD_KEYS for record in records)
    assert all(record["state"] in sr.TERMINAL_STATES for record in records)
    assert "SLOWEST OPERATORS: UNAVAILABLE" in printed


def test_a_second_run_of_a_finished_shard_re_runs_nothing_and_still_reports_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Resumable result storage, end to end: the second invocation finds every
    # mutant already recorded, executes none of them, and still exits 0.
    copy_dir = build_copy(tmp_path)
    shard = write_shard(tmp_path, [("M-1", "probe.calc.x_add__mutmut_1")])
    output = tmp_path / "results.jsonl"
    argv = worker_argv(tmp_path, shard, output, copy_dir)[2:]
    assert sr.cli(["prog", *argv]) == 0
    first = output.read_text(encoding="utf-8")
    capsys.readouterr()

    assert sr.cli(["prog", *argv]) == 0
    printed = capsys.readouterr().out
    assert output.read_text(encoding="utf-8") == first, "a finished mutant was run again"
    assert "0 of 1 mutants to run" in printed, printed


def test_the_shard_runner_never_prints_a_score(tmp_path: Path) -> None:
    # The aggregator owns the formula. A second copy of it here would be a second
    # number to disagree with (Law 14, 19).
    text = running_path(sr).read_text(encoding="utf-8")
    assert "%" not in text.replace("%s", "").replace("%(", "")
    assert tmp_path.is_dir()


# ═══════════════════════════════════════════════════════════════════════════
# 14 · THE REAL SUBPROCESS EDGE.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_attempt_activates_the_mutant_rather_than_the_original(tmp_path: Path) -> None:
    # Disconfirming check, and activation is proven by DIFFERENCE rather than by
    # inspecting the environment. Two mutants of one function, run back to back
    # from one parent process, must reach two different results. If activation
    # did nothing, both would run the ORIGINAL `a + b` and both would survive. If
    # it LEAKED into the parent, the second would inherit the first and both
    # would be killed. Only working, non-leaking activation gives one of each.
    copy_dir = build_copy(tmp_path)
    isolation = isolation_in(tmp_path)
    states = [
        sr.run_once(name, [COVERING_TEST], copy_dir, RESULT_BUDGET_SECONDS, isolation).state
        for name in ("probe.calc.x_add__mutmut_1", "probe.calc.x_add__mutmut_2")
    ]
    assert states == [sr.KILLED, sr.SURVIVED], states


def test_an_attempt_with_no_tests_refuses_to_run_the_whole_suite(tmp_path: Path) -> None:
    # Measured: `pytest` with no positional target collects EVERYTHING. Handing
    # an empty test list to a subprocess would run the entire repository suite
    # against one mutant and call the result a result.
    copy_dir = build_copy(tmp_path)
    with pytest.raises(ValueError, match="no tests"):
        sr.run_once(
            "probe.calc.x_add__mutmut_1",
            [],
            copy_dir,
            RESULT_BUDGET_SECONDS,
            isolation_in(tmp_path),
        )


def test_a_missing_mutation_copy_is_refused_rather_than_counted_as_empty(tmp_path: Path) -> None:
    with pytest.raises(MutationResultsUnavailableError, match="not a directory"):
        sr.MutationCopy.read(tmp_path / "never-created")


def test_the_registration_scan_is_read_once_per_source_file(tmp_path: Path) -> None:
    # Not a performance claim — a correctness one. The cache must return the same
    # answer as the first read, so a shard of 300 mutants in one file cannot
    # start disagreeing with itself halfway through.
    copy = sr.MutationCopy.read(build_copy(tmp_path))
    first = copy.registrations(SOURCE)
    (copy.directory / SOURCE).write_text("nothing is registered here\n", encoding="utf-8")
    assert copy.registrations(SOURCE) == first
    assert "x_add__mutmut_1" in first
