# voucher_translator

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#91-voucher_translator).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A destination system has its own representation, and something must speak it.

## Responsibility

Owns **translation only** — the faithful conversion of an approved Accounting Decision into the destination's voucher representation, with format mapping, field mapping and export structure.

**Destination-parametric by contract**, not Tally-shaped by assumption. Tally is the implementation path today; the boundary is defined for others without building them.

## Input

Accounting Decision · Validation Decision · Destination System.

## Output

The **Translated Voucher**, together with the mapping from each decision element to each payload element.

## Boundary

**Can:** map fields · convert formats · generate the destination-specific voucher · verify that required destination fields exist.

**Cannot:** change accounting treatment · change ledger selection · change journal entries · change tax treatment · **modify accounting meaning**. Cannot supply a value the decision left undecided — a missing value is a translation error, not a gap to fill. Cannot choose between two possible representations on accounting grounds.

## Failure Behaviour

**Stop execution · preserve the Accounting Decision · report translation failure · never invent missing values.**

## Future Notes

- The element mapping is what lets a destination's rejection be traced back to the part of the decision that caused it.
- Where two representations are equally faithful, pick on technical grounds and record the choice. Picking on accounting grounds would be reasoning, which this engine may not do.
