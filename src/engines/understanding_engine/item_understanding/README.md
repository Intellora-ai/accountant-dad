# item_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

What actually moved determines much of the treatment downstream.

## Responsibility

Owns identification of the goods or services in the transaction — descriptions, quantities, units, rates, line values, and any stated classification codes.

## Input

Structured Document, Confidence Report, and the transaction nature.

## Output

Item facts: one structured record per line, plus stated totals.

## Boundary

Cannot classify items into accounting heads. Cannot determine tax rates from item descriptions or codes. Cannot recompute a line value the document states, nor supply one it omits.

## Future Notes

- A stated HSN or SAC code is an item fact and travels forward as one. What it implies for tax is `tax_intelligence`'s to decide.
- Where a line's stated value disagrees with quantity × rate, both are reported. Choosing between them is not this engine's call.
