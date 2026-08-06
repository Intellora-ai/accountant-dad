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

import uuid
from decimal import Decimal
from typing import NamedTuple, cast

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

#: The identifiers `SEED` mints, in the order the fields are visited. They do
#: NOT depend on the originals: `_substitute` hands every unseen identifier the
#: next draw from `random.Random(seed)`, so a given seed and a given artifact
#: SHAPE always mint these exact values.
#:
#: Pinned by value rather than by "it changed", because "it changed" is true of
#: `None` as well. Substitution that mints a non-UUID, a v5 UUID, or a UUID with
#: no version bits at all still changes every identifier, and a harness whose
#: replacements are not themselves valid opaque identifiers is producing an
#: object the system could never make (INV-9's stated reason for UUIDv4).
FIRST_MINTED = uuid.UUID("87f27014-3dbc-4f6f-a45a-75bbdde5c48c")
SECOND_MINTED = uuid.UUID("cd6aa652-1048-48c3-9bfc-7c2da17e50c5")
THIRD_MINTED = uuid.UUID("5fb02196-a7e7-4fb8-8199-a09d4d3c304c")

#: How many consecutive seeds the "every minted id is a real v4" check sweeps.
#: One seed is not evidence: a substitution that never sets the version bits
#: lands on 4 by luck one time in sixteen.
SEED_SWEEP = 12

#: identity.py's choice, and the reason it gave: a v4 UUID encodes nothing an
#: engine could read out of it (INV-9). A replacement of any other version
#: would not carry that property.
RANDOM_UUID_VERSION = 4

#: `ablate` derives the outcome once from the original, then once per trial.
BASELINE_PLUS_ONE_TRIAL = 2


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


def test_the_minted_identifiers_are_pinned_value_for_value() -> None:
    """`!=` the original is not enough — `None` satisfies it.

    Asserting only that an identifier CHANGED clears a substitution that
    replaced it with nothing at all, and the object then carries a hole where
    an identifier belongs. These are the exact values `SEED` mints; they are a
    property of the seed and the field order, not of the originals, which is
    what makes the harness reproducible enough to cite as evidence (Law 44).

    If this test fails, the mint changed. Read the new values and decide whether
    the change was intended — do NOT relax the assertion to make it pass.
    """
    after = substitute_identifiers(payload(), seed=SEED)
    assert after.envelope.artifact_id == ArtifactId(FIRST_MINTED)
    assert after.envelope.transaction_id == TransactionId(SECOND_MINTED)


def test_a_nested_identifier_is_minted_from_the_same_sequence() -> None:
    """The parent's ID takes the SECOND draw, which pins the visit order too.

    A substitution that skipped the nested identifier would still change the
    top-level ones — and would shift every later draw, so the transaction ID
    would not land on the third value either.
    """
    after = substitute_identifiers(with_parents(), seed=SEED)
    assert after.envelope.artifact_id == ArtifactId(FIRST_MINTED)
    assert after.envelope.parent_versions[0].artifact_id == ArtifactId(SECOND_MINTED)
    assert after.envelope.transaction_id == TransactionId(THIRD_MINTED)


@pytest.mark.parametrize("seed", range(SEED, SEED + SEED_SWEEP))
def test_every_minted_identifier_is_a_v4_uuid_that_encodes_nothing(seed: int) -> None:
    """identity.py chose UUIDv4 so that an identifier encodes NOTHING an engine
    could read (INV-9). A replacement that is not a v4 UUID breaks that property
    for the ablated object, and the ablated object is the one the experiment
    draws its conclusion from.
    """
    after = substitute_identifiers(with_parents(), seed=seed)
    minted = (
        after.envelope.artifact_id.value,
        after.envelope.parent_versions[0].artifact_id.value,
        after.envelope.transaction_id.value,
    )
    assert len(set(minted)) == len(minted), "two identifiers were minted to the same value"
    for identifier in minted:
        assert identifier.version == RANDOM_UUID_VERSION
        assert identifier.variant == uuid.RFC_4122


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


#: Identifiers the artifact does not carry. Nothing substitutes them, so the
#: mapping has no entry for either, and `_remap` must hand them back UNCHANGED.
#: A remap that returns `None` for an unknown identifier would invent a
#: difference and report a leak in a function that read no identifier at all —
#: a false accusation, which is the second way this harness can be worthless.
UNMAPPED_TRANSACTION = TransactionId(uuid.UUID("11111111-1111-4111-8111-111111111111"))
UNMAPPED_ARTIFACT = ArtifactId(uuid.UUID("22222222-2222-4222-8222-222222222222"))


def carries_identifiers_forward_inside_a_tuple(p: Payload) -> object:
    # A realistic audit outcome: some IDs the artifact carries, some it does
    # not, and a piece of content. The comparison is modulo the SAME mapping,
    # so all five must survive it.
    return (
        p.envelope.transaction_id,
        p.envelope.artifact_id,
        UNMAPPED_TRANSACTION,
        UNMAPPED_ARTIFACT,
        p.narration,
    )


def test_a_tuple_of_carried_identifiers_is_not_reported_as_a_leak() -> None:
    """An outcome that is a TUPLE has to be remapped element by element.

    Every earlier test derives a scalar, so the tuple branch of the mapping was
    never exercised and a remap that dropped its elements, lost the mapping, or
    substituted the wrong argument produced a leak nobody was looking at.
    """
    assert ablate(payload(), carries_identifiers_forward_inside_a_tuple, seed=SEED) == []


def returns_only_identifiers_the_artifact_never_carried(_artifact: Payload) -> object:
    return (UNMAPPED_TRANSACTION, UNMAPPED_ARTIFACT)


def test_an_identifier_the_artifact_never_carried_maps_to_itself() -> None:
    """Stated on its own, because it is the case the mapping has no entry for.

    `_remap` defaults an unknown identifier to ITSELF. Defaulting it to `None`
    would make every outcome that mentions an unrelated ID look like a leak.
    """
    assert ablate(payload(), returns_only_identifiers_the_artifact_never_carried, seed=SEED) == []


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


def test_exactly_one_trial_is_a_legal_run_and_is_actually_executed() -> None:
    """One is the boundary the refusal above sits against, and it is INSIDE.

    The refusal exists to stop a run that looks at nothing. `trials=1` looks at
    something, so it must run. A guard that rejected it would turn the smallest
    honest ablation into an error, and the boundary would be untested from the
    legal side — which is how an off-by-one survives.
    """
    seen: list[object] = []

    def record(p: Payload) -> object:
        seen.append(p.envelope.transaction_id)
        return p.amount

    assert ablate(payload(), record, seed=SEED, trials=1) == []
    assert len(seen) == BASELINE_PLUS_ONE_TRIAL


def echoes_the_transaction_id_as_text(p: Payload) -> object:
    # Returns the identifier as a plain `str`. `_remap` maps identifier TYPES,
    # so text is left alone and the outcome cannot survive the comparison - it
    # leaks on every trial, deterministically, and the reported text names
    # exactly which substitution produced it.
    return str(p.envelope.transaction_id.value)


def test_trial_n_substitutes_with_seed_plus_n() -> None:
    """The whole run must be reproducible from `seed` alone, trial by trial.

    "Deterministic" is only worth something if the mapping from `seed` to each
    trial's substitution is fixed and known. Re-seeding from the clock, or
    walking the seed the other way, still yields a stable-looking list of leaks
    - so the assertion has to name the substitution each trial used, not merely
    observe that leaks appeared.
    """
    artifact = payload()
    leaks = ablate(artifact, echoes_the_transaction_id_as_text, seed=SEED, trials=3)

    assert [leak.trial for leak in leaks] == [1, 2, 3]
    for leak in leaks:
        expected = substitute_identifiers(artifact, seed=SEED + leak.trial)
        assert leak.before == repr(str(artifact.envelope.transaction_id.value))
        assert leak.after == repr(str(expected.envelope.transaction_id.value))


def test_the_leak_report_is_pinned_field_for_field() -> None:
    """`before` and `after` ARE the report. A `Leak` whose two outcomes are
    `None` still counts as a leak, still has a truthy list, and tells an
    engineer nothing about which branch produced it."""
    artifact = payload()
    leaks = ablate(artifact, echoes_the_transaction_id_as_text, seed=SEED, trials=1)
    ablated = substitute_identifiers(artifact, seed=SEED + 1)

    assert leaks == [
        Leak(
            trial=1,
            before=repr(str(artifact.envelope.transaction_id.value)),
            after=repr(str(ablated.envelope.transaction_id.value)),
        )
    ]


# ── a caller that is not handing over a model is told so, by name ────────────


class NotAModel(NamedTuple):
    """A tuple carrying an identifier, offered where a model is required.

    `substitute_identifiers` and `ablate` are typed for `BaseModel`, and nothing
    at runtime enforces it. `_substitute` returns a PLAIN tuple for anything
    tuple-shaped, so this comes back as a different type than it went in as -
    the exact condition both functions guard against.
    """

    transaction_id: TransactionId


def ignores_the_artifact_entirely(_artifact: Payload) -> object:
    return "constant"


TYPE_CHANGED = "substitution changed the type: tuple"


def test_substitution_that_changes_the_type_is_refused_and_names_the_type() -> None:
    """Loud, and specific about WHAT came back (Law 11).

    Returning the plain tuple would hand the caller an object that is not the
    artifact it passed, and every later assertion about "the ablated artifact"
    would be about something else. The guard is only useful if its message names
    the type that arrived, so the caller can see which conversion happened.
    """
    lying_caller = cast(Payload, NotAModel(TransactionId.new()))
    with pytest.raises(TypeError) as raised:
        substitute_identifiers(lying_caller, seed=SEED)
    assert str(raised.value) == TYPE_CHANGED


def test_ablate_makes_the_same_refusal_inside_the_trial_loop() -> None:
    """`ablate` re-checks per trial rather than trusting the caller's first
    call, and its own guard has its own message. Both are asserted, because a
    guard whose message says nothing is a guard nobody can act on."""
    lying_caller = cast(Payload, NotAModel(TransactionId.new()))
    with pytest.raises(TypeError) as raised:
        ablate(lying_caller, ignores_the_artifact_entirely, seed=SEED)
    assert str(raised.value) == TYPE_CHANGED
