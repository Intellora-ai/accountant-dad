# understanding

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#103-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Detect contradictions between evidence, understanding and accounting decisions.

## Responsibility

Owns **conflict identification** — finding where the pipeline disagrees with itself.

## Name and responsibility

A contradiction cannot be found without comprehending all three artifacts **together**. In Phase 1 this component comprehended the case and located the **doubts** in it; it now comprehends the case and locates the **contradictions** in it. Same faculty, sharper target.

## Input

The **Accounting Decision**, the **Business Understanding Object**, and the **Missing Information Result**.

## Output

**Conflict Analysis Result** — detected conflicts · conflicting assumptions · conflicting reasoning · conflict severity · affected accounting decisions.

## Boundary

**Can:** identify contradictions · preserve all conflicting information · maintain traceability.

**Cannot: resolve conflicts** · discard conflicting evidence · **choose one interpretation**.

## Failure Behaviour

**Every detected conflict remains visible until resolved by the responsible engine.** A conflict that cannot be characterised is still recorded, marked as uncharacterised.

## Future Notes

- Distinct from `story_builder` (Engine 2), which finds contradictions *among the facts*. This finds contradictions between the **decision and the facts it was built on**. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- Example: the Business Understanding Object says a laptop was bought for resale; the Accounting Decision treats it as Office Equipment. Neither is corrected — the disagreement is the output.
