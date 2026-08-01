# payment_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Whether and how money moved is a separate fact from what was supplied.

## Responsibility

Owns identification of how consideration moved or was promised — cash, bank, cheque, UPI or credit; paid, unpaid or part-paid; the terms and any instrument references stated.

## Input

Structured Document, Confidence Report, and the transaction nature.

## Output

Payment facts: mode, status, amounts, terms, and instrument references.

## Boundary

Cannot select a cash or bank ledger, or any account. Cannot infer payment from silence — an unstated payment status is recorded as unstated. Cannot reconcile against bank records.

## Future Notes

- Unstated payment status is extremely common and is one of the most frequent sources of a legitimate question later. Marking it absent — rather than assuming credit — is what makes that question possible.
- Part-payment needs amounts, not just a flag.
