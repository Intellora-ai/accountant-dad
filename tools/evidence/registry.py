"""The manifest, promoted from a note to the architecture.

`manifest.jsonl` used to be a record of what happened to be downloaded. It is
now the declaration of what the repository REQUIRES: for every source, where it
came from, which version it is, what its bytes must hash to, and which grammar
parses its sections.

That change is what makes a fresh clone possible. Before, the set of documents
was whatever a previous session had left on one machine, and the verifier
silently reported success on a subset. Now the manifest is the authority: a
document in the manifest and absent from disk is a hard failure with the exact
command to fix it, never a quietly skipped check.

WHY THE TEXT SIDECAR IS COMMITTED AND THE PDF IS NOT

Verification reads the `.txt` sidecar, and the sidecar is committed, so results
are identical on every machine without depending on which PDF library happens
to be installed. The PDF itself is 42 MB of re-fetchable government bytes and is
fetched by `bootstrap`, which checks it against the manifest hash.

Both halves are needed. The sidecar alone would mean verifying my own extraction
against my own extraction — the checksum has to be able to reach the original
bytes, or nothing anchors the text to the government's copy.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
from collections.abc import Iterator

from .model import CitationError
from .parsers import build_parsers
from .parsers.base import SectionParser

BRAIN = pathlib.Path(__file__).resolve().parents[2] / "Accounting_Brain"
SOURCES = BRAIN / "Evidence_Library" / "sources"
MANIFEST = BRAIN / "Evidence_Library" / "manifest.jsonl"

BOOTSTRAP_COMMAND = "python3 -m tools.evidence.bootstrap"


@dataclasses.dataclass(frozen=True, slots=True)
class Document:
    """One required source, exactly as the manifest declares it."""

    file: str
    sha256: str
    url: str
    body: str
    kind: str
    #: Directory this document lives in. Carried per-document rather than read
    #: from a module global so a test can build a complete, disposable evidence
    #: tree of its own — §J.6, REAL + ISOLATED. A global here would mean every
    #: test either touched the real 42 MB corpus or monkeypatched around it, and
    #: both of those are how a suite starts proving the mock.
    root: pathlib.Path = SOURCES
    title: str = ""
    version: str = ""
    retrieved: str = ""
    bytes_: int | None = None
    defect: str = ""

    @property
    def path(self) -> pathlib.Path:
        return self.root / self.file

    @property
    def sidecar(self) -> pathlib.Path:
        return self.root / f"{self.file}.txt"

    def present(self) -> bool:
        """True when the original bytes are on disk. The sidecar is separate."""
        return self.path.is_file()

    def actual_sha256(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def text(self) -> str:
        """The extracted text this document's quotes are checked against."""
        if not self.sidecar.is_file():
            raise CitationError(
                f"{self.file} has no committed .txt sidecar. Verification reads the "
                f"sidecar so results do not depend on a PDF library version; extract "
                f"it once and commit the result."
            )
        return self.sidecar.read_text(encoding="utf-8", errors="replace")

    def missing_report(self) -> str:
        """Everything needed to obtain this document, stated rather than implied."""
        return (
            f"{self.file}\n"
            f"      source   {self.url}\n"
            f"      sha256   {self.sha256}\n"
            f"      bootstrap {BOOTSTRAP_COMMAND}"
        )


class Registry:
    """Every declared document, and the parser that reads each one's sections."""

    def __init__(self, documents: dict[str, Document], parsers: dict[str, SectionParser]):
        self._documents = documents
        self._parsers = parsers

    @classmethod
    def load(
        cls,
        manifest: pathlib.Path | None = None,
        sources: pathlib.Path | None = None,
        parsers: dict[str, SectionParser] | None = None,
    ) -> Registry:
        """The registry this repository declares, or a disposable one for a test.

        `sources` defaults beside the manifest when one is given, so pointing at
        a temporary manifest automatically points at that manifest's own tree —
        a test cannot half-escape into the real corpus by forgetting an argument.
        """
        path = manifest or MANIFEST
        root = sources if sources is not None else (path.parent / "sources")
        return cls(read_manifest(path, root), parsers if parsers is not None else build_parsers())

    def __iter__(self) -> Iterator[Document]:
        return iter(self._documents.values())

    def __len__(self) -> int:
        return len(self._documents)

    def get(self, filename: str) -> Document | None:
        return self._documents.get(filename)

    def parser_for(self, document: Document) -> SectionParser:
        parser = self._parsers.get(document.kind)
        if parser is None:
            raise CitationError(
                f"{document.file} declares kind {document.kind!r}, which no parser "
                f"implements. Known kinds: {', '.join(sorted(self._parsers))}. A "
                f"document whose sections cannot be parsed cannot be cited — add a "
                f"parser rather than loosening the check."
            )
        return parser

    def missing(self) -> list[Document]:
        return [d for d in self._documents.values() if not d.present()]


def read_manifest(path: pathlib.Path, root: pathlib.Path = SOURCES) -> dict[str, Document]:
    """Parse the manifest, refusing anything that would weaken a later proof."""
    if not path.is_file():
        raise CitationError(
            f"no manifest at {path}. The manifest declares which documents the "
            f"repository requires; without it nothing can be verified."
        )

    documents: dict[str, Document] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CitationError(f"{path.name} line {number} is not valid JSON: {exc}") from exc

        for required in ("file", "sha256", "url", "kind"):
            if not record.get(required):
                raise CitationError(
                    f"{path.name} line {number} has no {required!r}. Every declared "
                    f"document needs one; a missing field is an unverifiable source."
                )

        filename = str(record["file"])
        if filename in documents:
            raise CitationError(
                f"{path.name} declares {filename} twice. Two records for one file "
                f"means two possible checksums, and no way to say which is right."
            )

        documents[filename] = Document(
            file=filename,
            sha256=str(record["sha256"]),
            url=str(record["url"]),
            body=str(record.get("body", "")),
            kind=str(record["kind"]),
            root=root,
            title=str(record.get("title", "")),
            version=str(record.get("version", "")),
            retrieved=str(record.get("downloaded", "")),
            bytes_=record.get("bytes"),
            defect=str(record.get("defect", "")),
        )
    return documents
