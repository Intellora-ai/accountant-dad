"""The `confidence` sub-engine — a recorder, not a gate.

`SUB_ENGINE_RESPONSIBILITIES.md` §1.4 gives this module one job: *"the honest
measurement of extraction trustworthiness, per field and overall, and the
identification of the specific regions and fields that are weak."*
`ENGINE_1_INPUT_ENGINE_RULES.md:574-627` states the same as Receives / Produces
/ Allowed / Forbidden: it receives `cleaner`, `reader` and `parser` output, and
produces confidence scores, uncertainty markers and a reliability assessment —
nothing else, and never a decision.

WHAT "RECORDER, NOT A GATE" MEANS HERE, CONCRETELY.
    `MEASUREMENT_FRAMEWORK.md:258` — *"Until it passes [the separation] test,
    confidence is an ordinal ranking, not a probability, and it may gate
    NOTHING."* Sixteen of Engine 1's parameters exist to gate something
    (`ENGINE_1_CONFIDENCE_PARAMETERS.md`), and every one of them is `UNSET`.
    This module never compares a confidence value against a number and never
    decides accept/reject/retry/review from one — that decision has nowhere
    to live yet, so no function here makes it. It reads three inputs, writes
    three outputs, and stops.

THERE IS NO DOCUMENT-LEVEL SCALAR, AND NONE IS ADDED HERE.
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` settles this with a named theorem —
    Marichal & Mesiar, *Aequationes Math.* 77(3) 2009, Corollary 5.7: on an
    ordinal scale, a symmetric, continuous, idempotent aggregation is
    comparison-meaningful *iff* it is an order statistic. `min ≥ t` is
    identically `∀i : c_i ≥ t`, so a scalar built from the per-field scores
    would carry nothing the per-field scores do not already carry, while
    inviting a caller downstream to average, compare across documents, or
    threshold it — all meaningless on this scale. So `record_confidence`
    below returns per-field scores and named markers, never a combined
    number, and there is no function anywhere in this module that could
    produce one.

ONE REPRESENTATION FOR CONFIDENCE, ONE REPRESENTATION FOR THE REPORT.
    `Confidence` is imported from `accountant_dad.confidence`, never
    redeclared — that module's own docstring records the outage a second
    definition caused once already. Likewise `ConfidenceReport`,
    `FieldConfidence` and `UncertaintyMarker` are imported from
    `accountant_dad.artifacts.evidence`: the Confidence Report is *"a
    component of the Document Evidence Object"* (§1.4), owned there, and this
    module assembles one rather than defining a second shape that would mean
    the same thing and drift from it.

TWO INPUTS ARE CONTRACTS, NOT IMPLEMENTATIONS.
    `cleaner` exists (`engines/input_engine/cleaner.py`) and its real
    `CleanedDocument` is imported and used directly. `reader` and `parser`
    also exist now (`engines/input_engine/reader.py`,
    `engines/input_engine/parser.py`), but their landed shapes do not yet
    carry what this module needs, so `RegionReading`, `ParsedField` and
    `MissingField` below stay this module's reading of the *documented*
    output contracts instead — §1.2, *"raw extracted information ...
    source locations ... extraction confidence"*, and §1.3, *"structured
    fields ... field mappings ... missing field information."* Concretely:
    `reader.TextRegion.text` is a required `str` with no state for "this
    region could not be read at all" (`RegionReading.text` needs `None` for
    exactly that, to build the unread-region markers §1.4 requires), and
    `parser.MappedField` — which DOES now name a value and keep its source
    reference, for text regions and for table cells alike — carries
    `reader`'s raw two-state signal (`Decimal | None`) rather than a
    measurement STATE, because deciding what an absent signal MEANS belongs
    to this sub-engine and not to `parser`
    (`ENGINE_1_INPUT_ENGINE_RULES.md:109`). Importing either real type today
    would therefore lose a state this module must keep.
    When `reader` and `parser`'s real output grows the shapes §1.2 and §1.3
    describe, that output need only be mapped into these three types, or
    these three retired in favour of theirs; nothing else here depends on
    how either is implemented. (`assembly.py` makes the identical choice for
    the identical reason — see its own module docstring, "THE FOUR INPUT
    CONTRACTS, AND WHY THEY ARE DEFINED HERE RATHER THAN IMPORTED.")

WHAT THIS MODULE NEVER DOES, AND WHY EACH IS A BOUNDARY AND NOT A CHOICE.
    Cannot re-read, re-parse or correct anything (§1.4 Boundary) — every
    function below is a pure function of the values it is given; none opens
    a file, decodes an image, or touches text. Cannot increase confidence
    without evidence (§1.4, INV-2) — no function here ever raises a
    `Confidence` value above what it was given; `_field_confidence_scores`
    mirrors reader's own reading unchanged, and `capture_fidelity` below is
    the one place a number is produced from nothing, and it is produced
    from an equality check, not an increase. Cannot hide uncertainty — every
    categorical signal this module can see without inventing a cut-off
    becomes an `UncertaintyMarker`, and every marker carries a reason
    (`ENGINE_1:626`). Cannot reject a document or halt the pipeline — the
    `MalformedSignalError` raised by the dataclasses below fires only on a
    caller handing this module a self-contradictory signal (text with no
    confidence, a nameless field), the same class of defence
    `cleaner.CleanerSettings` uses against an impossible setting; it is never
    raised because a document read poorly. Cannot use business plausibility
    as evidence — nothing here reads a field's *value*, only whether it was
    read, how confidently, and whether it exists; the content is never
    inspected for whether it makes commercial sense.

RISKY FIELDS STAY EMPTY. ALWAYS. STATED, NOT HIDDEN.
    §1.4's Allowed Actions include *"Highlight risky fields,"* and
    `ConfidenceReport.risky_fields` exists to carry them. But
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` lists *what makes a field "risky"* as
    gap **#4**, undefined rather than merely unset: *"Deriving it from
    `confidence < X` is a confidence gate, which `MEASUREMENT_FRAMEWORK.md:258`
    forbids until calibration passes."* There is no rule to apply, so none is
    invented; `record_confidence` always returns `risky_fields=()`, and the
    weak fields and regions this module *can* name without a threshold are
    named as uncertainty markers instead — see below.

CAPTURE FIDELITY IS SCORED ONLY WHERE IT IS ACTUALLY DEFINED.
    §1.4 Failure Behaviour: *"For a provided source, it scores capture
    fidelity — how faithfully the input was stored — never whether the
    statement is true."* But `ENGINE_1_CONFIDENCE_PARAMETERS.md` lists *who
    computes capture fidelity, and how* as gap **#12**, undefined: no locked
    document states a formula, and `ENGINE_1:283`'s "100%" is an
    illustration, not a measurement. `cleaner` (§1.1) and `reader` (§1.2) are
    both contractually required to pass a provided source through
    *untouched*, so the one thing genuinely measurable this far into the
    pipeline, without inventing a formula for a degree of loss nobody has
    specified, is whether that guarantee held: does the text reaching this
    module still equal, character for character, the text that was
    submitted? `capture_fidelity` below answers exactly that question and no
    other. An exact match earns the type's own upper identity element,
    `Confidence`'s `MAX` — not a number this module chose, the one value that
    requires no scale to justify. A mismatch earns no number at all: grading
    *how much* was lost would mean inventing the missing rule, which is
    exactly what `CLAUDE.md` Law 54 forbids. The mismatch itself becomes the
    finding, carried as an `UncertaintyMarker` AND, since Amendment 7, as a
    named state — `CAPTURE_FIDELITY_ON_MISMATCH`, FAILED, with its reason.
    Before that state existed a mismatch put NOTHING in `confidence_scores`,
    so this name appeared on a match and was absent on a mismatch, which
    reads exactly like no Human Business Context having been supplied. That
    silence was about the one case where a preservation guarantee had just
    broken. That `MAX` score is not left
    as a value merely computed and implied by prose — `record_confidence`
    records it into `confidence_scores` under `CAPTURE_FIDELITY_FIELD_NAME`,
    so it survives inside the emitted artifact rather than being computed and
    silently dropped (CONFIDENCE_SPECIFICATION.md §3.1: *"a summary computed
    before the rule is known is a decision nobody made, taken irreversibly"*
    — a signal computed and then discarded is the same failure by another
    route: the module measured something and never said so).

NO CONFIGURATION IS DEFINED HERE, AND NONE IS NEEDED.
    `ENGINE_1_CONFIDENCE_PARAMETERS.md`: *"prefer needing none at all, since a
    recorder that gates nothing needs no cutoffs."* Every one of the sixteen
    named parameters is either a GATING threshold (accept, reject, retry,
    route to review — none of which this module performs) or one of the three
    undefined gaps above (which this module refuses to guess at rather than
    silently answer). Nothing this module does compares a `Confidence` value
    against a number: every branch below tests `is None`, string equality, or
    an enum member already decided by `cleaner` from *its own* caller-supplied
    setting. There is therefore no settings dataclass in this file — adding
    one would be inventing a parameter with nothing to configure, which is
    the opposite of Law 52's discipline, not an application of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    FieldConfidence,
    HumanBusinessContext,
    UncertaintyMarker,
)
from accountant_dad.confidence import (
    MAX,
    Confidence,
    ConfidenceOrUnmeasured,
    MeasurementFailedType,
    MeasurementState,
    NotApplicableType,
    measurement_state,
)
from accountant_dad.engines.input_engine.cleaner import CleanedDocument, PreservationStatus

#: The one value `capture_fidelity` ever returns for a match, and the reason
#: it needs no comparison against anything: see CAPTURE FIDELITY above. `MAX`
#: is imported, never re-typed as a local `Decimal` literal — the identity
#: comes from the single source of truth for the scale, not from this file.
CAPTURE_FIDELITY_ON_EXACT_MATCH: Confidence = MAX

#: The name under which a Human Business Context's capture-fidelity score is
#: recorded in `ConfidenceReport.confidence_scores`, alongside the per-field
#: scores `reader`/`parser` produced. `FieldConfidence.field_name` "need not
#: be a detected field" (CONFIDENCE_SPECIFICATION.md §3.4, citing
#: `evidence.py:211-217`) — this is the one degree of freedom that clause
#: grants, used rather than inventing a second schema slot the frozen
#: artifact does not have (open item O4). Namespaced with a dot no parsed
#: document field is ever named, so it can never collide with a real
#: detected field and be mistaken for one; if it ever did,
#: `ConfidenceReport._each_name_is_scored_once` refuses the artifact rather
#: than silently picking one, the same structural defence every other
#: name collision in this schema already gets.
CAPTURE_FIDELITY_FIELD_NAME = "human_business_context.capture_fidelity"

#: What a capture-fidelity MISMATCH records instead of a number (Amendment 7).
#: FAILED rather than NOT_MEASURED, and the difference is the whole point:
#: `cleaner` (§1.1) and `reader` (§1.2) are each contractually required to pass
#: a provided source through untouched, so a mismatch means that guarantee
#: broke at this exact value. The measurement was attempted, and it could not
#: produce a score. NOT_MEASURED would file a broken guarantee under the same
#: heading as an ordinary unscored text-layer reading, which is the collapse
#: the four states exist to prevent.
CAPTURE_FIDELITY_ON_MISMATCH = MeasurementFailedType(
    basis=(
        "the text now stored does not match, character for character, the text "
        "submitted, and no rule exists anywhere in this repository for grading "
        "how much was lost (ENGINE_1_CONFIDENCE_PARAMETERS.md gap #12). The "
        "comparison ran and produced no score; inventing a partial one is what "
        "CLAUDE.md Law 54 forbids"
    )
)


class MalformedSignalError(ValueError):
    """A signal this module cannot honestly record without inventing part of
    it — a field with no name, a region claiming both a reading and no
    confidence for it. Raised on the CALLER'S data, at construction, the same
    defence `cleaner.CleanerSettings` uses against an impossible setting.
    Never raised because a document was read poorly (§1.4 — this module
    cannot reject a document or halt the pipeline).
    """


class ReadingState(Enum):
    """Which of the three things `reader` can report about one region.

    THREE STATES, NOT TWO (Law 24, and the same discipline
    `ENGINE_1_INPUT_ENGINE_RULES.md:569` imposes on absent/zero/unreadable and
    `measurement.py:41-59` imposes on absent/zero/unread).

    | State | `text` | `extraction_confidence` |
    |---|---|---|
    | `UNREAD` | `None` | `None` |
    | `READ_AND_SCORED` | present | present |
    | `READ_BUT_UNSCORED` | present | `None` |

    `READ_BUT_UNSCORED` is not a degenerate case; it is what
    `reader.read_pdf_text_layer` produces for EVERY region, because a PDF text
    layer is transcribed rather than recognised and no recogniser ran to
    produce a score (`reader.py:255-259`, *"`None` is NOT zero confidence and
    NOT full confidence - it is the absence of a measurement"*).

    This enum exists so no caller re-derives the state from a bare
    `extraction_confidence is None`, which is ambiguous: that test is true for
    an unread region AND for a read-but-unscored one. Naming the state forces
    every reader to say which it means — the same reason
    `measurement.AbsentType` refuses `__bool__` (`measurement.py:122-150`, the
    F-005 resolution) rather than answering `False` and letting two facts
    collapse into one.
    """

    UNREAD = "unread"
    READ_AND_SCORED = "read and scored"
    READ_BUT_UNSCORED = "read but unscored"


@dataclass(frozen=True, slots=True)
class RegionReading:
    """One thing `reader` found, or failed to find, at one place on the page.

    §1.2's output, per region: *"raw extracted information ... source
    locations ... extraction confidence."* See the module docstring, TWO
    INPUTS ARE CONTRACTS — this is read off that prose, not off `reader`'s
    code, which does not yet carry this shape.

    `text` is `None` for *"a region that could not be read at all ...
    reported as unread, not omitted silently"* (§1.2 Failure Behaviour), and
    that — never the confidence — is what makes a region unread. A region
    that was read carries text and may or may not carry a score; see
    `ReadingState` for why both are legitimate.

    The one pairing still refused is a confidence with NO text: an instrument
    cannot score a reading that does not exist, no backend produces that
    shape, and there is no honest meaning to give it.
    """

    source_location: str
    text: str | None
    extraction_confidence: Confidence | None

    def __post_init__(self) -> None:
        if not self.source_location.strip():
            raise MalformedSignalError(
                "a region reading must name a non-blank source location; §1.2 "
                "requires source locations even for low-confidence extractions, "
                "precisely so a human can find the spot later."
            )
        if self.text is None and self.extraction_confidence is not None:
            raise MalformedSignalError(
                f"region {self.source_location!r} carries a confidence but no "
                "text; an instrument cannot score a reading that does not "
                "exist. Text with no confidence is the opposite case and is "
                "legitimate -- see ReadingState.READ_BUT_UNSCORED."
            )

    @property
    def state(self) -> ReadingState:
        """Which of `ReadingState`'s three this reading is. Derived, never
        stored, so it cannot disagree with the fields it describes.

        EVERY TEST BELOW IS `is None`, NEVER FALSINESS, AND THAT IS LOAD-BEARING.
        `Confidence`'s own `MIN` is `Decimal("0")` and the empty string is
        `""`; both are FALSY. Written `if not self.extraction_confidence`, a
        region a recogniser scored at rock bottom would be reported as one it
        never scored at all — the most alarming signal in the report, lost
        silently, in the direction that reads as reassuring. Written
        `if not self.text`, a box `reader` read and found empty would be
        reported as one `reader` could not read — an instrument failure that
        did not happen. Absent, zero and empty are three different facts
        (`ENGINE_1_INPUT_ENGINE_RULES.md:569`, `measurement.py:41-59`), and
        falsiness answers the same `True` to all three. Both substitutions are
        pinned red in `test_input_engine_confidence.py`.
        """
        if self.text is None:
            return ReadingState.UNREAD
        if self.extraction_confidence is None:
            return ReadingState.READ_BUT_UNSCORED
        return ReadingState.READ_AND_SCORED


@dataclass(frozen=True, slots=True)
class ParsedField:
    """One field `parser` recovered, with the extraction confidence `reader`
    attached to the region it came from, carried through unchanged.

    §1.3's output component, structured fields. `extraction_confidence` is
    not re-scored here — this module's boundary forbids re-reading or
    re-parsing (§1.4) — it is the same reading `reader` produced, mirrored
    into a `FieldConfidence` entry by `_field_confidence_scores` below and
    never modified.

    `extraction_confidence` is `ConfidenceOrUnmeasured`, so it holds a score OR
    any of the three stated absences. THIS IS OPEN ITEM O11 FROM AMENDMENT 6,
    closed on this side. It was `Confidence` — `Decimal` only — which meant an
    unscored reading could not be expressed here at all, so `pipeline` had to
    filter those out and assemble their Confidence Report entries itself, and
    `ConfidenceReport.confidence_scores` acquired a second producer. Widening
    it is the annotation O11 names; removing the filter is the other half and
    lives in `pipeline.parsed_fields`, which this change does not own.

    `Confidence` and `ConfidenceOrUnmeasured` are both
    `Annotated[..., PlainValidator(...)]` (`accountant_dad/confidence.py`);
    that validator only runs inside pydantic, so a plain dataclass field
    carries no runtime check by itself. The check still happens — deferred to
    `FieldConfidence`'s own construction in `record_confidence`, the one place
    downstream where an out-of-range or wrongly-typed score cannot pass
    silently.
    """

    field_name: str
    extraction_confidence: ConfidenceOrUnmeasured

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise MalformedSignalError(
                "a parsed field must carry a non-blank name; a nameless field "
                "cannot be matched to the confidence score built for it."
            )


@dataclass(frozen=True, slots=True)
class MissingField:
    """One field the document's structure calls for and does not contain.

    §1.3's third output component, missing field information. `state` keeps
    *"absent", "zero" and "unreadable"* distinguishable
    (`ENGINE_1_INPUT_ENGINE_RULES.md:569`) — collapsing them into one boolean
    is exactly the mistake that line exists to prevent, so `state` is carried
    through into the marker's reason rather than discarded.
    """

    field_name: str
    state: str

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise MalformedSignalError("a missing field must carry a non-blank name.")
        if not self.state.strip():
            raise MalformedSignalError(
                f'missing field {self.field_name!r} carries no state; "absent", '
                '"zero" and "unreadable" must remain distinguishable.'
            )


@dataclass(frozen=True, slots=True)
class HumanCaptureEvidence:
    """What `capture_fidelity` needs, and all it needs: the text as
    submitted, and the Human Business Context as it now stands.

    Both `cleaner` (§1.1) and `reader` (§1.2) are contractually forbidden
    from touching a provided source; each is required to pass it through
    untouched. So the only thing capture fidelity can honestly measure this
    far into the pipeline is whether that guarantee held.
    """

    submitted_text: str
    stored: HumanBusinessContext


def capture_fidelity(
    evidence: HumanCaptureEvidence,
) -> tuple[ConfidenceOrUnmeasured, UncertaintyMarker | None]:
    """Say what is known about how faithfully a Human Business Context was stored.

    Never whether the statement is true (`ENGINE_1_INPUT_ENGINE_RULES.md:624`)
    — only whether what is stored is what was submitted. See CAPTURE FIDELITY
    IS SCORED ONLY WHERE IT IS ACTUALLY DEFINED in the module docstring for
    why a mismatch returns no NUMBER rather than an invented partial one.

    ALWAYS RETURNS A STATE, NEVER `None`. It used to return `None` on a
    mismatch, and `record_confidence` then recorded nothing at all — so
    `CAPTURE_FIDELITY_FIELD_NAME` appeared in `confidence_scores` on a match
    and was ABSENT on a mismatch, which is indistinguishable from no Human
    Business Context having been supplied. The worst outcome was the silent
    one, and it was silent about the case where a preservation guarantee had
    just broken (`ENGINE_1_ARCHITECTURE.md` P-F3, concealed uncertainty).
    Amendment 7 gives the absence a name — `CAPTURE_FIDELITY_ON_MISMATCH`,
    FAILED — so both outcomes are stated and neither is a number.

    Returns `(state, marker)`. A match returns
    `CAPTURE_FIDELITY_ON_EXACT_MATCH` and no marker; a mismatch returns the
    FAILED state and a marker naming the mismatch as the finding.
    """
    if evidence.submitted_text == evidence.stored.original_user_text:
        return CAPTURE_FIDELITY_ON_EXACT_MATCH, None
    return (
        CAPTURE_FIDELITY_ON_MISMATCH,
        UncertaintyMarker(
            subject="the human business context",
            reason=(
                "the text now stored does not match, character for character, "
                "the text submitted, even though cleaner and reader are both "
                "required to pass a provided source through untouched "
                "(ENGINE_1_INPUT_ENGINE_RULES.md:459, :508). No numeric capture "
                "fidelity score is emitted for a mismatch: no locked document "
                "states a rule for grading a partial loss "
                "(ENGINE_1_CONFIDENCE_PARAMETERS.md gap #12), and inventing one "
                "is exactly what CLAUDE.md Law 54 forbids. The mismatch itself "
                "is the finding."
            ),
        ),
    )


def _preservation_marker(cleaned: CleanedDocument) -> UncertaintyMarker | None:
    """Relay `cleaner`'s own already-made finding. Nothing is re-decided.

    `cleaner.PreservationStatus.ORIGINAL_IS_SAFER` is `cleaner`'s verdict,
    reached from ITS caller's `max_ink_loss_fraction` — not a number this
    module compares against anything. This function only asks which of the
    two named states `cleaned.preservation_status` already is.
    """
    if cleaned.preservation_status is PreservationStatus.ORIGINAL_IS_SAFER:
        return UncertaintyMarker(
            subject="the document as cleaned",
            reason=(
                "cleaner found that processing this artifact could have lost "
                "information and reported the original as the safer basis for "
                "reading (engines/input_engine/cleaner.py, "
                "PreservationStatus.ORIGINAL_IS_SAFER); this module records "
                "that finding rather than re-deciding it."
            ),
        )
    return None


def _unread_region_markers(regions: tuple[RegionReading, ...]) -> tuple[UncertaintyMarker, ...]:
    """One marker per region `reader` could not read at all.

    `text is None` is `RegionReading`'s own definition of "unread" (see its
    docstring) — a categorical fact `reader` already established, not a score
    compared against a cut-off.
    """
    return tuple(
        UncertaintyMarker(
            subject=region.source_location,
            reason="reader could not read this region at all; nothing is guessed in its place.",
        )
        for region in regions
        if region.state is ReadingState.UNREAD
    )


def _unscored_region_markers(regions: tuple[RegionReading, ...]) -> tuple[UncertaintyMarker, ...]:
    """One marker per region `reader` read but did not score.

    Its text reaches the artifact with no reliability signal behind it. Saying
    nothing would be concealed uncertainty — the thing §1.4 and
    `ENGINE_1_ARCHITECTURE.md` P-F3 forbid — while inventing a stand-in score
    would be the fabrication `ENGINE_1_INPUT_ENGINE_RULES.md:337` forbids. The
    marker is the only honest third option: name it, score nothing.
    """
    return tuple(
        UncertaintyMarker(
            subject=region.source_location,
            reason=(
                "reader read this region but produced no per-region extraction "
                "score for it: the backend transcribed the text rather than "
                "recognising it, so no recogniser ran to produce one "
                "(engines/input_engine/reader.py, 'THE CONFIDENCE OF A TEXT "
                "LAYER IS None'). The text is real and is carried through; the "
                "absence of a score is recorded rather than filled in."
            ),
        )
        for region in regions
        if region.state is ReadingState.READ_BUT_UNSCORED
    )


def _missing_field_markers(
    missing_fields: tuple[MissingField, ...],
) -> tuple[UncertaintyMarker, ...]:
    """One marker per field `parser` recorded as absent from the document."""
    return tuple(
        UncertaintyMarker(
            subject=missing.field_name,
            reason=f"parser recorded this field as {missing.state}: not read from the document.",
        )
        for missing in missing_fields
    )


def _missing_field_scores(
    missing_fields: tuple[MissingField, ...],
) -> tuple[FieldConfidence, ...]:
    """One Confidence Report entry per field the document does not contain,
    each stating NOT_APPLICABLE and carrying `parser`'s own state verbatim.

    THE ASYMMETRY THIS REMOVES. A missing field already produced an
    `UncertaintyMarker` and no `FieldConfidence`, so the report NAMED it and
    said nothing about its reliability. That reads as an oversight rather than
    as a fact, and §1.4's job is *"the honest measurement of extraction
    trustworthiness, per field"* — for a field the document does not contain,
    the honest answer is that a score is not a question that applies here.

    NOT_APPLICABLE, not NOT_MEASURED: there is no reading for a score to be
    ABOUT. Collapsing the two would put "a real value carried with nothing
    behind it" and "there is nothing here at all" under one heading, and a
    human deciding what to check next needs them apart.

    `MissingField.state` — *"absent"*, *"zero"*, *"unreadable"* — is carried
    into the basis VERBATIM rather than mapped onto a state of this module's
    choosing. Those three must stay distinguishable
    (`ENGINE_1_INPUT_ENGINE_RULES.md:569`) and no document says which
    measurement state each implies, so translating them here would be this
    module answering a question nobody has answered (Law 54).

    Empty today and not because of a choice made here: `parser` is given no
    expected-field list and holds none, so `missing_field_information` reports
    nothing absent (`parser.py`, "WHICH FIELDS A DOCUMENT MUST CARRY IS
    KNOWLEDGE"). This is the mapping that will carry those fields the day one
    is supplied, not a claim that any exist now.
    """
    return tuple(
        FieldConfidence(
            field_name=missing.field_name,
            confidence=NotApplicableType(
                basis=(
                    f"parser recorded this field as {missing.state}: it was not read "
                    "from the document, so there is no reading here for a score to "
                    "be about"
                )
            ),
        )
        for missing in missing_fields
    )


def _field_confidence_scores(parsed_fields: tuple[ParsedField, ...]) -> tuple[FieldConfidence, ...]:
    """Mirror `reader`'s per-field confidence into the report, unmodified.

    Every value here is the exact object `parsed_fields` carried in; nothing
    is computed, rounded, or adjusted. This is how INV-2 ("confidence never
    changes because an engine reasoned harder") and the "never increase
    without evidence" boundary are satisfied — by never changing the number
    at all.
    """
    return tuple(
        FieldConfidence(field_name=field.field_name, confidence=field.extraction_confidence)
        for field in parsed_fields
    )


def _capture_fidelity_state(human_capture: HumanCaptureEvidence | None) -> str:
    """The three states `reliability_information` reports for capture
    fidelity. A tiny, separately-testable function rather than an inline
    branch, so the exact wording for each state is checked directly.
    """
    if human_capture is None:
        return "not supplied"
    score, _marker = capture_fidelity(human_capture)
    if measurement_state(score) is MeasurementState.MEASURED:
        return "matched the text as submitted, character for character"
    return "could not be established: the stored text differs from what was submitted"


def _reliability_information(
    cleaned: CleanedDocument,
    reader_regions: tuple[RegionReading, ...],
    parsed_fields: tuple[ParsedField, ...],
    missing_fields: tuple[MissingField, ...],
    human_capture: HumanCaptureEvidence | None,
) -> str:
    """A factual recount of what was received. No verdict — see the module
    docstring's boundary section on business plausibility. Counts and named
    states only; no word here claims the extraction was good, bad, reliable
    or risky, because none of those is a term this module is authorised to
    define (CLAUDE.md Law 54).
    """
    unread = sum(1 for region in reader_regions if region.state is ReadingState.UNREAD)
    unscored = sum(1 for region in reader_regions if region.state is ReadingState.READ_BUT_UNSCORED)
    capture_state = _capture_fidelity_state(human_capture)
    return (
        f"{len(parsed_fields)} field(s) carry a confidence score from parser; "
        f"{unread} of {len(reader_regions)} region(s) reader attempted could not "
        f"be read at all; {unscored} of them were read but carry no per-region "
        f"extraction score; {len(missing_fields)} field(s) parser recorded as "
        f"missing; cleaner's preservation status: {cleaned.preservation_status.value}; "
        f"human business context capture fidelity: {capture_state}."
    )


def record_confidence(
    cleaned: CleanedDocument,
    reader_regions: tuple[RegionReading, ...],
    parsed_fields: tuple[ParsedField, ...],
    missing_fields: tuple[MissingField, ...],
    human_capture: HumanCaptureEvidence | None = None,
) -> ConfidenceReport:
    """Assemble the Confidence Report from what `cleaner`, `reader` and
    `parser` produced. Records every signal it can name without inventing a
    cut-off. Decides nothing.

    `risky_fields` is always `()` — see RISKY FIELDS STAY EMPTY in the module
    docstring. `human_capture` defaults to `None` because a document with no
    Human Business Description is a genuine, ordinary state
    (`ENGINE_1_INPUT_ENGINE_RULES.md:138` — the description is optional and
    the system must work correctly without one); this is not a threshold
    default, it mirrors `DocumentEvidenceObject.human_business_context`'s own
    default in `accountant_dad.artifacts.evidence`.

    When `human_capture` is supplied, `CAPTURE_FIDELITY_FIELD_NAME` joins
    `confidence_scores` EITHER WAY — the one extra degree of freedom
    `FieldConfidence.field_name` is documented to allow (CONFIDENCE_SPECIFICATION.md
    §3.4: *"the name need not be a detected field"*). A match records the
    score; a mismatch records `CAPTURE_FIDELITY_ON_MISMATCH`, the FAILED
    state, alongside the `UncertaintyMarker` `capture_fidelity` returns. It
    used to record nothing on a mismatch, so the name's ABSENCE carried the
    finding — and an absence is indistinguishable from no Human Business
    Context having been supplied at all.

    Each `MissingField` also gets an entry, stating NOT_APPLICABLE — see
    `_missing_field_scores`. A name appearing in both `parsed_fields` and
    `missing_fields` is a contradiction (a field both read and not read) and
    `ConfidenceReport` refuses the collision rather than letting this module
    pick a side.

    Raises `MalformedSignalError` if a `RegionReading`, `ParsedField` or
    `MissingField` was itself malformed (that check runs at THEIR
    construction, before this function ever sees them) and
    `pydantic.ValidationError` if two scored names collide — a check this
    function does not repeat, because `ConfidenceReport` already owns it
    (`accountant_dad.artifacts.evidence.ConfidenceReport
    ._each_name_is_scored_once`, INV-10, CLAUDE.md Law 14).
    """
    markers: list[UncertaintyMarker] = []
    preservation = _preservation_marker(cleaned)
    if preservation is not None:
        markers.append(preservation)
    markers.extend(_unread_region_markers(reader_regions))
    markers.extend(_unscored_region_markers(reader_regions))
    markers.extend(_missing_field_markers(missing_fields))

    scores = list(_field_confidence_scores(parsed_fields))
    scores.extend(_missing_field_scores(missing_fields))
    if human_capture is not None:
        capture_score, capture_marker = capture_fidelity(human_capture)
        # Recorded whichever way the comparison came out. A mismatch used to
        # add nothing here, so this name appeared on a match and vanished on a
        # mismatch — silence about the one case where a preservation guarantee
        # had just broken. Both outcomes are now stated; neither is a number
        # this module chose.
        scores.append(
            FieldConfidence(field_name=CAPTURE_FIDELITY_FIELD_NAME, confidence=capture_score)
        )
        if capture_marker is not None:
            markers.append(capture_marker)

    return ConfidenceReport(
        confidence_scores=tuple(scores),
        uncertainty_markers=tuple(markers),
        reliability_information=_reliability_information(
            cleaned, reader_regions, parsed_fields, missing_fields, human_capture
        ),
        risky_fields=(),
    )
