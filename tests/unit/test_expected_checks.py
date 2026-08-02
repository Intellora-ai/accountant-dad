"""The parser decides what the merge gate expects. If it under-reports, gates vanish silently."""

from pathlib import Path

import pytest
from expected_checks import MERGE_GATE_CHECK_NAME, check_names, cli

WORKFLOW = """\
name: probe
on:
  push:
jobs:
  alpha:
    name: gate alpha
    runs-on: ubuntu-24.04
    steps:
      - run: exit 0
"""


def write(directory: Path, filename: str, body: str) -> None:
    (directory / filename).write_text(body, encoding="utf-8")


def test_reads_the_name_key_not_the_job_id(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", WORKFLOW)
    assert check_names(str(tmp_path)) == {"gate alpha"}


def test_falls_back_to_job_id_when_name_is_absent(tmp_path: Path) -> None:
    write(
        tmp_path,
        "a.yml",
        "name: p\non:\n  push:\njobs:\n  bare-job:\n"
        "    runs-on: x\n    steps:\n      - run: exit 0\n",
    )
    assert check_names(str(tmp_path)) == {"bare-job"}


def test_merge_gate_excludes_itself(tmp_path: Path) -> None:
    write(
        tmp_path,
        "m.yml",
        f"name: m\non:\n  push:\njobs:\n  mg:\n    name: {MERGE_GATE_CHECK_NAME}\n"
        f"    runs-on: x\n    steps:\n      - run: exit 0\n",
    )
    # Waiting on your own check run never terminates.
    assert check_names(str(tmp_path)) == set()


def test_unions_across_every_workflow_file(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", WORKFLOW)
    other = WORKFLOW.replace("gate alpha", "gate beta").replace("alpha:", "beta:")
    write(tmp_path, "b.yaml", other)
    assert check_names(str(tmp_path)) == {"gate alpha", "gate beta"}


def test_reads_both_yml_and_yaml_extensions(tmp_path: Path) -> None:
    write(tmp_path, "only.yaml", WORKFLOW)
    assert check_names(str(tmp_path)) == {"gate alpha"}


def test_empty_directory_is_an_error_not_an_empty_set(tmp_path: Path) -> None:
    # Returning an empty set here would make the merge gate expect nothing and
    # pass trivially — the exact failure this must never have.
    with pytest.raises(SystemExit):
        check_names(str(tmp_path))


def test_top_level_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", "- just\n- a\n- list\n")
    with pytest.raises(SystemExit):
        check_names(str(tmp_path))


def test_missing_jobs_mapping_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", "name: p\non:\n  push:\n")
    with pytest.raises(SystemExit):
        check_names(str(tmp_path))


def test_job_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", "name: p\non:\n  push:\njobs:\n  broken: 'a string'\n")
    with pytest.raises(SystemExit):
        check_names(str(tmp_path))


def test_malformed_yaml_raises_rather_than_silently_reporting_fewer_gates(tmp_path: Path) -> None:
    write(tmp_path, "a.yml", "name: p\n  bad indent: [unclosed\n")
    with pytest.raises(Exception):  # noqa: B017 - any failure beats a silent undercount
        check_names(str(tmp_path))


def test_the_real_repository_workflows_parse(tmp_path: Path) -> None:  # noqa: ARG001
    repo_workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    names = check_names(str(repo_workflows))
    assert "merge gate" not in names
    assert "lint" in names
    assert len(names) > 1


def test_non_string_job_name_is_rejected(tmp_path: Path) -> None:
    # A YAML name of `123` parses as an int. Silently str()-ing it would produce
    # an expected check name that can never match a real one.
    write(tmp_path, "a.yml", "name: p\non:\n  push:\njobs:\n  j:\n    name: 123\n")
    with pytest.raises(SystemExit):
        check_names(str(tmp_path))


def test_cli_prints_every_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "a.yml", WORKFLOW)
    cli(["expected_checks.py", str(tmp_path)])
    assert "gate alpha" in capsys.readouterr().out


def test_cli_rejects_wrong_argument_count() -> None:
    with pytest.raises(SystemExit):
        cli(["expected_checks.py"])
