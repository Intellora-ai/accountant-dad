# tax_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#85-tax_intelligence).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Analyze tax implications — *what tax treatment applies?*

## Responsibility

Owns **tax treatment reasoning** — GST applicability, rate and classification, place of supply, reverse charge, input tax credit eligibility, TDS.

## Input

**Transaction Analysis Result** and **Company Context Result**.

## Output

**Tax Treatment Recommendation** — applicable tax treatment · tax assumptions · risks · confidence.

Contributed into the **Accounting Treatment Result**, which the parent engine assembles.

## Boundary

**Can:** determine tax applicability, rate and classification · place of supply · reverse charge · ITC eligibility · TDS · and state the basis for each.

**Cannot:** file taxes · guarantee compliance · override the accounting decision · modify transaction facts · apply unsupported assumptions · validate its own compliance — that is Validation's `tax_validation`.

## Decision Authority

**Owns.** Tax treatment reasoning.

**Cannot.** Select ledgers, construct the journal, or approve anything.

No other component may override this Result — including `accounting_rules`, which does **not** produce it.

## Failure Behaviour

Flag tax uncertainty. A rate is never chosen for being the most common one; where the basis is absent, the treatment is recorded as undetermined.

## Future Notes

- Rate tables and tax rules are versioned content and belong under [`src/rules/`](../../../rules/); a decision must record which version it was made under.
- Place of supply depends on party facts the understanding may not carry. That is a doubt worth raising, and often worth a question.
