# Engine Responsibilities

> **Precedence level 2 — Locked Architecture Decisions.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> One section per engine. Five fixed headings each: **Mission · Owns · Inputs · Outputs · Cannot Do.**
>
> "Cannot Do" is not advice. It is a prohibition. See [SYSTEM_BOUNDARIES.md](SYSTEM_BOUNDARIES.md).

---

## Summary

| Engine | Mission |
|---|---|
| **Input** | Turn a raw artifact into clean, readable, structured data with a confidence score. |
| **Understanding** | Turn structured data into a factual business story — who, what, when, how much, how paid. |
| **Accounting** | Turn the business story into an accounting decision, plus its doubts and risks. |
| **Clarification** | Resolve doubt by asking the human the fewest, sharpest questions, then update the decision. |
| **Validation** | Judge whether the decision is safe to post — correctness, tax, data integrity, duplicates, risk. |
| **Tally** | Execute the approved decision against Tally and record the truth of what happened. |

---

## 1. Input Engine

### Mission
Turn a raw artifact into clean, readable, structured data with a confidence score.

### Owns
- The physical quality of the artifact — orientation, noise, cropping, format and encoding normalisation.
- Extraction of everything written on it, including layout position.
- Structuring that extraction into fields, tables and line-item rows.
- The honest measurement of how much the extraction can be trusted, field by field.
- **Collection and preservation of every input evidence source** — uploaded documents, scanned images, PDFs, spreadsheets, emails, structured metadata, and the optional human business description. Every source is treated as evidence; **no source automatically becomes truth.**
- **Internal assembly of its four sub-engines' outputs into the Document Evidence Object**, and assignment of the Document ID.

Sub-engines: `cleaner` · `reader` · `parser` · `confidence`

> **Scope of the assembly responsibility.** The Input Engine owns the internal assembly of outputs from its four sub-engines into the Document Evidence Object. It does **not** own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, workflow control, or overriding sub-engine outputs. No assembler sub-engine exists, and none may be added.

### Inputs
- A raw artifact as received: photo, camera photo capture, image upload, PDF, scanned invoice, handwritten accounting note, receipt, bill, or other supporting accounting document — plus **Excel files, email content and structured metadata**.
- An **optional Human Business Description** in plain English. It is optional, and **the system must work correctly when none is provided**.
- Poor-quality human inputs are a normal operating condition, not an exception. What varies is the confidence attached to what is read, never whether the artifact is accepted.
- Nothing else. The Input Engine has no knowledge of the company, its books, or its history.

### Outputs
- **Document Evidence Object** — the engine's single output artifact, containing the Document ID, source references, and three components:
  - **Structured Document** — extracted text, detected fields, document structure, tables, field values and field locations.
  - **Human Business Context** *(optional)* — the original user text verbatim, source = Human, timestamp, evidence reference. Independent from extracted evidence; **never merged with it**.
  - **Confidence Report** — confidence scores, uncertainty markers, reliability information and risky fields.

Every extracted value preserves where it came from, how reliable it is, and whether uncertainty exists. **Document ID exists only for identity, traceability, and lifecycle tracking; it carries no accounting meaning and must never influence accounting decisions.**

Full specification: [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md).

### Cannot Do
- Cannot make accounting decisions of any kind — cannot decide transaction type, decide accounting treatment, select ledger accounts, create journal entries, or apply tax rules.
- Cannot interpret business meaning or understand business intent — it may extract a name, it may not conclude the name is a supplier.
- Cannot correct, complete or "improve" content it believes is wrong. It reports low confidence instead.
- Cannot fill missing information by guessing, and cannot modify original financial values.
- Cannot ask accounting questions.
- Cannot discard content it judges irrelevant.
- Cannot consult company master data, prior transactions, or any downstream engine.
- **Concerning the human description:** cannot convert it into fact, override document evidence, remove conflicting evidence, hide contradictions, **increase confidence because the user wrote something**, or **rewrite the user's wording**.

> **A human note is evidence, not truth.**

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

---

## 2. Understanding Engine

### Mission
Turn structured data into a factual business story — who, what, when, how much, how paid.

### Owns
- What kind of business event occurred.
- Who the parties are and what role each played.
- What goods or services moved, in what quantity, at what rate.
- How money moved, or was promised to move.
- When each event in the transaction occurred.
- How the transaction sits in this business's own reality — recurrence, location, trade pattern.
- The assembly of all of the above into one coherent, contradiction-checked story.

Sub-engines: `transaction_understanding` · `party_understanding` · `item_understanding` · `payment_understanding` · `timeline_understanding` · `business_context` · `story_builder`

### Inputs
- The **Document Evidence Object**, from the Input Engine — including the **Human Business Context** when one was provided.

### Outputs
- **Business Understanding Object** — the engine's single output artifact, containing four components:
  - **Transaction Story** — the final assembled narrative of what happened, in business terms only.
  - **Supporting Understanding Data** — the six sub-engine Results the story was built from.
  - **Identified Unknowns** — every gap, named.
  - **Confidence Assessment** — evidence confidence, understanding confidence, missing information, detected conflicts.

Every fact traces to the evidence that produced it; every gap is named; every conflict is preserved. `story_builder` **creates** the artifact; the **Understanding Engine owns** it.

Full specification: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).

### Cannot Do
- Cannot select ledgers, accounts or voucher types.
- Cannot determine tax treatment, rates, or eligibility.
- Cannot produce a journal entry or any debit/credit.
- Cannot invent facts to fill a gap — an absent fact is recorded as absent.
- Cannot re-read or re-extract the artifact; if the extraction is inadequate it says so, it does not go back to the source.
- Cannot use accounting vocabulary to describe business events.
- **Cannot assume the human description is automatically correct.** It may use it while interpreting the business event; it may never treat it as confirmed fact, let it override document evidence, or merge it into extracted evidence.

---

## 3. Accounting Engine

### Mission
Turn the business story into an accounting decision, plus its doubts and risks.

### Owns
- The economic substance of the event in accounting terms.
- The accounting principles and policies that govern its treatment.
- Which ledger accounts are involved, and whether a new one is required.
- The double entry itself — debits, credits, amounts, balance.
- The tax treatment: GST applicability and rate, place of supply, ITC eligibility, TDS.
- **Accounting period treatment** — which period the transaction affects.
- The company's accounting context that informs all of the above.
- An honest statement of how risky the resulting decision is.
- An honest statement of where the decision is uncertain, and what fact would resolve it.
- **Decision confidence**, and the assumptions every part of the decision rested on.
- The assembly of all of the above into one decision artifact.

Sub-engines: `transaction_analyzer` · `accounting_rules` · `ledger_intelligence` · `journal_intelligence` · `tax_intelligence` · `company_understanding` · `risk_analysis` · `doubt_detection` · `decision_output`

> **Scope of the assembly responsibility.** `decision_output` **creates** the Accounting Decision; the **Accounting Engine owns** it. The parent assembles the internal Accounting Treatment Result **mechanically** — it may combine, organize and structure, but may never change the Ledger Recommendation, change the Tax Treatment Recommendation, remove uncertainty, or increase confidence. It does not own system-wide orchestration, engine routing, workflow control, or **overriding sub-engine outputs**. No sub-engine creates another sub-engine's decision.

### Inputs
- The **Business Understanding Object**, from the Understanding Engine.
- **Company information** — chart of accounts structure, policies, preferences, historical patterns.
- Clarification Answers arriving from an external actor — which cause this engine to emit a **new version** of the Accounting Decision, never to patch the existing one.

### Outputs
- **Accounting Decision** — the engine's single output artifact, thirteen components: Decision ID · **Decision Status** · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · **accounting assumptions** · risk indicators · **decision confidence** · supporting reasoning · unresolved doubts.

Every decision shows **why it exists, what information supports it, and what uncertainty remains**. **Decision ID exists only for identity, traceability, lifecycle tracking and audit history; it has zero accounting meaning** — IDENTITY ≠ INTELLIGENCE.

Full specification: [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).

### Cannot Do
- Cannot post to Tally, or communicate with Tally in any way.
- Cannot ask the user a question directly.
- Cannot approve its own decision, or declare it safe. Cannot override validation results.
- Cannot read the raw artifact or the Document Evidence Object — it reasons from the Business Understanding Object and company information only.
- Cannot modify the Business Understanding Object, change source evidence, or invent missing facts.
- Cannot resolve its own doubt by guessing, defaulting, or picking the most common treatment. **Never guess** — insufficient information produces `INCOMPLETE_INFORMATION_REQUIRED`, not a decision.
- **Cannot pretend assumptions are confirmed facts.** Nothing may assume silently.
- Cannot decide whether the document information is correct, whether the business story is correct, or whether the user intended something different. Those belong upstream.
- Cannot validate itself; correctness is judged by the Validation Engine. **Balance ≠ correctness** — a balanced journal on a wrong ledger is still wrong.

---

## 4. Clarification Engine

### Mission
Prevent incorrect execution by detecting uncertainty before validation. **Validation should never discover uncertainty that Clarification should have identified.**

### Owns
- Missing information detection.
- Uncertainty detection.
- Conflict identification.
- Clarification generation.
- Clarification prioritisation.
- Clarification traceability.
- Clarification lifecycle tracking.
- Clarification confidence.
- Clarification completeness.

Sub-engines: `understanding` · `uncertainty_detection` · `missing_information` · `question_generator` · `answer_understanding` · `decision_updater` · `stop_decision`

> **Names are historical; responsibilities are current.** Three of these were coined in Phase 1 for a clarification loop that then ran inside the engine. That loop now runs outside it. Identities are part of the system contract and do not change — each sub-engine's entry in [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) states why its name owns its present responsibility.

> **Scope of the assembly responsibility.** `question_generator` **creates** the Clarification Request; the **Clarification Engine owns** it, with Clarification Status and Clarification History. The parent assembles; it never rewrites sub-engine outputs, resolves a conflict, changes a priority, or removes uncertainty.

### Inputs
- **Primary: the Accounting Decision** — accounting treatment, ledger classification, journal structure, tax treatment, assumptions, risk indicators, decision confidence, supporting reasoning, unresolved doubts.
- **Secondary: the Business Understanding Object** — *reference only*, for traceability, explanation, conflict identification and context.

It must preserve evidence references, reasoning, assumptions, confidence, uncertainty and traceability. It never communicates directly with Engine 1.

### Outputs
- **Clarification Request** — the engine's single output artifact: Clarification ID · **Decision Status–bearing Related Decision ID** · **Related Artifact Version** · missing information · detected conflicts · required clarification · reason it is required · affected decision · priority · supporting evidence references · **Clarification Confidence** · status.

Every request answers: what was unclear · why it mattered · what information is required · which decision depends on it · how important it is. **Clarification ID exists only for identity, traceability, lifecycle tracking and audit history** — IDENTITY ≠ INTELLIGENCE.

**Emit-only.** Questions are outputs, not actions. A later system layer may deliver the request to a user, accountant or external system; **Engine 4 never asks anyone directly and never receives answers.** New information re-enters through Engine 1, 2 or 3 as a new artifact version.

Full specification: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).

### Cannot Do
- Cannot create journal entries, choose ledgers, decide accounting treatment, or decide tax treatment.
- Cannot modify evidence, business understanding or accounting decisions.
- Cannot approve or reject execution.
- Cannot invent facts, or assume or default a value nobody supplied.
- **Cannot silently resolve conflicts.** Cannot convert assumptions into facts or uncertainty into certainty.
- **Cannot ask users directly.**
- Cannot bypass previous engines or bypass validation.
- Cannot raise uncertainty that has no evidence upstream, or increase confidence without new evidence.
- Cannot mark a decision correct, approved or safe.

**Failure behaviour:** return what is known, what is unknown, why clarification is required, and which decision is affected. **Never guess.**

---

## 5. Validation Engine

> **Specification locked.** Deep authority: [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md).

### Mission
Protect system correctness. Prevent incorrect entries, unsupported decisions, hidden assumptions and the execution of uncertain accounting.

> **Is the complete reasoning chain sufficiently correct, complete, traceable and safe for execution?**

Everything before it attempts to understand, reason and clarify. **This engine attempts to prove them wrong.**

### Owns
- Whether required artifacts exist, are complete, version-correct and structurally valid.
- Whether the entry is accounting-correct: correctly signed, posted to appropriate heads, consistent with the rules invoked.
- Whether the tax treatment is compliant and internally consistent.
- Whether this business event has already been recorded — **economic** duplication.
- What posting this would expose the business to.
- **Whether execution is legally permitted** — closed periods, statutory locks, authorisation limits.
- The single Validation Decision that results, and the naming of the engine responsible for each finding.
- Validation confidence · validation traceability · validation completeness.

Sub-engines: `data_validation` · `accounting_validation` · `tax_validation` · `duplicate_detection` · `risk_assessment` · `validation_decision`

**Only `data_validation` may stop the pipeline.** Once artifacts exist, all four validators run — a decision with an accounting error *and* a tax error reports both.

### Inputs
- **Accounting Decision** — the primary artifact to validate; original or a new version issued after clarification.
- **Clarification Request** — whether unresolved uncertainty blocks execution.
- **Reference only:** Business Understanding Object · Document Evidence Object · Company Context · Knowledge Brain.

Boundary contracts: [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) · [`COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](COMMUNICATION_RULES_CLARIFICATION_ENGINE.md).

### Outputs
- **Validation Decision** — Validation ID · Transaction ID · Related Decision ID · Related Artifact Version · Validation Status · findings · errors · warnings · risks · failed validation rules · supporting evidence references · Validation Confidence · reasoning · timestamp.
- **Validation Status:** `Approved` · `Approved With Warning` · `Clarification Required` · `Rejected`.
- **Severity:** `Critical` blocks execution · `High` · `Medium` · `Low`, non-blocking but permanently recorded.

`Approved With Warning` means *correct, but a human should look before it posts*. `Clarification Required` means *the reasoning is incomplete*. **The two are never interchangeable.**

### Cannot Do
- Cannot create accounting entries, or any part of a decision.
- Cannot modify accounting decisions, business understanding, evidence or clarification requests. **Validation never rewrites history.**
- **Cannot repair what it detects** — a defect is reported, never fixed.
- Cannot recompute ledgers, entries or tax; it judges what it was given.
- Cannot invent facts or confidence · remove assumptions · hide uncertainty · resolve conflicts.
- Cannot generate clarification or ask users — a case needing questions returns to the Clarification Engine.
- Cannot post, execute journals, or bypass any engine.
- Cannot approve while a Critical finding stands, or return a failure without naming the responsible engine.

**Failure behaviour:** never simply *"Validation failed."* Always what failed, why, the **responsible engine**, the affected artifact, blocking severity, and the recommended next step.

---

## 6. Execution Engine

> **Specification locked.** Deep authority: [`ENGINE_6_EXECUTION_ENGINE_RULES.md`](ENGINE_6_EXECUTION_ENGINE_RULES.md).
>
> **Name and folder.** The architectural name is **Execution Engine**; the locked folder is [`src/engines/tally_engine/`](../src/engines/tally_engine/). Identities are never renamed once referenced — the folder stays.

### Mission
Safely execute validated accounting decisions in the outside world, and record the truth of what happened.

> **How do we safely execute an already validated accounting decision in the outside world?**

**It never decides whether execution should happen.** That belongs exclusively to Validation. Execution is irreversible, so the engine is built around determinism, duplicate prevention, retry safety and complete auditability.

### Owns
- Translation of an approved decision into the destination's voucher representation.
- The connection to external systems, and its state.
- The act of posting: ordering, **idempotency**, the single-post guarantee, retry of transport failures, queue coordination.
- Interpretation of the destination's response into a definite outcome.
- Classification of failures, their severity, and **naming the responsible stage**.
- The append-only record of what was sent, when, on whose decision, and what came back.
- Execution notifications · execution status · **Execution Result generation**.

Sub-engines: `voucher_translator` · `tally_connector` · `posting_manager` · `response_processor` · `error_handler` · `audit_logger`

**The only engine that touches the outside world.** Tally, Zoho, Busy, SAP, QuickBooks, portals, APIs, webhooks, email, WhatsApp, notifications, file exports. **No earlier engine may communicate with an external system.**

### Inputs
- **Validation Decision** — `Approved` only, and released. Nothing else reaches this engine.
- **Accounting Decision** — what is executed.
- **Reference only:** Document Evidence Object · Business Understanding Object · Clarification Request · Validation artifacts.

Boundary contract: [`COMMUNICATION_RULES_VALIDATION_ENGINE.md`](COMMUNICATION_RULES_VALIDATION_ENGINE.md).

An `Approved With Warning` decision reaches Engine 6 **only after the Application Layer releases it** — Engine 6 cannot hold a workflow gate.

### Outputs
- **Execution Result** — the single canonical artifact. Execution ID · Execution Attempt ID · Transaction ID · Accounting Decision ID · Decision Version · Validation Decision ID · Destination System · Corrects Execution Result · Posting Status · External Transaction ID(s) · Retry Count · Queue Status · Notification Status · Classified Error · Audit Reference · Execution Outcome · Execution Confidence · Execution Timestamp.

`Posting Result`, `Classified Error` and `Audit Reference` are **components**, never artifacts in their own right. The **Audit Record** is append-only history, referenced rather than carried.

### Cannot Do
- Cannot reason, interpret or make any judgement about the transaction.
- Cannot alter the accounting meaning of what it was given, or change ledgers, journal entries or tax treatment.
- Cannot supply a value that is missing — missing data is an error, not a gap to fill.
- Cannot decide whether posting should happen; Validation decided that.
- Cannot correct a rejected voucher and resubmit it, or invent a correction.
- Cannot modify any upstream artifact, or override a Validation Decision.
- Cannot create duplicate postings, invent an external response, or suppress a failure.
- Cannot alter, delete or omit an audit record, including records of failure.
- Cannot route work backwards — it names the responsible stage; the Application Layer routes.

> **The Execution Engine transports approved decisions. It cannot create, modify or interpret business meaning.**
>
> **A posting failure must never cause the system to silently change the accounting decision.**

**Failure behaviour:** report exactly what failed, why, where, the current execution status and the recommended next action. **Never guess. Never hide failure. Never change the accounting decision.**

### Execution Confidence
The sixth confidence layer, assembled by the parent from connection, posting, acknowledgement, response processing, audit logging and notification status. **It measures transport only.** It never changes accounting or Validation confidence, and **a failed execution can never be high**.
