# Communication Rules — Accounting Engine, Internal

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> How the nine Accounting sub-engines communicate with one another.
>
> Companion to [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md). **Specification only — no implementation.**
>
> This document governs communication *inside* Engine 3. The boundary into it is governed by [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md).

---

# 1. Flow

```text
Business Understanding Object          Company information
        ↓                                      ↓
transaction_analyzer                  company_understanding
        ↓                                      ↓
Transaction Analysis Result            Company Context Result
        │                                      │  context, not decisions
        └──────────────┬───────────────────────┘
                       ↓
   ┌───────────────────┼───────────────────┐
   ↓                   ↓                   ↓
ledger_intelligence  tax_intelligence  accounting_rules
   ↓                   ↓                   ↓
Ledger              Tax Treatment      Accounting Rule
Recommendation      Recommendation     Application Result
   │                   │                   │  (incl. period treatment)
   └───────────────────┴───────────────────┘
                       ↓
        Accounting Treatment Result   ← assembled by the parent engine
                       ↓
              journal_intelligence
                       ↓
          Journal Entry Recommendation   guarantees Debit = Credit
                       ↓
                 risk_analysis      ← all accounting analysis outputs
                       ↓
                doubt_detection     ← all accounting outputs
                       ↓
                decision_output     ← all sub-engine outputs
                       ↓
                Accounting Decision
```

## Specialised decisions, then combination

Three sub-engines decide independently, and their outputs are **combined** — not authored — into the Accounting Treatment Result:

| Sub-engine | Owns the question | Produces |
|---|---|---|
| `ledger_intelligence` | *Where does this transaction go?* | Ledger Recommendation |
| `tax_intelligence` | *What tax treatment applies?* | Tax Treatment Recommendation |
| `accounting_rules` | *Which accounting rules and timing principles apply?* | Accounting Rule Application Result |
| `journal_intelligence` | *Is the final journal structurally correct?* | Journal Entry Recommendation |

```text
Accounting Treatment Result          ← internal to the engine
├── Ledger Recommendation                from ledger_intelligence
├── Tax Treatment Recommendation         from tax_intelligence
├── Accounting Period Treatment          from accounting_rules
├── Applied Accounting Rules             from accounting_rules
├── Supporting Evidence
├── Confidence
└── Reasoning
```

The flow is: **specialised decisions → combined accounting treatment → journal construction → validation.**

---

# 2. Communication Rules

---

## Rule 1 — Sub-engines communicate only through defined outputs

Each sub-engine publishes exactly one named Result, and that Result is the entirety of what siblings may see.

| Sub-engine | Publishes |
|---|---|
| `transaction_analyzer` | Transaction Analysis Result |
| `company_understanding` | Company Context Result |
| `accounting_rules` | Accounting Rule Application Result |
| `ledger_intelligence` | Ledger Recommendation |
| `tax_intelligence` | Tax Treatment Recommendation |
| `journal_intelligence` | Journal Entry Recommendation |
| `risk_analysis` | Accounting Risk Analysis |
| `doubt_detection` | Accounting Doubt Report |
| `decision_output` | Accounting Decision |

---

## Rule 2 — No hidden communication

No shared mutable state. No side channels. No implicit coupling through anything other than a published Result.

If a sub-engine needs something a sibling knows, that something must be part of the sibling's Result — which means it is named, traceable and challengeable. If it is not in the Result, it is not available, and the correct response is to record an unknown.

---

## Rule 3 — No sub-engine modifies another sub-engine's output

A Result is **read-only** to every sibling, permanently.

A sub-engine that believes a sibling's Result is wrong does not correct it. It records the disagreement in its own Result as a conflict, and `doubt_detection` carries it forward.

---

## Rule 4 — Confidence must travel with every output

Every Result carries confidence. No Result may omit it, and no Result may raise it.

> **Confidence is recalculated only when evidence changes** — [`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes). Never because a sub-engine reasoned harder.

A sub-engine consuming a sibling's Result inherits that Result's uncertainty. It cannot become more certain than what it consumed. **High confidence cannot exist when critical information is uncertain.**

---

## Rule 5 — Evidence references must be preserved

Every accounting conclusion points back through the Business Understanding Object to the evidence that produced it.

A conclusion with no evidence reference cannot appear in a Result. There is no mechanism for producing one, and that is deliberate: it is the structural reason this engine cannot invent facts.

**Assumptions travel the same way.** Every sub-engine relying on an assumption records it — what was assumed, and why. **Nothing may assume silently.**

---

## Rule 6 — `decision_output` assembles; it does not rewrite history

| `decision_output` CAN | `decision_output` CANNOT |
|---|---|
| Combine accounting outputs | Invent conclusions |
| Organize them | Remove uncertainty |
| Present the final reasoning | Override sub-engines |
| Set Decision Status | Alter, reconcile or soften any component |
| | Omit risks or doubts |
| | Bypass validation |

**`decision_output` creates the Accounting Decision. The Accounting Engine owns it.** It does not become an independent owner.

---

## Rule 7 — Conflicts remain visible

Where two Results disagree, the disagreement survives into the Accounting Decision. It is never resolved by preference, seniority of component, or convenience.

A decision carrying an unresolved conflict is a legitimate output. `doubt_detection` records it, `decision_output` may mark the decision `INCOMPLETE_INFORMATION_REQUIRED`, and the Clarification Engine is where it gets resolved — by new information, not by choosing.

---

# 3. Assembly Rules

## The parent assembles mechanically

> **The Accounting Engine parent assembles the Accounting Treatment Result mechanically. It does not author, modify, approve, or override the individual recommendations.**

| Parent **CAN** | Parent **CANNOT** |
|---|---|
| Combine outputs | Change the Ledger Recommendation |
| Organize outputs | Change the Tax Treatment Recommendation |
| Create the final structure | Remove uncertainty |
| | Increase confidence |

## No sub-engine creates another sub-engine's decision

`accounting_rules` does **not** produce the Ledger Recommendation or the Tax Treatment Recommendation — that would be fake ownership, a component publishing an artifact containing outputs it does not create.

**No hidden override. No circular reasoning.**

## Balance ≠ correctness

`journal_intelligence` guarantees **internal journal mathematical balance only** — debit = credit, and accounting-equation balance. It does **not** guarantee accounting correctness, tax correctness, or business correctness.

```text
Wrong ledger + balanced journal = still wrong
```

It combines approved components; it does not calculate tax, interpret tax, or select ledgers. Correctness is judged by the Validation Engine.

---

# 4. What These Rules Protect

Every rule above defends one property: **a conclusion in the Accounting Decision can be traced to the evidence and the rule that produced it, its assumptions are visible, and its confidence is no higher than what it rests on.**

Break any one and that property goes:

- Allow a side channel, and a conclusion appears with no basis.
- Allow a sub-engine to edit a sibling's Result, and the author of a decision is no longer knowable.
- Allow confidence to be raised, and the number stops meaning anything.
- Allow the parent to adjust what it assembles, and a tenth decision-maker exists that appears in no diagram.
- Allow a conflict to be resolved by preference, and a choice was made that nothing downstream can see.
- Allow an assumption to go unrecorded, and it becomes a confirmed fact by default.

None of these fail loudly. They all produce output that looks better than the honest version — which is exactly why they are prohibitions rather than guidance.

---

## Related documents

- [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) — the Accounting Engine specification.
- [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — the inbound boundary contract.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, IDENTITY ≠ INTELLIGENCE.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
