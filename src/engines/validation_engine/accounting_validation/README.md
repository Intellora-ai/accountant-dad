# accounting_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#102-accounting_validation).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A decision must be checked by something that did not make it.

## Responsibility

Owns **accounting validation** — whether the entry is accounting-correct: correctly signed, posted to appropriate heads, and consistent with the rules its own reasoning invoked.

### Balance ≠ correctness

Engine 3's [`journal_intelligence`](../../accounting_engine/journal_intelligence/) guarantees **internal mathematical balance only**. This sub-engine judges whether the entry is **accounting-correct**.

```text
Wrong ledger + balanced journal = still wrong
```

A balanced journal on the wrong ledger fails here.

## Input

The Accounting Decision, including its stated reasoning and rulings · the Data Validation Result.

## Output

The **Accounting Validation Result** — accounting findings · failed accounting rules · journal correctness · ledger correctness · confidence. Each defect carries its severity and where in the decision it sits.

## Boundary

**Can:** validate · compare against accounting rules · report failures.

**Cannot:** redesign journals · select ledgers · rewrite accounting · fix, adjust or repair the entry. Cannot substitute its own preferred treatment for a defensible one. Cannot judge tax treatment — that is [`tax_validation`](../tax_validation/).

## Failure Behaviour

**Every accounting failure remains visible. Never repair accounting.** A defect is reported with its severity and location, never corrected.

## Future Notes

- Checking the decision against its own claimed rulings is the strongest available test and costs nothing extra — it is why the Accounting Engine is required to output its reasoning.
- "Defensible but not what I would have done" is not a defect. Only genuine incorrectness is.
