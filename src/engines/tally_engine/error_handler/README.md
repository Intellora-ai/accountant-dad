# error_handler

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#95-error_handler).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A failed post has a cause, and the cause determines who must fix it.

## Responsibility

Owns **error category, severity, and responsible stage identification** — transport, destination rejection, data defect or translation defect — plus retry decisions, queue decisions and user notification triggers.

## It names; it never routes

> **`error_handler` classifies the failure and names the responsible stage. It never moves work.**

The **Classified Error** is a component of the Execution Result and carries the responsible stage as a *field*. The **Application Layer** reads it and routes, because workflow is its property ([`docs/SYSTEM_INVARIANTS.md` INV-4](../../../../docs/SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)).

**Engine 6 therefore has no backward arrow.** The flow rule holds unbroken through the last engine in the pipeline.

## Input

Failed Execution · Failed Connection · Failed Posting · Failed Response.

## Output

The **Error Resolution Result**, containing the **Classified Error**: category, cause, severity, whether retry is permissible, and the responsible stage.

## Boundary

**Can:** classify failures · retry · queue · notify · stop execution safely.

**Cannot:** ignore or **hide failures** · delete failed executions · correct data · re-decide anything · modify accounting · override Validation · **route work to another engine**. Cannot retry directly — it tells [`posting_manager`](../posting_manager/) whether retry is permissible. Cannot name a stage that could not have caused the failure.

## Failure Behaviour

**Every failure remains permanently visible. Execution never silently disappears. Users always receive execution status.**

An error that cannot be classified is recorded **as unclassifiable**, with a notification trigger. **It is never suppressed for lacking a category**, and never retried on the assumption that it might be transient.

## Future Notes

- The categories differ in one decisive way: a transport failure is retryable, a data or translation defect never is. Confusing them produces either lost work or a retry storm.
- Naming a responsible stage is a *finding*. Moving work is *workflow*. Keeping those apart is why the last engine in the pipeline has no backward arrow.
