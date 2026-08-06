#!/usr/bin/env python3
"""Run one immutable shard of mutants, and write each result down as it happens.

THE DEFECT THIS EXISTS FOR, MEASURED. The last full mutation run reached 2893 of
4429 mutants — 2440 killed, 288 survived, 162 TIMEOUT — and was then terminated.
Two losses at once:

    the 2893 results vanished     nothing was written until the end, so a killed
                                  process erased work already done
    the 162 timeouts had no home  they are neither killed nor survived, and a
                                  run that models only those two columns has to
                                  put them somewhere

The second is the dangerous one. A timeout folded into `killed` RAISES the
printed number, and nothing in the output says which mutants moved.

THE STATES ARE THE OWNER'S, AND THEY ARE CLOSED. `killed`, `survived`,
`timeout`, `error`, `infrastructure_failure`, `cancelled`. Exactly one per
mutant. `unattempted` is deliberately NOT among them: a mutant nobody got to has
no execution result, it is a RUN-LEVEL COMPLETENESS FAILURE, and it stays
visible in the report rather than being written into the file as though it were
an outcome.

WHAT THIS MODULE WILL NOT DO.

* It computes no score and prints no ratio. The aggregator owns that formula and
  a second copy of it would be a second number to disagree with (Law 14, 19).
* It invents no timeout, no retry count, no thread budget and no threshold.
  Every one is a required argument with no default, because a number chosen here
  is a decision nobody made.
* It never converts a no-result outcome into a result. A timeout is a `timeout`,
  and a mutant that was never reached is reported by ID as unattempted.
* It never retries a result. Re-running a survivor until it dies, or a failure
  until it passes, is choosing the answer. Only `infrastructure_failure`
  repeats, and only up to the bound the caller gave.
* It does not rank by mutation OPERATOR, because that number does not exist to
  be read. Measured against mutmut 3.x: a mutant is named
  `<module>.<mangled>__mutmut_<index>` and the `.meta` store holds
  `exit_code_by_key` and `hash_by_function_name`. Neither carries an operator,
  so an operator ranking here would be fabricated (Law 24). It is reported
  UNAVAILABLE, with that reason, rather than invented.

THE FALSE SURVIVOR THIS INHERITS, AND REFUSES. `mutation_denominator`'s
docstring records it: activation is a string in an environment variable, and
mutmut's generated trampoline calls the ORIGINAL function for a name it does not
recognise (`trampoline.py`: `if mutated_func is None: return orig_func(...)`).
So a mutant the mutation copy never registered runs pristine code, every test
passes, pytest exits 0, and a runner that trusted that exit code would print a
survivor that never ran. Every mutant here is proven REGISTERED before any
result about it is believed, and the proof is read off the generated file.

WHERE THE FACTS COME FROM. Nothing here re-derives mutmut's layout or pytest's
behaviour from memory. The mutant store, the covering-test store, the
registration scan, the activation variable and mutmut's own pytest arguments are
imported from `mutation_denominator`, which reads them from mutmut. The
exit-code classification was MEASURED against the pinned pytest, not recalled:

    all covering tests passed                     0
    at least one covering test failed             1
    the mutated module could not be imported      4, and `ERROR <file> - <exc>`
                                                  on STDOUT
    the covering test id does not exist           4, `no tests ran` on stdout and
                                                  `ERROR: not found:` on STDERR
    the interpreter died on a signal              negative, the signal negated
    no positional target at all                   the ENTIRE suite is collected

That last line is why an empty test list raises instead of starting a process.
The `4` collision is why `had_collection_error` exists: two different failures
share one exit code and only one of them is a fact about the mutant, so the
discriminator is pytest's own short summary, pinned with `-r fE` rather than
left to a default that could change.

ISOLATION, because parallel execution breaks things a sequential run never did.
Sixteen workers against one mutation copy collide on the filesystem in four
places, and each is closed here rather than hoped about:

    the shared temporary directory   TMPDIR / TEMP / TMP point into the work dir
    pytest's own tmp_path trees      `--basetemp` under the work dir
    `.pytest_cache` in the tree      `-p no:cacheprovider`
    `__pycache__` in the tree        PYTHONPYCACHEPREFIX under the work dir

and CPU contention and repeated model loads are bounded by an explicit thread
budget the caller states. THE ONE THING THIS MODULE CANNOT PROVIDE is a unique
working directory: pytest resolves a test id like `tests/unit/test_x.py::test_y`
against the current directory, and mutmut's own `pythonpath` resolves against
the same root, so the working directory MUST be the mutation copy. Giving each
worker its own copy of that tree is the orchestrator's to do, and this module
says so instead of pretending otherwise.

RESUMABLE BY CONSTRUCTION. Every mutant already carrying a record in the output
file is skipped, so a worker that died halfway resumes from where the disk says
it stopped rather than from the beginning. `--only` overrides that for named
mutants, which is how ONE failed mutant is retried without re-running its shard;
the later record wins, so a retry REPLACES rather than duplicates.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType

# TWO PRIVATE NAMES ARE IMPORTED, DELIBERATELY, AND THIS NOTE IS WHY.
#
# `_pytest_command` is mutmut's OWN pytest arguments. Copying that list would
# make a result reached here mean something subtly different from a result
# reached by `mutation_denominator` or by mutmut itself, and the difference
# would be invisible (Law 19).
#
# `_load_json_object` is the WHOLE-DOCUMENT JSON reader that module already uses
# on `mutmut-stats.json`. Reading that file any other way is how this module
# silently lost every per-test duration once already; two readers for one file
# is two chances to disagree about it.
#
# Both are private there only because nothing else had needed them yet.
from mutation_denominator import (
    MUTANT_ENV_VAR,
    NO_PROXY_ENVIRONMENT,
    PYTEST_ALL_PASSED,
    PYTEST_TESTS_FAILED,
    STATS_FILENAME,
    Mutant,
    MutationResultsUnavailableError,
    _load_json_object,
    _pytest_command,
    generated_function,
    mangled_name,
    read_covering_tests,
    read_mutants,
    registered_mutants,
)

# ── the six terminal states, and the one word that is not among them ─────────

#: The two that are results about the mutant.
KILLED = "killed"
SURVIVED = "survived"

#: The four that are not, and are never allowed to become one.
TIMEOUT = "timeout"
ERROR = "error"
INFRASTRUCTURE_FAILURE = "infrastructure_failure"
CANCELLED = "cancelled"

#: Closed by design, and checked before the command line exits 0.
TERMINAL_STATES = frozenset({KILLED, SURVIVED, TIMEOUT, ERROR, INFRASTRUCTURE_FAILURE, CANCELLED})

#: NOT a terminal execution result, and deliberately not in the set above. A
#: mutant nobody reached has no outcome to record; it is a completeness failure
#: of the RUN, and it is reported by ID rather than written into the file as
#: though something had been observed.
UNATTEMPTED = "unattempted"

#: The only state worth attempting again. A `killed`, a `survived`, a `timeout`,
#: an `error` and a `cancelled` are all facts; re-running a fact until it
#: changes is choosing an answer.
RETRYABLE_STATES = frozenset({INFRASTRUCTURE_FAILURE})

# ── pytest, as measured ──────────────────────────────────────────────────────

#: Exit codes that are neither result: interrupted, internal error, usage error,
#: nothing collected. Which of `error` and `infrastructure_failure` they mean is
#: decided by the short summary, because a broken import and a missing test id
#: both exit 4.
PYTEST_NOT_A_RESULT = frozenset({2, 3, 4, 5})

#: Pinned rather than inherited. pytest's default already prints failures and
#: errors in the short summary, but a classification that depends on a default
#: is a classification that changes when the default does.
PYTEST_REPORT_CHARS = "fE"

#: `FAILED <nodeid> - <reason>` names the test that killed the mutant;
#: `ERROR <file> - <exception>` says the module never imported.
_FAILED_LINE = re.compile(r"^FAILED\s+(?P<test>\S+)", re.MULTILINE)
_ERROR_LINE = re.compile(r"^ERROR\s+\S", re.MULTILINE)

# ── shapes and defaults ──────────────────────────────────────────────────────

#: Millisecond precision on the wire. Far finer than any decision taken on it,
#: and it keeps a record from carrying seventeen digits of float noise.
DURATION_PLACES = 3

#: mutmut writes its copy to a literal `mutants/`. Not a threshold and not a
#: choice — it is where the tree is.
DEFAULT_MUTANTS_DIRECTORY = "mutants"

#: How many rows each slowest-first table prints. A DISPLAY length, not a
#: threshold: nothing is hidden by it, because every mutant's own duration is in
#: the JSONL and the aggregator sees all of them.
SLOWEST_SHOWN = 10

#: The header's fields, in the order the aggregator was told to expect.
HEADER_FIELDS = (
    "shard_index",
    "shard_count",
    "manifest_sha256",
    "commit",
    "dependency_lock_hash",
)

#: Per-worker isolation, all under one directory the caller names.
TEMPORARY_SUBDIRECTORY = "tmp"
BASETEMP_SUBDIRECTORY = "pytest-basetemp"
PYCACHE_SUBDIRECTORY = "pycache"

#: Every library that reads a thread count from the environment before this
#: repository's code gets a say. Sixteen workers each defaulting to one thread
#: per core is how a parallel run becomes slower than the sequential one it
#: replaced, and how sixteen model loads exhaust memory at once.
THREAD_BUDGET_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)

_FLAGS = (
    "--shard",
    "--output",
    "--worker",
    "--work-dir",
    "--timeout-seconds",
    "--max-attempts",
    "--cpu-threads",
    "--shard-index",
    "--shard-count",
    "--manifest-sha256",
    "--commit",
    "--dependency-lock-hash",
    "--mutants-dir",
    "--only",
)

#: Everything the caller must state. Nothing here has a default, by rule.
_REQUIRED = tuple(flag for flag in _FLAGS if flag not in ("--mutants-dir", "--only"))

_USAGE = "\n".join(
    [
        "usage: mutation_shard_runner.py",
        "  --shard FILE               JSONL, one object per mutant, with `id` and `name`",
        "  --output FILE              JSONL; line 1 is the header, then one line per mutant",
        "  --worker NAME              recorded on every line this process writes",
        "  --work-dir DIR             this worker's private temp, basetemp and pycache root",
        "  --timeout-seconds SECS     per attempt; must be greater than zero",
        "  --max-attempts N           at least 1; only infrastructure failures repeat",
        "  --cpu-threads N            at least 1; the per-worker thread budget",
        "  --shard-index N            echoed into the header",
        "  --shard-count N            echoed into the header",
        "  --manifest-sha256 HEX      echoed into the header UNMODIFIED",
        "  --commit SHA               echoed into the header",
        "  --dependency-lock-hash H   echoed into the header",
        f"  --mutants-dir DIR          the mutation copy (default: {DEFAULT_MUTANTS_DIRECTORY})",
        "  --only ID[,ID...]          re-run exactly these mutants, replacing their results",
    ]
)


class ShardUnreadableError(Exception):
    """Raised when the shard, or an existing output file, cannot be trusted.

    Never falls back to the part it could parse. A shard silently reduced to its
    readable half is the same silent exclusion this pipeline exists to end, one
    level up: the aggregator would see fewer records and no failure.
    """


class ShardCancelled(Exception):  # noqa: N818 - a control signal, not an error condition
    """Raised inside a signal handler so a stop request unwinds the current attempt.

    Deliberately an exception rather than a polled flag. `subprocess.run` blocks
    for as long as a mutant runs, and it kills its child on ANY exception out of
    `communicate()`, so raising here both stops the shard promptly and leaves no
    orphaned pytest behind.
    """


@dataclass(frozen=True)
class ShardEntry:
    """One mutant this shard is responsible for."""

    #: The manifest's identifier, e.g. `M-004201`. Carried through untouched so
    #: the aggregator can join results back to the manifest.
    id: str
    #: mutmut's mutant name, e.g. `accountant_dad.confidence.x_score__mutmut_3`.
    name: str


@dataclass(frozen=True)
class Header:
    """The first line of a shard result file. The aggregator's join key.

    `manifest_sha256` is echoed exactly as given. The aggregator compares it
    across shards and refuses to combine any that disagree, so normalising it
    here — trimming, lower-casing, anything — would silently defeat the one
    check that notices two workers ran different manifests.
    """

    shard_index: int
    shard_count: int
    manifest_sha256: str
    commit: str
    dependency_lock_hash: str

    def as_json(self) -> str:
        return json.dumps(
            {
                "shard_index": self.shard_index,
                "shard_count": self.shard_count,
                "manifest_sha256": self.manifest_sha256,
                "commit": self.commit,
                "dependency_lock_hash": self.dependency_lock_hash,
            }
        )


@dataclass(frozen=True)
class Attempt:
    """What one run of one mutant's covering tests observed.

    An attempt is not a record. It carries no identifier and no worker, because
    a mutant may take several attempts and only the mutant gets a record.
    """

    state: str
    #: The process's exit code, or `None` when it never exited on its own.
    exit_code: int | None
    #: The signal that killed the process, or `None`. A timeout leaves BOTH
    #: empty: we killed that process, so attributing our own signal to the
    #: mutant would report something nobody observed.
    signal: int | None
    #: The test that killed the mutant, read off pytest's summary. `None` unless
    #: the state is `killed`.
    test: str | None
    duration_seconds: float
    reason: str = ""


@dataclass(frozen=True)
class Record:
    """One mutant's terminal result — the durable unit this module produces."""

    id: str
    name: str
    source: str
    state: str
    exit_code: int | None
    signal: int | None
    test: str | None
    worker: str
    #: How many runs it took. Greater than 1 only after an infrastructure
    #: failure, and never after a result.
    attempt: int
    #: Every attempt added together, not just the last one. A retried mutant
    #: reporting only its final run would under-report what the shard spent.
    duration_seconds: float
    #: Why, whenever the state is not `killed` or `survived`. Empty otherwise.
    #: A failure with no explanation is a silent failure wearing a state word.
    reason: str

    def as_json(self) -> str:
        """The record as one JSON object on one line."""
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "source": self.source,
                "state": self.state,
                "exit_code": self.exit_code,
                "signal": self.signal,
                "test": self.test,
                "worker": self.worker,
                "attempt": self.attempt,
                "duration_seconds": round(self.duration_seconds, DURATION_PLACES),
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class Isolation:
    """One worker's private corners of the filesystem, and its thread budget.

    Created rather than assumed: a directory that does not exist is a collision
    waiting to happen the first time two workers race to make it.
    """

    work_dir: Path
    cpu_threads: int

    @property
    def temporary(self) -> Path:
        return self.work_dir / TEMPORARY_SUBDIRECTORY

    @property
    def basetemp(self) -> Path:
        return self.work_dir / BASETEMP_SUBDIRECTORY

    @property
    def pycache(self) -> Path:
        return self.work_dir / PYCACHE_SUBDIRECTORY

    def prepare(self) -> None:
        """Make every directory this worker will write into."""
        for directory in (self.temporary, self.basetemp.parent, self.pycache):
            directory.mkdir(parents=True, exist_ok=True)

    def environment(self) -> dict[str, str]:
        """The environment variables that keep this worker out of the others' way."""
        variables = {
            "TMPDIR": str(self.temporary),
            "TEMP": str(self.temporary),
            "TMP": str(self.temporary),
            "PYTHONPYCACHEPREFIX": str(self.pycache),
            # Tokenizers forks a thread pool on import and warns about it; off is
            # both quieter and one less source of contention between workers.
            "TOKENIZERS_PARALLELISM": "false",
        }
        variables.update(dict.fromkeys(THREAD_BUDGET_VARIABLES, str(self.cpu_threads)))
        return variables

    def pytest_arguments(self) -> list[str]:
        """The pytest flags that stop two workers writing into one shared tree.

        `--basetemp` puts every `tmp_path` under this worker's own root, and
        `-p no:cacheprovider` stops pytest creating `.pytest_cache` inside the
        mutation copy, which is the one directory all workers share.
        """
        return ["--basetemp", str(self.basetemp), "-p", "no:cacheprovider"]


@dataclass(frozen=True)
class Policy:
    """The numbers the caller owns. Not one of them has a default."""

    worker: str
    max_attempts: int
    timeout_seconds: float


@dataclass(frozen=True)
class Options:
    """What the command line asked for."""

    shard: Path
    output: Path
    worker: str
    work_dir: Path
    timeout_seconds: float
    max_attempts: int
    cpu_threads: int
    header: Header
    mutants_dir: Path
    only: tuple[str, ...]


@dataclass(frozen=True)
class MutationCopy:
    """The tree a shard runs against, and mutmut's own records of it."""

    directory: Path
    #: Mutant name to the mutant mutmut recorded. A name absent from here is a
    #: name mutmut never generated, and nothing about it can be measured.
    mutants: Mapping[str, Mutant]
    #: Mangled function name to the tests mutmut saw execute it.
    covering: Mapping[str, tuple[str, ...]]
    #: Source path to the mutant names its generated file registers. Filled in
    #: on demand: a shard touches a handful of files, and reading every mutated
    #: file up front would make one unreadable file fail shards that never go
    #: near it.
    _registered: dict[str, frozenset[str]] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def read(cls, directory: Path) -> MutationCopy:
        """Read mutmut's own records. Raises rather than reporting an empty tree."""
        mutants = {mutant.name: mutant for mutant in read_mutants(directory)}
        return cls(directory=directory, mutants=mutants, covering=read_covering_tests(directory))

    def source_of(self, name: str) -> str:
        """The authored source path a mutant belongs to, or empty when unknown."""
        mutant = self.mutants.get(name)
        return "" if mutant is None else mutant.source

    def registrations(self, source: str) -> frozenset[str]:
        """Every mutant name the generated file for `source` actually registers."""
        if source not in self._registered:
            self._registered[source] = registered_mutants(self.directory / source)
        return self._registered[source]

    def plan(self, name: str) -> tuple[tuple[str, ...], str]:
        """The covering tests for `name`, or the reason there is no result to reach.

        THREE REFUSALS, and every one of them would otherwise become a survivor.

        A name mutmut never recorded cannot be activated, because the generated
        file defines nothing under it.

        A name the mutation copy does not REGISTER is worse than useless: the
        trampoline falls back to the original function, the covering tests pass
        against pristine code, and pytest exits 0. Proving registration first is
        what stops "the mutation copy is stale" from reading as "the mutant is
        alive".

        A mutant with no covering test has nothing to run. Calling it survived
        because no test failed, when no test ran, is a result nobody measured
        (Law 24).
        """
        mutant = self.mutants.get(name)
        if mutant is None:
            return (), f"mutmut recorded no such mutant under {self.directory}"
        if generated_function(name) not in self.registrations(mutant.source):
            return (), (
                f"{self.directory / mutant.source} registers no such mutant, so activating "
                "it would run the ORIGINAL function and every test would pass"
            )
        tests = self.covering.get(mangled_name(name), ())
        if not tests:
            return (), "mutmut recorded no test covering this function"
        return tests, ""


#: The narrow I/O edge. Everything else in this module is arithmetic over files
#: and strings; this is the only thing that starts a process, and it is the only
#: thing a test is ever allowed to fake (CLAUDE.md J.7).
AttemptRunner = Callable[[str, Sequence[str]], Attempt]

#: Where a finished record goes. Separated from the running so that durability
#: is one small thing that can be attacked on its own.
Sink = Callable[[Record], None]

#: Progress, reported per MUTANT ID rather than as a count, so a shard that
#: stalls says which mutant it stalled on.
Progress = Callable[[str], None]


# ── cancellation ─────────────────────────────────────────────────────────────


def _raise_cancelled(number: int, frame: FrameType | None) -> None:
    raise ShardCancelled(f"signal {number} received; the shard was cancelled at {frame}")


@contextmanager
def cancel_on_signals(numbers: Sequence[int] = (signal.SIGTERM, signal.SIGINT)) -> Iterator[None]:
    """Turn a stop request into a `ShardCancelled` at the point of execution.

    Restores the previous handlers on the way out, so importing this module
    never changes how another process behaves and a test can install it around
    one block without leaking.
    """
    previous = [(number, signal.getsignal(number)) for number in numbers]
    for number in numbers:
        signal.signal(number, _raise_cancelled)
    try:
        yield
    finally:
        for number, handler in previous:
            signal.signal(number, handler)


# ── pytest's answer, classified ──────────────────────────────────────────────


def had_collection_error(stdout: str) -> bool:
    """Whether pytest reported a collection ERROR — the mutated module never imported.

    Read off stdout ONLY, and that is the whole discriminator. Measured: a
    broken import prints `ERROR <file> - <exception>` in the short summary on
    stdout, while a test id pytest cannot find prints `ERROR: not found:` on
    stderr and `no tests ran` on stdout. Both exit 4, so the exit code alone
    cannot tell a fact about the mutant from a fact about the manifest.
    """
    return _ERROR_LINE.search(stdout) is not None


def failing_test(stdout: str) -> str | None:
    """The node id of the test that failed, or `None` when none did.

    With `-x` there is at most one, because pytest stops at the first failure.
    """
    match = _FAILED_LINE.search(stdout)
    return None if match is None else match.group("test")


def state_from_exit(
    returncode: int, *, collection_error: bool
) -> tuple[str, int | None, int | None]:
    """The state one finished process carries, with its exit code and signal.

    Only two codes are results. Everything else is reported by name and by
    number, never folded into either column. A code nobody defined becomes
    `error` rather than `infrastructure_failure`: the process ran and left on
    its own terms, so that is the mutated program's behaviour and not the
    harness's — and `error` is deliberately not retried.
    """
    if returncode < 0:
        return ERROR, None, -returncode
    if returncode == PYTEST_ALL_PASSED:
        return SURVIVED, returncode, None
    if returncode == PYTEST_TESTS_FAILED:
        return KILLED, returncode, None
    if returncode in PYTEST_NOT_A_RESULT:
        return (ERROR if collection_error else INFRASTRUCTURE_FAILURE), returncode, None
    return ERROR, returncode, None


def _reason_for(state: str, returncode: int, *, collection_error: bool) -> str:
    """Why this attempt reached no result. Empty when it did.

    The `error` state covers two distinct failures the owner's set does not
    separate — the mutant broke the import, and the interpreter died. Neither is
    lost: the state is `error` as specified, and which one it was is written
    here in words rather than smuggled in as a seventh state.
    """
    if state in (KILLED, SURVIVED):
        return ""
    if returncode < 0:
        return f"the interpreter was killed by signal {-returncode} (runtime failure)"
    if collection_error:
        return (
            f"pytest exited {returncode} reporting a collection error (the mutant broke the import)"
        )
    return f"pytest exited {returncode}, which is not a result"


# ── the one place a process is started ───────────────────────────────────────


def run_once(
    name: str,
    tests: Sequence[str],
    directory: Path,
    timeout_seconds: float,
    isolation: Isolation,
) -> Attempt:
    """Activate one mutant and run its covering tests in a FRESH, ISOLATED process.

    THE WHOLE POINT IS `exec`, NOT `fork`. mutmut forks a child per mutant and
    inherits an already-initialised interpreter, which is what makes a
    fork-unsafe call site crash. `subprocess.run` forks AND execs, so the child
    starts clean and the unsafe state does not exist to be inherited.

    The working directory is the mutation copy and the same three entries are
    stated on `PYTHONPATH`, so pytest resolves against the INSTRUMENTED tree
    exactly as it does under mutmut — an exec'd process inherits none of the
    `sys.path` surgery mutmut performs in its parent.

    Everything the child would otherwise write into that SHARED tree is
    redirected into this worker's own directory, and its thread pools are capped
    to the budget the caller stated.

    An empty `tests` is refused rather than passed through. Measured: pytest
    with no positional target collects the ENTIRE suite, so an empty list would
    run the whole repository against one mutant and return a number that looks
    like a result.
    """
    if not tests:
        raise ValueError(
            f"{name} was given no tests to run, and pytest with no target collects "
            "the whole suite. There is no result to reach here."
        )
    root = directory.resolve()
    environment = dict(os.environ)
    environment.update(NO_PROXY_ENVIRONMENT)
    environment.update(isolation.environment())
    environment[MUTANT_ENV_VAR] = name
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root / "src"), str(root / "tools" / "ci"), str(root)]
    )
    argv = [
        *_pytest_command(sys.executable, list(tests)),
        "-r",
        PYTEST_REPORT_CHARS,
        *isolation.pytest_arguments(),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - argv list, no shell, interpreter is a path
            argv,
            check=False,
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return Attempt(
            state=TIMEOUT,
            exit_code=None,
            signal=None,
            test=None,
            duration_seconds=time.monotonic() - started,
            reason=(
                f"no result within {timeout_seconds} seconds; this process killed it, "
                "so nothing about how the mutant would have ended was observed"
            ),
        )
    duration = time.monotonic() - started
    stdout = completed.stdout.decode("utf-8", errors="replace")
    collection_error = had_collection_error(stdout)
    state, exit_code, signal_number = state_from_exit(
        completed.returncode, collection_error=collection_error
    )
    return Attempt(
        state=state,
        exit_code=exit_code,
        signal=signal_number,
        test=failing_test(stdout) if state == KILLED else None,
        duration_seconds=duration,
        reason=_reason_for(state, completed.returncode, collection_error=collection_error),
    )


def subprocess_runner(copy: MutationCopy, policy: Policy, isolation: Isolation) -> AttemptRunner:
    """The real attempt runner, bound to one mutation copy, timeout and worker."""

    def run(name: str, tests: Sequence[str]) -> Attempt:
        return run_once(name, tests, copy.directory, policy.timeout_seconds, isolation)

    return run


# ── one mutant, one record ───────────────────────────────────────────────────


def _record(
    entry: ShardEntry, copy: MutationCopy, policy: Policy, attempt: Attempt, runs: int
) -> Record:
    return Record(
        id=entry.id,
        name=entry.name,
        source=copy.source_of(entry.name),
        state=attempt.state,
        exit_code=attempt.exit_code,
        signal=attempt.signal,
        test=attempt.test,
        worker=policy.worker,
        attempt=runs,
        duration_seconds=attempt.duration_seconds,
        reason=attempt.reason,
    )


def run_mutant(entry: ShardEntry, copy: MutationCopy, policy: Policy, run: AttemptRunner) -> Record:
    """One mutant, one record — however many attempts that took.

    The retry loop repeats ONLY while the outcome is retryable, so a result ends
    it on the first attempt by construction rather than by a check somebody has
    to remember to write. A refusal never becomes an attempt at all: there is no
    process to re-run, and retrying a deterministic refusal would only multiply
    the same answer.

    A `ShardCancelled` raised out of an attempt is caught HERE and turned into a
    `cancelled` record, so a stopped worker still says what happened to the
    mutant it was holding, and then re-raised so the shard stops.
    """
    tests, refusal = copy.plan(entry.name)
    if refusal:
        return _record(
            entry,
            copy,
            policy,
            Attempt(
                state=INFRASTRUCTURE_FAILURE,
                exit_code=None,
                signal=None,
                test=None,
                duration_seconds=0.0,
                reason=refusal,
            ),
            1,
        )
    outcome = run(entry.name, tests)
    runs = 1
    spent = outcome.duration_seconds
    while outcome.state in RETRYABLE_STATES and runs < policy.max_attempts:
        runs += 1
        outcome = run(entry.name, tests)
        spent += outcome.duration_seconds
    return _record(entry, copy, policy, replace_duration(outcome, spent), runs)


def replace_duration(attempt: Attempt, seconds: float) -> Attempt:
    """The same attempt, carrying the time every attempt for that mutant took."""
    return Attempt(
        state=attempt.state,
        exit_code=attempt.exit_code,
        signal=attempt.signal,
        test=attempt.test,
        duration_seconds=seconds,
        reason=attempt.reason,
    )


def cancelled_record(entry: ShardEntry, copy: MutationCopy, policy: Policy, why: str) -> Record:
    """The record a mutant gets when the worker was told to stop while holding it."""
    return _record(
        entry,
        copy,
        policy,
        Attempt(
            state=CANCELLED,
            exit_code=None,
            signal=None,
            test=None,
            duration_seconds=0.0,
            reason=why,
        ),
        1,
    )


def _ignore(_line: str) -> None:
    """The default progress reporter: says nothing, so a library caller is quiet."""


@dataclass(frozen=True)
class Reporting:
    """Where a finished record goes: onto the disk, and into the log, per mutant.

    One object rather than two parameters because they are one decision — how
    this run is observed — and because a mutant is only ever reported after its
    record is durable, never before.
    """

    sink: Sink
    progress: Progress = _ignore

    def publish(self, position: int, total: int, record: Record) -> None:
        """Durable first, announced second. Never the other way round."""
        self.sink(record)
        self.progress(
            f"[{position}/{total}] {record.id} {record.name} -> {record.state} "
            f"({record.duration_seconds:.3f}s, attempt {record.attempt})"
        )


def run_shard(
    entries: Sequence[ShardEntry],
    copy: MutationCopy,
    policy: Policy,
    run: AttemptRunner,
    reporting: Reporting,
) -> tuple[Record, ...]:
    """Every mutant in the shard, each made durable before the next one starts.

    The ordering is the durability guarantee. A batch written at the end is a
    batch a killed worker takes with it, which is exactly what happened to 2893
    results.

    On cancellation the mutant in hand gets a `cancelled` record and the loop
    STOPS. Everything after it is left with no record at all, which is what
    makes a cancelled shard an incomplete run rather than a short one that looks
    finished.
    """
    records: list[Record] = []
    for position, entry in enumerate(entries, 1):
        try:
            record = run_mutant(entry, copy, policy, run)
        except ShardCancelled as cancellation:
            record = cancelled_record(entry, copy, policy, str(cancellation))
            records.append(record)
            reporting.publish(position, len(entries), record)
            break
        records.append(record)
        reporting.publish(position, len(entries), record)
    return tuple(records)


@contextmanager
def record_sink(path: Path, header: Header | None = None) -> Iterator[Sink]:
    """Append one record per line, flushed and fsynced before the call returns.

    APPEND, never truncate: a restarted worker must not delete what an earlier
    one already proved. `fsync` rather than `flush` alone, because a flush only
    reaches the operating system's buffers — a killed process survives that, a
    killed machine does not, and the cost is nothing beside a test run.

    The header is written only when the file is new or empty, so a resumed
    worker appends to the file it started rather than putting a second header in
    the middle of it.
    """
    fresh = not path.is_file() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8") as handle:
        if fresh and header is not None:
            handle.write(header.as_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        def write(record: Record) -> None:
            handle.write(record.as_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        yield write


# ── the shard file, and the output file read back ────────────────────────────


def _field(where: str, line: Mapping[str, object], key: str) -> str:
    value = line.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ShardUnreadableError(f"{where} has no usable {key!r}: {value!r}")
    return value


def _entry(where: str, line: str) -> ShardEntry:
    try:
        loaded = json.loads(line)
    except json.JSONDecodeError as error:
        raise ShardUnreadableError(f"{where} is not valid JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise ShardUnreadableError(f"{where} is not a JSON object")
    return ShardEntry(id=_field(where, loaded, "id"), name=_field(where, loaded, "name"))


def read_shard(path: Path) -> tuple[ShardEntry, ...]:
    """The mutants this shard owns: JSONL, `id` and `name` on every line.

    Only those two keys are read, and every other key is left alone. The shard
    file is produced by whoever owns the manifest and the sharding; this module
    is deliberately not a second opinion on their schema, and reading two keys
    strictly is what lets a richer manifest line pass through untouched.

    The shard is IMMUTABLE here — it is opened for reading and never written.

    A blank line is skipped; a trailing newline is not a defect. Anything else
    it cannot parse is refused BY LINE NUMBER, because a shard is machine
    written and a malformed line means the writer is broken.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ShardUnreadableError(f"{path} could not be read: {error}") from error
    entries = [
        _entry(f"{path}:{number}", line)
        for number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]
    if not entries:
        raise ShardUnreadableError(
            f"{path} lists no mutants. An empty shard that exits 0 is a shard whose "
            "absence nothing would notice."
        )
    return tuple(entries)


def _json_lines(path: Path) -> list[object]:
    """Every line of a JSONL file that parses. A torn write contributes nothing."""
    if not path.is_file():
        return []
    parsed: list[object] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return parsed


def recorded_states(path: Path) -> dict[str, str]:
    """Mutant id to its LAST recorded state, read back off disk.

    Read back rather than remembered on purpose. A count kept in memory says the
    runner believes it wrote something; this says the bytes are there and parse.
    A line torn in half by a kill contributes nothing, which is correct — that
    mutant has no durable record.

    LAST wins, and that is the retry contract: re-running one mutant appends a
    new record and the later one is its result, so a retry REPLACES rather than
    creating a second logical result for the same id.
    """
    states: dict[str, str] = {}
    for loaded in _json_lines(path):
        if not isinstance(loaded, dict):
            continue
        identifier, state = loaded.get("id"), loaded.get("state")
        if isinstance(identifier, str) and isinstance(state, str):
            states[identifier] = state
    return states


def existing_header(path: Path) -> Header | None:
    """The header already on disk, or `None` when the file has none yet."""
    lines = _json_lines(path)
    if not lines or not isinstance(lines[0], dict):
        return None
    first = lines[0]
    if any(key not in first for key in HEADER_FIELDS):
        return None
    return Header(
        shard_index=int(str(first["shard_index"])),
        shard_count=int(str(first["shard_count"])),
        manifest_sha256=str(first["manifest_sha256"]),
        commit=str(first["commit"]),
        dependency_lock_hash=str(first["dependency_lock_hash"]),
    )


def check_resumable(path: Path, header: Header) -> None:
    """Refuse to append this worker's results to somebody else's shard file.

    The header identifies the manifest, the commit and the dependency lock. A
    resumed run that disagrees with any of them is two different runs sharing
    one file, and the aggregator would combine them without ever seeing that
    they were not the same measurement.
    """
    found = existing_header(path)
    if found is not None and found != header:
        raise ShardUnreadableError(
            f"{path} already carries a different header, so resuming into it would mix two "
            f"runs.\n  on disk : {found.as_json()}\n  given   : {header.as_json()}"
        )


def still_to_run(
    entries: Sequence[ShardEntry], done: Mapping[str, str], only: Sequence[str]
) -> tuple[ShardEntry, ...]:
    """Which of this shard's mutants this process should actually execute.

    With `--only`, exactly the named ones — that is how a single failed mutant is
    retried without re-running its shard, and the entries are taken FROM THE
    SHARD, so a name that is not this shard's cannot be smuggled in.

    Without it, everything that has no record on disk yet. A worker that died
    halfway therefore resumes from the disk rather than from the beginning, and
    cannot produce a duplicate for work already proven.
    """
    if only:
        wanted = set(only)
        return tuple(entry for entry in entries if entry.id in wanted)
    return tuple(entry for entry in entries if entry.id not in done)


def unattempted(entries: Sequence[ShardEntry], done: Mapping[str, str]) -> tuple[str, ...]:
    """The ids this shard was given and cannot show a durable record for.

    Not a state, and never written into the file. A mutant nobody reached is a
    completeness failure of the RUN, and it is named here so a crashed or
    cancelled shard reads as incomplete instead of short.
    """
    return tuple(entry.id for entry in entries if entry.id not in done)


# ── reporting ────────────────────────────────────────────────────────────────


def read_test_durations(mutants_dir: Path) -> Mapping[str, float]:
    """mutmut's own per-test durations, from the stats file it already writes.

    Read rather than measured here, and that is the point: this module times a
    whole attempt, not the individual tests inside it, so a per-test number of
    its own would be an attribution rather than a measurement. `duration_by_test`
    is mutmut's, taken during its statistics phase. Absent or malformed, the
    answer is an empty mapping and the report says the breakdown is unavailable.

    THE BUG THIS FIXES, FOUND BY THE PILOT AND NOT BY ITS OWN TESTS. The first
    version read this file with the JSONL reader used for the RESULT files. The
    hand-built fixture wrote the stats as one line, so the reader worked and the
    test agreed. Real mutmut writes it PRETTY-PRINTED over thirty lines, so line
    one is `{`, nothing parsed, and the function silently returned no durations
    at all — a whole breakdown missing with no error anywhere. It is a WHOLE JSON
    DOCUMENT, and it is now read by the same whole-document reader
    `mutation_denominator` already uses for it, so the two cannot disagree.
    """
    try:
        stats = _load_json_object(mutants_dir / STATS_FILENAME)
    except MutationResultsUnavailableError:
        return {}
    durations = stats.get("duration_by_test")
    if not isinstance(durations, dict):
        return {}
    return {
        str(test): float(seconds)
        for test, seconds in durations.items()
        if isinstance(seconds, int | float)
    }


def _slowest(pairs: Mapping[str, float], label: str) -> list[str]:
    if not pairs:
        return [f"  (no {label} recorded)"]
    ranked = sorted(pairs.items(), key=lambda item: (-item[1], item[0]))[:SLOWEST_SHOWN]
    return [f"  {seconds:9.3f}s  {name}" for name, seconds in ranked]


def timing_report(records: Sequence[Record], durations: Mapping[str, float]) -> list[str]:
    """Slowest mutants, slowest files, slowest tests — and the one that is not there.

    The operator breakdown the specification asks for is reported UNAVAILABLE
    rather than invented. Measured against mutmut 3.x: a mutant is named
    `<module>.<mangled>__mutmut_<index>` and its `.meta` store holds
    `exit_code_by_key` and `hash_by_function_name`. Neither records which
    mutation operator produced the mutant, so ranking by operator would mean
    guessing from the index (Law 24).
    """
    by_mutant = {f"{record.id} {record.name}": record.duration_seconds for record in records}
    by_source: dict[str, float] = {}
    for record in records:
        key = record.source or "(source unknown)"
        by_source[key] = by_source.get(key, 0.0) + record.duration_seconds
    lines = ["", f"SLOWEST MUTANTS (top {SLOWEST_SHOWN} of {len(records)})"]
    lines += _slowest(by_mutant, "mutants")
    lines += ["", f"SLOWEST FILES (top {SLOWEST_SHOWN}, summed over this shard)"]
    lines += _slowest(by_source, "files")
    lines += ["", f"SLOWEST TESTS (top {SLOWEST_SHOWN}, from mutmut's own duration_by_test)"]
    lines += _slowest(durations, "test durations")
    lines += [
        "",
        "SLOWEST OPERATORS: UNAVAILABLE. mutmut names a mutant by INDEX, not by",
        "  operator, and neither the `.meta` store nor `mutmut-stats.json` records",
        "  which operator produced it. A ranking here would be invented.",
    ]
    return lines


def summary(records: Sequence[Record], elapsed_seconds: float) -> list[str]:
    """One line per state, the shard's own wall time, and every retry by ID.

    Deliberately no ratio. The aggregator owns the formula; this owns the
    records it is taken over.
    """
    counts: dict[str, int] = {}
    for record in records:
        counts[record.state] = counts.get(record.state, 0) + 1
    lines = [f"{state:24} {count}" for state, count in sorted(counts.items())]
    results = counts.get(KILLED, 0) + counts.get(SURVIVED, 0)
    lines.append("-" * 34)
    lines.append(f"{'reached a result':24} {results}")
    lines.append(f"{'NO RESULT':24} {len(records) - results}")
    lines.append(f"{'shard wall time':24} {elapsed_seconds:.3f}s")
    lines.append(f"{'mutant time, summed':24} {sum(r.duration_seconds for r in records):.3f}s")
    retried = [record for record in records if record.attempt > 1]
    lines.append(f"{'retried':24} {len(retried)}")
    lines += [
        f"  {record.id} took {record.attempt} attempts: {record.reason}" for record in retried
    ]
    return lines


def completeness(entries: Sequence[ShardEntry], output: Path) -> tuple[list[str], int]:
    """The shard's verdict on itself, read back off the disk, and the exit code.

    Separated from `cli` so the BLOCKED path is reachable in a test without
    faking a filesystem failure. A defensive branch nothing can execute is a
    branch nobody has ever seen work.

    COMPLETENESS, never quality: every mutant this shard was given has a durable
    record, and every state is inside the closed set. Whether the results are
    good enough is the aggregator's question, and answering it twice would be
    two answers.
    """
    done = recorded_states(output)
    missing = unattempted(entries, done)
    unknown = sorted({state for state in done.values() if state not in TERMINAL_STATES})
    if missing or unknown:
        return (
            [
                f"BLOCKED - INCOMPLETE RUN. {len(missing)} of {len(entries)} mutants are "
                f"{UNATTEMPTED} in {output}, and {len(unknown)} carry a state outside the "
                "closed set.",
                f"  {UNATTEMPTED}: {', '.join(missing) if missing else 'none'}",
                f"  bad state  : {', '.join(unknown) if unknown else 'none'}",
            ],
            1,
        )
    return (
        [f"every one of {len(entries)} mutants in this shard has a durable record in {output}."],
        0,
    )


# ── the command line ─────────────────────────────────────────────────────────


def _integer(values: Mapping[str, str], flag: str) -> int:
    try:
        return int(values[flag])
    except ValueError as error:
        raise SystemExit(_USAGE) from error


def parse_argv(argv: Sequence[str]) -> Options:
    """Read the command line. Refuses anything it does not recognise.

    Nothing here has a default except the mutation copy's location, which is a
    fixed fact about mutmut rather than a choice, and `--only`, whose absence
    means "run the whole shard". A timeout, a retry bound, a thread budget and a
    worker name are the caller's to state.
    """
    values: dict[str, str] = {}
    remaining = list(argv[1:])
    while remaining:
        argument = remaining.pop(0)
        if argument not in _FLAGS or not remaining:
            raise SystemExit(_USAGE)
        values[argument] = remaining.pop(0)
    if any(flag not in values for flag in _REQUIRED):
        raise SystemExit(_USAGE)
    try:
        timeout_seconds = float(values["--timeout-seconds"])
    except ValueError as error:
        raise SystemExit(_USAGE) from error
    max_attempts = _integer(values, "--max-attempts")
    cpu_threads = _integer(values, "--cpu-threads")
    shard_index = _integer(values, "--shard-index")
    shard_count = _integer(values, "--shard-count")
    if timeout_seconds <= 0 or max_attempts < 1 or cpu_threads < 1:
        # Not thresholds — the caller still chooses all three. A budget that
        # cannot elapse would report a shard of timeouts that measured nothing,
        # and fewer than one attempt or one thread would measure nothing at all.
        raise SystemExit(_USAGE)
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise SystemExit(_USAGE)
    return Options(
        shard=Path(values["--shard"]),
        output=Path(values["--output"]),
        worker=values["--worker"],
        work_dir=Path(values["--work-dir"]),
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        cpu_threads=cpu_threads,
        header=Header(
            shard_index=shard_index,
            shard_count=shard_count,
            # Echoed EXACTLY as given. The aggregator compares this across
            # shards; normalising it here would defeat the one check that
            # notices two workers ran different manifests.
            manifest_sha256=values["--manifest-sha256"],
            commit=values["--commit"],
            dependency_lock_hash=values["--dependency-lock-hash"],
        ),
        mutants_dir=Path(values.get("--mutants-dir", DEFAULT_MUTANTS_DIRECTORY)),
        only=tuple(part for part in values.get("--only", "").split(",") if part.strip()),
    )


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the shard, then prove every mutant in it has a record ON DISK."""
    options = parse_argv(sys.argv if argv is None else argv)
    entries = read_shard(options.shard)
    check_resumable(options.output, options.header)
    copy = MutationCopy.read(options.mutants_dir)
    isolation = Isolation(work_dir=options.work_dir, cpu_threads=options.cpu_threads)
    isolation.prepare()
    policy = Policy(
        worker=options.worker,
        max_attempts=options.max_attempts,
        timeout_seconds=options.timeout_seconds,
    )
    todo = still_to_run(entries, recorded_states(options.output), options.only)
    print(f"worker {options.worker}: {len(todo)} of {len(entries)} mutants to run")

    started = time.monotonic()
    with cancel_on_signals(), record_sink(options.output, options.header) as sink:
        records = run_shard(
            todo,
            copy,
            policy,
            subprocess_runner(copy, policy, isolation),
            Reporting(sink=sink, progress=print),
        )
    elapsed = time.monotonic() - started

    for line in summary(records, elapsed):
        print(line)
    for line in timing_report(records, read_test_durations(options.mutants_dir)):
        print(line)
    lines, code = completeness(entries, options.output)
    print("")
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(cli())
