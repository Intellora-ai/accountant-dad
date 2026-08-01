# ledger_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#84-ledger_intelligence).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Determine appropriate ledger classification — *where does this transaction go?*

## Responsibility

Owns **ledger reasoning**: which accounts are involved, their groups, and the determination that an existing master is inadequate and a new ledger is required.

## Input

**Transaction Analysis Result** and **Company Context Result**.

## Output

**Ledger Recommendation** — recommended ledgers · classification reasoning · confidence.

Contributed into the **Accounting Treatment Result**, which the parent engine assembles.

## Boundary

**Can:** select ledger accounts and groups · identify that an existing master is inadequate and specify a new ledger.

**Cannot:** create journal posting · change transaction meaning · create a ledger anywhere — it specifies, it does not provision · compute amounts · decide debit/credit direction.

## Decision Authority

**Owns.** Ledger classification.

**Cannot.** Construct the journal, or decide tax.

No other component may override this Result — including `accounting_rules`, which does **not** produce it.

## Failure Behaviour

Return possible ledgers with uncertainty. A weak match against an existing master is a doubt, not a decision.

## Future Notes

- Matching a party to an existing ledger master is the hard part, and getting it wrong is expensive.
- The same item classifies differently at different companies — which is why the Company Context Result is an input, not a nicety.
