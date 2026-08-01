# Clarification Engine

> Engine 4 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What must we ask a human?*

An engine that can both decide and ask will always prefer to guess, because guessing is cheaper. So doubt is produced by the Accounting Engine but acted on here — by an engine with no authority to invent answers, and no authority to decide accounting treatment.

## Responsibility

Resolve doubt by asking the human the fewest, sharpest questions, then update the decision.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`understanding`](understanding/) | Comprehension of the case and its doubts |
| [`uncertainty_detection`](uncertainty_detection/) | Which uncertainties actually block us |
| [`missing_information`](missing_information/) | What facts are absent, and who has them |
| [`question_generator`](question_generator/) | The fewest, clearest questions |
| [`answer_understanding`](answer_understanding/) | What the human actually answered |
| [`decision_updater`](decision_updater/) | Carrying answers back into the decision |
| [`stop_decision`](stop_decision/) | When to stop asking |

## Input

Accounting Decision with its doubts and risks; Confidence Report and Transaction Story as evidence of where uncertainty originated; the human's answers.

## Output

- **Question Set** — the minimal set of questions put to the human.
- **Resolved Facts** — the answers, structured, returned to the Accounting Engine.
- **Clarification Outcome** — whether questioning is complete, and why.

## Boundary

**Cannot invent answers. Cannot decide accounting treatment on its own.** Cannot mark a decision correct, approved or safe. Cannot post to Tally. Cannot ask the human to make the accounting decision on the system's behalf.

## Future Notes

- This engine runs only when an uncertainty is judged material. Most transactions should never reach it, and that is the design working.
- Its arrow points *back* to the Accounting Engine, not forward to Validation. A clarified decision is remade, never patched here.
