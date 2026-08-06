"""`config` red-team — an adversarial second pass over the loader that decides
which numbers Engine 1 is allowed to have at all.

`tests/unit/test_input_engine_config.py` already proves the module's headline
promise: nothing is returned when a parameter is missing. This file attacks
what that one does not — the ways a threshold could end up DIFFERENT from the
number the operator wrote, without anybody being told.

────────────────────────────────────────────────────────────────────────────
ONE DEFECT FOUND. ITS TEST IS LEFT RED ON PURPOSE. READ THIS FIRST.
────────────────────────────────────────────────────────────────────────────

    test_a_weight_named_twice_is_refused_rather_than_silently_taking_the_last

`ENGINE_1_CONFIDENCE_DOCUMENT_SCORE_WEIGHTS='{"gstin": 0.4000, "gstin": 1.0000}'`
loads successfully today, with `gstin` weighted `1.0000`. The operator wrote
two weights for one field; one of them was silently discarded, the surviving
set summed to `1.0000` so the arithmetic check passed, and Engine 1 started
with a weight nobody chose between. Nothing was logged, nothing was raised.

Measured, not assumed:

    json.loads('{"gstin": 0.4000, "gstin": 1.0000}', parse_float=Decimal)
        -> {'gstin': Decimal('1.0000')}          last key wins, silently

That the project already regards this as a defect is not an opinion of mine —
`measurement._no_duplicate_names`, in the sibling module, refuses exactly this
shape with exactly this reasoning:

    "Two values for one name leaves no authority for which one a later
     calibration run should read."

A weight has strictly more authority than a measurement: it decides a document
score, which decides whether a document reaches a human. `config` has no such
check. The fix belongs in `src/`, which this file does not touch, so the test
below states the correct behaviour and fails.

Confidence that this is a defect rather than a design choice: high, but not
absolute — JSON's own grammar leaves duplicate keys implementation-defined, so
"last wins" is not a violation of JSON. It IS a violation of the rule this
repository states about itself.

────────────────────────────────────────────────────────────────────────────
WHAT ELSE WAS ATTACKED, AND HELD
────────────────────────────────────────────────────────────────────────────

Absence, in every shape it comes in — key gone, empty string, whitespace only,
key present but lower-cased. All sixteen parameters, all four shapes, every one
refused, every one naming itself.

Wrongness, in every shape — a value in another parameter's units, a NaN weight,
a negative weight inside a set that still sums to one, five decimal places,
exponent notation past the agreed scale, a count written with a decimal point.
All refused.

Fabrication by arithmetic — the one that would be invisible. A weight typed
`0.1` must arrive as `Decimal("0.1")`, never as the `Decimal` a binary float
decays into. It does.

Several problems at once — sixteen missing, sixteen invalid, and a mixed set,
each reported in one raise, in the catalogue's order, one to a line, with the
whole message pinned character for character.

REAL DEPENDENCIES, NO MOCKS (`CLAUDE.md` §J.6). Every attack calls the real
loader with a real `Mapping[str, str]` — the shape `os.environ` already has.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping, MutableMapping
from decimal import Decimal
from types import MappingProxyType
from typing import cast

import pytest

from accountant_dad.confidence import CONFIDENCE_PLACES, MAX, MIN
from accountant_dad.engines.input_engine import config as c

# `MIN`, `MAX` and `CONFIDENCE_PLACES` come from `accountant_dad.confidence`
# itself, not through `config`. `config` imports them for its own use and does
# not re-export them (`no_implicit_reexport` under `mypy --strict`), and going
# to the real source is the honest form anyway — `config`'s docstring says the
# bounds are imported "not restated, so this scale and the stored Confidence
# scale can never silently disagree." Reading them from a second place here
# would be the drift that sentence exists to prevent.

#: `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md` §Sign-off: "Parameters awaiting a
#: value: 16." Named, because `assert len(...) == 16` is a magic value and
#: because the number is a claim about the document, not about this file.
EXPECTED_PARAMETER_COUNT = 16

#: Exactly one candidate below is legal for any given parameter — see
#: `test_each_parameter_accepts_exactly_one_of_the_four_value_shapes`.
ONE_LEGAL_SHAPE = 1

TWO_PROBLEMS = 2

#: A legal, arbitrary wall-clock budget, in milliseconds, used only to give the
#: count-shaped attacks below a value with more than one digit in it. Not a
#: recommendation: `processing_budget_ms` is UNSET and stays UNSET until stage 4.
A_BUDGET_IN_MS = 30000

#: One legal raw string for each SHAPE of parameter in the catalogue, and
#: nothing else. There is deliberately no name-to-value table here: the table
#: would be a second source of truth that could drift from `PARAMETER_CATALOG`,
#: and `a_legal_value` below picks from these four using the parameter's OWN
#: parser, so a seventeenth parameter of an existing shape needs no edit here.
#:
#: None of these four is claimed to be a correct operating point. Stage 4 of
#: `ENGINE_1_CONFIDENCE_PARAMETERS.md` — the only route by which a real value
#: may be chosen — is blocked on P1. They are legal, and that is all.
CANDIDATE_SHAPES: tuple[str, ...] = (
    "0.5000",
    "3",
    "min",
    '{"gstin": 1.0000}',
)

#: What `CANDIDATE_SHAPES[1]` means once parsed — named so the count assertions
#: below never compare against a bare literal.
LEGAL_COUNT = 3

#: A value written in no parameter's units at all.
NONSENSE = "@@@"


def a_legal_value(spec: c.ParameterSpec) -> str:
    """The first of `CANDIDATE_SHAPES` this parameter's own parser accepts.

    The real parser decides, so this fixture cannot drift from the module it
    exercises, and it cannot quietly supply a value the loader would reject.
    """
    for candidate in CANDIDATE_SHAPES:
        try:
            spec.parse(candidate)
        except c._ParameterValueError:
            continue
        return candidate
    raise AssertionError(f"no candidate shape is legal for {spec.name!r}")


def a_valid_env() -> dict[str, str]:
    """All sixteen parameters, each set to a value its own parser accepts."""
    return {spec.env_var: a_legal_value(spec) for spec in c.PARAMETER_CATALOG}


def env_var(name: str) -> str:
    """The environment variable a parameter name resolves to, read from the
    real catalogue rather than rebuilt from `_ENV_PREFIX` a second time.
    """
    return c._env_var(name)


def problem_lines(message: str) -> list[str]:
    """The individual problems in a `ConfigurationError`, in the order raised."""
    return [line for line in message.splitlines() if line.startswith("  - ")]


def expected_missing_line(spec: c.ParameterSpec) -> str:
    """The exact line the loader must emit for an absent parameter.

    Assembled from the spec's own fields, so this pins the SENTENCE, never the
    prose — a reworded `purpose` does not break it, a dropped `Unit:` does.
    """
    return (
        f"  - {spec.name} is not set. Set the environment variable "
        f"{spec.env_var} — {spec.purpose}. Unit: {spec.unit}. "
        f"Valid range: {spec.range_text}."
    )


def expected_invalid_line(spec: c.ParameterSpec, problem: str) -> str:
    """The exact line the loader must emit for a present-but-unusable value."""
    return (
        f"  - {spec.name} ({spec.env_var}) is invalid: {problem} "
        f"{spec.purpose}. Unit: {spec.unit}. Valid range: {spec.range_text}."
    )


CATALOG_IDS = [spec.name for spec in c.PARAMETER_CATALOG]


# ══════════════════════════════════════════════════════════════════════════
# DEFECT — LEFT RED. See the module docstring.
# ══════════════════════════════════════════════════════════════════════════


def test_a_weight_named_twice_is_refused_rather_than_silently_taking_the_last() -> None:
    """RED BY DESIGN — a real defect in `src/`, not a broken test.

    Two weights for `gstin`. JSON's `last key wins` discards `0.4000` before
    `_parse_weights` ever sees the object, the survivors sum to `1.0000`, and
    the loader returns a fully valid `ConfidenceParameters` carrying a weight
    the operator never agreed to use alone.

    `measurement._no_duplicate_names` refuses the identical shape one module
    away, for the identical reason. Fixing this belongs in `src/`; this file
    only traps it.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 0.4000, "gstin": 1.0000}'

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert c.DOCUMENT_SCORE_WEIGHTS in message
    assert "gstin" in message, "the field named twice must be named in the refusal"


# ══════════════════════════════════════════════════════════════════════════
# THE DUPLICATE REFUSAL'S OWN WORDS — membership is not the claim
#
# The test above asks only whether `gstin` appears somewhere in the message.
# That is satisfied by a refusal whose entire explanation has been deleted,
# case-flipped, or replaced with the literal `None` — all of which still raise
# `ConfigurationError`, and none of which tell the operator anything.
#
# The explanation is the only thing the operator gets. `_parse_weights` cannot
# say WHICH weight was meant — that is the whole reason it refuses — so the
# message has to justify refusing rather than picking, and specifically has to
# say that the arithmetic check cannot catch this. An operator who is told only
# "gstin" will assume the sum check would have caught a real problem, and
# reach for the shortest edit that makes the error go away.
#
# `_object_pairs_without_duplicates` builds that message out of four separate
# pieces — an f-string and three plain literals — and mutation testing rewrites
# each independently. Pinning the assembled line is the only assertion that
# sees all four (§J.2).
# ══════════════════════════════════════════════════════════════════════════


def spec_for(name: str) -> c.ParameterSpec:
    """The catalogue entry for a parameter, read from the real catalogue so
    `purpose`, `unit` and `range_text` are never restated here.
    """
    for spec in c.PARAMETER_CATALOG:
        if spec.name == name:
            return spec
    raise AssertionError(f"{name!r} is not in PARAMETER_CATALOG")


def expected_duplicate_problem(names: str, raw: str) -> str:
    """The exact sentence a duplicated weight key must produce, after
    `_parse_weights` has appended the raw input it came from.

    Written out character for character on purpose: this IS the pin. `names`
    is a parameter rather than a literal so the separator between two
    duplicated field names is pinned too — a single duplicated name joins to
    itself no matter what separator `str.join` was given, so only a case with
    two DISTINCT duplicated names can observe that argument at all.
    """
    return (
        f"names the same field twice: {names}. Two weights "
        "for one field leaves no authority for which one the document "
        "score should use, and the surviving pair can still sum to 1.0000, "
        f"so the arithmetic check cannot catch it. ({raw!r})"
    )


def test_the_duplicate_weight_refusal_is_pinned_character_for_character() -> None:
    """One field written twice. Pins the whole problem line — the refusal, its
    justification, the raw input echoed back, and the catalogue wording the
    loader wraps around every invalid value.
    """
    raw = '{"gstin": 0.4000, "gstin": 1.0000}'
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = raw

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert line == expected_invalid_line(
        spec_for(c.DOCUMENT_SCORE_WEIGHTS), expected_duplicate_problem("gstin", raw)
    )


def test_two_fields_named_twice_are_listed_sorted_and_comma_separated() -> None:
    """Two DISTINCT duplicated names, written `hsn` first so the expected
    order is not the order they appear in.

    This is the only shape that can see the join separator and the `sorted()`
    at once: with one duplicated name both are invisible. `hsn` before `gstin`
    in the input, `gstin, hsn` in the message.
    """
    raw = '{"hsn": 0.2000, "hsn": 0.3000, "gstin": 0.4000, "gstin": 0.5000}'
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = raw

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert line == expected_invalid_line(
        spec_for(c.DOCUMENT_SCORE_WEIGHTS), expected_duplicate_problem("gstin, hsn", raw)
    )


# ══════════════════════════════════════════════════════════════════════════
# NO DEFAULT EXISTS ANYWHERE — the structural half of the claim
#
# `test_input_engine_config.py` proves the loader returns nothing when a
# parameter is absent. That is the BEHAVIOURAL half. A default could still be
# introduced somewhere the loader never reaches — a dataclass field default is
# invisible to `load_confidence_parameters({})`, because it raises before any
# construction happens. These tests close that route.
# ══════════════════════════════════════════════════════════════════════════


def test_no_field_of_confidence_parameters_carries_a_default() -> None:
    """`CLAUDE.md` §P: "No hardcoded defaults. No silently assumed values."

    A default here would never show up in any loader test: the loader raises
    on the missing key long before `ConfidenceParameters(...)` is called. It
    WOULD show up the first time anything constructs the object directly, at
    which point a threshold nobody chose is live and looks deliberate.
    """
    defaulted = [
        field.name
        for field in dataclasses.fields(c.ConfidenceParameters)
        if field.default is not dataclasses.MISSING
        or field.default_factory is not dataclasses.MISSING
    ]

    assert defaulted == [], (
        f"{defaulted} carry a default. Every value in "
        "docs/ENGINE_1_CONFIDENCE_PARAMETERS.md is UNSET and awaiting the "
        "user's sign-off; a default is that decision taken without them."
    )


def test_no_field_of_parameter_spec_carries_a_default() -> None:
    """The catalogue entry itself must be fully stated too. A `ParameterSpec`
    with a defaulted `range_text` or `unit` would let a parameter enter the
    table without saying what it means — Law 52's exact failure, one level up
    from the value.
    """
    defaulted = [
        field.name
        for field in dataclasses.fields(c.ParameterSpec)
        if field.default is not dataclasses.MISSING
        or field.default_factory is not dataclasses.MISSING
    ]

    assert defaulted == []


def test_every_catalog_name_is_a_field_of_confidence_parameters_in_the_same_order() -> None:
    """A name in the catalogue that is not a field is a parameter validated and
    then thrown away; a field not in the catalogue is a parameter nobody
    checks. Either way the two would disagree about what "the sixteen" are, and
    no existing test compares them.
    """
    fields = [field.name for field in dataclasses.fields(c.ConfidenceParameters)]
    names = [spec.name for spec in c.PARAMETER_CATALOG]

    assert names == fields
    assert len(fields) == EXPECTED_PARAMETER_COUNT


def test_every_environment_variable_is_exactly_the_prefix_plus_the_upper_cased_name() -> None:
    """`config`: "One rule, so 'where do I set X' always has the same answer
    shape." The existing suite checks only that each variable STARTS with the
    prefix — `ENGINE_1_CONFIDENCE_ANYTHING_AT_ALL` passes that. This pins the
    whole derivation, so a variable that does not follow the one rule is a
    failure rather than a surprise at deployment time.
    """
    wrong = [
        (spec.name, spec.env_var)
        for spec in c.PARAMETER_CATALOG
        if spec.env_var != f"ENGINE_1_CONFIDENCE_{spec.name.upper()}"
    ]

    assert wrong == []


def test_no_two_parameters_share_a_name_or_an_environment_variable() -> None:
    """Two specs sharing one variable is the quietest failure in the file: both
    parameters would read the same number, both would validate, and the second
    one's configured value would be ignored with no error anywhere.
    """
    names = [spec.name for spec in c.PARAMETER_CATALOG]
    variables = [spec.env_var for spec in c.PARAMETER_CATALOG]

    assert len(set(names)) == len(names)
    assert len(set(variables)) == len(variables)


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=CATALOG_IDS)
def test_each_parameter_accepts_exactly_one_of_the_four_value_shapes(
    spec: c.ParameterSpec,
) -> None:
    """A probability, a count, a named rule and a weight map are four different
    kinds of thing. A parser that accepted a value written in another
    parameter's units would let `worst_k=0.5000` or `ocr_region_accept=3`
    through — a number in the wrong units is a number nobody chose, and it
    would pass every "is it set?" test in the suite.
    """
    accepted = [candidate for candidate in CANDIDATE_SHAPES if _is_accepted(spec, candidate)]

    assert len(accepted) == ONE_LEGAL_SHAPE, (
        f"{spec.name} accepts {accepted}; a parameter must accept values in "
        "its own units and no others."
    )


def _is_accepted(spec: c.ParameterSpec, raw: str) -> bool:
    try:
        spec.parse(raw)
    except c._ParameterValueError:
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════
# EVERY WAY A VALUE CAN BE MISSING
# ══════════════════════════════════════════════════════════════════════════


def test_every_parameter_absent_is_reported_once_each_on_its_own_line() -> None:
    """Nothing set at all. Sixteen problems, sixteen lines, each naming its own
    parameter with its own purpose, unit and range — pinned line by line rather
    than by membership, so a template that lost `Unit:` or merged two problems
    onto one line turns red.
    """
    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters({})

    message = str(raised.value)
    assert message.startswith(
        f"Engine 1 confidence configuration has {EXPECTED_PARAMETER_COUNT} problem(s):"
    )
    assert problem_lines(message) == [expected_missing_line(spec) for spec in c.PARAMETER_CATALOG]


def test_environment_keys_in_the_wrong_case_are_not_found() -> None:
    """All sixteen present, all sixteen lower-cased. `os.environ` is
    case-sensitive on every platform this runs on, so a lower-cased key is an
    unset parameter — and must read as unset, not as an unlucky lookup that
    quietly resolves to something.
    """
    environment = {spec.env_var.lower(): a_legal_value(spec) for spec in c.PARAMETER_CATALOG}

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    assert len(problem_lines(str(raised.value))) == EXPECTED_PARAMETER_COUNT


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=CATALOG_IDS)
def test_each_parameter_set_to_an_empty_string_is_refused_as_invalid_not_missing(
    spec: c.ParameterSpec,
) -> None:
    """Present-but-empty is a different fact from absent, and the operator has
    to be told which one they did. The existing suite checks three parameters;
    this checks all sixteen, and pins that the message uses the INVALID
    wording rather than the missing wording.
    """
    environment = a_valid_env()
    environment[spec.env_var] = ""

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert line.startswith(f"  - {spec.name} ({spec.env_var}) is invalid: ")
    assert "is not set" not in line


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=CATALOG_IDS)
def test_each_parameter_set_to_whitespace_only_is_refused(spec: c.ParameterSpec) -> None:
    """The shape a shell produces from an unset substitution or a blank line in
    an env file. `Decimal` and `int` both strip surrounding whitespace, so a
    value that is NOTHING BUT whitespace is the case where stripping could
    plausibly have left something usable behind. It leaves nothing, and all
    sixteen say so.
    """
    environment = a_valid_env()
    environment[spec.env_var] = "   \t  "

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert line.startswith(f"  - {spec.name} ({spec.env_var}) is invalid: ")


def test_loading_from_a_cleared_process_environment_refuses_all_sixteen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real startup adapter, attacked rather than confirmed. The existing
    suite only shows it succeeds when everything is set — which a function that
    ignored `os.environ` entirely and returned a hardcoded object would also
    pass. With the sixteen variables deleted it must refuse, naming all of them.
    """
    for spec in c.PARAMETER_CATALOG:
        monkeypatch.delenv(spec.env_var, raising=False)

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters_from_environment()

    assert len(problem_lines(str(raised.value))) == EXPECTED_PARAMETER_COUNT


# ══════════════════════════════════════════════════════════════════════════
# EVERY WAY A VALUE CAN BE WRONG
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=CATALOG_IDS)
def test_each_parameter_given_a_value_in_no_units_at_all_is_refused_by_name(
    spec: c.ParameterSpec,
) -> None:
    """`@@@` is not a probability, a count, a rule name or a JSON object. Every
    one of the sixteen must say so, and must say WHICH parameter said so —
    a refusal that does not name the parameter makes the operator guess, and
    guessing is how a wrong number gets set.
    """
    environment = a_valid_env()
    environment[spec.env_var] = NONSENSE

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert line.startswith(f"  - {spec.name} ({spec.env_var}) is invalid: ")
    assert spec.range_text in line, "the operator must be told what would be acceptable"


def test_a_nan_weight_is_refused_naming_the_field_and_the_raw_input() -> None:
    """`json.loads` accepts the bare constant `NaN` and routes it around
    `parse_float`, so it arrives as a `float` that is not a number. The
    existing suite covers `Infinity`; `NaN` is the other half of the same hole,
    and it is the more dangerous one — every comparison against NaN is false,
    so a NaN weight would make a document score silently unorderable.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": NaN, "sentinel_field": 1}'

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert "gstin" in message
    assert "finite" in message
    assert "sentinel_field" in message, "the raw input must be echoed, not just the key"


def test_a_negative_weight_is_refused_even_though_the_set_sums_to_one() -> None:
    """The sum check alone would pass this: `-0.5000 + 1.5000 == 1.0000`. Both
    weights are outside `[0.0000, 1.0000]`, and a negative weight would make a
    field's confidence LOWER the document score by rising. The per-weight range
    check has to run before the sum, and this proves it does.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": -0.5000, "hsn": 1.5000}'

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert "gstin" in message
    assert f"must lie in [{MIN}, {MAX}]" in message


def test_a_weight_above_one_is_refused_even_though_the_set_sums_to_one() -> None:
    """The mirror of the test above, entered from the other end so a mutation
    that checks only one bound cannot survive both.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"hsn": 1.5000, "gstin": -0.5000}'

    with pytest.raises(c.ConfigurationError, match=re.escape(f"[{MIN}, {MAX}]")):
        c.load_confidence_parameters(environment)


def test_a_weight_carrying_five_decimal_places_is_refused() -> None:
    """Weights are `P` values and are held to the same agreed scale as every
    other probability — `1.00000` sums to exactly one and is still refused,
    because a fifth place is precision the scale does not have. No existing
    test applies the decimal-place rule to a weight rather than to a threshold.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 1.00000}'

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert "gstin" in message
    assert str(CONFIDENCE_PLACES) in message


def test_a_zero_weight_is_legal_and_arrives_as_zero() -> None:
    """`0.0000` is inside `[MIN, MAX]`, so a field weighted zero is a legal
    configuration — the operator saying "count this field, at no weight". It
    must survive as a real zero rather than being dropped from the map, which
    would silently change how many fields the rule believes it has.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 0.0000, "hsn": 1.0000}'

    parameters = c.load_confidence_parameters(environment)

    assert dict(parameters.document_score_weights) == {
        "gstin": Decimal("0.0000"),
        "hsn": Decimal("1.0000"),
    }


def test_a_weight_never_passes_through_binary_floating_point() -> None:
    """`config`: "passing `Decimal` there means a weight typed by an operator
    never touches binary floating point on its way in."

    That claim is invisible to every existing test, because
    `Decimal("0.1") == Decimal(0.1)` is False but
    `float(Decimal("0.1")) == float(Decimal(0.1))` is True — so any assertion
    written in floats would pass either way. Compared against the `Decimal` a
    float decays into, the difference is exact and enormous.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 0.1, "hsn": 0.9}'

    parameters = c.load_confidence_parameters(environment)

    weight = parameters.document_score_weights["gstin"]
    assert weight == Decimal("0.1")
    assert str(weight) == "0.1"
    # `Decimal.from_float` rather than `Decimal(0.1)`: identical value, and it
    # says out loud that the comparison target is deliberately the number a
    # BINARY FLOAT decays into, not a typo for `Decimal("0.1")`. Ruff refuses
    # the bare form (RUF032) precisely because that confusion is usually a bug;
    # here it is the whole assertion.
    assert weight != Decimal.from_float(0.1), (
        "the weight went through a binary float first: Decimal(0.1) is "
        f"{Decimal.from_float(0.1)}, which is not the number the operator wrote."
    )


def test_a_probability_never_passes_through_binary_floating_point() -> None:
    """The same claim for `_parse_probability`, which builds `Decimal(raw)`
    straight from the string. `Decimal(0.1)` carries 55 significant digits and
    would be refused by the decimal-place check — so a loader that went through
    `float` first would not merely be imprecise here, it would reject a legal
    value. Neither half of that is visible without comparing against
    `Decimal(0.1)` itself.
    """
    environment = a_valid_env()
    environment[env_var(c.OCR_REGION_ACCEPT)] = "0.1000"

    parameters = c.load_confidence_parameters(environment)

    assert parameters.ocr_region_accept == Decimal("0.1000")
    assert str(parameters.ocr_region_accept) == "0.1000"
    assert parameters.ocr_region_accept != Decimal.from_float(0.1)


def test_exponent_notation_is_held_to_the_same_decimal_place_limit() -> None:
    """`1E-4` and `0.0001` are the same number written two ways, and both must
    be accepted. `1E-5` and `0.00001` are the same number written two ways, and
    both must be refused. Every existing decimal-place test uses plain notation
    only, so an exponent form could have slipped past the scale entirely.
    """
    accepted = a_valid_env()
    accepted[env_var(c.OCR_REGION_ACCEPT)] = "1E-4"

    parameters = c.load_confidence_parameters(accepted)
    assert parameters.ocr_region_accept == Decimal("0.0001")

    refused = a_valid_env()
    refused[env_var(c.OCR_REGION_ACCEPT)] = "1E-5"
    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(refused)
    assert str(CONFIDENCE_PLACES) in str(raised.value)


def test_a_negative_zero_probability_is_the_same_threshold_as_zero() -> None:
    """`Decimal("-0.0000")` is accepted — it is inside the range, finite and on
    the agreed scale. The question a red team has to ask is whether it BEHAVES
    as a different threshold from `0.0000`, because a sign that survives into a
    comparison would make two identical configurations act differently.

    It does not: `Decimal` compares numerically, so the loaded value equals
    `MIN` exactly. Pinned here so that if the representation ever starts
    mattering, it is a test failure rather than a field report.
    """
    environment = a_valid_env()
    environment[env_var(c.OCR_REGION_ACCEPT)] = "-0.0000"

    parameters = c.load_confidence_parameters(environment)

    assert parameters.ocr_region_accept == MIN
    assert parameters.ocr_region_accept <= MIN
    assert parameters.ocr_region_accept >= MIN


def test_a_trailing_newline_does_not_change_the_value() -> None:
    """`VALUE=$(cat secret_file)` and a here-doc both hand over a trailing
    newline. `Decimal` and `int` strip it, so the loader reads the number the
    operator wrote — and the operator is not told about the newline, which is
    the right outcome only because the stripped value is genuinely identical.
    """
    environment = a_valid_env()
    environment[env_var(c.OCR_REGION_ACCEPT)] = "0.5000\n"
    environment[env_var(c.PROCESSING_BUDGET_MS)] = f" {A_BUDGET_IN_MS} \n"

    parameters = c.load_confidence_parameters(environment)

    assert parameters.ocr_region_accept == Decimal("0.5000")
    assert parameters.processing_budget_ms == A_BUDGET_IN_MS


def test_a_count_written_with_digit_separators_is_the_number_python_reads() -> None:
    """`int("1_0")` is 10 — PEP 515 digit separators are honoured by `int`, and
    therefore by this loader. The danger would be a loader that quietly
    produced something ELSE from the same text: `1`, or a refusal the operator
    reads as "not a number" when it plainly was. It produces exactly what the
    text says, which is the only defensible behaviour for a value the operator
    typed.
    """
    environment = a_valid_env()
    environment[env_var(c.PROCESSING_BUDGET_MS)] = "30_000"

    parameters = c.load_confidence_parameters(environment)

    assert parameters.processing_budget_ms == A_BUDGET_IN_MS


@pytest.mark.parametrize("name", [c.RETRY_MAX_ATTEMPTS, c.WORST_K, c.PROCESSING_BUDGET_MS])
def test_a_count_written_with_a_decimal_point_is_refused_never_truncated(name: str) -> None:
    """All three counts, not just `worst_k`. A loader that reached for
    `int(float(raw))` would turn `2.9` into `2` — a budget, a retry cap or a
    `k` silently one lower than the operator wrote, with no error to notice.
    """
    environment = a_valid_env()
    environment[env_var(name)] = "2.9"

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    (line,) = problem_lines(str(raised.value))
    assert "2.9" in line
    assert "whole number" in line


# ══════════════════════════════════════════════════════════════════════════
# SEVERAL PROBLEMS AT ONCE — one restart, not N
# ══════════════════════════════════════════════════════════════════════════


def test_a_missing_and_an_invalid_parameter_are_both_reported_with_their_own_wording() -> None:
    """The whole message, character for character. Two problems of DIFFERENT
    kinds, so both templates are pinned at once and neither can be mutated into
    the other. The existing suite pins membership of the pieces; nothing pins
    the sentences they are assembled into.
    """
    environment = a_valid_env()
    del environment[env_var(c.OCR_REGION_ACCEPT)]
    environment[env_var(c.DOCUMENT_SCORE_RULE)] = "banana"

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    missing = next(s for s in c.PARAMETER_CATALOG if s.name == c.OCR_REGION_ACCEPT)
    invalid = next(s for s in c.PARAMETER_CATALOG if s.name == c.DOCUMENT_SCORE_RULE)
    assert str(raised.value) == (
        f"Engine 1 confidence configuration has {TWO_PROBLEMS} problem(s):\n"
        + expected_missing_line(missing)
        + "\n"
        + expected_invalid_line(
            invalid, "must be one of min, product, weighted_mean, worst_k; got 'banana'."
        )
    )


def test_all_sixteen_invalid_at_once_are_all_reported_in_one_raise() -> None:
    """The invalid-value mirror of "everything missing". A loader that raised
    on the first BAD value — rather than the first MISSING one — would still
    pass every existing test, because the existing all-at-once test removes
    keys instead of corrupting them.
    """
    environment = {spec.env_var: NONSENSE for spec in c.PARAMETER_CATALOG}

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert len(problem_lines(message)) == EXPECTED_PARAMETER_COUNT
    for spec in c.PARAMETER_CATALOG:
        assert f"  - {spec.name} ({spec.env_var}) is invalid: " in message


def test_problems_are_reported_in_the_catalogues_own_order() -> None:
    """A deployment log that lists the same four problems in a different order
    on two runs cannot be diffed against itself, and an operator working down
    the list has no way to know they have reached the end. The order is the
    document's own table order, which is also the order the doc is read in.
    """
    environment = a_valid_env()
    for name in (c.PROCESSING_BUDGET_MS, c.OCR_REGION_ACCEPT, c.CLASSIFICATION_ACCEPT):
        del environment[env_var(name)]

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    reported = [line.split()[1] for line in problem_lines(str(raised.value))]
    assert reported == [c.OCR_REGION_ACCEPT, c.CLASSIFICATION_ACCEPT, c.PROCESSING_BUDGET_MS]


# ══════════════════════════════════════════════════════════════════════════
# THE LOADER ONLY READS
# `ENGINE_1_CONFIDENCE_PARAMETERS.md`: "Configuration is never modified
# automatically."
# ══════════════════════════════════════════════════════════════════════════


def test_the_loader_leaves_the_environment_it_was_given_untouched() -> None:
    """On the success path and on the failure path. A loader that normalised a
    value in place — stripping a newline, upper-casing a rule — would change
    what the NEXT reader of that same mapping sees, which for `os.environ`
    means every subprocess started afterwards.
    """
    environment = a_valid_env()
    before = dict(environment)

    c.load_confidence_parameters(environment)
    assert environment == before

    broken = a_valid_env()
    broken[env_var(c.WORST_K)] = NONSENSE
    snapshot = dict(broken)
    with pytest.raises(c.ConfigurationError):
        c.load_confidence_parameters(broken)
    assert broken == snapshot


def test_the_loader_accepts_any_mapping_not_only_a_dict() -> None:
    """The signature says `Mapping[str, str]`, and `os.environ` is not a dict.
    A loader that reached for `dict`-only behaviour — `.copy()`, `.setdefault()`
    — would work in every test that passes a literal and fail at real startup.
    """
    environment: Mapping[str, str] = MappingProxyType(a_valid_env())

    parameters = c.load_confidence_parameters(environment)

    assert parameters.document_score_rule is c.DocumentScoreRule.MIN


def test_environment_variables_the_catalogue_does_not_name_are_ignored() -> None:
    """A real `os.environ` holds hundreds of unrelated variables, including
    ones sharing this prefix from a previous version of the table. None may
    influence the load, and none may cause a failure.
    """
    environment = a_valid_env()
    environment["ENGINE_1_CONFIDENCE_PARAMETER_THAT_WAS_REMOVED"] = "0.9999"
    environment["PATH"] = "/usr/bin"

    parameters = c.load_confidence_parameters(environment)

    assert parameters.ocr_region_accept == Decimal("0.5000")


# ══════════════════════════════════════════════════════════════════════════
# WHAT COMES OUT CANNOT CHANGE AFTERWARDS
# ══════════════════════════════════════════════════════════════════════════


def test_the_loaded_weight_map_cannot_be_mutated() -> None:
    """`_parse_weights` returns a `MappingProxyType`. Nothing tests it, and a
    mutation dropping the wrapper would leave a live, writable dict inside a
    "frozen" configuration object — a weight that could change after startup is
    a weight the sign-off never covered.

    The `cast` is deliberate: the type checker is told to allow the assignment
    precisely so the RUNTIME gets the chance to refuse it. Asserting the type
    alone would prove the annotation, not the behaviour.
    """
    parameters = c.load_confidence_parameters(a_valid_env())
    weights = parameters.document_score_weights

    with pytest.raises(TypeError):
        cast(MutableMapping[str, Decimal], weights)["gstin"] = Decimal("0.0000")

    assert dict(parameters.document_score_weights) == {"gstin": Decimal("1.0000")}


def test_a_loaded_parameter_cannot_be_reassigned() -> None:
    """Written through `setattr` with a computed name because that is the shape
    an attacker has: a configuration reloader iterating names, not a literal
    assignment the type checker would have caught first.
    """
    parameters = c.load_confidence_parameters(a_valid_env())
    attribute = c.WORST_K

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(parameters, attribute, LEGAL_COUNT + 1)

    assert parameters.worst_k == LEGAL_COUNT


# ══════════════════════════════════════════════════════════════════════════
# THE WEIGHT MAP'S OWN SHAPE
# ══════════════════════════════════════════════════════════════════════════


def test_a_weight_map_given_a_json_object_of_objects_is_refused() -> None:
    """Valid JSON, valid object, values that are objects rather than numbers —
    a shape neither the `float` branch nor the `bool` branch reaches, and one
    an operator produces easily by writing `{"gstin": {"weight": 1.0}}`.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": {"weight": 1.0}}'

    with pytest.raises(c.ConfigurationError) as raised:
        c.load_confidence_parameters(environment)

    message = str(raised.value)
    assert "gstin" in message
    assert "must be a number" in message


def test_a_weight_map_given_json_null_is_refused_as_not_an_object() -> None:
    """`json.loads("null")` succeeds and returns `None`, so this reaches the
    `not isinstance(parsed, dict)` guard rather than the decode-error branch —
    the same guard a JSON array reaches, entered from a different direction.
    """
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = "null"

    with pytest.raises(c.ConfigurationError, match="JSON object"):
        c.load_confidence_parameters(environment)


def test_a_weight_map_of_many_fields_sums_exactly_with_no_tolerance() -> None:
    """Ten fields at `0.1000`. Exactness is the claim `_weights_problem` makes
    ("`Decimal` arithmetic is exact for finite decimal fractions, so 'exactly'
    is a real equality check, not a tolerance"), and a ten-way split is where a
    tolerance would have been reached for.
    """
    ten_ways = {f"field_{index}": 0.1000 for index in range(10)}
    environment = a_valid_env()
    environment[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = json.dumps(ten_ways)

    parameters = c.load_confidence_parameters(environment)

    assert sum(parameters.document_score_weights.values()) == Decimal("1.0000")

    nine_ways = dict(ten_ways)
    del nine_ways["field_9"]
    short = a_valid_env()
    short[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = json.dumps(nine_ways)
    with pytest.raises(c.ConfigurationError, match=r"sum to 1\.0000"):
        c.load_confidence_parameters(short)
