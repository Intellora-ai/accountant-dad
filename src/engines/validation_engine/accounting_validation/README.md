# accounting_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A decision must be checked by something that did not make it.

## Responsibility

Owns the judgement of whether the entry is accounting-correct — balanced, correctly signed, posted to appropriate heads, and consistent with the rules its own reasoning invoked.

## Input

The Accounting Decision, including its stated reasoning and rulings.

## Output

An accounting verdict with findings: each defect, its severity, and where in the decision it sits.

## Boundary

Cannot fix, rewrite or adjust the entry. Cannot substitute its own preferred treatment for a defensible one. Cannot judge tax treatment — that is [`tax_validation`](../tax_validation/).

## Future Notes

- Checking the decision against its own claimed rulings is the strongest available test and costs nothing extra — it is why the Accounting Engine is required to output its reasoning.
- "Defensible but not what I would have done" is not a defect. Only genuine incorrectness is.
