"""One interface, many document grammars.

Indian legal sources do not agree on how to number themselves. An Act writes
`16. Eligibility and conditions...— (1)`, the Rules write `46. Tax invoice.-`,
an ICAI standard writes `8.4`, and a notification writes nothing recognisable
at all. Hardcoding one of those grammars into the verifier would mean the
verifier silently stops working the moment a document of another kind is
cited — which is the failure mode where a check keeps returning green while
having quietly stopped checking.

So: every document kind gets its own parser, and all of them implement the
same three questions.

    owns(label)      does this label even BELONG to my grammar?      (layer 5)
    sections(text)   what sections exist, and where does each start
                     and end?                                        (layer 2)
    canonical(label) what is the one true spelling of this label,
                     so `CGST s.16(2)(a)` and `Section 16(2)(a)`
                     resolve to the same section?

`owns` is what makes a wrong section number falsifiable. Without it, citing
`CGST Act s.999` against an ICAI standard fails only because no such section
exists; with it, the citation is rejected for the stronger and more useful
reason that an Act section reference has no meaning inside an accounting
standard.

THE TABLE-OF-CONTENTS TRAP

Both the CGST Act and the Companies Act print a full contents listing before
the body, using the same `N. Title` form as the real sections. A parser that
takes the first match indexes every section to its one-line contents entry, so
every containment check then fails — or worse, a short quote that happens to
appear in a heading passes while the real provision is never examined.

`pick_body_occurrence` resolves it structurally rather than by guessing a page
number: contents entries are one-liners packed adjacently, so the body
occurrence is the one with the most text before the next heading. That holds
for every document here without a per-document offset to maintain.
"""

from __future__ import annotations

import abc
import re

from ..model import Span


class SectionParser(abc.ABC):
    """The contract every document grammar implements."""

    #: Stable name recorded in the manifest as `kind`. Never derived from a
    #: filename — a file renamed for clarity must not change how it is parsed.
    kind: str

    #: Human-readable description of the label form, quoted verbatim in the
    #: failure message so an author can see what shape was expected.
    label_form: str

    @abc.abstractmethod
    def owns(self, label: str) -> bool:
        """True when `label` is a reference this document grammar can express."""

    @abc.abstractmethod
    def canonical(self, label: str) -> str:
        """The one spelling of `label` used as a key into `sections`."""

    @abc.abstractmethod
    def sections(self, text: str) -> dict[str, Span]:
        """Every section in `text`, canonical label to its span.

        Spans must not overlap, and each must cover the section's body — from
        its own heading to the start of the next.
        """

    def ancestors(self, label: str) -> list[str]:
        """`label` and each enclosing level, finest first.

        `16(2)(a)` yields `16(2)(a)`, `16(2)`, `16`. Default splits on trailing
        parenthesised groups, which covers Acts and Rules; ICAI's dotted
        paragraph numbering overrides it.
        """
        canonical = self.canonical(label)
        chain = [canonical]
        trimmed = canonical
        while (match := re.match(r"^(.*?)\([^()]*\)$", trimmed)) and match.group(1):
            trimmed = match.group(1)
            chain.append(trimmed)
        return chain

    def locate(self, text: str, label: str) -> tuple[Span, str] | None:
        """The tightest span proving `label`, with the level actually proven.

        A citation is written at the depth a lawyer would write it — `s.16(2)(a)`
        — but a document only prints headings at the depths it prints them. Where
        the exact clause is parseable, containment is checked against that clause.
        Where it is not, the nearest enclosing level is used and REPORTED, so the
        proof is never silently weaker than it looks.

        This is still an enormous narrowing. `s.16` is a few thousand characters
        of a 500,000-character Act, and it is the narrowing that makes a wrong
        section number falsifiable at all.
        """
        sections = self.sections(text)
        for level in self.ancestors(label):
            span = sections.get(level)
            if span is not None:
                return span, level
        return None


def spans_from_headings(text: str, headings: list[tuple[str, int]]) -> dict[str, Span]:
    """Turn ordered `(label, start)` pairs into non-overlapping spans.

    Each section runs to the start of the next heading; the last runs to the
    end of the document. Where a label appears more than once — the contents
    listing — the occurrence with the most following text wins.
    """
    by_label: dict[str, list[int]] = {}
    for label, start in headings:
        by_label.setdefault(label, []).append(start)

    starts = sorted(start for _, start in headings)
    spans: dict[str, Span] = {}
    for label, occurrences in by_label.items():
        start = pick_body_occurrence(occurrences, starts, len(text))
        following = [s for s in starts if s > start]
        spans[label] = Span(start, following[0] if following else len(text))
    return spans


def pick_body_occurrence(occurrences: list[int], all_starts: list[int], end: int) -> int:
    """Of several occurrences of one heading, the one that begins the real section.

    A contents entry is followed almost immediately by the next contents entry;
    a body heading is followed by the provision itself. Choosing the occurrence
    with the largest gap to the next heading therefore picks the body without
    needing to know where the contents listing ends.
    """

    def gap(start: int) -> int:
        following = [s for s in all_starts if s > start]
        return (following[0] if following else end) - start

    return max(occurrences, key=gap)


def strip_extraction_noise(label: str) -> str:
    """Remove decoration an author may reasonably include around a label.

    Handles the leading `Section`/`Sec.`/`s.`/`rule`/`para` words, a trailing
    comma-and-gloss (`s.16(2), the possession limb`), and surrounding
    whitespace. Never touches the numbers themselves.
    """
    label = label.strip()
    label = re.split(r",", label, maxsplit=1)[0].strip()
    return re.sub(
        r"^(?:the\s+)?(?:section|sec\.?|s\.|rule|regulation|para(?:graph)?|clause)\s*",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip()
