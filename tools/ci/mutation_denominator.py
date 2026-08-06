#!/usr/bin/env python3
"""The TRUE mutation denominator: every mutant generated, and every one with no verdict.

THE DEFECT THIS EXISTS FOR — F-007, and it is a SILENT one. The score is
`killed / (killed + survived)`. mutmut also produces `segfault`, `timeout`,
`no tests`, `suspicious`, `skipped`, `caught by type check` and `not checked`.
Every one of those is neither killed nor survived, so every one of them leaves
the arithmetic — and the denominator quietly becomes "whatever this run happened
to reach a verdict on" rather than "the tree".

A shrinking denominator makes the PRINTED PERCENTAGE GO UP. That is the whole
danger: the number improves as the measurement gets smaller, and nothing in the
output says which mutants stopped counting or why. `KNOWN_FAILURES.md` F-007
records the trend with its CI runs and commits; those measurements belong to the
commits that produced them and are deliberately not re-quoted here (Law 56).

THE TRANSFORM (Law 53). *"Stop mutmut segfaulting"* is a hard problem living in
`fork()` on macOS, third-party import side effects, and library internals nobody
here owns. *"Given mutmut's own results, which mutants have no verdict, and what
IS the verdict when the same tests are run against the same mutant outside the
fork?"* is a small problem with the same answer. A mutant is activated by one
environment variable that the generated trampoline reads AT CALL TIME
(`mutmut/mutation/trampoline.py`), so activating one needs no fork at all — an
ordinary `exec`'d subprocess does it, and `exec` is exactly what makes the
fork-unsafe call sites safe again.

WHAT THIS MODULE WILL NOT DO.

* It does not print a mutation score. The `mutation` gate owns that formula and
  a second copy of it would be a second number to disagree with (Law 14, 19).
* It invents no threshold. The only judgement it makes is COMPLETENESS -- every
  generated mutant is accounted for, or it is not -- and that is the objective
  itself, not a quality bar somebody chose.
* It never drops a mutant it cannot resolve. An unresolved mutant is printed by
  name with the reason. Silence is the defect being fixed; re-introducing it
  here would be the same bug with a nicer table.

WHERE THE FACTS COME FROM. Nothing here re-derives mutmut's semantics from
memory:

    mutants/<source>.py.meta     exit_code_by_key -- mutmut's own verdict store
    mutants/mutmut-stats.json    tests_by_mangled_function_name -- covering tests
    mutmut.__main__              status_by_exit_code -- exit code to status word

The status table is IMPORTED, never copied. A copy is a second source of truth
that goes stale in silence the next time mutmut adds an exit code, which is the
identical failure mode this module exists to expose.

ONE THING THE IMPORTED TABLE HIDES, AND THIS MODULE DOES NOT. mutmut's table is
a `defaultdict` whose factory returns `"suspicious"`, so an exit code mutmut has
never heard of is reported as if it were a known outcome. Membership is checked
before lookup, and an unknown code is reported as `suspicious` WITH ITS RAW EXIT
CODE attached, so a new failure mode arrives named instead of disguised.

THE FALSE SURVIVOR THIS MODULE HAD, FOUND BY ATTACKING IT AND FIXED HERE.
Activation is a string in an environment variable, and the trampoline's response
to a name it does not recognise is to call the ORIGINAL function
(`trampoline.py`: `if mutated_func is None: return orig_func(...)`). So a mutant
name the mutation copy does not define runs pristine code, every test passes,
pytest exits 0 and the resolver reads that as `survived`. Measured, not
imagined: `probe.calc.x_add__mutmut_9999` -- a name invented for the attack --
resolved to `survived` with exit code 0. Every unresolvable mutant would have
become a survivor, and survivors are the numerator's complement. `resolve` now
requires the mutation copy to REGISTER the mutant before it will believe any
verdict about it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from authored_source import MUTATION_COPY_DIRECTORY

# THE STATUS TABLE IS IMPORTED, NEVER RESTATED. A copy of `status_by_exit_code`
# would be a second source of truth that goes stale in silence the next time
# mutmut adds an exit code -- the identical failure this module exists to
# expose. `mutmut` is pinned in `requirements-ci.txt` and installed by every
# job, and `mutmut.__main__` is already resident under mutation because the
# generated trampoline imports it.
from mutmut.__main__ import status_by_exit_code

#: The two statuses that reach the mutation score. Everything else is excluded
#: from it, which is precisely the population this module refuses to lose.
KILLED = "killed"
SURVIVED = "survived"
SCOREABLE = (KILLED, SURVIVED)

#: mutmut's own fallback word for an exit code it has no entry for.
UNKNOWN_EXIT_CODE_STATUS = "suspicious"

#: The name mutmut writes its per-run test-association cache under, inside the
#: mutation copy. Read-only here.
STATS_FILENAME = "mutmut-stats.json"

#: The environment variable the generated trampoline reads to decide whether to
#: call the original function or the mutant. Read on EVERY call, so setting it
#: for a fresh process is a complete activation.
MUTANT_ENV_VAR = "MUTANT_UNDER_TEST"

#: Proxy lookup is the proven fork-unsafe path behind the local segfaults:
#: `docling` -> `huggingface_hub` -> `httpx` calls `urllib.request.getproxies()`,
#: which on macOS reaches `getproxies_macosx_sysconf()` -- a SystemConfiguration
#: call that is not fork-safe. Both spellings are set because `urllib` reads the
#: lower-case one and several libraries read the upper-case one.
NO_PROXY_ENVIRONMENT = {"no_proxy": "*", "NO_PROXY": "*"}

#: pytest's exit codes, as this module interprets them for one activated mutant.
#: 0 means the covering tests all passed WITH the mutant live -- the mutant is
#: alive. 1 means at least one test failed -- the mutant is dead. Anything else
#: is not a verdict and is reported as such.
PYTEST_ALL_PASSED = 0
PYTEST_TESTS_FAILED = 1

#: The separator mutmut puts between a function's mangled name and its mutant
#: index. `mangled_name_from_mutant_name` in mutmut splits on exactly this.
MUTANT_INDEX_SEPARATOR = "__mutmut_"

#: How a mutated file registers each mutant so the trampoline can dispatch to
#: it, e.g. `mutants_x_clamp__mutmut['x_clamp__mutmut_1'] = x_clamp__mutmut_1`.
#: A name absent from this set is a name the trampoline will ignore, and a
#: mutant the trampoline ignores is a mutant that never ran.
_REGISTRATION = re.compile(r"""^\s*mutants_\S+?\[(['"])(?P<name>.+?)\1\]\s*=""", re.MULTILINE)

_USAGE = (
    "usage: mutation_denominator.py [--mutants-dir DIR] [--resolve]\n"
    "  --mutants-dir DIR  the mutation copy to read (default: mutants)\n"
    "  --resolve          re-run every no-verdict mutant outside the fork"
)


class MutationResultsUnavailableError(Exception):
    """Raised when mutmut's own output cannot be read.

    Never falls back to a partial view. A denominator computed from some of the
    meta files is exactly the silent exclusion this module exists to end, so an
    unreadable results tree is an error and not an empty tally (Law 11).
    """


@dataclass(frozen=True)
class Mutant:
    """One mutant, as mutmut recorded it."""

    #: mutmut's key, e.g. `accountant_dad.confidence.x_score__mutmut_3`.
    name: str
    #: The authored source file it mutates, e.g. `src/accountant_dad/confidence.py`.
    source: str
    #: mutmut's stored exit code. `None` means the mutant was never run.
    exit_code: int | None
    #: mutmut's word for that exit code.
    status: str
    #: True when mutmut has no entry for this exit code and its `defaultdict`
    #: invented `suspicious`. The status is then a guess, and says so.
    status_was_defaulted: bool

    @property
    def has_verdict(self) -> bool:
        """Whether this mutant reaches the score at all."""
        return self.status in SCOREABLE

    def describe(self) -> str:
        """One line naming the mutant, its file, its status and its exit code."""
        code = "none" if self.exit_code is None else str(self.exit_code)
        suffix = " [exit code UNKNOWN TO MUTMUT]" if self.status_was_defaulted else ""
        return f"{self.source}::{self.name}  status={self.status}  exit={code}{suffix}"


@dataclass(frozen=True)
class Resolution:
    """What running one no-verdict mutant's covering tests outside the fork said."""

    mutant: Mutant
    #: `killed`, `survived`, or a word describing why no verdict was reached.
    verdict: str
    #: The exit code of the out-of-fork test run, or `None` when it never ran.
    exit_code: int | None
    #: How many tests mutmut associated with this mutant.
    test_count: int
    #: Present only when `verdict` is neither `killed` nor `survived`.
    reason: str = ""

    @property
    def resolved(self) -> bool:
        """Whether this attempt produced a verdict the score can use."""
        return self.verdict in SCOREABLE

    def describe(self) -> str:
        """One line: the mutant, the verdict reached, and why if none was."""
        code = "none" if self.exit_code is None else str(self.exit_code)
        line = (
            f"{self.mutant.source}::{self.mutant.name}  was={self.mutant.status}  "
            f"now={self.verdict}  exit={code}  tests={self.test_count}"
        )
        return f"{line}  ({self.reason})" if self.reason else line


@dataclass(frozen=True)
class Tally:
    """The counts for one source file, with the excluded population itemised."""

    source: str
    generated: int
    killed: int
    survived: int
    #: Status word to count, for every mutant that reached no verdict.
    no_verdict: Mapping[str, int]

    @property
    def no_verdict_total(self) -> int:
        """How many of this file's mutants never reached the score."""
        return sum(self.no_verdict.values())


def status_for(exit_code: int | None) -> tuple[str, bool]:
    """mutmut's status word for `exit_code`, and whether mutmut had to guess.

    Imported from mutmut rather than restated, so this module cannot disagree
    with the tool whose results it is reading. Membership is tested before
    lookup for two reasons: reading a missing key from a `defaultdict` MUTATES
    it, and the caller is entitled to know that the word was invented.
    """
    if exit_code in status_by_exit_code:
        return str(status_by_exit_code[exit_code]), False
    return UNKNOWN_EXIT_CODE_STATUS, True


def mangled_name(mutant_name: str) -> str:
    """The function key mutmut files a mutant's covering tests under.

    Mirrors `mutmut.__main__.mangled_name_from_mutant_name`. A name without the
    separator is not a mutant name and is refused rather than silently returned
    whole -- a mangled name that is really a mutant name would look up an empty
    test set, and an empty test set reads as "no test covers this".
    """
    head, separator, _ = mutant_name.partition(MUTANT_INDEX_SEPARATOR)
    if not separator:
        raise MutationResultsUnavailableError(
            f"{mutant_name!r} is not a mutant name: it has no {MUTANT_INDEX_SEPARATOR!r}"
        )
    return head


def _meta_files(mutants_dir: Path) -> tuple[Path, ...]:
    if not mutants_dir.is_dir():
        raise MutationResultsUnavailableError(
            f"{mutants_dir} is not a directory. Run `mutmut run` first; a denominator "
            "computed from nothing is not a small denominator, it is no measurement."
        )
    return tuple(sorted(mutants_dir.rglob("*.py.meta")))


def _source_of(meta_path: Path, mutants_dir: Path) -> str:
    """The authored source path a `.meta` file belongs to."""
    return str(meta_path.relative_to(mutants_dir)).removesuffix(".meta")


def _load_json_object(path: Path) -> Mapping[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise MutationResultsUnavailableError(f"{path} could not be read: {error}") from error
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as error:
        raise MutationResultsUnavailableError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise MutationResultsUnavailableError(f"{path} is not a JSON object")
    return {str(key): value for key, value in loaded.items()}


def read_mutants(mutants_dir: Path) -> tuple[Mutant, ...]:
    """Every mutant mutmut recorded, from every `.meta` file under `mutants_dir`.

    This tuple IS the true denominator. Nothing is filtered out of it, including
    mutants that were never run: a mutant mutmut generated and never got to is
    still a mutant the tree contains.
    """
    mutants: list[Mutant] = []
    for meta_path in _meta_files(mutants_dir):
        meta = _load_json_object(meta_path)
        exit_codes = meta.get("exit_code_by_key")
        if not isinstance(exit_codes, dict):
            raise MutationResultsUnavailableError(
                f"{meta_path} has no `exit_code_by_key` mapping, so it records no verdicts"
            )
        source = _source_of(meta_path, mutants_dir)
        for key, value in sorted(exit_codes.items()):
            exit_code = value if isinstance(value, int) else None
            status, defaulted = status_for(exit_code)
            mutants.append(
                Mutant(
                    name=str(key),
                    source=source,
                    exit_code=exit_code,
                    status=status,
                    status_was_defaulted=defaulted,
                )
            )
    if not mutants:
        raise MutationResultsUnavailableError(
            f"no mutants recorded under {mutants_dir}. Every `.meta` file was empty or absent."
        )
    return tuple(mutants)


def read_covering_tests(mutants_dir: Path) -> Mapping[str, tuple[str, ...]]:
    """Which tests mutmut saw execute each mutated function.

    These are the exact tests mutmut's own child process would have run for a
    mutant, so re-running them outside the fork asks mutmut's question rather
    than a similar one.
    """
    stats_path = mutants_dir / STATS_FILENAME
    stats = _load_json_object(stats_path)
    by_function = stats.get("tests_by_mangled_function_name")
    if not isinstance(by_function, dict):
        raise MutationResultsUnavailableError(
            f"{stats_path} has no `tests_by_mangled_function_name`, so no mutant "
            "can be told which tests cover it"
        )
    covering: dict[str, tuple[str, ...]] = {}
    for function, tests in by_function.items():
        names = tests if isinstance(tests, list) else []
        covering[str(function)] = tuple(sorted(str(test) for test in names))
    return covering


def without_verdict(mutants: Iterable[Mutant]) -> tuple[Mutant, ...]:
    """Every mutant the score never saw. The population this module exists for."""
    return tuple(mutant for mutant in mutants if not mutant.has_verdict)


def tally_by_source(mutants: Iterable[Mutant]) -> tuple[Tally, ...]:
    """Per source file: how many mutants exist, and what became of each."""
    generated: Counter[str] = Counter()
    killed: Counter[str] = Counter()
    survived: Counter[str] = Counter()
    excluded: dict[str, Counter[str]] = {}

    for mutant in mutants:
        generated[mutant.source] += 1
        if mutant.status == KILLED:
            killed[mutant.source] += 1
        elif mutant.status == SURVIVED:
            survived[mutant.source] += 1
        else:
            excluded.setdefault(mutant.source, Counter())[mutant.status] += 1

    return tuple(
        Tally(
            source=source,
            generated=generated[source],
            killed=killed[source],
            survived=survived[source],
            no_verdict=dict(excluded.get(source, Counter())),
        )
        for source in sorted(generated)
    )


def _pytest_command(python: str, tests: Sequence[str]) -> list[str]:
    """mutmut's own pytest arguments, as an argv list, with ONE stated difference.

    `-x -q -p no:randomly -p no:random-order` are mutmut's
    (`PytestRunner._pytest_args_regular_run`). A shuffled order would make a
    mutant's verdict depend on the seed, and a verdict that changes between runs
    of one commit is not a measurement.

    THE DIFFERENCE, stated rather than glossed: mutmut's child sorts the covering
    tests by their recorded duration, fastest first; the caller's order is used
    here. That cannot change any VERDICT -- with `-x`, a mutant is killed iff at
    least one covering test fails, and every order finds such a test if one
    exists -- but it does change how long a kill takes to find. Measured on this
    repository at `564bb1d`: startup and collection cost 4s of a 150s resolution
    for a 61-test mutant, so the tests themselves are 97% of the cost and the
    order in which a failing one is reached is the only lever there is.
    """
    return [
        python,
        "-m",
        "pytest",
        "--rootdir=.",
        "--tb=native",
        "-x",
        "-q",
        "-p",
        "no:randomly",
        "-p",
        "no:random-order",
        *tests,
    ]


def run_covering_tests(
    mutant: Mutant,
    tests: Sequence[str],
    mutants_dir: Path,
    python: str | None = None,
) -> int:
    """Activate one mutant and run its covering tests in a FRESH process.

    THE WHOLE POINT IS `exec`, NOT `fork`. mutmut forks a child per mutant and
    inherits an already-initialised interpreter, which is what makes a
    fork-unsafe call site crash. `subprocess.run` forks AND execs, so the child
    starts from a clean interpreter and the unsafe state does not exist to be
    inherited.

    The working directory is the mutation copy, so pytest's `pythonpath`
    resolves against the INSTRUMENTED tree exactly as it does under mutmut. The
    same three entries are also stated explicitly on `PYTHONPATH`, because an
    exec'd process inherits none of the `sys.path` surgery mutmut performs in
    its parent (`mutmut.__main__.setup_source_paths`).
    """
    interpreter = sys.executable if python is None else python
    environment = dict(os.environ)
    environment.update(NO_PROXY_ENVIRONMENT)
    environment[MUTANT_ENV_VAR] = mutant.name
    root = mutants_dir.resolve()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root / "src"), str(root / "tools" / "ci"), str(root)]
    )
    completed = subprocess.run(  # noqa: S603 - argv list, no shell, interpreter is a path
        _pytest_command(interpreter, tests),
        check=False,
        cwd=root,
        env=environment,
        capture_output=True,
    )
    return completed.returncode


#: The narrow I/O edge. Everything above is arithmetic over files; this is the
#: one place a process is started, and it is the only thing a test fakes.
TestRun = Callable[[Mutant, Sequence[str]], int]


def verdict_from_exit_code(exit_code: int) -> tuple[str, str]:
    """The verdict an out-of-fork test run's exit code carries, and why.

    Only two codes are verdicts. Everything else -- a collection error, a
    crash, an interpreter that could not start -- is reported by its number
    rather than folded into either column.
    """
    if exit_code == PYTEST_ALL_PASSED:
        return SURVIVED, ""
    if exit_code == PYTEST_TESTS_FAILED:
        return KILLED, ""
    status, defaulted = status_for(exit_code)
    unknown = " (mutmut has no entry for this code)" if defaulted else ""
    return status, f"pytest exited {exit_code}, which is not a verdict{unknown}"


def registered_mutants(source_file: Path) -> frozenset[str]:
    """Every mutant name a mutated file actually registers with its trampoline.

    Read off the generated file rather than trusted from the meta store,
    because they are two different records and the whole point is to notice
    when they disagree.
    """
    try:
        text = source_file.read_text(encoding="utf-8")
    except OSError as error:
        raise MutationResultsUnavailableError(
            f"{source_file} could not be read, so no mutant in it can be verified: {error}"
        ) from error
    return frozenset(match.group("name") for match in _REGISTRATION.finditer(text))


def generated_function(mutant_name: str) -> str:
    """The generated function name inside the mutated file, e.g. `x_add__mutmut_1`."""
    return mutant_name.rpartition(".")[2]


def resolve(
    mutants: Iterable[Mutant],
    covering: Mapping[str, tuple[str, ...]],
    mutants_dir: Path,
    run: TestRun,
) -> tuple[Resolution, ...]:
    """Reach a verdict on each mutant by running its covering tests out of the fork.

    TWO REFUSALS, both of which would otherwise become fabricated survivors.

    A mutant mutmut recorded no covering tests for is not resolvable this way.
    Calling it survived because no test failed, when no test ran, is a verdict
    nobody measured (Law 24).

    A mutant the mutation copy does not register is not resolvable either: the
    trampoline silently falls back to the original function for a name it does
    not know, so the tests would pass against pristine code and exit 0. Proving
    the name is registered first is what stops "the mutation copy is stale" from
    reading as "the mutant is alive".
    """
    resolutions: list[Resolution] = []
    known_by_source: dict[str, frozenset[str]] = {}
    for mutant in mutants:
        if mutant.source not in known_by_source:
            known_by_source[mutant.source] = registered_mutants(mutants_dir / mutant.source)
        if generated_function(mutant.name) not in known_by_source[mutant.source]:
            resolutions.append(
                Resolution(
                    mutant=mutant,
                    verdict="not in mutation copy",
                    exit_code=None,
                    test_count=0,
                    reason=(
                        f"{mutants_dir / mutant.source} registers no such mutant, so activating "
                        "it would run the ORIGINAL function and every test would pass"
                    ),
                )
            )
            continue
        tests = covering.get(mangled_name(mutant.name), ())
        if not tests:
            resolutions.append(
                Resolution(
                    mutant=mutant,
                    verdict="no tests",
                    exit_code=None,
                    test_count=0,
                    reason="mutmut recorded no test covering this function",
                )
            )
            continue
        exit_code = run(mutant, tests)
        verdict, reason = verdict_from_exit_code(exit_code)
        resolutions.append(
            Resolution(
                mutant=mutant,
                verdict=verdict,
                exit_code=exit_code,
                test_count=len(tests),
                reason=reason,
            )
        )
    return tuple(resolutions)


def with_resolutions(
    mutants: Iterable[Mutant], resolutions: Iterable[Resolution]
) -> tuple[Mutant, ...]:
    """Every mutant, with each out-of-fork verdict substituted for mutmut's.

    A DERIVED VIEW, and the data says so: a substituted mutant carries the exit
    code of the run that produced it, not the one that crashed. `tally_by_source`
    over this tuple is therefore the same arithmetic over a better-informed
    population rather than a second implementation of it (Law 14) -- which is
    what makes a per-module TRUE-survivor column possible without a second
    counter that could disagree with the first.
    """
    verdicts = {resolution.mutant.name: resolution for resolution in resolutions}
    substituted: list[Mutant] = []
    for mutant in mutants:
        resolution = verdicts.get(mutant.name)
        if resolution is None:
            substituted.append(mutant)
            continue
        substituted.append(
            replace(mutant, status=resolution.verdict, exit_code=resolution.exit_code)
        )
    return tuple(substituted)


def _tally_lines(tallies: Sequence[Tally]) -> list[str]:
    lines = [
        f"{'source':52} {'generated':>9} {'killed':>7} {'survived':>8} {'NO VERDICT':>10}",
        "-" * 90,
    ]
    for tally in tallies:
        itemised = ", ".join(
            f"{status}={count}" for status, count in sorted(tally.no_verdict.items())
        )
        detail = f"  {itemised}" if itemised else ""
        lines.append(
            f"{tally.source:52} {tally.generated:>9} {tally.killed:>7} "
            f"{tally.survived:>8} {tally.no_verdict_total:>10}{detail}"
        )
    return lines


def _resolution_lines(mutants: Sequence[Mutant], resolutions: Sequence[Resolution]) -> list[str]:
    counts: Counter[str] = Counter(resolution.verdict for resolution in resolutions)
    lines = ["", "RESOLVED OUTSIDE THE FORK", "-" * 90]
    lines += [f"  {verdict:32} {count}" for verdict, count in sorted(counts.items())]

    # The per-module TRUE columns: mutmut's verdicts, with every re-run mutant's
    # own answer put in its place. `survived` here is a mutant that is genuinely
    # ALIVE and was reported as no-verdict -- a real hole the score never saw.
    resolved = tally_by_source(with_resolutions(mutants, resolutions))
    lines.append("")
    lines.append("PER MODULE AFTER RESOLUTION - `survived` is a TRUE survivor")
    lines += _tally_lines(resolved)

    unresolved = [resolution for resolution in resolutions if not resolution.resolved]
    lines.append("")
    lines.append(f"still no verdict after resolution: {len(unresolved)}")
    lines += [f"  {resolution.describe()}" for resolution in unresolved]
    return lines


def report(
    mutants: Sequence[Mutant],
    resolutions: Sequence[Resolution] | None = None,
) -> list[str]:
    """The whole finding as text: the true denominator, and every silent mutant.

    Deliberately prints no percentage. The `mutation` gate owns the score; this
    owns the population the score is taken over.
    """
    tallies = tally_by_source(mutants)
    silent = without_verdict(mutants)
    lines = _tally_lines(tallies)
    lines.append("-" * 90)
    lines.append(
        f"{'TOTAL':52} {len(mutants):>9} "
        f"{sum(t.killed for t in tallies):>7} {sum(t.survived for t in tallies):>8} "
        f"{len(silent):>10}"
    )
    lines.append("")
    lines.append(f"TRUE DENOMINATOR (mutants generated) : {len(mutants)}")
    lines.append(f"reached the score                    : {len(mutants) - len(silent)}")
    lines.append(f"EXCLUDED FROM THE SCORE, ITEMISED    : {len(silent)}")
    lines += [f"  {mutant.describe()}" for mutant in silent]
    if resolutions is not None:
        lines += _resolution_lines(mutants, resolutions)
    return lines


@dataclass(frozen=True)
class Options:
    """What the command line asked for."""

    mutants_dir: Path
    resolve: bool


def parse_argv(argv: Sequence[str]) -> Options:
    """Read the command line. Refuses anything it does not recognise."""
    mutants_dir = Path(MUTATION_COPY_DIRECTORY)
    should_resolve = False
    remaining = list(argv[1:])
    while remaining:
        argument = remaining.pop(0)
        if argument == "--resolve":
            should_resolve = True
        elif argument == "--mutants-dir":
            if not remaining:
                raise SystemExit(_USAGE)
            mutants_dir = Path(remaining.pop(0))
        else:
            raise SystemExit(_USAGE)
    return Options(mutants_dir=mutants_dir, resolve=should_resolve)


def accounted_for(mutants: Sequence[Mutant], resolutions: Sequence[Resolution] | None) -> int:
    """How many generated mutants ended with a verdict, resolution included."""
    reached = sum(1 for mutant in mutants if mutant.has_verdict)
    if resolutions is None:
        return reached
    return reached + sum(1 for resolution in resolutions if resolution.resolved)


def cli(argv: Sequence[str] | None = None) -> int:
    """Print the denominator, and fail when any mutant is still unaccounted for.

    The exit code answers COMPLETENESS, never quality: 0 means every generated
    mutant has a verdict, 1 means at least one does not. No threshold is applied
    and none is invented -- one unaccounted mutant is one silent exclusion.
    """
    options = parse_argv(sys.argv if argv is None else argv)
    mutants = read_mutants(options.mutants_dir)
    resolutions: tuple[Resolution, ...] | None = None
    if options.resolve:
        covering = read_covering_tests(options.mutants_dir)
        resolutions = resolve(
            without_verdict(mutants),
            covering,
            options.mutants_dir,
            lambda mutant, tests: run_covering_tests(mutant, tests, options.mutants_dir),
        )
    for line in report(mutants, resolutions):
        print(line)

    settled = accounted_for(mutants, resolutions)
    missing = len(mutants) - settled
    if missing:
        print(
            f"\nBLOCKED - {missing} of {len(mutants)} mutants have NO VERDICT. "
            "The denominator above is the true one; the score is taken over less than it."
        )
        return 1
    print(f"\nevery one of {len(mutants)} mutants has a verdict. The denominator is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
