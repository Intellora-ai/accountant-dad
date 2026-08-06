"""What a citation IS, and what makes one provable.

A citation is not a string. It is a claim that a specific span of text exists at
a specific place in a specific version of a specific document — and every part
of that claim has to be checkable independently, or the parts that are not
checkable are the parts that get fabricated.

THE FIVE LAYERS

    1  document    the file exists locally and its bytes hash to the recorded
                   value, so we are reading the version we think we are
    2  section     the cited section EXISTS in that document
    3  containment the quote lies INSIDE that section's span, not merely
                   somewhere in the file
    4  text        the quote matches the source exactly, under normalisation
                   rules that are declared rather than assumed
    5  ownership   the cited label BELONGS to that document's grammar — an
                   ICAI paragraph reference cited against the CGST Act is
                   wrong even if a matching string happens to exist

Layer 3 is the one whose absence let `CGST Act s.999` pass with an AS-9
dividend quote: the old check asked "does this text appear in this file",
which a 500,000-character Act answers yes to far too easily. Layers 2 and 5
are what make a section number falsifiable at all.

A failure in ANY layer is a failure. There is no partial credit, no warning
tier, and no "verified except for the section" state — a citation that is
wrong about where it came from is wrong, because the only thing a citation is
for is telling someone where to look.

STORED vs RESOLVED

Every evidence entry carries the full metadata: document, version, source URL,
checksum, section, quote, normalised text, character range, retrieval date,
evidence id. But almost none of it is hand-written. The author supplies the
three things only a human can know — WHICH document, WHICH section, WHAT the
quote is — and the rest is resolved from the manifest and computed from the
text.

The stored copy is then checked against the resolved copy on every run, and a
disagreement is a failure (`METADATA_DRIFT`). This is deliberate: a checksum
typed by hand into 700 places is 700 places to forget when a source is
re-fetched, and a stale checksum that nobody compares is indistinguishable
from a correct one. Machine-written, machine-compared, or it is decoration.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import re
import unicodedata

#: The author writes these. Nothing else about a citation is hand-typed.
AUTHORED_FIELDS = frozenset({"file", "section", "quote"})

#: Optional, still authored: finer location, and the record of an extraction
#: artifact that forced a quote to be split.
AUTHORED_OPTIONAL = frozenset({"subsection", "page", "paragraph", "extraction_note"})

#: Written by the verifier, compared on every run, never edited by hand.
RESOLVED_FIELDS = frozenset(
    {
        "version",
        "source_url",
        "checksum",
        "normalised",
        "char_range",
        "retrieved",
        "evidence_id",
    }
)


class Layer(enum.Enum):
    """Which proof failed. Ordered: a lower layer failing makes higher ones moot."""

    DOCUMENT = 1
    SECTION = 2
    CONTAINMENT = 3
    TEXT = 4
    OWNERSHIP = 5
    METADATA = 6


@dataclasses.dataclass(frozen=True, slots=True)
class Span:
    """A half-open character range `[start, end)` in a document's extracted text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"span start must not be negative, got {self.start}")
        if self.end < self.start:
            raise ValueError(f"span end {self.end} precedes start {self.start}")

    def contains(self, other: Span) -> bool:
        """True when `other` lies wholly inside this span."""
        return self.start <= other.start and other.end <= self.end

    def __len__(self) -> int:
        return self.end - self.start


@dataclasses.dataclass(frozen=True, slots=True)
class Failure:
    """One reason a citation is not proven. Carries enough to act on it."""

    layer: Layer
    message: str
    remedy: str = ""

    def render(self) -> str:
        line = f"[{self.layer.name}] {self.message}"
        return f"{line}\n      → {self.remedy}" if self.remedy else line


class CitationError(Exception):
    """A citation could not be structurally read at all — malformed, not merely wrong."""


#: Characters a PDF extractor substitutes for ordinary punctuation. Normalising
#: Written as escapes, not literals, on purpose. Several of these render
#: identically to the ASCII character they map to, so a literal table would be
#: one nobody could proofread — and this is the single place where mistaking an
#: en dash for a hyphen silently changes what counts as a match.
_TYPOGRAPHIC = {
    "\u2015": '"',  # HORIZONTAL BAR       these extractions open quotes with it
    "\u2016": '"',  # DOUBLE VERTICAL LINE  and close them with this
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH
    "\u2010": "-",  # HYPHEN
    "\u2011": "-",  # NON-BREAKING HYPHEN
    "\u00a0": " ",  # NO-BREAK SPACE
}

_TYPOGRAPHIC_RE = re.compile("|".join(map(re.escape, _TYPOGRAPHIC)))


def typographic_equivalents() -> dict[str, str]:
    """Plain character → every odd character that normalises to it.

    Public because `verify` needs it to build a raw-text search pattern, and
    reaching into `_TYPOGRAPHIC` from another module meant a function-level
    import to dodge the circularity — which cost a lint suppression, and a CI
    gate blocks any increase in those. Exposing the derived view is the honest
    fix: the table stays private, the fact other code needs is public.
    """
    equivalents: dict[str, str] = {}
    for odd, plain in _TYPOGRAPHIC.items():
        equivalents[plain] = equivalents.get(plain, "") + odd
    return equivalents


def normalise(text: str) -> str:
    """Collapse only what a PDF extractor legitimately mangles.

    Three things, and no others:

        whitespace     a PDF breaks lines where the PAGE broke, so the same
                       sentence arrives with different spacing on every extract
        typography     curly quotes, en/em dashes and non-breaking spaces are
                       rendering choices, not wording
        unicode form   NFKC, so a composed and a decomposed accent compare equal

    Casing, wording, punctuation that carries meaning, and digits are NEVER
    touched. `thirty days` and `forty-five days` must not normalise together,
    and neither must `plant or machinery` and `plant and machinery` — those two
    in particular decide real money in `s.17(5)(d)`.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _TYPOGRAPHIC_RE.sub(lambda m: _TYPOGRAPHIC[m.group()], text)
    return re.sub(r"\s+", " ", text).strip()


def evidence_id(document: str, section: str, quote: str) -> str:
    """A stable, content-derived id for one piece of evidence.

    Derived rather than assigned, so the same citation written twice in two
    files gets the same id, and an id can never silently point at a different
    quote than the one it was minted for.
    """
    digest = hashlib.sha256()
    for part in (document, section, normalise(quote)):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return f"EV-{digest.hexdigest()[:16]}"


@dataclasses.dataclass(frozen=True, slots=True)
class Citation:
    """One fully-resolved citation. Every field either authored or derived."""

    file: str
    section: str
    quote: str
    version: str
    source_url: str
    checksum: str
    normalised: str
    char_range: tuple[int, int]
    retrieved: str
    evidence_id: str
    subsection: str | None = None
    page: int | None = None
    paragraph: str | None = None
    extraction_note: str | None = None

    def to_entry(self) -> dict[str, object]:
        """The JSON shape stored in a claim file. Ordered for readable diffs."""
        entry: dict[str, object] = {
            "file": self.file,
            "section": self.section,
            "quote": self.quote,
        }
        for name in ("subsection", "page", "paragraph"):
            value = getattr(self, name)
            if value is not None:
                entry[name] = value
        entry["version"] = self.version
        entry["source_url"] = self.source_url
        entry["checksum"] = self.checksum
        entry["normalised"] = self.normalised
        entry["char_range"] = list(self.char_range)
        entry["retrieved"] = self.retrieved
        entry["evidence_id"] = self.evidence_id
        if self.extraction_note is not None:
            entry["extraction_note"] = self.extraction_note
        return entry
