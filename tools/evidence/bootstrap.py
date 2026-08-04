"""Clone → bootstrap → verify, with the same result on every machine.

The repository commits the extracted `.txt` sidecars and not the 42 MB of PDFs.
That is a deliberate split: the sidecars make verification reproducible without
depending on which PDF library is installed, and the PDFs are re-fetchable
government bytes whose only job is to anchor the sidecars to an official source
via a checksum.

This module closes the loop. It reads the manifest — which is now the
declaration of what the repository REQUIRES, not a note about what somebody
once downloaded — fetches anything absent, and refuses anything whose bytes do
not hash to the declared value.

    every document declared        → fetched or already present
    every fetched document         → sha256 checked against the manifest
    any mismatch                   → deleted and reported, never kept

A downloaded file that fails its checksum is removed rather than left on disk,
because a wrong-but-present document is worse than an absent one: absence is
loud, and a silently wrong version verifies quotes against text nobody chose.

OFFLINE IS A FIRST-CLASS CASE. `--check` fetches nothing and reports exactly
what is missing, with each source URL and expected hash, so CI or an air-gapped
machine can state the gap precisely instead of failing with a stack trace.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import urllib.error
import urllib.request

from .model import CitationError
from .registry import SOURCES, Document, Registry

#: Government portals reject the default urllib agent. This identifies the
#: fetcher honestly rather than impersonating a browser.
USER_AGENT = "accountant-dad-evidence-bootstrap/1.0 (+source verification)"

TIMEOUT_SECONDS = 120


def fetch(document: Document, destination: pathlib.Path | None = None) -> None:
    """Download one document and keep it only if its bytes match the manifest."""
    target = destination or document.path
    target.parent.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(  # noqa: S310 — manifest URLs, checksum-verified below
        document.url, headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CitationError(
            f"could not fetch {document.file} from {document.url}: {exc}"
        ) from exc

    target.write_bytes(payload)
    actual = document.actual_sha256()
    if actual != document.sha256:
        target.unlink()
        raise CitationError(
            f"{document.file} downloaded from {document.url} hashes to {actual}, "
            f"but the manifest declares {document.sha256}. The file has been removed: "
            f"a document that is present and wrong is more dangerous than one that is "
            f"absent, because absence is visible and a wrong version is not."
        )


def report_missing(missing: list[Document]) -> str:
    """Say exactly which documents are absent, where each comes from, and what to run."""
    lines = [f"{len(missing)} required document(s) missing:", ""]
    for document in missing:
        lines.append(f"  {document.missing_report()}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.evidence.bootstrap",
        description="Fetch and checksum every source the manifest declares.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what is missing without fetching anything (offline safe)",
    )
    args = parser.parse_args(argv)

    try:
        registry = Registry.load()
    except CitationError as exc:
        print(f"BLOCKED — {exc}")
        return 1

    missing = registry.missing()
    print(f"  {'declared':16} {len(registry)}")
    print(f"  {'present':16} {len(registry) - len(missing)}")
    print(f"  {'missing':16} {len(missing)}")

    if not missing:
        print(f"\nevery declared document is present in {SOURCES}")
        return 0

    if args.check:
        print()
        print(report_missing(missing))
        return 1

    failures: list[str] = []
    for document in missing:
        print(f"\nfetching {document.file}")
        print(f"  from {document.url}")
        try:
            fetch(document)
        except CitationError as exc:
            failures.append(str(exc))
            print(f"  FAILED — {exc}")
        else:
            print(f"  ok, sha256 matches {document.sha256[:16]}…")

    if failures:
        print(f"\nBLOCKED — {len(failures)} document(s) could not be obtained.")
        print("Fetch them by hand from the URLs above and re-run; the checksum is")
        print("verified either way, so a hand-placed file is held to the same proof.")
        return 1

    print(f"\nall {len(missing)} document(s) fetched and checksum-verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
