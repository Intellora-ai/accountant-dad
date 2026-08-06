"""The aggregator must be UNABLE to publish a score it did not earn.

WHAT IS BEING GUARDED. `tools/ci/mutation_aggregate.py` turns a manifest plus a
set of shard result files into exactly one of four states. The only interesting
question about it is the one this file asks over and over: *can a number come
out the other end when the inputs do not account for the whole tree?*

THE TWO MEASUREMENTS THAT FORCED THE MODULE, and they are different defects:

  1. A partial run reported 2440 killed / 288 survived at 65% completion.
     `2440 / (2440 + 288)` is 89.44% — a real division over a denominator that
     was never complete. Nothing in the arithmetic is wrong; the denominator is.

  2. mutmut's own summary printed `3867 + 1 + 75 = 3943` while 4612 mutants had
     been generated. 669 mutants appeared in NO column, because `print_stats`
     has no segfault field. A status nobody prints is a mutant nobody counts.

Both are the same shape: the denominator quietly became "whatever we happened to
reach a verdict on", and a shrinking denominator makes the printed percentage go
UP. So every test below that ends in a score also pins the DENOMINATOR, and
every test that ends in a refusal also pins that `score` is `None` — a refusal
that still carries a number is the defect wearing a warning label.

HOW THESE TESTS ARE WRITTEN TO FAIL. Each of the five failure modes named in the
brief — a missing record, a duplicate, a malformed record, a mismatched manifest
hash, a shard that never reported — is constructed from a run that PASSES, by
changing exactly one thing. The passing run is asserted first in each pair, so a
refusal can never be credited to a fixture that was broken all along.
"""

from __future__ import annotations

import ast
import json
import runpy
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import mutation_aggregate
import pytest
from authored_source import authored_tree, running_path

# ── the fixture universe ─────────────────────────────────────────────────────
# One commit, one lock hash, one manifest hash. Every test that wants a conflict
# builds it by overriding exactly one of these, so the conflict is visible in
# the test body rather than buried in a second fixture.

COMMIT = "0123456789abcdef0123456789abcdef01234567"
LOCK = "sha256:lockfile"
MANIFEST_SHA = "sha256:manifest"
OTHER_SHA = "sha256:a-different-manifest"

FOUR = ("m0", "m1", "m2", "m3")

#: Four mutants, three killed. 75% — chosen so that the pass/fail boundary can
#: be walked with a floor either side of it and never lands on a round number
#: that a bug could produce by accident.
THREE_OF_FOUR_KILLED = {"m0": "killed", "m1": "killed", "m2": "killed", "m3": "survived"}
SCORE_OF_THREE_OF_FOUR = 75.0
FLOOR_AT_THE_SCORE = 75.0
FLOOR_BELOW_THE_SCORE = 74.9
FLOOR_ABOVE_THE_SCORE = 75.1

USAGE_EXIT = 2

#: The floor this module must NOT contain. It lives in
#: `.github/workflows/testing.yml` and nowhere else.
THE_MUTATION_FLOOR = 93.0

#: The partition sizes used below, named because a bare integer in a comparison
#: is a magic value and because these two ARE the thing being asserted.
TWO_SHARDS = 2
ONE_FINDING = 1

#: Three killed, one timeout: the timeout is not in the denominator, so the
#: denominator is 3 and not 4. Named because that 3 IS the owner-spec §5 change.
KILLED_PLUS_SURVIVED_OF_THREE = 3


def manifest_body(ids: Sequence[str], overrides: Mapping[str, object] | None = None) -> str:
    body: dict[str, object] = {
        "commit": COMMIT,
        "mutmut_version": "3.3.1",
        "python_version": "3.12.13",
        "platform": "linux-x86_64",
        "dependency_lock_hash": LOCK,
        "manifest_sha256": MANIFEST_SHA,
        "expected_mutants": len(ids),
        "mutants": [
            {"id": name, "name": f"x_{name}__mutmut_1", "source": "src/a.py"} for name in ids
        ],
    }
    body.update(overrides or {})
    return json.dumps(body)


def write_manifest(
    tmp_path: Path, ids: Sequence[str], overrides: Mapping[str, object] | None = None
) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(manifest_body(ids, overrides), encoding="utf-8")
    return path


def header(
    index: int, count: int, overrides: Mapping[str, object] | None = None
) -> dict[str, object]:
    body: dict[str, object] = {
        "shard_index": index,
        "shard_count": count,
        "manifest_sha256": MANIFEST_SHA,
        "commit": COMMIT,
        "dependency_lock_hash": LOCK,
    }
    body.update(overrides or {})
    return body


def record(mutant_id: str, status: str = "killed") -> dict[str, object]:
    return {
        "id": mutant_id,
        "status": status,
        "exit_code": 1 if status == "killed" else 0,
        "signal": None,
        "test": "tests/unit/test_a.py::test_a",
        "worker": "w0",
        "attempt": 1,
        "duration_seconds": 0.5,
    }


def write_shard(path: Path, lines: Sequence[object]) -> Path:
    """Each entry is either a mapping (encoded) or a raw string (written as-is).

    The raw-string door is what lets a malformed line be built without also
    having to fake a whole file, so the malformed-record tests differ from the
    passing run by one line and nothing else.
    """
    rendered = [line if isinstance(line, str) else json.dumps(line) for line in lines]
    path.write_text("".join(f"{text}\n" for text in rendered), encoding="utf-8")
    return path


def one_shard(tmp_path: Path, statuses: Mapping[str, str]) -> Path:
    lines: list[object] = [header(0, 1)]
    lines.extend(record(name, status) for name, status in statuses.items())
    return write_shard(tmp_path / "shard-0.jsonl", lines)


def complete_pass(tmp_path: Path) -> mutation_aggregate.Report:
    """The run every failure test is built by breaking. Asserted, not assumed."""
    return mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR),
        [one_shard(tmp_path, THREE_OF_FOUR_KILLED)],
        FLOOR_BELOW_THE_SCORE,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PASS — and what the published number is actually computed over.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_complete_run_publishes_the_score_and_passes(tmp_path: Path) -> None:
    report = complete_pass(tmp_path)
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons
    assert report.score == SCORE_OF_THREE_OF_FOUR
    assert report.killed == len([s for s in THREE_OF_FOUR_KILLED.values() if s == "killed"])
    assert report.denominator == len(FOUR)
    assert report.exit_code == 0


def test_a_score_exactly_on_the_floor_passes(tmp_path: Path) -> None:
    """The boundary, in the direction that matters. `>` instead of `>=` would
    fail a run that met the floor exactly, and no other test in this file could
    tell those two operators apart.
    """
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR),
        [one_shard(tmp_path, THREE_OF_FOUR_KILLED)],
        FLOOR_AT_THE_SCORE,
    )
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons


def test_the_score_is_killed_over_killed_plus_survived_and_a_timeout_stays_visible(
    tmp_path: Path,
) -> None:
    """OWNER SPEC §5, approved 2026-08-06. Replaces the manifest-denominator rule.

    Three killed, one timeout, nothing survived. The score is `killed /
    (killed + survived)` = 100.0%, because the question a mutation score asks is
    *"when a test could have noticed, did it?"* — and on the timed-out mutant no
    test was ever given the chance.

    THE INFLATION HAZARD THAT RULE USED TO CARRY IS NOT BACK, and this test
    pins the reason rather than trusting it: the timeout is still COUNTED, in
    `timeout_count`, on a report that also states 100% coverage. A run can now be
    complete, perfectly scored, and visibly sick at the same time — which is more
    information than the old single number carried, not less.

    The guard against `2440/(2440+288)` moved rather than vanished. It now lives
    in reconciliation, one layer up, and
    `test_an_incomplete_run_is_refused_before_any_arithmetic_happens` holds it.
    """
    statuses = {"m0": "killed", "m1": "killed", "m2": "killed", "m3": "timeout"}
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, statuses)], FLOOR_BELOW_THE_SCORE
    )
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons
    assert report.denominator == KILLED_PLUS_SURVIVED_OF_THREE, "denominator = killed + survived"
    assert report.score == pytest.approx(100.0)

    counts = mutation_aggregate.machine_report(report)
    assert counts["timeout_count"] == 1, "a timeout is never silently dropped (spec §4)"
    assert counts["manifest_coverage_percent"] == pytest.approx(100.0)
    assert counts["missing_count"] == 0


def test_a_run_where_nothing_was_killed_or_survived_earns_no_score(tmp_path: Path) -> None:
    """`0/0` is not 0% and it is not 100%. It is the absence of a measurement.

    Every mutant timed out, so no test was ever asked a question. Under the
    manifest-denominator rule this returned 0.0% — a real number, and a false
    one: it reads as "the suite caught nothing" when the truth is "the suite was
    never run against anything."
    """
    statuses = dict.fromkeys(FOUR, "timeout")
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, statuses)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert mutation_aggregate.machine_report(report)["score_percent"] is None


def test_no_error_status_is_ever_counted_as_killed(tmp_path: Path) -> None:
    """One mutant per terminal status. Only the killed one reaches the
    numerator; every other one stays in the denominator and drags the score
    down, which is the safe direction and the only defensible one.
    """
    ids = tuple(f"m{index}" for index in range(len(mutation_aggregate.TERMINAL_STATUSES)))
    statuses = dict(zip(ids, mutation_aggregate.TERMINAL_STATUSES, strict=True))
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, ids), [one_shard(tmp_path, statuses)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons
    assert report.killed == 1

    # OWNER SPEC §5. One killed and one survived are the only two statuses that
    # answer the score's question, so the denominator is 2 however many other
    # terminal states exist. This assertion is deliberately written against
    # TERMINAL_STATUSES rather than a literal: adding a seventh state must not
    # silently move the score, and if it ever does, this goes red.
    assert report.denominator == len(mutation_aggregate.SCORED_STATUSES)
    assert report.score == pytest.approx(50.0)

    # ...and every other status is still COUNTED, just counted elsewhere. That is
    # the whole difference between "excluded from the score" and "dropped".
    counts = mutation_aggregate.machine_report(report)
    unscored = len(mutation_aggregate.TERMINAL_STATUSES) - len(mutation_aggregate.SCORED_STATUSES)

    def count(name: str) -> int:
        value = counts[name]
        assert isinstance(value, int), f"{name} is {type(value).__name__}, not a count"
        return value

    accounted = (
        count("timeout_count")
        + count("error_count")
        + count("infrastructure_failure_count")
        + count("cancelled_count")
    )
    assert accounted == unscored, (
        f"{unscored} non-scoring statuses were reported and only {accounted} were "
        f"counted — a status that reaches no count is a mutant that vanished."
    )
    assert counts["missing_count"] == 0
    assert counts["duplicate_count"] == 0
    assert counts["unique_reported_count"] == counts["manifest_count"]


def test_the_tally_names_every_status_that_occurred(tmp_path: Path) -> None:
    report = complete_pass(tmp_path)
    assert dict(report.tally) == {"killed": 3, "survived": 1}


def test_records_split_across_several_shards_reconcile_into_one_run(tmp_path: Path) -> None:
    """Sharding is the whole point; a tool that only worked on one file would
    pass every other test here and be useless.
    """
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    second = write_shard(
        tmp_path / "s1.jsonl", [header(1, 2), record("m2"), record("m3", "survived")]
    )
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [first, second], FLOOR_BELOW_THE_SCORE
    )
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons
    assert report.score == SCORE_OF_THREE_OF_FOUR
    assert report.shards_reported == (0, 1)


def test_a_trailing_blank_line_is_not_a_record(tmp_path: Path) -> None:
    """Every JSONL writer ends the last line with a newline. Reading that as a
    malformed record would refuse every correct file ever produced.
    """
    lines: list[object] = [header(0, 1)]
    lines.extend(record(name, status) for name, status in THREE_OF_FOUR_KILLED.items())
    lines.append("   ")
    shard = write_shard(tmp_path / "s0.jsonl", lines)
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [shard], FLOOR_BELOW_THE_SCORE
    )
    assert report.state == mutation_aggregate.STATE_PASS, report.reasons


# ═══════════════════════════════════════════════════════════════════════════
# FAIL_SCORE — the run reconciled; the number is simply below the floor.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_reconciled_run_below_the_floor_fails_on_the_score(tmp_path: Path) -> None:
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR),
        [one_shard(tmp_path, THREE_OF_FOUR_KILLED)],
        FLOOR_ABOVE_THE_SCORE,
    )
    assert report.state == mutation_aggregate.STATE_FAIL_SCORE
    assert report.exit_code != 0
    # The score IS reported here, unlike every other failure state: it was
    # earned over a complete denominator and is the reason for the refusal.
    assert report.score == SCORE_OF_THREE_OF_FOUR


def test_the_floor_comes_from_the_argument_and_not_from_the_module(tmp_path: Path) -> None:
    """THE SAME INPUTS, TWO FLOORS, TWO STATES.

    A hardcoded threshold would make one of these two assertions impossible, and
    no amount of reading the source proves it the way running it does.
    """
    ids = write_manifest(tmp_path, FOUR)
    shard = one_shard(tmp_path, THREE_OF_FOUR_KILLED)
    below = mutation_aggregate.aggregate(ids, [shard], FLOOR_BELOW_THE_SCORE)
    above = mutation_aggregate.aggregate(ids, [shard], FLOOR_ABOVE_THE_SCORE)
    assert below.state == mutation_aggregate.STATE_PASS
    assert above.state == mutation_aggregate.STATE_FAIL_SCORE


# ═══════════════════════════════════════════════════════════════════════════
# FAIL_INCOMPLETE — the shards agree about the universe, and do not cover it.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_missing_record_refuses_to_score(tmp_path: Path) -> None:
    """FAILURE MODE 1 of 5. The 65%-completion defect, in miniature."""
    partial = {name: status for name, status in THREE_OF_FOUR_KILLED.items() if name != "m3"}
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, partial)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.exit_code != 0
    assert report.score is None, "a refusal that still carries a number is not a refusal"
    assert report.reconciliation is not None
    assert report.reconciliation.missing == ("m3",)


def test_the_partial_run_that_forced_this_tool_publishes_nothing(tmp_path: Path) -> None:
    """A re-enactment with the same shape and a floor of zero.

    Every recorded mutant is killed, so `killed / recorded` is 100.0% and would
    clear ANY floor. Two thirds of the manifest was never run. The floor of 0.0
    removes the score from the explanation entirely: the only thing that can
    produce a refusal here is the reconciliation.
    """
    ids = tuple(f"m{index}" for index in range(9))
    recorded = dict.fromkeys(ids[:6], "killed")
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, ids), [one_shard(tmp_path, recorded)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.missing == ("m6", "m7", "m8")


def test_a_duplicate_record_refuses_to_score(tmp_path: Path) -> None:
    """FAILURE MODE 2 of 5. Two verdicts for one mutant means the partition is
    not a partition, whether or not the two verdicts agree.
    """
    lines: list[object] = [header(0, 1)]
    lines.extend(record(name, status) for name, status in THREE_OF_FOUR_KILLED.items())
    lines.append(record("m0"))
    shard = write_shard(tmp_path / "s0.jsonl", lines)
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.duplicated == ("m0",)


def test_the_same_mutant_reported_by_two_shards_is_a_duplicate(tmp_path: Path) -> None:
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    second = write_shard(
        tmp_path / "s1.jsonl",
        [header(1, 2), record("m1"), record("m2"), record("m3", "survived")],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first, second], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.reconciliation is not None
    assert report.reconciliation.duplicated == ("m1",)


def test_a_record_for_a_mutant_the_manifest_does_not_contain_refuses_to_score(
    tmp_path: Path,
) -> None:
    lines: list[object] = [header(0, 1)]
    lines.extend(record(name, status) for name, status in THREE_OF_FOUR_KILLED.items())
    lines.append(record("m-not-generated"))
    shard = write_shard(tmp_path / "s0.jsonl", lines)
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.unexpected == ("m-not-generated",)


def test_a_status_outside_the_terminal_set_refuses_to_score(tmp_path: Path) -> None:
    """FAILURE MODE 3 of 5, first half. `not checked` is mutmut's word for a
    mutant it never reached — precisely the population that vanished from the
    `3867 + 1 + 75 = 3943` summary.
    """
    statuses = dict(THREE_OF_FOUR_KILLED)
    statuses["m3"] = "not checked"
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, statuses)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert len(report.reconciliation.invalid) == 1
    assert "not checked" in str(report.reconciliation.invalid[0])


@pytest.mark.parametrize(
    ("line", "expected_in_reason"),
    [
        ("{not json at all", "not valid JSON"),
        ('["a", "list"]', "not a JSON object"),
        ('{"status": "killed"}', "id"),
        ('{"id": 7, "status": "killed"}', "id"),
        ('{"id": "", "status": "killed"}', "id"),
        ('{"id": "m3"}', "status"),
        ('{"id": "m3", "status": 1}', "status"),
    ],
)
def test_a_malformed_record_refuses_to_score(
    tmp_path: Path, line: str, expected_in_reason: str
) -> None:
    """FAILURE MODE 3 of 5, second half — every way one line can be unreadable.

    The reason must name the offending line, because a refusal that says only
    "something was wrong" is a refusal somebody eventually switches off.
    """
    lines: list[object] = [header(0, 1)]
    lines.extend(
        record(name, status) for name, status in THREE_OF_FOUR_KILLED.items() if name != "m3"
    )
    lines.append(line)
    shard = write_shard(tmp_path / "s0.jsonl", lines)
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert len(report.reconciliation.invalid) == 1
    rendered = str(report.reconciliation.invalid[0])
    assert expected_in_reason in rendered
    assert "s0.jsonl:5" in rendered, f"the line number is missing from {rendered!r}"


def test_a_shard_that_never_reported_refuses_to_score(tmp_path: Path) -> None:
    """FAILURE MODE 5 of 5.

    INCOMPLETE and not INFRASTRUCTURE, deliberately. The shards that DID report
    agree about the universe perfectly; what is wrong is that their union does
    not cover the manifest. The state names what can be proven, never the cause
    that is being guessed at.
    """
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.absent_shards == (1,)
    assert report.shards_reported == (0,)
    assert report.shards_expected == TWO_SHARDS


def test_a_silent_shard_refuses_even_when_no_mutant_is_missing(tmp_path: Path) -> None:
    """THE DISCRIMINATING CASE for `absent_shards`, and it was added because a
    hand-run mutation survived without it.

    Deleting `absent_shards` from the completeness predicate left the whole
    suite green: in every other test the silent shard's mutants were ALSO
    missing, so `missing` did all the refusing and the shard check was never
    the thing under test. Here shard 0 carries every mutant in the manifest and
    shard 1 never speaks. Nothing is missing — and a partition with a silent
    member is not a partition that finished, because whatever shard 1 was
    assigned is not what shard 0 ran.
    """
    everything = write_shard(
        tmp_path / "s0.jsonl",
        [header(0, TWO_SHARDS), *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items())],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [everything], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.missing == ()
    assert report.reconciliation.absent_shards == (1,)


def test_an_unreadable_line_refuses_even_when_every_mutant_has_a_verdict(tmp_path: Path) -> None:
    """THE DISCRIMINATING CASE for `invalid`, added for the same reason.

    Deleting `invalid` from the completeness predicate left the suite green,
    because a malformed record also leaves its mutant missing and `missing` was
    doing all the work. Here every mutant in the manifest has a good record and
    one EXTRA line is garbage: nothing is missing, nothing is duplicated,
    nothing is unexpected. A file this tool cannot fully read is a file it
    cannot certify — the unreadable line might have been a second verdict for a
    mutant already counted, and there is no way to know which.
    """
    lines: list[object] = [header(0, 1)]
    lines.extend(record(name, status) for name, status in THREE_OF_FOUR_KILLED.items())
    lines.append("{ not json, and not blank either")
    shard = write_shard(tmp_path / "s0.jsonl", lines)
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INCOMPLETE
    assert report.score is None
    assert report.reconciliation is not None
    assert report.reconciliation.missing == ()
    assert report.reconciliation.duplicated == ()
    assert len(report.reconciliation.invalid) == ONE_FINDING


# ═══════════════════════════════════════════════════════════════════════════
# FAIL_INFRASTRUCTURE — the inputs cannot be combined at all.
# ═══════════════════════════════════════════════════════════════════════════


def test_shards_with_different_manifest_hashes_are_infrastructure(tmp_path: Path) -> None:
    """FAILURE MODE 4 of 5. Two shards that measured two different universes.

    Not INCOMPLETE: "which mutants are missing" has no meaning until the two
    sides agree on what the full set even is.
    """
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    second = write_shard(
        tmp_path / "s1.jsonl",
        [
            header(1, 2, {"manifest_sha256": OTHER_SHA}),
            record("m2"),
            record("m3", "survived"),
        ],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first, second], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert report.exit_code != 0
    assert report.score is None
    assert any(OTHER_SHA in reason for reason in report.reasons), report.reasons


def test_infrastructure_outranks_incomplete_when_both_are_true(tmp_path: Path) -> None:
    """PRECEDENCE. One shard measured a different universe AND half the
    manifest is unaccounted for. Reporting "records are missing" would send the
    reader hunting for a crashed worker that does not exist.
    """
    first = write_shard(
        tmp_path / "s0.jsonl", [header(0, 2, {"manifest_sha256": OTHER_SHA}), record("m0")]
    )
    second = write_shard(tmp_path / "s1.jsonl", [header(1, 2), record("m1")])
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first, second], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE


@pytest.mark.parametrize(
    ("override", "expected_in_reason"),
    [
        ({"manifest_sha256": OTHER_SHA}, "manifest_sha256"),
        ({"commit": "f" * 40}, "commit"),
        ({"dependency_lock_hash": "sha256:other-lock"}, "dependency_lock_hash"),
    ],
)
def test_a_shard_whose_provenance_differs_from_the_manifest_is_infrastructure(
    tmp_path: Path, override: Mapping[str, object], expected_in_reason: str
) -> None:
    shard = write_shard(
        tmp_path / "s0.jsonl",
        [header(0, 1, override), *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items())],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any(expected_in_reason in reason for reason in report.reasons), report.reasons


def test_shards_that_disagree_about_the_partition_size_are_infrastructure(tmp_path: Path) -> None:
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    second = write_shard(
        tmp_path / "s1.jsonl", [header(1, 3), record("m2"), record("m3", "survived")]
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first, second], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("shard_count" in reason for reason in report.reasons), report.reasons


def test_two_files_claiming_the_same_shard_is_infrastructure(tmp_path: Path) -> None:
    """The same shard passed twice. Its records would reconcile as duplicates,
    which would report the symptom and hide the cause: the input SET is wrong.
    """
    first = write_shard(tmp_path / "s0.jsonl", [header(0, 2), record("m0"), record("m1")])
    again = write_shard(
        tmp_path / "s0-again.jsonl", [header(0, 2), record("m2"), record("m3", "survived")]
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [first, again], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("shard 0" in reason for reason in report.reasons), report.reasons


def test_the_same_shard_file_passed_twice_is_infrastructure(tmp_path: Path) -> None:
    """A repeated `--shard`. Found by attacking the tool rather than by a test.

    It reconciles as "every mutant has two records", which is true, useless and
    points at the runner instead of at the invocation. The duplicate is caught
    where it happened: one slice of the partition, reported twice.
    """
    shard = one_shard(tmp_path, THREE_OF_FOUR_KILLED)
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard, shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("reported 2 times" in reason for reason in report.reasons), report.reasons


def test_aggregate_with_no_shards_at_all_returns_a_report_rather_than_raising(
    tmp_path: Path,
) -> None:
    """`--shard` is required, so the CLI cannot reach this — a caller can.

    Found by calling `aggregate` directly: `max()` over an empty sequence raised
    `ValueError`, and a tool that dies with a traceback leaves CI in exactly the
    ambiguous state this module exists to remove.
    """
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert report.score is None
    assert any("no shard result files" in reason for reason in report.reasons), report.reasons


@pytest.mark.parametrize("index", [-1, 2])
def test_a_shard_index_outside_the_partition_is_infrastructure(tmp_path: Path, index: int) -> None:
    shard = write_shard(
        tmp_path / "s.jsonl",
        [header(index, 2), *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items())],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE


@pytest.mark.parametrize("key", ["shard_index", "shard_count"])
def test_a_boolean_is_not_an_integer_in_a_shard_header(tmp_path: Path, key: str) -> None:
    """`True` is a subclass of `int`, and this case survived a hand-run mutation.

    Dropping the `isinstance(value, bool)` guard left the suite green. It is not
    cosmetic: `"shard_count": true` becomes a partition of size one, every
    record lines up against it, and the run reports PASS having silently
    reconciled against a universe nobody declared. `"shard_index": true`
    relabels the shard as number one instead.
    """
    shard = write_shard(
        tmp_path / "s0.jsonl",
        [
            header(0, TWO_SHARDS, {key: True}),
            *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items()),
        ],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any(key in reason for reason in report.reasons), report.reasons


def test_a_boolean_expected_mutants_is_not_an_integer(tmp_path: Path) -> None:
    """The same guard, on the manifest side. `true` equals one, so a manifest of
    exactly one mutant would reconcile and publish a score off a count that was
    never a number.
    """
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, ("m0",), {"expected_mutants": True}),
        [one_shard(tmp_path, {"m0": "killed"})],
        0.0,
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("expected_mutants" in reason for reason in report.reasons), report.reasons


@pytest.mark.parametrize(
    "first_line",
    [
        '{"id": "m0", "status": "killed"}',
        '{"shard_index": 0}',
        '{"shard_index": "0", "shard_count": 1, "manifest_sha256": "s", "commit": "c",'
        ' "dependency_lock_hash": "l"}',
        "not json",
    ],
)
def test_a_shard_whose_first_line_is_not_a_header_is_infrastructure(
    tmp_path: Path, first_line: str
) -> None:
    """A shard that cannot say which universe it measured is unusable, and
    guessing "it was probably ours" is exactly the assumption this refuses.
    """
    shard = write_shard(
        tmp_path / "s0.jsonl",
        [first_line, *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items())],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert report.score is None


def test_a_partition_of_size_zero_is_infrastructure(tmp_path: Path) -> None:
    """`shard_count: 0` declares a partition with no members, which would make
    `absent_shards` empty by arithmetic and let any record set look complete.
    """
    shard = write_shard(
        tmp_path / "s0.jsonl",
        [header(0, 0), *(record(n, s) for n, s in THREE_OF_FOUR_KILLED.items())],
    )
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("shard_count" in reason for reason in report.reasons), report.reasons


def test_an_empty_shard_file_is_infrastructure(tmp_path: Path) -> None:
    shard = write_shard(tmp_path / "s0.jsonl", [])
    report = mutation_aggregate.aggregate(write_manifest(tmp_path, FOUR), [shard], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE


def test_a_shard_file_that_does_not_exist_is_infrastructure(tmp_path: Path) -> None:
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [tmp_path / "absent.jsonl"], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE


@pytest.mark.parametrize(
    ("overrides", "expected_in_reason"),
    [
        ({"expected_mutants": 3}, "expected_mutants"),
        ({"mutants": []}, "no mutants"),
        ({"mutants": "four"}, "mutants is not a list"),
        ({"mutants": ["m0"]}, "not a JSON object"),
        ({"mutants": [{"name": "n", "source": "src/a.py"}]}, "no usable id"),
        ({"manifest_sha256": None}, "manifest_sha256"),
        ({"commit": 7}, "commit"),
    ],
)
def test_a_manifest_that_contradicts_itself_is_infrastructure(
    tmp_path: Path, overrides: Mapping[str, object], expected_in_reason: str
) -> None:
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR, overrides),
        [one_shard(tmp_path, THREE_OF_FOUR_KILLED)],
        0.0,
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any(expected_in_reason in reason for reason in report.reasons), report.reasons


def test_a_manifest_listing_the_same_mutant_twice_is_infrastructure(tmp_path: Path) -> None:
    """A duplicated id makes `expected_mutants` and the id SET disagree, so
    every record set would look short by one and the missing list would name a
    mutant that was in fact reported.
    """
    duplicated = [{"id": "m0", "name": "n", "source": "src/a.py"} for _ in range(2)]
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, ("m0", "m1"), {"mutants": duplicated}),
        [one_shard(tmp_path, {"m0": "killed"})],
        0.0,
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert any("duplicate" in reason for reason in report.reasons), report.reasons


@pytest.mark.parametrize("body", ["{not json", "[]", '{"commit": "c"}'])
def test_an_unreadable_manifest_is_infrastructure(tmp_path: Path, body: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(body, encoding="utf-8")
    report = mutation_aggregate.aggregate(path, [one_shard(tmp_path, THREE_OF_FOUR_KILLED)], 0.0)
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE


def test_a_manifest_that_does_not_exist_is_infrastructure(tmp_path: Path) -> None:
    report = mutation_aggregate.aggregate(
        tmp_path / "absent.json", [one_shard(tmp_path, THREE_OF_FOUR_KILLED)], 0.0
    )
    assert report.state == mutation_aggregate.STATE_FAIL_INFRASTRUCTURE
    assert report.score is None


# ═══════════════════════════════════════════════════════════════════════════
# The four states, their exit codes, and the two reports.
# ═══════════════════════════════════════════════════════════════════════════


def test_only_pass_exits_zero_and_every_state_is_distinguishable() -> None:
    codes = mutation_aggregate.EXIT_CODE_BY_STATE
    assert set(codes) == set(mutation_aggregate.STATES)
    assert codes[mutation_aggregate.STATE_PASS] == 0
    assert all(code != 0 for state, code in codes.items() if state != mutation_aggregate.STATE_PASS)
    assert len(set(codes.values())) == len(codes), "two states sharing an exit code are one state"


def test_no_state_collides_with_the_usage_exit_code() -> None:
    """`argparse` exits 2 on a bad invocation. A state that also exited 2 would
    make a typo'd flag indistinguishable from an incomplete run — the exact
    ambiguity this tool exists to remove.
    """
    assert USAGE_EXIT not in set(mutation_aggregate.EXIT_CODE_BY_STATE.values())


def test_the_human_summary_binds_the_score_to_its_commit(tmp_path: Path) -> None:
    """Law 56. A percentage with no commit beside it is an opinion."""
    summary = mutation_aggregate.human_summary(complete_pass(tmp_path))
    assert f"75.00% @ {COMMIT}" in summary, summary


def test_the_human_summary_of_a_refusal_carries_no_score(tmp_path: Path) -> None:
    partial = {name: status for name, status in THREE_OF_FOUR_KILLED.items() if name != "m3"}
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, partial)], 0.0
    )
    summary = mutation_aggregate.human_summary(report)
    assert mutation_aggregate.STATE_FAIL_INCOMPLETE in summary
    assert "%" not in summary, f"a percentage escaped into a refusal:\n{summary}"
    assert "m3" in summary


def test_the_human_summary_still_renders_when_nothing_could_be_read(tmp_path: Path) -> None:
    """The worst failure is the one whose summary a person most needs.

    No manifest means no commit, no hash, no tally and no reconciliation — every
    field the renderer normally reaches for is absent. It must still produce a
    page naming the file it could not read, because a traceback here is a gate
    that failed without saying why.
    """
    report = mutation_aggregate.aggregate(
        tmp_path / "absent.json", [tmp_path / "absent.jsonl"], 0.0
    )
    summary = mutation_aggregate.human_summary(report)
    assert mutation_aggregate.STATE_FAIL_INFRASTRUCTURE in summary
    assert "UNKNOWN" in summary
    assert "absent.json" in summary
    assert "%" not in summary, f"a percentage escaped into a refusal:\n{summary}"


def test_the_machine_report_is_json_and_carries_the_provenance(tmp_path: Path) -> None:
    body = mutation_aggregate.machine_report(complete_pass(tmp_path))
    decoded = json.loads(json.dumps(body))
    assert decoded["state"] == mutation_aggregate.STATE_PASS
    assert decoded["exit_code"] == 0
    assert decoded["score_percent"] == SCORE_OF_THREE_OF_FOUR
    assert decoded["denominator"] == len(FOUR)
    assert decoded["commit"] == COMMIT
    assert decoded["manifest_sha256"] == MANIFEST_SHA
    assert decoded["dependency_lock_hash"] == LOCK
    assert decoded["floor_percent"] == FLOOR_BELOW_THE_SCORE


def test_the_machine_report_of_a_refusal_has_a_null_score(tmp_path: Path) -> None:
    report = mutation_aggregate.aggregate(
        write_manifest(tmp_path, FOUR), [one_shard(tmp_path, {"m0": "killed"})], 0.0
    )
    body = mutation_aggregate.machine_report(report)
    assert body["score_percent"] is None
    assert body["state"] == mutation_aggregate.STATE_FAIL_INCOMPLETE


# ═══════════════════════════════════════════════════════════════════════════
# The command line — the only surface CI ever touches.
# ═══════════════════════════════════════════════════════════════════════════


def invoke(tmp_path: Path, floor: str, statuses: Mapping[str, str]) -> tuple[int, Path]:
    report_path = tmp_path / "report.json"
    code = mutation_aggregate.main(
        [
            "--manifest",
            str(write_manifest(tmp_path, FOUR)),
            "--shard",
            str(one_shard(tmp_path, statuses)),
            "--floor",
            floor,
            "--report",
            str(report_path),
        ]
    )
    return code, report_path


def test_the_cli_writes_both_reports_and_returns_the_states_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report_path = invoke(tmp_path, "74.9", THREE_OF_FOUR_KILLED)
    assert code == 0
    printed = capsys.readouterr().out
    assert mutation_aggregate.STATE_PASS in printed
    assert f"75.00% @ {COMMIT}" in printed
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["score_percent"] == SCORE_OF_THREE_OF_FOUR
    assert written["floor_percent"] == FLOOR_BELOW_THE_SCORE


def test_the_cli_returns_non_zero_when_the_run_did_not_reconcile(tmp_path: Path) -> None:
    code, report_path = invoke(tmp_path, "0", {"m0": "killed"})
    assert code == mutation_aggregate.EXIT_CODE_BY_STATE[mutation_aggregate.STATE_FAIL_INCOMPLETE]
    assert json.loads(report_path.read_text(encoding="utf-8"))["score_percent"] is None


def test_the_cli_returns_non_zero_when_the_score_is_below_the_floor(tmp_path: Path) -> None:
    code, _ = invoke(tmp_path, "75.1", THREE_OF_FOUR_KILLED)
    assert code == mutation_aggregate.EXIT_CODE_BY_STATE[mutation_aggregate.STATE_FAIL_SCORE]


@pytest.mark.parametrize("missing", ["--floor", "--shard", "--manifest", "--report"])
def test_the_cli_refuses_an_invocation_missing_any_required_argument(
    tmp_path: Path, missing: str
) -> None:
    """`--floor` in particular: an optional floor is a defaulted floor, and a
    defaulted floor is a threshold nobody chose.
    """
    argv = [
        "--manifest",
        str(write_manifest(tmp_path, FOUR)),
        "--shard",
        str(one_shard(tmp_path, THREE_OF_FOUR_KILLED)),
        "--floor",
        "93",
        "--report",
        str(tmp_path / "r.json"),
    ]
    index = argv.index(missing)
    del argv[index : index + 2]
    with pytest.raises(SystemExit) as excinfo:
        mutation_aggregate.main(argv)
    assert excinfo.value.code == USAGE_EXIT


@pytest.mark.parametrize("floor", ["-0.1", "100.1", "not-a-number"])
def test_the_cli_refuses_a_floor_outside_the_percentage_scale(tmp_path: Path, floor: str) -> None:
    """A floor above 100 can never be met and a negative one can never be
    missed. Either one is a gate that reports the same verdict forever.
    """
    with pytest.raises(SystemExit) as excinfo:
        invoke(tmp_path, floor, THREE_OF_FOUR_KILLED)
    assert excinfo.value.code == USAGE_EXIT


def test_the_module_entrypoint_exits_with_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI runs `python3 tools/ci/mutation_aggregate.py`, not `main()`. A wrong
    `__main__` block returns a traceback where a verdict belongs.
    """
    argv = [
        "mutation_aggregate.py",
        "--manifest",
        str(write_manifest(tmp_path, FOUR)),
        "--shard",
        str(one_shard(tmp_path, {"m0": "killed"})),
        "--floor",
        "0",
        "--report",
        str(tmp_path / "r.json"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(running_path(mutation_aggregate)), run_name="__main__")
    assert (
        excinfo.value.code
        == (mutation_aggregate.EXIT_CODE_BY_STATE[mutation_aggregate.STATE_FAIL_INCOMPLETE])
    )


def test_the_module_entrypoint_exits_zero_on_a_run_that_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pair matters: the test above alone passes against a hardcoded
    non-zero exit.
    """
    argv = [
        "mutation_aggregate.py",
        "--manifest",
        str(write_manifest(tmp_path, FOUR)),
        "--shard",
        str(one_shard(tmp_path, THREE_OF_FOUR_KILLED)),
        "--floor",
        "74.9",
        "--report",
        str(tmp_path / "r.json"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(running_path(mutation_aggregate)), run_name="__main__")
    assert excinfo.value.code == 0


def test_an_unwritable_report_path_fails_loudly_rather_than_silently(tmp_path: Path) -> None:
    """The machine report is not optional output. Losing it while still exiting
    zero would hand CI a green with no record of what was measured.
    """
    with pytest.raises(SystemExit) as excinfo:
        mutation_aggregate.main(
            [
                "--manifest",
                str(write_manifest(tmp_path, FOUR)),
                "--shard",
                str(one_shard(tmp_path, THREE_OF_FOUR_KILLED)),
                "--floor",
                "0",
                "--report",
                str(tmp_path / "no-such-directory" / "r.json"),
            ]
        )
    assert excinfo.value.code != 0


# ═══════════════════════════════════════════════════════════════════════════
# The module, read as SOURCE — the threshold must not live here.
# ═══════════════════════════════════════════════════════════════════════════


def numeric_constants() -> tuple[float, ...]:
    """Every numeric literal in the AUTHORED module.

    `authored_tree`, never `inspect.getsource`: under mutation the imported
    module is mutmut's rewrite of it, and a test that reads the rewrite is
    asking a question about the interpreter rather than about this repository
    (L-013).
    """
    tree = authored_tree(mutation_aggregate)
    return tuple(
        float(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        # `True`/`False` are `int` subclasses and are not numbers here.
        and not isinstance(node.value, bool)
    )


def test_the_scan_for_literals_actually_reads_the_module() -> None:
    """HOLLOW-GATE DEFENCE. An empty tuple satisfies the test below trivially."""
    constants = numeric_constants()
    assert constants, "no numeric literal found — the source was not read"
    assert 0.0 in constants, "the PASS exit code is 0 and must have been seen"


def test_the_mutation_floor_is_not_a_literal_in_this_module() -> None:
    """The floor is 93 and it lives in `.github/workflows/testing.yml`. A copy
    here would be a second place to change and one place to forget (Law 19).
    """
    assert THE_MUTATION_FLOOR not in numeric_constants(), (
        "the mutation floor is hardcoded in the aggregator"
    )


def test_the_floor_argument_is_declared_required_and_undefaulted() -> None:
    """Behaviour is asserted elsewhere; this pins the DECLARATION, because a
    `default=` reintroduces a chosen threshold without changing any test that
    always passes `--floor`.
    """
    calls = [
        node
        for node in ast.walk(authored_tree(mutation_aggregate))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and any(isinstance(arg, ast.Constant) and arg.value == "--floor" for arg in node.args)
    ]
    assert len(calls) == ONE_FINDING, "expected exactly one --floor declaration"
    keywords = {keyword.arg for keyword in calls[0].keywords}
    assert "default" not in keywords
    assert any(
        keyword.arg == "required"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value
        for keyword in calls[0].keywords
    )
