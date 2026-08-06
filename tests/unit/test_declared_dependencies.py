"""What the wheel DECLARES must cover what the code IMPORTS. (F-020)

`pyproject.toml` declared only `pydantic` while `cleaner.py` imported `cv2`,
`reader.py` imported `numpy`, `PIL` and `pymupdf`, and `pipeline.py` imported
`pymupdf` — all at module scope. Measured on a stdlib-only interpreter with the
declared list installed and nothing else::

    OK    accountant_dad
    FAIL  accountant_dad.engines.input_engine.cleaner  -> No module named 'cv2'
    FAIL  accountant_dad.engines.input_engine.reader   -> No module named 'numpy'
    FAIL  accountant_dad.engines.input_engine.pipeline -> No module named 'pymupdf'

`pip install accountant-dad` therefore shipped an Engine 1 that cannot be
imported. Law 18: never introduce hidden dependencies.

WHY NO GATE SAW IT. `quality.yml:47` installs the wheel into a fresh venv and
runs `import accountant_dad` — the TOP-LEVEL package, which has no heavy
imports. The gate was green on an artifact that was broken for everyone who
installed it the declared way. The same class of defect already cost this
repository once, when `reader.py` resolved PaddleOCR at module scope and every
gate died at collection; that one was loud because it broke everything, and this
one was quiet because it broke only on install.

WHY THIS TEST IS STRUCTURAL AND NOT A LIST. A test that hardcoded today's answer
(`{"pydantic", "numpy", "opencv-python", "pillow", "pymupdf"}`) would be a
SECOND source of truth for the dependency set, and the two would drift the first
time a sub-engine grew an import — which is precisely how the defect arose. Both
sides are derived instead: the needed set by walking the package's own AST, the
declared set by reading `[project].dependencies`. Adding an import to a module
is then the only edit required, and forgetting to declare it fails here by name.

IMPORT NAME IS NOT DISTRIBUTION NAME. `cv2` ships in `opencv-python` and `PIL`
in `pillow`. That mapping is a fact about the installed environment, not about
this repository, so it is read from `importlib.metadata.packages_distributions()`
rather than written down. A name that cannot be mapped fails loudly here rather
than being skipped — an unmappable import is either a missing install or a
dependency nobody declared, and both must stop the gate.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib
from importlib.metadata import packages_distributions

REPO = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = REPO / "src" / "accountant_dad"
PYPROJECT = REPO / "pyproject.toml"

#: The distribution this repository IS. It is never one of its own dependencies.
SELF = "accountant-dad"

#: The import name every module in this package uses to reach its own siblings.
FIRST_PARTY = "accountant_dad"


def canonical(name: str) -> str:
    """PEP 503 normalisation. `opencv_python`, `OpenCV-Python` and
    `opencv-python` are one distribution and must compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


# ── reading what the package DECLARES ─────────────────────────────────────


def declared_specifiers() -> list[str]:
    """`[project].dependencies`, verbatim, shape-checked on the way in.

    `tomllib` returns `object`, so every subscript is an error under
    `disallow_any_explicit`. Narrowing at each hop keeps the type honest and
    costs NO `# type: ignore` — this repository counts suppressions and blocks
    on any increase, so a guard that needed one would break another gate.
    """
    with PYPROJECT.open("rb") as handle:
        node: object = tomllib.load(handle)
    for key in ("project", "dependencies"):
        assert isinstance(node, dict), f"pyproject.toml: {key} is not inside a table"
        assert key in node, f"pyproject.toml has no [project] {key}"
        node = node[key]
    assert isinstance(node, list), "[project].dependencies is not a list"
    return [str(item) for item in node]


def distribution_of(specifier: str) -> str:
    """`"opencv-python==5.0.0.93"` -> `"opencv-python"`, canonicalised."""
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", specifier)
    assert match is not None, f"cannot read a distribution name out of {specifier!r}"
    return canonical(match.group(1))


def declared_distributions() -> set[str]:
    return {distribution_of(item) for item in declared_specifiers()}


# ── reading what the package IMPORTS ──────────────────────────────────────


def module_scope_imports(tree: ast.Module) -> set[str]:
    """Top-level package names imported when the MODULE IS IMPORTED.

    Module scope is not the same as "a direct child of `Module.body`". A module
    level `if`, `try`, `else` or `except` body executes at import time too, so a
    walker that only read `tree.body` would miss::

        try:
            import cv2
        except ImportError:
            import cv2_stub as cv2

    and would hand back a green gate on the exact shape that hides a dependency.
    Function and class bodies are deliberately NOT followed: an import in there
    runs when the function is CALLED, which is how `parser.require_module` and
    `reader`'s PaddleOCR lookup deliberately keep ~2 GB of ML wheels out of the
    install closure.
    """
    found: set[str] = set()

    def record(node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif node.level == 0 and node.module:
            found.add(node.module.split(".")[0])

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                record(node)
            elif isinstance(node, ast.If):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.Try):
                walk(node.body)
                walk(node.orelse)
                walk(node.finalbody)
                for handler in node.handlers:
                    walk(handler.body)

    walk(tree.body)
    return found


def deferred_imports(tree: ast.Module) -> set[str]:
    """Top-level package names imported inside a function or class body only."""
    inside: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            inside.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            inside.add(node.module.split(".")[0])
    return inside - module_scope_imports(tree)


def third_party(names: set[str]) -> set[str]:
    return {name for name in names if name not in sys.stdlib_module_names and name != FIRST_PARTY}


def package_sources() -> list[pathlib.Path]:
    sources = sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)
    assert sources != [], (
        f"no modules found under {PACKAGE}. This guard derives BOTH sides from "
        "the tree; reading an empty tree would pass while proving nothing."
    )
    return sources


def imports_by_kind() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Every third-party import in the package, split by when it executes."""
    at_import: dict[str, list[str]] = {}
    when_called: dict[str, list[str]] = {}
    for path in package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = path.relative_to(REPO).as_posix()
        for name in third_party(module_scope_imports(tree)):
            at_import.setdefault(name, []).append(where)
        for name in third_party(deferred_imports(tree)):
            when_called.setdefault(name, []).append(where)
    return at_import, when_called


def distributions_providing(import_name: str) -> set[str]:
    """Which installed distribution ships this top-level import name."""
    providers = packages_distributions().get(import_name, [])
    assert providers != [], (
        f"cannot tell which distribution provides `import {import_name}`. Either "
        f"it is not installed in this environment, or nothing declares it. Both "
        "are failures: an import this package cannot resolve is a broken install."
    )
    return {canonical(name) for name in providers}


# ── the guard ─────────────────────────────────────────────────────────────


def test_every_module_scope_import_is_a_declared_dependency() -> None:
    """F-020's permanent regression test. `pip install` must be enough to import.

    Fails naming the module, the import and the file, because "a dependency is
    missing" is not actionable and "cleaner.py imports cv2, which nothing
    declares" is.
    """
    declared = declared_distributions()
    at_import, _ = imports_by_kind()

    undeclared = sorted(
        f"`import {name}` at {', '.join(sorted(sites))} needs one of "
        f"{sorted(distributions_providing(name))}"
        for name, sites in at_import.items()
        if not distributions_providing(name) & declared
    )
    assert undeclared == [], (
        "module-scope import(s) that `pyproject.toml` does not declare:\n  "
        + "\n  ".join(undeclared)
        + f"\nDeclared: {sorted(declared)}. A module that imports something the "
        "wheel does not require is unimportable from a correct install, and no "
        "gate that imports only the top-level package can see it."
    )


def test_every_declared_dependency_is_imported_at_module_scope() -> None:
    """The other direction, and the reason the test above cannot be gamed.

    The cheapest way to pass the guard above is to declare everything. This
    makes the dependency list cost something: a distribution nothing imports at
    import time is weight in every install and a licence and CVE surface nobody
    asked for.
    """
    at_import, _ = imports_by_kind()
    needed: set[str] = set()
    for name in at_import:
        needed |= distributions_providing(name)

    unused = sorted(name for name in declared_distributions() if name not in needed)
    assert unused == [], (
        f"declared but never imported at module scope: {unused}. Deferred tools "
        "belong in a requirements file, not in the install closure — that is why "
        "`docling`, `torch` and `paddleocr` are reached through "
        "`require_module()` and are not declared here."
    )


def test_no_declared_dependency_floats() -> None:
    """Every pin is `==`. An unpinned runtime dependency makes the same commit
    validate differently on two runs, which is the reason the original single
    entry carried an exact version in the first place."""
    floating = sorted(item for item in declared_specifiers() if not re.search(r"==\s*[0-9]", item))
    assert floating == [], (
        f"dependency specifier(s) without an exact `==` pin: {floating}. "
        "Pin it to the version the gates were proven against."
    )


def test_the_deferred_tools_stay_out_of_the_install_closure() -> None:
    """`docling`, `torch`, `transformers`, `pypdfium2` and `paddleocr` are
    reached from inside a function on purpose (`reader.py:396`): the dependency
    is needed to RUN OCR, never to IMPORT the module that offers it. Declaring
    one here would put gigabytes of ML wheels behind `import accountant_dad` and
    reintroduce, as a slow install, the collection failure that deferring them
    fixed. This makes any future move visible instead of accidental.
    """
    declared = declared_distributions()
    _, when_called = imports_by_kind()

    promoted = sorted(name for name in when_called if distributions_providing(name) & declared)
    assert promoted == [], (
        f"deferred import(s) now also declared as install-time requirements: "
        f"{promoted}. Either the import moved to module scope — in which case "
        "say so here — or the declaration is unnecessary weight."
    )


# ── the walker itself must not be hollow ──────────────────────────────────


def test_the_walker_sees_module_scope_imports_that_are_not_top_level_statements() -> None:
    """A guard is only as good as its detector, so the detector is tested too.

    Every shape below runs at IMPORT time, and a walker that read only
    `tree.body` would miss all four — handing back a green gate on exactly the
    construction someone would reach for to hide a dependency. Built from a
    source STRING, never a file: this repository's freeze forbids planting a
    sample module in the tree, and an in-memory source needs no cleanup that
    could be forgotten.
    """
    source = """
import top_level
if CONDITION:
    import inside_if
else:
    import inside_else
try:
    import inside_try
except ImportError:
    import inside_except
finally:
    import inside_finally

def f():
    import inside_a_function

class C:
    import inside_a_class
"""
    tree = ast.parse(source)
    assert module_scope_imports(tree) == {
        "top_level",
        "inside_if",
        "inside_else",
        "inside_try",
        "inside_except",
        "inside_finally",
    }
    assert deferred_imports(tree) == {"inside_a_function", "inside_a_class"}


def test_the_walker_reads_from_imports_and_dotted_names_down_to_the_distribution() -> None:
    """`import numpy.typing` and `from PIL import Image` both name a
    DISTRIBUTION by their first segment. A walker that kept `numpy.typing`
    whole, or that ignored `from` imports, would fail to match anything
    declared and would then have to be "fixed" by loosening the assertion.

    Relative imports are excluded on purpose: `from . import x` is first-party
    by construction and can never name a distribution.
    """
    tree = ast.parse("import numpy.typing\nfrom PIL import Image\nfrom . import sibling\n")
    assert module_scope_imports(tree) == {"numpy", "PIL"}


def test_the_first_party_package_is_never_treated_as_a_dependency() -> None:
    """`accountant_dad` importing itself must not demand that `accountant-dad`
    appear in its own `[project].dependencies` — a self-referential requirement
    pip cannot satisfy."""
    tree = ast.parse("import accountant_dad.identity\nimport os\nimport numpy\n")
    assert third_party(module_scope_imports(tree)) == {"numpy"}
    assert SELF not in declared_distributions()
