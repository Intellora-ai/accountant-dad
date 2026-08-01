# rules

> **Defined as of Phase 0.** **Phase 1 placeholder — no implementation.**

## Purpose

**Shared, reusable business rules and accounting standards** — declarative content that engines *apply*.

Rules are content, not logic. Keeping them here rather than inside an engine means a treatment can be traced to the rule and the **rule version** that produced it, which is what makes a decision defensible later.

## What will belong here

- Accounting principles and policies applied by [`accounting_rules`](../engines/accounting_engine/accounting_rules/).
- GST, ITC and TDS rule content and rate tables applied by [`tax_intelligence`](../engines/accounting_engine/tax_intelligence/).
- Validation rule definitions applied by the Validation Engine.
- **Version identity** for all of the above, so a decision records which version it was made under.

## What must not belong here

- Any logic that **decides**. Engines apply rules; this directory holds them.
- Company-specific configuration — that is **Company Knowledge** in [`brain/`](../brain/).
- Anything an engine could not name as the basis for a ruling.

## Boundary against `brain/`

| | Holds |
|---|---|
| **`rules/`** | The rules themselves, versioned — applied deterministically |
| **`brain/`** | Knowledge *about* rules — standards, guidance, references, explanations. **Advisory, never binding.** |

## Status

Empty by design.
