# story_builder

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#87-story-builder).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The Accounting Engine must receive one coherent account of events, not six fragments.

## Responsibility

Owns **assembly** — combining the six Results into the **Business Understanding Object**, and creating the **Transaction Story** component from them.

## Input

All six preceding sub-engine Results, plus the Confidence Report within the Document Evidence Object.

## Output

The **Business Understanding Object** — the sole artifact handed to the Accounting Engine.

```text
Business Understanding Object
├── Transaction Story ................. the narrative this component creates
├── Supporting Understanding Data ..... the six Results, unaltered
├── Identified Unknowns
└── Confidence Assessment
```

## Boundary

| **CAN** | **CANNOT** |
|---|---|
| Combine six sub-engine outputs | Change source observations |
| Organize information | Override sub-engine results |
| Create the Transaction Story component | **Resolve conflicts** |
| Create the Business Understanding Object | **Choose the "correct" interpretation when evidence disagrees** |
| | **Remove unknowns** |
| | **Increase confidence** |
| | Create accounting conclusions |
| | Add a fact no sub-engine produced |
| | Use accounting vocabulary |

**Story Builder consumes outputs but cannot rewrite history.**

## Decision Authority

**Owns.** Assembly.

**Determines.** The Transaction Story and the Business Understanding Object.

**Cannot.** Resolve conflicts · override results · remove unknowns · increase confidence.

> **Story Builder creates the artifact. The Understanding Engine owns it.**

Story Builder does not become an independent owner. Assembly is not permission to edit — an assembler that owned what it assembled would eventually start improving it.

## Failure Behaviour

Where the Results disagree, the narrative reports the disagreement rather than selecting a reading — **a story containing an unresolved conflict is the correct output, not a failure.** Unknowns are carried into Identified Unknowns intact. Where the six Results cannot be made into a coherent narrative at all, that incoherence is itself reported, with the Results preserved unchanged beneath it.

## Future Notes

- The Business Understanding Object is the Accounting Engine's *only* input. Anything omitted here is invisible downstream, permanently.
- The six Results travel alongside the narrative rather than being replaced by it, so a downstream engine can always read what the story was built on.
