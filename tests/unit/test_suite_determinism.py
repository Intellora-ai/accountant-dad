"""The suite must give the same answer twice, and this is what enforces it.

WHY A WHOLE FILE FOR THIS. mutmut's statistics phase runs the suite once, with `-x`,
and calls `exit(1)` if that run is not green. So ONE test that behaves differently on
two runs of identical code destroys the measurement for every mutant — not degrades
it, destroys it. The 2% unscoreable cap turns that into a loud refusal rather than a
fabricated score, which is why F-029 exists as an entry instead of as a number in a
report. Both halves of that mechanism are read off mutmut's own source below rather
than trusted, because a gate built on a remembered API is a gate that expires.

`-p no:randomly` is in that same argument list, so test ORDER is fixed during the
stats phase. Ordering is therefore NOT a candidate explanation for variation there,
and this file does not pretend otherwise.

WHAT THIS FILE CAN AND CANNOT DO. Re-running the suite can only find a source of
variation that happened to fire. Reading it finds sources that did not fire today and
will fire on a busier machine. So the enforcement here is STRUCTURAL: every place a
test reaches for a clock, a random draw, a socket, the environment, a shared
directory, a subprocess or a thread is enumerated and frozen. A new one fails this
file, which is the point — the reviewer is then made to say why it is safe.

The measurement that accompanies it lives in `tools/ci/flaky_scan.py repeat`, which
runs the suite N times under exactly these conditions and reports the failure rate
with its sample size and its bound.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import flaky_scan
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: A reason shorter than this is not a reason. Long enough to force a sentence,
#: short enough that an honest one-liner fits.
SHORTEST_USABLE_REASON = 20

#: One entry per (test module, category, source). File-level rather than
#: function-level on purpose: the risk this guards is per-file-per-mechanism — does
#: THIS file seed its generator, does THIS file patch its clock — and a second
#: `uuid4()` in a file that already uses `uuid4()` the same way carries no new risk,
#: while the first `uuid4()` in a file that never had one does.
#:
#: Every entry carries the reason it is deterministic anyway. An entry with no reason
#: is a defect waiting to be discovered (CLAUDE.md Law 54 applied to this file).
FROZEN_INVENTORY: dict[tuple[str, str, str], str] = {
    # ── the enforcement and measurement tools, added 2026-08-06 ──────────
    # Both run a fixed argv with no shell and no network, and both assert on the
    # RESULT rather than on timing. Deterministic for the same reason a unit test
    # calling a pure function is: same input, same output, every run.
    ("tests/unit/test_engineering_method_enforced.py", "process", "subprocess"): (
        "runs the repository's own hook with a fixed argv to watch it REFUSE; the "
        "assertion is the exit code and the message, neither of which can vary"
    ),
    ("tests/unit/test_mutation_denominator.py", "process", "subprocess"): (
        "runs mutmut over a 4-mutant fixture project as the ORACLE for the "
        "out-of-fork resolver; mutmut's verdicts on a fixed tree are fixed"
    ),
    ("tests/unit/test_mutation_denominator.py", "environment", "os.environ"): (
        "sets MUTANT_UNDER_TEST, which is how a mutant is activated at all; the "
        "value is written by the test, never read from the machine"
    ),
    # ── uuid4: the VALUE is never asserted on ────────────────────────────
    # Each of these builds a bare `uuid.UUID` for one purpose: to prove the typed
    # identifier is REQUIRED and the bare one is refused. Which uuid it is cannot
    # change the outcome, because the outcome is a rejection.
    ("tests/unit/test_clarification.py", "random", "uuid.uuid4"): (
        "a bare uuid built only to be refused where a typed id belongs"
    ),
    ("tests/unit/test_evidence.py", "random", "uuid.uuid4"): (
        "a bare uuid built only to be refused where a DocumentId belongs"
    ),
    ("tests/unit/test_execution.py", "random", "uuid.uuid4"): (
        "a bare uuid built only to be refused where an ExecutionId belongs"
    ),
    ("tests/unit/test_identity.py", "random", "uuid.uuid4"): (
        "bare uuids built to prove two typed ids are not interchangeable"
    ),
    ("tests/unit/test_input_engine_measurement.py", "random", "uuid.uuid4"): (
        "a document id whose value never reaches an assertion"
    ),
    ("tests/unit/test_input_engine_measurement_redteam.py", "random", "uuid.uuid4"): (
        "a document id whose value never reaches an assertion"
    ),
    ("tests/unit/test_validation.py", "random", "uuid.uuid4"): (
        "a bare uuid shared between two fields to prove they are distinct types"
    ),
    # ── numpy: every draw is seeded, and a separate test proves it ───────
    ("tests/unit/test_input_engine_cleaner.py", "random", "numpy.random"): (
        "every draw goes through default_rng(SEED); "
        "test_every_random_draw_in_the_suite_is_seeded proves the argument is there"
    ),
    ("tests/unit/test_input_engine_cleaner_redteam.py", "random", "numpy.random"): (
        "every draw goes through default_rng(SEED); "
        "test_every_random_draw_in_the_suite_is_seeded proves the argument is there"
    ),
    # ── clock and network: neutralised, never called ─────────────────────
    ("tests/unit/test_poll_checks_main.py", "clock", "time"): (
        "monkeypatched: setattr(time, 'sleep', lambda _: None). The real clock is "
        "never read; test_no_test_reads_a_real_clock proves no dotted clock call exists"
    ),
    ("tests/unit/test_poll_checks_main.py", "network", "urllib.request"): (
        "monkeypatched: setattr(urllib.request, 'urlopen', ...). No socket is opened"
    ),
    ("tests/unit/test_poll_checks_main.py", "network", "urllib.error"): (
        "URLError is raised as a value by a stub; the module performs no I/O here"
    ),
    ("tests/unit/test_cli_entrypoints.py", "network", "urllib.request"): (
        "monkeypatched: setattr(urllib.request, 'urlopen', ...). No socket is opened"
    ),
    # ── a real server on loopback, measured rather than argued ───────────
    ("tests/unit/test_evidence_bootstrap.py", "network", "http.server"): (
        "a real ThreadingHTTPServer on 127.0.0.1:0. Bound to an EPHEMERAL port, so it "
        "cannot collide with another process; loopback only, so no name resolution and "
        "no proxy lookup. tools/evidence/bootstrap.py uses http.client directly rather "
        "than urlopen, so the macOS CoreFoundation proxy path (F-016) is never entered"
    ),
    ("tests/unit/test_evidence_bootstrap.py", "process", "threading"): (
        "one daemon thread serving the fixture above, shut down and joined in the "
        "fixture's finally. No state is shared with the test body"
    ),
    # ── subprocess and environment: deliberate, and the point of the test ─
    ("tests/unit/test_gate_ratchet.py", "process", "subprocess"): (
        "runs the real CLI entry point on a temporary tree, which is what the test is "
        "for — a gate proven through its own command line, not through an import"
    ),
    ("tests/unit/test_gate_ratchet.py", "environment", "os.environ"): (
        "reads MUTANT_UNDER_TEST so the subprocess it spawns inherits what mutmut set. "
        "Environment-DEPENDENT by design, and it is the one place in the suite where "
        "running inside the mutation run differs from running outside it"
    ),
    # ── hash(): comparisons only, so PYTHONHASHSEED cannot reach them ────
    ("tests/unit/test_execution.py", "hash_order", "hash"): (
        "asserts hash(a) == hash(b) within one process. No hash VALUE is written down, "
        "so per-process hash randomisation cannot change the outcome"
    ),
    ("tests/unit/test_state.py", "hash_order", "hash"): (
        "asserts a StrEnum member hashes as its own text, within one process. "
        "No hash VALUE is written down"
    ),
    # ── the shared temporary directory ───────────────────────────────────
    ("tests/unit/test_input_engine_pipeline.py", "filesystem", "tempfile"): (
        "NamedTemporaryFile(delete=False), written and unlinked inside the test. It "
        "does not READ the directory, so another process's files cannot reach it"
    ),
    ("tests/unit/test_input_engine_pipeline_redteam.py", "filesystem", "tempfile"): (
        "KNOWN DEFECT, PROVEN FLAKY — see test_only_the_known_defect_snapshots_the_"
        "shared_temporary_directory below. This file does not merely write to the "
        "shared temp dir, it READS it and asserts nothing new appeared"
    ),
}

#: The one test that snapshots the SHARED system temporary directory and asserts
#: nothing new appeared in it, which is an assertion about every other process on the
#: host rather than about this repository's code.
#:
#: Reproduced at `564bb1d`, LOCAL ONLY — NOT AUTHORITATIVE, by running the node alone
#: and then again with a single writer dropping one `.pdf` into that directory:
#:
#:     alone                     1 passed
#:     one other writer          1 failed
#:       AssertionError: assert {PosixPath('/...T/tmpnoise-0.pdf')} == set()
#:       tests/unit/test_input_engine_pipeline_redteam.py:648
#:
#: It also fails on its own, with nothing injected. Measured at `b4d163b`,
#: LOCAL ONLY — NOT AUTHORITATIVE, on a 10-core machine running sibling copies of
#: this same suite:
#:
#:     heavy concurrent suite load      8 red / 200 runs   =  4.00%
#:     light load                       1 red / 150 runs   =  0.67%
#:
#: The rate tracking the load is the causal evidence, and the file named in a natural
#: failure — `/var/folders/.../T/tmp7f4rkmcq.pdf` — is a `NamedTemporaryFile` name,
#: which is what THIS pipeline's `_document_on_disk` produces. So the writer is
#: another process running this same suite. An intrinsic leak would fail every time,
#: not four times in a hundred.
#:
#: FIXED 2026-08-06, and this record is now EMPTY because the guard demanded it be.
#:
#: The offender took `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`, so
#: both the pipeline's own `NamedTemporaryFile` and the sweep land in a private
#: directory. The check KEPT its full strength — it still catches a leak of ANY file,
#: not merely the one handed to the parser — and stopped observing the machine.
#:
#: Falsified in three directions before it was believed: passes clean; passes with six
#: `.pdf` files planted in the shared directory, which is the exact trigger that used
#: to redden it; and still goes RED when a genuine leak is injected into `tmp_path`.
#: Re-measured under the stats phase's own flags with three processes churning `.pdf`
#: files: **0 red in 60**, against **8 in 200 (4.00%)** at `b4d163b`.
#:
#: THE SET IS A RATCHET AND IT IS NOW EMPTY. A test that snapshots the shared
#: directory fails the guard below — there is no longer any grandfathered entry to
#: hide behind. That is the strongest state this record can be in, and it was reached
#: by the guard failing on its own author's fix rather than by anyone remembering.
KNOWN_SHARED_TEMPDIR_READERS: frozenset[str] = frozenset()

#: Categories whose findings must never be a dotted CALL in a test — only a bare
#: module reference, which is what a monkeypatch target looks like.
CALL_FREE_CATEGORIES: tuple[str, ...] = ("clock",)


def _mutmut_source() -> str:
    """mutmut's own dispatcher text, located without importing `__main__`."""
    spec = importlib.util.find_spec("mutmut.__main__")
    assert spec is not None and spec.origin is not None, "mutmut is not installed"
    return Path(spec.origin).read_text(encoding="utf-8")


def _plant(root: Path, body: str) -> Path:
    """A throwaway test module, so the scanner is run against real syntax."""
    planted = root / "tests" / "test_planted.py"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text(body, encoding="utf-8")
    return planted


# ── what the statistics phase actually does ───────────────────────────────


def test_the_statistics_phase_still_stops_at_the_first_failure() -> None:
    """R1, read off mutmut rather than remembered.

    If mutmut ever drops `-x`, or stops exiting on a non-zero stats run, then one red
    test no longer destroys the whole measurement and the premise of this file is
    gone. That is a good outcome and it must still be NOTICED, because everything
    here is calibrated to the harsh behaviour.
    """
    source = _mutmut_source()

    assert '"-x", "-q", "-p", "no:randomly", "-p", "no:random-order"' in source, (
        "mutmut's stats-phase pytest arguments have changed; re-read "
        "_pytest_args_regular_run and re-derive what a single red test costs"
    )
    assert "if collect_stats_exit_code != 0:" in source
    assert "failed to collect stats. runner returned" in source


def test_the_scanner_reproduces_the_statistics_phase_arguments_exactly() -> None:
    """A measurement taken under different arguments is a measurement of something else."""
    source = _mutmut_source()
    rendered = ", ".join(f'"{argument}"' for argument in flaky_scan.STATS_PYTEST_ARGS)

    assert rendered in source, (
        f"flaky_scan runs pytest with {flaky_scan.STATS_PYTEST_ARGS}, which no longer "
        "appears in mutmut's source. The reproduction has drifted from the thing it "
        "reproduces, so its numbers no longer describe the stats phase"
    )
    assert "-x" in flaky_scan.STATS_PYTEST_ARGS, (
        "without -x the reproduction is more forgiving than the gate it models, "
        "and would report green for a suite the gate rejects"
    )


# ── the detector must be able to fire ─────────────────────────────────────


@pytest.mark.parametrize(
    ("category", "body"),
    [
        ("clock", "import time\n\n\ndef test_x():\n    time.time()\n"),
        ("random", "import random\n\n\ndef test_x():\n    random.random()\n"),
        ("network", "import socket\n\n\ndef test_x():\n    socket.socket()\n"),
        ("environment", "import os\n\n\ndef test_x():\n    os.environ['HOME']\n"),
        ("filesystem", "import os\n\n\ndef test_x():\n    os.getcwd()\n"),
        ("process", "import threading\n\n\ndef test_x():\n    threading.Thread()\n"),
        ("hash_order", "def test_x():\n    hash('a')\n"),
        ("model_download", "import torch\n\n\ndef test_x():\n    pass\n"),
    ],
)
def test_the_scanner_reports_a_planted_source_in_every_category(
    tmp_path: Path, category: str, body: str
) -> None:
    """A detector that cannot fire is a green light wired to nothing (CLAUDE.md J.3)."""
    _plant(tmp_path, body)

    found = {finding.category for finding in flaky_scan.scan(tmp_path)}

    assert category in found, f"a planted {category} source was not reported: {body!r}"


def test_a_dotted_import_does_not_rebind_its_own_root(tmp_path: Path) -> None:
    """Permanent regression test for a real false negative (CLAUDE.md Law 3).

    `import a.b` binds the name `a`, and `a` means `a` — NOT `a.b`. Binding it to the
    full dotted path made `urllib.request.urlopen` resolve to
    `urllib.request.request.urlopen`, and every network call reached through a dotted
    import went unreported.

    THE ASSERTION HERE IS DELIBERATELY NOT THE `urllib` ONE, and that is the whole
    lesson. Once `urllib.request` became a category entry in its own right, the
    MANGLED name `urllib.request.request.urlopen` still prefix-matches it, so the
    doubling is invisible from that direction — the first version of this test was
    written that way and SURVIVED the bug being put back.

    A SIBLING submodule discriminates, because doubling sends the name somewhere that
    matches nothing at all. Measured on the real scanner, both ways:

        import os.path  +  os.environ[...]      fixed -> os.environ reported
                                                buggy -> os.path.environ, NOTHING
    """
    _plant(
        tmp_path,
        "import os.path\nimport urllib.request\n\n\n"
        'def test_x():\n    os.environ["HOME"]\n    urllib.request.urlopen("http://x")\n',
    )

    found = {(f.category, f.name) for f in flaky_scan.scan(tmp_path)}

    assert ("environment", "os.environ") in found, (
        "`os.environ` reached from a file that also does `import os.path` was not "
        "reported. The alias map has regressed to binding a dotted import's ROOT to "
        "the full dotted path, which silently relocates every sibling attribute"
    )
    assert ("network", "urllib.request") in found


def test_a_module_reference_is_seen_even_when_it_is_never_called(tmp_path: Path) -> None:
    """The second false negative, and the more dangerous one.

    A test that neutralises the clock writes `monkeypatch.setattr(time, "sleep", ...)`
    and never writes `time.sleep` as a call. A scanner matching only calls reports a
    suite with no clock in it — which reads as proof of determinism and is instead
    proof that the scanner is blind.
    """
    _plant(
        tmp_path,
        "import time\n\n\ndef test_x(monkeypatch):\n    monkeypatch.setattr(time, 's', 1)\n",
    )

    found = {(f.category, f.name) for f in flaky_scan.scan(tmp_path)}

    assert ("clock", "time") in found, "a bare module reference to the clock was not reported"


# ── properties the suite must hold ────────────────────────────────────────


def test_no_test_reads_a_real_clock() -> None:
    """A test may hold the clock module to neutralise it. It may not ask it the time.

    `datetime.now()` in a test is the classic case: it passes for months and then
    fails once at a month boundary, in someone else's pull request.
    """
    offenders = [
        finding
        for finding in flaky_scan.scan(REPO_ROOT)
        if finding.category in CALL_FREE_CATEGORIES and "." in finding.name
    ]

    assert offenders == [], "a test calls a real clock: " + "; ".join(
        f"{f.path}:{f.line} {f.scope} -> {f.name}" for f in offenders
    )


def test_every_random_draw_in_the_suite_is_seeded() -> None:
    """An unseeded draw makes the suite a different suite on every run.

    Checked at the CALL, not at the import. `numpy.random` appearing in a file says
    nothing about determinism; `default_rng()` against `default_rng(SEED)` says
    everything, and the two differ only by an argument.
    """
    draws = flaky_scan.resolved_calls(
        REPO_ROOT, prefixes=("numpy.random", "random", "secrets", "os.urandom")
    )
    assert draws, "no random draws found at all — the extractor has stopped seeing them"

    unseeded = [
        call
        for call in draws
        if call.name != "numpy.random.default_rng" or call.positional_arguments < 1
    ]

    named = "; ".join(f"{c.path}:{c.line} {c.name}/{c.positional_arguments}" for c in unseeded)

    assert unseeded == [], (
        f"a random draw is not seeded, so two runs of this suite are two different suites: {named}"
    )


def test_only_the_known_defect_snapshots_the_shared_temporary_directory() -> None:
    """Reading the machine's temp directory is an assertion about other processes.

    `tempfile.gettempdir()` is ONE directory for the whole host. A test that lists it
    and asserts nothing new appeared is asserting that no other process on the machine
    created a file during its run — which is not a property of this repository's code,
    and is false the moment two suites run at once.

    Two directions, both load-bearing:

    1. A SECOND test doing this fails here. That is the class fixed, not the instance
       (CLAUDE.md J.9).
    2. When the known one is fixed this ALSO fails, because the entry will describe
       nothing. That forces the record above to be deleted rather than left behind as
       a stale exception for someone to trust later.
    """
    readers = {
        call.path
        for call in flaky_scan.resolved_calls(REPO_ROOT, prefixes=("tempfile.gettempdir",))
    }

    assert readers == KNOWN_SHARED_TEMPDIR_READERS, (
        "the set of tests reading the SHARED temporary directory changed.\n"
        f"  expected exactly: {sorted(KNOWN_SHARED_TEMPDIR_READERS)}\n"
        f"  found:            {sorted(readers)}\n"
        "Reading the machine's temp directory asserts that no OTHER process on the "
        "host writes there, which is not a property of this repository. Measured at "
        "`b4d163b`: 8 red in 200 under load. Give the test `tmp_path`, or "
        "`monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))` when the code under "
        "test creates the file itself.\n"
        "The allowed set is EMPTY and stays empty; there is no entry to hide behind."
    )


def test_the_non_determinism_inventory_is_exactly_this() -> None:
    """Every source the suite reaches for, frozen, each with the reason it is safe.

    A ratchet in both directions. An ADDED source fails, so nobody introduces a clock
    or an unseeded draw without saying why it is safe. A REMOVED source fails too, so
    the reasons above cannot quietly describe code that is no longer there.
    """
    found = {(f.path, f.category, f.name) for f in flaky_scan.scan(REPO_ROOT)}
    frozen = set(FROZEN_INVENTORY)

    added = sorted(found - frozen)
    removed = sorted(frozen - found)

    assert not added, (
        "a test reached for a NEW source of non-determinism. One test that differs "
        "between two runs destroys the mutation measurement for every mutant "
        "(mutmut runs the stats phase with -x). Add it to FROZEN_INVENTORY WITH the "
        f"reason it is deterministic anyway, or remove it:\n  {added}"
    )
    assert not removed, (
        "FROZEN_INVENTORY names a source the suite no longer has. Delete the entry — "
        f"a reason attached to nothing is a reason nobody can check:\n  {removed}"
    )


def test_every_frozen_entry_says_why_it_is_safe() -> None:
    """An entry with an empty reason is an exception nobody ever justified."""
    unexplained = sorted(
        key
        for key, reason in FROZEN_INVENTORY.items()
        if len(reason.strip()) < SHORTEST_USABLE_REASON
    )

    assert unexplained == [], f"frozen without a reason: {unexplained}"


def test_this_files_own_planting_helper_produces_parseable_python(tmp_path: Path) -> None:
    """The planted modules above must be real Python, or every detector test is hollow.

    A syntax error in a planted body makes `ast.parse` raise, the scan never runs, and
    the parametrised tests above would fail loudly rather than silently — but only if
    the helper writes what it was given. This pins that.
    """
    planted = _plant(tmp_path, "import time\n\n\ndef test_x():\n    time.time()\n")

    assert ast.parse(planted.read_text(encoding="utf-8")) is not None
    assert planted.parent.name == "tests", "scan() only reads tests/, so the plant must land there"
