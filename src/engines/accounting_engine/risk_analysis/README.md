# risk_analysis

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A decision that is defensible and a decision that is risky are different things, and the difference must be stated.

## Responsibility

Owns assessment of how risky *the decision this engine just made* is — how aggressive the treatment is, how thin its basis, how unusual the amount or pattern, how much it depends on a contested reading.

## Input

The assembled components of the decision, the rulings behind them, and the Business Understanding Object.

## Output

A risk profile of the decision: each risk, its source, and its severity.

## Boundary

Cannot block, approve or gate anything. Cannot assess the consequences of *posting* — exposure, materiality and reversibility belong to the Validation Engine's [`risk_assessment`](../../validation_engine/risk_assessment/). Cannot change the decision to reduce its own risk score.

## Future Notes

- **Adjacent-ownership warning.** This looks *inward* at the reasoning; `risk_assessment` looks *outward* at consequences, and consumes this output rather than repeating it. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- A risk is not a doubt. A risk means "this could be wrong and it would matter"; a doubt means "I do not know". They travel separately.
