# timeline_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Accounting is periodic; when each thing happened is load-bearing.

## Responsibility

Owns identification of every date and sequence in the transaction — document date, supply or service date, receipt date, due date — and their order relative to one another.

## Input

Structured Document, Confidence Report, and the transaction nature.

## Output

Timeline facts: each date, what it dates, and the resulting sequence of events.

## Boundary

Cannot decide the accounting period a transaction belongs to, or apply any cut-off rule. Cannot assume a missing date equals the document date. Cannot resolve a contradictory date sequence by choosing one — it reports the contradiction.

## Future Notes

- Ambiguous date formats are an extraction concern with a business consequence; where the format is genuinely ambiguous, that ambiguity travels forward rather than being silently normalised.
- Which date drives the accounting period is the Accounting Engine's decision, and it needs all of them to make it.
