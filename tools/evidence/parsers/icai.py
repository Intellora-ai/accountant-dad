"""ICAI's grammar: dotted paragraphs, a restarting appendix, and page headers
that are indistinguishable from paragraph numbers by shape alone.

An accounting standard numbers itself `8.4`, not `16(2)(a)`, so the base class's
parenthesis-stripping `ancestors` never reaches `8` from `8.4` and is overridden
here. That much is obvious from one line of the text. Three things are not.

THE PAGE-HEADER TRAP

A running page header in these extractions reads

    134   AS  9 (issued  1985)

and a paragraph heading reads

    134.  Some provision...

The only difference is a full stop, and the full stop is not reliable: AS-1's
paragraph 20 lost its own in extraction —

    20                                     It would be helpful to the reader...

so a parser that demands the stop drops a real paragraph, and one that does not
demand it invents paragraph 134. Both failures are silent. A hardcoded list of
page numbers would fix this file and break the next one.

The transform is to stop asking what a heading LOOKS like and ask where it sits.
Paragraph numbers in a standard form one ascending run from 1; page numbers,
footnote markers and mid-sentence digits do not join that run. So candidates are
walked in document order and each is accepted only if it is the next number at
its level, or the first number one level deeper. That single rule removes, with
no per-document knowledge:

    134   AS  9 (issued  1985)      page header    — 134 does not follow 8
    1982 and  was titled'Prior...   footnote wrap  — 1982 does not follow nothing
    12  are  satisfied, provided    a sentence of paragraph 10 that wrapped onto
                                    a new line beginning with a cross-reference
                                    to paragraph 12 — and would otherwise have
                                    become a second, earlier, wrong `12`

and keeps AS-1's paragraph 20 despite its missing stop, because 20 follows 19.

THE RESTARTING APPENDIX

AS 9's appendix restarts at `1.` and reaches `9.`, so its items collide with the
body's paragraphs 1-9. The sequence rule already refuses them — after paragraph
14 the next number is 15, not 1 — but that leaves paragraph 14 owning the whole
appendix, which would let an appendix quote pass as a paragraph-14 quote. The
appendix is therefore cut off structurally at its own `APPENDIX` line and parsed
under its own labels, `Appendix A.9`.

SPANS NEST, DELIBERATELY

`SectionParser.sections` says spans must not overlap. That cannot hold for a
document whose numbering is hierarchical while `ancestors` — in the base class
itself — resolves `16(2)(a)` to `16(2)` to `16`: if `16`'s span stopped at
`16(1)`, proving a citation at the fallback level would prove almost nothing.
So "to the start of the next" is read here as the next heading at the SAME OR
SHALLOWER level, which makes every span cover its own body including its
children, and makes the set a hierarchy rather than a partition. `para 13`
is checked against all of paragraph 13; `para 13(iii)` against that clause
alone. Both are correct and the narrower one is used when it is cited. This is a
deviation from the letter of the base docstring and is recorded rather than
resolved by editing it.

THE CONTENTS LISTING IS A NAMED SPAN, NOT A REJECTED LABEL

`AS 9 contents listing` cites the word `Disclosure`. One word, occurring four
times in the file, so "somewhere in this document" proves nothing about it —
which is exactly the check this package exists to replace.

The contents block is a physically bounded region: from the `Contents` line to
the last line carrying a page or paragraph reference. It therefore has a
determinate span, and containment is checked against 1,074 characters instead of
27,674. Naming it is the STRICTER option, not the looser one — it adds a boundary
the quote must sit inside, and a paragraph-14 quote mis-cited as the contents
listing now fails, measured. Rejecting the label would have removed a provable
fact rather than an unprovable one, and would have left the author with nowhere
honest to record it.

The block is only named where it can be bounded, which is what keeps this from
becoming a guessed window: if a file's contents entries carry no references,
there are no entries to end the span at, no `contents listing` key exists, and a
citation to one fails at the SECTION layer.

WHAT THIS PARSER STILL DOES NOT BOUND

A document's LAST numbered paragraph runs to the end of the file, so unnumbered
trailing matter falls inside it — the ASB Announcement's paragraph 7 is two lines
of text followed by 12.5 KB of annexure, and the annexure has no heading of any
shape to cut on. Inventing a boundary would be guessing; the over-reach is left
visible instead. Nothing cites it today.
"""

from __future__ import annotations

import functools
import re

from ..model import Span
from .base import SectionParser, pick_body_occurrence

#: A heading candidate: a dotted number at the start of a line, an optional full
#: stop, then text. Deliberately permissive on all three counts — the stop is
#: unreliable (AS 1's paragraph 20 lost its own) and so is the indent (the
#: Preface prints `  1.    Formation of the Accounting Standards Board` two
#: columns in while printing `4.` flush left, and the 2019 compendium indents its
#: entire body thirteen). Shape never decides; `_accept` does, which is what
#: makes it safe to over-collect here. Measured: at indent budgets of 6, 15, 20
#: and unlimited, all six single-standard and pronouncement files parse to
#: exactly the same paragraph sets, so the widest is chosen — it costs nothing
#: and it is the only one that reads the 2019 compendium at all.
_HEADING = re.compile(r"(?m)^[ \t]*(\d+(?:\.\d+)*)\.?[ \t]+(?=\S)")

#: A clause marker inside a paragraph. Both forms occur: AS 9 prints `(iii)`
#: (sometimes as `(v )`, with the space the extractor left behind) and AS 1
#: prints `a.` at the margin. Both are cited as `(a)` / `(iii)`.
_CLAUSE = re.compile(r"(?m)^[ \t]*(?:\(\s*([a-z]+)\s*\)|([a-z])\.)[ \t]+(?=\S)")

#: The appendix boundary. The word alone on its line — it also appears as a
#: contents entry, which is why the occurrence is chosen by position, not shape.
_APPENDIX = re.compile(r"(?m)^[ \t]*APPENDIX[ \t]*$")

#: An appendix group: `A.     Sale    of  Goods`.
_APPENDIX_GROUP = re.compile(r"(?m)^[ \t]*([A-Z])\.[ \t]{2,}(?=\S)")

#: An appendix item: `9.   Trade   discounts    and  volume    rebates`. The stop
#: is required here — it is what separates an item from the page header `138`
#: that sits in the middle of the appendix.
_APPENDIX_ITEM = re.compile(r"(?m)^[ \t]*(\d+)\.[ \t]+(?=\S)")

#: The contents heading, and a contents entry — text, a gutter, a page number or
#: a paragraph range. The dashes are written as escapes because an en dash and a
#: hyphen are indistinguishable on screen, and a range that silently stopped
#: matching would shrink the contents span without saying so.
_CONTENTS = re.compile(r"(?mi)^[ \t]*contents[ \t]*$")
_CONTENTS_ENTRY = re.compile(
    r"(?m)^[ \t]*\S.*?\S[ \t]{3,}\d+(?:[ \t]*[-\u2013\u2014][ \t]*\d+)?[ \t]*$"
)

#: A footnote, as this extractor renders one: the superscript digit fuses with
#: the first word of the note. `5Refer to AS 7 on ...`. Nothing else in these
#: files puts a digit flush against a letter at the start of a line, which is
#: what keeps page headers and paragraph numbers out — both are followed by
#: whitespace.
_FOOTNOTE = re.compile(r"(?m)^[ \t]*(\d{1,2})(?=[A-Za-z])")

#: The document's own title, used to learn which standard a file IS. A prose
#: cross-reference always continues with a comma and a name, so requiring the
#: line to END at the number separates `Accounting Standard (AS) 9` the heading
#: from `Accounting Standard (AS) 15, Employee Benefits` the mention.
_AS_TITLE = re.compile(r"(?m)^[ \t]*Accounting\s+Standard\s*\(\s*AS\s*\)\s*(\d+)[^\w\n]*$")

#: The one spelling of a reference. Everything after the match is a positional
#: gloss — `, definition of prior period items`, ` Going Concern` — which names
#: a place inside the paragraph and is not part of the label.
_LABEL = re.compile(
    r"""
    ^\s*
    (?:\bAS\b[ \t.]*(?P<std>\d{1,2})\b[ \t,]*)?
    (?:
        (?P<contents>contents[ \t]+listing)
      | footnote[ \t]+(?P<fn>\d+)
        (?:[ \t]+to[ \t]+para(?:graph)?\.?[ \t]*
           (?P<fnpara>\d+(?:\.\d+)*)(?P<fnclauses>(?:[ \t]*\([ \t]*[a-z]+[ \t]*\))*))?
      | [Aa]ppendix[ \t]+(?P<app>[A-Za-z])\.(?P<appitem>\d+)
      | para(?:graph)?\.?[ \t]*(?P<para>\d+(?:\.\d+)*)
        (?P<clauses>(?:[ \t]*\([ \t]*[a-z]+[ \t]*\))*)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CLAUSE_TOKEN = re.compile(r"\(\s*([a-z]+)\s*\)", re.IGNORECASE)

#: The highest AS number ICAI has issued. Used only to read a title whose
#: number has a footnote marker glued to it — `(AS) 91` is AS 9 with footnote 1,
#: because there is no AS 91.
_MAX_STANDARD = 32

_ALPHA: tuple[str, ...] = tuple("abcdefghijklmnopqrstuvwxyz")


def _roman(number: int) -> str:
    """Lowercase roman numeral. Clause series run `(i)`, `(ii)`, `(iii)`, ..."""
    pairs = ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))
    out: list[str] = []
    for value, glyph in pairs:
        count, number = divmod(number, value)
        out.append(glyph * count)
    return "".join(out)


_ROMAN: tuple[str, ...] = tuple(_roman(n) for n in range(1, 41))


# ── the sequence rule ──────────────────────────────────────────────────────


def _candidates(text: str, start: int, end: int) -> list[tuple[tuple[int, ...], int]]:
    """Every heading-shaped line in `[start, end)`, as (components, offset)."""
    return [
        (tuple(int(part) for part in match.group(1).split(".")), match.start())
        for match in _HEADING.finditer(text, start, end)
    ]


def _opening_level(path: tuple[int, ...], nxt: dict[tuple[int, ...], int]) -> int | None:
    """The depth at which `path` opens a new node, or None if it is not a heading.

    A component either CONTINUES the node already open at its level — it equals
    the last number accepted there — or OPENS the next one, equalling that
    number plus one. Anything else is not part of the run: a page number, a
    footnote marker, or a sentence that happened to begin with a digit. Below
    the level that opens, every remaining component must be the first at its own
    level, because a section cannot begin at its third sub-paragraph.
    """
    opened: int | None = None
    for depth, value in enumerate(path):
        expected = nxt.get(path[:depth], 1)
        if value == expected:
            opened = depth
            break
        if value != expected - 1:
            return None
    if opened is None:
        return None  # every component merely repeated the open path
    for depth in range(opened + 1, len(path)):
        if path[depth] != nxt.get(path[:depth], 1):
            return None
    return opened


def _accept(candidates: list[tuple[tuple[int, ...], int]]) -> list[tuple[tuple[int, ...], int]]:
    """Keep only the candidates that form the document's ascending numbering."""
    accepted: list[tuple[tuple[int, ...], int]] = []
    nxt: dict[tuple[int, ...], int] = {}
    for path, offset in candidates:
        opened = _opening_level(path, nxt)
        if opened is None:
            continue
        accepted.append((path, offset))
        for depth in range(opened, len(path)):
            nxt[path[:depth]] = path[depth] + 1
    return accepted


def _hierarchy(
    accepted: list[tuple[tuple[int, ...], int]], end: int
) -> list[tuple[tuple[int, ...], Span, Span]]:
    """Each node as (path, full span, own span).

    The full span reaches the next heading at the same or shallower level, so it
    covers the node's children. The own span stops at the next heading of any
    level, so clause scanning inside a parent does not re-read its children.
    """
    out: list[tuple[tuple[int, ...], Span, Span]] = []
    for index, (path, offset) in enumerate(accepted):
        following = accepted[index + 1 :]
        closes = next((o for p, o in following if len(p) <= len(path)), end)
        own_end = following[0][1] if following else end
        out.append((path, Span(offset, closes), Span(offset, min(own_end, closes))))
    return out


# ── clauses ────────────────────────────────────────────────────────────────


def _clause_series(tokens: list[str]) -> int:
    """How many leading tokens form a valid clause run.

    A run starts at `a` or at `i` and every later token is the next in whichever
    of the two series it started. `a` is only ever alphabetic and `i` is only
    ever the first roman numeral, so the series is settled by the first token and
    never ambiguous — AS 1's `(a)`...`(j)` reaches `(i)` at position nine and
    stays alphabetic.
    """
    if not tokens:
        return 0
    if tokens[0] == _ALPHA[0]:
        series = _ALPHA
    elif tokens[0] == _ROMAN[0]:
        series = _ROMAN
    else:
        return 0
    length = 1
    while length < len(tokens) and length < len(series) and tokens[length] == series[length]:
        length += 1
    return length


def _clauses(text: str, region: Span, end: int) -> list[tuple[str, Span]]:
    """Clause spans inside one paragraph's own text, `(a)` / `(iii)` labelled."""
    marks = [
        ((match.group(1) or match.group(2)).lower(), match.start())
        for match in _CLAUSE.finditer(text, region.start, region.end)
    ]
    kept = marks[: _clause_series([token for token, _ in marks])]
    out: list[tuple[str, Span]] = []
    for index, (token, offset) in enumerate(kept):
        closes = kept[index + 1][1] if index + 1 < len(kept) else min(region.end, end)
        out.append((f"({token})", Span(offset, max(offset, closes))))
    return out


# ── the body of one standard ───────────────────────────────────────────────


def _appendix_start(text: str, start: int, end: int, last_heading: int) -> int:
    """Where the appendix begins, or `end` when there is none.

    `APPENDIX` appears twice — once as a contents entry, once as the real
    boundary — so the occurrence is chosen by position: the real one is the
    first that follows the document's last numbered paragraph.
    """
    for match in _APPENDIX.finditer(text, start, end):
        if match.start() > last_heading:
            return match.start()
    return end


def _contents_span(text: str, start: int, first_heading: int) -> Span | None:
    """The contents block, from its heading to its last entry with a reference."""
    header = _CONTENTS.search(text, start, first_heading)
    if header is None:
        return None
    entries = list(_CONTENTS_ENTRY.finditer(text, header.end(), first_heading))
    if not entries:
        return None
    return Span(header.start(), entries[-1].end())


def _appendix_sections(text: str, start: int, end: int) -> dict[str, Span]:
    """`Appendix A`, `Appendix A.9`, and any clauses inside an appendix item."""
    groups = _accept_letters(text, start, end)
    sections: dict[str, Span] = {}
    for index, (letter, offset) in enumerate(groups):
        closes = groups[index + 1][1] if index + 1 < len(groups) else end
        sections[f"Appendix {letter}"] = Span(offset, closes)
        found = _APPENDIX_ITEM.finditer(text, offset, closes)
        items = _accept([((int(match.group(1)),), match.start()) for match in found])
        for path, span, own in _hierarchy(items, closes):
            label = f"Appendix {letter}.{path[0]}"
            sections[label] = span
            for token, clause in _clauses(text, own, closes):
                sections[f"{label}{token}"] = clause
    return sections


def _accept_letters(text: str, start: int, end: int) -> list[tuple[str, int]]:
    """Appendix group letters, accepted only as the run `A`, `B`, `C`, ..."""
    out: list[tuple[str, int]] = []
    for match in _APPENDIX_GROUP.finditer(text, start, end):
        letter = match.group(1)
        if letter == chr(ord("A") + len(out)):
            out.append((letter, match.start()))
    return out


def _footnote_sections(
    text: str, start: int, end: int, headings: list[tuple[str, Span]]
) -> dict[str, Span]:
    """`footnote 5`, and `footnote 5 to para 2(i)` where the reference is found.

    The qualified form is emitted only when the superscript marker that hangs
    the note off the text can be located inside a parsed section. That makes the
    `to para` half of the label falsifiable rather than decorative: a note cited
    against the wrong paragraph has no key and fails at the SECTION layer.
    """
    marks = [(match.group(1), match.start()) for match in _FOOTNOTE.finditer(text, start, end)]
    stops = sorted([offset for _, offset in marks] + [span.start for _, span in headings] + [end])
    sections: dict[str, Span] = {}
    for number, offset in marks:
        closes = next((s for s in stops if s > offset), end)
        sections[f"footnote {number}"] = Span(offset, closes)
        host = _footnote_host(text, number, offset, headings)
        if host is not None:
            sections[f"footnote {number} to {host}"] = Span(offset, closes)
    return sections


def _footnote_host(
    text: str, number: str, note: int, headings: list[tuple[str, Span]]
) -> str | None:
    """The narrowest section holding the superscript that calls this footnote.

    A superscript sits flush against the word it follows — `contracts;5` — so the
    character before it is never a space and never a digit. It is also never the
    tail of a dotted number: `paragraph 4.3` ends in a `3` that is otherwise
    shaped exactly like a call to footnote 3, and taking it as one attached AS 9's
    footnote 3 to paragraph 1 when the note in fact hangs off the preamble. A
    false attachment is worse than none, because it is a key that passes.
    """
    reference = re.compile(rf"(?<=[^\s\d])(?<!\d\.){re.escape(number)}(?![\d.])")
    calls = [match.start() for match in reference.finditer(text, 0, note)]
    if not calls:
        return None
    call = Span(calls[-1], calls[-1] + len(number))
    holding = [(len(span), label) for label, span in headings if span.contains(call)]
    return min(holding)[1] if holding else None


@functools.lru_cache(maxsize=512)
def _body_sections(text: str, start: int, end: int) -> dict[str, Span]:
    """Every section of one standard: paragraphs, clauses, contents, appendix.

    Keys are unqualified — `para 8.3`, `Appendix A.9` — because the same body
    grammar is used for a standalone standard, for one standard inside the
    compendium, and for a pronouncement. Only the caller knows what to prefix.
    """
    accepted = _accept(_candidates(text, start, end))
    if not accepted:
        return {}
    boundary = _appendix_start(text, start, end, accepted[-1][1])
    accepted = [(path, offset) for path, offset in accepted if offset < boundary]
    if not accepted:
        return {}

    sections: dict[str, Span] = {}
    for path, span, own in _hierarchy(accepted, boundary):
        label = "para " + ".".join(str(part) for part in path)
        sections[label] = span
        for token, clause in _clauses(text, own, boundary):
            sections[f"{label}{token}"] = clause

    contents = _contents_span(text, start, accepted[0][1])
    if contents is not None:
        sections["contents listing"] = contents
    if boundary < end:
        sections.update(_appendix_sections(text, boundary, end))
    sections.update(_footnote_sections(text, start, end, sorted(sections.items())))
    return sections


@functools.lru_cache(maxsize=64)
def _standard_number(text: str, start: int, end: int) -> int | None:
    """Which AS this region IS, read from its own title rather than its filename."""
    numbers = [_title_number(match.group(1)) for match in _AS_TITLE.finditer(text, start, end)]
    found = [number for number in numbers if number is not None]
    if not found:
        return None
    return max(set(found), key=found.count)


def _title_number(digits: str) -> int | None:
    """`9` from `(AS) 9`, and `9` from `(AS) 91` where the `1` is a footnote."""
    for length in range(len(digits), 0, -1):
        value = int(digits[:length])
        if 1 <= value <= _MAX_STANDARD:
            return value
    return None


# ── labels ─────────────────────────────────────────────────────────────────


def _parse(label: str) -> tuple[int | None, str] | None:
    """(standard number or None, canonical position) — or None if not ICAI."""
    match = _LABEL.match(label)
    if match is None:
        return None
    standard = int(match["std"]) if match["std"] else None
    return standard, _position(match)


def _position(match: re.Match[str]) -> str:
    """The canonical spelling of the position half of a label."""
    if match["contents"]:
        return "contents listing"
    if match["fn"]:
        note = f"footnote {int(match['fn'])}"
        if not match["fnpara"]:
            return note
        return f"{note} to para {match['fnpara']}{_clause_suffix(match['fnclauses'])}"
    if match["app"]:
        return f"Appendix {match['app'].upper()}.{int(match['appitem'])}"
    return f"para {match['para']}{_clause_suffix(match['clauses'])}"


def _clause_suffix(raw: str | None) -> str:
    """`(ii)` from ` (ii)`, `( ii )` or `(v )` — the extractor produces all three."""
    if not raw:
        return ""
    return "".join(f"({token.group(1).lower()})" for token in _CLAUSE_TOKEN.finditer(raw))


def _position_ancestors(position: str) -> list[str]:
    """A position and each enclosing level, finest first.

    `para 7.1(ii)` yields `para 7.1(ii)` then `para 7.1`, and STOPS there.

    Clauses are stripped because clause markers are recovered heuristically from
    a mangled layout, so a clause this parser failed to see should still prove at
    its paragraph rather than fail outright.

    Dotted components are NOT stripped, because they are the document's own
    primary numbering and the sequence rule parses them completely — every
    paragraph of AS 1, AS 5 and AS 9 is recovered with no gaps. If `para 7.2` is
    absent it is because AS 9 has no paragraph 7.2, and falling back to
    paragraph 7 would let a citation to a paragraph that does not exist pass on
    its parent's text. Measured: allowing that fallback let 27 of 207 quotes
    re-cited at a non-existent neighbouring sub-paragraph still pass. Refusing it
    lets none.

    A footnote that names the paragraph it hangs off does not fall back to the
    bare footnote either: the attachment is part of what the citation asserts.
    """
    if position.startswith("Appendix "):
        return [position, position.split(".")[0]]
    if position.startswith("footnote ") or position == "contents listing":
        return [position]
    chain = [position]
    trimmed = position
    while (match := re.match(r"^(.*?)\([^()]*\)$", trimmed)) and match.group(1):
        trimmed = match.group(1)
        chain.append(trimmed)
    return chain


class _IcaiParser(SectionParser):
    """What the three ICAI grammars share: one numbering, three ways to name it."""

    #: True when the label must carry `AS N`, False when it must not, None when
    #: the prefix is optional because the file is itself one standard.
    requires_standard: bool | None = None

    def owns(self, label: str) -> bool:
        parsed = _parse(label)
        if parsed is None:
            return False
        standard, _ = parsed
        if self.requires_standard is True:
            return standard is not None
        if self.requires_standard is False:
            return standard is None
        return True

    def canonical(self, label: str) -> str:
        parsed = _parse(label)
        if parsed is None:
            return label.strip()
        standard, position = parsed
        return f"AS {standard} {position}" if standard is not None else position

    def ancestors(self, label: str) -> list[str]:
        parsed = _parse(label)
        if parsed is None:
            return [label.strip()]
        standard, position = parsed
        chain = _position_ancestors(position)
        return chain if standard is None else [f"AS {standard} {step}" for step in chain]


class StandardParser(_IcaiParser):
    """One standard, one file. `AS 9 para 8.3`, or `para 8.3` for short.

    The `AS 9` prefix identifies the FILE rather than a section inside it, but it
    is still checked: the number is read from the document's own title, so
    `AS 5 para 11` cited against the AS-9 file finds no key and fails. That is a
    real error — the words of AS 5 paragraph 11 are not in this file at all — and
    it is worth catching at the section layer rather than waiting for the quote
    to happen not to match.
    """

    kind = "icai_standard"
    label_form = (
        "`AS 9 para 8.3`, `AS 9 para 7.1(ii)`, `AS 9 Appendix A.9`, `AS 9 contents listing`"
    )
    requires_standard = None

    def sections(self, text: str) -> dict[str, Span]:
        sections = _body_sections(text, 0, len(text))
        number = _standard_number(text, 0, len(text))
        if number is None:
            return sections
        return sections | {f"AS {number} {label}": span for label, span in sections.items()}


class CompendiumParser(_IcaiParser):
    """AS 1 to AS 29 in one file, so a label MUST say which standard.

    A bare `para 9` is not under-specified, it is twenty-nine different
    paragraphs, and choosing one of them would be the parser guessing on the
    author's behalf. It is rejected at the ownership layer instead.
    """

    kind = "icai_compendium"
    label_form = "`AS 22 para 9` — the standard is required, a bare `para 9` is ambiguous here"
    requires_standard = True

    def sections(self, text: str) -> dict[str, Span]:
        return _compendium_sections(text)


class PronouncementParser(_IcaiParser):
    """The Preface, the Framework, an ASB Announcement — not standards.

    These number themselves like a standard does (`4.3`, `5.11`) but they are not
    AS anything, so `AS 9 para 4.3` cited against the Preface is a citation to a
    different document and is refused at the ownership layer.
    """

    kind = "icai_pronouncement"
    label_form = "`paragraph 22`, `para 4.3` — no `AS N` prefix; a pronouncement is not a standard"
    requires_standard = False

    def sections(self, text: str) -> dict[str, Span]:
        return _body_sections(text, 0, len(text))


@functools.lru_cache(maxsize=8)
def _compendium_sections(text: str) -> dict[str, Span]:
    """Every standard's sections in one table, qualified by standard.

    Cached whole. Parsing 2.2 MB of compendium costs 3.3 seconds and the verifier
    asks for this table once per citation, so an uncached call would be paid
    hundreds of times. Measured: 3272 ms cold, 0.27 ms warm.
    """
    sections: dict[str, Span] = {}
    for number, region in _standard_regions(text):
        for label, span in _body_sections(text, region.start, region.end).items():
            sections[f"AS {number} {label}"] = span
    return sections


@functools.lru_cache(maxsize=8)
def _standard_regions(text: str) -> list[tuple[int, Span]]:
    """Where each standard's body lives inside a compendium.

    Every standard is titled twice — once on its divider page, once above the
    text — so the body occurrence is chosen the same way the base class chooses
    a body section over its contents entry: by which one is followed by more
    text before the next title.

    The titles are found as the LONGEST ASCENDING RUN of candidates, not as a
    strict successor chain. Two reasons, both measured. Standards are not
    contiguous — AS 6 and AS 8 stand withdrawn, so the file jumps 7 to 9, and
    demanding the next integer stopped the parse at AS 7 and lost every standard
    after it. And the compendium's front matter quotes standard titles in prose
    before any standard begins; those quotations do not ascend, so the real
    sequence is simply the longest run that does.
    """
    runs: list[list[tuple[int, int]]] = [[]]
    for match in _AS_TITLE.finditer(text):
        number = _title_number(match.group(1))
        if number is None:
            continue
        if runs[-1] and number < runs[-1][-1][0]:
            runs.append([])
        runs[-1].append((number, match.start()))

    titles: dict[int, list[int]] = {}
    for number, offset in max(runs, key=len):
        titles.setdefault(number, []).append(offset)

    starts = sorted(offset for offsets in titles.values() for offset in offsets)
    chosen = {
        number: pick_body_occurrence(offsets, starts, len(text))
        for number, offsets in titles.items()
    }
    ordered = sorted(chosen.items(), key=lambda item: item[1])
    return [
        (number, Span(offset, ordered[index + 1][1] if index + 1 < len(ordered) else len(text)))
        for index, (number, offset) in enumerate(ordered)
    ]
