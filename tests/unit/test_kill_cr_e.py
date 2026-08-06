"""Mutation tests for conformance_registry.py lines 1720-2149 (Engine 2-6 exclusions).

Each test kills a specific mutation in the phase strings and constant references of
the EXCLUSIONS tuples. Mutations tested:
  - Phase string mutation: "P3" → "P4", "P5" → "P4", etc.
  - Constant reference mutation: IMMUTABLE → UNKNOWNS_INTACT, etc.
  - Phase presence and validity for _not_yet entries
  - Constant identifier matches for _restates entries
"""

from accountant_dad.conformance import Exclusion, Uncovered
from accountant_dad.conformance_registry import (
    EXCLUSIONS,
    IMMUTABLE,
    NO_RESOLUTION,
    UNKNOWNS_INTACT,
)


def _find_exclusion(source: str) -> Exclusion | None:
    """Find an exclusion by its source citation."""
    return next((item for item in EXCLUSIONS if item.source == source), None)


def test_engine_2_boundary_1_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_2 boundary 1."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#1-create-journal-entries@cc3d801b2bef"
    found = _find_exclusion(source)
    assert found is not None
    assert found.kind is Uncovered.NOT_YET_A_PREDICATE
    assert found.expiry == "P3"


def test_engine_2_boundary_2_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_2 boundary 2."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#2-choose-ledgers@c54249c73921"
    found = _find_exclusion(source)
    assert found is not None
    assert found.kind is Uncovered.NOT_YET_A_PREDICATE
    assert found.expiry == "P3"


def test_engine_2_boundary_3_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_2 boundary 3."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#3-decide-debit-credit@df24b975e01e"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_engine_2_boundary_4_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_2 boundary 4."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#4-apply-tax-rules@1584aa6d3a80"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_engine_2_boundary_6_restates_immutable() -> None:
    """Mutation: IMMUTABLE → UNKNOWNS_INTACT on ENGINE_2 boundary 6."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#6-modify-evidence@6d22e8c62dc0"
    found = _find_exclusion(source)
    assert found is not None
    assert found.kind is Uncovered.RESTATEMENT
    assert found.restates == IMMUTABLE


def test_engine_2_boundary_7_restates_unknowns() -> None:
    """Mutation: UNKNOWNS_INTACT → IMMUTABLE on ENGINE_2 boundary 7."""
    source = "docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#7-convert-uncertainty-in@277918a27384"
    found = _find_exclusion(source)
    assert found is not None
    assert found.kind is Uncovered.RESTATEMENT
    assert found.restates == UNKNOWNS_INTACT


def test_system_boundaries_1_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 1."""
    source = "docs/SYSTEM_BOUNDARIES.md#1-create-journal-entries@45ef16ac37e1"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_2_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 2."""
    source = "docs/SYSTEM_BOUNDARIES.md#2-choose-ledgers@4f0978eb9cd9"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_3_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 3."""
    source = "docs/SYSTEM_BOUNDARIES.md#3-decide-debit-credit@f643c41fe468"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_4_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 4."""
    source = "docs/SYSTEM_BOUNDARIES.md#4-apply-tax-rules@2013b1291aa5"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_6_restates_immutable() -> None:
    """Mutation: IMMUTABLE → UNKNOWNS_INTACT on SYSTEM_BOUNDARIES boundary 6."""
    source = "docs/SYSTEM_BOUNDARIES.md#6-modify-evidence@9a5c8654dd6e"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == IMMUTABLE


def test_system_boundaries_7_restates_unknowns() -> None:
    """Mutation: UNKNOWNS_INTACT → IMMUTABLE on SYSTEM_BOUNDARIES boundary 7."""
    source = "docs/SYSTEM_BOUNDARIES.md#7-convert-uncertainty-in@773c103abb34"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == UNKNOWNS_INTACT


def test_engine_3_boundary_1_restates_immutable() -> None:
    """Mutation: IMMUTABLE → NO_RESOLUTION on ENGINE_3 boundary 1."""
    source = "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#1-modify-the-document-ev@667b0f562ef3"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == IMMUTABLE


def test_engine_3_boundary_2_restates_immutable() -> None:
    """Mutation: IMMUTABLE → UNKNOWNS_INTACT on ENGINE_3 boundary 2."""
    source = "docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#2-modify-the-business-un@b2ca94a0995d"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == IMMUTABLE


def test_engine_4_boundary_11_restates_no_resolution() -> None:
    """Mutation: NO_RESOLUTION → IMMUTABLE on ENGINE_4 boundary 11."""
    source = "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#11-silently-resolve-conf@2c62a01fadf5"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == NO_RESOLUTION


def test_system_boundaries_11_restates_no_resolution() -> None:
    """Mutation: NO_RESOLUTION → IMMUTABLE on SYSTEM_BOUNDARIES boundary 11."""
    source = "docs/SYSTEM_BOUNDARIES.md#11-silently-resolve-conf@12fad53a56a7"
    found = _find_exclusion(source)
    assert found is not None
    assert found.restates == NO_RESOLUTION


def test_engine_4_boundary_8_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_4 boundary 8."""
    source = "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#8-approve-execution@3b734361a985"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_engine_4_boundary_9_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on ENGINE_4 boundary 9."""
    source = "docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#9-reject-execution@d56b419b3e77"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_8_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 8."""
    source = "docs/SYSTEM_BOUNDARIES.md#8-approve-execution@19024653a975"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"


def test_system_boundaries_9_phase_is_p3() -> None:
    """Mutation: "P3" → "P4" on SYSTEM_BOUNDARIES boundary 9."""
    source = "docs/SYSTEM_BOUNDARIES.md#9-reject-execution@c682f2535afd"
    found = _find_exclusion(source)
    assert found is not None
    assert found.expiry == "P3"
