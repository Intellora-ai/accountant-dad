# doubt_detection

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#88-doubt_detection).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Identify unresolved accounting uncertainty.

## Responsibility

Owns **accounting doubts** — where the decision is uncertain, and the specific fact that would resolve each.

## Input

All accounting outputs.

## Output

**Accounting Doubt Report** — missing information · conflicts · required clarification areas.

## Boundary

**Can:** identify where the decision is uncertain · name the fact that would resolve each doubt · record conflicts between sub-engine Results.

**Cannot:** **ask users directly** · resolve doubts itself · guess · default · select the most common treatment · suppress a doubt because it is inconvenient or would delay posting · judge which doubts block posting — that is the Clarification Engine's [`uncertainty_detection`](../../clarification_engine/uncertainty_detection/).

## Decision Authority

**Owns.** Identify uncertainty.

**Cannot.** Resolve it, or ask anyone about it.

No other component may override this Result.

## Failure Behaviour

Preserve uncertainty. A doubt that cannot be characterised precisely is still recorded, marked as uncharacterised — never dropped for being hard to describe.

## Future Notes

- **Adjacent-ownership warning.** This *produces* doubt from accounting reasoning; `uncertainty_detection` triages it for materiality across the whole case. Production versus materiality.
- "The specific fact that would resolve it" is the hard requirement and the valuable one: a doubt that names no resolving fact cannot become a good question.
