# Engine 6 — Execution Engine: Specification Lock

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> **Status: LOCKED.** Forward Dependency Inventory completed before writing — see [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md).
>
> **Specification only — no implementation.** No code, no APIs, no UI, no databases, no integrations, no infrastructure.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map. **This document is the deeper authority for Execution Engine specifics.**

---

# 1. Engine Identity

## Engine Name

**Execution Engine**

> **Name and folder.** The architectural name is **Execution Engine**; the locked implementation folder is [`src/engines/tally_engine/`](../src/engines/tally_engine/). **Identities are part of the system contract and are never renamed once other engines reference them** — the folder stays. The same case as `tally_connector` below, and as Engine 4's three.

## Core Role

Engine 6 is the **final transport layer**. Reasoning ended at Validation.

### The question it answers

> **"How do we safely execute an already validated accounting decision in the outside world?"**

**It never decides whether execution should happen.** That belongs exclusively to Validation.

### The questions it does not answer

| Question | Owner |
|---|---|
| ~~What information exists?~~ | Engine 1 — Input |
| ~~What happened?~~ | Engine 2 — Understanding |
| ~~How should it be accounted?~~ | Engine 3 — Accounting |
| ~~What should be asked?~~ | Engine 4 — Clarification |
| ~~Is it safe to post?~~ | Engine 5 — Validation |

**Execution is irreversible.** The engine is therefore designed around determinism, reliability, traceability, duplicate prevention, retry safety and complete auditability.

---

# 2. Mission

Safely execute validated accounting decisions while guaranteeing **reliability · determinism · duplicate prevention · retry safety · complete traceability · permanent audit history · accurate external communication**.

---

# 3. Responsibility

## The Execution Engine owns

Voucher translation · external system communication · execution orchestration · posting management · retry management · queue management · execution responses · execution notifications · execution failures · execution audit history · execution status · **Execution Result generation**.

## The Execution Engine does NOT own

Evidence · business understanding · accounting · clarification · validation.

## The only engine that touches the outside world

> **Everything external passes through Engine 6. No earlier engine may communicate with an external system.**

Tally · Zoho Books · Busy · SAP · QuickBooks · government portals · APIs · webhooks · email · WhatsApp · internal notifications · file exports (Excel, PDF, CSV, JSON) · future accounting systems.

---

# 3A. The Execution Meaning Boundary

> **The Execution Engine transports approved decisions. It cannot create, modify or interpret business meaning.**

| Engine 6 **may** | Engine 6 **must never** |
|---|---|
| Translate approved accounting decisions | Choose accounts |
| Communicate with external systems | Change accounting treatment |
| Process responses | Modify tax decisions |
| Retry failed transmissions | Resolve missing information |
| Record execution outcomes | Invent corrections |
| | Override Validation decisions |

**A posting failure must never cause the system to silently change the accounting decision.**

> **Thinking stops. Execution begins.**

Execution is the final transport layer, not another reasoning layer.

---

# 3B. Decision Authority

| Engine 6 may decide | Engine 6 may never decide |
|---|---|
| When execution begins | Accounting treatment |
| Where execution is sent | Journal structure |
| Retry timing | Ledger selection |
| Queue timing | Tax treatment |
| Notification timing | Validation approval |
| Execution completion | Clarification requirements |
| Execution failure | Business meaning |
| Execution status | Accounting confidence |

> **Execution authority never becomes accounting authority.**

Per sub-engine:

| Sub-engine | Can decide | Cannot decide |
|---|---|---|
| `voucher_translator` | Field and format mapping to the destination | Anything the mapping represents |
| `tally_connector` | Connection, authentication, transmission, session | What is transmitted |
| `posting_manager` | Whether an attempt is a duplicate · retry timing · queue timing · lifecycle state | Whether execution was permitted |
| `response_processor` | What an external response means | Whether the decision was right |
| `error_handler` | Error category · severity · **responsible stage** | Where the work goes next |
| `audit_logger` | What is recorded and when | Whether anything may be omitted |
| **Execution Engine parent** | **Assembly of the Execution Result** · Execution Confidence | Anything a sub-engine decided |

**The parent assembles. It never overrides, rewrites or suppresses any sub-engine output.**

---

# 4. Input Contract

## Primary inputs

```text
Validation Decision      Approved only — the primary authority
Accounting Decision      what is executed
```

## Reference inputs — read-only

Document Evidence Object · Business Understanding Object · Clarification Request *(if applicable)* · Validation artifacts.

## Preservation rules

Inputs must preserve **evidence references · traceability · confidence · assumptions · version history · artifact identity**.

> **Engine 6 must never modify any upstream artifact.**

Boundary contract: [`COMMUNICATION_RULES_VALIDATION_ENGINE.md`](COMMUNICATION_RULES_VALIDATION_ENGINE.md). **The sending engine owns the contract of what leaves it.**

## What is never received

| Status | What Engine 6 receives |
|---|---|
| **Approved** | The decision, released for execution |
| **Approved With Warning** | Nothing — **until the Application Layer releases it after human attention.** Engine 6 cannot hold a workflow gate ([`SYSTEM_INVARIANTS.md` INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)) |
| **Clarification Required** | Nothing |
| **Rejected** | Nothing |

> **Engine 6 may never bypass Engine 5.**

---

# 5. Output Contract

Exactly one canonical artifact: the **Execution Result**.

```text
Execution Result
├── Execution ID                     identity only — IDENTITY ≠ INTELLIGENCE
├── Execution Attempt ID             one per attempt; identity only
├── Transaction ID                   lifecycle grouping only
├── Accounting Decision ID
├── Decision Version
├── Validation Decision ID
├── Destination System
├── Corrects Execution Result        lineage; empty unless this is a correction
├── Posting Status                   posting_manager's Posting Result
├── External Transaction ID(s)
├── Retry Count
├── Queue Status
├── Notification Status
├── Classified Error                 error_handler's output; names the responsible stage
├── Audit Reference                  points at the append-only Audit Record
├── Execution Outcome
├── Execution Confidence             transport success only
└── Execution Timestamp
```

**The Execution Result becomes the permanent record of execution.**

## 5.1 One artifact, one arrow

> **Every arrow carries exactly one named artifact** — [`DATA_FLOW.md` §2](DATA_FLOW.md#2-artifacts).

`Posting Result`, `Classified Error` and `Audit Reference` are **components** of the Execution Result, never artifacts in their own right and never alternative names for it. **`Posting Result` is internal to Engine 6** — it is `posting_manager`'s output name and never crosses an engine boundary, exactly as Engine 3's Ledger Recommendation never does.

## 5.2 Execution Attempt Identity

One decision version may be attempted many times — *Tally unavailable*, then *posted*. The Execution Result alone cannot express that.

```text
Transaction ID
   └─ Accounting Decision Version
        └─ Execution Attempt ID
             └─ Execution Result
```

**Execution Attempt ID exists only to track execution attempts. It is not a business identity.**

## 5.3 Correction lineage

A correction is a **new Accounting Decision under the same Transaction ID** ([`SYSTEM_INVARIANTS.md` INV-5](SYSTEM_INVARIANTS.md#inv-5--history-is-never-modified)). The execution link is explicit:

```text
Original Execution Result → Correction Accounting Decision → Correction Execution Result
```

The system must always answer: **"Which execution corrected which previous execution?"** The `Corrects Execution Result` field answers it structurally, not by inference.

> **History remains immutable. No existing Execution Result is ever edited.**

## 5.4 Artifact ownership

| Engine 6 owns | Engine 6 never owns |
|---|---|
| Execution Result | Document Evidence Object |
| Execution History | Business Understanding Object |
| Retry History | Accounting Decision |
| Queue History | Clarification Request |
| Notification History | Validation Decision |
| External Response History | |

**Ownership never moves backwards through the pipeline.**

### Creator and owner

Engine 6 is the **only** engine whose parent creates the outbound artifact. Its assembly draws on every sub-engine in the chain, and no single sub-engine sees the whole picture. Creator and owner are therefore the same here — deliberately, and stated rather than left implicit.

## 5.5 Identity

**Execution ID** and **Execution Attempt ID** exist only for identity, traceability, lifecycle tracking and audit history. Neither may influence destination selection, retry behaviour, duplicate judgement, confidence, or any future decision — [`SYSTEM_INVARIANTS.md` INV-9](SYSTEM_INVARIANTS.md#inv-9--identity--intelligence).

---

# 6. Absolute Boundaries

Engine 6 **MUST NEVER**:

perform accounting reasoning · validate accounting · generate clarification · rewrite journal entries · modify ledgers · modify tax treatment · modify Validation Decisions · modify Accounting Decisions · invent external responses · **suppress execution failures** · silently ignore retries · **delete execution history** · bypass Validation · communicate outside defined execution channels · execute unapproved decisions · **create duplicate postings**.

## Failure behaviour

If execution cannot proceed, Engine 6 reports exactly:

- **what** failed
- **why** it failed
- **where** it failed
- current **execution status**
- **recommended next action**

> **It never guesses. It never hides failure. It never changes the accounting decision.**

## Business failure versus runtime failure

| | Belongs to |
|---|---|
| A **partial post** — the external system accepted part of the voucher | **Engine 6.** A business outcome, fully described in a complete Execution Result. |
| A **partial artifact** — Engine 6 itself crashed mid-assembly | **The Application Layer.** Nothing is produced; *engine failure is not an artifact* ([INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)). |

The distinction is the whole reason both rules can hold at once.

---

# 7. Knowledge Brain Boundary

The Knowledge Brain is **not part of Engine 6**. It may provide connector documentation · destination system capabilities · API reference information · export format specifications · regulatory reference material.

It may **never** execute postings · change execution behaviour · override validation · create Execution Results · modify external responses · make execution decisions.

> **Knowledge informs. Execution acts.**

---

# 8. Internal Architecture

Exactly **six** sub-engines. No additions. No removals. No renames.

```text
Approved Validation Decision + Accounting Decision
                    │
                    ▼
            voucher_translator
                    │  Translated Voucher
                    ▼
            tally_connector
                    │  Connection Result
                    ▼
            posting_manager
                    │  Posting Result          ← internal name
                    ▼
            response_processor
                    │  Processed Execution Result
                    ▼
            error_handler
                    │  Error Resolution Result
                    ▼
            audit_logger
                    │  Audit Record             ← append-only
                    ▼
      Execution Result   ← assembled by the parent Execution Engine
```

**Flow is strictly one-way.** No hidden communication · no shared mutable state · no circular reasoning · no sub-engine edits another sub-engine's output · the parent assembles but never overrides history.

## 8.1 Artifact ownership within the engine

| Artifact | Creator | Owner | Consumer |
|---|---|---|---|
| Translated Voucher | `voucher_translator` | Execution Engine | `tally_connector` · `posting_manager` |
| Connection Result | `tally_connector` | Execution Engine | `posting_manager` |
| **Posting Result** | `posting_manager` | Execution Engine | `response_processor` — **internal only** |
| Processed Execution Result | `response_processor` | Execution Engine | `error_handler` · parent |
| Error Resolution Result | `error_handler` | Execution Engine | `audit_logger` · parent |
| Audit Record | `audit_logger` | Execution Engine | referenced, never carried |
| **Execution Result** | **Execution Engine** | **Execution Engine** | Application Layer · external record |

## 8.2 The destination boundary

Engine 6 is where destinations attach. **The boundary is defined now; no generic adapter is built.**

```text
Execution Engine
    ├── Tally Adapter              the implementation path today
    ├── Zoho Adapter               when required
    └── Future Destination Adapter when required
```

`voucher_translator` and `tally_connector` are **destination-parametric by contract**, not Tally-shaped by assumption. **Destinations are implemented only when required** — the boundary costs nothing now and cannot be added cheaply after the freeze.

---

# 9. Sub-Engine Specifications

---

## 9.1 `voucher_translator`

### Purpose
Convert the validated Accounting Decision into the exact format required by the destination accounting system.

### Owns
**Translation only** — Voucher Translation · Format Mapping · Field Mapping · Export Structure.

### Receives
Accounting Decision · Validation Decision · Destination System.

### Produces
**Translated Voucher**.

### Allowed Actions
Map fields · convert formats · generate the destination-specific voucher · verify that required destination fields exist.

### Forbidden Actions
Change accounting treatment · change ledger selection · change journal entries · change tax treatment · **modify accounting meaning**.

### Failure Behaviour
If translation cannot be completed: **stop execution · preserve the Accounting Decision · report translation failure · never invent missing values.** A missing value is a translation error, not a gap to fill.

---

## 9.2 `tally_connector`

> **Locked folder name retained. Architecturally this is the destination connector** — its responsibility covers all external accounting systems, not Tally alone. **Identities are stable; responsibilities are not.**

### Purpose
Communicate with external accounting software.

### Owns
**Connection · transmission · acknowledgement** — External Connections · Authentication · API Communication · Connector Sessions.

### Receives
Translated Voucher.

### Produces
**Connection Result**.

### Allowed Actions
Connect · authenticate · send voucher · receive responses · disconnect safely.

### Forbidden Actions
Modify voucher · change accounting · **retry endlessly** · skip authentication · ignore connection failures · **reason**.

### Failure Behaviour
If connection fails: **report failure · hand control to `error_handler` · preserve execution state.**

---

## 9.3 `posting_manager`

### Purpose
Safely execute the posting operation.

### Owns
**Idempotency · execution lifecycle · retry of transport failures** — plus Posting Control and Queue Coordination.

### The idempotency key

```text
Idempotency Key = Accounting Decision ID + Decision Version + Destination System
```

| Component | Role |
|---|---|
| **Accounting Decision ID** | Which decision |
| **Decision Version** | **What** is executed. A correction is a new version, so it posts; a retry of the same version never does. |
| **Destination System** | **Where** it is executed. One approved decision may legitimately post to two destinations; each needs independent protection. |

**Transaction ID is never part of the key.** It represents the complete business event and must never block a legitimate execution — it is for lifecycle grouping only, per [INV-9](SYSTEM_INVARIANTS.md#inv-9--identity--intelligence).

### Receives
Connection Result · Translated Voucher.

### Produces
**Posting Result** — *internal to Engine 6; it becomes the Posting Status component of the Execution Result and never crosses an engine boundary.*

### Allowed Actions
Execute posting · retry according to policy · queue execution · resume queued execution · **prevent duplicate execution**.

### Forbidden Actions
Post duplicate entries · modify vouchers · change accounting decisions · ignore retry policy · bypass Validation · **restart crashed workflows** — that is the Application Layer.

### Retry ownership, drawn exactly
| | Owner |
|---|---|
| Reposting a **transport-failed voucher** | `posting_manager` |
| Restarting a **crashed engine** | The Application Layer ([INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)) |

Two different failures, two different owners. **No responsibility exists in two places** ([INV-10](SYSTEM_INVARIANTS.md#inv-10--one-concept-one-owner)).

### Failure Behaviour
If posting fails: **retry automatically**; if retries fail, **queue safely and notify the user**. **Never lose the validated transaction. Never execute twice accidentally.**

---

## 9.4 `response_processor`

### Purpose
Interpret responses received from external systems.

### Owns
**Success/failure interpretation** — Response Interpretation · External IDs · Posting Status · Success Detection.

### Receives
External Response.

### Produces
**Processed Execution Result**.

### Allowed Actions
Interpret response codes · extract transaction IDs · record posting status · detect successful execution.

### Forbidden Actions
Rewrite responses · ignore failures · modify accounting decisions · **increase accounting confidence** · change business decisions.

### Failure Behaviour
**Unknown responses remain visible. Never assume success. Never invent external IDs.** An absent or ambiguous response is never read as success.

---

## 9.5 `error_handler`

### Purpose
Manage execution failures safely.

### Owns
**Error category · severity · responsible stage identification** — plus Retry Decisions, Queue Decisions and User Notification Triggers.

### It names; it does not route

> **`error_handler` classifies and names the responsible stage. It never routes work backwards.**

The **Classified Error** is a component of the Execution Result and carries the responsible stage as a *field*. The **Application Layer** reads it and routes, because workflow is its property ([INV-4](SYSTEM_INVARIANTS.md#inv-4--reasoning-is-separate-from-workflow)). Engine 6 therefore has **no backward arrow** — [`DATA_FLOW.md` §5](DATA_FLOW.md#5-flow-rules) rule 1 holds unbroken.

An error that cannot be classified is recorded as unclassifiable, with a notification trigger. **It is never suppressed for lacking a category.**

### Receives
Failed Execution · Failed Connection · Failed Posting · Failed Response.

### Produces
**Error Resolution Result**.

### Allowed Actions
Classify failures · retry · queue · notify · stop execution safely.

### Forbidden Actions
Ignore failures · **hide failures** · delete failed executions · modify accounting · override Validation · **route work to another engine**.

### Failure Behaviour
**Every failure remains permanently visible. Execution never silently disappears. Users always receive execution status.**

---

## 9.6 `audit_logger`

### Purpose
Create a permanent, immutable execution history.

### Owns
**Audit linkage** — Execution History · Retry History · Queue History · Notification History · External Response History · Audit Trail.

### Receives
**All execution events** — it observes throughout the chain. It is last only in *assembly* order.

### Produces
**Audit Record** — **append-only history, not a versioned artifact.** One per Execution ID. It is reached through the Execution Result's `Audit Reference` and **never crosses an arrow itself**.

### Allowed Actions
Record events · retries · failures · notifications · timestamps · destination systems · operator actions.

### Forbidden Actions
Delete history · **rewrite history** · hide failures · modify previous audit records · **edit history**.

### Failure Behaviour
If logging cannot complete: **execution status remains visible · failure is reported immediately · no audit record may be silently lost.**

---

# 10. Execution Rules

- Engine 6 executes **only Approved Validation Decisions**.
- Execution is **deterministic**.
- Every execution is **traceable**.
- Every execution has **exactly one Execution ID**, and every attempt exactly one Execution Attempt ID.
- **Exactly one successful posting** is allowed per idempotency key, unless the user explicitly requests another.
- **Engine 6 never performs reasoning.**

## Retry Rules

- Retry automatically according to policy.
- **Never retry forever.**
- Retry history is permanently recorded.
- Every retry references the **same Execution ID**.
- **Retry never creates duplicate postings.**

## Queue Rules

If execution cannot complete: **preserve the validated transaction · place execution into the queue · retry later · notify the user · never require reconstruction of the Accounting Decision.**

> **The user must never lose work because an external system failed.**

## Notification Rules

Engine 6 notifies on: execution started · execution successful · queued · retrying · execution failed · manual action required.

**Default recipient:** the initiating user. Future policies may extend recipients **without changing Engine 6 architecture.**

## Audit Rules

Every execution permanently records: Execution ID · Execution Attempt ID · Accounting Decision ID · Decision Version · Validation Decision ID · Destination System · Operator · Timestamp · Retry Count · Queue Events · External Response · Notification Events · Final Status.

> **Audit history is immutable. Nothing is ever deleted. Nothing is ever rewritten.**

---

# 11. Execution Confidence Model

> **"How confident are we that the validated decision was executed successfully?"**

**Execution Confidence measures transport and execution only — never accounting correctness.**

## It is not

Evidence Reliability · Understanding Confidence · Accounting Confidence · Clarification Confidence · Validation Confidence. It is the **sixth** layer ([`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes)).

## Influenced by

Successful external connection · successful posting · verified external acknowledgement · complete response processing · successful audit logging · notification status.

## Owner

**The parent Execution Engine assembles it, mechanically.** Its six inputs span the whole chain and no single sub-engine sees them all.

## Rules

- Execution Confidence **never changes accounting confidence**.
- Execution Confidence **never changes Validation confidence**.
- **A failed execution cannot have High Execution Confidence.**
- It measures transport and execution only, not accounting correctness.

---

# 12. Conflict Handling

**Engine 6 never resolves business or accounting conflicts.** Those were handled by previous engines.

It handles only **execution conflicts**: external system unavailable · authentication failure · network interruption · duplicate posting attempt · queue conflict · retry conflict · timeout · partial execution failure.

Every execution conflict must **remain visible · reference the responsible component · be recorded in the audit log · preserve execution state · trigger the appropriate retry, queue or notification policy**.

> **Execution conflicts are never hidden or silently ignored.**

---

# 13. Communication Contracts

| Direction | Contract |
|---|---|
| **Inbound** — Validation → Execution | [`COMMUNICATION_RULES_VALIDATION_ENGINE.md`](COMMUNICATION_RULES_VALIDATION_ENGINE.md) |
| **Internal** | [`COMMUNICATION_RULES_EXECUTION_INTERNAL.md`](COMMUNICATION_RULES_EXECUTION_INTERNAL.md) |
| **Outbound** | The **Execution Result** — the only artifact Engine 6 publishes |

External communications — Tally, Zoho, APIs, notifications, exports — are performed by Engine 6 and **recorded in the audit trail**. They are not engine boundaries and carry no artifact contract.

## Decision Authority

Every communication contract carries this block unchanged:

> **The sending engine owns the meaning of its artifact.** The receiving engine may consume, analyze and produce its own artifact; it may not rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 14. Quality Standard

## Success
Deterministic execution · exactly-once posting · complete traceability · permanent audit history · visible failure · accurate external communication.

## Failure
Duplicate postings · silent failure · lost work · deleted or rewritten history · an invented external response · an accounting decision changed by a transport problem.

---

# 15. Execution Invariants

1. Engine 6 **never reasons** about accounting.
2. Engine 6 **never modifies upstream artifacts**.
3. Engine 6 communicates **only through the Execution Result**.
4. The Execution Result is the **only outbound artifact**.
5. `Posting Result` remains **internal only**.
6. The Audit Record is **append-only and referenced**, never carried.
7. **Execution Confidence exists** and is separate from the other five layers.
8. **Runtime failures** belong to the Application Layer.
9. **Business execution failures** belong to Engine 6.
10. **No backward workflow path** exists from Engine 6.
11. Duplicate protection works per **Decision Version + Destination**.
12. **Correction executions maintain lineage.**

Plus: **IDENTITY ≠ INTELLIGENCE** holds for Execution ID and Execution Attempt ID.

---

# 16. Final Verification Checklist

- [x] 1. Exactly six Execution sub-engines exist.
- [x] 2. No new folders or architectural layers were added.
- [x] 3. Every sub-engine owns exactly one responsibility.
- [x] 4. Engine 6 never performs reasoning.
- [x] 5. Engine 6 never modifies upstream artifacts.
- [x] 6. Engine 6 is the only engine allowed to interact with external systems.
- [x] 7. Duplicate posting is prevented through idempotent execution.
- [x] 8. Retry and queue behaviour are fully defined.
- [x] 9. Every execution produces exactly one Execution Result.
- [x] 10. Every execution event is permanently recorded.
- [x] 11. Audit history is immutable.
- [x] 12. Execution Confidence is separate from all previous confidence models.
- [x] 13. No hidden communication paths exist.
- [x] 14. Parent engine assembles but never overrides sub-engine outputs.
- [x] 15. Creator and Owner remain separate architectural concepts where applicable — and where they coincide (§5.4) it is stated.
- [x] 16. IDENTITY ≠ INTELLIGENCE remains a system-wide rule.
- [x] 17. Repository structure unchanged — 6 engines, locked sub-engine identities.
- [x] 18. No implementation code has been added.

---

## Related documents

- [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md) — highest authority.
- [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md) — commitments honoured and conflicts resolved before this lock.
- [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md) — the engine that authorises this one.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) · [`DATA_FLOW.md`](DATA_FLOW.md) · [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md).
