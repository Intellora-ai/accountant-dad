# Communication Rules — Accounting Engine

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> How the Accounting Engine communicates with the Clarification Engine and the Validation Engine.
>
> Companion to [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md). **Specification only — no implementation.**
>
> **The sending engine owns the contract of what leaves it.** This document is owned by the **Accounting Engine**. It defines **two separate boundaries** — one contract each, no overlap between them. The receiving engines reference it; they do not restate it.

---

# 1. Two Outbound Boundaries

```text
                    Accounting Decision
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     Clarification Engine          Validation Engine
      (detect uncertainty)        (judge safety)
```

The **same artifact** crosses both boundaries, for different purposes. It is not copied, forked or altered — both engines read the same immutable Accounting Decision.

Communication *inside* Engine 3 is governed separately by [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).

---

# 2. Boundary Contract — Accounting → Clarification

All nine items, per [`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement):

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Business Understanding Object + company information. |
| 2 | **Output artifact** | **Accounting Decision** — with accounting assumptions, risk indicators, decision confidence, supporting reasoning and unresolved doubts. |
| 3 | **Artifact creator** | `decision_output`. |
| 4 | **Artifact owner** | The **Accounting Engine**, permanently. `decision_output` does not become an independent owner. |
| 5 | **Allowed transformation** | The Clarification Engine may **read**, **analyze** and **reference** it — identify blockers, detect conflicts, request information — and produce its own artifact, the Clarification Request. |
| 6 | **Forbidden transformation** | It may **not** change the accounting treatment, rewrite the decision, modify, delete, remove uncertainty from, or change confidence in the Accounting Decision. Artifacts are immutable after creation. |
| 7 | **Decision authority** | Accounting decides accounting treatment, ledger mapping, debit/credit structure, journal design and tax interpretation. Clarification decides whether clarification is needed, what is missing, what should be asked, and clarification status. **A question is not a decision.** |
| 8 | **Uncertainty movement** | Accounting assumptions, risk indicators, unresolved doubts and decision confidence all cross intact. **Clarification Confidence may never exceed Decision Confidence.** Uncertainty is only ever described more precisely, never removed. |
| 9 | **Failure movement** | An Accounting Decision marked `INCOMPLETE_INFORMATION_REQUIRED` crosses **as a decision**, not as an error — its named required clarification is exactly what Engine 4 exists to formalise. New information never returns along this arrow; it re-enters through Engine 1/2/3 as a new artifact version. |

## Sender ownership · receiver responsibility

**Sender ownership.** The Accounting Engine defines what the Accounting Decision asserts — its meaning, integrity and versioning. Only it may create a new version.

**Receiver responsibility.** The Clarification Engine must preserve evidence references, reasoning, assumptions, confidence, uncertainty and traceability; must never modify previous artifacts, hide conflicts, remove assumptions, increase confidence without new evidence, or create accounting decisions.

---

# 3. Boundary Contract — Accounting → Validation

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Business Understanding Object + company information. |
| 2 | **Output artifact** | **Accounting Decision** — the primary artifact to validate. |
| 3 | **Artifact creator** | `decision_output`. |
| 4 | **Artifact owner** | The **Accounting Engine**, permanently. |
| 5 | **Allowed transformation** | The Validation Engine may **read**, **analyze** and **reference** it, and produce its own artifact — the verdict. |
| 6 | **Forbidden transformation** | It may **not** amend, correct or repair the decision. A defect is **reported**, never fixed. It may not recompute ledgers, entries or tax. |
| 7 | **Decision authority** | Accounting decides treatment. Validation decides accept, reject or request correction. **Validation never creates accounting decisions; Accounting never approves its own.** |
| 8 | **Uncertainty movement** | Assumptions, risks, doubts and Decision Confidence cross intact. Validation Confidence may never exceed Decision Confidence. |
| 9 | **Failure movement** | A rejection returns to the **named** stage that must handle it — it never moves forward and is never silently dropped ([`DATA_FLOW.md` §4.4](DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on)). |

## Validation receives two artifacts

Validation cannot validate a Clarification Request alone — it must validate the decision itself.

```text
Accounting Decision ──────────────────► VALIDATION   primary artifact
Clarification Request ────────────────► VALIDATION   supplementary
```

The Clarification Request tells Validation **whether unresolved uncertainty exists**. It is supplementary, never a replacement. Each artifact travels under its own contract, from its own owner — the Accounting Decision under this document, the Clarification Request under the Clarification Engine's outbound contract, authored when Engine 5 is specified.

---

# 4. What Is Sent

Both boundaries carry the same immutable artifact:

```text
Accounting Decision
├── Decision ID · Decision Status
├── Accounting treatment · Ledger classification
├── Debit entries · Credit entries · Journal structure
├── Tax treatment
├── Accounting assumptions
├── Risk indicators · Decision confidence
├── Supporting reasoning
└── Unresolved doubts
```

Full structure: [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md` §5](ENGINE_3_ACCOUNTING_ENGINE_RULES.md#5-output-contract).

## Decision Status crosses first

`COMPLETE` or `INCOMPLETE_INFORMATION_REQUIRED` exists so a receiving engine can ask *can this move forward?* and get a structured answer rather than infer one from prose. Neither receiver may override it.

---

# 5. Assumptions and Doubts Cross Intact

The Accounting Engine records every assumption it relied on and every doubt it could not resolve. Both cross both boundaries unaltered.

Neither receiver may:

- Remove an assumption because it looks safe.
- Drop a doubt because the decision reads complete without it.
- Treat an assumption as a confirmed fact.

**An unrecorded assumption becomes a confirmed fact by default** — which is exactly why they are written down, and exactly why nothing downstream may unwrite them.

---

# 6. Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

If the Clarification Engine believes the treatment is wrong, it records that as a conflict in **its own** artifact. If the Validation Engine believes it is wrong, it records that as a finding in **its own** verdict. Neither edits the decision to match.

---

# 7. What These Boundaries Protect

> **Accounting Engine decides treatment. Clarification Engine detects what blocks it. Validation Engine decides safety.**

Three separations hold here at once:

- **A decision reviewed by its own author is not reviewed.** Validation is a separate engine precisely so it can reject.
- **An engine that could both decide and ask would always prefer to guess**, because guessing is cheaper. Doubt is produced by Accounting but *acted on* by an engine with no authority to answer.
- **The same artifact reaching two engines keeps them honest.** Clarification and Validation see identical input, so a disagreement between them is visible rather than absorbed.

---

## Related documents

- [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) — the sending engine's specification.
- [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) — the first receiving engine's specification.
- [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md) — communication inside Engine 3.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, versioning, boundary contract requirement.
