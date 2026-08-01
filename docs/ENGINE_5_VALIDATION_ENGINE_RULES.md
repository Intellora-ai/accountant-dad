# Engine 5 — Validation Engine: Specification Lock

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> **Status: LOCKED.** Forward Dependency Inventory completed before writing — see [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md).
>
> **Specification only — no implementation.** No code, no AI model, no databases, no APIs, no execution.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map. **This document is the deeper authority for Validation Engine specifics.**

---

# 1. Engine Identity

## Engine Name

**Validation Engine**

## Core Role

The Validation Engine is the system's **independent quality gate**.

Everything before it attempts to understand, reason and clarify. This engine attempts to **prove them wrong**.

### The question it answers

> **"Is the complete reasoning chain sufficiently correct, complete, traceable and safe for execution?"**

### The questions it does not answer

| Question | Owner |
|---|---|
| ~~What information exists?~~ | Engine 1 — Input |
| ~~What happened?~~ | Engine 2 — Understanding |
| ~~How should it be accounted?~~ | Engine 3 — Accounting |
| ~~What should be asked?~~ | Engine 4 — Clarification |
| ~~How should it be posted?~~ | Engine 6 — Execution |

**If Validation does not approve, Execution never begins.**

---

# 2. Mission

Protect system correctness. Prevent incorrect accounting entries, unsupported decisions, hidden assumptions, and the execution of uncertain accounting.

**Maintain trust in the entire accounting pipeline.**

---

# 3. Responsibility

## The Validation Engine owns

- Accounting validation · tax validation · data validation.
- Duplicate detection *(economic)*.
- Risk assessment.
- The validation decision.
- **Validation confidence · validation traceability · validation completeness.**

## The Validation Engine does NOT own

Extraction · understanding · accounting · clarification · posting · execution · document editing · evidence modification · accounting decisions · asking users.

---

# 3A. Decision Authority

> **Validation is an independent decision engine. It validates previous engine outputs but never rewrites them.**

Each sub-engine owns exactly one decision.

| Sub-engine | Can decide | Cannot decide |
|---|---|---|
| **`data_validation`** | Whether required artifacts exist, are complete, correctly versioned and structurally valid | Business meaning · accounting treatment · tax treatment · approval |
| **`accounting_validation`** | Whether accounting treatment complies with accounting rules and journal structure | Change accounting decisions · redesign journals · select ledgers |
| **`tax_validation`** | Whether tax treatment complies with applicable tax rules | Calculate new tax · change tax treatment · modify accounting |
| **`duplicate_detection`** | Whether duplicate execution risk exists | Delete, merge or ignore transactions |
| **`risk_assessment`** | Execution risk level and severity | Approve execution · reject execution · rewrite previous decisions |
| **`validation_decision`** | Final Validation Status from all validation outputs | Override sub-engine findings · suppress failures · modify upstream artifacts |
| **Validation Engine parent** | **Assembly of the Validation Decision** | Anything a sub-engine decided |

**The parent assembles. It never overrides, suppresses, rewrites or replaces any sub-engine decision** — [`SYSTEM_INVARIANTS.md` INV-10](SYSTEM_INVARIANTS.md#inv-10--one-concept-one-owner).

---

# 4. Input Contract

Engine 5 receives **completed artifacts**. It never receives raw documents for interpretation.

## Primary inputs

```text
Accounting Decision          the primary artifact to validate
Clarification Request        whether unresolved uncertainty blocks execution
```

From the **Accounting Decision** it validates: accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · assumptions · risks · confidence · reasoning · unresolved doubts.

From the **Clarification Request** it checks: whether required clarification exists · whether it blocks execution · whether unresolved issues remain · whether clarification priority matches severity.

**Validation never generates clarification.**

## Reference inputs — read-only

Business Understanding Object · Document Evidence Object · Company Context · Knowledge Brain.

Boundary contracts: [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md` §3](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md#3-boundary-contract--accounting--validation) and [`COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](COMMUNICATION_RULES_CLARIFICATION_ENGINE.md). **The sending engine owns the contract of what leaves it.**

## Preservation rules

Validation must preserve: **evidence provenance** (Source Type · Source ID · Evidence Reference · Timestamp · Confidence · Corroborated) · evidence references · assumptions · reasoning · confidence · uncertainty · traceability · artifact versions · **Transaction ID** · Decision IDs.

> **Validation never rewrites history.**

---

# 5. Output Contract

Exactly one canonical artifact: the **Validation Decision**.

```text
Validation Decision
├── Validation ID                    identity only — IDENTITY ≠ INTELLIGENCE
├── Transaction ID                   the business event this belongs to
├── Related Decision ID
├── Related Artifact Version
├── Validation Status                Approved | Approved With Warning |
│                                    Clarification Required | Rejected
├── Validation Findings
├── Validation Errors
├── Validation Warnings
├── Validation Risks
├── Failed Validation Rules
├── Supporting Evidence References
├── Validation Confidence
├── Validation Reasoning
└── Validation Timestamp
```

## 5.1 Validation Status — four outcomes

| Status | Meaning | Execution |
|---|---|---|
| **Approved** | Safe for Engine 6. | Proceeds |
| **Approved With Warning** | **Correct, but unsafe to post unattended.** A human must look before it goes. | Proceeds only with human attention |
| **Clarification Required** | The decision may become correct with additional information. | Blocked — returns through the clarification loop |
| **Rejected** | Unsafe. | **Prohibited** |

**`Approved With Warning` and `Clarification Required` are not interchangeable.** The first says the reasoning is sound but the consequences warrant a human; the second says the reasoning is incomplete. `risk_assessment` produces findings that can only be expressed as the first — *"some entries are correct and still should not be posted unattended."*

## 5.2 Validation Severity — four levels

| Severity | Effect | Examples |
|---|---|---|
| **Critical** | **Execution prohibited.** Must be resolved before Engine 6. | Debit ≠ credit · missing evidence · broken traceability · invalid accounting treatment · confirmed duplicate · **closed accounting period** |
| **High** | Execution normally blocked; usually requires clarification or correction. | |
| **Medium** | Execution policy dependent. Visible to users and auditors. | |
| **Low** | Non-blocking. **Still recorded permanently.** | |

> **Severity must never be hidden or downgraded without evidence.**

## 5.3 Artifact ownership

> **`validation_decision` creates the Validation Decision. The Validation Engine owns it. Execution consumes it.**

Ownership never changes and never moves backwards through the pipeline. Creator and owner remain separate concepts.

## 5.4 Validation ID

**Identity only** — identity · traceability · lifecycle · audit history. It must never influence approval, rejection, confidence, future validation or execution. Same system rule as Document ID, Transaction ID, Decision ID and Clarification ID — [`SYSTEM_INVARIANTS.md` INV-9](SYSTEM_INVARIANTS.md#inv-9--identity--intelligence).

---

# 6. Validation Rule Categories

Validation verifies that the complete reasoning chain satisfies every required system rule.

| # | Category |
|---|---|
| 1 | Data integrity validation |
| 2 | Accounting correctness validation |
| 3 | Tax correctness validation |
| 4 | Duplicate transaction validation *(economic)* |
| 5 | Risk acceptability validation |
| 6 | **Permission validation** — closed periods, statutory locks, authorisation limits |
| 7 | Traceability validation |
| 8 | Artifact completeness validation |
| 9 | Evidence reference validation |
| 10 | Communication contract compliance |
| 11 | Ownership compliance |
| 12 | Repository architecture compliance |
| 13 | System invariant validation |

Validation never performs document extraction, business understanding, accounting reasoning, clarification generation or execution.

## Permission validation — INV-8

> **The Accounting Engine decides the correct accounting treatment. The Validation Engine decides whether execution is legally permitted.**

A closed accounting period is a **Critical** finding here, **before execution begins**. Execution must never discover that posting was impossible — [`SYSTEM_INVARIANTS.md` INV-8](SYSTEM_INVARIANTS.md#inv-8--permission-to-execute-is-decided-before-execution).

---

# 7. Absolute Boundaries

Validation **MUST NEVER**:

create accounting entries · modify accounting decisions · modify business understanding · modify evidence · modify clarification requests · invent facts · invent confidence · remove assumptions · hide uncertainty · resolve conflicts · ask users · bypass clarification · bypass accounting · bypass evidence · bypass execution rules · post transactions · execute journals · **repair accounting mistakes**.

> **Validation only validates.**

## Validation cannot repair

If validation detects accounting errors, missing evidence, contradictions, unsupported assumptions or broken traceability — **it never fixes them. It reports them.**

## Failure behaviour

**Validation never throws away information.** If it cannot approve, it returns:

- what failed
- why it failed
- the **responsible engine**
- the affected artifact
- blocking severity
- the recommended next step

> **Never simply "Validation Failed." Always exactly why.**

## Every failure has an owner

Every validation issue points back to Engine 1, 2, 3 or 4.

```text
✗ "Validation failed."
✓ "Validation failed because the Accounting Decision lacks supporting evidence
   for its ITC claim — responsible engine: Accounting."
```

---

# 8. Knowledge Brain Boundary

The Knowledge Brain is a shared system capability, available as a **reference source** in both layers — Global Knowledge (accounting standards, GST, Income Tax, Companies Act, ICAI guidance) and Company Knowledge (chart of accounts, policies, financial year, registrations).

It may **never** approve validation · reject validation · change confidence · change accounting · override engine outputs · create Validation Decisions.

> **Knowledge informs. Validation decides.**

---

# 9. Internal Architecture

Exactly **six** sub-engines. No additions. No removals. No renames.

```text
Accounting Decision · Clarification Request · Reference Artifacts
                        │
                        ▼
                 data_validation           ← may short-circuit
                        │
        ┌───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
accounting_validation  tax_validation  duplicate_detection  risk_assessment
        │               │               │               │
        └───────────────┴───────┬───────┴───────────────┘
                                ▼
                        validation_decision
                                │
                                ▼
                       Validation Decision
```

## 9.1 Only `data_validation` may short-circuit

If required artifacts are missing, incomplete or version-incompatible, there is nothing to validate and it stops there.

**Once artifacts exist, all four validators always run.** None is skipped because another failed.

> A transaction with **both** an accounting error **and** a tax error reports **both**.

This preserves the invariant: **every failed validation rule remains visible.** `risk_assessment` reads the other three because posting risk depends on what they found.

## 9.2 Internal rules

- Every sub-engine communicates only through defined artifacts.
- No hidden communication. No shared mutable state. No circular reasoning.
- No sub-engine edits another sub-engine's output.
- Confidence always travels with outputs. Evidence references remain attached. Assumptions remain visible.
- **Every failed validation rule remains visible. No validation finding may disappear inside the pipeline.**
- The parent assembles the final Validation Decision but **never rewrites, suppresses or overrides** any sub-engine output.

## 9.3 Artifact ownership within the engine

| Artifact | Creator | Owner | Consumer |
|---|---|---|---|
| Data Validation Result | `data_validation` | Validation Engine | all four validators |
| Accounting Validation Result | `accounting_validation` | Validation Engine | `risk_assessment` · `validation_decision` |
| Tax Validation Result | `tax_validation` | Validation Engine | `risk_assessment` · `validation_decision` |
| Duplicate Detection Result | `duplicate_detection` | Validation Engine | `risk_assessment` · `validation_decision` |
| Risk Assessment | `risk_assessment` | Validation Engine | `validation_decision` |
| **Validation Decision** | `validation_decision` | **Validation Engine** | **Execution Engine** |

---

# 10. Sub-Engine Specifications

---

## 10.1 `data_validation`

### Purpose
Verify that every required input artifact exists, is complete, internally consistent, version-correct and structurally valid before validation continues.

### Owns
Data validation.

### Receives
Accounting Decision · Clarification Request · reference artifacts.

### Produces
**Data Validation Result** — completeness · missing artifacts · version compatibility · traceability status · confidence.

### Allowed Actions
Verify · inspect · compare · report.

### Forbidden Actions
Edit artifacts · create artifacts · infer missing information · modify accounting.

### Failure Behaviour
**If required data is missing, report every missing component and stop further validation.** This is the only sub-engine permitted to short-circuit — there is nothing to validate against absent artifacts. It reports *all* missing components, never the first one found.

---

## 10.2 `accounting_validation`

### Purpose
Validate accounting correctness. A decision must be checked by something that did not make it.

### Owns
Accounting validation.

### Receives
Accounting Decision · Data Validation Result.

### Produces
**Accounting Validation Result** — accounting findings · failed accounting rules · journal correctness · ledger correctness · confidence.

### Allowed Actions
Validate · compare against accounting rules · report failures.

### Forbidden Actions
Redesign journals · select ledgers · rewrite accounting.

### The balance check lands here
Engine 3's `journal_intelligence` guarantees **internal mathematical balance only** — *balance ≠ correctness*. This component judges whether the entry is **accounting-correct**: correctly signed, posted to appropriate heads, and consistent with the rules the decision claimed to apply. A balanced journal on the wrong ledger fails here.

### Failure Behaviour
**Every accounting failure remains visible. Never repair accounting.** A defect is reported with its severity and location, never corrected.

---

## 10.3 `tax_validation`

### Purpose
Validate tax correctness. Tax errors are the ones that come back years later.

### Owns
Tax validation.

### Receives
Accounting Decision · Data Validation Result.

### Produces
**Tax Validation Result** — GST findings · tax inconsistencies · missing tax information · confidence.

### Allowed Actions
Validate · compare tax treatment · report.

### Forbidden Actions
Calculate new tax · rewrite tax treatment.

### Failure Behaviour
**Unknown tax treatment remains unknown. Never invent tax interpretation.** Where the basis for a treatment is absent, that absence is the finding.

> **Depth note.** The specific tax domains this component validates — HSN/SAC, place of supply, reverse charge, ITC eligibility, blocked credits, TDS, TCS, e-invoicing, e-way bills, GSTR reconciliation — were to be established by the Reality Probe. They are named here as the expected scope, not as a measured one. Recorded in [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md).

---

## 10.4 `duplicate_detection`

### Purpose
Prevent duplicate accounting.

### Owns
**Economic** duplicate detection.

### Receives
Accounting Decision · transaction identifiers · history references.

### Produces
**Duplicate Detection Result** — duplicate probability · duplicate evidence · duplicate confidence.

### Allowed Actions
Compare · search · detect.

### Forbidden Actions
Delete transactions · merge transactions · **ignore duplicates**.

### Screening is not deciding
The Input Engine already **screened** for artifact identity — same file, same hash, same document number — and recorded a **fact**. This component makes the **judgement**: is this the same *economic transaction*, by accounting effect, even if entered differently? See [`SYSTEM_INVARIANTS.md` INV-7](SYSTEM_INVARIANTS.md#inv-7--screening-is-not-deciding).

### Failure Behaviour
**If uncertain, flag possible duplicate. Never silently allow duplication.** A legitimate near-duplicate — a monthly retainer at the same amount from the same vendor — is reported with its match strength, not suppressed.

---

## 10.5 `risk_assessment`

### Purpose
Assess execution risk. Some entries are correct and still should not be posted unattended.

### Owns
**Risk Assessment** — posting risk, distinct from Engine 3's **Accounting Risk Analysis**, which rates the reasoning rather than the consequences.

### Receives
All previous validation results, plus Engine 3's Accounting Risk Analysis.

### Produces
**Risk Assessment** — risk level · severity · affected areas · confidence · recommendation.

### Allowed Actions
Classify · score · prioritise.

### Forbidden Actions
Approve execution · reject execution · rewrite previous outputs.

### The route to `Approved With Warning`
This component cannot approve or reject. Its recommendation is what `validation_decision` converts into **Approved With Warning** — the outcome for a decision that is correct but whose consequences warrant a human. Without that status this component has no output path.

### Failure Behaviour
**Unknown risk defaults to higher severity.** An unassessed risk is never a zero risk.

---

## 10.6 `validation_decision`

### Purpose
Produce the final Validation Decision. Five opinions must become one answer.

### Owns
The Validation Decision.

### Receives
All Validation Results.

### Produces
The **Validation Decision** — status · reasoning · findings · confidence · evidence references, per §5.

### Allowed Actions
Assemble · report · publish.

### Forbidden Actions
Override sub-engine outputs · **hide failures** · remove uncertainty · create accounting decisions.

### Failure Behaviour
**Every blocking issue must appear inside the Validation Decision.** No approval exists while a Critical finding remains. Every rejection names the **responsible engine** and the recommended next step.

---

# 11. Confidence Model

**Validation Confidence** answers:

> **"How confident is the system that execution is safe?"**

## Inputs

Evidence Reliability · Understanding Confidence · Accounting Decision Confidence · Clarification Confidence · Validation Findings.

## Rules

- **Never exceeds the weakest critical confidence** it depends on.
- **Decreases when blocking issues exist.**
- **Never ignores unresolved clarification.**
- **Never increases because of assumptions.**

Governed by [`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes): confidence is recalculated when **evidence** changes, never because an engine reasoned harder. Validation cannot make weak evidence stronger and cannot create confidence — **it only evaluates existing confidence.**

**High Validation Confidence requires:** complete evidence · consistent understanding · correct accounting · no blocking clarification · acceptable risk.

---

# 12. Conflict Handling

**Validation never resolves conflicts.** It reports accounting conflicts · tax conflicts · evidence conflicts · clarification conflicts · duplicate conflicts.

Every conflict:

- **remains visible**
- references its source
- identifies the **responsible engine**
- blocks execution if required

> **No conflict may disappear.**

---

# 13. Communication Contract

| Direction | Contract |
|---|---|
| **Inbound** — Accounting → Validation | [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md` §3](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md#3-boundary-contract--accounting--validation) |
| **Inbound** — Clarification → Validation | [`COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](COMMUNICATION_RULES_CLARIFICATION_ENGINE.md) |
| **Internal** | [`COMMUNICATION_RULES_VALIDATION_INTERNAL.md`](COMMUNICATION_RULES_VALIDATION_INTERNAL.md) |
| **Outbound** — Validation → Execution | `COMMUNICATION_RULES_VALIDATION_ENGINE.md` — *authored with Engine 6; owned by Validation* |

**Validation emits only the Validation Decision.** Execution never receives intermediate validation artifacts.

## Engine 5 → Engine 6 boundary

**Execution depends entirely on Validation.**

| Status | Execution |
|---|---|
| **Approved** | May begin |
| **Approved With Warning** | May begin **only with human attention**; the warning travels with it |
| **Clarification Required** | Stops. The clarification pipeline completes, a **new Accounting Decision** is generated, and **Validation runs again**. |
| **Rejected** | Stops. Nothing is posted. The Validation Decision becomes the final output. |

> **Engine 6 may never bypass Engine 5.**

## Decision Authority

Every communication contract carries this block unchanged:

> **The sending engine owns the meaning of its artifact.** The receiving engine may consume, analyze and produce its own artifact; it may not rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 14. Quality Standard

## Success
Correct validation · complete traceability · visible uncertainty · **explainable approval** · **explainable rejection** · reproducible validation.

## Failure
Hidden validation failures · **silent approval** · unsupported rejection · missing traceability · ignored risks · hidden assumptions.

---

# 15. Validation Principles

- Validation never guesses · never invents facts · never hides failures.
- Validation never rewrites history or modifies upstream artifacts.
- Validation remains **independent** from Accounting — it assumes every previous engine could have made mistakes.
- Every approval and every rejection must be **explainable**.
- Every finding is **traceable**; every failed rule stays visible.
- Validation confidence never exceeds upstream confidence.
- **Critical uncertainty prevents approval.**
- IDs identify objects only.

---

# 16. Final Validation Checklist

- [x] Exactly six Validation sub-engines. No additions, removals or renames.
- [x] Every validation responsibility belongs to exactly one sub-engine.
- [x] Validation never performs accounting.
- [x] Validation never modifies previous artifacts.
- [x] Every failure identifies its source engine.
- [x] Every finding contains evidence references.
- [x] Validation Decision is the only outbound artifact.
- [x] Four statuses defined; `Approved With Warning` gives `risk_assessment` an output path.
- [x] Only `data_validation` short-circuits; all four validators otherwise run.
- [x] Validation Confidence follows upstream confidence.
- [x] Every conflict remains visible.
- [x] Permission validation owns the closed-period gate.
- [x] Economic duplicate detection distinguished from Input's identity screening.
- [x] Transaction ID carried.
- [x] No duplicate responsibility with Engines 1–4 or 6.
- [x] No implementation added.

---

## Related documents

- [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md) — highest authority.
- [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md) — commitments honoured and conflicts resolved before this lock.
- [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) — the engines that produce this engine's inputs.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) · [`DATA_FLOW.md`](DATA_FLOW.md) · [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md).
