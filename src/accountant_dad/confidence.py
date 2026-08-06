"""The one representation of Confidence. Every artifact imports it from here.

The owner's ruling, verbatim and authoritative:

    Confidence is a normalized Decimal score (0.0000-1.0000) representing the
    system's degree of confidence in an artifact's correctness. It is not a
    probability and must not be used as the sole gating criterion for any
    decision.

    Storage: Decimal only, never float, to avoid precision loss.
    Display: percentages or High/Medium/Low bands are PRESENTATION, never the
    stored representation.
    Invariant: every artifact schema uses this single representation. No schema
    may define its own confidence type or scale.

WHY THIS MODULE EXISTS AT ALL. It was written after the failure it prevents.
Two artifact schemas were built on the same day from the same specification and
gave the word two incompatible types: one `float` bounded to [0, 1], the other
`Decimal` that explicitly rejected `float`. The result was that 0.7 was a legal
confidence on one artifact and an illegal one on the next, and 1.7 was legal on
the second and illegal on the first. Six artifacts each carry a confidence
field, so the divergence was going to be sixfold. One definition, imported, is
the only structural fix - a convention would have been agreed and then drifted
exactly the same way.

WHAT THIS TYPE DOES AND DOES NOT ENFORCE.

Enforced here, structurally:
  - Decimal, never float, never int
  - inclusive range 0.0000 to 1.0000
  - at most four decimal places, the scale the ruling wrote
  - finite: NaN and the infinities are refused

NOT enforced here, and it cannot be:
  - "must not be used as the sole gating criterion for any decision"

That last rule constrains how a CALLER reasons, not what a value contains. No
type can see the decision a number was used for. It is a review-only
prohibition and belongs on the prohibition inventory, not in this file. Saying
so plainly is the point: a reader who assumes importing this type satisfies the
whole ruling would be wrong, and quietly wrong.

NOT A PROBABILITY. `MEASUREMENT_FRAMEWORK.md` puts it sharply - until the
separation test passes, confidence is an ordinal ranking. A four-place decimal
happens to LOOK like a probability, which is exactly why the ruling says in
words that it is not one. Nothing here may be multiplied with another
confidence, summed, or fed to Bayes.

A MEASUREMENT AND THE ABSENCE OF ONE ARE TWO DIFFERENT FACTS (Amendment 5).
`UnmeasuredType` below is the second one, and `ConfidenceOrUnmeasured` is the
slot that can hold either. `Confidence` itself is UNCHANGED and still admits
only a `Decimal` in [0.0000, 1.0000] - the owner's ruling defines confidence as
a score, and the absence of a score is not a score. Widening `Confidence` would
have let every artifact in the system carry "not measured" wherever a number
belongs; instead the two states are separate types and only the slots that
genuinely need both say so.

    WHY IT IS NEEDED. `reader.read_pdf_text_layer` sets
    `extraction_confidence=None` on every region it produces, by design
    (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER IS None" - "`None` is NOT
    zero confidence and NOT full confidence - it is the absence of a
    measurement"). A PDF text layer is transcribed, not recognised; no
    instrument runs, so no instrument produces a score. A PDF text layer is
    also the MVP's primary input.

    WHY NO NUMBER WOULD DO. `1.0000` is the default
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids by name ("never to a default
    'good enough' value"). `0.0000` asserts a measured worthlessness nobody
    measured. None of the sixteen parameters in
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` covers the case, so the number cannot
    be looked up either. There is no honest number, which is why this is a type
    and not a value (Law 54: never invent the definition).

THERE ARE FOUR STATES, NOT TWO (Amendment 7, approved by the owner 2026-08-06).
Amendment 5 named ONE way a measurement can be absent and stopped there. Its
own "What would prove this wrong" section named the successor condition in
advance: *"A slot that needs a third measurement state ... If one is found,
this amendment needs a successor, not a patch."* Two were found.

    measured          an instrument ran and produced a score. A `Decimal` on
                      the agreed scale, and the only state that IS a number.
    not measured      the value was read, is real, and travels into the
                      artifact; nothing scored it. `NotMeasuredType`.
    not applicable    there is no reading here for a score to be ABOUT. A
                      grid position the document left blank, a field the
                      document does not contain. `NotApplicableType`.
    failed            an instrument was asked and could not produce a
                      reading or a score. Something went wrong, and that is
                      itself the finding. `MeasurementFailedType`.

THE ROOT CAUSE ALL FOUR EXIST TO REMOVE. Before Amendment 5 this module
modelled the RESULT of measuring - a number - and used `None` for everything
else. `None` was already spoken for four ways in the same pipeline
(`reader.TextRegion.extraction_confidence`, `confidence_report.RegionReading
.text`, `parser.Cell.text`, an absent `HumanBusinessContext`), so the absence
of a measurement had no name, and a fact with no name cannot be carried,
checked or refused. A schema demanding a number from a world that supplies one
only sometimes leaves code three moves: INVENT a number, DROP the value, or
CRASH. This repository has done the first two, in production paths, and each
time the fix named one more special case.

The transform (Law 53) is to stop modelling the score and start modelling
WHAT HAPPENED WHEN WE TRIED TO MEASURE. "Measured" then becomes one of four
outcomes rather than the only representable one, and the other three stop
having to disguise themselves as numbers or as silence.

    NOT COLLAPSIBLE, BY CONSTRUCTION AND NOT BY CARE. No non-measured state
    has a truth value, an ordering, or a numeric conversion; none is a
    default anywhere; none can be constructed without stating WHY in
    `basis`; and `records_the_same_measurement` treats two different
    non-measured states as a DISAGREEMENT, exactly as it treats a measured
    value against a non-measured one.

    ONE COMMON BASE, ON PURPOSE. `UnmeasuredType` is the base of all three,
    so every caller already written as `isinstance(x, UnmeasuredType)` keeps
    getting the correct answer to "is a measurement absent here?" as states
    are added (Law 33). Asking WHICH of the four is `measurement_state`, and
    that is the only question a caller should be answering with a branch.
    Sibling classes with no shared base were rejected for exactly this: an
    existing `isinstance` test would have started answering "measured" for a
    value nobody measured - silent, and in the reassuring direction, which is
    the failure mode this whole module exists to prevent (Law 11).
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import Field, PlainValidator

#: Four, because the ruling wrote the bounds as `0.0000-1.0000`. Not a default
#: and not a rounding choice - it is the agreed scale, read off the agreement.
CONFIDENCE_PLACES = 4

MIN = Decimal("0.0000")
MAX = Decimal("1.0000")


def _exactly_a_decimal_in_range(value: object) -> Decimal:
    """Accept a Decimal that already satisfies the ruling. Convert nothing.

    A PlainValidator, not a BeforeValidator with a type annotation, and
    deliberately: pydantic's own Decimal handling coerces `float` and `int`
    into Decimal before any constraint runs. `Decimal(0.1)` is
    0.1000000000000000055511151231257827021181583404541015625 - the coercion
    IS the precision loss the ruling forbids, and it would have happened
    before any check of ours could object. So the check has to come first and
    refuse the type outright.
    """
    if not isinstance(value, Decimal):
        raise ValueError(
            f"confidence must be a Decimal, got {type(value).__name__}. "
            "float and int are refused rather than converted: converting is "
            "the precision loss the representation exists to prevent."
        )
    if not value.is_finite():
        raise ValueError(
            f"confidence must be finite, got {value}. A non-finite Decimal "
            "compares false against everything and would poison every "
            "comparison downstream of the artifact carrying it."
        )
    if not MIN <= value <= MAX:
        raise ValueError(f"confidence must be within [{MIN}, {MAX}], got {value}")

    # `exponent` is int for a finite Decimal, but the type is
    # `int | Literal["n", "N", "F"]` because NaN and Infinity use those markers.
    # Narrow BEFORE negating - `-"n"` is a TypeError, and the finiteness check
    # above already guarantees we never get there, which is exactly the kind of
    # guarantee a typechecker is right not to take on trust.
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > CONFIDENCE_PLACES:
        places = -exponent
        raise ValueError(
            f"confidence carries {places} decimal places; the agreed scale is "
            f"{CONFIDENCE_PLACES} ({MIN} to {MAX}). Refused rather than rounded: "
            "an artifact is immutable and auditable, so silently rewriting a "
            "value its producer asserted would falsify the record."
        )
    return value


#: The canonical type. Import this; never redeclare it.
#:
#: Fewer than four places is fine and is left exactly as written - `Decimal("0.5")`
#: stays `0.5`, it is not rewritten to `0.5000`. An artifact records what its
#: producer asserted, verbatim.
Confidence = Annotated[
    Decimal,
    PlainValidator(_exactly_a_decimal_in_range),
    Field(ge=MIN, le=MAX),
]


class MeasurementState(StrEnum):
    """WHICH of the four a confidence slot is in. The one question a caller
    branches on, so there is exactly one place that answers it.

    A `StrEnum` for the reason `evidence.SourceType` is one: the spellings
    reach humans, in refusal messages and in the reliability text an accountant
    reads, and a member renamed silently is a contract changed silently.

    NOT STORED ANYWHERE. It is DERIVED, by `measurement_state`, from the value
    itself - the same discipline `confidence_report.RegionReading.state` uses,
    and for the same reason: a stored state can disagree with the value it
    describes, and a derived one cannot.
    """

    MEASURED = "measured"
    NOT_MEASURED = "not measured"
    NOT_APPLICABLE = "not applicable"
    FAILED = "failed"


class UnmeasuredType:
    """No measurement is recorded here, and this says WHICH kind of absence.

    ABSTRACT. Instantiating it directly is refused: "a measurement is absent,
    and I decline to say how" is precisely the *"unknown but looks valid"*
    shape the four states exist to make unrepresentable. Use
    `NotMeasuredType`, `NotApplicableType` or `MeasurementFailedType`.

    NOT `None`, NOT a number, and NOT the same fact as
    `measurement.AbsentType`. The shapes it must stay distinguishable from,
    and what each already means elsewhere in this repository:

        None on TextRegion.extraction_confidence
            the raw signal `reader` reports when no recogniser ran
            (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER IS None")
        None on RegionReading.text
            the region could not be read at all
            (`confidence_report.ReadingState.UNREAD`)
        measurement.ABSENT
            this whole signal CATEGORY was never produced for the document
            (`measurement.AbsentType`)
        a subclass of this, here
            what happened when this ONE value's reliability was measured
            (`Provenance.confidence`, `FieldConfidence.confidence`)

    WHY NOT SHARE ONE SENTINEL WITH `measurement.AbsentType`. Two reasons, one
    of them mechanical and unarguable.

      1. THE SEMANTICS DIFFER, AND COLLAPSING THEM DESTROYS THE DISTINCTION
         BOTH TYPES EXIST TO KEEP. `ABSENT` says a category was never
         produced - nothing was attempted. These say a reading was attempted,
         and record what came of it. Sharing one class would make
         `isinstance(x, AbsentType)` answer yes to both, which is the exact
         collapse Law 24 forbids and the reason `measurement.AbsentType`
         refuses to let two facts wear one shape.
      2. SHARING IS A CIRCULAR IMPORT. `measurement` imports `DocumentId`
         from `artifacts.evidence`, and `artifacts.evidence` imports this
         module. `confidence -> measurement -> evidence -> confidence` does
         not import at all. Measured, not assumed.

    Layering says the same thing without either argument: `measurement.py` is
    an Engine 1 calibration store, and a type six artifact schemas depend on
    cannot be owned by one engine's internal module (INV-10, one owner per
    concept). The F-005 precedent is copied as a PATTERN - a distinct class,
    `__slots__`, a refused `__bool__`, a `__repr__` that names itself - never
    as a shared object (Law 53: copy the principle, never the mechanism).

    `__slots__` and no `__dict__`, because a value that can grow an attribute
    can stop being the thing it claims to be. `__bool__` is REFUSED rather
    than answering `False`: written `if not provenance.confidence:`, a reading
    nobody scored and a reading a recogniser scored at rock bottom take the
    same branch - the single most alarming signal in the artifact silently
    becoming the most reassuring reading of it. Ordering is refused for the
    same reason one level up: `confidence < threshold` is how a gate gets
    written, and against one of these it must be a stack trace and never a
    branch (`MEASUREMENT_FRAMEWORK.md` - confidence "may gate NOTHING").

    `basis` IS REQUIRED AND MAY NOT BE BLANK. Which of the three is the
    STATE; `basis` is the WHY. An absence with no stated reason is a gap that
    reads as a decision, and `ENGINE_1_INPUT_ENGINE_RULES.md:626` already
    settles the general form of this - *"Every uncertainty marker carries a
    reason. A bare score cannot become a good question downstream."* A bare
    absence is worse than a bare score.
    """

    __slots__: tuple[str, ...] = ("basis",)

    #: Set by each concrete subclass; the base deliberately has none, so a
    #: subclass that forgets to declare one cannot be constructed silently.
    state: ClassVar[MeasurementState]

    #: Why no measurement exists for this value. Free text, non-blank, and
    #: carried verbatim into refusal messages so a reader learns the reason
    #: at the point the artifact is refused rather than three hops later.
    basis: str

    def __init__(self, basis: str) -> None:
        if type(self) is UnmeasuredType:
            raise TypeError(
                "UnmeasuredType is abstract: it says a measurement is absent "
                "without saying which absence. Construct NotMeasuredType, "
                "NotApplicableType or MeasurementFailedType - naming which of "
                "the three is the whole reason the base exists."
            )
        if not basis.strip():
            raise ValueError(
                f"{type(self).__name__} needs a non-blank basis saying why no "
                "measurement exists. An absence with no stated reason is a gap "
                "that reads as a decision nobody made."
            )
        object.__setattr__(self, "basis", basis)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"{type(self).__name__} is immutable; {name!r} cannot be reassigned. "
            "A measurement state that can be edited in place is a fact that can "
            "be rewritten after the artifact carrying it was audited."
        )

    def __repr__(self) -> str:
        return self.state.name

    def __bool__(self) -> bool:
        raise TypeError(
            f"{self.state.name} has no truth value. Test it with "
            "`measurement_state(x)` - `if not confidence:` is exactly "
            "the collapse into a measured zero this type exists to prevent."
        )

    def _refuse_comparison(self, other: object) -> bool:
        raise TypeError(
            f"{self.state.name} has no magnitude, so it cannot be ordered "
            f"against {other!r}. A comparison is how a confidence gate gets "
            "written, and MEASUREMENT_FRAMEWORK.md holds that confidence may "
            "gate nothing until calibration passes. Ask `measurement_state(x)` "
            "which state this is instead."
        )

    __lt__ = _refuse_comparison
    __le__ = _refuse_comparison
    __gt__ = _refuse_comparison
    __ge__ = _refuse_comparison


class NotMeasuredType(UnmeasuredType):
    """The value was READ, is real, and travels into the artifact. Nothing
    scored it.

    The state a PDF text layer produces for every value on the page: it is
    transcribed rather than recognised, so no recogniser ran and no recogniser
    produced a score (`reader.py`, "THE CONFIDENCE OF A TEXT LAYER IS None").
    Nothing is wrong with the document and nothing is wrong with the reading -
    the score simply does not exist.
    """

    __slots__: tuple[str, ...] = ()
    state: ClassVar[MeasurementState] = MeasurementState.NOT_MEASURED


class NotApplicableType(UnmeasuredType):
    """There is no reading here for a score to be ABOUT.

    Distinct from NOT_MEASURED, and the distinction is the point: NOT_MEASURED
    says a real value is carried with no score behind it, so a human may want
    to check it. NOT_APPLICABLE says there is nothing to check - a grid
    position the document left blank, a field the document does not contain.
    Collapsing the two would either manufacture work on empty cells or hide a
    genuinely unscored value among them.
    """

    __slots__: tuple[str, ...] = ()
    state: ClassVar[MeasurementState] = MeasurementState.NOT_APPLICABLE


class MeasurementFailedType(UnmeasuredType):
    """An instrument was asked, and could not produce a reading or a score.

    The alarming one, and the reason it may never share a shape with the other
    two: NOT_MEASURED and NOT_APPLICABLE are ordinary states of a healthy run,
    while this one says something went wrong at this exact value. Reported as
    a state rather than raised, because one region a recogniser could not read
    is not a document that could not be read
    (`COMMUNICATION_RULES_INPUT_ENGINE.md:159` - the Input Engine reports, it
    does not halt the pipeline).
    """

    __slots__: tuple[str, ...] = ()
    state: ClassVar[MeasurementState] = MeasurementState.FAILED


#: The one NOT_MEASURED value shared by callers with nothing more specific to
#: say. A NAMED constant with its reason written here, never a default: no
#: schema slot falls back to it, and a caller with a sharper reason builds its
#: own `NotMeasuredType`. Compared with `measurement_state`, not with `is` and
#: not with `==`: identity is deliberately NOT load-bearing, so a second
#: instance built by a caller behaves identically.
UNMEASURED: NotMeasuredType = NotMeasuredType(
    basis="no instrument produced a score for this reading"
)


def measurement_state(value: Decimal | UnmeasuredType) -> MeasurementState:
    """WHICH of the four states a confidence slot holds. The only inspector.

    Total over the union and hostile to everything else. A `float`, an `int`,
    a `str` or `None` reaching a confidence slot is refused HERE rather than
    reported as MEASURED - `float` in particular is the one that matters,
    because `1.0` is both the forbidden default
    (`ENGINE_1_INPUT_ENGINE_RULES.md:625`) and the value a coercion produces
    from `True`. A classifier that answered "measured" for it would launder
    exactly the fabrication this module exists to refuse (Law 24).

    `isinstance`, never `is` and never `==`, for the reason
    `records_the_same_measurement` gives below.
    """
    if isinstance(value, UnmeasuredType):
        return value.state
    if isinstance(value, Decimal):
        return MeasurementState.MEASURED
    raise TypeError(
        f"{value!r} is neither a Decimal measurement nor a stated absence of "
        f"one, so it has no measurement state. {type(value).__name__} was "
        "refused rather than reported as measured: a value that only looks "
        "like a score is the fabrication this type exists to prevent."
    )


def describe_measurement(value: Decimal | UnmeasuredType) -> str:
    """One phrase a human can read for what a confidence slot holds.

    The ONE place a measurement state is put into words, so a refusal raised
    by `evidence.py` and a reason recorded by the `confidence` sub-engine
    cannot describe the same fact two ways (Law 14, Law 19).

    A measured value reads as its number; an absent one reads as its state
    AND its basis, because "not measured" without a reason sends the reader
    back to the source to find out why, which is the whole cost the `basis`
    field exists to remove.

    `measurement_state` is called first and its result discarded on the
    measured branch, deliberately: it is what refuses a `float`, an `int` or
    a `None` that reached a confidence slot, and describing one of those as
    though it were a score is the fabrication this module refuses (Law 24).
    """
    state = measurement_state(value)
    if isinstance(value, UnmeasuredType):
        return f"{state.value} ({value.basis})"
    return f"{state.value} {value}"


def _a_measurement_or_its_stated_absence(value: object) -> Decimal | UnmeasuredType:
    """Accept a stated absence as itself; put everything else through the ruling.

    One validator, not two: the Decimal branch delegates to
    `_exactly_a_decimal_in_range` rather than restating four checks, so a slot
    that admits an absence enforces exactly the same scale as one that does not
    (Law 14, Law 19). The absence is tested FIRST and by type, because
    `_exactly_a_decimal_in_range` would otherwise refuse it as "not a Decimal"
    - correctly, and for the wrong question.

    Tested against the BASE, so all three non-measured states pass through one
    branch and a fourth added later inherits the acceptance rather than having
    to remember it.
    """
    if isinstance(value, UnmeasuredType):
        return value
    return _exactly_a_decimal_in_range(value)


#: A slot that records EITHER a measurement or the stated absence of one, in
#: any of the three ways an absence can arise (Amendment 7). The annotation
#: names the BASE, so a fourth kind of absence added later needs no change at
#: any of the slots that carry one.
#:
#: A `PlainValidator`, for the reason `Confidence` gives above: pydantic's own
#: Decimal handling coerces before any constraint of ours could run, and a
#: PlainValidator replaces the inner schema outright so no coercion happens and
#: an arbitrary class needs no `arbitrary_types_allowed` on the model.
#:
#: `Field(ge=MIN, le=MAX)` is deliberately NOT attached: a numeric bound cannot
#: be stated over a union whose other member is not a number. Nothing is lost -
#: `_exactly_a_decimal_in_range` is what actually enforces the range, on this
#: type and on `Confidence` alike, and it is the same function in both.
ConfidenceOrUnmeasured = Annotated[
    Decimal | UnmeasuredType,
    PlainValidator(_a_measurement_or_its_stated_absence),
]


def records_the_same_measurement(
    left: Decimal | UnmeasuredType, right: Decimal | UnmeasuredType
) -> bool:
    """Whether two slots state the SAME fact about measurement.

    THE COMPLETE RULE, over all four states. It is not exempted anywhere and
    it is not loosened anywhere - every state added has made it STRICTER,
    because each one is a new way for two slots to differ:

        same state, both measured, equal numbers   AGREE
        same state, both measured, different       DISAGREE
        same non-measured state                    AGREE     neither claims a
                                                             score; there is
                                                             nothing to
                                                             contradict
        different states                           DISAGREE  including every
                                                             measured-against-
                                                             non-measured pair
                                                             and every pair of
                                                             DIFFERENT
                                                             non-measured
                                                             states

    Measured against non-measured is the precise shape of the bug these types
    exist to prevent - one side asserts a number the other says was never
    taken - so it must fail loudest. NOT_MEASURED against NOT_APPLICABLE fails
    for the same reason one level in: one side says a real value is carried
    with no score behind it and the other says there is no value at all. Two
    components that disagree about whether something was even read have not
    "both declined to score", and treating them as agreeing would let the
    disagreement travel into the artifact unremarked.

    THE BASIS IS NOT PART OF AGREEMENT, DELIBERATELY. Two components may say
    "nothing scored this" for reasons worded differently and still be stating
    the same fact. Agreement is over the STATE; the basis is the explanation
    carried alongside it, and comparing explanations would turn a prose edit
    into a refused artifact.

    `measurement_state`, never `is` and never `==`. `==` between a `Decimal`
    and a non-measured state answers `False` by falling through two
    `NotImplemented`s to identity - the right answer reached by accident, from
    a rule about neither type. A fact this load-bearing is decided by asking
    what each value IS.

    Numbers are still compared as numbers, so `0.98` and `0.9800` remain one
    value: this module records what a producer asserted verbatim rather than
    padding it, and string comparison would make the same score disagree with
    itself.
    """
    state = measurement_state(left)
    if state is not measurement_state(right):
        return False
    if state is MeasurementState.MEASURED:
        return left == right
    return True
