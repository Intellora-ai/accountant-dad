"""The five proofs, run on every citation, every time.

Replaces a check that asked one question — "does this text appear somewhere in
this file?" — and therefore passed a claim citing `CGST Act s.999` for a quote
taken from an ICAI standard on dividends. The words were real, the file was
real, and the citation was nonsense. A 500,000-character Act says yes to almost
any short string, so "appears somewhere" is close to no check at all.

Each layer below is independent, and a failure in any one is a failure. There
is no warning tier: a citation exists to tell a reader where to look, so a
citation that is wrong about where it came from has failed at the only job it
has.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import sys

from .model import (
    AUTHORED_FIELDS,
    AUTHORED_OPTIONAL,
    RESOLVED_FIELDS,
    Citation,
    CitationError,
    Failure,
    Layer,
    Span,
    evidence_id,
    normalise,
)
from .parsers.base import SectionParser
from .registry import BOOTSTRAP_COMMAND, BRAIN, SOURCES, Document, Registry

VERIFIED = "VERIFIED"

#: Statuses that record a gap honestly. A gap is not a defect — a claim that
#: says UNKNOWN is doing its job. Only a claim asserting VERIFIED and failing to
#: prove it is a defect.
HONEST_GAPS = frozenset(
    {"UNKNOWN", "NO AUTHORITATIVE SOURCE FOUND", "REQUIRES HUMAN ACCOUNTANT", "CONFLICT"}
)

ALL_STATUSES = HONEST_GAPS | {VERIFIED}


@dataclasses.dataclass(slots=True)
class Result:
    """What one run learned. Failures are the product; the tallies are context."""

    failures: list[str] = dataclasses.field(default_factory=list)
    tally: dict[str, int] = dataclasses.field(default_factory=dict)
    citations: int = 0
    proven: int = 0
    missing_documents: list[Document] = dataclasses.field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and not self.missing_documents


def check_document(document: Document) -> list[Failure]:
    """LAYER 1 — the right document, in the version we recorded.

    Absence is reported with the source URL, the expected hash and the exact
    bootstrap command, because a check that fails without saying how to fix it
    trains people to ignore it.
    """
    if not document.present():
        return [
            Failure(
                Layer.DOCUMENT,
                f"{document.file} is declared in the manifest but not on disk",
                f"fetch it: {BOOTSTRAP_COMMAND}   (source {document.url})",
            )
        ]

    actual = document.actual_sha256()
    if actual != document.sha256:
        return [
            Failure(
                Layer.DOCUMENT,
                f"{document.file} hashes to {actual[:16]}… but the manifest "
                f"declares {document.sha256[:16]}…",
                "the local copy is not the version every quote was checked against; "
                "re-fetch it, or update the manifest deliberately and re-verify every "
                "quote that cites it",
            )
        ]
    return []


def _read_entry(entry: object) -> tuple[Failure | None, dict[str, object] | None]:
    """Is this even a citation? Shape only — no document is opened here."""
    if not isinstance(entry, dict):
        return Failure(Layer.METADATA, "evidence entry is not an object"), None

    missing = sorted(AUTHORED_FIELDS - set(entry))
    if missing:
        return Failure(
            Layer.METADATA,
            f"evidence entry lacks {', '.join(missing)}",
            "an author supplies file, section and quote; everything else is resolved",
        ), None

    unknown = set(entry) - AUTHORED_FIELDS - AUTHORED_OPTIONAL - RESOLVED_FIELDS
    if unknown:
        return Failure(
            Layer.METADATA,
            f"evidence entry carries unknown field(s): {', '.join(sorted(unknown))}",
            "an unrecognised field is either a typo or a fact nothing checks",
        ), None

    if not str(entry["quote"]).strip():
        return Failure(
            Layer.METADATA,
            f"{entry['file']} {entry['section']}: quote is empty",
            "an empty quote asserts a source for nothing",
        ), None

    return None, entry


def _resolve_document(filename: str, registry: Registry) -> tuple[Failure | None, Document | None]:
    """LAYER 1 for a citation — is this document one the repository declares?"""
    document = registry.get(filename)
    if document is None:
        return Failure(
            Layer.DOCUMENT,
            f"cites {filename}, which the manifest does not declare",
            "add it to the manifest with its source URL and sha256, or correct the "
            "filename — a quote checked against an undeclared document is checked "
            "against nothing",
        ), None
    return None, document


def _resolve_section(
    document: Document, parser: SectionParser, text: str, label: str
) -> tuple[Failure | None, tuple[Span, str] | None]:
    """LAYERS 5 then 2. Ownership first, so a foreign label fails for its own reason."""
    if not parser.owns(label):
        return Failure(
            Layer.OWNERSHIP,
            f"{document.file} is a {document.kind} document, whose references look "
            f"like {parser.label_form}; {label!r} is not one",
            "a reference that the document's own grammar cannot express is a "
            "citation to a different document",
        ), None

    found = parser.locate(text, label)
    if found is None:
        return Failure(
            Layer.SECTION,
            f"{document.file} has no section {label!r}",
            "the words may well be somewhere in this document, but not under the "
            "heading claimed; find the real one or record NO AUTHORITATIVE SOURCE FOUND",
        ), None
    return None, found


@dataclasses.dataclass(frozen=True, slots=True)
class _Source:
    """The document under examination, its grammar, and its extracted text.

    Bundled because these three always travel together and always agree with
    each other; passing them separately invites a caller to parse one document's
    text with another document's parser.
    """

    document: Document
    parser: SectionParser
    text: str


def _prove_quote(
    source: _Source, label: str, quote: str, found: tuple[Span, str]
) -> tuple[Failure | None, Span | None]:
    """LAYER 4 then LAYER 3 — the words exist, AND they exist where claimed.

    Order matters for the error message. "not in this document at all" and "in
    this document but under a different heading" are different mistakes with
    different fixes, and collapsing them would hide the second behind the first.
    """
    span, proven_level = found
    if normalise(quote) not in normalise(source.text):
        return Failure(
            Layer.TEXT,
            f"{source.document.file} {label}: quote NOT FOUND anywhere in the "
            f"document — {quote[:70]!r}",
            "record it as NO AUTHORITATIVE SOURCE FOUND rather than asserting it",
        ), None

    occurrences = _occurrences(source.text, quote)
    inside = [occ for occ in occurrences if span.contains(occ)]
    if not inside:
        exact = proven_level == source.parser.canonical(label)
        at = label if exact else f"{label} (at {proven_level})"
        return Failure(
            Layer.CONTAINMENT,
            f"{source.document.file}: the quote exists but NOT inside {at} — {quote[:60]!r}",
            f"it appears {_describe_elsewhere(source.parser, source.text, occurrences)}. "
            f"Cite the section the words are actually in.",
        ), None
    return None, inside[0]


def check_citation(entry: object, registry: Registry) -> tuple[list[Failure], Citation | None]:
    """LAYERS 1-6 for one evidence entry. An empty list means every proof held."""
    failure, authored = _read_entry(entry)
    if failure or authored is None:
        return ([failure] if failure else []), None

    filename = str(authored["file"])
    label = str(authored["section"])
    quote = str(authored["quote"])

    failure, document = _resolve_document(filename, registry)
    if failure or document is None:
        return ([failure] if failure else []), None

    parser = registry.parser_for(document)
    text = document.text()

    failure, found = _resolve_section(document, parser, text, label)
    if failure or found is None:
        return ([failure] if failure else []), None
    failure, located = _prove_quote(_Source(document, parser, text), label, quote, found)
    if failure or located is None:
        return ([failure] if failure else []), None
    normalised_quote = normalise(quote)
    resolved = Citation(
        file=filename,
        section=label,
        quote=quote,
        version=document.version,
        source_url=document.url,
        checksum=document.sha256,
        normalised=normalised_quote,
        char_range=(located.start, located.end),
        retrieved=document.retrieved,
        evidence_id=evidence_id(filename, label, quote),
        subsection=_optional(authored, "subsection"),
        page=_page(authored),
        paragraph=_optional(authored, "paragraph"),
        extraction_note=_optional(authored, "extraction_note"),
    )

    # LAYER 6 — stored metadata agrees with resolved metadata.
    drift = _metadata_drift(authored, resolved)
    if drift:
        return [drift], resolved

    return [], resolved


def _page(entry: dict[str, object]) -> int | None:
    """A page number only when it really is one. A string here is a defect elsewhere."""
    value = entry.get("page")
    return value if isinstance(value, int) else None


def _optional(entry: dict[str, object], name: str) -> str | None:
    value = entry.get(name)
    return str(value) if value is not None else None


def _occurrences(text: str, quote: str) -> list[Span]:
    """Every place the quote sits in the RAW text, found via the normalised form.

    Matching happens on normalised text, but a span must index the raw text so
    it can be compared against raw section spans. The bridge is a whitespace-and-
    typography-tolerant pattern built from the quote's own characters, which
    keeps `char_range` meaningful against the committed sidecar.
    """
    from .model import _TYPOGRAPHIC  # noqa: PLC0415 — private, deliberately not re-exported

    equivalents: dict[str, str] = {}
    for odd, plain in _TYPOGRAPHIC.items():
        equivalents.setdefault(plain, "")
        equivalents[plain] += odd

    pieces: list[str] = []
    for char in normalise(quote):
        if char == " ":
            pieces.append(r"\s+")
        elif char in equivalents:
            pieces.append(f"[{re.escape(char + equivalents[char])}]")
        else:
            pieces.append(re.escape(char))
    pattern = re.compile("".join(pieces))
    return [Span(m.start(), m.end()) for m in pattern.finditer(text)]


def _describe_elsewhere(
    parser: SectionParser, text: str, occurrences: list[Span]
) -> str:
    """Name the sections the quote IS in, so the fix is obvious rather than a hunt."""
    if not occurrences:
        return "nowhere the raw text can be indexed"
    sections = parser.sections(text)
    found = {
        label
        for label, span in sections.items()
        if any(span.contains(occ) for occ in occurrences)
    }
    if not found:
        return f"{len(occurrences)} time(s), outside every parsed section"
    listed = ", ".join(sorted(found)[:4])
    return f"in {listed}"


def _metadata_drift(entry: dict[str, object], resolved: Citation) -> Failure | None:
    """LAYER 6 — a stored field that disagrees with the source of truth."""
    stored = resolved.to_entry()
    for field in sorted(RESOLVED_FIELDS):
        if field not in entry:
            continue
        was, now = entry[field], stored[field]
        if field == "char_range":
            was = list(was) if isinstance(was, (list, tuple)) else was
        if was != now:
            return Failure(
                Layer.METADATA,
                f"{resolved.file} {resolved.section}: stored {field} is {was!r} but "
                f"resolves to {now!r}",
                "resolved metadata is machine-written; a disagreement means the source "
                "changed under a citation, or the field was edited by hand",
            )
    return None


def claims(root: pathlib.Path = BRAIN) -> list[tuple[pathlib.Path, dict[str, object]]]:
    """Every `.json` under the brain that carries a `status`."""
    found: list[tuple[pathlib.Path, dict[str, object]]] = []
    for path in sorted(root.rglob("*.json")):
        if SOURCES in path.parents:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CitationError(f"{path.relative_to(root)} is not valid JSON: {exc}") from exc
        if isinstance(record, dict) and "status" in record:
            found.append((path, record))
    return found


def run(root: pathlib.Path = BRAIN, registry: Registry | None = None) -> Result:
    """Verify every claim under `root`. The result is the whole truth about this tree."""
    registry = registry or Registry.load()
    result = Result()

    result.missing_documents = registry.missing()
    for document in registry:
        if document.present():
            result.failures.extend(f.render() for f in check_document(document))

    for path, record in claims(root):
        status = str(record.get("status", ""))
        result.tally[status] = result.tally.get(status, 0) + 1
        label = path.relative_to(root)

        if status not in ALL_STATUSES:
            result.failures.append(f"{label}: unknown status {status!r}")
            continue
        if status in HONEST_GAPS:
            continue

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            result.failures.append(f"{label}: VERIFIED but carries no evidence")
            continue

        for entry in evidence:
            result.citations += 1
            problems, _ = check_citation(entry, registry)
            if problems:
                result.failures.extend(f"{label}: {p.render()}" for p in problems)
            else:
                result.proven += 1

    return result


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = pathlib.Path(argv[0]).resolve() if argv else BRAIN

    try:
        result = run(root)
    except CitationError as exc:
        print(f"BLOCKED — {exc}")
        return 1

    for status, count in sorted(result.tally.items()):
        print(f"  {status:28} {count}")
    print(f"  {'claims total':28} {sum(result.tally.values())}")
    print(f"  {'citations proven':28} {result.proven}/{result.citations}")

    if result.missing_documents:
        print(f"\nBLOCKED — {len(result.missing_documents)} required document(s) missing:\n")
        for document in result.missing_documents:
            print(f"  {document.missing_report()}\n")

    if result.failures:
        print(f"BLOCKED — {len(result.failures)} unproven citation(s):")
        for line in result.failures:
            print(f"  {line}")

    if not result.ok:
        return 1

    print("\nevery VERIFIED claim proved its document, section, containment and text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
