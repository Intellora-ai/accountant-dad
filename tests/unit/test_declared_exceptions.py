"""The declared-exceptions mechanism, tested where it is dangerous.

Every test asserts the RESULT, not that a function ran. The dangerous direction
is always the lenient one: a bug that excuses a real failure is worse than a bug
that blocks a clean pull request, so the lenient path gets the most tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from declared_exceptions import Declared, assert_cannot_execute, assert_shrink_only, parse
from poll_checks import verdict

BLOCKED = 1
PASSED = 0

GOOD = "PH-01 | perf | @o | P4 | pipeline exists | nothing to time\n"


def _write(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


# ── parsing: an unknown placeholder is forbidden ─────────────────────────────


def test_parses_all_six_fields(tmp_path: Path) -> None:
    got = parse(_write(tmp_path, "d.txt", "# c\n\n" + GOOD))
    assert got == {"perf": Declared("PH-01", "@o", "P4", "pipeline exists", "nothing to time")}


def test_preserves_the_u00b7_separators_byte_for_byte(tmp_path: Path) -> None:
    # The legacy check name contains U+00B7. A parser that normalised it would
    # silently stop matching the real Check Run name.
    line = "PH-01 | typecheck · lint · tests · build | @o | NOW | PR lands | legacy\n"
    assert "typecheck · lint · tests · build" in parse(_write(tmp_path, "d.txt", line))


@pytest.mark.parametrize(
    "line",
    [
        "perf\n",  # no fields at all
        "PH-01 | perf | @o | P4 | pipeline exists\n",  # five: no blocker
        "PH-01 | perf | @o | P4\n",  # four: no removal condition
        "PH-01 | perf |  | P4 | pipeline exists | nothing\n",  # empty owner
        "PH-01 | perf | @o |  | pipeline exists | nothing\n",  # empty milestone
        "PH-01 | perf | @o | P4 |  | nothing\n",  # empty removal condition
        " | perf | @o | P4 | pipeline exists | nothing\n",  # empty id
    ],
)
def test_a_line_missing_any_field_is_a_parse_error_not_a_default(tmp_path: Path, line: str) -> None:
    # "Unknown placeholders are forbidden." The lenient reading would excuse a
    # gate nobody could justify excusing.
    with pytest.raises(SystemExit):
        parse(_write(tmp_path, "d.txt", line))


def test_a_duplicate_check_name_is_rejected(tmp_path: Path) -> None:
    body = GOOD + "PH-02 | perf | @o | P4 | x | y\n"
    with pytest.raises(SystemExit):
        parse(_write(tmp_path, "d.txt", body))


def test_a_duplicate_id_is_rejected(tmp_path: Path) -> None:
    # IDs must be unique and never reused, or a reference means two things.
    body = GOOD + "PH-01 | other | @o | P4 | x | y\n"
    with pytest.raises(SystemExit):
        parse(_write(tmp_path, "d.txt", body))


def test_a_missing_file_aborts_rather_than_excusing_nothing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse(str(tmp_path / "absent.txt"))


# ── cannot execute ───────────────────────────────────────────────────────────

_DECL = {"perf": Declared("PH-01", "@o", "P4", "pipeline exists", "nothing to time")}


def _workflows(tmp_path: Path, body: str) -> str:
    directory = tmp_path / "wf"
    directory.mkdir(exist_ok=True)
    (directory / "w.yml").write_text(body, encoding="utf-8")
    return str(directory)


_EXIT_ONE = """
jobs:
  p:
    name: perf
    steps:
      - uses: actions/checkout@abc
      - run: |
          echo "NOT IMPLEMENTED"
          exit 1
"""


def test_an_exit_one_only_job_is_accepted(tmp_path: Path) -> None:
    assert assert_cannot_execute(_workflows(tmp_path, _EXIT_ONE), _DECL) == PASSED


def test_a_declared_job_that_can_actually_run_is_blocked(tmp_path: Path) -> None:
    # The whole point: "placeholder" must be a property, not a claim. A job that
    # executes could emit a pass, which this list would then excuse.
    body = _EXIT_ONE.replace("          exit 1", "          pytest")
    assert assert_cannot_execute(_workflows(tmp_path, body), _DECL) == BLOCKED


def test_a_declared_job_with_two_run_steps_is_blocked(tmp_path: Path) -> None:
    body = _EXIT_ONE + "      - run: echo second\n"
    assert assert_cannot_execute(_workflows(tmp_path, body), _DECL) == BLOCKED


def test_a_declared_name_with_no_matching_job_is_blocked(tmp_path: Path) -> None:
    # Dead weight at best, a typo shadowing a live gate at worst.
    ghost = {"ghost": Declared("PH-99", "@o", "P4", "x", "y")}
    assert assert_cannot_execute(_workflows(tmp_path, _EXIT_ONE), ghost) == BLOCKED


# ── the shrink-only ratchet ──────────────────────────────────────────────────


def test_adding_an_exception_is_blocked(tmp_path: Path) -> None:
    base = _write(tmp_path, "base.txt", GOOD)
    head = _write(tmp_path, "head.txt", GOOD + "PH-02 | b | @o | P2 | x | y\n")
    assert assert_shrink_only(base, head) == BLOCKED


def test_removing_an_exception_is_allowed_because_it_is_promotion(tmp_path: Path) -> None:
    base = _write(tmp_path, "base.txt", GOOD + "PH-02 | b | @o | P2 | x | y\n")
    head = _write(tmp_path, "head.txt", GOOD)
    assert assert_shrink_only(base, head) == PASSED


def test_swapping_one_name_for_another_is_blocked(tmp_path: Path) -> None:
    # Same count, so a length check would pass this. The set difference catches it.
    base = _write(tmp_path, "base.txt", GOOD)
    head = _write(tmp_path, "head.txt", "PH-01 | other | @o | P4 | x | y\n")
    assert assert_shrink_only(base, head) == BLOCKED


def test_bootstrap_allows_a_base_with_no_file_at_all(tmp_path: Path) -> None:
    # Can only happen once: the pull request that introduces the mechanism.
    head = _write(tmp_path, "head.txt", GOOD)
    assert assert_shrink_only(str(tmp_path / "absent.txt"), head) == PASSED


def test_bootstrap_still_parses_the_head_file_strictly(tmp_path: Path) -> None:
    # Bootstrap skips the COMPARISON. It must not skip validation, or the very
    # first list could be malformed and never checked again.
    head = _write(tmp_path, "head.txt", "PH-01 | perf\n")
    with pytest.raises(SystemExit):
        assert_shrink_only(str(tmp_path / "absent.txt"), head)


# ── the four verdicts ────────────────────────────────────────────────────────


def test_red_and_undeclared_blocks() -> None:
    code, lines = verdict({"real"}, {}, {"real": "failure"})
    assert code == BLOCKED
    assert any("NOT declared a placeholder" in line for line in lines)


def test_red_and_declared_is_excused_and_names_its_id_owner_milestone() -> None:
    code, lines = verdict({"perf"}, _DECL, {"perf": "failure"})
    assert code == PASSED
    excused = next(line for line in lines if "EXCUSED perf" in line)
    assert "PH-01" in excused
    assert "P4" in excused
    assert "@o" in excused


def test_green_and_declared_blocks_as_stale() -> None:
    # The rule that stops the list rotting. Without it a gate that starts
    # passing stays excused forever and silently covers a later regression.
    code, lines = verdict({"perf"}, _DECL, {"perf": "success"})
    assert code == BLOCKED
    assert any("STALE" in line for line in lines)


def test_green_and_undeclared_passes() -> None:
    assert verdict({"real"}, {}, {"real": "success"})[0] == PASSED


def test_one_undeclared_failure_blocks_even_among_many_excused() -> None:
    code, lines = verdict({"perf", "real"}, _DECL, {"perf": "failure", "real": "failure"})
    assert code == BLOCKED
    assert any("FAILURE real" in line for line in lines)


def test_a_missing_conclusion_is_treated_as_failure_not_success() -> None:
    assert verdict({"real"}, {}, {})[0] == BLOCKED


def test_skipped_does_not_pass() -> None:
    # GitHub treats a skipped job as satisfying a required check. This must not.
    assert verdict({"real"}, {}, {"real": "skipped"})[0] == BLOCKED
