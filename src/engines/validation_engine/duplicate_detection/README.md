# duplicate_detection

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#104-duplicate_detection).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The same invoice posted twice is a real and common loss.

## Responsibility

Owns **economic duplicate detection** — whether this is the same business event by accounting effect, even if entered differently.

### Screening is not deciding

The Input Engine already **screened** for artifact identity — same file, same hash, same document number — and recorded a **fact**. This sub-engine makes the **judgement**. See [`docs/SYSTEM_INVARIANTS.md` INV-7](../../../../docs/SYSTEM_INVARIANTS.md#inv-7--screening-is-not-deciding).

## Input

The Accounting Decision · transaction identifiers · history references — previously posted transactions and audit records.

## Output

The **Duplicate Detection Result** — duplicate probability · duplicate evidence · duplicate confidence, with the strength of each match found.

## Boundary

**Can:** compare · search · detect.

**Cannot:** delete, merge, reverse or amend any existing record · **ignore duplicates** · decide what to do about one — it reports the match; [`validation_decision`](../validation_decision/) decides.

## Failure Behaviour

**If uncertain, flag possible duplicate. Never silently allow duplication.**

## Future Notes

- Distinct from [`posting_manager`](../../tally_engine/posting_manager/)'s single-post guarantee: that prevents the *same decision* being posted twice; this detects a *different decision* recording the same event.
- Legitimate near-duplicates exist — a monthly retainer from the same vendor at the same amount. **Match strength matters more than a boolean**, and a near-duplicate is reported with its strength, never suppressed.
