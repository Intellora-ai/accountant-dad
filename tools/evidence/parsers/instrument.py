"""Four grammars for the four shapes a subordinate GST instrument arrives in.

An Act numbers itself `16. Eligibility ...— (1)` and an ICAI standard numbers
itself `8.4`. Nothing below the Act agrees with either, or with the others:

    notification    a preamble, then a TABLE whose rows are numbered `Sl. No.`,
                    sometimes split into rate `Schedule I … VII`, then a short
                    tail of numbered PARAGRAPHS. 11/2017 and 12/2017 are almost
                    entirely table; 11/2025 and ROD 02/2018 are entirely
                    paragraphs; 1/2017 and 9/2025 are six or seven schedules of
                    several hundred rows each and only one paragraph.
    rate_schedule   a GST Council rate table and nothing else. One serial
                    column, no numbered paragraphs, no operative text.
    circular        numbered paragraphs in dotted-decimal outline — `2`, `3.1`,
                    `3.1.2` — usually issue-then-clarification.
    guidance        a FAQ numbered `Q 12`, or (Rule 86A) prose in the same
                    dotted outline a circular uses.

Forcing one grammar onto all four is the hardcoding this package exists to
remove, so each parser gets the unit its document actually prints, and
`label_form` says which, verbatim, in the failure message.

WHY EVERY SCAN IS A SEQUENCE AND NOT A PATTERN MATCH

A pattern alone cannot tell `44 of the CGST Act, i.e. both FORM GSTR-9` from
paragraph 44, or a wrapped table cell reading `1.  Fish seeds` from row 1. Both
are a number at the start of a line. What separates them is not how they look
but where they sit: a serial column runs 1, 2, 3 … and an outline runs 2, 3,
3.1, 3.1.1, 3.2. So every scan here collects candidates by shape and then keeps
only those that CONTINUE THE SEQUENCE. That is a property of the document, not a
tuned constant, and it is why `2017`, `168` and `01.08.2021` — all real lines
from Circular 246/03/2025 — are rejected without naming any of them.

The same rule is what makes a missed heading fail loudly. A row the extractor
mangled is simply absent, so citing it fails at layer 2. It is never quietly
mapped to its neighbour.

WHAT THESE PARSERS DO NOT NARROW

Five honest limits, stated here rather than discovered later:

  1  A row's span runs from its serial to the next heading, so an unnumbered
     group header — `Tobacco and Tobacco Products` in the compensation cess
     table — falls inside the PRECEDING row rather than the following one.
     The same applies to the annexed `List 1 … List 3` of 1/2017, which land
     inside the last row of Schedule I.
  2  Where a document restarts its numbering (rate Schedules in 1/2017 and
     9/2025; chapters in the CBIC FAQ), the bare form is ambiguous and is
     therefore NOT registered. `Schedule III, Sl. No. 21` and `Chapter 3 Q 12`
     are required. A bare `Sl. No. 21` fails at layer 2 rather than resolving
     to whichever schedule happened to be scanned first.
  3  A label may carry the instrument's own identity — `Notification
     11/2017-CTR, Sl. No. 5`. The prefix is checked for SHAPE only. Nothing
     here can confirm it names the same document as the entry's `file` field,
     because a parser is handed text and never the document it came from. The
     `file` field remains the sole authority on which document is being cited.
  4  The last heading of a document runs to the end of the file — the interface
     defines it that way and there is nothing to end it at. Where a document
     appends matter with no numbering of its own, that last span is a weak
     narrowing. Two of these are bounded anyway, because the appended matter
     restarts a serial column and the restart becomes a boundary; nothing
     bounds a trailing signature block or annexure that carries no numbers.
  5  Measured across every section this module produces — 3,702 of them large
     enough to quote from — 3,700 proved a fragment taken from their own span.
     The two that did not are `Chapter 10 Q 27` and `Chapter 24 Q 2` of the GST
     FAQ, whose text contains U+2026 HORIZONTAL ELLIPSIS. `model.normalise`
     applies NFKC and expands it to three full stops, so the quote matches at
     layer 4; `verify._occurrences` then rebuilds its pattern from the
     normalised characters and searches the RAW text, where the ellipsis is
     still one character, and finds nothing. The citation fails LOUDLY at
     layer 3 with "nowhere the raw text can be indexed". It is a false
     negative in the verifier's raw re-indexing, not a wrong span here, and it
     is reported rather than worked around.

TWO DOCUMENTS ARE RECORDED AS DEFECTIVE

The manifest marks notifications 1/2017 and 2/2017 `SOURCE PDF IS TRUNCATED AS
SERVED`. Every heading these parsers report from them is real; the set is not
known to be complete. Nothing here can or should imply otherwise — a quote
found in a truncated file is found, and the ABSENCE of a section proves only
that the extraction does not contain it.
"""

from __future__ import annotations

import abc
import bisect
import re

from ..model import Span
from .base import SectionParser

# ── shapes ────────────────────────────────────────────────────────────────
#
# Each of these says only "this line COULD be a heading". The sequence rules
# below decide whether it is.

#: A page break precedes a heading whenever the heading opens a page, and the
#: extractor emits it as a form feed at the start of the line. `Schedule VI -
#: 0.125%` in 1/2017 is exactly this, and requiring plain spaces lost it.
_PAGE_BREAK = r"\f?"

#: The dashes a PDF extractor emits between a schedule and its rate. Written
#: as escapes rather than literals so the character class cannot be mistaken
#: for a hyphen by a reader or a linter.
_DASH = "[-\u2013\u2014]"

#: `Schedule III- 40%` on a line of its own. The rate is required: every real
#: banner in 1/2017 and 9/2025 carries one, and the lines that merely say
#: `Schedule V` are wrapped cell text quoting a schedule, not headings.
_SCHEDULE_BANNER = re.compile(
    rf"(?m)^{_PAGE_BREAK}[ \t]*Schedule[ \t]+([IVX]{{1,5}})"
    rf"[ \t]*{_DASH}?[ \t]*\d+(?:\.\d+)?[ \t]*%[ \t]*$"
)

#: A serial cell: a number at the far left, then the gap to the next column.
#: The indent bound is what separates a row from a numbered list INSIDE a cell,
#: which the extractor indents to the cell's own left edge.
_SERIAL_ROW = re.compile(rf"(?m)^{_PAGE_BREAK}[ \t]{{0,4}}(\d{{1,4}})[ \t]*[.)]?[ \t]{{2,}}\S")

#: A flat numbered paragraph — `2. In the Central Goods and Services Tax Rules`.
#: Prose must follow the number. A rate-table row puts a tariff code or a dash
#: there instead, which is what keeps `1.  0303  Fish, frozen` out.
#:
#: The indent bound is TWO, not four. Measured across all eleven notifications:
#: every operative paragraph sits at column 0, 1 or 2, and the only thing at
#: column 4 is `27. Verification (by authorised signatory)` - a field of FORM
#: GST REG-01, which 3/2017 carries after its twenty-six rules. Admitting it
#: would publish `paragraph 27` of a notification that has twenty-six.
_FLAT_PARAGRAPH = re.compile(
    "(?m)^\\f?[ \\t]{0,2}(\\d{1,3})\\.[ \\t]+[\"\u201c\u201d'\u2018(A-Za-z]"
)

#: A dotted-decimal outline paragraph — `3.1.2`. Three digits maximum per
#: component, which is what makes a year unmatchable: `2017  (hereinafter` has
#: no way to end after three digits and still be followed by a space.
#: Interior spacing is tolerated because Circular 232/26/2024 extracts one of
#: its own headings as `3.2  .2`.
_DOTTED_PARAGRAPH = re.compile(
    rf"(?m)^{_PAGE_BREAK}[ \t]{{0,4}}"
    rf"(\d{{1,3}}(?:[ \t]*\.[ \t]*\d{{1,3}}){{0,3}})[ \t]*[.,]?[ \t]+\S"
)

#: `Q 12.` / `Question 12.` / `Q. 12)`.
_QUESTION = re.compile(
    rf"(?m)^{_PAGE_BREAK}[ \t]{{0,4}}Q(?:uestion)?[ \t]*\.?[ \t]*(\d{{1,3}})[ \t]*[.)]"
)

#: `2.  Levy of and Exemption from Tax` — a FAQ chapter heading.
_CHAPTER = re.compile(
    rf"(?m)^{_PAGE_BREAK}[ \t]{{0,4}}(\d{{1,2}})\.[ \t]{{2,}}([A-Z][^\n]*?)[ \t]*$"
)

#: A run of leaders marks a contents entry, never a body heading.
_LEADERS = re.compile(r"\.{4,}")

#: An instrument's numbering may begin at 1, or at 2 where the opening
#: paragraph is the unnumbered `G.S.R.…(E).-` recital — which is the norm for a
#: notification and universal for a circular.
_FIRST_PARAGRAPH = frozenset({1, 2})

# ── sequence rules ────────────────────────────────────────────────────────


def _increasing(
    candidates: list[tuple[int, int]], first_allowed: frozenset[int]
) -> list[tuple[int, int]]:
    """Keep the candidates that continue a strictly increasing run.

    Gaps are allowed and are common: the chapter-wise goods schedule genuinely
    has no rows for chapters 50 to 64 because the Council had not fixed textile
    rates, and the truncated 2/2017 extraction loses rows outright. A gap costs
    one unreachable section. Accepting a number that goes BACKWARDS would cost
    a wrong span, so it never happens.
    """
    kept: list[tuple[int, int]] = []
    for number, start in candidates:
        if not kept:
            if number in first_allowed:
                kept.append((number, start))
        elif number > kept[-1][0]:
            kept.append((number, start))
    return kept


def _one_serial_column(
    candidates: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], int | None]:
    """The FIRST serial column only, and where it ended.

    A second `1` ends the scan, it does not continue it.

    A serial number restarting at 1 is a new table, and a new table's rows are
    not the first table's rows. Two documents proved this is not hypothetical:

      GST-Schedule-of-Rates-for-Services carries the rate table (rows 1 to 36) and
      then `Service Tax Exemptions to be continued in GST` (rows 1 to 83). Merely
      skipping the restart made row 40 of the EXEMPTIONS table answer to
      `S. No. 40` of the rate table — a citation resolving to a different
      table, silently, with containment satisfied.

      Notification 3/2017 carries a three-row composition table and then FORM
      GST REG-01, whose fields are numbered 1 to 21. Row 21 of "the table" became
      a 133,000-character span covering a third of the notification, which is
      containment that has stopped containing anything.

    Stopping means the second table is unaddressable. That is the correct
    answer: without a name to qualify it by, `Sl. No. 40` in such a document
    genuinely means two things, and a citation to it must fail rather than pick.

    The offset of the restart is returned as well, and becomes a boundary. The
    last row of the first table then ends where the second table begins instead
    of running to the end of the file — which is the difference between
    `S. No. 36` covering its own row and `S. No. 36` covering the entire
    exemptions table that follows it.
    """
    kept: list[tuple[int, int]] = []
    for number, start in candidates:
        if not kept:
            if number == 1:
                kept.append((number, start))
        elif number == 1:
            return kept, start
        elif number > kept[-1][0]:
            kept.append((number, start))
    return kept, None


def _outline(
    candidates: list[tuple[tuple[int, ...], int]],
) -> list[tuple[tuple[int, ...], int]]:
    """Keep the candidates that continue a dotted-decimal outline.

    A heading may open a child (`3.1` after `3`), advance a sibling at any depth
    (`3.2` after `3.1.4`, `4` after `3.3.4`), or skip a level the document never
    printed — the Rule 86A guidelines jump from `3.3.2` straight to `3.4.1`
    without ever printing `3.4`. What it may never do is move the top-level
    number by more than one, and that single constraint is what rejects `168`,
    `44` and every other sentence that opens with a figure.
    """
    kept: list[tuple[tuple[int, ...], int]] = []
    for parts, start in candidates:
        if not kept:
            if len(parts) == 1 and parts[0] in _FIRST_PARAGRAPH:
                kept.append((parts, start))
        else:
            previous = kept[-1][0]
            if parts > previous and parts[0] - previous[0] in (0, 1):
                kept.append((parts, start))
    return kept


def _spans(headings: list[tuple[str, int]], boundaries: list[int], end: int) -> dict[str, Span]:
    """Ordered `(label, start)` pairs into non-overlapping spans.

    `base.spans_from_headings` is not used here because these documents need a
    boundary that is NOT itself citable. A rate Schedule's banner ends the last
    row of the schedule before it, and a FAQ chapter heading ends the last
    question of the chapter before it, but neither is a unit anyone cites — a
    span reaching from `Schedule I, Sl. No. 263` across the `Schedule II - 6%`
    banner and into the next table would be a containment check that had
    quietly stopped containing.
    """
    stops = sorted({*boundaries, *(start for _, start in headings)})
    spans: dict[str, Span] = {}
    for label, start in headings:
        index = bisect.bisect_right(stops, start)
        spans[label] = Span(start, stops[index] if index < len(stops) else end)
    return spans


def _drop_duplicates(headings: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Remove every label that occurs more than once, rather than choosing one.

    The CBIC FAQ prints two different questions as `Q 15` in chapter 1. Picking
    either is a coin toss recorded as a proof, so neither is registered and a
    citation to it fails at layer 2 — visibly, and for the right reason.
    """
    counts: dict[str, int] = {}
    for label, _ in headings:
        counts[label] = counts.get(label, 0) + 1
    return [(label, start) for label, start in headings if counts[label] == 1]


# ── shared scans ──────────────────────────────────────────────────────────


def _schedule_groups(text: str) -> list[tuple[str | None, int, int]]:
    """`(roman, start, end)` per rate Schedule, or one unnamed group covering all."""
    banners = [(match.group(1).upper(), match.start()) for match in _SCHEDULE_BANNER.finditer(text)]
    if not banners:
        return [(None, 0, len(text))]
    groups: list[tuple[str | None, int, int]] = []
    for position, (roman, start) in enumerate(banners):
        end = banners[position + 1][1] if position + 1 < len(banners) else len(text)
        groups.append((roman, start, end))
    return groups


def _flat_paragraphs(text: str) -> list[tuple[str, int]]:
    """`paragraph N` for each numbered paragraph, in document order."""
    candidates = [(int(m.group(1)), m.start()) for m in _FLAT_PARAGRAPH.finditer(text)]
    return [(f"paragraph {n}", start) for n, start in _increasing(candidates, _FIRST_PARAGRAPH)]


def _dotted_paragraphs(text: str) -> list[tuple[str, int]]:
    """`paragraph 3.1.2` for each outline paragraph, in document order."""
    candidates: list[tuple[tuple[int, ...], int]] = []
    for match in _DOTTED_PARAGRAPH.finditer(text):
        parts = tuple(int(piece) for piece in re.split(r"[ \t]*\.[ \t]*", match.group(1)))
        candidates.append((parts, match.start()))
    return [
        ("paragraph " + ".".join(str(part) for part in parts), start)
        for parts, start in _outline(candidates)
    ]


def _serial_sections(text: str, *, with_paragraphs: bool) -> dict[str, Span]:
    """Every serial row, and every numbered paragraph, as non-overlapping spans.

    Paragraphs are scanned first and their offsets are withheld from the row
    scan. Both shapes can match the same line: `2.   In the Central Goods and
    Services Tax Rules, 2017,` opens 11/2025 and looks exactly like a serial.
    Prose wins, because a rate table's second column holds a tariff code or a
    dash and never a sentence.

    `with_paragraphs` is false for the Council rate tables, which have no
    operative paragraphs at all and whose first column IS prose: `1. Transport
    of goods by rail`. Running the paragraph scan there consumed every row and
    published 83 sections named `paragraph N` that the label grammar then
    refused to own — a whole document silently unreachable.
    """
    paragraphs = _flat_paragraphs(text) if with_paragraphs else []
    claimed = {start for _, start in paragraphs}

    rows: list[tuple[str, int]] = []
    groups = _schedule_groups(text)
    boundaries = [start for _, start, _ in groups]
    qualified = len(groups) > 1 or groups[0][0] is not None
    for roman, start, end in groups:
        candidates = [
            (int(m.group(1)), start + m.start())
            for m in _SERIAL_ROW.finditer(text[start:end])
            if start + m.start() not in claimed
        ]
        column, restarted_at = _one_serial_column(candidates)
        prefix = f"Schedule {roman}, " if qualified else ""
        rows.extend((f"{prefix}Sl. No. {number}", offset) for number, offset in column)
        if restarted_at is not None:
            boundaries.append(restarted_at)

    headings = _drop_duplicates(sorted(rows + paragraphs, key=lambda item: item[1]))
    return _spans(headings, boundaries, len(text))


# ── label grammars ────────────────────────────────────────────────────────

#: `Notification 11/2017-CTR,` or `Order No. 02/2018-Central Tax,`. A
#: notification is numbered `<serial>/<year>`; a circular is numbered
#: `<serial>/<issue>/<year>`, which this cannot match.
_NOTIFICATION_PREFIX = re.compile(
    r"^(?:notification|order)[ \t]+(?:no\.?[ \t]*)?\d{1,3}[ \t]*/[ \t]*\d{4}[^,]*,[ \t]*",
    re.IGNORECASE,
)

#: `Circular 232/26/2024-GST,`.
_CIRCULAR_PREFIX = re.compile(
    r"^circular[ \t]+(?:no\.?[ \t]*)?\d{1,4}[ \t]*/[ \t]*\d{1,3}[ \t]*/[ \t]*\d{4}[^,]*,[ \t]*",
    re.IGNORECASE,
)

#: `Schedule III,` qualifying a serial within a rate-schedule notification.
_SCHEDULE_QUALIFIER = re.compile(r"^schedule[ \t]+([ivx]{1,5})[ \t]*,[ \t]*", re.IGNORECASE)

#: `Sl. No. 5`, `S.No 5`, `serial 5`, `entry 5`.
_SERIAL_LABEL = re.compile(
    r"^(?:sl?\.?[ \t]*no\.?|serial(?:[ \t]*(?:no\.?|number))?|entry)[ \t]*(\d{1,4})$",
    re.IGNORECASE,
)

#: `paragraph 2`, `para 2(a)` — flat, with optional parenthesised sub-clauses.
_FLAT_LABEL = re.compile(r"^para(?:graph)?[ \t]*(\d{1,3})((?:\([^()]{1,8}\))*)$", re.IGNORECASE)

#: `paragraph 3.1.2` — dotted outline, with a bare top level allowed.
_DOTTED_LABEL = re.compile(
    r"^para(?:graph)?[ \t]*(\d{1,3}(?:[ \t]*\.[ \t]*\d{1,3}){0,3})\.?$", re.IGNORECASE
)

#: `Q 12`, `Question 12`, optionally qualified by `Chapter 3`.
_QUESTION_LABEL = re.compile(r"^q(?:uestion)?[ \t]*\.?[ \t]*(\d{1,3})\.?$", re.IGNORECASE)
_CHAPTER_QUALIFIER = re.compile(r"^chapter[ \t]*(\d{1,2})[ \t]*,?[ \t]*", re.IGNORECASE)


def _tidy(label: str) -> str:
    """Collapse internal whitespace so `Sl.  No.  5` and `Sl. No. 5` are one label."""
    return re.sub(r"[ \t]+", " ", label.strip())


def _serial_label(rest: str) -> str | None:
    """`Sl. No. 5` or `Schedule III, Sl. No. 21`, in one spelling, or None."""
    schedule = _SCHEDULE_QUALIFIER.match(rest)
    if schedule is not None:
        serial = _SERIAL_LABEL.match(rest[schedule.end() :].strip())
        if serial is None:
            return None
        return f"Schedule {schedule.group(1).upper()}, Sl. No. {int(serial.group(1))}"

    serial = _SERIAL_LABEL.match(rest)
    return f"Sl. No. {int(serial.group(1))}" if serial is not None else None


def _dotted_label(rest: str) -> str | None:
    """`paragraph 3.1.2`, in one spelling, or None."""
    dotted = _DOTTED_LABEL.match(rest)
    if dotted is None:
        return None
    parts = re.split(r"[ \t]*\.[ \t]*", dotted.group(1))
    return "paragraph " + ".".join(str(int(part)) for part in parts)


# ── parsers ───────────────────────────────────────────────────────────────


class _InstrumentParser(SectionParser):
    """`owns` and `canonical` are the same two questions asked of one reader.

    Each subclass supplies `_parse`, which returns the one canonical spelling of
    a label it can express and None for a label it cannot. Ownership is then
    exactly "`_parse` produced something", so the two answers can never drift
    apart — a parser that owned a label but canonicalised it to a key its own
    `sections` never emits would fail at layer 2 while looking correct.
    """

    def owns(self, label: str) -> bool:
        return self._parse(label) is not None

    def canonical(self, label: str) -> str:
        parsed = self._parse(label)
        return parsed if parsed is not None else _tidy(label)

    @abc.abstractmethod
    def _parse(self, label: str) -> str | None:
        """The one canonical spelling of `label`, or None if this grammar cannot express it."""


class NotificationParser(_InstrumentParser):
    """CBIC notifications and removal-of-difficulty orders.

    Two addressable units, because these documents genuinely have two. A rate
    or exemption notification is a TABLE and its unit is the row — `Sl. No. 5`
    of 11/2017 is the entry for wholesale trade, and it is what a lawyer cites.
    An amending notification is a list of PARAGRAPHS and its unit is
    `paragraph 2`. 11/2017 and 12/2017 have both: several hundred rows, then a
    handful of paragraphs defining terms and commencement.

    1/2017 and 9/2025 divide their rows into rate Schedules that each restart
    at 1, so there the schedule is part of the unit: `Schedule III, Sl. No. 21`.
    The bare form is not registered for those two, because six rows numbered 21
    cannot resolve to one.
    """

    kind = "notification"
    label_form = (
        'a numbered table row — "Sl. No. 5" — or, where the notification is divided '
        'into rate Schedules, "Schedule III, Sl. No. 21"; or a numbered paragraph, '
        '"paragraph 2" or "paragraph 2(a)". Either may carry the instrument\'s own '
        'number in front of it: "Notification 11/2017-CTR, Sl. No. 5", '
        '"Order No. 02/2018-Central Tax, paragraph 2". Paragraph numbers in a '
        "notification are flat; a dotted 3.1.2 belongs to a circular, not here"
    )

    def sections(self, text: str) -> dict[str, Span]:
        return _serial_sections(text, with_paragraphs=True)

    def _parse(self, label: str) -> str | None:
        rest = _NOTIFICATION_PREFIX.sub("", _tidy(label), count=1).strip()
        serial = _serial_label(rest)
        if serial is not None:
            return serial
        flat = _FLAT_LABEL.match(rest)
        return f"paragraph {int(flat.group(1))}{flat.group(2)}" if flat is not None else None


class RateScheduleParser(_InstrumentParser):
    """The four GST Council rate tables — goods, services, RCM services, cess.

    One table, one column of serial numbers, no operative paragraphs at all.
    The unit is therefore the row and only the row: `S. No. 12`. Anything that
    reads like a paragraph reference is a citation to a different document, and
    that is what makes `paragraph 2` a layer-5 rejection here and a valid label
    one class up.

    These four carry no rate-Schedule banners, so the qualified
    `Schedule III, S. No. 12` form resolves to nothing today. It is accepted by
    the grammar because the scan that builds the spans is shared with
    notifications and would produce it if a Council table were ever published
    that way; it fails at layer 2 rather than silently at layer 5.
    """

    kind = "rate_schedule"
    label_form = (
        'a numbered row of the rate table — "S. No. 12", "Sl. No. 12" — optionally '
        'qualified by a rate Schedule, "Schedule III, S. No. 12". These documents '
        "have no numbered paragraphs, so a paragraph reference is not one of them"
    )

    def sections(self, text: str) -> dict[str, Span]:
        return _serial_sections(text, with_paragraphs=False)

    def _parse(self, label: str) -> str | None:
        return _serial_label(_tidy(label))


class CircularParser(_InstrumentParser):
    """CBIC circulars — numbered paragraphs in a dotted-decimal outline.

    A circular states an issue and clarifies it, and every level of that
    argument is printed: `3` Clarification, `3.1` the first question, `3.1.1`
    the reasoning, `3.1.4` the conclusion. Because every level is printed,
    `ancestors` is deliberately NOT overridden to fall back from `3.1.5` to
    `3.1`. A sub-paragraph that does not exist is a wrong citation, and it
    should fail at layer 2 saying so rather than quietly prove itself against
    its parent — the widening the default would allow is right for an Act,
    whose clause letters are never headings, and wrong here.
    """

    kind = "circular"
    label_form = (
        'a numbered paragraph in the circular\'s own dotted outline — "paragraph 3.1", '
        '"para 3.1.2", "paragraph 4" — optionally prefixed with the circular\'s number, '
        '"Circular 232/26/2024-GST, paragraph 3.1.2". Every level the circular prints '
        "is addressable, and only those; there is no fallback to a parent paragraph"
    )

    def sections(self, text: str) -> dict[str, Span]:
        headings = _drop_duplicates(_dotted_paragraphs(text))
        return _spans(headings, [], len(text))

    def _parse(self, label: str) -> str | None:
        return _dotted_label(_CIRCULAR_PREFIX.sub("", _tidy(label), count=1).strip())


class GuidanceParser(_InstrumentParser):
    """CBIC FAQs and guidelines — two shapes under one manifest kind.

    A FAQ's addressable unit is the question, and nothing smaller: `Q 12` is
    both the question and its answer, which is exactly the span a citation to a
    FAQ means. The Composition Levy FAQ numbers its questions once through, so
    `Q 12` is enough. The 2nd-edition GST FAQ restarts at `Q 1` in each of its
    twenty-odd chapters, so `Q 6` there names twenty-four different questions
    and the chapter is required: `Chapter 3 Q 12`. Where a number is ambiguous
    the bare form is not registered at all.

    A chapter is a boundary, not a unit. Registering `Chapter 3` as a span
    would overlap every question inside it, which the interface forbids, and a
    citation to a whole chapter is not a citation to anything in particular.

    The Rule 86A guidelines are not a FAQ — they are prose in the same
    dotted-decimal outline a circular uses, so when a document contains no
    questions at all the paragraph grammar applies instead. That is a property
    of the text, not a filename check.
    """

    kind = "guidance"
    label_form = (
        'a numbered question — "Q 12", "Question 12" — qualified by its chapter where '
        'the document restarts numbering, "Chapter 3 Q 12"; or, for guidance written '
        "as prose rather than questions, a numbered paragraph in dotted outline, "
        '"paragraph 3.1.2". A bare "Q 6" is only addressable where exactly one '
        "question in the document carries that number"
    )

    def sections(self, text: str) -> dict[str, Span]:
        chapters = self._chapters(text)
        questions = self._questions(text, chapters)
        if not questions:
            return _spans(_drop_duplicates(_dotted_paragraphs(text)), [], len(text))
        boundaries = [start for _, start in chapters]
        return _spans(_drop_duplicates(questions), boundaries, len(text))

    @staticmethod
    def _chapters(text: str) -> list[tuple[int, int]]:
        """`(number, start)` per body chapter heading, contents listing excluded."""
        candidates = [
            (int(match.group(1)), match.start())
            for match in _CHAPTER.finditer(text)
            if not _LEADERS.search(match.group(2))
        ]
        return _increasing(candidates, frozenset({1}))

    @staticmethod
    def _questions(text: str, chapters: list[tuple[int, int]]) -> list[tuple[str, int]]:
        """Question headings — chapter-qualified where the document has chapters.

        Chaptered and bare forms are never both registered for one question.
        Two labels over one span are two names for one proof, and the interface
        asks for spans that do not overlap; more usefully, a document that
        restarts numbering should teach the author to write the chapter, not
        offer a bare form that works for `Q 35` and fails for `Q 6`.
        """
        starts = [start for _, start in chapters]
        grouped: dict[int | None, list[tuple[int, int]]] = {}
        for match in _QUESTION.finditer(text):
            index = bisect.bisect_right(starts, match.start()) - 1
            chapter = chapters[index][0] if index >= 0 else None
            grouped.setdefault(chapter, []).append((int(match.group(1)), match.start()))

        headings: list[tuple[str, int]] = []
        for chapter, candidates in grouped.items():
            # A question number printed twice in one chapter is a defect in the
            # source — the GST FAQ prints two different `Q 15` in chapter 1.
            # `_increasing` would keep the first and drop the second; counting
            # here drops both, so the ambiguity fails loudly instead of
            # resolving to whichever the scan happened to reach first.
            counted: dict[int, int] = {}
            for number, _ in candidates:
                counted[number] = counted.get(number, 0) + 1
            for number, start in _increasing(candidates, frozenset({1})):
                if counted[number] > 1:
                    continue
                label = f"Q {number}" if chapter is None else f"Chapter {chapter} Q {number}"
                headings.append((label, start))
        return sorted(headings, key=lambda item: item[1])

    def _parse(self, label: str) -> str | None:
        rest = _tidy(label)

        chapter = _CHAPTER_QUALIFIER.match(rest)
        if chapter is not None:
            question = _QUESTION_LABEL.match(rest[chapter.end() :].strip())
            if question is None:
                return None
            return f"Chapter {int(chapter.group(1))} Q {int(question.group(1))}"

        question = _QUESTION_LABEL.match(rest)
        return f"Q {int(question.group(1))}" if question is not None else _dotted_label(rest)


__all__ = [
    "CircularParser",
    "GuidanceParser",
    "NotificationParser",
    "RateScheduleParser",
]
