"""`config` — tests written to catch an invented default, not to confirm parsing.

`ENGINE_1_CONFIDENCE_PARAMETERS.md` marks all sixteen parameters `UNSET`, and
`CLAUDE.md` §P states the one behaviour this module exists to guarantee:

    A missing required parameter raises at STARTUP, naming the parameter -
    never at first use, never silently, never falling back to a default.

So the tests below are organised around ways a default could sneak back in,
because a test that only confirms "valid input produces a valid object" would
never notice one:

  A MUTATION THAT INSERTS A FALLBACK MUST TURN SOMETHING RED.
      `test_every_parameter_missing_at_once_raises_rather_than_returning_an_object`
      calls the loader with nothing set at all. If a future edit adds
      `env.get(spec.env_var, "0.5000")` anywhere, this stops raising and starts
      returning a fully populated `ConfidenceParameters` built entirely from
      invented numbers - the exact failure this module exists to prevent.

  MISSING AND INVALID ARE DIFFERENT PROBLEMS AND MUST BE REPORTED DIFFERENTLY.
      A parameter set to `""` is present-but-empty, not absent, and the loader
      must say so as an invalid value, not silently accept it or misreport it
      as unset.

  SEVERAL PROBLEMS MUST COST THE OPERATOR ONE RESTART, NOT N.
      `test_several_missing_parameters_are_all_named_in_one_raise` proves the
      loader collects every problem across all sixteen parameters before
      raising once, rather than stopping at the first.

REAL DEPENDENCIES, NO MOCKS (`CLAUDE.md` §J.6). Every test calls the real
loader with a real `dict[str, str]` - the same shape `os.environ` already
has - never a stand-in for one.

Private helpers of `config` (`_env_var`) are used directly from a few tests
below to build environments keyed by real variable names without duplicating
`_ENV_PREFIX`'s own logic in this file - a second copy of that mapping would
be exactly the drift Law 19 forbids.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from accountant_dad.engines.input_engine import config as c

#: Guards against silent growth or shrinkage of the parameter table itself.
EXPECTED_PARAMETER_COUNT = 16

ONE_MISSING_PARAMETER = 1
THREE_MISSING_PARAMETERS = 3

_PROBLEM_COUNT_PATTERN = re.compile(r"has (\d+) problem\(s\)")

#: The legal raw values `a_valid_env()` sets for the parameters whose valid
#: range is not a `P` value - named once, so a fixture value and the
#: assertion that checks it can never silently drift apart from each other.
VALID_PROBABILITY = "0.5000"
VALID_RETRY_MAX_ATTEMPTS = 3
VALID_WORST_K = 1
VALID_PROCESSING_BUDGET_MS = 30000
VALID_DOCUMENT_SCORE_RULE = "min"
VALID_DOCUMENT_SCORE_WEIGHTS = {"gstin": Decimal("1.0000")}


def valid_raw_value(name: str) -> str:
    """One legal raw string for the named parameter - never used to claim
    these are the RIGHT operating points (Stage 4, blocked on P1); only that
    they are legal enough to isolate one parameter's behaviour at a time.
    """
    if name == c.DOCUMENT_SCORE_RULE:
        return VALID_DOCUMENT_SCORE_RULE
    if name == c.DOCUMENT_SCORE_WEIGHTS:
        return '{"gstin": 1.0000}'
    if name == c.RETRY_MAX_ATTEMPTS:
        return str(VALID_RETRY_MAX_ATTEMPTS)
    if name == c.WORST_K:
        return str(VALID_WORST_K)
    if name == c.PROCESSING_BUDGET_MS:
        return str(VALID_PROCESSING_BUDGET_MS)
    return VALID_PROBABILITY


def a_valid_env() -> dict[str, str]:
    """Every one of the sixteen parameters, set to a legal value.

    Built from `PARAMETER_CATALOG` itself rather than a hand-typed literal
    list of environment variable names, so this fixture cannot drift from the
    module it exercises - if a seventeenth parameter is ever added, this
    fixture grows with it automatically.
    """
    return {spec.env_var: valid_raw_value(spec.name) for spec in c.PARAMETER_CATALOG}


def without(env: dict[str, str], *env_vars: str) -> dict[str, str]:
    return {key: value for key, value in env.items() if key not in env_vars}


def reported_problem_count(message: str) -> int:
    """How many problems `ConfigurationError`'s own message says it found -
    read from the message's stated total (`"has N problem(s)"`) rather than
    counted by searching for parameter names, which is unreliable: several
    parameters' `purpose` text legitimately names OTHER parameters in prose.
    """
    match = _PROBLEM_COUNT_PATTERN.search(message)
    assert match is not None, f"no stated problem count found in: {message!r}"
    return int(match.group(1))


def env_var(name: str) -> str:
    """The environment variable a parameter name resolves to, read from the
    real catalog rather than reconstructed with `_ENV_PREFIX` a second time.
    """
    return c._env_var(name)


# ── the catalog itself ──────────────────────────────────────────────────────


def test_parameter_catalog_has_exactly_sixteen_entries() -> None:
    assert len(c.PARAMETER_CATALOG) == EXPECTED_PARAMETER_COUNT


def test_every_catalog_entry_uses_the_engine_1_confidence_prefix() -> None:
    for spec in c.PARAMETER_CATALOG:
        assert spec.env_var.startswith("ENGINE_1_CONFIDENCE_")


def test_every_catalog_entry_names_its_purpose_unit_and_range() -> None:
    """Law 52/54: a threshold with no purpose, unit or range is a number
    nobody can audit later, whatever value it eventually gets."""
    for spec in c.PARAMETER_CATALOG:
        assert spec.purpose.strip()
        assert spec.unit.strip()
        assert spec.range_text.strip()


# ── a full valid environment loads correctly - the positive baseline ──────


def test_a_fully_valid_environment_loads_every_field_with_its_real_value() -> None:
    parameters = c.load_confidence_parameters(a_valid_env())

    probability = Decimal(VALID_PROBABILITY)
    assert parameters.ocr_region_accept == probability
    assert parameters.ocr_vision_fallback == probability
    assert parameters.field_confidence_floor == probability
    assert parameters.field_risky_mark == probability
    assert parameters.document_confidence_floor == probability
    assert parameters.human_review_trigger == probability
    assert parameters.retry_trigger == probability
    assert parameters.retry_max_attempts == VALID_RETRY_MAX_ATTEMPTS
    assert parameters.classification_accept == probability
    assert parameters.table_structure_accept == probability
    assert parameters.table_cell_accept == probability
    assert parameters.capture_fidelity_floor == probability
    assert parameters.document_score_rule is c.DocumentScoreRule(VALID_DOCUMENT_SCORE_RULE)
    assert parameters.document_score_weights == VALID_DOCUMENT_SCORE_WEIGHTS
    assert parameters.worst_k == VALID_WORST_K
    assert parameters.processing_budget_ms == VALID_PROCESSING_BUDGET_MS


def test_load_confidence_parameters_from_environment_reads_the_real_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one-line adapter that supplies `os.environ` at real startup."""
    for key, value in a_valid_env().items():
        monkeypatch.setenv(key, value)

    parameters = c.load_confidence_parameters_from_environment()

    assert parameters.ocr_region_accept == Decimal("0.5000")


# ── no default exists, anywhere - the mutation-sensitive tests ────────────


def test_every_parameter_missing_at_once_raises_rather_than_returning_an_object() -> None:
    """Construct with NOTHING set. A mutation that inserts a fallback for even
    one parameter turns this green-when-it-should-be-red; this test is written
    so that instead it fails to raise, which pytest reports as a failure."""
    with pytest.raises(c.ConfigurationError) as excinfo:
        c.load_confidence_parameters({})

    message = str(excinfo.value)
    for spec in c.PARAMETER_CATALOG:
        assert spec.name in message


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=lambda spec: spec.name)
def test_each_parameter_missing_alone_raises_naming_only_it(spec: c.ParameterSpec) -> None:
    env = without(a_valid_env(), spec.env_var)

    with pytest.raises(c.ConfigurationError, match=spec.name):
        c.load_confidence_parameters(env)


@pytest.mark.parametrize("spec", c.PARAMETER_CATALOG, ids=lambda spec: spec.name)
def test_each_missing_parameter_message_carries_its_purpose_unit_and_range(
    spec: c.ParameterSpec,
) -> None:
    env = without(a_valid_env(), spec.env_var)

    with pytest.raises(c.ConfigurationError) as excinfo:
        c.load_confidence_parameters(env)

    message = str(excinfo.value)
    assert spec.env_var in message
    assert spec.purpose in message
    assert spec.unit in message
    assert spec.range_text in message


def test_several_missing_parameters_are_all_named_in_one_raise() -> None:
    """Three removed, three reported - counted from the message's own stated
    total rather than by checking that no OTHER parameter's name appears:
    `WORST_K` and `DOCUMENT_SCORE_WEIGHTS`'s own purposes legitimately
    mention `document_score_rule` in prose, so a bare substring check would
    misfire on a parameter that was never broken.
    """
    env = without(
        a_valid_env(),
        env_var(c.OCR_REGION_ACCEPT),
        env_var(c.WORST_K),
        env_var(c.DOCUMENT_SCORE_RULE),
    )

    with pytest.raises(c.ConfigurationError) as excinfo:
        c.load_confidence_parameters(env)

    message = str(excinfo.value)
    assert c.OCR_REGION_ACCEPT in message
    assert c.WORST_K in message
    assert c.DOCUMENT_SCORE_RULE in message
    assert reported_problem_count(message) == THREE_MISSING_PARAMETERS


def test_one_missing_parameter_names_only_that_one() -> None:
    env = without(a_valid_env(), env_var(c.WORST_K))

    with pytest.raises(c.ConfigurationError) as excinfo:
        c.load_confidence_parameters(env)

    message = str(excinfo.value)
    assert c.WORST_K in message
    assert reported_problem_count(message) == ONE_MISSING_PARAMETER


# ── missing vs. present-but-empty are different problems ──────────────────


def test_a_probability_parameter_present_but_empty_is_reported_as_invalid() -> None:
    env = a_valid_env()
    env[env_var(c.FIELD_CONFIDENCE_FLOOR)] = ""

    with pytest.raises(c.ConfigurationError) as excinfo:
        c.load_confidence_parameters(env)

    message = str(excinfo.value)
    assert c.FIELD_CONFIDENCE_FLOOR in message
    assert "invalid" in message
    assert "is not set" not in message.split(c.FIELD_CONFIDENCE_FLOOR)[1].split("\n")[0]


def test_a_count_parameter_present_but_empty_is_reported_as_invalid() -> None:
    env = a_valid_env()
    env[env_var(c.RETRY_MAX_ATTEMPTS)] = ""

    with pytest.raises(c.ConfigurationError, match=r"invalid"):
        c.load_confidence_parameters(env)


def test_document_score_weights_present_but_empty_is_reported_as_invalid() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = ""

    with pytest.raises(c.ConfigurationError, match=r"invalid"):
        c.load_confidence_parameters(env)


# ── non-numeric strings ─────────────────────────────────────────────────────


def test_a_probability_parameter_given_a_non_numeric_string_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "not-a-number"

    with pytest.raises(c.ConfigurationError, match=r"not-a-number"):
        c.load_confidence_parameters(env)


def test_a_count_parameter_given_a_non_numeric_string_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.RETRY_MAX_ATTEMPTS)] = "three"

    with pytest.raises(c.ConfigurationError, match=r"three"):
        c.load_confidence_parameters(env)


def test_a_count_parameter_given_a_decimal_string_is_refused_not_truncated() -> None:
    """`int("3.5")` raises; the loader must refuse it, never floor it to 3."""
    env = a_valid_env()
    env[env_var(c.WORST_K)] = "3.5"

    with pytest.raises(c.ConfigurationError, match=r"3\.5"):
        c.load_confidence_parameters(env)


def test_document_score_rule_given_an_unknown_name_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_RULE)] = "banana"

    with pytest.raises(c.ConfigurationError, match=r"banana"):
        c.load_confidence_parameters(env)


def test_document_score_weights_given_non_json_text_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = "not json at all"

    with pytest.raises(c.ConfigurationError, match=r"not json at all"):
        c.load_confidence_parameters(env)


# ── probability bounds: below, above, and exactly at each boundary ────────


def test_a_probability_parameter_below_the_range_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "-0.0001"

    with pytest.raises(c.ConfigurationError, match=r"-0.0001"):
        c.load_confidence_parameters(env)


def test_a_probability_parameter_above_the_range_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "1.0001"

    with pytest.raises(c.ConfigurationError, match=r"1.0001"):
        c.load_confidence_parameters(env)


def test_a_probability_parameter_exactly_at_the_lower_boundary_is_accepted() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "0.0000"

    parameters = c.load_confidence_parameters(env)

    assert parameters.ocr_region_accept == Decimal("0.0000")


def test_a_probability_parameter_exactly_at_the_upper_boundary_is_accepted() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "1.0000"

    parameters = c.load_confidence_parameters(env)

    assert parameters.ocr_region_accept == Decimal("1.0000")


def test_a_probability_parameter_with_four_decimal_places_is_accepted() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "0.1234"

    parameters = c.load_confidence_parameters(env)

    assert parameters.ocr_region_accept == Decimal("0.1234")


def test_a_probability_parameter_with_five_decimal_places_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.OCR_REGION_ACCEPT)] = "0.12345"

    with pytest.raises(c.ConfigurationError, match=r"0.12345"):
        c.load_confidence_parameters(env)


# ── count bounds: below, above (none), and exactly at each boundary ───────


def test_retry_max_attempts_negative_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.RETRY_MAX_ATTEMPTS)] = "-1"

    with pytest.raises(c.ConfigurationError, match=r"-1"):
        c.load_confidence_parameters(env)


def test_retry_max_attempts_zero_is_accepted_as_its_own_lower_boundary() -> None:
    env = a_valid_env()
    env[env_var(c.RETRY_MAX_ATTEMPTS)] = "0"

    parameters = c.load_confidence_parameters(env)

    assert parameters.retry_max_attempts == 0


def test_worst_k_zero_is_refused_below_its_lower_boundary_of_one() -> None:
    env = a_valid_env()
    env[env_var(c.WORST_K)] = "0"

    with pytest.raises(c.ConfigurationError, match=r"WORST_K"):
        c.load_confidence_parameters(env)


def test_worst_k_one_is_accepted_at_its_lower_boundary() -> None:
    env = a_valid_env()
    env[env_var(c.WORST_K)] = "1"

    parameters = c.load_confidence_parameters(env)

    assert parameters.worst_k == 1


def test_processing_budget_ms_zero_is_refused_below_its_lower_boundary_of_one() -> None:
    env = a_valid_env()
    env[env_var(c.PROCESSING_BUDGET_MS)] = "0"

    with pytest.raises(c.ConfigurationError):
        c.load_confidence_parameters(env)


def test_processing_budget_ms_one_is_accepted_at_its_lower_boundary() -> None:
    env = a_valid_env()
    env[env_var(c.PROCESSING_BUDGET_MS)] = "1"

    parameters = c.load_confidence_parameters(env)

    assert parameters.processing_budget_ms == 1


# ── document_score_weights: its own arithmetic ─────────────────────────────


def test_document_score_weights_summing_below_one_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 0.4000, "amount": 0.5999}'

    with pytest.raises(c.ConfigurationError, match=r"1\.0000"):
        c.load_confidence_parameters(env)


def test_document_score_weights_summing_to_exactly_one_across_two_fields_is_accepted() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": 0.4000, "amount": 0.6000}'

    parameters = c.load_confidence_parameters(env)

    assert parameters.document_score_weights == {
        "gstin": Decimal("0.4000"),
        "amount": Decimal("0.6000"),
    }


def test_document_score_weights_with_no_fields_is_refused() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = "{}"

    with pytest.raises(c.ConfigurationError, match=r"at least one field"):
        c.load_confidence_parameters(env)


def test_document_score_weights_rejects_a_boolean_weight() -> None:
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": true}'

    with pytest.raises(c.ConfigurationError, match=r"boolean"):
        c.load_confidence_parameters(env)


def test_document_score_weights_rejects_an_infinite_weight() -> None:
    """`json.loads` accepts the `Infinity` constant by default; `_parse_weights`
    must refuse it explicitly rather than let an infinite weight through."""
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_WEIGHTS)] = '{"gstin": Infinity}'

    with pytest.raises(c.ConfigurationError, match=r"finite"):
        c.load_confidence_parameters(env)


# ── document_score_rule: the tension left visible on purpose ──────────────


@pytest.mark.parametrize("rule", ["min", "product", "weighted_mean", "worst_k"])
def test_document_score_rule_currently_accepts_all_four_named_values(rule: str) -> None:
    """`ENGINE_1_CONFIDENCE_PARAMETERS.md` #13 names all four as the range.
    `CONFIDENCE_SPECIFICATION.md` §4 later eliminates two by a cited theorem,
    but that elimination is not yet an amendment to the locked parameter
    table (§9, open item O3) - so narrowing this set is not this module's
    call to make, and this test locks the current, wider behaviour so a
    silent narrowing is visible as a test failure rather than an undiscussed
    edit."""
    env = a_valid_env()
    env[env_var(c.DOCUMENT_SCORE_RULE)] = rule

    parameters = c.load_confidence_parameters(env)

    assert parameters.document_score_rule is c.DocumentScoreRule(rule)


# ── direct construction: ConfidenceParameters.__post_init__ ───────────────


def test_direct_construction_out_of_range_raises_impossible_parameter_error() -> None:
    valid = c.load_confidence_parameters(a_valid_env())

    with pytest.raises(c.ImpossibleParameterError, match=r"ocr_region_accept"):
        c.ConfidenceParameters(
            ocr_region_accept=Decimal("1.5000"),
            ocr_vision_fallback=valid.ocr_vision_fallback,
            field_confidence_floor=valid.field_confidence_floor,
            field_risky_mark=valid.field_risky_mark,
            document_confidence_floor=valid.document_confidence_floor,
            human_review_trigger=valid.human_review_trigger,
            retry_trigger=valid.retry_trigger,
            retry_max_attempts=valid.retry_max_attempts,
            classification_accept=valid.classification_accept,
            table_structure_accept=valid.table_structure_accept,
            table_cell_accept=valid.table_cell_accept,
            capture_fidelity_floor=valid.capture_fidelity_floor,
            document_score_rule=valid.document_score_rule,
            document_score_weights=valid.document_score_weights,
            worst_k=valid.worst_k,
            processing_budget_ms=valid.processing_budget_ms,
        )


def test_direct_construction_with_every_valid_value_succeeds() -> None:
    valid = c.load_confidence_parameters(a_valid_env())

    reconstructed = c.ConfidenceParameters(
        ocr_region_accept=valid.ocr_region_accept,
        ocr_vision_fallback=valid.ocr_vision_fallback,
        field_confidence_floor=valid.field_confidence_floor,
        field_risky_mark=valid.field_risky_mark,
        document_confidence_floor=valid.document_confidence_floor,
        human_review_trigger=valid.human_review_trigger,
        retry_trigger=valid.retry_trigger,
        retry_max_attempts=valid.retry_max_attempts,
        classification_accept=valid.classification_accept,
        table_structure_accept=valid.table_structure_accept,
        table_cell_accept=valid.table_cell_accept,
        capture_fidelity_floor=valid.capture_fidelity_floor,
        document_score_rule=valid.document_score_rule,
        document_score_weights=valid.document_score_weights,
        worst_k=valid.worst_k,
        processing_budget_ms=valid.processing_budget_ms,
    )

    assert reconstructed == valid
