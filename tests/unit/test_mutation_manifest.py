"""The manifest, and the five ways an input side can lie about the universe.

WHAT IS BEING GUARDED. `tools/ci/mutation_manifest.py` answers two questions
before a single mutant is executed: *which mutants exist, with what context* and
*which worker runs each one*. Five failures would make it worse than nothing, and
each is attacked here rather than assumed away:

    the recorded universe is a SUBSET of the
    generated one                             -> the denominator shrinks silently
    the same input produces different IDs on
    two machines                              -> shards cannot be compared at all
    a mutant lands in two shards, or in none  -> the score is over the wrong set
    COST decides what is included, not just
    where it goes                             -> the exact way ~1536 were lost
    a shard balance is called `measured` when
    nothing was measured                      -> a fabricated number (Law 24)

THE ORACLE IS MUTMUT ITSELF. Every structural claim below is finally checked
against a REAL `mutmut run` over a four-mutant project: the manifest must name
exactly the mutants mutmut generated, locate them where mutmut's own span index
says they are, and quote the original that mutmut copied. A manifest checked only
against a hand-written fixture would prove the fixture.

WHY THE HAND-WRITTEN TREES ARE NOT MOCKS (§J.6). They are real files in mutmut's
real on-disk layout — `<source>`, `<source>.meta`, `<source>.spans`,
`mutmut-stats.json` — read by the real readers.
`test_the_hand_written_copy_matches_the_shape_mutmut_writes` proves the layout
matches what mutmut actually produced, so the cheap fixtures cannot drift away
from the tool.

IT NEVER SKIPS. If mutmut cannot run, this file fails.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from importlib import metadata
from pathlib import Path

import mutation_denominator as md
import mutation_manifest as mm
import pytest

# Imported from where they are DEFINED, never through `mutation_manifest`.
# `no_implicit_reexport` is on, and a test reaching a constant through whichever
# module happened to import it is how a name quietly becomes public API.
from authored_source import MUTATION_COPY_DIRECTORY, authored_repo_root

# ═══════════════════════════════════════════════════════════════════════════
# Fixture builders. Real files, real JSON, real readers — nothing is patched.
# ═══════════════════════════════════════════════════════════════════════════

#: A stand-in environment. Every field is provenance only: none of them may
#: reach `manifest_sha256`, and `test_the_hash_covers_the_mutant_list_alone`
#: proves it.
PROBE_ENVIRONMENT = mm.Environment(
    commit="0123456789abcdef0123456789abcdef01234567",
    mutmut_version="3.7.0",
    python_version="3.12.13",
    platform="probe-platform",
    dependency_lock_hash="d" * 64,
)

FOUR = 4
TWO = 2
THREE = 3
FIVE = 5
#: 30 expressions -> one original and 29 mutants.
TWENTY_NINE = 29
SIXTEEN = mm.OWNER_SHARD_COUNT

#: One file's functions: `(function, (original_expression, *mutant_expressions))`.
Functions = Sequence[tuple[str, Sequence[str]]]
#: One file: `(authored path, dotted module, functions)`.
File = tuple[str, str, Functions]

#: Two files, written in an order that is neither sorted nor grouped, so any
#: reliance on input order shows up. `x_go` carries two mutants, `x_add` and
#: `x_sub` one each — four in total.
UNSORTED: tuple[File, ...] = (
    ("src/probe/zebra.py", "probe.zebra", (("x_go", ("1", "2", "3")),)),
    (
        "src/probe/alpha.py",
        "probe.alpha",
        (("x_add", ("a + b", "a - b")), ("x_sub", ("a - b", "a"))),
    ),
)


def render(functions: Functions) -> tuple[str, dict[str, list[int]]]:
    """One mutated file's text, and the span index mutmut writes beside it.

    Two lines per generated function, exactly as mutmut lays them out: the
    untouched `__mutmut_orig` first, then `__mutmut_1..N`.
    """
    lines: list[str] = []
    spans: dict[str, list[int]] = {}
    for function, expressions in functions:
        suffixes = ["orig", *[str(index) for index in range(1, len(expressions))]]
        for suffix, expression in zip(suffixes, expressions, strict=True):
            generated = f"{function}{md.MUTANT_INDEX_SEPARATOR}{suffix}"
            start = len(lines) + 1
            lines.append(f"def {generated}(a, b):\n")
            lines.append(f"    return {expression}\n")
            spans[generated] = [start, len(lines)]
        lines.append(f"mutants_{function}__mutmut = {{}}\n")
    return "".join(lines), spans


def mutant_names(module: str, functions: Functions) -> list[str]:
    """mutmut's keys for every mutant these functions generate."""
    return [
        f"{module}.{function}{md.MUTANT_INDEX_SEPARATOR}{index}"
        for function, expressions in functions
        for index in range(1, len(expressions))
    ]


def write_copy(
    root: Path,
    files: Sequence[File] = UNSORTED,
    durations: Mapping[str, float] | None = None,
    covering: Mapping[str, Sequence[str]] | None = None,
) -> Path:
    """Write a complete `mutants/` tree and return its directory.

    Every artifact mutmut writes and this module reads: the mutated source, the
    `.meta` verdict store, the `.spans` line index and `mutmut-stats.json`.
    `None` is the exit code mutmut writes at generation time, before anything has
    been executed (`mutmut/__main__.py:348-358`).
    """
    mutants_dir = root / MUTATION_COPY_DIRECTORY
    measured = dict(durations or {})
    tests_by_function: dict[str, list[str]] = {}
    for source, module, functions in files:
        text, spans = render(functions)
        path = mutants_dir / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.with_name(path.name + mm.SPANS_SUFFIX).write_text(
            json.dumps({"version": mm.SPANS_FORMAT_VERSION, "spans": spans}), encoding="utf-8"
        )
        names = mutant_names(module, functions)
        path.with_name(path.name + ".meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": dict.fromkeys(names),
                    "hash_by_function_name": {},
                    "type_check_error_by_key": {},
                    "durations_by_key": {n: measured[n] for n in names if n in measured},
                    "estimated_durations_by_key": {},
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        for function, _ in functions:
            key = f"{module}.{function}"
            supplied = None if covering is None else covering.get(key)
            tests_by_function[key] = (
                list(supplied) if supplied is not None else [f"tests/test_{function}.py::test_it"]
            )
    (mutants_dir / md.STATS_FILENAME).write_text(
        json.dumps({"tests_by_mangled_function_name": tests_by_function}), encoding="utf-8"
    )
    return mutants_dir


def probe_manifest(root: Path, **kwargs: object) -> mm.Manifest:
    """A four-mutant manifest built from a real tree by the real readers."""
    durations = kwargs.get("durations")
    assert durations is None or isinstance(durations, Mapping)
    return mm.generate_manifest(write_copy(root, durations=durations), PROBE_ENVIRONMENT)


def parsed(text: str) -> dict[str, object]:
    """A JSON object, typed, so assertions below index it without `Any`."""
    loaded = json.loads(text)
    assert isinstance(loaded, dict), f"not a JSON object: {text[:200]}"
    return {str(key): value for key, value in loaded.items()}


def mutant_rows(document: Mapping[str, object]) -> list[dict[str, object]]:
    """The `mutants` array of a manifest document, as plain typed rows."""
    rows = document["mutants"]
    assert isinstance(rows, list)
    typed: list[dict[str, object]] = []
    for row in rows:
        assert isinstance(row, dict)
        typed.append({str(key): value for key, value in row.items()})
    return typed


def rebuilt(rows: Sequence[Mapping[str, object]]) -> tuple[mm.ManifestEntry, ...]:
    """Entries from raw rows, so a test can re-digest a document it edited."""
    entries: list[mm.ManifestEntry] = []
    for row in rows:
        span = row["line_span"]
        assert isinstance(span, list)
        targets = row["test_target"]
        assert isinstance(targets, list)
        entries.append(
            mm.ManifestEntry(
                id=str(row["id"]),
                name=str(row["name"]),
                source=str(row["source"]),
                line_span=(int(span[0]), int(span[1])),
                operator=str(row["operator"]),
                original=str(row["original"]),
                test_target=tuple(str(target) for target in targets),
            )
        )
    return tuple(entries)


def entry(name: str, source: str = "src/probe/alpha.py") -> md.Mutant:
    """One `Mutant` as `read_mutants` would produce it before any run."""
    return md.Mutant(
        name=name, source=source, exit_code=None, status="not checked", status_was_defaulted=False
    )


DETAIL: dict[str, tuple[tuple[int, int], str, str, tuple[str, ...]]] = {}


def detail_for(
    names: Sequence[str],
) -> dict[str, tuple[tuple[int, int], str, str, tuple[str, ...]]]:
    """Stand-in per-mutant context, for the ordering tests that build by hand."""
    return {
        name: ((1, 2), f"-  {name}\n+  mutated", f"def {name}_orig(): ...", ("tests/t.py::t",))
        for name in names
    }


# ═══════════════════════════════════════════════════════════════════════════
# §1 FREEZE. Every generated mutant, exactly once, with all four fields.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_manifest_names_every_mutant_in_the_meta_store_exactly_once(tmp_path: Path) -> None:
    """The denominator is the whole tree or it is not a denominator."""
    mutants_dir = write_copy(tmp_path)
    expected = {mutant.name for mutant in md.read_mutants(mutants_dir)}

    manifest = mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)

    named = [item.name for item in manifest.entries]
    assert sorted(named) == sorted(expected)
    assert len(named) == len(set(named)), f"a name appears twice: {named}"
    assert manifest.expected_mutants == FOUR


def test_a_mutant_with_no_exit_code_is_still_in_the_universe(tmp_path: Path) -> None:
    """The exact CI shape: mutmut writes `None` for every mutant at generation
    time and fills exit codes in as it goes, so a run killed part-way leaves a
    meta store of mostly-`None`. If the manifest counted only mutants with a
    verdict it would freeze 2893 instead of 4429 and call the shortfall success.
    """
    mutants_dir = write_copy(tmp_path)
    codes = json.loads((mutants_dir / "src/probe/alpha.py.meta").read_text(encoding="utf-8"))

    assert set(codes["exit_code_by_key"].values()) == {None}, "precondition: nothing has run"
    assert mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT).expected_mutants == FOUR


def test_every_mutant_carries_a_location_an_operator_an_original_and_a_test_target(
    tmp_path: Path,
) -> None:
    """§1 of the spec, field by field. A manifest missing any of these cannot
    drive a worker: without the location nobody can find the mutant, without the
    test target nobody knows what to run, and without the original and the edit
    nobody reading a survivor can tell what it did.
    """
    manifest = mm.generate_manifest(write_copy(tmp_path), PROBE_ENVIRONMENT)

    first = next(item for item in manifest.entries if item.name.endswith("x_add__mutmut_1"))
    assert first.source == "src/probe/alpha.py"
    assert first.line_span == (3, 4), "the mutant's own lines in the mutation copy"
    assert first.operator == "-    return a + b\n+    return a - b"
    assert first.original == "def x_add__mutmut_orig(a, b):\n    return a + b\n"
    assert first.test_target == ("tests/test_x_add.py::test_it",)
    for item in manifest.entries:
        assert item.line_span[0] >= 1 and item.line_span[1] >= item.line_span[0]
        assert item.operator and item.original and item.test_target


def test_a_mutant_no_test_covers_records_an_empty_target_rather_than_a_missing_one(
    tmp_path: Path,
) -> None:
    """An empty test target is a REAL answer — mutmut scores such a mutant
    `no tests` (exit code 33). It must be distinguishable from a manifest that
    never learned the targets at all, which is why the test below exists.
    """
    mutants_dir = write_copy(tmp_path, covering={"probe.alpha.x_add": []})

    manifest = mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)

    uncovered = next(item for item in manifest.entries if "x_add" in item.name)
    covered = next(item for item in manifest.entries if "x_sub" in item.name)
    assert uncovered.test_target == ()
    assert covered.test_target != ()


def test_a_manifest_cannot_be_frozen_before_the_test_targets_exist(tmp_path: Path) -> None:
    """`mutmut-stats.json` is written by the stats phase, after generation. A
    manifest built before it exists would give EVERY mutant an empty target,
    which is indistinguishable from "no test covers this" — a real and different
    answer. Refused, naming the fix, rather than emitting a column of empties.
    """
    mutants_dir = write_copy(tmp_path)
    (mutants_dir / md.STATS_FILENAME).unlink()

    with pytest.raises(md.MutationResultsUnavailableError):
        mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)


def test_a_mutant_the_span_index_cannot_locate_is_refused(tmp_path: Path) -> None:
    """A mutant nobody can locate is a mutant nobody can run, and silently
    dropping it is the shrinking denominator this module exists to end.
    """
    mutants_dir = write_copy(tmp_path)
    spans_path = mutants_dir / ("src/probe/alpha.py" + mm.SPANS_SUFFIX)
    index = parsed(spans_path.read_text(encoding="utf-8"))
    spans = index["spans"]
    assert isinstance(spans, dict)
    del spans["x_add__mutmut_1"]
    spans_path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="x_add__mutmut_1"):
        mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)


def test_a_span_index_of_an_unknown_format_is_refused(tmp_path: Path) -> None:
    """mutmut's own loader returns `None` for a version it does not understand
    (`data.py:51-52`). Reading a v2 index as v1 would attribute the wrong lines
    to every mutant, and every `original` quoted afterwards would be fiction.
    """
    mutants_dir = write_copy(tmp_path)
    spans_path = mutants_dir / ("src/probe/alpha.py" + mm.SPANS_SUFFIX)
    index = parsed(spans_path.read_text(encoding="utf-8"))
    index["version"] = mm.SPANS_FORMAT_VERSION + 1
    spans_path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="span format"):
        mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)


def test_a_mutant_identical_to_its_original_is_refused(tmp_path: Path) -> None:
    """An unkillable entry in the denominator is worse than a missing one: no
    test can ever kill it, so it depresses the score forever and looks like a
    testing gap that no amount of testing closes.
    """
    identical: tuple[File, ...] = (
        ("src/probe/alpha.py", "probe.alpha", (("x_add", ("a + b", "a + b")),)),
    )

    with pytest.raises(mm.ManifestError, match="textually identical"):
        mm.generate_manifest(write_copy(tmp_path, identical), PROBE_ENVIRONMENT)


def test_ids_come_from_a_canonical_order_and_not_from_the_input_order(tmp_path: Path) -> None:
    """A dict iteration order or an `rglob` order is a property of a machine. An
    ID derived from either makes shard 3 of 16 mean different things on the
    generator and the runner, which is the whole reason the manifest exists.
    """
    mutants = md.read_mutants(write_copy(tmp_path))
    detail = detail_for([mutant.name for mutant in mutants])

    forwards = mm.manifest_from_mutants(mutants, PROBE_ENVIRONMENT, detail)
    backwards = mm.manifest_from_mutants(tuple(reversed(mutants)), PROBE_ENVIRONMENT, detail)

    assert backwards.entries == forwards.entries
    assert [item.id for item in forwards.entries] == [
        "M-000001",
        "M-000002",
        "M-000003",
        "M-000004",
    ]


def test_each_id_is_used_by_exactly_one_mutant(tmp_path: Path) -> None:
    ids = [item.id for item in probe_manifest(tmp_path).entries]

    assert len(ids) == len(set(ids))
    assert ids == sorted(ids), "IDs must ascend with the canonical order"


def test_generating_the_same_universe_twice_produces_identical_bytes(tmp_path: Path) -> None:
    """No timestamp, no run counter, no machine-local field anywhere in the
    document. A manifest that differs from itself proves nothing about anything.
    """
    assert probe_manifest(tmp_path / "a").to_json() == probe_manifest(tmp_path / "b").to_json()


def test_an_empty_universe_is_refused_rather_than_recorded_as_zero() -> None:
    """Zero mutants is not a small universe; it is a broken generation step, and
    a manifest saying `expected_mutants: 0` would make every later check vacuous.
    """
    with pytest.raises(mm.ManifestError, match="no mutants"):
        mm.manifest_from_mutants((), PROBE_ENVIRONMENT, {})


def test_a_repeated_mutant_name_is_refused() -> None:
    """The runtime history is keyed by NAME, so two mutants sharing one name
    makes a measured cost ambiguous. Refused loudly rather than deduplicated.
    """
    name = "probe.alpha.x_add__mutmut_1"

    with pytest.raises(mm.ManifestError, match=re.escape(name)):
        mm.manifest_from_mutants((entry(name), entry(name)), PROBE_ENVIRONMENT, detail_for([name]))


def test_one_name_claimed_by_two_source_files_is_refused() -> None:
    """A mutant belongs to exactly one file. Two claims means the meta store is
    corrupt, and picking either one would be a guess.
    """
    name = "probe.alpha.x_add__mutmut_1"
    conflicting = (entry(name, "src/probe/alpha.py"), entry(name, "src/probe/zebra.py"))

    with pytest.raises(mm.ManifestError, match="more than once"):
        mm.manifest_from_mutants(conflicting, PROBE_ENVIRONMENT, detail_for([name]))


def test_a_mutant_with_no_recorded_context_is_refused() -> None:
    """Every mutant carries all four fields or none does. A row silently missing
    its original would look complete and explain nothing.
    """
    name = "probe.alpha.x_add__mutmut_1"

    with pytest.raises(mm.ManifestError, match="no location"):
        mm.manifest_from_mutants((entry(name),), PROBE_ENVIRONMENT, {})


# ═══════════════════════════════════════════════════════════════════════════
# THE HASH. Its canonicalisation is stated, and every field is inside it.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_digest_matches_the_canonicalisation_the_module_docstring_states(
    tmp_path: Path,
) -> None:
    """§4 OF THE SPEC. The aggregator COMPARES this hash and does not recompute
    it, so an undocumented canonicalisation lets the two halves agree by accident
    and disagree later for a reason nobody can name.

    The recipe is restated here INDEPENDENTLY rather than imported, so a silent
    change to the module's serialisation fails this test instead of quietly
    redefining what both sides mean by `the same universe`.
    """
    manifest = probe_manifest(tmp_path)

    rows = [
        {
            "id": item.id,
            "line_span": [item.line_span[0], item.line_span[1]],
            "name": item.name,
            "operator": item.operator,
            "original": item.original,
            "source": item.source,
            "test_target": list(item.test_target),
        }
        for item in manifest.entries
    ]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == manifest.manifest_sha256
    assert '", "' not in payload, "separators must strip every optional space"


def test_the_hash_covers_the_mutant_list_alone(tmp_path: Path) -> None:
    """The same universe measured on a different machine has the same
    `manifest_sha256`. That is what makes the hash answer *"is this the same set
    of mutants?"* rather than *"is this the same file?"*, and it is why the
    environment fields sit beside it and not inside.
    """
    mutants_dir = write_copy(tmp_path)
    elsewhere = mm.Environment(
        commit="f" * 40,
        mutmut_version="9.9.9",
        python_version="3.13.0",
        platform="another-platform",
        dependency_lock_hash="e" * 64,
    )

    here = mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT)
    there = mm.generate_manifest(mutants_dir, elsewhere)

    assert here.manifest_sha256 == there.manifest_sha256
    assert here.to_json() != there.to_json(), "the document must still record where it came from"


def test_the_hash_is_not_the_hash_of_the_document(tmp_path: Path) -> None:
    """A document cannot contain its own digest, so a reader that recomputed the
    digest over the whole file would never match. Proven by construction.
    """
    manifest = probe_manifest(tmp_path)
    text = manifest.to_json()

    assert parsed(text)["manifest_sha256"] == manifest.manifest_sha256
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() != manifest.manifest_sha256


def test_adding_a_mutant_changes_the_hash(tmp_path: Path) -> None:
    bigger: tuple[File, ...] = (
        ("src/probe/zebra.py", "probe.zebra", (("x_go", ("1", "2", "3")),)),
        (
            "src/probe/alpha.py",
            "probe.alpha",
            (("x_add", ("a + b", "a - b", "a * b")), ("x_sub", ("a - b", "a"))),
        ),
    )

    before = probe_manifest(tmp_path / "a").manifest_sha256
    after = mm.generate_manifest(write_copy(tmp_path / "b", bigger), PROBE_ENVIRONMENT)

    assert before != after.manifest_sha256
    assert after.expected_mutants == FOUR + 1


def test_removing_a_mutant_changes_the_hash(tmp_path: Path) -> None:
    mutants = md.read_mutants(write_copy(tmp_path))
    detail = detail_for([mutant.name for mutant in mutants])

    before = mm.manifest_from_mutants(mutants, PROBE_ENVIRONMENT, detail).manifest_sha256
    after = mm.manifest_from_mutants(mutants[1:], PROBE_ENVIRONMENT, detail).manifest_sha256

    assert before != after


def test_renaming_a_mutant_changes_the_hash(tmp_path: Path) -> None:
    """4429 against 4709 is the measured symptom this hash exists to name. A
    hash that only counted mutants would call two different universes equal.
    """
    mutants = md.read_mutants(write_copy(tmp_path))
    renamed = (entry("probe.alpha.x_add__mutmut_99"), *mutants[1:])
    detail = detail_for([mutant.name for mutant in (*mutants, *renamed)])

    before = mm.manifest_from_mutants(mutants, PROBE_ENVIRONMENT, detail).manifest_sha256
    after = mm.manifest_from_mutants(renamed, PROBE_ENVIRONMENT, detail).manifest_sha256

    assert before != after
    assert len(renamed) == len(mutants), "same count, different universe"


def test_the_digest_separates_universes_that_differ_only_in_source_file() -> None:
    """FOUND BY ATTACKING AN EARLIER TEST THAT PASSED FOR THE WRONG REASON.

    Dropping `source` from the digest payload once left the whole file green:
    moving a mutant between files changes the canonical ORDER, so its ID changes
    too, and the ID alone was enough to move the digest.

    Here the ID and the name are held IDENTICAL and only the file differs, which
    is a real collision: a one-mutant universe in `alpha.py` and the same mutant
    in `zebra.py` both sort first and both number `M-000001`.
    """
    fields = {
        "id": "M-000001",
        "name": "probe.calc.x_add__mutmut_1",
        "line_span": (3, 4),
        "operator": "-a\n+b",
        "original": "def x(): ...",
        "test_target": ("t::t",),
    }
    here = (mm.ManifestEntry(source="src/probe/alpha.py", **fields),)  # type: ignore[arg-type]
    there = (mm.ManifestEntry(source="src/probe/zebra.py", **fields),)  # type: ignore[arg-type]

    assert here[0].id == there[0].id and here[0].name == there[0].name, "precondition"
    assert mm.mutant_set_digest(here) != mm.mutant_set_digest(there)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("line_span", (99, 100), id="line_span"),
        pytest.param("operator", "-x\n+y", id="operator"),
        pytest.param("original", "def other(): ...", id="original"),
        pytest.param("test_target", ("tests/other.py::test",), id="test_target"),
    ],
)
def test_every_recorded_field_is_inside_the_digest(field: str, value: object) -> None:
    """Two shard results are comparable only when the same mutants ran against
    the same tests over the same code. Each field is varied ALONE, so a digest
    that quietly ignored one of them fails on exactly that row.
    """
    fields: dict[str, object] = {
        "id": "M-000001",
        "name": "probe.calc.x_add__mutmut_1",
        "source": "src/probe/alpha.py",
        "line_span": (3, 4),
        "operator": "-a\n+b",
        "original": "def x(): ...",
        "test_target": ("t::t",),
    }
    before = (mm.ManifestEntry(**fields),)  # type: ignore[arg-type]
    after = (mm.ManifestEntry(**{**fields, field: value}),)  # type: ignore[arg-type]

    assert mm.mutant_set_digest(before) != mm.mutant_set_digest(after)


# ═══════════════════════════════════════════════════════════════════════════
# THE DOCUMENT. Written once, read back fail-closed.
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA_KEYS = (
    "commit",
    "mutmut_version",
    "python_version",
    "platform",
    "dependency_lock_hash",
    "manifest_sha256",
    "expected_mutants",
    "mutants",
)
ROW_KEYS = {"id", "name", "source", "line_span", "operator", "original", "test_target"}


def test_the_document_carries_exactly_the_keys_the_schema_names(tmp_path: Path) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())

    assert tuple(document) == SCHEMA_KEYS
    assert all(set(row) == ROW_KEYS for row in mutant_rows(document))


def test_expected_mutants_equals_the_length_of_the_list_it_describes(tmp_path: Path) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())

    assert document["expected_mutants"] == len(mutant_rows(document))


def test_a_manifest_round_trips_through_a_file(tmp_path: Path) -> None:
    written = probe_manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(written.to_json(), encoding="utf-8")

    reloaded = mm.read_manifest(path)

    assert reloaded == written
    assert reloaded.to_json() == written.to_json()


def test_a_tampered_mutant_list_is_refused_by_the_hash(tmp_path: Path) -> None:
    """The point of writing the digest down: a manifest edited after the fact is
    not a manifest. Read fail-closed or the freeze is decoration.
    """
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = mutant_rows(document)
    rows[0]["operator"] = "-  nothing\n+  nothing"
    document["mutants"] = rows
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="manifest_sha256"):
        mm.read_manifest(path)


def test_a_tampered_id_is_refused_even_when_the_hash_is_recomputed(tmp_path: Path) -> None:
    """The second, independent guard. An attacker who edits an ID and rewrites
    the digest defeats the hash — so IDs are re-derived from the canonical order
    on read and compared, and a hand-assigned ID never survives.
    """
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = mutant_rows(document)
    rows[0]["id"], rows[1]["id"] = rows[1]["id"], rows[0]["id"]
    document["mutants"] = rows
    document["manifest_sha256"] = mm.mutant_set_digest(rebuilt(rows))
    path = tmp_path / "reidentified.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="canonical"):
        mm.read_manifest(path)


def test_rows_out_of_canonical_order_are_refused(tmp_path: Path) -> None:
    """Manifest ORDER is part of the record: the digest hashes the list as it
    stands, so a reordered document is a different byte string with the same
    mutants. Both guards must fire rather than one masking the other.
    """
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = list(reversed(mutant_rows(document)))
    document["mutants"] = rows
    document["manifest_sha256"] = mm.mutant_set_digest(rebuilt(rows))
    path = tmp_path / "reordered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="canonical"):
        mm.read_manifest(path)


def test_a_manifest_whose_count_disagrees_with_its_list_is_refused(tmp_path: Path) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())
    document["expected_mutants"] = FOUR + 1
    path = tmp_path / "miscounted.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="expected_mutants"):
        mm.read_manifest(path)


@pytest.mark.parametrize("missing", SCHEMA_KEYS)
def test_a_manifest_missing_any_schema_key_is_refused(tmp_path: Path, missing: str) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())
    del document[missing]
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match=missing):
        mm.read_manifest(path)


@pytest.mark.parametrize("missing", sorted(ROW_KEYS))
def test_a_mutant_row_missing_any_field_is_refused(tmp_path: Path, missing: str) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = mutant_rows(document)
    del rows[0][missing]
    document["mutants"] = rows
    path = tmp_path / "short-row.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match=missing):
        mm.read_manifest(path)


def test_a_mutant_row_carrying_an_unknown_field_is_refused(tmp_path: Path) -> None:
    """Fail-closed on a schema this reader does not know. A row with an extra
    field was written by a different version of this document; consuming it as
    though the unknown field said nothing is how a v2 manifest is silently read
    as a v1 one, and the shard assignment would then be over the wrong set.
    """
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = mutant_rows(document)
    rows[0]["weight"] = "17"
    document["mutants"] = rows
    path = tmp_path / "extended.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match="weight"):
        mm.read_manifest(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("line_span", [1, 2, 3], id="three-element-span"),
        pytest.param("line_span", "3-4", id="span-as-string"),
        pytest.param("line_span", [True, 4], id="span-of-booleans"),
        pytest.param("test_target", "tests/t.py::t", id="target-not-a-list"),
        pytest.param("test_target", [7], id="target-not-strings"),
        pytest.param("operator", 7, id="operator-not-a-string"),
    ],
)
def test_a_malformed_row_field_is_refused(tmp_path: Path, field: str, value: object) -> None:
    """External input is untrusted (Law 23): this file is written by one CI job
    and read by seventeen others.
    """
    document = parsed(probe_manifest(tmp_path).to_json())
    rows = mutant_rows(document)
    rows[0][field] = value
    document["mutants"] = rows
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match=field):
        mm.read_manifest(path)


def test_a_mutant_row_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    document = parsed(probe_manifest(tmp_path).to_json())
    document["mutants"] = ["probe.alpha.x_add__mutmut_1"]
    path = tmp_path / "flat.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError):
        mm.read_manifest(path)


# ═══════════════════════════════════════════════════════════════════════════
# PROVENANCE. Collected from the real environment, never invented.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_dependency_lock_hash_changes_when_a_pin_changes(tmp_path: Path) -> None:
    (tmp_path / "requirements-ci.txt").write_text("mutmut==3.7.0\n", encoding="utf-8")

    before = mm.dependency_lock_hash(tmp_path)
    (tmp_path / "requirements-ci.txt").write_text("mutmut==3.8.0\n", encoding="utf-8")

    assert before != mm.dependency_lock_hash(tmp_path)


def test_the_dependency_lock_hash_changes_when_a_requirements_file_appears(tmp_path: Path) -> None:
    (tmp_path / "requirements-ci.txt").write_text("mutmut==3.7.0\n", encoding="utf-8")

    before = mm.dependency_lock_hash(tmp_path)
    (tmp_path / "requirements-engine1.txt").write_text("", encoding="utf-8")

    assert before != mm.dependency_lock_hash(tmp_path)


def test_the_dependency_lock_hash_changes_when_a_pinned_file_is_renamed(tmp_path: Path) -> None:
    """FOUND BY ATTACKING THE TEST ABOVE, WHICH PASSED FOR THE WRONG REASON.

    Deleting `digest.update(path.name...)` left the whole file green: the test
    above adds an EMPTY file, and the field separators around its empty contents
    already move the digest, so the file NAME was covered by nothing.

    Here the bytes are held identical and only the name changes — the one case
    that isolates it.
    """
    (tmp_path / "requirements-ci.txt").write_text("mutmut==3.7.0\n", encoding="utf-8")

    before = mm.dependency_lock_hash(tmp_path)
    (tmp_path / "requirements-ci.txt").rename(tmp_path / "requirements-engine1.txt")

    assert before != mm.dependency_lock_hash(tmp_path)
    assert (tmp_path / "requirements-engine1.txt").read_text(encoding="utf-8") == "mutmut==3.7.0\n"


def test_no_requirements_file_is_refused_rather_than_hashed_as_empty(tmp_path: Path) -> None:
    """An empty hash would be a stable, meaningless value that compares equal
    across every environment — the strongest possible false green.
    """
    with pytest.raises(mm.ManifestError, match="requirements"):
        mm.dependency_lock_hash(tmp_path)


def test_the_lock_hash_of_this_repository_is_taken_over_its_real_manifests() -> None:
    """REAL dependency, not a fixture: the pins this repository actually ships."""
    root = authored_repo_root()

    digest = mm.dependency_lock_hash(root)

    assert len(digest) == len(hashlib.sha256(b"").hexdigest())
    assert sorted(path.name for path in root.glob(mm.DEPENDENCY_LOCK_GLOB)) != []


def test_the_commit_is_read_from_a_real_git_repository(tmp_path: Path) -> None:
    """REAL git, not a fake runner. The commit is the one field Law 56 makes
    load-bearing, and a stubbed `git` would prove the stub.
    """
    subprocess.run(  # noqa: S603 - argv list, no shell
        ["git", "init", "-q", str(tmp_path)],  # noqa: S607 - git on PATH
        check=True,
    )
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    for argv in (
        ["config", "user.email", "probe@example.invalid"],
        ["config", "user.name", "probe"],
        ["add", "a.txt"],
        ["commit", "-qm", "probe"],
    ):
        subprocess.run(  # noqa: S603 - argv list, no shell
            ["git", "-C", str(tmp_path), *argv],  # noqa: S607 - git on PATH
            check=True,
        )
    expected = subprocess.run(  # noqa: S603 - argv list, no shell
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],  # noqa: S607 - git on PATH
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert mm.head_commit(tmp_path) == expected


def test_a_repository_with_no_commit_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    """A manifest with a blank or invented commit violates Law 56 at the moment
    it is written, and every number derived from it afterwards is an opinion.
    """
    subprocess.run(  # noqa: S603 - argv list, no shell
        ["git", "init", "-q", str(tmp_path)],  # noqa: S607 - git on PATH
        check=True,
    )

    with pytest.raises(mm.ManifestError, match="commit"):
        mm.head_commit(tmp_path)


def test_a_path_that_is_not_a_repository_is_refused(tmp_path: Path) -> None:
    with pytest.raises(mm.ManifestError, match="commit"):
        mm.head_commit(tmp_path / "does-not-exist")


def test_the_environment_records_the_interpreter_and_mutmut_actually_in_use() -> None:
    """Provenance that disagrees with the process it was collected in explains
    nothing. 4429 against 4709 is an environment difference or it is nothing.
    """
    collected = mm.describe_environment(authored_repo_root())

    assert collected.python_version == platform.python_version()
    assert collected.platform == platform.platform()
    assert collected.mutmut_version == metadata.version("mutmut")
    assert len(collected.commit) == len(collected.commit.strip()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# §2 and §3 THE PARTITION. Complete, disjoint, deterministic, at 16.
# ═══════════════════════════════════════════════════════════════════════════


def test_every_manifest_id_is_assigned_exactly_once_across_sixteen_shards(tmp_path: Path) -> None:
    """§3 ACCEPTANCE. The owner's shard count, stated as an identity: the union
    of the sixteen shards IS the manifest, and no id appears twice.
    """
    manifest = probe_manifest(tmp_path)

    sharding = mm.shard_manifest(manifest, SIXTEEN)

    assert len(sharding.shards) == SIXTEEN
    placed = [item for shard in sharding.shards for item in shard.entries]
    assert sorted(placed, key=lambda item: item.id) == list(manifest.entries)
    assert len({item.id for item in placed}) == manifest.expected_mutants


@pytest.mark.parametrize("shard_count", [1, 2, 3, 4, 5, 9, SIXTEEN, 64])
def test_every_mutant_lands_in_exactly_one_shard(tmp_path: Path, shard_count: int) -> None:
    """Union equals the manifest; every pairwise intersection is empty. Both
    halves, because either alone is satisfiable by a broken sharder.
    """
    manifest = probe_manifest(tmp_path)

    sharding = mm.shard_manifest(manifest, shard_count)

    assert len(sharding.shards) == shard_count
    union: list[mm.ManifestEntry] = []
    for shard in sharding.shards:
        union.extend(shard.entries)
    assert sorted(union, key=lambda item: item.id) == list(manifest.entries)
    assert len(union) == len(set(union)), "a mutant was placed in two shards"
    for first in range(len(sharding.shards)):
        for second in range(first + 1, len(sharding.shards)):
            left = set(sharding.shards[first].entries)
            right = set(sharding.shards[second].entries)
            assert left & right == set(), f"shards {first + 1} and {second + 1} overlap"


def test_shard_sizes_are_computed_from_the_manifest_and_never_assumed(tmp_path: Path) -> None:
    """`Shard size is CALCULATED FROM THE MANIFEST, never assumed to be 277.`
    Two universes of different sizes, the same shard count: the sizes must move
    with the manifest and sum to it both times.
    """
    small = probe_manifest(tmp_path / "small")
    bigger: tuple[File, ...] = (
        ("src/probe/alpha.py", "probe.alpha", (("x_add", tuple(str(n) for n in range(30))),)),
    )
    large = mm.generate_manifest(write_copy(tmp_path / "large", bigger), PROBE_ENVIRONMENT)

    small_shards = mm.shard_manifest(small, FOUR)
    large_shards = mm.shard_manifest(large, FOUR)

    assert sum(len(s.entries) for s in small_shards.shards) == small.expected_mutants == FOUR
    assert sum(len(s.entries) for s in large_shards.shards) == large.expected_mutants == TWENTY_NINE
    assert sorted(len(s.entries) for s in large_shards.shards) == [7, 7, 7, 8]


def test_more_shards_than_mutants_still_partitions(tmp_path: Path) -> None:
    """An empty shard is a wasted worker, not a lost mutant."""
    manifest = probe_manifest(tmp_path)

    sharding = mm.shard_manifest(manifest, SIXTEEN)

    assert sum(len(shard.entries) for shard in sharding.shards) == manifest.expected_mutants
    assert any(shard.entries == () for shard in sharding.shards)


def test_one_shard_holds_the_whole_manifest(tmp_path: Path) -> None:
    manifest = probe_manifest(tmp_path)

    assert mm.shard_manifest(manifest, 1).shards[0].entries == manifest.entries


def test_fewer_than_one_shard_is_refused(tmp_path: Path) -> None:
    manifest = probe_manifest(tmp_path)

    for shard_count in (0, -1):
        with pytest.raises(mm.ManifestError, match="at least one shard"):
            mm.shard_manifest(manifest, shard_count)


def test_the_same_manifest_and_count_assign_identically_every_time(tmp_path: Path) -> None:
    """Determinism is the property CI depends on: shard 3 of 16 must hold the
    same mutants on the machine that froze the manifest and the sixteen that
    consume it.
    """
    manifest = probe_manifest(tmp_path)

    runs = [mm.shard_manifest(manifest, SIXTEEN).shards for _ in range(10)]

    assert all(run == runs[0] for run in runs)


def test_a_manifest_reloaded_from_disk_shards_identically(tmp_path: Path) -> None:
    """The real CI shape: one job writes the manifest, sixteen read it."""
    manifest = probe_manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.to_json(), encoding="utf-8")

    assert mm.shard_manifest(mm.read_manifest(path), SIXTEEN) == mm.shard_manifest(
        manifest, SIXTEEN
    )


def test_shard_indexes_are_one_based_and_out_of_range_is_refused(tmp_path: Path) -> None:
    sharding = mm.shard_manifest(probe_manifest(tmp_path), THREE)

    assert [shard.index for shard in sharding.shards] == [1, 2, 3]
    assert all(shard.of == THREE for shard in sharding.shards)
    assert sharding.shard(1) is sharding.shards[0]
    for out_of_range in (0, 4):
        with pytest.raises(mm.ManifestError, match="1 and 3"):
            sharding.shard(out_of_range)


def test_the_reconciliation_closes_and_says_so(tmp_path: Path) -> None:
    """§3 ACCEPTANCE: `the report reconciles all counts mathematically`. The
    report states the numbers that must be equal AND whether they are, because a
    report that says `complete` without showing the sum is asking to be believed.
    """
    sharding = mm.shard_manifest(probe_manifest(tmp_path), SIXTEEN)

    lines = sharding.reconciliation()

    assert any("all four equal" in line and "YES" in line for line in lines)
    assert all(str(FOUR) in line for line in lines if "mutants in the manifest" in line)
    assert any("sum of shard sizes" in line for line in lines)
    assert "RECONCILIATION" in "\n".join(sharding.describe())


def test_a_broken_partition_is_reported_as_broken_not_as_complete(tmp_path: Path) -> None:
    """The reconciliation is only worth printing if it can say NO. Built by hand
    from a Sharding that has lost a mutant, because the real sharder cannot
    produce one — and a check that can never fail is not a check (§J.3).
    """
    sharding = mm.shard_manifest(probe_manifest(tmp_path), TWO)
    lost = mm.Sharding(
        manifest_sha256=sharding.manifest_sha256,
        shards=(sharding.shards[0],),
        measured=sharding.measured,
        unmeasured=sharding.unmeasured,
        history_names_unused=0,
    )

    assert any("THE PARTITION IS BROKEN" in line for line in lost.reconciliation())


# ═══════════════════════════════════════════════════════════════════════════
# §2 COST BALANCES. COST NEVER DECIDES INCLUSION.
# ═══════════════════════════════════════════════════════════════════════════

#: `x_a` is `M-000001`, `x_b` `M-000002`, `x_c` `M-000003`, `x_d` `M-000004`.
LOPSIDED: tuple[File, ...] = (
    ("src/probe/alpha.py", "probe.alpha", (("x_a", ("1", "2")), ("x_b", ("3", "4")))),
    ("src/probe/zebra.py", "probe.zebra", (("x_c", ("5", "6")), ("x_d", ("7", "8")))),
)
FIRST_BY_ID = "probe.alpha.x_a__mutmut_1"
LAST_BY_ID = "probe.zebra.x_d__mutmut_1"
TEN_SECONDS = 10.0
ONE_SECOND = 1.0
ALL_NAMES = (FIRST_BY_ID, "probe.alpha.x_b__mutmut_1", "probe.zebra.x_c__mutmut_1", LAST_BY_ID)
HEAD_HEAVY = dict.fromkeys(ALL_NAMES, ONE_SECOND) | {FIRST_BY_ID: TEN_SECONDS}
TAIL_HEAVY = dict.fromkeys(ALL_NAMES, ONE_SECOND) | {LAST_BY_ID: TEN_SECONDS}


def lopsided(root: Path, durations: Mapping[str, float] | None = None) -> mm.Manifest:
    return mm.generate_manifest(write_copy(root, LOPSIDED, durations), PROBE_ENVIRONMENT)


def test_cost_may_balance_a_shard_and_may_never_decide_whether_a_mutant_is_in_one(
    tmp_path: Path,
) -> None:
    """§2 OF THE SPEC, AND THE REASON ~1536 MUTANTS WERE LOST.

    A history that names ONE mutant and prices it a thousand times the rest: the
    three with no measurement must still be assigned, and the expensive one must
    not crowd them out. Inclusion is a partition of the manifest by `has a
    recorded duration`, and both halves are filled — so no cost, however extreme,
    can remove a mutant from the run.
    """
    manifest = lopsided(tmp_path)

    sharding = mm.shard_manifest(manifest, TWO, {FIRST_BY_ID: 1000.0})

    placed = sorted(item.id for shard in sharding.shards for item in shard.entries)
    assert placed == sorted(item.id for item in manifest.entries)
    assert sharding.measured == 1
    assert sharding.unmeasured == THREE
    assert any("all four equal" in line and "YES" in line for line in sharding.reconciliation())


def test_a_mutant_nobody_ever_timed_is_assigned_exactly_as_surely_as_a_timed_one(
    tmp_path: Path,
) -> None:
    """The complement of the test above: a history covering NOBODY still yields a
    complete partition. `unmeasured` is not a bucket that gets dropped.
    """
    manifest = lopsided(tmp_path)

    sharding = mm.shard_manifest(manifest, THREE, {})

    assert sharding.measured == 0
    assert sharding.unmeasured == manifest.expected_mutants
    placed = [item for shard in sharding.shards for item in shard.entries]
    assert sorted(placed, key=lambda item: item.id) == list(manifest.entries)


def test_measured_cost_beats_count_and_the_split_proves_which_one_ran(tmp_path: Path) -> None:
    """THE CLAIM, stated as a number: with `10 + 1 + 1 + 1` seconds over two
    shards, cost balancing gives `10s` and `3s`; count balancing gives `11s` and
    `2s`. The 1/3 SPLIT is the fingerprint — no count-balanced sharder produces
    it — so this fails if the history is accepted and then ignored.
    """
    sharding = mm.shard_manifest(lopsided(tmp_path), TWO, HEAD_HEAVY)

    assert sorted(len(shard.entries) for shard in sharding.shards) == [1, THREE]
    alone = next(shard for shard in sharding.shards if len(shard.entries) == 1)
    assert alone.entries[0].name == FIRST_BY_ID
    assert sorted(shard.measured_seconds for shard in sharding.shards) == [3.0, TEN_SECONDS]


def test_the_heaviest_mutant_is_placed_first_even_when_it_is_last_by_id(tmp_path: Path) -> None:
    """FOUND BY ATTACKING THE TEST ABOVE, WHICH PASSED FOR THE WRONG REASON.

    Replacing `heaviest first` with `ID order` once left the whole file green,
    because in `HEAD_HEAVY` the expensive mutant is ALSO `M-000001`: the two
    orders coincide, so the fixture agreed with both algorithms.

    Here the `10s` mutant is `M-000004`, the LAST by ID, and they diverge:

        heaviest first  ->  {M-000004} = 10s   and   {M-000001..3} = 3s
        ID order        ->  {M-000001, M-000003} = 2s  and  {M-000002, M-000004} = 11s
    """
    sharding = mm.shard_manifest(lopsided(tmp_path), TWO, TAIL_HEAVY)

    alone = next(shard for shard in sharding.shards if len(shard.entries) == 1)
    assert alone.entries[0].name == LAST_BY_ID
    assert alone.entries[0].id == "M-000004", "precondition: the heavy mutant sorts LAST by ID"
    assert sorted(len(shard.entries) for shard in sharding.shards) == [1, THREE]
    assert max(shard.measured_seconds for shard in sharding.shards) == TEN_SECONDS


def test_without_history_the_output_says_the_balance_is_uninformed(tmp_path: Path) -> None:
    """`say so in the output rather than pretending the balance is informed`."""
    sharding = mm.shard_manifest(lopsided(tmp_path), TWO)

    assert sharding.measured == 0
    assert sharding.unmeasured == FOUR
    assert "UNMEASURED" in sharding.basis
    assert "COUNT" in sharding.basis
    assert all(shard.measured_seconds == 0.0 for shard in sharding.shards)
    assert any("UNMEASURED" in line for line in sharding.describe())


def test_a_full_history_says_the_balance_is_measured(tmp_path: Path) -> None:
    sharding = mm.shard_manifest(lopsided(tmp_path), TWO, HEAD_HEAVY)

    assert sharding.measured == FOUR
    assert sharding.unmeasured == 0
    assert "MEASURED" in sharding.basis
    assert "UNMEASURED" not in sharding.basis


def test_a_partial_history_balances_what_was_measured_and_names_what_was_not(
    tmp_path: Path,
) -> None:
    """The real CI state: 2893 of 4429 mutants ran, so a rerun has history for
    some. Seconds are never invented for the rest — they are spread by count on
    their own accumulator, because adding a count to a duration is an arithmetic
    error wearing a number.
    """
    manifest = lopsided(tmp_path)

    sharding = mm.shard_manifest(manifest, TWO, {FIRST_BY_ID: TEN_SECONDS})

    assert sharding.measured == 1
    assert sharding.unmeasured == THREE
    assert "MEASURED RUNTIME for 1 of 4" in sharding.basis
    assert "COUNT" in sharding.basis
    assert sum(shard.measured_seconds for shard in sharding.shards) == TEN_SECONDS
    assert sum(shard.unmeasured for shard in sharding.shards) == THREE


def test_a_history_from_a_different_universe_is_reported_not_swallowed(tmp_path: Path) -> None:
    """A stale history is the common case — the universe moves every commit.
    Ignoring its dead keys is right; ignoring them SILENTLY hides a history that
    is 100% stale and a balance that is really count-based.
    """
    sharding = mm.shard_manifest(lopsided(tmp_path), TWO, {"probe.gone.x_z__mutmut_1": TEN_SECONDS})

    assert sharding.history_names_unused == 1
    assert sharding.measured == 0
    assert any("not in this manifest" in line for line in sharding.describe())


def test_the_order_of_the_history_mapping_cannot_change_the_shards(tmp_path: Path) -> None:
    manifest = lopsided(tmp_path)
    backwards = dict(reversed(list(HEAD_HEAVY.items())))

    assert mm.shard_manifest(manifest, TWO, backwards) == mm.shard_manifest(
        manifest, TWO, HEAD_HEAVY
    )


def test_equal_costs_are_broken_by_id_and_not_by_chance(tmp_path: Path) -> None:
    """Every tie — equal cost, equal load — resolves to the lowest ID and the
    lowest shard index. Without both, a merely-stable sort would still let two
    machines disagree.
    """
    flat = dict.fromkeys(ALL_NAMES, ONE_SECOND)

    shards = mm.shard_manifest(lopsided(tmp_path), TWO, flat).shards

    assert [item.id for item in shards[0].entries] == ["M-000001", "M-000003"]
    assert [item.id for item in shards[1].entries] == ["M-000002", "M-000004"]


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="inf"),
        pytest.param(-1.0, id="negative"),
    ],
)
def test_a_runtime_that_is_not_a_duration_is_refused(tmp_path: Path, bad: float) -> None:
    """NaN is the dangerous one and the reason this check exists: every
    comparison against it is False, so `min` silently returns shard 1 forever and
    the sort order becomes an accident of input order. A partition that depends
    on input order is not deterministic, and nothing would have said so.
    """
    assert math.isnan(bad) or bad < 0 or math.isinf(bad), "precondition"

    with pytest.raises(mm.ManifestError, match=re.escape(FIRST_BY_ID)):
        mm.shard_manifest(lopsided(tmp_path), TWO, {FIRST_BY_ID: bad})


@pytest.mark.parametrize(
    "bad",
    [pytest.param(True, id="bool"), pytest.param("10", id="str"), pytest.param(None, id="none")],
)
def test_a_runtime_that_is_not_a_number_is_refused(tmp_path: Path, bad: object) -> None:
    """`True` is included deliberately: `bool` is a subclass of `int`, so a naive
    numeric check accepts it and one second becomes one boolean.
    """
    with pytest.raises(mm.ManifestError, match=re.escape(FIRST_BY_ID)):
        mm.shard_manifest(lopsided(tmp_path), TWO, {FIRST_BY_ID: bad})


def test_the_runtime_history_is_read_from_the_durations_mutmut_already_records(
    tmp_path: Path,
) -> None:
    """FIND THE DATA, DO NOT MANUFACTURE IT. mutmut times every mutant it runs
    and writes it to `durations_by_key` (`mutmut/mutation/data.py:130-138`), so
    the measured cost this sharder wants already exists on disk.
    """
    mutants_dir = write_copy(tmp_path, LOPSIDED, HEAD_HEAVY)

    assert mm.read_runtime_history(mutants_dir) == HEAD_HEAVY


def test_a_tree_that_has_never_run_yields_an_empty_history_not_an_error(tmp_path: Path) -> None:
    """Generation happens before execution, so the first manifest of a commit
    legitimately has no durations. That is the `count only` case.
    """
    history = mm.read_runtime_history(write_copy(tmp_path, LOPSIDED))

    assert history == {}
    assert "UNMEASURED" in mm.shard_manifest(lopsided(tmp_path), TWO, history).basis


def test_a_duration_mutmut_recorded_as_nonsense_is_still_refused(tmp_path: Path) -> None:
    """The reader validates what it reads. A meta file is JSON on disk that any
    process could have written, so it is untrusted input like any other.
    """
    mutants_dir = write_copy(tmp_path, LOPSIDED)
    meta = mutants_dir / "src/probe/alpha.py.meta"
    document = parsed(meta.read_text(encoding="utf-8"))
    document["durations_by_key"] = {FIRST_BY_ID: "quick"}
    meta.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(mm.ManifestError, match=re.escape(FIRST_BY_ID)):
        mm.read_runtime_history(mutants_dir)


# ═══════════════════════════════════════════════════════════════════════════
# §4 THE CONSUMED CONTRACT — the header the aggregator reads
# ═══════════════════════════════════════════════════════════════════════════


def test_the_shard_header_carries_exactly_the_five_keys_the_aggregator_consumes(
    tmp_path: Path,
) -> None:
    """§4. Emitted from THIS side because all five values are properties of the
    manifest and the shard; letting the executor retype them is how the two
    halves come to agree by accident.
    """
    manifest = probe_manifest(tmp_path)
    sharding = mm.shard_manifest(manifest, SIXTEEN)

    header = mm.shard_header(sharding.shard(3), manifest.manifest_sha256, manifest.environment)

    assert tuple(header) == (
        "shard_index",
        "shard_count",
        "manifest_sha256",
        "commit",
        "dependency_lock_hash",
    )
    assert header["shard_index"] == THREE
    assert header["shard_count"] == SIXTEEN
    assert header["manifest_sha256"] == manifest.manifest_sha256
    assert header["commit"] == PROBE_ENVIRONMENT.commit
    assert header["dependency_lock_hash"] == PROBE_ENVIRONMENT.dependency_lock_hash


def test_headers_from_two_different_universes_cannot_be_aggregated_together(
    tmp_path: Path,
) -> None:
    """§3 ACCEPTANCE: `two runs with different manifest hashes cannot be
    aggregated together`. The aggregator enforces the rejection; this side's job
    is to make the difference VISIBLE in the header, so the rejection has
    something to fire on.
    """
    one = probe_manifest(tmp_path / "one")
    other_files: tuple[File, ...] = (
        ("src/probe/alpha.py", "probe.alpha", (("x_add", ("a + b", "a * b")),)),
    )
    other = mm.generate_manifest(write_copy(tmp_path / "two", other_files), PROBE_ENVIRONMENT)

    first = mm.shard_header(
        mm.shard_manifest(one, SIXTEEN).shard(1), one.manifest_sha256, one.environment
    )
    second = mm.shard_header(
        mm.shard_manifest(other, SIXTEEN).shard(1), other.manifest_sha256, other.environment
    )

    assert first["manifest_sha256"] != second["manifest_sha256"]
    assert first["shard_index"] == second["shard_index"], "same shard, different universe"


# ═══════════════════════════════════════════════════════════════════════════
# THE COMMAND LINE. The seam CI uses; refuses everything it does not recognise.
# ═══════════════════════════════════════════════════════════════════════════


def test_generate_writes_a_manifest_that_reads_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mutants_dir = write_copy(tmp_path)
    out = tmp_path / "manifest.json"

    code = mm.cli(
        ["mutation_manifest.py", "generate", "--mutants-dir", str(mutants_dir), "--out", str(out)]
    )

    capsys.readouterr()
    assert code == 0
    assert mm.read_manifest(out).expected_mutants == FOUR


def test_generate_without_an_out_path_prints_the_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mutants_dir = write_copy(tmp_path)

    assert mm.cli(["mutation_manifest.py", "generate", "--mutants-dir", str(mutants_dir)]) == 0

    assert parsed(capsys.readouterr().out)["expected_mutants"] == FOUR


def test_shard_prints_the_names_in_one_shard_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = probe_manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.to_json(), encoding="utf-8")

    code = mm.cli(
        ["mutation_manifest.py", "shard", "--manifest", str(path), "--shards", "2", "--index", "1"]
    )

    printed = capsys.readouterr().out.split()
    assert code == 0
    assert printed == [item.name for item in mm.shard_manifest(manifest, TWO).shard(1).entries]


def test_shard_prints_the_aggregator_header_on_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = probe_manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.to_json(), encoding="utf-8")

    code = mm.cli(
        [
            "mutation_manifest.py",
            "shard",
            "--manifest",
            str(path),
            "--shards",
            str(SIXTEEN),
            "--index",
            str(FIVE),
            "--header",
        ]
    )

    printed = capsys.readouterr().out.strip()
    assert code == 0
    header = parsed(printed)
    assert header["shard_index"] == FIVE
    assert header["shard_count"] == SIXTEEN
    assert header["manifest_sha256"] == manifest.manifest_sha256
    assert "\n" not in printed, "the header is ONE JSONL line"


def test_shard_without_an_index_prints_the_basis_and_the_reconciliation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(probe_manifest(tmp_path).to_json(), encoding="utf-8")

    assert mm.cli(["mutation_manifest.py", "shard", "--manifest", str(path), "--shards", "2"]) == 0

    printed = capsys.readouterr().out
    assert "UNMEASURED" in printed
    assert "RECONCILIATION" in printed


def test_the_command_line_uses_the_durations_on_disk_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One tree, written once WITH durations. Rebuilding it without them between
    the manifest and the shard would silently test the empty-history path.
    """
    mutants_dir = write_copy(tmp_path, LOPSIDED, HEAD_HEAVY)
    path = tmp_path / "manifest.json"
    path.write_text(
        mm.generate_manifest(mutants_dir, PROBE_ENVIRONMENT).to_json(), encoding="utf-8"
    )

    code = mm.cli(
        [
            "mutation_manifest.py",
            "shard",
            "--manifest",
            str(path),
            "--shards",
            "2",
            "--durations-from",
            str(mutants_dir),
        ]
    )

    assert code == 0
    assert "MEASURED RUNTIME for all 4" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["mutation_manifest.py"], id="no-command"),
        pytest.param(["mutation_manifest.py", "explode"], id="unknown-command"),
        pytest.param(["mutation_manifest.py", "generate", "--wat"], id="unknown-option"),
        pytest.param(["mutation_manifest.py", "generate", "--out"], id="missing-value"),
        pytest.param(["mutation_manifest.py", "shard", "--shards", "2"], id="shard-no-manifest"),
        pytest.param(["mutation_manifest.py", "shard", "--manifest", "m"], id="shard-no-count"),
        pytest.param(["mutation_manifest.py", "shard", "--shards", "two"], id="not-a-number"),
        pytest.param(["mutation_manifest.py", "generate", "--shards", "2"], id="wrong-command"),
        pytest.param(
            ["mutation_manifest.py", "shard", "--manifest", "m", "--shards", "2", "--header"],
            id="header-without-index",
        ),
    ],
)
def test_an_argument_the_parser_does_not_recognise_is_refused(argv: list[str]) -> None:
    """Hand-rolled rather than `argparse` on purpose: argparse accepts unique
    prefixes, so `--shard 2` would silently mean `--shards 2` and a typo would
    become a different partition.
    """
    with pytest.raises(SystemExit):
        mm.parse_argv(argv)


# ═══════════════════════════════════════════════════════════════════════════
# FALSIFICATION. A real mutmut run is the oracle for every claim above.
# ═══════════════════════════════════════════════════════════════════════════

_PROJECT = "[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['src']\n"
_MUTMUT_CONFIG = "[tool.mutmut]\nsource_paths = ['src']\nalso_copy = ['pyproject.toml']\n"
_CALC = (
    "def add(a, b):\n    return a + b\n\n\n"
    "def clamp(x):\n    if x > 0:\n        return x\n    return 0\n"
)
_CALC_TESTS = (
    "from probe.calc import add, clamp\n\n\n"
    "def test_add():\n    assert add(1, 2) == 3\n\n\n"
    "def test_clamp():\n    assert clamp(5) == 5\n    assert clamp(-1) == 0\n"
)


@pytest.fixture(scope="session")
def real_mutmut_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A genuine `mutmut run`, returning its `mutants/` directory.

    `MUTANT_UNDER_TEST` is stripped because this file itself runs under mutation;
    inheriting `stats` or a live mutant name would make the nested run measure
    the outer one. `no_proxy` is set because `getproxies_macosx_sysconf()` is not
    fork-safe and mutmut forks.
    """
    project = tmp_path_factory.mktemp("manifest_oracle")
    (project / "pyproject.toml").write_text(_PROJECT + "\n" + _MUTMUT_CONFIG, encoding="utf-8")
    (project / "src" / "probe").mkdir(parents=True)
    (project / "src" / "probe" / "__init__.py").write_text("", encoding="utf-8")
    (project / "src" / "probe" / "calc.py").write_text(_CALC, encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_calc.py").write_text(_CALC_TESTS, encoding="utf-8")
    environment = {k: v for k, v in os.environ.items() if k != md.MUTANT_ENV_VAR}
    environment.update(md.NO_PROXY_ENVIRONMENT)

    completed = subprocess.run(  # noqa: S603 - argv list, no shell, interpreter is sys.executable
        [sys.executable, "-m", "mutmut", "run"],
        check=False,
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )
    # NEVER a skip. A manifest whose oracle did not run is a manifest nothing
    # checked, and reporting that as passed is this repository's own F-029.
    assert completed.returncode == 0, (
        "the oracle `mutmut run` failed, so nothing below proves anything:\n"
        f"{completed.stdout[-4000:]}\n{completed.stderr[-4000:]}"
    )
    return project / MUTATION_COPY_DIRECTORY


def test_the_manifest_names_exactly_what_mutmut_generated(real_mutmut_run: Path) -> None:
    """THE FALSIFICATION. Two independent records of the same universe: mutmut's
    meta store, and the registrations mutmut wrote into the generated file. The
    manifest must agree with both. A manifest built from a subset would pass the
    first and fail the second.
    """
    manifest = mm.generate_manifest(real_mutmut_run, PROBE_ENVIRONMENT)

    named = {item.name for item in manifest.entries}
    assert named == {mutant.name for mutant in md.read_mutants(real_mutmut_run)}
    registered = md.registered_mutants(real_mutmut_run / "src" / "probe" / "calc.py")
    assert {md.generated_function(name) for name in named} <= registered
    assert manifest.expected_mutants == FOUR, f"expected four mutants here, got {sorted(named)}"


def test_the_recorded_context_is_read_out_of_mutmuts_own_output(real_mutmut_run: Path) -> None:
    """THE SHARPEST CHECK IN THIS FILE. Every one of the four fields is compared
    against mutmut's own artifacts rather than against a fixture this file wrote:

      line_span   -> mutmut's `.spans` index
      original    -> the `__mutmut_orig` function mutmut copied
      operator    -> a diff of two texts mutmut generated, containing the real edit
      test_target -> the covering tests mutmut recorded in its stats file
    """
    manifest = mm.generate_manifest(real_mutmut_run, PROBE_ENVIRONMENT)
    spans = json.loads(
        (real_mutmut_run / ("src/probe/calc.py" + mm.SPANS_SUFFIX)).read_text(encoding="utf-8")
    )["spans"]
    covering = md.read_covering_tests(real_mutmut_run)

    for item in manifest.entries:
        function = md.generated_function(item.name)
        assert list(item.line_span) == spans[function], f"{function} is not where mutmut put it"
        assert item.original.lstrip().startswith("def "), item.original
        assert "__mutmut_orig" in item.original or mm.FUNCTION_PLACEHOLDER not in item.original
        assert item.operator.startswith(("-", "+")), item.operator
        assert item.test_target == covering[md.mangled_name(item.name)]

    add = next(item for item in manifest.entries if "x_add" in item.name)
    assert "return a + b" in add.original, "the ORIGINAL, not the mutant"
    assert "-    return a + b" in add.operator
    assert "+    return a" in add.operator and "+    return a + b" not in add.operator


def test_the_hand_written_copy_matches_the_shape_mutmut_writes(
    real_mutmut_run: Path, tmp_path: Path
) -> None:
    """Keeps the cheap fixtures honest. If mutmut changed its on-disk layout,
    every fast test above would keep passing against a format that no longer
    exists.
    """
    written = write_copy(tmp_path, LOPSIDED)

    for suffix in (".meta", mm.SPANS_SUFFIX):
        real_path = real_mutmut_run / ("src/probe/calc.py" + suffix)
        real = parsed(real_path.read_text(encoding="utf-8"))
        mine = parsed((written / ("src/probe/alpha.py" + suffix)).read_text(encoding="utf-8"))
        assert set(mine) == set(real), f"{suffix} layout drifted"
    real_stats = parsed((real_mutmut_run / md.STATS_FILENAME).read_text(encoding="utf-8"))
    mine_stats = parsed((written / md.STATS_FILENAME).read_text(encoding="utf-8"))
    assert set(mine_stats) <= set(real_stats)


def test_the_real_tree_shards_into_a_complete_disjoint_partition(real_mutmut_run: Path) -> None:
    """The whole point, over mutants nobody in this file invented, at the shard
    count the owner specified.
    """
    manifest = mm.generate_manifest(real_mutmut_run, PROBE_ENVIRONMENT)

    sharding = mm.shard_manifest(manifest, SIXTEEN, mm.read_runtime_history(real_mutmut_run))

    placed = [item for shard in sharding.shards for item in shard.entries]
    assert sorted(placed, key=lambda item: item.id) == list(manifest.entries)
    assert len(placed) == len(set(placed))
    assert any("all four equal" in line and "YES" in line for line in sharding.reconciliation())
    assert sharding.measured == manifest.expected_mutants, (
        "precondition: a completed run times every mutant, so this history is full"
    )


def test_the_real_durations_are_positive_seconds(real_mutmut_run: Path) -> None:
    """The balance is only worth anything if the numbers it balances are real."""
    history = mm.read_runtime_history(real_mutmut_run)

    assert history != {}
    assert all(seconds > 0 for seconds in history.values())
    assert set(history) <= {mutant.name for mutant in md.read_mutants(real_mutmut_run)}
