# risk_assessment

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Some entries are correct and still should not be posted unattended.

## Responsibility

Owns the judgement of what *posting this* would expose the business to — compliance exposure, materiality, reversibility, and audit visibility.

## Input

The Accounting Decision, the risk profile produced by the Accounting Engine's [`risk_analysis`](../../accounting_engine/risk_analysis/), and the findings of the other validators.

## Output

A posting-risk rating with the exposures that drive it.

## Boundary

Cannot re-derive the decision's internal risk — it consumes `risk_analysis` rather than repeating it. Cannot reason about accounting treatment. Cannot block posting itself; it rates, [`validation_decision`](../validation_decision/) decides.

## Future Notes

- **Adjacent-ownership warning.** `risk_analysis` looks inward at the reasoning; this looks outward at consequences. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- This is what most often converts a technically-valid decision into a *flag* rather than an approval, and that is the intended use.
