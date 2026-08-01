# transaction_analyzer

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A business story must first be read as an economic event before treatment can be considered.

## Responsibility

Owns determination of the economic substance of the transaction in accounting terms — what was acquired or disposed of, what obligation arose or was discharged, and which accounting event class it belongs to.

## Input

The Transaction Story.

## Output

An accounting characterisation of the event: substance, event class, and the aspects requiring treatment.

## Boundary

Cannot select specific ledgers or write any entry. Cannot read the Document Evidence Object or the raw artifact. Cannot re-derive business facts — it consumes the story as given.

## Future Notes

- Substance over form is the point of this component. Where the document's label and the economic reality disagree, the disagreement is the output.
- One document can carry several accounting events. Identifying that is this component's job; entering them is not.
