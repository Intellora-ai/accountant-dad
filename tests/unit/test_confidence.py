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

import json
import numbers
import operator
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from accountant_dad.confidence import (
    CONFIDENCE_PLACES,
    MAX,
    MIN,
    UNMEASURED,
    Confidence,
    ConfidenceOrUnmeasured,
    MeasurementFailedType,
    MeasurementState,
    NotApplicableType,
    NotMeasuredType,
    UnmeasuredType,
    describe_measurement,
    measurement_state,
    records_the_same_measurement,
)
from accountant_dad.engines.input_engine.measurement import ABSENT, AbsentType

adapter: TypeAdapter[Decimal] = TypeAdapter(Confidence)

#: The widened slot Amendment 5 introduced. Held beside `adapter`, never
#: instead of it: several tests below run the SAME input through both and
#: assert the refusals are word for word identical, which is what proves one
#: scale exists rather than two.
either: TypeAdapter[Decimal | UnmeasuredType] = TypeAdapter(ConfidenceOrUnmeasured)

#: One representative per non-measured state (Amendment 7). Built here, at
#: module scope, because `parametrize` evaluates its arguments at import time —
#: and built rather than imported because only NOT_MEASURED has a shared
#: constant: NOT_APPLICABLE and FAILED deliberately have none, so that no
#: caller can reach for one without stating why it applies.
NOT_APPLICABLE = NotApplicableType(basis="the grid position holds no text to score")
FAILED = MeasurementFailedType(basis="the recogniser could not read this region at all")


class Holder(BaseModel):  # type: ignore[explicit-any]  # pydantic's own signature carries Any
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


def _state_of(value: object) -> MeasurementState:
    """`measurement_state` reached through an `object` parameter.

    Callers below hand it values its signature forbids — that IS the
    assertion, not an accident. Widening here states the wrongness in the
    type system instead of silencing the checker at each call site.
    """
    return measurement_state(cast("ConfidenceOrUnmeasured", value))


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
        "NOT_MEASURED has no truth value. Test it with "
        "`measurement_state(x)` - `if not confidence:` is exactly "
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


def test_no_absent_state_can_grow_an_attribute() -> None:
    # `basis` is the ONLY attribute any of them carries, and it is fixed at
    # construction. A value that can carry arbitrary state can stop being the
    # thing it claims to be. The absent `__dict__` is the STRUCTURAL form of
    # that claim: without an instance dictionary there is no attribute to set,
    # so this cannot be defeated by a subclass that merely catches the error.
    assert UnmeasuredType.__slots__ == ("basis",)
    for kind in (NotMeasuredType, NotApplicableType, MeasurementFailedType):
        assert kind.__slots__ == (), f"{kind.__name__} declares a slot of its own"
    for absence in (UNMEASURED, NOT_APPLICABLE, FAILED):
        assert not hasattr(absence, "__dict__")
        # Runtime, not the typechecker: `__setattr__` accepts any name as far
        # as mypy is concerned, so this refusal has to be proven by running it.
        with pytest.raises(AttributeError):
            absence.invented = "a second fact"


def test_the_basis_cannot_be_rewritten_after_the_artifact_carrying_it_exists() -> None:
    # Immutability is not decoration here. The basis is the artifact's own
    # answer to "why is there no score?", and a fact that can be edited in
    # place is a fact that can be rewritten after somebody audited it.
    with pytest.raises(AttributeError, match="is immutable"):
        UNMEASURED.basis = "something more reassuring"


@pytest.mark.parametrize(
    ("absence", "expected"),
    [(UNMEASURED, "NOT_MEASURED"), (NOT_APPLICABLE, "NOT_APPLICABLE"), (FAILED, "FAILED")],
)
def test_each_absent_state_says_which_one_it_is(absence: UnmeasuredType, expected: str) -> None:
    # They reach humans through refusal messages and artifact dumps. "<object
    # at 0x10a…>" in a validation error tells a reader nothing about why the
    # artifact was refused — and a repr shared by all three would tell them
    # something WRONG, which is worse.
    assert repr(absence) == expected


def test_the_three_absences_never_share_a_repr() -> None:
    # The disconfirming form of the test above: a single `__repr__` on the base
    # returning one word would satisfy "says what it is" for whichever state
    # happened to be parametrised first.
    absences = (UNMEASURED, NOT_APPLICABLE, FAILED)
    reprs = {repr(absence) for absence in absences}
    assert len(reprs) == len(absences), f"two absent states print the same word: {sorted(reprs)}"


@pytest.mark.parametrize("absence", [UNMEASURED, NOT_APPLICABLE, FAILED])
def test_no_absent_state_is_a_number_or_will_pretend_to_be_one(absence: UnmeasuredType) -> None:
    # Ordering and arithmetic must be IMPOSSIBLE, not merely discouraged. If
    # any of these succeeded, an absence would have a magnitude, and a
    # threshold comparison written against it would silently take a branch.
    for combine in (operator.add, operator.sub, operator.mul):
        with pytest.raises(TypeError):
            combine(absence, MIN)
        with pytest.raises(TypeError):
            combine(MAX, absence)

    # Ordering, which is what a threshold comparison reaches for FIRST. Every
    # one of the four raises, and the message names the state rather than
    # leaving Python's generic "not supported between instances of" — a reader
    # who wrote `if confidence < floor:` needs to be told there is no floor to
    # be below, not that two types are unrelated.
    for compare in (operator.lt, operator.le, operator.gt, operator.ge):
        with pytest.raises(TypeError, match="has no magnitude"):
            compare(absence, MIN)

    # And it is not a number by the stdlib's own reckoning either.
    assert not isinstance(absence, numbers.Number)

    # And it converts to no numeric type, so `float(...)` cannot launder it
    # into one. Asserted on the protocol rather than on a raised error: a
    # `__float__` added later would make the conversion succeed, and this goes
    # red at the moment it is added rather than at the first wrong entry.
    for numeric_protocol in ("__float__", "__int__", "__index__", "__complex__"):
        assert not hasattr(absence, numeric_protocol)


def test_no_absent_state_is_a_decimal_by_class_and_not_merely_by_instance() -> None:
    # The class relationship, not one object's. `isinstance` on the singleton
    # would still hold if some OTHER instance were built as a `Decimal`
    # subclass — which is the one shape Amendment 6 named as the wrong answer,
    # because it would satisfy every existing annotation and bring the
    # collapse into zero back wearing the type system's approval.
    for kind in (UnmeasuredType, NotMeasuredType, NotApplicableType, MeasurementFailedType):
        assert not issubclass(kind, Decimal), f"{kind.__name__} is a Decimal"
        assert not issubclass(kind, numbers.Number), f"{kind.__name__} is a Number"


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
    # asks what STATE each value is in, so a caller who constructs its own
    # `NotMeasuredType` instead of importing the constant does not get a
    # spurious disagreement.
    mine = NotMeasuredType(basis="a reason of my own")
    assert records_the_same_measurement(mine, UNMEASURED)
    assert records_the_same_measurement(UNMEASURED, mine)
    assert mine.basis != UNMEASURED.basis, "or this proves nothing about the basis"


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


# ── four states: the complete pairing matrix — Amendment 7 ───────────────────
#
# The tests above cover the two states Amendment 5 had. These prove the rule
# over ALL FOUR, exhaustively, because "we extended it" is a claim and a full
# matrix is the only evidence for it. Every pair is generated rather than
# listed, so a fifth state added later WIDENS this test automatically instead
# of leaving a hole nobody notices.

#: One representative per state, and a second measured value so
#: measured-vs-measured is not tested only against itself.
A_SCORE = Decimal("0.3100")
THE_SAME_SCORE_PADDED = Decimal("0.31")
ANOTHER_SCORE = Decimal("0.9800")

#: Every distinct state, each with the value that represents it here.
BY_STATE: dict[MeasurementState, Decimal | UnmeasuredType] = {
    MeasurementState.MEASURED: A_SCORE,
    MeasurementState.NOT_MEASURED: UNMEASURED,
    MeasurementState.NOT_APPLICABLE: NOT_APPLICABLE,
    MeasurementState.FAILED: FAILED,
}


def test_the_matrix_covers_every_state_the_enum_declares() -> None:
    """The matrix below is only exhaustive if this is true.

    A fifth state added to `MeasurementState` and not added here would leave
    every pairing test silently passing over a state nobody checked — the exact
    shape of the hole Amendment 5 left, one level up. This turns that into a
    red test at the moment the member is added.
    """
    assert set(BY_STATE) == set(MeasurementState)


@pytest.mark.parametrize("state", list(MeasurementState))
def test_each_representative_really_is_in_the_state_it_stands_for(state: MeasurementState) -> None:
    # Guards the guard. If a representative were mislabelled, the matrix would
    # test one state twice and another never.
    assert measurement_state(BY_STATE[state]) is state


@pytest.mark.parametrize("right_state", list(MeasurementState))
@pytest.mark.parametrize("left_state", list(MeasurementState))
def test_every_pairing_of_states_agrees_exactly_when_the_states_match(
    left_state: MeasurementState, right_state: MeasurementState
) -> None:
    """THE COMPLETE TRUTH TABLE — all sixteen pairings, generated.

    The rule, stated once: two slots agree when they are in the SAME state,
    and measured slots additionally need equal numbers. Everything else
    disagrees, including every pair of two DIFFERENT absences — one side
    saying "a real value is carried with nothing behind it" and the other
    saying "there is nothing here at all" is a genuine contradiction about
    whether the document was read at that spot.
    """
    left, right = BY_STATE[left_state], BY_STATE[right_state]
    expected = left_state is right_state
    assert records_the_same_measurement(left, right) is expected
    # Symmetry, asserted rather than assumed. An implementation that tested
    # only `isinstance(left, ...)` would pass one direction and fail the other.
    assert records_the_same_measurement(right, left) is expected


def test_two_measured_slots_in_the_same_state_still_have_to_carry_the_same_number() -> None:
    # The matrix says "same state agrees"; for MEASURED that is necessary and
    # NOT sufficient. Without this, an implementation comparing only states
    # would pass every cell above while calling 0.31 and 0.98 the same reading.
    assert records_the_same_measurement(A_SCORE, THE_SAME_SCORE_PADDED)
    assert not records_the_same_measurement(A_SCORE, ANOTHER_SCORE)


@pytest.mark.parametrize("state", list(MeasurementState))
def test_the_widened_slot_accepts_every_state_the_enum_declares(state: MeasurementState) -> None:
    # The type may hold four states and the SLOT may hold two would be a type
    # nobody can use. Identity, so a validator that rebuilt the value — losing
    # its basis on the way — goes red.
    value = BY_STATE[state]
    assert either.validate_python(value) is value


# ── the base is abstract, and every absence must state its reason ────────────


def test_the_base_state_cannot_be_constructed_and_says_why() -> None:
    """ "A measurement is absent and I decline to say which" is exactly the
    *unknown but looks valid* shape the four states exist to remove.

    Equality on the message: a bare `raise TypeError()` still raises, still
    passes `pytest.raises`, and sends whoever hits it looking for a bug in
    their arguments rather than for the three concrete classes.
    """
    with pytest.raises(TypeError) as raised:
        UnmeasuredType("some absence or other")
    assert str(raised.value) == (
        "UnmeasuredType is abstract: it says a measurement is absent "
        "without saying which absence. Construct NotMeasuredType, "
        "NotApplicableType or MeasurementFailedType - naming which of "
        "the three is the whole reason the base exists."
    )


@pytest.mark.parametrize("kind", [NotMeasuredType, NotApplicableType, MeasurementFailedType])
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_no_absence_may_be_constructed_without_a_stated_reason(
    kind: type[UnmeasuredType], blank: str
) -> None:
    # A padded blank is a blank — the same rule `evidence._meaningful_text`
    # applies to a source id, applied to the reason a measurement is missing.
    # `ENGINE_1_INPUT_ENGINE_RULES.md:626`: a bare score cannot become a good
    # question downstream, and a bare absence is worse than a bare score.
    with pytest.raises(ValueError, match="non-blank basis"):
        kind(blank)


@pytest.mark.parametrize("state", list(MeasurementState))
def test_every_state_describes_itself_in_words_a_reader_can_act_on(
    state: MeasurementState,
) -> None:
    # `describe_measurement` is what reaches a human inside a refusal. It must
    # name the state, and for an absence it must carry the reason too — "not
    # measured" with no reason sends the reader back to the source to find out
    # why, which is the entire cost the basis exists to remove.
    value = BY_STATE[state]
    described = describe_measurement(value)
    assert described.startswith(state.value)
    if isinstance(value, UnmeasuredType):
        assert value.basis in described


# ── it has to survive being written down ─────────────────────────────────────
#
# FOUND BY A RED TEST, NOT BY READING. `model_dump_json()` on a model holding a
# stated absence raised `PydanticSerializationError: Unable to serialize unknown
# type`. The defect PRE-DATES the four states — Amendment 6's single sentinel
# had it too, and it stayed invisible only because no artifact carrying one had
# ever been dumped to JSON. An artifact that can be built and not written down
# cannot be audited (Law 43), and this artifact is the one an auditor reads.


# Not a second BaseModel. `Provenance` — the PRODUCTION model that carries
# this type — is asserted in `tests/unit/test_evidence.py`; a local double
# here would prove the double (§J.6). A TypeAdapter exercises the type's own
# serialisation directly, which is the thing that raised.
DUMPED: TypeAdapter[ConfidenceOrUnmeasured] = TypeAdapter(ConfidenceOrUnmeasured)


@pytest.mark.parametrize("state", list(MeasurementState))
def test_every_state_can_be_written_to_json(state: MeasurementState) -> None:
    # The regression, for all four. A state added later that forgot a
    # serialisation rule would raise here rather than at the first audit.
    assert DUMPED.dump_json(BY_STATE[state])


@pytest.mark.parametrize("state", [s for s in MeasurementState if s is not s.MEASURED])
def test_an_absence_is_written_as_a_named_state_and_never_as_a_number(
    state: MeasurementState,
) -> None:
    """The two convenient shapes are the two wrong ones.

    A number would put the fabricated score back past every guard in the
    module, at the one boundary with nothing left to check it. `null` would
    land as the same token four other absent things in this pipeline already
    use, and the far side could not tell which.
    """
    value = BY_STATE[state]
    assert isinstance(value, UnmeasuredType)
    written = json.loads(DUMPED.dump_json(value))

    assert written == {"measurement_state": state.value, "basis": value.basis}
    assert not isinstance(written, int | float | str), (
        "an absence written as a scalar is one coercion away from being read back as a score"
    )
    assert written is not None


def test_a_measured_score_is_still_written_as_its_own_digits() -> None:
    # Adding a state must not cost the state that already worked, and the
    # digits must be the producer's own — verbatim, not padded to four places.
    written = json.loads(DUMPED.dump_json(Decimal("0.31")))
    assert written == "0.31"


@pytest.mark.parametrize("state", list(MeasurementState))
def test_a_python_mode_dump_still_hands_back_the_value_itself(state: MeasurementState) -> None:
    # `when_used="json"` is load-bearing. The ablation comparison walks a
    # `model_dump()` and needs the state OBJECT to compare; a serialiser that
    # fired in Python mode too would turn every artifact comparison into a
    # comparison of dictionaries that happen to look alike.
    value = BY_STATE[state]
    assert DUMPED.dump_python(value) is value


@pytest.mark.parametrize("impostor", [1.0, 0, True, "0.98", None, ABSENT])
def test_nothing_that_merely_looks_like_a_score_is_reported_as_measured(
    impostor: object,
) -> None:
    """The inspector is hostile, not permissive, and this is why.

    `float(True)` is `1.0`; `1.0` is both the forbidden default
    (`ENGINE_1_INPUT_ENGINE_RULES.md:625`) and the top of the scale. A
    classifier that answered MEASURED for any of these would launder a
    fabricated score into every downstream branch that asks which state a
    value is in (Law 24). `ABSENT` is in the list because it is the mistake a
    reader is most likely to make — both are module-level capitals meaning
    "nothing here" — and it means a different thing.
    """
    with pytest.raises(TypeError, match="neither a Decimal measurement nor a stated absence"):
        _state_of(impostor)


# The sentinel's behaviour as a field on a real frozen model is asserted in
# `tests/unit/test_evidence.py`, against `Provenance` — the PRODUCTION model
# that actually carries it. A local `Holder`-style double here would prove the
# double (§J.6), and `Provenance` exercises the same type through the same
# validator with the artifact's own `frozen`/`extra="forbid"` config.
