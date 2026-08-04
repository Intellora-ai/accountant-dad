"""Deleting a STEP must be caught. The job-level ratchet cannot see it.

A canary step or an anti-gaming assertion can be removed while the job count
stays identical — every other check still reports "no gate removed". These
tests exist because that hole was real and shipped.
"""

from pathlib import Path

import pytest
from assert_steps_not_removed import main, split_pair
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


def two_gates(alpha_steps: str, beta_steps: str) -> str:
    """Two named checks whose step lists are written out in full.

    Spelled literally rather than produced by `.replace()` on a template: a
    fixture built by string surgery can silently stop expressing the case it
    was named for, and then the test passes for the wrong reason.
    """
    return (
        "name: probe\non:\n  push:\njobs:\n"
        f"  alpha:\n    name: gate alpha\n    runs-on: ubuntu-24.04\n    steps:{alpha_steps}\n"
        f"  beta:\n    name: gate beta\n    runs-on: ubuntu-24.04\n    steps:{beta_steps}\n"
    )


PLACEHOLDER_STEPS = "\n      - name: not implemented\n        run: exit 1"
NO_STEPS = " []"
BETA_ONE = "\n      - name: untouched\n        run: exit 0"
BETA_TWO = BETA_ONE + "\n      - name: brand new\n        run: exit 0"


def test_a_placeholder_may_be_replaced_by_real_steps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole reason the exception exists.

    Implementing a placeholder gate means DELETING its `not implemented` step.
    The first version of the ratchet forbade that, which froze all 14 declared
    placeholders permanently. This is the case that must pass.
    """
    base = write(tmp_path / "base", two_gates(PLACEHOLDER_STEPS, BETA_ONE))
    real = "\n      - name: the real assertion\n        run: exit 0"
    head = write(tmp_path / "head", two_gates(real, BETA_ONE))
    assert check(base, head) == 0
    assert "UPGRADED gate alpha :: not implemented" in capsys.readouterr().out


def test_a_placeholder_may_not_be_deleted_leaving_the_gate_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Deleting the placeholder and adding nothing leaves a door unguarded.

    This is the half of the rule that keeps it a ratchet rather than a licence:
    the exception buys an UPGRADE, never a plain deletion.
    """
    base = write(tmp_path / "base", two_gates(PLACEHOLDER_STEPS, BETA_ONE))
    head = write(tmp_path / "head", two_gates(NO_STEPS, BETA_ONE))
    assert check(base, head) == 1
    out = capsys.readouterr().out
    assert "REMOVED gate alpha :: not implemented" in out
    assert "gained no step to replace it" in out


def test_a_placeholder_removal_cannot_be_laundered_through_another_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ANTI-GAMING. The exception is per-check, not global.

    Without this, deleting `alpha`'s placeholder would be excused by unrelated
    growth in `beta` — a removal paid for with someone else's work.
    """
    base = write(tmp_path / "base", two_gates(PLACEHOLDER_STEPS, BETA_ONE))
    head = write(tmp_path / "head", two_gates(NO_STEPS, BETA_TWO))
    assert check(base, head) == 1
    out = capsys.readouterr().out
    assert "REMOVED gate alpha :: not implemented" in out
    assert "ADDED   gate beta :: brand new" in out


def test_a_real_step_is_still_blocked_even_when_the_gate_grows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ANTI-GAMING. The exception is by NAME, not by "something was added".

    Otherwise any step could be deleted by bundling a decoy addition into the
    same check — exactly how a canary would disappear.
    """
    base = write(tmp_path / "base", WORKFLOW)
    head = write(
        tmp_path / "head",
        WORKFLOW.replace(
            "      - name: prove this gate can still fail\n        run: exit 0\n",
            "      - name: decoy\n        run: exit 0\n",
        ),
    )
    assert check(base, head) == 1
    assert "REMOVED gate alpha :: prove this gate can still fail" in capsys.readouterr().out


def test_split_pair_keeps_a_separator_inside_the_step_label() -> None:
    """Partition once from the LEFT. A step label may contain ` :: `; a check
    name may not, so the check must win the first split."""
    assert split_pair("gate alpha :: a :: b") == ("gate alpha", "a :: b")
    assert split_pair("no separator here") == ("no separator here", "")


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
