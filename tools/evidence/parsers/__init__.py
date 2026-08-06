"""Every document grammar, registered by the `kind` its manifest entry declares.

A kind with no parser is a hard failure at citation time, never a fallback to
"search the whole file" — that fallback is exactly the behaviour this package
exists to remove. Adding a document of a new kind means writing its parser
first.
"""

from __future__ import annotations

from .act import ActParser
from .base import SectionParser
from .icai import CompendiumParser, PronouncementParser, StandardParser
from .instrument import CircularParser, GuidanceParser, NotificationParser, RateScheduleParser
from .rules import RulesParser


def build_parsers() -> dict[str, SectionParser]:
    """The kind → parser table. One entry per grammar, no aliases."""
    parsers: list[SectionParser] = [
        ActParser(),
        RulesParser(),
        StandardParser(),
        CompendiumParser(),
        PronouncementParser(),
        NotificationParser(),
        CircularParser(),
        RateScheduleParser(),
        GuidanceParser(),
    ]
    table: dict[str, SectionParser] = {}
    for parser in parsers:
        if parser.kind in table:
            raise RuntimeError(
                f"two parsers both claim kind {parser.kind!r}; a kind must select "
                f"exactly one grammar or parsing is order-dependent"
            )
        table[parser.kind] = parser
    return table


__all__ = ["SectionParser", "build_parsers"]
