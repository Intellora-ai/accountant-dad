#!/usr/bin/env bash
#
# Audit EVERY dependency manifest in this repository, not just the one.
#
# ── WHAT WAS UNAUDITED ────────────────────────────────────────────────────
#
# `dependency scan` runs pip-audit against `requirements-ci.txt` and against
# `pyproject.toml`'s five declared dependencies. It has never run against
# `requirements-engine1.txt` or `requirements-engine1-ocr.txt`, which four other
# CI jobs install. Measured at a467bb2, that is six pinned distributions —
# docling, transformers, torch, torchvision, timm, pypdfium2 — entering CI with
# no advisory scanning at all.
#
# ── WHY THE LIST IS ASKED FOR RATHER THAN WRITTEN HERE ────────────────────
#
# A list of manifests written into this file, or into a workflow, is a second
# source of truth that nothing compares against the filesystem. That is the same
# shape as the hole above. `--list` derives it by walking the tree, so a fourth
# manifest is audited the day it appears.
#
# ── WHY IT VERIFIES AFTERWARDS ────────────────────────────────────────────
#
# The loop below accumulates the manifests it ACTUALLY handed to pip-audit and
# passes them to `--verify`, which compares them against what is on disk. A loop
# that exits early, filters, or silently skips a file is caught. Asking for the
# list and then not auditing all of it is the failure mode a `for` loop makes
# easy, and it would otherwise be invisible.
#
# ── USAGE ─────────────────────────────────────────────────────────────────
#
#     tools/ci/audit_dependency_manifests.sh
#
# Exits non-zero on any advisory, any unaudited manifest, and any manifest that
# declares no pins.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DERIVE="${HERE}/audit_dependency_manifests.py"

if [ ! -f "$DERIVE" ]; then
  echo "BLOCKED - ${DERIVE} is missing; the manifest set cannot be derived." >&2
  exit 1
fi

if ! command -v pip-audit > /dev/null 2>&1; then
  echo "BLOCKED - pip-audit is not on PATH. Install requirements-ci.txt first." >&2
  exit 1
fi

# `while read` rather than `mapfile`: mapfile is a bash 4 builtin and macOS
# ships bash 3.2, so this script would die with "command not found" on any
# developer machine while passing on the ubuntu runner. A guard that only runs
# in one place is a guard nobody can reproduce.
MANIFESTS=()
while IFS= read -r line; do
  [ -n "$line" ] && MANIFESTS+=("$line")
done < <(python3 "$DERIVE" --list)

if [ "${#MANIFESTS[@]}" -eq 0 ]; then
  # ZERO IS NOT A PASS. An empty list would make the loop below run no audits
  # and the script exit 0 having proved nothing.
  echo "BLOCKED - no dependency manifest was discovered. Nothing was audited." >&2
  exit 1
fi

echo "discovered ${#MANIFESTS[@]} dependency manifest(s):"
printf '  %s\n' "${MANIFESTS[@]}"
echo

AUDITED=()
FAILED=0
for manifest in "${MANIFESTS[@]}"; do
  echo "── pip-audit ${manifest} ──"
  # --strict so pip-audit fails on a dependency it cannot resolve rather than
  # skipping it. A skipped package is an unaudited package wearing a pass.
  if pip-audit --strict --progress-spinner off --requirement "$manifest"; then
    AUDITED+=("$manifest")
  else
    echo "ADVISORY - ${manifest} did not pass the audit." >&2
    FAILED=1
    # Recorded as audited: it WAS audited, and it failed. Leaving it out would
    # make --verify report it as skipped and hide the real reason.
    AUDITED+=("$manifest")
  fi
  echo
done

# Coverage, checked against the filesystem rather than against this loop's own
# intentions.
python3 "$DERIVE" --verify "${AUDITED[@]}"

# The installed tree, not the manifest. Auditing manifests proves things about
# what was ASKED FOR; this asks what is actually THERE. F-023 measured 13
# distributions on this project's own environment that no manifest can reach —
# importable, unpinned, and audited by nothing.
#
# Handed every manifest, because a subset would report the other manifests'
# packages as orphans and be wrong in the direction that destroys trust.
echo "── installed distributions vs. the manifests ──"
python3 "$DERIVE" --orphans "${MANIFESTS[@]}"

if [ "$FAILED" -ne 0 ]; then
  echo "BLOCKED - at least one dependency manifest carries a known advisory." >&2
  exit 1
fi

echo "every dependency manifest in the tree was audited and is clean"
