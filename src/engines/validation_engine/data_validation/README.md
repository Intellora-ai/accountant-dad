# data_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A perfectly reasoned entry built on broken data is still broken.

## Responsibility

Owns the judgement of whether the underlying data are sound — required fields present, dates within permissible range and sequence, totals reconciling to their lines, and every referenced master actually existing.

## Input

The Accounting Decision, the Transaction Story, the Confidence Report within the Document Evidence Object, and the company's master data.

## Output

A data verdict with findings.

## Boundary

Cannot correct, complete or normalise any data. Cannot judge whether the accounting treatment is right. Cannot lower a requirement because the data cannot meet it.

## Future Notes

- This is where a discrepancy faithfully carried from [`parser`](../../input_engine/parser/) is finally adjudicated — the whole pipeline preserved it for this moment.
- A data defect a human could resolve is routed to Clarification, not to Input. The routing rule is in [`docs/DATA_FLOW.md`](../../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on).
