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
| 2 | **Understanding** → **Accounting** | **Transaction Story** | What happened, in business terms only: parties and roles, items, money movement, dates, business context. Every fact traced to its source; every gap explicitly marked absent. No accounting vocabulary. |
| 3 | **Accounting** → **Clarification** *or* **Validation** | **Accounting Decision** | Ledger selection, the balanced journal entry, tax treatment, the reasoning behind each, the risk profile of the decision, and the unresolved doubts. |
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
                       Transaction Story
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
3. **No reaching back.** An engine consumes only the artifact handed to it. The Accounting Engine reasons from the Transaction Story, never from the Document Evidence Object or the raw artifact. The Tally Engine acts on the Approved Decision, never on the story.
4. **No reaching sideways.** No engine writes into another engine's output. Every artifact has exactly one producing engine.
5. **Doubt travels.** Doubts, risks and low-confidence markers are carried forward with the artifact at every stage. They are never dropped because a later stage found them inconvenient.
6. **Gaps stay gaps.** A fact that is absent is marked absent and remains absent until a human supplies it. No stage fills a gap by inference, default or convention.
7. **Approval precedes execution.** Nothing reaches Tally that the Validation Engine has not approved.
8. **Every attempt is recorded.** Posting attempts, successes, partials and failures are all written to the audit record. Failure is not less loggable than success.
