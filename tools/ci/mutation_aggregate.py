#!/usr/bin/env python3
"""Combine sharded mutation results, and refuse to publish a score not earned.

THE DEFECT THIS EXISTS FOR, in two measured halves.

  1. A partial run reported 2440 killed / 288 survived at 65% completion.
     `2440 / (2440 + 288)` is 89.44%. Every step of that division is correct and
     the answer is meaningless, because the denominator was never the tree — it
     was whatever the run happened to finish.

  2. mutmut's own summary printed `3867 + 1 + 75 = 3943` while 4612 mutants had
     been generated. 669 mutants appeared in NO column, because `print_stats`
     has no segfault field. A status nobody prints is a mutant nobody counts.

Both are one shape: **the denominator shrinks in silence, and a shrinking
denominator makes the printed percentage go UP.** The number improves exactly as
the measurement gets smaller, and nothing in the output says which mutants
stopped counting.

THE TRANSFORM (Law 53). *"Make every shard finish"* is a hard problem living in
runner crashes, OOM kills and CI timeouts that nobody here owns. *"Given a
manifest of every mutant that was generated, does the union of the shard results
account for exactly that set, once each?"* is set arithmetic, answers in
milliseconds, and fails in the same place. This module answers the second, and
the first stops mattering: an unfinished run cannot produce a number at all.

WHAT MAKES A SCORE UNEARNABLE HERE — three structural choices, not three checks.

  COMPLETENESS IS PROVEN BEFORE ARITHMETIC IS ATTEMPTED. The union of the shard
  results must account for every manifest ID, exactly once. Nothing can leave the
  manifest, so nothing can inflate a percentage by leaving it — and unlike a
  denominator you merely *hope* is whole, this one is checked by set arithmetic
  that fails in milliseconds. This is why the 2% unscoreable cap the in-workflow
  `mutation` gate needs has no counterpart here: that cap bounds a denominator
  that CAN shrink, and this run cannot be scored at all until its universe is
  proven complete.

  THE SCORE IS `killed / (killed + survived)` — owner spec §5, approved
  2026-08-06, replacing an earlier rule that used the whole manifest as the
  denominator. The change is deliberate and the reason is that the two rules
  answer different questions. `killed / (killed + survived)` asks *"when a test
  could have noticed, did it?"* — a fact about the SUITE. A timeout is a fact
  about the RUNNER. Mixing them yields a suite-quality number that degrades
  because a machine was busy, which is not a measurement of the suite.

  NOTHING IS DISCARDED TO ACHIEVE THAT. `timeout`, `error`, `cancelled`,
  `infrastructure_failure`, `compile_error` and `runtime_error` each get their
  own count in the report, beside `manifest_coverage_percent`. A run can be
  complete, scored, and visibly sick at the same time — strictly more information
  than one blended number carried. What is forbidden is a status that reaches NO
  count, because that is a mutant that vanished.

  `0/0` IS NOT A SCORE. If no mutant reached `killed` or `survived`, no test was
  ever asked a question, and the run returns FAIL_INCOMPLETE rather than 0.0% —
  which would read as "the suite caught nothing" when the truth is "the suite was
  never run against anything."

  A SCORE IS COMPUTED ONLY AFTER RECONCILIATION SUCCEEDS. Not computed and
  withheld — not computed. `Report.score` is `None` for every state but `PASS`
  and `FAIL_SCORE`, and the human summary of a refusal contains no percentage
  anywhere, because a number printed beside a refusal is the number somebody
  quotes later.

THE FOUR STATES, and the line between the two failures that look alike.

    PASS                  every mutant accounted for, score at or above the floor
    FAIL_SCORE            every mutant accounted for, score below the floor
    FAIL_INCOMPLETE       the shards agree about the universe and do not cover it
    FAIL_INFRASTRUCTURE   the inputs cannot be combined at all

`FAIL_INFRASTRUCTURE` outranks `FAIL_INCOMPLETE` whenever both apply, and the
reason is not severity. If two shards carry different `manifest_sha256` values
they measured different universes, so *"which mutants are missing"* has no
referent — the union is not a set of results about one thing. Reporting missing
records there would send a reader hunting for a crashed worker that never
existed.

A shard that never reported is `FAIL_INCOMPLETE`, not infrastructure, for the
mirror-image reason: the shards that did report agree perfectly, and the only
thing that can be PROVEN is that their union falls short. The state names what
was measured, never the cause being guessed at.

THE THRESHOLD IS AN ARGUMENT, AND IT IS DELIBERATELY ABSENT FROM THIS FILE.
The mutation floor is 93 percent and it is declared once, in
`.github/workflows/testing.yml`. A copy here would be a second place to change
and one place to forget (Law 19), and a default would be a threshold nobody
chose. `--floor` is required and has no default; `tests/unit/
test_mutation_aggregate.py` reads this module's AST to prove both.

──────────────────────────────────────────────────────────────────────────────
THE TWO INPUT FORMATS THIS CONSUMES. Neither is produced here.

MANIFEST — one JSON object, written once per run before any shard starts:

    {"commit": ..., "mutmut_version": ..., "python_version": ...,
     "platform": ..., "dependency_lock_hash": ..., "manifest_sha256": ...,
     "expected_mutants": 4612,
     "mutants": [{"id": ..., "name": ..., "source": ...}, ...]}

SHARD RESULT FILE — one per shard. JSONL. **The first line is a header object**
and every line after it is one record:

    {"shard_index": 0, "shard_count": 8, "manifest_sha256": ...,
     "commit": ..., "dependency_lock_hash": ...}
    {"id": ..., "status": "killed", "exit_code": 1, "signal": null,
     "test": ..., "worker": ..., "attempt": 1, "duration_seconds": 0.41}
    ...

The header line is what makes provenance checkable per shard rather than per
run: without it a shard cannot say which universe it measured, and assuming it
measured ours is the assumption this whole module refuses.

WHAT IS ENFORCED IN A RECORD, AND WHY NOT MORE. `id` and `status` — the only two
fields that can corrupt the published score. `exit_code`, `signal`, `test`,
`worker`, `attempt` and `duration_seconds` are provenance for a human reading a
failure; a refusal triggered by a field that cannot change the answer is a false
alarm, and false alarms are how a gate gets switched off.

`manifest_sha256` IS TREATED AS AN OPAQUE IDENTITY TOKEN. It is compared, never
recomputed. Recomputing it would require knowing the producer's canonicalisation
of the manifest, and a guess at that either cries wolf on correct input or —
far worse — agrees by accident. This module therefore proves that every shard
measured THE SAME manifest, and does not prove that the manifest is authentic.
That boundary is stated rather than papered over (Law 25).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

# ── the four states ──────────────────────────────────────────────────────────

STATE_PASS = "PASS"  # noqa: S105 - a verdict word, not a credential
STATE_FAIL_SCORE = "FAIL_SCORE"
STATE_FAIL_INCOMPLETE = "FAIL_INCOMPLETE"
STATE_FAIL_INFRASTRUCTURE = "FAIL_INFRASTRUCTURE"

STATES: tuple[str, ...] = (
    STATE_PASS,
    STATE_FAIL_SCORE,
    STATE_FAIL_INCOMPLETE,
    STATE_FAIL_INFRASTRUCTURE,
)

#: Distinct per state, so a CI log can name the failure from the exit status
#: alone. They start at ten because `argparse` exits 2 on a malformed
#: invocation and 1 is the conventional "it crashed": a state sharing either
#: would make a typo'd flag indistinguishable from an incomplete run, which is
#: the exact ambiguity this module exists to remove.
EXIT_CODE_BY_STATE: Mapping[str, int] = {
    STATE_PASS: 0,
    STATE_FAIL_SCORE: 10,
    STATE_FAIL_INCOMPLETE: 11,
    STATE_FAIL_INFRASTRUCTURE: 12,
}

# ── the record vocabulary ────────────────────────────────────────────────────

KILLED = "killed"
SURVIVED = "survived"
TIMEOUT = "timeout"
ERROR = "error"
CANCELLED = "cancelled"
INFRASTRUCTURE_FAILURE = "infrastructure_failure"
COMPILE_ERROR = "compile_error"
RUNTIME_ERROR = "runtime_error"
INFRASTRUCTURE_ERROR = "infrastructure_error"

#: Every status a finished mutant may carry. A record outside this set is not a
#: verdict this module knows how to place, and is refused rather than bucketed
#: into the nearest thing — `not checked` bucketed as `survived` would be a
#: fabricated survivor, and bucketed as `killed` a fabricated kill.
#:
#: THE OWNER'S SIX, plus two the code already distinguished. The spec names one
#: `error`; this module had already split it into `compile_error` (the mutant
#: never built) and `runtime_error` (it built and then died). Both are accepted,
#: because collapsing them would RECORD LESS than the code records today, and a
#: mutant that cannot compile is a different engineering problem from one that
#: crashes. `cancelled` was a genuine gap and is new.
#:
#: `unattempted` is deliberately ABSENT. It is not a terminal execution result —
#: it is a run-level completeness failure, and it surfaces through
#: `reconciliation.missing`, never as a per-mutant verdict.
TERMINAL_STATUSES: tuple[str, ...] = (
    KILLED,
    SURVIVED,
    TIMEOUT,
    ERROR,
    CANCELLED,
    INFRASTRUCTURE_FAILURE,
    COMPILE_ERROR,
    RUNTIME_ERROR,
    INFRASTRUCTURE_ERROR,
)

#: Statuses that answer the question the mutation score asks — "did a test
#: notice?". Everything else answers a different question and is reported
#: separately rather than mixed in (owner spec §5).
SCORED_STATUSES: tuple[str, ...] = (KILLED, SURVIVED)

MANIFEST_STRING_KEYS: tuple[str, ...] = (
    "commit",
    "mutmut_version",
    "python_version",
    "platform",
    "dependency_lock_hash",
    "manifest_sha256",
)

SHARD_STRING_KEYS: tuple[str, ...] = ("manifest_sha256", "commit", "dependency_lock_hash")
SHARD_INT_KEYS: tuple[str, ...] = ("shard_index", "shard_count")

#: How many entries of a list the HUMAN summary prints before summarising the
#: rest. The machine report is never truncated: a report that hides data is the
#: defect being fixed, wearing a nicer table.
LONGEST_HUMAN_LIST = 20

PERCENT = 100.0
LOWEST_FLOOR = 0.0
HIGHEST_FLOOR = 100.0


class InfrastructureError(Exception):
    """An input that cannot be combined with the others, or read at all.

    Never caught and ignored: every raise reaches `aggregate`, which turns it
    into a `FAIL_INFRASTRUCTURE` report so the tool always emits both reports
    and never dies with a traceback where a verdict belongs.
    """


# ── what was read ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Manifest:
    """Every mutant that was generated, and the universe they belong to."""

    path: Path
    commit: str
    mutmut_version: str
    python_version: str
    platform: str
    dependency_lock_hash: str
    manifest_sha256: str
    expected_mutants: int
    mutant_ids: tuple[str, ...]


@dataclass(frozen=True)
class ShardHeader:
    """One shard's claim about which universe it measured, and which slice."""

    path: Path
    shard_index: int
    shard_count: int
    manifest_sha256: str
    commit: str
    dependency_lock_hash: str


@dataclass(frozen=True)
class Record:
    """One mutant's verdict, and where it was read from."""

    mutant_id: str
    status: str
    path: Path
    line: int


@dataclass(frozen=True)
class InvalidRecord:
    """A line that could not be turned into a verdict, and why."""

    path: Path
    line: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}"


@dataclass(frozen=True)
class Shard:
    header: ShardHeader
    records: tuple[Record, ...]
    invalid: tuple[InvalidRecord, ...]


@dataclass(frozen=True)
class Reconciliation:
    """The set arithmetic between the manifest and the union of the shards."""

    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    duplicated: tuple[str, ...]
    invalid: tuple[InvalidRecord, ...]
    absent_shards: tuple[int, ...]

    @property
    def complete(self) -> bool:
        """True only when every mutant has exactly one readable verdict."""
        return not (
            self.missing or self.unexpected or self.duplicated or self.invalid or self.absent_shards
        )

    def reasons(self) -> tuple[str, ...]:
        found: list[str] = []
        if self.absent_shards:
            listed = ", ".join(str(index) for index in self.absent_shards)
            found.append(f"shard(s) that never reported: {listed}")
        if self.missing:
            found.append(f"{len(self.missing)} mutant(s) in the manifest have no record")
        if self.unexpected:
            found.append(f"{len(self.unexpected)} record(s) name a mutant the manifest does not")
        if self.duplicated:
            found.append(f"{len(self.duplicated)} mutant(s) have more than one record")
        if self.invalid:
            found.append(f"{len(self.invalid)} record(s) could not be read as a verdict")
        return tuple(found)


# ── the verdict ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Report:
    """The whole answer. Constructed once, rendered two ways, never mutated."""

    state: str
    floor_percent: float
    reasons: tuple[str, ...] = ()
    manifest: Manifest | None = None
    shards_reported: tuple[int, ...] = ()
    shards_expected: int | None = None
    tally: Mapping[str, int] = field(default_factory=dict)
    killed: int | None = None
    denominator: int | None = None
    score: float | None = None
    reconciliation: Reconciliation | None = None

    @property
    def exit_code(self) -> int:
        return EXIT_CODE_BY_STATE[self.state]


# ── reading the manifest ─────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InfrastructureError(f"{path} could not be read: {error}") from error


def _json_object(text: str, where: str) -> Mapping[str, object]:
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as error:
        raise InfrastructureError(f"{where} is not valid JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise InfrastructureError(f"{where} is not a JSON object")
    return {str(key): value for key, value in loaded.items()}


def _string(body: Mapping[str, object], key: str, where: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise InfrastructureError(f"{where}: {key} is not a non-empty string ({value!r})")
    return value


def _integer(body: Mapping[str, object], key: str, where: str) -> int:
    value = body.get(key)
    # `bool` is a subclass of `int`, and `True` arriving as a shard index would
    # silently become shard 1.
    if not isinstance(value, int) or isinstance(value, bool):
        raise InfrastructureError(f"{where}: {key} is not an integer ({value!r})")
    return value


def _mutant_ids(body: Mapping[str, object], where: str) -> tuple[str, ...]:
    mutants = body.get("mutants")
    if not isinstance(mutants, list):
        raise InfrastructureError(f"{where}: mutants is not a list")
    if not mutants:
        raise InfrastructureError(
            f"{where}: the manifest lists no mutants, so there is nothing to score"
        )
    ids: list[str] = []
    for position, entry in enumerate(mutants):
        if not isinstance(entry, dict):
            raise InfrastructureError(f"{where}: mutants[{position}] is not a JSON object")
        value = entry.get("id")
        if not isinstance(value, str) or not value:
            raise InfrastructureError(f"{where}: mutants[{position}] has no usable id ({value!r})")
        ids.append(value)
    return tuple(ids)


def load_manifest(path: Path) -> Manifest:
    """The manifest, or an `InfrastructureError` naming what is wrong with it.

    The checks run in the order a reader needs them: a manifest with no mutants
    is reported as empty rather than as a count mismatch, because "expected 4,
    listed 0" describes the symptom and "the manifest lists no mutants"
    describes what happened.
    """
    where = str(path)
    body = _json_object(_read_text(path), where)
    strings = {key: _string(body, key, where) for key in MANIFEST_STRING_KEYS}
    ids = _mutant_ids(body, where)

    repeated = sorted({name for name in ids if ids.count(name) > 1})
    if repeated:
        raise InfrastructureError(f"{where}: duplicate mutant id(s) in the manifest: {repeated}")

    expected = _integer(body, "expected_mutants", where)
    if expected != len(ids):
        raise InfrastructureError(
            f"{where}: expected_mutants is {expected} and the manifest lists {len(ids)} mutants"
        )

    return Manifest(
        path=path,
        expected_mutants=expected,
        mutant_ids=ids,
        commit=strings["commit"],
        mutmut_version=strings["mutmut_version"],
        python_version=strings["python_version"],
        platform=strings["platform"],
        dependency_lock_hash=strings["dependency_lock_hash"],
        manifest_sha256=strings["manifest_sha256"],
    )


# ── reading a shard ──────────────────────────────────────────────────────────


def _header(text: str, path: Path) -> ShardHeader:
    where = f"{path}:1"
    body = _json_object(text, where)
    missing = [key for key in (*SHARD_STRING_KEYS, *SHARD_INT_KEYS) if key not in body]
    if missing:
        raise InfrastructureError(
            f"{where}: the first line of a shard result file must be a header object; "
            f"this one has no {missing}"
        )
    integers = {key: _integer(body, key, where) for key in SHARD_INT_KEYS}
    strings = {key: _string(body, key, where) for key in SHARD_STRING_KEYS}
    return ShardHeader(
        path=path,
        shard_index=integers["shard_index"],
        shard_count=integers["shard_count"],
        manifest_sha256=strings["manifest_sha256"],
        commit=strings["commit"],
        dependency_lock_hash=strings["dependency_lock_hash"],
    )


def _record(text: str, path: Path, line: int) -> Record | InvalidRecord:
    """One line, as a verdict or as a named reason it is not one.

    Never raises: a single unreadable record is a coverage defect
    (`FAIL_INCOMPLETE`), not an unusable input. Only the header can make a whole
    shard unusable.
    """
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as error:
        return InvalidRecord(path, line, f"not valid JSON: {error}")
    if not isinstance(loaded, dict):
        return InvalidRecord(path, line, "not a JSON object")

    mutant_id = loaded.get("id")
    if not isinstance(mutant_id, str) or not mutant_id:
        return InvalidRecord(path, line, f"no usable id ({mutant_id!r})")

    status = loaded.get("status")
    if not isinstance(status, str):
        return InvalidRecord(path, line, f"{mutant_id}: status is not a string ({status!r})")
    if status not in TERMINAL_STATUSES:
        return InvalidRecord(
            path, line, f"{mutant_id}: status {status!r} is not one of {list(TERMINAL_STATUSES)}"
        )
    return Record(mutant_id=mutant_id, status=status, path=path, line=line)


def load_shard(path: Path) -> Shard:
    """One shard result file: its header, its verdicts, and its bad lines.

    Whitespace-only lines are skipped. Every JSONL writer ends its last line
    with a newline, so reading that as a malformed record would refuse every
    correct file ever produced.
    """
    lines = _read_text(path).splitlines()
    body = [(number, text) for number, text in enumerate(lines, start=1) if text.strip()]
    if not body:
        raise InfrastructureError(f"{path} contains no lines, so it claims no shard and no results")

    header = _header(body[0][1], path)
    records: list[Record] = []
    invalid: list[InvalidRecord] = []
    for number, text in body[1:]:
        parsed = _record(text, path, number)
        if isinstance(parsed, Record):
            records.append(parsed)
        else:
            invalid.append(parsed)
    return Shard(header=header, records=tuple(records), invalid=tuple(invalid))


# ── are these results even about the same thing? ─────────────────────────────


def _partition_conflicts(headers: Sequence[ShardHeader]) -> list[str]:
    found: list[str] = []
    counts = sorted({header.shard_count for header in headers})
    if len(counts) > 1:
        found.append(f"the shards disagree about shard_count: {counts}")
    by_index: dict[int, list[Path]] = {}
    for header in headers:
        if header.shard_count < 1:
            found.append(f"{header.path}: shard_count is {header.shard_count}")
        elif not 0 <= header.shard_index < header.shard_count:
            found.append(
                f"{header.path}: shard_index {header.shard_index} is outside "
                f"the partition of {header.shard_count}"
            )
        by_index.setdefault(header.shard_index, []).append(header.path)
    # Counted by INDEX and not by path, so passing the same file twice is caught
    # by the same line that catches two different files claiming one slice.
    # Comparing paths instead would let a repeated `--shard` through here and
    # report it downstream as "every mutant has two records", which describes
    # the symptom and hides the cause.
    found.extend(
        f"shard {index} was reported {len(paths)} times: {', '.join(str(path) for path in paths)}"
        for index, paths in sorted(by_index.items())
        if len(paths) > 1
    )
    return found


def _provenance_conflicts(manifest: Manifest, headers: Sequence[ShardHeader]) -> list[str]:
    expected = {
        "manifest_sha256": manifest.manifest_sha256,
        "commit": manifest.commit,
        "dependency_lock_hash": manifest.dependency_lock_hash,
    }
    found: list[str] = []
    for header in headers:
        actual = {
            "manifest_sha256": header.manifest_sha256,
            "commit": header.commit,
            "dependency_lock_hash": header.dependency_lock_hash,
        }
        found.extend(
            f"{header.path}: {key} is {actual[key]}, the manifest says {value}"
            for key, value in expected.items()
            if actual[key] != value
        )
    return found


def conflicts(manifest: Manifest, shards: Sequence[Shard]) -> tuple[str, ...]:
    """Every reason these shards cannot be combined into one measurement.

    Empty means the shards agree about WHAT was measured. It says nothing about
    whether they covered it — that is `reconcile`, and the two are separate
    because they have different fixes and different states.
    """
    headers = [shard.header for shard in shards]
    return (*_partition_conflicts(headers), *_provenance_conflicts(manifest, headers))


# ── did they cover it? ───────────────────────────────────────────────────────


def _repeated(names: Iterable[str]) -> tuple[str, ...]:
    counted = Counter(names)
    return tuple(sorted(name for name, count in counted.items() if count > 1))


def reconcile(manifest: Manifest, shards: Sequence[Shard]) -> Reconciliation:
    """Set difference, both directions, plus the shards that never spoke."""
    expected = set(manifest.mutant_ids)
    reported = [record.mutant_id for shard in shards for record in shard.records]
    seen = set(reported)

    declared = max(header.shard_count for header in (shard.header for shard in shards))
    present = {shard.header.shard_index for shard in shards}

    return Reconciliation(
        missing=tuple(name for name in manifest.mutant_ids if name not in seen),
        unexpected=tuple(sorted(seen - expected)),
        duplicated=_repeated(reported),
        invalid=tuple(item for shard in shards for item in shard.invalid),
        absent_shards=tuple(index for index in range(declared) if index not in present),
    )


# ── the whole answer ─────────────────────────────────────────────────────────


def aggregate(manifest_path: Path, shard_paths: Sequence[Path], floor_percent: float) -> Report:
    """Manifest plus shards plus a floor, in — exactly one state, out.

    Never raises. Every failure becomes a `Report`, because a tool that dies
    with a traceback leaves CI in the ambiguous state this whole mechanism
    exists to remove.
    """
    try:
        manifest = load_manifest(manifest_path)
        shards = [load_shard(path) for path in shard_paths]
        if not shards:
            # Found by probing this function directly rather than through the
            # CLI, where `--shard` is required. Without it `max()` over an empty
            # sequence raised `ValueError` two lines below and the promise above
            # — never raises — was simply false.
            raise InfrastructureError("no shard result files were given, so nothing was measured")
    except InfrastructureError as error:
        return Report(
            state=STATE_FAIL_INFRASTRUCTURE, floor_percent=floor_percent, reasons=(str(error),)
        )

    tally: Mapping[str, int] = dict(
        sorted(Counter(record.status for shard in shards for record in shard.records).items())
    )
    # Everything already known, carried into whichever verdict follows. Built as
    # a refusal and narrowed by `replace`, so a new field cannot be added to
    # `Report` and then forgotten at one of the three exits below.
    read = Report(
        state=STATE_FAIL_INFRASTRUCTURE,
        floor_percent=floor_percent,
        manifest=manifest,
        shards_reported=tuple(sorted(shard.header.shard_index for shard in shards)),
        shards_expected=max(shard.header.shard_count for shard in shards),
        tally=tally,
    )

    unusable = conflicts(manifest, shards)
    if unusable:
        return replace(read, reasons=unusable)

    reconciliation = reconcile(manifest, shards)
    if not reconciliation.complete:
        return replace(
            read,
            state=STATE_FAIL_INCOMPLETE,
            reasons=reconciliation.reasons(),
            reconciliation=reconciliation,
        )

    # OWNER SPEC §5, approved 2026-08-06. The score is `killed / (killed +
    # survived)`, and it is computed ONLY on the far side of reconciliation —
    # which is what makes this denominator safe.
    #
    # THE EARLIER RULE, AND WHY IT CHANGED. This module first used the whole
    # manifest as the denominator, so a timeout cost exactly what a survivor
    # cost. That is stricter, and it was wrong for a stated reason: it answers a
    # different question. `killed / (killed + survived)` asks *"when a test could
    # have noticed, did it?"* — a fact about the SUITE. A timeout is a fact about
    # the RUNNER. Mixing them produces a number that moves when CI gets slower,
    # and a suite-quality metric that degrades because a machine was busy is not
    # measuring the suite.
    #
    # THE SHRINKING-DENOMINATOR HAZARD IS NOT REINTRODUCED, because completeness
    # is enforced ABOVE this line: `reconciliation.complete` has already proven
    # every manifest ID carries exactly one terminal result. The old failure was
    # `killed / (killed + survived)` over a partial run — 2440/(2440+288) = 89.44%
    # across 65% of the tree. Here that state returns FAIL_INCOMPLETE and never
    # reaches this arithmetic at all.
    #
    # Timeouts, errors and cancellations are NOT discarded — they are reported as
    # their own counts, so a run can be complete, scored, and still visibly sick.
    killed = tally.get(KILLED, 0)
    survived = tally.get(SURVIVED, 0)
    denominator = killed + survived
    # Every mutant timed out or errored: no test was ever given the chance to
    # notice, so there is no score to state. `0/0` is not 0% and not 100%.
    if denominator == 0:
        return replace(
            read,
            state=STATE_FAIL_INCOMPLETE,
            reasons=(
                "no mutant reached a killed or survived verdict, so the suite was "
                "never actually asked a question — the run is complete but unscoreable",
            ),
            reconciliation=reconciliation,
            killed=killed,
            denominator=denominator,
        )
    score = PERCENT * killed / denominator
    below = score < floor_percent
    return replace(
        read,
        state=STATE_FAIL_SCORE if below else STATE_PASS,
        reasons=(f"the mutation score is below the floor of {floor_percent}",) if below else (),
        reconciliation=reconciliation,
        killed=killed,
        denominator=denominator,
        score=score,
    )


# ── the two reports ──────────────────────────────────────────────────────────


def _counts(report: Report) -> dict[str, object]:
    """The thirteen counts of owner spec §5, reconciled mathematically.

    WHY EACH IS SEPARATE AND NONE IS DERIVED FROM A WORKER'S SELF-REPORT.
    `reported_count` and `unique_reported_count` differ exactly when a mutant was
    recorded twice — a retry that appended instead of replacing, or two shards
    that both believed they owned it. Collapsing them into one number is how that
    defect stays invisible, so they are counted apart and compared.

    `manifest_coverage_percent` is the run's honesty metric, and it is the one
    number that is meaningful even when `score_percent` is null.
    """
    manifest = report.manifest
    reconciliation = report.reconciliation
    tally = report.tally

    manifest_count = None if manifest is None else manifest.expected_mutants
    duplicated = () if reconciliation is None else reconciliation.duplicated
    missing = () if reconciliation is None else reconciliation.missing

    reported = sum(tally.values())
    duplicate_count = len(duplicated)
    unique_reported = reported - duplicate_count
    coverage = (
        None if not manifest_count else PERCENT * (manifest_count - len(missing)) / manifest_count
    )
    return {
        "manifest_count": manifest_count,
        "assigned_count": manifest_count,
        "reported_count": reported,
        "unique_reported_count": unique_reported,
        "duplicate_count": duplicate_count,
        "missing_count": len(missing),
        "killed_count": tally.get(KILLED, 0),
        "survived_count": tally.get(SURVIVED, 0),
        "timeout_count": tally.get(TIMEOUT, 0),
        "error_count": (
            tally.get(ERROR, 0) + tally.get(COMPILE_ERROR, 0) + tally.get(RUNTIME_ERROR, 0)
        ),
        "infrastructure_failure_count": (
            tally.get(INFRASTRUCTURE_FAILURE, 0) + tally.get(INFRASTRUCTURE_ERROR, 0)
        ),
        "cancelled_count": tally.get(CANCELLED, 0),
        "manifest_coverage_percent": coverage,
    }


def machine_report(report: Report) -> dict[str, object]:
    """The verdict as JSON. Nothing is truncated and nothing is rounded.

    `score_percent` is `null` for every state that did not earn a number, which
    is the one field a downstream consumer must branch on.
    """
    manifest = report.manifest
    reconciliation = report.reconciliation
    return {
        "state": report.state,
        "exit_code": report.exit_code,
        "floor_percent": report.floor_percent,
        "score_percent": report.score,
        "killed": report.killed,
        "denominator": report.denominator,
        "tally": dict(report.tally),
        # OWNER SPEC §5 — the thirteen counts, every one derived from the actual
        # manifest and the actual result IDs, never from a worker's own total.
        # A worker that says "I did 277" is making a claim; a set of 277 distinct
        # IDs is evidence. Only the second is counted here.
        **_counts(report),
        "commit": None if manifest is None else manifest.commit,
        "manifest_sha256": None if manifest is None else manifest.manifest_sha256,
        "dependency_lock_hash": None if manifest is None else manifest.dependency_lock_hash,
        "mutmut_version": None if manifest is None else manifest.mutmut_version,
        "python_version": None if manifest is None else manifest.python_version,
        "platform": None if manifest is None else manifest.platform,
        "expected_mutants": None if manifest is None else manifest.expected_mutants,
        "shards_expected": report.shards_expected,
        "shards_reported": list(report.shards_reported),
        "reasons": list(report.reasons),
        "missing": [] if reconciliation is None else list(reconciliation.missing),
        "unexpected": [] if reconciliation is None else list(reconciliation.unexpected),
        "duplicated": [] if reconciliation is None else list(reconciliation.duplicated),
        "absent_shards": [] if reconciliation is None else list(reconciliation.absent_shards),
        "invalid": [] if reconciliation is None else [str(item) for item in reconciliation.invalid],
    }


def _listed(label: str, entries: Sequence[str]) -> list[str]:
    if not entries:
        return []
    shown = list(entries[:LONGEST_HUMAN_LIST])
    rest = len(entries) - len(shown)
    body = ", ".join(shown) + (f", and {rest} more" if rest else "")
    return [f"    {label} ({len(entries)}): {body}"]


def _provenance(report: Report) -> list[str]:
    manifest = report.manifest
    unknown = "UNKNOWN"
    shards = (
        unknown
        if report.shards_expected is None
        else f"{len(report.shards_reported)} of {report.shards_expected}"
    )
    return [
        f"  commit               : {unknown if manifest is None else manifest.commit}",
        f"  manifest sha256      : {unknown if manifest is None else manifest.manifest_sha256}",
        f"  dependency lock hash : "
        f"{unknown if manifest is None else manifest.dependency_lock_hash}",
        f"  mutmut / python      : "
        f"{unknown if manifest is None else manifest.mutmut_version} / "
        f"{unknown if manifest is None else manifest.python_version} on "
        f"{unknown if manifest is None else manifest.platform}",
        f"  shards reported      : {shards}",
        f"  mutants in manifest  : {unknown if manifest is None else manifest.expected_mutants}",
    ]


def _refusal(report: Report) -> list[str]:
    """The failure half of the summary — and it contains no percentage.

    Deliberate, and tested. `2440 killed / 288 survived` beside the word BLOCKED
    is one division away from 89.44%, and somebody eventually does that division
    and quotes it. What is printed here is the verdict and the mutants with no
    usable verdict, never a number that reads like a score.
    """
    lines = [
        "",
        "  NO SCORE. The records do not account for the manifest, so no score was",
        "  computed and none is reported. What follows is diagnosis, not measurement:",
    ]
    lines.extend(f"    - {reason}" for reason in report.reasons)
    reconciliation = report.reconciliation
    if reconciliation is not None:
        lines.extend(_listed("missing", reconciliation.missing))
        lines.extend(_listed("unexpected", reconciliation.unexpected))
        lines.extend(_listed("duplicated", reconciliation.duplicated))
        lines.extend(_listed("never reported", [str(i) for i in reconciliation.absent_shards]))
        lines.extend(_listed("unreadable", [str(item) for item in reconciliation.invalid]))
    if report.tally:
        lines.append("    records seen, which is NOT a measurement of this tree:")
        lines.extend(f"      {status:22} {count}" for status, count in report.tally.items())
    return lines


def human_summary(report: Report) -> str:
    """The verdict for a person reading a CI log."""
    lines = [f"mutation aggregate — {report.state}", *_provenance(report)]
    if report.score is None:
        lines.extend(_refusal(report))
        return "\n".join(lines)

    manifest = report.manifest
    commit = "UNKNOWN" if manifest is None else manifest.commit
    lines.extend(f"  {status:20} : {count}" for status, count in report.tally.items())
    # Law 56, made literal: the number and the commit that produced it are one
    # string, so no copy of it can arrive anywhere without its provenance.
    lines.append(
        f"  mutation score       : {report.score:.2f}% @ {commit}  "
        f"(floor {report.floor_percent:.2f}%)"
    )
    lines.extend(f"  {reason}" for reason in report.reasons)
    return "\n".join(lines)


# ── the command line ─────────────────────────────────────────────────────────


def percentage(text: str) -> float:
    """A floor on the percentage scale, or an `argparse` refusal.

    A floor above 100 can never be met and a negative one can never be missed;
    either is a gate that returns the same verdict forever regardless of the
    code. This is arithmetic domain, not policy: WHICH floor applies is the
    workflow's decision and is never made here.
    """
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from error
    if not LOWEST_FLOOR <= value <= HIGHEST_FLOOR:
        raise argparse.ArgumentTypeError(
            f"{value} is outside the percentage scale {LOWEST_FLOOR}..{HIGHEST_FLOOR}"
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile sharded mutation results and publish a score only if earned.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manifest", type=Path, required=True, help="the run manifest, JSON")
    parser.add_argument(
        "--shard",
        type=Path,
        action="append",
        required=True,
        metavar="PATH",
        help="one shard result file; repeat once per shard",
    )
    # No `default=`. The mutation floor is declared in
    # `.github/workflows/testing.yml` and a default here would be a second one.
    parser.add_argument(
        "--floor", type=percentage, required=True, metavar="PERCENT", help="the mutation floor"
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        metavar="PATH",
        help="where the JSON report is written",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = aggregate(args.manifest, args.shard, args.floor)

    body = json.dumps(machine_report(report), indent=2, sort_keys=True)
    try:
        args.report.write_text(body + "\n", encoding="utf-8")
    except OSError as error:
        # Loud, and never green: the machine report is the record of what was
        # measured, and exiting zero without one hands CI a verdict nobody can
        # audit.
        raise SystemExit(
            f"the machine report could not be written to {args.report}: {error}"
        ) from error

    print(human_summary(report))
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
