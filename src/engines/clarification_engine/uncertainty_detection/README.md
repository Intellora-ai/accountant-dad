# uncertainty_detection

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Not every uncertainty is worth a human's attention; asking about all of them is as bad as asking about none.

## Responsibility

Owns the judgement of which uncertainties *across the whole case* — extraction confidence, story gaps, accounting doubts — are material enough to block posting, and their relative priority.

## Input

The case understanding, the accounting doubts, the Identified Unknowns in the Business Understanding Object, and the Confidence Report within the Document Evidence Object.

## Output

Ranked material uncertainties, each with the reason it blocks posting.

## Boundary

Cannot resolve an uncertainty. Cannot raise an uncertainty that has no evidence upstream. Cannot detect *accounting* ambiguity itself — it consumes what [`doubt_detection`](../../accounting_engine/doubt_detection/) produced and judges materiality.

## Future Notes

- **Adjacent-ownership warning.** `doubt_detection` produces doubt from accounting reasoning; this component triages uncertainty from all three upstream sources. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- This is the gate for the whole engine: an empty ranked list means clarification is skipped entirely.
