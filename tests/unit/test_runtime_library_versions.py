"""A pin can be violated while every check in this repository reports green.

THE MEASURED DEFECT, not a hypothetical one. `opencv-python` and
`opencv-contrib-python` both provide the top-level module `cv2`. Installing the
second beside the first overwrites the first's files in place — exit 0, no
error, no warning — and the metadata of BOTH distributions survives intact. So:

    importlib.metadata.version("opencv-python")  ->  the PINNED version
    cv2.__version__                              ->  the version that WON

A guard written against package metadata sees nothing wrong. `requirements-
engine1.txt` records that exactly this happened here, and that the same install
also silently replaced numpy. Before this file existed, nothing in `tests/`,
`src/` or `tools/` asserted `cv2.__version__` at all, while `cleaner.py` uses
cv2 throughout.

WHY THIS IS NOT TIDINESS. `ROADMAP.md` records a measured deskew residual of
0.0017 at 32 degrees. cv2 measured it. Without this file, nothing in the
repository can say WHICH cv2 — the pinned 5.x or a 4.x that a transitive
dependency of an OCR package quietly substituted. That does not disprove the
number; it makes it UNVERIFIABLE, which under Law 52 is the same as not having
it. An assertion guarding a different library than the one its number was
derived from still passes and no longer means what it says.

FOUR PROPERTIES THAT KEEP THIS FROM BECOMING THE PROBLEM IT GUARDS AGAINST.

  THE PIN IS READ, NEVER WRITTEN. Every expected version below is parsed from
  the requirements files at test time. A version literal in this file would be
  a SECOND source of truth that drifts from the manifest — the same defect one
  level up. `test_this_file_hardcodes_no_version` reads this file's own source
  and fails if any pin under test appears in it.

  THE LIBRARY LIST IS DERIVED, NEVER GUESSED. The modules checked are found by
  parsing every file under `src/` — both `import x` statements and the string
  literals handed to `importlib.import_module` / `parser.require_module`, which
  is how docling, pypdfium2, torch, transformers and paddleocr are actually
  loaded. A library added to Engine 1 tomorrow is covered without editing this
  file.

  THE VERSION IS THE ONE THE LIBRARY REPORTS ABOUT ITSELF. Not metadata.
  `__version__` is not universal — `pypdfium2` has none and exposes
  `PYPDFIUM_INFO` instead — so the attribute is searched for, and a module that
  reports no version at all fails loudly rather than passing quietly.

  ABSENCE IS NOT A MISMATCH, AND IS NOT A SKIP. PaddleOCR cannot be installed
  beside these pins (`requirements-engine1.txt`, KNOWN_FAILURES F-002/F-009), so
  it is deliberately absent. A library that is not installed has no runtime
  version to disagree with anything; it is partitioned into a named ABSENT set
  that `test_every_pinned_import_is_either_checked_or_named_absent` requires to
  be accounted for. This file carries no skip marker of any kind — a skip would
  hide the same fact behind a marker, and the ratchet counts those.

  THE SENTENCE ABOVE IS WORDED THE WAY IT IS ON PURPOSE. The skip ratchet in
  `testing.yml` greps every file under `tests/` for the literal marker text,
  without parsing Python. So spelling the marker out here — even inside a
  docstring boasting that we avoid it — INCREASES THE COUNT and fails the gate.
  That cost a CI run, and it is the second time this class has bitten: the
  suppression budget in `quality.yml` counts prose the same way, and a
  docstring in `test_declared_dependencies.py` tripped it for the same reason.

  Both gates are text-based on purpose. Teaching them to parse Python would let
  the very thing they guard be smuggled past in a string, an f-string or a
  generated file. The bluntness is the feature; the prose is what moves.
"""

from __future__ import annotations

import ast
import importlib
import importlib.metadata
import importlib.util
import pathlib
import re
import sys
from types import ModuleType

import pytest

# ── where the repository is ─────────────────────────────────────────────
#
# Found by walking UP from this file rather than by counting `parents[n]`.
# Under mutation testing mutmut runs the suite from a `mutants/` copy of the
# tree, and `pyproject.toml`'s `also_copy` does not carry the Engine 1
# manifests — a fixed depth would resolve to a path that does not exist there
# and fail for a reason that has nothing to do with a mutant.

#: The file that marks the repository root. Chosen because it is the manifest
#: that exists in every configuration of this repository.
ROOT_MARKER = "requirements-ci.txt"


def _repository_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ROOT_MARKER).is_file():
            return candidate
    raise AssertionError(
        f"no ancestor of {here} carries {ROOT_MARKER!r}; the repository root cannot be located, "
        "so no pin can be read and this guard must not pretend to have checked anything"
    )


REPO = _repository_root()
SOURCE_TREE = REPO / "src"

# ── the pins, read from the manifests ───────────────────────────────────

#: `name==version`, ignoring comments, blanks and anything that is not an
#: exact pin. Only `==` is accepted: a range is not a pin and cannot be
#: checked against a single runtime version.
_PIN = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*==\s*([A-Za-z0-9._+!-]+)\s*$")


def _canonical(name: str) -> str:
    """PEP 503 normalisation, so `PyMuPDF`, `pymupdf` and `py_mu_pdf` are one
    name and a manifest's capitalisation cannot create a second entry."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins() -> dict[str, str]:
    found: dict[str, str] = {}
    files = sorted(REPO.glob("requirements*.txt"))
    if not files:
        raise AssertionError(f"no requirements*.txt under {REPO}; there is nothing to check")
    for manifest in files:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            match = _PIN.match(line)
            if match is not None:
                found[_canonical(match.group(1))] = match.group(2)
    return found


PINS = _pins()

# ── the libraries, derived from the code's actual imports ───────────────

#: Names handed a module string at runtime rather than imported by statement.
#: `parser.require_module` is this repository's own wrapper around the first.
_DYNAMIC_IMPORTERS = frozenset({"import_module", "require_module"})


def _dynamic_target(node: ast.Call) -> str | None:
    """The module name a dynamic-import call names, when it is a literal."""
    function = node.func
    name = (
        function.attr
        if isinstance(function, ast.Attribute)
        else function.id
        if isinstance(function, ast.Name)
        else None
    )
    if name not in _DYNAMIC_IMPORTERS or not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def _roots_in(source: str, filename: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source, filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            target = _dynamic_target(node)
            if target is not None:
                roots.add(target.split(".")[0])
    return roots


def _third_party_import_roots() -> frozenset[str]:
    """Every non-stdlib, non-first-party top-level module `src/` reaches for."""
    first_party = {entry.name for entry in SOURCE_TREE.iterdir() if entry.is_dir()}
    if not first_party:
        raise AssertionError(f"{SOURCE_TREE} holds no package; the import scan would find nothing")
    roots: set[str] = set()
    for module in sorted(SOURCE_TREE.rglob("*.py")):
        roots |= _roots_in(module.read_text(encoding="utf-8"), str(module))
    return frozenset(roots - set(sys.stdlib_module_names) - first_party - {"__future__"})


IMPORT_ROOTS = _third_party_import_roots()

#: The two libraries whose runtime version this guard exists for. Named as an
#: ANTI-HOLLOW ANCHOR, not as the list under test: if the AST scan above ever
#: silently returns nothing, every other assertion here would pass over an
#: empty set. `cleaner.py` uses cv2 throughout and numpy is what it hands cv2,
#: so their absence from a derived list means the derivation is broken.
MUST_BE_DERIVED = frozenset({"cv2", "numpy"})


def _providers(root: str) -> frozenset[str]:
    """Every installed distribution that could be providing `root`.

    `packages_distributions()` answers this from the installed metadata, which
    is how a name provided by TWO distributions becomes visible at all. The
    import root itself is added as a candidate because a distribution whose
    name equals its module (numpy, torch, pymupdf) is the common case, and
    because a distribution that ships no top-level record — `docling` here —
    would otherwise disappear.
    """
    mapped = importlib.metadata.packages_distributions().get(root, [])
    return frozenset(_canonical(name) for name in [*mapped, root])


def _pinned_imports() -> dict[str, str]:
    """Import root -> the pinned version of the distribution behind it.

    When two pinned distributions claim one import name at two DIFFERENT
    versions, both are recorded, joined. Nothing can agree with the joined
    string, so the disagreement is reported by name instead of one of the two
    pins being picked arbitrarily and the other forgotten.
    """
    pinned: dict[str, str] = {}
    for root in sorted(IMPORT_ROOTS):
        versions = sorted({PINS[distribution] for distribution in _providers(root) & set(PINS)})
        if versions:
            pinned[root] = " and ".join(versions)
    return pinned


PINNED_IMPORTS = _pinned_imports()


def _is_importable(root: str) -> bool:
    """Whether `root` can be imported at all, asked without importing it."""
    try:
        return importlib.util.find_spec(root) is not None
    except (ImportError, ValueError):
        return False


PRESENT = frozenset(root for root in PINNED_IMPORTS if _is_importable(root))
ABSENT = frozenset(PINNED_IMPORTS) - PRESENT

# ── what a library says about itself ────────────────────────────────────

#: Searched in order. `__version__` is the convention, not the rule:
#: `pypdfium2` exposes `PYPDFIUM_INFO` and nothing else, `pydantic` also
#: carries `VERSION`, and `pymupdf` also carries `VersionBind`. A name is only
#: accepted when its value actually LOOKS like a version, which is what stops
#: `numpy.version` (a submodule) and `pymupdf.version` (a tuple) being read as
#: one.
VERSION_ATTRIBUTES = (
    "__version__",
    "VERSION",
    "VersionBind",
    "PYPDFIUM_INFO",
    "version",
)

#: Two or more dot-separated numbers at the START of the string. Anchored at
#: the start so a module's repr can never match; a trailing local segment
#: (torch's `+cpu` on a CPU wheel) is a build variant of the same release and
#: is allowed to follow.
_NUMERIC_PREFIX = re.compile(r"\d+(?:\.\d+)+")

#: How many leading components must agree. Three, because a release is
#: major.minor.patch — `opencv-python` pins a FOURTH, packaging-only component
#: that cv2 itself never reports, so requiring full string equality would fail
#: on a correct install. This is a structural fact about how those two strings
#: are shaped, not a tolerance anyone chose, and
#: `test_the_comparison_rejects_a_version_that_is_not_the_pinned_release`
#: proves a change in any of the three is still rejected.
COMPONENTS_REQUIRED = 3


def reported_version(module: ModuleType) -> str:
    """The version the module states about ITSELF, or a loud failure."""
    for attribute in VERSION_ATTRIBUTES:
        raw = getattr(module, attribute, None)
        if raw is None:
            continue
        match = _NUMERIC_PREFIX.match(str(raw))
        if match is not None:
            return match.group()
    raise AssertionError(
        f"{module.__name__} reports no version through any of {VERSION_ATTRIBUTES}. "
        "Its pin therefore cannot be verified at runtime, and an unverifiable pin "
        "is the exact hole this file exists to close - refused rather than skipped."
    )


def agrees(runtime: str, pin: str) -> bool:
    """Whether a runtime-reported version and a pinned one are the same release."""
    reported = runtime.split(".")
    pinned = pin.split(".")
    shared = min(len(reported), len(pinned))
    return shared >= COMPONENTS_REQUIRED and reported[:shared] == pinned[:shared]


# ── the guard ───────────────────────────────────────────────────────────


def test_the_import_scan_actually_found_the_libraries_engine_1_runs_on() -> None:
    """Anti-hollow. Every assertion below quantifies over a DERIVED set; if the
    derivation broke, they would all pass over nothing."""
    assert MUST_BE_DERIVED <= IMPORT_ROOTS, (
        f"the import scan of {SOURCE_TREE} missed {sorted(MUST_BE_DERIVED - IMPORT_ROOTS)}; "
        "it is not reading the real code and every check here is vacuous"
    )
    assert PINNED_IMPORTS, "no imported library matched any pin; nothing is being checked"


def test_every_present_pinned_library_reports_the_version_it_is_pinned_to() -> None:
    """The whole point. Runtime-reported, never metadata — metadata is exactly
    what stayed correct while the wrong library was the one imported."""
    disagreements: list[str] = []
    for root in sorted(PRESENT):
        module = importlib.import_module(root)
        runtime = reported_version(module)
        pin = PINNED_IMPORTS[root]
        if not agrees(runtime, pin):
            disagreements.append(f"{root}: reports {runtime}, pinned {pin} ({module.__file__})")
    assert not disagreements, "runtime libraries disagree with the manifests:\n" + "\n".join(
        disagreements
    )


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def test_opencv_python_and_opencv_contrib_python_are_not_both_installed() -> None:
    """The exact condition that produced the mismatch. Both ship `cv2`, install
    order decides which wins, and both sets of metadata survive."""
    rivals = ("opencv-python", "opencv-contrib-python")
    installed = [
        f"{name}=={_distribution_version(name)}"
        for name in rivals
        if _distribution_version(name) is not None
    ]
    assert len(installed) < len(rivals), (
        f"both cv2 providers are installed: {installed}. They overwrite each other's "
        "files, package metadata keeps reporting BOTH versions, and `import cv2` "
        "silently returns whichever was installed last."
    )


def test_no_checked_import_name_is_provided_by_two_installed_distributions() -> None:
    """The general class the opencv case is one instance of (§J.9).

    Two distributions claiming one import name is shadowing, whichever
    libraries they are — the loser's files are gone and only its metadata
    remains to mislead the next reader.
    """
    mapping = importlib.metadata.packages_distributions()
    shared = {
        root: sorted(mapping[root]) for root in sorted(PRESENT) if len(mapping.get(root, [])) > 1
    }
    assert not shared, (
        f"an import name is claimed by more than one installed distribution: {shared}. "
        "Whichever was installed last is the one that answers `import`."
    )


def test_every_pinned_import_is_either_checked_or_named_absent() -> None:
    """No third, silent category.

    A library that is not installed has no runtime version and is not a
    mismatch — but it must be VISIBLE as absent rather than quietly dropped,
    which is what a skip marker would do while the skip ratchet counted it.
    """
    assert frozenset(PINNED_IMPORTS) == PRESENT | ABSENT
    assert not (PRESENT & ABSENT)
    for root in sorted(ABSENT):
        assert importlib.util.find_spec(root) is None, (
            f"{root} was partitioned as absent but is importable; the partition is wrong"
        )


# ── proving the guard can fail ──────────────────────────────────────────


def test_the_comparison_rejects_a_version_that_is_not_the_pinned_release() -> None:
    """RED PROOF, in process. The wrong versions here are DERIVED from the real
    pins by changing them, so this test carries no version literal of its own
    and cannot drift from the manifest."""
    pin = PINNED_IMPORTS["cv2"]
    components = pin.split(".")
    assert len(components) > COMPONENTS_REQUIRED, (
        f"opencv's pin {pin} no longer carries the fourth, packaging-only component "
        "this test is built on; re-derive the examples below from what it does carry"
    )
    bumped_major = ".".join([str(int(components[0]) + 1), *components[1:]])
    bumped_patch = ".".join([*components[:2], str(int(components[2]) + 1), *components[3:]])

    assert agrees(pin, pin)
    assert agrees(".".join(components[:COMPONENTS_REQUIRED]), pin), (
        "cv2 reports three components where the manifest pins four; a correct "
        "install must not be reported as a mismatch"
    )
    assert not agrees(bumped_major, pin)
    assert not agrees(bumped_patch, pin)
    assert not agrees(".".join(components[: COMPONENTS_REQUIRED - 1]), pin), (
        "a version too short to identify a release must not be accepted"
    )


def test_a_module_that_reports_no_version_fails_loudly_rather_than_passing() -> None:
    """The other way this guard could go hollow: a library with no version
    attribute silently contributing nothing."""
    silent = ModuleType("silent_library")
    #: `numpy.version` is a SUBMODULE and `pymupdf.version` is a TUPLE. Both
    #: are named in `VERSION_ATTRIBUTES`; neither may be read as a version.
    module_shaped = ModuleType("misleading_library")
    module_shaped.__dict__["version"] = ModuleType("misleading_library.version")
    tuple_shaped = ModuleType("tuple_library")
    tuple_shaped.__dict__["version"] = ("1", "2", "3")

    for module in (silent, module_shaped, tuple_shaped):
        with pytest.raises(AssertionError, match="reports no version"):
            reported_version(module)


def test_a_real_installed_library_still_reports_a_usable_version() -> None:
    """The inverse of the test above: the resolver must not reject everything.
    A resolver that always raised would make the mismatch test vacuous, and one
    that returned a truncated value would make `agrees` decide on too little.
    """
    assert PRESENT, "no pinned library is installed; the resolver is never exercised"
    for root in sorted(PRESENT):
        runtime = reported_version(importlib.import_module(root))
        assert len(runtime.split(".")) >= COMPONENTS_REQUIRED, (
            f"{root} resolved to {runtime!r}, too few components to identify a release"
        )


def test_this_file_hardcodes_no_version() -> None:
    """The manifest stays the one source of truth.

    A version literal pasted in here would pass forever after the manifest
    moved on — the same class of defect as metadata reporting a version the
    import does not have.
    """
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    pasted = sorted({pin for pin in PINNED_IMPORTS.values() if pin in source})
    assert not pasted, (
        f"these pinned versions are written into this test file: {pasted}. "
        "Read them from the requirements manifest instead."
    )
