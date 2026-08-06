"""What this repository imports from ITSELF, read off the authored tree.

WHY ONE MODULE OWNS THIS. Three separate defects — F-018, F-024 and F-025 —
are the same sentence with three different objects:

    F-024   a NAME is imported and nothing defines it
    F-025   a CALL is written and the callee's parameters have moved
    F-018   a MODULE is written and nothing imports it

Each is a reference that was never checked against the thing it refers to. All
three checks need the same three primitives — find the first-party modules,
parse them as authored, and resolve a dotted reference to a definition — so the
primitives live here once (Law 14) and the three validators own one question
each (§G4).

WHY STATIC AND NOT `import`. Answering these by importing would need `cv2`,
`numpy`, `pymupdf` and `pillow` resident, would execute module-scope code to
ask a question about text, and would report a module that fails to import as a
module with no symbols. Parsing answers the question that was actually asked.

WHY `authored_source` AND NOT `__file__`. Under `mutmut run` the tree is copied
to `mutants/` and every mutated module is rewritten: functions are renamed to
`x_<name>__mutmut_orig` and the public name is rebound to a generated
dispatcher taking `(*args, **kwargs)`. A signature read off that dispatcher
binds ANY call, so `signature_drift` would go silently hollow exactly where it
is most needed. Every read here goes through `tools/ci/authored_source.py`,
which is the repository's single answer to that class.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

from authored_source import authored_path

import accountant_dad

#: The one first-party import root. A dotted name starting with this is code
#: this repository wrote; anything else is a third-party or stdlib module whose
#: definitions are none of this module's business.
PACKAGE = "accountant_dad"

#: `__init__.py` names a package by its directory, not by the file.
_PACKAGE_MARKER = "__init__"


def package_root() -> Path:
    """The authored `src/accountant_dad` directory.

    Derived from the package's own module object rather than from
    `Path(__file__)`: `tools/ci` is on `sys.path` as a flat directory, so this
    file's location says nothing about where `src` is, and under mutation the
    two trees differ.
    """
    return authored_path(accountant_dad).parent


def repo_root() -> Path:
    """The authored repository root — the parent of `src`."""
    return package_root().parent.parent


def module_files() -> dict[str, Path]:
    """Every module in the first-party package, dotted name to authored path.

    `accountant_dad/engines/__init__.py` is keyed `accountant_dad.engines`, so
    a lookup can ask about a package and a module in the same breath — which is
    what `from accountant_dad.engines import input_engine` requires.
    """
    root = package_root()
    found: dict[str, Path] = {}
    for path in sorted(root.rglob("*.py")):
        parts = list(path.relative_to(root.parent).with_suffix("").parts)
        if parts[-1] == _PACKAGE_MARKER:
            parts.pop()
        found[".".join(parts)] = path
    return found


def is_package(path: Path) -> bool:
    """Whether an authored path is a package's `__init__.py`."""
    return path.stem == _PACKAGE_MARKER


def parse_text(text: str, filename: str) -> ast.Module:
    """Parse source text, naming the file it came from in any error.

    A `SyntaxError` is deliberately NOT caught. A module this repository cannot
    parse is a module this repository cannot import, which is the F-024 failure
    one step earlier, and swallowing it here would report "no symbols" for a
    file that is simply broken — then flag every name imported from it as
    missing, turning one true failure into a hundred false ones (Law 11).
    """
    return ast.parse(text, filename=filename)


def parse(path: Path) -> ast.Module:
    """Parse a file that is already known to be authored."""
    return parse_text(path.read_text(encoding="utf-8"), str(path))


def module_scope_statements(body: Iterable[ast.stmt]) -> Iterator[ast.stmt]:
    """Statements that execute in MODULE scope, `if`/`try` wrappers included.

    `if TYPE_CHECKING:` and `try: import x / except ImportError:` are the two
    ways this repository binds a top-level name conditionally, and both bind
    real module attributes. Function and class bodies do not, so they are never
    entered — counting a name bound inside a function would admit exactly the
    F-024 shape: a symbol discussed everywhere and defined nowhere an importer
    can reach.
    """
    for node in body:
        yield node
        if isinstance(node, ast.If):
            yield from module_scope_statements(node.body)
            yield from module_scope_statements(node.orelse)
        elif isinstance(node, ast.Try):
            yield from module_scope_statements(node.body)
            yield from module_scope_statements(node.orelse)
            yield from module_scope_statements(node.finalbody)
            for handler in node.handlers:
                yield from module_scope_statements(handler.body)


def defined_names(tree: ast.Module) -> frozenset[str]:
    """Every name a module binds in module scope, and so every name it exports."""
    names: set[str] = set()
    for node in module_scope_statements(tree.body):
        names |= _names_bound_by(node)
    return frozenset(names)


def _names_bound_by(node: ast.stmt) -> set[str]:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.Import | ast.ImportFrom):
        return {alias.asname or alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.Assign):
        return {target.id for target in node.targets if isinstance(target, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every top-level `def` in a module, by name.

    Top level only, and for the reason `authored_function_source` gives: an
    inner helper sharing a name with the function asked for would otherwise be
    returned in its place, and its parameters are not the ones being called.
    """
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def is_first_party(dotted: str | None) -> bool:
    """Whether a dotted module name belongs to this repository's package."""
    return dotted is not None and (dotted == PACKAGE or dotted.startswith(f"{PACKAGE}."))


def absolute_module(node: ast.ImportFrom, containing_package: str) -> str | None:
    """The absolute module an `ImportFrom` names, resolving relative levels.

    `containing_package` is the package the statement lives in — for
    `a/b/c.py` that is `a.b`, and for `a/b/__init__.py` it is `a.b`, because
    Python resolves `from . import x` against the PACKAGE either way.

    Returns `None` when the statement names nothing first-party, so a caller
    may skip it without knowing the rules. A relative import that climbs past
    the root also returns `None`: that import cannot resolve at runtime either,
    and inventing a plausible target would hide it.
    """
    if node.level == 0:
        return node.module if is_first_party(node.module) else None

    parts = containing_package.split(".")
    climb = node.level - 1
    if climb > len(parts):
        return None
    anchor = ".".join(parts[: len(parts) - climb])
    if not anchor:
        return None
    resolved = f"{anchor}.{node.module}" if node.module else anchor
    return resolved if is_first_party(resolved) else None


def containing_package(dotted: str, path: Path) -> str:
    """The package a module lives in — the anchor for its relative imports."""
    return dotted if is_package(path) else dotted.rpartition(".")[0]
