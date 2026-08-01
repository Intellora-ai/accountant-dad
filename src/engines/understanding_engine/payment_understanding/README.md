# payment_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#84-payment-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Whether and how money moved is a separate fact from what was supplied.

## Responsibility

Owns **money movement** — how consideration moved or was promised: cash, bank, cheque, UPI or credit; paid, unpaid or part-paid; the terms, amount relationships and any instrument references stated.

## Input

The **Document Evidence Object**, and the **Transaction Understanding Result**.

## Output

**Payment Understanding Result** — payment method · payment references · amount relationships · confidence · unknown payment details.

## Boundary

**Can:** identify how consideration moved or was promised · record status as paid, unpaid or part-paid with amounts · record terms and instrument references as stated · record relationships between amounts.

**Cannot:** create cash or bank entries, or select any account · infer payment from silence · reconcile against bank records.

## Decision Authority

**Owns.** Money movement.

**Determines.** Payment method, references, and amount relationships.

**Cannot.** Create cash or bank entries.

No other component may override this Result.

## Failure Behaviour

An unstated payment status is recorded as unstated — never assumed to be credit, never assumed to be paid. It is one of the most frequent legitimate sources of a question later, and marking it absent is what makes that question possible. Part-payment without amounts is an unknown, not a flag.

## Future Notes

- Where the document amount and a payment record disagree, that is a conflict this component surfaces and does not settle — see [Conflict Handling](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#10-conflict-handling).
- Part-payment needs amounts, not just a flag.
