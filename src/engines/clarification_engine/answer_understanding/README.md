# answer_understanding

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A human's reply is prose; the system needs facts.

## Responsibility

Owns interpretation of the human's answers into structured facts, and the judgement of whether each answer actually addresses the question asked.

## Input

The Question Set and the human's replies.

## Output

**Resolved Facts** — structured, attributed to the question they answer — plus any question left unanswered or answered inadequately.

## Boundary

Cannot infer beyond what was said. Cannot accept a non-answer as an answer. Cannot correct or complete an answer it finds implausible — it records the answer and flags the implausibility.

## Future Notes

- "Yes" to a two-part question is a non-answer. Detecting that is this component's job, and it is what keeps a bad answer from becoming a bad posting.
- A flagged implausible answer is evidence for [`stop_decision`](../stop_decision/) and for Validation; it is not grounds to overrule the human.
