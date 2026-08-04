"""The one representation of Confidence, shared by every artifact.

Owner's ruling, verbatim:

    Confidence is a normalized Decimal score (0.0000-1.0000) representing the
    system's degree of confidence in an artifact's correctness. It is not a
    probability and must not be used as the sole gating criterion for any
    decision.

Written before the implementation. The dangerous direction here is the
permissive one: this project posts into real books, and a confidence value
that silently lost precision, or that a float rounded, is a number nobody can
audit afterwards.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from accountant_dad.confidence import CONFIDENCE_PLACES, MAX, MIN, Confidence

adapter: TypeAdapter[Decimal] = TypeAdapter(Confidence)


class Holder(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any
    model_config = ConfigDict(frozen=True, extra="forbid")

    score: Confidence


def messages(raised: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    """Every message pydantic reported, EXACTLY as the validator worded it.

    Equality, not substring. `match="must be a Decimal"` passes against a
    refusal whose remaining two sentences have been deleted, re-cased or
    emptied — measured, not supposed: thirteen mutations of the three refusals
    in `confidence.py` survived CI run 30946373087 with every test here green.

    The wording is not decoration. Each refusal answers the question the reader
    asks next — *why was my perfectly reasonable 0.7 rejected?* — and a
    refusal that raises without answering it sends whoever hits it to go
    "fix" the value rather than the type.
    """
    return [str(error["msg"]) for error in raised.value.errors()]


# ── the agreed range, at both ends ───────────────────────────────────────────


@pytest.mark.parametrize("ok", ["0.0000", "1.0000", "0.5000", "0.0001", "0.9999"])
def test_a_value_inside_the_agreed_range_is_accepted(ok: str) -> None:
    assert adapter.validate_python(Decimal(ok)) == Decimal(ok)


@pytest.mark.parametrize("bad", ["-0.0001", "1.0001", "-1.0000", "2.0000"])
def test_a_value_outside_the_agreed_range_is_rejected(bad: str) -> None:
    # Both ends are inclusive and both are hard. A score above 1 is not
    # "very confident", it is a defect in whatever produced it.
    with pytest.raises(ValidationError):
        adapter.validate_python(Decimal(bad))


def test_the_range_error_names_the_bounds_and_the_offending_value() -> None:
    # Added after a mutation survived. Deleting the explicit range check in
    # confidence.py broke NO test, because Field(ge/le) enforces the range too
    # — an equivalent mutant, not a weak assertion. The check earns its place
    # only through the diagnostic it produces, so the diagnostic is what gets
    # asserted. Without this, that branch is unreachable by any test and is
    # indistinguishable from dead code.
    with pytest.raises(ValidationError, match=r"within \[0.0000, 1.0000\], got 2.0000"):
        adapter.validate_python(Decimal("2.0000"))


# ── never float ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", [0.5, 0.0, 1.0, 0.1])
def test_a_float_is_rejected_even_when_its_value_is_legal(bad: float) -> None:
    # The ruling says Decimal only, "never float, to avoid precision loss".
    # 0.5 is a perfectly legal CONFIDENCE and an illegal TYPE. Accepting it
    # and converting would be the silent precision loss the rule forbids -
    # Decimal(0.1) is 0.1000000000000000055511151231257827021181583404541015625.
    with pytest.raises(ValidationError):
        adapter.validate_python(bad)


def test_the_float_rejection_is_not_merely_a_range_check() -> None:
    # A float whose value is in range must still fail. If this passed, the
    # type would be accepting floats and the previous test would be proving
    # nothing but the range.
    with pytest.raises(ValidationError):
        adapter.validate_python(0.7)


@pytest.mark.parametrize(
    ("bad", "type_name"),
    [(0.7, "float"), (1, "int"), ("0.7", "str"), (None, "NoneType"), (True, "bool")],
)
def test_the_type_refusal_names_the_type_it_got_and_why_converting_is_refused(
    bad: object, type_name: str
) -> None:
    # The type name is the whole diagnostic value of this refusal: `0.7` and
    # `Decimal("0.7")` are indistinguishable when printed, so a message that
    # did not name the TYPE would leave the reader staring at a number that
    # looks correct. `type(value).__name__` replaced by a constant still
    # raises, still says "must be a Decimal", and tells four of these five
    # callers something false.
    with pytest.raises(ValidationError) as raised:
        adapter.validate_python(bad)

    assert messages(raised) == [
        f"Value error, confidence must be a Decimal, got {type_name}. "
        "float and int are refused rather than converted: converting is "
        "the precision loss the representation exists to prevent."
    ]


def test_an_int_is_rejected_rather_than_widened() -> None:
    # 1 is in range and would widen to Decimal("1") cleanly. Still rejected:
    # the agreed representation is a four-place Decimal, and accepting bare
    # ints reintroduces two spellings of the same score.
    with pytest.raises(ValidationError):
        adapter.validate_python(1)


# ── scale: the ruling wrote 0.0000, which fixes four places ──────────────────


@pytest.mark.parametrize("bad", ["0.00001", "0.123456", "0.50000"])
def test_more_precision_than_the_agreed_scale_is_rejected_not_rounded(bad: str) -> None:
    # Rounding would be the friendly choice and the wrong one. Quantising
    # 0.00001 to 0.0000 changes a stated value inside an artifact that is
    # immutable and auditable (INV-5). Refusing is the honest failure.
    with pytest.raises(ValidationError):
        adapter.validate_python(Decimal(bad))


@pytest.mark.parametrize(("bad", "places"), [("0.00001", 5), ("0.123456", 6), ("0.50000", 5)])
def test_the_scale_refusal_counts_the_places_and_names_the_agreed_scale(
    bad: str, places: int
) -> None:
    # `places = -exponent` mutated to `+exponent` prints "carries -5 decimal
    # places" — still a refusal, still `ValidationError`, and a count that is
    # negative is not a count. Asserting the number is the only thing that
    # separates the two, and the number is what the reader trims the value by.
    with pytest.raises(ValidationError) as raised:
        adapter.validate_python(Decimal(bad))

    assert messages(raised) == [
        f"Value error, confidence carries {places} decimal places; the agreed scale is "
        f"{CONFIDENCE_PLACES} ({MIN} to {MAX}). Refused rather than rounded: "
        "an artifact is immutable and auditable, so silently rewriting a "
        "value its producer asserted would falsify the record."
    ]
    assert places > CONFIDENCE_PLACES, "a refusal that reports fewer places than the scale is a lie"


def test_fewer_places_than_the_scale_are_accepted_and_left_exactly_as_given() -> None:
    # Decimal("0.5") is unambiguous and loses nothing. It is NOT rewritten to
    # "0.5000": an artifact records what its producer asserted, verbatim.
    assert str(adapter.validate_python(Decimal("0.5"))) == "0.5"


def test_the_scale_constant_matches_the_ruling() -> None:
    # 0.0000 has four places. If someone changes the constant, this fails and
    # names the ruling rather than letting the change pass silently.
    assert len("0000") == CONFIDENCE_PLACES
    assert (Decimal("0.0000"), Decimal("1.0000")) == (MIN, MAX)


# ── the non-finite values a Decimal can legally hold ─────────────────────────


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_a_non_finite_decimal_is_rejected(bad: str) -> None:
    # Decimal("NaN") constructs happily and compares false against everything,
    # so a range check alone would let it through and it would then poison
    # every comparison downstream.
    with pytest.raises(ValidationError):
        adapter.validate_python(Decimal(bad))


@pytest.mark.parametrize(
    ("bad", "shown"),
    [("NaN", "NaN"), ("Infinity", "Infinity"), ("-Infinity", "-Infinity"), ("sNaN", "sNaN")],
)
def test_the_non_finite_refusal_names_the_value_and_why_it_poisons_comparisons(
    bad: str, shown: str
) -> None:
    # A `Decimal("NaN")` that reached an artifact would compare false against
    # every threshold downstream, so the refusal has to say WHY rather than
    # only that something was wrong — otherwise the obvious "fix" is to relax
    # whichever comparison later reads false.
    #
    # `raise ValueError(None)` mutated in here still raises `ValidationError`
    # and still passes the bare `pytest.raises` above it. It reports the word
    # "None" to the reader. Equality is what tells the two apart.
    with pytest.raises(ValidationError) as raised:
        adapter.validate_python(Decimal(bad))

    assert messages(raised) == [
        f"Value error, confidence must be finite, got {shown}. A non-finite Decimal "
        "compares false against everything and would poison every "
        "comparison downstream of the artifact carrying it."
    ]


# ── it behaves as a field on a real frozen model ─────────────────────────────


def test_it_works_as_a_model_field_and_stays_frozen() -> None:
    held = Holder(score=Decimal("0.9800"))
    assert held.score == Decimal("0.9800")
    with pytest.raises(ValidationError):
        held.score = Decimal("0.1000")


def test_a_model_field_rejects_a_float_too() -> None:
    # The constraint must travel with the type, not live only in the adapter.
    with pytest.raises(ValidationError):
        Holder(score=0.98)  # type: ignore[arg-type]
