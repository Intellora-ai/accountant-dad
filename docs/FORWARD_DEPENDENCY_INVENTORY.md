# Forward Dependency Inventory

> **Precedence level 2.** Required by [`SYSTEM_INVARIANTS.md` INV-1](SYSTEM_INVARIANTS.md#inv-1--locks-win).
>
> **Before any engine is locked**, this document lists every promise previous engines already made about it. **Conflicts are resolved before the specification is written, never during propagation.**

---

## How to use this document

1. Before locking Engine *N*, read its section below.
2. Every listed commitment is either **honoured** by the new specification, or **explicitly revised** with the contradiction named.
3. A commitment that is neither honoured nor revised is a defect, not a choice.
4. After the lock, move resolved rows to **Settled** with the outcome recorded.

---

# Engine 5 — Validation Engine

> **Locked.** [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md). Every row below is honoured, added or explicitly revised by that specification.

## Commitments made by Engines 1–4

| # | Commitment | Made in | Status |
|---|---|---|---|
| 1 | **Validation Confidence** exists as a named confidence layer | 7 places across locked docs | Honoured |
| 2 | Validation receives **both** the Accounting Decision and the Clarification Request | Engine 3 §11, Engine 4 §13 | Honoured |
| 3 | `risk_assessment` owns the name **Risk Assessment** — Accounting deliberately uses *Accounting Risk Analysis* to avoid collision | Engine 3 §8.7, Ownership Collisions | Honoured |
| 4 | Validation judges whether the entry **balances** — *"Balance ≠ correctness"* delegates the check here | Engine 3 §8.6 | Honoured |
| 5 | A rejection **names the stage responsible** | `DATA_FLOW` §4.4 routing table | Honoured — strengthened to *responsible engine* on **every** finding |
| 6 | Validation **cannot amend or repair** — a defect is reported, never fixed | Engine 3, `SYSTEM_BOUNDARIES` §5 | Honoured |
| 7 | Validation **cannot ask the user** — a case needing questions returns to Clarification | `SYSTEM_BOUNDARIES` §5 | Honoured |
| 8 | Validation **cannot approve with an unresolved finding** | `SYSTEM_BOUNDARIES` §5 | Honoured |
| 9 | The **closed-period gate** belongs to Validation — execution must never discover posting was impossible | INV-8 | **Added** — owned by `data_validation` |
| 10 | **Economic** duplicate judgement belongs to Validation; **identity** screening to Input | INV-7 | **Added** — `duplicate_detection` owns the judgement |
| 11 | Every artifact carries a **Transaction ID** | INV-3 | **Added** — carried by the Validation Decision |

## Conflicts resolved before locking

| Conflict | Locked position | Resolution |
|---|---|---|
| **Artifact name** — `Validation Verdict` (10 occurrences, 8 files) vs `Validation Decision` | Verdict | **Renamed to `Validation Decision`.** Engine 5 was unlocked, so no name was final; deferred conflict now settled. |
| **Third status** — locked `flag for human attention` vs proposed `Clarification Required` | Flag | **Both retained.** Four statuses: Approved · **Approved With Warning** · Clarification Required · Rejected. *Correct but needs a human* and *incorrect until more information* are different outcomes; `risk_assessment` requires the first as an output path. |
| **Internal flow** — locked parallel (*"the verdicts and findings of all five preceding validators"*) vs proposed strict chain | Parallel | **Only `data_validation` short-circuits.** The other four always run, so a transaction with an accounting error *and* a tax error reports both. Preserves *"every failed validation rule remains visible."* |
| **Confidence wording** — *"Validation never increases certainty"* | INV-2 | **INV-2 governs.** Directional wording replaced by recalculation. |

---

# Engine 6 — Execution Engine

## Commitments made by Engines 1–5

| # | Commitment | Made in | Status |
|---|---|---|---|
| 1 | Execution begins **only** on an approved Validation Decision | `DATA_FLOW` §5 rule 7, Engine 5 | Honoured |
| 2 | Execution **cannot reason, interpret or judge** the transaction | `SYSTEM_BOUNDARIES` §6 | Honoured |
| 3 | Execution **cannot supply a missing value** — missing data is an error, not a gap to fill | `SYSTEM_BOUNDARIES` §6 | Honoured |
| 4 | Execution **cannot correct a rejected voucher and resubmit** | `SYSTEM_BOUNDARIES` §6 | Honoured |
| 5 | Audit records are **append-only**; failures are as loggable as success | `SYSTEM_BOUNDARIES` §6, INV-13 uncertainty rules | Honoured |
| 6 | `posting_manager` guarantees **at most one post** per approved decision | Engine 6 sub-engine locks | Honoured — restated as idempotency |
| 7 | `response_processor` **never reads an ambiguous or absent response as success** | Engine 6 sub-engine locks | Honoured |
| 8 | `error_handler` classifies and routes; **never retries directly** | Engine 6 sub-engine locks | Honoured |
| 9 | A correction is a **new Accounting Decision under the same Transaction ID** — execution never edits history | INV-5 | **Added** |

## Conflicts resolved before locking

| Conflict | Locked position | Resolution |
|---|---|---|
| **Artifact name** — `Posting Result` (12 occurrences, 9 files) vs `Execution Result` | Posting Result | **Renamed to `Execution Result`.** Engine 6 was unlocked; no name was final. |
| **`tally_connector` name vs role** — now all external systems, not only Tally | Name locked | **Name unchanged, responsibility expanded.** Recorded as a name-and-responsibility case, as with Engine 4's three. Identities are stable; responsibilities are not. |
| **New responsibilities** — queue, notification, retry ownership | Not previously assigned | Assigned to existing sub-engines: `posting_manager` owns queue and retry coordination; `error_handler` owns notification triggers. **No sub-engine added.** |
| **Flow diagram** — `audit_logger` shown last, but receives *all* execution events | — | **Both true.** It observes throughout; it is last only in assembly order. |
| **Destination scope** — Zoho, Busy, SAP, QuickBooks, portals, exports, messaging | Tally only | `voucher_translator` is **destination-parametric**, not Tally-shaped. |

---

# Unsettled — carried forward

| Item | Status |
|---|---|
| **Human Business Context** — locked *inside* the Document Evidence Object as evidence (`6416be4`); a later direction proposed a separate artifact for operational context | **Open.** Recommendation: keep the lock, add a separate **Human Instruction** artifact owned by the Application Layer, on the **observation versus instruction** distinction — *"Bought laptops for the design team"* is evidence; *"Post this tomorrow"* is an instruction. Never binding on any engine. |
| **Reality Probe** — INV-13 requires measurement before commitment | **Deferred by decision.** Engine 5's tax validation categories and Engine 6's external-system boundary are specified from first principles rather than measurement. Recorded as a known shallow spot. |
| **39 sub-engine count** — fixed in Phase 1 before any engine was specified | **Open.** Engine 4 already needed different components and received a name-and-responsibility remapping instead. No engine's count has been tested against its real needs. |

---

# Settled

| Item | Outcome | Settled at |
|---|---|---|
| `Accounting Decision` name | Confirmed final, not renamed to *Accounting Decision Object* | Engine 3 lock |
| `Structured Document` + `Confidence Report` as artifact name | Superseded by **Document Evidence Object**; both survive as components | Engine 1 lock |
| `Transaction Story` as artifact name | Superseded by **Business Understanding Object**; survives as its narrative component | Engine 2 lock |
| `src/brain/` role | Defined as the **Knowledge Brain** | Engine 4 lock |
| Clarification lifecycle states | `Created/Waiting/Information Received/Obsolete/Closed` → **`Open/Answered/Superseded/Cancelled/Resolved`** | Phase 0 |
| `Validation Verdict` as artifact name | Superseded by **Validation Decision**; the old name survives nowhere | Engine 5 lock |
| Validation statuses | `approve / reject / flag` → **`Approved` · `Approved With Warning` · `Clarification Required` · `Rejected`** | Engine 5 lock |
| Validation internal flow | `data_validation` gates; the other four validators always run | Engine 5 lock |
