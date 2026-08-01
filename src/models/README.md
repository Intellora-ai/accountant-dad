# models

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Purpose

Internal representations of the domain concepts the system reasons about — a party, an item, a ledger, an entry, a doubt.

## What will belong here

Shared representations of concepts that more than one engine must speak about in the same terms.

## What must not belong here

- Business logic of any kind. A representation carries no judgement.
- Anything that decides, validates or posts.
- Representations belonging to one engine alone — those are that engine's internal concern.

## Relationship to [`schemas/`](../schemas/)

`schemas/` describes the shape of the **artifacts that cross between engines** — the Transaction Story, the Accounting Decision, the Validation Verdict. `models/` describes the **domain concepts** those artifacts are built from.

The boundary between the two must be drawn deliberately when implementation begins. Until then: **stop and ask** rather than assuming.

## Status

Empty by design.
