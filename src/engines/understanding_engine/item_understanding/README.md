# item_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#83-item-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

What actually moved determines much of the treatment downstream.

## Responsibility

Owns **what moved** — the goods or services in the transaction: descriptions, quantities, units, rates, line values, and any stated classification codes.

## Input

The **Document Evidence Object**, and the **Transaction Understanding Result**.

## Output

**Item Understanding Result** — identified goods/services · descriptions · evidence references · confidence · unknown item details.

## Boundary

**Can:** identify the goods or services · record descriptions, quantities, units, rates and line values as stated · record stated classification codes as stated facts.

**Cannot:** decide **asset**, **expense** or **inventory** · classify items into accounting heads · determine tax rates from item descriptions or codes · recompute a line value the document states, nor supply one it omits.

## Decision Authority

**Owns.** What moved.

**Determines.** Goods and services, descriptions, quantities and rates as stated.

**Cannot.** Decide asset, expense or inventory.

No other component may override this Result.

## Failure Behaviour

Where a line's stated value disagrees with quantity × rate, both are reported and the disagreement is recorded as a conflict — choosing between them is not this component's call. Missing item detail is recorded in unknown item details.

## Future Notes

- A stated HSN or SAC code is an item fact and travels forward as one. What it implies for tax is `tax_intelligence`'s to decide.
- "Laptop" is an item description. "Fixed asset" is a conclusion, and it belongs two engines away.
