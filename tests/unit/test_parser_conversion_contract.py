"""The parser's conversion-status contract, one test per branch of it.

── WHY THIS FILE EXISTS ──

`parser._convert` used to test ONE of Docling's six conversion statuses:

    if str(getattr(result.status, "name", result.status)) != "SUCCESS":
        reasons = tuple(str(error.error_message) for error in result.errors)
        raise DocumentUnreadableError(text, reasons)

Three defects in three lines, and all three showed up together on CI
(`KNOWN_FAILURES.md` F-029):

  1. PENDING, STARTED, SKIPPED, FAILURE and PARTIAL_SUCCESS were one
     undifferentiated refusal. A partially converted document that DID carry
     readable pages was thrown away with the same message as a total failure.
  2. Only `error_message` survived. `component_type`, `module_name`, `category`
     and `page_no` were discarded — and "which component failed" was precisely
     the question nobody could answer afterwards.
  3. When Docling reported a non-success status and an EMPTY error list, the
     refusal carried no reason at all. `DocumentUnreadableError` renders that as
     *"no reason was reported"*, which travels into the artifact as an
     unexplained absence of measurement.

The contract those defects cost, approved by the owner 2026-08-06:

```
SUCCESS          + usable output    ->  proceed
PARTIAL_SUCCESS  + usable output    ->  proceed
PARTIAL_SUCCESS  + no usable output ->  refuse as a conversion failure
FAILURE · SKIPPED · missing document · malformed output
                                    ->  refuse, with docling's own account
```

**UNMEASURED is a symptom, never a diagnosis.** Every refusal below is asserted
to carry the underlying conversion reason, not merely the fact of refusal.

── WHAT IS FAKED, AND WHY ONLY THIS ──

§J.7 — fake at the I/O edge, never inside the logic. The edge here is Docling
itself: `DocumentConverter().convert()`. Everything under test — the status
comparison, the output validation, the diagnosis — is this repository's own code
and runs for real.

The STATUSES and the ERROR TYPE are imported from the installed library rather
than re-declared, so a Docling release that renames a status or adds a field to
`ErrorItem` breaks these tests instead of letting them keep passing against a
vocabulary that no longer exists.
"""

from __future__ import annotations

import enum
import hashlib
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from accountant_dad.engines.input_engine import parser

if TYPE_CHECKING:
    from collections.abc import Iterator

docling_models = pytest.importorskip(
    "docling.datamodel.base_models",
    reason="the parsing stack is not installed in this environment",
)
docling_converter = pytest.importorskip("docling.document_converter")

ConversionStatus = docling_models.ConversionStatus
ErrorItem = docling_models.ErrorItem
DoclingComponentType = docling_models.DoclingComponentType

A_REFERENCE = "upload:invoice-481.pdf"

#: The height of the one page every usable fake document carries, in points.
#: Any positive number works; this one is A4's, so a reader of the test does not
#: pause to wonder whether the value is load-bearing. It is not.
A_PAGE_HEIGHT = 842.0


# ── the smallest document Docling could hand back that `parse` can use ────


@dataclass(frozen=True)
class _Size:
    height: float


@dataclass(frozen=True)
class _Page:
    size: _Size


@dataclass
class _Document:
    """Only the four attributes `_convert` reads. Deliberately not more: a fake
    that grew to mirror Docling would start hiding the coupling it exists to
    expose.
    """

    pages: dict[int, _Page]
    texts: list[object] = field(default_factory=list)
    pictures: list[object] = field(default_factory=list)
    tables: list[object] = field(default_factory=list)


@dataclass
class _Result:
    status: object
    document: object | None
    errors: list[object] = field(default_factory=list)


def a_usable_document() -> _Document:
    return _Document(pages={1: _Page(size=_Size(height=A_PAGE_HEIGHT))})


def an_error(message: str = "layout model failed to load") -> object:
    """A real `ErrorItem`, populated in every field the library declares."""
    return ErrorItem(
        component_type=DoclingComponentType.DOCUMENT_BACKEND,
        module_name="docling.backend.pdf_backend",
        error_message=message,
        category=next(iter(docling_models.FailureCategory)),
        page_no=3,
    )


@pytest.fixture
def a_pdf(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real file on disk. `_running_environment` hashes it, so a path that
    does not exist would exercise the diagnosis's own error branch instead of
    the one under test.
    """
    document = tmp_path / "invoice-481.pdf"
    document.write_bytes(b"%PDF-1.4\nnot a real document, and never parsed\n")
    return document


@pytest.fixture
def converting(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[_Result]]:
    """Replace ONLY `DocumentConverter`, and only for the duration of a test.

    The list is the test's control: append the result Docling should return.
    """
    queued: list[_Result] = []

    class _Converter:
        def convert(self, source: pathlib.Path, *, raises_on_error: bool = True) -> _Result:
            del source, raises_on_error
            return queued[0]

    monkeypatch.setattr(docling_converter, "DocumentConverter", _Converter)
    yield queued


def parse_failing_with(a_pdf: pathlib.Path) -> str:
    """`parser.parse` refused, and this is everything it said."""
    with pytest.raises(parser.DocumentUnreadableError) as raised:
        parser.parse(a_pdf, source_reference=A_REFERENCE)
    return str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# The contract, one test per branch
# ═══════════════════════════════════════════════════════════════════════════


def test_success_with_a_usable_document_is_parsed(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    converting.append(_Result(status=ConversionStatus.SUCCESS, document=a_usable_document()))

    parsed = parser.parse(a_pdf, source_reference=A_REFERENCE)

    assert parsed.page_count == 1, "a one-page document converted successfully reported no page"


def test_partial_success_with_a_usable_document_is_parsed(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """THE BRANCH THAT DID NOT EXIST. `!= "SUCCESS"` refused this outright, so a
    document Docling converted with reservations — but which carries real,
    readable pages — was discarded exactly as a total failure was.

    Accepted on the OUTPUT, never on the label: the page below is real, and
    `test_partial_success_without_a_usable_document_is_refused` proves the same
    status is refused when it is not.
    """
    converting.append(
        _Result(
            status=ConversionStatus.PARTIAL_SUCCESS,
            document=a_usable_document(),
            errors=[an_error("page 3 had no extractable text")],
        )
    )

    parsed = parser.parse(a_pdf, source_reference=A_REFERENCE)

    assert parsed.page_count == 1


def test_partial_success_without_a_usable_document_is_refused(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """The other half of the same status, and the reason the status alone is
    never enough. A document reporting zero pages is not evidence of a zero-page
    document — it is an absence of measurement, and this engine may not invent
    one in its place.
    """
    converting.append(
        _Result(
            status=ConversionStatus.PARTIAL_SUCCESS,
            document=_Document(pages={}),
            errors=[an_error()],
        )
    )

    message = parse_failing_with(a_pdf)

    assert "no readable page" in message
    assert "status=PARTIAL_SUCCESS" in message
    assert "document_present=True" in message


@pytest.mark.parametrize(
    "status", [ConversionStatus.FAILURE, ConversionStatus.SKIPPED, ConversionStatus.PENDING]
)
def test_an_unusable_status_is_refused_and_names_itself(
    converting: list[_Result], a_pdf: pathlib.Path, status: enum.Enum
) -> None:
    """PENDING is in the list on purpose. It is not one of the three the
    contract names, and that is the point: the check is `status not in
    (SUCCESS, PARTIAL_SUCCESS)`, an allowlist, so a status nobody anticipated is
    refused rather than silently treated as success.
    """
    converting.append(_Result(status=status, document=None, errors=[an_error()]))

    message = parse_failing_with(a_pdf)

    assert f"status={status.name}" in message


def test_a_usable_status_with_no_document_is_refused(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """SUCCESS is not trusted either. The status says the conversion finished;
    it does not say anything came back.
    """
    converting.append(_Result(status=ConversionStatus.SUCCESS, document=None))

    message = parse_failing_with(a_pdf)

    assert "no document came back" in message
    assert "document_present=False" in message


def test_a_malformed_document_is_refused_rather_than_read_as_empty(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """Pages that cannot be read are not pages that are not there.

    `_page_heights` returns empty for a document whose `pages` raises on access,
    and empty means refuse. Reading a malformed structure as "zero pages" would
    put a fabricated `page_count=0` into the artifact.
    """

    class _Unreadable:
        @property
        def pages(self) -> dict[int, _Page]:
            raise AttributeError("page geometry is not available on this document")

    converting.append(_Result(status=ConversionStatus.SUCCESS, document=_Unreadable()))

    message = parse_failing_with(a_pdf)

    assert "no readable page" in message


# ═══════════════════════════════════════════════════════════════════════════
# The diagnosis itself — every refusal above must be actionable
# ═══════════════════════════════════════════════════════════════════════════


def test_a_refusal_carries_every_field_docling_reported_not_only_the_message(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """The old code kept `error_message` and discarded the rest. `component_type`
    is what says WHICH part of Docling failed, and it was the field most needed
    and least available.
    """
    converting.append(
        _Result(
            status=ConversionStatus.FAILURE,
            document=None,
            errors=[an_error("layout model failed to load")],
        )
    )

    message = parse_failing_with(a_pdf)

    assert "layout model failed to load" in message
    assert "DOCUMENT_BACKEND" in message
    assert "docling.backend.pdf_backend" in message
    assert "page_no=3" in message
    assert "error_count=1" in message


def test_a_refusal_with_no_docling_errors_says_so_rather_than_saying_nothing(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """THE SILENT CASE, AND THE WHOLE REASON THIS FILE EXISTS. Docling can end a
    conversion with a non-success status and an EMPTY error list. The old code
    then raised with an empty `reasons`, which `DocumentUnreadableError` renders
    as *"no reason was reported"* — an unexplained absence travelling into the
    artifact as if it were a finding.

    UNMEASURED is a symptom, never a diagnosis.
    """
    converting.append(_Result(status=ConversionStatus.FAILURE, document=None, errors=[]))

    message = parse_failing_with(a_pdf)

    assert "no reason was reported" not in message
    assert "reported NO ErrorItem" in message
    assert "error_count=0" in message
    assert "status=FAILURE" in message


def test_a_refusal_identifies_the_machine_and_the_input_that_produced_it(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """A failure that happens on CI and nowhere else must carry enough to
    identify the environment that produced it — that is the lesson F-029 cost.

    The commit is asserted PRESENT, never asserted to a value: it comes from
    `GITHUB_SHA`, which is unset locally and set on a runner. Both readings are
    correct, and a test demanding a hash would be a test that only passes on CI.
    """
    converting.append(_Result(status=ConversionStatus.FAILURE, document=None))

    message = parse_failing_with(a_pdf)

    for field_name in (
        "commit=",
        "python=",
        "docling distributions=",
        "command=",
        "cwd=",
        "input ",
    ):
        assert field_name in message, f"the diagnosis does not report {field_name!r}"
    assert "docling-slim" in message, (
        "the diagnosis names only the `docling` meta-package. The import is served "
        "by `docling-slim`, so a report omitting it omits the distribution that "
        "shipped the code that failed."
    )


def test_the_input_is_identified_by_content_not_only_by_name(
    converting: list[_Result], a_pdf: pathlib.Path
) -> None:
    """Two runs of one path can differ by the bytes they were given. A filename
    cannot tell those apart; a digest can, and the fixture PDF is authored at
    run time so its path carries no information at all.
    """
    converting.append(_Result(status=ConversionStatus.FAILURE, document=None))

    message = parse_failing_with(a_pdf)

    assert f"sha256={hashlib.sha256(a_pdf.read_bytes()).hexdigest()}" in message
