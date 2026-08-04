"""Deleting a STEP must be caught. The job-level ratchet cannot see it.

A canary step or an anti-gaming assertion can be removed while the job count
stays identical — every other check still reports "no gate removed". These
tests exist because that hole was real and shipped.
"""

from pathlib import Path

import pytest
from assert_steps_not_removed import main
from expected_steps import MERGE_GATE_CHECK_NAME, cli, step_names

WORKFLOW = """\
name: probe
on:
  push:
jobs:
  alpha:
    name: gate alpha
    runs-on: ubuntu-24.04
    steps:
      - name: first
        run: exit 0
      - name: prove this gate can still fail
        run: exit 0
"""


def write(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "w.yml").write_text(body, encoding="utf-8")
    return directory


def check(base: Path, head: Path) -> int:
    return main(["assert_steps_not_removed.py", str(base), str(head)])


def test_steps_are_reported_as_check_plus_step(tmp_path: Path) -> None:
    names = step_names(str(write(tmp_path, WORKFLOW)))
    assert "gate alpha :: first" in names
    assert "gate alpha :: prove this gate can still fail" in names


def test_unnamed_step_falls_back_to_its_action(tmp_path: Path) -> None:
    body = (
        "name: p\non:\n  push:\njobs:\n  a:\n    name: A\n"
        "    steps:\n      - uses: actions/checkout@abc\n"
    )
    assert step_names(str(write(tmp_path, body))) == {"A :: actions/checkout@abc"}


def test_unnamed_and_actionless_step_falls_back_to_position(tmp_path: Path) -> None:
    body = "name: p\non:\n  push:\njobs:\n  a:\n    name: A\n    steps:\n      - run: exit 0\n"
    assert step_names(str(write(tmp_path, body))) == {"A :: <step 0>"}


def test_merge_gate_excludes_itself(tmp_path: Path) -> None:
    body = (
        f"name: p\non:\n  push:\njobs:\n  m:\n    name: {MERGE_GATE_CHECK_NAME}\n"
        "    steps:\n      - name: x\n        run: exit 0\n"
    )
    assert step_names(str(write(tmp_path, body))) == set()


def test_job_without_steps_is_tolerated(tmp_path: Path) -> None:
    body = "name: p\non:\n  push:\njobs:\n  a:\n    name: A\n"
    assert step_names(str(write(tmp_path, body))) == set()


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        step_names(str(tmp_path))


def test_non_mapping_top_level_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        step_names(str(write(tmp_path, "- a\n- b\n")))


def test_missing_jobs_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        step_names(str(write(tmp_path, "name: p\non:\n  push:\n")))


def test_job_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        step_names(str(write(tmp_path, "name: p\non:\n  push:\njobs:\n  a: 'str'\n")))


def test_non_string_job_name_is_rejected(tmp_path: Path) -> None:
    body = "name: p\non:\n  push:\njobs:\n  a:\n    name: 123\n    steps:\n      - run: exit 0\n"
    with pytest.raises(SystemExit):
        step_names(str(write(tmp_path, body)))


def test_identical_steps_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = write(tmp_path / "base", WORKFLOW)
    head = write(tmp_path / "head", WORKFLOW)
    assert check(base, head) == 0
    assert "no step removed" in capsys.readouterr().out


def test_deleting_a_canary_step_is_blocked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # THE case this module exists for. Job count is unchanged; only a step goes.
    base = write(tmp_path / "base", WORKFLOW)
    without_canary = WORKFLOW.replace(
        "      - name: prove this gate can still fail\n        run: exit 0\n", ""
    )
    head = write(tmp_path / "head", without_canary)
    assert check(base, head) == 1
    out = capsys.readouterr().out
    assert "prove this gate can still fail" in out
    assert "may only be added" in out


def test_adding_a_step_passes_and_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = write(tmp_path / "base", WORKFLOW)
    head = write(tmp_path / "head", WORKFLOW + "      - name: extra\n        run: exit 0\n")
    assert check(base, head) == 0
    assert "ADDED   gate alpha :: extra" in capsys.readouterr().out


def test_renaming_a_step_reads_as_removal(tmp_path: Path) -> None:
    base = write(tmp_path / "base", WORKFLOW)
    head = write(tmp_path / "head", WORKFLOW.replace("- name: first", "- name: renamed"))
    assert check(base, head) == 1


def test_wrong_argument_count_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["assert_steps_not_removed.py", str(tmp_path)])


def test_the_real_workflows_have_their_canaries() -> None:
    real = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    names = step_names(str(real))
    canaries = {n for n in names if "prove this gate can still fail" in n}
    # Every gate that runs real code must carry a hollow-gate canary.
    assert canaries, "no canary steps found in the real workflows"


def test_cli_prints_every_step(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli(["expected_steps.py", str(write(tmp_path, WORKFLOW))])
    assert "gate alpha :: first" in capsys.readouterr().out


def test_cli_rejects_wrong_argument_count() -> None:
    with pytest.raises(SystemExit):
        cli(["expected_steps.py"])
