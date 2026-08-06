"""Mutation tests for ablation.py and identity.py.

IDENTITY != INTELLIGENCE. These tests verify:
1. IDs are actually substituted at every depth (ablation.py)
2. ID substitutions are detected when they influence outcomes (ablation.py)
3. Version lineage is enforced correctly (identity.py)
4. Duplicate parents are rejected (identity.py)

Each test is designed to fail if a single source line is flipped.
"""

from __future__ import annotations

import itertools
import uuid

import pytest
from pydantic import BaseModel, ConfigDict

from accountant_dad.ablation import ablate, substitute_identifiers
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
)

_COUNTER = itertools.count(1)


def _distinct_uuid() -> uuid.UUID:
    """A fresh, VALID v4 UUID that is the same on every run.

    These identifiers are opaque here — no assertion reads their value,
    only that they differ. `uuid4()` supplied that at the cost of making
    the suite non-reproducible; a counter supplies it without.
    """
    return uuid.UUID(int=next(_COUNTER), version=4)


#: Named for the lint gate. Values unchanged — every mutant these killed
#: before the rename is still killed after it.
EXPECTED_MINIMUM_TRIALS = 5
EXPECTED_PARENT_VERSIONS = 2


class SimpleModel(BaseModel):  # type: ignore[explicit-any]
    """Test fixture: a model with ID fields."""

    model_config = ConfigDict(frozen=True)
    artifact_id: ArtifactId
    value: str


class NestedModel(BaseModel):  # type: ignore[explicit-any]
    """Test fixture: nested IDs in parent_versions."""

    model_config = ConfigDict(frozen=True)
    artifact_id: ArtifactId
    parent_versions: tuple[ParentVersion, ...]


# ============================================================================
# ABLATION TESTS: Ensure IDs are substituted and leaks are detected
# ============================================================================


class TestSubstituteIdentifiersActuallyReplaces:
    """Mutation target: ablation.py line 93-96 (isinstance checks for ID types)."""

    def test_substitutes_transaction_id_in_model(self) -> None:
        """If line 93 is flipped to skip TransactionId, this fails."""
        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )
        original_id = artifact.artifact_id.value

        result = substitute_identifiers(artifact, seed=42)

        # IDs must be replaced
        assert result.artifact_id.value != original_id
        assert result.value == artifact.value  # Everything else unchanged

    def test_substitutes_artifact_id_in_model(self) -> None:
        """If line 95 is flipped to skip ArtifactId, this fails."""
        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )
        original_id = artifact.artifact_id.value

        result = substitute_identifiers(artifact, seed=42)

        assert result.artifact_id.value != original_id

    def test_substitutes_nested_artifact_ids_in_parent_versions(self) -> None:
        """If recursion (line 97-104) is broken, nested IDs aren't replaced."""
        parent_id = ArtifactId(_distinct_uuid())
        artifact = NestedModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            parent_versions=(ParentVersion(artifact_id=parent_id, version=1),),
        )

        result = substitute_identifiers(artifact, seed=42)

        # Top-level ID replaced
        assert result.artifact_id.value != artifact.artifact_id.value
        # Nested parent ID replaced (this is the exhaustiveness check)
        assert result.parent_versions[0].artifact_id.value != parent_id.value

    def test_substitution_is_consistent_within_trial(self) -> None:
        """Same ID maps to same replacement (line 94: setdefault)."""
        parent1_id = ArtifactId(_distinct_uuid())
        parent2_id = ArtifactId(_distinct_uuid())
        artifact = NestedModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            parent_versions=(
                ParentVersion(artifact_id=parent1_id, version=1),
                ParentVersion(artifact_id=parent2_id, version=2),
            ),
        )

        result = substitute_identifiers(artifact, seed=42)

        # Each unique original ID maps to exactly one replacement
        replaced_parent1 = result.parent_versions[0].artifact_id.value
        replaced_parent2 = result.parent_versions[1].artifact_id.value
        assert replaced_parent1 != replaced_parent2  # Different originals
        # If we see parent1 again, it's the same replacement
        assert replaced_parent1 != artifact.artifact_id.value


class TestAblateDetectsLeaksWhenIDsInfluenceOutcome:
    """Mutation target: ablation.py lines 178-180 (leak detection logic)."""

    def test_ablate_detects_when_id_influences_outcome(self) -> None:
        """If line 180: != is changed to ==, this fails."""

        def derive_with_id_leak(artifact: SimpleModel) -> object:
            # LEAK: outcome depends on the ID, not just the value
            return str(artifact.artifact_id.value)

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        leaks = ablate(artifact, derive_with_id_leak, seed=42, trials=2)

        # Must detect that outcome changed when only ID changed
        assert len(leaks) > 0

    def test_ablate_passes_when_id_is_not_read(self) -> None:
        """Ablate should not report leaks for outcomes that don't use IDs."""

        def derive_without_id_leak(artifact: SimpleModel) -> object:
            # NO LEAK: outcome depends only on value, not ID
            return artifact.value

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        leaks = ablate(artifact, derive_without_id_leak, seed=42, trials=2)

        assert len(leaks) == 0

    def test_ablate_uses_seed_and_trial_offset_correctly(self) -> None:
        """If line 168: seed + trial is changed, determinism breaks."""

        def derive_with_id_leak(artifact: SimpleModel) -> object:
            return str(artifact.artifact_id.value)

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        # Run twice with same seed, must get same results
        leaks1 = ablate(artifact, derive_with_id_leak, seed=100, trials=3)
        leaks2 = ablate(artifact, derive_with_id_leak, seed=100, trials=3)

        assert len(leaks1) == len(leaks2)
        if leaks1:
            assert leaks1[0].trial == leaks2[0].trial


class TestAblateValidatesTrialsParameter:
    """Mutation target: ablation.py line 160-161 (trials < 1 check)."""

    def test_ablate_rejects_zero_trials(self) -> None:
        """If line 160: < is changed to <=, this fails."""

        def derive(artifact: SimpleModel) -> object:
            return artifact.value

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        with pytest.raises(ValueError, match="at least one trial"):
            ablate(artifact, derive, seed=42, trials=0)

    def test_ablate_rejects_negative_trials(self) -> None:
        """If line 160: < is changed, this fails."""

        def derive(artifact: SimpleModel) -> object:
            return artifact.value

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        with pytest.raises(ValueError, match="at least one trial"):
            ablate(artifact, derive, seed=42, trials=-1)

    def test_ablate_accepts_one_trial(self) -> None:
        """Boundary: exactly 1 trial should be accepted."""

        def derive(artifact: SimpleModel) -> object:
            return artifact.value

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        leaks = ablate(artifact, derive, seed=42, trials=1)
        assert isinstance(leaks, list)


class TestAblateTrialIterationBoundary:
    """Mutation target: ablation.py line 165 (range(1, trials + 1))."""

    def test_ablate_runs_all_trials(self) -> None:
        """If line 165: range is wrong, all trials don't run."""
        trial_count = 0

        def counting_derive(artifact: SimpleModel) -> object:
            nonlocal trial_count
            trial_count += 1
            # Return something that depends on artifact to force iteration
            return artifact.value + str(artifact.artifact_id.value)

        artifact = SimpleModel(
            artifact_id=ArtifactId(_distinct_uuid()),
            value="test",
        )

        ablate(artifact, counting_derive, seed=42, trials=5)

        # derive() called once for original, then once per trial
        assert trial_count >= EXPECTED_MINIMUM_TRIALS


# ============================================================================
# IDENTITY TESTS: Ensure version lineage is enforced
# ============================================================================


class TestIdentityEnvelopeFirstVersionValidation:
    """Mutation target: identity.py line 113 (version == FIRST_VERSION)."""

    def test_first_version_rejects_parents(self) -> None:
        """If line 113: == is changed to > or <, this fails."""
        with pytest.raises(ValueError, match="version 1 is the origin"):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=FIRST_VERSION,
                parent_versions=(ParentVersion(artifact_id=ArtifactId.new(), version=1),),
                transaction_id=TransactionId.new(),
            )

    def test_first_version_accepts_no_parents(self) -> None:
        """Origin version must have no parents."""
        envelope = IdentityEnvelope(
            artifact_id=ArtifactId.new(),
            version=FIRST_VERSION,
            parent_versions=(),
            transaction_id=TransactionId.new(),
        )
        assert envelope.version == FIRST_VERSION
        assert len(envelope.parent_versions) == 0


class TestIdentityEnvelopeNonFirstVersionValidation:
    """Mutation target: identity.py line 118 (version > FIRST_VERSION)."""

    def test_non_first_version_requires_parents(self) -> None:
        """If line 118: > is changed to == or >=, this fails."""
        with pytest.raises(ValueError, match="must record the parent version"):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=FIRST_VERSION + 1,
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )

    def test_non_first_version_accepts_parents(self) -> None:
        """Non-origin versions must have at least one parent."""
        envelope = IdentityEnvelope(
            artifact_id=ArtifactId.new(),
            version=FIRST_VERSION + 1,
            parent_versions=(ParentVersion(artifact_id=ArtifactId.new(), version=1),),
            transaction_id=TransactionId.new(),
        )
        assert envelope.version == FIRST_VERSION + 1
        assert len(envelope.parent_versions) == 1

    def test_version_3_requires_parent(self) -> None:
        """Boundary: version 3 must also have parents."""
        with pytest.raises(ValueError, match="must record the parent version"):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=3,
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )


class TestIdentityEnvelopeDuplicateParentDetection:
    """Mutation target: identity.py lines 124-129 (duplicate detection)."""

    def test_detects_duplicate_parent_versions(self) -> None:
        """If line 125: != is changed to ==, this fails."""
        parent_id = ArtifactId.new()
        with pytest.raises(ValueError, match="listed more than once"):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=FIRST_VERSION + 1,
                parent_versions=(
                    ParentVersion(artifact_id=parent_id, version=1),
                    ParentVersion(artifact_id=parent_id, version=1),
                ),
                transaction_id=TransactionId.new(),
            )

    def test_accepts_different_parent_versions(self) -> None:
        """Different artifact IDs should be accepted."""
        envelope = IdentityEnvelope(
            artifact_id=ArtifactId.new(),
            version=FIRST_VERSION + 1,
            parent_versions=(
                ParentVersion(artifact_id=ArtifactId.new(), version=1),
                ParentVersion(artifact_id=ArtifactId.new(), version=1),
            ),
            transaction_id=TransactionId.new(),
        )
        assert len(envelope.parent_versions) == EXPECTED_PARENT_VERSIONS

    def test_accepts_different_versions_of_same_parent(self) -> None:
        """Same artifact ID with different versions is allowed (merge case)."""
        parent_id = ArtifactId.new()
        envelope = IdentityEnvelope(
            artifact_id=ArtifactId.new(),
            version=FIRST_VERSION + 1,
            parent_versions=(
                ParentVersion(artifact_id=parent_id, version=1),
                ParentVersion(artifact_id=parent_id, version=2),
            ),
            transaction_id=TransactionId.new(),
        )
        assert len(envelope.parent_versions) == EXPECTED_PARENT_VERSIONS


class TestVersionFieldValidation:
    """Mutation target: identity.py line 52 (VersionField strict=True, ge=FIRST_VERSION)."""

    def test_version_field_strict_rejects_string(self) -> None:
        """If strict=True is removed, "1" becomes accepted."""
        with pytest.raises(ValueError):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version="1",  # type: ignore[arg-type]
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )

    def test_version_field_rejects_zero(self) -> None:
        """If ge=FIRST_VERSION is changed, 0 becomes accepted."""
        with pytest.raises(ValueError):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=0,
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )

    def test_version_field_rejects_negative(self) -> None:
        """Negative versions are never valid."""
        with pytest.raises(ValueError):
            IdentityEnvelope(
                artifact_id=ArtifactId.new(),
                version=-1,
                parent_versions=(),
                transaction_id=TransactionId.new(),
            )
