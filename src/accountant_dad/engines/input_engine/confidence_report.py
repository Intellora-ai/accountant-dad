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
    `parser.ParsedStructure` has no concept of a named field at all yet — it
    carries `Region` and `Table`/`Cell` geometry, not the "structured
    fields" §1.3 promises. Importing either real type today would therefore
    either lose a state this module must keep, or have nothing to import.
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
    finding, carried as an `UncertaintyMarker`. That `MAX` score is not left
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

from accountant_dad.artifacts.evidence import (
    ConfidenceReport,
    FieldConfidence,
    HumanBusinessContext,
    UncertaintyMarker,
)
from accountant_dad.confidence import MAX, Confidence
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


class MalformedSignalError(ValueError):
    """A signal this module cannot honestly record without inventing part of
    it — a field with no name, a region claiming both a reading and no
    confidence for it. Raised on the CALLER'S data, at construction, the same
    defence `cleaner.CleanerSettings` uses against an impossible setting.
    Never raised because a document was read poorly (§1.4 — this module
    cannot reject a document or halt the pipeline).
    """


@dataclass(frozen=True, slots=True)
class RegionReading:
    """One thing `reader` found, or failed to find, at one place on the page.

    §1.2's output, per region: *"raw extracted information ... source
    locations ... extraction confidence."* See the module docstring, TWO
    INPUTS ARE CONTRACTS — this is read off that prose, not off `reader`'s
    code, which does not yet carry this shape.

    `text` is `None` for *"a region that could not be read at all ...
    reported as unread, not omitted silently"* (§1.2 Failure Behaviour).
    `extraction_confidence` is `None` in exactly that case and no other: an
    instrument cannot score a reading that does not exist. An unclear
    character or word still carries text — however garbled — and a
    confidence; §1.2's *"never resolved by guessing"* describes the VALUE a
    reading holds, not whether a score accompanies it.
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
        if (self.text is None) != (self.extraction_confidence is None):
            raise MalformedSignalError(
                f"region {self.source_location!r} carries text without a "
                "confidence, or a confidence without text; an unread region has "
                "neither, and a read region -- however unclear -- has both."
            )


@dataclass(frozen=True, slots=True)
class ParsedField:
    """One field `parser` recovered, with the extraction confidence `reader`
    attached to the region it came from, carried through unchanged.

    §1.3's output component, structured fields. `extraction_confidence` is
    not re-scored here — this module's boundary forbids re-reading or
    re-parsing (§1.4) — it is the same reading `reader` produced, mirrored
    into a `FieldConfidence` entry by `_field_confidence_scores` below and
    never modified.

    `Confidence` is `Annotated[Decimal, PlainValidator(...)]`
    (`accountant_dad/confidence.py`); that validator only runs inside
    pydantic, so a plain dataclass field carries no runtime check by itself.
    The check still happens — deferred to `FieldConfidence`'s own
    construction in `record_confidence`, the one place downstream where an
    out-of-range or wrongly-typed score cannot pass silently.
    """

    field_name: str
    extraction_confidence: Confidence

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
) -> tuple[Confidence | None, UncertaintyMarker | None]:
    """Score how faithfully a Human Business Context was stored.

    Never whether the statement is true (`ENGINE_1_INPUT_ENGINE_RULES.md:624`)
    — only whether what is stored is what was submitted. See CAPTURE FIDELITY
    IS SCORED ONLY WHERE IT IS ACTUALLY DEFINED in the module docstring for
    why a mismatch returns no score rather than an invented partial one.

    Returns `(score, marker)`. Exactly one of the two is non-`None`: a match
    returns `CAPTURE_FIDELITY_ON_EXACT_MATCH` and no marker; a mismatch
    returns no score and a marker naming the mismatch as the finding.
    """
    if evidence.submitted_text == evidence.stored.original_user_text:
        return CAPTURE_FIDELITY_ON_EXACT_MATCH, None
    return (
        None,
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
        if region.text is None
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
    if score is not None:
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
    unread = sum(1 for region in reader_regions if region.text is None)
    capture_state = _capture_fidelity_state(human_capture)
    return (
        f"{len(parsed_fields)} field(s) carry a confidence score from parser; "
        f"{unread} of {len(reader_regions)} region(s) reader attempted could not "
        f"be read at all; {len(missing_fields)} field(s) parser recorded as "
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

    When `human_capture` is supplied and its text matches exactly, the
    capture-fidelity score joins `confidence_scores` under
    `CAPTURE_FIDELITY_FIELD_NAME` — the one extra degree of freedom
    `FieldConfidence.field_name` is documented to allow (CONFIDENCE_SPECIFICATION.md
    §3.4: *"the name need not be a detected field"*). A mismatch adds no
    score to `confidence_scores`, only the `UncertaintyMarker`
    `capture_fidelity` already returns.

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
    markers.extend(_missing_field_markers(missing_fields))

    scores = list(_field_confidence_scores(parsed_fields))
    if human_capture is not None:
        capture_score, capture_marker = capture_fidelity(human_capture)
        if capture_score is not None:
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
