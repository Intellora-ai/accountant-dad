# Communication Rules — Clarification Engine

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> How the Clarification Engine communicates with the Validation Engine.
>
> Companion to [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md). **Specification only — no implementation.**
>
> **The sending engine owns the contract of what leaves it.** This document is owned by the **Clarification Engine**. The Validation Engine references it; it does not restate it.

---

# 1. The Path

```text
Clarification Engine
        ↓
Clarification Request
        ↓
Validation Engine
```

The Clarification Engine's only outbound artifact is the Clarification Request. It also reaches an **external actor** — a UI, an API, a human — but that is delivery of the same artifact by a later system layer, not a second engine boundary. **Engine 4 never asks anyone directly.**

Communication *inside* Engine 4 is governed by [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).

---

# 2. Boundary Contract

All nine items, per [`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement):

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Accounting Decision (primary) · Business Understanding Object (reference only). |
| 2 | **Output artifact** | **Clarification Request** — with Transaction ID, Related Decision ID, Related Artifact Version, missing information, detected conflicts, required clarification, reason, affected decision, priority, supporting evidence references, Clarification Confidence and status. |
| 3 | **Artifact creator** | `question_generator`. |
| 4 | **Artifact owner** | The **Clarification Engine**, permanently — along with Clarification Status and Clarification History. |
| 5 | **Allowed transformation** | The Validation Engine may **read**, **analyze** and **reference** it — to check whether required clarification exists, whether it blocks execution, whether unresolved issues remain, and whether clarification priority matches severity — and produce its own artifact. |
| 6 | **Forbidden transformation** | It may **not** generate clarification, resolve it, change its priority, alter its status, or modify the Clarification Request in any way. Artifacts are immutable after creation. |
| 7 | **Decision authority** | Clarification decides whether clarification is needed, what is missing, what should be asked, and clarification status. Validation decides whether execution is safe and permitted. **A question is not a decision; a verdict is not a question.** |
| 8 | **Uncertainty movement** | Missing information, detected conflicts and Clarification Confidence cross intact. **Validation Confidence may never exceed Clarification Confidence** where clarification is the weakest critical input. Unresolved clarification is never ignored. |
| 9 | **Failure movement** | A Clarification Request that is `Open` or `Answered` but not `Resolved` means uncertainty is still outstanding. Validation treats this as a **blocking condition**, returning `Clarification Required` — it never resolves the request itself, and never approves around it. |

## Sender ownership · receiver responsibility

**Sender ownership.** The Clarification Engine defines what the Clarification Request asserts — what is missing, why it matters, which decision depends on it, how important it is. Only it may create a new version or change the status.

**Receiver responsibility.** Validation must preserve evidence references, reasoning, assumptions, confidence, uncertainty and traceability; must never modify the request, resolve it, hide it, or approve while it blocks.

---

# 3. What Is Sent

```text
Clarification Request
├── Clarification ID · Transaction ID
├── Related Decision ID · Related Artifact Version
├── Missing Information · Detected Conflicts
├── Required Clarification · Reason Clarification Is Required
├── Affected Decision · Priority
├── Supporting Evidence References
├── Clarification Confidence
└── Status    Open | Answered | Superseded | Cancelled | Resolved
```

Full structure: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md` §5](ENGINE_4_CLARIFICATION_ENGINE_RULES.md#5-output-contract).

## Status is what Validation reads first

| Status | What it tells Validation |
|---|---|
| **Open** · **Answered** | Uncertainty is outstanding — a **blocking** condition |
| **Superseded** | Raised against an older decision version; **does not block** the current one |
| **Cancelled** | Withdrawn; does not block |
| **Resolved** | The uncertainty is gone; does not block |

**Only one active Clarification Request may exist per Transaction ID.** A newer Accounting Decision supersedes older requests automatically — so Validation never has to reconcile several competing open requests for one business event.

---

# 4. Validation May Judge the Request, Never Change It

Validation checks four things about the request and records its findings in **its own** artifact:

1. **Does required clarification exist** where the decision carried unresolved doubts?
2. **Does it block execution?**
3. **Do unresolved issues remain?**
4. **Does clarification priority match severity?** — a Critical validation finding paired with a Low-priority clarification is itself a finding.

If Validation believes the request is wrong — mis-prioritised, incomplete, or raised against the wrong decision — it records that as a **finding naming the Clarification Engine as the responsible engine**. It never edits the request to match.

---

# 5. Validation Never Generates Clarification

A case that needs a question returns to the Clarification Engine as `Clarification Required`. Validation does not write the question, does not decide what is missing, and does not ask anyone.

The loop is:

```text
Validation → Clarification Required
    → Clarification Engine emits a new Clarification Request
    → external actor answers
    → Engine 1/2/3 rebuild → new Accounting Decision
    → Validation runs again
```

**Validation never receives answers.** New information re-enters through the normal pipeline as a new artifact version — [`SYSTEM_INVARIANTS.md` INV-5](SYSTEM_INVARIANTS.md#inv-5--history-is-never-modified).

---

# 6. Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 7. What This Boundary Protects

> **Clarification detects what blocks a decision. Validation decides whether it is safe to execute.**

Two separations hold here:

- **The engine that finds uncertainty does not judge whether it matters enough to stop.** Clarification says what is missing and how important it is; Validation decides whether execution proceeds. An engine doing both would eventually rate its own findings as non-blocking.
- **The engine that judges safety cannot manufacture the question.** If Validation could write its own clarification, it could shape a question whose answer it had already assumed.

---

## Related documents

- [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) — the sending engine's specification.
- [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md) — the receiving engine's specification.
- [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md) — communication inside Engine 4.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, boundary contract requirement.
