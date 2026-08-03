"""The ID ablation harness. INV-9, turned from a rule into an experiment.

    IDENTITY != INTELLIGENCE. IDs identify objects. They do not influence
    reasoning. An identifier exists only for identity, traceability, lifecycle
    tracking and audit history. It must never influence ledger selection,
    journal creation, tax treatment, validation outcome, confidence, or any
    future decision.

`MVP_IMPLEMENTATION_BLUEPRINT.md:135` makes "ID ablation test passes" part of
P2's definition of done. This module is the instrument that test uses.

THE METHOD. Take an object and a function that derives some outcome from it.
Record the outcome. Then replace every identifier the object carries, at every
depth, hold everything else byte-identical, and derive the outcome again. If
the two outcomes differ, the function read an identifier, and INV-9 is broken.

WHY IT IS BUILT TO FAIL, NOT TO PASS. The naive version of this harness always
passes and therefore proves nothing - it is the classic false green. Three
properties are what make it evidence rather than decoration:

  EXHAUSTIVE   substitution reaches nested identifiers, not just top-level
               ones. A shallow swap silently exonerates any function that
               reads a PARENT's id, which is exactly the case a lineage-aware
               engine is most likely to get wrong.

  REPEATED     one substitution can collide by luck - a function branching on
               the first hex digit agrees with itself about 1 time in 16. A
               single trial would clear it 6% of the time. Trials are run
               until the disagreement shows or the budget is spent.

  DETERMINISTIC  seeded. An ablation that cannot be re-run identically cannot
               be cited as evidence for a build (Law 44).

WHAT IT CANNOT DETECT, stated plainly because an undocumented blind spot is a
false green:

  - A leak that maps EVERY identifier to the same outcome. If a function
    returns a constant derived from an id, ablation sees no change. Nothing
    black-box can distinguish that from a function ignoring the id.
  - A leak through a channel that is not this object - a global, a database
    read, a clock. Ablation substitutes what it is handed and nothing else.
  - Non-determinism in the function itself. A function that returns random
    output looks exactly like a leak. The report says outcomes differed; it
    does not say why, and a caller must rule this out separately.
  - Identifiers stored as bare strings rather than as `TransactionId` /
    `ArtifactId` / `ParentVersion`. Substitution is driven by TYPE. This is
    the strongest argument for those types existing at all, and the reason
    `identity.py` makes them distinct rather than aliases for `str`.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from accountant_dad.identity import ArtifactId, TransactionId

DEFAULT_TRIALS = 8


@dataclass(frozen=True, slots=True)
class Leak:
    """One ablation trial in which the outcome changed. INV-9 is broken."""

    trial: int
    before: str
    after: str

    def __str__(self) -> str:
        return (
            f"trial {self.trial}: outcome changed when only identifiers changed. "
            f"before={self.before!r} after={self.after!r}"
        )


def _deterministic_uuid(rng: random.Random) -> uuid.UUID:
    """A version-4 UUID drawn from a seeded source, so a run is reproducible."""
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _substitute(value: object, rng: random.Random, seen: dict[uuid.UUID, uuid.UUID]) -> object:
    """Replace identifiers at every depth. Leave everything else untouched.

    Recursion is the whole point. `IdentityEnvelope.parent_versions` holds
    `ParentVersion` models that each carry an `ArtifactId`, so a version that
    only looked at the top level would leave a real identifier in place and
    then report a clean pass.
    """
    if isinstance(value, TransactionId):
        return TransactionId(seen.setdefault(value.value, _deterministic_uuid(rng)))
    if isinstance(value, ArtifactId):
        return ArtifactId(seen.setdefault(value.value, _deterministic_uuid(rng)))
    if isinstance(value, BaseModel):
        swapped = {
            name: _substitute(getattr(value, name), rng, seen) for name in type(value).model_fields
        }
        # `model_construct` would skip validation and could build an artifact
        # the real constructor rejects, which would make the ablated object a
        # thing the system can never actually produce.
        return type(value)(**swapped)
    if isinstance(value, tuple):
        return tuple(_substitute(item, rng, seen) for item in value)
    return value


def substitute_identifiers[M: BaseModel](artifact: M, *, seed: int) -> M:
    """Return a copy of `artifact` with every identifier replaced, nothing else."""
    result, _ = _substituted_with_map(artifact, seed)
    if not isinstance(result, type(artifact)):
        raise TypeError(f"substitution changed the type: {type(result).__name__}")
    return result


def _substituted_with_map(artifact: object, seed: int) -> tuple[object, dict[uuid.UUID, uuid.UUID]]:
    """Substitute, and return the old-to-new mapping that was used.

    The mapping is what makes a legitimate use distinguishable from a leak.
    The same identifier appearing twice maps to the same replacement, so a
    function that merely CARRIES an identifier forward produces an outcome
    that is equal-after-mapping, while a function that BRANCHES on one
    produces an outcome that is not.
    """
    seen: dict[uuid.UUID, uuid.UUID] = {}
    rng = random.Random(seed)  # noqa: S311 - reproducibility, not secrecy
    return _substitute(artifact, rng, seen), seen


def _remap(value: object, mapping: dict[uuid.UUID, uuid.UUID]) -> object:
    """Apply an existing substitution mapping. Mint nothing new."""
    if isinstance(value, TransactionId):
        return TransactionId(mapping.get(value.value, value.value))
    if isinstance(value, ArtifactId):
        return ArtifactId(mapping.get(value.value, value.value))
    if isinstance(value, BaseModel):
        return type(value)(
            **{name: _remap(getattr(value, name), mapping) for name in type(value).model_fields}
        )
    if isinstance(value, tuple):
        return tuple(_remap(item, mapping) for item in value)
    return value


def ablate[M: BaseModel](
    artifact: M,
    derive: Callable[[M], object],
    *,
    seed: int,
    trials: int = DEFAULT_TRIALS,
) -> list[Leak]:
    """Run the experiment. An empty list means no leak was observed.

    "No leak observed" is deliberately weaker than "no leak exists" - see the
    blind spots in the module docstring. Overstating this would be the exact
    kind of unearned claim Law 24 forbids.
    """
    if trials < 1:
        raise ValueError(f"ablation needs at least one trial, got {trials}")

    original = derive(artifact)
    leaks: list[Leak] = []
    for trial in range(1, trials + 1):
        # Seed per trial, so trial N is reproducible on its own and the run as
        # a whole is reproducible from `seed` alone.
        ablated_artifact, mapping = _substituted_with_map(artifact, seed + trial)
        if not isinstance(ablated_artifact, type(artifact)):
            raise TypeError(f"substitution changed the type: {type(ablated_artifact).__name__}")

        # The comparison is modulo the SAME substitution. INV-9 forbids an
        # identifier INFLUENCING an outcome, not appearing in one - identity,
        # traceability and audit history are its stated legitimate purposes.
        # A function that carries an id forward yields an outcome that maps
        # exactly onto the ablated one; a function that branches on an id does
        # not, because its result is not made of identifiers at all.
        expected = repr(_remap(original, mapping))
        outcome = repr(derive(ablated_artifact))
        if outcome != expected:
            leaks.append(Leak(trial=trial, before=expected, after=outcome))
    return leaks
