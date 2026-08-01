# story_builder

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The Accounting Engine must receive one coherent account of events, not six fragments.

## Responsibility

Owns assembly of every Understanding output into a single **Transaction Story**, checked for internal contradiction, with each fact traced to its source and each gap explicitly marked absent.

## Input

The outputs of all six preceding Understanding sub-engines, plus the Confidence Report.

## Output

The **Transaction Story** — the sole artifact handed to the Accounting Engine.

## Boundary

Cannot add a fact no sub-engine produced. Cannot resolve a contradiction between sub-engines by choosing a side — the contradiction travels with the story. Cannot use accounting vocabulary. Cannot omit a fact because it appears unimportant.

## Future Notes

- The story is the Accounting Engine's *only* input. Anything omitted here is invisible downstream, permanently.
- Contradictions and marked gaps are what Clarification later turns into questions, so they need to be first-class parts of the structure, not annotations.
