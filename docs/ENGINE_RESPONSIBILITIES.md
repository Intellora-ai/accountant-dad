# Engine Responsibilities

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

Sub-engines: `cleaner` · `reader` · `parser` · `confidence`

### Inputs
- A raw artifact as received: scan, photograph, PDF, or digital file.
- Nothing else. The Input Engine has no knowledge of the company, its books, or its history.

### Outputs
- **Structured Document** — the artifact's contents as fields, tables and rows, faithful to what is written.
- **Confidence Report** — per-field and overall trust scores, plus the specific regions that are weak.

### Cannot Do
- Cannot make accounting decisions of any kind.
- Cannot interpret business meaning — it may extract a name, it may not conclude the name is a supplier.
- Cannot correct, complete or "improve" content it believes is wrong. It reports low confidence instead.
- Cannot discard content it judges irrelevant.
- Cannot consult company master data, prior transactions, or any downstream engine.

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
- Structured Document and Confidence Report, from the Input Engine.

### Outputs
- **Transaction Story** — a complete, accounting-free description of what happened, with every fact traceable to the document or explicitly marked absent.

### Cannot Do
- Cannot select ledgers, accounts or voucher types.
- Cannot determine tax treatment, rates, or eligibility.
- Cannot produce a journal entry or any debit/credit.
- Cannot invent facts to fill a gap — an absent fact is recorded as absent.
- Cannot re-read or re-extract the artifact; if the extraction is inadequate it says so, it does not go back to the source.
- Cannot use accounting vocabulary to describe business events.

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
- The company's accounting reality that constrains all of the above.
- An honest statement of how risky the resulting decision is.
- An honest statement of where the decision is uncertain, and what fact would resolve it.
- The assembly of all of the above into one decision artifact.

Sub-engines: `transaction_analyzer` · `accounting_rules` · `ledger_intelligence` · `journal_intelligence` · `tax_intelligence` · `company_understanding` · `risk_analysis` · `doubt_detection` · `decision_output`

### Inputs
- Transaction Story, from the Understanding Engine.
- Resolved Facts, when the Clarification Engine returns answers.

### Outputs
- **Accounting Decision** — ledgers, journal entry, tax treatment, the reasoning behind them, the risks they carry, and the doubts that remain.

### Cannot Do
- Cannot post to Tally, or communicate with Tally in any way.
- Cannot ask the user a question directly.
- Cannot approve its own decision, or declare it safe.
- Cannot read the raw artifact or the Structured Document — it reasons from the Transaction Story only.
- Cannot resolve its own doubt by guessing, defaulting, or picking the most common treatment.
- Cannot validate itself; correctness is judged by the Validation Engine.

---

## 4. Clarification Engine

### Mission
Resolve doubt by asking the human the fewest, sharpest questions, then update the decision.

### Owns
- Comprehension of the case and the doubts attached to it.
- The judgement of which uncertainties across the whole case are material enough to block posting.
- Identification of exactly what facts are missing and who or what could supply them.
- The wording, ordering and minimality of the questions put to the human.
- Interpretation of the human's answers into structured facts.
- Carrying resolved facts back so the decision is remade.
- The judgement of when questioning is complete.

Sub-engines: `understanding` · `uncertainty_detection` · `missing_information` · `question_generator` · `answer_understanding` · `decision_updater` · `stop_decision`

### Inputs
- Accounting Decision, including its doubts and risks.
- Confidence Report and Transaction Story, as evidence of where uncertainty originated.
- The human's answers.

### Outputs
- **Question Set** — the minimal set of questions put to the human.
- **Resolved Facts** — the human's answers, structured, returned to the Accounting Engine.
- **Clarification Outcome** — whether questioning is complete, and why.

### Cannot Do
- Cannot invent, assume or default an answer the human did not give.
- Cannot decide accounting treatment; it applies answers, it does not author judgement.
- Cannot mark a decision correct, approved or safe.
- Cannot raise uncertainty that has no evidence upstream.
- Cannot post to Tally.
- Cannot ask the human to make the accounting decision on the system's behalf.

---

## 5. Validation Engine

### Mission
Judge whether the decision is safe to post — correctness, tax, data integrity, duplicates, risk.

### Owns
- Whether the entry is accounting-correct: balanced, correctly signed, posted to appropriate heads, consistent with the rules invoked.
- Whether the tax treatment is compliant and internally consistent.
- Whether the underlying data are sound: complete, in range, reconciling, referencing masters that exist.
- Whether this transaction has already been recorded.
- What posting this would expose the business to.
- The single verdict that results, and the naming of who must act on a rejection.

Sub-engines: `accounting_validation` · `tax_validation` · `data_validation` · `duplicate_detection` · `risk_assessment` · `validation_decision`

### Inputs
- Accounting Decision — original or updated after clarification.
- Supporting evidence: Transaction Story, Confidence Report, prior posted transactions.

### Outputs
- **Validation Verdict** — approve, reject, or flag for human attention.
- **Findings** — every issue detected, with severity and the stage responsible for it.

### Cannot Do
- Cannot create a decision, or any part of one.
- Cannot amend, correct or "fix up" a decision it is judging — a defect is reported, not repaired.
- Cannot recompute ledgers, entries or tax; it judges what it was given.
- Cannot post to Tally.
- Cannot ask the human questions — a case needing questions is returned to the Clarification Engine.
- Cannot pass a decision forward with an unresolved finding.

---

## 6. Tally Engine

### Mission
Execute the approved decision against Tally and record the truth of what happened.

### Owns
- Translation of an approved decision into Tally's voucher representation.
- The connection to Tally, and its state.
- The act of posting: ordering, single-post guarantee, retry policy.
- Interpretation of Tally's response into a definite outcome.
- Classification of failures and routing them to the stage that must handle them.
- The immutable record of what was sent, when, on whose decision, and what came back.

Sub-engines: `voucher_translator` · `tally_connector` · `posting_manager` · `response_processor` · `error_handler` · `audit_logger`

### Inputs
- **Approved Accounting Decision** — and nothing that has not been approved.

### Outputs
- **Posting Result** — posted, rejected or partial, with Tally's identifiers.
- **Classified Error** — where posting failed, its category and the stage that must act.
- **Audit Record** — the permanent, immutable account of the attempt and its outcome.

### Cannot Do
- Cannot reason, interpret or make any judgement about the transaction.
- Cannot alter the accounting meaning of what it was given.
- Cannot supply a value that is missing — missing data is an error, not a gap to fill.
- Cannot decide whether posting should happen; that was decided by the Validation Engine.
- Cannot correct a rejected voucher and resubmit it.
- Cannot alter, delete or omit an audit record, including records of failure.
