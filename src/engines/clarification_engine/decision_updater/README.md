# decision_updater

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

An answer is worthless until it changes the decision.

## Responsibility

Owns carrying resolved facts back so that the decision is remade under the Accounting Engine's authority, and recording the difference between the decision before and after.

## Input

Resolved Facts, and the Accounting Decision as it stood.

## Output

The **Updated Accounting Decision**, together with a record of what changed and which answer caused it.

## Boundary

Cannot author accounting treatment — it applies answers, the Accounting Engine decides. Cannot edit a decision's reasoning in place, or silently overwrite it. Cannot discard a doubt that the answers did not actually resolve.

## Future Notes

- The temptation to patch the decision here instead of returning to the Accounting Engine is the single most likely architectural erosion in the system. Returning facts, not edits, is the rule.
- The before/after record is what makes a clarified decision auditable later.
