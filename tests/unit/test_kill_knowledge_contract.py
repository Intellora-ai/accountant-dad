"""Mutation tests for knowledge_contract.py.

Targets: critical mutations that allow advice to become binding.
Each test is designed to fail if a single operator or condition is flipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from accountant_dad.knowledge_contract import (
    AdvisoryViolation,
    KnowledgeAnswer,
    KnowledgeQuestion,
    KnowledgeStatement,
    violates_advisory_contract,
)


def answer(*statements: KnowledgeStatement) -> KnowledgeAnswer:
    return KnowledgeAnswer(statements=statements)


def statement(
    text: str = "knowledge",
    source: str = "a source",
) -> KnowledgeStatement:
    return KnowledgeStatement(statement=text, source_reference=source)


# ── Mutations in the early type check (line 356) ──────────────────────────────


def test_only_exact_type_knowledge_answer_passes() -> None:
    """Mutation: `is not` → `is` would invert the check and reject valid answers.

    This test ensures that `type(answer) is not KnowledgeAnswer` is the correct
    predicate. If mutated to `is`, all valid answers would be rejected.
    """
    valid = answer(statement())
    assert violates_advisory_contract(valid) == ()

    # A subclass should still fail
    class _Extended(KnowledgeAnswer):  # type: ignore[explicit-any]
        extra_field: str

    with_extra = _Extended(statements=(statement(),), extra_field="x")
    violations = violates_advisory_contract(with_extra)
    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations


def test_any_subclass_is_rejected_even_with_zero_extra_fields() -> None:
    """Mutation: `is not` → `isinstance` would accept subclasses.

    Even a subclass with no extra fields is rejected because inheritance
    could add fields later, and the type check must be exact.
    """

    class _ValidSubclass(KnowledgeAnswer):  # type: ignore[explicit-any]
        pass

    subclass_answer = _ValidSubclass(statements=(statement(),))
    # Subclass is rejected at the type level
    assert violates_advisory_contract(subclass_answer) == (
        AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,
    )


# ── Mutations in the payload accumulation loop (line 364-365) ──────────────────


def test_payload_scan_runs_unconditionally() -> None:
    """Mutation: removing the loop would skip payload scanning.

    The payload scan runs even on a KnowledgeAnswer. If a KnowledgeAnswer
    is ever widened with a forbidden field, the scan catches it, not the
    type rule.
    """
    # A KnowledgeAnswer normally passes both checks
    assert violates_advisory_contract(answer()) == ()

    # A subclass of KnowledgeAnswer with a forbidden field fails on payload
    class _WidenedAnswer(KnowledgeAnswer):  # type: ignore[explicit-any]
        confidence: float

    widened = _WidenedAnswer(statements=(), confidence=0.95)
    violations = violates_advisory_contract(widened)

    # Type check fails (subclass)
    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    # Payload check also fails (confidence field)
    assert AdvisoryViolation.RETURNS_A_CONFIDENCE in violations


def test_multiple_forbidden_fields_are_all_detected() -> None:
    """Mutation: accumulation operator `|=` → `=` would only detect the last field.

    If the union operator is changed to assignment, only the last token
    would be checked, allowing earlier violations to pass.
    """

    class _MultiViolation:
        def __init__(self) -> None:
            self.decision = "yes"  # RETURNS_A_DECISION
            self.confidence = 0.99  # RETURNS_A_CONFIDENCE
            self.ledger = "AR"  # RETURNS_A_LEDGER

    obj = _MultiViolation()
    violations = violates_advisory_contract(obj)

    # All three violations must be reported
    assert AdvisoryViolation.RETURNS_A_DECISION in violations
    assert AdvisoryViolation.RETURNS_A_CONFIDENCE in violations
    assert AdvisoryViolation.RETURNS_A_LEDGER in violations


# ── Mutations in the set intersection (line 367) ─────────────────────────────


def test_set_intersection_operator_is_critical() -> None:
    """Mutation: `carried & markers` → `carried | markers` would report everything.

    The test ensures we're using intersection (`&`), not union (`|`). With union,
    every object would report all violations simultaneously.
    """
    expected_violations = 2

    # A field that matches EXACTLY one violation
    class _OnlyDecision:
        def __init__(self) -> None:
            self.decision = "yes"

    obj = _OnlyDecision()
    violations = violates_advisory_contract(obj)

    # Must report exactly two violations: NOT_A_KNOWLEDGE_ANSWER + RETURNS_A_DECISION
    assert len(violations) == expected_violations
    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    assert AdvisoryViolation.RETURNS_A_DECISION in violations
    # Must NOT report other violations (would happen if using union)
    assert AdvisoryViolation.RETURNS_A_TREATMENT not in violations
    assert AdvisoryViolation.RETURNS_A_CONFIDENCE not in violations


def test_intersection_condition_not_inverted() -> None:
    """Mutation: `if carried & markers` → `if not carried & markers`.

    If the condition is inverted, violations would be reported only when
    there is NO intersection.
    """

    class _Clean:
        pass

    clean = _Clean()
    # Has no payload at all
    violations = violates_advisory_contract(clean)
    # Should only report NOT_A_KNOWLEDGE_ANSWER, not violations from empty intersection
    assert violations == (AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,)


# ── Mutations in _payload_names: Mapping branch (line 320-321) ────────────────


def test_mapping_branch_is_executed() -> None:
    """Mutation: removing `isinstance(value, Mapping)` branch would miss dict payloads.

    A dict is the simplest way to return a decision, and it must be caught.
    """
    payload = {"decision": "yes", "ledger": "AR"}
    violations = violates_advisory_contract(payload)

    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    assert AdvisoryViolation.RETURNS_A_DECISION in violations
    assert AdvisoryViolation.RETURNS_A_LEDGER in violations


def test_dict_keys_are_all_tokenized() -> None:
    """Mutation: removing the tokenization step would miss camelCase keys.

    A dict with camelCase keys must be tokenized like any other payload.
    """
    payload = {"recommendedLedger": "AR"}
    violations = violates_advisory_contract(payload)

    # recommendedLedger tokenizes to ["recommended", "ledger"]
    # "ledger" matches RETURNS_A_LEDGER
    # "recommended" matches RETURNS_A_TREATMENT
    assert AdvisoryViolation.RETURNS_A_LEDGER in violations
    assert AdvisoryViolation.RETURNS_A_TREATMENT in violations


# ── Mutations in _payload_names: __dict__ branch (line 323-325) ───────────────


def test_dict_branch_is_executed() -> None:
    """Mutation: removing `if isinstance(attributes, Mapping)` would miss some objects.

    An object with __dict__ must be scanned, but the current code also checks
    if __dict__ is a Mapping to avoid trying to iterate None.
    """

    class _RegularObject:
        def __init__(self) -> None:
            self.instruction = "do this"

    obj = _RegularObject()
    violations = violates_advisory_contract(obj)

    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    assert AdvisoryViolation.RETURNS_AN_INSTRUCTION in violations


# ── Mutations in _payload_names: __slots__ branch (line 326-331) ──────────────


def test_slotted_object_slots_are_scanned() -> None:
    """Mutation: removing the __slots__ loop would miss slotted payloads.

    A slotted object has no __dict__, so only __slots__ scanning catches it.
    """

    @dataclass(frozen=True, slots=True)
    class _Slotted:
        confidence: float

    obj = _Slotted(confidence=0.95)
    violations = violates_advisory_contract(obj)

    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    assert AdvisoryViolation.RETURNS_A_CONFIDENCE in violations


def test_slots_from_base_classes_are_included() -> None:
    """Mutation: using `[type(obj)]` instead of `__mro__` would miss inherited slots.

    The code iterates type(value).__mro__ to get slots from all base classes,
    not just the direct type.
    """

    @dataclass(frozen=True, slots=True)
    class _BaseSlotted:
        decision: str

    class _DerivedSlotted(_BaseSlotted):
        pass

    obj = _DerivedSlotted(decision="yes")
    violations = violates_advisory_contract(obj)

    # Must detect "decision" even though it's in the base class slots
    assert AdvisoryViolation.RETURNS_A_DECISION in violations


def test_bare_string_slot_name_is_handled() -> None:
    """Mutation: treating __slots__ string as iterable would split it into chars.

    When __slots__ is a single string (not a tuple), it must be treated as
    one name, not iterated character by character.
    """

    # Simulate __slots__ = "instruction" (a single string, not a tuple)
    slotted = type("_BareSlots", (), {"__slots__": "instruction"})()

    violations = violates_advisory_contract(slotted)

    # "instruction" as a whole word matches RETURNS_AN_INSTRUCTION
    # If treated as ["i", "n", "s", "t", "r", "u", "c", "t", "i", "o", "n"],
    # no match would occur
    assert AdvisoryViolation.RETURNS_AN_INSTRUCTION in violations


# ── Mutations in _tokens: regex boundaries (line 301-307) ────────────────────


def test_camel_case_split_is_exact() -> None:
    """Mutation: changing the camelCase regex pattern would miss conventions.

    recommendedLedger must split into ["recommended", "ledger"] to catch both
    RETURNS_A_TREATMENT and RETURNS_A_LEDGER.
    """

    class _CamelCase:
        def __init__(self) -> None:
            self.recommendedLedger = "AR"

    obj = _CamelCase()
    violations = violates_advisory_contract(obj)

    # Both parts must be detected
    assert AdvisoryViolation.RETURNS_A_TREATMENT in violations
    assert AdvisoryViolation.RETURNS_A_LEDGER in violations


def test_lowercase_conversion_is_applied() -> None:
    """Mutation: removing `.lower()` would miss uppercase markers.

    Markers are lowercase; field names are converted to lowercase to match.
    """

    class _UpperCase:
        def __init__(self) -> None:
            self.Decision = "yes"  # Uppercase D

    obj = _UpperCase()
    violations = violates_advisory_contract(obj)

    # "Decision" lowercased to "decision" matches the marker
    assert AdvisoryViolation.RETURNS_A_DECISION in violations


# ── Mutations in _payload_names: private name filter (line 335) ──────────────


def test_private_names_are_excluded() -> None:
    """Mutation: removing `if not name.startswith('_')` would report pydantic machinery.

    Private names like _decision are excluded; only public names are payload.
    """
    payload = {"_decision": "yes"}
    violations = violates_advisory_contract(payload)

    # _decision is private and ignored
    # Only NOT_A_KNOWLEDGE_ANSWER should be reported
    assert violations == (AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,)


def test_dunder_names_are_excluded() -> None:
    """Mutation: `startswith("_")` must exclude both `_name` and `__name__`.

    pydantic adds __pydantic_extra__ and similar; these must not be treated
    as returned data.
    """
    payload = {"__pydantic_extra__": {"x": "y"}}
    violations = violates_advisory_contract(payload)

    # __pydantic_extra__ is private and excluded
    assert violations == (AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER,)


# ── Integration: the advisory contract is enforced ───────────────────────────


def test_a_brain_returning_a_dict_of_decisions_is_caught() -> None:
    """Integration: a Brain returning a dict is caught by mapping branch.

    This ensures the entire chain works: violates_advisory_contract calls
    _payload_names, which identifies the dict, which identifies the keys.
    """

    def lying_brain(_question: KnowledgeQuestion) -> object:
        return {"decision": "treat as this", "confidence": 0.95}

    # The Brain's return type is KnowledgeAnswer (from the signature),
    # but it actually returns a dict. The predicate catches this.
    returned = lying_brain(KnowledgeQuestion(question="test"))
    violations = violates_advisory_contract(returned)

    assert AdvisoryViolation.NOT_A_KNOWLEDGE_ANSWER in violations
    assert AdvisoryViolation.RETURNS_A_DECISION in violations
    assert AdvisoryViolation.RETURNS_A_CONFIDENCE in violations


def test_binding_keyword_is_detected() -> None:
    """Mutation: if 'binding' is removed from _FORBIDDEN_PAYLOADS markers.

    The BINDS_THE_CALLER violation must catch "binding" in payload names.
    """

    class _Binding:
        def __init__(self) -> None:
            self.is_binding = True

    obj = _Binding()
    violations = violates_advisory_contract(obj)

    assert AdvisoryViolation.BINDS_THE_CALLER in violations
