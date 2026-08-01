# Understanding Engine

> Engine 2 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What happened in the business?*

Reading is not understanding. Extracting `19,800.00` is a perception problem; knowing it is a credit purchase from a recurring supplier is a comprehension problem. This engine exists so that the facts of the transaction are established — and can be checked — before any judgement is made about them.

## Responsibility

Turn structured data into a factual business story — who, what, when, how much, how paid.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`transaction_understanding`](transaction_understanding/) | What kind of event occurred |
| [`party_understanding`](party_understanding/) | Who was involved, and as what |
| [`item_understanding`](item_understanding/) | What goods or services moved |
| [`payment_understanding`](payment_understanding/) | How money moved, or did not |
| [`timeline_understanding`](timeline_understanding/) | When each thing happened |
| [`business_context`](business_context/) | How this fits the business's reality |
| [`story_builder`](story_builder/) | Assembly into one coherent story |

## Input

Structured Document and Confidence Report, from the Input Engine.

## Output

**Transaction Story** — a complete, accounting-free description of what happened, with every fact traceable to the document or explicitly marked absent.

## Boundary

**Cannot choose ledgers or tax treatment.** Cannot produce a journal entry or any debit/credit. Cannot invent facts to fill a gap — an absent fact is recorded as absent. Cannot re-read the artifact. Cannot use accounting vocabulary to describe business events.

## Future Notes

- The no-accounting-vocabulary rule is the cheapest available test of whether this boundary is holding. If the story mentions a ledger, something has leaked.
- Facts and their traces should be one structure, not two. A fact whose source cannot be shown is not usable downstream.
