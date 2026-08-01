# party_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#82-party-understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A transaction is between people; who they are and what role they played is a fact about the event.

## Responsibility

Owns **entity identification** — every party to the transaction, the role each played (buyer, seller, consignee, agent), the relationships between them, and their identifying details as stated on the document.

## Input

The **Document Evidence Object**, and the **Transaction Understanding Result**.

## Output

**Party Understanding Result** — identified entities · relationships · supporting evidence · confidence · unknown parties.

## Boundary

**Can:** identify every party and role · record identifying details as stated · record relationships between entities · report that two parties resemble one another.

**Cannot:** classify accounting ledgers, or select, create or match a ledger account for any party · decide a party's accounting group · merge two parties it believes to be the same entity.

## Decision Authority

**Owns.** Entity identification.

**Determines.** Who was involved, what role each played, and the relationships between them.

**Cannot.** Classify accounting ledgers.

No other component may override this Result.

## Failure Behaviour

An unidentifiable party is recorded in unknown parties — not omitted, not guessed. Where the document does not make clear which party is the business itself, that is an unknown, never assumed from position on the page.

## Future Notes

- Party identity matching against existing masters is an Accounting Engine concern (`ledger_intelligence`). Here, similarity is evidence, not a conclusion.
- "Which party is us" is itself a fact to establish, and it is not always the one printed first.
