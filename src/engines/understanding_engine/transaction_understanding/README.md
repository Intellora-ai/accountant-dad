# transaction_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Before anything else can be understood, the kind of business event must be established.

## Responsibility

Owns identification of what kind of event occurred — a purchase, a sale, a return, an expense, a receipt, a payment, a transfer, a credit or debit note.

## Input

The Document Evidence Object.

## Output

The transaction's nature in business terms, with the evidence supporting it.

## Boundary

Cannot map the event to a voucher type or accounting classification — that is the Accounting Engine's. Cannot decide the event type by what would be convenient to post.

## Future Notes

- Its output constrains every other Understanding sub-engine, so it runs first.
- A document whose nature is genuinely ambiguous should produce an ambiguous result carried forward, not a confident guess. The ambiguity is what earns a question later.
