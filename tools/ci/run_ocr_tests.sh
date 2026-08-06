#!/usr/bin/env bash
#
# Engine 1's OCR path, run in an interpreter that CANNOT contain the pins it
# conflicts with.
#
# ── THE PROBLEM THIS SOLVES, AND THE ONE IT DOES NOT ──────────────────────
#
# KNOWN_FAILURES.md F-009 records that PaddleOCR is absent on CI, so eleven of
# `reader`'s tests skip and the OCR path — the path every photographed invoice
# takes — has never executed where proof lives (CLAUDE.md Law 44).
#
# The recorded cause is a package conflict, and it is real. Re-measured on
# Linux resolution rules, not recalled:
#
#     Because paddlex>=3.7.0 depends on numpy>=1.24,<2.4 and paddleocr>=3.7.0
#     depends on paddlex[ocr-core]>=3.7.0, we can conclude that
#     paddleocr>=3.7.0 depends on numpy>=1.24,<2.4.
#     And because you require numpy==2.5.1 and paddleocr==3.7.0, we can
#     conclude that your requirements are unsatisfiable.
#
#         uv pip compile --python-platform x86_64-unknown-linux-gnu
#                        --python-version 3.12
#                        requirements-engine1.txt + requirements-engine1-ocr.txt
#
# pip agrees, in its own words, on the same platform:
#
#     ERROR: Cannot install numpy==2.5.1 and paddlex because these package
#     versions have conflicting dependencies.
#     paddlex 3.7.2 depends on numpy<2.4 and >=1.24
#     ERROR: ResolutionImpossible
#
# ── WHY THE PACKAGE CONFLICT IS NOT THE ROOT CAUSE ────────────────────────
#
# The conflict only bites because CI has ONE interpreter per job and the test
# suite is run as ONE unit, so the union of every test module's dependencies
# has to be satisfiable in a single site-packages. That assumption is what
# makes two disjoint requirements collide:
#
#     cleaner  needs opencv-python 5.0.0.93 + numpy 2.5.1   (its deskew
#              residual was measured against exactly those)
#     reader   needs pymupdf + pillow + paddleocr, and imports NO cv2 at all
#
# `reader.py`'s import list is pinned by a test: pymupdf, numpy, PIL, and
# PaddleOCR through `importlib`. OpenCV is not on it. The two sets never
# actually needed to share an environment; only the runner did.
#
# So the transform (CLAUDE.md Law 53) is to stop solving "make PaddleOCR
# coexist with numpy 2.5.1" — which needs either an upstream release or the
# unpinning of a number that carries a measurement — and instead solve "give
# the OCR tests an interpreter that never contains the pins they do not use".
# Same outcome. No pin changes. No measurement invalidated.
#
# ── THE SECOND DEFECT, WHICH THE ENVIRONMENT FIX ALONE DOES NOT REACH ─────
#
# `tests/unit/test_input_engine_reader.py` guards those eleven tests with
#
#     for name in ("paddleocr", "paddlepaddle") if find_spec(name) is None
#
# `paddlepaddle` is a DISTRIBUTION name. Its importable top-level module is
# `paddle` — read from the installed metadata, not from memory:
#
#     paddlepaddle dist version: 3.3.1
#     top_level.txt            : paddle
#     find_spec('paddlepaddle') -> False       with paddlepaddle 3.3.1 present
#     find_spec('paddle')       -> True
#
# So the guard is unsatisfiable. Those eleven tests skip in EVERY environment
# that can exist, including one with the full OCR stack installed — measured,
# by installing it and running them:
#
#     1 failed, 40 passed, 11 skipped
#     SKIPPED ... reason: "not installed: paddlepaddle"
#
# A skip condition nobody could satisfy is a test that was never run. The
# environment was only half the story.
#
# ── WHY THIS SCRIPT ASSERTS ZERO SKIPS ────────────────────────────────────
#
# That is the problem principle, and it generalises past this one typo
# (CLAUDE.md J.9): a skip guard is UNVERIFIED until something checks that the
# tests it guards actually ran. Counting passes cannot catch it — a suite of
# forty passes and eleven silent skips reports green.
#
# Zero is not a threshold anyone chose. It is the definition of "this
# environment is the complete one": if this run skips anything at all, the
# environment it built is not the environment it promised, and saying so is
# the only honest outcome. The check is proved live on a synthetic result
# before it is trusted on the real one, the same way every gate in
# .github/workflows/ proves itself against a canary first.
#
# ── PINS ARE SELECTED, NEVER COPIED ───────────────────────────────────────
#
# Every version below is read out of the manifest that already owns it, so
# this file adds no fourth place where a version lives (CLAUDE.md Law 19).
# numpy and opencv-python are deliberately NOT selected from
# requirements-engine1.txt: taking them is exactly the collision this script
# exists to avoid, and `reader` uses neither pin — numpy arrives as paddlex's
# own resolved version and no OpenCV is imported at all.
#
# ── USAGE ─────────────────────────────────────────────────────────────────
#
#     tools/ci/run_ocr_tests.sh [venv-path] [junit-path]
#
# Exits non-zero, loudly, on: an unbuildable environment, a missing PaddleOCR,
# a suite that collected nothing, a suite that skipped anything, or any test
# failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUITE="tests/unit/test_input_engine_reader.py"

# `--self-test` runs the hollow-gate defence below and nothing else. It builds
# no environment, downloads nothing and finishes in milliseconds, so a workflow
# can carry the same "prove this gate can still fail" step every sibling job
# already carries without paying for the environment twice.
SELF_TEST=0
if [ "${1:-}" = "--self-test" ]; then
  SELF_TEST=1
  shift
fi

VENV="${1:-/tmp/ocr-venv}"
JUNIT="${2:-/tmp/ocr-junit.xml}"

cd "$REPO_ROOT"

# ── the assertion, written once, proved live, then trusted ────────────────
ASSERT="$(mktemp -t ocr_junit_assert)"
cat > "$ASSERT" <<'PY'
"""Refuse a run that collected nothing, skipped anything, or failed anything.

A skipped test is treated exactly as harshly as a failing one HERE and nowhere
else in the repository, and the difference is deliberate. Elsewhere a skip
means "this environment cannot run it". This job exists only to be that
environment, so a skip here means the environment it built is not the one it
claimed to build - which is the failure that hid F-009 for as long as it hid.

READ BY REGEX OVER THE COUNT ATTRIBUTES, NOT BY AN XML PARSER. This is the
mechanism .github/workflows/testing.yml already uses for its collected count,
reused rather than reinvented, and it has a second merit: an XML parser would
expand entities, and pointing one at a file is a surface this job does not
need. Only four integers are wanted and they are attributes of the opening
tag. Every skipped test's NAME AND REASON is already printed by pytest's own
`-rs` summary immediately above, so nothing is lost by not walking the tree.
"""

import pathlib
import re
import sys

report = pathlib.Path(sys.argv[1])
if not report.is_file():
    print(f"BLOCKED - no JUnit report at {report}. The suite did not run.")
    sys.exit(1)

text = report.read_text(encoding="utf-8")


def total(attribute: str) -> int:
    """Sum one count attribute across every testsuite element in the report."""
    return sum(int(value) for value in re.findall(rf'\b{attribute}="(\d+)"', text))


tests = total("tests")
skipped = total("skipped")
failures = total("failures")
errors = total("errors")

print(f"collected : {tests}")
print(f"skipped   : {skipped}")
print(f"failures  : {failures}")
print(f"errors    : {errors}")

blocked = False
if tests == 0:
    print("BLOCKED - zero tests collected. A suite that ran nothing is not a pass.")
    blocked = True
if skipped:
    print(f"BLOCKED - {skipped} test(s) skipped in the environment built to run them.")
    print("          Their names and reasons are in the pytest summary above.")
    print("          A skip guard nobody can satisfy is a test that never ran.")
    blocked = True
if failures or errors:
    print(f"BLOCKED - {failures} failure(s) and {errors} error(s).")
    blocked = True

sys.exit(1 if blocked else 0)
PY

# HOLLOW-GATE DEFENCE. The skip detector above is the only thing standing
# between this job and the exact false green that produced F-009, so it is fed
# results it MUST reject before any real result is handed to it. Three of them:
# a skipped test, an empty collection, and a failure - one per branch, because
# a canary that only exercises one branch proves only that branch.
canary_must_be_rejected() {
  local label="$1" body="$2" report
  report="$(mktemp -t ocr_junit_canary)"
  printf '%s\n' "$body" > "$report"
  if python3 "$ASSERT" "$report"; then
    echo "BLOCKED - the result check is HOLLOW: it accepted ${label}."
    rm -f "$report"
    exit 1
  fi
  rm -f "$report"
  echo "canary rejected as expected: ${label}"
}

canary_must_be_rejected "a skipped test" \
  '<testsuites><testsuite name="c" tests="1" skipped="1" failures="0" errors="0"/></testsuites>'
canary_must_be_rejected "a suite that collected nothing" \
  '<testsuites><testsuite name="c" tests="0" skipped="0" failures="0" errors="0"/></testsuites>'
canary_must_be_rejected "a failing test" \
  '<testsuites><testsuite name="c" tests="1" skipped="0" failures="1" errors="0"/></testsuites>'

# FALSIFICATION OF THE CANARIES ABOVE (CLAUDE.md D.13). A check that rejects
# everything passes all three of them and is just as useless as one that
# accepts everything - it would turn this gate permanently red for a reason
# that has nothing to do with OCR. So a clean result must be ACCEPTED, and
# that is asserted here rather than assumed.
CLEAN="$(mktemp -t ocr_junit_clean)"
printf '%s\n' \
  '<testsuites><testsuite name="c" tests="1" skipped="0" failures="0" errors="0"/></testsuites>' \
  > "$CLEAN"
if ! python3 "$ASSERT" "$CLEAN"; then
  echo "BLOCKED - the result check rejects a clean result. It would never pass."
  rm -f "$CLEAN"
  exit 1
fi
rm -f "$CLEAN"
echo "clean result accepted as expected - the check is not stuck red"

if [ "$SELF_TEST" -eq 1 ]; then
  echo "self-test complete - the result check is live on all three branches"
  exit 0
fi

# ── select the pins, and refuse to proceed if a selection came back empty ──
#
# An empty selection would silently build an environment missing a package and
# then blame the tests for the failure. A renamed or deleted pin must stop the
# run and name itself instead.
select_pins() {
  local manifest="$1" names="$2" found
  found="$(grep -E "^(${names})==" "$manifest" || true)"
  if [ -z "$found" ]; then
    echo "BLOCKED - no pin matching '${names}' found in ${manifest}." >&2
    echo "          This script selects versions rather than restating them," >&2
    echo "          so a renamed pin must stop the run, not be guessed." >&2
    exit 1
  fi
  echo "$found"
}

RUNNER_PINS="$(select_pins requirements-ci.txt 'pytest|pytest-randomly')"
SHARED_PINS="$(select_pins requirements-engine1.txt 'pymupdf|pillow')"

echo "── pins selected from the manifests that own them ──"
echo "$RUNNER_PINS"
echo "$SHARED_PINS"
grep -E '^[A-Za-z]' requirements-engine1-ocr.txt

# ── build the isolated interpreter ────────────────────────────────────────
#
# The removal below is guarded BY CONSTRUCTION rather than by care
# (CLAUDE.md J.6): a path is only ever deleted when it is already a virtual
# environment, which `pyvenv.cfg` establishes and nothing else does. An
# absolute path is required as well, so a relative argument cannot resolve
# against whatever directory the caller happened to be in.
case "$VENV" in
  /*) ;;
  *)
    echo "BLOCKED - the venv path must be absolute, got '${VENV}'." >&2
    exit 1
    ;;
esac
if [ -e "$VENV" ]; then
  if [ ! -f "$VENV/pyvenv.cfg" ]; then
    echo "BLOCKED - '${VENV}' exists and is not a virtual environment." >&2
    echo "          Refusing to delete it. Nothing without a pyvenv.cfg is" >&2
    echo "          this script's to remove." >&2
    exit 1
  fi
  rm -rf "$VENV"
fi

# THE INTERPRETER IS NAMED, NOT INHERITED. `python3` is whatever happens to be
# first on PATH, and PaddlePaddle 3.3.1 publishes wheels for cp39 through cp313
# only. On a machine whose `python3` is 3.14 this script fails with
#
#     ERROR: Could not find a version that satisfies the requirement
#     paddlepaddle==3.3.1 (from versions: none)
#
# which blames the pin for a property of the interpreter. Measured here, not
# predicted - it is how this line came to be written. CI sets `python3` to 3.12
# through actions/setup-python, so the default is correct there and OCR_PYTHON
# is what makes the script runnable anywhere else.
OCR_PYTHON="${OCR_PYTHON:-python3}"
echo "building with: $("$OCR_PYTHON" -V 2>&1) at $(command -v "$OCR_PYTHON")"
"$OCR_PYTHON" -m venv "$VENV"

set +e
# shellcheck disable=SC2086
"$VENV/bin/python" -m pip install --disable-pip-version-check --quiet \
  -r requirements-engine1-ocr.txt $RUNNER_PINS $SHARED_PINS
INSTALL_STATUS=$?
set -e
if [ "$INSTALL_STATUS" -ne 0 ]; then
  echo "BLOCKED - the OCR environment would not install under $("$OCR_PYTHON" -V 2>&1)." >&2
  echo "          If pip reported 'from versions: none', this interpreter has no" >&2
  echo "          wheel for a pinned package rather than the pin being wrong." >&2
  echo "          Set OCR_PYTHON to an interpreter the pins publish wheels for." >&2
  exit "$INSTALL_STATUS"
fi

# ── prove the environment is the one that was asked for ───────────────────
#
# `find_spec` on the IMPORT name, never the distribution name. Getting this
# wrong is the whole of the second defect described above, so the check that
# guards against it is written the correct way and says which is which.
"$VENV/bin/python" - requirements-engine1.txt <<'PY'
import importlib.metadata as metadata
import importlib.util
import pathlib
import re
import sys

REQUIRED_IMPORT_NAMES = ("paddleocr", "paddle", "pymupdf", "PIL", "numpy")
missing = [n for n in REQUIRED_IMPORT_NAMES if importlib.util.find_spec(n) is None]
if missing:
    print(f"BLOCKED - the OCR environment is incomplete: {missing} not importable.")
    print("          These are IMPORT names. `paddlepaddle` is the distribution;")
    print("          `paddle` is what it installs, and only the import name can")
    print("          be looked up with find_spec.")
    sys.exit(1)

# ISOLATION, ASSERTED RATHER THAN INTENDED. The whole design rests on this
# interpreter never containing `requirements-engine1.txt`'s OpenCV pin: two
# distributions both provide `cv2`, pip installs both without a word, and
# import order alone decides which one wins. If that pin is ever found here,
# the two environments have been merged and the separation this script exists
# to create no longer exists.
if importlib.util.find_spec("cv2") is not None:
    try:
        opencv_python = metadata.version("opencv-python")
    except metadata.PackageNotFoundError:
        opencv_python = None
    if opencv_python is not None:
        print("BLOCKED - opencv-python is installed in the OCR environment.")
        print(f"          requirements-engine1.txt pins it at {opencv_python} and")
        print("          paddlex installs opencv-contrib-python, which provides the")
        print("          same `cv2`. With both present nothing decides which one")
        print("          `import cv2` resolves to, and no error is raised either way.")
        sys.exit(1)

import numpy

engine1 = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
pinned_numpy = re.search(r"^numpy==(\S+)", engine1, re.MULTILINE)
print(f"OCR environment built: numpy {numpy.__version__}")
if pinned_numpy:
    print(f"requirements-engine1.txt pins numpy {pinned_numpy.group(1)} in ITS OWN")
    print("interpreter. The two differ on purpose and never share a site-packages.")
PY

# Every pin in the OCR manifest must be the version that actually imports, in
# this interpreter, unshadowed. Metadata alone cannot answer that question.
"$REPO_ROOT/tools/ci/assert_imports_match_pins.sh" \
  "$VENV/bin/python" requirements-engine1-ocr.txt

# ── run the OCR path for real ─────────────────────────────────────────────
rm -f "$JUNIT"
set +e
"$VENV/bin/python" -m pytest "$SUITE" -p no:randomly -rs --junitxml="$JUNIT"
PYTEST_STATUS=$?
set -e

python3 "$ASSERT" "$JUNIT"

if [ "$PYTEST_STATUS" -ne 0 ]; then
  echo "BLOCKED - pytest exited ${PYTEST_STATUS}."
  exit "$PYTEST_STATUS"
fi

echo "the OCR path executed: every test in ${SUITE} ran, none skipped"
