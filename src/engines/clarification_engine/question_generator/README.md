# question_generator

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The human's time is the scarcest resource in the system.

## Responsibility

Owns the wording, ordering and minimality of what is put to the human — the fewest questions that resolve the most blocking uncertainty, phrased so the person who has the answer can give it.

## Input

Ranked material uncertainties and the missing-fact list.

## Output

The **Question Set** — each question, what it resolves, and the form of answer expected.

## Boundary

Cannot ask about anything already known or already answered. Cannot ask in accounting jargon the respondent cannot be expected to answer. Cannot ask the human to choose the accounting treatment on the system's behalf. Cannot ask a question whose answer would change nothing.

## Future Notes

- One question can resolve several uncertainties. Finding that question is the whole value of this component.
- "What form of answer is expected" is what makes [`answer_understanding`](../answer_understanding/) able to tell an answer from a non-answer.
