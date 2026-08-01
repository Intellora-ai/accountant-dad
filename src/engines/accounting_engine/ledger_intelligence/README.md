# ledger_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

An entry is only as correct as the accounts it touches.

## Responsibility

Owns selection of the ledger accounts involved, their groups, and the determination that an existing master is inadequate and a new ledger is required.

## Input

The accounting characterisation, the applicable rulings, and the company's chart of accounts and existing masters.

## Output

Ledger selection: each account involved, its group, and — where required — a specification for a ledger that does not yet exist.

## Boundary

Cannot create a ledger in Tally or anywhere else; it specifies, it does not provision. Cannot compute amounts. Cannot decide the debit/credit direction — that is [`journal_intelligence`](../journal_intelligence/).

## Future Notes

- **Adjacent-ownership warning.** This component decides *which accounts*; `journal_intelligence` decides *which side and how much*. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- Matching a party to an existing ledger master is the hard part, and getting it wrong is expensive. A weak match is a doubt, not a decision.
