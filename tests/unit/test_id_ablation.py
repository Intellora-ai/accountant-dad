"""INV-9 — IDENTITY != INTELLIGENCE, made checkable.

    IDs identify objects. They do not influence reasoning.

Ablation is the experiment that tests it: take an object, replace every
identifier, hold everything else constant, and prove the outcome is identical.
If swapping IDs changes any result, an identifier leaked into reasoning.

`MVP_IMPLEMENTATION_BLUEPRINT.md:135` makes "ID ablation test passes" part of
P2's definition of done.

The trap this file is written against: the naive ablation always passes and
therefore proves nothing. So the tests below spend most of their effort on the
harness's ability to FAIL — a leaking function it must catch, a shallow
substitution it must not settle for, and a legitimate traceability use it must
not falsely accuse.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict

from accountant_dad.ablation import Leak, ablate, substitute_identifiers
from accountant_dad.identity import (
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
    Version,
)

FIRST = 1
SECOND = 2
SEED = 20260803


class Payload(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any
    """A stand-in for an artifact: an envelope plus content that is not identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope: IdentityEnvelope
    amount: Decimal
    narration: str


def envelope(*, version: int = FIRST, parents: tuple[ParentVersion, ...] = ()) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId.new(),
        version=Version(version),
        parent_versions=parents,
        transaction_id=TransactionId.new(),
    )


def payload(**kw: object) -> Payload:
    return Payload(
        envelope=kw.get("envelope", envelope()),  # type: ignore[arg-type]
        amount=Decimal("1234.56"),
        narration="freight inward on invoice 7781",
    )


def with_parents() -> Payload:
    parent = ParentVersion(artifact_id=ArtifactId.new(), version=Version(FIRST))
    return payload(envelope=envelope(version=SECOND, parents=(parent,)))


# ── substitution is exhaustive, including nested identifiers ─────────────────


def test_every_top_level_identifier_is_replaced() -> None:
    before = payload()
    after = substitute_identifiers(before, seed=SEED)
    assert after.envelope.artifact_id != before.envelope.artifact_id
    assert after.envelope.transaction_id != before.envelope.transaction_id


def test_identifiers_nested_inside_parent_versions_are_replaced_too() -> None:
    # The failure a shallow harness hides. If nested IDs survive substitution,
    # a leak that reads a PARENT's id is invisible, and the harness reports a
    # confident pass over the exact case it was built to catch.
    before = with_parents()
    after = substitute_identifiers(before, seed=SEED)
    assert (
        after.envelope.parent_versions[0].artifact_id
        != before.envelope.parent_versions[0].artifact_id
    )


def test_nothing_that_is_not_an_identifier_is_touched() -> None:
    # Ablation is only evidence if IDs are the ONLY thing that changed.
    before = payload()
    after = substitute_identifiers(before, seed=SEED)
    assert after.amount == before.amount
    assert after.narration == before.narration
    assert after.envelope.version == before.envelope.version


def test_substitution_is_deterministic_for_a_given_seed() -> None:
    # CI reproducibility. An ablation that cannot be re-run identically cannot
    # be cited as evidence for a build.
    before = payload()
    assert substitute_identifiers(before, seed=SEED) == substitute_identifiers(before, seed=SEED)


def test_different_seeds_produce_different_substitutions() -> None:
    before = payload()
    a = substitute_identifiers(before, seed=SEED)
    b = substitute_identifiers(before, seed=SEED + 1)
    assert a.envelope.transaction_id != b.envelope.transaction_id


# ── the harness must PASS a function that ignores identifiers ────────────────


def sums_the_amount(p: Payload) -> object:
    return p.amount


def test_a_function_that_ignores_identifiers_survives_ablation() -> None:
    assert ablate(payload(), sums_the_amount, seed=SEED) == []


# ── the harness must CATCH a function that reads an identifier ───────────────


def leaks_the_transaction_id(p: Payload) -> object:
    # The canonical INV-9 violation, from DATA_FLOW.md:426 - a decision that
    # differs because of an identifier's value.
    return "even" if str(p.envelope.transaction_id.value)[0] in "02468ace" else "odd"


def test_a_function_whose_result_depends_on_an_identifier_is_caught() -> None:
    leaks = ablate(payload(), leaks_the_transaction_id, seed=SEED, trials=32)
    assert leaks, "a function branching on the transaction id must not survive ablation"
    assert isinstance(leaks[0], Leak)


def test_the_leak_report_names_the_before_and_after_outcome() -> None:
    # "Something changed" is not a usable report. An engineer needs to see the
    # two outcomes to find the branch that produced them.
    leaks = ablate(payload(), leaks_the_transaction_id, seed=SEED, trials=32)
    assert leaks[0].before != leaks[0].after


def leaks_a_parent_id(p: Payload) -> object:
    # Reads a NESTED identifier. Survives any harness that only swaps the top
    # level, which is why exhaustive substitution is load-bearing rather than
    # tidy.
    return str(p.envelope.parent_versions[0].artifact_id.value)[0]


def test_a_function_reading_a_nested_identifier_is_caught() -> None:
    assert ablate(with_parents(), leaks_a_parent_id, seed=SEED, trials=32)


# ── it must not falsely accuse legitimate traceability ──────────────────────


def returns_the_id_for_traceability(p: Payload) -> object:
    return p.envelope.transaction_id


def test_returning_an_identifier_verbatim_is_not_reported_as_a_leak() -> None:
    # INV-9 forbids an identifier INFLUENCING a decision, not appearing in one.
    # Traceability and audit history are its stated legitimate purposes. A
    # harness that flags this is unusable - every audit path would trip it.
    assert ablate(payload(), returns_the_id_for_traceability, seed=SEED) == []


def echoes_the_whole_artifact(p: Payload) -> object:
    return p


def test_echoing_the_artifact_is_not_reported_as_a_leak() -> None:
    assert ablate(payload(), echoes_the_whole_artifact, seed=SEED) == []


# ── trials must actually be run ──────────────────────────────────────────────


def test_more_trials_are_actually_executed() -> None:
    seen: list[object] = []

    def record(p: Payload) -> object:
        seen.append(p.envelope.transaction_id)
        return p.amount

    ablate(payload(), record, seed=SEED, trials=7)
    assert len(seen) == 7 + 1  # one baseline call, then one call per trial


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_trial_count_is_refused(bad: int) -> None:
    # Zero trials would ablate nothing and return [] - a green that means
    # "never looked". That is the false-pass this whole file exists to prevent.
    with pytest.raises(ValueError, match="at least one trial"):
        ablate(payload(), sums_the_amount, seed=SEED, trials=bad)
