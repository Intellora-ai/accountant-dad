#!/usr/bin/env python3
"""Every dependency manifest in this repository gets audited. Not just the one.

── THE MEASURED HOLE THIS EXISTS TO CLOSE ────────────────────────────────

`dependency scan` (`.github/workflows/security.yml:99-145`) audits exactly two
things:

    pip-audit --strict --requirement requirements-ci.txt
    pip-audit --strict .                       # pyproject's five declared deps

The repository has THREE requirements manifests. The other two —
`requirements-engine1.txt` and `requirements-engine1-ocr.txt` — are installed by
four other CI jobs and have never been passed to pip-audit. Measured at commit
a467bb2, they carry between them:

    docling==2.118.0   transformers==5.8.1   torch==2.13.0
    torchvision==0.28.0   timm==1.0.28   pypdfium2==5.12.1

Six pinned distributions, `torch` among them, enter a CI environment with zero
advisory scanning. The gate is not wrong about what it audits; it is silent
about what it does not, and silence reads as green.

── WHY THE MANIFEST LIST IS DERIVED AND NOT WRITTEN DOWN ─────────────────

Two more `pip-audit --requirement` lines would close today's hole and reopen it
the moment somebody adds a fourth manifest. The list would live in a workflow,
where nothing checks it against the filesystem — the same shape as the hole
itself, one level out.

So the set is DERIVED by walking the tree. A manifest added tomorrow is audited
without editing anything, and a manifest that exists but was skipped is a hard
failure rather than an omission nobody sees.

── WHY THIS FILE RUNS NOTHING ────────────────────────────────────────────

pip-audit is invoked by `audit_dependency_manifests.sh`, not from here. Keeping
the subprocess out of Python leaves everything in this module pure — parsing and
set arithmetic — so the tests exercise the real logic directly instead of
shelling out and asserting on captured text (§J.7: fake only at the I/O edge,
and here there is no I/O to fake).

`verify` is what makes the split safe. The shell loop accumulates the manifests
it ACTUALLY handed to pip-audit and passes them back; `verify` compares that
against what is on disk. A loop that breaks early, filters, or silently skips a
file fails here. That is not circular: one side is what ran, the other is what
exists.

── WHAT IT REFUSES ───────────────────────────────────────────────────────

  1. A discovered manifest that was not audited.
  2. A manifest that declares no pins. Emptying a manifest is the cheapest way
     to make an audit "pass" over it, so zero is refused rather than counted as
     success — the same rule, for the same reason, as
     `assert_imports_match_pins.sh`.
  3. A tree with no manifests at all, which would make every loop below
     quantify over nothing and report success having proved nothing.
  4. An audited path that is not a manifest this repository actually has.

── USAGE ─────────────────────────────────────────────────────────────────

    tools/ci/audit_dependency_manifests.py --list
    tools/ci/audit_dependency_manifests.py --verify <audited> [<audited>...]

`pyproject.toml`'s `[project].dependencies` are not listed here: the existing
`pip-audit --strict .` step already covers them, and auditing them twice would
put one fact in two places (Law 19). `declaration_sites` names both, so a test
can assert the union leaves nothing out.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping, Sequence
from importlib import metadata
from pathlib import Path

from authored_source import MUTATION_COPY_DIRECTORY

#: `name==version`, ignoring comments, blanks, environment markers and anything
#: that is not an exact pin. Only `==` counts: a range is not a pin.
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#]+)")

#: Directories that hold a COPY of the tree rather than the tree. mutmut's
#: working copy carries duplicates of every manifest; auditing those would audit
#: the same pins twice, under paths that do not exist on a clean checkout, and
#: make the count disagree with reality.
#:
#: Its NAME is imported rather than retyped. `authored_source` already owns the
#: answer to *"what is the directory mutmut copies the tree into"* — it is the
#: constant every authored-source redirect strips — and a second spelling of it
#: here is a second place to edit if mutmut ever changes it, with nothing
#: connecting the two (Law 19). The failure would be silent in the worst
#: direction: this audit would walk into the copy and report doubled pins.
NOT_THE_TREE = frozenset(
    {".git", ".venv", "venv", MUTATION_COPY_DIRECTORY, "__pycache__", "node_modules"}
)

#: The one glob that defines "is a dependency manifest", so the question has a
#: single answer rather than one per caller.
MANIFEST_GLOB = "requirements*.txt"

#: Audited by the pre-existing `pip-audit --strict .` step, never by this one.
PYPROJECT = "pyproject.toml"

#: Returned when the command line names no mode this script has. Distinct from
#: 1, which means "the repository failed the check": a caller that mistyped a
#: flag has learned nothing about its dependencies, and must not be told it
#: found a problem.
USAGE_EXIT_CODE = 2


def manifests(repo: Path) -> tuple[Path, ...]:
    """Every requirements manifest in the tree, repo-relative, sorted.

    Recursive on purpose. A manifest in a subdirectory is still installed by
    whoever points at it, and a root-only glob would miss it in silence — which
    is the exact failure mode this file exists to remove.
    """
    found = [
        path.relative_to(repo)
        for path in repo.rglob(MANIFEST_GLOB)
        if not NOT_THE_TREE & set(path.relative_to(repo).parts)
    ]
    return tuple(sorted(found))


def pins(manifest: Path) -> tuple[tuple[str, str], ...]:
    """The exact pins a manifest declares, in file order."""
    found: list[tuple[str, str]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        # No separate comment or blank-line guard. `_PIN` is anchored and its
        # first character class is alphanumeric, so `# comment` and `""` cannot
        # match it. A guard the regex already subsumes is a line that no test
        # can ever turn red, and unfalsifiable code is worse than no code.
        match = _PIN.match(line.strip())
        if match is not None:
            found.append((match.group(1), match.group(2)))
    return tuple(found)


def declaration_sites(repo: Path) -> tuple[Path, ...]:
    """Every file in this repository that declares a dependency.

    The manifests, plus `pyproject.toml`. This is the set that has to be audited
    by SOMEBODY; this script covers the manifests and the pre-existing
    `pip-audit .` step covers pyproject.
    """
    pyproject = Path(PYPROJECT)
    extra = (pyproject,) if (repo / pyproject).is_file() else ()
    return (*manifests(repo), *extra)


def verify(repo: Path, audited: Sequence[str]) -> tuple[str, ...]:
    """Every reason the audit that just ran did not cover this repository.

    Returns the problems. Empty means the audit was complete.
    """
    problems: list[str] = []
    present = manifests(repo)
    if not present:
        return (
            f"no {MANIFEST_GLOB} anywhere under {repo}. Nothing was audited, and a "
            "run that audited nothing is not a pass.",
        )

    handled = {Path(entry) for entry in audited}

    missed = [path for path in present if path not in handled]
    if missed:
        problems.append(
            "these manifests exist and were NOT audited: "
            + ", ".join(str(path) for path in missed)
            + ". Every pin in them enters CI with no advisory scanning."
        )

    unknown = sorted(handled - set(present))
    if unknown:
        problems.append(
            "these were reported as audited but are not manifests in this tree: "
            + ", ".join(str(path) for path in unknown)
            + ". The audit and the repository disagree about what exists."
        )

    for path in present:
        if not pins(repo / path):
            problems.append(
                f"{path} declares no pins. A manifest that pins nothing cannot be "
                "audited, and emptying one is the cheapest way to silence this check."
            )
    return tuple(problems)


# ── the installed tree, not the manifest ────────────────────────────────
#
# Auditing manifests proves things about what was ASKED FOR. It proves nothing
# about what is actually installed. F-023 measured the gap on this repository's
# own environment: 13 distributions present and reachable from no manifest at
# all — leftovers of an earlier install that pip never removed, every one of
# them from the OCR tree. They are importable, they are unpinned, and no audit
# has ever seen them.
#
# The check is reachability, not membership. Demanding that every installed
# distribution be PINNED would fail on every correct environment, because a
# manifest legitimately pulls transitive dependencies it does not name. So the
# closure is walked through each distribution's own declared requirements, and
# only what falls outside it is reported.

#: pip's own footprint. Present in every environment pip built, required by no
#: manifest, and removing them would break the installer that put them there.
#: Named exhaustively rather than pattern-matched, so nothing else slips in.
BOOTSTRAP = frozenset({"pip", "setuptools", "wheel", "pkg-resources", "distribute"})


def canonical(name: str) -> str:
    """PEP 503 normalisation, so `PyYAML`, `pyyaml` and `py_yaml` are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _required_names(raw: str) -> str:
    """The distribution name out of one `Requires-Dist` entry.

    `docling-slim[standard] (>=2.1) ; extra == "ocr"` -> `docling-slim`. Extras
    and markers are deliberately ignored: a dependency declared under an extra
    that was not requested is still installed if something else pulled it, and
    the question here is reachability, not whether pip would install it again.
    """
    head = raw.split(";")[0].strip()
    return canonical(re.split(r"[\s\[<>=!~(]", head, maxsplit=1)[0])


def installed_requirements() -> dict[str, frozenset[str]]:
    """Every installed distribution mapped to the distributions it declares.

    The single I/O edge of the orphan check. Everything below `unreachable` is
    set arithmetic on this mapping and is tested without an environment.
    """
    graph: dict[str, frozenset[str]] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if not name:
            continue
        graph[canonical(name)] = frozenset(
            _required_names(entry) for entry in distribution.requires or []
        )
    return graph


def unreachable(
    pinned: frozenset[str],
    requires: Mapping[str, frozenset[str]],
    bootstrap: frozenset[str] = BOOTSTRAP,
) -> tuple[str, ...]:
    """Installed distributions no manifest can reach, directly or transitively.

    `pinned` are the roots. `requires` is the installed dependency graph. A name
    that is required but not installed is simply absent from the graph and is
    not walked further — an environment cannot be judged on a package it does
    not have.
    """
    closure = {name for name in pinned if name in requires}
    frontier = set(closure)
    while frontier:
        following: set[str] = set()
        for name in frontier:
            for dependency in requires.get(name, frozenset()):
                if dependency in requires and dependency not in closure:
                    closure.add(dependency)
                    following.add(dependency)
        frontier = following
    return tuple(sorted(set(requires) - closure - bootstrap))


def pinned_across(repo: Path, paths: Sequence[str]) -> frozenset[str]:
    """Every distribution pinned by the given manifests, canonically named."""
    return frozenset(canonical(name) for path in paths for name, _ in pins(repo / path))


def cli(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    repo = Path.cwd()

    if args and args[0] == "--orphans":
        # Only meaningful when handed EVERY manifest installed into this
        # interpreter: a subset would report the other manifests' packages as
        # orphans and be wrong in the direction that destroys trust in a guard.
        wanted = args[1:] or [str(path) for path in manifests(repo)]
        strays = unreachable(pinned_across(repo, wanted), installed_requirements())
        if strays:
            print("BLOCKED - installed distributions that no manifest can reach:")
            for name in strays:
                print(f"  {name}")
            print(
                "\nEach is importable, unpinned, and audited by nothing. Rebuild the "
                "environment from the manifests, or pin what is genuinely wanted."
            )
            return 1
        print(f"every installed distribution is reachable from {len(wanted)} manifest(s)")
        return 0

    if args and args[0] == "--list":
        for path in manifests(repo):
            print(path)
        return 0

    if args and args[0] == "--verify":
        problems = verify(repo, args[1:])
        if problems:
            print("BLOCKED - the dependency audit did not cover this repository.")
            for problem in problems:
                print(f"  {problem}")
            return 1
        covered = manifests(repo)
        total = sum(len(pins(repo / path)) for path in covered)
        print(f"audited every manifest in the tree: {len(covered)} files, {total} pins")
        return 0

    print(
        "usage: audit_dependency_manifests.py "
        "--list | --verify <audited>... | --orphans [<manifest>...]"
    )
    return USAGE_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(cli())
