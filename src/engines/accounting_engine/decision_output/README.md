# decision_output

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Downstream engines must receive one decision, not nine partial opinions.

## Responsibility

Owns assembly of the complete **Accounting Decision** — entry, ledgers, tax treatment, reasoning, risks and doubts — as a single coherent artifact.

## Input

The outputs of all eight preceding Accounting sub-engines.

## Output

The **Accounting Decision**.

## Boundary

Cannot alter, reconcile or soften any component it assembles. Cannot post the decision. Cannot mark it approved, safe or final. Cannot omit doubts or risks from the assembled artifact.

## Future Notes

- Three different consumers read this artifact — Clarification, Validation and (once approved) Tally. It should be designed for all three rather than for the engine that produces it.
- The decision needs an identity that survives the clarification loop, so a decision before and after answers can be compared.
