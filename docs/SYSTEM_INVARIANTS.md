# System Invariants

> **Precedence level 1 — the highest authority in this repository.**
>
> Every other document is subordinate to this one. Where any document contradicts an invariant here, that document is wrong and must be revised.

---

## Precedence hierarchy

```text
1. System Invariants              ← this document
2. Locked Architecture Decisions   MVP_ARCHITECTURE · DATA_FLOW · SYSTEM_BOUNDARIES ·
                                   ENGINE_RESPONSIBILITIES · SUB_ENGINE_RESPONSIBILITIES
3. Engine Specifications           ENGINE_1..6_*_RULES.md
4. Communication Contracts         COMMUNICATION_RULES_*.md
5. README documentation            every README.md
```

**An invariant is stated once, here.** Other documents may reference it; they may not restate it in different words. Two differing statements of the same rule is a defect.

---

# INV-1 — Locks win

> **If a newer specification contradicts a previously locked architectural decision, the lock wins by default. The newer specification must be revised instead of silently changing architecture.**

Identities **and commitments** are stable. A component is never renamed once another component references it; a promise made about a future engine is never quietly withdrawn.

## Forward Dependency Inventory

**Before any engine is locked**, a Forward Dependency Inventory must list every promise previous engines already made about it.

> **Conflicts are resolved before the specification is written, never during propagation.**

See [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md).

## Reopening

An invariant may be refined only by a **higher-level contradiction** — a demonstration that the architecture cannot correctly represent required behaviour. Convenience, elegance and preference are not grounds. Every refinement is recorded explicitly, never applied silently.

---

# INV-2 — Confidence changes only when evidence changes

> **Confidence is recalculated whenever evidence changes. It may increase, decrease, or remain unchanged, depending on the complete evidence set.**

Stated as a recalculation, not a direction. A directional rule always eventually meets a case it forbids.

- **Corroboration is not new evidence.** It raises confidence *only* because it establishes that two **independent** sources support the same fact — the increase comes from added **evidential support**, never from agreement itself.
- **Confidence never changes because an engine reasoned harder.** Understanding may improve; confidence does not follow.
- Independence must be recorded, so a human can judge whether two sources were genuinely independent or two copies of one mistake.

## The confidence layers

Each engine measures confidence about its own responsibility. None replaces another; all travel.

| Engine | Confidence | Asks |
|---|---|---|
| Input | Evidence confidence | Was information captured correctly? |
| Understanding | Understanding confidence | Was the business event understood correctly? |
| Accounting | Decision confidence | Is the accounting treatment likely correct? |
| Clarification | Clarification confidence | Has every decision-blocking uncertainty been found? |
| Validation | Validation confidence | Is execution safe? |
| Execution | Execution confidence | Did execution succeed? *(transport only — never accounting correctness)* |

**A later confidence never exceeds the weakest critical confidence it depends on.**

---

# INV-3 — Transaction identity is separate from artifact identity

Three identity concepts, three distinct jobs:

| Concept | Identifies | Scope |
|---|---|---|
| **Artifact ID** | One artifact | One artifact |
| **Parent Artifact Version** | Versions of the same artifact | One artifact's history |
| **Transaction ID** | **One business event** | **The entire lifecycle** |

> **The Transaction ID is generated exactly once, when a business event is first recognised. It never changes. Every artifact references exactly one.**

```text
Document Evidence Object → Business Understanding Object → Accounting Decision
    → Clarification Request → Validation Decision → Execution Result
```

**The Application Layer creates it** (INV-4). Engines consume it; they never create or modify it.

## Many documents, one business event

> **Many Document Evidence Objects may contribute to one Business Understanding Object.**

Extraction stays **document-centric**. Understanding becomes **transaction-centric** and owns evidence aggregation. The Document Evidence Object is never redesigned to hold several documents.

---

# INV-4 — Reasoning is separate from workflow

> **Workflow orchestration belongs to the Application Layer, not the Cognitive Architecture.**

**Engines are reasoning stages. They never own workflow. Workflow never becomes another engine.**

| The Application Layer owns | It never owns |
|---|---|
| Creating the Transaction ID · starting engines · routing artifacts · lifecycle · retrying engine execution · coordinating state transitions · deciding a transaction is complete | Any decision · any artifact · any confidence · any reasoning · any authority-table row |

Lives in [`src/services/`](../src/services/).

## Runtime failure is not business failure

**Business failures belong to sub-engines. Runtime failures belong to the Application Layer.**

When an engine crashes:

- **Never fabricate outputs.**
- **Never continue with partial reasoning.**
- Preserve completed artifacts.
- Record the runtime failure.
- Allow safe restart **from the last completed artifact**.

> **Engine failure is not an artifact.** An engine that cannot complete produces nothing — never a partial artifact.

## Transaction state machine

```text
Input → Understanding → Accounting → Clarification → Validation → Execution → Completed
                                                                             ↘ Failed
```

- Each Transaction ID is in **exactly one state** at any moment.
- **State transitions are atomic.**
- **Parallel transactions are allowed. Parallel states for one transaction are prohibited.**
- `Completed` is not permanently terminal — a correction returns the transaction to an active state (INV-5).

Distinct from Clarification Status, which the Clarification Engine owns: transaction state is *workflow*; clarification status is *an artifact's* lifecycle.

---

# INV-5 — History is never modified

> **Every artifact is immutable after creation. Correction means a new version, never an edit.**

## Versioning

Every artifact carries an **Artifact ID**, a **Version**, and its **Parent Artifact Version(s)**.

- A new version is created when new information changes what an artifact should assert. **Only the owning engine creates it.**
- A version, once created, is frozen — content, confidence, uncertainty, assumptions and reasoning alike.
- Each version records the exact parent versions it derived from, so any artifact traces back to the raw artifact.
- A downstream artifact is **stale** when a parent version it derived from is no longer current. Staleness is **structural**, not noticed.
- **Every version is retained.** Superseded versions are never deleted; the chain is the audit trail.

## Ownership

> **Every artifact has exactly one owner: the engine that creates it. The owner controls creation, versioning, integrity and meaning.**

| Other engines may | Other engines may NOT |
|---|---|
| Read · Analyze · Reference | Modify · Rewrite · Delete · Remove uncertainty · Change confidence |

**Creator and owner are separate concepts.** A sub-engine creates; an engine owns.

## Correction

> **A correction is a new Accounting Decision referencing the original Transaction ID.**

```text
Wrong Entry → New Business Understanding → New Accounting Decision (new version)
    → Reverse Entry → Validation → New Execution Result
```

The **Transaction ID stays the same** — it is the same business event. Execution never edits history.

---

# INV-6 — Every canonical artifact has a specification-level schema

**Schemas are architecture, not implementation.**

Each defines: identity fields · required fields · optional fields · relationships · ownership · versioning · Transaction ID reference · evidence references · confidence representation.

No database decisions. No programming language.

> **Two independent engineers must build identical artifacts from the specification.**

---

# INV-7 — Screening is not deciding

A cheap identity check and a judgement are different problems with different owners.

| | Screens | Decides |
|---|---|---|
| Duplicates | **Input Engine** — same file, same hash, same document number | **Validation Engine** — same economic transaction, same accounting effect |
| Output | **A fact with provenance** | **A judgement** |
| Purpose | Prevent unnecessary processing | Prevent double-posting |

A screening component never rejects and never decides.

---

# INV-8 — Permission to execute is decided before execution

> **The Accounting Engine decides the correct accounting treatment. The Validation Engine decides whether execution is legally permitted.**

Closed accounting periods, statutory locks, authorisation limits — every permission gate is a **Validation** concern.

**Execution must never discover that posting was impossible.**

---

# INV-9 — IDENTITY ≠ INTELLIGENCE

> **IDs identify objects. They do not influence reasoning.**

Applies to Document ID, Transaction ID, Decision ID, Clarification ID, Validation ID, Execution ID, User ID, and any future identifier.

An identifier exists only for **identity · traceability · lifecycle tracking · audit history**. It must never influence ledger selection, journal creation, tax treatment, validation outcome, confidence, or any future decision.

```text
✗ "Because ACC-000123 existed before, choose the same accounting treatment."
```

---

# INV-10 — One concept, one owner

> **No responsibility exists in two places. No component owns two problems.**

- Every artifact has one creator and one owner.
- Every decision has one authority.
- Every communication boundary has one sender, who owns its contract.
- **No sub-engine creates another sub-engine's decision.** No hidden override. No circular reasoning.
- **A parent engine assembles mechanically.** It may combine, organize and structure; it may never author, modify, approve, override or suppress a sub-engine's output.

If a component finds itself deciding two kinds of thing, or two components could each plausibly make the same call — **stop and ask.**

---

# INV-11 — Evidence carries its origin, permanently

Every fact records:

| Attribute | Values |
|---|---|
| **Source Type** | `Document` · `Human` · `Structured Metadata` |
| **Source ID** | Which source it came from |
| **Evidence Reference** | Where within that source |
| **Timestamp** | When it entered the system |
| **Confidence** | Extraction confidence for documents; **capture confidence** for provided sources |
| **Corroborated** | Whether another source supports it |

> **No engine may merge these origins into a single anonymous fact.**

## A human note is evidence, not truth

It may supply intent, explanation, business context or missing narrative. It may **never** be treated as confirmed fact, **never** automatically override document evidence, and **never be rewritten** — it is stored verbatim.

**Capture confidence measures how faithfully an input was stored, never whether it is true.** A human note may never raise Evidence Reliability simply by existing.

---

# INV-12 — Knowledge is shared; authority is not

The **Knowledge Brain** ([`src/brain/`](../src/brain/)) provides knowledge to every engine on identical terms, in two layers:

| Layer | Holds |
|---|---|
| **Global Knowledge** | Accounting standards · GST · Income Tax · Companies Act · ICAI guidance |
| **Company Knowledge** | Chart of accounts · ledger mappings · cost centres · approval policies · financial year · destination-system configuration · GST registrations · bank accounts |

**Advisory, never binding.** Any engine may ignore it, recording why. It may never return a decision, recommendation, approval, ledger, rate or instruction, and owns no decisions, artifacts, confidence or workflow.

> **Knowledge flows into engines. Decision authority never leaves engines.**

---

# INV-13 — Reality validation precedes architectural commitment

> **A specification may define principles. Reality defines constraints. Architecture must satisfy both.**

Where an architectural decision depends on an assumption about the outside world — an external system's requirements, a regulatory domain's scope, how work actually arrives — that assumption is **measured before it is locked**, not after.

---

## Uncertainty, stated once

These follow from the invariants above and hold everywhere:

- **Nothing is invented.** When information is unclear, report uncertainty. Never guess.
- **Nothing assumes silently.** Every component relying on an assumption records what it assumed and why.
- **Uncertainty is never removed, only described more precisely.**
- **Conflicts remain visible** until new information resolves them or a human explicitly accepts them. No conflict is silently resolved.
- **Gaps stay gaps.** An absent fact is marked absent until supplied. No defaults, no conventions, no most-common-value.
- **Failure is as loggable as success.**
