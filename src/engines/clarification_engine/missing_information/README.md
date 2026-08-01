# missing_information

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A question is only answerable if the missing fact and its holder are known.

## Responsibility

Owns determination of exactly which facts are absent, and who or what could supply each — the user, the source document, a party, or company master data.

## Input

Ranked material uncertainties, the Transaction Story's marked gaps, and the company accounting profile.

## Output

A missing-fact list: each absent fact, why it is needed, and its likely source.

## Boundary

Cannot fabricate, default or estimate a missing value. Cannot fetch the fact itself. Cannot declare a fact missing that is present but merely low-confidence — that is an uncertainty, not an absence.

## Future Notes

- Absence and low confidence are different problems with different questions: "what was it?" versus "is this right?".
- Naming the likely source is what lets a question be aimed at someone who can actually answer it.
