"""`classification` — a second, adversarial pass, written to make the module
say something WRONG rather than to watch it say something right.

`CLAUDE.md` §J.10 and §I.10 both ask for a separate red-team pass with a
different stance from the one that wrote the code. `test_input_engine_
classification.py` already attacks the module's stated prohibitions. This file
attacks the things that file's stance could not see, in five directions:

  1. THE "NO NUMBER" CLAIM, VERIFIED TWO WAYS AT ONCE. The existing AST sweep
     proves no `Compare` carries a numeric operand. That is necessary and not
     sufficient — a winner can be picked with no comparison at all, by slicing
     (`candidates[:1]`) or by `max(..., key=len)`. So this file adds a
     structural sweep for those shapes AND a behavioural one: the status is
     shown to depend only on HOW MANY DISTINCT TYPES matched, never on how much
     evidence any of them carries. Five cues for one type and one for another
     still yields both, in catalogue order.

  2. NEAR-MISSES, WHICH ARE WHERE A CLASSIFIER GUESSES. Thirteen headings that
     a human would read as one of the eight catalogued types, and that this
     module must refuse to round up: transposed letters, a missing space, a
     hyphen, a line break, a heading split across two regions, and one partial
     cue from each of three different types at once.

  3. AMBIGUITY THAT MUST NOT COLLAPSE. All eight types at once, and an
     ambiguity where one candidate carries five times the evidence of the
     other. Every candidate, every matched cue and the catalogue's own ordering
     must survive both.

  4. THE ACCOUNTING BOUNDARY, ATTACKED AT THE VALUES RATHER THAN THE NAMES.
     The existing suite sweeps public NAMES for accounting vocabulary. A
     conclusion can just as easily hide in a `StrEnum`'s VALUE or in a `reasons`
     string, both of which a caller reads and neither of which that sweep
     touches. Every enum value this module defines, and every `reasons` string
     all three real branches produce, is swept here instead — with the verbatim
     evidence quotes deliberately EXCLUDED from the sweep, because quoting what
     a document printed is the evidence, and is the one thing this module is
     supposed to do (`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 1).

  5. UNICODE, WHERE CASE-INSENSITIVE MATCHING GOES WRONG IN BOTH DIRECTIONS.
     A Cyrillic lookalike must not match. An invisible character must not be
     able to make a visible heading match. Both directions are measured here,
     and one of them turns out to be surprising: Python's `str.upper()` is
     Unicode-aware, so a Turkish dotless i (U+0131) folds into ASCII `I` and
     match. That is pinned rather than assumed.

THE DEFECT THIS PASS FOUND IS NOW FIXED, AND ONE EXPECTATION IN THIS FILE WAS
CORRECTED TO MATCH. `test_a_catalogued_phrase_in_body_prose_must_not_become_
the_documents_type` was written red on purpose and is now green: `classify`
requires a cue to OPEN or CLOSE the region it was found in, as a whole phrase,
before it counts as this document's own heading.

That rule also changed one expectation this file had pinned, and the change is
recorded rather than absorbed. `"\\x1b[1mTAX INVOICE\\x1b[0m"` — a heading
welded to layout noise on BOTH sides — used to read as TYPED and now reads as
UNKNOWN. Under ANY whole-word rule it must: the character before the "T" is the
letter "m", so the cue is not a word there, and this module cannot know that
`\\x1b[1m` is a terminal escape rather than part of a word. That is the same
class of artefact-induced false negative `test_an_invisible_character_makes_a_
visible_heading_read_as_unknown` already pins for zero-width spaces, and it
errs the safe way — the module refuses instead of guessing. The test's own
point, that refusing everything is not robustness, is kept and now measured on
a heading that carries control characters on one side, which still matches.
"""

from __future__ import annotations

import ast

import pytest
from authored_source import authored_source

from accountant_dad.engines.input_engine import classification as classification_module
from accountant_dad.engines.input_engine.classification import (
    CUE_CATALOG,
    ClassificationResult,
    ClassificationStatus,
    DocumentType,
    Instrument,
    classify,
)
from accountant_dad.engines.input_engine.parser import BoundingBox, ParsedStructure, Region
from accountant_dad.engines.input_engine.reader import Backend, Reading, SourceLocation, TextRegion

# ── builders ─────────────────────────────────────────────────────────────────
# Deliberately this file's own, not imported from `test_input_engine_
# classification.py`: a red-team pass that shares its target's fixtures shares
# its blind spots too, which is precisely the trap `CLAUDE.md` §J.(b) names.


def a_location(*, page_index: int = 0) -> SourceLocation:
    return SourceLocation(page_index=page_index, left=10.0, top=10.0, right=200.0, bottom=30.0)


def a_reading(*texts: str) -> Reading:
    return Reading(
        regions=tuple(
            TextRegion(text=text, location=a_location(), extraction_confidence=None)
            for text in texts
        ),
        backend=Backend.OCR,
        pages_read=1,
    )


def a_structure(*texts: str | None) -> ParsedStructure:
    return ParsedStructure(
        source_reference="scan-redteam.pdf",
        page_count=1,
        regions=tuple(
            Region(
                label="section_header",
                text=text,
                box=BoundingBox(page=1, left=5.0, top=5.0, right=100.0, bottom=25.0),
                detector="docling",
            )
            for text in texts
        ),
        tables=(),
    )


NOTHING_READ = Reading(regions=(), backend=Backend.OCR, pages_read=0)
NOTHING_STRUCTURED = ParsedStructure(
    source_reference="scan-redteam.pdf", page_count=0, regions=(), tables=()
)

#: Named because ruff's magic-value check (`PLR2004`) forbids the literal, and
#: because each number IS the assertion rather than an incidental size.
EVERY_CATALOGUED_TYPE = 8
LOPSIDED_EVIDENCE_COUNT = 5
REPEATED_SINGLE_TYPE_COUNT = 7
THREE_PARTIAL_CUES = 3
A_LONG_REGION = 100_000
MANY_REGIONS = 500


def unknown_reason(region_count: int) -> str:
    """The exact sentence `classify` emits for UNKNOWN, region count included.

    Written out here rather than substring-matched: the count is the part a
    silent change to which sources are searched would move, and a substring
    assertion on the surrounding words would not notice.
    """
    return (
        "none of this module's catalogued structural cues were found in the "
        f"{region_count} region(s) of text supplied by reader and parser; no "
        "type is guessed in their place."
    )


def ambiguity_reason(*types: DocumentType) -> str:
    names = ", ".join(document_type.value for document_type in types)
    return (
        f"structural cues were found for more than one catalogued document "
        f"type ({names}); this module does not choose between them."
    )


#: What `_describe_reader_location` renders for `a_location()`, and what
#: `_describe_parser_location` renders for `a_structure`'s region. Written out
#: rather than substring-matched for the same reason `unknown_reason` is: a
#: reason that names WHERE a set-aside cue was found is only useful if the
#: place it names is actually checked.
READER_LOCATION = "page 0, (10.0, 10.0)-(200.0, 30.0)"
PARSER_LOCATION = "page 1, 'section_header' region, (5.0, 5.0)-(100.0, 25.0)"


def no_heading_reason(region_count: int) -> str:
    """The sentence UNKNOWN carries when a cue WAS on the page but not where a
    heading sits. Deliberately a different sentence from `unknown_reason`:
    saying "none were found" when one was found and set aside would be a
    fabricated reason (`CLAUDE.md` Law 24), and this pins that they differ.
    """
    return (
        "no catalogued structural cue was found where a document prints its "
        f"own heading, in the {region_count} region(s) of text supplied by "
        "reader and parser; no type is guessed in their place."
    )


def set_aside_reason(cue: str, location: str) -> str:
    """The exact sentence `classify` emits for a cue found with running text on
    both sides of it. Every word is pinned: this string is the ONLY record that
    the module saw the cue at all, so a silent edit to it is a silent loss of
    the evidence.
    """
    return (
        f"the catalogued cue '{cue}' was found at {location}, with other text "
        "on both sides of it inside the same region — where a document refers "
        "to a DIFFERENT document, not where it prints its own heading. It is "
        "recorded here and names no type."
    )


# ── 1. the "no number" claim, attacked structurally and behaviourally ────────


def test_no_slice_anywhere_could_silently_keep_only_the_first_candidate() -> None:
    """The hole a `Compare`-only sweep leaves open.

    `candidates[:1]` picks a single winner from an ambiguous document while
    introducing no comparison, no numeric threshold and no `len()` — the
    existing AST sweep would stay green through it, and every AMBIGUOUS
    document would silently become TYPED. Nothing in this module has any
    legitimate need to slice, so the rule here is zero tolerance.
    """
    tree = ast.parse(authored_source(classification_module))

    slices = sorted({node.lineno for node in ast.walk(tree) if isinstance(node, ast.Slice)})

    assert slices == [], (
        f"slice expression(s) found at line(s) {slices} of classification.py. "
        "A slice is how a single winner gets picked out of several candidates "
        "without any comparison for the existing AST sweep to catch."
    )


def test_no_ranking_builtin_could_pick_a_most_likely_type_without_comparing() -> None:
    """The second hole: `max(candidates, key=len)` ranks without comparing.

    `sorted`, `max` and `min` each choose a winner while leaving no `Compare`
    node and no numeric literal in the module. AMBIGUOUS exists precisely so
    that no winner is chosen, so none of the three may appear.
    """
    ranking = {"max", "min", "sorted"}
    tree = ast.parse(authored_source(classification_module))

    found = sorted(
        {
            f"{node.func.id}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ranking
        }
    )

    assert found == [], (
        f"ranking builtin(s) found at {found} in classification.py. Choosing a "
        "most-likely type is exactly what AMBIGUOUS exists to refuse."
    )


@pytest.mark.parametrize(
    ("texts", "expected"),
    [
        ((), ClassificationStatus.UNKNOWN),
        (("nothing catalogued here",), ClassificationStatus.UNKNOWN),
        (("TAX INVOICE",), ClassificationStatus.TYPED),
        (("TAX INVOICE", "TAX INVOICE", "TAX INVOICE"), ClassificationStatus.TYPED),
        (("TAX INVOICE", "QUOTATION"), ClassificationStatus.AMBIGUOUS),
        (("TAX INVOICE", "TAX INVOICE", "QUOTATION"), ClassificationStatus.AMBIGUOUS),
    ],
)
def test_the_status_tracks_distinct_types_only_never_the_amount_of_evidence(
    texts: tuple[str, ...], expected: ClassificationStatus
) -> None:
    """The behavioural half of "no number": the status is a function of how
    many DISTINCT catalogued types matched, and of nothing else. Three cues for
    one type is still TYPED; one cue each for two types is AMBIGUOUS even
    though it carries less evidence in total.
    """
    assert classify(a_reading(*texts), NOTHING_STRUCTURED).status is expected


def test_five_pieces_of_evidence_for_one_type_do_not_outrank_one_for_another() -> None:
    """ "Most cues wins" is the tie-break this module claims not to have, and it
    is the one a reader would most plausibly add later. Measured directly: the
    lopsided candidate does not win, is not listed first, and loses no evidence.
    """
    reading = a_reading(
        *(["QUOTATION"] * LOPSIDED_EVIDENCE_COUNT),
        "TAX INVOICE",
    )

    result = classify(reading, NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.AMBIGUOUS
    assert result.document_type is None
    evidence = {
        candidate.document_type: len(candidate.matched_cues) for candidate in result.candidates
    }
    assert evidence == {
        DocumentType.TAX_INVOICE: 1,
        DocumentType.QUOTATION: LOPSIDED_EVIDENCE_COUNT,
    }
    # catalogue order, not evidence order: TAX_INVOICE is first in DocumentType
    assert [candidate.document_type for candidate in result.candidates] == [
        DocumentType.TAX_INVOICE,
        DocumentType.QUOTATION,
    ]
    assert result.reasons == (ambiguity_reason(DocumentType.TAX_INVOICE, DocumentType.QUOTATION),)


def test_one_type_repeated_seven_times_stays_typed_and_keeps_all_seven_quotes() -> None:
    reading = a_reading(*(["DELIVERY CHALLAN"] * REPEATED_SINGLE_TYPE_COUNT))

    result = classify(reading, NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.DELIVERY_CHALLAN
    assert len(result.candidates[0].matched_cues) == REPEATED_SINGLE_TYPE_COUNT


# ── 2. near-misses are never rounded up to a catalogued type ─────────────────


@pytest.mark.parametrize(
    "heading",
    [
        "TAX INVOCIE",  # two letters transposed
        "TAX INVOIC",  # truncated by one letter
        "TAXINVOICE",  # the space lost by a layout engine
        "TAX  INVOICE",  # two spaces, as a justified heading often prints
        "TAX-INVOICE",  # hyphenated
        "TAX\nINVOICE",  # wrapped across two lines inside one region
        "INVOICE TAX",  # the same two words, the other way round
        "PRO FORMA INVOICE",  # the other common spelling of proforma
        "BILL OF SUPPLIES",  # plural, so the catalogued cue is not contained
        "DELIVERY CHALAN",  # one L
        "PURCHASE ORDR",  # a vowel dropped
        "CREDIT MEMO",  # the American name for a credit note
        "T A X   I N V O I C E",  # letter-spaced, as a designed heading prints
    ],
)
def test_a_near_miss_heading_is_never_rounded_up_to_the_type_it_resembles(heading: str) -> None:
    """Thirteen headings a human would read as one of the eight catalogued
    types. Every one must read as UNKNOWN, because the alternative — picking
    the nearest catalogued type — is the confident guess `ENGINE_1_INPUT_
    ENGINE_RULES.md:647` calls a failure "even if the guess happened to be
    right".
    """
    result = classify(a_reading(heading), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.document_type is None
    assert result.reasons == (unknown_reason(1),)


def test_a_cue_split_across_two_reader_regions_is_never_joined_into_a_match() -> None:
    """If the matcher ever concatenated its sources before searching, this
    would silently become TYPED — a match assembled by this module out of two
    things the document never printed together.
    """
    result = classify(a_reading("TAX", "INVOICE"), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.reasons == (unknown_reason(2),)


def test_a_cue_split_across_the_two_instruments_is_never_joined_either() -> None:
    """The sharper version: half the phrase from `reader`, half from `parser`.
    Pooling two instruments' text is the exact thing `CONFIDENCE_SPECIFICATION.md`
    §3.2 forbids doing with their scores, and it would be no better here.
    """
    result = classify(a_reading("PURCHASE"), a_structure("ORDER"))

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.reasons == (unknown_reason(2),)


def test_one_partial_cue_from_each_of_three_types_still_resolves_to_nothing() -> None:
    """Three separate hints, none of them complete. A classifier under pressure
    to answer would pick whichever partial cue it saw most of; this one must
    report that it found nothing at all.
    """
    result = classify(a_reading("TAX", "CREDIT", "PURCHASE"), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.reasons == (unknown_reason(THREE_PARTIAL_CUES),)


# ── 3. ambiguity never collapses, however lopsided or however wide ───────────


def test_all_eight_catalogued_types_at_once_survive_intact_and_in_catalogue_order() -> None:
    """The widest ambiguity this module can produce. Every candidate survives,
    the order is the catalogue's rather than the document's, and the convenient
    single answer stays `None`.
    """
    every_heading = tuple(cue.text for cue in CUE_CATALOG)

    result = classify(a_reading(*every_heading), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.AMBIGUOUS
    assert len(result.candidates) == EVERY_CATALOGUED_TYPE
    assert [candidate.document_type for candidate in result.candidates] == list(DocumentType)
    assert result.document_type is None
    assert result.reasons == (ambiguity_reason(*DocumentType),)


def test_ambiguity_order_follows_the_catalogue_not_the_order_the_document_printed() -> None:
    """ "First one seen wins" is the other tie-break a later reader might add.
    QUOTATION is printed first here and is still listed second, because
    `DocumentType`'s own order — not the document's — decides.
    """
    result = classify(a_reading("QUOTATION", "TAX INVOICE"), NOTHING_STRUCTURED)

    assert [candidate.document_type for candidate in result.candidates] == [
        DocumentType.TAX_INVOICE,
        DocumentType.QUOTATION,
    ]
    assert result.reasons == (ambiguity_reason(DocumentType.TAX_INVOICE, DocumentType.QUOTATION),)


def test_the_same_cue_found_by_both_instruments_is_kept_as_two_separate_findings() -> None:
    """`reader`'s raw text and `parser`'s laid-out region are different kinds
    of finding and are never merged into one. Both survive, each carrying which
    instrument produced it.
    """
    result = classify(a_reading("TAX INVOICE"), a_structure("TAX INVOICE"))

    assert result.status is ClassificationStatus.TYPED
    (candidate,) = result.candidates
    assert [cue.instrument for cue in candidate.matched_cues] == [
        Instrument.READER,
        Instrument.PARSER,
    ]


# ── 4. no accounting conclusion, attacked at the VALUES not the names ────────

#: The vocabulary of a TREATMENT decision — whether something may be posted,
#: is allowed, is owed, or is safe. Distinct from the vocabulary of a document
#: TYPE, which this module is authorised to name: "Tax Invoice" and "Credit
#: Note" are what CGST calls the documents, not decisions about them.
_TREATMENT_VOCABULARY = (
    "post",
    "safe",
    "approv",
    "eligible",
    "payable",
    "receivable",
    "recommend",
    "accept",
    "reject",
    "genuine",
    "should be",
    "must be",
    "ledger",
    "tax rate",
    "input credit",
    "reverse charge",
)


def _every_value_a_caller_can_read_off_this_module() -> list[str]:
    """Every enum VALUE this module defines — the surface a public-NAME sweep
    cannot see, and the one a caller actually renders.
    """
    values: list[str] = []
    for enumeration in (DocumentType, Instrument, ClassificationStatus):
        values.extend(member.value for member in enumeration)
    return values


def test_no_enum_value_this_module_defines_states_an_accounting_treatment() -> None:
    """`test_no_accounting_conclusion_vocabulary_appears_on_the_public_surface`
    sweeps NAMES. A conclusion is far easier to write into a VALUE — a status
    reading "safe to post" would pass that sweep untouched and be the string a
    caller displays.
    """
    offenders = [
        (value, marker)
        for value in _every_value_a_caller_can_read_off_this_module()
        for marker in _TREATMENT_VOCABULARY
        if marker in value.lower()
    ]

    assert offenders == [], (
        f"treatment vocabulary found in an enum VALUE: {offenders}. This module "
        "names a document's type; whether anything may be posted belongs to "
        "Engine 3 and Engine 5."
    )


def test_no_reasons_string_any_branch_produces_states_an_accounting_treatment() -> None:
    """The other string a caller reads. All three real branches are exercised
    through the real `classify`, not read off the source.
    """
    produced = (
        classify(NOTHING_READ, NOTHING_STRUCTURED),
        classify(a_reading("TAX INVOICE"), NOTHING_STRUCTURED),
        classify(a_reading("TAX INVOICE", "QUOTATION"), NOTHING_STRUCTURED),
    )

    offenders = [
        (reason, marker)
        for result in produced
        for reason in result.reasons
        for marker in _TREATMENT_VOCABULARY
        if marker in reason.lower()
    ]

    assert offenders == []


def test_a_document_dense_with_treatment_language_yields_a_type_and_verbatim_quotes_only() -> None:
    """The boundary attack: a heading that is this module's business printed in
    the same region as language that is emphatically Engine 3's and Engine 5's.

    The evidence quote MAY contain that language — quoting what a document
    printed is the observation (`COMMUNICATION_RULES_INPUT_ENGINE.md` Rule 1).
    What must not happen is the module ADDING anything: `matched_text` has to
    be the source region's text character-for-character, and everything else
    the result exposes has to stay clean.
    """
    printed = "TAX INVOICE - reverse charge applicable, ITC eligible, place of supply 27"

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE
    assert result.reasons == ()
    (candidate,) = result.candidates
    (matched,) = candidate.matched_cues
    # the quote is the document's own text, unedited, unnormalised, untruncated
    assert matched.matched_text == printed
    # and everything this module wrote itself carries none of that language
    authored = (matched.cue, matched.location, result.status.value, candidate.document_type.value)
    offenders = [
        (text, marker)
        for text in authored
        for marker in _TREATMENT_VOCABULARY
        if marker in text.lower()
    ]
    assert offenders == []


def test_a_proforma_says_nothing_about_whether_it_may_be_posted() -> None:
    """`GOLDEN_DATASET.md` negative control N1, from the other side: a proforma
    that announces its own ineligibility. Naming it a Proforma Invoice is this
    module's job; agreeing or disagreeing with the ineligibility is not, and
    the result must not contain a word about it outside the quote.
    """
    printed = "PROFORMA INVOICE - NOT VALID FOR INPUT TAX CREDIT"

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.PROFORMA_INVOICE
    assert result.reasons == ()
    (matched,) = result.candidates[0].matched_cues
    assert matched.matched_text == printed
    assert matched.cue == "PROFORMA INVOICE"


# ── 5. case, whitespace and unicode, in both failure directions ──────────────

#: Spelled as escapes, never as the glyphs themselves. Every codepoint below
#: is either invisible or indistinguishable from an ASCII letter in an editor,
#: so a literal here would be a character a reviewer cannot see and cannot
#: check — which is what ruff's RUF001, PLE2502 and PLE2515 refuse. The escape
#: is both the more honest spelling and the lint-clean one; the VALUE that
#: reaches `classify` is byte-for-byte what it was.
#: U+0410 CYRILLIC CAPITAL LETTER A, which renders identically to Latin A.
CYRILLIC_A = "\u0410"
#: U+200B ZERO WIDTH SPACE — invisible, and a real artefact of PDF text layers.
ZERO_WIDTH_SPACE = "\u200b"
#: U+200F RIGHT-TO-LEFT MARK — invisible, and emitted by bidirectional layout.
RIGHT_TO_LEFT_MARK = "\u200f"
#: U+00A0 NO-BREAK SPACE — visually a space, a different codepoint.
NO_BREAK_SPACE = "\u00a0"
#: U+0131 LATIN SMALL LETTER DOTLESS I, whose `.upper()` is ASCII I.
TURKISH_DOTLESS_I = "\u0131"
#: "TAX INVOICE" in fullwidth forms, U+FF34 onward, separated by the ordinary
#: U+0020 space the original literal carried.
FULLWIDTH_TAX_INVOICE = "\uff34\uff21\uff38 \uff29\uff2e\uff36\uff2f\uff29\uff23\uff25"


@pytest.mark.parametrize(
    "heading",
    [
        f"T{CYRILLIC_A}X INVOICE",
        f"t{CYRILLIC_A.lower()}x invoice",
    ],
)
def test_a_cyrillic_lookalike_never_matches_a_latin_cue(heading: str) -> None:
    """The dangerous direction: a homoglyph must not be able to satisfy a cue.
    A document whose heading is spelled with a Cyrillic U+0410 is not the same
    string as the catalogued one, and this module must not pretend it is.
    """
    result = classify(a_reading(heading), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()


@pytest.mark.parametrize(
    "heading",
    [
        f"TAX {ZERO_WIDTH_SPACE}INVOICE",
        f"TAX IN{ZERO_WIDTH_SPACE}VOICE",
        f"TAX {RIGHT_TO_LEFT_MARK}INVOICE",
        f"TAX{NO_BREAK_SPACE}INVOICE",
    ],
)
def test_an_invisible_character_makes_a_visible_heading_read_as_unknown(heading: str) -> None:
    """A KNOWN, NAMED LIMIT, pinned rather than left to be discovered.

    Every heading here is indistinguishable from "TAX INVOICE" on a page, and
    every one reads as UNKNOWN. That is the SAFE direction — the module refuses
    rather than guesses, exactly as `CLAUDE.md` Law 25 requires — but it is a
    false negative a human cannot see, so it is recorded here explicitly. If a
    later normalisation step ever closes it, this test is what notices, and the
    change gets made deliberately instead of silently.
    """
    result = classify(a_reading(heading), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.document_type is None
    assert result.reasons == (unknown_reason(1),)


def test_a_turkish_dotless_i_folds_into_ascii_and_does_match() -> None:
    """MEASURED, AND SURPRISING, SO IT IS PINNED.

    Matching upper-cases the source with `str.upper()`, which is Unicode-aware
    rather than ASCII-only: `"\u0131".upper()` is `"I"`. So a heading printed
    with a
    Turkish dotless i matches the catalogued cue. This errs toward matching,
    which is the direction that would matter if a type were ever concluded from
    it — so the safety property asserted alongside it is the one that makes it
    checkable: the evidence quote keeps the dotless i verbatim, so a human
    reading the Document Evidence Object can see exactly what the page said.
    """
    printed = f"TAX INVO{TURKISH_DOTLESS_I}CE"

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE
    (matched,) = result.candidates[0].matched_cues
    assert matched.matched_text == printed
    assert TURKISH_DOTLESS_I in matched.matched_text


@pytest.mark.parametrize(
    "heading",
    [
        FULLWIDTH_TAX_INVOICE,  # fullwidth forms
        "TAX INVOICÉ",  # an accent Python's upper() does not strip
        "TAX İNVOICE",  # U+0130 LATIN CAPITAL LETTER I WITH DOT ABOVE
    ],
)
def test_other_unicode_forms_of_a_heading_do_not_match(heading: str) -> None:
    result = classify(a_reading(heading), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN


def test_surrounding_whitespace_and_mixed_case_match_and_the_quote_stays_verbatim() -> None:
    printed = "   Tax Invoice \n "

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE
    (matched,) = result.candidates[0].matched_cues
    # neither trimmed nor upper-cased on its way into the evidence
    assert matched.matched_text == printed
    assert matched.cue == "TAX INVOICE"


# ── the count in the UNKNOWN reason is honest about what was searched ────────


def test_a_whitespace_only_reader_region_is_not_counted_as_a_region_searched() -> None:
    """The reason sentence states how many regions were searched. A blank
    region is not evidence and is not searched, so counting it would overstate
    the search and make the honest answer look better-founded than it is.
    """
    result = classify(a_reading("   ", "nothing catalogued"), NOTHING_STRUCTURED)

    assert result.reasons == (unknown_reason(1),)


def test_a_parser_region_reporting_no_text_is_not_counted_either() -> None:
    """`parser.Region.text` is `None` when the detector reported nothing —
    `ENGINE_1_INPUT_ENGINE_RULES.md:569`'s three-state rule. A region with
    nothing to read was not searched and must not be counted as if it were.
    """
    result = classify(NOTHING_READ, a_structure(None, "nothing catalogued", None))

    assert result.reasons == (unknown_reason(1),)


# ── hostile input, determinism, and no mutation of what it was given ─────────


def test_classify_survives_hostile_text_without_raising_or_guessing() -> None:
    """Control characters, a null byte, punctuation-only text and a hundred
    thousand characters in one region. `classify` documents that it never
    raises for any valid `Reading`; this attacks that claim rather than
    reading it.
    """
    hostile = a_reading(
        "\x00\x01\x02",
        "\x1b[31m\x1b[0m",
        '!@#$%^&*()_+{}|:"<>?',
        "x" * A_LONG_REGION,
        *(["nothing catalogued here"] * MANY_REGIONS),
    )

    result = classify(hostile, NOTHING_STRUCTURED)

    assert isinstance(result, ClassificationResult)
    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()


def test_a_cue_hidden_among_hostile_text_is_still_found_with_its_verbatim_quote() -> None:
    """The other half of the hostile-input attack: refusing everything is not
    robustness. A real cue carrying control characters must still be found, and
    its quote must still be the region's own bytes.

    EXPECTATION CORRECTED, AND THE REASON IS LOUD. This test used to print
    `"\\x1b[1mTAX INVOICE\\x1b[0m"` — noise on BOTH sides — and assert TYPED. It
    cannot, now that a cue must be a WHOLE PHRASE opening or closing its region:
    the character before the "T" is the letter "m" of `\\x1b[1m`, so "TAX
    INVOICE" is not a word there, and nothing available to this module says that
    "m" is a terminal escape rather than part of a word. The both-sides form is
    pinned immediately below, as UNKNOWN. What is measured here is the claim
    this test was written to make, on a form that still holds it: the cue opens
    the region, control characters follow it, and it is found.
    """
    printed = "TAX INVOICE\x1b[0m"

    result = classify(a_reading("\x00\x01", printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.TAX_INVOICE
    (matched,) = result.candidates[0].matched_cues
    assert matched.matched_text == printed
    assert matched.cue == "TAX INVOICE"
    assert result.reasons == ()


def test_a_heading_welded_to_layout_noise_on_both_sides_reads_as_unknown() -> None:
    """THE CORRECTED EXPECTATION, PINNED RATHER THAN LEFT TO BE REDISCOVERED.

    `"\\x1b[1mTAX INVOICE\\x1b[0m"` is a heading to a human and is refused here,
    because "1mTAX" is one run of word characters and this module will not read
    a cue out of the middle of a word. It is a false NEGATIVE — the safe
    direction, and the same class already pinned for zero-width spaces — and it
    is not silent: the reason names the cue and where it was found, so the
    evidence a human would need survives even though no type does.
    """
    printed = "\x1b[1mTAX INVOICE\x1b[0m"

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.document_type is None
    assert result.reasons == (
        no_heading_reason(1),
        set_aside_reason("TAX INVOICE", READER_LOCATION),
    )


def test_classify_returns_the_same_result_for_the_same_input_twice() -> None:
    reading = a_reading("TAX INVOICE", "QUOTATION")
    structure = a_structure("DEBIT NOTE")

    first = classify(reading, structure)
    second = classify(reading, structure)

    assert first == second


def test_classify_leaves_the_reading_and_the_structure_it_was_given_unchanged() -> None:
    """A classifier that normalised its inputs in place would corrupt the
    evidence every other consumer of the same `Reading` depends on.
    """
    reading = a_reading("Tax Invoice", "   ", "QUOTATION")
    structure = a_structure("Delivery Challan", None)
    before_reading = (tuple(region.text for region in reading.regions), reading.backend)
    before_structure = tuple(region.text for region in structure.regions)

    classify(reading, structure)

    assert (tuple(region.text for region in reading.regions), reading.backend) == before_reading
    assert tuple(region.text for region in structure.regions) == before_structure


# ── THE DEFECT THIS PASS FOUND, NOW FIXED AND GUARDED PERMANENTLY ────────────


def test_a_catalogued_phrase_in_body_prose_must_not_become_the_documents_type() -> None:
    """WRITTEN RED, NOW GREEN — the permanent regression test for the defect
    this pass found (`CLAUDE.md` Law 3, §J.8).

    WHAT USED TO HAPPEN, MEASURED. `_candidate_for` tested `cue.text in
    source.text.upper()` against EVERY region `reader` and `parser` produced,
    with no word boundary and no position. So a goods receipt note whose body
    reads "Received against your purchase order 123" came back `TYPED`,
    `document_type == DocumentType.PURCHASE_ORDER`, `reasons == ()` —
    indistinguishable, in every field a caller reads, from a document that
    actually printed PURCHASE ORDER as its heading.

    WHY THAT WAS A DEFECT AND NOT A DOCUMENTED LIMIT.
      - The module's own docstring says it matches "document headings the way a
        human skims a page for the word printed at the top of it". It did not
        look at the top of the page, or at a heading, or at anything positional.
      - `ENGINE_1_INPUT_ENGINE_RULES.md:647` is explicit: *"A confident
        extraction that quietly guessed is a failure, even if the guess happened
        to be right."* That was a confident answer with no uncertainty attached
        — not AMBIGUOUS, not UNKNOWN, and `reasons` empty.
      - §9's failure list names *"Information is invented"*. The document never
        said it was a purchase order; the module concluded it was.
      - It is the same failure the module was built to prevent, arriving from
        the other direction: N1 asks that a proforma not be read as a tax
        invoice, and an incidental cross-reference is a cheaper way to get there
        than a look-alike heading.

    WHAT FIXED IT. A cue counts as this document's own heading only when it
    OPENS or CLOSES the region it was found in, as a whole phrase. Asserted
    below in full rather than only on `document_type`: the original assertion
    would also have passed on an AMBIGUOUS result, and "ambiguous" would be its
    own quiet guess here.
    """
    goods_receipt = a_reading(
        "GOODS RECEIPT NOTE",
        "Received against your purchase order 123 dated 4 May.",
    )

    result = classify(goods_receipt, NOTHING_STRUCTURED)

    assert result.document_type is not DocumentType.PURCHASE_ORDER, (
        "a purchase-order reference in body prose was reported as this "
        "document's own type, with no uncertainty attached. "
        "ENGINE_1_INPUT_ENGINE_RULES.md:647 - a confident extraction that "
        "quietly guessed is a failure even when the guess is right."
    )
    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    # and the cue is not thrown away in silence either: what was seen, and
    # where, is on the record.
    assert result.reasons == (
        no_heading_reason(2),
        set_aside_reason("PURCHASE ORDER", READER_LOCATION),
    )

    # The same defect, second instance: the word "misquotation" contains the
    # catalogued cue "QUOTATION", so a sentence disclaiming a quotation was
    # reported as one.
    disclaimer = a_reading("Please disregard any misquotation in our earlier mail.")
    disclaimed = classify(disclaimer, NOTHING_STRUCTURED)

    assert disclaimed.document_type is not DocumentType.QUOTATION, (
        "the substring 'QUOTATION' inside the word 'misquotation' was reported "
        "as the document's own type."
    )
    assert disclaimed.status is ClassificationStatus.UNKNOWN
    assert disclaimed.reasons == (
        no_heading_reason(1),
        set_aside_reason("QUOTATION", READER_LOCATION),
    )


def test_a_cue_welded_inside_a_longer_word_at_the_region_edge_is_still_refused() -> None:
    """Position alone would not have been enough, and this proves it.

    "MISQUOTATION" alone in a region ENDS that region, so a rule that only asked
    where the cue sits would have accepted it. The word-boundary half is what
    refuses it. Both halves are load-bearing and both are measured.
    """
    result = classify(a_reading("MISQUOTATION"), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.candidates == ()
    assert result.reasons == (
        no_heading_reason(1),
        set_aside_reason("QUOTATION", READER_LOCATION),
    )


def test_a_typed_document_still_reports_the_cross_reference_it_set_aside() -> None:
    """The case that would be easiest to lose: the document DOES announce its
    own type, so a caller reading `document_type` is right — and it also names
    another document in its body. `reasons` is not empty on a TYPED result
    here, which is exactly the point: the answer is right AND the discarded
    evidence is visible.
    """
    reading = a_reading(
        "DELIVERY CHALLAN",
        "Delivered against your purchase order 123 dated 4 May.",
    )

    result = classify(reading, NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.DELIVERY_CHALLAN
    assert result.reasons == (set_aside_reason("PURCHASE ORDER", READER_LOCATION),)


def test_an_ambiguous_document_reports_its_ambiguity_and_its_cross_reference() -> None:
    """The third branch, with a set-aside occurrence alongside it. The
    ambiguity sentence still comes first — a caller reading only `reasons[0]`
    must not have it replaced by a cross-reference note.
    """
    reading = a_reading(
        "TAX INVOICE",
        "QUOTATION",
        "Raised against your purchase order 123 dated 4 May.",
    )

    result = classify(reading, NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.AMBIGUOUS
    assert [candidate.document_type for candidate in result.candidates] == [
        DocumentType.TAX_INVOICE,
        DocumentType.QUOTATION,
    ]
    assert result.reasons == (
        ambiguity_reason(DocumentType.TAX_INVOICE, DocumentType.QUOTATION),
        set_aside_reason("PURCHASE ORDER", READER_LOCATION),
    )


def test_the_same_cue_can_be_a_heading_in_one_region_and_a_reference_in_another() -> None:
    """The case a per-DOCUMENT rule would get wrong and a per-REGION rule gets
    right. "PURCHASE ORDER" is printed as the heading AND mentioned inside a
    sentence lower down. The heading types the document; the mention is still
    set aside and still recorded, so the two are never pooled into one verdict.
    """
    reading = a_reading(
        "PURCHASE ORDER",
        "Supersedes the purchase order 122 we sent on 1 May.",
    )

    result = classify(reading, NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.PURCHASE_ORDER
    (candidate,) = result.candidates
    # exactly ONE piece of evidence: the heading. The sentence is not evidence.
    assert [matched.matched_text for matched in candidate.matched_cues] == ["PURCHASE ORDER"]
    assert result.reasons == (set_aside_reason("PURCHASE ORDER", READER_LOCATION),)


def test_a_cross_reference_found_by_the_parser_names_the_parser_region_it_sat_in() -> None:
    """The same rule on the other instrument, and the reason must locate it
    there — a set-aside note that could not say WHICH region it came from would
    be a record a human cannot check.
    """
    structure = a_structure("Received against your purchase order 123 dated 4 May.")

    result = classify(NOTHING_READ, structure)

    assert result.status is ClassificationStatus.UNKNOWN
    assert result.reasons == (
        no_heading_reason(1),
        set_aside_reason("PURCHASE ORDER", PARSER_LOCATION),
    )


def test_a_heading_that_opens_its_region_survives_the_prose_that_follows_it() -> None:
    """The other direction of the same rule, measured rather than assumed: a
    heading printed with a subtitle on the same line is still a heading. If the
    fix had required the cue to be the WHOLE region, this would have gone
    UNKNOWN and every real document with a strapline would have been lost.
    """
    printed = "DELIVERY CHALLAN for goods sent to our Pune warehouse on 4 May"

    result = classify(a_reading(printed), NOTHING_STRUCTURED)

    assert result.status is ClassificationStatus.TYPED
    assert result.document_type is DocumentType.DELIVERY_CHALLAN
    assert result.reasons == ()
    (matched,) = result.candidates[0].matched_cues
    assert matched.matched_text == printed
