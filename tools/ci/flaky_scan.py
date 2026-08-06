#!/usr/bin/env python3
"""Measure and enumerate non-determinism in the test suite.

WHY THIS EXISTS. mutmut's statistics phase runs the whole suite ONCE to time each
test, and it does so with `-x`. One red test there ends the phase and mutmut calls
`exit(1)`, so **no mutant is ever scored** — the measurement for every mutant is
destroyed by a single test. Both halves are read off mutmut 3.7.0's own source
rather than inferred, and both are pinned by `tests/unit/test_suite_determinism.py`
so this file cannot drift away from the thing it claims to reproduce:

    mutmut/__main__.py:453  pytest_args = ["-x", "-q", "-p", "no:randomly",
                                           "-p", "no:random-order"]
    mutmut/__main__.py:760  if collect_stats_exit_code != 0: ... exit(1)

`-p no:randomly` is in that list, so test ORDER is fixed during the stats phase and
ordering is NOT a source of variation there. Any variation that remains is a test
that behaves differently on two runs of identical code.

TWO MEASUREMENTS, because one alone proves nothing:

  repeat   Runs the suite N times under the stats phase's exact arguments and
           environment, and counts how many runs went red. This is the direct
           measurement of the quantity that matters. Zero failures in N runs is an
           UPPER BOUND, never proof of zero, and the bound is reported with it.

  scan     Reads every test module's syntax tree and names each place a test reaches
           for something that can differ between two runs of the same code: a clock,
           a random source, the network, the environment, the working directory, a
           downloaded model, a subprocess, a thread. Re-running cannot find a source
           that did not happen to fire; reading can.

FAITHFULNESS, and where it stops. mutmut invokes `pytest.main()` IN PROCESS
(`__main__.py:445`), and the stats phase is the first such call in a fresh
interpreter — so one fresh subprocess per run is the faithful model of it, and that
is what `repeat` does. What `repeat` does NOT reproduce: the stats phase runs from
mutmut's `mutants/` copy of the tree, against source rewritten with trampolines.
A failure that needs that copy to exist is invisible here, and `--target` exists so
the same measurement can be pointed at one, once one is built.

Reads and runs only. Writes nothing except the JSON file it is asked for.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess  # runs pytest by full interpreter path, argv list, shell=False
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Copied character for character from mutmut 3.7.0 `_pytest_args_regular_run`,
# `mutmut/__main__.py:453`. `test_suite_determinism.py` reads the installed
# mutmut and fails if this list stops matching it.
STATS_PYTEST_ARGS: tuple[str, ...] = ("-x", "-q", "-p", "no:randomly", "-p", "no:random-order")

# What mutmut exports before calling the stats runner, `mutmut/__main__.py:753-757`.
# `MUTMUT_DEPENDENCY_DEPTH` carries `Config.dependency_tracking_depth`, whose default
# is -1 (`mutmut/configuration.py:155`).
#
# `MUTANT_UNDER_TEST` is NOT inert here. `tests/unit/test_gate_ratchet.py:161`
# branches on its presence, so a run without it exercises a different path than the
# stats phase does. Setting it is the faithful choice, and `--no-mutmut-env` exists
# to measure the difference rather than to assume there is none.
STATS_ENVIRONMENT: tuple[tuple[str, str], ...] = (
    ("MUTANT_UNDER_TEST", "stats"),
    ("PY_IGNORE_IMPORTMISMATCH", "1"),
    ("MUTMUT_DEPENDENCY_DEPTH", "-1"),
)

# F-016: a CoreFoundation proxy lookup after a raw fork() segfaults on macOS. These
# two make the lookup never happen, so the crash cannot confound a measurement that
# is about the test suite rather than about libSystem.
FORK_SAFETY_ENVIRONMENT: tuple[tuple[str, str], ...] = (
    ("no_proxy", "*"),
    ("NO_PROXY", "*"),
)

#: `3900 passed` is two words: the count and the outcome. Fewer is not a tally.
_COUNT_AND_OUTCOME = 2

_SUMMARY_OUTCOMES: tuple[str, ...] = (
    "passed",
    "failed",
    "error",
    "errors",
    "skipped",
    "xfailed",
    "xpassed",
    "deselected",
)

# ── what counts as a source of non-determinism ────────────────────────────
#
# Every entry is a DOTTED NAME as written after import aliases are resolved, and
# every one of them can return a different value on two runs of identical code.
# The categories are the ones named in the task: clock, random seed, filesystem,
# network, environment variable, model download, process/thread state.
#
# BARE MODULE NAMES ARE IN HERE ON PURPOSE. A test that does
# `monkeypatch.setattr(time, "sleep", ...)` never writes `time.sleep` as a dotted
# call, so a scanner that only matches calls sees a suite with no clock in it and
# reports zero. That is the false negative this whole file exists to avoid, and it
# was a real one: before bare names were added, `tests/unit/test_poll_checks_main.py`
# — which patches BOTH the clock and `urlopen` — produced no clock and no network
# finding at all.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "clock": (
        "time",
        "time.time",
        "time.time_ns",
        "time.monotonic",
        "time.monotonic_ns",
        "time.perf_counter",
        "time.perf_counter_ns",
        "time.process_time",
        "time.sleep",
        "datetime.datetime.now",
        "datetime.datetime.today",
        "datetime.datetime.utcnow",
        "datetime.date.today",
    ),
    "random": (
        "random",
        "secrets",
        "uuid.uuid1",
        "uuid.uuid4",
        "os.urandom",
        "numpy.random",
    ),
    "network": (
        "socket",
        "socketserver",
        "urllib.request",
        "urllib.error",
        "requests",
        "httpx",
        "http.client",
        # A test that SERVES is as exposed as one that fetches: it binds a real
        # port, and the bind can lose a race that no amount of re-reading the
        # test would reveal. Added after the first scan reported zero network
        # sources for `tests/unit/test_evidence_bootstrap.py`, which starts a
        # real `ThreadingHTTPServer` on loopback.
        "http.server",
    ),
    "environment": (
        "os.environ",
        "os.getenv",
        "os.putenv",
        "os.unsetenv",
        "platform.system",
        "platform.machine",
        "platform.processor",
        "platform.python_version",
        "sys.platform",
        "sys.version_info",
    ),
    "filesystem": (
        "os.getcwd",
        "os.chdir",
        "os.listdir",
        "pathlib.Path.cwd",
        "pathlib.Path.home",
        "tempfile",
        "glob.glob",
        "glob.iglob",
    ),
    "process": (
        "subprocess",
        "multiprocessing",
        "threading",
        "concurrent.futures",
        "os.fork",
        "os.system",
        "os.spawnv",
    ),
    "hash_order": ("hash",),
}

# Importing any of these pulls a downloaded model, a native runtime, or both, and
# what it resolves to depends on a cache that is not in this repository.
MODEL_MODULES: tuple[str, ...] = (
    "docling",
    "docling_core",
    "docling_parse",
    "torch",
    "torchvision",
    "transformers",
    "paddleocr",
    "paddle",
    "huggingface_hub",
    "rapidocr",
)


@dataclass(frozen=True)
class Finding:
    """One place a test reaches for something that can differ between two runs."""

    path: str
    line: int
    scope: str
    category: str
    name: str

    def key(self) -> tuple[str, str, str, str]:
        """Identity WITHOUT the line number, so moving code does not look like a change."""
        return (self.path, self.scope, self.category, self.name)

    def as_json(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "line": self.line,
            "scope": self.scope,
            "category": self.category,
            "name": self.name,
        }


@dataclass(frozen=True)
class RunResult:
    """One complete run of the suite under the stats phase's conditions."""

    index: int
    exit_code: int
    seconds: float
    counts: dict[str, int]
    failed: tuple[str, ...]

    @property
    def red(self) -> bool:
        return self.exit_code != 0

    def as_json(self) -> dict[str, str | int | float | bool | list[str] | dict[str, int]]:
        return {
            "index": self.index,
            "exit_code": self.exit_code,
            "seconds": round(self.seconds, 2),
            "counts": dict(self.counts),
            "failed": list(self.failed),
            "red": self.red,
        }


# ── static scan ───────────────────────────────────────────────────────────


class _Resolver(ast.NodeVisitor):
    """Resolve every dotted call/attribute in one module against its imports.

    An import alias is the whole difficulty: `import numpy as np` then `np.random`
    is the same thing as `numpy.random`, and a scanner that matches source text
    misses it. Names are resolved through the alias map before they are matched, so
    the alias cannot hide the source.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.scope: str = "<module>"
        self.findings: list[Finding] = []
        self.imported_models: list[Finding] = []

    # imports ------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                # `import a.b as c` binds `c` to the module `a.b`.
                self.aliases[alias.asname] = alias.name
            else:
                # `import a.b` binds `a`, and `a` means `a` — NOT `a.b`. Binding it
                # to `a.b` made `urllib.request.urlopen` resolve to
                # `urllib.request.request.urlopen`, which matches nothing, so every
                # network call through a dotted import was invisible. Proven with a
                # planted `urllib.request.urlopen(...)` that the scanner did not
                # report; `test_suite_determinism.py` keeps it proven.
                root = alias.name.split(".")[0]
                self.aliases[root] = root
            self._note_model(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level:
            # A relative import cannot reach a third-party clock or model.
            self.generic_visit(node)
            return
        for alias in node.names:
            bound = alias.asname or alias.name
            self.aliases[bound] = f"{module}.{alias.name}" if module else alias.name
        self._note_model(module, node.lineno)
        self.generic_visit(node)

    def _note_model(self, module: str, line: int) -> None:
        root = module.split(".")[0]
        if root in MODEL_MODULES:
            self.imported_models.append(
                Finding(self.path, line, self.scope, "model_download", root)
            )

    # scopes -------------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._in_scope(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._in_scope(node.name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._in_scope(node.name, node)

    def _in_scope(self, name: str, node: ast.AST) -> None:
        outer = self.scope
        self.scope = name if outer == "<module>" else f"{outer}.{name}"
        self.generic_visit(node)
        self.scope = outer

    # uses ---------------------------------------------------------------
    def visit_Attribute(self, node: ast.Attribute) -> None:
        dotted = _dotted(node)
        if dotted is not None:
            # The whole chain is plain names, so `time.sleep` is the complete
            # description of this site. Descending would also record the `time`
            # underneath it and report one call as two sources.
            self._record(dotted, node.lineno)
            return
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self._record(node.id, node.lineno)
        self.generic_visit(node)

    def _record(self, dotted: str | None, line: int) -> None:
        if dotted is None:
            return
        resolved = self.resolve(dotted)
        match = _longest_match(resolved)
        if match is not None:
            category, name = match
            self.findings.append(Finding(self.path, line, self.scope, category, name))

    def resolve(self, dotted: str) -> str:
        head, _, rest = dotted.partition(".")
        target = self.aliases.get(head)
        if target is None:
            return dotted
        return f"{target}.{rest}" if rest else target


def _longest_match(resolved: str) -> tuple[str, str] | None:
    """The most specific category entry this name falls under, or None.

    LONGEST wins, and that is not a detail. `time` is a clock entry and so is
    `time.sleep`; a first-match-wins loop would report whichever the dictionary
    happened to yield first, so the same code would be described differently
    depending on insertion order. Ties cannot occur — a name appears once.
    """
    best: tuple[str, str] | None = None
    for category, names in CATEGORIES.items():
        for name in names:
            matches = resolved == name or resolved.startswith(f"{name}.")
            if matches and (best is None or len(name) > len(best[1])):
                best = (category, name)
    return best


def _dotted(node: ast.AST) -> str | None:
    """`a.b.c` as a string, or None when the base is not a plain name."""
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def test_files(root: Path) -> list[Path]:
    """Every test module, in a stable order."""
    return sorted(p for p in (root / "tests").rglob("*.py") if "__pycache__" not in p.parts)


@dataclass(frozen=True)
class ResolvedCall:
    """One call site, named after import aliases are resolved, with its arity."""

    path: str
    line: int
    name: str
    positional_arguments: int


def resolved_calls(root: Path, *, prefixes: Sequence[str]) -> list[ResolvedCall]:
    """Every call in the test suite whose resolved name starts with one of `prefixes`.

    `scan` cannot answer the questions this answers, and the difference matters.
    `scan` reports that a file touches `numpy.random`; that is not a fact about
    whether two runs agree. `default_rng(SEED)` and `default_rng()` are the same
    three words to a name matcher and opposite facts about determinism, and the
    ARGUMENT COUNT is the entire signal. So it is read off the call node itself.
    """
    calls: list[ResolvedCall] = []
    for path in test_files(root):
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        resolver = _Resolver(relative)
        resolver.visit(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            if dotted is None:
                continue
            resolved = resolver.resolve(dotted)
            if any(resolved == p or resolved.startswith(f"{p}.") for p in prefixes):
                calls.append(ResolvedCall(relative, node.lineno, resolved, len(node.args)))
    return sorted(calls, key=lambda c: (c.path, c.line, c.name))


def scan(root: Path) -> list[Finding]:
    """Every non-determinism source reachable from the test suite, deduplicated."""
    seen: dict[tuple[str, str, str, str], Finding] = {}
    for path in test_files(root):
        relative = path.relative_to(root).as_posix()
        resolver = _Resolver(relative)
        resolver.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for finding in [*resolver.findings, *resolver.imported_models]:
            seen.setdefault(finding.key(), finding)
    return sorted(seen.values(), key=lambda f: (f.path, f.scope, f.category, f.name))


# ── repeated execution ────────────────────────────────────────────────────


def stats_environment(*, mutmut_env: bool) -> dict[str, str]:
    """The environment the stats phase runs under."""
    env = dict(os.environ)
    env.update(dict(FORK_SAFETY_ENVIRONMENT))
    if mutmut_env:
        env.update(dict(STATS_ENVIRONMENT))
    else:
        for name, _ in STATS_ENVIRONMENT:
            env.pop(name, None)
    return env


def parse_counts(output: str) -> dict[str, int]:
    """`3900 passed, 11 skipped` off pytest's terminal summary line."""
    counts: dict[str, int] = {}
    for line in output.splitlines():
        stripped = line.strip().strip("=").strip()
        if " in " not in stripped and "no tests ran" not in stripped:
            continue
        for chunk in stripped.split(","):
            words = chunk.strip().split()
            if (
                len(words) >= _COUNT_AND_OUTCOME
                and words[0].isdigit()
                and words[1] in _SUMMARY_OUTCOMES
            ):
                counts[words[1]] = int(words[0])
    return counts


def parse_failed(output: str) -> tuple[str, ...]:
    """Every node id pytest named as FAILED or ERROR, in the order it named them."""
    found: list[str] = []
    for line in output.splitlines():
        for marker in ("FAILED ", "ERROR "):
            if line.startswith(marker):
                node = line[len(marker) :].split(" - ")[0].strip()
                if node and node not in found:
                    found.append(node)
    return tuple(found)


def run_once(
    index: int,
    *,
    root: Path,
    python: Path,
    targets: Sequence[str],
    mutmut_env: bool,
) -> RunResult:
    """One suite run under the stats phase's arguments. Never raises on a red run."""
    argv = [str(python), "-m", "pytest", *STATS_PYTEST_ARGS, *targets]
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - full interpreter path, argv list, shell=False
        argv,
        cwd=root,
        env=stats_environment(mutmut_env=mutmut_env),
        capture_output=True,
        text=True,
        check=False,
    )
    seconds = time.monotonic() - started
    output = completed.stdout + completed.stderr
    return RunResult(
        index=index,
        exit_code=completed.returncode,
        seconds=seconds,
        counts=parse_counts(output),
        failed=parse_failed(output),
    )


def upper_bound(runs: int, failures: int) -> float | None:
    """The 95% upper bound on the per-run failure rate when nothing went red.

    Exact, from the binomial: the largest p for which observing zero failures in
    `runs` trials still has probability 0.05 is `1 - 0.05 ** (1 / runs)`. Reported
    ONLY for a zero-failure result, because that is the case where the observed rate
    of 0 is not the answer and quoting it alone would be a false claim.
    """
    if runs <= 0 or failures:
        return None
    return 1.0 - float(0.05 ** (1.0 / runs))


@dataclass(frozen=True)
class Plan:
    """Everything one repeated measurement needs, in one value.

    A plan rather than eight parameters so the conditions of a measurement can be
    written down, passed around and printed as a single thing. A number whose
    conditions travel separately from it is the shape of Law 56's failure.
    """

    root: Path
    python: Path
    runs: int
    targets: Sequence[str] = ()
    mutmut_env: bool = True
    journal: Path | None = None


def repeat(plan: Plan) -> list[RunResult]:
    """Run the suite `plan.runs` times, writing each result to disk as it lands.

    Written after EVERY run, not at the end: a measurement that only exists once
    the loop finishes is lost to any interruption, and the loop is hours long.
    """
    results: list[RunResult] = []
    for index in range(1, plan.runs + 1):
        result = run_once(
            index,
            root=plan.root,
            python=plan.python,
            targets=plan.targets,
            mutmut_env=plan.mutmut_env,
        )
        results.append(result)
        verdict = "RED " + ", ".join(result.failed) if result.red else "green"
        print(
            f"run {index}/{plan.runs}  exit={result.exit_code}  "
            f"{result.seconds:.1f}s  {result.counts}  {verdict}",
            flush=True,
        )
        if plan.journal is not None:
            _write_journal(plan.journal, plan, results)
    return results


def _write_journal(journal: Path, plan: Plan, results: Sequence[RunResult]) -> None:
    """The partial measurement, on disk, with the conditions it was taken under."""
    journal.write_text(
        json.dumps(
            {
                "runs_attempted": len(results),
                "runs_requested": plan.runs,
                "failures": sum(1 for r in results if r.red),
                "mutmut_env": plan.mutmut_env,
                "targets": list(plan.targets),
                "pytest_args": list(STATS_PYTEST_ARGS),
                "results": [r.as_json() for r in results],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def report(results: Sequence[RunResult]) -> str:
    """The measurement, with its sample size and its bound. Never a bare rate."""
    attempted = len(results)
    failures = sum(1 for r in results if r.red)
    lines = [
        f"runs attempted : {attempted}",
        f"runs red       : {failures}",
    ]
    if attempted:
        lines.append(f"observed rate  : {failures}/{attempted} = {failures / attempted:.4f}")
    bound = upper_bound(attempted, failures)
    if bound is not None:
        lines.append(
            f"95% upper bound: {bound:.4f} per run "
            f"(zero failures in {attempted} runs is an UPPER BOUND, not proof of zero)"
        )
    for result in results:
        if result.red:
            named = ", ".join(result.failed) or "no node id parsed"
            lines.append(f"  run {result.index} RED: {named}")
    return "\n".join(lines)


# ── entry point ───────────────────────────────────────────────────────────


def _grouped(findings: Sequence[Finding]) -> Iterator[tuple[str, list[Finding]]]:
    for category in [*CATEGORIES, "model_download"]:
        matching = [f for f in findings if f.category == category]
        if matching:
            yield category, matching


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=("repeat", "scan"))
    parser.add_argument("--runs", type=int, default=10, help="repeat: how many suite runs")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--json", type=Path, default=None, help="results, rewritten every run")
    parser.add_argument("--target", action="append", default=[], help="repeat: pytest path")
    parser.add_argument(
        "--no-mutmut-env",
        action="store_true",
        help="repeat: drop MUTANT_UNDER_TEST and friends, to measure what they change",
    )
    args = parser.parse_args(argv)

    if args.mode == "scan":
        findings = scan(args.root)
        for category, matching in _grouped(findings):
            print(f"\n── {category} ── {len(matching)}")
            for finding in matching:
                print(f"  {finding.path}:{finding.line}  {finding.scope}  {finding.name}")
        print(f"\ntotal distinct sources: {len(findings)}")
        if args.json is not None:
            body = json.dumps([f.as_json() for f in findings], indent=2)
            args.json.write_text(body + "\n", encoding="utf-8")
        return 0

    results = repeat(
        Plan(
            root=args.root,
            python=args.python,
            runs=args.runs,
            targets=args.target,
            mutmut_env=not args.no_mutmut_env,
            journal=args.json,
        )
    )
    print()
    print(report(results))
    return 1 if any(r.red for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
