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
