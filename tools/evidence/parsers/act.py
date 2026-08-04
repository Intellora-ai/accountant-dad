"""The Act grammar: numbered sections, nested clauses, and schedules.

An Indian Act numbers itself in exactly one way and every citation to it is a
walk down that numbering:

    16                      the section
    16(2)                   the sub-section
    16(2)(a)                the clause
    17(5)(aa)(i)(A)         and as deep as the drafter went

Schedules are NOT part of that sequence. `Schedule II, Part C, paragraph 5` of
the Companies Act is not section 2, and a parser that treats schedule numbering
as section numbering will resolve it to the wrong span and then prove a quote
against text it never came from. Schedules are therefore first-class here, with
their own heading grammar (`SCHEDULE II`, `PART 'A'`, `1.`, `Notes.—`, roman
item numbers) and their own canonical spelling.

WHAT A LABEL IS ALLOWED TO SAY, AND WHAT IS DECORATION

Real labels in this repository carry four kinds of decoration around the number
that actually locates the text:

    CGST Act s.17(5), opening words
    ^^^^^^^^          ^^^^^^^^^^^^^
    document name     position INSIDE the section, not a different section

    CGST Act s.16(2), second proviso (source B, IndiaCode text as on 11-06-2026)
                      ^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      comma gloss    parenthesised gloss

None of that changes WHICH section is cited, so none of it may survive
canonicalisation — otherwise `s.17(5)` and `s.17(5), opening words` become two
different sections and one of them does not exist.

The dangerous half is the parenthesis. `(source B, ...)` must be discarded and
`(5)(i)` must not, and both are trailing parentheses. Rather than discriminate
negatively — "strip a parenthesis if it looks like prose" — this parser reads
the label POSITIVELY: after the document name and the `s.`/`Section` marker,
it matches the longest run of `number` followed by immediately-adjacent
`(token)` groups, where a token is at most four alphanumerics with no space.
The match stops at the first character that cannot be part of a number, so
every gloss — comma-led, space-led or parenthesised — is left behind without
ever being described. A clause reference cannot be lost, because a clause
reference is precisely what the grammar accepts.

`base.strip_extraction_noise` is deliberately NOT used. It splits on the first
comma, which is correct for `s.16(2), the possession limb` and destroys
`Schedule II, Part A, paragraph 1`; and it strips a leading `rule`/`para`,
which would make `rule 46(b)` look like an Act reference and defeat layer 5.

THE TABLE-OF-CONTENTS TRAP

Both the CGST Act and the Companies Act print a full contents listing before the
body in the same `N. Title` form as the real sections. `pick_body_occurrence`
answers this by gap, and on these files that is necessary but not sufficient —
it was measured, not assumed, and it failed twice. `_body_headings` below states
both failures and what settles them. `spans_from_headings` is still what turns
the chosen headings into spans; only the CHOICE of occurrence is made here.

WHY SPANS NEST

`SectionParser.locate` walks `16(2)(a)` → `16(2)` → `16` and proves containment
against the first level it finds. That walk is only sound if a section's span
CONTAINS its sub-sections' spans. A flat partition — where `16` covers only the
heading line up to `(1)` — would fail every citation written at section level
against text that lives in a sub-section, which is most of them. Sibling spans
never overlap; a parent always encloses its children.
"""

from __future__ import annotations

import bisect
import dataclasses
import functools
import re

from ..model import Span
from .base import SectionParser, spans_from_headings

#: How deep a clause chain may go before the parser stops trusting itself.
#: `17(5)(aa)(i)(A)` is the deepest real reference in this repository; five
#: levels leaves one spare and stops a run of stray parentheses in a table from
#: manufacturing sections nobody wrote.
_MAX_DEPTH = 5

#: Document names an author may reasonably put in front of the section number.
#: A CLOSED list on purpose: a permissive prefix would let `AS 9 s.11` through
#: layer 5, which is the exact failure this parser exists to make impossible.
_DOCUMENT_NAME = re.compile(
    r"^(?:the\s+)?"
    r"(?:C?GST|SGST|IGST|UTGST|Companies|Income[-\s]?tax"
    r"|Central\s+Goods\s+and\s+Services\s+Tax"
    r"|Integrated\s+Goods\s+and\s+Services\s+Tax)"
    r"(?:\s+Act)?(?:,?\s*\d{4})?[\s,]+",
    re.IGNORECASE,
)

#: `s.`, `s `, `Section`, `Sec.`, … — longest alternative first so `section 128`
#: is not consumed as a bare `s`. A digit is REQUIRED after it, which is what
#: keeps `Schedule II` from being read as `S` + `chedule II`.
_SECTION_LABEL = re.compile(
    r"^(?:sections|section|secs|sec|ss|s)\s*\.?\s*(\d{1,3}[A-Z]{0,2})((?:\([0-9A-Za-z]{1,4}\))*)",
    re.IGNORECASE,
)

_SCHEDULE_LABEL = re.compile(r"^schedule\s+([IVXLC]{1,6}|\d{1,2})\b", re.IGNORECASE)

#: The numbering series that live inside a schedule. They are separate series —
#: `paragraph 5` and `Note 5` are different places — so the series word is part
#: of the canonical spelling rather than something to normalise away.
_SERIES_NAME = {
    "para": "paragraph",
    "paragraph": "paragraph",
    "note": "Note",
    "notes": "Note",
    "item": "item",
    "clause": "clause",
}

#: What may follow `Schedule II`, read POSITIONALLY rather than by splitting on
#: commas: an optional part, then an optional numbered series, then whatever
#: gloss the author added. Reading it this way makes the result idempotent —
#: `canonical(canonical(x)) == canonical(x)` — which a comma split cannot be,
#: because canonicalisation removes the commas it would need to split on again.
_SCHEDULE_TAIL = re.compile(
    r"^(?:part\s*['\u2018\"]?\s*(?P<part>[A-Za-z]{1,4})['\u2019\"]?\b)?"
    r"\s*(?:(?P<series>para|paragraph|notes|note|item|clause)\s*\.?\s*"
    r"(?P<number>\d{1,3}[A-Z]?|[IVXLC]{1,6})(?P<clauses>(?:\([0-9A-Za-z]{1,4}\))*))?",
    re.IGNORECASE,
)

_SERIES_TAIL = re.compile(r"\s+(?:paragraph|Note|item|clause)\s+\S+$")
_PART_TAIL = re.compile(r"\s+Part\s+\S+$")

#: A section heading: the number at the left margin, then a Title-Case title
#: that ends in a full stop — followed by the em dash that OPENS THE PROVISION
#: in the body, or by end of line in the contents listing. Both forms are
#: collected, and the `dash` group is what tells them apart.
#:
#: The title length is bounded because an Act's schedules contain numbered
#: PARAGRAPHS that also begin `1. Some sentence.` — the bound plus the schedule
#: exclusion below keeps those out of the section table.
_SECTION_HEADING = re.compile(
    r"(?m)^[ \t]{0,12}(?P<number>\d{1,3}[A-Z]{0,2})\.[ \t]+"
    r"(?=[A-Z\u201c\u2018])[^\n]{2,150}?\.[ \t]*(?:(?P<dash>[\u2014\u2013-])|$)"
)

#: A schedule heading. In the contents listing it carries a trailing full stop
#: (`SCHEDULE II.`, Companies Act) or a page number (`SCHEDULE II      198`,
#: CGST Act); in the body it stands alone on its line. The `contents` group is
#: what tells them apart.
_SCHEDULE_HEADING = re.compile(
    r"(?m)^[ \t]*SCHEDULE[ \t]+([IVXLC]{1,6})\b(?P<contents>[ \t]*\.|[ \t]+\d{1,4})?[ \t]*$"
)

_PART_HEADING = re.compile(
    r"(?m)^[ \t]*PART[ \t]*['\u2018\"]?[ \t]*([A-Z]{1,4})['\u2019\"]?[ \t]*"
    r"(?:[.\u2014\u2013-][^\n]*)?$"
)

#: `Notes.—` splits a schedule part into its paragraph series and its note
#: series. Both restart at 1, so without this marker `paragraph 1` and `Note 1`
#: collide and one of them silently wins.
_NOTES_HEADING = re.compile(r"(?m)^[ \t]*Notes?[ \t]*\.?[ \t]*[\u2014\u2013-]")

#: A numbered entry inside a schedule: `5.`, `1[4(a)`, or the roman item numbers
#: of the Companies Act depreciation table (`XII.`).
_SCHEDULE_ENTRY = re.compile(
    r"(?m)^[ \t]{0,14}(?:\d{0,2}\[)?"
    r"(?:(?P<num>\d{1,3})(?:\.[ \t]+(?=\S)|(?P<clause>\([a-z]{1,3}\))[ \t]*(?=\S))"
    r"|(?P<roman>[IVXL]{1,6})\.[ \t]+(?=\S))"
)

#: Sub-section (1) is not at the left margin. Every one of these Acts runs it on
#: from the heading — `128. Books of account, etc., to be kept by company.—(1)
#: Every company shall` — so a line-anchored marker never sees it, and the
#: consequences reach further than one missing span: with (1) absent, `(a)` to
#: `(d)` open the FIRST level, and the `(2)` that resumes the real first level
#: then continues nothing and opens nothing, so (2) onward are dropped too.
#: Measured: the whole of CGST s.18 and Companies s.129 proved only at section
#: level until this was read.
_OPENING_MARKER = re.compile(r"\.[ \t]*[\u2014\u2013-][ \t]*(?:\d{0,2}\[)?\(([0-9A-Za-z]{1,4})\)")

#: A clause marker at the left margin. The optional `N[` prefix is the footnote
#: bracket these extractions carry into the text — `4[(3) The Board of Directors`
#: is sub-section (3), not sub-section 4.
_MARKER = re.compile(r"(?m)^[ \t]{0,28}(?:\d{0,2}\[)?\(([0-9A-Za-z]{1,4})\)[ \t]")

_ROMAN_UNITS: tuple[tuple[int, str], ...] = (
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)


class ActParser(SectionParser):
    """Sections, sub-sections, clauses and schedules of an Act."""

    kind = "act"
    label_form = "s.16, Section 128(1), CGST Act s.17(5)(i), or Schedule II, Part C, paragraph 5"

    def owns(self, label: str) -> bool:
        """True only for Act-shaped references.

        An Act reference always names its unit: `s.`/`Section` before a number,
        or the word `Schedule`. That requirement is what rejects `rule 46(b)`
        and `AS 9 para 11` at layer 5 — with the stronger message that the
        reference belongs to another document's grammar — rather than letting
        them fall through to layer 2 and fail merely for not existing.
        """
        rest = _without_document_name(label)
        return bool(_SCHEDULE_LABEL.match(rest) or _SECTION_LABEL.match(rest))

    def canonical(self, label: str) -> str:
        """One spelling per section, with every gloss removed and no clause lost."""
        rest = _without_document_name(label)
        return _canonical_schedule(rest) or _canonical_section(rest) or " ".join(label.split())

    def ancestors(self, label: str) -> list[str]:
        """`label` and each enclosing level, finest first.

        Schedules do not nest by parentheses alone — `Schedule II Part C Note 3`
        encloses `Note 3(i)` but is itself enclosed by `Schedule II Part C` and
        then `Schedule II`, none of which the default parenthesis walk can see.
        Emitting the full chain is what lets a paragraph-level citation still be
        proven at part level, and REPORTED at part level, when the paragraph
        grammar does not reach it.
        """
        canonical = self.canonical(label)
        if not canonical.startswith("Schedule "):
            return super().ancestors(label)

        chain = [canonical]
        trimmed = canonical
        while (match := re.match(r"^(.*?)\([^()]*\)$", trimmed)) and match.group(1):
            trimmed = match.group(1)
            chain.append(trimmed)
        for pattern in (_SERIES_TAIL, _PART_TAIL):
            shorter = pattern.sub("", trimmed)
            if shorter != trimmed:
                trimmed = shorter
                chain.append(trimmed)
        return chain

    def sections(self, text: str) -> dict[str, Span]:
        """Every section, sub-section, clause and schedule division in `text`."""
        return dict(_parse(text))


# ── label canonicalisation ────────────────────────────────────────────────


def _without_document_name(label: str) -> str:
    """`CGST Act s.17(5)` → `s.17(5)`. Whitespace collapsed, nothing else touched."""
    return _DOCUMENT_NAME.sub("", " ".join(label.split()), count=1).strip()


def _canonical_section(rest: str) -> str:
    """`s.17(5), opening words` → `17(5)`. Empty string when this is not a section."""
    match = _SECTION_LABEL.match(rest)
    return f"{match.group(1)}{match.group(2)}" if match else ""


def _canonical_schedule(rest: str) -> str:
    """`Schedule II, Part C, Note 3(i)` → `Schedule II Part C Note 3(i)`.

    Reads the part and the numbered series in the only order a schedule can
    print them, and stops at the first thing that is neither. `Schedule II,
    footnote 1 to paragraph 3` therefore canonicalises to `Schedule II` — a
    footnote names a position inside the schedule, and the `paragraph 3` inside
    its own wording is the footnote's prose, not a level to descend into.
    """
    match = _SCHEDULE_LABEL.match(rest)
    if not match:
        return ""

    parts = [f"Schedule {match.group(1).upper()}"]
    tail = _SCHEDULE_TAIL.match(rest[match.end() :].replace(",", " ").strip())
    if tail is None:
        return parts[0]
    if tail.group("part"):
        parts.append(f"Part {tail.group('part').upper()}")
    if tail.group("series"):
        name = _SERIES_NAME[tail.group("series").lower()]
        parts.append(f"{name} {tail.group('number')}{tail.group('clauses')}")
    return " ".join(parts)


# ── document parsing ──────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class _Level:
    """One open level of the clause stack: what it last saw, and its full label."""

    token: str
    label: str


@dataclasses.dataclass(frozen=True, slots=True)
class _Markers:
    """Every left-margin clause marker in a document, with a searchable index."""

    tokens: list[str]
    positions: list[int]

    def within(self, span: Span) -> list[tuple[str, int]]:
        lo = bisect.bisect_left(self.positions, span.start)
        hi = bisect.bisect_left(self.positions, span.end)
        return list(zip(self.tokens[lo:hi], self.positions[lo:hi], strict=True))


@functools.lru_cache(maxsize=8)
def _parse(text: str) -> dict[str, Span]:
    """Every span in one document. Cached: the verifier asks once per citation."""
    schedules = _body_headings(
        [
            (f"Schedule {match.group(1).upper()}", match.start(), not match.group("contents"))
            for match in _SCHEDULE_HEADING.finditer(text)
        ]
    )
    schedule_spans = spans_from_headings(text, schedules) if schedules else {}

    sections = _body_headings(
        [
            (match.group("number"), match.start(), bool(match.group("dash")))
            for match in _SECTION_HEADING.finditer(text)
            if not _inside_any(match.start(), schedule_spans)
        ]
    )

    top = spans_from_headings(text, sections + schedules)
    matches = list(_MARKER.finditer(text))
    markers = _Markers(
        tokens=[match.group(1) for match in matches],
        positions=[match.start() for match in matches],
    )

    spans = dict(top)
    for label, span in top.items():
        children = (
            _schedule_children(text, label, span, markers)
            if label.startswith("Schedule ")
            else _clause_children(label, span, markers, _opening_marker(text, span))
        )
        for child, child_span in children.items():
            _keep_widest(spans, child, child_span)
    return spans


def _opening_marker(text: str, span: Span) -> tuple[str, int] | None:
    """The run-on `(1)` on a heading line, as a marker the clause stack can use."""
    line_end = text.find("\n", span.start, span.end)
    match = _OPENING_MARKER.search(text, span.start, line_end if line_end != -1 else span.end)
    return (match.group(1), match.start(1) - 1) if match else None


def _body_headings(candidates: list[tuple[str, int, bool]]) -> list[tuple[str, int]]:
    """Of every occurrence of a heading, the one that begins the real provision.

    `pick_body_occurrence` decides this by gap — a contents entry is followed
    almost immediately by the next contents entry, a body heading by the
    provision. That holds INSIDE a dense contents block and breaks at its edge.
    Two failures were measured on the real files, not assumed:

        SCHEDULE III is the LAST line of the CGST Act's contents listing, so
        its gap to the next schedule heading is the 456,000 characters of the
        Act itself. It won on gap, the whole Act parsed as a schedule, and
        165 sections collapsed to 3.

        `6. Subs. by Act 8 of 2023, s. 138, for "added to his output tax
        liability…".` is a FOOTNOTE, and it has the same shape as a contents
        entry: number, stop, capitalised text, stop. It ended section 16 three
        sub-sections early, and 16(3) to 16(6) belonged to nothing.

    Typography settles the first without gap arithmetic. A body section heading
    is followed by the em dash that opens the provision; a contents entry ends
    at the line. A body schedule heading stands alone on its line; a contents
    entry carries a full stop or a page number. Where a label has such an
    occurrence the EARLIEST one is the heading — later ones are the running
    header repeated at the top of each page.

    Position settles the second. A contents listing is printed ONCE, before the
    body; a footnote block is interleaved with it. So an occurrence that lacks
    the body marker and sits after the body has started is not a heading of any
    kind, and is dropped rather than allowed to cut a section in half.

    Where a document has no body-marked heading at all, every occurrence is
    passed through and `pick_body_occurrence` decides — which is the case its
    gap rule is correct for.
    """
    grouped: dict[str, list[tuple[int, bool]]] = {}
    for label, start, is_body in candidates:
        grouped.setdefault(label, []).append((start, is_body))

    marked = [start for _, start, is_body in candidates if is_body]
    body_begins = min(marked) if marked else None

    chosen: list[tuple[str, int]] = []
    for label, occurrences in grouped.items():
        bodies = [start for start, is_body in occurrences if is_body]
        if bodies:
            chosen.append((label, min(bodies)))
            continue
        contents = [start for start, _ in occurrences if body_begins is None or start < body_begins]
        chosen.extend((label, start) for start in contents)
    return chosen


def _inside_any(position: int, spans: dict[str, Span]) -> bool:
    """True when `position` falls inside any of `spans`.

    Used to keep a schedule's numbered PARAGRAPHS out of the section table.
    Without it, `1. Depreciation is the systematic allocation ... by the
    entity.` in Schedule II reads as a section heading numbered 1, and can win
    the body-occurrence contest against the real section 1.
    """
    return any(span.start <= position < span.end for span in spans.values())


def _keep_widest(spans: dict[str, Span], label: str, span: Span) -> None:
    """On a repeated label, keep the occurrence covering the most text.

    Same principle as `pick_body_occurrence`, applied one level down: a heading
    that repeats because a running header or a re-extracted page duplicated it
    produces a short span, and the real provision produces a long one.
    """
    existing = spans.get(label)
    if existing is None or len(span) > len(existing):
        spans[label] = span


def _schedule_children(text: str, prefix: str, span: Span, markers: _Markers) -> dict[str, Span]:
    """Parts, paragraphs, notes and items inside one schedule.

    A part label is taken ONCE. Companies Act Schedule III prints `PART I` twice
    — once per Division — and letting the second block contribute entries under
    the same prefix put `Part I paragraph 3(2)` 70,000 characters outside `Part
    I paragraph 3`, breaking the containment the ancestor walk depends on.
    """
    headings = [
        (f"{prefix} Part {m.group(1).upper()}", m.start())
        for m in _PART_HEADING.finditer(text, span.start, span.end)
    ]
    blocks: list[tuple[str, Span]] = []
    taken: set[str] = set()
    for label, block in _blocks(headings, span):
        if label not in taken:
            taken.add(label)
            blocks.append((label, block))
    if not blocks:
        blocks = [(prefix, span)]

    children: dict[str, Span] = {}
    for label, block in blocks:
        if label != prefix:
            children.setdefault(label, block)
        for entry, entry_span in _schedule_entries(text, label, block).items():
            children.setdefault(entry, entry_span)
            opening = _entry_opening(text, entry_span)
            for clause, clause_span in _clause_children(
                entry, entry_span, markers, opening
            ).items():
                children.setdefault(clause, clause_span)
    return children


def _entry_opening(text: str, span: Span) -> tuple[str, int] | None:
    """The clause an amended schedule entry runs on from its own number.

    Companies Act Schedule II prints note 4 as `1[4(a) Useful life specified in
    Part C…` — the `(a)` is part of the entry's own heading, so the margin scan
    never sees it and `(b)` on the next line has nothing to follow.
    """
    match = _SCHEDULE_ENTRY.match(text, span.start)
    if match is None or not match.group("clause"):
        return None
    return match.group("clause").strip("()"), match.start("clause")


def _schedule_entries(text: str, prefix: str, block: Span) -> dict[str, Span]:
    """The numbered entries of one schedule part, in their own series."""
    notes_at = _NOTES_HEADING.search(text, block.start, block.end)
    boundary = notes_at.start() if notes_at else block.end

    headings: list[tuple[str, int]] = []
    for match in _SCHEDULE_ENTRY.finditer(text, block.start, block.end):
        if match.group("roman"):
            headings.append((f"{prefix} item {match.group('roman')}", match.start()))
            continue
        series = "Note" if match.start() >= boundary else "paragraph"
        headings.append((f"{prefix} {series} {match.group('num')}", match.start()))

    # FIRST occurrence wins, not widest. A schedule's page footers repeat the
    # same `1.` `2.` `3.` amendment notes lower down the part, and those trail
    # to the part's end, so "widest" hands `paragraph 1` to a footnote and the
    # real paragraph 1 stops existing. Measured on Companies Act Schedule II.
    entries: dict[str, Span] = {}
    for label, span in _blocks(headings, block):
        entries.setdefault(label, span)
    return entries


def _blocks(headings: list[tuple[str, int]], span: Span) -> list[tuple[str, Span]]:
    """Ordered headings into flat sibling spans covering `span`."""
    ordered = sorted(headings, key=lambda pair: pair[1])
    return [
        (label, Span(start, ordered[index + 1][1] if index + 1 < len(ordered) else span.end))
        for index, (label, start) in enumerate(ordered)
    ]


def _clause_children(
    prefix: str, span: Span, markers: _Markers, opening: tuple[str, int] | None = None
) -> dict[str, Span]:
    """The nested `(1)(a)(i)(A)` chain inside one section, part or paragraph.

    Depth is decided by SEQUENCE, not by the shape of the token. `(i)` after
    `(h)` continues the clause letters; `(i)` after `(b)` opens a roman
    sub-clause. Asking "is this token roman or alphabetic" has no answer;
    asking "does this token follow the one this level last saw" always does.

    `opening` is the run-on marker printed on the heading line rather than at
    the margin, and it is prepended so that the first level starts where the
    drafter started it.
    """
    entries: list[tuple[str, int, int]] = []
    stack: list[_Level] = []
    found = markers.within(span)
    if opening is not None and (not found or opening[1] < found[0][1]):
        found = [opening, *found]

    for token, position in found:
        continued = _continued_level(stack, token)
        if continued is not None:
            del stack[continued + 1 :]
            parent = prefix if continued == 0 else stack[continued - 1].label
            stack[continued] = _Level(token, f"{parent}({token})")
        elif not stack:
            stack.append(_Level(token, f"{prefix}({token})"))
        elif len(stack) < _MAX_DEPTH and _opens_a_level(token):
            stack.append(_Level(token, f"{stack[-1].label}({token})"))
        else:
            continue
        entries.append((stack[-1].label, position, len(stack)))

    return _nested_spans(entries, span)


def _continued_level(stack: list[_Level], token: str) -> int | None:
    """The deepest open level `token` continues, or None when it opens a new one."""
    for index in range(len(stack) - 1, -1, -1):
        if _follows(stack[index].token, token):
            return index
    return None


def _nested_spans(entries: list[tuple[str, int, int]], span: Span) -> dict[str, Span]:
    """Close every entry at the next entry of the same or shallower depth.

    This is what makes a parent contain its children: `16(2)` ends where `(3)`
    begins, not where `(a)` begins, so `16(2)(a)` lies inside it.
    """
    ends = [span.end] * len(entries)
    open_indexes: list[int] = []
    for index, (_, start, depth) in enumerate(entries):
        while open_indexes and entries[open_indexes[-1]][2] >= depth:
            ends[open_indexes.pop()] = start
        open_indexes.append(index)

    spans: dict[str, Span] = {}
    for (label, start, _), end in zip(entries, ends, strict=True):
        _keep_widest(spans, label, Span(start, end))
    return spans


# ── token sequences ───────────────────────────────────────────────────────


def _opens_a_level(token: str) -> bool:
    """True for the first token of any of the four numbering sequences."""
    return token in {"1", "a", "A", "i", "I"}


def _follows(previous: str, current: str) -> bool:
    """True when `current` is the next token after `previous` in some sequence."""
    return (
        _numeric_follows(previous, current)
        or _alphabetic_follows(previous, current)
        or _roman_follows(previous, current)
    )


def _numeric_follows(previous: str, current: str) -> bool:
    """`1`→`2`, and the inserted-section forms `1`→`1A`, `1A`→`1B`, `1A`→`2`."""
    before = re.fullmatch(r"(\d+)([A-Z]*)", previous)
    after = re.fullmatch(r"(\d+)([A-Z]*)", current)
    if not before or not after:
        return False
    if int(after.group(1)) == int(before.group(1)) + 1 and not after.group(2):
        return True
    return int(after.group(1)) == int(before.group(1)) and _letters_follow(
        before.group(2).lower(), after.group(2).lower()
    )


def _alphabetic_follows(previous: str, current: str) -> bool:
    """`a`→`b`, and the inserted-clause forms `a`→`aa`, `aa`→`ab`, `ab`→`b`."""
    if not (previous.isalpha() and current.isalpha()):
        return False
    if previous.isupper() != current.isupper() or previous.islower() != current.islower():
        return False
    return _letters_follow(previous.lower(), current.lower())


def _letters_follow(previous: str, current: str) -> bool:
    """The letter sequence an Indian draftsman uses when inserting a clause."""
    if not previous:
        return current == "a"
    if not current:
        return False
    if len(current) == len(previous) and current[:-1] == previous[:-1]:
        return ord(current[-1]) == ord(previous[-1]) + 1
    if current == previous + "a":
        return True
    return len(current) == 1 and len(previous) > 1 and ord(current) == ord(previous[0]) + 1


def _roman_follows(previous: str, current: str) -> bool:
    """`i`→`ii`, `iv`→`v`, `II`→`III`. Same case, and both genuine numerals."""
    if previous.isupper() != current.isupper():
        return False
    before, after = _roman_value(previous), _roman_value(current)
    return before is not None and after is not None and after == before + 1


def _roman_value(token: str) -> int | None:
    """The value of a roman numeral, or None when `token` is not one.

    Round-trips through the canonical rendering so that `iiii` and `ic` are
    rejected rather than silently given a value — a parser that invents an
    ordering invents a containment proof with it.
    """
    lowered = token.lower()
    if not lowered or any(character not in "ivxlc" for character in lowered):
        return None
    value, index = 0, 0
    for amount, numeral in _ROMAN_UNITS:
        while lowered.startswith(numeral, index):
            value += amount
            index += len(numeral)
    return value if index == len(lowered) and _to_roman(value) == lowered else None


def _to_roman(value: int) -> str:
    rendered: list[str] = []
    for amount, numeral in _ROMAN_UNITS:
        while value >= amount:
            rendered.append(numeral)
            value -= amount
    return "".join(rendered)
