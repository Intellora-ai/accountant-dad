# Engine 3 — Accounting Engine: Specification Lock

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> **Status: LOCKED.** This is the permanent engineering specification for the Accounting Engine. Future implementation must follow it.
>
> **Specification only — no implementation.** No code, no libraries, no accounting logic, no tax engines, no Tally connection, no databases, no AI models, no dependencies.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map of all 39 sub-engines. **This document is the deeper authority for Accounting Engine specifics.** Where they overlap they must agree; a disagreement is a defect to be fixed, not a choice to be made.

---

# 1. Engine Identity

## Engine Name

**Accounting Engine**

## Core Role

The Accounting Engine is the **reasoning layer** of the AI Accountant.

> Convert business understanding into an accounting decision, preserving uncertainty, assumptions and reasoning traceability.

### The question it answers

> **"Given what happened in the business, how should this be represented according to accounting rules?"**

### The questions it does not answer

| Question | Owner |
|---|---|
| ~~What information exists?~~ | Engine 1 — Input |
| ~~What happened in the business?~~ | Engine 2 — Understanding |
| ~~Is this safe to execute?~~ | Engine 5 — Validation |

### What it decides

Accounting treatment · ledger classification · journal structure · tax treatment recommendation · accounting risks and doubts.

---

# 2. Mission

**The Accounting Engine converts the Business Understanding Object into a structured accounting decision while preserving uncertainty, assumptions, and reasoning traceability.**

Facts can be verified against evidence. **Judgements must be justified.** This engine is where judgement lives, which is why every output it produces must carry the reasoning that led to it, the assumptions it rested on, and the doubt it could not remove.

---

# 3. Responsibility

## The Accounting Engine owns

- Transaction accounting interpretation.
- Ledger decision.
- Debit/credit reasoning.
- Journal entry design.
- Tax treatment analysis.
- **Accounting period treatment.**
- Accounting risk identification.
- Decision confidence.

## The Accounting Engine does NOT own

- Document reading.
- Business event discovery.
- Asking users questions.
- Posting to Tally.
- Changing evidence.
- Changing business understanding.

---

# 3A. Decision Authority

> **The Accounting Engine controls only accounting decisions.**
>
> **No engine outside the Accounting Engine can modify its decisions.**

## What it can and cannot decide

| Can decide | Cannot decide |
|---|---|
| Accounting treatment | Whether the document information is correct |
| Ledger mapping | Whether the business story is correct |
| Debit/credit structure | Whether the user intended something different |
| Journal entry design | Validation approval |
| Tax interpretation | Execution |

The three on the right belong **upstream**. The two below them belong downstream.

## Internal authority

| Component | Authority |
|---|---|
| **`transaction_analyzer`** | Understand accounting-relevant transaction facts |
| **`company_understanding`** | Provide company context |
| **`ledger_intelligence`** | Ledger classification |
| **`tax_intelligence`** | Tax treatment reasoning |
| **`accounting_rules`** | Accounting rule application + period treatment |
| **`journal_intelligence`** | Journal structure + balance |
| **`risk_analysis`** | Identify accounting risks |
| **`doubt_detection`** | Identify uncertainty |
| **`decision_output`** | Assemble final Accounting Decision |
| **Accounting Engine parent** | **Own final artifact** |

> **`decision_output` creates the artifact. The parent owns it. These are different.**

## The parent does NOT

- Orchestrate the entire system.
- Route workflows.
- Perform business reasoning.
- **Override sub-engine outputs.**

## No sub-engine creates another sub-engine's decision

No hidden override. No circular reasoning. Each Result stands as its author produced it.

---

# 4. Input Contract

## The Accounting Engine receives

```text
Business Understanding Object          ← created and owned by the Understanding Engine
        +
Company information                    ← chart of accounts, policies, history, preferences
```

The Business Understanding Object carries the Transaction Story, Supporting Understanding Data, Identified Unknowns and the Confidence Assessment. Full structure: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §5](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#5-output-contract).

The contract governing this boundary is [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md). **The sending engine owns the contract of what leaves it.** This document references it; it does not restate it.

## Receiving rules

**Preserve evidence provenance.** Source Type (`Document` · `Human` · `Structured Metadata`), Source ID, Evidence Reference, Timestamp, Confidence and Corroborated travel with every fact. **No origin may be merged into an anonymous fact**, and a fact asserted only by a human and corroborated by nothing is never treated as established.

The Accounting Engine **must**:

1. Preserve evidence references.
2. Preserve uncertainty.
3. Preserve unknown information.
4. Never modify the Business Understanding Object.
5. **Never convert assumptions into facts.**

## What it receives, and what it never receives

The Understanding Engine sends **facts**. It never sends accounting conclusions.

| ✗ Never received | ✓ What is actually received |
|---|---|
| "Fixed asset purchase" | Item description: `Laptop` · vendor: `ABC Traders` · amount: `50,000` |

If an accounting conclusion ever appears in the Business Understanding Object, that is an Engine 2 defect. This engine does not act on it and does not correct it — it reports it.

---

# 5. Output Contract

The Accounting Engine produces exactly one artifact: the **Accounting Decision**.

```text
Accounting Decision
├── Decision ID              identity only — see §5.2
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

## Every decision must show

1. **Why this decision exists.**
2. **What information supports it.**
3. **What uncertainty remains.**

## 5.1 Decision Status

Downstream engines must be able to ask *can this move forward?* and receive a structured answer, not infer one from prose.

| Status | Meaning |
|---|---|
| `COMPLETE` | The decision is fully formed. It may still carry risks and doubts — completeness is not correctness. |
| `INCOMPLETE_INFORMATION_REQUIRED` | The decision could not be completed. Required clarification is named. See §6. |

## 5.2 Decision ID

> **Decision ID exists only for identity, traceability, lifecycle tracking and audit history.**
>
> **It has ZERO accounting meaning.**

It must **never** influence ledger selection · journal creation · tax treatment · validation outcome · confidence · future accounting decisions.

```text
✓ Correct     Decision ID: ACC-000123        → "Track this decision."

✗ Incorrect   "Because ACC-000123 existed before, choose the same accounting treatment."
```

This is the system-wide **IDENTITY ≠ INTELLIGENCE** rule — see [`DATA_FLOW.md` §9](DATA_FLOW.md#9-identity--intelligence).

## 5.3 Artifact Ownership

> **The Accounting Engine owns the Accounting Decision.**
>
> **`decision_output` creates the artifact. `decision_output` does NOT become an independent owner.**

```text
decision_output
        ↓
Creates Accounting Decision
        ↓
Accounting Engine owns artifact
        ↓
Clarification / Validation / Tally read only
```

The artifact is immutable after creation. New information produces a new version authored by its owner, never an edit in place — [`DATA_FLOW.md` §6](DATA_FLOW.md#6-artifact-ownership).

## 5.4 Correction

> **A correction is a new Accounting Decision referencing the original Transaction ID.**

```text
Wrong Entry → New Business Understanding → New Accounting Decision (new version)
    → Reverse Entry → Validation → New Execution Result
```

The **Transaction ID stays the same** — a wrong tax rate on a laptop purchase is still that purchase. What changes is a new **version** of this artifact and a new Execution Result, both under the original identity.

Nothing new is required of this engine. The discovery that an entry was wrong arrives as **new evidence at Engine 1**, which is already how all new information enters, and **a reversal is a journal entry** this engine already knows how to produce.

See [`SYSTEM_INVARIANTS.md` INV-5](SYSTEM_INVARIANTS.md#inv-5--history-is-never-modified).

## 5.5 Naming

`Accounting Decision` is the artifact's **only** name — final, as fixed by this contract. No engine may create an alternative name, and no duplicate representation may exist.

---

# 6. Absolute Boundaries

The Accounting Engine **MUST NEVER**:

1. Modify the Document Evidence Object.
2. Modify the Business Understanding Object.
3. Invent missing facts.
4. Hide uncertainty.
5. Ask users questions directly.
6. Post transactions to Tally.
7. Override validation results.
8. Change source evidence.
9. **Pretend assumptions are confirmed facts.**

## Insufficient information

If information is insufficient, the engine returns a **named output**, not an exception and not a guess:

```text
Decision Status:         INCOMPLETE_INFORMATION_REQUIRED
Reason:                  Missing information
Required clarification:  …
```

> **Never guess.**

The Clarification Engine exists to obtain what is missing. This engine identifies the gap and stops.

## Observation, understanding, judgement, approval

> **Input Engine provides evidence. Understanding Engine creates interpretation. Accounting Engine decides treatment. Validation Engine decides safety.**

---

# 7. Internal Architecture

The Accounting Engine contains **exactly nine** sub-engines:

```text
Accounting Engine
├── transaction_analyzer
├── accounting_rules
├── ledger_intelligence
├── journal_intelligence
├── tax_intelligence
├── company_understanding
├── risk_analysis
├── doubt_detection
└── decision_output
```

No additions. No removals. No merges.

## Flow

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

## 7.1 Three specialised decisions, then one combined treatment

**`accounting_rules` does not own the Ledger Recommendation or the Tax Treatment Recommendation.** That would be fake ownership — a component producing an artifact containing outputs it does not create. Three sub-engines each decide their own question:

| Sub-engine | Owns the question |
|---|---|
| `ledger_intelligence` | *Where does this transaction go?* |
| `tax_intelligence` | *What tax treatment applies?* |
| `accounting_rules` | *Which accounting rules and timing principles apply?* |
| `journal_intelligence` | *Is the final journal structurally correct?* |

Their outputs are **combined** into the Accounting Treatment Result:

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

**Accounting Period Treatment is not a separate artifact.** Ledger, tax and period all answer one question — *how should this business event be recorded?* — so they are parts of one treatment decision, not three.

## 7.2 Assembly is mechanical

> **The Accounting Engine parent assembles the Accounting Treatment Result mechanically. It does not author, modify, approve, or override the individual recommendations.**

| Parent **CAN** | Parent **CANNOT** |
|---|---|
| Combine outputs | Change the Ledger Recommendation |
| Organize outputs | Change the Tax Treatment Recommendation |
| Create the final structure | Remove uncertainty |
| | Increase confidence |

Stated explicitly because unqualified "parent assembly" is exactly how hidden decision-making creeps in. A parent permitted to adjust what it assembles is a tenth decision-maker that appears in no diagram.

## 7.3 Sub-engine output contracts

Stated identically here, in [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) and in each sub-engine's README.

| Sub-engine | Produces | Contains |
|---|---|---|
| `transaction_analyzer` | **Transaction Analysis Result** | Transaction category · accounting implications · supporting facts · unknowns · confidence |
| `company_understanding` | **Company Context Result** | Company rules · historical patterns · relevant preferences · confidence |
| `accounting_rules` | **Accounting Rule Application Result** | Applied accounting rules · accounting period treatment · recognition timing rules · rule references · assumptions · confidence |
| `ledger_intelligence` | **Ledger Recommendation** | Recommended ledgers · classification reasoning · confidence |
| `tax_intelligence` | **Tax Treatment Recommendation** | Applicable tax treatment · tax assumptions · risks · confidence |
| `journal_intelligence` | **Journal Entry Recommendation** | Debit accounts · credit accounts · amounts · reasoning · confidence |
| `risk_analysis` | **Accounting Risk Analysis** | Risk indicators · risk reasons · severity · confidence |
| `doubt_detection` | **Accounting Doubt Report** | Missing information · conflicts · required clarification areas |
| `decision_output` | **Accounting Decision** | The thirteen components of §5 |

Every Result carries **confidence**, **assumptions** and **evidence references**. No Result may omit them.

---

# 8. Sub-Engine Specifications

---

## 8.1 transaction_analyzer

### Purpose
Determine the accounting nature of the business event.

### Owns
Initial accounting interpretation — accounting-relevant transaction facts.

### Receives
The Business Understanding Object.

### Produces
**Transaction Analysis Result** — transaction category · accounting implications · supporting facts · unknowns · confidence.

### Allowed Actions
Can analyze transaction meaning in accounting terms · identify accounting implications · cite the understanding evidence supporting each.

### Forbidden Actions
Cannot create final journal entries · modify the business story · decide tax · select ledgers.

### Failure Behaviour
Return incomplete analysis with uncertainty. Where the accounting nature cannot be determined, that is recorded in unknowns — never resolved by picking the likeliest category.

---

## 8.2 company_understanding

### Purpose
Understand company-specific accounting context.

### Owns
Company accounting preferences and context. **Context provision, not decision-making.**

### Receives
The Business Understanding Object and company information.

### Produces
**Company Context Result** — company rules · historical patterns · relevant preferences · confidence.

### Allowed Actions
Can provide company profile · industry · accounting preferences · chart of accounts structure · historical patterns · policies.

### Forbidden Actions
Cannot decide debit · credit · ledger · tax treatment · journal. Cannot override accounting standards. Cannot change evidence.

### Historical patterns are evidence, not decisions

Company understanding **may influence** reasoning. It may **never** become *"the company usually does X, therefore automatically do X."*

```text
Previous treatment:  Laptop → expense
Future treatment:    Laptop → asset      ← legitimate; history cannot forbid it
```

History is offered as evidence for a decision, never copied as one. The same transaction genuinely means different things at different companies — a laptop is an employee expense at one and resale inventory at another — which is why context arrives *before* the decision and why it must not become the decision.

### Failure Behaviour
Mark missing company context. Absent configuration is recorded as absent, never substituted with a general default.

---

## 8.3 accounting_rules

### Purpose
Apply accounting principles and timing rules to the analyzed transaction.

### Owns
Accounting rule application · **accounting period treatment** · recognition timing rules.

### Receives
Transaction Analysis Result and Company Context Result.

### Produces
**Accounting Rule Application Result** — applied accounting rules · accounting period treatment · recognition timing rules · rule references · assumptions · confidence.

### Allowed Actions
Can determine which principles apply · decide which accounting period the transaction affects · apply recognition timing rules · cite the rule behind every ruling.

### Forbidden Actions
Cannot modify facts · create Tally postings · hide uncertainty. **Cannot produce the Ledger Recommendation or the Tax Treatment Recommendation** — those belong to `ledger_intelligence` and `tax_intelligence`.

### Accounting period treatment

`timeline_understanding` (Engine 2) provides dates, sequence and event timing facts. This component decides period impact. The boundary:

| Component | Statement |
|---|---|
| `timeline_understanding` | *"This event happened on this date."* |
| `accounting_rules` | *"This event belongs to this accounting period."* |

Invoice dated 31 March, paid 10 April — does it belong to March closing or April? That is an accounting decision, not a timeline fact.

### Failure Behaviour
Flag rule uncertainty. Where two principles could apply and the evidence does not distinguish them, both are recorded with the ambiguity — never resolved by preference.

---

## 8.4 ledger_intelligence

### Purpose
Determine appropriate ledger classification.

### Owns
Ledger reasoning — *where does this transaction go?*

### Receives
Transaction Analysis Result and Company Context Result.

### Produces
**Ledger Recommendation** — recommended ledgers · classification reasoning · confidence.

### Allowed Actions
Can select ledger accounts and groups · identify that an existing master is inadequate and specify a new ledger.

### Forbidden Actions
Cannot create journal posting · change transaction meaning · create a ledger anywhere — it specifies, it does not provision.

### Failure Behaviour
Return possible ledgers with uncertainty. A weak match against an existing master is a doubt, not a decision.

---

## 8.5 tax_intelligence

### Purpose
Analyze tax implications.

### Owns
Tax treatment reasoning — *what tax treatment applies?*

### Receives
Transaction Analysis Result and Company Context Result.

### Produces
**Tax Treatment Recommendation** — applicable tax treatment · tax assumptions · risks · confidence.

### Allowed Actions
Can determine GST applicability, rate and classification · place of supply · reverse charge · input tax credit eligibility · TDS · and state the basis for each.

### Forbidden Actions
Cannot file taxes · guarantee compliance · override the accounting decision · validate its own compliance — that is Validation's `tax_validation`.

### Failure Behaviour
Flag tax uncertainty. A rate is never chosen for being the most common one; where the basis is absent, the treatment is recorded as undetermined.

---

## 8.6 journal_intelligence

### Purpose
Design the journal structure.

### Owns
Debit/credit construction · **the balance guarantee**.

### Receives
The **Accounting Treatment Result** — ledger recommendation, tax treatment recommendation and accounting period treatment, combined.

### Produces
**Journal Entry Recommendation** — debit accounts · credit accounts · amounts · reasoning · confidence.

### Allowed Actions
Can combine the approved accounting components · create the journal structure · ensure **debit = credit** · ensure accounting equation balance.

### Forbidden Actions
Cannot post to Tally · change accounting rules · **calculate or interpret tax** · **select ledgers**. It consumes those decisions; it does not make them. Cannot force a balance by inserting a plug figure.

### Balance ≠ correctness

It guarantees **internal journal mathematical balance only.** It does **not** guarantee accounting correctness, tax correctness, or business correctness.

```text
Wrong ledger + balanced journal = still wrong
```

Correctness is judged by the Validation Engine. Balance is a property of the journal output itself, which is why only journal construction can guarantee it — and why guaranteeing it proves nothing about whether the entry is right.

### Failure Behaviour
Return incomplete journal reasoning. An entry that will not balance is a doubt to be raised, never a rounding line to be invented.

---

## 8.7 risk_analysis

### Purpose
Identify accounting decision risks.

### Owns
Accounting risk identification.

### Receives
All accounting analysis outputs.

### Produces
**Accounting Risk Analysis** — risk indicators · risk reasons · severity · confidence.

**Not named "Risk Assessment."** The Validation Engine owns `risk_assessment`. Two engines may not own the same concept name: Accounting risk is risk in the *reasoning*; Validation risk is risk in *approving and executing*.

### Allowed Actions
Can identify how aggressive a treatment is · how thin its basis · how unusual the amount or pattern · how much it depends on a contested reading.

### Forbidden Actions
Cannot reject decisions · modify decisions · block or gate anything · change a decision to reduce its own risk score.

### Failure Behaviour
Report unknown risks. Where the risk of a treatment cannot be assessed, that inability is itself recorded — an unassessed risk is not a zero risk.

---

## 8.8 doubt_detection

### Purpose
Identify unresolved accounting uncertainty.

### Owns
Accounting doubts.

### Receives
All accounting outputs.

### Produces
**Accounting Doubt Report** — missing information · conflicts · required clarification areas.

### Allowed Actions
Can identify where the decision is uncertain and name the specific fact that would resolve each doubt.

### Forbidden Actions
**Cannot ask users directly.** Cannot resolve doubts itself · guess · default · select the most common treatment · suppress a doubt because it would delay posting.

### Failure Behaviour
Preserve uncertainty. A doubt that cannot be characterised precisely is still recorded, marked as uncharacterised — never dropped for being hard to describe.

---

## 8.9 decision_output

### Purpose
Assemble the final Accounting Decision artifact.

### Owns
Final accounting decision assembly.

### Receives
All sub-engine outputs.

### Produces
The **Accounting Decision** — the thirteen components of §5, including **Decision Status**.

### Allowed Actions
Can combine accounting outputs · organize them · present the final reasoning · set Decision Status from the state of the doubts and missing information.

### Forbidden Actions
Cannot invent conclusions · remove uncertainty · override sub-engines · alter, reconcile or soften any component it assembles · omit risks or doubts · bypass validation.

### Failure Behaviour
Where the sub-engine outputs do not support a complete decision, it emits `INCOMPLETE_INFORMATION_REQUIRED` with the required clarification named. It does not complete the decision by assumption.

---

# 9. Accounting Assumptions

**Assumptions are a first-class component of the Accounting Decision.**

Every sub-engine relying on an assumption records it in its own Result: **what was assumed, and why.** `decision_output` assembles them into the decision.

> **Nothing may assume silently.**

An unrecorded assumption is precisely the mechanism by which "pretend assumptions are confirmed facts" happens. An assumption that is written down can be challenged by Validation, questioned by Clarification, or spotted by a human. One that is not, cannot.

---

# 10. Confidence Model

## Layered, not merged

Each engine measures confidence about its own responsibility:

| Engine | Confidence | Asks |
|---|---|---|
| Input | Evidence confidence | Was information extracted correctly? |
| Understanding | Understanding confidence | Was the business event understood correctly? |
| **Accounting** | **Decision confidence** | **Is the accounting treatment likely correct?** |
| Validation | Validation confidence | Is this safe to approve? *(declared; specified with Engine 5)* |

**A later confidence cannot ignore earlier uncertainty. Confidence must have traceability.**

## Confidence changes only when evidence changes

> **Confidence is recalculated only when evidence changes** — [`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes). It may increase, decrease or stay the same given the complete evidence set, and never rises because an engine reasoned harder.

```text
Evidence Confidence  →  Understanding Confidence  →  Decision Confidence  →  Validation Confidence
                              (never increases without new evidence)
```

Later engines cannot magically increase certainty. They may only **maintain**, **reduce**, or **request clarification**. The single exemption is new evidence — which is precisely what the Clarification Engine exists to obtain.

## Composition within this engine

```text
Decision Confidence

    Evidence Reliability
  + Understanding Confidence
  + Accounting Reasoning Confidence
  + Missing Information
  + Detected Risks
```

> **High confidence cannot exist when critical information is uncertain.**

---

# 11. Communication Contract

## Inbound — Understanding Engine → Accounting Engine

Governed by [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md). **One contract per boundary**; the sending engine owns it. This document references it and does not duplicate it.

## Internal — between the nine sub-engines

Governed by [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).

## Outbound — Accounting Engine → Clarification Engine, and → Validation Engine

Both boundaries are governed by [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) — **owned by this engine**, since the sending engine owns the contract of what leaves it. Two separate contracts, no overlap.

The **same immutable artifact** crosses both. It is not copied, forked or altered.

| | → Clarification | → Validation |
|---|---|---|
| **Artifact** | Accounting Decision | Accounting Decision |
| **Creator / Owner** | `decision_output` / Accounting Engine | `decision_output` / Accounting Engine |
| **Allowed** | Read, analyze, reference; identify blockers; request information | Read, analyze, reference; produce a Validation Decision |
| **Forbidden** | Change treatment, rewrite the decision, remove uncertainty | Amend, correct or repair it — a defect is reported, never fixed |

**Engine 3 does not ask questions.** Engine 4 detects what blocks the decision and emits a Clarification Request; Validation receives **both** artifacts, since it cannot validate a Clarification Request alone. This engine does not approve its own decision.

## Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 12. Quality Standard

## The Accounting Engine succeeds when

- ✅ Accounting reasoning is correct.
- ✅ Decisions are traceable to the understanding evidence behind them.
- ✅ Uncertainty is visible.
- ✅ Assumptions are clear.
- ✅ No facts were invented.

## The Accounting Engine fails when

- ❌ Assumptions are hidden.
- ❌ Ledger decisions are wrong.
- ❌ Certainty is unsupported.
- ❌ **Validation responsibility is mixed in** — the engine judges its own safety.

Note the asymmetry, as in Engines 1 and 2: a decision marked `INCOMPLETE_INFORMATION_REQUIRED` with the gap named is a **success**. A `COMPLETE` decision resting on one silent assumption is a **failure**, even when the assumption is correct.

---

# 13. Final Validation Checklist

## Architecture
- [x] Exactly 9 accounting sub-engines exist.
- [x] No new folders created.
- [x] No new artifact beyond those named.
- [x] No responsibilities overlap with Engine 2 or Engine 4.

## Artifacts
- [x] Accounting Decision defined — thirteen components including Decision Status.
- [x] Accounting Treatment Result defined as internal and combined.
- [x] Decision ID protected by IDENTITY ≠ INTELLIGENCE.

## Authority
- [x] Decision authority defined — ten rows.
- [x] `decision_output` creates; the parent owns.
- [x] Parent assembly is mechanical and cannot modify recommendations.
- [x] No sub-engine creates another sub-engine's decision.
- [x] Risk naming collision avoided.

## Safety
- [x] Company history is evidence, not automatic decision.
- [x] Balance ≠ correctness.
- [x] Confidence cannot increase without new evidence.
- [x] Communication contracts exist, one per boundary.
- [x] No code created. No implementation created.

---

## Related documents

- [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — the engine that produces this engine's input.
- [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — the inbound boundary contract.
- [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md) — communication between the nine sub-engines.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) — the canonical system-wide sub-engine map.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, IDENTITY ≠ INTELLIGENCE, boundary contract requirement.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
