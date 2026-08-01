# confidence

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Every downstream engine needs to know how much of this extraction to trust.

## Responsibility

Owns the honest measurement of extraction trustworthiness, per field and overall, and the identification of the specific regions that are weak.

## Input

Signals from [`cleaner`](../cleaner/), [`reader`](../reader/) and [`parser`](../parser/), plus the Structured Document.

## Output

The **Confidence Report**: per-field and overall trust scores, and a list of low-confidence regions with the reason for each.

## Boundary

Cannot re-read, re-parse or correct anything. Cannot reject a document or halt the pipeline. Cannot use business plausibility as evidence — it measures extraction quality, not whether the content makes commercial sense.

## Future Notes

- The report is read much later by Clarification's `uncertainty_detection` and by Validation's `data_validation`. Per-field granularity matters more than a single overall score.
- A reason attached to each weak region is what makes a good question possible downstream; a bare number is not enough.
