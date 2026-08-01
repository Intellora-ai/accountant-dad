# Communication Rules — Validation Engine

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> How the Validation Engine communicates with the Execution Engine.
>
> Companion to [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md). **Specification only — no implementation.**
>
> **The sending engine owns the contract of what leaves it.** This document is owned by the **Validation Engine**. The Execution Engine references it; it does not restate it.

---

# 1. The Path

```text
Validation Engine
        ↓
Validation Decision   (Approved)
   + Accounting Decision
        ↓
Execution Engine
```

Communication *inside* Engine 5 is governed by [`COMMUNICATION_RULES_VALIDATION_INTERNAL.md`](COMMUNICATION_RULES_VALIDATION_INTERNAL.md); inside Engine 6 by [`COMMUNICATION_RULES_EXECUTION_INTERNAL.md`](COMMUNICATION_RULES_EXECUTION_INTERNAL.md).

> **This is the last boundary in the system. Nothing reaches the books that has not crossed it.**

---

# 2. Boundary Contract

All nine items, per [`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement):

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Accounting Decision (primary) · Clarification Request · reference-only Business Understanding Object, Document Evidence Object, Company Context. |
| 2 | **Output artifact** | The **Validation Decision** — with Validation Status, findings, failed rules, Validation Confidence and reasoning — accompanied by the **Accounting Decision** it approves. |
| 3 | **Artifact creator** | `validation_decision`. |
| 4 | **Artifact owner** | The **Validation Engine**, permanently. |
| 5 | **Allowed transformation** | The Execution Engine may **read**, **analyze** and **reference** both artifacts, translate the Accounting Decision into a destination voucher, and produce its own artifact — the **Execution Result**. |
| 6 | **Forbidden transformation** | It may **not** modify either artifact, re-validate, reverse a status, execute anything not `Approved`, change the accounting meaning of what it translates, or supply a value the decision left undecided. Artifacts are immutable after creation. |
| 7 | **Decision authority** | Validation decides **whether** execution may happen. Execution decides **how, where and when** it happens. **Execution authority never becomes accounting authority.** |
| 8 | **Uncertainty movement** | Findings, warnings, risks, failed rules and Validation Confidence cross intact and are referenced by the Execution Result. **Execution Confidence is a separate layer and never alters Validation Confidence.** A warning travels with the work; it is never consumed by posting. |
| 9 | **Failure movement** | Anything other than a released `Approved` decision means Engine 6 receives nothing. An execution failure is **not** a validation failure: it is recorded in the Execution Result with its responsible stage, and the **Application Layer** routes it. **Execution never returns work to Validation.** |

## Sender ownership · receiver responsibility

**Sender ownership.** The Validation Engine defines what the Validation Decision asserts — the status, the findings, who is responsible for each. Only it may create a new version.

**Receiver responsibility.** Execution must preserve evidence references, traceability, confidence, assumptions, version history and artifact identity; it must never modify any upstream artifact.

---

# 3. What Crosses, By Status

**Execution depends entirely on Validation.**

| Validation Status | What Engine 6 receives | Execution |
|---|---|---|
| **Approved** | The Validation Decision and the Accounting Decision | May begin |
| **Approved With Warning** | **Nothing — until the Application Layer releases it after human attention.** The warning then travels with the work and is referenced by the Execution Result. | Begins only after release |
| **Clarification Required** | Nothing. The clarification pipeline completes, a **new Accounting Decision** is generated, and **Validation runs again**. | Stops |
| **Rejected** | Nothing. The Validation Decision becomes the final output. | **Prohibited** |

> **Engine 6 may never bypass Engine 5.**

## Who holds the `Approved With Warning` gate

**The Application Layer.** Engine 6 cannot hold a workflow gate — workflow is not an engine responsibility ([`SYSTEM_INVARIANTS.md` INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)), and an engine that waited for a human would be reasoning about whether to proceed.

Validation says *"correct, but a human should look."* The Application Layer holds the work until a human has. Engine 6 then executes an already-released decision and never learns that a gate existed — which is exactly why it cannot accidentally skip one.

---

# 4. Execution Never Re-Validates

Engine 6 does not check whether the approval was right. It has no validators, no rules and no authority to form an opinion about the decision it is executing.

If a destination system rejects the voucher, that is an **execution failure**, recorded with its responsible stage. It is never evidence that Validation was wrong, and Engine 6 never treats it as grounds to alter, retry differently, or adjust the accounting.

> **A posting failure must never cause the system to silently change the accounting decision.**

---

# 5. Nothing Returns Along This Arrow

Work moves forward only. **Execution never returns work to Validation, and never to any engine.**

`error_handler` names the **responsible stage** inside the Classified Error; the **Application Layer** reads it and routes. The arrow in this document is one-directional and stays that way — [`DATA_FLOW.md` §5](DATA_FLOW.md#5-flow-rules) rule 1.

```text
✗  Engine 6 → Engine 3   "the ledger was wrong, fix it"
✓  Engine 6 → Execution Result (Classified Error names Accounting)
       → Application Layer routes → Engine 3 issues a NEW decision version
```

A correction is a **new Accounting Decision under the same Transaction ID**, revalidated and re-executed with lineage — never an edit ([INV-5](SYSTEM_INVARIANTS.md#inv-5--history-is-never-modified)).

---

# 6. Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 7. What This Boundary Protects

> **Validation decides whether execution may happen. Execution decides how it happens.**

Three separations hold here:

- **The engine that judges safety does not perform the act.** A validator that could also post would eventually approve in order to finish.
- **The engine that performs the act cannot judge it.** Execution has no validators by construction — so an inconvenient rejection has no mechanism through which it could be argued away.
- **The engine that fails cannot decide where the work goes.** Naming a responsible stage is a finding; moving work is workflow. Keeping them apart is why the last engine in the pipeline has no backward arrow.

---

## Related documents

- [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md) — the sending engine's specification.
- [`ENGINE_6_EXECUTION_ENGINE_RULES.md`](ENGINE_6_EXECUTION_ENGINE_RULES.md) — the receiving engine's specification.
- [`COMMUNICATION_RULES_EXECUTION_INTERNAL.md`](COMMUNICATION_RULES_EXECUTION_INTERNAL.md) — communication inside Engine 6.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, boundary contract requirement.
