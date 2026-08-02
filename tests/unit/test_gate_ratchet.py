"""The ratchet is what stops a gate being silently deleted. It gets the hardest tests.

Called in-process so coverage sees it. Two tests also drive the real CLI entry point,
because that is what `merge.yml` actually invokes.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from assert_gates_not_removed import main

TOOLS_CI = Path(__file__).resolve().parents[2] / "tools" / "ci"
SCRIPT = TOOLS_CI / "assert_gates_not_removed.py"

JOB = """\
  {job_id}:
    name: {name}
    runs-on: ubuntu-24.04
    steps:
      - run: exit 0
"""


def workflow(*jobs: tuple[str, str]) -> str:
    body = "".join(JOB.format(job_id=j, name=n) for j, n in jobs)
    return f"name: probe\non:\n  push:\njobs:\n{body}"


def make(directory: Path, *jobs: tuple[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "w.yml").write_text(workflow(*jobs), encoding="utf-8")
    return directory


def check(base: Path, head: Path) -> int:
    return main(["assert_gates_not_removed.py", str(base), str(head)])


def test_identical_sets_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = make(tmp_path / "base", ("a", "alpha"), ("b", "beta"))
    head = make(tmp_path / "head", ("a", "alpha"), ("b", "beta"))
    assert check(base, head) == 0
    assert "no gate removed" in capsys.readouterr().out


def test_adding_a_gate_passes_and_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = make(tmp_path / "base", ("a", "alpha"))
    head = make(tmp_path / "head", ("a", "alpha"), ("b", "beta"))
    assert check(base, head) == 0
    assert "ADDED   beta" in capsys.readouterr().out


def test_removing_a_gate_fails_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = make(tmp_path / "base", ("a", "alpha"), ("b", "beta"))
    head = make(tmp_path / "head", ("a", "alpha"))
    assert check(base, head) == 1
    out = capsys.readouterr().out
    assert "REMOVED beta" in out
    assert "The number may only go up" in out


def test_renaming_is_caught_as_a_removal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A rename is the obvious way around a naive "count went down" check.
    base = make(tmp_path / "base", ("a", "alpha"))
    head = make(tmp_path / "head", ("a", "alpha-renamed"))
    assert check(base, head) == 1
    out = capsys.readouterr().out
    assert "REMOVED alpha" in out
    assert "ADDED   alpha-renamed" in out


def test_swapping_one_gate_for_another_keeps_the_count_but_still_fails(tmp_path: Path) -> None:
    # Counts match at 2-for-2. Only set comparison catches this.
    base = make(tmp_path / "base", ("a", "alpha"), ("b", "beta"))
    head = make(tmp_path / "head", ("a", "alpha"), ("c", "gamma"))
    assert check(base, head) == 1


def test_removing_every_gate_fails(tmp_path: Path) -> None:
    base = make(tmp_path / "base", ("a", "alpha"), ("b", "beta"))
    head = make(tmp_path / "head", ("x", "x"))
    assert check(base, head) == 1


def test_wrong_argument_count_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["assert_gates_not_removed.py", str(tmp_path)])


def test_real_cli_entry_point_passes_on_identical_trees(tmp_path: Path) -> None:
    # merge.yml runs this as a subprocess. Prove that path works, not just main().
    base = make(tmp_path / "base", ("a", "alpha"))
    head = make(tmp_path / "head", ("a", "alpha"))
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-controlled paths
        [sys.executable, str(SCRIPT), str(base), str(head)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(TOOLS_CI), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_real_cli_entry_point_fails_on_removal(tmp_path: Path) -> None:
    base = make(tmp_path / "base", ("a", "alpha"), ("b", "beta"))
    head = make(tmp_path / "head", ("a", "alpha"))
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-controlled paths
        [sys.executable, str(SCRIPT), str(base), str(head)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(TOOLS_CI), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 1
    assert "REMOVED beta" in result.stdout
