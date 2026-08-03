# Application Layer — Responsibility Matrix

> **Precedence level 3.** Every responsibility, with **exactly one owner**.
>
> `SYSTEM_INVARIANTS.md` INV-10 — **one concept, one owner.** A responsibility appearing twice is a defect, not a redundancy.
>
> This document exists to be **checked**, not read. Any duplicate owner is a failure.

---

## Workflow — the Application Layer owns all of it

| Responsibility | Owner | Nobody else may |
|---|---|---|
| Create the Transaction ID | **Application Layer** | No engine creates or modifies one |
| Start an engine | **Application Layer** | No engine starts another |
| Route an artifact between engines | **Application Layer** | No engine passes an artifact directly |
| Change transaction state | **Application Layer** | No engine reads, writes or infers state |
| Retry engine **execution** | **Application Layer** | No engine retries itself |
| Restart a **crashed** engine | **Application Layer** | `posting_manager` never restarts a workflow |
| Hold the `Approved With Warning` gate ⚠️ | **Application Layer** | Engine 6 cannot hold a workflow gate |
| Release a held decision ⚠️ | **Application Layer** (human-triggered) | No engine releases; no timer releases |
| Decide a transaction is complete | **Application Layer** | No engine declares completion |
| Record the audit trail of transitions | **Application Layer** | No engine writes workflow history |
| Read the Classified Error's responsible stage and route | **Application Layer** | `error_handler` names; it never routes |

---

## Reasoning — the Application Layer owns none of it

| Responsibility | Owner | The Application Layer must never |
|---|---|---|
| Extract facts from a document | Engine 1 | Interpret or pre-classify a document |
| Six provenance attributes per fact | Engine 1 | Add, infer or complete provenance |
| Aggregate many documents into one business event | Engine 2 | Split or merge transactions |
| Build the Transaction Story | Engine 2 | Read it to form an opinion |
| Decide ledger, amount, tax treatment, period | Engine 3 | Supply a hint or a preference |
| Raise a doubt | Engine 3 | Decide something is not worth doubting |
| Accounting Risk Analysis — risk in the **reasoning** | Engine 3 | Compute or adjust risk |
| Judge which doubts **block** | Engine 4 | Decide a doubt is unimportant |
| Produce a Clarification Request | Engine 4 | Answer one |
| Clarification Status — an artifact's lifecycle | Engine 4 | Merge it with transaction state |
| Validate correctness | Engine 5 | Override, re-run or reinterpret a status |
| Risk Assessment — risk in **posting** | Engine 5 | Compute exposure or materiality |
| Choose one of four validation statuses | Engine 5 | Treat `Approved With Warning` as `Approved` |
| Translate a decision into a voucher | Engine 6 | Modify a voucher |
| Communicate with the external system | Engine 6 | Contact Tally |
| **Re-post** a transport-failed voucher | Engine 6 (`posting_manager`) | Decide a voucher should be sent again |
| Idempotency: Decision ID + Version + Destination | Engine 6 | Compute or bypass the key |
| Classify an execution error | Engine 6 (`error_handler`) | Classify or reclassify |

---

## Knowledge — the Brain owns it, and only advisorily

| Responsibility | Owner | Nobody else may |
|---|---|---|
| Accounting standards, GST, Income Tax, Companies Act, ICAI guidance | **Brain** | No engine holds its own private copy |
| Chart of accounts, policies, financial year, registrations | **Brain** | — |
| Historical accounting patterns | **Brain** | — |
| **Deciding what to do with knowledge** | **The asking engine** | The Brain never returns a decision, treatment, approval, ledger, rate or instruction |
| Recording why Brain knowledge was ignored | **The asking engine** | The Brain never learns it was ignored |

**The Application Layer never queries the Brain.** No arrow exists between them (AL-INV-8).

---

## The four splits that would otherwise be duplicated

Each of these was a genuine collision, resolved in the locked documents. Repeating them here so they cannot silently re-merge.

### 1. Retry

```
Engine 6 reposts a TRANSPORT-FAILED VOUCHER.        posting_manager
Application Layer restarts a CRASHED ENGINE.        here
```
`FORWARD_DEPENDENCY_INVENTORY.md:80` — *"Split."* `COMM_EXECUTION_INTERNAL:131` — *"No responsibility exists in two places."*

### 2. Error routing

```
error_handler NAMES the responsible stage inside the Classified Error.
Application Layer READS it and ROUTES.
```
Engine 6 gains no backward arrow. `FORWARD_DEPENDENCY_INVENTORY.md:64`.

### 3. Risk

```
Accounting Risk Analysis   Engine 3   risk in the REASONING — how thin the basis
Risk Assessment            Engine 5   risk in POSTING — exposure, reversibility
```
Deliberately separated, never merged.

### 4. State versus status

```
Transaction state     Application Layer   WORKFLOW
Clarification Status  Engine 4            AN ARTIFACT'S LIFECYCLE
```
`DATA_FLOW §14` — distinct, never inferred from one another.

---

## Artifact ownership — six artifacts, six owners, none the Application Layer's

| Artifact | Creator | Owner | Application Layer's role |
|---|---|---|---|
| Document Evidence Object | Engine 1 | Engine 1 | Route only |
| Business Understanding Object | Engine 2 | Engine 2 | Route only |
| Accounting Decision | Engine 3 | Engine 3 | Route only |
| Clarification Request | Engine 4 | Engine 4 | Route only |
| Validation Decision | Engine 5 | Engine 5 | Route only, **and read its status to choose a transition** |
| Execution Result | Engine 6 | Engine 6 | Route only, **and read the responsible stage to route a failure** |

**Reading a status to choose a transition is workflow, not reasoning.** The Application Layer learns *"this status means go to state X"*, never *"this decision is sound."* It is a lookup, not a judgement.

---

## Duplicate check

Every responsibility above appears **exactly once**. Verified in `ARCHITECTURE_AUDIT.md`:

```
responsibilities listed          count
distinct owners per responsibility  1 each
responsibilities with two owners    0
responsibilities with no owner      0
```

---

## Ownership conflicts — none open

| Was | Now |
|---|---|
| **Human Instruction artifact** — `FORWARD_DEPENDENCY_INVENTORY.md:94` proposed an artifact **owned by the Application Layer**, contradicting INV-4 | ✅ **Closed 2026-08-03, Amendment 4.** The artifact is **withdrawn.** It held zero of the four properties of an artifact here. *"Post this tomorrow"* is orchestration state the Application Layer already owns under INV-4, not an artifact. **INV-4 unchanged.** |

**Six canonical artifacts. Six owners. The Application Layer owns none.** No responsibility in this document has two owners, and none has none.

### The split is made at input, never inferred

```
business context box   →  Engine 1, Human Business Context, EVIDENCE
scheduling control     →  Application Layer orchestration state
```

**The Application Layer never classifies free text.** Classifying would be reasoning, which INV-4 forbids — it would have swapped one violation for another. Free text typed into the context box is stored **verbatim as evidence** and has no scheduling effect, whatever it says.
