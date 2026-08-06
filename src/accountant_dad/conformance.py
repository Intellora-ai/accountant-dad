"""The conformance layer — proving each prohibition is enforced, and by what.

`MVP_BUILD_VERIFY_FIX.md:50` — green requires *"Conformance suite passes —
every predicate, including the ID ablation test."*
`MVP_IMPLEMENTATION_BLUEPRINT.md:135` — P2 is done when *"every `MUST NEVER` is
a predicate or on the review-only list with an expiry"* and *"a malformed
artifact is rejected **by the correct predicate**."*

THE HARD WORD IS `CORRECT`.
    Showing that a malformed artifact is refused is easy — the six schemas
    already refuse a great deal. Showing WHICH rule refused it is the whole
    problem, and the two obvious approaches both fail:

      - MATCH THE ERROR TEXT. Couples every conformance test to the prose of a
        message, so rewording a message silently breaks attribution, and
        rewording it *wrongly* silently repairs it. A test that passes because
        of a sentence is not evidence about a rule.

      - RE-IMPLEMENT EACH RULE AS A STANDALONE PREDICATE. That is the same
        logic written twice (Law 14) with two owners (INV-10). The copies drift,
        and the copy that drifts is the one nobody runs against real payloads.

    Problem transformed (Law 53). Attribution does not have to be read out of
    the failure — it can be built into the input. A `NegativeControl` carries
    TWO payloads that differ in exactly one thing: the prohibition under test.

        clean    → must CONSTRUCT
        violating → must be REFUSED

    If both hold, the difference between them is what was refused, and the
    difference is the prohibition. Nothing is parsed and nothing is duplicated.

WHY THE CLEAN HALF IS NOT OPTIONAL, AND IS THE POINT.
    A control whose `clean` payload also fails proves nothing: the artifact was
    refused for some other defect and the rule under test was never reached. A
    suite of such controls is all green and all worthless — the false-green
    §J exists to prevent, arriving through the front door.

    So a failing `clean` is reported as `CONTROL_INVALID`, loudly, and is NOT a
    pass. It is an accusation against the test, not against the code.

WHAT THIS LAYER DELIBERATELY CANNOT DO.
    A `REVIEW_ONLY` prohibition constrains a CALLER's behaviour, not a value —
    *"never reason harder to raise confidence"* has no artifact that could
    witness it, because the artifact looks identical either way. No pure
    function decides these, and pretending otherwise would be the worst outcome
    available: a green suite implying coverage that does not exist.

    They are therefore listed, not tested, and each one MUST name the phase at
    which it stops being review-only. A review-only entry with no expiry is
    refused by `Registry`, because an exemption with no end date is a deletion
    written politely.

A REFUSAL AND A CRASH ARE NOT THE SAME EVENT.
    `attribute` used to treat ANY exception out of the violating payload as
    proof of enforcement. Measured, not argued: deleting the missing-score
    branch of `evidence.py` left the next line reaching into a dict that no
    longer had the key, and the conformance suite reported

        ENGINE_1:245/every-reading-carries-its-confidence -> enforced
        :: refused by KeyError                                  GATE: GREEN

    The enforcement was gone and the gate applauded. A crash inside a validator
    and a deliberate refusal are different events with opposite meanings, and
    reading one as the other is the false green in its purest form.

    So a control DECLARES what a refusal of its payload looks like — `refusal`,
    a tuple of exception types. Anything outside that set is `CONTROL_CRASHED`,
    which is not a pass. `conformance_registry` declares `ValidationError` for
    every one of its controls, so the deletion above now goes RED.

WHAT `refusal` DOES NOT CLOSE, MEASURED AND WRITTEN DOWN RATHER THAN IMPLIED.
    It separates a CRASH from a refusal. It does not separate a refusal for the
    RIGHT reason from a refusal for the wrong one. A violating builder with a
    typo'd override key is refused by `extra="forbid"` and still reports

        invented -> enforced :: refused by ValidationError

    because a mistyped key and a deliberately forbidden field are the same event
    to an exception type. Distinguishing them needs each control to declare the
    validation error it expects — pydantic's `errors()[i]["type"]`, which is an
    API constant and not prose, so it does not reintroduce the error-text
    coupling this module rejects above. Across the 47 live controls those types
    are 30 `value_error`, 6 `frozen_instance`, 5 `extra_forbidden`, 2
    `string_too_short`, 2 `missing`, 1 `too_short`, 1 `enum` — measured, not
    estimated. Not built here: it is a per-control declaration across all 47 and
    a wider change than the crash defect this fix was scoped to.

WHY `refusal` STILL DEFAULTS TO `(Exception,)`.
    Because narrowing it by fiat would silently reclassify every control anyone
    ever wrote against this harness, including ones outside this repository, and
    a harness that changes the meaning of existing results on upgrade is worse
    than the defect it fixes (Law 33). The default is the OLD behaviour, stated
    out loud; the real inventory opts into the narrow one, and a test asserts
    that every control in it did — so forgetting is red, not quiet.

WHAT THE INVENTORY DOES NOT COVER IS ALSO INVENTORY.
    A rule absent from `PROHIBITIONS` is indistinguishable from a rule nobody
    ever wrote, and that is the most dangerous shape a registry can have: the
    omission is silent and the suite is green. `Exclusion` is the fix — every
    prohibition clause in `docs/` that carries no rule must be listed here with
    a reason, so a gap is a written sentence somebody can argue with rather than
    an empty space nobody can see. `NOT_YET_A_PREDICATE` exclusions carry an
    expiry for the same reason review-only entries do.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

#: A prohibition that is enforced structurally carries no expiry; one that is
#: only reviewed must name the phase at which it becomes a predicate.
PHASES = frozenset({"P3", "P4", "P5", "P6"})


class Enforcement(StrEnum):
    """How a prohibition is held. There is no third option, on purpose."""

    #: A pure function decides it, against an artifact's structure or values.
    #: No AI, no ground truth, no network, no clock.
    PREDICATE = "predicate"
    #: No pure function can decide it — it constrains a caller's reasoning, or
    #: needs a judgement the artifact does not carry. Listed, never faked.
    REVIEW_ONLY = "review only"


class Attribution(StrEnum):
    """What a negative control established. Only one of these is a pass."""

    #: The clean payload built, the violating payload was refused. The rule is
    #: enforced and this control is what proves it.
    ENFORCED = "enforced"
    #: The violating payload was accepted. The prohibition is not enforced.
    NOT_ENFORCED = "not enforced"
    #: The clean payload was ALSO refused, so the violating payload's rejection
    #: cannot be attributed to this rule. The control is wrong, not the code.
    CONTROL_INVALID = "control invalid"
    #: Something raised that is NOT how this payload gets refused — a validator
    #: reaching into a missing key, a builder calling a name that moved, a
    #: helper renamed under it. The rule was never reached, so nothing was
    #: established either way. See "A REFUSAL AND A CRASH" in the module
    #: docstring: this state exists because its absence read as `ENFORCED`.
    CONTROL_CRASHED = "control crashed"


class Uncovered(StrEnum):
    """Why a prohibition clause in `docs/` carries no rule of its own.

    Four reasons, and the difference between them decides whether anybody owes
    work. Anything that is none of them is not an exclusion — it is an omission,
    and an omission is what this whole mechanism exists to make impossible.
    """

    #: The line states no prohibition: a section heading, a table header row, or
    #: a sentence about the rules rather than a rule. The marker matched a
    #: label. The reason must say which, and must name anything the label hides.
    NOT_A_PROHIBITION = "not a prohibition"
    #: The same thing, about the same artifact, as a rule already in the
    #: inventory — written again at a second line. `restates` names that rule,
    #: and `Registry` refuses an identifier that is not in the inventory, so
    #: this claim is checked rather than believed.
    RESTATEMENT = "restatement"
    #: A real rule that no artifact could carry the difference for. The payload
    #: looks identical whether or not it was obeyed, so no pure function decides
    #: it and no control could be written. Permanent; carries no expiry.
    UNWITNESSABLE = "unwitnessable"
    #: A real rule, witnessable, and nothing enforces it. A named, dated debt —
    #: never a pass — and it MUST name the phase by which it stops being one.
    NOT_YET_A_PREDICATE = "not yet a predicate"


def _must_name_a_line(source: str, what: str) -> None:
    """`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:467`, not a bare file.

    Shared by `Prohibition` and `Exclusion` rather than written twice (Law 14):
    a citation that cannot be re-checked is the same defect in both, and two
    copies of the rule would eventually disagree about what a citation is.
    """
    if ":" not in source:
        raise ValueError(
            f"source {source!r} must name a line, as `path:line`; a "
            f"{what} attributed to a whole document cannot be re-checked"
        )


@dataclass(frozen=True, slots=True)
class Prohibition:
    """One rule, quoted from the document that states it.

    `quote` and `source` are not decoration. A prohibition recorded without the
    line it came from cannot be re-checked when the document changes, and an
    inventory that cannot be re-checked stops describing the system the moment
    anyone edits a spec.
    """

    identifier: str
    quote: str
    source: str
    subject: str
    enforcement: Enforcement
    #: Required for REVIEW_ONLY, forbidden for PREDICATE. See `Registry`.
    expiry: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("identifier", self.identifier),
            ("quote", self.quote),
            ("source", self.source),
            ("subject", self.subject),
        ):
            if not value.strip():
                raise ValueError(f"a prohibition needs a {name}")
        if ":" not in self.source:
            # `docs/ENGINE_5_VALIDATION_ENGINE_RULES.md:467`, not a bare file.
            raise ValueError(
                f"source {self.source!r} must name a line, as `path:line`; a "
                "prohibition attributed to a whole document cannot be re-checked"
            )
        if self.enforcement is Enforcement.REVIEW_ONLY:
            if self.expiry is None:
                raise ValueError(
                    f"{self.identifier}: a review-only prohibition must name the "
                    "phase at which it becomes a predicate. An exemption with no "
                    "end date is a deletion written politely."
                )
            if self.expiry not in PHASES:
                raise ValueError(
                    f"{self.identifier}: expiry {self.expiry!r} is not a phase; "
                    f"expected one of {sorted(PHASES)}"
                )
        elif self.expiry is not None:
            raise ValueError(
                f"{self.identifier}: a predicate is enforced now and cannot carry "
                f"an expiry, got {self.expiry!r}"
            )


@dataclass(frozen=True, slots=True)
class NegativeControl:
    """Two payloads differing in exactly one prohibition.

    `clean` and `violating` are callables rather than values because building
    the violating one is expected to raise, and a raise at import time would
    take the whole suite down before anything ran.
    """

    prohibition: str
    #: Builds a payload that breaks ONLY the named prohibition.
    violating: Callable[[], object]
    #: Builds the same payload with that one violation removed. Must succeed.
    clean: Callable[[], object]


@dataclass(frozen=True, slots=True)
class Finding:
    """What one control established, and enough detail to act on it."""

    prohibition: str
    attribution: Attribution
    detail: str

    @property
    def is_pass(self) -> bool:
        return self.attribution is Attribution.ENFORCED


def attribute(control: NegativeControl) -> Finding:
    """Run one control. The clean half is checked FIRST, and that order matters.

    Checking `violating` first and `clean` second would let a broken control
    report a rejection it did not cause, which is precisely the attribution
    error this whole module exists to prevent.
    """
    try:
        control.clean()
    # Broad on purpose: a control is invalidated by ANY refusal, not only a
    # ValidationError. A narrower catch here would let an unrelated TypeError
    # through as a pass, which is the false green this module exists to stop.
    except Exception as refused:
        return Finding(
            control.prohibition,
            Attribution.CONTROL_INVALID,
            f"the clean payload was refused too, so a rejection cannot be "
            f"attributed to this rule: {type(refused).__name__}: {refused}",
        )

    try:
        control.violating()
    # Broad for the same reason: the enforcement is the refusal, whatever
    # raised it. Insisting on ValidationError would silently exempt any rule
    # enforced by a plain TypeError from a frozen dataclass.
    except Exception as refused:
        return Finding(
            control.prohibition,
            Attribution.ENFORCED,
            f"refused by {type(refused).__name__}",
        )
    return Finding(
        control.prohibition,
        Attribution.NOT_ENFORCED,
        "the violating payload was accepted; nothing enforces this prohibition",
    )


class Registry:
    """The inventory, and the proof that it is complete.

    Two completeness rules, both refusing rather than warning:

      - every PREDICATE has at least one negative control. A rule declared
        enforced with nothing exercising it is a claim, not an enforcement.
      - every REVIEW_ONLY has NO control and an expiry. A control against a
        review-only rule means one of the two labels is wrong.
    """

    def __init__(
        self, prohibitions: Iterable[Prohibition], controls: Iterable[NegativeControl]
    ) -> None:
        self._prohibitions = tuple(prohibitions)
        self._controls = tuple(controls)

        seen: set[str] = set()
        for prohibition in self._prohibitions:
            if prohibition.identifier in seen:
                raise ValueError(
                    f"two prohibitions share the identifier {prohibition.identifier!r}; "
                    "attribution would name a rule that is not unique"
                )
            seen.add(prohibition.identifier)

        known = {prohibition.identifier: prohibition for prohibition in self._prohibitions}
        for control in self._controls:
            if control.prohibition not in known:
                raise ValueError(
                    f"a control names {control.prohibition!r}, which is not in the "
                    "inventory; a control for an unlisted rule proves nothing about "
                    "the specification"
                )
            if known[control.prohibition].enforcement is Enforcement.REVIEW_ONLY:
                raise ValueError(
                    f"{control.prohibition!r} is listed review-only but has a negative "
                    "control. One of the two is wrong — either it is testable and "
                    "should be a predicate, or the control does not test it."
                )

    @property
    def prohibitions(self) -> tuple[Prohibition, ...]:
        return self._prohibitions

    @property
    def controls(self) -> tuple[NegativeControl, ...]:
        return self._controls

    def by_enforcement(self, enforcement: Enforcement) -> tuple[Prohibition, ...]:
        return tuple(item for item in self._prohibitions if item.enforcement is enforcement)

    def untested_predicates(self) -> tuple[str, ...]:
        """Predicates with no negative control. Must be empty for P2 to be done."""
        controlled = {control.prohibition for control in self._controls}
        return tuple(
            sorted(
                item.identifier
                for item in self.by_enforcement(Enforcement.PREDICATE)
                if item.identifier not in controlled
            )
        )

    def run(self) -> tuple[Finding, ...]:
        """Every control, in inventory order. Order is stable so a diff of two
        runs is readable."""
        return tuple(attribute(control) for control in self._controls)

    def failures(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.run() if not finding.is_pass)
