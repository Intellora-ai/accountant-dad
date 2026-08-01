# response_processor

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

"Tally replied" and "the entry is in the books" are not the same statement.

## Responsibility

Owns interpretation of what Tally returned into one definite outcome — posted, rejected, or partial — with the identifiers Tally assigned.

## Input

Tally's raw responses and the corresponding post attempts.

## Output

The **Posting Result**: outcome, Tally identifiers, and the raw response it was derived from.

## Boundary

Cannot retry or resubmit. Cannot interpret an ambiguous or absent response as success. Cannot classify or route a failure — that is [`error_handler`](../error_handler/).

## Future Notes

- The raw response is retained alongside the interpretation so that a wrong interpretation can be found later. This matters more here than almost anywhere else in the system.
- Partial success is a real Tally outcome and the most damaging one to mis-read; it deserves to be a first-class result, not a variant of failure.
