# uncertainty_detection

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#102-uncertainty_detection).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Determine whether available information is reliable enough for downstream execution.

## Responsibility

Owns **uncertainty evaluation** — measuring and classifying uncertainty, and stating its impact on confidence.

## Name and responsibility

Detection is the act; analysis is its output. The Phase 1 name describes what it does, the artifact name what it produces — the same faculty named from opposite ends.

## Input

**Missing Information Result** and the **Accounting Decision**.

## Output

**Uncertainty Analysis Result** — uncertainty sources · uncertainty severity · confidence impact · affected decisions · supporting reasoning.

## Boundary

**Can:** measure uncertainty · classify uncertainty · preserve supporting evidence.

**Cannot:** increase confidence without evidence · remove uncertainty · modify accounting reasoning.

## Failure Behaviour

**Unknown uncertainty remains visible. Never convert uncertainty into certainty.** Uncertainty that cannot be classified is recorded as unclassified, not dropped.

## Future Notes

- Severity is what makes the next three steps possible: a conflict between two low-confidence readings is not the same finding as one between two reliable ones.
- It measures uncertainty in the **decision**, not in the extraction. Extraction confidence belongs to Engine 1's `confidence`.
