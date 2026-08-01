# company_understanding

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Every decision above is constrained by the accounting reality of this specific company.

## Responsibility

Owns knowledge of the company's accounting configuration — chart of accounts, existing ledger and group masters, GST registrations, method and basis of accounting, financial year, and book conventions.

## Input

The company's accounting configuration and master data.

## Output

The company accounting profile that constrains every other Accounting sub-engine.

## Boundary

Cannot decide treatment for a transaction. Cannot create or modify a master. Cannot own the business's *operating* context — recurrence, branch and trade pattern belong to the Understanding Engine's [`business_context`](../../understanding_engine/business_context/).

## Future Notes

- **Adjacent-ownership warning.** Configuration, not operations. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- This profile is read by nearly every other component here, so it is a constraint, not a suggestion — and it is the natural place for a company's conventions to be made explicit rather than assumed.
