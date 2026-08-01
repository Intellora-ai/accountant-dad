# Validation Engine

> Engine 5 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*Is this safe to post?*

A decision reviewed by its own author is not reviewed. This engine exists as a separate authority precisely so that it can reject — and so that "the entry is correct" is a claim something other than the decision-maker has tested.

## Responsibility

Judge whether the decision is safe to post — correctness, tax, data integrity, duplicates, risk.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`accounting_validation`](accounting_validation/) | Is the entry accounting-correct |
| [`tax_validation`](tax_validation/) | Is the tax treatment compliant |
| [`data_validation`](data_validation/) | Are the underlying data sound |
| [`duplicate_detection`](duplicate_detection/) | Have we recorded this already |
| [`risk_assessment`](risk_assessment/) | What posting this would expose us to |
| [`validation_decision`](validation_decision/) | Approve, reject, or flag |

## Input

Accounting Decision — original or updated after clarification — with supporting evidence: Transaction Story, the Confidence Report within the Document Evidence Object, and prior posted transactions.

## Output

- **Validation Verdict** — approve, reject, or flag for human attention.
- **Findings** — every issue detected, with severity and the stage responsible for it.

## Boundary

**Cannot create decisions.** Cannot amend or repair a decision it is judging — a defect is reported, never fixed. Cannot recompute ledgers, entries or tax. Cannot post to Tally. Cannot ask the human questions. Cannot pass a decision forward with an unresolved finding.

## Future Notes

- A rejection must name the stage that must handle it, or the pipeline has nowhere to send the work. See [`docs/DATA_FLOW.md`](../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on).
- A *flag* is not a rejection: the decision is sound, but posting it unattended is judged unsafe. It goes to a human, not back to a stage.
