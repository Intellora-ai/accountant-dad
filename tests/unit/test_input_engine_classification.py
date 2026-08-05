"""`classification` — attacked rather than confirmed.

Mirrors `test_input_engine_confidence.py`'s own stance: every prohibition the
module's docstring claims gets a test that tries to OBSERVE the violation,
not one that reads the docstring's word for it.

WHAT WOULD PROVE THIS MODULE WRONG, AND WHY EACH TEST IS SHAPED THE WAY IT IS.
    A hardcoded threshold is checked the same way
    `test_input_engine_confidence.py` checks `confidence_report.py`: by
    walking the module's own AST for ANY `Compare` node carrying a numeric,
    `Decimal`, `MIN` or `MAX` operand anywhere in its subtree — not by
    grepping for suspicious numbers, which a differently-spelled cutoff would
    evade.

    "No accounting conclusion reachable" is checked STRUCTURALLY: every
    public class, function, dataclass field and enum member this module
    exports is inspected by name for the vocabulary Engine 2, Engine 3 and
    Engine 5 own (`SUB_ENGINE_RESPONSIBILITIES.md` 1.3, `ENGINE_1_
    ARCHITECTURE.md` G9.1) — supplier, ledger, debit, tax rate, and so on.
    "Tax Invoice" and "Proforma Invoice" are deliberately NOT on that list:
    the task this module was built against states plainly that naming a
    document's own printed TYPE from structural evidence is exactly what it
    is authorised to do; deciding tax treatment, a ledger, or who the parties
    are is not.

    Everything else is exercised through the real, frozen dependencies this
    module was built against — `reader.Reading`/`TextRegion`/`SourceLocation`
    and `parser.ParsedStructure`/`Region`/`BoundingBox` — never a stand-in.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, is_dataclass

import pytest

from accountant_dad.engines.input_engine import classification as classification_module
from accountant_dad.engines.input_engine.classification import (
    CUE_CATALOG,
    ClassificationResult,
    ClassificationStatus,
    Cue,
    DocumentType,
    Instrument,
    MatchedCue,
    TypeCandidate,
    classify,
)
from accountant_dad.engines.input_engine.parser import BoundingBox, ParsedStructure, Region
from accountant_dad.engines.input_engine.reader import Backend, Reading, SourceLocation, TextRegion

# ── builders ─────────────────────────────────────────────────────────────────
# Deliberately explicit, matching test_input_engine_confidence.py's own
# convention: nothing under test is defaulted away.


def a_location(*, page_index: int = 0) -> SourceLocation:
    return SourceLocation(page_index=page_index, left=10.0, top=10.0, right=200.0, bottom=30.0)


def a_text_region(text: str, *, page_index: int = 0) -> TextRegion:
    return TextRegion(
        text=text, location=a_location(page_index=page_index), extraction_confidence=None
    )


def a_reading(*texts: str) -> Reading:
    return Reading(
        regions=tuple(a_text_region(text) for text in texts),
        backend=Backend.OCR,
        pages_read=1,
    )


EMPTY_READING = Reading(regions=(), backend=Backend.OCR, pages_read=0)


def a_box(*, page: int = 1) -> BoundingBox:
    return BoundingBox(page=page, left=5.0, top=5.0, right=100.0, bottom=25.0)


def a_parser_region(text: str | None, *, label: str = "section_header") -> Region:
    return Region(label=label, text=text, box=a_box(), detector="docling")


def a_structure(*texts: str) -> ParsedStructure:
    return ParsedStructure(
        source_reference="scan-001.pdf",
        page_count=1,
        regions=tuple(a_parser_region(text) for text in texts),
        tables=(),
    )


EMPTY_STRUCTURE = ParsedStructure(
    source_reference="scan-001.pdf", page_count=0, regions=(), tables=()
)

#: Named rather than inlined so ruff's own magic-value check (`PLR2004`) does
#: not have to be suppressed to assert an exact count — a suppression this
#: task's own "zero new suppressions" constraint forbids.
REPEATED_CUE_OCCURRENCES = 2
THREE_WAY_CANDIDATE_COUNT = 3


# ── a document with clear structural cues gets its type ──────────────────────


def test_a_document_with_one_clear_cue_is_typed_and_carries_its_own_evidence() -> None:
    reading = a_reading("ACME TRADERS", "TAX INVOICE", "Invoice No: INV-2026-0481")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE
    assert len(result.candidates) == 1
    (candidate,) = result.candidates
    assert candidate.document_type is DocumentType.TAX_INVOICE
    matched = candidate.matched_cues
    assert len(matched) == 1
    assert matched[0].cue == "TAX INVOICE"
    assert matched[0].matched_text == "TAX INVOICE"
    assert matched[0].instrument is Instrument.READER
    assert "page 0" in matched[0].location
    # A TYPED result carries no `reasons` — there is nothing to explain when
    # exactly one catalogued type was found. `None` is not `()`: a caller
    # that iterates `result.reasons` on a mutated `None` would raise, which
    # is exactly what this line catches.
    assert result.reasons == ()


def test_a_lower_case_heading_still_matches_case_insensitively() -> None:
    reading = a_reading("bill of supply")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.BILL_OF_SUPPLY
    assert result.candidates[0].matched_cues[0].matched_text == "bill of supply"


def test_a_cue_found_in_parser_output_is_typed_and_attributed_to_parser() -> None:
    structure = a_structure("DELIVERY CHALLAN")

    result = classify(EMPTY_READING, structure)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.DELIVERY_CHALLAN
    matched = result.candidates[0].matched_cues[0]
    assert matched.instrument is Instrument.PARSER
    assert "section_header" in matched.location


def test_the_same_cue_found_twice_is_recorded_as_two_pieces_of_evidence() -> None:
    """More confirming evidence is not deduplicated away — every occurrence a
    human could check survives, matching reader's own "source locations are
    emitted even for low-confidence extractions" stance on never discarding
    a locatable finding.
    """
    reading = a_reading("CREDIT NOTE", "Ref: 88", "CREDIT NOTE")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.TYPED
    assert len(result.candidates[0].matched_cues) == REPEATED_CUE_OCCURRENCES


# ── a document with no cues returns UNKNOWN, never a nearest guess ───────────


def test_a_document_with_no_catalogued_cue_is_unknown_with_reasons() -> None:
    reading = a_reading("ACME TRADERS PRIVATE LIMITED", "Thank you for your business")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.document_type is None
    # Exact text, not a substring: a mutation to either edge of the message
    # (the opening clause or the closing clause) must be observable here —
    # the middle clause alone (checked by the old substring assertion) never
    # moved when either edge was mutated by hand.
    assert result.reasons == (
        "none of this module's catalogued structural cues were found in the "
        "2 region(s) of text supplied by reader and parser; no type is "
        "guessed in their place.",
    )


def test_unknown_is_never_resolved_to_the_nearest_or_most_similar_catalogued_type() -> None:
    """ "INVOICE" alone is not "TAX INVOICE": a near-miss must not be rounded
    up to a real catalogued type. If this ever passed by accident the
    catalogue's own cue text would have to be a strict superstring match,
    which `_candidate_for` never performs partially.
    """
    reading = a_reading("INVOICE", "Total Due: 500")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()


# ── an empty Reading returns UNKNOWN rather than raising or defaulting ───────


def test_an_empty_reading_and_structure_returns_unknown_without_raising() -> None:
    result = classify(EMPTY_READING, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.document_type is None


def test_an_empty_reading_alongside_a_typed_structure_still_classifies() -> None:
    """An empty `Reading` must never poison classification through the other
    instrument — `reader` finding nothing is a fact about `reader`, not a
    reason to ignore what `parser` found.
    """
    structure = a_structure("PURCHASE ORDER")

    result = classify(EMPTY_READING, structure)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.PURCHASE_ORDER


# ── conflicting cues: BOTH sets of evidence survive, no silent winner ────────


def test_conflicting_cues_in_one_document_are_both_preserved_as_ambiguous() -> None:
    """A proforma invoice printed alongside the words "tax invoice" — exactly
    GOLDEN_DATASET.md negative control N1's failure shape — must never be
    silently resolved to one winner.
    """
    reading = a_reading("PROFORMA INVOICE", "This is not a TAX INVOICE")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.AMBIGUOUS
    assert result.document_type is None
    found_types = {candidate.document_type for candidate in result.candidates}
    assert found_types == {DocumentType.PROFORMA_INVOICE, DocumentType.TAX_INVOICE}
    by_type = {candidate.document_type: candidate for candidate in result.candidates}
    assert by_type[DocumentType.PROFORMA_INVOICE].matched_cues[0].cue == "PROFORMA INVOICE"
    assert by_type[DocumentType.TAX_INVOICE].matched_cues[0].cue == "TAX INVOICE"
    # Exact text, including the ", " that separates the two type names and
    # the closing "between them." clause — a substring check on either name
    # alone survives a mutation to the separator or the closing clause
    # because both names still appear somewhere in the string either way.
    assert result.reasons == (
        "structural cues were found for more than one catalogued document "
        "type (Tax Invoice, Proforma Invoice); this module does not choose "
        "between them.",
    )


def test_conflicting_cues_split_across_reader_and_parser_are_both_preserved() -> None:
    reading = a_reading("DEBIT NOTE")
    structure = a_structure("CREDIT NOTE")

    result = classify(reading, structure)

    assert result.status is ClassificationStatus.AMBIGUOUS
    by_type = {candidate.document_type: candidate for candidate in result.candidates}
    assert by_type[DocumentType.DEBIT_NOTE].matched_cues[0].instrument is Instrument.READER
    assert by_type[DocumentType.CREDIT_NOTE].matched_cues[0].instrument is Instrument.PARSER


def test_three_way_ambiguity_preserves_every_candidate_not_just_the_first_two() -> None:
    reading = a_reading("QUOTATION", "PURCHASE ORDER", "DELIVERY CHALLAN")

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.AMBIGUOUS
    assert len(result.candidates) == THREE_WAY_CANDIDATE_COUNT


# ── no hardcoded threshold ─────────────────────────────────────────────────────
# ENGINE_1_CONFIDENCE_PARAMETERS.md: "No numeric literal used as a threshold
# ... No comparison against a constant that is not loaded from configuration
# ... A mutation that inserts a default must turn [this] red."


def _is_a_hardcoded_numeric_operand(node: ast.AST) -> bool:
    """True for anything that could supply an invented cutoff to a `Compare`.

    Identical rule to `test_input_engine_confidence.py`'s own detector,
    repeated here rather than imported: a shared helper two test files both
    rely on would itself become a place a hardcoded threshold could hide if
    it were ever "simplified" to miss a shape either module actually uses.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return not isinstance(node.value, bool)
    if isinstance(node, ast.Name) and node.id in {"Decimal", "MIN", "MAX"}:
        return True
    return isinstance(node, ast.Attribute) and node.attr in {"Decimal", "MIN", "MAX"}


def test_no_numeric_comparison_appears_anywhere_in_the_module() -> None:
    """`classification_accept` (`ENGINE_1_CONFIDENCE_PARAMETERS.md` #9) is
    `UNSET`, and `ENGINE_1_ARCHITECTURE.md` G9.2 blocks any confidence
    threshold behaviour for it until calibration passes. This module produces
    no score at all, so it has nothing to gate and no cutoff to invent — every
    real branch is `is None`/`is not None`, string containment, or a `match`
    on the SHAPE of a tuple. Walks the WHOLE comparison subtree, not just the
    immediate operands, so a mutation such as
    `if len(candidates) > Decimal("1"):` cannot hide inside a `Decimal(...)`
    call the way a bare `ast.Constant` check would miss.
    """
    source = inspect.getsource(classification_module)
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is mutmut's instrumentation rather than ours. Asserting on it "
            "measures the mutation tool, not the code under test — and a structural "
            "assertion about OUR source cannot be evaluated against a file we did "
            "not write. Skipped under mutation only; it runs in every ordinary suite."
        )
    tree = ast.parse(source)
    offending_lines = sorted(
        {
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Compare)
            for descendant in ast.walk(node)
            if _is_a_hardcoded_numeric_operand(descendant)
        }
    )
    assert offending_lines == [], (
        f"numeric comparison(s) found at line(s) {offending_lines} of "
        "classification.py. classification_accept is UNSET; a module with "
        "nothing to gate needs no cutoffs."
    )


def test_status_is_decided_by_pattern_matching_the_shape_not_a_count() -> None:
    """Structural proof to accompany the AST sweep above: `classify` never
    calls `len()` on `candidates` and compares it to anything — the THREE-WAY
    decision is made entirely by `match candidates: case () / case (only,) /
    case multiple`, which is what makes the AST sweep able to stay a
    zero-tolerance "no numeric Compare at all" rule instead of a narrower
    "no Compare against a suspicious-looking number" rule that a renamed
    threshold could dodge.
    """
    source = inspect.getsource(classification_module.classify)
    if "__mutmut_" in source or "MUTANT_UNDER_TEST" in source:
        pytest.skip(
            "mutmut rewrote this module in its `mutants/` copy, so the source read "
            "here is mutmut's instrumentation rather than ours. Asserting on it "
            "measures the mutation tool, not the code under test — and a structural "
            "assertion about OUR source cannot be evaluated against a file we did "
            "not write. Skipped under mutation only; it runs in every ordinary suite."
        )
    tree = ast.parse(source)
    assert any(isinstance(node, ast.Match) for node in ast.walk(tree))


def test_cue_text_must_already_be_upper_case() -> None:
    """A defence against the catalogue itself drifting: a cue added later in
    mixed case would silently under-match (case-insensitive matching upper-
    cases the SOURCE text, not the catalogue), and this is refused at
    construction rather than discovered as a false UNKNOWN.
    """
    with pytest.raises(ValueError, match="upper-case"):
        Cue(DocumentType.TAX_INVOICE, "Tax Invoice")


def test_the_real_catalog_entries_are_all_already_upper_case() -> None:
    """Every entry in the real catalogue actually satisfies the rule above —
    exercised against the REAL `CUE_CATALOG`, not a synthetic one."""
    for cue in CUE_CATALOG:
        assert cue.text == cue.text.upper()


# ── no accounting conclusion is reachable from the module's public surface ───


#: Deliberately does NOT include "debit" or "credit" bare — "Credit Note" and
#: "Debit Note" are two of the eight catalogued DOCUMENT TYPES this module is
#: authorised to name (they are what CGST calls the document, not a decision
#: about which side of a ledger anything goes), and a bare substring would
#: flag its own legitimate catalogue. The compound forms below target the
#: DECISION vocabulary — which side an entry sits on, who owes whom — without
#: colliding with the noun that names the document.
_FORBIDDEN_ACCOUNTING_VOCABULARY = (
    "supplier",
    "buyer",
    "vendor",
    "customer",
    "party",
    "debit_entry",
    "credit_entry",
    "debit_amount",
    "credit_amount",
    "debit_side",
    "credit_side",
    "creditor",
    "debtor",
    "ledger",
    "journal",
    "gstin",
    "hsn",
    "itc",
    "reverse_charge",
    "place_of_supply",
    "voucher",
    "account",
    "tax_rate",
    "tax_amount",
    "taxable",
    "posting",
    "post_",
    "payable",
    "receivable",
    "amount",
    "value",
    "quantity",
    "rate",
)


def _public_names() -> list[str]:
    """Every public name this module DEFINES: classes, functions, module-level
    constants and (for dataclasses) their own field names.

    Filtered by `__module__` so an imported name (`Reading`, `ParsedStructure`,
    `StrEnum`, ...) is never checked as if this module had defined it — this
    test is about what `classification` EXPORTS, not what it imports.
    """
    names: list[str] = []
    for name, member in inspect.getmembers(classification_module):
        if name.startswith("_"):
            continue
        owner = getattr(member, "__module__", classification_module.__name__)
        if owner != classification_module.__name__:
            continue
        names.append(name)
        if is_dataclass(member):
            names.extend(field.name for field in fields(member))
    return names


def _enum_member_names() -> list[str]:
    names: list[str] = []
    for _name, member in inspect.getmembers(classification_module, inspect.isclass):
        if issubclass(member, str) and hasattr(member, "__members__"):
            names.extend(member.__members__)
    return names


def test_no_accounting_conclusion_vocabulary_appears_on_the_public_surface() -> None:
    candidates_to_check = [name.lower() for name in _public_names() + _enum_member_names()]

    offenders = [
        (name, marker)
        for name in candidates_to_check
        for marker in _FORBIDDEN_ACCOUNTING_VOCABULARY
        if marker in name
    ]

    assert offenders == [], (
        f"accounting-decision vocabulary found on the public surface: {offenders}. "
        "This module names a document's own TYPE from structural evidence; "
        "deciding parties, ledgers, tax treatment or amounts belongs to "
        "Engine 2, Engine 3 or Engine 5, never to this one."
    )


def test_document_type_values_carry_no_field_that_could_hold_a_money_amount() -> None:
    """Attacks the schema, not just the names: no dataclass this module
    DEFINES may declare a field annotated as carrying a number at all —
    everything a caller can read off a `ClassificationResult` is text,
    an enum, or a tuple of one of those.

    Filtered to classes `classification` itself defines — `reader.SourceLocation`
    and `parser.ParsedStructure` legitimately carry `int`/`float` page geometry
    imported alongside them, and checking an imported type would be attacking
    the wrong module's boundary.
    """
    numeric_annotations = {"int", "float", "Decimal", "Confidence"}
    offenders = []
    for _name, member in inspect.getmembers(classification_module, is_dataclass):
        # `is_dataclass` admits both a dataclass INSTANCE and a dataclass CLASS,
        # and only the class carries `__name__`. A module attribute that is a
        # dataclass is always the class, so narrowing to `type` costs nothing
        # here and is stricter than a suppression would have been: mypy now
        # checks the rest of the loop instead of being told to look away.
        if not isinstance(member, type):
            continue
        if getattr(member, "__module__", None) != classification_module.__name__:
            continue
        for field in fields(member):
            annotation = str(field.type)
            if any(marker in annotation for marker in numeric_annotations):
                offenders.append((member.__name__, field.name, annotation))

    assert offenders == [], f"numeric-carrying field(s) found: {offenders}"


def test_classify_function_signature_returns_only_this_modules_own_result_type() -> None:
    signature = inspect.signature(classify)
    assert signature.return_annotation == "ClassificationResult"


# ── construction refuses malformed evidence, never repairs it silently ───────


def test_a_matched_cue_refuses_a_blank_cue_text() -> None:
    with pytest.raises(ValueError, match="must not be empty or blank"):
        MatchedCue(
            cue="   ", instrument=Instrument.READER, matched_text="TAX INVOICE", location="page 0"
        )


def test_a_matched_cue_refuses_a_blank_location() -> None:
    with pytest.raises(ValueError, match="must not be empty or blank"):
        MatchedCue(
            cue="TAX INVOICE", instrument=Instrument.READER, matched_text="TAX INVOICE", location=""
        )


def test_a_type_candidate_refuses_to_be_built_with_no_evidence() -> None:
    with pytest.raises(ValueError, match="carries no evidence"):
        TypeCandidate(document_type=DocumentType.TAX_INVOICE, matched_cues=())


def test_a_cue_refuses_blank_text() -> None:
    with pytest.raises(ValueError, match="must not be empty or blank"):
        Cue(DocumentType.TAX_INVOICE, "   ")


# ── the result's own status/candidates invariant is enforced, not assumed ────


def test_typed_status_paired_with_zero_candidates_is_refused() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        ClassificationResult(status=ClassificationStatus.TYPED, candidates=(), reasons=())


def test_unknown_status_paired_with_a_candidate_is_refused() -> None:
    matched = MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 0",
    )
    candidate = TypeCandidate(document_type=DocumentType.TAX_INVOICE, matched_cues=(matched,))
    with pytest.raises(ValueError, match="inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.UNKNOWN, candidates=(candidate,), reasons=()
        )


def test_ambiguous_status_paired_with_one_candidate_is_refused() -> None:
    matched = MatchedCue(
        cue="TAX INVOICE",
        instrument=Instrument.READER,
        matched_text="TAX INVOICE",
        location="page 0",
    )
    candidate = TypeCandidate(document_type=DocumentType.TAX_INVOICE, matched_cues=(matched,))
    with pytest.raises(ValueError, match="inconsistent"):
        ClassificationResult(
            status=ClassificationStatus.AMBIGUOUS, candidates=(candidate,), reasons=()
        )


def test_document_type_property_reads_none_for_both_unknown_and_ambiguous() -> None:
    """The dishonest shortcut this property must not offer: a caller reading
    only `.document_type` must see the SAME `None` whether the document was
    genuinely untyped or genuinely ambiguous — never a value for either.
    """
    unknown = classify(EMPTY_READING, EMPTY_STRUCTURE)
    ambiguous = classify(a_reading("QUOTATION", "PURCHASE ORDER"), EMPTY_STRUCTURE)

    assert unknown.document_type is None
    assert ambiguous.document_type is None


# ── every catalogued type is independently reachable ──────────────────────────


@pytest.mark.parametrize("cue", CUE_CATALOG)
def test_every_catalogued_cue_independently_types_its_own_document(cue: Cue) -> None:
    """Each of the eight catalogued types is exercised on its own, so a future
    edit that silently drops or renames one is caught here rather than only
    by the single-cue tests above happening to cover it.
    """
    reading = a_reading(cue.text)

    result = classify(reading, EMPTY_STRUCTURE)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is cue.document_type


def test_the_catalog_names_one_cue_per_document_type_with_no_duplicate_types() -> None:
    document_types = [cue.document_type for cue in CUE_CATALOG]
    assert len(document_types) == len(set(document_types))
    assert set(document_types) == set(DocumentType)


def test_no_two_catalogued_cues_are_substrings_of_one_another() -> None:
    """A cue that is a substring of a different type's cue would make the two
    types inseparable — every document matching the shorter one would also,
    silently, match the longer one. Exercised against the REAL catalogue.
    """
    offenders = [
        (a.document_type, b.document_type)
        for a in CUE_CATALOG
        for b in CUE_CATALOG
        if a is not b and a.text in b.text
    ]
    assert offenders == []


# ── real interoperability with reader's and parser's frozen types ────────────


def test_classify_accepts_the_real_reading_and_parsed_structure_types_directly() -> None:
    """REAL + ISOLATED (`CLAUDE.md` §J.6): both arguments are the genuine
    `reader.Reading` and `parser.ParsedStructure` this module claims to
    accept, never a stand-in shaped to fit.
    """
    reading = Reading(
        regions=(
            TextRegion(
                text="TAX INVOICE",
                location=SourceLocation(page_index=0, left=0.0, top=0.0, right=1.0, bottom=1.0),
                extraction_confidence=None,
            ),
        ),
        backend=Backend.PDF_TEXT_LAYER,
        pages_read=1,
    )
    structure = ParsedStructure(source_reference="real.pdf", page_count=1, regions=(), tables=())

    result = classify(reading, structure)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE


def test_a_parser_region_with_no_text_contributes_no_evidence() -> None:
    """`parser.Region.text` is `None` when the detector reported nothing —
    `ENGINE_1_INPUT_ENGINE_RULES.md:569`'s three-state rule. A `None` region
    must never be coerced into a string and searched.
    """
    region = Region(label="picture", text=None, box=a_box(), detector="docling")
    structure = ParsedStructure(
        source_reference="scan.pdf", page_count=1, regions=(region,), tables=()
    )

    result = classify(EMPTY_READING, structure)

    assert result.status is ClassificationStatus.UNKNOWN
