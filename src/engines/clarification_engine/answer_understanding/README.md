# answer_understanding

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#105-answer_understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Determine the order in which clarification should occur. Critical accounting blockers must always be resolved before cosmetic or informational clarification.

## Responsibility

Owns **clarification priority**.

## Name and responsibility

Priority is a judgement about **answers**. Nothing can be ranked without understanding how much the answer to each clarification would change the decision. In Phase 1 this component reasoned about answers received; it now reasons about the weight of answers **not yet received**. It is the answer-centric component in both eras.

## Input

**Clarification Necessity Result**.

## Output

**Clarification Priority Result** — priority level · affected decision · business impact · accounting impact · urgency reasoning.

Priority levels: **Critical · High · Medium · Low.**

## Boundary

**Can:** prioritise clarification · group related clarification · determine execution order.

**Cannot:** remove clarification requirements · modify accounting reasoning · modify previous artifacts.

## Failure Behaviour

**Unknown priority defaults to High until sufficient information exists.** Under-prioritising an unknown is the more expensive error.

## Future Notes

- One answer often resolves several clarifications at once. Finding that answer is where grouping earns its place.
- Priority is a field of the Clarification Request, which is why this runs before `question_generator` rather than after it.
