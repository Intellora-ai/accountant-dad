#!/usr/bin/env python3
"""The mutant universe, frozen and hashed before anything runs — then partitioned.

THE TWO DEFECTS THIS EXISTS FOR, both MEASURED, neither one visible from inside
a run.

*A run that does not finish reports a smaller universe than it was given.* CI
processed 2893 of 4429 mutants in 269.9 minutes (10.7/min) and was terminated
with mutmut still alive. Nothing in that output distinguishes "1536 mutants have
no verdict" from "there were only 2893 mutants." `mutation_denominator` closes
that hole AFTER the fact by itemising every mutant without a verdict; this module
closes it BEFORE, by writing the universe down while it can still be observed, so
a later count has something to be wrong against.

*The universe is not reproducible across environments, and nothing said so.* The
same commit generated 4429 mutants on CI and 4612 on a laptop. No artifact
recorded either number, because no artifact recorded the universe at all.

THE TRANSFORM (Law 53). *"Make mutation testing finish inside a CI job"* is a
hard problem about wall clock, fork safety and third-party import cost. *"Given a
frozen, named set of mutants, which subset does worker k of N run?"* is
arithmetic. Freezing the set first is what turns one into the other.

COST MAY BALANCE A SHARD. COST MAY NEVER DECIDE WHETHER A MUTANT IS IN ONE.
Every mutant in the manifest is assigned to a shard before execution begins,
including the slow tail and including every mutant nobody has ever timed. The
previous run lost ~1536 mutants precisely because cost ordering decided what got
reached, so inclusion here is a partition of the manifest -- `measured` and
`unmeasured` together ARE `manifest.entries` -- and the runtime history only
chooses which shard, never whether.

═══════════════════════════════════════════════════════════════════════════════
THE CANONICALISATION OF `manifest_sha256` — STATED, because the aggregator
COMPARES this value and does not recompute it
═══════════════════════════════════════════════════════════════════════════════

Two halves that never state their canonicalisation can agree by accident and
disagree later for a reason nobody can name. Exactly this:

    rows    = [entry.row() for entry in manifest.entries]      # MANIFEST ORDER
    payload = json.dumps(rows, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True)
    manifest_sha256 = sha256(payload.encode("utf-8")).hexdigest()

and each row is exactly these seven keys, serialised with `sort_keys=True` so the
key order inside a row is alphabetical regardless of how it was built:

    id          str        `M-000001`, positional within THIS manifest
    line_span   [int,int]  1-based inclusive, in the MUTATION COPY
    name        str        mutmut's key, e.g. `pkg.mod.x_f__mutmut_3`
    operator    str        the OBSERVED edit (see below)
    original    str        the original function's source, verbatim
    source      str        authored path, e.g. `src/accountant_dad/confidence.py`
    test_target [str]      mutmut's covering tests, sorted

MANIFEST ORDER is `(source, name)` ascending, lexicographic. The rows are NOT
re-sorted inside the digest; `sort_keys` applies to the keys of each row, never
to the list.

WHAT IS AND IS NOT COVERED. The digest covers the mutant list and NOTHING else.
The five environment fields sit beside it, never inside it, for two reasons that
both matter: a document cannot contain its own digest, and the same universe
generated on two machines must hash the same or the hash answers *"is this the
same FILE?"* instead of *"is this the same UNIVERSE?"*.

The digest DOES cover `original`, `operator` and `test_target`, deliberately. Two
shard results are comparable only when the same mutants were run against the same
tests over the same code; folding all three in makes the hash mean exactly that,
so a test added between two runs stops them being aggregated — which is correct,
because they measured different work.

═══════════════════════════════════════════════════════════════════════════════

WHERE EVERY FACT COMES FROM. Nothing here re-derives mutmut's semantics from
memory, and nothing is copied out of another module:

    mutation_denominator.read_mutants        the mutant set (the meta store)
    mutation_denominator.read_covering_tests `test_target`
    mutants/<source>.py.spans                `line_span`, and the two texts below
    mutants/<source>.py                      `original`, and the mutant's own source
    git rev-parse HEAD                       `commit` (Law 56)
    importlib.metadata / platform            the environment that produced the set

WHY THE METa STORE IS THE WHOLE UNIVERSE AND NOT JUST THE PART THAT RAN. Read
from mutmut's source, not assumed: `mutmut/__main__.py:348-358` builds
`exit_code_by_key` over `mutated_file.mutant_names` -- every mutant it just
generated -- writing `None` for each one it has no result for, and saves that
BEFORE the first mutant is executed. An interrupted run therefore leaves a meta
store listing every generated mutant, most of them `None`. Measured on this
repository: generation alone produced 4709 mutants across 34 files in 15.2s, all
of them `not checked`.

`operator` IS THE OBSERVED EDIT, AND THAT IS NOT A SYNONYM. mutmut does NOT
persist which mutation operator fired. `mutation/mutators.py` defines fifteen
operators and `mutation/file_mutation.py:216-218` applies them at generation,
keeping only the generated names (`x_f__mutmut_1`, `..._2`); the operator's
identity is discarded and appears in no file mutmut writes. Inventing a label
would be a fabricated measurement (Law 24), so this field carries what CAN be
observed: the unified diff between the original function and the mutant, both
read out of the mutation copy mutmut generated. That is strictly more specific
than an operator name -- it says `-  return a + b / +  return a - b` rather than
`operator_swap_op` -- and every character of it was read from disk.

FIND THE DATA, DO NOT MANUFACTURE IT. The per-mutant runtime used to balance
shards already exists: `mutmut/mutation/data.py:130-138` records the wall-clock
seconds of every mutant it runs into `durations_by_key`, in the same `.meta`
files. No new instrumentation, no new format, and the numbers are mutmut's own.

AN ID IS AN INDEX INTO A UNIVERSE; A NAME IDENTIFIES A MUTANT. `M-000001` is
positional within one manifest's canonical order and is deliberately NOT stable
across universes -- inserting a mutant renumbers everything after it, which is
correct, because a different universe must not be able to masquerade as the same
one under the same labels. Anything that must survive a universe change -- the
runtime history above, most of all -- is keyed by mutmut's mutant NAME.

WHAT THIS MODULE WILL NOT DO. It prints no mutation score and no completeness
verdict: `.github/workflows/testing.yml` owns the score and `mutation_denominator`
owns completeness, and a second copy of either would be a second number to
disagree with (Laws 14, 19).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

# THREE PRIVATE HELPERS COME FROM `mutation_denominator`, DELIBERATELY.
# `_load_json_object`, `_meta_files` and `_source_of` are this repository's reader
# for mutmut's on-disk results, and this module reads the same files. Copying them
# would create a SECOND reader that can disagree with the first about a malformed
# meta file -- a second source of truth (Laws 14, 19) whose divergence would be
# silent. The coupling is real either way; importing makes it visible instead of
# hiding it in a duplicate.
from authored_source import MUTATION_COPY_DIRECTORY, authored_repo_root
from mutation_denominator import (
    MUTANT_INDEX_SEPARATOR,
    Mutant,
    _load_json_object,
    _meta_files,
    generated_function,
    mangled_name,
    read_covering_tests,
    read_mutants,
)

#: The prefix and width of a manifest ID. Fixed by the schema this module was
#: asked for (`M-000001`); nothing about it is a threshold. A universe larger
#: than `10**ID_DIGITS` simply widens the number rather than colliding.
ID_PREFIX = "M-"
ID_DIGITS = 6

#: The shard count the owner specified, 2026-08-06. Named here so it can be
#: CITED rather than retyped, and deliberately NOT a default: `shard_manifest`
#: takes the count as an argument and computes every shard's size from the
#: manifest, so no size is ever assumed.
OWNER_SHARD_COUNT = 16

#: Which files the dependency lock hash is taken over. A GLOB, not a hand-kept
#: list: a hand-kept list silently stops covering a manifest somebody adds, and
#: stops covering it exactly when it starts to matter. The file NAMES are hashed
#: alongside their bytes, so an added, removed or renamed manifest cannot leave
#: the hash unchanged.
DEPENDENCY_LOCK_GLOB = "requirements*.txt"

#: mutmut's key for its own per-mutant wall-clock timings, inside each `.meta`.
DURATIONS_KEY = "durations_by_key"

#: mutmut's line-span index, written beside each mutated file at generation
#: (`mutmut/mutation/data.py:57-65`). `format_version` is 1 in mutmut 3.7.0 and
#: is CHECKED rather than assumed: mutmut's own loader returns `None` for a
#: version it does not understand, and reading a v2 index as v1 would attribute
#: the wrong lines to every mutant.
SPANS_SUFFIX = ".spans"
SPANS_FORMAT_VERSION = 1

#: The suffix mutmut gives the untouched copy of a mutated function.
ORIGINAL_SUFFIX = f"{MUTANT_INDEX_SEPARATOR}orig"

#: Both function names are replaced with this before diffing, so the `def` line
#: — which always differs, because the names always differ — does not show up as
#: the mutation.
FUNCTION_PLACEHOLDER = "__FUNCTION__"

#: The manifest document, in order. `expected_mutants` and `manifest_sha256` are
#: DERIVED from `mutants` and are written down anyway: a reader that recomputes
#: them and compares is what makes the record fail-closed rather than decorative.
MANIFEST_KEYS = (
    "commit",
    "mutmut_version",
    "python_version",
    "platform",
    "dependency_lock_hash",
    "manifest_sha256",
    "expected_mutants",
    "mutants",
)

#: One mutant's row. Every field the owner specified: source location
#: (`source` + `line_span`), operator, original code context, test target.
MUTANT_KEYS = ("id", "name", "source", "line_span", "operator", "original", "test_target")

#: The header the aggregator consumes as the FIRST LINE of a shard result file.
#: These five keys, in this order, and nothing else.
SHARD_HEADER_KEYS = (
    "shard_index",
    "shard_count",
    "manifest_sha256",
    "commit",
    "dependency_lock_hash",
)

#: A partition into zero parts of a non-empty set does not exist. This is the
#: only bound on the shard count, and it is arithmetic rather than a choice --
#: no maximum is invented, and asking for more shards than mutants is allowed
#: (it wastes a worker; it never loses a mutant).
MINIMUM_SHARDS = 1

#: One claim on a mutant name is correct. Two is a corrupt meta store.
ONE_CLAIM = 1

#: A line span is a start and an end. Nothing else is a line span.
SPAN_LENGTH = 2

GENERATE = "generate"
SHARD = "shard"

_USAGE = (
    "usage: mutation_manifest.py generate [--mutants-dir DIR] [--out PATH]\n"
    "       mutation_manifest.py shard --manifest PATH --shards N\n"
    "                                  [--index I] [--header] [--durations-from DIR]\n"
    "  --mutants-dir DIR     the mutation copy to read (default: mutants)\n"
    "  --out PATH            write the manifest here instead of stdout\n"
    "  --manifest PATH       a manifest written by `generate`\n"
    "  --shards N            how many shards to cut it into\n"
    "  --index I             print only shard I's mutant names (1..N)\n"
    "  --header              print shard I's JSONL result header instead of names\n"
    "  --durations-from DIR  a mutation copy whose `.meta` files carry mutmut's\n"
    "                        own per-mutant timings, used to BALANCE by measured\n"
    "                        cost. It never decides which mutants are included."
)


class ManifestError(Exception):
    """Raised when the universe, the record of it, or a shard request is unsound.

    Never falls back to a partial or invented answer. A manifest that silently
    drops a malformed row, or a shard set that silently drops a mutant, is the
    exact silent exclusion this module exists to end (Law 11).
    """


# ═══════════════════════════════════════════════════════════════════════════
# The record
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ManifestEntry:
    """One mutant, with everything needed to run it and to explain it."""

    #: Positional within THIS manifest's canonical order. Not stable across
    #: universes; `name` is what survives one.
    id: str
    #: mutmut's key, e.g. `accountant_dad.confidence.x_score__mutmut_3`.
    name: str
    #: The authored source file it mutates.
    source: str
    #: The mutant function's lines in the MUTATION COPY, 1-based and inclusive.
    #: `source` plus this is the source location.
    line_span: tuple[int, int]
    #: The OBSERVED edit — a unified diff of the original against the mutant.
    #: mutmut records no operator identity; see the module docstring.
    operator: str
    #: The original function, verbatim, as mutmut copied it into `__mutmut_orig`.
    original: str
    #: The tests mutmut saw execute this mutant's function. Empty is a real
    #: answer (mutmut scores such a mutant `no tests`), a MISSING stats file is
    #: not, and `generate_manifest` refuses that rather than writing empties.
    test_target: tuple[str, ...]

    def row(self) -> Mapping[str, object]:
        """This entry as it appears in the document AND in the digest.

        ONE function builds both, so the bytes that are hashed and the bytes
        that are written cannot drift apart (Law 19).
        """
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "line_span": [self.line_span[0], self.line_span[1]],
            "operator": self.operator,
            "original": self.original,
            "test_target": list(self.test_target),
        }


@dataclass(frozen=True)
class Environment:
    """Where a universe came from — the answer to `4429 there, 4709 here`.

    Provenance only. None of it reaches `manifest_sha256`, because the question
    that hash answers is *"is this the same set of mutants?"* and the answer must
    not change because the machine did.
    """

    commit: str
    mutmut_version: str
    python_version: str
    platform: str
    dependency_lock_hash: str


@dataclass(frozen=True)
class Manifest:
    """An immutable record of one mutant universe."""

    environment: Environment
    entries: tuple[ManifestEntry, ...]

    @property
    def expected_mutants(self) -> int:
        """The true denominator, fixed before anything ran."""
        return len(self.entries)

    @property
    def manifest_sha256(self) -> str:
        """The identity of the mutant SET. Canonicalisation: module docstring."""
        return mutant_set_digest(self.entries)

    def document(self) -> Mapping[str, object]:
        """The manifest as the JSON object it is written as.

        Key order is fixed here rather than sorted at write time, so two
        generations of one universe are byte-identical. Nothing time-varying
        appears anywhere in it — a timestamp would make the record differ from
        itself and destroy the only property it has.
        """
        return {
            "commit": self.environment.commit,
            "mutmut_version": self.environment.mutmut_version,
            "python_version": self.environment.python_version,
            "platform": self.environment.platform,
            "dependency_lock_hash": self.environment.dependency_lock_hash,
            "manifest_sha256": self.manifest_sha256,
            "expected_mutants": self.expected_mutants,
            "mutants": [entry.row() for entry in self.entries],
        }

    def to_json(self) -> str:
        """The document as text. Deterministic for a given universe."""
        return json.dumps(self.document(), indent=2)


def mutant_set_digest(entries: Sequence[ManifestEntry]) -> str:
    """sha256 over the mutant list alone. Canonicalisation: module docstring.

    `sort_keys` orders the keys WITHIN each row; the rows themselves stay in
    manifest order, which is already canonical. `separators` removes every
    optional space and `ensure_ascii` forces a byte-identical payload whatever
    the locale, so the digest is a property of the universe and of nothing else.
    """
    payload = json.dumps(
        [entry.row() for entry in entries],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# Building the record from what mutmut wrote
# ═══════════════════════════════════════════════════════════════════════════


def read_spans(mutants_dir: Path, source: str) -> dict[str, tuple[int, int]]:
    """mutmut's line-span index for one mutated file.

    Read here rather than through `mutmut.mutation.data.MutantLineSpans` for a
    stated reason: that class hardcodes `Path("mutants")` as the tree root
    (`data.py:33-34`), so it cannot address a mutation copy anywhere else, and
    every test below builds its copy under a temporary directory.
    """
    path = mutants_dir / f"{source}{SPANS_SUFFIX}"
    index = _load_json_object(path)
    version = index.get("version")
    if version != SPANS_FORMAT_VERSION:
        raise ManifestError(
            f"{path} declares span format {version!r}, not {SPANS_FORMAT_VERSION}. "
            "Reading it anyway would attribute the wrong lines to every mutant."
        )
    spans = index.get("spans")
    if not isinstance(spans, dict):
        raise ManifestError(f"{path} has no `spans` mapping, so no mutant has a location")
    located: dict[str, tuple[int, int]] = {}
    for function, span in spans.items():
        if not isinstance(span, list) or len(span) != SPAN_LENGTH:
            raise ManifestError(f"{path} gives {function} a span of {span!r}, not [start, end]")
        start, end = span
        if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool):
            raise ManifestError(f"{path} gives {function} a non-integer span {span!r}")
        located[str(function)] = (start, end)
    return located


def read_function_sources(
    mutated_file: Path, spans: Mapping[str, tuple[int, int]]
) -> dict[str, str]:
    """Every named function's text, sliced out of one mutated file in one read.

    One pass per FILE rather than per mutant. A mutated module holds hundreds of
    generated functions, and re-opening it for each of them turns an O(files)
    read into an O(mutants) one.
    """
    try:
        lines = mutated_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as error:
        raise ManifestError(f"{mutated_file} could not be read: {error}") from error
    sources: dict[str, str] = {}
    for function, (start, end) in spans.items():
        if start < 1 or end > len(lines) or end < start:
            raise ManifestError(
                f"{mutated_file} has {len(lines)} lines; {function} claims {start}-{end}"
            )
        sources[function] = "".join(lines[start - 1 : end])
    return sources


def observed_edit(original: str, mutated: str, original_name: str, mutant_name: str) -> str:
    """The unified diff of one function against its mutant, changed lines only.

    Both generated names are replaced with a placeholder first, because the `def`
    line always differs — `x_f__mutmut_orig` against `x_f__mutmut_3` — and
    reporting that as the mutation would bury the actual edit under noise present
    in every single row.

    `n=0` keeps only the changed lines. The hunk headers are dropped for the same
    reason: they are line numbers in the mutation copy, which `line_span` already
    carries.
    """
    left = original.replace(original_name, FUNCTION_PLACEHOLDER).splitlines()
    right = mutated.replace(mutant_name, FUNCTION_PLACEHOLDER).splitlines()
    changed = [
        line
        for line in difflib.unified_diff(left, right, lineterm="", n=0)
        if line.startswith(("-", "+")) and not line.startswith(("---", "+++"))
    ]
    return "\n".join(changed)


def original_function_name(mutant_function: str) -> str:
    """`x_add__mutmut_3` -> `x_add__mutmut_orig`, mutmut's untouched copy."""
    head, separator, _ = mutant_function.rpartition(MUTANT_INDEX_SEPARATOR)
    if not separator:
        raise ManifestError(
            f"{mutant_function!r} is not a generated mutant name: it has no "
            f"{MUTANT_INDEX_SEPARATOR!r}, so its original cannot be located"
        )
    return f"{head}{ORIGINAL_SUFFIX}"


def _detail_for_source(
    mutants_dir: Path,
    source: str,
    mutants: Sequence[Mutant],
    covering: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[tuple[int, int], str, str, tuple[str, ...]]]:
    """Location, edit, original text and covering tests for one file's mutants."""
    spans = read_spans(mutants_dir, source)
    sources = read_function_sources(mutants_dir / source, spans)
    detail: dict[str, tuple[tuple[int, int], str, str, tuple[str, ...]]] = {}
    for mutant in mutants:
        function = generated_function(mutant.name)
        original_name = original_function_name(function)
        if function not in spans or original_name not in spans:
            raise ManifestError(
                f"{mutants_dir / source}{SPANS_SUFFIX} indexes no span for "
                f"{function!r} or {original_name!r}, so {mutant.name} has no location "
                "and no original. A mutant nobody can locate is a mutant nobody can run."
            )
        edit = observed_edit(sources[original_name], sources[function], original_name, function)
        if not edit:
            raise ManifestError(
                f"{mutant.name} is textually identical to its original. A mutant that "
                "changes nothing cannot be killed by any test, and recording it as a "
                "mutant would put an unkillable entry in the denominator."
            )
        detail[mutant.name] = (
            spans[function],
            edit,
            sources[original_name],
            covering.get(mangled_name(mutant.name), ()),
        )
    return detail


def manifest_from_mutants(
    mutants: Sequence[Mutant],
    environment: Environment,
    detail: Mapping[str, tuple[tuple[int, int], str, str, tuple[str, ...]]],
) -> Manifest:
    """Freeze `mutants` as a universe, refusing anything ambiguous.

    Deliberately takes records rather than a directory, so the ordering guarantee
    can be attacked directly with a reversed input.

    SORTED FIRST, ALWAYS. The input arrives from a `dict` and an `rglob`, and both
    of those orders are properties of a machine rather than of the tree. An ID
    derived from either would make shard 3 of 16 mean different things on the
    generator and the runner, which is the one thing a manifest exists to stop.
    The order is lexicographic on `(source, name)`, so `__mutmut_10` precedes
    `__mutmut_2` — not numeric order, and not pretending to be; reproducible,
    which is the property being bought.

    NO STATUS IS RECORDED. A manifest is generated once and read many times,
    including after mutants have run; carrying a verdict would make the same
    universe hash differently before and after execution.
    """
    sources_by_name: dict[str, list[str]] = {}
    for mutant in mutants:
        sources_by_name.setdefault(mutant.name, []).append(mutant.source)
    repeated = sorted(name for name, sources in sources_by_name.items() if len(sources) > ONE_CLAIM)
    if repeated:
        raise ManifestError(
            "these mutants are claimed more than once, so their identity and any "
            f"runtime measured against them is ambiguous: {', '.join(repeated)}. "
            "A mutant belongs to exactly one source file, and two claims means the "
            "meta store is corrupt — picking either would be a guess."
        )
    if not sources_by_name:
        raise ManifestError(
            "no mutants were given, so there is no universe to freeze. Zero is not a "
            "small denominator; it is a broken generation step, and a manifest "
            "recording `expected_mutants: 0` makes every later check vacuous."
        )
    missing = sorted(name for name in sources_by_name if name not in detail)
    if missing:
        raise ManifestError(
            f"{len(missing)} mutants have no location, original or test target: "
            f"{', '.join(missing[:5])}. Every mutant carries all four or none does."
        )
    ordered = sorted((sources[0], name) for name, sources in sources_by_name.items())
    entries = []
    for index, (source, name) in enumerate(ordered, start=1):
        line_span, operator, original, test_target = detail[name]
        entries.append(
            ManifestEntry(
                id=f"{ID_PREFIX}{index:0{ID_DIGITS}d}",
                name=name,
                source=source,
                line_span=line_span,
                operator=operator,
                original=original,
                test_target=test_target,
            )
        )
    return Manifest(environment=environment, entries=tuple(entries))


def generate_manifest(mutants_dir: Path, environment: Environment) -> Manifest:
    """CAPABILITY 1. Freeze and hash the universe under `mutants_dir`.

    The mutant set comes from `mutation_denominator.read_mutants`, this
    repository's one reader of mutmut's meta store (Law 15). It returns every
    GENERATED mutant, including the ones no run has reached, which is precisely
    the population a manifest must fix.

    THE COVERING TESTS ARE REQUIRED, NOT OPTIONAL. `mutmut-stats.json` is written
    by mutmut's stats phase, which runs after generation and before the first
    mutant. A manifest built before it exists would carry an empty `test_target`
    for every mutant — indistinguishable from "no test covers this", which is a
    real and different answer — so its absence is an error naming the fix rather
    than a column of empty lists.
    """
    mutants = read_mutants(mutants_dir)
    covering = read_covering_tests(mutants_dir)
    by_source: dict[str, list[Mutant]] = {}
    for mutant in mutants:
        by_source.setdefault(mutant.source, []).append(mutant)
    detail: dict[str, tuple[tuple[int, int], str, str, tuple[str, ...]]] = {}
    for source, group in sorted(by_source.items()):
        detail.update(_detail_for_source(mutants_dir, source, group, covering))
    return manifest_from_mutants(mutants, environment, detail)


# ═══════════════════════════════════════════════════════════════════════════
# Reading the record back — fail-closed, or the freeze is decoration
# ═══════════════════════════════════════════════════════════════════════════


def _text(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str):
        raise ManifestError(f"`{key}` is {type(value).__name__}, not a string")
    return value


def _row_text(row: Mapping[str, object], key: str, position: int) -> str:
    value = row[key]
    if not isinstance(value, str):
        raise ManifestError(
            f"mutant {position} has `{key}` as {type(value).__name__}, not a string"
        )
    return value


def _row_span(row: Mapping[str, object], position: int) -> tuple[int, int]:
    value = row["line_span"]
    if not isinstance(value, list) or len(value) != SPAN_LENGTH:
        raise ManifestError(f"mutant {position} has `line_span` {value!r}, not [start, end]")
    start, end = value
    if isinstance(start, bool) or isinstance(end, bool):
        raise ManifestError(f"mutant {position} has a boolean in `line_span`")
    if not isinstance(start, int) or not isinstance(end, int):
        raise ManifestError(f"mutant {position} has a non-integer `line_span` {value!r}")
    return (start, end)


def _row_tests(row: Mapping[str, object], position: int) -> tuple[str, ...]:
    value = row["test_target"]
    if not isinstance(value, list):
        raise ManifestError(
            f"mutant {position} has `test_target` as {type(value).__name__}, not a list"
        )
    tests: list[str] = []
    for test in value:
        if not isinstance(test, str):
            raise ManifestError(
                f"mutant {position} has a non-string entry in `test_target`: {test!r}"
            )
        tests.append(test)
    return tuple(tests)


def _entries_from_rows(rows: object) -> tuple[ManifestEntry, ...]:
    if not isinstance(rows, list):
        raise ManifestError(f"`mutants` is {type(rows).__name__}, not a list")
    entries: list[ManifestEntry] = []
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ManifestError(f"mutant {position} is {type(row).__name__}, not an object")
        typed = {str(key): value for key, value in row.items()}
        absent = [key for key in MUTANT_KEYS if key not in typed]
        if absent:
            raise ManifestError(f"mutant {position} has no {', '.join(absent)}")
        # Extra fields are REFUSED, not ignored. A row carrying something this
        # reader does not understand was written by a different version of this
        # schema, and reading it as though the unknown field said nothing is how
        # a v2 manifest gets silently consumed as a v1 one.
        unexpected = sorted(set(typed) - set(MUTANT_KEYS))
        if unexpected:
            raise ManifestError(
                f"mutant {position} carries fields this schema does not define: "
                f"{', '.join(unexpected)}"
            )
        entries.append(
            ManifestEntry(
                id=_row_text(typed, "id", position),
                name=_row_text(typed, "name", position),
                source=_row_text(typed, "source", position),
                line_span=_row_span(typed, position),
                operator=_row_text(typed, "operator", position),
                original=_row_text(typed, "original", position),
                test_target=_row_tests(typed, position),
            )
        )
    return tuple(entries)


def manifest_from_document(document: Mapping[str, object]) -> Manifest:
    """Rebuild a manifest, refusing one that has been edited since it was written.

    THREE CHECKS, and each one catches what the others cannot.

    `expected_mutants` against the length of the list it describes — a count
    edited on its own.

    `manifest_sha256` against a fresh digest of the mutant list — any change to a
    name, a location, an edit, an original, a test target or the membership.

    Every ID against a fresh derivation from the canonical order — the case the
    digest cannot see, because somebody who renumbers the IDs can also recompute
    the digest. Two independent records of the same fact, and both must agree.
    """
    missing = [key for key in MANIFEST_KEYS if key not in document]
    if missing:
        raise ManifestError(f"this is not a manifest: it is missing {', '.join(missing)}")

    entries = _entries_from_rows(document["mutants"])
    declared_count = document["expected_mutants"]
    if isinstance(declared_count, bool) or not isinstance(declared_count, int):
        raise ManifestError(
            f"`expected_mutants` is {type(declared_count).__name__}, not a whole number"
        )
    if declared_count != len(entries):
        raise ManifestError(
            f"`expected_mutants` says {declared_count}, the mutant list holds {len(entries)}"
        )

    digest = mutant_set_digest(entries)
    if _text(document, "manifest_sha256") != digest:
        raise ManifestError(
            f"`manifest_sha256` says {_text(document, 'manifest_sha256')}, the mutant list "
            f"hashes to {digest}. This document was edited after it was written, so it "
            "records a universe that never existed."
        )

    expected_ids = [f"{ID_PREFIX}{index:0{ID_DIGITS}d}" for index in range(1, len(entries) + 1)]
    canonical = sorted((entry.source, entry.name) for entry in entries)
    if [entry.id for entry in entries] != expected_ids or [
        (entry.source, entry.name) for entry in entries
    ] != canonical:
        raise ManifestError(
            "the IDs in this manifest are not the canonical numbering of the mutants "
            "it lists. An ID is derived from the `(source, name)` order, never chosen, "
            "so a hand-assigned one means the document was rewritten — digest included."
        )

    return Manifest(
        environment=Environment(
            commit=_text(document, "commit"),
            mutmut_version=_text(document, "mutmut_version"),
            python_version=_text(document, "python_version"),
            platform=_text(document, "platform"),
            dependency_lock_hash=_text(document, "dependency_lock_hash"),
        ),
        entries=entries,
    )


def read_manifest(path: Path) -> Manifest:
    """A manifest from disk. The JSON reader is `mutation_denominator`'s."""
    return manifest_from_document(_load_json_object(path))


# ═══════════════════════════════════════════════════════════════════════════
# Provenance — collected from the real environment, never invented
# ═══════════════════════════════════════════════════════════════════════════


def head_commit(repo_root: Path) -> str:
    """The commit this universe belongs to, from git.

    Law 56 makes a measurement without its commit invalid, so a failure here is
    an error and never a placeholder: an empty or invented commit would make the
    manifest look valid while binding every number taken against it to nothing.
    """
    completed = subprocess.run(  # noqa: S603 - argv list, no shell
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],  # noqa: S607 - git on PATH
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ManifestError(
            f"git could not name the HEAD commit of {repo_root}: "
            f"{completed.stderr.strip() or 'no output'}"
        )
    commit = completed.stdout.strip()
    if not commit:
        raise ManifestError(f"git printed no commit for {repo_root}")
    return commit


def dependency_lock_hash(repo_root: Path) -> str:
    """One digest over every pinned requirements file, names included.

    The names are hashed as well as the bytes so that adding, deleting or
    RENAMING a manifest changes the result. Hashing contents alone would let one
    requirements file be swapped for another without the lock hash noticing.
    """
    paths = sorted(path for path in repo_root.glob(DEPENDENCY_LOCK_GLOB) if path.is_file())
    if not paths:
        raise ManifestError(
            f"no {DEPENDENCY_LOCK_GLOB} under {repo_root}, so the installed versions "
            "cannot be pinned. An empty lock hash would be a stable value that "
            "compares equal in every environment — the strongest possible false green."
        )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def describe_environment(repo_root: Path) -> Environment:
    """The environment that produced a universe, as this process observes it.

    Every field is read live rather than passed in, because the number these
    fields exist to explain — 4429 on CI against 4709 here — is a difference
    between two running processes, and a field copied from somewhere else
    explains nothing.
    """
    return Environment(
        commit=head_commit(repo_root),
        mutmut_version=metadata.version("mutmut"),
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_lock_hash=dependency_lock_hash(repo_root),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Runtime history — mutmut's own timings, validated as untrusted input
# ═══════════════════════════════════════════════════════════════════════════


def validated_history(history: Mapping[str, object]) -> dict[str, float]:
    """Seconds per mutant name, refusing anything that is not a duration.

    `NaN` is the dangerous entry and the reason this exists. Every comparison
    against it is False, so the least-loaded search below would return shard 1
    forever and the cost sort would collapse to input order — a partition that
    silently stops being deterministic, with nothing in the output to say so.

    `True` is refused for a quieter reason: `bool` is a subclass of `int`, so a
    naive numeric test accepts it and one second becomes one boolean.
    """
    seconds_by_name: dict[str, float] = {}
    for name, value in history.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ManifestError(
                f"the runtime recorded for {name} is {type(value).__name__}, not a number"
            )
        seconds = float(value)
        if not math.isfinite(seconds) or seconds < 0:
            raise ManifestError(f"the runtime recorded for {name} is {seconds}, not a duration")
        seconds_by_name[str(name)] = seconds
    return seconds_by_name


def read_runtime_history(mutants_dir: Path) -> dict[str, float]:
    """mutmut's own per-mutant wall-clock timings, from the meta store.

    FOUND, NOT MANUFACTURED. `mutmut/mutation/data.py:130-138` writes the elapsed
    seconds of every mutant it runs into `durations_by_key`, in the same `.meta`
    files the universe is read from. There is nothing to instrument.

    A tree that has never been run carries no durations, and that is returned as
    an empty history rather than an error — generation legitimately precedes
    execution. `shard_manifest` then reports the balance as `count only` instead
    of inventing a number.
    """
    if not mutants_dir.is_dir():
        raise ManifestError(f"{mutants_dir} is not a directory, so it records no durations")
    history: dict[str, float] = {}
    for meta_path in _meta_files(mutants_dir):
        durations = _load_json_object(meta_path).get(DURATIONS_KEY, {})
        if not isinstance(durations, dict):
            raise ManifestError(
                f"{meta_path} records `{DURATIONS_KEY}` as {type(durations).__name__}, "
                "not a mapping"
            )
        history.update(validated_history({str(key): value for key, value in durations.items()}))
    return history


# ═══════════════════════════════════════════════════════════════════════════
# The partition
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Shard:
    """One worker's share of the universe."""

    #: 1-based, to match `M-000001` and a CI matrix a human reads.
    index: int
    of: int
    entries: tuple[ManifestEntry, ...]
    #: Seconds this shard is KNOWN to cost. Zero when nothing in it was measured
    #: — never an estimate standing in for one.
    measured_seconds: float
    #: How many of `entries` carry no measurement at all.
    unmeasured: int


@dataclass(frozen=True)
class Sharding:
    """A complete, disjoint partition of one manifest, and what balanced it."""

    manifest_sha256: str
    shards: tuple[Shard, ...]
    measured: int
    unmeasured: int
    #: Names in the supplied history that this manifest does not contain — a
    #: history recorded against a different universe.
    history_names_unused: int

    @property
    def total(self) -> int:
        return self.measured + self.unmeasured

    @property
    def basis(self) -> str:
        """What the balance is actually founded on, in one sentence.

        Never says `balanced` without saying WHAT BY. An even split by count is
        an even split by DURATION only if every mutant costs the same, and that
        is a claim nothing here has measured.
        """
        if self.measured == 0:
            return (
                "BALANCE BASIS: mutant COUNT only. No runtime history was supplied, so "
                "every mutant is assumed to cost the same. That assumption is UNMEASURED."
            )
        if self.unmeasured == 0:
            return f"BALANCE BASIS: MEASURED RUNTIME for all {self.measured} mutants."
        return (
            f"BALANCE BASIS: MEASURED RUNTIME for {self.measured} of {self.total} mutants; "
            f"the remaining {self.unmeasured} carry no measurement and are spread by COUNT."
        )

    def shard(self, index: int) -> Shard:
        """Shard `index`, 1-based. An index outside the range is refused."""
        if not MINIMUM_SHARDS <= index <= len(self.shards):
            raise ManifestError(
                f"shard {index} does not exist: this manifest was cut into "
                f"{len(self.shards)}, numbered between {MINIMUM_SHARDS} and {len(self.shards)}"
            )
        return self.shards[index - 1]

    def reconciliation(self) -> list[str]:
        """The counts, and the arithmetic that has to close for them to mean anything.

        Printed as an identity rather than a claim: every line states two numbers
        that must be equal and whether they are. A report that says `complete`
        without showing the sum is asking to be believed.
        """
        placed = [entry for shard in self.shards for entry in shard.entries]
        distinct = len({entry.id for entry in placed})
        rows = (
            ("mutants in the manifest", self.total),
            ("sum of shard sizes", len(placed)),
            ("distinct ids placed", distinct),
            ("measured + unmeasured", self.measured + self.unmeasured),
            ("sum of per-shard unmeasured", sum(shard.unmeasured for shard in self.shards)),
        )
        lines = ["RECONCILIATION"]
        lines += [f"  {label:32} {count:>8}" for label, count in rows[:4]]
        agree = len({count for _, count in rows[:4]}) == 1
        lines.append(
            f"  {'all four equal':32} {'YES' if agree else 'NO — THE PARTITION IS BROKEN':>8}"
        )
        lines.append(f"  {'of which unmeasured':32} {rows[4][1]:>8}")
        return lines

    def describe(self) -> list[str]:
        """The whole assignment as text: basis, reconciliation, then the shards."""
        lines = [
            f"manifest_sha256 {self.manifest_sha256}",
            f"{self.total} mutants -> {len(self.shards)} shards",
            self.basis,
        ]
        if self.history_names_unused:
            lines.append(
                f"{self.history_names_unused} names in the supplied history are not in "
                "this manifest — that history was recorded against a different universe"
            )
        lines.append("")
        lines += self.reconciliation()
        lines.append("")
        lines.append(f"{'shard':>7} {'mutants':>9} {'measured s':>12} {'unmeasured':>12}")
        lines.append("-" * 43)
        lines += [
            f"{shard.index:>7} {len(shard.entries):>9} "
            f"{shard.measured_seconds:>12.3f} {shard.unmeasured:>12}"
            for shard in self.shards
        ]
        return lines


def shard_header(
    shard: Shard, manifest_sha256: str, environment: Environment
) -> Mapping[str, object]:
    """The FIRST LINE of a shard result file, as the aggregator consumes it.

    Emitted from THIS side on purpose. All five values are properties of the
    manifest and the shard, and letting the executor retype them is how the two
    halves come to agree by accident and disagree later for a reason nobody can
    name.
    """
    return {
        "shard_index": shard.index,
        "shard_count": shard.of,
        "manifest_sha256": manifest_sha256,
        "commit": environment.commit,
        "dependency_lock_hash": environment.dependency_lock_hash,
    }


def _fill(
    entries: Sequence[ManifestEntry],
    cost_of: Callable[[ManifestEntry], float],
    buckets: Sequence[list[ManifestEntry]],
    load: list[float],
) -> None:
    """Longest-processing-time-first: heaviest mutant into the lightest shard.

    EVERY TIE IS BROKEN EXPLICITLY. Equal cost falls back to the lowest ID, and
    equal load to the lowest shard index. Without both, a merely-stable sort
    would still let two machines that enumerated the mutants differently produce
    different shards, and nothing downstream could tell.

    This chooses WHICH shard. It never chooses WHETHER: every entry handed to it
    is appended to some bucket, on every path.
    """
    for entry in sorted(entries, key=lambda item: (-cost_of(item), item.id)):
        target = min(range(len(load)), key=lambda index: (load[index], index))
        buckets[target].append(entry)
        load[target] += cost_of(entry)


def shard_manifest(
    manifest: Manifest,
    shard_count: int,
    runtime_history: Mapping[str, object] | None = None,
) -> Sharding:
    """CAPABILITY 2. Cut `manifest` into `shard_count` deterministic shards.

    THE GUARANTEE: every mutant lands in exactly one shard, the union is the
    manifest, and the same manifest with the same count produces the same
    assignment on every machine. Shard sizes are COMPUTED from the manifest;
    none is assumed.

    COST NEVER DECIDES INCLUSION. `measured` and `unmeasured` are a partition of
    `manifest.entries` by one predicate — is there a recorded duration — and BOTH
    are filled. A mutant nobody has ever timed is assigned exactly as surely as
    the most expensive one. This is the distinction that matters: the previous
    run lost ~1536 mutants because cost ordering decided what got reached.

    TWO ACCUMULATORS, NOT ONE, AND THAT IS THE POINT. Measured mutants are
    balanced against each other in SECONDS; unmeasured ones are spread against
    each other by COUNT, on a separate accumulator. Adding a count to a duration
    would be an arithmetic error wearing a number, and giving the unmeasured ones
    an average would be a fabricated measurement (Law 24) indistinguishable from
    a real one. The two populations are reported separately for the same reason.

    `shard_count` is an argument. No default, no maximum and no timeout is
    invented here.
    """
    if shard_count < MINIMUM_SHARDS:
        raise ManifestError(
            f"{shard_count} shards is not a partition: at least one shard is needed to "
            f"hold {manifest.expected_mutants} mutants"
        )
    history = validated_history(runtime_history or {})
    measured = tuple(item for item in manifest.entries if item.name in history)
    unmeasured = tuple(item for item in manifest.entries if item.name not in history)

    buckets: list[list[ManifestEntry]] = [[] for _ in range(shard_count)]
    _fill(measured, lambda item: history[item.name], buckets, [0.0] * shard_count)
    _fill(unmeasured, lambda _: 1.0, buckets, [0.0] * shard_count)

    return Sharding(
        manifest_sha256=manifest.manifest_sha256,
        shards=tuple(
            Shard(
                index=index,
                of=shard_count,
                entries=tuple(sorted(bucket, key=lambda item: item.id)),
                measured_seconds=sum(history.get(item.name, 0.0) for item in bucket),
                unmeasured=sum(1 for item in bucket if item.name not in history),
            )
            for index, bucket in enumerate(buckets, start=MINIMUM_SHARDS)
        ),
        measured=len(measured),
        unmeasured=len(unmeasured),
        history_names_unused=len(set(history) - {item.name for item in manifest.entries}),
    )


# ═══════════════════════════════════════════════════════════════════════════
# The command line — the seam CI uses
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GenerateOptions:
    """What `generate` was asked for."""

    mutants_dir: Path
    out: Path | None


@dataclass(frozen=True)
class ShardOptions:
    """What `shard` was asked for."""

    manifest: Path
    shards: int
    index: int | None
    header: bool
    durations_from: Path | None


def _value(remaining: list[str], option: str) -> str:
    if not remaining:
        raise SystemExit(f"{option} needs a value\n{_USAGE}")
    return remaining.pop(0)


def _whole_number(text: str, option: str) -> int:
    try:
        return int(text)
    except ValueError as error:
        raise SystemExit(f"{option} needs a whole number, not {text!r}\n{_USAGE}") from error


def _parse_generate(remaining: list[str]) -> GenerateOptions:
    mutants_dir = Path(MUTATION_COPY_DIRECTORY)
    out: Path | None = None
    while remaining:
        argument = remaining.pop(0)
        if argument == "--mutants-dir":
            mutants_dir = Path(_value(remaining, argument))
        elif argument == "--out":
            out = Path(_value(remaining, argument))
        else:
            raise SystemExit(_USAGE)
    return GenerateOptions(mutants_dir=mutants_dir, out=out)


def _parse_shard(remaining: list[str]) -> ShardOptions:
    manifest: Path | None = None
    shards: int | None = None
    index: int | None = None
    header = False
    durations_from: Path | None = None
    while remaining:
        argument = remaining.pop(0)
        if argument == "--manifest":
            manifest = Path(_value(remaining, argument))
        elif argument == "--shards":
            shards = _whole_number(_value(remaining, argument), argument)
        elif argument == "--index":
            index = _whole_number(_value(remaining, argument), argument)
        elif argument == "--header":
            header = True
        elif argument == "--durations-from":
            durations_from = Path(_value(remaining, argument))
        else:
            raise SystemExit(_USAGE)
    if manifest is None or shards is None:
        raise SystemExit(f"shard needs --manifest and --shards\n{_USAGE}")
    if header and index is None:
        raise SystemExit(f"--header needs --index: a header names ONE shard\n{_USAGE}")
    return ShardOptions(
        manifest=manifest,
        shards=shards,
        index=index,
        header=header,
        durations_from=durations_from,
    )


def parse_argv(argv: Sequence[str]) -> GenerateOptions | ShardOptions:
    """Read the command line. Refuses anything it does not recognise.

    Hand-rolled rather than `argparse` on purpose: argparse accepts unambiguous
    PREFIXES, so `--shard 2` would silently mean `--shards 2`. A typo that
    changes the partition and reports success is exactly the failure mode this
    module exists to remove.
    """
    remaining = list(argv[1:])
    if not remaining:
        raise SystemExit(_USAGE)
    command = remaining.pop(0)
    if command == GENERATE:
        return _parse_generate(remaining)
    if command == SHARD:
        return _parse_shard(remaining)
    raise SystemExit(_USAGE)


def _run_generate(options: GenerateOptions) -> int:
    manifest = generate_manifest(options.mutants_dir, describe_environment(authored_repo_root()))
    document = manifest.to_json()
    if options.out is None:
        print(document)
    else:
        options.out.write_text(document + "\n", encoding="utf-8")
        print(f"wrote {options.out}")
    # Provenance on stderr, so stdout is the document and nothing else.
    print(
        f"{manifest.expected_mutants} mutants  "
        f"manifest_sha256={manifest.manifest_sha256}  "
        f"commit={manifest.environment.commit}",
        file=sys.stderr,
    )
    return 0


def _run_shard(options: ShardOptions) -> int:
    manifest = read_manifest(options.manifest)
    history = (
        None if options.durations_from is None else read_runtime_history(options.durations_from)
    )
    sharding = shard_manifest(manifest, options.shards, history)
    if options.index is None:
        for line in sharding.describe():
            print(line)
        return 0
    shard = sharding.shard(options.index)
    if options.header:
        print(
            json.dumps(
                shard_header(shard, manifest.manifest_sha256, manifest.environment),
                separators=(",", ":"),
            )
        )
        return 0
    for item in shard.entries:
        print(item.name)
    return 0


def cli(argv: Sequence[str] | None = None) -> int:
    """Freeze a manifest, or print one shard of it.

    Exit code 0 means the request was answered. Nothing here judges quality, so
    there is no other code to return; an unsound universe, an edited manifest or
    an impossible shard raises instead, loudly and with the reason (Law 11).
    """
    options = parse_argv(sys.argv if argv is None else argv)
    if isinstance(options, GenerateOptions):
        return _run_generate(options)
    return _run_shard(options)


if __name__ == "__main__":
    raise SystemExit(cli())
