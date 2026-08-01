# error_handler

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A failed post has a cause, and the cause determines who must fix it.

## Responsibility

Owns classification of failures — transport, Tally rejection, data defect, or translation defect — and routing each to the stage that must handle it.

## Input

Posting Results indicating failure, transport-level errors, and translation errors.

## Output

A **Classified Error**: category, cause, whether a retry is permissible, and the stage that must act.

## Boundary

Cannot correct data or re-decide anything. Cannot retry directly — it tells [`posting_manager`](../posting_manager/) whether retry is permissible. Cannot route a failure to a stage that could not have caused it. Cannot suppress an error it cannot classify.

## Future Notes

- The categories differ in one decisive way: a transport failure is retryable, a data or translation defect never is. Confusing them produces either lost work or a retry storm.
- An unclassifiable error goes to a human. It is never dropped, and never retried on the assumption that it might be transient.
