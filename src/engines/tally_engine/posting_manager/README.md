# posting_manager

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Posting the same entry twice is worse than not posting it at all.

## Responsibility

Owns the act of posting — ordering, the single-post guarantee, idempotency, and retry policy.

## Input

Tally voucher payloads and the connection state.

## Output

Post attempts and their outcomes, with the guarantee that each approved decision is posted at most once.

## Boundary

Cannot change payload content. Cannot decide *whether* posting should happen — the Validation Engine decided that. Cannot retry a failure it has not been told is retryable by [`error_handler`](../error_handler/).

## Future Notes

- The dangerous case is a request that succeeds in Tally but whose response is lost. Idempotency has to survive that, not merely avoid double submission.
- Distinct from [`duplicate_detection`](../../validation_engine/duplicate_detection/): that catches a different decision recording the same event; this catches the same decision posted twice.
