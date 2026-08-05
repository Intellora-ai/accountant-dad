"""`classification` — what KIND of document this is, never what it means.

AUTHORIZED BY AMENDMENT 3, AND STATED HONESTLY: THE ARCHITECTURE HAS NOT CAUGHT UP.
    `SUB_ENGINE_RESPONSIBILITIES.md` §1 names exactly four Engine 1 sub-engines
    — `cleaner`, `reader`, `parser`, `confidence` — and its own boxed note says
    *"no assembler sub-engine exists, and none may be added."* This module is
    not a fifth entry in that list; it is a separate capability `CLAUDE.md` §P
    Amendment 3 (2026-08-05) names explicitly and by name: *"Engine 1 ...
    document classification ... released for implementation."*

    `docs/ENGINE_1_ARCHITECTURE.md` G9.5, written the SAME day, has not been
    reconciled with that sentence. It calls document-type detection *"one open
    question this document does not answer"* and states plainly: *"It is not
    authorised ... out of scope until the owner rules on which side of that
    line document-type detection sits."* That line is the one this module
    stands on: *"this artifact is a scanned image with an invoice-like
    layout"* (an observation, permitted) versus *"this is a proforma invoice"*
    (G9.5's own example of a conclusion that decides whether anything posts).

    This is a real, unreconciled tension between two documents from the same
    day, not a mistake silently resolved here. `CLAUDE.md` §E.9 requires it
    reported, not hidden, so it is reported here, in the file it governs, for
    whoever reads this module next. What follows is built to sit on the
    permitted side of G9.5's own line regardless of how that reconciliation
    goes: every output is a labelled OBSERVATION carrying its evidence, never
    a decision, and nothing here ever states or implies that a document may be
    posted, is safe, or is approved. GOLDEN_DATASET.md negative control N1 —
    *"Proforma invoice. Looks identical to a tax invoice. The classic real
    error."* — is exactly the failure a document-type OBSERVATION, honestly
    labelled UNKNOWN when ambiguous, helps surface rather than hides.

WHAT THIS MODULE OWNS, AND THE ONE SENTENCE THAT BOUNDS IT.
    Given what `reader` and `parser` already produced, name which catalogued
    document type's own structural cues — literal strings a document of that
    type is expected to carry, such as the heading it prints on itself — were
    found, and where. It never decides who the parties are, what was sold,
    what tax applies, whether the document is genuine, or whether anything
    should post. Those are Engine 2's, Engine 3's and Engine 5's, and nothing
    below imports, names, or reaches toward any of them.

NO SCORE. NOT EVEN AN UNCALIBRATED ONE.
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #9, `classification_accept`, is
    `UNSET`, and `ENGINE_1_ARCHITECTURE.md` G9.2 lists it, by name, among the
    confidence-threshold behaviour that is *"not in this build"* until
    separation is measured (`MEASUREMENT_FRAMEWORK.md:258` — *"confidence
    gates nothing"*). `confidence_report.py` answers the identical problem for
    its own sixteen parameters by producing no comparable number at all: *"a
    recorder that gates nothing needs no cutoffs."* This module goes one step
    further than a raw uncalibrated float, because even a float invites a
    caller to sort or threshold it silently — it counts nothing and scores
    nothing. What it returns is the set of matched cues themselves, which is
    already the whole of the evidence a human or a future calibration step
    would need; `measurement.py` already reserves a `classification` signal
    category and a `source_document_type` ground-truth field for exactly that
    future step (`measurement.py:119,269`), and this module produces neither —
    it is not that step, and does not anticipate its answer.

NO NUMERIC LITERAL IS COMPARED AGAINST ANYTHING, ANYWHERE IN THIS MODULE.
    Not `if score > 0.8`, not a cue count, not a "closest match." Whether a
    document reads as TYPED, AMBIGUOUS or UNKNOWN is decided by
    `match candidates:` against the SHAPE of the tuple found — `()`, a
    one-tuple, or anything else — which is Python's structural pattern
    matching, not a numeric `Compare`. `test_no_numeric_comparison_appears_
    anywhere_in_the_module` in this module's test file walks the AST to prove
    it, the same way `test_input_engine_confidence.py` already proves it for
    `confidence_report.py`.

UNKNOWN AND AMBIGUOUS ARE BOTH HONEST ANSWERS, AND THEY ARE DIFFERENT ONES.
    `CLAUDE.md` Law 25 — *"expose uncertainty instead of guessing."* A
    document carrying no catalogued cue at all is `UNKNOWN`: nothing is
    guessed, and the reasons say what was searched and where. A document
    carrying cues for MORE THAN ONE catalogued type is `AMBIGUOUS`, and BOTH
    (or all) sets of evidence survive in `candidates` — there is no tie-break,
    no "most cues wins," and no silently preferred type. Collapsing that case
    to a single winner is exactly the failure a proforma invoice printed
    alongside tax-invoice language would need this module to commit.

LITERAL STRINGS, NEVER ACCOUNTING REASONING.
    The catalogue below matches document headings the way a human skims a
    page for the word printed at the top of it — case-insensitive substring
    matching against text `reader` and `parser` already extracted. It does not
    read a value, does not total a table, does not look at a GSTIN, a party
    name or an amount, and does not decide postability, tax treatment or
    ledger classification. `test_no_accounting_conclusion_is_reachable_from_
    the_public_surface` in this module's test file inspects every public
    name — class, function, dataclass field, enum member — for the
    accounting-decision vocabulary those other engines own, and fails if any
    of it appears here.

TWO INSTRUMENTS, NOT ONE, BECAUSE `reader` AND `parser` ALREADY EXIST.
    Unlike `confidence_report.py`, which was written before `reader` and
    `parser` landed and therefore defined its own placeholder input shapes,
    both sub-engines exist now with real output types — `reader.Reading` and
    `parser.ParsedStructure` — so this module imports and uses them directly
    rather than inventing a third contract for the same evidence.
    `CONFIDENCE_SPECIFICATION.md` §3.2 treats *"document-type classification"*
    as its own instrument, one of several that must never be pooled; in the
    same spirit, every `MatchedCue` below carries WHICH of the two it came
    from, so a cue found in `reader`'s raw text and one found in `parser`'s
    located regions are never presented as if they were the same kind of
    finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from accountant_dad.engines.input_engine.parser import ParsedStructure, Region
from accountant_dad.engines.input_engine.reader import Reading, SourceLocation


def _reject_blank(value: str, what: str) -> None:
    if not value.strip():
        raise ValueError(f"{what} must not be empty or blank")


class DocumentType(StrEnum):
    """The closed catalogue of document types this module can name.

    Closed and small, deliberately — mirroring `parser.py`'s own refusal to
    hold an expected-field list it was never given: which document types
    exist, and which particulars each one must carry, is knowledge (CGST
    Rules 46-55 alone name 86 mandatory particulars for one of these eight),
    and knowledge is not this sub-engine's to hold or complete
    (`SUB_ENGINE_RESPONSIBILITIES.md` 1.3). A type this catalogue does not
    name is never guessed at; the document reads as `UNKNOWN` instead.
    """

    TAX_INVOICE = "Tax Invoice"
    BILL_OF_SUPPLY = "Bill of Supply"
    CREDIT_NOTE = "Credit Note"
    DEBIT_NOTE = "Debit Note"
    DELIVERY_CHALLAN = "Delivery Challan"
    PURCHASE_ORDER = "Purchase Order"
    PROFORMA_INVOICE = "Proforma Invoice"
    QUOTATION = "Quotation"


class Instrument(StrEnum):
    """Which sub-engine's output a piece of evidence text came from.

    `CONFIDENCE_SPECIFICATION.md` §3.2 — instruments are independent scales
    and must never be silently merged. `reader` sees raw recognised text;
    `parser` sees text already resolved to a laid-out region. They are kept
    apart here for the same reason `Band.score` and `TextRegion.extraction_
    confidence` are never merged into one number elsewhere in this engine.
    """

    READER = "reader"
    PARSER = "parser"


class ClassificationStatus(StrEnum):
    """What kind of answer this module is giving, named rather than implied
    by counting `candidates` at the call site.
    """

    TYPED = "exactly one catalogued document type's cues were found"
    AMBIGUOUS = "more than one catalogued document type's cues were found"
    UNKNOWN = "no catalogued document type's cues were found"


@dataclass(frozen=True, slots=True)
class Cue:
    """One literal string this module looks for, and the type it is evidence for.

    `text` is stored upper-case because matching is case-insensitive — a
    document may print "Tax Invoice", "TAX INVOICE" or "tax invoice", and none
    of those is more or less a tax invoice than another.
    """

    document_type: DocumentType
    text: str

    def __post_init__(self) -> None:
        _reject_blank(self.text, "cue text")
        if self.text != self.text.upper():
            raise ValueError(
                f"cue text must already be upper-case for case-insensitive "
                f"matching; got {self.text!r}"
            )


#: The whole of this module's knowledge about what a document type looks
#: like: one printed heading each, taken from the name CGST Rules 46-55 and
#: the GST business-document vocabulary give each of these eight document
#: types. Not exhaustive — a real tax invoice may print "TAX INVOICE" in a
#: dozen typefaces this catalogue does not enumerate, and that is a known,
#: named limit, not a hidden one: a document whose heading this catalogue does
#: not recognise reads as `UNKNOWN`, honestly, rather than as a false negative
#: dressed up as a clean miss.
CUE_CATALOG: tuple[Cue, ...] = (
    Cue(DocumentType.TAX_INVOICE, "TAX INVOICE"),
    Cue(DocumentType.BILL_OF_SUPPLY, "BILL OF SUPPLY"),
    Cue(DocumentType.CREDIT_NOTE, "CREDIT NOTE"),
    Cue(DocumentType.DEBIT_NOTE, "DEBIT NOTE"),
    Cue(DocumentType.DELIVERY_CHALLAN, "DELIVERY CHALLAN"),
    Cue(DocumentType.PURCHASE_ORDER, "PURCHASE ORDER"),
    Cue(DocumentType.PROFORMA_INVOICE, "PROFORMA INVOICE"),
    Cue(DocumentType.QUOTATION, "QUOTATION"),
)


@dataclass(frozen=True, slots=True)
class MatchedCue:
    """One catalogued cue, actually found, with where it was found and by which instrument.

    `matched_text` is the SOURCE text the cue was found inside, verbatim —
    not the catalogue's own upper-cased form — so the evidence shows what the
    document actually said, not what this module normalised it to.
    """

    cue: str
    instrument: Instrument
    matched_text: str
    location: str

    def __post_init__(self) -> None:
        _reject_blank(self.cue, "matched cue text")
        _reject_blank(self.matched_text, "matched cue's source text")
        _reject_blank(self.location, "matched cue's location")


@dataclass(frozen=True, slots=True)
class TypeCandidate:
    """One document type, and every piece of evidence found for it.

    `matched_cues` may never be empty — a candidate with no evidence is an
    assertion, exactly what this module exists not to make (module docstring,
    "EMIT THE EVIDENCE, NOT JUST THE LABEL" in the deliverable's own words).
    """

    document_type: DocumentType
    matched_cues: tuple[MatchedCue, ...]

    def __post_init__(self) -> None:
        if not self.matched_cues:
            raise ValueError(
                f"a type candidate for {self.document_type.value} carries no "
                "evidence; a candidate is only ever built from at least one "
                "matched cue"
            )


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """What `classify` returns: a status, the surviving evidence, and why.

    The three-way shape of `candidates` IS the status — `__post_init__` below
    refuses any other pairing, so a caller can never observe `TYPED` next to
    zero or several candidates, or `UNKNOWN` next to any.
    """

    status: ClassificationStatus
    candidates: tuple[TypeCandidate, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        match self.status, self.candidates:
            case ClassificationStatus.UNKNOWN, ():
                pass
            case ClassificationStatus.TYPED, (_,):
                pass
            case ClassificationStatus.AMBIGUOUS, (_, _, *_):
                pass
            case _:
                raise ValueError(
                    f"status {self.status.name} is inconsistent with the "
                    f"candidates supplied alongside it"
                )

    @property
    def document_type(self) -> DocumentType | None:
        """The single identified type, or `None`.

        `None` covers BOTH `UNKNOWN` and `AMBIGUOUS` on purpose: a caller
        reading only this property cannot mistake "genuinely undetermined"
        for a real answer by accident, which is the whole point of Law 25 —
        the honest cases must not be reachable through the convenient path.
        """
        match self.candidates:
            case (only,):
                return only.document_type
            case _:
                return None


@dataclass(frozen=True, slots=True)
class _Source:
    """One piece of text this module may search, normalised to a common shape.

    Internal only — `reader.TextRegion` and `parser.Region` keep their own
    real types everywhere else; this exists so the matching loop below does
    not need to know which of the two produced a given piece of text.
    """

    instrument: Instrument
    text: str
    location: str


def _describe_reader_location(location: SourceLocation) -> str:
    return (
        f"page {location.page_index}, "
        f"({location.left:.1f}, {location.top:.1f})-"
        f"({location.right:.1f}, {location.bottom:.1f})"
    )


def _describe_parser_location(region: Region) -> str:
    box = region.box
    return (
        f"page {box.page}, {region.label!r} region, "
        f"({box.left:.1f}, {box.top:.1f})-({box.right:.1f}, {box.bottom:.1f})"
    )


def _reader_sources(reading: Reading) -> tuple[_Source, ...]:
    return tuple(
        _Source(
            instrument=Instrument.READER,
            text=region.text,
            location=_describe_reader_location(region.location),
        )
        for region in reading.regions
        if region.text.strip()
    )


def _parser_sources(structure: ParsedStructure) -> tuple[_Source, ...]:
    return tuple(
        _Source(
            instrument=Instrument.PARSER,
            text=region.text,
            location=_describe_parser_location(region),
        )
        for region in structure.regions
        if region.text is not None
    )


def _candidate_for(
    document_type: DocumentType, sources: tuple[_Source, ...]
) -> TypeCandidate | None:
    """Every matched cue this module can find for one document type, or `None`.

    Case-insensitive substring containment against text `reader` or `parser`
    already extracted — the one matching rule this whole module has, and the
    only place `.upper()` is called on anything that was not already
    normalised by `CUE_CATALOG` itself.
    """
    found = tuple(
        MatchedCue(
            cue=cue.text,
            instrument=source.instrument,
            matched_text=source.text,
            location=source.location,
        )
        for cue in CUE_CATALOG
        if cue.document_type is document_type
        for source in sources
        if cue.text in source.text.upper()
    )
    return TypeCandidate(document_type=document_type, matched_cues=found) if found else None


def classify(reading: Reading, structure: ParsedStructure) -> ClassificationResult:
    """Name which catalogued document type's cues were found, and where.

    Never raises for any valid `Reading` or `ParsedStructure`, including an
    empty one — a document with nothing read, or nothing structured, is a
    real answer (`UNKNOWN`), never an error and never a default guess.

    `reading` and `structure` are both required: this module is given what
    `reader` and `parser` produced, and both already exist with real output
    types, so there is no partial-input case to default around.
    """
    sources = _reader_sources(reading) + _parser_sources(structure)

    candidates = tuple(
        candidate
        for document_type in DocumentType
        if (candidate := _candidate_for(document_type, sources)) is not None
    )

    match candidates:
        case ():
            return ClassificationResult(
                status=ClassificationStatus.UNKNOWN,
                candidates=(),
                reasons=(
                    "none of this module's catalogued structural cues were found "
                    f"in the {len(sources)} region(s) of text supplied by reader "
                    "and parser; no type is guessed in their place.",
                ),
            )
        case (only,):
            return ClassificationResult(
                status=ClassificationStatus.TYPED,
                candidates=(only,),
                reasons=(),
            )
        case multiple:
            names = ", ".join(candidate.document_type.value for candidate in multiple)
            return ClassificationResult(
                status=ClassificationStatus.AMBIGUOUS,
                candidates=multiple,
                reasons=(
                    f"structural cues were found for more than one catalogued "
                    f"document type ({names}); this module does not choose "
                    "between them.",
                ),
            )
