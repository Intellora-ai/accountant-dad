#!/usr/bin/env python3
"""Re-open every cited source and confirm every quote is really in it.

THE ONE THING THAT MAKES THIS DIRECTORY WORTH ANYTHING.

Without this, a claim citing `CGST Act s.16(2)(c)` is indistinguishable from a
claim that remembers something shaped like it. Both look identical in a file.
The difference is only visible by opening the document and looking, which is
what this does, on every claim, every run.

`tests/unit/test_conformance_registry.py` already applies this to the 23 locked
documents in `docs/` — it opens the cited file, reads the cited line, and fails
if the quote drifted. This is the same mechanism pointed at downloaded law.

WHAT IT REFUSES, and why each one matters

    quote not found in the source     the claim is unsupported. This is the
                                      fabrication case and the reason the file
                                      exists.
    source not downloaded             a citation to a document nobody has is a
                                      citation nobody can check.
    hash mismatch                     the local copy changed after it was
                                      recorded, so every quote verified against
                                      the old bytes is now unverified.
    VERIFIED with no quote            a status asserting evidence, with none.

Statuses other than VERIFIED are not failures. `UNKNOWN`, `NO AUTHORITATIVE
SOURCE FOUND` and `REQUIRES HUMAN ACCOUNTANT` are honest and expected — a gap
recorded is a gap that can be filled. Only a claim that says VERIFIED and is not
is a defect.

Whitespace is normalised before comparison, because a PDF extractor breaks lines
wherever the page did and the same sentence legitimately arrives with different
spacing. Nothing else is normalised: casing, wording and punctuation must match,
or it is a different sentence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

BRAIN = pathlib.Path(__file__).resolve().parent
SOURCES = BRAIN / "Evidence_Library" / "sources"
MANIFEST = BRAIN / "Evidence_Library" / "manifest.jsonl"

#: A claim asserting evidence must produce it. Everything else is a recorded gap.
VERIFIED = "VERIFIED"
HONEST_GAPS = frozenset(
    {"UNKNOWN", "NO AUTHORITATIVE SOURCE FOUND", "REQUIRES HUMAN ACCOUNTANT", "CONFLICT"}
)


def normalise(text: str) -> str:
    """Collapse whitespace only. A PDF wraps where the page wrapped."""
    return re.sub(r"\s+", " ", text).strip()


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def extracted_text(path: pathlib.Path) -> str:
    """The searchable text of a downloaded source.

    A `.txt` sidecar is preferred when present: PDF extraction is lossy and
    slow, so a source is extracted once and the result committed beside it,
    which also makes every verification reproducible without the extractor.
    """
    sidecar = path.with_suffix(path.suffix + ".txt")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".pdf":
        raise SystemExit(
            f"{path.name} has no .txt sidecar. Extract it once and commit the "
            "result, so verification does not depend on a PDF library version."
        )
    return path.read_text(encoding="utf-8", errors="replace")


def manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.is_file():
        return {}
    entries: dict[str, dict[str, str]] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            entries[str(record["file"])] = record
    return entries


def claims() -> list[tuple[pathlib.Path, dict[str, object]]]:
    """Every `.json` under the brain that carries a `status`."""
    found: list[tuple[pathlib.Path, dict[str, object]]] = []
    for path in sorted(BRAIN.rglob("*.json")):
        if SOURCES in path.parents:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(record, dict) and "status" in record:
            found.append((path, record))
    return found


def main() -> int:
    failures: list[str] = []
    tally: dict[str, int] = {}
    recorded = manifest()

    for path, record in claims():
        status = str(record.get("status", ""))
        tally[status] = tally.get(status, 0) + 1
        label = path.relative_to(BRAIN)

        if status in HONEST_GAPS:
            continue
        if status != VERIFIED:
            failures.append(f"{label}: unknown status {status!r}")
            continue

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"{label}: VERIFIED but carries no evidence")
            continue

        for item in evidence:
            if not isinstance(item, dict):
                failures.append(f"{label}: evidence entry is not an object")
                continue
            filename = str(item.get("file", ""))
            quote = str(item.get("quote", ""))
            local = SOURCES / filename

            if not filename or not quote:
                failures.append(f"{label}: evidence needs both `file` and `quote`")
                continue
            if not local.is_file():
                failures.append(f"{label}: cites {filename}, which is not downloaded")
                continue
            if filename in recorded and sha256(local) != recorded[filename].get("sha256"):
                failures.append(f"{label}: {filename} no longer matches its recorded hash")
                continue
            if normalise(quote) not in normalise(extracted_text(local)):
                failures.append(
                    f"{label}: quote NOT FOUND in {filename} — {quote[:70]!r}. "
                    "Record it as NO AUTHORITATIVE SOURCE FOUND rather than asserting it."
                )

    for status, count in sorted(tally.items()):
        print(f"  {status:28} {count}")
    print(f"  {'claims total':28} {sum(tally.values())}")

    if failures:
        print(f"\nBLOCKED - {len(failures)} unsupported claim(s):")
        for line in failures:
            print(f"  {line}")
        return 1

    print("\nevery VERIFIED claim was found in its downloaded source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
