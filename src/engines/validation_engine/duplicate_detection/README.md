# duplicate_detection

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The same invoice posted twice is a real and common loss.

## Responsibility

Owns the judgement of whether this transaction has already been recorded — by document identity, by party and amount and date, or by economic equivalence.

## Input

The Accounting Decision and Transaction Story, and previously posted transactions and audit records.

## Output

A duplicate verdict with any matches found and the strength of each match.

## Boundary

Cannot delete, merge, reverse or amend any existing record. Cannot decide what to do about a duplicate — it reports the match; [`validation_decision`](../validation_decision/) decides.

## Future Notes

- Distinct from [`posting_manager`](../../tally_engine/posting_manager/)'s single-post guarantee: that prevents the *same decision* being posted twice; this detects a *different decision* recording the same event.
- Legitimate near-duplicates exist — a monthly retainer from the same vendor at the same amount. Match strength matters more than a boolean.
