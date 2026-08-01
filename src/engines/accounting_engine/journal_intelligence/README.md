# journal_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The double entry is the decision's core; it must balance and mean what it says.

## Responsibility

Owns construction of the entry itself — which accounts are debited, which credited, in what amounts — and the guarantee that it balances.

## Input

Ledger selection from [`ledger_intelligence`](../ledger_intelligence/), the applicable rulings, tax lines from [`tax_intelligence`](../tax_intelligence/), and the amounts in the Business Understanding Object.

## Output

The journal entry: a balanced, system-neutral set of debit and credit lines.

## Boundary

Cannot select the accounts itself — it consumes `ledger_intelligence`'s selection. Cannot determine tax amounts — it consumes `tax_intelligence`'s lines. Cannot format for Tally. Cannot force a balance by inserting a plug figure.

## Future Notes

- The entry is deliberately system-neutral. Tally's representation is [`voucher_translator`](../../tally_engine/voucher_translator/)'s problem, and keeping them apart is what lets the accounting be reviewed on its own terms.
- An entry that will not balance is a doubt to be raised, never a rounding line to be invented.
