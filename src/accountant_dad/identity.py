"""The identity envelope every canonical artifact carries.

`DATA_FLOW.md` §2: *"Every artifact carries an Artifact ID, a Version, its Parent
Artifact Version(s), and exactly one Transaction ID. The tables below list what
is distinctive to each artifact; the identity envelope is universal and not
repeated."* This module is that envelope, and nothing else.

Three invariants are structural here rather than remembered:

  INV-3  Transaction identity is separate from artifact identity.
         Three distinct types, not three strings. A Transaction ID cannot be
         passed where an Artifact ID belongs, because they are not the same
         type — not because a reviewer noticed.

  INV-5  History is never modified.
         Every model is frozen. Correction is a new version with its parents
         recorded, never an edit, so the chain always traces back to the raw
         artifact.

  INV-9  IDENTITY != INTELLIGENCE.
         UUIDv4, chosen over ULID and over a prefixed sequence. A ULID encodes
         its creation time and a sequence encodes its order — both are real
         information an engine could read out of an identifier, which is the
         precise thing INV-9 forbids from touching a decision. A v4 UUID
         encodes nothing, so opacity is a property of the value rather than a
         discipline anyone has to maintain.

The Application Layer creates the Transaction ID (INV-4). Engines consume it.
Nothing in this module knows what a transaction means, and that is deliberate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

FIRST_VERSION = 1

#: A version number. Starts at 1; there is no version 0. Zero would make
#: "this is the origin" indistinguishable from "nobody set this", which is
#: exactly how a gap in a lineage becomes invisible.
Version = int

VersionField = Annotated[int, Field(ge=FIRST_VERSION)]


@dataclass(frozen=True, slots=True)
class TransactionId:
    """One business event, for its entire lifecycle.

    Generated exactly once, when a business event is first recognised, and
    never changed. Every artifact references exactly one.
    """

    value: uuid.UUID

    @classmethod
    def new(cls) -> TransactionId:
        return cls(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class ArtifactId:
    """One artifact, across all of its versions."""

    value: uuid.UUID

    @classmethod
    def new(cls) -> ArtifactId:
        return cls(uuid.uuid4())


class ParentVersion(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Exactly which version of which artifact a later version derived from."""

    # CORRECTION. An earlier version of this comment claimed ConfigDict could
    # not be used here because it is a TypedDict carrying Any. That was FALSE,
    # and a 3-line mypy probe falsifies it: ConfigDict(...) raises no
    # explicit-any. The error is on the `class X(BaseModel)` line and nowhere
    # else. The false claim propagated - artifacts/evidence.py factored this
    # literal into `_FROZEN: dict[str, object]` and earned 10 typecheck errors,
    # because a dict LITERAL checks against the declared TypedDict while a
    # constant annotated `dict[str, object]` does not.
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: ArtifactId
    version: VersionField


class IdentityEnvelope(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """The four identity fields every canonical artifact carries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: ArtifactId
    version: VersionField
    #: A tuple, not a list. A list would let a caller append a parent to a
    #: frozen artifact's lineage after the fact, and `frozen=True` would not
    #: see it — the model would be immutable while its history was not.
    parent_versions: tuple[ParentVersion, ...]
    transaction_id: TransactionId

    @model_validator(mode="after")
    def _lineage_is_consistent_with_the_version(self) -> IdentityEnvelope:
        if self.version == FIRST_VERSION and self.parent_versions:
            raise ValueError(
                "version 1 is the origin and cannot record a parent; "
                f"got {len(self.parent_versions)}"
            )
        if self.version > FIRST_VERSION and not self.parent_versions:
            raise ValueError(
                f"version {self.version} must record the parent version(s) it derived from; "
                "an artifact with no parent cannot be traced back to the raw artifact"
            )

        seen = {(parent.artifact_id, parent.version) for parent in self.parent_versions}
        if len(seen) != len(self.parent_versions):
            raise ValueError(
                "the same parent version is listed more than once; "
                "a repeated parent is not a merge, and it makes the lineage count meaningless"
            )
        return self
