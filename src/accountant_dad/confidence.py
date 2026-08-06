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
    (`reader.py:255-259` - "`None` is NOT zero confidence and NOT full
    confidence - it is the absence of a measurement"). A PDF text layer is
    transcribed, not recognised; no instrument runs, so no instrument produces
    a score. A PDF text layer is also the MVP's primary input.

    WHY NO NUMBER WOULD DO. `1.0000` is the default
    `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids by name ("never to a default
    'good enough' value"). `0.0000` asserts a measured worthlessness nobody
    measured. None of the sixteen parameters in
    `ENGINE_1_CONFIDENCE_PARAMETERS.md` covers the case, so the number cannot
    be looked up either. There is no honest number, which is why this is a type
    and not a value (Law 54: never invent the definition).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

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


class UnmeasuredType:
    """The sentinel for "no instrument produced a score for this reading."

    NOT `None`, NOT a number, and NOT the same fact as
    `measurement.AbsentType`. The three shapes it must stay distinguishable
    from, and what each one already means elsewhere in this repository:

    | Shape | Fact | Where |
    |---|---|---|
    | `None` on `TextRegion.extraction_confidence` | the raw signal `reader` reports when no recogniser ran | `reader.py:255-259` |
    | `None` on `RegionReading.text` | the region could not be read at all | `confidence_report.ReadingState.UNREAD` |
    | `measurement.ABSENT` | this whole signal CATEGORY was never produced for the document | `measurement.py:147-170` |
    | `UNMEASURED` (here) | the value WAS read, and nothing scored it | `Provenance.confidence`, `FieldConfidence.confidence` |

    WHY NOT SHARE ONE SENTINEL WITH `measurement.AbsentType`. Two reasons, one
    of them mechanical and unarguable.

      1. THE SEMANTICS DIFFER, AND COLLAPSING THEM DESTROYS THE DISTINCTION
         BOTH TYPES EXIST TO KEEP. `ABSENT` says a category was never
         produced - nothing was attempted. `UNMEASURED` says a reading exists,
         is real, and travels into the artifact, and only its SCORE is
         missing. Sharing one class would make `isinstance(x, AbsentType)`
         answer yes to both, which is the exact collapse Law 24 forbids and
         the reason `measurement.py:41-59` refuses to let two facts wear one
         shape.
      2. SHARING IS A CIRCULAR IMPORT. `measurement.py:138` imports
         `DocumentId` from `artifacts.evidence`, and `artifacts.evidence`
         imports this module. `confidence -> measurement -> evidence ->
         confidence` does not import at all. Measured, not assumed.

    Layering says the same thing without either argument: `measurement.py` is
    an Engine 1 calibration store, and a type six artifact schemas depend on
    cannot be owned by one engine's internal module (INV-10, one owner per
    concept). The F-005 precedent is copied as a PATTERN - a distinct class,
    `__slots__ = ()`, a refused `__bool__`, a `__repr__` that names itself -
    never as a shared object (Law 53: copy the principle, never the mechanism).

    `__slots__ = ()` because a sentinel that can grow an attribute can stop
    being one. `__bool__` is REFUSED rather than answering `False`: written
    `if not provenance.confidence:`, an unmeasured reading and a reading
    measured at rock bottom would take the same branch - "nobody scored this"
    silently becoming "this scored zero", which is the single most alarming
    signal in the artifact collapsing into the most reassuring reading of it.
    Refusing forces every caller to say which it means, with
    `isinstance(x, UnmeasuredType)`.
    """

    __slots__: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return "UNMEASURED"

    def __bool__(self) -> bool:
        raise TypeError(
            "UNMEASURED has no truth value. Test it with "
            "`isinstance(x, UnmeasuredType)` - `if not confidence:` is exactly "
            "the collapse into a measured zero this type exists to prevent."
        )


#: The one instance every unmeasured slot uses. Compared with `isinstance`, not
#: with `is` and not with `==`: identity is deliberately NOT load-bearing, so a
#: second instance built by a caller behaves identically.
UNMEASURED: UnmeasuredType = UnmeasuredType()


def _a_measurement_or_its_stated_absence(value: object) -> Decimal | UnmeasuredType:
    """Accept the sentinel as itself; put everything else through the ruling.

    One validator, not two: the Decimal branch delegates to
    `_exactly_a_decimal_in_range` rather than restating four checks, so a slot
    that admits UNMEASURED enforces exactly the same scale as one that does not
    (Law 14, Law 19). The sentinel is tested FIRST and by type, because
    `_exactly_a_decimal_in_range` would otherwise refuse it as "not a Decimal"
    - correctly, and for the wrong question.
    """
    if isinstance(value, UnmeasuredType):
        return value
    return _exactly_a_decimal_in_range(value)


#: A slot that records EITHER a measurement or the stated absence of one.
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

    WHAT "AGREEMENT" MEANS WHEN ONE SIDE IS UNMEASURED. It is not exempted, and
    it is not loosened - it is stricter than numeric equality, because it has
    one more way to fail:

        both unmeasured          AGREE     neither claims a score; nothing to
                                           contradict
        both measured, equal     AGREE     the existing rule, unchanged
        both measured, differ    DISAGREE  the existing rule, unchanged
        one of each              DISAGREE  one side asserts a number the other
                                           says was never taken - which is the
                                           precise shape of the bug this type
                                           exists to prevent, so it is the case
                                           that must fail loudest

    `isinstance`, never `is` and never `==`. `==` between a `Decimal` and this
    sentinel answers `False` by falling through two `NotImplemented`s to
    identity - the right answer reached by accident, from a rule about neither
    type. A fact this load-bearing is decided by asking what each value IS.

    Numbers are still compared as numbers, so `0.98` and `0.9800` remain one
    value: `confidence.py` records what a producer asserted verbatim rather
    than padding it, and string comparison would make the same score disagree
    with itself.
    """
    left_unmeasured = isinstance(left, UnmeasuredType)
    right_unmeasured = isinstance(right, UnmeasuredType)
    if left_unmeasured or right_unmeasured:
        return left_unmeasured and right_unmeasured
    return left == right
