# audit_logger

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#96-audit_logger).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The books must be defensible, which means the trail must be complete.

## Responsibility

Owns **audit linkage** — the append-only record of every execution event: execution history, retry history, queue history, notification history and external response history. What was sent, when, on which decision's authority, and what came back.

## Input

**All execution events.** It observes throughout the chain; it is last only in *assembly* order.

## Output

The **Audit Record** — permanent and **append-only history, not a versioned artifact**. One per Execution ID.

It is reached through the Execution Result's `Audit Reference` and **never crosses an arrow itself** — which is why it does not break the one-artifact-per-arrow rule.

## Boundary

**Can:** record events · retries · failures · notifications · timestamps · destination systems · operator actions.

**Cannot:** delete or **rewrite history** · alter a record once written · omit failures, retries or partial outcomes · modify previous audit records · summarise away detail needed to reconstruct what happened.

## Failure Behaviour

If logging cannot complete: **execution status remains visible · failure is reported immediately · no audit record may be silently lost.**

## Future Notes

- Append-only is a property of the design, not a convention to be observed. **If a record can be updated, it is not an audit record.**
- The link back to the authorising decision is what makes the whole pipeline reconstructible from an entry in the books — the single most valuable property this component provides.
