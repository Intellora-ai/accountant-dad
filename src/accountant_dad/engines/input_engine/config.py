"""Engine 1's configuration loader — it invents nothing, and says so loudly.

`docs/ENGINE_1_CONFIDENCE_PARAMETERS.md` names sixteen parameters and marks
every one `UNSET`. `CLAUDE.md` §P, Amendment 3: *"Every threshold, weight and
cutoff is a named configuration variable... No hardcoded defaults. No
silently assumed values. Missing required confidence configuration fails
fast at startup, never falls back."* This module is the one place that
promise is kept: it turns a `Mapping[str, str]` — the shape `os.environ`
already has — into a `ConfidenceParameters`, and it has exactly one
behaviour worth documenting, because it is the module's entire reason to
exist:

    A MISSING REQUIRED PARAMETER RAISES AT STARTUP, NAMING THE PARAMETER —
    NEVER AT FIRST USE, NEVER SILENTLY, NEVER FALLING BACK TO A DEFAULT.

WHY EVERY PROBLEM IS COLLECTED BEFORE THE FIRST RAISE. A loader that raises
on the first missing name and stops turns a sixteen-parameter deployment
into sixteen restarts — the operator fixes one, reruns, discovers the next.
`load_confidence_parameters` reads all sixteen, validates all sixteen, and
raises once with every problem it found. `ConfidenceParameters.__post_init__`
does the opposite on purpose: it raises on the FIRST bad field, matching
`cleaner.CleanerSettings`, because a direct construction (a test, or code
that already has typed values) is a programming error already narrowed to
one call site, not an operator reading a deployment log.

WHY THE PROBABILITY-TYPE PARAMETERS REUSE `accountant_dad.confidence`. Eleven
of the sixteen are `P` values in the doc's own notation — *"Decimal never
float"*, `0.0000` to `1.0000`, four places — which is EXACTLY the
representation `accountant_dad.confidence` already defines as the ONE
Confidence type every artifact schema imports. Restating the range and the
precision here would be the identical failure `confidence.py`'s own
docstring was written to prevent: two definitions of the same scale,
drifting apart the first time one of them is edited. `MIN`, `MAX` and
`CONFIDENCE_PLACES` are imported, not copied; `_probability_problem` below is
the loader's OWN function, because turning an untyped raw string into a
typed value and deciding whether an already-typed value is a valid
Confidence are different jobs; the second one is imported.

WHY `document_score_rule` STILL ACCEPTS ALL FOUR NAMED VALUES. The same
document that names this parameter's range as `min · product · weighted_mean
· worst_k` goes on, in its own later section, to eliminate `product` and
`weighted_mean` by a cited theorem (Marichal & Mesiar 2009, Corollary 5.7).
That elimination is analysis, not yet a rewritten table row, and Law 54 is
explicit: *"Never invent the definition yourself. Ask."* Narrowing the
accepted set to `{min, worst_k}` here would be this module quietly making
the architectural call the doc says still needs the user's sign-off. So the
tension is left visible — on `DocumentScoreRule` below — rather than
resolved in code.

WHY `document_score_weights` IS PARSED AS JSON WITH `parse_float=Decimal`.
The doc's range for this parameter is *"map field -> weight, sum `1.0000`"*
and repeats, for every `P` value in the file, *"Decimal never float"*.
Python's `json` module routes ordinary decimal literals (`0.6`) through
whatever `parse_float` names before they ever become a `float` — passing
`Decimal` there means a weight typed by an operator never touches binary
floating point on its way in. It does NOT cover `NaN` / `Infinity` /
`-Infinity`: those are JSON *constants*, routed through a separate hook
Python leaves defaulted to `float`, so they still arrive as `float` and are
refused explicitly in `_parse_weights` rather than silently accepted as
"a number that happens to be infinite."

AND WHY IT IS PARSED WITH `object_pairs_hook` TOO. A JSON object may name the
same key twice, and Python resolves that LAST-WINS while it builds the dict —
so by the time `json.loads` returns the discarded weight is gone, and nothing
anywhere records that it was ever written. An operator who edits a weight map
and leaves a stale duplicate behind gets a weight they never chose between; the
survivors can still sum to `1.0000`, so the arithmetic check cannot catch it;
and Engine 1 starts with a number nobody agreed to, with nothing raised and
nothing logged. `object_pairs_hook` is the only point at which both weights are
still visible, which makes it the only place the refusal can happen at all. It
does not displace `parse_float`: the hook is handed values that have already
been through it.

WHY `env` IS A PARAMETER, NEVER READ FROM `os.environ` INTERNALLY BY
DEFAULT. `load_confidence_parameters(env: Mapping[str, str])` takes the
mapping as an argument with no default value — not because `os.environ` is
untrustworthy, but because a default value on THIS parameter would be the
same shape of quiet assumption the doc forbids for every parameter it
names, and because a test that must pass a real `dict[str, str]` exercises
the REAL parsing and REAL validation path (`os.environ` already satisfies
`Mapping[str, str]`; a plain `dict` literal is not a stand-in for it, it is
the same shape) rather than a mock standing in for one, matching `CLAUDE.md`
§J.6. `load_confidence_parameters_from_environment` is the one-line, no-logic
adapter that supplies the real process environment at actual startup.

WHAT THIS MODULE DOES NOT DO. It does not choose a value. It does not decide
what "safe" means, what "risky" means, or which document-score rule is
correct — those are Law 54 gaps this file inherits and passes through
unresolved. It does not write configuration anywhere:
`ENGINE_1_CONFIDENCE_PARAMETERS.md` — *"Configuration is never modified
automatically"* — and this module only ever reads.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType

from accountant_dad.confidence import CONFIDENCE_PLACES, MAX, MIN

# ── the sixteen parameter names ───────────────────────────────────────────
# `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md`'s table, in its own order, one
# constant per row, so a doc row and a name here can be put side by side.
# Plain strings, not a StrEnum: they do not share a scale or a type the way
# `cleaner.py`'s measurement names do not either — each is an independent
# parameter, and a shared enum would imply a relationship none of them has.

OCR_REGION_ACCEPT = "ocr_region_accept"
OCR_VISION_FALLBACK = "ocr_vision_fallback"
FIELD_CONFIDENCE_FLOOR = "field_confidence_floor"
FIELD_RISKY_MARK = "field_risky_mark"
DOCUMENT_CONFIDENCE_FLOOR = "document_confidence_floor"
HUMAN_REVIEW_TRIGGER = "human_review_trigger"
RETRY_TRIGGER = "retry_trigger"
RETRY_MAX_ATTEMPTS = "retry_max_attempts"
CLASSIFICATION_ACCEPT = "classification_accept"
TABLE_STRUCTURE_ACCEPT = "table_structure_accept"
TABLE_CELL_ACCEPT = "table_cell_accept"
CAPTURE_FIDELITY_FLOOR = "capture_fidelity_floor"
DOCUMENT_SCORE_RULE = "document_score_rule"
DOCUMENT_SCORE_WEIGHTS = "document_score_weights"
WORST_K = "worst_k"
PROCESSING_BUDGET_MS = "processing_budget_ms"

#: Every environment variable this module reads is this prefix plus the
#: parameter's own name, upper-cased. One rule, so "where do I set X" always
#: has the same answer shape, and so a name typed once above never has to be
#: retyped for its variable.
_ENV_PREFIX = "ENGINE_1_CONFIDENCE_"


class ConfigurationError(ValueError):
    """Raised by the loader, naming every parameter that is missing or
    invalid — never one at a time. The message is the whole deployment's
    problem list, not the first problem found.
    """


class ImpossibleParameterError(ValueError):
    """A parameter value arithmetic or the doc's own range cannot honour.

    Raised by `ConfidenceParameters.__post_init__` on direct construction —
    the mirror of `cleaner.ImpossibleSettingError` for this module. The
    loader never lets a caller see this: it validates first and only
    constructs once nothing can fail.
    """


class DocumentScoreRule(StrEnum):
    """How per-field confidence scores combine into one document score.

    `ENGINE_1_CONFIDENCE_PARAMETERS.md` #13 names all four values below as
    the parameter's range. Its own later section eliminates `PRODUCT` and
    `WEIGHTED_MEAN` by a cited theorem, on the grounds that only an
    order-statistic function is comparison-meaningful on an ordinal
    confidence scale. All four stay legal here anyway: choosing which values
    remain valid is the sign-off decision Law 54 reserves for the user, not
    a decision this loader is entitled to make for them.
    """

    MIN = "min"
    PRODUCT = "product"
    WEIGHTED_MEAN = "weighted_mean"
    WORST_K = "worst_k"


class _ParameterValueError(ValueError):
    """Internal control flow only. One parameter's raw value could not
    become a valid setting. Always caught inside this module and folded into
    `ConfigurationError`; it never reaches a caller on its own.
    """


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One parameter's name, purpose, unit, valid range — and the function
    that turns a raw string into the typed value or raises. Not `_`-prefixed:
    the loader's central promise is only checkable from outside if the
    catalogue it validates against is inspectable too, and `parse` belongs
    in the catalogue rather than beside it — it IS the range, expressed as
    code instead of a second prose copy that could drift from the first.
    """

    name: str
    env_var: str
    purpose: str
    unit: str
    range_text: str
    parse: Callable[[str], object]


def _probability_problem(value: Decimal) -> str | None:
    """The one place a `P` value's validity is decided. Bounds imported from
    `accountant_dad.confidence`, not restated, so this scale and the stored
    Confidence scale can never silently disagree.
    """
    if not value.is_finite():
        return f"must be finite; got {value}."
    if not MIN <= value <= MAX:
        return f"must lie in [{MIN}, {MAX}]; got {value}."
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > CONFIDENCE_PLACES:
        places = -exponent
        return (
            f"carries {places} decimal place(s); the agreed scale is "
            f"{CONFIDENCE_PLACES} ({MIN} to {MAX}); got {value}."
        )
    return None


def _count_problem(value: int, minimum: int) -> str | None:
    """`minimum` is the caller's own floor, arithmetic rather than a
    preference: `worst_k` needs at least one field to have a worst one,
    `retry_max_attempts` needs only "not negative" — the floors differ, so
    each call site supplies its own rather than this function picking one.
    """
    if value < minimum:
        return f"must be at least {minimum}; got {value}."
    return None


def _weights_problem(weights: Mapping[str, Decimal]) -> str | None:
    """Every weight a valid Confidence-scale value, and the set summing to
    exactly `1.0000` — `Decimal` arithmetic is exact for finite decimal
    fractions, so "exactly" is a real equality check, not a tolerance.
    """
    if not weights:
        return "must name at least one field; got none."
    total = Decimal("0")
    for key, value in weights.items():
        problem = _probability_problem(value)
        if problem is not None:
            return f"weight for {key!r} {problem}"
        total += value
    if total != Decimal("1.0000"):
        return f"weights must sum to 1.0000; got {total}."
    return None


def _parse_probability(raw: str) -> Decimal:
    """A `P` value: `Decimal`, never `float` — constructing straight from
    the raw string, never through `float(raw)` first, is what keeps a
    binary-float rounding error from ever entering a Confidence-scale
    number on its way in from configuration.
    """
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise _ParameterValueError(
            f"must be a decimal number in [{MIN}, {MAX}]; got {raw!r}, which is not a number."
        ) from exc
    problem = _probability_problem(value)
    if problem is not None:
        raise _ParameterValueError(problem)
    return value


def _parse_count(raw: str, *, minimum: int) -> int:
    """An `N`: a whole number, `int(raw)` rather than `int(float(raw))`, so
    `"3.5"` is refused as not a whole number instead of being truncated into
    one it never was.
    """
    try:
        value = int(raw)
    except ValueError as exc:
        raise _ParameterValueError(
            f"must be a whole number; got {raw!r}, which is not one."
        ) from exc
    problem = _count_problem(value, minimum)
    if problem is not None:
        raise _ParameterValueError(problem)
    return value


def _parse_retry_max_attempts(raw: str) -> int:
    return _parse_count(raw, minimum=0)


def _parse_worst_k(raw: str) -> int:
    return _parse_count(raw, minimum=1)


def _parse_processing_budget_ms(raw: str) -> int:
    return _parse_count(raw, minimum=1)


def _parse_document_score_rule(raw: str) -> DocumentScoreRule:
    try:
        return DocumentScoreRule(raw)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in DocumentScoreRule)
        raise _ParameterValueError(f"must be one of {allowed}; got {raw!r}.") from exc


class _DuplicateJsonKeyError(ValueError):
    """Internal control flow only. A JSON object named the same key twice.

    Raised from `_object_pairs_without_duplicates` while `json.loads` is still
    running, and always caught by `_parse_weights`, which folds it into a
    `_ParameterValueError` like every other way a weight map can be wrong.
    """


def _object_pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """A JSON object's members, refusing any name written twice.

    This runs as `object_pairs_hook` rather than after `json.loads` returns,
    because the duplicate does not survive that return: Python resolves
    repeated keys LAST-WINS while building the dict, and by the time a caller
    holds the result the discarded weight is simply gone. Measured, not assumed
    — `json.loads('{"gstin": 0.4000, "gstin": 1.0000}', parse_float=Decimal)`
    is `{'gstin': Decimal('1.0000')}`, and nothing anywhere records that
    `0.4000` was ever written. The hook is the only place both are still
    visible, so it is the only place the refusal can happen at all.

    `measurement._no_duplicate_names` refuses the identical shape one module
    away, for the identical reason it states in its own words: two values for
    one name leaves no authority for which one should be read. A weight has
    strictly more authority than a measurement — it decides a document score,
    which decides whether a document ever reaches a human.
    """
    names = [key for key, _ in pairs]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise _DuplicateJsonKeyError(
            f"names the same field twice: {', '.join(duplicated)}. Two weights "
            "for one field leaves no authority for which one the document "
            "score should use, and the surviving pair can still sum to 1.0000, "
            "so the arithmetic check cannot catch it."
        )
    return dict(pairs)


def _parse_weights(raw: str) -> Mapping[str, Decimal]:
    """`map field -> weight, sum 1.0000`, given as a JSON object. Ordinary
    decimal literals (`0.6`) arrive already `Decimal`, routed there by
    `parse_float` before this function ever sees them; only the JSON
    constants `NaN` / `Infinity` / `-Infinity` bypass that hook and still
    arrive as `float`, which is why `float` is refused explicitly below
    rather than accepted as "a number that happens to be infinite."

    `object_pairs_hook` is supplied for a second, separate reason: it is the
    only point at which a field named twice is still visible at all. See
    `_object_pairs_without_duplicates`. It does not displace `parse_float` —
    the hook receives values that have already been through it, so a weight
    still never touches binary floating point on its way in.
    """
    try:
        parsed = json.loads(
            raw, parse_float=Decimal, object_pairs_hook=_object_pairs_without_duplicates
        )
    except _DuplicateJsonKeyError as exc:
        raise _ParameterValueError(f"{exc} ({raw!r})") from exc
    except json.JSONDecodeError as exc:
        raise _ParameterValueError(
            "must be a JSON object mapping field name to weight; got "
            f"{raw!r}, which does not parse as JSON."
        ) from exc
    if not isinstance(parsed, dict):
        raise _ParameterValueError(
            f"must be a JSON object mapping field name to weight; got {raw!r}."
        )
    weights: dict[str, Decimal] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise _ParameterValueError(
                f"every weight key must be a string; got {key!r} in {raw!r}."
            )
        if isinstance(value, bool):
            raise _ParameterValueError(
                f"weight for {key!r} must be a number, not a boolean; got {value!r} in {raw!r}."
            )
        if isinstance(value, float):
            raise _ParameterValueError(
                f"weight for {key!r} must be finite; got {value!r} in {raw!r}."
            )
        if not isinstance(value, (int, Decimal)):
            raise _ParameterValueError(
                f"weight for {key!r} must be a number; got {value!r} in {raw!r}."
            )
        weights[key] = value if isinstance(value, Decimal) else Decimal(str(value))
    problem = _weights_problem(weights)
    if problem is not None:
        raise _ParameterValueError(f"{problem} ({raw!r})")
    return MappingProxyType(weights)


#: `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md`'s table, made executable. Sixteen
#: entries, in the doc's own order, each carrying everything the loader and a
#: caller both need: where to find it, why it exists, what unit it is in,
#: what range it accepts, and the function that enforces that range.
PARAMETER_CATALOG: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        name=OCR_REGION_ACCEPT,
        env_var=f"{_ENV_PREFIX}{OCR_REGION_ACCEPT.upper()}",
        purpose="the lowest per-region OCR score Engine 1 will treat as read at all",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=OCR_VISION_FALLBACK,
        env_var=f"{_ENV_PREFIX}{OCR_VISION_FALLBACK.upper()}",
        purpose="the score below which the vision fallback replaces PaddleOCR",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=FIELD_CONFIDENCE_FLOOR,
        env_var=f"{_ENV_PREFIX}{FIELD_CONFIDENCE_FLOOR.upper()}",
        purpose="the lowest per-field score a field may carry and still be reported as read",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=FIELD_RISKY_MARK,
        env_var=f"{_ENV_PREFIX}{FIELD_RISKY_MARK.upper()}",
        purpose="the score at or below which a field is flagged risky in the Confidence Report",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=DOCUMENT_CONFIDENCE_FLOOR,
        env_var=f"{_ENV_PREFIX}{DOCUMENT_CONFIDENCE_FLOOR.upper()}",
        purpose="the lowest whole-document score Engine 1 will emit as a usable Evidence Object",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=HUMAN_REVIEW_TRIGGER,
        env_var=f"{_ENV_PREFIX}{HUMAN_REVIEW_TRIGGER.upper()}",
        purpose="the document score at or below which the document is routed to a human",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=RETRY_TRIGGER,
        env_var=f"{_ENV_PREFIX}{RETRY_TRIGGER.upper()}",
        purpose=(
            "the document score at or below which Engine 1 re-processes with "
            "different preprocessing"
        ),
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=RETRY_MAX_ATTEMPTS,
        env_var=f"{_ENV_PREFIX}{RETRY_MAX_ATTEMPTS.upper()}",
        purpose="the hard cap on retries for one document",
        unit="count (N)",
        range_text="a whole number, at least 0",
        parse=_parse_retry_max_attempts,
    ),
    ParameterSpec(
        name=CLASSIFICATION_ACCEPT,
        env_var=f"{_ENV_PREFIX}{CLASSIFICATION_ACCEPT.upper()}",
        purpose="the lowest document-type classification score accepted without review",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=TABLE_STRUCTURE_ACCEPT,
        env_var=f"{_ENV_PREFIX}{TABLE_STRUCTURE_ACCEPT.upper()}",
        purpose="the lowest table-structure detection score accepted",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=TABLE_CELL_ACCEPT,
        env_var=f"{_ENV_PREFIX}{TABLE_CELL_ACCEPT.upper()}",
        purpose="the lowest per-cell score accepted within an accepted table",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=CAPTURE_FIDELITY_FLOOR,
        env_var=f"{_ENV_PREFIX}{CAPTURE_FIDELITY_FLOOR.upper()}",
        purpose="the lowest capture-fidelity score for a typed Human Business Description",
        unit="probability (P)",
        range_text=f"[{MIN}, {MAX}], at most {CONFIDENCE_PLACES} decimal places",
        parse=_parse_probability,
    ),
    ParameterSpec(
        name=DOCUMENT_SCORE_RULE,
        env_var=f"{_ENV_PREFIX}{DOCUMENT_SCORE_RULE.upper()}",
        purpose="how per-field scores combine into one document score",
        unit="named rule",
        range_text="one of: " + ", ".join(member.value for member in DocumentScoreRule),
        parse=_parse_document_score_rule,
    ),
    ParameterSpec(
        name=DOCUMENT_SCORE_WEIGHTS,
        env_var=f"{_ENV_PREFIX}{DOCUMENT_SCORE_WEIGHTS.upper()}",
        purpose=(
            "per-field weights, used when document_score_rule combines scores by weighted_mean"
        ),
        unit="JSON weight map",
        range_text=(
            "a JSON object mapping field name to a decimal weight in "
            f"[{MIN}, {MAX}], summing to exactly 1.0000"
        ),
        parse=_parse_weights,
    ),
    ParameterSpec(
        name=WORST_K,
        env_var=f"{_ENV_PREFIX}{WORST_K.upper()}",
        purpose=(
            "how many worst fields the document score uses, when document_score_rule is worst_k"
        ),
        unit="count (N)",
        range_text="a whole number, at least 1",
        parse=_parse_worst_k,
    ),
    ParameterSpec(
        name=PROCESSING_BUDGET_MS,
        env_var=f"{_ENV_PREFIX}{PROCESSING_BUDGET_MS.upper()}",
        purpose="the wall-clock budget per document before Engine 1 reports a timeout",
        unit="milliseconds (ms)",
        range_text="a whole number, at least 1",
        parse=_parse_processing_budget_ms,
    ),
)


@dataclass(frozen=True, slots=True)
class ConfidenceParameters:
    """Sixteen numbers, all required, none of them this module's opinion.

    Every field matches a row of `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md`'s
    table, in the table's own order. Nothing here has a default: the table's
    own heading is *"Status: AWAITING NUMERIC SIGN-OFF... every value below
    is UNSET"*, and `CLAUDE.md` §P forbids exactly the pattern a default
    would create — a number nobody decided, arriving downstream wearing the
    specification's authority. `#14` and `#15` are required unconditionally
    even though the doc marks each *"only if"* a particular `document_score_rule`
    — the alternative, requiring them only when that rule is chosen, would
    make THIS loader the thing deciding which fields are load-bearing for a
    rule Law 54 has not yet let anyone finalise; requiring all sixteen keeps
    that decision exactly where it already sits, undecided, rather than
    half-encoding it here.
    """

    ocr_region_accept: Decimal
    ocr_vision_fallback: Decimal
    field_confidence_floor: Decimal
    field_risky_mark: Decimal
    document_confidence_floor: Decimal
    human_review_trigger: Decimal
    retry_trigger: Decimal
    retry_max_attempts: int
    classification_accept: Decimal
    table_structure_accept: Decimal
    table_cell_accept: Decimal
    capture_fidelity_floor: Decimal
    document_score_rule: DocumentScoreRule
    document_score_weights: Mapping[str, Decimal]
    worst_k: int
    processing_budget_ms: int

    def __post_init__(self) -> None:
        for name, probability in (
            (OCR_REGION_ACCEPT, self.ocr_region_accept),
            (OCR_VISION_FALLBACK, self.ocr_vision_fallback),
            (FIELD_CONFIDENCE_FLOOR, self.field_confidence_floor),
            (FIELD_RISKY_MARK, self.field_risky_mark),
            (DOCUMENT_CONFIDENCE_FLOOR, self.document_confidence_floor),
            (HUMAN_REVIEW_TRIGGER, self.human_review_trigger),
            (RETRY_TRIGGER, self.retry_trigger),
            (CLASSIFICATION_ACCEPT, self.classification_accept),
            (TABLE_STRUCTURE_ACCEPT, self.table_structure_accept),
            (TABLE_CELL_ACCEPT, self.table_cell_accept),
            (CAPTURE_FIDELITY_FLOOR, self.capture_fidelity_floor),
        ):
            problem = _probability_problem(probability)
            if problem is not None:
                raise ImpossibleParameterError(f"{name} {problem}")

        for name, count, minimum in (
            (RETRY_MAX_ATTEMPTS, self.retry_max_attempts, 0),
            (WORST_K, self.worst_k, 1),
            (PROCESSING_BUDGET_MS, self.processing_budget_ms, 1),
        ):
            count_problem = _count_problem(count, minimum)
            if count_problem is not None:
                raise ImpossibleParameterError(f"{name} {count_problem}")

        weights_problem = _weights_problem(self.document_score_weights)
        if weights_problem is not None:
            raise ImpossibleParameterError(f"{DOCUMENT_SCORE_WEIGHTS} {weights_problem}")


def _find_problems(env: Mapping[str, str]) -> list[str]:
    """Every problem across all sixteen parameters, not the first one found.

    A missing name and an invalid value are reported the same way: the
    operator does not care which restart introduced which problem, only that
    the next restart fixes all of them.
    """
    problems: list[str] = []
    for spec in PARAMETER_CATALOG:
        raw = env.get(spec.env_var)
        if raw is None:
            problems.append(
                f"{spec.name} is not set. Set the environment variable "
                f"{spec.env_var} — {spec.purpose}. Unit: {spec.unit}. "
                f"Valid range: {spec.range_text}."
            )
            continue
        try:
            spec.parse(raw)
        except _ParameterValueError as problem:
            problems.append(
                f"{spec.name} ({spec.env_var}) is invalid: {problem} "
                f"{spec.purpose}. Unit: {spec.unit}. Valid range: {spec.range_text}."
            )
    return problems


def _env_var(name: str) -> str:
    """The environment variable a parameter name resolves to. A function
    rather than a second dict: `PARAMETER_CATALOG` above is already that
    mapping's one source of truth, so this reads name -> env_var straight off
    it instead of building a second table that could drift from the first.
    """
    for spec in PARAMETER_CATALOG:
        if spec.name == name:
            return spec.env_var
    raise KeyError(f"{name!r} is not a parameter this module knows about.")


def load_confidence_parameters(env: Mapping[str, str]) -> ConfidenceParameters:
    """Read all sixteen parameters from `env`, or raise naming every one that
    is missing or invalid, in a single `ConfigurationError`.

    `env` takes no default. `os.environ` already satisfies
    `Mapping[str, str]` — CPython guarantees every value it holds is `str` on
    every supported platform — so a caller at real startup passes it directly
    or calls `load_confidence_parameters_from_environment` below; a test
    passes a plain `dict[str, str]`, exercising this exact parsing and
    validation path rather than a stand-in for it.
    """
    problems = _find_problems(env)
    if problems:
        listed = "\n".join(f"  - {problem}" for problem in problems)
        raise ConfigurationError(
            f"Engine 1 confidence configuration has {len(problems)} problem(s):\n{listed}"
        )
    return ConfidenceParameters(
        ocr_region_accept=_parse_probability(env[_env_var(OCR_REGION_ACCEPT)]),
        ocr_vision_fallback=_parse_probability(env[_env_var(OCR_VISION_FALLBACK)]),
        field_confidence_floor=_parse_probability(env[_env_var(FIELD_CONFIDENCE_FLOOR)]),
        field_risky_mark=_parse_probability(env[_env_var(FIELD_RISKY_MARK)]),
        document_confidence_floor=_parse_probability(env[_env_var(DOCUMENT_CONFIDENCE_FLOOR)]),
        human_review_trigger=_parse_probability(env[_env_var(HUMAN_REVIEW_TRIGGER)]),
        retry_trigger=_parse_probability(env[_env_var(RETRY_TRIGGER)]),
        retry_max_attempts=_parse_retry_max_attempts(env[_env_var(RETRY_MAX_ATTEMPTS)]),
        classification_accept=_parse_probability(env[_env_var(CLASSIFICATION_ACCEPT)]),
        table_structure_accept=_parse_probability(env[_env_var(TABLE_STRUCTURE_ACCEPT)]),
        table_cell_accept=_parse_probability(env[_env_var(TABLE_CELL_ACCEPT)]),
        capture_fidelity_floor=_parse_probability(env[_env_var(CAPTURE_FIDELITY_FLOOR)]),
        document_score_rule=_parse_document_score_rule(env[_env_var(DOCUMENT_SCORE_RULE)]),
        document_score_weights=_parse_weights(env[_env_var(DOCUMENT_SCORE_WEIGHTS)]),
        worst_k=_parse_worst_k(env[_env_var(WORST_K)]),
        processing_budget_ms=_parse_processing_budget_ms(env[_env_var(PROCESSING_BUDGET_MS)]),
    )


def load_confidence_parameters_from_environment() -> ConfidenceParameters:
    """The real entry point at process startup. `os.environ` already
    satisfies `Mapping[str, str]`, so this is a one-line adapter, not a
    second implementation.
    """
    return load_confidence_parameters(os.environ)
