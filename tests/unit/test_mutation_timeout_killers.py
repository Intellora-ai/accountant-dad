"""Fast kills for bounded-iteration mutants whose only covering tests are slow.

WHY THIS FILE EXISTS, AND WHAT MEASUREMENT PUT IT HERE.

mutmut runs a mutant's covering tests with `-x`, sorted FASTEST FIRST
(`mutmut/__main__.py`: `sorted(tests, key=lambda t: duration_by_test[t])` and
`pytest_args = ["-x", ...]`), and kills the mutant at the first test that fails.
A mutant no test catches instead burns its whole budget, which mutmut computes
as `(sum of its covering tests' durations + timeout_constant) * timeout_multiplier`
— defaults 1.0 and 15.0, not overridden in `[tool.mutmut]`. So the wall clock a
timed-out mutant wastes is proportional to how slow its covering set already is,
and the cheapest way to stop wasting it is a test that fails FAST.

THE SITE THIS FILE GUARDS. `cleaner._pdf_has_text_layer` decides, per page,
whether a PDF carries an embedded text layer:

    any(plain_text(document, index).strip() for index in range(page_count(document)))

`operator_arg_removal` is one of mutmut's operators, and removing `.strip()`
produces a mutant that MEASURABLY SURVIVED the whole of
`tests/unit/test_input_engine_cleaner.py` — 68.20 s of wall clock spent
reaching no verdict. No test in the tree builds a PDF whose text layer is
whitespace only, which is the single input that separates the two behaviours.

WHY THE SURVIVING MUTANT IS A REAL DEFECT, not just an unkilled one. A page
whose text layer holds only whitespace is a page with no readable text. Without
`.strip()` that page reads as "this PDF has a text layer", so `_clean_pdf`
routes it to `_pdf_passed_through` — returned UNCLEANED — instead of
`_pdf_rebuilt_from_cleaned_pages`. A scanned document carrying a stray
whitespace text layer would skip cleaning entirely and reach the reader as-is.

NO NEW DEPENDENCY AND NO NEW TIMEOUT MECHANISM. The repository configures no
per-test timeout plugin, so termination is pinned the way the cheaper half of
the rule says to pin it: by asserting the exact output. Both directions are
asserted, so this file cannot pass vacuously if the function is ever broken
into always-False.
"""

from __future__ import annotations

import pymupdf

from accountant_dad.engines.input_engine.cleaner import _pdf_has_text_layer

#: Small on purpose. Nothing here renders or rasterises — the function under
#: test only reads the text layer — so the page exists solely to carry one.
_PAGE_WIDTH_POINTS = 200
_PAGE_HEIGHT_POINTS = 200

#: Where the text is placed. Well inside the page, so a real glyph is genuinely
#: extractable and the "has text" case is not accidentally empty for a reason
#: that has nothing to do with the code under test.
_TEXT_ORIGIN = (50, 50)


def _one_page_pdf(text: str) -> bytes:
    """A real single-page PDF whose text layer is exactly `text`.

    A REAL PDF THROUGH THE REAL BACKEND, not a stub. `_pdf_has_text_layer`
    reads its pages through `pdf_backend`, and faking that would test the fake:
    whether whitespace survives into an extracted text layer is a property of
    the PDF format and the extractor, which is precisely the thing in question.
    """
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    try:
        page = document.new_page(width=_PAGE_WIDTH_POINTS, height=_PAGE_HEIGHT_POINTS)
        page.insert_text(_TEXT_ORIGIN, text)
        return bytes(document.tobytes())  # type: ignore[no-untyped-call]
    finally:
        document.close()  # type: ignore[no-untyped-call]


def test_a_text_layer_of_only_whitespace_is_not_a_text_layer() -> None:
    """Kills the `.strip()`-removal mutant at `cleaner.py`'s page loop.

    Whitespace is not text. Without `.strip()` this returns True, and the
    document is passed through uncleaned on the strength of a text layer that
    says nothing. MEASURED: this exact mutant survived the existing cleaner
    suite, so this assertion is the only thing standing between it and the
    score's excluded bucket.
    """
    assert _pdf_has_text_layer(_one_page_pdf("   \t  ")) is False


def test_a_text_layer_carrying_real_characters_is_reported_as_one() -> None:
    """The other direction, so the test above cannot pass vacuously.

    If `_pdf_has_text_layer` were ever broken into returning False for
    everything, the whitespace assertion alone would still pass and would be a
    false green. This is the assertion that makes that impossible.
    """
    assert _pdf_has_text_layer(_one_page_pdf("TAX INVOICE")) is True
