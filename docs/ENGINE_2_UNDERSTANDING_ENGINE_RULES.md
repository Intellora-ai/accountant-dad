# Engine 2 — Understanding Engine: Specification Lock

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> **Status: LOCKED.** This is the permanent engineering specification for the Understanding Engine. Future implementation must follow it.
>
> **Specification only — no implementation.** No code, no libraries, no AI models, no LLM pipelines, no OCR, no APIs, no databases, no dependencies.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map of all 39 sub-engines. **This document is the deeper authority for Understanding Engine specifics** — allowed and forbidden actions, output contracts, failure behaviour, conflict handling and the confidence model. Where they overlap they must agree; a disagreement is a defect to be fixed, not a choice to be made.

---

# 1. Engine Identity

## Engine Name

**Understanding Engine**

## Core Role

The Understanding Engine is the **comprehension layer** of the AI Accountant.

> Convert evidence into a factual business story, preserving every uncertainty the evidence carried.

### The question it answers

> **"What happened in the business?"**

### The question it does not answer

> ~~"How should it be recorded?"~~

Ledgers, entries, tax and treatment belong to the Accounting Engine.

### Why this engine is separate

Reading is not understanding, and understanding is not deciding.

Extracting `19,800.00` is a perception problem — Engine 1's. Knowing it is a credit purchase from a recurring supplier is a comprehension problem — this engine's. Deciding it debits Purchases and credits a supplier ledger is a *judgement* — Engine 3's.

Facts can be verified against evidence. Judgements must be justified. Keeping them in separate engines is what lets the system show its reasoning and be checked.

---

# 2. Mission

**The Understanding Engine converts the Document Evidence Object into a coherent business story, with every fact traced to its evidence, every gap named, every conflict preserved, and confidence that never exceeds what the evidence supports.**

Four properties define success:

- **Factual** — it states what happened, in business terms, with no accounting vocabulary.
- **Traceable** — every fact points back to the evidence that produced it.
- **Honest about gaps** — what is unknown is named as unknown.
- **Honest about conflict** — where evidence disagrees, the disagreement survives.

An understanding that is coherent because it quietly picked a side has failed, however plausible the result.

---

# 3. Responsibility

## The Understanding Engine owns

- What kind of business event occurred.
- Who the parties are and what role each played.
- What goods or services moved.
- How money moved, or was promised to move.
- When each event occurred.
- How the transaction sits in this business's own operating reality.
- Story Builder's assembly of the Business Understanding Object.
- **Business Understanding Object integrity.**
- **Understanding confidence.**
- **Preservation of uncertainty.**
- **Conflict preservation.**

The last four are ownership in the full sense of [`DATA_FLOW.md` §6](DATA_FLOW.md#6-artifact-ownership): this engine is answerable for the artifact being internally sound, for what its confidence means, and for the fact that no doubt or contradiction was lost on the way through.

## The Understanding Engine does NOT own

- Accounting treatment.
- Ledger or account selection.
- Tax determination.
- Journal entries.
- Any decision about how the transaction is recorded.

---

# 3A. Decision Authority

> **The Understanding Engine controls only understanding decisions.**
>
> **No engine outside the Understanding Engine can modify its decisions.**

Authority is divided internally. Each sub-engine decides within its own domain and nowhere else.

| Component | Owns | Determines | Cannot |
|---|---|---|---|
| **Transaction Understanding** | The base event | What kind of business event occurred · the evidence supporting it | Decide accounting treatment or voucher type |
| **Party Understanding** | Entity identification | Who was involved · what role each played · relationships between them | Classify accounting ledgers |
| **Item Understanding** | What moved | Goods and services · descriptions · quantities and rates as stated | Decide asset, expense or inventory |
| **Payment Understanding** | Money movement | Payment method · references · amount relationships | Create cash or bank entries |
| **Timeline Understanding** | When | Dates · event sequence · time relationships | Decide accounting period treatment |
| **Business Context** | Operating context | Context clues · business purpose indicators | Apply accounting rules |
| **Story Builder** | Assembly | The Transaction Story · the Business Understanding Object | Resolve conflicts · override results · remove unknowns · increase confidence |
| **Understanding Engine (parent)** | Ownership of the Business Understanding Object · understanding confidence · uncertainty and conflict preservation | — | See below |

## The parent Understanding Engine does NOT

- Orchestrate the entire system.
- Route workflows.
- Make accounting decisions.
- **Override sub-engine outputs.**

## No sub-engine overrides another

Each Result stands as its author produced it. A downstream sub-engine consumes a Result; it never corrects one. Where two Results disagree, the disagreement is recorded — see §10.

---

# 4. Input Contract

## The Understanding Engine receives

```text
Document Evidence Object
```

Created and **owned** by the Input Engine. Full structure: [`ENGINE_1_INPUT_ENGINE_RULES.md` §5](ENGINE_1_INPUT_ENGINE_RULES.md#5-output-contract).

```text
Document Evidence Object
├── Document ID
├── Source References
├── Structured Document                 [EXTRACTED]
│   ├── Extracted Text
│   ├── Detected Fields
│   ├── Tables
│   ├── Field Values
│   └── Field Locations
├── Human Business Context              [PROVIDED, optional]
│   ├── Original User Text              verbatim
│   ├── Source = Human
│   ├── Timestamp
│   └── Evidence Reference
└── Confidence Report
    ├── Confidence Scores
    ├── Reliability Information
    ├── Uncertainty Markers
    └── Risky Fields
```

The contract governing this boundary is [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md). **The sending engine owns the contract of what leaves it.** This document references it; it does not restate it.

## Many documents, one business event

The Understanding Engine receives **all Document Evidence Objects sharing one Transaction ID** — not one.

```text
Invoice · Delivery Note · Bank Statement · Purchase Order · Email
        ↓  (all sharing one Transaction ID)
Business Understanding Object
```

**Extraction is document-centric. Understanding is transaction-centric.** This engine owns **evidence aggregation**: `story_builder` reconciles sources across documents exactly as it reconciles the six Results, preserving every conflict between them. A fact stated on the invoice and contradicted by the bank line is a conflict, not a choice.

See [`SYSTEM_INVARIANTS.md` INV-3](SYSTEM_INVARIANTS.md#inv-3--transaction-identity-is-separate-from-artifact-identity).

## The Human Business Context

When the user supplied a plain-English description, it arrives inside the Document Evidence Object as **provided evidence** — separate from, and never merged with, extracted document evidence.

**This engine may use it while interpreting the business event.** It may **never assume it is automatically correct.**

- It may never override document evidence.
- It may never be treated as confirmed fact.
- Where it contradicts a document, `story_builder` records the **conflict**, exactly as it would between any two Results — it does not pick a side.
- `business_context` may read it as a **business purpose indicator**, never as a conclusion.
- It may not raise confidence on its own. A fact asserted only by a human, and corroborated by nothing, stays uncorroborated.

**Corroboration is assessed here.** The Input Engine records `Corroborated: not assessed`, because establishing that *"advance paid to supplier"* and a document's payment field mean the same thing is interpretation — this engine's work. The assessment is recorded in the **Business Understanding Object**, never written back into the immutable Document Evidence Object.

## Receiving rules

The Understanding Engine must:

1. **Respect confidence** — a value extracted at 40% is not treated as a value known at 100%.
2. **Preserve uncertainty** — every uncertainty marker received travels forward.
3. **Trace understanding back to evidence** — every fact produced here points to the evidence that produced it.
4. **Never modify source evidence** — the Document Evidence Object is read-only to this engine, permanently.
5. **Preserve evidence provenance** — Source Type, Source ID, Evidence Reference, Timestamp, Confidence and Corroborated travel with every fact. **No origin may be merged into an anonymous fact.**

## What the Input Engine sends, and what it never sends

The Input Engine sends **facts**:

```text
Vendor:     ABC Traders
Amount:     50,000
Date:       1 August
Item text:  Laptop
```

It never sends **interpretations**:

| ✗ Never received | ✓ What is actually received |
|---|---|
| "Fixed asset purchase" | Document contains item description "Laptop" |

If an interpretation ever appears in the Document Evidence Object, that is an Engine 1 defect. This engine does not act on it and does not correct it — it reports it.

---

# 5. Output Contract

The Understanding Engine produces exactly one artifact: the **Business Understanding Object**.

```text
Business Understanding Object
│
├── Transaction Story ................. the final assembled narrative
│
├── Supporting Understanding Data ..... the six sub-engine Results
│   ├── Transaction Understanding Result
│   ├── Party Understanding Result
│   ├── Item Understanding Result
│   ├── Payment Understanding Result
│   ├── Timeline Understanding Result
│   └── Business Context Result
│
├── Identified Unknowns ............... every gap, named
│
└── Confidence Assessment ............. per §11
```

## Transaction Story

**Transaction Story is not an independent understanding component.** It is the final assembled narrative created by Story Builder from the six Results. The Results are the *evidence for* the story; the story is the coherent account built from them. Both travel, so a downstream engine may read the narrative or the underlying records.

## Artifact Ownership

> **The Understanding Engine owns the Business Understanding Object.**
>
> **Story Builder creates the artifact. Story Builder does NOT become an independent owner.**

```text
Story Builder
        ↓
Creates Business Understanding Object
        ↓
Understanding Engine owns artifact
        ↓
Accounting / Clarification / Validation read only
```

Creator and owner are distinct by design — see [`DATA_FLOW.md` §6](DATA_FLOW.md#6-artifact-ownership). The artifact is immutable after creation; new information produces a new version authored by its owner, never an edit in place (§12).

## Naming

`Business Understanding Object` is the artifact's **only** name. `Transaction Story` names its narrative component and is never used as the name of the artifact itself. No engine may create an alternative name, and no duplicate representation may exist.

---

# 6. Absolute Boundaries

The Understanding Engine **MUST NEVER**:

1. Create journal entries.
2. Choose ledgers.
3. Decide debit/credit.
4. Apply tax rules.
5. Post to Tally.
6. Modify evidence.
7. **Convert uncertainty into certainty.**

## The uncertainty prohibition

Rule 7 is the one this engine exists to protect. Understanding is where a system is most tempted to tidy up — to pick the likelier reading, to round away a discrepancy, to let a coherent story paper over a gap. Every such tidy-up destroys information that a later engine, or a human, needed.

Uncertainty entering this engine leaves it. It may be *described* more precisely. It is never *removed*.

## Observation, understanding, judgement

> **Input Engine provides evidence. Understanding Engine creates interpretation. Accounting Engine decides treatment.**

The Understanding Engine determines what the evidence means in business terms. It does not determine what the books should say.

---

# 7. Internal Sub-Engine Architecture

The Understanding Engine contains **exactly seven** sub-engines:

```text
Understanding Engine
├── Transaction Understanding
├── Party Understanding
├── Item Understanding
├── Payment Understanding
├── Timeline Understanding
├── Business Context
└── Story Builder
```

## Rules

- Do not add new sub-engines.
- Do not remove sub-engines.
- Do not merge responsibilities.

## Dependency graph

**The Understanding Engine is not a flat pipeline.** The order is load-bearing.

```text
Document Evidence Object
        ↓
Transaction Understanding          ← establishes the base event
        ↓
        ├── Party Understanding    ← enrich that event
        ├── Item Understanding
        ├── Payment Understanding
        └── Timeline Understanding
        ↓
Business Context                   ← requires the previous understanding
        ↓
Story Builder                      ← final assembly layer
        ↓
Business Understanding Object
```

**Why the order exists.** Transaction Understanding establishes the base event; the other components enrich it. The same name on a document means a different thing on a purchase than on a sales return, and the same date means a different thing on an invoice than on a receipt — so party, item, payment and timeline each receive the event nature. Business Context requires the preceding understanding, because "is this normal for this business" cannot be answered before knowing what *this* is. Story Builder is the final assembly layer.

Internal communication rules: [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).

## Sub-engine output contracts

These are the seven named Results. They are stated identically here, in [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md), and in each sub-engine's README.

| Sub-engine | Produces | Contains |
|---|---|---|
| **Transaction Understanding** | Transaction Understanding Result | Identified event · supporting evidence references · confidence level · unknown information · conflicts detected |
| **Party Understanding** | Party Understanding Result | Identified entities · relationships · supporting evidence · confidence · unknown parties |
| **Item Understanding** | Item Understanding Result | Identified goods/services · descriptions · evidence references · confidence · unknown item details |
| **Payment Understanding** | Payment Understanding Result | Payment method · payment references · amount relationships · confidence · unknown payment details |
| **Timeline Understanding** | Timeline Understanding Result | Dates · event sequence · time relationships · confidence · missing dates |
| **Business Context** | Business Context Result | Context clues · business purpose indicators · supporting evidence · confidence · unknown context |
| **Story Builder** | **Business Understanding Object** | Receives all six Results |

Every Result carries **confidence**, **unknowns** and **evidence references**. No Result may omit them.

---

# 8. Sub-Engine Specifications

---

## 8.1 Transaction Understanding

### Purpose

Before anything else can be understood, the kind of business event must be established.

### Owns

The base event.

### Receives

The Document Evidence Object.

### Produces

**Transaction Understanding Result** — identified event · supporting evidence references · confidence level · unknown information · conflicts detected.

### Allowed Actions

Can:

- Identify what kind of event occurred — purchase, sale, return, expense, receipt, payment, transfer, credit or debit note.
- Cite the evidence supporting that identification.
- Report the event as ambiguous where the evidence is ambiguous.

### Forbidden Actions

Cannot:

- Decide accounting treatment.
- Map the event to a voucher type or accounting classification.
- Decide the event type by what would be convenient to post.

### Failure Behaviour

Where the event kind cannot be established, the Result says so. An ambiguous document produces an ambiguous Result carried forward — never a confident guess. The ambiguity is what earns a question later, and it is recorded in unknown information with the competing readings preserved as conflicts detected.

---

## 8.2 Party Understanding

### Purpose

A transaction is between people; who they are and what role they played is a fact about the event.

### Owns

Entity identification.

### Receives

The Document Evidence Object, and the Transaction Understanding Result.

### Produces

**Party Understanding Result** — identified entities · relationships · supporting evidence · confidence · unknown parties.

### Allowed Actions

Can:

- Identify every party to the transaction and the role each played — buyer, seller, consignee, agent.
- Record identifying details as stated on the document.
- Record relationships between entities.
- Report that two parties resemble one another.

### Forbidden Actions

Cannot:

- Classify accounting ledgers, or select, create or match a ledger account for any party.
- Decide a party's accounting group.
- Merge two parties it believes to be the same entity — the similarity is reported as a fact, not acted on.

### Failure Behaviour

An unidentifiable party is recorded in unknown parties, not omitted and not guessed. Where the document does not make clear which party is the business itself, that is an unknown — it is never assumed from position on the page.

---

## 8.3 Item Understanding

### Purpose

What actually moved determines much of the treatment downstream.

### Owns

What moved.

### Receives

The Document Evidence Object, and the Transaction Understanding Result.

### Produces

**Item Understanding Result** — identified goods/services · descriptions · evidence references · confidence · unknown item details.

### Allowed Actions

Can:

- Identify the goods or services in the transaction.
- Record descriptions, quantities, units, rates and line values as stated.
- Record any stated classification codes as stated facts.

### Forbidden Actions

Cannot:

- Decide **asset**, **expense** or **inventory**.
- Classify items into accounting heads.
- Determine tax rates from item descriptions or codes.
- Recompute a line value the document states, nor supply one it omits.

### Failure Behaviour

Where a line's stated value disagrees with quantity × rate, both are reported and the disagreement is recorded as a conflict. Choosing between them is not this component's call. Missing item detail is recorded in unknown item details.

---

## 8.4 Payment Understanding

### Purpose

Whether and how money moved is a separate fact from what was supplied.

### Owns

Money movement.

### Receives

The Document Evidence Object, and the Transaction Understanding Result.

### Produces

**Payment Understanding Result** — payment method · payment references · amount relationships · confidence · unknown payment details.

### Allowed Actions

Can:

- Identify how consideration moved or was promised — cash, bank, cheque, UPI or credit.
- Record status as paid, unpaid or part-paid, with amounts.
- Record terms and instrument references as stated.
- Record relationships between amounts.

### Forbidden Actions

Cannot:

- Create cash or bank entries, or select any account.
- Infer payment from silence.
- Reconcile against bank records.

### Failure Behaviour

An unstated payment status is recorded as unstated — never assumed to be credit, and never assumed to be paid. Unstated status is one of the most frequent legitimate sources of a question later, and marking it absent is what makes that question possible. Part-payment without amounts is an unknown, not a flag.

---

## 8.5 Timeline Understanding

### Purpose

Accounting is periodic; when each thing happened is load-bearing.

### Owns

When.

### Receives

The Document Evidence Object, and the Transaction Understanding Result.

### Produces

**Timeline Understanding Result** — dates · event sequence · time relationships · confidence · missing dates.

### Allowed Actions

Can:

- Identify every date in the transaction — document date, supply or service date, receipt date, due date.
- Record what each date dates.
- Record the sequence and the relationships between them.

### Forbidden Actions

Cannot:

- Decide accounting period treatment, or apply any cut-off rule.
- Assume a missing date equals the document date.
- Resolve a contradictory date sequence by choosing one.

### Failure Behaviour

Missing dates are recorded in missing dates. A contradictory sequence is recorded as a conflict and carried forward unresolved. Where a date format is genuinely ambiguous, the ambiguity travels rather than being silently normalised.

---

## 8.6 Business Context

### Purpose

The same document means different things at different businesses; the transaction must be situated in this one's reality.

### Owns

Operating context.

### Receives

The Document Evidence Object, the preceding five Results, and the business's own operating history.

### Produces

**Business Context Result** — context clues · business purpose indicators · supporting evidence · confidence · unknown context.

### Allowed Actions

Can:

- Record whether the party is recurring and whether the pattern is normal for this business.
- Record which location or branch is involved, and what this business does.
- Record **business purpose indicators** — observed clues as to why this transaction exists in this business's operations.

### Forbidden Actions

Cannot:

- Apply accounting rules.
- Read or apply the company's accounting configuration — chart of accounts, ledger masters, registration status and accounting policy belong to the Accounting Engine's `company_understanding`.
- Conclude a treatment because "this is how it is usually posted."
- **Conclude intent.** It produces *indicators*, never a determination of why someone acted.

### Failure Behaviour

Absent context is recorded in unknown context. Purpose indicators are always presented as indicators with their supporting evidence — never promoted to a conclusion, and never used to fill a gap another sub-engine left. Recurrence is a strong signal and a dangerous one: it is offered as context for a decision, never as a substitute for making one.

---

## 8.7 Story Builder

### Purpose

The Accounting Engine must receive one coherent account of events, not six fragments.

### Owns

Assembly.

### Receives

All six preceding sub-engine Results, plus the Confidence Report within the Document Evidence Object.

### Produces

The **Business Understanding Object**, including the **Transaction Story** component it creates.

### Allowed Actions

Story Builder **CAN**:

- Combine the six sub-engine outputs.
- Organize information.
- Create the Transaction Story component.
- Create the Business Understanding Object.

### Forbidden Actions

Story Builder **CANNOT**:

- Change source observations.
- Override sub-engine results.
- **Resolve conflicts.**
- **Choose the "correct" interpretation when evidence disagrees.**
- **Remove unknowns.**
- **Increase confidence.**
- Create accounting conclusions.
- Add a fact no sub-engine produced.
- Use accounting vocabulary.

### Failure Behaviour

Where the Results disagree, the narrative reports the disagreement rather than selecting a reading — a story containing an unresolved conflict is the correct output, not a failure. Unknowns are carried into Identified Unknowns intact. Where the six Results cannot be made into a coherent narrative at all, that incoherence is itself reported, with the Results preserved unchanged beneath it.

---

# 9. Story Builder Assembly Authority

Story Builder creates the Business Understanding Object. It does **not** own it — the Understanding Engine does (§5).

The distinction matters in practice: an assembler that owns what it assembles will eventually start improving it. Story Builder's authority is deliberately narrow.

| Story Builder CAN | Story Builder CANNOT |
|---|---|
| Combine six sub-engine outputs | Change source observations |
| Organize information | Override sub-engine results |
| Create the Transaction Story component | Resolve conflicts |
| Create the Business Understanding Object | Choose the "correct" interpretation when evidence disagrees |
| | Remove unknowns |
| | Increase confidence |
| | Create accounting conclusions |

**Story Builder consumes outputs but cannot rewrite history.**

---

# 10. Conflict Handling

## Rule 1 — Conflicts are preserved

**Never silently choose one answer.**

A conflict is information. Resolving it by preference destroys the one signal that would have told a human something was wrong.

## Rule 2 — The Understanding Engine cannot force resolution

Where ambiguity exists, the engine returns:

- Known facts.
- Conflicting facts.
- Confidence.
- Unknowns.

It does not return a resolution, because resolving requires information the engine does not have.

## Conflict Ownership Rule

**Conflicts belong to the Understanding Engine.** It detects them, records them, and carries them forward. It does not hand them to another engine to settle, and no other engine may settle them by editing this engine's artifact.

## Worked example

```text
Evidence
  Document Evidence:  Amount = ₹50,000
  Payment Evidence:   Amount = ₹45,000
```

**✓ Correct output**

```text
Known:       Two amounts exist.
Conflict:    Amount mismatch detected.
Status:      Unresolved.
Confidence:  Reduced.
```

**✗ Incorrect output**

```text
System chooses ₹50,000.
```

The incorrect output is wrong even when ₹50,000 turns out to be right. It is wrong because nothing downstream can tell that a choice was made.

---

# 11. Understanding Confidence Model

**Confidence cannot be a single number only.**

```text
Understanding Confidence Model

    Evidence Confidence
  + Understanding Confidence
  + Missing Information
  + Detected Conflicts
```

| Component | What it measures |
|---|---|
| **Evidence Confidence** | How reliable the extraction was — carried in from the Confidence Report within the Document Evidence Object |
| **Understanding Confidence** | How well the evidence supports this interpretation |
| **Missing Information** | What is absent, and what its absence prevents |
| **Detected Conflicts** | Where evidence or Results disagree |

## Rules

**High confidence** requires:

- Strong evidence.
- No major conflicts.

**Low confidence** follows from:

- Missing information.
- Contradictory evidence.
- Weak interpretation.

> **Low confidence never becomes certainty.**

## Confidence Propagation Rule

**Understanding confidence cannot exceed evidence reliability.**

```text
Understanding Confidence  ≤  Evidence Reliability
```

### Worked example

```text
Input Engine
  Amount extraction confidence = 40%

Understanding Engine
  ✗ Amount understanding confidence = 95%     ← forbidden
  ✓ Amount understanding confidence ≤ 40%
```

**The uncertainty must move forward.** A confident interpretation of an unreliable reading is not understanding; it is invention with a score attached.

## Distinction from the Input Engine's Confidence Report

Two confidence artifacts exist in the system and they measure different things:

| Artifact | Owner | Measures |
|---|---|---|
| **Confidence Report** — within the Document Evidence Object | Input Engine | Confidence in the **extraction** — was this read correctly? |
| **Confidence Assessment** — within the Business Understanding Object | Understanding Engine | Confidence in the **understanding** — does the evidence support this interpretation? |

The second is bounded by the first. Neither replaces the other; both travel.

---

# 12. Understanding → Clarification Boundary

## The Understanding Engine can

- Detect uncertainty.
- Identify missing information.
- Explain **why** understanding is incomplete.

## The Understanding Engine cannot

- Ask the user questions.
- Request documents.
- Resolve uncertainty itself.

```text
Understanding Engine
        ↓
Uncertainty Detected
        ↓
Clarification Engine
```

## The Clarification Engine does not modify the Business Understanding Object

New information does not rewrite the artifact. The **owning engine** creates an updated version.

```text
Business Understanding Object
        ↓
Missing information detected
        ↓
Clarification Engine
        ↓
New information collected
        ↓
Understanding Engine creates updated version
```

**Previous artifact versions remain unchanged.**

This is the general ownership rule from [`DATA_FLOW.md` §6](DATA_FLOW.md#6-artifact-ownership) applied at this boundary — the same rule that makes a clarified accounting decision *remade* rather than patched.

---

# 13. Communication Contract

## Inbound — Input Engine → Understanding Engine

Governed by [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md). **One contract per boundary**; the sending engine owns it. This document references it and does not duplicate it.

## Internal — between the seven sub-engines

Governed by [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).

## Outbound — Understanding Engine → Accounting Engine

Governed by [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — **owned by this engine**, since the sending engine owns the contract of what leaves it.

In summary:

- **Artifact sent:** Business Understanding Object.
- **Creator:** Story Builder. **Owner:** Understanding Engine.
- **Allowed:** the Accounting Engine reads, analyzes and references it — it may interpret the business story and apply accounting reasoning.
- **Forbidden:** the Accounting Engine changes the story, removes unknowns, edits evidence, or modifies, rewrites, deletes, removes uncertainty from, or changes confidence in the artifact.
- **The Understanding Engine sends facts, never accounting conclusions.** ✗ *"Fixed asset purchase"* · ✓ *"Item description: Laptop."*

## Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 14. Quality Standard

## The Understanding Engine succeeds when

- ✅ The business story is factually correct against the evidence.
- ✅ Every fact traces back to the evidence that produced it.
- ✅ Every gap is named in Identified Unknowns.
- ✅ Every conflict is preserved, unresolved.
- ✅ Confidence never exceeds evidence reliability.
- ✅ No accounting reasoning happens inside understanding.

## The Understanding Engine fails when

- ❌ A fact is invented to complete the story.
- ❌ A conflict is silently resolved.
- ❌ An unknown is dropped because the narrative reads better without it.
- ❌ Confidence is raised above what the evidence supports.
- ❌ Accounting vocabulary appears in the output.

Note the asymmetry, as in Engine 1: a story that is incomplete and honestly marked is a **success**. A complete, coherent story built on one quiet assumption is a **failure**, even when the assumption is correct.

---

# 15. Final Validation Checklist

## Architecture

- [x] Exactly 7 Understanding sub-engines.
- [x] No new components added.
- [x] No responsibilities moved.
- [x] The dependency graph matches Phase 1.

## Communication

- [x] Input Engine → Understanding Engine contract exists — and is not duplicated.
- [x] Understanding internal communication exists.
- [x] Understanding → Accounting contract exists — [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md).

## Intelligence

- [x] Every sub-engine has an input/output contract.
- [x] Story Builder authority is defined.
- [x] Conflict handling exists.
- [x] Confidence model exists.
- [x] Clarification boundary exists.

## Authority

- [x] Every artifact has one owner.
- [x] Every decision has one owner.
- [x] Story Builder creates but does not independently own the Business Understanding Object.
- [x] The Understanding Engine owns understanding decisions.
- [x] Downstream engines cannot modify upstream artifacts.
- [x] Confidence cannot increase after uncertainty appears.
- [x] Conflicts cannot be silently resolved.
- [x] Clarification updates through new artifact versions, not mutation.

## Safety

- [x] No accounting decisions inside the Understanding Engine.
- [x] No hallucinated facts.
- [x] No uncertainty removal.
- [x] No implementation exists.

---

## Related documents

- [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) — the engine that produces this engine's input.
- [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) — the inbound boundary contract.
- [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) — communication between the seven sub-engines.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) — the canonical system-wide sub-engine map.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, boundary contract requirement.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
