# voucher_translator

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Tally has its own representation, and something must speak it.

## Responsibility

Owns the faithful translation of an approved accounting decision into Tally's voucher representation.

## Input

The **Approved Accounting Decision**.

## Output

A Tally voucher payload, together with the mapping from each decision element to each payload element.

## Boundary

Cannot alter the accounting meaning of what it translates. Cannot supply a value the decision left undecided — a missing value is a translation error, not a gap to fill. Cannot choose between two possible representations on accounting grounds.

## Future Notes

- The element mapping is what lets a Tally rejection be traced back to the part of the decision that caused it.
- Where two Tally representations are equally faithful, pick on technical grounds and record the choice. Picking on accounting grounds would be reasoning, which this engine may not do.
