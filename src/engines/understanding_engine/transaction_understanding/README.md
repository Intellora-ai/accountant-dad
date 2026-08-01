# transaction_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#81-transaction-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Before anything else can be understood, the kind of business event must be established.

## Responsibility

Owns the **base event** — identification of what kind of event occurred: a purchase, a sale, a return, an expense, a receipt, a payment, a transfer, a credit or debit note.

Runs **first** in the dependency graph. Its Result is received by `party`, `item`, `payment` and `timeline`, because the event kind changes how everything else is read.

## Input

The **Document Evidence Object**.

## Output

**Transaction Understanding Result** — identified event · supporting evidence references · confidence level · unknown information · conflicts detected.

## Boundary

**Can:** identify the event kind · cite the evidence supporting it · report the event as ambiguous where the evidence is ambiguous.

**Cannot:** decide accounting treatment · map the event to a voucher type or accounting classification · decide the event type by what would be convenient to post.

## Decision Authority

**Owns.** The base event.

**Determines.** What kind of business event occurred, and the evidence supporting it.

**Cannot.** Decide accounting treatment or voucher type.

No other component may override this Result — not a sibling sub-engine, and not the parent Understanding Engine, which assembles outputs but never overrides them.

## Failure Behaviour

Where the event kind cannot be established, the Result says so. An ambiguous document produces an ambiguous Result carried forward — never a confident guess. The ambiguity is recorded in unknown information, with the competing readings preserved as conflicts detected.

## Future Notes

- Its output constrains every other Understanding sub-engine, which is why it runs first.
- Ambiguity here is what earns a question later. A confident guess forecloses that permanently.
