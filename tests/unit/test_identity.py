"""The identity envelope every canonical artifact carries.

Three concepts, three jobs (INV-3):

    Artifact ID              identifies one artifact
    Parent Artifact Version  identifies versions of the same artifact
    Transaction ID           identifies one business event, whole lifecycle

Written before the implementation. Every test names the invariant it defends,
and the dangerous direction is always the permissive one: a bug that lets an
identifier carry meaning, or lets an artifact be edited, is worse than a bug
that rejects something valid.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from accountant_dad.identity import (
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
    Version,
)

FIRST_VERSION = 1
SECOND_VERSION = 2


def txn() -> TransactionId:
    return TransactionId(uuid.uuid4())


def art() -> ArtifactId:
    return ArtifactId(uuid.uuid4())


def envelope(**overrides: object) -> IdentityEnvelope:
    base: dict[str, object] = {
        "artifact_id": art(),
        "version": Version(FIRST_VERSION),
        "parent_versions": (),
        "transaction_id": txn(),
    }
    base.update(overrides)
    return IdentityEnvelope(**base)  # type: ignore[arg-type]


# ── INV-9 — IDENTITY != INTELLIGENCE ─────────────────────────────────────────


def test_a_transaction_id_is_a_uuid4_and_carries_no_embedded_meaning() -> None:
    # UUIDv4 was chosen over ULID and over a prefixed sequence precisely because
    # it encodes nothing: no time, no order, no source. Opacity is then a
    # property of the type, not a rule someone has to remember.
    value = TransactionId.new()
    assert value.value.version == 4  # noqa: PLR2004 - 4 IS the RFC 4122 version


def test_two_transaction_ids_made_in_order_do_not_compare_as_ordered() -> None:
    # The ULID failure mode, asserted directly. If IDs sorted by creation time,
    # an engine could read order out of an identifier - which is the exact thing
    # INV-9 forbids influencing a decision.
    made = [TransactionId.new() for _ in range(50)]
    assert sorted(made, key=lambda t: str(t.value)) != made


def test_an_artifact_id_and_a_transaction_id_are_not_interchangeable() -> None:
    # Same underlying UUID, different concepts. If one could be passed where the
    # other is expected, INV-3's separation is decorative.
    shared = uuid.uuid4()
    with pytest.raises(ValidationError):
        envelope(artifact_id=TransactionId(shared))
    with pytest.raises(ValidationError):
        envelope(transaction_id=ArtifactId(shared))


# ── INV-3 — exactly one Transaction ID per artifact ──────────────────────────


def test_an_envelope_without_a_transaction_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentityEnvelope(  # type: ignore[call-arg]
            artifact_id=art(), version=Version(FIRST_VERSION), parent_versions=()
        )


def test_the_transaction_id_is_carried_verbatim_not_regenerated() -> None:
    # "Generated exactly once, when a business event is first recognised. It
    # never changes." An envelope that minted its own would break the chain
    # silently, and every downstream trace with it.
    shared = TransactionId.new()
    assert envelope(transaction_id=shared).transaction_id == shared


# ── INV-5 — history is never modified ────────────────────────────────────────


def test_an_envelope_cannot_be_mutated_after_creation() -> None:
    made = envelope()
    with pytest.raises(ValidationError):
        made.version = Version(SECOND_VERSION)


def test_parent_versions_cannot_be_mutated_after_creation() -> None:
    # A tuple, not a list, and on purpose: a list would let a caller append a
    # parent to a frozen artifact's lineage without the model ever noticing.
    made = envelope()
    assert isinstance(made.parent_versions, tuple)
    with pytest.raises(AttributeError):
        made.parent_versions.append(None)  # type: ignore[attr-defined]


@pytest.mark.parametrize("bad", [0, -1, -100])
def test_a_version_below_one_is_rejected(bad: int) -> None:
    # Versions start at 1. Zero would make "has no parent" ambiguous with
    # "unset", which is how a lineage gap becomes invisible.
    with pytest.raises(ValidationError):
        envelope(version=bad)


def test_the_first_version_has_no_parents() -> None:
    assert envelope(version=Version(FIRST_VERSION), parent_versions=()).parent_versions == ()


def test_a_first_version_that_claims_a_parent_is_rejected() -> None:
    # Version 1 is the origin. A parent here means the chain is lying about
    # where it started, and every trace back through it is wrong.
    with pytest.raises(ValidationError):
        envelope(
            version=Version(FIRST_VERSION),
            parent_versions=(ParentVersion(artifact_id=art(), version=Version(FIRST_VERSION)),),
        )


def test_a_later_version_with_no_parent_is_rejected() -> None:
    # "Each version records the exact parent versions it derived from." A
    # version 2 with no parent is an artifact that appeared from nowhere, and
    # it breaks "any artifact traces back to the raw artifact".
    with pytest.raises(ValidationError):
        envelope(version=Version(SECOND_VERSION), parent_versions=())


def test_a_later_version_records_the_exact_parent_it_derived_from() -> None:
    parent_of = art()
    made = envelope(
        artifact_id=parent_of,
        version=Version(SECOND_VERSION),
        parent_versions=(ParentVersion(artifact_id=parent_of, version=Version(FIRST_VERSION)),),
    )
    assert made.parent_versions[0].version == FIRST_VERSION


def test_a_duplicate_parent_version_is_rejected() -> None:
    # The same parent listed twice is not a merge, it is a bug. Accepting it
    # would make the lineage count meaningless.
    same = ParentVersion(artifact_id=art(), version=Version(FIRST_VERSION))
    with pytest.raises(ValidationError):
        envelope(version=Version(SECOND_VERSION), parent_versions=(same, same))


def test_several_distinct_parents_are_allowed() -> None:
    # INV-3: many Document Evidence Objects may contribute to one Business
    # Understanding Object. Multiple parents is the normal case there, not an
    # edge case, so it must not be rejected as one.
    parents = tuple(
        ParentVersion(artifact_id=art(), version=Version(FIRST_VERSION)) for _ in range(3)
    )
    made = envelope(version=Version(SECOND_VERSION), parent_versions=parents)
    assert len(made.parent_versions) == len(parents)
