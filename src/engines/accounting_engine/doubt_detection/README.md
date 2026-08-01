# doubt_detection

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Guessing quietly is the worst failure this system could have; doubt must be produced as an output.

## Responsibility

Owns identification of every point at which the accounting decision is uncertain, and the precise statement of what fact would remove each doubt.

## Input

The decision components, the rulings, the Identified Unknowns in the Business Understanding Object, and the Confidence Report within the Document Evidence Object.

## Output

Structured doubts: what is uncertain, why, and the specific fact that would resolve it.

## Boundary

Cannot ask the user anything. Cannot resolve its own doubt by guessing, defaulting, or selecting the most common treatment. Cannot suppress a doubt because it is inconvenient or would delay posting. Cannot judge which doubts matter enough to block posting — that is the Clarification Engine's [`uncertainty_detection`](../../clarification_engine/uncertainty_detection/).

## Future Notes

- **Adjacent-ownership warning.** This *produces* doubt; `uncertainty_detection` triages it for materiality. Production versus materiality — see [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- "The specific fact that would resolve it" is the hard requirement and the valuable one: a doubt that names no resolving fact cannot become a good question.
