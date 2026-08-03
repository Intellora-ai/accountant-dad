"""The Accounting Decision — Engine 3's only output artifact.

Written BEFORE the implementation (§J.1). Every test names the rule it defends,
and in every case the dangerous direction is the permissive one: this artifact
carries the debits and credits that end up in someone's real books, so a bug
that lets a wrong amount, an unbalanced journal, or a silently-normalised
ledger name through is worse than a bug that rejects something valid.

The three that carry the most weight:

  MONEY        `ACCOUNTING_DEFINITIONS.md` §1 — "Exact to the paisa. Zero
               tolerance. ₹0.01 off is wrong." Tested against the exact values
               a float would corrupt.

  BALANCE      `ENGINE_3_ACCOUNTING_ENGINE_RULES.md` §8.6 — debit = credit is a
               conservation law. It holds or it does not; no expert and no
               labels are needed to check it. Both directions are tested, and
               the empty journal (0 == 0, vacuously balanced) is closed.

  INV-9        IDENTITY != INTELLIGENCE. The documented failure is reasoning
               that cites an identifier: "Because ACC-000123 existed before,
               choose the same accounting treatment."
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from accountant_dad.artifacts.decision import (
    PAISA_PLACES,
    AccountingAssumption,
    AccountingDecision,
    DecisionStatus,
    JournalLine,
    RiskIndicator,
    UnresolvedDoubt,
)
from accountant_dad.identity import ArtifactId, IdentityEnvelope, ParentVersion, TransactionId

TXN_UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ARTIFACT_UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
PARENT_UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
UNRELATED_UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")

FIRST_VERSION = 1
SECOND_VERSION = 2
EXPECTED_STATUS_COUNT = 2
EXPECTED_PAISA_PLACES = 2

#: The thirteen components of `ENGINE_3_ACCOUNTING_ENGINE_RULES.md` §5, in the
#: order the document lists them. `identity` carries the first of them — the
#: Decision ID — together with the universal envelope of `DATA_FLOW.md` §2.
THE_THIRTEEN = (
    "identity",
    "decision_status",
    "accounting_treatment",
    "ledger_classification",
    "debit_entries",
    "credit_entries",
    "journal_structure",
    "tax_treatment",
    "accounting_assumptions",
    "risk_indicators",
    "decision_confidence",
    "supporting_reasoning",
    "unresolved_doubts",
)


def envelope(
    *,
    version: int = FIRST_VERSION,
    parents: tuple[ParentVersion, ...] = (),
) -> IdentityEnvelope:
    return IdentityEnvelope(
        artifact_id=ArtifactId(ARTIFACT_UUID),
        version=version,
        parent_versions=parents,
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
    """A decision that is valid on every rule, so one override isolates one rule."""
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


# ── the thirteen components, and only the thirteen ───────────────────────────


def test_the_artifact_carries_exactly_the_thirteen_components_in_order() -> None:
    # ENGINE_3 §5.5 and §13: "No new artifact beyond those named." A fourteenth
    # field would be a silent widening of a locked contract, and a renamed one
    # would break every downstream reader. Asserting the tuple catches both.
    assert tuple(AccountingDecision.model_fields) == THE_THIRTEEN


def test_decision_id_is_the_artifact_id_and_not_a_second_identifier() -> None:
    # DATA_FLOW.md §2 lists "Decision ID" among the Accounting Decision's
    # contents while also stating the identity envelope is universal and not
    # repeated. One source of truth (Law 19): the Decision ID IS the Artifact
    # ID, exposed under the name the contract uses. A separate field would be
    # two identities for one artifact and nothing would keep them equal.
    made = decision()
    assert made.decision_id is made.identity.artifact_id


def test_the_identity_envelope_is_the_shared_one_and_enforces_its_own_lineage() -> None:
    # Proves IdentityEnvelope is genuinely embedded rather than re-implemented:
    # its own INV-5 lineage rule must fire from inside this artifact.
    with pytest.raises(ValidationError, match="must record the parent version"):
        decision(identity=envelope(version=SECOND_VERSION))


def test_a_second_version_recording_its_parent_is_accepted() -> None:
    parent = ParentVersion(artifact_id=ArtifactId(ARTIFACT_UUID), version=FIRST_VERSION)
    made = decision(identity=envelope(version=SECOND_VERSION, parents=(parent,)))
    assert made.identity.version == SECOND_VERSION


# ── Decision Status — enumerated, exactly two ────────────────────────────────


def test_decision_status_has_exactly_the_two_documented_values() -> None:
    # ENGINE_3 §5.1 and DATA_FLOW.md §2.3. A third status invented later would
    # let a decision cross the boundary in a state no receiving engine handles.
    assert len(DecisionStatus) == EXPECTED_STATUS_COUNT
    assert DecisionStatus.COMPLETE.value == "COMPLETE"
    assert DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED.value == "INCOMPLETE_INFORMATION_REQUIRED"


@pytest.mark.parametrize("bad", ["PARTIAL", "complete", "OK", "", "Complete"])
def test_a_status_outside_the_enumeration_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        decision(decision_status=bad)


def test_the_status_string_round_trips_through_the_enumeration() -> None:
    made = decision(decision_status="COMPLETE")
    assert made.decision_status is DecisionStatus.COMPLETE


# ── money — exact to the paisa, never float ──────────────────────────────────


def test_a_sum_a_float_would_get_wrong_balances_exactly() -> None:
    # The canonical float failure, used deliberately: 0.1 + 0.2 != 0.3 in
    # binary floating point, so a float-based balance check would REJECT this
    # correct journal. Decimal makes it exact.
    assert 0.1 + 0.2 != 0.3  # noqa: PLR2004 - this literal IS the thing proven
    made = decision(
        debit_entries=(line("Bank Charges", "0.10"), line("Round Off", "0.20")),
        credit_entries=(line("Bank", "0.30"),),
    )
    assert made.debit_entries[0].amount + made.debit_entries[1].amount == Decimal("0.30")


def test_an_amount_a_float_would_round_is_preserved_exactly() -> None:
    # float(1.15) is 1.14999999999999991118215802998747676610946655273437500,
    # so a float round-trip loses a paisa on the wrong side. The stored value
    # must be the one the producer asserted, character for character.
    assert Decimal(1.15) != Decimal("1.15")  # noqa: RUF032 - the float IS the thing proven
    made = decision(
        debit_entries=(line("Bank Charges", "1.15"),),
        credit_entries=(line("Bank", "1.15"),),
    )
    assert made.debit_entries[0].amount == Decimal("1.15")
    assert str(made.debit_entries[0].amount) == "1.15"


def test_a_trailing_paisa_zero_is_kept_verbatim_and_not_renormalised() -> None:
    # 100.10 is what the producer wrote. Rewriting it to 100.1 would be an
    # edit to an immutable artifact (INV-5), however numerically harmless.
    made = decision(
        debit_entries=(line("Computers", "100.10"),),
        credit_entries=(line("ABC Traders", "100.10"),),
    )
    assert str(made.debit_entries[0].amount) == "100.10"


@pytest.mark.parametrize("bad", [0.1, 100.0, 50000.0, 0.0])
def test_a_float_amount_is_rejected_rather_than_converted(bad: float) -> None:
    # Converting is the precision loss the rule exists to prevent, and it would
    # happen before any range check of ours could object.
    with pytest.raises(ValidationError, match="must be a Decimal"):
        JournalLine(ledger="Computers", amount=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [100, "100.00", None, True])
def test_a_non_decimal_amount_is_rejected(bad: object) -> None:
    # One construction path. An int is exact and a string is exact, but two
    # accepted spellings of the same amount is two ways for producers to drift.
    with pytest.raises(ValidationError, match="must be a Decimal"):
        JournalLine(ledger="Computers", amount=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_a_non_finite_amount_is_rejected(bad: str) -> None:
    # NaN compares false against everything, so a journal carrying one would
    # fail the balance check for a reason nobody could read off the number.
    with pytest.raises(ValidationError, match="must be finite"):
        JournalLine(ledger="Computers", amount=Decimal(bad))


@pytest.mark.parametrize("ok", ["50000", "50000.0", "50000.00", "0.01", "1E+3"])
def test_an_amount_within_the_paisa_scale_is_accepted(ok: str) -> None:
    assert JournalLine(ledger="Computers", amount=Decimal(ok)).amount == Decimal(ok)


@pytest.mark.parametrize("bad", ["100.005", "0.001", "1.230", "50000.000"])
def test_an_amount_finer_than_a_paisa_is_refused_not_rounded(bad: str) -> None:
    # "Exact to the paisa. Zero tolerance." A third decimal place cannot be
    # posted, and rounding it silently would falsify what the producer
    # asserted. 1.230 is included on purpose: the check is on the scale the
    # producer WROTE, not on the numeric value, so a harmless-looking trailing
    # zero in the sub-paisa place is still refused.
    with pytest.raises(ValidationError, match="paisa"):
        JournalLine(ledger="Computers", amount=Decimal(bad))


def test_the_paisa_scale_is_two_places() -> None:
    assert PAISA_PLACES == EXPECTED_PAISA_PLACES


@pytest.mark.parametrize("bad", ["0", "0.00", "-0.01", "-50000.00"])
def test_a_zero_or_negative_amount_is_rejected(bad: str) -> None:
    # A negative debit is a credit wearing the wrong hat, and it makes the
    # balance rule meaningless: debit -100 plus debit 200 against credit 100
    # would "balance". A zero line posts nothing and pads a journal.
    with pytest.raises(ValidationError, match="greater than zero"):
        JournalLine(ledger="Computers", amount=Decimal(bad))


# ── the conservation law — debits equal credits ──────────────────────────────


def test_a_balanced_journal_with_differing_line_counts_is_accepted() -> None:
    made = decision(
        debit_entries=(line("Computers", "42372.88"), line("Input GST", "7627.12")),
        credit_entries=(line("ABC Traders", "50000.00"),),
    )
    assert sum(entry.amount for entry in made.debit_entries) == Decimal("50000.00")


def test_an_unbalanced_journal_is_rejected_and_the_error_names_the_difference() -> None:
    with pytest.raises(ValidationError, match=re.escape("out by 0.01")):
        decision(
            debit_entries=(line("Computers", "50000.00"),),
            credit_entries=(line("ABC Traders", "50000.01"),),
        )


def test_one_paisa_out_is_out() -> None:
    # ACCOUNTING_DEFINITIONS.md §1: "₹0.01 off is wrong." No tolerance band.
    with pytest.raises(ValidationError, match="do not equal"):
        decision(
            debit_entries=(line("Computers", "0.02"),),
            credit_entries=(line("ABC Traders", "0.01"),),
        )


def test_balance_compares_value_not_written_scale() -> None:
    # 50000 and 50000.00 are the same money written two ways. Rejecting this
    # would be a false negative, and false negatives train people to loosen
    # the check that matters.
    made = decision(
        debit_entries=(line("Computers", "50000"),),
        credit_entries=(line("ABC Traders", "50000.00"),),
    )
    assert made.debit_entries[0].amount == made.credit_entries[0].amount


def test_debits_with_no_credits_at_all_is_rejected() -> None:
    with pytest.raises(ValidationError, match=re.escape("out by 50000.00")):
        decision(
            decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
            unresolved_doubts=(a_doubt(),),
            debit_entries=(line("Computers", "50000.00"),),
            credit_entries=(),
        )


def test_a_plug_figure_cannot_be_hidden_in_a_third_line() -> None:
    # §8.6 forbidden action: "Cannot force a balance by inserting a plug
    # figure." The schema cannot read intent, but it can refuse the arithmetic
    # that a plug is inserted to fix.
    with pytest.raises(ValidationError, match=re.escape("out by 100.00")):
        decision(
            debit_entries=(line("Computers", "50000.00"), line("Suspense", "100.00")),
            credit_entries=(line("ABC Traders", "50000.00"),),
        )


# ── the vacuous balance, closed ──────────────────────────────────────────────


def test_a_complete_decision_with_no_entries_is_rejected() -> None:
    # 0 == 0 is balanced and means nothing. Without this, the conservation law
    # passes on a decision that posts nothing at all — a false green sitting
    # directly on top of the rule this artifact exists to guarantee.
    with pytest.raises(ValidationError, match="at least one debit entry and one credit entry"):
        decision(debit_entries=(), credit_entries=())


def test_a_complete_decision_with_debits_but_no_credits_is_rejected() -> None:
    # A VALID amount on purpose. This test was written with 0.00001, which the
    # paisa rule correctly refuses first — so it asserted its own message
    # against an error from an unrelated rule and never exercised the
    # one-sided journal it is named for. Fixture corrected; the requirement
    # itself is untouched and still rejects.
    with pytest.raises(ValidationError, match="at least one debit entry and one credit entry"):
        decision(debit_entries=(line("Computers", "50000.00"),), credit_entries=())


def test_an_incomplete_decision_may_carry_no_entries_at_all() -> None:
    # ENGINE_3 §6: where information is insufficient the engine returns a named
    # output, not a guess. A decision it could not complete has no journal.
    made = decision(
        decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
        unresolved_doubts=(a_doubt(),),
        debit_entries=(),
        credit_entries=(),
    )
    assert made.debit_entries == ()


def test_an_incomplete_decision_naming_no_doubt_is_rejected() -> None:
    # ENGINE_3 §5.1: "INCOMPLETE_INFORMATION_REQUIRED names the required
    # clarification." A decision that stops without naming what is missing has
    # told the Clarification Engine nothing it can act on.
    with pytest.raises(ValidationError, match="must name at least one unresolved doubt"):
        decision(
            decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
            unresolved_doubts=(),
            debit_entries=(),
            credit_entries=(),
        )


def test_a_complete_decision_may_still_carry_doubts_and_risks() -> None:
    # §5.1: "It may still carry risks and doubts — completeness is not
    # correctness." Rejecting this would force the engine to hide uncertainty
    # to get a decision through, which is the exact failure §12 names.
    made = decision(unresolved_doubts=(a_doubt(),))
    assert made.decision_status is DecisionStatus.COMPLETE
    assert len(made.unresolved_doubts) == 1


# ── INV-9 — an identifier never influences the reasoning ─────────────────────


def test_reasoning_that_cites_this_decisions_transaction_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="INV-9"):
        decision(supporting_reasoning=f"Because {TXN_UUID} was seen before, use the same ledger.")


def test_reasoning_that_cites_an_unrelated_artifacts_id_is_also_rejected() -> None:
    # The documented failure cites a DIFFERENT decision: "Because ACC-000123
    # existed before, choose the same accounting treatment." A check scoped to
    # this artifact's own identifiers would miss the example in the spec.
    with pytest.raises(ValidationError, match="INV-9"):
        decision(accounting_treatment=f"Treated as decision {UNRELATED_UUID} was treated.")


def test_an_identifier_written_without_hyphens_is_rejected() -> None:
    with pytest.raises(ValidationError, match="INV-9"):
        decision(tax_treatment=f"Same rate as {ARTIFACT_UUID.hex} used.")


def test_an_identifier_written_in_upper_case_is_rejected() -> None:
    with pytest.raises(ValidationError, match="INV-9"):
        decision(journal_structure=f"Mirrors {str(PARENT_UUID).upper()}.")


def test_a_ledger_name_carrying_an_identifier_is_rejected() -> None:
    # Ledger selection is the first thing INV-9 names.
    with pytest.raises(ValidationError, match="INV-9"):
        decision(
            debit_entries=(line(f"Computers {UNRELATED_UUID}", "50000.00"),),
            credit_entries=(line("ABC Traders", "50000.00"),),
        )


def test_an_assumption_a_risk_or_a_doubt_carrying_an_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError, match="INV-9"):
        decision(
            accounting_assumptions=(
                AccountingAssumption(
                    assumed="Same treatment as before.",
                    why=f"Decision {UNRELATED_UUID} did the same.",
                ),
            )
        )


def test_the_error_names_the_field_and_the_offending_identifier() -> None:
    with pytest.raises(ValidationError, match=r"ledger_classification.*44444444-4444-4444"):
        decision(ledger_classification=f"As per {UNRELATED_UUID}.")


def test_ordinary_accounting_prose_with_numbers_and_dates_is_accepted() -> None:
    # The disconfirming case. A rule that rejects real accounting text is
    # useless however well it blocks identifiers, so the false-positive
    # direction is tested explicitly: invoice numbers, dates, amounts, rates,
    # GSTINs and long digit runs all stay legal.
    made = decision(
        supporting_reasoning=(
            "Invoice INV-2026-0042 dated 31 March 2026, 50,000.00 at 18 percent, "
            "GSTIN 29ABCDE1234F1Z5, bank reference 000123456789012345678901234567."
        )
    )
    assert "INV-2026-0042" in made.supporting_reasoning


# ── text is stored verbatim, and never empty ─────────────────────────────────


@pytest.mark.parametrize(
    "field",
    [
        "accounting_treatment",
        "ledger_classification",
        "journal_structure",
        "tax_treatment",
        "supporting_reasoning",
    ],
)
@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_an_empty_or_blank_required_text_field_is_rejected(field: str, bad: str) -> None:
    # "Gaps stay gaps." A blank field is an absent fact dressed as a present
    # one, and it would pass every downstream reader that only checks presence.
    with pytest.raises(ValidationError, match="must not be empty"):
        decision(**{field: bad})


@pytest.mark.parametrize("bad", [42, None, True, ["text"]])
def test_a_non_string_text_field_is_rejected_rather_than_stringified(bad: object) -> None:
    with pytest.raises(ValidationError, match="must be a string"):
        decision(accounting_treatment=bad)


def test_a_ledger_name_is_stored_verbatim_and_never_trimmed() -> None:
    # ACCOUNTING_DEFINITIONS.md §1: "Exact string match against the golden
    # ledger name. A near-miss is a wrong ledger." Trimming " Computers" into
    # "Computers" would turn a near-miss into a match — the schema silently
    # fixing a defect it is supposed to expose.
    made = decision(
        debit_entries=(line(" Computers ", "50000.00"),),
        credit_entries=(line("ABC Traders", "50000.00"),),
    )
    assert made.debit_entries[0].ledger == " Computers "


def test_an_empty_ledger_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        JournalLine(ledger="", amount=Decimal("1.00"))


# ── confidence is THE shared type, not a local one ───────────────────────────


def test_a_float_confidence_is_rejected_by_the_shared_confidence_type() -> None:
    # The error text belongs to accountant_dad.confidence. Matching it proves
    # the shared validator ran, so this module cannot have quietly declared its
    # own confidence type — which is exactly the defect confidence.py exists
    # to stop.
    with pytest.raises(ValidationError, match="confidence must be a Decimal, got float"):
        decision(decision_confidence=0.82)


def test_a_confidence_above_one_is_rejected() -> None:
    with pytest.raises(ValidationError, match="confidence must be within"):
        decision(decision_confidence=Decimal("1.0001"))


def test_a_confidence_finer_than_four_places_is_rejected() -> None:
    with pytest.raises(ValidationError, match="decimal places"):
        decision(decision_confidence=Decimal("0.82001"))


def test_confidence_is_stored_exactly_as_written() -> None:
    made = decision(decision_confidence=Decimal("0.5"))
    assert str(made.decision_confidence) == "0.5"


# ── immutability — INV-5, history is never modified ──────────────────────────


def test_the_decision_cannot_be_assigned_to_after_creation() -> None:
    made = decision()
    with pytest.raises(ValidationError):
        made.decision_status = DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED


def test_a_journal_line_cannot_be_assigned_to_after_creation() -> None:
    # Freezing the parent is not enough: a mutable line would let an amount be
    # edited after the balance check passed.
    made = decision()
    with pytest.raises(ValidationError):
        made.debit_entries[0].amount = Decimal("1.00")


def test_the_entry_tuples_are_not_aliased_to_a_caller_owned_list() -> None:
    # A list handed in and kept by reference would let the caller append a
    # fourth line to a frozen artifact and break the balance after validation.
    caller_owned = [line("Computers", "50000.00")]
    made = decision(debit_entries=caller_owned)
    caller_owned.append(line("Suspense", "1.00"))
    assert len(made.debit_entries) == 1
    assert isinstance(made.debit_entries, tuple)


def test_an_unknown_field_is_rejected() -> None:
    # extra="forbid". A typo'd or invented component must fail loudly rather
    # than be carried along where nothing reads it.
    with pytest.raises(ValidationError):
        decision(posted_to_tally=True)


# ── the component structures ─────────────────────────────────────────────────


def test_an_assumption_must_record_both_what_was_assumed_and_why() -> None:
    # ENGINE_3 §9: "what was assumed, and why." An assumption with no reason
    # is the unrecorded assumption that becomes a confirmed fact by default.
    with pytest.raises(ValidationError):
        AccountingAssumption(assumed="The laptop is for business use.")  # type: ignore[call-arg]


def test_a_risk_indicator_must_record_its_reason() -> None:
    with pytest.raises(ValidationError):
        RiskIndicator(indicator="Aggressive capitalisation.")  # type: ignore[call-arg]


def test_a_doubt_must_name_the_missing_fact_and_the_clarification_required() -> None:
    # ACCOUNTING_DEFINITIONS.md §5: a doubt is "a named missing fact whose
    # absence would change the accounting treatment". Its measurement is
    # "supply the fact, re-run" — which is impossible unless the fact is named
    # precisely enough to supply.
    with pytest.raises(ValidationError):
        UnresolvedDoubt(missing_fact="Something about tax.")  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", ["", "  "])
def test_a_blank_doubt_or_assumption_field_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        UnresolvedDoubt(missing_fact=bad, required_clarification="Confirm the place of supply.")


def test_a_decision_may_carry_no_assumptions_and_no_risks() -> None:
    # Nothing in the contract requires either to be non-empty, and inventing
    # such a requirement would push a producer to fabricate a risk to satisfy
    # the schema — the opposite of what §12 asks for.
    made = decision(accounting_assumptions=(), risk_indicators=())
    assert made.accounting_assumptions == ()
    assert made.risk_indicators == ()
