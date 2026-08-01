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
| 1 | **Input** → **Understanding** | **Document Evidence Object** | Document ID · source references · the **Structured Document** (extracted text, detected fields, document structure, tables, field values, field locations) · the **Confidence Report** (confidence scores, uncertainty markers, reliability information, risky fields). |
| 2 | **Understanding** → **Accounting** | **Business Understanding Object** | The **Transaction Story** (the assembled narrative) · **Supporting Understanding Data** (the six sub-engine Results) · **Identified Unknowns** · **Confidence Assessment**. What happened, in business terms only. Every fact traced to its evidence; every gap named; every conflict preserved. No accounting vocabulary. |
| 3 | **Accounting** → **Clarification** *or* **Validation** | **Accounting Decision** | Decision ID · **Decision Status** · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts. |
| 4a | **Clarification** → *human* | **Question Set** | The minimal set of questions, what each resolves, and the form of answer expected. |
| 4b | *human* → **Clarification** | **Answers** | The human's replies, as given. |
| 4c | **Clarification** → **Accounting** | **Resolved Facts** | The answers as structured facts, attributed to the question each answers. |
| 4d | **Accounting** → **Validation** | **Updated Accounting Decision** | The decision remade under the Accounting Engine's authority, with a record of what changed and which answer caused it. |
| 4e | **Clarification** → *pipeline* | **Clarification Outcome** | Whether questioning is complete, why, and any uncertainty left unresolved. |
| 5 | **Validation** → **Tally** *or* back | **Validation Verdict** | Approve, reject, or flag — with every finding that drove it and, for a rejection, the stage responsible. |
| 6 | **Validation** → **Tally** | **Approved Accounting Decision** | The decision, and the verdict approving it. Nothing unapproved crosses this arrow. |
| 7 | **Tally** → *external* | **Posting Result** + **Audit Record** | Posted, rejected or partial, with Tally's identifiers; and the permanent, append-only record of the attempt. |

### 2.1 Document Evidence Object

The Input Engine's output has one name. `Structured Document` and `Confidence Report` are its two **components**, never the name of the artifact itself. No engine may create an alternative name, and no duplicate representation may exist.

```text
Document Evidence Object
├── Document ID
├── Source references
├── Structured Document ── extracted text · detected fields · document structure ·
│                          tables · field values · field locations
└── Confidence Report ──── confidence scores · uncertainty markers ·
                           reliability information · risky fields
```

A downstream engine that consumes one part names that part — *"the Confidence Report within the Document Evidence Object"* — and never treats it as a separate artifact on its own arrow.

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
        ┌──────►│   ACCOUNTING ENGINE      │
        │       └──────────────────────────┘
        │                      │
        │          Accounting Decision (+ doubts, + risk)
        │                      │
        │                      ▼
        │            ╔═══════════════════╗
        │            ║ material doubts?  ║
        │            ╚═══════════════════╝
        │               │             │
        │           yes │             │ no
        │               ▼             │
        │    ┌────────────────────┐   │
        │    │  CLARIFICATION     │   │
        │    │                    │   │
        │    │   ──► human        │   │
        │    │   ◄── answers      │   │
        │    └────────────────────┘   │
        │               │             │
        └───────────────┘             │
           Resolved Facts             │
       (decision is remade)           │
                                      │
                                      ▼
                         ┌────────────────────┐
                         │ VALIDATION ENGINE  │
                         └────────────────────┘
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

Clarification runs **only when the Clarification Engine's `uncertainty_detection` judges an uncertainty material enough to block posting.** When it does not, the Accounting Decision goes directly to Validation.

The condition is not "the Accounting Engine raised a doubt." The Accounting Engine's `doubt_detection` produces doubt; whether that doubt is *material* is judged separately and later. A decision may carry recorded doubts and still proceed, provided none of them blocks posting — and the doubts travel with it either way.

### 4.2 Clarification loops, then terminates

Within Clarification, question → answer → update may repeat. The loop is ended by `stop_decision`, which concludes on one of three grounds: clarity is now sufficient; further questions would not change the decision; or the human cannot supply what is needed.

`stop_decision` never concludes that the decision is *correct*. It concludes only that **questioning is complete.** Any uncertainty still unresolved at that point is carried forward openly in the Clarification Outcome, not suppressed.

### 4.3 A clarified decision is remade, not edited

When answers arrive, `decision_updater` does not patch the decision. It returns **Resolved Facts** to the Accounting Engine, which remakes the decision under its own rules. The record of what changed, and which answer caused it, travels with the Updated Accounting Decision.

This is why the arrow from Clarification points **back to Accounting**, not forward to Validation.

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

1. **One direction.** Work moves forward only. The single backward path in the system is a *return* — Validation returning a rejection to a named stage, or Clarification returning Resolved Facts to Accounting. A return is always explicit and always names its target.
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

This generalises a commitment the system already had: `decision_updater` returns **Resolved Facts** to the Accounting Engine, which *remakes* the decision — it never patches it in place (§4.3).

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
| Accounting → Clarification | — | Placeholder until Engine 4 |
| Accounting → Validation | — | Placeholder until Engine 5 |

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
