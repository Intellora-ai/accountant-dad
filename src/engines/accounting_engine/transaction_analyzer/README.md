# transaction_analyzer

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#81-transaction_analyzer).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Determine the accounting nature of the business event.

## Responsibility

Owns **initial accounting interpretation** — the accounting-relevant facts of the understood event: substance, event class, and the aspects requiring treatment.

Runs **first** in the chain; its Result feeds `accounting_rules`, `ledger_intelligence` and `tax_intelligence`.

## Input

The **Business Understanding Object**.

## Output

**Transaction Analysis Result** — transaction category · accounting implications · supporting facts · unknowns · confidence.

## Boundary

**Can:** analyze transaction meaning in accounting terms · identify accounting implications · cite the understanding evidence behind each.

**Cannot:** create final journal entries · modify the business story · decide tax · select ledgers · read the Document Evidence Object or the raw artifact.

## Decision Authority

**Owns.** Understand accounting-relevant transaction facts.

**Cannot.** Decide accounting treatment, tax, or ledgers.

No other component may override this Result — not a sibling sub-engine, and not the parent, which assembles but never overrides.

## Failure Behaviour

Return incomplete analysis with uncertainty. Where the accounting nature cannot be determined, that is recorded in unknowns — never resolved by picking the likeliest category.

## Future Notes

- Substance over form is the point. Where the document's label and the economic reality disagree, the disagreement is the output.
- One document can carry several accounting events. Identifying that is this component's job; entering them is not.
