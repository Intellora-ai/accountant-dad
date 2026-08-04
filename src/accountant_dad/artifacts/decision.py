"""The Accounting Decision — Engine 3's only output artifact.

`DATA_FLOW.md` §2 row 3 and `ENGINE_3_ACCOUNTING_ENGINE_RULES.md` §5. Thirteen
components, and only thirteen: §5.5 and §13 say *"No new artifact beyond those
named."* A fourteenth field is a silent widening of a locked contract.

This is the artifact whose debits and credits end up in someone's real books,
so every rule below leans the same way: refusing something valid is a nuisance,
accepting something wrong is a financial misstatement that a person has to
answer for.

MONEY IS DECIMAL, AND ONLY DECIMAL.
    `ACCOUNTING_DEFINITIONS.md` §1 — *"Exact to the paisa. Zero tolerance.
    ₹0.01 off is wrong."* `float` is refused rather than converted, because the
    conversion IS the loss: `Decimal(1.15)` is
    1.14999999999999991118215802998747676610946655273437500, and it would
    happen before any check of ours could object. `int` and `str` are refused
    too — both are exact, and that is the point: two accepted spellings of one
    amount is two ways for producers to drift apart.

    Values are stored verbatim. `100.10` is not renormalised to `100.1`;
    rewriting what a producer asserted is an edit to an immutable artifact
    (INV-5), however numerically harmless.

BALANCE IS A CONSERVATION LAW.
    `ENGINE_3` §8.6 — debit total equals credit total. It holds or it does
    not; no expert, no labels and no ground truth are needed to check it,
    which makes it the strongest predicate available at P2. Compared by VALUE,
    so `50000.00` and `50000.0000` balance.

    The vacuous case is closed deliberately: an empty journal satisfies
    `0 == 0` and would sail through a naive check, so a COMPLETE decision must
    carry entries on both sides. An INCOMPLETE one may carry none — but then
    it must name the doubt that stopped it (§6), or it is a decision that
    failed for no stated reason.

IDENTITY != INTELLIGENCE (INV-9).
    The documented failure is reasoning that cites an identifier:
    *"Because ACC-000123 existed before, choose the same accounting
    treatment."* (`DATA_FLOW.md:426`, `SYSTEM_INVARIANTS.md:222`.) So no text
    the artifact carries — reasoning, treatment, ledger name, assumption, risk
    or doubt — may contain an identifier, and the check is not scoped to this
    artifact's own ids: the example in the specification cites a DIFFERENT
    decision.

    The false-positive direction matters as much. A rule that rejects real
    accounting prose is useless however well it blocks identifiers, so the
    pattern is deliberately narrow: it matches the UUID shapes this system
    mints, hyphenated or bare, in either case. Invoice numbers, dates,
    amounts, tax rates, GSTINs and long bank references stay legal.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainValidator, model_validator

from accountant_dad.confidence import Confidence
from accountant_dad.identity import ArtifactId, IdentityEnvelope

#: `ACCOUNTING_DEFINITIONS.md` §1 — the paisa is the unit of exactness. Read
#: off the definition, not chosen: ₹0.01 is two decimal places.
PAISA_PLACES = 2

_FROZEN = ConfigDict(frozen=True, extra="forbid")


def _meaningful_text(value: object) -> str:
    """A real string with something in it. Stored verbatim, never trimmed.

    `ACCOUNTING_DEFINITIONS.md` §1 — *"Exact string match against the golden
    ledger name. A near-miss is a wrong ledger."* Trimming `" Computers "` into
    `"Computers"` would turn a near-miss into a match: the schema silently
    fixing the defect it exists to expose. So blankness is REJECTED and
    whitespace is PRESERVED.
    """
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value.strip():
        # "Gaps stay gaps." A blank field is an absent fact dressed as a
        # present one, and it passes every reader that only checks presence.
        raise ValueError("must not be empty or blank")
    return value


#: Text that means something. Verbatim in, verbatim out.
NonEmptyText = Annotated[str, PlainValidator(_meaningful_text)]

#: The identifiers this system mints, in every spelling they can be written:
#: hyphenated (`str(uuid)`), bare (`uuid.hex`), upper or lower case. Narrow on
#: purpose — see the false-positive note in the module docstring.
_IDENTIFIER = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|\b[0-9a-fA-F]{32}\b"
)


def _reject_identifiers(field: str, text: str) -> None:
    """No identifier may appear in text the artifact carries (INV-9)."""
    found = _IDENTIFIER.search(text)
    if found:
        raise ValueError(
            f"INV-9 — {field} contains an identifier: {found.group()}. "
            "IDs identify objects; they never influence reasoning, ledger "
            "selection, journal creation or tax treatment. Reasoning that "
            "cites an identifier is the failure the invariant names."
        )


def _exactly_a_decimal(value: object) -> Decimal:
    """A Decimal, already. Never a float, an int or a string.

    A PlainValidator so it runs BEFORE pydantic's own numeric handling, which
    would coerce all three into Decimal and take the precision with it.
    """
    if not isinstance(value, Decimal):
        raise ValueError(
            f"amount must be a Decimal, got {type(value).__name__}. "
            "float is refused rather than converted because the conversion is "
            "the precision loss; int and str are refused because two accepted "
            "spellings of one amount is two ways for producers to drift."
        )
    if not value.is_finite():
        raise ValueError(f"amount must be finite, got {value}")
    if value <= 0:
        # A negative debit is a credit wearing the wrong hat, and it makes the
        # balance rule meaningless: debit -100 plus debit 200 against credit
        # 100 would "balance". A zero line posts nothing and pads a journal.
        raise ValueError(f"amount must be greater than zero, got {value}")

    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > PAISA_PLACES:
        # Checked on the scale the producer WROTE, not the numeric value, so
        # `1.230` is refused too: a trailing zero in the sub-paisa place still
        # asserts a precision that cannot be posted. Refused, never rounded —
        # rounding falsifies what the producer asserted.
        raise ValueError(
            f"amount {value} is finer than a paisa; {PAISA_PLACES} decimal places "
            "is the limit. Refused rather than rounded: zero tolerance."
        )
    return value


Money = Annotated[Decimal, PlainValidator(_exactly_a_decimal)]


class DecisionStatus(StrEnum):
    """Exactly two. `ENGINE_3` §5.1 and `DATA_FLOW.md` §2.3.

    A third status invented later would let a decision cross the boundary in a
    state no receiving engine handles.
    """

    COMPLETE = "COMPLETE"
    INCOMPLETE_INFORMATION_REQUIRED = "INCOMPLETE_INFORMATION_REQUIRED"


class JournalLine(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One ledger and one amount. The unit the balance rule sums over."""

    model_config = _FROZEN

    ledger: NonEmptyText
    amount: Money

    @model_validator(mode="after")
    def _the_ledger_name_carries_no_identifier(self) -> JournalLine:
        # Ledger selection is the first thing INV-9 names.
        _reject_identifiers("ledger", self.ledger)
        return self


class AccountingAssumption(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What was assumed, and why. Both required — an assumption with no reason
    is indistinguishable from a guess, and `ENGINE_3` §9 exists to keep the two
    apart."""

    model_config = _FROZEN

    assumed: NonEmptyText
    why: NonEmptyText

    @model_validator(mode="after")
    def _no_identifier_in_either_half(self) -> AccountingAssumption:
        _reject_identifiers("assumed", self.assumed)
        _reject_identifiers("why", self.why)
        return self


class RiskIndicator(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """A named risk and the reason it was raised."""

    model_config = _FROZEN

    indicator: NonEmptyText
    reason: NonEmptyText

    @model_validator(mode="after")
    def _no_identifier_in_either_half(self) -> RiskIndicator:
        _reject_identifiers("indicator", self.indicator)
        _reject_identifiers("reason", self.reason)
        return self


class UnresolvedDoubt(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """A named missing fact, and what would resolve it.

    `ACCOUNTING_DEFINITIONS.md` §5 makes a doubt a structure rather than free
    text: a missing fact whose absence would change the treatment. Naming what
    is missing without naming what would settle it produces a question nobody
    can act on.
    """

    model_config = _FROZEN

    missing_fact: NonEmptyText
    required_clarification: NonEmptyText

    @model_validator(mode="after")
    def _no_identifier_in_either_half(self) -> UnresolvedDoubt:
        _reject_identifiers("missing_fact", self.missing_fact)
        _reject_identifiers("required_clarification", self.required_clarification)
        return self


class AccountingDecision(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Engine 3 → Engine 4 or Engine 5. `DATA_FLOW.md` §2 row 3.

    Field order is the order `ENGINE_3` §5 lists the components, and a test
    asserts the tuple: a renamed or reordered field breaks every downstream
    reader, and a fourteenth widens a locked contract.
    """

    model_config = _FROZEN

    identity: IdentityEnvelope
    decision_status: DecisionStatus
    accounting_treatment: NonEmptyText
    ledger_classification: NonEmptyText
    debit_entries: tuple[JournalLine, ...]
    credit_entries: tuple[JournalLine, ...]
    journal_structure: NonEmptyText
    tax_treatment: NonEmptyText
    accounting_assumptions: tuple[AccountingAssumption, ...]
    risk_indicators: tuple[RiskIndicator, ...]
    decision_confidence: Confidence
    supporting_reasoning: NonEmptyText
    unresolved_doubts: tuple[UnresolvedDoubt, ...]

    @property
    def decision_id(self) -> ArtifactId:
        """The Decision ID IS the Artifact ID, under the name the contract uses.

        `DATA_FLOW.md` §2 lists "Decision ID" among the contents while also
        stating the identity envelope is universal and not repeated. A separate
        field would be two identities for one artifact, with nothing keeping
        them equal (Law 19).
        """
        return self.identity.artifact_id

    @model_validator(mode="after")
    def _the_journal_balances_and_the_prose_cites_no_identifier(self) -> AccountingDecision:
        for name in (
            "accounting_treatment",
            "ledger_classification",
            "journal_structure",
            "tax_treatment",
            "supporting_reasoning",
        ):
            _reject_identifiers(name, getattr(self, name))

        debit_total = sum((line.amount for line in self.debit_entries), Decimal(0))
        credit_total = sum((line.amount for line in self.credit_entries), Decimal(0))

        if self.decision_status is DecisionStatus.COMPLETE and not (
            self.debit_entries and self.credit_entries
        ):
            # The vacuous balance, closed. An empty journal satisfies 0 == 0
            # and would pass a naive check while asserting nothing.
            raise ValueError(
                "a COMPLETE decision must carry at least one debit entry and one "
                "credit entry; an empty journal balances vacuously and asserts nothing"
            )

        if self.decision_status is DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED and (
            not self.unresolved_doubts
        ):
            # ENGINE_3 §6 — an incomplete decision names what stopped it.
            raise ValueError(
                "an INCOMPLETE_INFORMATION_REQUIRED decision must name at least "
                "one unresolved doubt; otherwise it is a decision that failed "
                "for no stated reason"
            )

        if debit_total != credit_total:
            # Compared by value, so 50000.00 and 50000.0000 balance.
            raise ValueError(
                f"debits {debit_total} and credits {credit_total} do not equal each other - "
                f"out by {abs(debit_total - credit_total)}. Debit equals credit is a "
                "conservation law, not a tolerance band."
            )
        return self
