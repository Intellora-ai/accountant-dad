"""Write the resolved half of every citation back into the claim files.

Every knowledge item must CARRY its full metadata — document, version, source
URL, checksum, section, quote, normalised text, character range, retrieval date,
evidence id. Almost none of it is hand-written: an author supplies the three
things only a human can know, and this writes the rest.

That split is the point. A checksum typed by hand into hundreds of files is
hundreds of places to forget when a source is re-fetched, and a stale checksum
nobody compares is indistinguishable from a correct one. Here the resolved
fields are machine-written, and `verify` re-derives and compares them on every
run — so a disagreement is a hard failure (layer 6) rather than a fact that
quietly went out of date.

WHAT IT REFUSES TO DO

    an unproven citation is never materialised

Writing resolved metadata onto a citation that failed a layer would dress a
broken claim in the appearance of provenance — a checksum and a character range
next to a quote that is not where it says it is. Those are left exactly as the
author wrote them, so the failure stays visible.

Running twice changes nothing: the resolved fields are a pure function of the
manifest and the source text, so this is a fixed point and reruns produce empty
diffs.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .model import CitationError
from .registry import BRAIN, Registry
from .verify import HONEST_GAPS, VERIFIED, check_citation, claims


def materialise_claim(
    record: dict[str, object], registry: Registry
) -> tuple[list[dict[str, object]] | None, int, int]:
    """Resolved evidence for one claim, plus how many proved and how many did not."""
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        return None, 0, 0

    rewritten: list[dict[str, object]] = []
    proven = unproven = 0
    for entry in evidence:
        problems, citation = check_citation(entry, registry)
        if problems or citation is None:
            unproven += 1
            rewritten.append(entry if isinstance(entry, dict) else {"unreadable": repr(entry)})
        else:
            proven += 1
            rewritten.append(citation.to_entry())
    return rewritten, proven, unproven


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.evidence.materialise",
        description="Write resolved citation metadata into every claim that proves.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change without writing anything",
    )
    parser.add_argument("root", nargs="?", default=str(BRAIN))
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()

    try:
        registry = Registry.load()
    except CitationError as exc:
        print(f"BLOCKED — {exc}")
        return 1

    changed = proven_total = unproven_total = 0
    for path, record in claims(root):
        status = str(record.get("status", ""))
        if status != VERIFIED:
            if status not in HONEST_GAPS:
                print(f"  unknown status {status!r} in {path.relative_to(root)}")
            continue

        rewritten, proven, unproven = materialise_claim(record, registry)
        proven_total += proven
        unproven_total += unproven
        if rewritten is None or rewritten == record.get("evidence"):
            continue

        changed += 1
        if not args.check:
            record["evidence"] = rewritten
            path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    verb = "would gain" if args.check else "gained"
    print(f"  {'claims ' + verb + ' metadata':34} {changed}")
    print(f"  {'citations proven':34} {proven_total}")
    print(f"  {'citations NOT proven':34} {unproven_total}")

    if unproven_total:
        print(
            "\nUnproven citations were left exactly as written. Resolved metadata on a "
            "\nfailing citation would dress a broken claim in the look of provenance."
            "\nRun `python3 -m tools.evidence.verify` for the reason on each."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
