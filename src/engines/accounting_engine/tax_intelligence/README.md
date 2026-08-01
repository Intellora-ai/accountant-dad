# tax_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Tax treatment is a distinct discipline with its own rules and its own consequences.

## Responsibility

Owns the transaction's tax treatment — GST applicability, rate and classification, place of supply, reverse charge, input tax credit eligibility, and TDS.

## Input

The accounting characterisation, item facts and party facts from the story, and the company's registration and tax profile.

## Output

Tax treatment and the resulting tax lines, each with the basis on which it was determined.

## Boundary

Cannot validate its own compliance — that is the Validation Engine's [`tax_validation`](../../validation_engine/tax_validation/). Cannot file, report or reconcile anything with a tax authority. Cannot choose a rate because it is the most common one.

## Future Notes

- Rate tables and tax rules are versioned content and belong under [`src/rules/`](../../../rules/); a decision must record which version it was made under.
- Place of supply depends on party facts the story may not carry. That is a doubt worth raising, and it is often worth a question.
