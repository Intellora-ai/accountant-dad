"""The command-line entrypoints — the only code the merge gate actually invokes.

Every other test in this suite calls a function directly. CI does not. CI runs
`python3 declared_exceptions.py <base> <head>`, and if that dispatch is wrong the
gate dies with a traceback instead of returning a verdict. A crashed gate is
exactly the ambiguous state this whole mechanism exists to remove, so the argv
dispatch and the `__main__` block are load-bearing and get tested as such.

`runpy.run_path(..., run_name="__main__")` executes the real module top level,
in-process, from the real file. Nothing is stubbed except the HTTP call.
"""

from __future__ import annotations

import re
import runpy
import sys
import urllib.request
from pathlib import Path

import declared_exceptions
import expected_checks
import poll_checks
import pytest
from authored_source import running_path
from test_poll_checks_main import FakeResponse

BLOCKED = 1
PASSED = 0

# Escaped: the '.' in the filename is a regex metacharacter, and an unescaped
# any-char would quietly match strings this is meant to reject.
USAGE = re.escape("usage: declared_exceptions.py")

GOOD = "PH-01 | perf | @o | P4 | pipeline exists | nothing to time\n"
EXTRA = "PH-02 | other | @o | P2 | schema exists | no artifact yet\n"

EXIT_ONE_WORKFLOW = """\
name: probe
on:
  push:
jobs:
  p:
    name: perf
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@abc
      - run: |
          echo "NOT IMPLEMENTED"
          exit 1
"""


def write(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def workflows(tmp_path: Path, body: str = EXIT_ONE_WORKFLOW) -> str:
    directory = tmp_path / "wf"
    directory.mkdir(exist_ok=True)
    (directory / "w.yml").write_text(body, encoding="utf-8")
    return str(directory)


def exit_code(excinfo: pytest.ExceptionInfo[SystemExit]) -> int:
    code = excinfo.value.code
    assert isinstance(code, int), f"expected a numeric exit code, got {code!r}"
    return code


# ── declared_exceptions: argv dispatch ───────────────────────────────────────


def test_two_paths_runs_the_shrink_only_ratchet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = write(tmp_path, "base.txt", GOOD)
    head = write(tmp_path, "head.txt", GOOD)
    assert declared_exceptions.main(["prog", base, head]) == PASSED
    assert "no gate was newly excused" in capsys.readouterr().out


def test_two_paths_still_blocks_a_grown_list(tmp_path: Path) -> None:
    # Proves the dispatch reaches the REAL ratchet, not a stub that returns 0.
    base = write(tmp_path, "base.txt", GOOD)
    head = write(tmp_path, "head.txt", GOOD + EXTRA)
    assert declared_exceptions.main(["prog", base, head]) == BLOCKED


def test_cannot_execute_flag_runs_the_real_assertion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = declared_exceptions.main(
        ["prog", "--cannot-execute", workflows(tmp_path), write(tmp_path, "d.txt", GOOD)]
    )
    assert code == PASSED
    assert "cannot execute" in capsys.readouterr().out


def test_cannot_execute_flag_still_blocks_an_executable_placeholder(tmp_path: Path) -> None:
    body = EXIT_ONE_WORKFLOW.replace("          exit 1", "          pytest")
    code = declared_exceptions.main(
        ["prog", "--cannot-execute", workflows(tmp_path, body), write(tmp_path, "d.txt", GOOD)]
    )
    assert code == BLOCKED


def test_the_flag_with_a_missing_argument_is_not_read_as_two_file_paths(tmp_path: Path) -> None:
    # `--cannot-execute <dir>` is three words, the same length as the ratchet
    # form. Falling through would compare a file literally named
    # "--cannot-execute" against a workflows directory and report nonsense.
    #
    # `match=` and not a bare raises: without it, falling through ALSO raises
    # SystemExit — from `parse` failing to open a file called
    # "--cannot-execute" — and a bare assertion cannot tell a usage refusal
    # apart from an accident that happens to abort. It must be the usage text.
    with pytest.raises(SystemExit, match=USAGE):
        declared_exceptions.main(["prog", "--cannot-execute", workflows(tmp_path)])


@pytest.mark.parametrize(
    "argv",
    [
        ["prog"],
        ["prog", "one"],
        ["prog", "a", "b", "c"],
        ["prog", "a", "b", "c", "d"],
    ],
)
def test_argv_it_does_not_understand_aborts_rather_than_guessing(argv: list[str]) -> None:
    with pytest.raises(SystemExit, match=USAGE):
        declared_exceptions.main(argv)


# ── the three `__main__` blocks ──────────────────────────────────────────────


def test_declared_exceptions_module_entrypoint_exits_with_the_ratchet_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = write(tmp_path, "base.txt", GOOD)
    head = write(tmp_path, "head.txt", GOOD + EXTRA)
    monkeypatch.setattr(sys, "argv", ["declared_exceptions.py", base, head])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(running_path(declared_exceptions)), run_name="__main__")
    # Non-zero, so the block cannot be a hardcoded `sys.exit(0)`.
    assert exit_code(excinfo) == BLOCKED


def test_expected_checks_module_entrypoint_prints_every_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["expected_checks.py", workflows(tmp_path)])
    runpy.run_path(str(running_path(expected_checks)), run_name="__main__")
    assert capsys.readouterr().out.splitlines() == ["perf"]


def test_expected_checks_module_entrypoint_refuses_a_missing_directory_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["expected_checks.py"])
    with pytest.raises(SystemExit):
        runpy.run_path(str(running_path(expected_checks)), run_name="__main__")


def poll_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, declared: str) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("MERGE_GATE_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("MERGE_GATE_POLL_TIMEOUT_MINUTES", "1")
    monkeypatch.setenv("MERGE_GATE_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("MERGE_GATE_WORKFLOWS_DIR", workflows(tmp_path))
    monkeypatch.setenv("MERGE_GATE_DECLARED_EXCEPTIONS", write(tmp_path, "d.txt", declared))
    monkeypatch.setattr(sys, "argv", ["poll_checks.py"])


def serve(monkeypatch: pytest.MonkeyPatch, conclusion: str) -> None:
    """Fake ONLY the HTTP call — the narrowest external edge there is."""
    run = {"id": 1, "name": "perf", "status": "completed", "conclusion": conclusion}
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *_a, **_k: FakeResponse({"check_runs": [run]})
    )


def test_poll_checks_module_entrypoint_exits_non_zero_on_an_undeclared_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, "failure")
    poll_environment(monkeypatch, tmp_path, declared="")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(running_path(poll_checks)), run_name="__main__")
    assert exit_code(excinfo) == BLOCKED
    assert "NOT declared a placeholder" in capsys.readouterr().out


def test_poll_checks_module_entrypoint_exits_zero_when_every_gate_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The pair matters: one direction alone would pass against a hardcoded exit.
    serve(monkeypatch, "success")
    poll_environment(monkeypatch, tmp_path, declared="")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(running_path(poll_checks)), run_name="__main__")
    assert exit_code(excinfo) == PASSED
