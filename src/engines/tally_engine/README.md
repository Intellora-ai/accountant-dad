# Execution Engine

> Engine 6 of 6. **Specification locked** — deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_EXECUTION_INTERNAL.md`](../../../docs/COMMUNICATION_RULES_EXECUTION_INTERNAL.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Name and folder.** The architectural name is **Execution Engine**; this folder keeps its locked name. **Identities are part of the system contract and are never renamed once other engines reference them.**
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*How do we safely execute an already validated accounting decision in the outside world?*

**It never decides whether execution should happen.** That belongs exclusively to Validation.

Execution against an external system fails in its own ways — the connection drops, a voucher is rejected, a post half-succeeds. Those failures must never be confused with accounting errors, so this engine owns no reasoning at all.

> **The Execution Engine transports approved decisions. It cannot create, modify or interpret business meaning.**

**Execution is irreversible.** The engine is built around determinism, duplicate prevention, retry safety and complete auditability.

## Responsibility

Safely execute validated accounting decisions, and record the truth of what happened.

Sub-engines and their output contracts:

| Sub-engine | Owns | Produces |
|---|---|---|
| [`voucher_translator`](voucher_translator/) | Translation only | **Translated Voucher** |
| [`tally_connector`](tally_connector/) | Connection · transmission · acknowledgement | **Connection Result** |
| [`posting_manager`](posting_manager/) | Idempotency · execution lifecycle · retry of transport failures | **Posting Result** *(internal)* |
| [`response_processor`](response_processor/) | Success/failure interpretation | **Processed Execution Result** |
| [`error_handler`](error_handler/) | Error category · severity · responsible stage | **Error Resolution Result** |
| [`audit_logger`](audit_logger/) | Audit linkage | **Audit Record** *(append-only)* |

### Flow

Strictly one-way. No stage reaches back.

```text
Approved Validation Decision + Accounting Decision
        ↓ voucher_translator → tally_connector → posting_manager
        ↓ response_processor → error_handler → audit_logger
        ↓
   Execution Result   ← assembled by the parent Execution Engine
```

`audit_logger` **receives all execution events** and observes throughout; it is last only in *assembly* order.

### The only engine that touches the outside world

Tally · Zoho Books · Busy · SAP · QuickBooks · government portals · APIs · webhooks · email · WhatsApp · notifications · file exports. **No earlier engine may communicate with an external system.**

The destination boundary is defined; **no generic adapter is built now**. Tally is the implementation path; further destinations are implemented only when required.

## Input

**Validation Decision** — `Approved` only, and released — plus the **Accounting Decision**. **Reference only:** Document Evidence Object · Business Understanding Object · Clarification Request · Validation artifacts.

Boundary contract: [`docs/COMMUNICATION_RULES_VALIDATION_ENGINE.md`](../../../docs/COMMUNICATION_RULES_VALIDATION_ENGINE.md).

An `Approved With Warning` decision arrives **only after the Application Layer releases it** — Engine 6 cannot hold a workflow gate.

Must preserve **evidence references · traceability · confidence · assumptions · version history · artifact identity**. **Engine 6 never modifies an upstream artifact.**

## Output

One artifact: the **Execution Result**.

```text
Execution Result
├── Execution ID · Execution Attempt ID     identity only
├── Transaction ID                          lifecycle grouping only
├── Accounting Decision ID · Decision Version · Validation Decision ID
├── Destination System
├── Corrects Execution Result               lineage; empty unless a correction
├── Posting Status · External Transaction ID(s)
├── Retry Count · Queue Status · Notification Status
├── Classified Error                        names the responsible stage
├── Audit Reference                         points at the append-only Audit Record
├── Execution Outcome
├── Execution Confidence                    transport success only
└── Execution Timestamp
```

Assembled by the **parent Execution Engine** — the only engine where the parent creates the outbound artifact, because assembly draws on every stage and no sub-engine sees the whole chain.

**Idempotency Key = Accounting Decision ID + Decision Version + Destination System.** Never Transaction ID, which must never block a legitimate execution.

## Boundary

**MUST NEVER:** perform accounting reasoning · validate accounting · generate clarification · rewrite journal entries · modify ledgers · modify tax treatment · modify any upstream artifact · invent external responses · **suppress execution failures** · silently ignore retries · **delete execution history** · bypass Validation · communicate outside defined execution channels · execute unapproved decisions · **create duplicate postings** · route work backwards.

> **Thinking stops. Execution begins.**
>
> **A posting failure must never cause the system to silently change the accounting decision.**

**Failure behaviour:** report exactly what failed, why, where, the current execution status and the recommended next action. **Never guess. Never hide failure. Never change the accounting decision.**

## Future Notes

- This is the only engine that touches anything outside the system, and the only one whose failures are not accounting failures. Keeping those two facts aligned is the reason it holds no reasoning.
- A destination's XML/HTTP interface and its version differences are entirely [`tally_connector`](tally_connector/) and [`voucher_translator`](voucher_translator/)'s concern; no other engine should ever learn about them.
- **There is no engine after this one to catch a mistake.** Every prohibition here exists because the alternative produces a cleaner-looking record than the honest one.
