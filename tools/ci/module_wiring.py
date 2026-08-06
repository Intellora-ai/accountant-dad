"""Is this module REACHED by anything that runs? (F-018)

THE QUESTION NO OTHER GATE ASKS. `unit tests`, `coverage` and `mutation` each
examine a module in isolation and each goes green on a module nothing calls:
the tests import it directly, the coverage counts the lines those tests ran,
and the mutants die against those same tests. Three green gates, zero
consumers. `classification`, `config` and `measurement` passed all three while
never seeing a document.

THE TRANSFORM (Law 53). *"Does this module do its job in production?"* needs a
running system, a real document and a human to judge the answer. *"Is this
module reachable in the first-party import graph from the Application Layer's
entry point?"* needs a parser, answers in milliseconds, and fails in the same
place. This module answers the second.

REACHABILITY, NOT POPULARITY. The predicate is *reachable from the entry
point*, never *somebody imports it*. Two orphans that import each other each
have a consumer and neither one ever runs; only a walk from the thing that
actually starts can tell those apart.

DEFERRED IMPORTS COUNT. `reader.py` resolves heavy optional dependencies inside
functions. An edge is an edge wherever the statement sits, so `ast.walk`
descends into function bodies — refusing to would report a wired module as an
orphan, and a detector that cries wolf is a detector that gets weakened.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterable, Mapping

import first_party

#: Graph edges, module to the first-party modules it imports.
type Graph = Mapping[str, frozenset[str]]


class UnknownModuleError(Exception):
    """Raised when an entry point or scope name is not a module on disk.

    Never treated as "unreachable". A typo'd entry point makes every module
    unreachable, which reads as *"the whole engine is orphaned"* — alarming,
    wrong, and eventually ignored (Law 11).
    """


def edges_from(tree: ast.Module, dotted: str, package: str) -> frozenset[str]:
    """Every first-party module the parsed module imports.

    `from accountant_dad.engines.input_engine import assembly` yields BOTH the
    package and the submodule: the statement genuinely imports the package to
    reach the submodule, and edging only to the parent would leave every
    submodule imported by name with no inbound edge at all.

    A name that is not a module — `from accountant_dad.confidence import
    Confidence` — contributes only the module that defines it.
    """
    known = set(first_party.module_files())
    edges: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = first_party.absolute_module(node, package)
            if base is None:
                continue
            if base in known:
                edges.add(base)
            edges |= {
                candidate for alias in node.names if (candidate := f"{base}.{alias.name}") in known
            }
        elif isinstance(node, ast.Import):
            edges |= {alias.name for alias in node.names if alias.name in known}

    edges.discard(dotted)
    return frozenset(edges)


def import_graph() -> Graph:
    """The whole first-party import graph, built from AUTHORED source."""
    files = first_party.module_files()
    return {
        dotted: edges_from(
            first_party.parse(path),
            dotted,
            first_party.containing_package(dotted, path),
        )
        for dotted, path in files.items()
    }


def walk(graph: Graph, entry: str) -> frozenset[str]:
    """Every node reachable from `entry`, cycles included.

    The seen-set is not an optimisation. Without it a cycle — and this package
    has packages importing submodules that import the package — hangs the gate
    instead of failing it, and a hung gate is indistinguishable from a slow one.
    """
    seen: set[str] = set()
    pending = [entry]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(graph.get(node, frozenset()) - seen)
    return frozenset(seen)


def reachable_from(entry: str) -> frozenset[str]:
    """Every first-party module reached from `entry` on the real tree."""
    graph = import_graph()
    if entry not in graph:
        raise UnknownModuleError(f"{entry!r} is not a module in {first_party.PACKAGE}")
    return walk(graph, entry)


def unreachable_in(graph: Graph, entry: str, scope: Iterable[str]) -> tuple[str, ...]:
    """Which of `scope` a walk from `entry` never reaches, sorted."""
    reached = walk(graph, entry)
    return tuple(sorted(set(scope) - reached))


def unreachable(entry: str, scope: Iterable[str]) -> tuple[str, ...]:
    """Which of `scope` never runs, on the real tree.

    Every name in `scope` must be a real module: asking about a module that
    does not exist would silently report it as an orphan, which is the same
    wrong answer for the opposite reason.
    """
    graph = import_graph()
    unknown = sorted(set(scope) - set(graph))
    if unknown:
        raise UnknownModuleError(f"not modules in {first_party.PACKAGE}: {unknown}")
    if entry not in graph:
        raise UnknownModuleError(f"{entry!r} is not a module in {first_party.PACKAGE}")
    return unreachable_in(graph, entry, scope)


def modules_imported_by_tests() -> frozenset[str]:
    """Every first-party module any file under `tests/` imports."""
    tests = first_party.repo_root() / "tests"
    imported: set[str] = set()
    for path in sorted(tests.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported |= edges_from(tree, "", first_party.PACKAGE)
    return frozenset(imported)


def not_imported_by_tests(scope: Iterable[str]) -> tuple[str, ...]:
    """Which of `scope` no test imports — modules with no evidence at all."""
    return tuple(sorted(set(scope) - modules_imported_by_tests()))


def coverage_source_directories() -> tuple[str, ...]:
    """`[tool.coverage.run] source`, read from `pyproject.toml`.

    Read rather than restated so the coverage gate and this check cannot
    disagree about what the coverage gate measures (Law 19).
    """
    config = first_party.repo_root() / "pyproject.toml"
    with config.open("rb") as handle:
        document = tomllib.load(handle)
    source = document["tool"]["coverage"]["run"]["source"]
    if not isinstance(source, list):
        raise TypeError(f"[tool.coverage.run] source is {type(source).__name__}, expected a list")
    return tuple(str(entry) for entry in source)


def outside_coverage_scope(scope: Iterable[str]) -> tuple[str, ...]:
    """Which of `scope` the coverage gate cannot see.

    A module outside every `source` directory contributes nothing to the
    coverage percentage, so the coverage floor stays satisfied however untested
    it is.
    """
    files = first_party.module_files()
    root = first_party.repo_root()
    directories = [root / entry for entry in coverage_source_directories()]

    outside: list[str] = []
    for dotted in scope:
        path = files.get(dotted)
        if path is None:
            raise UnknownModuleError(f"{dotted!r} is not a module in {first_party.PACKAGE}")
        if not any(path.is_relative_to(directory) for directory in directories):
            outside.append(dotted)
    return tuple(sorted(outside))
