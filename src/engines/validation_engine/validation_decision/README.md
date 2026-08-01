# validation_decision

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Five opinions must become one answer.

## Responsibility

Owns the single verdict — approve, reject, or flag for human attention — and the naming of the stage that must act on any rejection.

## Input

The verdicts and findings of all five preceding validators.

## Output

The **Validation Verdict**: the outcome, every finding that drove it, and for a rejection, the stage responsible.

## Boundary

Cannot create or amend a decision. Cannot post. Cannot approve a decision with an unresolved finding. Cannot return a rejection without naming the stage that must handle it. Cannot ask the human questions — a case needing questions returns to the Clarification Engine.

## Future Notes

- This is the only gate into the Tally Engine. Nothing reaches the books without passing through here.
- The routing table for rejections lives in [`docs/DATA_FLOW.md`](../../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on) and is part of the contract, not an implementation detail.
