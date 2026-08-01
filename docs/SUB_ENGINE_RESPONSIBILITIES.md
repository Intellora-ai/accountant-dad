# Sub-Engine Responsibilities

> **This document is canonical.** Every `src/engines/*/*/README.md` mirrors the entry below; where they disagree, this document wins.
>
> 39 sub-engines. Five fixed headings each: **Purpose · Responsibility · Input · Output · Boundary.**
>
> Sub-engines belonging to an engine whose specification has been **locked** carry a sixth heading, **Failure Behaviour**. Engines 2–6 gain it as their specifications land. For those engines, the locked specification is the deeper authority on allowed and forbidden actions, output contracts and failure behaviour; this document remains canonical for the system-wide map. Where they overlap they must agree.
>
> | Engine | Specification | Status |
> |---|---|---|
> | 1. Input | [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) | **Locked** |
> | 2. Understanding | [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) | **Locked** |
> | 3–6 | — | Not yet specified |
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

**Input.** The raw artifact exactly as received: photo, camera capture, image upload, PDF, scan, handwritten note, or other digital file — including poor-quality human inputs.

**Output.** Cleaned document representation · quality issues detected · preservation status.

**Boundary.** Cannot interpret the meaning of anything on the artifact. Cannot discard content it judges irrelevant, redundant or illegible. Cannot change numbers, correct accounting information, or alter original meaning — it alters presentation only.

**Failure Behaviour.** If processing may damage information, preserve the original input and mark uncertainty. The original artifact is never discarded, so a damaging transformation is always recoverable. Preservation status records whether the cleaned representation or the original is the safer basis for reading. Detected quality issues are reported as evidence for `confidence`, never repaired by guesswork.

---

## 1.2 `reader`

**Purpose.** Somebody must actually get the characters off the page.

**Responsibility.** Owns extraction of everything written on the cleaned document representation — printed text and handwriting alike — together with where on the page each piece of text sits.

**Input.** The cleaned document representation from `cleaner`.

**Output.** Raw extracted information (text, numbers, dates, names, tables, handwriting output) · source locations · extraction confidence.

**Boundary.** Cannot assign meaning to what it extracts — it may extract `27AAECS1234F1Z5`, it may not conclude that this is a GSTIN. Cannot understand transaction meaning, fix accounting mistakes, guess unclear words, or infer missing business information. Cannot reorder or restructure the text.

**Failure Behaviour.** Return extracted information with confidence levels and uncertainty. An unclear character or word is emitted as unclear, with its confidence, never resolved by guessing. A region that could not be read at all is reported as unread, not omitted silently. Source locations are emitted even for low-confidence extractions — that is what makes a later human check possible.

---

## 1.3 `parser`

**Purpose.** Loose text is not usable; the document's own structure must be recovered.

**Responsibility.** Owns the conversion of extracted information into structure — fields, key–value pairs, tables, and line-item rows — faithful to how the document is laid out.

**Input.** Raw extracted information with source locations from `reader`.

**Output.** Structured fields · field mappings · missing field information. Together these form the **Structured Document**, a component of the Document Evidence Object.

**Boundary.** Cannot decide business meaning — it may identify a field labelled "Supplier", it may not conclude that party is a supplier for accounting purposes. Cannot decide debit or credit, choose ledger accounts, apply accounting rules, or create transaction meaning. Cannot compute, derive or infer a value that is not written. Cannot fill a field that is absent.

**Failure Behaviour.** Unknown fields remain unknown; never fabricate values. A field that is absent is recorded in missing field information as absent — not defaulted, not estimated, not omitted. "Absent", "zero" and "unreadable" are three different states and must remain distinguishable. Field mappings retain the source reference for every mapped value, so a wrong mapping can be traced.

---

## 1.4 `confidence`

**Purpose.** Every downstream engine needs to know how much of this extraction to trust.

**Responsibility.** Owns the honest measurement of extraction trustworthiness, per field and overall, and the identification of the specific regions and fields that are weak.

**Input.** The outputs of `cleaner`, `reader` and `parser`.

**Output.** Confidence scores · uncertainty markers · reliability assessment. Together these form the **Confidence Report**, a component of the Document Evidence Object.

**Boundary.** Cannot re-read, re-parse or correct anything. Cannot increase confidence without evidence, hide uncertainty, or make accounting decisions. Cannot reject a document or halt the pipeline. Cannot use business plausibility as evidence — it measures extraction quality, not whether the content makes commercial sense.

**Failure Behaviour.** Reduce confidence and explain the uncertainty. Where reliability cannot be established, confidence goes down — never up, and never to a default "good enough" value. Every uncertainty marker carries a reason; a bare score cannot become a good question downstream. Uncertainty is never suppressed because it would delay processing.

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

**Input.** The Document Evidence Object.

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

## 3.1 `transaction_analyzer`

**Purpose.** A business story must first be read as an economic event before treatment can be considered.

**Responsibility.** Owns determination of the economic substance of the transaction in accounting terms — what was acquired or disposed of, what obligation arose or was discharged, and which accounting event class it belongs to.

**Input.** The Business Understanding Object.

**Output.** An accounting characterisation of the event: substance, event class, and the aspects requiring treatment.

**Boundary.** Cannot select specific ledgers or write any entry. Cannot read the Document Evidence Object or the raw artifact. Cannot re-derive business facts — it consumes the understanding as given.

---

## 3.2 `accounting_rules`

**Purpose.** Treatment must follow principle, not habit.

**Responsibility.** Owns the body of accounting principles and policies that govern treatment — double entry, revenue and expense recognition, capital versus revenue, matching, accrual — and the determination of which apply to this event.

**Input.** The accounting characterisation from `transaction_analyzer`, and the company's accounting profile.

**Output.** The applicable rule set, and the ruling each rule produces for this transaction.

**Boundary.** Cannot invent a rule from the transaction in front of it. Cannot own tax rules — GST, ITC and TDS belong to `tax_intelligence`. Cannot select ledgers or construct entries.

---

## 3.3 `ledger_intelligence`

**Purpose.** An entry is only as correct as the accounts it touches.

**Responsibility.** Owns selection of the ledger accounts involved, their groups, and the determination that an existing master is inadequate and a new ledger is required.

**Input.** The accounting characterisation, the applicable rulings, and the company's chart of accounts and existing masters.

**Output.** Ledger selection: each account involved, its group, and — where required — a specification for a ledger that does not yet exist.

**Boundary.** Cannot create a ledger in Tally or anywhere else; it specifies, it does not provision. Cannot compute amounts. Cannot decide the debit/credit direction — that is `journal_intelligence`.

---

## 3.4 `journal_intelligence`

**Purpose.** The double entry is the decision's core; it must balance and mean what it says.

**Responsibility.** Owns construction of the entry itself — which accounts are debited, which credited, in what amounts — and the guarantee that it balances.

**Input.** Ledger selection from `ledger_intelligence`, the applicable rulings, tax lines from `tax_intelligence`, and the amounts in the Business Understanding Object.

**Output.** The journal entry: a balanced, system-neutral set of debit and credit lines.

**Boundary.** Cannot select the accounts itself — it consumes `ledger_intelligence`'s selection. Cannot determine tax amounts — it consumes `tax_intelligence`'s lines. Cannot format for Tally. Cannot force a balance by inserting a plug figure.

---

## 3.5 `tax_intelligence`

**Purpose.** Tax treatment is a distinct discipline with its own rules and its own consequences.

**Responsibility.** Owns the transaction's tax treatment — GST applicability, rate and classification, place of supply, reverse charge, input tax credit eligibility, and TDS.

**Input.** The accounting characterisation, item facts and party facts from the story, and the company's registration and tax profile.

**Output.** Tax treatment and the resulting tax lines, each with the basis on which it was determined.

**Boundary.** Cannot validate its own compliance — that is the Validation Engine's `tax_validation`. Cannot file, report or reconcile anything with a tax authority. Cannot choose a rate because it is the most common one.

---

## 3.6 `company_understanding`

**Purpose.** Every decision above is constrained by the accounting reality of this specific company.

**Responsibility.** Owns knowledge of the company's accounting configuration — chart of accounts, existing ledger and group masters, GST registrations, method and basis of accounting, financial year, and book conventions.

**Input.** The company's accounting configuration and master data.

**Output.** The company accounting profile that constrains every other Accounting sub-engine.

**Boundary.** Cannot decide treatment for a transaction. Cannot create or modify a master. Cannot own the business's *operating* context — recurrence, branch and trade pattern belong to the Understanding Engine's `business_context`.

---

## 3.7 `risk_analysis`

**Purpose.** A decision that is defensible and a decision that is risky are different things, and the difference must be stated.

**Responsibility.** Owns assessment of how risky *the decision this engine just made* is — how aggressive the treatment is, how thin its basis, how unusual the amount or pattern, how much it depends on a contested reading.

**Input.** The assembled components of the decision, the rulings behind them, and the Business Understanding Object.

**Output.** A risk profile of the decision: each risk, its source, and its severity.

**Boundary.** Cannot block, approve or gate anything. Cannot assess the consequences of *posting* — exposure, materiality and reversibility belong to the Validation Engine's `risk_assessment`. Cannot change the decision to reduce its own risk score.

---

## 3.8 `doubt_detection`

**Purpose.** Guessing quietly is the worst failure this system could have; doubt must be produced as an output.

**Responsibility.** Owns identification of every point at which the accounting decision is uncertain, and the precise statement of what fact would remove each doubt.

**Input.** The decision components, the rulings, the Identified Unknowns in the Business Understanding Object, and the Confidence Report within the Document Evidence Object.

**Output.** Structured doubts: what is uncertain, why, and the specific fact that would resolve it.

**Boundary.** Cannot ask the user anything. Cannot resolve its own doubt by guessing, defaulting, or selecting the most common treatment. Cannot suppress a doubt because it is inconvenient or would delay posting. Cannot judge which doubts matter enough to block posting — that is the Clarification Engine's `uncertainty_detection`.

---

## 3.9 `decision_output`

**Purpose.** Downstream engines must receive one decision, not nine partial opinions.

**Responsibility.** Owns assembly of the complete **Accounting Decision** — entry, ledgers, tax treatment, reasoning, risks and doubts — as a single coherent artifact.

**Input.** The outputs of all eight preceding Accounting sub-engines.

**Output.** The **Accounting Decision**.

**Boundary.** Cannot alter, reconcile or soften any component it assembles. Cannot post the decision. Cannot mark it approved, safe or final. Cannot omit doubts or risks from the assembled artifact.

---

# 4. Clarification Engine

## 4.1 `understanding`

**Purpose.** You cannot ask a good question about a case you do not understand.

**Responsibility.** Owns comprehension of the accounting decision and its attached doubts — what was decided, on what basis, and what the doubts actually concern — in terms a human can be spoken to about.

**Input.** The Accounting Decision, including its doubts and risks, plus the Business Understanding Object for context.

**Output.** An internal case understanding: the decision restated in plain terms, with each doubt located in it.

**Boundary.** Cannot change the decision. Cannot form an accounting judgement of its own. Cannot dispute the decision's correctness — that is the Validation Engine's role.

---

## 4.2 `uncertainty_detection`

**Purpose.** Not every uncertainty is worth a human's attention; asking about all of them is as bad as asking about none.

**Responsibility.** Owns the judgement of which uncertainties *across the whole case* — extraction confidence, story gaps, accounting doubts — are material enough to block posting, and their relative priority.

**Input.** The case understanding, the accounting doubts, the Identified Unknowns in the Business Understanding Object, and the Confidence Report within the Document Evidence Object.

**Output.** Ranked material uncertainties, each with the reason it blocks posting.

**Boundary.** Cannot resolve an uncertainty. Cannot raise an uncertainty that has no evidence upstream. Cannot detect *accounting* ambiguity itself — it consumes what `doubt_detection` produced and judges materiality.

---

## 4.3 `missing_information`

**Purpose.** A question is only answerable if the missing fact and its holder are known.

**Responsibility.** Owns determination of exactly which facts are absent, and who or what could supply each — the user, the source document, a party, or company master data.

**Input.** Ranked material uncertainties, the Identified Unknowns in the Business Understanding Object, and the company accounting profile.

**Output.** A missing-fact list: each absent fact, why it is needed, and its likely source.

**Boundary.** Cannot fabricate, default or estimate a missing value. Cannot fetch the fact itself. Cannot declare a fact missing that is present but merely low-confidence — that is an uncertainty, not an absence.

---

## 4.4 `question_generator`

**Purpose.** The human's time is the scarcest resource in the system.

**Responsibility.** Owns the wording, ordering and minimality of what is put to the human — the fewest questions that resolve the most blocking uncertainty, phrased so the person who has the answer can give it.

**Input.** Ranked material uncertainties and the missing-fact list.

**Output.** The **Question Set** — each question, what it resolves, and the form of answer expected.

**Boundary.** Cannot ask about anything already known or already answered. Cannot ask in accounting jargon the respondent cannot be expected to answer. Cannot ask the human to choose the accounting treatment on the system's behalf. Cannot ask a question whose answer would change nothing.

---

## 4.5 `answer_understanding`

**Purpose.** A human's reply is prose; the system needs facts.

**Responsibility.** Owns interpretation of the human's answers into structured facts, and the judgement of whether each answer actually addresses the question asked.

**Input.** The Question Set and the human's replies.

**Output.** **Resolved Facts** — structured, attributed to the question they answer — plus any question left unanswered or answered inadequately.

**Boundary.** Cannot infer beyond what was said. Cannot accept a non-answer as an answer. Cannot correct or complete an answer it finds implausible — it records the answer and flags the implausibility.

---

## 4.6 `decision_updater`

**Purpose.** An answer is worthless until it changes the decision.

**Responsibility.** Owns carrying resolved facts back so that the decision is remade under the Accounting Engine's authority, and recording the difference between the decision before and after.

**Input.** Resolved Facts, and the Accounting Decision as it stood.

**Output.** The **Updated Accounting Decision**, together with a record of what changed and which answer caused it.

**Boundary.** Cannot author accounting treatment — it applies answers, the Accounting Engine decides. Cannot edit a decision's reasoning in place, or silently overwrite it. Cannot discard a doubt that the answers did not actually resolve.

---

## 4.7 `stop_decision`

**Purpose.** Asking forever is its own failure mode.

**Responsibility.** Owns the judgement of when questioning ends — because clarity is sufficient, because further questions would not change the decision, or because the human cannot supply what is needed.

**Input.** The state of the material uncertainties, the answers received, and the questions already asked.

**Output.** The **Clarification Outcome** — continue or stop, the reason, and any uncertainty that remains unresolved.

**Boundary.** Cannot stop by declaring the decision correct or safe — it concludes only that questioning is complete. Cannot conceal an unresolved uncertainty when stopping. Cannot continue questioning where no question would change the outcome.

---

# 5. Validation Engine

## 5.1 `accounting_validation`

**Purpose.** A decision must be checked by something that did not make it.

**Responsibility.** Owns the judgement of whether the entry is accounting-correct — balanced, correctly signed, posted to appropriate heads, and consistent with the rules its own reasoning invoked.

**Input.** The Accounting Decision, including its stated reasoning and rulings.

**Output.** An accounting verdict with findings: each defect, its severity, and where in the decision it sits.

**Boundary.** Cannot fix, rewrite or adjust the entry. Cannot substitute its own preferred treatment for a defensible one. Cannot judge tax treatment — that is `tax_validation`.

---

## 5.2 `tax_validation`

**Purpose.** Tax errors are the ones that come back years later.

**Responsibility.** Owns the judgement of whether the tax treatment is compliant and internally consistent — rate against classification, place of supply against parties, ITC eligibility against the stated basis, TDS against applicability.

**Input.** The tax treatment and tax lines from the decision, the party and item facts, and the company's tax profile.

**Output.** A tax verdict with findings.

**Boundary.** Cannot recompute or change a tax amount. Cannot select a different treatment. Cannot file or report anything.

---

## 5.3 `data_validation`

**Purpose.** A perfectly reasoned entry built on broken data is still broken.

**Responsibility.** Owns the judgement of whether the underlying data are sound — required fields present, dates within permissible range and sequence, totals reconciling to their lines, and every referenced master actually existing.

**Input.** The Accounting Decision, the Business Understanding Object, the Confidence Report within the Document Evidence Object, and the company's master data.

**Output.** A data verdict with findings.

**Boundary.** Cannot correct, complete or normalise any data. Cannot judge whether the accounting treatment is right. Cannot lower a requirement because the data cannot meet it.

---

## 5.4 `duplicate_detection`

**Purpose.** The same invoice posted twice is a real and common loss.

**Responsibility.** Owns the judgement of whether this transaction has already been recorded — by document identity, by party and amount and date, or by economic equivalence.

**Input.** The Accounting Decision and Business Understanding Object, and previously posted transactions and audit records.

**Output.** A duplicate verdict with any matches found and the strength of each match.

**Boundary.** Cannot delete, merge, reverse or amend any existing record. Cannot decide what to do about a duplicate — it reports the match; `validation_decision` decides.

---

## 5.5 `risk_assessment`

**Purpose.** Some entries are correct and still should not be posted unattended.

**Responsibility.** Owns the judgement of what *posting this* would expose the business to — compliance exposure, materiality, reversibility, and audit visibility.

**Input.** The Accounting Decision, the risk profile produced by the Accounting Engine's `risk_analysis`, and the findings of the other validators.

**Output.** A posting-risk rating with the exposures that drive it.

**Boundary.** Cannot re-derive the decision's internal risk — it consumes `risk_analysis` rather than repeating it. Cannot reason about accounting treatment. Cannot block posting itself; it rates, `validation_decision` decides.

---

## 5.6 `validation_decision`

**Purpose.** Five opinions must become one answer.

**Responsibility.** Owns the single verdict — approve, reject, or flag for human attention — and the naming of the stage that must act on any rejection.

**Input.** The verdicts and findings of all five preceding validators.

**Output.** The **Validation Verdict**: the outcome, every finding that drove it, and for a rejection, the stage responsible.

**Boundary.** Cannot create or amend a decision. Cannot post. Cannot approve a decision with an unresolved finding. Cannot return a rejection without naming the stage that must handle it. Cannot ask the human questions — a case needing questions returns to the Clarification Engine.

---

# 6. Tally Engine

## 6.1 `voucher_translator`

**Purpose.** Tally has its own representation, and something must speak it.

**Responsibility.** Owns the faithful translation of an approved accounting decision into Tally's voucher representation.

**Input.** The **Approved Accounting Decision**.

**Output.** A Tally voucher payload, together with the mapping from each decision element to each payload element.

**Boundary.** Cannot alter the accounting meaning of what it translates. Cannot supply a value the decision left undecided — a missing value is a translation error, not a gap to fill. Cannot choose between two possible representations on accounting grounds.

---

## 6.2 `tally_connector`

**Purpose.** The connection to an external system is its own concern, with its own failures.

**Responsibility.** Owns the connection to Tally — transport, session, company selection, and availability.

**Input.** Connection configuration, and payloads to be transmitted.

**Output.** A working channel, connection state, and transport-level results.

**Boundary.** Cannot inspect, interpret or modify a payload passing through it. Cannot decide whether to retry. Cannot judge whether a Tally response means success — that is `response_processor`.

---

## 6.3 `posting_manager`

**Purpose.** Posting the same entry twice is worse than not posting it at all.

**Responsibility.** Owns the act of posting — ordering, the single-post guarantee, idempotency, and retry policy.

**Input.** Tally voucher payloads and the connection state.

**Output.** Post attempts and their outcomes, with the guarantee that each approved decision is posted at most once.

**Boundary.** Cannot change payload content. Cannot decide *whether* posting should happen — the Validation Engine decided that. Cannot retry a failure it has not been told is retryable by `error_handler`.

---

## 6.4 `response_processor`

**Purpose.** "Tally replied" and "the entry is in the books" are not the same statement.

**Responsibility.** Owns interpretation of what Tally returned into one definite outcome — posted, rejected, or partial — with the identifiers Tally assigned.

**Input.** Tally's raw responses and the corresponding post attempts.

**Output.** The **Posting Result**: outcome, Tally identifiers, and the raw response it was derived from.

**Boundary.** Cannot retry or resubmit. Cannot interpret an ambiguous or absent response as success. Cannot classify or route a failure — that is `error_handler`.

---

## 6.5 `error_handler`

**Purpose.** A failed post has a cause, and the cause determines who must fix it.

**Responsibility.** Owns classification of failures — transport, Tally rejection, data defect, or translation defect — and routing each to the stage that must handle it.

**Input.** Posting Results indicating failure, transport-level errors, and translation errors.

**Output.** A **Classified Error**: category, cause, whether a retry is permissible, and the stage that must act.

**Boundary.** Cannot correct data or re-decide anything. Cannot retry directly — it tells `posting_manager` whether retry is permissible. Cannot route a failure to a stage that could not have caused it. Cannot suppress an error it cannot classify.

---

## 6.6 `audit_logger`

**Purpose.** The books must be defensible, which means the trail must be complete.

**Responsibility.** Owns the immutable record of every posting attempt — what was sent, when, on which decision's authority, and what came back.

**Input.** Voucher payloads, post attempts, Posting Results, and Classified Errors.

**Output.** The **Audit Record**: permanent, append-only, and linked to the decision that authorised it.

**Boundary.** Cannot alter or delete a record once written. Cannot omit failures, retries or partial outcomes. Cannot summarise away detail that would be needed to reconstruct what happened.

---

# Ownership Collisions

Four pairs of sub-engines have similar names and adjacent concerns. Each pair is separated by a single sharp distinction. These are the boundaries most likely to erode during implementation, so they are stated explicitly.

| Pair | Separation |
|---|---|
| Understanding `business_context` **vs** Accounting `company_understanding` | `business_context` owns the *operating* reality of the business — recurring party, normal pattern, branch, trade. `company_understanding` owns the *accounting* reality — chart of accounts, ledger masters, registrations, policy, financial year. Operations versus configuration. |
| Accounting `risk_analysis` **vs** Validation `risk_assessment` | `risk_analysis` looks **inward**: how risky is the decision I just made — how aggressive, how thin its basis. `risk_assessment` looks **outward**: what would posting this expose the business to — compliance, materiality, reversibility. It consumes `risk_analysis` rather than repeating it. |
| Accounting `doubt_detection` **vs** Clarification `uncertainty_detection` | `doubt_detection` **produces** doubt, from accounting reasoning only, and names the fact that would resolve each. `uncertainty_detection` **triages** uncertainty across the whole case — extraction, story and accounting — and judges which are material enough to block posting. Production versus materiality. |
| Accounting `ledger_intelligence` **vs** `journal_intelligence` | `ledger_intelligence` decides **which accounts**. `journal_intelligence` decides **which side and how much**. Neither does the other's job; `journal_intelligence` consumes the account selection as given. |

## Two confidence artifacts

The system carries confidence in two places. They measure different things and neither replaces the other — both travel.

| Artifact | Owner | Measures | Bounded by |
|---|---|---|---|
| **Confidence Report** — within the Document Evidence Object | Input Engine | Confidence in the **extraction**: was this read correctly? | — |
| **Confidence Assessment** — within the Business Understanding Object | Understanding Engine | Confidence in the **understanding**: does the evidence support this interpretation? | The Confidence Report |

The binding constraint is the **Confidence Propagation Rule**: `Understanding Confidence ≤ Evidence Reliability`. A confident interpretation of an unreliable reading is not understanding — see [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §11](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#11-understanding-confidence-model).
