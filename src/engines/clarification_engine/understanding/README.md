# understanding

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

You cannot ask a good question about a case you do not understand.

## Responsibility

Owns comprehension of the accounting decision and its attached doubts — what was decided, on what basis, and what the doubts actually concern — in terms a human can be spoken to about.

## Input

The Accounting Decision, including its doubts and risks, plus the Business Understanding Object for context.

## Output

An internal case understanding: the decision restated in plain terms, with each doubt located in it.

## Boundary

Cannot change the decision. Cannot form an accounting judgement of its own. Cannot dispute the decision's correctness — that is the Validation Engine's role.

## Future Notes

- This is where accounting language becomes human language. Everything downstream in this engine depends on that translation being honest as well as plain.
- Not to be confused with the Understanding *Engine*, which comprehends the business event. This component comprehends the decision.
