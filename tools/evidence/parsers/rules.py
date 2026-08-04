"""The CGST Rules, whose numbering is a different language from the Act's.

An Act section reads `16. Eligibility and conditions...— (1)`; a Rule reads
`46. Tax invoice.-`. They look similar enough that one parser could be talked
into reading both, and that is exactly the mistake this file exists to prevent:
`s.16(2)` cited against the Rules must fail at LAYER 5 for the strong reason
that an Act section reference has no meaning inside the Rules, not for the weak
and accidental reason that no rule happens to carry that number.

WHY `strip_extraction_noise` IS NOT USED HERE

Every Rules label in this repository is written `CGST Rules 2017, rule 53(1A)(b)`
— document name, comma, reference, and sometimes a second comma and a gloss.
`strip_extraction_noise` splits on the FIRST comma, which on that shape returns
`CGST Rules 2017` and discards the reference entirely. So the label is parsed
here by an explicit grammar instead, which also lets `owns` be a real test
rather than "whatever survived stripping":

    [<document name containing "Rules">, ] rule <number> <path> [, <gloss>]

The gloss is the part that names a POSITION inside a rule — `proviso`,
`fourth proviso`, `Explanation`, `footnote 118`. A proviso is not a numbered
subdivision of anything; it is a sentence beginning "Provided that" somewhere
inside a rule that already has a number. There is nothing finer to resolve it
to, so it resolves to the rule that contains it, and containment is proved
against that rule. `46A` is a different matter: a letter glued to the number is
PART of the number, and rule 46A is a wholly separate rule from rule 46.

WHY THE HEADING GRAMMAR IS TIGHT RATHER THAN GENEROUS

The same `kind: "rules"` parser is handed three files, and one of them —
Part B — contains no rules at all, only 348 GST FORMS. Forms number their own
fields the same way rules number themselves (`11. Statement of facts:-`,
`5. Order no. -`), so a heading pattern loose enough to be comfortable finds
seventeen "rules" in a document that has none, and each one is a span hundreds
of thousands of characters wide that any quote in the file would sit inside.

Two discriminators separate them, and both are needed:

    a rule heading terminates `.-`, or `:-` / `. -` when sub-rule `(1)` follows
    the accepted headings must climb from rule 1 without ever going backwards

The second is not a tidiness rule. A numbered instrument starts at rule 1 and
counts up; a form's field list starts wherever that form starts. Part B's one
surviving candidate — `7. Whether any modification in the application for
registration or fields is required.- Yes` — is rejected because nothing before
it was rule 1, and with it goes a 900,000-character span that any quote in the
file would have sat inside.

Measured on the committed sidecars: 189 rules in Part A, 151 in the as-notified
2017 text, and ZERO in Part B. Part B therefore answers "no such rule" to every
citation, which is the truth about it.

One limit is inherited and stated rather than hidden: `spans_from_headings`
runs the LAST section to the end of the file, so in the as-notified text — which
prints its FORMS after its rules — rule 162 reaches to EOF. Part A, where every
citation in this repository points, is unaffected: its rules and its forms are
separate files. Bounding it would need a rules/forms boundary marker, and there
is none — `FORM GST REG-08` opens a wrapped line 52 times inside Part A's own
rule text, so a marker-based cut would slice rules in half.

WHY THE FIRST OCCURRENCE WINS HERE AND `pick_body_occurrence` DOES NOT

`base.pick_body_occurrence` resolves a repeated heading by taking the one with
the most text after it, because in an Act the repeat is a contents listing
PRINTED FIRST as one-liners. The Rules repeat headings for the opposite reason:
Part A appends superseded text under the words "The older versions of the rules
are given below", and rule 138 appears three times — operative at 441,988, then
the January-2018 version, then the original August-2017 version. Largest-gap
picks the OLDEST of the three. The climbing chain picks the operative one,
because the re-prints come after and go backwards. After the chain has run each
label is unique, so `spans_from_headings` still builds the spans and its
duplicate handling simply has nothing left to do.
"""

from __future__ import annotations

import functools
import re

from ..model import Span
from .base import SectionParser, spans_from_headings

#: Every character a PDF extractor has been observed to use for the dash that
#: closes a rule heading. Listing them is cheaper than normalising the whole
#: document before parsing it, and they are written as escapes because six of
#: the eight are indistinguishable from a hyphen on screen — which is exactly
#: how one of them goes missing from the list unnoticed.
_DASH = (
    "-"  # U+002D hyphen-minus
    "\u2010"  # hyphen
    "\u2011"  # non-breaking hyphen
    "\u2012"  # figure dash
    "\u2013"  # en dash
    "\u2014"  # em dash
    "\u2015"  # horizontal bar
    "\u2212"  # minus sign
)

#: `[ <number>. <title>.-` — the shape of a rule heading.
#:
#: The leading brackets are the Rules' own convention for text inserted or
#: substituted by a later notification (`[46A.`, `[[[67A.`), and a bracket may
#: also sit between the number and the title (`11.  [Separate registration`).
#: A title carries no `.` or `:` of its own, which is what keeps footnote prose
#: (`Notf. No. 27/2017`) from being read as one, and it may wrap over up to
#: four lines because the extractor breaks where the PAGE broke.
_HEADING = re.compile(
    r"(?m)^[ \t]*\[{0,3}[ \t]*"
    r"(?P<number>\d{1,3}[A-Z]{0,2})[ \t]*\.[ \t]*\[{0,3}[ \t]*"
    r"(?P<title>[A-Z][^.:\n]{0,150}(?:\n[^.:\n]{0,150}){0,3}?)"
    r"(?:"
    rf"\.[{_DASH}]"
    rf"|[.:][ \t]*[{_DASH}][ \t\n]*(?=\(1\))"
    r")"
)

#: `(1)`, `(1A)` — a sub-rule, at the start of its own line.
_SUBRULE_LINE = re.compile(r"(?m)^[ \t]*\[{0,2}[ \t]*\((?P<token>\d{1,2}[A-Z]?)\)")

#: The same marker where it follows the heading on the heading's own line,
#: which is how most rules open: `53.  Revised tax invoice...-(1)A revised`.
#: Anchored by `Pattern.match` at the end of the heading, so it carries no `^`
#: of its own — `^` would mean the start of the whole document.
_SUBRULE_INLINE = re.compile(r"[ \t\n]*\[{0,2}[ \t]*\((?P<token>\d{1,2}[A-Z]?)\)")

#: `(a)`, `(c )`, `(ix)` — a clause. The tolerated space before the closing
#: bracket is real: rule 53(1)(c) is extracted as `(c )`.
#:
#: The line-start anchor is not decoration. Without it 55 spurious clauses
#: appear, and they are the ones that matter most: rule 19(1) contains
#: `Provided that (en dash)(a) where the change relates to,-`, and an
#: unanchored pattern promotes that proviso limb to a clause of the sub-rule.
_CLAUSE_LINE = re.compile(r"(?m)^[ \t]*\[{0,2}[ \t]*\([ \t]*(?P<token>[a-z]{1,5})[ \t]*\)")

#: The same marker where it opens the container instead of a line, which is how
#: rule 24 writes `(2)(a) Every person who has been granted...` and rule 54
#: writes `[(1A) (a) A registered person...`. Without this the first clause of
#: such a sub-rule is unreachable while every later one resolves — the kind of
#: gap that looks like the parser working.
_CLAUSE_INLINE = re.compile(r"[ \t]*\[{0,2}[ \t]*\([ \t]*(?P<token>[a-z]{1,5})[ \t]*\)")

#: A parenthesised number that is part of a sentence rather than the start of
#: a provision — `sub-section (1) of section 39` wrapping onto a fresh line.
#: A real sub-rule or clause never begins with any of these words.
_CONTINUATION = re.compile(r"[ \t]*(?:of|to|or|and|in)\b", re.IGNORECASE)

#: `[ <document name>, ] rule <number><path> [, <gloss>]`.
#:
#: The document name, when present, must itself contain the word "rule" —
#: `CGST Act 2017, rule 46` is a label that contradicts itself and is rejected
#: rather than half-read. The `rule` keyword is REQUIRED: a bare `46` is
#: indistinguishable from an Act section, and accepting it would let
#: `Section 46` be laundered into a rule reference by a prefix strip.
_LABEL = re.compile(
    r"""^\s*
    (?:(?P<document>[^()]*?rules?[^()]*?)\s*,\s*)?
    (?:rules?|r\.)\s*
    (?P<number>\d{1,3}[ \t]*[A-Za-z]{0,2})
    (?P<path>(?:[ \t]*\([ \t]*[0-9A-Za-z]{1,6}[ \t]*\))*)
    (?P<gloss>\s*,.*)?
    \s*$""",
    re.VERBOSE | re.IGNORECASE | re.DOTALL,
)

_PATH_STEP = re.compile(r"\([ \t]*([0-9A-Za-z]{1,6})[ \t]*\)")

#: Clause letters, in the order the Rules use them.
_LETTERS = tuple("abcdefghijklmnopqrstuvwxyz")

#: Clause roman numerals, in the order the Rules use them. Rule 55(1) runs to
#: (ix); the extra headroom costs nothing and removes a cliff.
_ROMANS = (
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
    "xiii",
    "xiv",
    "xv",
    "xvi",
    "xvii",
    "xviii",
    "xix",
    "xx",
    "xxi",
    "xxii",
    "xxiii",
    "xxiv",
    "xxv",
    "xxvi",
    "xxvii",
    "xxviii",
    "xxix",
    "xxx",
)


class RulesParser(SectionParser):
    """Sections of the CGST Rules: rules, sub-rules and clauses."""

    kind = "rules"
    label_form = (
        "rule 46, rule 46(b), rule 53(1A)(b), rule 46A — optionally prefixed "
        "with the document name (CGST Rules 2017, rule 50) and optionally "
        "followed by a position gloss (, fourth proviso)"
    )

    def owns(self, label: str) -> bool:
        """True only for a reference the Rules' own numbering can express."""
        return _LABEL.match(label) is not None

    def canonical(self, label: str) -> str:
        """`CGST Rules 2017, rule 53(1A)(b)` and `r. 53 (1a) (B)` → `53(1A)(b)`.

        The document name and the position gloss are dropped: neither selects a
        rule, and a proviso is proved against the rule that contains it. An
        unparseable label is returned with its whitespace collapsed and nothing
        else done to it, so it fails the section lookup instead of being
        massaged into something that might accidentally match.
        """
        match = _LABEL.match(label)
        if match is None:
            return " ".join(label.split())

        number = re.sub(r"\s+", "", match.group("number"))
        digits = number[: len(number) - len(number.lstrip("0123456789"))]
        suffix = number[len(digits) :].upper()
        steps = [_normalise_step(s) for s in _PATH_STEP.findall(match.group("path") or "")]
        return digits + suffix + "".join(f"({s})" for s in steps)

    def sections(self, text: str) -> dict[str, Span]:
        """Every rule, sub-rule and clause in `text`.

        Deeper spans are the point. `53` is 4,000 characters; `53(1A)(b)` is
        forty, and a quote that has to sit inside forty characters cannot be
        proved by accident.
        """
        return dict(_parse(text))


def _normalise_step(step: str) -> str:
    """`1a` → `1A`, `B` → `b`, `IX` → `ix`.

    Sub-rules carry an uppercase letter suffix (`1A`); clauses are lowercase.
    Which one a step is follows from whether it starts with a digit, so the
    spelling never has to be guessed at lookup time.
    """
    return step[0] + step[1:].upper() if step[0].isdigit() else step.lower()


@functools.lru_cache(maxsize=4)
def _parse(text: str) -> tuple[tuple[str, Span], ...]:
    """Parse once per document. `verify` asks for sections on every citation."""
    headings = _rule_headings(text)
    rules = spans_from_headings(text, [(label, start) for label, start, _ in headings])
    body_of = {start: body for _, start, body in headings}

    found: dict[str, Span] = dict(rules)
    for label, span in rules.items():
        body = body_of.get(span.start, span.start)
        found.update(_subdivide(text, label, span, body))
    return tuple(found.items())


def _rule_headings(text: str) -> list[tuple[str, int, int]]:
    """Rule headings as `(number, start, end-of-heading)`, in document order.

    Every candidate that matches the heading shape is offered to a chain that
    starts at rule 1 and only ever climbs. A candidate that would go backwards
    is not a rule of this instrument: it is a superseded re-print in an
    appendix, or a numbered field inside a form. Either way the document has
    already said what rule that text belongs to, and it is not this one.
    """
    chain: list[tuple[str, int, int]] = []
    last = (0, "")
    for match in _HEADING.finditer(text):
        number = match.group("number")
        rank = _rank(number)
        opens_the_instrument = rank == (1, "")
        continues_the_chain = bool(chain) and rank > last
        if not (continues_the_chain or (not chain and opens_the_instrument)):
            continue
        chain.append((number, match.start(), match.end()))
        last = rank
    return chain


def _rank(number: str) -> tuple[int, str]:
    """`46A` → `(46, "A")`, so `46A` sorts after `46` and before `47`."""
    digits = number[: len(number) - len(number.lstrip("0123456789"))]
    return int(digits), number[len(digits) :].upper()


def _subdivide(text: str, rule: str, span: Span, body: int) -> dict[str, Span]:
    """Sub-rules of one rule, and the clauses of each."""
    subrules = _subrule_starts(text, body, span.end)
    if not subrules:
        return _clauses(text, rule, body, span.end)

    found: dict[str, Span] = {}
    for index, (token, start, after) in enumerate(subrules):
        end = subrules[index + 1][1] if index + 1 < len(subrules) else span.end
        label = f"{rule}({_normalise_step(token)})"
        found[label] = Span(start, end)
        found.update(_clauses(text, label, after, end))
    return found


def _subrule_starts(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    """Sub-rule markers, as `(token, start, end-of-marker)`, in document order.

    A sub-rule opens either at the start of a line or immediately after the
    heading, and the numbers must climb from `(1)` one step at a time. That
    chain is what rejects a `(2)` that is really the tail of `sub-section (2)
    of section 31` wrapped onto a fresh line: it is out of sequence, or it is
    followed by a word no provision begins with.
    """
    candidates: list[tuple[str, int, int]] = []
    inline = _SUBRULE_INLINE.match(text, start, end)
    if inline is not None:
        candidates.append((inline.group("token"), inline.start(), inline.end()))
    for match in _SUBRULE_LINE.finditer(text, start, end):
        if match.start() == (candidates[0][1] if candidates else -1):
            continue
        candidates.append((match.group("token"), match.start(), match.end()))
    candidates.sort(key=lambda item: item[1])

    chain: list[tuple[str, int, int]] = []
    last = (0, "")
    for token, at, after in candidates:
        rank = _rank(token)
        if rank <= last or rank[0] > last[0] + 1:
            continue
        if _CONTINUATION.match(text, after, min(after + 12, end)):
            continue
        chain.append((token, at, after))
        last = rank
    return chain


def _clauses(text: str, parent: str, start: int, end: int) -> dict[str, Span]:
    """Clauses of one container, resolving `(i)` between letter and roman.

    `(i)` is the ninth letter and the first roman numeral, and the Rules use
    both — rule 53(1) runs (a)…(j) with (i) among them, while rule 55(1) runs
    (a)…(d) and then (i)…(ix). Guessing per marker gets one of them wrong.

    Instead both sequences are built as RUNS: letters must arrive a, b, c… and
    romans must arrive i, ii, iii…, each stopping at its first gap. Runs that
    do not touch the same marker are both real, which is how rule 55(1) keeps
    (a)…(d) AND (i)…(ix).

    When they DO touch the same marker, the letters win, and not by preference:
    a letter run can only reach `i` by having already produced `a` through `h`
    in order, which no accidental list does. Rule 50 is the case — its roman
    "run" is the letter clause (i) followed by a (ii) that belongs to a proviso,
    so the whole roman reading is dropped rather than patched, and rule 50 ends
    up with no `(ii)` at all. That is correct: a proviso is not a clause list.
    """

    def usable(match: re.Match[str]) -> bool:
        return not _CONTINUATION.match(text, match.end(), min(match.end() + 12, end))

    markers: list[tuple[str, int, int]] = []
    opening = _CLAUSE_INLINE.match(text, start, end)
    if opening is not None and usable(opening):
        markers.append((opening.group("token"), opening.start(), opening.end()))
    markers += [
        (match.group("token"), match.start(), match.end())
        for match in _CLAUSE_LINE.finditer(text, start, end)
        if usable(match) and match.start() != (markers[0][1] if markers else -1)
    ]
    markers.sort(key=lambda item: item[1])

    letters = _run(markers, _LETTERS)
    romans = _run(markers, _ROMANS)

    if {at for _, at, _ in letters} & {at for _, at, _ in romans}:
        romans = []

    chosen = sorted(letters + romans, key=lambda item: item[1])
    found: dict[str, Span] = {}
    for index, (token, at, _) in enumerate(chosen):
        stop = chosen[index + 1][1] if index + 1 < len(chosen) else end
        found[f"{parent}({token})"] = Span(at, stop)
    return found


def _run(
    markers: list[tuple[str, int, int]], sequence: tuple[str, ...]
) -> list[tuple[str, int, int]]:
    """The longest prefix of `sequence` that `markers` supplies in order."""
    accepted: list[tuple[str, int, int]] = []
    expected = 0
    for token, at, after in markers:
        if expected < len(sequence) and token == sequence[expected]:
            accepted.append((token, at, after))
            expected += 1
    return accepted
