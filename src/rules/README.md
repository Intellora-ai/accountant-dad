# rules

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Purpose

Declarative rule content — the accounting principles and tax rules that the Accounting Engine *applies*.

Rules are content, not logic. Keeping them here rather than inside an engine means a treatment can be traced to the rule and the rule version that produced it, which is what makes a decision defensible later.

## What will belong here

- Accounting principles and policies applied by [`accounting_rules`](../engines/accounting_engine/accounting_rules/).
- GST, ITC and TDS rule content and rate tables applied by [`tax_intelligence`](../engines/accounting_engine/tax_intelligence/).
- Version identity for the above, so a decision can record which version it was made under.

## What must not belong here

- Any logic that *decides*. The Accounting Engine applies rules; this directory holds them.
- Validation logic. The Validation Engine judges against rules; it does not own them either.
- Anything an engine could not name as the basis for a ruling.

## Status

Empty by design. Nothing is added until the Accounting Engine's implementation phase begins.
