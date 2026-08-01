# timeline_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#85-timeline-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Accounting is periodic; when each thing happened is load-bearing.

## Responsibility

Owns **when** — every date and sequence in the transaction: document date, supply or service date, receipt date, due date, and their order relative to one another.

## Input

The **Document Evidence Object**, and the **Transaction Understanding Result**.

## Output

**Timeline Understanding Result** — dates · event sequence · time relationships · confidence · missing dates.

## Boundary

**Can:** identify every date · record what each date dates · record the sequence and the relationships between them.

**Cannot:** decide accounting period treatment, or apply any cut-off rule · assume a missing date equals the document date · resolve a contradictory date sequence by choosing one.

## Decision Authority

**Owns.** When.

**Determines.** Dates, event sequence, and time relationships.

**Cannot.** Decide accounting period treatment.

No other component may override this Result.

## Failure Behaviour

Missing dates are recorded in missing dates. A contradictory sequence is recorded as a conflict and carried forward unresolved. Where a date format is genuinely ambiguous, the ambiguity travels rather than being silently normalised.

## Future Notes

- Which date drives the accounting period is the Accounting Engine's decision, and it needs all of them to make it.
- Ambiguous date formats are an extraction concern with a business consequence; the ambiguity belongs in the Result, not in a normalisation step.
