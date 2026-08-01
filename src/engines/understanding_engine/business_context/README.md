# business_context

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#86-business-context).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The same document means different things at different businesses; the transaction must be situated in this one's reality.

Owns the question *"why did this happen?"* — **as indicators, never as conclusion.**

## Responsibility

Owns **operating context** — whether the party is recurring, whether the pattern is normal for this business, which location or branch is involved, what this business actually does, and observed indicators of why this transaction exists in its operations.

Runs **after** the preceding five sub-engines: "is this normal for this business?" cannot be answered before knowing what *this* is.

## Input

The **Document Evidence Object**, the preceding five Results, and the business's own operating history.

## Output

**Business Context Result** — context clues · business purpose indicators · supporting evidence · confidence · unknown context.

## Boundary

**Can:** record recurrence and normality · record location or branch and what this business does · record business purpose **indicators**.

**Cannot:** apply accounting rules · read or apply the company's accounting configuration · conclude a treatment because "this is how it is usually posted" · **conclude intent**.

## Decision Authority

**Owns.** Operating context.

**Determines.** Context clues and business purpose indicators.

**Cannot.** Apply accounting rules.

No other component may override this Result.

## Failure Behaviour

Absent context is recorded in unknown context. Purpose indicators are always presented as indicators with their supporting evidence — never promoted to a conclusion, and never used to fill a gap another sub-engine left. Recurrence is a strong signal and a dangerous one: it is offered as context for a decision, never as a substitute for making one.

## Future Notes

- **Adjacent-ownership warning.** This is the *operating* reality of the business; the Accounting Engine's [`company_understanding`](../../accounting_engine/company_understanding/) is its *accounting configuration*. Operations versus configuration — see [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- "Indicator" versus "conclusion" is the whole discipline of this component. An indicator carries its evidence and can be disagreed with; a conclusion cannot.
