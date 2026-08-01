# accounting_rules

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#83-accounting_rules).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Apply accounting principles and timing rules to the analyzed transaction.

## Responsibility

Owns **accounting rule application**, **accounting period treatment**, and **recognition timing rules**.

## Input

**Transaction Analysis Result** and **Company Context Result**.

## Output

**Accounting Rule Application Result** — applied accounting rules · accounting period treatment · recognition timing rules · rule references · assumptions · confidence.

## Boundary

**Can:** determine which principles apply · decide which accounting period the transaction affects · apply recognition timing rules · cite the rule behind every ruling.

**Cannot:** modify facts · create Tally postings · hide uncertainty · invent a rule from the transaction in front of it. **Cannot produce the Ledger Recommendation or the Tax Treatment Recommendation** — those belong to [`ledger_intelligence`](../ledger_intelligence/) and [`tax_intelligence`](../tax_intelligence/).

### Dates versus periods

| Component | Statement |
|---|---|
| `timeline_understanding` (Engine 2) | *"This event happened on this date."* |
| `accounting_rules` | *"This event belongs to this accounting period."* |

Invoice dated 31 March, paid 10 April — March closing or April? That is an accounting decision, not a timeline fact.

## Decision Authority

**Owns.** Accounting rule application + period treatment.

**Cannot.** Produce another sub-engine's recommendation.

No other component may override this Result.

## Failure Behaviour

Flag rule uncertainty. Where two principles could apply and the evidence does not distinguish them, both are recorded with the ambiguity — never resolved by preference.

## Future Notes

- Rules are declarative content and belong under [`src/rules/`](../../../rules/) once implementation begins; this component applies them, it does not store them.
- Each ruling carries the rule that produced it, so Validation can check the decision against its own claimed basis.
