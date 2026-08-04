"""Every way a citation can be wrong, and proof that each one is caught.

The check these replace asked a single question — "does this text appear
somewhere in this file?" — and therefore passed a claim citing `CGST Act s.999`
for a quote taken from an ICAI standard about dividends. Every word was real.
The citation was nonsense. A 500,000-character Act answers "is this string in
here" with yes for almost any short phrase, so that question was close to no
question at all.

These tests are written against a REAL parser and a REAL registry over a
disposable evidence tree built per test (§J.6). Nothing here mocks the thing it
is testing: a mock would only ever prove the mock. What is synthetic is the
DOCUMENT, not the machinery — a nine-line Act in the genuine CGST grammar, so a
test can state exactly which section a quote belongs to and then prove the
verifier agrees.

Each test names the failure it traps. A test that cannot fail is not done.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from tools.evidence import model
from tools.evidence.model import Failure, Layer, Span, normalise
from tools.evidence.registry import Document, Registry, read_manifest
from tools.evidence.verify import check_citation, check_document, run

# A miniature Act in the real CGST grammar: number, whitespace, title, `.—`,
# body. Two sections, and one phrase deliberately repeated in BOTH so the
# duplicate-quote case has something honest to bite on.
ACT_TEXT = """
        THE CENTRAL GOODS AND SERVICES TAX ACT, 2017

        ARRANGEMENT OF SECTIONS

        16.      Eligibility and conditions for taking input tax credit.
        17.      Apportionment of credit and blocked credits.

        CHAPTER V
        INPUT TAX CREDIT

        16.      Eligibility and conditions for taking input tax credit.— (1) Every
        registered person shall, subject to such conditions and restrictions as may be
        prescribed, be entitled to take credit of input tax charged on any supply of
        goods or services or both to him which are used in the course or furtherance of
        his business. (2) He is in possession of a tax invoice issued by a supplier
        registered under this Act. (3) The registered person has furnished the return
        under section 39.

        17.      Apportionment of credit and blocked credits.— (1) Where the goods or
        services or both are used by the registered person partly for the purpose of any
        business and partly for other purposes, the amount of credit shall be restricted
        to so much of the input tax as is attributable to the purposes of his business.
        (5) Notwithstanding anything contained in sub-section (1) of section 16, input
        tax credit shall not be available in respect of motor vehicles. He is in
        possession of a tax invoice issued by a supplier registered under this Act.
"""

#: Appears in s.16 only.
ONLY_IN_16 = "entitled to take credit of input tax charged on any supply"
#: Appears in s.17 only.
ONLY_IN_17 = "input tax credit shall not be available in respect of motor vehicles"
#: Appears in BOTH sections, word for word. The duplicate case.
IN_BOTH = "He is in possession of a tax invoice issued by a supplier registered under this Act"


@pytest.fixture
def tree(tmp_path: pathlib.Path) -> pathlib.Path:
    """A complete, disposable evidence tree: manifest, source bytes, sidecar."""
    library = tmp_path / "Evidence_Library"
    sources = library / "sources"
    sources.mkdir(parents=True)

    raw = ACT_TEXT.encode("utf-8")
    (sources / "Tiny-Act.pdf").write_bytes(raw)
    (sources / "Tiny-Act.pdf.txt").write_text(ACT_TEXT, encoding="utf-8")

    (library / "manifest.jsonl").write_text(
        json.dumps(
            {
                "file": "Tiny-Act.pdf",
                "title": "A miniature Act for testing",
                "body": "TEST",
                "kind": "act",
                "version": "as enacted",
                "url": "https://example.invalid/tiny-act.pdf",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "downloaded": "2026-08-05",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def registry(tree: pathlib.Path) -> Registry:
    return Registry.load(tree / "Evidence_Library" / "manifest.jsonl")


def cite(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "file": "Tiny-Act.pdf",
        "section": "s.16",
        "quote": ONLY_IN_16,
    }
    entry.update(overrides)
    return entry


def layers(problems: list[Failure]) -> list[Layer]:
    return [p.layer for p in problems]


def declared(registry: Registry, filename: str = "Tiny-Act.pdf") -> Document:
    """The document, insisting it exists.

    `Registry.get` returns `Document | None` because a citation may name a file
    the manifest never declared — that is layer 1 and it has its own test. In a
    fixture that just wrote the manifest, None means the fixture is broken, and
    saying so here beats threading an Optional through every assertion.
    """
    document = registry.get(filename)
    assert document is not None, f"fixture did not declare {filename}"
    return document


# ---------------------------------------------------------------- the happy path


def test_a_correct_citation_proves_every_layer(registry: Registry) -> None:
    problems, citation = check_citation(cite(), registry)
    assert problems == [], [p.render() for p in problems]
    assert citation is not None
    assert citation.section == "s.16"
    assert citation.checksum == declared(registry).sha256
    assert citation.source_url == "https://example.invalid/tiny-act.pdf"
    assert citation.version == "as enacted"
    assert citation.evidence_id.startswith("EV-")
    start, end = citation.char_range
    assert ACT_TEXT[start:end] == ONLY_IN_16


# ---------------------------------------------------------------- LAYER 1, document


def test_a_missing_document_names_its_source_and_the_bootstrap_command(
    tree: pathlib.Path, registry: Registry
) -> None:
    """A check that fails without saying how to fix it trains people to ignore it."""
    (tree / "Evidence_Library" / "sources" / "Tiny-Act.pdf").unlink()

    document = declared(registry)
    problems = check_document(document)

    assert layers(problems) == [Layer.DOCUMENT]
    report = document.missing_report()
    assert "https://example.invalid/tiny-act.pdf" in report
    assert document.sha256 in report
    assert "tools.evidence.bootstrap" in report


def test_a_document_whose_bytes_changed_is_refused(tree: pathlib.Path, registry: Registry) -> None:
    """Every quote was proven against specific bytes. Different bytes, different proof."""
    (tree / "Evidence_Library" / "sources" / "Tiny-Act.pdf").write_bytes(b"something else")

    problems = check_document(declared(registry))

    assert layers(problems) == [Layer.DOCUMENT]
    assert "manifest declares" in problems[0].message


def test_citing_a_document_the_manifest_does_not_declare_is_refused(registry: Registry) -> None:
    """A quote checked against an undeclared document is checked against nothing."""
    problems, citation = check_citation(cite(file="Some-Other-Act.pdf"), registry)

    assert layers(problems) == [Layer.DOCUMENT]
    assert citation is None


# ---------------------------------------------------------------- LAYER 2, section


def test_a_section_that_does_not_exist_is_refused(registry: Registry) -> None:
    """This is the `s.999` case, stated directly."""
    problems, _ = check_citation(cite(section="s.999"), registry)

    assert layers(problems) == [Layer.SECTION]
    assert "s.999" in problems[0].message


# -------------------------------------------------------- LAYER 3, containment


def test_a_real_quote_under_the_wrong_section_is_refused(registry: Registry) -> None:
    """THE BUG THIS WHOLE MODULE EXISTS FOR.

    The words are real, present, and verbatim. They are simply not in s.16. The
    old check passed exactly this and called it VERIFIED.
    """
    problems, _ = check_citation(cite(section="s.16", quote=ONLY_IN_17), registry)

    assert layers(problems) == [Layer.CONTAINMENT]
    assert "NOT inside" in problems[0].message
    # The remedy must name where the words actually are, or fixing it is a hunt.
    assert "17" in problems[0].remedy


def test_a_quote_appearing_in_two_sections_is_proven_against_the_cited_one(
    registry: Registry,
) -> None:
    """A duplicated phrase must not make either citation unprovable — or provable
    by accident. Cited to s.16 it holds; cited to s.16 while sitting in s.17 it
    still holds, because it is genuinely in both. What must NOT happen is the
    verifier resolving to the wrong occurrence and reporting a span outside the
    cited section."""
    problems, citation = check_citation(cite(section="s.16", quote=IN_BOTH), registry)
    assert problems == [], [p.render() for p in problems]
    assert citation is not None

    section_16 = registry.parser_for(declared(registry)).locate(ACT_TEXT, "s.16")
    assert section_16 is not None
    span, _ = section_16
    start, end = citation.char_range
    assert span.contains(Span(start, end)), "resolved to an occurrence outside the cited section"


def test_the_same_duplicated_quote_also_proves_under_the_other_section(
    registry: Registry,
) -> None:
    """Both citations are true, and each must resolve inside its OWN section."""
    problems, citation = check_citation(cite(section="s.17", quote=IN_BOTH), registry)
    assert problems == [], [p.render() for p in problems]
    assert citation is not None

    found = registry.parser_for(declared(registry)).locate(ACT_TEXT, "s.17")
    assert found is not None
    span, _ = found
    start, end = citation.char_range
    assert span.contains(Span(start, end))


# ---------------------------------------------------------------- LAYER 4, text


def test_a_quote_not_in_the_document_at_all_is_refused(registry: Registry) -> None:
    problems, _ = check_citation(
        cite(quote="input tax credit is available to everyone without condition"), registry
    )

    assert layers(problems) == [Layer.TEXT]
    assert "NOT FOUND" in problems[0].message


def test_one_changed_word_is_enough_to_refuse(registry: Registry) -> None:
    """`shall` to `may` is the whole difference between a duty and a discretion."""
    problems, _ = check_citation(
        cite(quote=ONLY_IN_16.replace("entitled", "permitted")), registry
    )

    assert layers(problems) == [Layer.TEXT]


def test_an_empty_quote_is_refused(registry: Registry) -> None:
    """METADATA, not TEXT — an empty quote is malformed, not merely unfindable.

    It is caught during shape validation, before any document is opened, because
    there is nothing to search for. Reporting it as a TEXT failure would say
    "not found in the source", which invites the author to hunt for a quote they
    never wrote.
    """
    problems, _ = check_citation(cite(quote="   "), registry)

    assert layers(problems) == [Layer.METADATA]
    assert "quote is empty" in problems[0].message


# ------------------------------------------------------------ LAYER 5, ownership


def test_a_label_from_another_documents_grammar_is_refused(registry: Registry) -> None:
    """An ICAI paragraph reference has no meaning inside an Act, even if some
    matching string exists. This is the layer that makes a wrong section number
    falsifiable rather than merely unlucky."""
    problems, _ = check_citation(cite(section="AS 9 para 11"), registry)

    assert layers(problems) == [Layer.OWNERSHIP]


def test_a_rules_label_is_refused_against_an_act(registry: Registry) -> None:
    problems, _ = check_citation(cite(section="rule 46(b)"), registry)

    assert layers(problems) == [Layer.OWNERSHIP]


# ------------------------------------------------------- LAYER 6, metadata drift


def test_stored_metadata_that_disagrees_with_the_source_is_refused(registry: Registry) -> None:
    """Resolved fields are machine-written. A hand-edited one is either a typo or
    a source that moved under a citation, and both must stop the run."""
    problems, _ = check_citation(cite(checksum="0" * 64), registry)

    assert layers(problems) == [Layer.METADATA]
    assert "checksum" in problems[0].message


def test_stored_metadata_that_agrees_is_accepted(registry: Registry) -> None:
    _, citation = check_citation(cite(), registry)
    assert citation is not None

    problems, _ = check_citation(citation.to_entry(), registry)

    assert problems == [], [p.render() for p in problems]


def test_a_resolved_field_round_trips_exactly(registry: Registry) -> None:
    """Writing the resolved entry back and re-verifying must be a fixed point;
    otherwise every run would rewrite the files and every diff would be noise."""
    _, first = check_citation(cite(), registry)
    assert first is not None
    _, second = check_citation(first.to_entry(), registry)
    assert second is not None

    assert first.to_entry() == second.to_entry()


# --------------------------------------------------------- malformed citations


@pytest.mark.parametrize(
    ("entry", "why"),
    [
        ("a bare string", "not an object"),
        (["a", "list"], "not an object"),
        ({"file": "Tiny-Act.pdf"}, "no section, no quote"),
        ({"section": "s.16", "quote": ONLY_IN_16}, "no file"),
        ({"file": "Tiny-Act.pdf", "quote": ONLY_IN_16}, "no section"),
    ],
)
def test_a_malformed_citation_is_refused(registry: Registry, entry: object, why: str) -> None:
    problems, citation = check_citation(entry, registry)

    assert problems, why
    assert layers(problems) == [Layer.METADATA]
    assert citation is None


def test_an_unrecognised_field_is_refused(registry: Registry) -> None:
    """An unknown key is either a typo or a fact nothing checks. Both are defects."""
    problems, _ = check_citation(cite(sectoin="s.16"), registry)

    assert layers(problems) == [Layer.METADATA]


# ------------------------------------------------- unsupported document format


def test_a_document_whose_kind_has_no_parser_is_refused(tree: pathlib.Path) -> None:
    """A kind with no parser must be a hard error, never a fallback to searching
    the whole file — that fallback IS the bug this package removes."""
    manifest = tree / "Evidence_Library" / "manifest.jsonl"
    record = json.loads(manifest.read_text().strip())
    record["kind"] = "papyrus"
    manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")

    registry = Registry.load(manifest)

    with pytest.raises(model.CitationError, match="papyrus"):
        check_citation(cite(), registry)


def test_a_manifest_entry_without_a_kind_is_refused(tree: pathlib.Path) -> None:
    manifest = tree / "Evidence_Library" / "manifest.jsonl"
    record = json.loads(manifest.read_text().strip())
    del record["kind"]
    manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(model.CitationError, match="kind"):
        read_manifest(manifest)


def test_a_manifest_declaring_one_file_twice_is_refused(tree: pathlib.Path) -> None:
    """Two records for one file means two possible checksums and no way to choose."""
    manifest = tree / "Evidence_Library" / "manifest.jsonl"
    line = manifest.read_text().strip()
    manifest.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(model.CitationError, match="twice"):
        read_manifest(manifest)


def test_a_document_without_a_committed_sidecar_is_refused(
    tree: pathlib.Path, registry: Registry
) -> None:
    """Verification reads the sidecar so results never depend on a PDF library."""
    (tree / "Evidence_Library" / "sources" / "Tiny-Act.pdf.txt").unlink()

    with pytest.raises(model.CitationError, match="sidecar"):
        check_citation(cite(), registry)


# ------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("thirty  days", "thirty days"),
        ("plant\nand machinery", "plant and machinery"),
        ("“quoted”", '"quoted"'),
        ("s.16\u201317", "s.16-17"),
    ],
)
def test_normalisation_collapses_only_what_extraction_mangles(left: str, right: str) -> None:
    assert normalise(left) == normalise(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("thirty days", "forty-five days"),
        ("plant and machinery", "plant or machinery"),
        ("shall", "may"),
        ("September", "November"),
        ("Enterprise", "enterprise"),
    ],
)
def test_normalisation_never_collapses_a_difference_that_changes_meaning(
    left: str, right: str
) -> None:
    """Each pair here decides real money or a real duty. `plant and machinery`
    versus `plant or machinery` is the defined-term distinction in s.17(5)(d);
    September versus November is a six-week ITC cut-off.
    """
    assert normalise(left) != normalise(right)


# ------------------------------------------------------------------ end to end


def test_a_whole_tree_of_claims_passes_and_a_poisoned_one_fails(
    tree: pathlib.Path, registry: Registry
) -> None:
    """The gate binds on a real directory, not only on a single entry."""
    claims = tree / "claims"
    claims.mkdir()
    _, citation = check_citation(cite(), registry)
    assert citation is not None

    good = {"id": "T-1", "status": "VERIFIED", "evidence": [citation.to_entry()]}
    (claims / "good.json").write_text(json.dumps(good), encoding="utf-8")
    assert run(claims, registry).ok

    poisoned = {"id": "T-2", "status": "VERIFIED", "evidence": [cite(quote=ONLY_IN_17)]}
    (claims / "poisoned.json").write_text(json.dumps(poisoned), encoding="utf-8")
    result = run(claims, registry)

    assert not result.ok
    assert any("NOT inside" in failure for failure in result.failures)


def test_a_recorded_gap_is_not_a_failure(tree: pathlib.Path, registry: Registry) -> None:
    """UNKNOWN is honest. Only a claim asserting VERIFIED and failing is a defect."""
    claims = tree / "claims"
    claims.mkdir()
    for status in ("UNKNOWN", "NO AUTHORITATIVE SOURCE FOUND", "REQUIRES HUMAN ACCOUNTANT"):
        (claims / f"{status.replace(' ', '_')}.json").write_text(
            json.dumps({"id": status, "status": status}), encoding="utf-8"
        )

    assert run(claims, registry).ok


def test_an_unknown_status_is_a_failure(tree: pathlib.Path, registry: Registry) -> None:
    """A status nobody defined cannot be honest about anything."""
    claims = tree / "claims"
    claims.mkdir()
    (claims / "odd.json").write_text(
        json.dumps({"id": "T-3", "status": "PROBABLY FINE"}), encoding="utf-8"
    )

    result = run(claims, registry)

    assert not result.ok
    assert any("unknown status" in failure for failure in result.failures)


def test_verified_with_no_evidence_is_a_failure(tree: pathlib.Path, registry: Registry) -> None:
    """A status asserting evidence, with none, is the cheapest possible lie."""
    claims = tree / "claims"
    claims.mkdir()
    (claims / "empty.json").write_text(
        json.dumps({"id": "T-4", "status": "VERIFIED", "evidence": []}), encoding="utf-8"
    )

    result = run(claims, registry)

    assert not result.ok
    assert any("no evidence" in failure for failure in result.failures)
