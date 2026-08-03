# Application Layer — Engine Interface Contracts

> **Precedence level 3.** Consolidates what the ten locked communication documents already specify. **Nothing here is new.** Where this and a locked document differ, the locked document wins.
>
> One row per boundary. Every arrow carries exactly one named artifact.

---

## The shape every contract takes

```text
Application Layer  ──[ input artifact ]──►  Engine
Engine             ──[ output artifact ]─►  Application Layer
```

**Never engine-to-engine** (AL-INV-5). Every artifact passes through the Application Layer, which reads it only to route it — never to form an opinion about its content.

---

## Engine 1 — Input

| | |
|---|---|
| **Input artifact** | Raw document(s) · Transaction ID · optional human business context |
| **Output artifact** | **Document Evidence Object** — one per document |
| **Creator / owner** | Engine 1 |
| **Guarantees given** | Every fact carries six provenance attributes · a document that cannot be read produces an object recording that failure, never a fabricated one |
| **Preconditions** | Transaction ID exists · at least one document supplied |
| **Postconditions** | One Document Evidence Object per input document · every one carries the same Transaction ID |
| **Failure conditions** | **Business** — unreadable, corrupt, zero-byte: an object is produced recording the failure. **Runtime** — engine crash: nothing produced, Application Layer restarts |
| **Application Layer must not** | Interpret the document · pre-classify it · decide it is "obviously" an invoice |

---

## Engine 2 — Understanding

| | |
|---|---|
| **Input artifact** | **Every** Document Evidence Object sharing the Transaction ID |
| **Output artifact** | **Business Understanding Object** — exactly one |
| **Creator / owner** | Engine 2 |
| **Guarantees given** | Many documents may contribute to one business event; Engine 2 owns that aggregation · contradictions travel unresolved rather than being silently reconciled |
| **Preconditions** | Every Document Evidence Object for the transaction is present |
| **Postconditions** | Exactly one Business Understanding Object · same Transaction ID |
| **Failure conditions** | **Business** — missing facts, contradictions: recorded inside the object. **Runtime** — crash: nothing produced |
| **Application Layer must not** | Start Engine 2 before every Document Evidence Object exists · split one transaction across two Business Understanding Objects |

> **Extraction is document-centric. Understanding is transaction-centric.** Four artifacts, one business event.

---

## Engine 3 — Accounting

| | |
|---|---|
| **Input artifact** | **Business Understanding Object** |
| **Output artifact** | **Accounting Decision** |
| **Creator / owner** | Engine 3 |
| **Guarantees given** | Doubts are named missing facts whose absence would change the treatment · confidence changes only when evidence changes, never because the engine reasoned harder |
| **Preconditions** | Business Understanding Object present |
| **Postconditions** | One Accounting Decision · a **new version** on every re-decision, never an edit |
| **Failure conditions** | **Business** — blocking doubt: the decision carries it and routes to Clarification. **Runtime** — crash: nothing produced |
| **Application Layer must not** | Supply a hint · re-run hoping for higher confidence (AL-INV-12) · choose between two decisions |

---

## Engine 4 — Clarification

| | |
|---|---|
| **Input artifact** | **Accounting Decision** carrying a blocking doubt |
| **Output artifact** | **Clarification Request**, then a resolution |
| **Creator / owner** | Engine 4 |
| **Guarantees given** | Engine 4 judges which doubts block · a resolved clarification returns to Engine 3, which issues a **new decision version** |
| **Preconditions** | An Accounting Decision exists carrying at least one blocking doubt |
| **Postconditions** | A Clarification Request exists · after a human answers, control returns to Engine 3 |
| **Failure conditions** | **Business** — unanswerable: recorded, transaction cannot proceed to Validation. **Runtime** — crash: nothing produced |
| **Application Layer must not** | Answer a clarification · decide which doubts block · route a resolved clarification straight to Validation. **Engine 3 must re-decide first** |

**Clarification Status belongs to Engine 4. Transaction state belongs here.** Never merged, never inferred from one another.

---

## Engine 5 — Validation

| | |
|---|---|
| **Input artifact** | **Accounting Decision** |
| **Output artifact** | **Validation Decision** — exactly one of four statuses |
| **Creator / owner** | Engine 5 |
| **Guarantees given** | Only `data_validation` short-circuits; the other four validators always run · validation only validates — a defect is reported, never fixed |
| **Preconditions** | Accounting Decision present, with no unresolved blocking clarification |
| **Postconditions** | One Validation Decision · status determines the next transition |
| **Failure conditions** | **Business** — any of the four statuses. **Runtime** — crash: nothing produced |
| **Application Layer must not** | Override a status · re-run after `Rejected` · treat `Approved With Warning` as `Approved` |

### The four statuses and where each goes

| Status | Engine 6 receives | Transition |
|---|---|---|
| **Approved** | Validation Decision + Accounting Decision | → `Execution` |
| **Approved With Warning** | **Nothing until released** | → `WaitingForApproval` ⚠️ *Amendment 2* |
| **Clarification Required** | Nothing | → `Clarification`, then Engine 3 issues a **new version**, then **Validation runs again** |
| **Rejected** | Nothing | → `Failed`. Execution **prohibited** |

---

## Engine 6 — Execution

| | |
|---|---|
| **Input artifact** | **Accounting Decision** + **Validation Decision** (`Approved`, or `Approved With Warning` **after release**) |
| **Output artifact** | **Execution Result** |
| **Creator / owner** | Engine 6 |
| **Guarantees given** | Exactly once per **Decision ID + Decision Version + Destination System** · execution is transport, not reasoning · a correction is a new Execution Result pointing at the original via `Corrects Execution Result` |
| **Preconditions** | A released, approved Validation Decision exists |
| **Postconditions** | One Execution Result · the original is never edited |
| **Failure conditions** | **Business** — transport failure: recorded in the Execution Result; `posting_manager` reposts. **Runtime** — crash: nothing produced, **Application Layer restarts** |
| **Application Layer must not** | Re-post a voucher (`retry_engine()` always rejects Engine 6) · send work backwards from Execution · let Engine 6 learn a gate existed |

### No backward arrow

```text
error_handler NAMES the responsible stage inside the Classified Error.
The Application Layer READS it and routes.
The last engine in the pipeline never moves work itself.
```

---

## Contract summary

| Boundary | In | Out | Owner |
|---|---|---|---|
| AL → E1 | documents | Document Evidence Object | E1 |
| AL → E2 | Document Evidence Object(s) | Business Understanding Object | E2 |
| AL → E3 | Business Understanding Object | Accounting Decision | E3 |
| AL → E4 | Accounting Decision | Clarification Request | E4 |
| AL → E5 | Accounting Decision | Validation Decision | E5 |
| AL → E6 | Accounting Decision + Validation Decision | Execution Result | E6 |

**Six artifacts. Six owners. The Application Layer owns none of them** (INV-4).

---

## What every contract shares

```text
The Application Layer supplies the input artifact and nothing else.
No hints. No pre-classification. No opinion about content.

The engine returns its artifact or nothing.
A crash produces NOTHING — never a partial artifact.

Artifacts are immutable. Correction is a new version by the owning engine.

The Transaction ID is on every artifact and is never changed.

Every engine may consult the Brain. The Brain is advisory and may be
ignored, with the engine recording why. The Application Layer never
consults the Brain.
```
