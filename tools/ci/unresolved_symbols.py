"""Does every imported first-party NAME have a definition? (F-024)

WHAT BROKE. `e921c3c` shipped four references to `Exclusion` — a docstring
paragraph, an enum supplying its reasons, a parameter accepting it, and a test
importing it — and never wrote the dataclass. The suite could not collect:

    ImportError: cannot import name 'Exclusion' from 'accountant_dad.conformance'
    !!!! Interrupted: 1 error during collection !!!!

A collection error is not one red test. It is ZERO results: every gate
downstream of `unit tests` had nothing to judge, and Law 1 — keep the repo
buildable always — was broken by the commit that introduced it.

WHY FOUR REFERENCES CAUGHT NOTHING. Only one of them was an executable claim
that the name exists. A docstring cannot be wrong. An enum member is not a
reference to the class that uses it. Under `from __future__ import
annotations` every annotation is an unevaluated string. So the design was
spread across the module while the only load-bearing check — the import —
lived in a test, and was reached by RUNNING the thing that had stopped working.

THE TRANSFORM (Law 53). *"Does the suite collect?"* is answered by collecting,
takes minutes, and when the answer is no reports one line about one file.
*"Does every `from accountant_dad… import X` have an X?"* is a question about
text. Parse every module, collect what each binds in module scope, check every
import against that table. Milliseconds; every offender at once rather than the
first; and — the part collection can never do — it also sees a name that is
unresolved in a module no test imports yet.

SCOPE. First-party imports only. Whether `pydantic` exports `BaseModel` is
pydantic's promise and its own tests' business; whether `accountant_dad.
conformance` exports `Exclusion` is this repository's.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import NamedTuple

import first_party

#: Directories scanned for first-party imports, relative to the repo root.
#: `tools/evidence` is deliberately absent: it is a package rooted at `tools.`,
#: not at `accountant_dad.`, so none of its imports are first-party by the
#: definition this module uses.
SCANNED_DIRECTORIES = ("src", "tests", "tools/ci")

#: A floor, not the count — files are expected to be added. Its only job is to
#: fail when the walk finds nothing, because a scan over an empty list returns
#: `()` and passes. Measured on the tree this was written against: 111 files
#: across the three directories, holding 43 first-party modules.
FEWEST_FILES_THAT_CAN_BE_REAL = 80

_STAR = "*"


class Unresolved(NamedTuple):
    """One reference with nothing behind it."""

    file: str
    line: int
    module: str
    name: str
    reason: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} {self.module}.{self.name} — {self.reason}"


def unresolved(
    tree: ast.Module,
    filename: str,
    package: str,
    defined: Mapping[str, AbstractSet[str]],
    known: AbstractSet[str],
) -> tuple[Unresolved, ...]:
    """Every first-party import in `tree` that resolves to nothing.

    `defined` maps a module to the names it binds in module scope; `known` is
    every module that exists. A name resolves when it is a submodule, or when
    the module binds it — including by importing it, since a re-export is a
    real attribute.

    `import x.y` is checked too, but only that the MODULE exists: it binds no
    individual names, so there is no name to fail to find.
    """
    findings: list[Unresolved] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            findings.extend(_from_import(node, filename, package, defined, known))
        elif isinstance(node, ast.Import):
            findings.extend(_plain_import(node, filename, known))
    return tuple(findings)


def _from_import(
    node: ast.ImportFrom,
    filename: str,
    package: str,
    defined: Mapping[str, AbstractSet[str]],
    known: AbstractSet[str],
) -> list[Unresolved]:
    module = first_party.absolute_module(node, package)
    if module is None:
        return []

    if module not in known:
        return [
            Unresolved(
                filename,
                node.lineno,
                module,
                ", ".join(alias.name for alias in node.names),
                "no such module in the first-party package",
            )
        ]

    bound = defined.get(module, frozenset())
    return [
        Unresolved(
            filename,
            node.lineno,
            module,
            alias.name,
            "imported, but nothing in that module defines it at module scope",
        )
        for alias in node.names
        if alias.name != _STAR and alias.name not in bound and f"{module}.{alias.name}" not in known
    ]


def _plain_import(node: ast.Import, filename: str, known: AbstractSet[str]) -> list[Unresolved]:
    return [
        Unresolved(filename, node.lineno, alias.name, "", "no such module")
        for alias in node.names
        if first_party.is_first_party(alias.name) and alias.name not in known
    ]


def repository_symbol_table() -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """What every first-party module defines, and which modules exist."""
    files = first_party.module_files()
    defined = {
        dotted: first_party.defined_names(first_party.parse(path)) for dotted, path in files.items()
    }
    return defined, frozenset(files)


def scanned_files() -> tuple[Path, ...]:
    """Every file the scan reads, in a stable order."""
    root = first_party.repo_root()
    found: list[Path] = []
    for directory in SCANNED_DIRECTORIES:
        found.extend(sorted((root / directory).rglob("*.py")))
    return tuple(found)


def unresolved_first_party_imports() -> tuple[Unresolved, ...]:
    """Every unresolved first-party import in the repository."""
    defined, known = repository_symbol_table()
    root = first_party.repo_root()
    files = first_party.module_files()
    by_path = {path: dotted for dotted, path in files.items()}

    findings: list[Unresolved] = []
    for path in scanned_files():
        dotted = by_path.get(path)
        package = (
            first_party.containing_package(dotted, path)
            if dotted is not None
            else first_party.PACKAGE
        )
        tree = first_party.parse(path)
        findings.extend(unresolved(tree, str(path.relative_to(root)), package, defined, known))
    return tuple(findings)


def undefined_in_all(tree: ast.Module, filename: str, dotted: str) -> tuple[Unresolved, ...]:
    """Every `__all__` entry the module does not define.

    `__all__` is a promise about attributes: an entry with no definition is an
    `AttributeError` for `from x import *`, and a lie to every reader who takes
    the list as the module's public surface.
    """
    bound = first_party.defined_names(tree)
    findings: list[Unresolved] = []
    for node in first_party.module_scope_statements(tree.body):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            continue
        findings.extend(
            Unresolved(filename, node.lineno, dotted, exported, "exported, never defined")
            for exported in _string_elements(node.value)
            if exported not in bound
        )
    return tuple(findings)


def _string_elements(node: ast.expr) -> list[str]:
    """The string literals in an `__all__` list or tuple.

    Returns the VALUES rather than the nodes so the `str` narrowing survives:
    `ast.Constant.value` is typed as every literal type Python has, and a
    caller that took the node back would have to narrow it a second time.
    A computed `__all__` yields nothing, which is correct — there is no literal
    list of names to check against.
    """
    if not isinstance(node, ast.List | ast.Tuple):
        return []
    return [
        element.value
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]


def undefined_exports() -> tuple[Unresolved, ...]:
    """Every `__all__` entry in the first-party package with no definition."""
    root = first_party.repo_root()
    findings: list[Unresolved] = []
    for dotted, path in first_party.module_files().items():
        tree = first_party.parse(path)
        findings.extend(undefined_in_all(tree, str(path.relative_to(root)), dotted))
    return tuple(findings)
