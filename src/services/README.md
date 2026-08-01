# services — the Application Layer

> **Defined as of Phase 0.** Governed by [`docs/SYSTEM_INVARIANTS.md` INV-4](../../docs/SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

**Workflow orchestration belongs to the Application Layer, not the Cognitive Architecture.**

Engines are reasoning stages. They never own workflow. **Workflow never becomes another engine.**

Every engine explicitly disowns orchestration — *"does not own system-wide orchestration, engine routing, workflow control."* This directory is what owns it instead.

## What it owns

- **Creating the Transaction ID** — one per business event, generated once, never changed.
- Starting engines and routing artifacts between them.
- The **transaction state machine** and its transitions.
- **Retrying engine execution** after runtime failure.
- Recording runtime failures.
- Deciding a transaction is **complete**.

## What it never owns

- **Any decision.** It sequences reasoning; it performs none.
- **Any artifact.** Every artifact is owned by the engine that creates it.
- **Any confidence.** The six confidence types belong to Engines 1–6.
- **Any reasoning.** It never interprets, decides, validates or posts.
- **Any row in an authority table.**

## Transaction state machine

```text
Input → Understanding → Accounting → Clarification → Validation → Execution → Completed
                                                                            ↘ Failed
```

- Each Transaction ID is in **exactly one state** at any moment.
- **Transitions are atomic.**
- **Parallel transactions are allowed. Parallel states for one transaction are prohibited.**
- `Completed` is not permanently terminal — a correction returns the transaction to an active state under the same Transaction ID.

Distinct from Clarification Status, which the Clarification Engine owns. Transaction state is **workflow**; clarification status is **an artifact's lifecycle**.

## Runtime failure

**Business failures belong to sub-engines. Runtime failures belong here.**

When an engine cannot complete:

- **Never fabricate outputs.**
- **Never continue with partial reasoning.**
- Preserve completed artifacts.
- Record the runtime failure.
- Allow safe restart **from the last completed artifact**.

> **Engine failure is not an artifact.** A half-built Business Understanding Object is more dangerous than none.

## The risk this directory carries

A `services/` folder is where architectures usually erode. Logic that "does not fit anywhere" gets placed here, and the ownership stated in [`docs/ENGINE_RESPONSIBILITIES.md`](../../docs/ENGINE_RESPONSIBILITIES.md) quietly stops being true.

The boundary above is what prevents that. **If something does not fit in an engine, that is a signal the architecture needs a decision — not a signal to put it here.** Stop and ask.

## Status

Empty by design.
