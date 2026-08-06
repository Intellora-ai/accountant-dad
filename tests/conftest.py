"""Put the CI tooling and the repo root on the import path.

Mirrors what `merge.yml` does with `PYTHONPATH: tools/ci`, so the tests exercise
the modules exactly as CI imports them rather than through a different path.

The repo root is added for `tools.evidence`, the citation verifier. It goes here
rather than in `pyproject.toml`'s `pythonpath`, which is pinned by
`test_mutation_measures_the_real_tree.py` — that pin is load-bearing, because
under mutation pytest resolves `type="paths"` options against the INI FILE's
directory, and those two entries are what make the INSTRUMENTED copies the thing
being scored. Adding a third entry there broke the guard; the guard was right.

This mechanism cannot reintroduce that bug: `[tool.mutmut] paths_to_mutate` is
`["src"]`, so nothing under `tools/` is ever mutated and no scoring decision
depends on which copy of it is imported.

── THE RECORDED DOCLING READING, AND WHY IT LIVES HERE ───────────────────

`recorded_docling` and `recorded_docling_for_module` below replace ONE call —
`docling.document_converter.DocumentConverter` — with a converter that returns a
reading this repository recorded from the real library. Everything downstream of
that call is first-party code and runs for real.

WHY. MEASURED 2026-08-07 at commit `00c6b8d`, on this machine, warm model cache:

```
import docling.document_converter        5.19 s
DocumentConverter()                      0.11 s   <- construction is cheap
DocumentConverter().convert()  FIRST    64.00 s   <- the models load here
DocumentConverter().convert()  SECOND    1.05 s
```

The charge is PER PROCESS, on the first conversion, not per call. The whole
suite is one process and pays it once; the `mutation` gate runs a fresh process
per mutant and pays it once per mutant. That is what makes a unit test which
reads a real document with a real model unaffordable in a gate that reruns it
hundreds of times, and it is the measured cause behind `KNOWN_FAILURES.md`
F-014.

WHAT IS FAKED, AND WHY ONLY THIS — test discipline §J.7. The narrowest external
I/O edge is the converter. The status vocabulary and the coordinate origin are
imported from the INSTALLED library rather than re-declared, so a Docling
release that renames either breaks these tests instead of letting them keep
passing against a vocabulary that no longer exists. This is the same mechanism,
at the same seam, that `test_parser_conversion_contract.py` already documents
and uses; it is hosted here so there is ONE copy of it rather than one per test
module (Law 14).

WHAT THIS IS NOT FOR. A test whose SUBJECT is what the real model reports — the
fourteen `@needs_the_real_tools` measurements in `test_input_engine_parser.py`,
and `tests/integration/test_engine1_end_to_end.py` — keeps the real model.
Feeding those a recording would make them assert that a recording equals itself.
Use these fixtures only where the model's reading is an INPUT to the behaviour
under test, never where it is the behaviour under test.

THE RECORDING IS REAL. `text_reading` reproduces, field for field, what Docling
2.118.0 returned for a one-page PyMuPDF-authored invoice on 2026-08-07:

```
status  ConversionStatus.SUCCESS
pages   {1: size.height 842.0}
texts   ONE item, label 'text', text 'TAX INVOICE Vendor: Acme Traders Total
        1,180.00', prov page_no 1, bbox l=60.0 t=761.33 r=190.77 b=681.31,
        coord_origin BOTTOMLEFT
tables  none
```

The single merged region is not a simplification — Docling merges adjacent lines
of a page into one region, which `test_input_engine_parser.py:826` measured
independently and asserts against the real library.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_CI = REPO_ROOT / "tools" / "ci"
for entry in (TOOLS_CI, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))


# ── the shape `parser._convert` reads, and nothing wider ──────────────────
#
# Deliberately only the attributes the production code actually touches. A fake
# that grew to mirror Docling would start hiding the coupling it exists to
# expose — the same rule `test_parser_conversion_contract.py` states for its own
# `_Document`.
#
# The library's own enums travel as `object`: `parser` reads both of them with
# `str(...)`, never by identity, so widening them here to a declared type would
# state a coupling the production code does not have.


@dataclass(frozen=True)
class RecordedBox:
    """One bounding box, in the four edges Docling names it by."""

    left: float
    top: float
    right: float
    bottom: float
    coord_origin: object

    def __getattr__(self, name: str) -> float:
        """Serve Docling's own one-letter edge names: `l`, `t`, `r`, `b`.

        Reached through `__getattr__` rather than declared as fields because
        `l` is a name ruff refuses (E741) and this repository's suppression
        budget forbids silencing it. An unknown name still raises
        `AttributeError`, so a parser that started reading an edge Docling does
        not have fails here instead of reading a zero.
        """
        edges = {"l": "left", "t": "top", "r": "right", "b": "bottom"}
        if name not in edges:
            message = f"{type(self).__name__} has no edge {name!r}"
            raise AttributeError(message)
        edge: float = self.__dict__[edges[name]]
        return edge


@dataclass(frozen=True)
class RecordedProvenance:
    page_no: int
    bbox: RecordedBox


@dataclass(frozen=True)
class RecordedText:
    label: str
    text: str
    prov: tuple[RecordedProvenance, ...]


@dataclass(frozen=True)
class RecordedSize:
    height: float


@dataclass(frozen=True)
class RecordedPage:
    size: RecordedSize


@dataclass(frozen=True)
class RecordedDocument:
    pages: dict[int, RecordedPage]
    texts: tuple[RecordedText, ...] = ()
    pictures: tuple[object, ...] = ()
    tables: tuple[object, ...] = ()


@dataclass(frozen=True)
class RecordedReading:
    """What one `DocumentConverter().convert()` call hands back."""

    status: object
    document: RecordedDocument | None
    errors: tuple[object, ...] = field(default=())


#: The page height Docling reported for the A4 fixtures these modules author.
#: Not a threshold and nothing branches on its value — it is the number the
#: library returned, kept so the geometry the parser computes is the geometry it
#: computes in production.
A4_HEIGHT_POINTS = 842.0

#: The bounding box Docling returned for the merged text region of the recorded
#: invoice. Reproduced, not invented; the capture is in the module docstring.
_RECORDED_TEXT_BOX = (60.0, 761.33, 190.77, 681.31)


def text_reading(lines: tuple[str, ...]) -> RecordedReading:
    """The recorded reading, with the caller's own drawn lines substituted in.

    Docling merges adjacent lines of a page into ONE region joined by a single
    space — what the capture shows, and what `test_input_engine_parser.py`
    asserts against the real library. The join is reproduced so a caller that
    DOES look at the reading looks at its real shape.

    THE TWO CALLERS TODAY DO NOT LOOK AT IT, AND THAT IS MEASURED, NOT ASSUMED.
    Both mutations were run at commit `00c6b8d`:

    ```
    pages={} instead of one A4 page  ->  2 RED in test_conformance_registry.py
    text= a string nobody drew       ->  881 GREEN, nothing noticed
    ```

    So `test_pipeline.py` and `test_conformance_registry.py` require a reading
    that is STRUCTURALLY usable and assert nothing about its CONTENT — every
    text they check is `structured_document.extracted_text`, which `reader`
    produces from the PDF's own text layer and which still runs for real. That
    is exactly why substituting here loses nothing. It is also a gap in those
    two modules that predates this fixture and is not closed by it: recorded
    here so it is visible rather than discovered.
    """
    status = importlib.import_module("docling.datamodel.base_models").ConversionStatus
    origin = importlib.import_module("docling_core.types.doc").CoordOrigin

    left, top, right, bottom = _RECORDED_TEXT_BOX
    return RecordedReading(
        status=status.SUCCESS,
        document=RecordedDocument(
            pages={1: RecordedPage(size=RecordedSize(height=A4_HEIGHT_POINTS))},
            texts=(
                RecordedText(
                    label="text",
                    text=" ".join(lines),
                    prov=(
                        RecordedProvenance(
                            page_no=1,
                            bbox=RecordedBox(
                                left=left,
                                top=top,
                                right=right,
                                bottom=bottom,
                                coord_origin=origin.BOTTOMLEFT,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


class RecordedDocling:
    """Installs a recorded reading in place of the real converter.

    One instance per scope. `reading` may be called again to change what the
    next conversion returns; the patch itself is installed once and removed by
    the fixture that owns the `MonkeyPatch`.
    """

    def __init__(self, patch: pytest.MonkeyPatch) -> None:
        self._patch = patch
        self._reading: RecordedReading | None = None
        self._installed = False

    def reading(self, reading: RecordedReading) -> None:
        """Return `reading` from every conversion from here on."""
        self._reading = reading
        self._install()

    def of_text(self, lines: tuple[str, ...]) -> None:
        """Return the recorded reading of a page carrying exactly `lines`."""
        self.reading(text_reading(lines))

    def _install(self) -> None:
        if self._installed:
            return
        # `importlib`, not an `import` statement, and for the same reason
        # `parser.require_module` exists: several CI jobs install only
        # `requirements-ci.txt`, which carries no Docling. A top-level import
        # here would break collection in every one of them, and would charge
        # every other job 5.19 s of import it has no use for.
        document_converter = importlib.import_module("docling.document_converter")

        owner = self

        class _RecordedConverter:
            def convert(self, source: Path, *, raises_on_error: bool = True) -> RecordedReading:
                del raises_on_error
                # The path is READ, not ignored: a converter that never touched
                # its argument would keep passing if the pipeline stopped
                # handing the parser a real file at all, and that hand-off is
                # exactly what `test_input_engine_pipeline.py` proves.
                if not Path(source).exists():
                    message = f"no document at {source}"
                    raise FileNotFoundError(message)
                recorded = owner._reading
                if recorded is None:
                    message = "no reading was recorded for this conversion"
                    raise AssertionError(message)
                return recorded

        self._patch.setattr(document_converter, "DocumentConverter", _RecordedConverter)
        self._installed = True


#: What a test receives: call it with the lines the fixture drew, and every
#: conversion from that point on returns the recorded reading of those lines.
#: A plain callable rather than the class above, so a test module can annotate
#: it with `Callable[[tuple[str, ...]], None]` and needs no import from a
#: `conftest`, which pytest does not put on the import path.
RecordDrawnLines = Callable[[tuple[str, ...]], None]


@pytest.fixture
def recorded_docling(monkeypatch: pytest.MonkeyPatch) -> RecordDrawnLines:
    """A recorded Docling reading, for one test."""
    return RecordedDocling(monkeypatch).of_text


@pytest.fixture(scope="module")
def recorded_docling_for_module() -> Iterator[RecordDrawnLines]:
    """A recorded Docling reading, for a module-scoped fixture.

    `monkeypatch` is function-scoped and cannot be requested by a module-scoped
    fixture, so this owns its own `MonkeyPatch` context and undoes it when the
    module ends.
    """
    with pytest.MonkeyPatch.context() as patch:
        yield RecordedDocling(patch).of_text
