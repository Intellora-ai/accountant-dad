# business_context

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The same document means different things at different businesses; the transaction must be situated in this one's reality.

## Responsibility

Owns the contextual, non-accounting facts that situate the transaction — whether the party is recurring, whether the pattern is normal for this business, which location or branch is involved, what this business actually does.

## Input

Structured Document, the outputs of the other Understanding sub-engines, and the business's own operating history.

## Output

Contextual facts: recurrence, normality, location, and trade-pattern observations.

## Boundary

Cannot read or apply the company's accounting configuration — chart of accounts, ledger masters, registration status and accounting policy belong to the Accounting Engine's [`company_understanding`](../../accounting_engine/company_understanding/). Cannot conclude a treatment because "this is how it is usually posted."

## Future Notes

- **Adjacent-ownership warning.** This is the *operating* reality of the business; `company_understanding` is its *accounting configuration*. Operations versus configuration — see [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- Recurrence is a strong signal and a dangerous one: it is offered as context for a decision, never as a substitute for making one.
