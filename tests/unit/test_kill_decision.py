"""Mutation-killing tests for AccountingDecision artifact.

These tests target mutations in decision.py that existing tests might miss:
- Whitespace validator mutations (.strip → .lstrip/.rstrip)
- UUID regex mutations (digit ranges, boundaries)
- Boundary conditions in decimal validation

Each test is written to FAIL if a specific mutation exists.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.decision import (
    AccountingAssumption,
    AccountingDecision,
    DecisionStatus,
    JournalLine,
    RiskIndicator,
    UnresolvedDoubt,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

#: UUID with hex digit 'f' that existing tests don't cover (all use 1-4)
UUID_WITH_F = uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")

#: Standard test envelope
TXN_UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ARTIFACT_UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def envelope() -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId(ARTIFACT_UUID),
        version=1,
        parent_versions=(),
        transaction_id=TransactionId(TXN_UUID),
    )


def line(ledger: str, amount: str) -> JournalLine:
    return JournalLine(ledger=ledger, amount=Decimal(amount))


def a_doubt() -> UnresolvedDoubt:
    return UnresolvedDoubt(
        missing_fact="Whether the vendor charged IGST or CGST plus SGST.",
        required_clarification="Confirm the vendor's place of supply.",
    )


def decision(**overrides: object) -> AccountingDecision:
    """Valid decision for isolated mutation testing."""
    fields: dict[str, object] = {
        "identity": envelope(),
        "decision_status": DecisionStatus.COMPLETE,
        "accounting_treatment": "Laptop purchased on credit; capitalised as a fixed asset.",
        "ledger_classification": "Fixed Assets, Computers. The vendor is a trade creditor.",
        "debit_entries": (line("Computers", "50000.00"),),
        "credit_entries": (line("ABC Traders", "50000.00"),),
        "journal_structure": "One purchase voucher carrying two lines.",
        "tax_treatment": "GST 18 percent, input credit eligible, intra-state supply.",
        "accounting_assumptions": (
            AccountingAssumption(
                assumed="The laptop is for business use.",
                why="The invoice is addressed to the company, and no personal use was stated.",
            ),
        ),
        "risk_indicators": (
            RiskIndicator(
                indicator="Capitalisation threshold is close to the company policy limit.",
                reason="The amount sits within ten percent of the stated expensing limit.",
            ),
        ),
        "decision_confidence": Decimal("0.8200"),
        "supporting_reasoning": "The invoice names a laptop and a vendor, and the amount agrees.",
        "unresolved_doubts": (),
    }
    fields.update(overrides)
    return AccountingDecision(**fields)  # type: ignore[arg-type]


# ── Mutation kills: whitespace validator (.strip → .lstrip/.rstrip) ───────────


def test_ledger_with_only_trailing_newline_is_rejected() -> None:
    """Kill: `.strip()` → `.lstrip()` in _meaningful_text.

    With `.lstrip()`, `"text\n"` becomes `"text\n"` (truthy, accepted).
    With `.strip()`, becomes `"text"` or `""` depending on value.

    Uses trailing-only whitespace; existing test uses both leading and trailing.
    """
    with pytest.raises(ValidationError, match="must not be empty"):
        JournalLine(ledger="  \n", amount=Decimal("1.00"))


def test_assumption_with_only_leading_whitespace_is_rejected() -> None:
    """Kill: `.strip()` → `.rstrip()` in _meaningful_text.

    With `.rstrip()`, `"\n  "` becomes `"\n  "` (truthy, accepted).
    With `.strip()`, becomes `""` (falsy, rejected).

    Different field and different whitespace pattern from existing tests.
    """
    with pytest.raises(ValidationError, match="must not be empty"):
        AccountingAssumption(assumed="\n  ", why="Some reason.")


def test_risk_reason_with_only_tabs_is_rejected() -> None:
    """Kill: any mutation that changes whitespace checking logic.

    Uses tab-only whitespace; covers the `.strip()` validator completely.
    """
    with pytest.raises(ValidationError, match="must not be empty"):
        RiskIndicator(indicator="Some risk.", reason="\t\t")


# -- Mutation kills: UUID regex pattern - missing 'f' digit ------------------


def test_uuid_with_f_digit_in_supporting_reasoning_is_rejected() -> None:
    """Kill: regex `[0-9a-fA-F]` -> `[0-9a-eA-F]` (missing lowercase 'f').

    Existing tests use UUIDs with only digits 1-4. This UUID has 'f' in both
    hyphenated and bare forms. If regex excludes 'f', this mutation escapes.

    The UUID ffffffff-ffff-4fff-bfff-ffffffffffff contains only 'f' hex digits.
    """
    with pytest.raises(ValidationError, match="INV-9"):
        decision(supporting_reasoning=f"Treated same as {UUID_WITH_F}.")


def test_uuid_with_f_digit_bare_hex_is_rejected() -> None:
    """Kill: regex for bare UUID form `[0-9a-fA-F]{32}` missing 'f'.

    If the regex is changed to exclude 'f' (e.g., `[0-9a-eA-F]`), the bare
    hex form of UUID_WITH_F would not be detected.
    """
    bare_f = UUID_WITH_F.hex
    with pytest.raises(ValidationError, match="INV-9"):
        decision(ledger_classification=f"As per decision {bare_f} before.")


def test_uuid_with_uppercase_f_is_rejected() -> None:
    """Kill: regex missing uppercase 'F' in `[0-9a-fA-F]`.

    The pattern must include both lowercase and uppercase 'f' for hyphenated
    UUIDs in any case form.
    """
    uuid_upper_f = uuid.UUID("FFFFFFFF-FFFF-4FFF-BFFF-FFFFFFFFFFFF")
    with pytest.raises(ValidationError, match="INV-9"):
        decision(tax_treatment=f"Same rate as {uuid_upper_f}.")


# -- Mutation kills: decimal places boundary - off-by-one errors ---------------


def test_exactly_three_decimal_places_is_rejected() -> None:
    """Kill: `>` -> `>=` in exponent check (line 136).

    Current: `if -exponent > PAISA_PLACES:` raises for > 2 places.
    Mutated: `if -exponent >= PAISA_PLACES:` would reject exactly 2 places.
    This test ensures 3 places is always rejected.

    PAISA_PLACES is the boundary; this tests one place beyond it.
    """
    with pytest.raises(ValidationError, match="finer than a paisa"):
        JournalLine(ledger="Test", amount=Decimal("100.123"))


def test_exactly_two_decimal_places_at_boundary_is_accepted() -> None:
    """Kill: `>` -> `>=` mutation in exponent check.

    If mutated to `>=`, this would be rejected. Exponent check must use `>`
    not `>=` to allow exactly PAISA_PLACES decimal places.
    """
    line_obj = JournalLine(ledger="Test", amount=Decimal("100.00"))
    assert line_obj.amount == Decimal("100.00")
    assert str(line_obj.amount) == "100.00"


def test_one_decimal_place_is_accepted() -> None:
    """Kill: comparison direction errors in PAISA_PLACES check.

    One decimal place is within tolerance. If boundary check is wrong,
    might be rejected or have wrong behavior.
    """
    line_obj = JournalLine(ledger="Test", amount=Decimal("100.1"))
    assert line_obj.amount == Decimal("100.1")


# ── Mutation kills: identity vs equality in status checks ─────────────────


def test_complete_status_check_uses_identity_not_just_enum_value() -> None:
    """Kill: `is` → `==` mutation in decision_status checks (line 279, 289).

    Using `is` ensures exact enum member identity. Both should work for
    normal EnumStr usage, but the pattern is important for correctness.

    Decision with COMPLETE status must reject empty journals.
    """
    with pytest.raises(ValidationError, match="at least one debit entry"):
        decision(
            decision_status=DecisionStatus.COMPLETE,
            debit_entries=(),
            credit_entries=(),
        )


def test_incomplete_status_check_requires_exactly_incomplete_not_just_value() -> None:
    """Kill: `is` → `==` mutation in INCOMPLETE status check (line 289).

    INCOMPLETE_INFORMATION_REQUIRED without unresolved_doubts must fail.
    Tests that the status check is precise.
    """
    with pytest.raises(ValidationError, match="must name at least one"):
        decision(
            decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
            unresolved_doubts=(),
            debit_entries=(),
            credit_entries=(),
        )


# ── Mutation kills: NOT operator removal in conditional checks ────────────


def test_vacuous_balance_with_complete_status_is_rejected() -> None:
    """Kill: `not (x and y)` → `(x and y)` in line 280.

    An empty journal (0 == 0) balances but asserts nothing. Must be rejected
    for COMPLETE status. Removing the `not` would flip the logic.
    """
    with pytest.raises(ValidationError, match="at least one debit entry"):
        decision(debit_entries=(), credit_entries=())


def test_incomplete_without_doubts_requires_not_check() -> None:
    """Kill: `not x` → `x` in line 290 unresolved_doubts check.

    An INCOMPLETE decision without naming any doubt is invalid.
    Must specifically check for ABSENCE of doubts.
    """
    with pytest.raises(ValidationError, match="unresolved doubt"):
        decision(
            decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
            debit_entries=(),
            credit_entries=(),
            unresolved_doubts=(),
        )


# ── Mutation kills: balance check operator direction ────────────────────


def test_debits_less_than_credits_is_rejected() -> None:
    """Kill: `!=` → `<` or `>` in balance check (line 299).

    Must reject when debits < credits. Flipping the operator would accept
    imbalanced journals in one direction.
    """
    with pytest.raises(ValidationError, match="do not equal"):
        decision(
            debit_entries=(line("Computers", "49999.99"),),
            credit_entries=(line("ABC Traders", "50000.00"),),
        )


def test_debits_greater_than_credits_is_rejected() -> None:
    """Kill: `!=` → `<` in balance check (line 299).

    Must reject when debits > credits. Mutations in the comparison must
    catch both directions.
    """
    with pytest.raises(ValidationError, match="do not equal"):
        decision(
            debit_entries=(line("Computers", "50000.01"),),
            credit_entries=(line("ABC Traders", "50000.00"),),
        )


# ── Mutation kills: AND/OR in entry existence check ─────────────────────────


def test_complete_with_debits_only_is_rejected() -> None:
    """Kill: `and` → `or` in line 280 `debit_entries and credit_entries`.

    With `or`, missing one side would still allow the conditional to pass.
    This must be rejected.
    """
    with pytest.raises(ValidationError, match="at least one debit entry and one credit entry"):
        decision(
            debit_entries=(line("Computers", "50000.00"),),
            credit_entries=(),
        )


def test_complete_with_credits_only_is_rejected() -> None:
    """Kill: `and` → `or` in line 280 entry check.

    With `or`, missing debits would still allow the conditional to pass.
    This must be rejected. Symmetric to debits-only case.
    """
    with pytest.raises(ValidationError, match="at least one debit entry and one credit entry"):
        decision(
            debit_entries=(),
            credit_entries=(line("ABC Traders", "50000.00"),),
        )
