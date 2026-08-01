# party_understanding

> Sub-engine of the **Understanding Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A transaction is between people; who they are and what role they played is a fact about the event.

## Responsibility

Owns identification of every party to the transaction, the role each played (buyer, seller, consignee, agent), and their identifying details as stated on the document.

## Input

Structured Document, Confidence Report, and the transaction nature from [`transaction_understanding`](../transaction_understanding/).

## Output

Party facts: identities, roles, and stated registration or contact details.

## Boundary

Cannot select, create or match a ledger account for any party. Cannot decide a party's accounting group. Cannot merge two parties it believes to be the same entity — it reports the similarity as a fact.

## Future Notes

- Party identity matching against existing masters is an Accounting Engine concern (`ledger_intelligence`). Here, similarity is evidence, not a conclusion.
- "Which party is us" is itself a fact to establish, and it is not always the one printed first.
