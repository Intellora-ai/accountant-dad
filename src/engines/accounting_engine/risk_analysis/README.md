# risk_analysis

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#87-risk_analysis).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Identify accounting decision risks.

## Responsibility

Owns **accounting risk identification** — how aggressive a treatment is, how thin its basis, how unusual the amount or pattern, how much it depends on a contested reading.

## Input

All accounting analysis outputs.

## Output

**Accounting Risk Analysis** — risk indicators · risk reasons · severity · confidence.

**Deliberately not named "Risk Assessment."** The Validation Engine owns [`risk_assessment`](../../validation_engine/risk_assessment/). Two engines may not own the same concept name.

## Boundary

**Can:** identify and rate risks in the reasoning · state the source and severity of each.

**Cannot:** reject decisions · modify decisions · block or gate anything · change a decision to reduce its own risk score · assess the consequences of *posting* — exposure, materiality and reversibility belong to Validation.

## Decision Authority

**Owns.** Identify accounting risks.

**Cannot.** Approve, reject or gate.

No other component may override this Result.

## Failure Behaviour

Report unknown risks. Where the risk of a treatment cannot be assessed, that inability is itself recorded — **an unassessed risk is not a zero risk.**

## Future Notes

- **Adjacent-ownership warning.** This looks *inward* at the reasoning; Validation's `risk_assessment` looks *outward* at consequences and consumes this rather than repeating it. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- A risk is not a doubt. A risk means "this could be wrong and it would matter"; a doubt means "I do not know."
