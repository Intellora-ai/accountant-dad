#!/usr/bin/env bash
#
# The library that gets IMPORTED must be the one the manifest PINNED.
#
# ── THE FAILURE THIS EXISTS TO MAKE IMPOSSIBLE ────────────────────────────
#
# Two distributions can install the same top-level module. When they do, pip
# reports success, records both, and `import` silently resolves to whichever
# one landed last. Nothing warns. Measured on this project, not imagined:
#
#     pip install numpy==2.5.1 opencv-python==5.0.0.93
#     pip install -r requirements-engine1-ocr.txt      # exit 0, no warning
#
#     importlib.metadata.version("opencv-python")  ->  '5.0.0.93'
#     cv2.__version__                              ->  '4.10.0'
#
# `opencv-contrib-python` arrives as a transitive dependency of paddlex, also
# provides `cv2`, and wins. A guard written against installed METADATA reports
# green while the pin is violated, because the metadata is telling the truth
# about what is installed and lying about nothing - it simply is not the
# question. The question is which module the interpreter actually loads.
#
# This is not hypothetical history either. Commit cab6c0a in this repository
# is titled "the pins said 5.0.0.93 and 2.5.1; the process had 4.10.0 and
# 2.3.5". It happened, it was found by hand, and nothing was added afterwards
# that would find it again.
#
# ── WHY IT MATTERS MORE HERE THAN IN AN ORDINARY PROJECT ──────────────────
#
# `cleaner`'s deskew residual - 0.0017 degrees at 32 degrees - is a MEASURED
# number and OpenCV is the thing that measured it. A number produced against
# 4.10.0 and then asserted in an environment claiming 5.0.0.93 still passes
# and no longer means what it says (CLAUDE.md Law 24). The test would stay
# green through the entire deception, which is precisely why the check has to
# be on the import and not on the assertion.
#
# ── WHAT IT CHECKS, IN ORDER OF STRENGTH ──────────────────────────────────
#
#   1. PROVENANCE.  Every top-level module a pinned distribution installs must
#      be provided by THAT distribution and no other. This needs no version
#      strings at all and catches the shadow exactly, by name.
#   2. VERSION.     Where the imported module exposes `__version__`, it must
#      agree with the pin. OpenCV reports `5.0.0` for a `5.0.0.93` pin, so
#      agreement means "the pin starts with what the module reports" - a rule
#      read off how these packages version themselves, not chosen.
#   3. PRESENCE.    Every pinned distribution must be installed. A manifest an
#      environment does not satisfy is not the manifest that environment ran.
#
# Import names are DERIVED from installed metadata, never from a table written
# here. A hand-written map of distribution to module is the same guess that
# produced the `paddlepaddle` versus `paddle` defect in F-009, and it rots the
# moment a package changes what it ships.
#
# ── USAGE ─────────────────────────────────────────────────────────────────
#
#     tools/ci/assert_imports_match_pins.sh <python> <manifest> [<manifest>...]
#
#     tools/ci/assert_imports_match_pins.sh python3 requirements-engine1.txt
#     tools/ci/assert_imports_match_pins.sh /tmp/ocr-venv/bin/python \
#         requirements-engine1-ocr.txt
#
# Exits non-zero and names every offender. Prints what it actually imported,
# so the log carries the truth even on a pass.

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: assert_imports_match_pins.sh <python> <manifest> [<manifest>...]" >&2
  exit 1
fi

PYTHON="$1"
shift

if [ ! -x "$PYTHON" ] && ! command -v "$PYTHON" > /dev/null 2>&1; then
  echo "BLOCKED - '${PYTHON}' is not an executable interpreter." >&2
  exit 1
fi

for manifest in "$@"; do
  if [ ! -f "$manifest" ]; then
    echo "BLOCKED - no manifest at '${manifest}'." >&2
    exit 1
  fi
done

"$PYTHON" - "$@" <<'PY'
import importlib
import importlib.metadata as metadata
import importlib.util
import pathlib
import re
import sys
import sysconfig

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;#]+)")

# ── what counts as a self-reported version ──────────────────────────────
#
# `__version__` is a CONVENTION, not a rule, and treating it as the rule left
# real pins verified by nothing. Measured on this repository: `pypdfium2` — an
# Engine 1 library that `parser.py` loads — exposes no `__version__` at all. It
# exposes `PYPDFIUM_INFO`. Every one of its four top-level modules therefore
# printed "(exposes no __version__)" and the run still ended in
# "every pinned distribution ... imports at its pin", having verified NOTHING
# about pypdfium2's version.
#
# The list is the same one `tests/unit/test_runtime_library_versions.py` already
# uses, so the two guards agree about what a version is instead of each having
# its own opinion (Law 19).
VERSION_ATTRIBUTES = ("__version__", "VERSION", "VersionBind", "PYPDFIUM_INFO", "version")

# Two or more dot-separated numbers at the START. Anchored so a module's repr
# can never match, which is what stops `numpy.version` (a SUBMODULE) and
# `pymupdf.version` (a TUPLE) being read as a version string.
NUMERIC_PREFIX = re.compile(r"\d+(?:\.\d+)+")

# ── where a module is allowed to come from ──────────────────────────────
#
# Every check in this file below asks the interpreter about a module it
# imported, and then trusts that the module came from the distribution pip
# recorded. Nothing verified that. A file named `cv2.py` earlier on `sys.path`
# than site-packages answers `import cv2`, and if it sets `__version__` to the
# pinned string it satisfies the version check, the provenance check and the
# metadata check simultaneously — every one of which is asking about the
# INSTALLED distribution while the interpreter is running something else.
#
# `PYTHONPATH` is set to `tools/ci:src` by five CI jobs, so this is not a
# theoretical path: anything dropped into those directories outranks every
# installed package.
SITE_DIRECTORIES = {
    pathlib.Path(sysconfig.get_paths()[key]).resolve() for key in ("purelib", "platlib")
}


def normalise(name: str) -> str:
    """PEP 503 normalisation. `opencv-python` and `opencv_python` are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def self_reported(module) -> str | None:
    """The version the module states about ITSELF, or None if it states none."""
    for attribute in VERSION_ATTRIBUTES:
        raw = getattr(module, attribute, None)
        if raw is None:
            continue
        match = NUMERIC_PREFIX.match(str(raw))
        if match is not None:
            return match.group()
    return None


def agrees(reported: str, pinned: str) -> bool:
    """Whether a self-reported version and a pin name the same release.

    PEP 440: everything after "+" is a LOCAL VERSION IDENTIFIER — the build
    variant, not the version. On a Linux runner `pip install torch==2.13.0`
    resolves to the CUDA wheel, which reports `2.13.0+cu130`. That IS 2.13.0.
    Comparing the raw strings called a correct environment wrong, and a guard
    that fires on a correct environment gets switched off — after which it
    catches nothing.

    Only the local segment is stripped. The shadow this file exists to catch is
    a PUBLIC version difference (`cv2.__version__` 4.10.0 against a 5.0.0.93
    pin), and that is still caught exactly.
    """
    public = reported.split("+", 1)[0]
    return pinned in (reported, public) or pinned.startswith(f"{public}.")


def outside_site_packages(module_name: str) -> str | None:
    """Where `module_name` resolves from, when that is NOT an installed location.

    Returns None when the module is where pip put it, or when it has no file at
    all (namespace packages, built-ins, frozen modules) — those cannot be a
    file-shadow and refusing them would fire on a correct environment.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin in (None, "built-in", "frozen"):
        return None
    origin = pathlib.Path(spec.origin).resolve()
    if any(root in origin.parents for root in SITE_DIRECTORIES):
        return None
    return str(origin)


def pins(manifest: pathlib.Path) -> list[tuple[str, str]]:
    found = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PIN.match(stripped)
        if match:
            found.append((match.group(1), match.group(2)))
    return found


# module name -> the distributions that provide it, straight from the installed
# metadata of the interpreter under inspection.
providers: dict[str, list[str]] = {}
for module, dists in metadata.packages_distributions().items():
    providers[module] = [normalise(d) for d in dists]

problems: list[str] = []
checked = 0
found_pins = 0

# Distributions for which at least one module SELF-REPORTED a version that
# agreed with the pin. A distribution absent from this set passed on metadata
# and provenance alone, which is exactly the evidence this file distrusts, so
# it is printed by name at the end rather than left invisible.
version_verified: set[str] = set()
version_silent: dict[str, list[str]] = {}


def inspect_module(module_name: str, raw_name: str, pinned: str, note: str = "") -> None:
    """Import one module and check everything that can be checked about it."""
    global checked
    checked += 1
    stray = outside_site_packages(module_name)
    if stray is not None:
        problems.append(
            f"module '{module_name}' resolves from {stray}, which is not an installed "
            f"location. '{raw_name}' is pinned at {pinned}, but `import {module_name}` "
            "loads that file instead - every version, metadata and provenance check "
            "below would be answered by the shadow rather than by the package."
        )
        return
    try:
        loaded = importlib.import_module(module_name)
    except Exception as failure:
        # A PRIVATE top-level name is not part of anyone's import surface.
        # `paddlepaddle` ships `_foo`, a C-extension artifact with no
        # `PyInit__foo`, which cannot be imported standalone and is never meant
        # to be - it blocked this guard on an environment that was correctly
        # built. Reported, not silently dropped, and the shadow defence is
        # untouched: a shadow is only reachable through a name somebody writes
        # in an `import` statement, and nobody writes `import _foo`.
        if module_name.startswith("_"):
            print(
                f"  {module_name:24} from {raw_name}  "
                f"(private, not an import surface: {type(failure).__name__})"
            )
            return
        problems.append(f"module '{module_name}' from '{raw_name}' will not import: {failure}")
        return

    reported = self_reported(loaded)
    if reported is None:
        version_silent.setdefault(normalise(raw_name), []).append(module_name)
        print(f"  {module_name:24} from {raw_name}=={pinned}  (reports no version){note}")
        return
    ok = agrees(reported, pinned)
    print(f"  {module_name:24} version={reported:12} pin={pinned:12} "
          f"{'ok' if ok else 'MISMATCH'}{note}")
    if ok:
        version_verified.add(normalise(raw_name))
    else:
        problems.append(
            f"module '{module_name}' reports {reported} while '{raw_name}' is pinned at "
            f"{pinned} - the assertion would pass against the wrong library"
        )

for argument in sys.argv[1:]:
    manifest = pathlib.Path(argument)
    print(f"── {manifest} ──")
    declared = pins(manifest)
    if not declared:
        # ZERO IS NOT A PASS. A manifest with no pins would sail through every
        # loop below and print the success line having verified nothing - the
        # same false green as a test suite that collects zero tests and exits 0.
        # Emptying a manifest is also the cheapest way to silence this check, so
        # it is refused rather than reported.
        problems.append(
            f"{manifest} declares no pins at all. A manifest that pins nothing "
            "cannot be checked, and a check that verified nothing is not a pass."
        )
    found_pins += len(declared)
    for raw_name, pinned in declared:
        name = normalise(raw_name)
        try:
            installed = metadata.version(raw_name)
        except metadata.PackageNotFoundError:
            problems.append(f"{raw_name}=={pinned} is pinned but NOT INSTALLED")
            continue
        if installed != pinned:
            problems.append(
                f"{raw_name} is pinned at {pinned} and {installed} is installed"
            )

        modules = sorted(m for m, d in providers.items() if name in d)
        if not modules:
            # A distribution that ships no importable top-level module is
            # USUALLY benign - a tool, a stub package - and nothing can shadow
            # what nothing imports. There is one shape that is not benign, and
            # it was found in this repository rather than imagined:
            #
            #     requirements-engine1.txt pins  docling==2.118.0
            #     the `docling` MODULE is provided by  docling-slim
            #     no manifest pins docling-slim at all
            #
            # The pin names a metapackage while a DIFFERENT distribution
            # supplies every line of code that actually runs. Reporting that as
            # "ships no top-level module" and moving on is the same blind spot
            # as trusting metadata over the import - one level further out.
            #
            # It is currently safe only because docling requires
            # `docling-slim[standard]==2.118.0` exactly. That is an upstream
            # decision, not a guarantee this repository holds, so it is CHECKED
            # against the imported module's own version rather than assumed.
            delegate = name.replace("-", "_")
            owners = providers.get(delegate)
            if not owners:
                print(f"  {raw_name}=={installed}  (ships no top-level module)")
                continue
            inspect_module(delegate, raw_name, pinned, note=f"  (delegated to {owners})")
            continue

        for module in modules:
            checked += 1
            owners = providers[module]
            if owners != [name]:
                others = [o for o in owners if o != name]
                problems.append(
                    f"module '{module}' is provided by {owners}; "
                    f"'{raw_name}' is pinned but {others} also install it, and "
                    "import order alone decides which one wins"
                )
                continue
            inspect_module(module, raw_name, pinned)

print()
print(f"pins declared             : {found_pins}")
print(f"top-level modules checked : {checked}")

# ── how many pins were verified by the LIBRARY and not by metadata ──────
#
# The whole premise of this file is that metadata can be correct while the
# import is wrong, so a pin whose agreement rests only on metadata is a pin this
# file has not actually done its job on. That number used to be invisible: the
# run printed "(exposes no __version__)" per module and then declared success.
#
# It is REPORTED rather than REFUSED, and the difference is deliberate. Measured
# on requirements-ci.txt + requirements-engine1.txt, four pinned distributions
# self-report nothing through any known attribute: mypy, pytest-randomly, ruff
# and types-PyYAML. ruff's wheel ships a binary and a shim; types-PyYAML ships
# stub files and no runtime module at all. There is no version for them to
# report, so refusing them would fail a correct environment — and a guard that
# does that gets switched off, after which it catches nothing.
#
# What IS refused: a pin with no runtime evidence AND no metadata evidence, and
# any pin whose library disagrees. Both are handled above.
silent_distributions = sorted(set(version_silent) - version_verified)
print(f"pins verified by the library's own version : {len(version_verified)}")
if silent_distributions:
    print(f"pins resting on metadata alone            : {len(silent_distributions)}")
    for distribution in silent_distributions:
        print(f"    {distribution:24} modules={version_silent[distribution]}")

if found_pins and not checked:
    # Every pin resolved to a distribution that imports nothing. Possible in
    # principle for a manifest of pure tooling, but it means this run proved
    # nothing about any imported library, and saying so is the honest outcome.
    problems.append(
        "no top-level module was checked. Every pin resolved to a distribution "
        "that imports nothing, so nothing about any imported library was proved."
    )
if problems:
    print("BLOCKED - the imported libraries are not the pinned ones.")
    for problem in problems:
        print(f"  {problem}")
    sys.exit(1)
print("every pinned distribution is installed, unshadowed, and imports at its pin")
PY
