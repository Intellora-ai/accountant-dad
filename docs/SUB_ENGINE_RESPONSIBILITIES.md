# Sub-Engine Responsibilities

> **Precedence level 2 — Locked Architecture Decisions.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> **This document is canonical.** Every `src/engines/*/*/README.md` mirrors the entry below; where they disagree, this document wins.
>
> 39 sub-engines. Five fixed headings each: **Purpose · Responsibility · Input · Output · Boundary.**
>
> Sub-engines belonging to an engine whose specification has been **locked** carry a sixth heading, **Failure Behaviour**. Engines 2–6 gain it as their specifications land. For those engines, the locked specification is the deeper authority on allowed and forbidden actions, output contracts and failure behaviour; this document remains canonical for the system-wide map. Where they overlap they must agree.
>
> | Engine | Specification | Status |
> |---|---|---|
> | 1. Input | [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) | **Locked** |
> | 2. Understanding | [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) · [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) | **Locked** |
> | 3. Accounting | [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) · [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md) | **Locked** |
> | 4. Clarification | [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md) | **Locked** |
> | 5–6 | — | Not yet specified |
>
> Each sub-engine owns exactly one problem. No two entries in this document claim the same problem — see §"Ownership Collisions" at the end for the pairs that look alike and how they are separated.

---

# 1. Input Engine

> **Specification locked.** Deeper authority: [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md).
>
> **Engine-level assembly.** The four sub-engines below produce four parts. The **Input Engine itself** combines them into the **Document Evidence Object** and assigns the Document ID. It owns the internal assembly of its own sub-engines' outputs and nothing more — not system-wide orchestration, engine routing, downstream reasoning, accounting decisions, workflow control, or overriding sub-engine outputs. **No assembler sub-engine exists, and none may be added.**

## 1.1 `cleaner`

**Purpose.** A document cannot be read reliably until it is physically readable.

**Responsibility.** Owns the physical quality of the artifact — deskewing, rotation, denoising, cropping, contrast, and normalisation of file format and character encoding.

**Input.** The raw artifact exactly as received: photo, camera capture, image upload, PDF, scan, handwritten note, Excel file, email content, structured metadata, or other digital file — including poor-quality human inputs. Also the **optional Human Business Description**, which it passes through untouched.

**Output.** Cleaned document representation · quality issues detected · preservation status.

**Boundary.** Cannot interpret the meaning of anything on the artifact. Cannot discard content it judges irrelevant, redundant or illegible. Cannot change numbers, correct accounting information, or alter original meaning — it alters presentation only.

**Failure Behaviour.** A **provided source passes through untouched** — a Human Business Description has no image to deskew and no encoding to repair, and any transformation would be a rewrite. If processing may damage information, preserve the original input and mark uncertainty. The original artifact is never discarded, so a damaging transformation is always recoverable. Preservation status records whether the cleaned representation or the original is the safer basis for reading. Detected quality issues are reported as evidence for `confidence`, never repaired by guesswork.

---

## 1.2 `reader`

**Purpose.** Somebody must actually get the characters off the page.

**Responsibility.** Owns extraction of everything written on the cleaned document representation — printed text and handwriting alike — together with where on the page each piece of text sits.

**Input.** The cleaned document representation from `cleaner`.

**Output.** Raw extracted information (text, numbers, dates, names, tables, handwriting output) · source locations · extraction confidence.

**Boundary.** Cannot assign meaning to what it extracts — it may extract `27AAECS1234F1Z5`, it may not conclude that this is a GSTIN. Cannot understand transaction meaning, fix accounting mistakes, guess unclear words, or infer missing business information. Cannot reorder or restructure the text.

**Failure Behaviour.** A **provided source passes through untouched** — a typed note is already text, and reading it would mean interpreting it. Return extracted information with confidence levels and uncertainty. An unclear character or word is emitted as unclear, with its confidence, never resolved by guessing. A region that could not be read at all is reported as unread, not omitted silently. Source locations are emitted even for low-confidence extractions — that is what makes a later human check possible.

---

## 1.3 `parser`

**Purpose.** Loose text is not usable; the document's own structure must be recovered.

**Responsibility.** Owns the conversion of extracted information into structure — fields, key–value pairs, tables, and line-item rows — faithful to how the document is laid out.

**Input.** Raw extracted information with source locations from `reader`.

**Output.** Structured fields · field mappings · missing field information. Together these form the **Structured Document**, a component of the Document Evidence Object.

**Boundary.** Cannot decide business meaning — it may identify a field labelled "Supplier", it may not conclude that party is a supplier for accounting purposes. Cannot decide debit or credit, choose ledger accounts, apply accounting rules, or create transaction meaning. Cannot compute, derive or infer a value that is not written. Cannot fill a field that is absent.

**Failure Behaviour.** A **provided source receives no structure** — a Human Business Description is narrative, not fields, and structuring it would begin interpreting it. Unknown fields remain unknown; never fabricate values. A field that is absent is recorded in missing field information as absent — not defaulted, not estimated, not omitted. "Absent", "zero" and "unreadable" are three different states and must remain distinguishable. Field mappings retain the source reference for every mapped value, so a wrong mapping can be traced.

---

## 1.4 `confidence`

**Purpose.** Every downstream engine needs to know how much of this extraction to trust.

**Responsibility.** Owns the honest measurement of extraction trustworthiness, per field and overall, and the identification of the specific regions and fields that are weak.

**Input.** The outputs of `cleaner`, `reader` and `parser`.

**Output.** Confidence scores · uncertainty markers · reliability assessment. Together these form the **Confidence Report**, a component of the Document Evidence Object.

**Boundary.** Cannot re-read, re-parse or correct anything. Cannot increase confidence without evidence, hide uncertainty, or make accounting decisions. Cannot reject a document or halt the pipeline. Cannot use business plausibility as evidence — it measures extraction quality, not whether the content makes commercial sense.

**Failure Behaviour.** For a **provided source it scores capture fidelity** — how faithfully the input was stored — never whether the statement is true; a human note may never raise Evidence Reliability simply by existing. Reduce confidence and explain the uncertainty. Where reliability cannot be established, confidence goes down — never up, and never to a default "good enough" value. Every uncertainty marker carries a reason; a bare score cannot become a good question downstream. Uncertainty is never suppressed because it would delay processing.

---

# 2. Understanding Engine

> **Specification locked.** Deeper authority: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).
>
> **Not a flat pipeline.** `transaction_understanding` establishes the base event; `party`, `item`, `payment` and `timeline` enrich it; `business_context` requires the preceding understanding; `story_builder` assembles last.
>
> **Engine-level ownership.** `story_builder` **creates** the **Business Understanding Object**; the **Understanding Engine owns** it. Story Builder does not become an independent owner. Every Result below carries confidence, unknowns and evidence references — none may omit them.

## 2.1 `transaction_understanding`

**Purpose.** Before anything else can be understood, the kind of business event must be established.

**Responsibility.** Owns the base event — identification of what kind of event occurred: a purchase, a sale, a return, an expense, a receipt, a payment, a transfer, a credit or debit note.

**Input.** The Document Evidence Object, including the Human Business Context when one was provided.

**Output.** **Transaction Understanding Result** — identified event · supporting evidence references · confidence level · unknown information · conflicts detected.

**Boundary.** Cannot decide accounting treatment. Cannot map the event to a voucher type or accounting classification — that is the Accounting Engine's. Cannot decide the event type by what would be convenient to post.

**Failure Behaviour.** Where the event kind cannot be established, the Result says so. An ambiguous document produces an ambiguous Result carried forward — never a confident guess. The ambiguity is recorded in unknown information, with the competing readings preserved as conflicts detected.

---

## 2.2 `party_understanding`

**Purpose.** A transaction is between people; who they are and what role they played is a fact about the event.

**Responsibility.** Owns entity identification — every party to the transaction, the role each played (buyer, seller, consignee, agent), the relationships between them, and their identifying details as stated on the document.

**Input.** The Document Evidence Object, and the Transaction Understanding Result.

**Output.** **Party Understanding Result** — identified entities · relationships · supporting evidence · confidence · unknown parties.

**Boundary.** Cannot classify accounting ledgers, or select, create or match a ledger account for any party. Cannot decide a party's accounting group. Cannot merge two parties it believes to be the same entity — it reports the similarity as a fact.

**Failure Behaviour.** An unidentifiable party is recorded in unknown parties, not omitted and not guessed. Where the document does not make clear which party is the business itself, that is an unknown — never assumed from position on the page.

---

## 2.3 `item_understanding`

**Purpose.** What actually moved determines much of the treatment downstream.

**Responsibility.** Owns what moved — the goods or services in the transaction: descriptions, quantities, units, rates, line values, and any stated classification codes.

**Input.** The Document Evidence Object, and the Transaction Understanding Result.

**Output.** **Item Understanding Result** — identified goods/services · descriptions · evidence references · confidence · unknown item details.

**Boundary.** Cannot decide **asset**, **expense** or **inventory**. Cannot classify items into accounting heads. Cannot determine tax rates from item descriptions or codes. Cannot recompute a line value the document states, nor supply one it omits.

**Failure Behaviour.** Where a line's stated value disagrees with quantity × rate, both are reported and the disagreement is recorded as a conflict; choosing between them is not this component's call. Missing item detail is recorded in unknown item details.

---

## 2.4 `payment_understanding`

**Purpose.** Whether and how money moved is a separate fact from what was supplied.

**Responsibility.** Owns money movement — how consideration moved or was promised: cash, bank, cheque, UPI or credit; paid, unpaid or part-paid; the terms, amount relationships and any instrument references stated.

**Input.** The Document Evidence Object, and the Transaction Understanding Result.

**Output.** **Payment Understanding Result** — payment method · payment references · amount relationships · confidence · unknown payment details.

**Boundary.** Cannot create cash or bank entries, or select any account. Cannot infer payment from silence. Cannot reconcile against bank records.

**Failure Behaviour.** An unstated payment status is recorded as unstated — never assumed to be credit, never assumed to be paid. It is one of the most frequent legitimate sources of a question later, and marking it absent is what makes that question possible. Part-payment without amounts is an unknown, not a flag.

---

## 2.5 `timeline_understanding`

**Purpose.** Accounting is periodic; when each thing happened is load-bearing.

**Responsibility.** Owns when — every date and sequence in the transaction: document date, supply or service date, receipt date, due date, and their order relative to one another.

**Input.** The Document Evidence Object, and the Transaction Understanding Result.

**Output.** **Timeline Understanding Result** — dates · event sequence · time relationships · confidence · missing dates.

**Boundary.** Cannot decide accounting period treatment, or apply any cut-off rule. Cannot assume a missing date equals the document date. Cannot resolve a contradictory date sequence by choosing one.

**Failure Behaviour.** Missing dates are recorded in missing dates. A contradictory sequence is recorded as a conflict and carried forward unresolved. Where a date format is genuinely ambiguous, the ambiguity travels rather than being silently normalised.

---

## 2.6 `business_context`

**Purpose.** The same document means different things at different businesses; the transaction must be situated in this one's reality.

**Responsibility.** Owns operating context — whether the party is recurring, whether the pattern is normal for this business, which location or branch is involved, what this business actually does, and observed indicators of why this transaction exists in its operations.

**Input.** The Document Evidence Object, the preceding five Results, and the business's own operating history.

**Output.** **Business Context Result** — context clues · business purpose indicators · supporting evidence · confidence · unknown context.

**Boundary.** Cannot apply accounting rules. Cannot read or apply the company's accounting configuration — chart of accounts, ledger masters, registration status and accounting policy belong to the Accounting Engine's `company_understanding`. Cannot conclude a treatment because "this is how it is usually posted." **Cannot conclude intent** — it produces indicators, never a determination of why someone acted.

**Failure Behaviour.** Absent context is recorded in unknown context. Purpose indicators are always presented as indicators with their supporting evidence — never promoted to a conclusion, and never used to fill a gap another sub-engine left. Recurrence is a strong signal and a dangerous one: it is offered as context for a decision, never as a substitute for making one.

---

## 2.7 `story_builder`

**Purpose.** The Accounting Engine must receive one coherent account of events, not six fragments.

**Responsibility.** Owns assembly — combining the six Results into the **Business Understanding Object**, and creating the **Transaction Story** component from them.

**Input.** All six preceding sub-engine Results, plus the Confidence Report within the Document Evidence Object.

**Output.** The **Business Understanding Object** — Transaction Story · Supporting Understanding Data (the six Results, unaltered) · Identified Unknowns · Confidence Assessment. The sole artifact handed to the Accounting Engine.

**Boundary.** Can combine outputs, organize information, create the Transaction Story component, and create the artifact. **Cannot** change source observations · override sub-engine results · **resolve conflicts** · **choose the "correct" interpretation when evidence disagrees** · **remove unknowns** · **increase confidence** · create accounting conclusions · add a fact no sub-engine produced · use accounting vocabulary. It **creates** the artifact but does not **own** it — the Understanding Engine does.

**Failure Behaviour.** Where the Results disagree, the narrative reports the disagreement rather than selecting a reading — a story containing an unresolved conflict is the correct output, not a failure. Unknowns are carried into Identified Unknowns intact. Where the six Results cannot be made into a coherent narrative at all, that incoherence is itself reported, with the Results preserved unchanged beneath it.

---

# 3. Accounting Engine

> **Specification locked.** Deeper authority: [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).
>
> **Three specialised decisions, then one combined treatment.** `ledger_intelligence`, `tax_intelligence` and `accounting_rules` each decide their own question; their outputs are **combined** by the parent engine into the internal **Accounting Treatment Result**, which `journal_intelligence` then consumes. **`accounting_rules` does not produce the Ledger Recommendation or the Tax Treatment Recommendation** — that would be fake ownership.
>
> **Engine-level ownership.** `decision_output` **creates** the **Accounting Decision**; the **Accounting Engine owns** it. The parent assembles **mechanically** — it may combine, organize and structure, never change a recommendation, remove uncertainty, or increase confidence. **No sub-engine creates another sub-engine's decision.** Every Result carries confidence, assumptions and evidence references — none may omit them.

## 3.1 `transaction_analyzer`

**Purpose.** Determine the accounting nature of the business event.

**Responsibility.** Owns initial accounting interpretation — the accounting-relevant facts of the understood event: substance, event class, and the aspects requiring treatment.

**Input.** The Business Understanding Object.

**Output.** **Transaction Analysis Result** — transaction category · accounting implications · supporting facts · unknowns · confidence.

**Boundary.** Cannot create final journal entries · modify the business story · decide tax · select ledgers. Cannot read the Document Evidence Object or the raw artifact — it consumes the understanding as given.

**Failure Behaviour.** Return incomplete analysis with uncertainty. Where the accounting nature cannot be determined, that is recorded in unknowns — never resolved by picking the likeliest category.

---

## 3.2 `company_understanding`

**Purpose.** Understand company-specific accounting context. The same transaction means different things at different companies — a laptop is an employee expense at one and resale inventory at another.

**Responsibility.** Owns company accounting preferences and context — **context provision, not decision-making**: company profile, industry, accounting preferences, chart of accounts structure, historical patterns, policies.

**Input.** The Business Understanding Object and company information.

**Output.** **Company Context Result** — company rules · historical patterns · relevant preferences · confidence.

**Boundary.** Cannot decide debit · credit · ledger · tax treatment · journal. Cannot override accounting standards. Cannot change evidence. **Historical patterns are evidence, not decisions** — *"the company usually does X, therefore automatically do X"* is forbidden; a laptop treated as expense last year may legitimately be an asset this year.

**Failure Behaviour.** Mark missing company context. Absent configuration is recorded as absent, never substituted with a general default.

---

## 3.3 `accounting_rules`

**Purpose.** Apply accounting principles and timing rules to the analyzed transaction.

**Responsibility.** Owns accounting rule application, **accounting period treatment**, and recognition timing rules.

**Input.** Transaction Analysis Result and Company Context Result.

**Output.** **Accounting Rule Application Result** — applied accounting rules · accounting period treatment · recognition timing rules · rule references · assumptions · confidence.

**Boundary.** Cannot modify facts · create Tally postings · hide uncertainty · invent a rule from the transaction in front of it. **Cannot produce the Ledger Recommendation or the Tax Treatment Recommendation** — those belong to `ledger_intelligence` and `tax_intelligence`. Period boundary: `timeline_understanding` states *"this event happened on this date"*; this component decides *"this event belongs to this accounting period."*

**Failure Behaviour.** Flag rule uncertainty. Where two principles could apply and the evidence does not distinguish them, both are recorded with the ambiguity — never resolved by preference.

---

## 3.4 `ledger_intelligence`

**Purpose.** Determine appropriate ledger classification — *where does this transaction go?*

**Responsibility.** Owns ledger reasoning: which accounts are involved, their groups, and the determination that an existing master is inadequate and a new ledger is required.

**Input.** Transaction Analysis Result and Company Context Result.

**Output.** **Ledger Recommendation** — recommended ledgers · classification reasoning · confidence.

**Boundary.** Cannot create journal posting · change transaction meaning · create a ledger anywhere — it specifies, it does not provision. Cannot compute amounts or decide debit/credit direction.

**Failure Behaviour.** Return possible ledgers with uncertainty. A weak match against an existing master is a doubt, not a decision.

---

## 3.5 `tax_intelligence`

**Purpose.** Analyze tax implications — *what tax treatment applies?*

**Responsibility.** Owns tax treatment reasoning — GST applicability, rate and classification, place of supply, reverse charge, input tax credit eligibility, TDS.

**Input.** Transaction Analysis Result and Company Context Result.

**Output.** **Tax Treatment Recommendation** — applicable tax treatment · tax assumptions · risks · confidence.

**Boundary.** Cannot file taxes · guarantee compliance · override the accounting decision · modify transaction facts · apply unsupported assumptions. Cannot validate its own compliance — that is the Validation Engine's `tax_validation`.

**Failure Behaviour.** Flag tax uncertainty. A rate is never chosen for being the most common one; where the basis is absent, the treatment is recorded as undetermined.

---

## 3.6 `journal_intelligence`

**Purpose.** Design the journal structure — *is the final journal structurally correct?*

**Responsibility.** Owns debit/credit construction and **the balance guarantee**: combining the approved accounting components, creating the journal structure, and ensuring debit = credit and accounting-equation balance.

**Input.** The **Accounting Treatment Result** — ledger recommendation, tax treatment recommendation and accounting period treatment, combined.

**Output.** **Journal Entry Recommendation** — debit accounts · credit accounts · amounts · reasoning · confidence.

**Boundary.** Cannot post to Tally · change accounting rules · **calculate or interpret tax** · **select ledgers** — it consumes those decisions. Cannot force a balance by inserting a plug figure. **Balance ≠ correctness**: it guarantees internal journal mathematical balance only, never accounting, tax or business correctness — *wrong ledger + balanced journal = still wrong*. Correctness is judged by the Validation Engine.

**Failure Behaviour.** Return incomplete journal reasoning. An entry that will not balance is a doubt to be raised, never a rounding line to be invented.

---

## 3.7 `risk_analysis`

**Purpose.** Identify accounting decision risks.

**Responsibility.** Owns accounting risk identification — how aggressive a treatment is, how thin its basis, how unusual the amount or pattern, how much it depends on a contested reading.

**Input.** All accounting analysis outputs.

**Output.** **Accounting Risk Analysis** — risk indicators · risk reasons · severity · confidence. **Not named "Risk Assessment"** — the Validation Engine owns that name.

**Boundary.** Cannot reject decisions · modify decisions · block or gate anything · change a decision to reduce its own risk score. Cannot assess the consequences of *posting* — exposure, materiality and reversibility belong to the Validation Engine's `risk_assessment`.

**Failure Behaviour.** Report unknown risks. Where the risk of a treatment cannot be assessed, that inability is itself recorded — an unassessed risk is not a zero risk.

---

## 3.8 `doubt_detection`

**Purpose.** Identify unresolved accounting uncertainty.

**Responsibility.** Owns accounting doubts — where the decision is uncertain, and the specific fact that would resolve each.

**Input.** All accounting outputs.

**Output.** **Accounting Doubt Report** — missing information · conflicts · required clarification areas.

**Boundary.** **Cannot ask users directly.** Cannot resolve doubts itself · guess · default · select the most common treatment · suppress a doubt because it is inconvenient or would delay posting. Cannot judge which doubts matter enough to block posting — that is the Clarification Engine's `uncertainty_detection`.

**Failure Behaviour.** Preserve uncertainty. A doubt that cannot be characterised precisely is still recorded, marked as uncharacterised — never dropped for being hard to describe.

---

## 3.9 `decision_output`

**Purpose.** Assemble the final Accounting Decision artifact.

**Responsibility.** Owns final accounting decision assembly, including setting **Decision Status** from the state of the doubts and missing information.

**Input.** The outputs of all eight preceding Accounting sub-engines.

**Output.** The **Accounting Decision** — Decision ID · Decision Status · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts.

**Boundary.** Cannot invent conclusions · remove uncertainty · override sub-engines · alter, reconcile or soften any component it assembles · omit risks or doubts · bypass validation · mark the decision approved or safe. It **creates** the artifact but does not **own** it — the Accounting Engine does.

**Failure Behaviour.** Where the sub-engine outputs do not support a complete decision, it emits `INCOMPLETE_INFORMATION_REQUIRED` with the required clarification named. **Never guess** — it does not complete the decision by assumption.

---

# 4. Clarification Engine

> **Specification locked.** Deeper authority: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).
>
> **Emit-only.** Engine 4 detects what blocks a decision and emits a **Clarification Request**. It never asks users and never receives answers — new information re-enters through Engine 1, 2 or 3 as a **new artifact version**.
>
> **Names are historical; responsibilities are current.** Three of these names were coined in Phase 1 for a clarification loop that then ran *inside* the engine. That loop now runs outside it. Identities are part of the system contract and do not change; each entry below states why its name owns its present responsibility.
>
> **Engine-level ownership.** `question_generator` **creates** the **Clarification Request**; the **Clarification Engine owns** it, with Clarification Status and Clarification History. The parent assembles; it never rewrites sub-engine outputs. Every Result carries confidence and evidence references — none may omit them.

## 4.1 `missing_information`

**Purpose.** Identify every piece of information required to safely continue that is currently unavailable.

**Responsibility.** Owns missing information identification.

**Name and responsibility.** Name and role are identical: it found what was absent in Phase 1, and it finds what is absent now.

**Input.** The Accounting Decision, and the Business Understanding Object (reference only).

**Output.** **Missing Information Result** — missing facts · missing relationships · missing supporting evidence · affected accounting decisions · confidence · evidence references.

**Boundary.** Can compare required against available information, detect absence, preserve traceability. Cannot infer missing facts · invent values · modify previous artifacts · ask users directly.

**Failure Behaviour.** If completeness cannot be determined, preserve uncertainty and report incomplete detection rather than assuming completeness. An undetermined completeness is never recorded as complete.

---

## 4.2 `uncertainty_detection`

**Purpose.** Determine whether available information is reliable enough for downstream execution.

**Responsibility.** Owns uncertainty evaluation.

**Name and responsibility.** Detection is the act; analysis is its output. The Phase 1 name describes what it does, the artifact name what it produces — the same faculty named from opposite ends.

**Input.** Missing Information Result and the Accounting Decision.

**Output.** **Uncertainty Analysis Result** — uncertainty sources · uncertainty severity · confidence impact · affected decisions · supporting reasoning.

**Boundary.** Can measure and classify uncertainty, preserve supporting evidence. Cannot increase confidence without evidence · remove uncertainty · modify accounting reasoning.

**Failure Behaviour.** Unknown uncertainty remains visible. **Never convert uncertainty into certainty.** Uncertainty that cannot be classified is recorded as unclassified, not dropped.

---

## 4.3 `understanding`

**Purpose.** Detect contradictions between evidence, understanding and accounting decisions.

**Responsibility.** Owns conflict identification.

**Name and responsibility.** A contradiction cannot be found without comprehending all three artifacts together. In Phase 1 this component comprehended the case and located the **doubts** in it; it now comprehends the case and locates the **contradictions** in it. Same faculty, sharper target.

**Input.** The Accounting Decision, the Business Understanding Object, and the Missing Information Result.

**Output.** **Conflict Analysis Result** — detected conflicts · conflicting assumptions · conflicting reasoning · conflict severity · affected accounting decisions.

**Boundary.** Can identify contradictions, preserve all conflicting information, maintain traceability. **Cannot resolve conflicts** · discard conflicting evidence · **choose one interpretation**.

**Failure Behaviour.** Every detected conflict remains visible until resolved by the responsible engine. A conflict that cannot be characterised is still recorded, marked as uncharacterised.

---

## 4.4 `stop_decision`

**Purpose.** Determine whether clarification is actually required. Not every uncertainty deserves a request: some has no effect on accounting treatment, some changes the entire decision.

**Responsibility.** Owns clarification necessity.

**Name and responsibility.** It was always the go/no-go gate on the clarification path. Phase 1 asked *is questioning complete?*; it now asks *is clarification required at all?* Both are one binary judgement about whether clarification runs.

**Input.** Missing Information Result, Uncertainty Analysis Result, Conflict Analysis Result, and the Accounting Decision.

**Output.** **Clarification Necessity Result** — clarification required · clarification optional · clarification unnecessary · business impact · accounting impact · supporting reasoning.

**Boundary.** Can evaluate decision impact, determine necessity, preserve reasoning. Cannot generate clarification requests · modify accounting decisions · modify uncertainty.

**Failure Behaviour.** **If necessity cannot be determined safely, default to Clarification Required. Never silently ignore uncertainty.** The asymmetry is deliberate: an unnecessary question costs time, a missed one costs correctness.

---

## 4.5 `answer_understanding`

**Purpose.** Determine the order in which clarification should occur. Critical accounting blockers must always be resolved before cosmetic or informational clarification.

**Responsibility.** Owns clarification priority.

**Name and responsibility.** Priority is a judgement about **answers** — nothing can be ranked without understanding how much the answer to each clarification would change the decision. Phase 1 it reasoned about answers received; it now reasons about the weight of answers not yet received. The answer-centric component in both eras.

**Input.** Clarification Necessity Result.

**Output.** **Clarification Priority Result** — priority level (Critical · High · Medium · Low) · affected decision · business impact · accounting impact · urgency reasoning.

**Boundary.** Can prioritise clarification, group related clarification, determine execution order. Cannot remove clarification requirements · modify accounting reasoning · modify previous artifacts.

**Failure Behaviour.** **Unknown priority defaults to High until sufficient information exists.** Under-prioritising an unknown is the more expensive error.

---

## 4.6 `question_generator`

**Purpose.** Construct the canonical Clarification Request.

**Responsibility.** Owns Clarification Request creation.

**Name and responsibility.** It formulates what is asked. The Clarification Request *is* what Phase 1 called the Question Set, in structured form — what is missing, why it matters, what is needed. Generating the question is generating the request.

**Input.** Outputs from every previous Clarification sub-engine.

**Output.** The **Clarification Request** — Clarification ID · Related Decision ID · Related Artifact Version · missing information · detected conflicts · required clarification · reason · affected decision · priority · supporting evidence references · Clarification Confidence · status.

**Boundary.** Can assemble clarification, merge components, preserve evidence references. Cannot invent clarification · modify upstream decisions · hide uncertainty · rewrite reasoning. It **creates** the artifact but does not **own** it — the Clarification Engine does.

**Failure Behaviour.** Produces an incomplete Clarification Request while preserving every unresolved issue. An incomplete request naming what it could not determine is correct output; a complete-looking request that dropped an issue is not.

---

## 4.7 `decision_updater`

**Purpose.** Track the lifecycle of every clarification request. Clarification is not complete when a request is created — only when the required information has been received and the responsible upstream engine has produced a new artifact version.

**Responsibility.** Owns clarification lifecycle, clarification status and clarification history.

**Name and responsibility.** It is the component that knows the relationship between a clarification and the **state of the decision**. Phase 1 it carried answers back so the decision could be remade; it now links each clarification to the decision version it was raised against and marks it superseded when a newer version overtakes it. Version-and-state tracking in both eras.

**Input.** The Clarification Request.

**Output.** **Clarification Status Result** — current status · timestamps · related artifact versions · resolution history · audit trail.

**Boundary.** Can track progress, maintain history, link clarification to artifact versions. **Cannot resolve clarification** · modify decisions · approve execution. It owns every status transition but no resolution — resolution is an upstream engine emitting a new artifact version.

**Failure Behaviour.** Preserve complete audit history even if clarification remains unresolved. History is never trimmed because a request went nowhere.

---

# 5. Validation Engine

> **Specification locked.** Deep authority: [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_VALIDATION_INTERNAL.md`](COMMUNICATION_RULES_VALIDATION_INTERNAL.md).
>
> **Only `data_validation` may stop the pipeline.** Once artifacts exist, all four validators run — a transaction with an accounting error *and* a tax error reports both.

## 5.1 `accounting_validation`

**Purpose.** A decision must be checked by something that did not make it.

**Responsibility.** Owns **accounting validation** — whether the entry is accounting-correct: correctly signed, posted to appropriate heads, and consistent with the rules its own reasoning invoked. Engine 3's `journal_intelligence` guarantees mathematical balance only; **balance ≠ correctness**, and a balanced journal on the wrong ledger fails here.

**Input.** The Accounting Decision, including its stated reasoning and rulings · the Data Validation Result.

**Output.** The **Accounting Validation Result** — accounting findings · failed accounting rules · journal correctness · ledger correctness · confidence.

**Boundary.** Can validate, compare against accounting rules, report failures. Cannot redesign journals · select ledgers · rewrite accounting · fix, adjust or repair the entry. Cannot substitute its own preferred treatment for a defensible one. Cannot judge tax treatment — that is `tax_validation`.

**Failure Behaviour.** Every accounting failure remains visible. **Never repair accounting** — a defect is reported with its severity and location, never corrected.

---

## 5.2 `tax_validation`

**Purpose.** Tax errors are the ones that come back years later.

**Responsibility.** Owns **tax validation** — whether the tax treatment is compliant and internally consistent: rate against classification, place of supply against parties, ITC eligibility against the stated basis, TDS against applicability.

**Input.** The Accounting Decision — its tax treatment and tax lines, the party and item facts, the company's tax profile · the Data Validation Result.

**Output.** The **Tax Validation Result** — GST findings · tax inconsistencies · missing tax information · confidence.

**Boundary.** Can validate, compare tax treatment, report. Cannot calculate new tax · rewrite tax treatment · select a different treatment · file or report anything.

**Failure Behaviour.** Unknown tax treatment remains unknown. **Never invent tax interpretation** — where the basis for a treatment is absent, that absence is the finding.

---

## 5.3 `data_validation`

**Purpose.** A perfectly reasoned entry built on broken data is still broken.

**Responsibility.** Owns **data validation** — whether every required input artifact exists, is complete, internally consistent, version-correct and structurally valid: required fields present, dates in range and sequence, totals reconciling to their lines, every referenced master existing. **Owns the closed-period gate** — see Permission validation, below.

**Input.** The Accounting Decision · the Clarification Request · reference artifacts: Business Understanding Object, Document Evidence Object, Company Context.

**Output.** The **Data Validation Result** — completeness · missing artifacts · version compatibility · traceability status · confidence.

**Boundary.** Can verify, inspect, compare, report. Cannot edit artifacts · create artifacts · infer missing information · modify accounting · correct, complete or normalise any data. Cannot judge whether the accounting treatment is right. Cannot lower a requirement because the data cannot meet it.

**Failure Behaviour.** If required data is missing, report **every** missing component and stop further validation. **This is the only sub-engine permitted to short-circuit** — there is nothing to validate against absent artifacts.

---

## 5.4 `duplicate_detection`

**Purpose.** The same invoice posted twice is a real and common loss.

**Responsibility.** Owns **economic duplicate detection** — whether this is the same business event by accounting effect, even if entered differently. The Input Engine already *screened* for artifact identity and recorded a fact; **screening is not deciding** ([`SYSTEM_INVARIANTS.md` INV-7](SYSTEM_INVARIANTS.md#inv-7--screening-is-not-deciding)). The judgement is made here.

**Input.** The Accounting Decision · transaction identifiers · history references — previously posted transactions and audit records.

**Output.** The **Duplicate Detection Result** — duplicate probability · duplicate evidence · duplicate confidence.

**Boundary.** Can compare, search, detect. Cannot delete, merge, reverse or amend any record · **ignore duplicates** · decide what to do about one — it reports the match; `validation_decision` decides.

**Failure Behaviour.** If uncertain, flag possible duplicate. **Never silently allow duplication.** A legitimate near-duplicate — a monthly retainer at the same amount from the same vendor — is reported with its match strength, not suppressed.

---

## 5.5 `risk_assessment`

**Purpose.** Some entries are correct and still should not be posted unattended.

**Responsibility.** Owns the **Risk Assessment** — what *posting this* would expose the business to: compliance exposure, materiality, reversibility, audit visibility. Distinct from Engine 3's **Accounting Risk Analysis**, which rates the reasoning rather than the consequences.

**Input.** All previous validation results, plus the Accounting Risk Analysis produced by the Accounting Engine's `risk_analysis`.

**Output.** The **Risk Assessment** — risk level · severity · affected areas · confidence · recommendation.

**Boundary.** Can classify, score, prioritise. Cannot approve execution · reject execution · rewrite previous outputs · re-derive the decision's internal risk — it consumes `risk_analysis` rather than repeating it. Cannot reason about accounting treatment. **It rates; `validation_decision` decides.**

**Failure Behaviour.** **Unknown risk defaults to higher severity.** An unassessed risk is never a zero risk.

**Its output path.** This sub-engine cannot approve or reject. Its recommendation is what `validation_decision` converts into **Approved With Warning** — the status for a decision that is correct but whose consequences warrant a human. Without that status this sub-engine has no output route.

---

## 5.6 `validation_decision`

**Purpose.** Five opinions must become one answer.

**Responsibility.** Owns the **Validation Decision** — the single status, and the naming of the engine responsible for every finding.

**Input.** All Validation Results — Data, Accounting, Tax, Duplicate Detection, Risk Assessment.

**Output.** The **Validation Decision** — Validation ID · Transaction ID · Related Decision ID · Related Artifact Version · Validation Status · findings · errors · warnings · risks · failed validation rules · supporting evidence references · Validation Confidence · reasoning · timestamp.

**Validation Status.** `Approved` · `Approved With Warning` · `Clarification Required` · `Rejected`. **The last two are not interchangeable** — the first of them says the reasoning is sound and the consequences warrant a human; the second says the reasoning is incomplete.

**Boundary.** Can assemble, report, publish. Cannot override sub-engine outputs · **hide failures** · remove uncertainty · create accounting decisions · amend a decision · post · approve while a Critical finding stands · return a rejection without naming the responsible engine · ask the human questions — a case needing questions returns to the Clarification Engine. It **creates** the artifact but does not **own** it — the Validation Engine does.

**Failure Behaviour.** Every blocking issue must appear inside the Validation Decision. **No approval exists while a Critical finding remains**, and every rejection names the responsible engine and the recommended next step.

---

## Permission validation

> **The Accounting Engine decides the correct accounting treatment. The Validation Engine decides whether execution is legally permitted.**

A closed accounting period, a statutory lock or an exceeded authorisation limit is a **Critical** finding in `data_validation`, raised **before execution begins**. Execution must never discover that posting was impossible — [`SYSTEM_INVARIANTS.md` INV-8](SYSTEM_INVARIANTS.md#inv-8--permission-to-execute-is-decided-before-execution).

---

# 6. Execution Engine

> **Specification locked.** Deep authority: [`ENGINE_6_EXECUTION_ENGINE_RULES.md`](ENGINE_6_EXECUTION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_EXECUTION_INTERNAL.md`](COMMUNICATION_RULES_EXECUTION_INTERNAL.md).
>
> **Name and folder.** The architectural name is **Execution Engine**; the locked folder is [`src/engines/tally_engine/`](../src/engines/tally_engine/). Identities are part of the system contract and are never renamed — the folder stays. Same case as `tally_connector` below.
>
> **Engine 6 transports approved decisions. It cannot create, modify or interpret business meaning.** Reasoning ended at Validation.
>
> **It is the only engine that touches the outside world** — Tally, Zoho, Busy, SAP, QuickBooks, portals, APIs, webhooks, email, WhatsApp, notifications, file exports. No earlier engine may.

## 6.1 `voucher_translator`

**Purpose.** A destination system has its own representation, and something must speak it.

**Responsibility.** Owns **translation only** — the faithful conversion of an approved Accounting Decision into the destination's voucher representation, with format mapping, field mapping and export structure.

**Input.** Accounting Decision · Validation Decision · Destination System.

**Output.** The **Translated Voucher**, together with the mapping from each decision element to each payload element.

**Boundary.** Can map fields, convert formats, generate the destination-specific voucher, verify required destination fields exist. Cannot change accounting treatment · ledger selection · journal entries · tax treatment · **the accounting meaning of what it translates**. Cannot supply a value the decision left undecided — a missing value is a translation error, not a gap to fill. Cannot choose between two representations on accounting grounds.

**Failure Behaviour.** Stop execution · preserve the Accounting Decision · report translation failure · **never invent missing values**.

---

## 6.2 `tally_connector`

> **Locked folder name retained. Architecturally the destination connector** — its responsibility covers all external accounting systems, not Tally alone. **Identities are stable; responsibilities are not.**

**Purpose.** The connection to an external system is its own concern, with its own failures.

**Responsibility.** Owns **connection, transmission and acknowledgement** — external connections, authentication, API communication, connector sessions, and connection state.

**Input.** The Translated Voucher, and connection configuration.

**Output.** The **Connection Result** — a working channel, connection state, and transport-level results.

**Boundary.** Can connect, authenticate, send, receive, disconnect safely. Cannot inspect, interpret or modify a payload passing through it · change accounting · **retry endlessly** · skip authentication · ignore connection failures · **reason**. Cannot judge whether a response means success — that is `response_processor`.

**Failure Behaviour.** Report failure · hand control to `error_handler` · **preserve execution state**.

---

## 6.3 `posting_manager`

**Purpose.** Posting the same entry twice is worse than not posting it at all.

**Responsibility.** Owns **idempotency, execution lifecycle, and retry of transport failures** — plus posting control, ordering and queue coordination.

**The idempotency key.**

```text
Idempotency Key = Accounting Decision ID + Decision Version + Destination System
```

**Decision Version** determines *what* is executed — so a correction, being a new version, posts, while a retry of the same version never does. **Destination System** determines *where* — so one approved decision may legitimately reach two destinations, each independently protected. **Transaction ID is never part of the key**: it represents the complete business event and must never block a legitimate execution.

**Input.** Connection Result · Translated Voucher.

**Output.** The **Posting Result** — post attempts and their outcomes, with the guarantee that each approved decision version reaches each destination at most once. *Internal to Engine 6; it becomes the Posting Status component of the Execution Result and never crosses an engine boundary.*

**Boundary.** Can execute posting, retry per policy, queue, resume, prevent duplicate execution. Cannot post duplicates · change payload content · change accounting decisions · ignore retry policy · bypass Validation · decide *whether* posting should happen — Validation decided that. **Cannot restart crashed workflows** — that is the Application Layer. Reposting a transport-failed voucher is Engine 6; restarting a crashed engine is not.

**Failure Behaviour.** Retry automatically; if retries fail, **queue safely and notify the user**. **Never lose the validated transaction. Never execute twice accidentally.**

---

## 6.4 `response_processor`

**Purpose.** *"The system replied"* and *"the entry is in the books"* are not the same statement.

**Responsibility.** Owns **success/failure interpretation** — turning what the destination returned into one definite outcome (posted, rejected, or partial), with the identifiers it assigned.

**Input.** The External Response, and the corresponding post attempts.

**Output.** The **Processed Execution Result** — outcome, external transaction identifiers, and the raw response it was derived from.

**Boundary.** Can interpret response codes, extract transaction IDs, record posting status, detect successful execution. Cannot rewrite responses · ignore failures · retry or resubmit · modify accounting decisions · **increase accounting confidence** · change business decisions. Cannot classify or route a failure — that is `error_handler`.

**Failure Behaviour.** **Unknown responses remain visible. Never assume success. Never invent external IDs.** An ambiguous or absent response is never read as success.

---

## 6.5 `error_handler`

**Purpose.** A failed post has a cause, and the cause determines who must fix it.

**Responsibility.** Owns **error category, severity, and responsible stage identification** — transport, destination rejection, data defect or translation defect — plus retry decisions, queue decisions and user notification triggers.

**It names; it does not route.** The **Classified Error** carries the responsible stage as a *field* and becomes a component of the Execution Result. The **Application Layer** reads it and routes, because workflow is its property. **Engine 6 therefore has no backward arrow** — [`DATA_FLOW.md` §5](DATA_FLOW.md#5-flow-rules) rule 1 holds through the last engine in the pipeline.

**Input.** Failed Execution · Failed Connection · Failed Posting · Failed Response.

**Output.** The **Error Resolution Result**, containing the **Classified Error**: category, cause, severity, whether retry is permissible, and the responsible stage.

**Boundary.** Can classify, retry, queue, notify, stop execution safely. Cannot ignore or **hide failures** · delete failed executions · correct data · re-decide anything · modify accounting · override Validation · **route work to another engine**. Cannot suppress an error it cannot classify — an unclassifiable error is recorded *as unclassifiable*, with a notification trigger.

**Failure Behaviour.** **Every failure remains permanently visible. Execution never silently disappears. Users always receive execution status.**

---

## 6.6 `audit_logger`

**Purpose.** The books must be defensible, which means the trail must be complete.

**Responsibility.** Owns **audit linkage** — the append-only record of every execution event: execution history, retry history, queue history, notification history and external response history.

**Input.** **All execution events.** It observes throughout the chain; it is last only in *assembly* order.

**Output.** The **Audit Record** — permanent, **append-only history rather than a versioned artifact**. One per Execution ID, reached through the Execution Result's `Audit Reference` and never crossing an arrow itself.

**Boundary.** Can record events, retries, failures, notifications, timestamps, destination systems, operator actions. Cannot delete or **rewrite history** · alter a record once written · omit failures, retries or partial outcomes · modify previous audit records · summarise away detail needed to reconstruct what happened.

**Failure Behaviour.** If logging cannot complete: **execution status remains visible · failure is reported immediately · no audit record may be silently lost.**

---

## The Execution Result

Engine 6 publishes exactly one artifact, assembled by the **parent Execution Engine** — the only engine where the parent creates the outbound artifact, because its assembly draws on every stage and no single sub-engine sees the whole chain.

```text
Execution Result
├── Execution ID · Execution Attempt ID     identity only
├── Transaction ID                          lifecycle grouping only
├── Accounting Decision ID · Decision Version · Validation Decision ID
├── Destination System
├── Corrects Execution Result               lineage; empty unless a correction
├── Posting Status                          from posting_manager
├── External Transaction ID(s)
├── Retry Count · Queue Status · Notification Status
├── Classified Error                        from error_handler
├── Audit Reference                         points at the append-only Audit Record
├── Execution Outcome
├── Execution Confidence                    transport success only
└── Execution Timestamp
```

**Execution Attempt ID** exists because one decision version may be attempted many times — *destination unavailable*, then *posted*. It tracks attempts and **is not a business identity**.

**Corrects Execution Result** answers *"which execution corrected which previous execution?"* structurally. **No existing Execution Result is ever edited.**

---

# Ownership Collisions

Four pairs of sub-engines have similar names and adjacent concerns. Each pair is separated by a single sharp distinction. These are the boundaries most likely to erode during implementation, so they are stated explicitly.

| Pair | Separation |
|---|---|
| Understanding `business_context` **vs** Accounting `company_understanding` | `business_context` owns the *operating* reality of the business — recurring party, normal pattern, branch, trade. `company_understanding` owns the *accounting* reality — chart of accounts, ledger masters, registrations, policy, financial year. Operations versus configuration. |
| Accounting `risk_analysis` **vs** Validation `risk_assessment` | `risk_analysis` looks **inward**: how risky is the decision I just made — how aggressive, how thin its basis. `risk_assessment` looks **outward**: what would posting this expose the business to — compliance, materiality, reversibility. It consumes `risk_analysis` rather than repeating it. |
| Accounting `doubt_detection` **vs** Clarification `uncertainty_detection` | `doubt_detection` **produces** doubt, from accounting reasoning only, and names the fact that would resolve each. `uncertainty_detection` **triages** uncertainty across the whole case — extraction, story and accounting — and judges which are material enough to block posting. Production versus materiality. |
| Accounting `ledger_intelligence` **vs** `journal_intelligence` | `ledger_intelligence` decides **which accounts**. `journal_intelligence` decides **which side and how much**. Neither does the other's job; `journal_intelligence` consumes the account selection as given. |

## Layered confidence

Confidence is measured at every stage. Each level answers about its own engine's responsibility, and none replaces another — all of them travel.

| Confidence | Owner | Lives in | Measures |
|---|---|---|---|
| **Evidence confidence** | Input Engine | Confidence Report, within the Document Evidence Object | Was this read correctly? |
| **Understanding confidence** | Understanding Engine | Confidence Assessment, within the Business Understanding Object | Does the evidence support this interpretation? |
| **Decision confidence** | Accounting Engine | Decision confidence, within the Accounting Decision | Is the accounting treatment likely correct? |
| **Clarification confidence** | Clarification Engine | Clarification Confidence, within the Clarification Request | Has every decision-blocking uncertainty been found? |
| **Validation confidence** | Validation Engine | Validation Confidence, within the Validation Decision | Is execution safe and permitted? |
| **Execution confidence** | Execution Engine | Execution Confidence, within the Execution Result | Did execution succeed? **Transport only — never accounting correctness.** |

Two rules bind them:

- **`Understanding Confidence ≤ Evidence Reliability`** — the arithmetic bound locked with Engine 2.
- **Confidence is recalculated whenever evidence changes** — [`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes). It may increase, decrease or stay the same given the complete evidence set. It never rises because an engine reasoned harder; corroboration raises it only through added **independent** evidential support. New evidence is what the Clarification Engine exists to obtain.
- **Execution Confidence sits outside the chain.** It measures transport, never accounting, and never alters any confidence above it.

## Two risk artifacts

| Artifact | Owner | Measures |
|---|---|---|
| **Accounting Risk Analysis** — from `risk_analysis` | Accounting Engine | Risk in the **reasoning**: how aggressive the treatment, how thin its basis |
| **Risk Assessment** — from `risk_assessment` | Validation Engine | Risk in **approving and executing**: exposure, materiality, reversibility |

Two engines may not own the same concept name, which is why Accounting's output is deliberately *not* called a Risk Assessment.

## Dates versus periods

| Component | Statement |
|---|---|
| Understanding `timeline_understanding` | *"This event happened on this date."* |
| Accounting `accounting_rules` | *"This event belongs to this accounting period."* |

An invoice dated 31 March and paid 10 April raises the question of March closing versus April. That is an accounting decision, not a timeline fact — which is why `timeline_understanding` is forbidden from answering it and `accounting_rules` owns accounting period treatment.

## Evidence origin — extracted versus provided

Every fact carries a **Source Type**, and the distinction survives the whole pipeline.

| Source Type | Read or asserted | Examples | Checkable against |
|---|---|---|---|
| **Document** | Read off an artifact — *extracted* | Invoice fields, table rows, handwriting | The artifact itself |
| **Human** | Asserted by a person — *provided* | The optional Human Business Description | Nothing — only corroboration |
| **Structured Metadata** | Supplied by a system — *provided* | Upload metadata, file attributes | Nothing — only corroboration |

**No engine may merge these origins into a single anonymous fact.** Something read off an artifact can be re-checked against it; something asserted cannot. See [`DATA_FLOW.md` §12](DATA_FLOW.md#12-evidence-provenance).

## Capture confidence versus truth confidence

| For | Confidence measures |
|---|---|
| Extracted evidence | How reliably it was **read** |
| Provided evidence | How faithfully it was **captured** |

Neither measures whether the content is **true**.

```text
User typed:          "Advance paid to supplier."
Capture confidence:  100%      the system stored exactly what was typed
Truth confidence:    unknown   until supported by other evidence
```

**A human note must never increase Evidence Reliability simply because it exists.** It can improve understanding once corroborated; it can never independently raise confidence.

## Three places gaps are named

Absence is recorded at three stages, and each records a different kind.

| Component | Records | The gap is |
|---|---|---|
| Input `parser` | **missing field information** | A field the document does not contain |
| Understanding `story_builder` | **Identified Unknowns** | A business fact the evidence does not establish |
| Clarification `missing_information` | **Missing Information Result** | Information the *accounting decision* needs and does not have |

They narrow as they descend: the document lacks a field · the story lacks a fact · the decision lacks what it needs to be safe. A field can be missing without the story caring; a fact can be unknown without the decision depending on it. Only the third is a candidate for a Clarification Request, and only after `stop_decision` judges it necessary.

## Conflicts are detected twice, for different reasons

| Component | Detects | Between |
|---|---|---|
| Understanding `story_builder` | Contradictions in the business story | The six Understanding Results |
| Clarification `understanding` | Contradictions across the pipeline | Evidence, understanding **and** the accounting decision |

Neither resolves. The first asks *do the facts disagree with each other?*; the second asks *does the decision disagree with the facts it was built on?*
