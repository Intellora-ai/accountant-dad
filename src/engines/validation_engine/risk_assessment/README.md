# risk_assessment

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#105-risk_assessment).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Some entries are correct and still should not be posted unattended.

## Responsibility

Owns the **Risk Assessment** — what *posting this* would expose the business to: compliance exposure, materiality, reversibility, audit visibility.

Distinct from Engine 3's **Accounting Risk Analysis**, which rates the reasoning rather than the consequences.

## Input

All previous validation results — Data, Accounting, Tax, Duplicate Detection — plus the Accounting Risk Analysis produced by the Accounting Engine's [`risk_analysis`](../../accounting_engine/risk_analysis/).

## Output

The **Risk Assessment** — risk level · severity · affected areas · confidence · recommendation.

## Boundary

**Can:** classify · score · prioritise.

**Cannot:** approve execution · reject execution · rewrite previous outputs · re-derive the decision's internal risk — it consumes `risk_analysis` rather than repeating it. Cannot reason about accounting treatment.

> **It rates. [`validation_decision`](../validation_decision/) decides.**

## Failure Behaviour

**Unknown risk defaults to higher severity.** An unassessed risk is never a zero risk.

## Future Notes

- **Adjacent-ownership warning.** `risk_analysis` looks inward at the reasoning; this looks outward at consequences. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- **This sub-engine's only output path is `Approved With Warning`.** It cannot approve or reject; its recommendation is what `validation_decision` converts into the status for a decision that is correct but whose consequences warrant a human. Remove that status and this sub-engine has nowhere to send its finding.
