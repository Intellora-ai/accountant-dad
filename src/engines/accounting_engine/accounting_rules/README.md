# accounting_rules

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Treatment must follow principle, not habit.

## Responsibility

Owns the body of accounting principles and policies that govern treatment — double entry, revenue and expense recognition, capital versus revenue, matching, accrual — and the determination of which apply to this event.

## Input

The accounting characterisation from [`transaction_analyzer`](../transaction_analyzer/), and the company's accounting profile.

## Output

The applicable rule set, and the ruling each rule produces for this transaction.

## Boundary

Cannot invent a rule from the transaction in front of it. Cannot own tax rules — GST, ITC and TDS belong to [`tax_intelligence`](../tax_intelligence/). Cannot select ledgers or construct entries.

## Future Notes

- Rules are declarative content and belong under [`src/rules/`](../../../rules/) once implementation begins; this component applies them, it does not store them.
- Each ruling should carry the rule that produced it. Validation checks the decision against its own claimed basis.
