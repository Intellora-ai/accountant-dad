# Communication Rules — Execution Engine, Internal

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> How the six Execution sub-engines communicate with one another.
>
> Companion to [`ENGINE_6_EXECUTION_ENGINE_RULES.md`](ENGINE_6_EXECUTION_ENGINE_RULES.md). **Specification only — no implementation.**
>
> This document governs communication *inside* Engine 6. The boundary into it is governed by [`COMMUNICATION_RULES_VALIDATION_ENGINE.md`](COMMUNICATION_RULES_VALIDATION_ENGINE.md).

---

# 1. Flow

Strictly one-way. No stage reaches back.

```text
Approved Validation Decision + Accounting Decision
                    ↓
            voucher_translator
                    ↓  Translated Voucher
            tally_connector
                    ↓  Connection Result
            posting_manager
                    ↓  Posting Result            ← internal name; never crosses a boundary
            response_processor
                    ↓  Processed Execution Result
            error_handler
                    ↓  Error Resolution Result
            audit_logger
                    ↓  Audit Record              ← append-only
            Execution Result   ← assembled by the parent Execution Engine
```

`audit_logger` **receives all execution events** and observes throughout the chain. It appears last only in **assembly order**.

---

# 2. Communication Rules

---

## Rule 1 — Sub-engines communicate only through defined outputs

Each sub-engine publishes exactly one named output, and that output is the entirety of what the next stage may see.

| Sub-engine | Publishes |
|---|---|
| `voucher_translator` | Translated Voucher |
| `tally_connector` | Connection Result |
| `posting_manager` | **Posting Result** — *internal only* |
| `response_processor` | Processed Execution Result |
| `error_handler` | Error Resolution Result |
| `audit_logger` | Audit Record |
| **Execution Engine parent** | **Execution Result** |

---

## Rule 2 — No hidden communication

No shared mutable state. No side channels. No implicit coupling through anything other than a published output.

External calls — to Tally, Zoho, an API, a notification service — are **performed by a named sub-engine and recorded in the audit trail**. They are never a path by which one sub-engine learns something another did not publish.

---

## Rule 3 — No sub-engine modifies another sub-engine's output

An output is **read-only** to every sibling, permanently — and so is every upstream artifact.

`voucher_translator` may not adjust the Accounting Decision to make it translatable. `response_processor` may not rewrite what an external system actually said. `error_handler` may not amend a Posting Result that recorded a failure.

---

## Rule 4 — No circular reasoning, and no reasoning at all

There is no loop in this diagram, and there is nothing in it that reasons.

> **The Execution Engine transports approved decisions. It cannot create, modify or interpret business meaning.**

A sub-engine that finds the decision inconvenient records the problem. It never fixes it.

---

## Rule 5 — `Posting Result` is internal

`posting_manager` produces a **Posting Result**. It becomes the **Posting Status** component of the Execution Result and **never crosses an engine boundary**.

Same pattern as Engine 3's Ledger Recommendation and Engine 5's five validation Results: **one name for what crosses each arrow**, internal names below it.

---

## Rule 6 — `error_handler` names; it never routes

> **`error_handler` classifies the failure and names the responsible stage. It never moves work.**

The **Classified Error** is a component of the Execution Result and carries the responsible stage as a *field*. The **Application Layer** reads it and routes, because workflow is its property ([`SYSTEM_INVARIANTS.md` INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)).

**Engine 6 therefore has no backward arrow** — [`DATA_FLOW.md` §5](DATA_FLOW.md#5-flow-rules) rule 1 holds unbroken through the last engine in the pipeline.

An error that cannot be classified is recorded **as unclassifiable**, with a notification trigger. It is never suppressed for lacking a category.

---

## Rule 7 — Idempotency is keyed, and the key is stated

```text
Idempotency Key = Accounting Decision ID + Decision Version + Destination System
```

`posting_manager` enforces it. **Transaction ID is never part of the key.**

| Case | Outcome |
|---|---|
| Same decision version, same destination, retried | **Blocked.** One successful post. |
| **Correction** — new decision version, same destination | **Posts.** A correction must be able to execute. |
| Same decision version, **different destination** | **Posts.** Independent targets, independent protection. |
| Repeated button press · browser refresh · duplicated API request | **Blocked.** |

Keying on Transaction ID would have blocked every correction; keying without Destination would have blocked the second destination the moment one existed.

---

## Rule 8 — Retry belongs to two owners, and the line is drawn

| Failure | Owner |
|---|---|
| A **transport failure** — the voucher did not reach the destination | `posting_manager` reposts |
| A **crashed engine** — Engine 6 itself did not complete | The **Application Layer** restarts |

**No responsibility exists in two places** ([INV-10](SYSTEM_INVARIANTS.md#inv-10--one-concept-one-owner)). `posting_manager` never restarts a workflow; the Application Layer never decides that a voucher should be sent again.

---

## Rule 9 — The Audit Record is append-only, not versioned

It is **history**, not a versioned artifact. One per Execution ID. It is reached through the Execution Result's `Audit Reference` and **never crosses an arrow itself** — which is why it does not break the one-artifact-per-arrow rule.

**Nothing is ever deleted. Nothing is ever rewritten.** Every attempt, retry, queue event, external response and notification is appended, including the failures.

---

## Rule 10 — A partial post is not a partial artifact

| | Belongs to |
|---|---|
| A **partial post** — the destination accepted part of the voucher | **Engine 6.** A business outcome, fully described in a complete Execution Result. |
| A **partial artifact** — Engine 6 crashed mid-assembly | **The Application Layer.** Nothing is produced. |

*"Engine failure is not an artifact"* and *"partial is a first-class outcome"* are both true, and only because these are different things. A half-built artifact is more dangerous than none; a fully-described partial post is information the business needs.

---

## Rule 11 — The parent assembles; it does not rewrite

| The parent **CAN** | The parent **CANNOT** |
|---|---|
| Combine sub-engine outputs | Invent an outcome |
| Organize them | **Suppress a failure** |
| Assemble Execution Confidence from named factors | Override a sub-engine |
| Create the final Execution Result | Delete or edit history |
| | Alter what was actually sent or received |

Engine 6 is the **only** engine whose parent creates the outbound artifact — its assembly draws on every stage, and no single sub-engine sees the whole chain. **Assembly is mechanical. It is not permission to edit.**

---

# 3. Execution Confidence Assembly

The parent assembles it from six factors, each published by a named sub-engine:

| Factor | Published by |
|---|---|
| Successful external connection | `tally_connector` |
| Successful posting | `posting_manager` |
| Verified external acknowledgement | `response_processor` |
| Complete response processing | `response_processor` |
| Successful audit logging | `audit_logger` |
| Notification status | `error_handler` |

**Execution Confidence measures transport only.** It never changes accounting confidence or Validation confidence, and **a failed execution can never be high**.

---

# 4. What These Rules Protect

Every rule above defends one property: **what the books say happened is exactly what happened, once, and the record of it cannot be edited afterwards.**

Break any one and that property goes:

- Allow a side channel, and a voucher is sent that no output records.
- Allow `voucher_translator` to adjust the decision, and a transport problem quietly became an accounting change.
- Allow idempotency to key on Transaction ID, and no correction can ever be posted.
- Allow idempotency to ignore Destination, and the second destination silently never receives anything.
- Allow `error_handler` to route, and the last engine acquires a backward arrow that no diagram shows.
- Allow the Audit Record to be rewritten, and the audit trail becomes an assertion rather than a record.
- Allow an ambiguous response to count as success, and a failed post is recorded as a posted one.
- Allow the parent to soften a failure during assembly, and the Execution Result stops being evidence.

None of these fail loudly. Most of them produce a *cleaner* record than the honest version — which is exactly why they are prohibitions rather than guidance.

**Execution is irreversible. There is no engine after this one to catch it.**

---

## Related documents

- [`ENGINE_6_EXECUTION_ENGINE_RULES.md`](ENGINE_6_EXECUTION_ENGINE_RULES.md) — the Execution Engine specification.
- [`COMMUNICATION_RULES_VALIDATION_ENGINE.md`](COMMUNICATION_RULES_VALIDATION_ENGINE.md) — the inbound boundary contract.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, IDENTITY ≠ INTELLIGENCE.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
