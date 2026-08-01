# posting_manager

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#93-posting_manager).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Posting the same entry twice is worse than not posting it at all.

## Responsibility

Owns **idempotency, execution lifecycle, and retry of transport failures** — plus posting control, ordering and queue coordination.

### The idempotency key

```text
Idempotency Key = Accounting Decision ID + Decision Version + Destination System
```

| Case | Outcome |
|---|---|
| Same version, same destination, retried | **Blocked** — one successful post |
| **Correction** — new decision version | **Posts** |
| Same version, **different destination** | **Posts** — independent targets |
| Repeated button press · refresh · duplicated request | **Blocked** |

**Transaction ID is never part of the key.** It represents the complete business event and must never block a legitimate execution — keying on it would block every correction.

### Retry ownership

| | Owner |
|---|---|
| Reposting a **transport-failed voucher** | This sub-engine |
| Restarting a **crashed engine** | The **Application Layer** |

Two different failures, two different owners.

## Input

Connection Result · Translated Voucher.

## Output

The **Posting Result** — post attempts and their outcomes, with the guarantee that each approved decision version reaches each destination at most once.

**Internal to Engine 6.** It becomes the `Posting Status` component of the Execution Result and never crosses an engine boundary.

## Boundary

**Can:** execute posting · retry per policy · queue · resume queued execution · **prevent duplicate execution**.

**Cannot:** post duplicates · change payload content · change accounting decisions · ignore retry policy · bypass Validation · decide *whether* posting should happen — Validation decided that · **restart crashed workflows**.

## Failure Behaviour

**Retry automatically**; if retries fail, **queue safely and notify the user**. **Never lose the validated transaction. Never execute twice accidentally.** Never retry forever.

## Future Notes

- The dangerous case is a request that succeeds at the destination but whose response is lost. Idempotency has to survive that, not merely avoid double submission.
- Distinct from [`duplicate_detection`](../../validation_engine/duplicate_detection/): that catches a *different decision* recording the same event; this catches the *same decision version* posted twice.
