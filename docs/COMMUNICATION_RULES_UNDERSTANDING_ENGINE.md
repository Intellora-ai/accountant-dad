# Communication Rules — Understanding Engine

> How the Understanding Engine communicates with the Accounting Engine.
>
> Companion to [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md). **Specification only — no implementation.**
>
> **The sending engine owns the contract of what leaves it.** This document is owned by the **Understanding Engine**. The Accounting Engine references it; it does not restate or duplicate it. One contract per boundary — see [`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement).

---

# 1. The Only Path

```text
Understanding Engine
        ↓
Business Understanding Object
        ↓
Accounting Engine
```

The Understanding Engine's sole outbound artifact is the Business Understanding Object, and its sole recipient is the Accounting Engine. It does not communicate with the Clarification, Validation or Tally Engines, and it does not communicate with the user.

Communication *inside* Engine 2 is governed separately by [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).

---

# 2. Boundary Contract

All nine items, per [`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement):

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Document Evidence Object, from the Input Engine. |
| 2 | **Output artifact** | **Business Understanding Object.** |
| 3 | **Artifact creator** | `story_builder`. |
| 4 | **Artifact owner** | The **Understanding Engine**, permanently. `story_builder` does not become an independent owner. |
| 5 | **Allowed transformation** | The Accounting Engine may **read**, **analyze** and **reference** it — it may interpret the business story and apply accounting reasoning — and produce its own artifact, the Accounting Decision. |
| 6 | **Forbidden transformation** | It may **not** change the story, remove unknowns, edit evidence, modify, rewrite, delete, remove uncertainty from, or change confidence in the Business Understanding Object. Artifacts are immutable after creation. |
| 7 | **Decision authority** | Understanding decides business event interpretation, entity relationships and the business story. Accounting decides accounting treatment, ledger mapping, debit/credit structure, journal design and tax interpretation. Neither may make the other's decision. |
| 8 | **Uncertainty movement** | The Transaction Story, Supporting Understanding Data, **Identified Unknowns** and **Confidence Assessment** all cross intact. Decision confidence may never exceed what the understanding supports — confidence can only decrease downstream unless new evidence is introduced. Uncertainty is only ever described more precisely, never removed. |
| 9 | **Failure movement** | The Understanding Engine does not halt the pipeline. Gaps, conflicts and low confidence cross the boundary **as named unknowns and preserved conflicts**, not as errors. A Validation finding that a business fact is wrong or contradictory returns to **Understanding**; one a human could resolve returns to **Clarification** ([`DATA_FLOW.md` §4.4](DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on)). |

## Sender ownership · receiver responsibility

**Sender ownership.** The Understanding Engine defines what the Business Understanding Object asserts — its meaning, its integrity, its versioning. Only it may create a new version.

**Receiver responsibility.** The Accounting Engine must preserve evidence references, preserve uncertainty, preserve unknown information, never modify the artifact, and **never convert assumptions into facts**.

---

# 3. What Is Sent

The Business Understanding Object carries:

```text
Business Understanding Object
├── Transaction Story ................. the assembled narrative of what happened
├── Supporting Understanding Data ..... the six sub-engine Results
├── Identified Unknowns ............... every gap, named
└── Confidence Assessment ............. evidence · understanding · missing
                                        information · detected conflicts
```

Full structure: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §5](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#5-output-contract).

---

# 4. Facts, Not Accounting Conclusions

**The Understanding Engine sends facts. It never sends accounting conclusions.**

**✗ Never sent**

> "Fixed asset purchase."

**✓ What is actually sent**

> Item description: `Laptop` · vendor: `ABC Traders` · amount: `50,000` · dated `1 August`.

The first asserts a treatment — asset versus expense, capital versus revenue. That is the Accounting Engine's to decide, and it may legitimately decide differently at different companies. The second states only what was understood to have happened.

### The test

If a sentence could be **wrong about the accounting** rather than **wrong about the business**, it is a conclusion and does not belong in the Business Understanding Object.

| Business fact ✓ | Accounting conclusion ✗ |
|---|---|
| "Goods were supplied on credit terms of 30 days." | "This is a trade payable." |
| "Item description reads *Laptop*." | "This is a fixed asset." |
| "Tax amount of ₹9,000 is stated separately on the document." | "Input tax credit of ₹9,000 is available." |
| "Invoice is dated 31 March; payment is dated 10 April." | "This belongs to the March period." |

The last pair matters most. `timeline_understanding` states *when things happened*; `accounting_rules` decides *which period they belong to*. Those are different questions and different engines.

---

# 5. Conflicts and Unknowns Cross Intact

The Understanding Engine preserves conflicts rather than resolving them, and names its gaps rather than filling them. Both cross this boundary unchanged.

```text
Known:       Two amounts exist.
Conflict:    Amount mismatch detected.
Status:      Unresolved.
Confidence:  Reduced.
```

The Accounting Engine **may not** resolve that conflict on the Understanding Engine's behalf. It may reason about it, record a doubt about it, and mark its own decision `INCOMPLETE_INFORMATION_REQUIRED` — but the conflict itself belongs to the Understanding Engine and is settled only by new information arriving through Clarification.

---

# 6. Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

If the Accounting Engine believes the business story is wrong, it records that judgement in **its own** output — as a doubt, a risk, or an incomplete decision. It never amends the story to match.

---

# 7. What This Boundary Protects

> **Understanding Engine creates interpretation. Accounting Engine decides treatment.**

If understanding were permitted to send accounting conclusions, three things would break at once:

- **The same understanding could not serve two companies.** A laptop is an expense at one and inventory at another; deciding upstream forecloses that permanently.
- **Errors would become untraceable.** A wrong conclusion looks identical to a correct one downstream; a wrong *fact* can be checked against the evidence.
- **Reasoning would happen twice, differently.** Two engines interpreting the same transaction would eventually disagree, and nothing in the system could say which was right.

---

## Related documents

- [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — the sending engine's specification.
- [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) — the receiving engine's specification.
- [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) — communication inside Engine 2.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, boundary contract requirement.
