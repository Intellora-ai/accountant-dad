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

import numbers
import operator
from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from accountant_dad.confidence import (
    CONFIDENCE_PLACES,
    MAX,
    MIN,
    UNMEASURED,
    Confidence,
    ConfidenceOrUnmeasured,
    UnmeasuredType,
    records_the_same_measurement,
)
from accountant_dad.engines.input_engine.measurement import ABSENT, AbsentType

adapter: TypeAdapter[Decimal] = TypeAdapter(Confidence)

#: The widened slot Amendment 5 introduced. Held beside `adapter`, never
#: instead of it: several tests below run the SAME input through both and
#: assert the refusals are word for word identical, which is what proves one
#: scale exists rather than two.
either: TypeAdapter[Decimal | UnmeasuredType] = TypeAdapter(ConfidenceOrUnmeasured)


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


# ── the absence of a measurement — Amendment 5 ───────────────────────────────
#
# `UNMEASURED` exists because `reader.read_pdf_text_layer` scores nothing and a
# PDF text layer is the MVP's primary input. The dangerous direction here is
# the SILENT one: a sentinel that reads as falsy, compares equal to zero, or
# converts to a number would let "nobody measured this" become "this measured
# zero" with nothing raised and nothing logged. Every test below attacks that
# direction specifically.


def test_the_sentinel_survives_validation_as_itself_and_is_not_converted() -> None:
    # Identity, not equality. A validator that rebuilt the sentinel would still
    # compare equal under `isinstance`, and this is the assertion that tells a
    # pass-through apart from a reconstruction.
    assert either.validate_python(UNMEASURED) is UNMEASURED


def test_the_widened_slot_enforces_the_identical_scale_as_confidence_itself() -> None:
    """The whole point of delegating to one validator (Law 14, Law 19).

    A SECOND scale is the exact failure `confidence.py:16-24` was written
    after — two schemas built the same day gave the word two incompatible
    types. So this asserts the widened slot's refusals are the SAME STRINGS the
    narrow type produces, not merely that it also refuses something.
    """
    for bad in (0.98, 1, "0.98", None, True, Decimal("1.5"), Decimal("0.00001"), Decimal("NaN")):
        with pytest.raises(ValidationError) as narrow:
            adapter.validate_python(bad)
        with pytest.raises(ValidationError) as widened:
            either.validate_python(bad)
        assert messages(widened) == messages(narrow), (
            f"the widened slot worded its refusal of {bad!r} differently from "
            "`Confidence`, so two scales exist where the repository claims one"
        )


def test_a_real_score_still_passes_through_the_widened_slot_unchanged() -> None:
    # Adding a state must not cost the state that already worked. Verbatim, so
    # Decimal("0.5") is still not padded to "0.5000".
    assert str(either.validate_python(Decimal("0.5"))) == "0.5"
    assert either.validate_python(Decimal("0.3100")) == Decimal("0.3100")


def test_the_sentinel_refuses_to_have_a_truth_value() -> None:
    """THE ONE THAT MATTERS MOST, AND THE REASON THIS IS A CLASS.

    Written `if not provenance.confidence:`, a reading nobody scored and a
    reading a recogniser scored at rock bottom take the same branch — the most
    alarming signal in the artifact silently becoming the most reassuring
    reading of it. Answering `False` would make that bug invisible; raising
    makes it a stack trace.

    Equality on the message, not `pytest.raises` alone: a `raise TypeError()`
    with the explanation deleted still raises, still passes a bare `raises`,
    and sends whoever hits it to go and add a `bool()` call.
    """
    with pytest.raises(TypeError) as raised:
        bool(UNMEASURED)
    assert str(raised.value) == (
        "UNMEASURED has no truth value. Test it with "
        "`isinstance(x, UnmeasuredType)` - `if not confidence:` is exactly "
        "the collapse into a measured zero this type exists to prevent."
    )


def test_every_ordinary_way_of_reaching_for_the_truth_value_also_raises() -> None:
    # `__bool__` is not only called by `bool()`. Each of these is a real line
    # someone writes without thinking, and each must fail loudly rather than
    # take a branch about a measurement that does not exist.
    with pytest.raises(TypeError):
        if UNMEASURED:
            pass
    with pytest.raises(TypeError):
        _ = not UNMEASURED
    with pytest.raises(TypeError):
        _ = UNMEASURED and Decimal("1.0000")


def test_the_sentinel_cannot_grow_an_attribute() -> None:
    # `__slots__ = ()`. A sentinel that can carry state can stop being one —
    # two instances with different attributes are two different sentinels, and
    # `isinstance` would stop being a complete answer. The absent `__dict__` is
    # the STRUCTURAL form of that claim: without an instance dictionary there
    # is no attribute to set, so this cannot be defeated by a subclass that
    # merely catches the error.
    assert UnmeasuredType.__slots__ == ()
    assert not hasattr(UNMEASURED, "__dict__")


def test_the_sentinel_says_what_it_is() -> None:
    # It reaches humans through refusal messages and artifact dumps. "<object
    # at 0x10a…>" in a validation error tells a reader nothing about why the
    # artifact was refused.
    assert repr(UNMEASURED) == "UNMEASURED"


def test_the_sentinel_is_not_a_number_and_will_not_pretend_to_be_one() -> None:
    # Ordering and arithmetic must be IMPOSSIBLE, not merely discouraged. If
    # any of these succeeded, "not measured" would have a magnitude, and a
    # threshold comparison written against it would silently take a branch.
    for combine in (operator.add, operator.sub, operator.mul):
        with pytest.raises(TypeError):
            combine(UNMEASURED, MIN)
        with pytest.raises(TypeError):
            combine(MAX, UNMEASURED)

    # Ordering, which is what a threshold comparison would reach for. Asserted
    # against the stdlib's own numeric ABC rather than by attempting `<`: the
    # typechecker refuses to compile the attempt at all, which is itself the
    # first line of this defence and is worth keeping rather than silencing.
    assert not isinstance(UNMEASURED, numbers.Number)
    assert not isinstance(UNMEASURED, Decimal)

    # And it converts to no numeric type, so `float(...)` cannot launder it
    # into one. Asserted on the protocol rather than on a raised error: a
    # `__float__` added later would make the conversion succeed, and this goes
    # red at the moment it is added rather than at the first wrong entry.
    for numeric_protocol in ("__float__", "__int__", "__index__", "__complex__"):
        assert not hasattr(UNMEASURED, numeric_protocol)


def test_the_sentinel_is_never_equal_to_a_score_at_either_end_of_the_scale() -> None:
    # `==` is not how agreement is decided (see below), but a caller WILL write
    # it, and it must not answer "yes" for the two values a mistake would most
    # plausibly produce.
    assert UNMEASURED != MIN
    assert UNMEASURED != MAX
    assert MIN != UNMEASURED
    assert MAX != UNMEASURED


# ── it is NOT `measurement.ABSENT`, and the two must never cross ─────────────


def test_the_two_sentinels_are_different_types_and_neither_satisfies_the_other() -> None:
    """`measurement.ABSENT` and `UNMEASURED` say different things.

    `ABSENT` — a whole signal CATEGORY was never produced for the document;
    nothing was attempted. `UNMEASURED` — the value WAS read, is real, and
    travels into the artifact; only its score is missing.

    If one class served both, `isinstance` would answer yes to both and the
    distinction both types exist to preserve would be gone — the exact collapse
    `measurement.py:41-59` refuses. This is the test that keeps a future
    "simplification" from merging them.
    """
    assert not isinstance(UNMEASURED, AbsentType)
    assert not isinstance(ABSENT, UnmeasuredType)
    # Neither may become the other by SUBCLASSING either, which is how a
    # well-meant "these are the same thing" refactor would most plausibly
    # arrive — and which the two `isinstance` checks above would not catch,
    # because a subclass satisfies its parent.
    assert not issubclass(UnmeasuredType, AbsentType)
    assert not issubclass(AbsentType, UnmeasuredType)


def test_a_confidence_slot_refuses_the_measurement_stores_sentinel() -> None:
    # Handing `ABSENT` to a confidence slot is a real mistake — both are
    # module-level singletons spelled in capitals — and it must be refused
    # rather than stored as a second kind of nothing.
    with pytest.raises(ValidationError):
        either.validate_python(ABSENT)


# ── what "agreement" means, as a complete truth table ────────────────────────


def test_two_unmeasured_slots_agree() -> None:
    # Neither claims a score, so there is nothing to contradict.
    assert records_the_same_measurement(UNMEASURED, UNMEASURED)


def test_identity_is_not_load_bearing_for_agreement() -> None:
    # A second instance behaves identically. `records_the_same_measurement`
    # asks what each value IS, so a caller who constructs `UnmeasuredType()`
    # instead of importing the singleton does not get a spurious disagreement.
    assert records_the_same_measurement(UnmeasuredType(), UNMEASURED)
    assert records_the_same_measurement(UNMEASURED, UnmeasuredType())


@pytest.mark.parametrize(("left", "right"), [("0.98", "0.9800"), ("0.5", "0.50"), ("1", "1.0000")])
def test_two_measured_slots_agree_as_numbers_not_as_strings(left: str, right: str) -> None:
    # `confidence.py` records what a producer asserted verbatim rather than
    # padding it, so string comparison would make one score disagree with
    # itself. This is the pre-existing rule, unchanged by the amendment.
    assert records_the_same_measurement(Decimal(left), Decimal(right))


def test_two_different_measurements_disagree() -> None:
    assert not records_the_same_measurement(Decimal("0.9800"), Decimal("0.9700"))


@pytest.mark.parametrize("score", ["0.0000", "0.3100", "1.0000"])
def test_a_measurement_and_an_absent_one_disagree_in_both_directions(score: str) -> None:
    """THE NEW REFUSAL, AND THE WHOLE REASON THE PREDICATE EXISTS.

    One side asserts a number the other says was never taken. That is not an
    edge case to be exempted — it is the precise shape of the bug this type was
    added to catch, so it must fail, and it must fail whichever side holds the
    number.

    `0.0000` and `1.0000` are parametrised deliberately: they are the two
    values a "helpful" default would most likely produce, and both are the
    numbers `ENGINE_1_INPUT_ENGINE_RULES.md:625` and Law 24 forbid inventing.
    """
    assert not records_the_same_measurement(Decimal(score), UNMEASURED)
    assert not records_the_same_measurement(UNMEASURED, Decimal(score))


# The sentinel's behaviour as a field on a real frozen model is asserted in
# `tests/unit/test_evidence.py`, against `Provenance` — the PRODUCTION model
# that actually carries it. A local `Holder`-style double here would prove the
# double (§J.6), and `Provenance` exercises the same type through the same
# validator with the artifact's own `frozen`/`extra="forbid"` config.
