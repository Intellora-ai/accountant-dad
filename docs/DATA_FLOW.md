# Data Flow

> How information moves through the system, what artifact crosses each arrow, and what happens when a stage refuses to pass work forward.

---

## 1. The Pipeline

```text
Input
 ↓
Understanding
 ↓
Accounting Decision
 ↓
Clarification (if required)
 ↓
Validation
 ↓
Tally Execution
```

---

## 2. Artifacts

Every arrow carries exactly one named artifact. An engine may only consume the artifact handed to it — never the internals of the engine that produced it, and never an artifact from further upstream unless it is listed here.

| # | From → To | Artifact | Contains |
|---|---|---|---|
| 0 | *external* → **Input** | **Raw Artifact** | The document as received: scan, photograph, PDF, digital file. |
| 1 | **Input** → **Understanding** | **Document Evidence Object** | Document ID · source references · the **Structured Document** (extracted text, detected fields, document structure, tables, field values, field locations) · the **Human Business Context** (optional, verbatim user text with source, timestamp and evidence reference) · the **Confidence Report** (confidence scores, uncertainty markers, reliability information, risky fields). |
| 2 | **Understanding** → **Accounting** | **Business Understanding Object** | The **Transaction Story** (the assembled narrative) · **Supporting Understanding Data** (the six sub-engine Results) · **Identified Unknowns** · **Confidence Assessment**. What happened, in business terms only. Every fact traced to its evidence; every gap named; every conflict preserved. No accounting vocabulary. |
| 3 | **Accounting** → **Clarification** *or* **Validation** | **Accounting Decision** | Decision ID · **Decision Status** · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts. |
| 4 | **Clarification** → **Validation** | **Clarification Request** | Clarification ID · Related Decision ID · **Related Artifact Version** · missing information · detected conflicts · required clarification · reason it is required · affected decision · priority · supporting evidence references · Clarification Confidence · status. |
| 4x | **Clarification** → *external actor* | *(the same Clarification Request)* | Delivered by a later system layer to a user, accountant or external system. **Engine 4 never asks anyone directly.** |
| 4y | *external actor* → **Input / Understanding / Accounting** | **Clarification Answer** | New information re-entering through the normal pipeline. It never returns to Engine 4; the responsible upstream engine emits a **new artifact version**. |
| 5 | **Validation** → **Tally** *or* back | **Validation Verdict** | Approve, reject, or flag — with every finding that drove it and, for a rejection, the stage responsible. |
| 6 | **Validation** → **Tally** | **Approved Accounting Decision** | The decision, and the verdict approving it. Nothing unapproved crosses this arrow. |
| 7 | **Tally** → *external* | **Posting Result** + **Audit Record** | Posted, rejected or partial, with Tally's identifiers; and the permanent, append-only record of the attempt. |

### 2.1 Document Evidence Object

The Input Engine's output has one name. `Structured Document` and `Confidence Report` are its two **components**, never the name of the artifact itself. No engine may create an alternative name, and no duplicate representation may exist.

```text
Document Evidence Object
├── Document ID
├── Source references
├── Structured Document ──── extracted text · detected fields · document structure ·
│                            tables · field values · field locations     [EXTRACTED]
├── Human Business Context ─ original user text · source = Human ·
│                            timestamp · evidence reference   [PROVIDED, optional]
└── Confidence Report ────── confidence scores · uncertainty markers ·
                             reliability information · risky fields
```

A downstream engine that consumes one part names that part — *"the Confidence Report within the Document Evidence Object"* — and never treats it as a separate artifact on its own arrow.

**Human Business Context** is present only when the user supplied a plain-English description. It is **optional**, and the system must work correctly without one. It stays **independent** from extracted document evidence: the two are separate, linked entries, and **Engine 1 never merges them into a single fact**. See §12.

**Document ID exists only for identity, traceability, and lifecycle tracking. It carries no accounting meaning and must never influence accounting decisions.**

Full contract: [`ENGINE_1_INPUT_ENGINE_RULES.md` §5](ENGINE_1_INPUT_ENGINE_RULES.md#5-output-contract).

### 2.2 Business Understanding Object

The Understanding Engine's output has one name. `Transaction Story` is its narrative **component**, never the name of the artifact itself.

```text
Business Understanding Object
├── Transaction Story ................. the final assembled narrative
├── Supporting Understanding Data ..... the six sub-engine Results
│   └── Transaction · Party · Item · Payment · Timeline · Business Context
├── Identified Unknowns ............... every gap, named
└── Confidence Assessment ............. evidence confidence · understanding
                                        confidence · missing information ·
                                        detected conflicts
```

**Transaction Story is not an independent understanding component.** It is the final assembled narrative created by `story_builder` from the six Results. The Results are the evidence *for* the story and travel alongside it, so a downstream engine may read the narrative or the underlying records.

**Creator and owner differ here.** `story_builder` **creates** the artifact; the **Understanding Engine owns** it. Story Builder does not become an independent owner.

Full contract: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §5](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#5-output-contract).

### 2.3 Accounting Decision

The Accounting Engine's output. The name is **final**, fixed by the Engine 3 contract.

```text
Accounting Decision
├── Decision ID              identity only — see IDENTITY ≠ INTELLIGENCE (§9)
├── Decision Status          COMPLETE | INCOMPLETE_INFORMATION_REQUIRED
├── Accounting treatment
├── Ledger classification
├── Debit entries
├── Credit entries
├── Journal structure
├── Tax treatment
├── Accounting assumptions
├── Risk indicators          from the Accounting Risk Analysis
├── Decision confidence
├── Supporting reasoning
└── Unresolved doubts        from the Accounting Doubt Report
```

**Decision Status** exists so a downstream engine can ask *can this move forward?* and get a structured answer rather than infer one from prose. `INCOMPLETE_INFORMATION_REQUIRED` names the required clarification; the Accounting Engine never completes a decision by guessing.

**Creator and owner differ here.** `decision_output` **creates** the artifact; the **Accounting Engine owns** it. `decision_output` does not become an independent owner.

**Accounting Treatment Result** is internal to Engine 3 and does not cross any engine boundary — it combines the Ledger Recommendation, Tax Treatment Recommendation and Accounting Period Treatment before journal construction.

Full contract: [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md` §5](ENGINE_3_ACCOUNTING_ENGINE_RULES.md#5-output-contract).

### 2.4 Clarification Request

The Clarification Engine's output. It states what prevents a decision from being safely completed — and never resolves it.

```text
Clarification Request
├── Clarification ID                 identity only — see IDENTITY ≠ INTELLIGENCE (§9)
├── Related Decision ID
├── Related Artifact Version         the exact decision version this was raised against
├── Missing Information
├── Detected Conflicts
├── Required Clarification
├── Reason Clarification Is Required
├── Affected Decision
├── Priority                         Critical | High | Medium | Low
├── Supporting Evidence References
├── Clarification Confidence
└── Status                           Created | Waiting for Information |
                                     Information Received | Obsolete | Closed
```

**Related Artifact Version** is the universal versioning rule (§11) applied at this boundary. A request raised against decision `v3` is **Obsolete** the moment `v4` exists — it must never be answered against a decision that has since been rebuilt.

**Creator and owner differ here.** `question_generator` **creates** the artifact; the **Clarification Engine owns** it, along with Clarification Status and Clarification History.

**Validation receives two artifacts** — the Accounting Decision (primary, from the Accounting Engine) and the Clarification Request (supplementary, from the Clarification Engine). Validation cannot validate a Clarification Request alone.

Full contract: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md` §5](ENGINE_4_CLARIFICATION_ENGINE_RULES.md#5-output-contract).

---

## 3. The Flow in Full

```text
                          Raw Artifact
                               │
                               ▼
                    ┌────────────────────┐
                    │   INPUT ENGINE     │
                    └────────────────────┘
                               │
                    Document Evidence Object
                               │
                               ▼
                    ┌────────────────────┐
                    │ UNDERSTANDING      │
                    └────────────────────┘
                               │
                 Business Understanding Object
                               │
                               ▼
                    ┌──────────────────────────┐
                    │   ACCOUNTING ENGINE      │
                    └──────────────────────────┘
                               │
                   Accounting Decision (+ assumptions,
                               │          + risks, + doubts)
                    ┌──────────┴───────────┐
                    ▼                      │
          ┌────────────────────┐           │
          │  CLARIFICATION     │           │
          └────────────────────┘           │
                    │                      │
          Clarification Request            │
                    │                      │
                    ├──► external actor    │
                    │    (UI / API / human)│
                    │         │            │
                    │  Clarification Answer│
                    │         │            │
                    │         ▼            │
                    │  Engine 1 / 2 / 3    │
                    │  rebuild → new       │
                    │  artifact version    │
                    │                      │
                    ▼                      ▼
                         ┌────────────────────┐
                         │ VALIDATION ENGINE  │
                         └────────────────────┘
                          receives BOTH the
                          Accounting Decision
                          and the Clarification Request
                                      │
                     ┌────────────────┴────────────────┐
                     │                                 │
                 approve                        reject / flag
                     │                                 │
                     ▼                                 ▼
        Approved Accounting Decision      return to the NAMED stage
                     │                    (Clarification, Accounting,
                     ▼                     Understanding, or Input)
          ┌────────────────────┐                       │
          │   TALLY ENGINE     │                       │
          └────────────────────┘              never forward, never
                     │                        silently discarded
                     ▼
        Posting Result + Audit Record
```

---

## 4. Conditional Paths

### 4.1 Clarification is conditional

Clarification runs **only when `stop_decision` judges clarification necessary.** Not every uncertainty deserves a request: some has no effect on accounting treatment, some changes the entire decision. When no clarification is required, no Clarification Request is created and the Accounting Decision goes to Validation alone.

The condition is not "the Accounting Engine raised a doubt." `doubt_detection` produces doubt; whether that doubt *blocks* is judged separately and later. A decision may carry recorded doubts and still proceed — and the doubts travel with it either way.

**If necessity cannot be determined safely, the default is Clarification Required.** An unnecessary question costs time; a missed one costs correctness.

### 4.2 The clarification loop runs outside Engine 4

Engine 4 is **emit-only**. It never asks users and never receives answers as a decision engine.

```text
Accounting Decision
        ↓
Clarification Request
        ↓
External actor  (UI / API / human)          ← outside every engine
        ↓
Clarification Answer
        ↓
Engine 1 / 2 / 3 rebuilds the affected artifact
        ↓
New Accounting Decision
        ↓
Engine 4 runs again if needed
```

New information enters through the **normal pipeline**. This preserves artifact ownership — the engine that owns an artifact is the only one that ever rewrites it — and it means no backward mutation exists anywhere in the system.

### 4.3 Clarification tracks status; it never resolves

`decision_updater` owns the Clarification Status lifecycle: **Created → Waiting for Information → Information Received → Closed**, with **Obsolete** reachable from any state. Both `Closed` and `Obsolete` are terminal.

Engine 4 owns **every transition** but no **resolution**. A request is closed only when a new artifact version no longer carries the uncertainty that caused it; it becomes obsolete when a newer version supersedes the one it was raised against. **Obsolete ≠ Closed** — collapsing the two would hide that a question went unanswered.

Full state machine: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md` §7](ENGINE_4_CLARIFICATION_ENGINE_RULES.md#7-clarification-lifecycle).

### 4.4 Validation returns work; it never passes it on

A rejection does not move forward and is never quietly dropped. `validation_decision` must name the stage responsible:

| Finding | Returns to |
|---|---|
| The data are unsound or a field is missing | **Input** — or **Clarification**, if a human can supply it |
| A business fact is wrong or contradictory | **Understanding** |
| The treatment, entry or tax is wrong | **Accounting** |
| The defect is a material uncertainty a human could resolve | **Clarification** |
| A duplicate was found | **Clarification** — a human decides |

A **flag** is distinct from a rejection: the decision is not defective, but posting it unattended is judged unsafe. It goes to a human, not back to a stage.

---

## 5. Flow Rules

These hold for every transaction, without exception.

1. **One direction.** Work moves forward only. **No artifact ever moves backward, and no engine ever mutates an upstream artifact.** The only backward movement in the system is a *return* — Validation returning a rejection to a named stage, which is a routing instruction, not an artifact edit. New information re-enters at Engine 1, 2 or 3 as a **new artifact version**, never as a patch.
2. **No skipping.** No stage may be bypassed. A decision cannot reach Tally without a Validation Verdict approving it, however obvious it appears.
3. **No reaching back.** An engine consumes only the artifact handed to it. The Accounting Engine reasons from the Business Understanding Object, never from the Document Evidence Object or the raw artifact. The Tally Engine acts on the Approved Decision, never on the understanding.
4. **No reaching sideways.** No engine writes into another engine's output. Every artifact has exactly one producing engine.
5. **Doubt travels.** Doubts, risks and low-confidence markers are carried forward with the artifact at every stage. They are never dropped because a later stage found them inconvenient.
6. **Gaps stay gaps.** A fact that is absent is marked absent and remains absent until a human supplies it. No stage fills a gap by inference, default or convention.
7. **Approval precedes execution.** Nothing reaches Tally that the Validation Engine has not approved.
8. **Every attempt is recorded.** Posting attempts, successes, partials and failures are all written to the audit record. Failure is not less loggable than success.

---

## 6. Artifact Ownership

> **Every artifact has exactly one owner. The engine that creates an artifact owns that artifact permanently.**
>
> **Artifacts are immutable after creation.**

### What ownership means

The owner engine controls:

- **Creation** — only the owner may produce the artifact.
- **Versioning** — only the owner may produce a new version of it.
- **Integrity** — the owner is answerable for the artifact being internally sound.
- **Meaning** — the owner defines what the artifact asserts.

| Other engines **may** | Other engines **may NOT** |
|---|---|
| Read | Modify |
| Analyze | Rewrite |
| Reference | Delete |
| | Remove uncertainty |
| | Change confidence |

### Worked example

The Input Engine creates the **Document Evidence Object**, and therefore owns it permanently.

- ✓ The Understanding Engine reads it.
- ✗ The Understanding Engine edits it.
- ✗ The Accounting Engine edits it.
- ✗ The Validation Engine edits it.

### Creator and owner are not always the same component

An artifact is **created** by a sub-engine but **owned** by its engine. Story Builder creates the Business Understanding Object; the **Understanding Engine** owns it. Story Builder does not become an independent owner.

### Versioning, not mutation

New information never rewrites an existing artifact. The **owning engine** creates an updated version; previous versions remain unchanged.

```text
Business Understanding Object → missing information detected → Clarification Engine
    → new information collected → Understanding Engine creates updated version
```

This is why the clarification loop runs *outside* Engine 4 (§4.2): an answer does not return to the engine that asked, it re-enters at Engine 1, 2 or 3, which **remakes** the artifact it owns. Nothing is ever patched in place. Full rules: §11.

---

## 7. Decision Authority

> **Authority belongs only to the engine responsible for that decision.**
>
> No engine may make, override, or silently substitute a decision that belongs to another.

| Engine | Owns decisions | Cannot decide |
|---|---|---|
| **Input** | Extraction method · extraction confidence · document structure | Business meaning · accounting treatment · tax · ledger |
| **Understanding** | Business event interpretation · entity relationships · business story | Debit/credit · journal · ledger · tax · accounting treatment |
| **Accounting** | Accounting treatment recommendation | Validation approval · execution |
| **Clarification** | Questions required to remove uncertainty · when enough information exists | Accounting answers without evidence |
| **Validation** | Accept · reject · request correction | Creating accounting decisions |
| **Tally** | Execution result | Accounting reasoning |

Authority is also divided *within* an engine. See each locked engine specification for its internal authority table — [Engine 1](ENGINE_1_INPUT_ENGINE_RULES.md) · [Engine 2](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md).

---

## 8. Boundary Contract Requirement

Every engine boundary **must** define all nine:

1. **Input artifact** — what is received.
2. **Output artifact** — what is produced.
3. **Artifact creator** — which component builds it.
4. **Artifact owner** — which engine owns it permanently.
5. **Allowed transformation** — what the receiver may do.
6. **Forbidden transformation** — what the receiver may never do.
7. **Decision authority** — who decides what, on each side.
8. **Uncertainty movement** — how doubt, gaps and confidence travel across the boundary.
9. **Failure movement** — where a failure goes and who must handle it.

Items 3 and 4 are separate because creator and owner differ: a sub-engine creates, an engine owns.

### The standard decision-authority block

Every communication contract carries this, unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

### Contracts

| Boundary | Contract | Status |
|---|---|---|
| Input → Understanding | [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) | Locked |
| Understanding, internal | [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) | Locked |
| Understanding → Accounting | [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) | Locked |
| Accounting, internal | [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md) | Locked |
| Accounting → Clarification | [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md` §2](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md#2-boundary-contract--accounting--clarification) | Locked |
| Accounting → Validation | [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md` §3](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md#3-boundary-contract--accounting--validation) | Locked |
| Clarification, internal | [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md) | Locked |
| Clarification → Validation | — | Placeholder until Engine 5 |
| Validation → Tally | — | Placeholder until Engine 5 |

**One contract per boundary.** The sending engine owns the contract of what leaves it; the receiving engine references it. No duplicate communication documents.

---

## 9. IDENTITY ≠ INTELLIGENCE

> **IDs identify objects. They do not influence reasoning.**

Applies to **Document ID**, **Decision ID**, Transaction ID, User ID, and any future identifier.

An identifier exists only for:

- Identity
- Traceability
- Lifecycle tracking
- Audit history

An identifier must **never** influence ledger selection · journal creation · tax treatment · validation outcome · confidence · future decisions of any kind.

```text
✓ Correct     Decision ID: ACC-000123        → "Track this decision."

✗ Incorrect   "Because ACC-000123 existed before, choose the same accounting treatment."
```

The failure this prevents is subtle and would be very hard to detect once present: reasoning that quietly keys off an identifier produces decisions that look justified, cite a real reference, and are wrong for a reason nothing in the audit trail records.

| Identifier | Owner | Carries |
|---|---|---|
| **Document ID** | Input Engine | Identity of the artifact only |
| **Decision ID** | Accounting Engine | Identity of the decision only |

---

## 10. Confidence Across Engines

Confidence is **layered, not merged.** Each engine measures confidence about its own responsibility, and every level is reported in its own right.

| Engine | Confidence | Asks |
|---|---|---|
| Input | Evidence confidence | Was information extracted correctly? |
| Understanding | Understanding confidence | Was the business event understood correctly? |
| Accounting | Decision confidence | Is the accounting treatment likely correct? |
| Validation | Validation confidence | Is this safe to approve? *(declared; specified with Engine 5)* |

> **Confidence can only decrease downstream unless new evidence is introduced.**

```text
Evidence Confidence  →  Understanding Confidence  →  Decision Confidence  →  Validation Confidence
                              (never increases without new evidence)
```

Later engines cannot magically increase certainty. They may only **maintain**, **reduce**, or **request clarification**. The single exemption is new evidence — which is what the Clarification Engine exists to obtain.

**A later confidence cannot ignore earlier uncertainty. Confidence must have traceability.**

---

## 11. Artifact Versioning

**Every artifact follows identical rules.** Versioning is a property of the system, not a feature of any one engine.

### Every artifact carries

| Field | Meaning |
|---|---|
| **Artifact ID** | Identity of the artifact across all its versions. Identity only — see §9. |
| **Version** | Which version this is. |
| **Parent Artifact Version(s)** | The exact versions this one was derived from. |

### When a new version is created

When **new information changes what an artifact should assert.** Only the **owning engine** creates it — the engine that created the artifact is the only one that may ever create another version of it.

### What never changes

**A version, once created, is immutable.** Its content, confidence, uncertainty, assumptions and reasoning are all frozen.

> **Correction means a new version, never an edit.**

There is no mechanism for amending a version in place, and that absence is the point: an artifact that could be quietly corrected could be quietly falsified.

### Parent–child tracking

Each version records the exact parent versions it was derived from. Any artifact can therefore be traced backwards through every intermediate version to the raw artifact it came from.

```text
Raw Artifact
  └─ Document Evidence Object      v1
       └─ Business Understanding Object  v1
            └─ Accounting Decision       v1
                 └─ Clarification Request    v1   (Related Artifact Version = Decision v1)

  new information arrives …

  └─ Document Evidence Object      v2
       └─ Business Understanding Object  v2
            └─ Accounting Decision       v2
                                             ↑ Clarification Request v1 is now Obsolete
```

### Stale detection

A downstream artifact is **stale** when a parent version it was derived from is no longer current.

Staleness is **structural, not noticed**. No engine has to spot it, remember it, or be told: the version chain makes it computable. This is what lets the Clarification Engine mark a request `Obsolete` without any engine reporting back to it.

### Audit

**Every version is retained.** Superseded versions are never deleted. The version chain *is* the audit trail — it records not only what the system concluded, but what it concluded before, and what changed the answer.

---

## 12. Evidence Provenance

**Every fact carries its origin, permanently.** The Input Engine establishes the provenance envelope; every downstream engine preserves it.

### Every fact records

| Attribute | Meaning |
|---|---|
| **Source Type** | `Document` · `Human` · `Structured Metadata` |
| **Source ID** | Which source it came from |
| **Evidence Reference** | Where within that source |
| **Timestamp** | When it entered the system |
| **Confidence** | Extraction confidence for documents; **capture confidence** for provided sources |
| **Corroborated** | Whether another source supports it |

> **No engine may merge these origins into a single anonymous fact.**

### The three source types

| Source Type | Read or asserted | Examples |
|---|---|---|
| **Document** | Read off an artifact — **extracted** | Invoice fields, table rows, scanned values, handwriting |
| **Human** | Asserted by a person — **provided** | The optional Human Business Description |
| **Structured Metadata** | Supplied by a system — **provided** | Upload metadata, file attributes, source identifiers |

The dividing line is **extracted versus provided**. Something read off an artifact can be checked against that artifact. Something asserted cannot — it can only be corroborated by something else.

### A human note is evidence, not truth

> **The description may never be treated as confirmed fact.**

It may supply intent, explanation, business context or missing narrative. It must **never automatically override** documents, receipts, invoices, bank statements or any other evidence. Conflicts between a note and other evidence **remain visible** and are handled by later engines.

### Capture confidence is not truth confidence

```text
User typed:          "Advance paid to supplier."

Capture confidence:  100%       the system stored exactly what was typed
Truth confidence:    unknown    until supported by other evidence
```

> **Human notes contribute context, not certainty.**
>
> **A human note must never increase Evidence Reliability simply because it exists.**

It can improve understanding once **corroborated**; it can never independently raise confidence. The same holds for structured metadata — capturing a field perfectly says nothing about whether its content is correct.

### Corroboration

The **Corroborated** attribute is assessed by the **first engine able to assess it**, and recorded in **that engine's own artifact**.

The Input Engine records `Corroborated: not assessed`, honestly — establishing that *"advance paid to supplier"* and a document's payment field mean the same thing is **interpretation**, which Engine 1 is forbidden from performing. It is never written back into the Document Evidence Object, which is immutable and owned upstream (§6). In practice the Understanding Engine makes the assessment, in the Business Understanding Object.

### Provenance travels the whole pipeline

```text
Document Evidence Object → Business Understanding Object → Accounting Decision
    → Clarification Request → Validation Verdict → audit history
```

Complete provenance from input to execution. At every stage, for every fact, the system can answer: **where did this come from, how reliable was the capture, and does anything else support it?**

### What this protects

Without it, a claim and an observation become indistinguishable one stage after they enter.

- **A user's assertion could silently become a posted entry.** "Advance payment to supplier" is a claim; if it loses its origin it reads as an established fact by the time it reaches the Accounting Engine.
- **Corroboration could not be reasoned about.** An engine cannot ask "is this supported by anything else?" if it cannot tell how many independent sources a fact has.
- **The audit trail would end at the wrong place.** A trail that reaches "the system decided" and not "the user said, uncorroborated" cannot be defended.
