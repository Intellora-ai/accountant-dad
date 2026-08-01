# System Boundaries

> Forbidden behaviour. Every statement here is an absolute, not a guideline.
>
> The boundaries **are** the architecture. An engine that respects its inputs and outputs but crosses a boundary has broken the system just as thoroughly as one that ignores the flow entirely.
>
> If a requirement appears to demand crossing a boundary: **stop and ask.** Do not resolve it in code.

---

## Why boundaries, and not just interfaces

The value of this system is that it can be trusted with the books. Trust comes from four properties, and each is held in place by a prohibition rather than a feature:

- **It cannot silently guess** — because the engine that detects doubt is forbidden from resolving it, and the engine that asks is forbidden from inventing answers.
- **It cannot approve itself** — because the engine that decides is forbidden from validating, and the engine that validates is forbidden from deciding.
- **It cannot post something unexamined** — because execution is forbidden from reasoning, and nothing unapproved crosses into execution.
- **It cannot hide what happened** — because the audit record is append-only and failure is as loggable as success.

Remove any one prohibition and the corresponding property disappears, no matter how good the code is.

---

## 1. Input Engine

> **Specification locked.** Deeper authority: [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md).

**The Input Engine observes and structures information. It does not interpret transactions, make accounting decisions, or apply accounting rules.**

It **MUST NEVER**:

1. Decide transaction type.
2. Decide accounting treatment.
3. Select ledger accounts.
4. Create journal entries.
5. Apply tax rules.
6. Understand business intent.
7. Ask accounting questions.
8. Fill missing information by guessing.
9. Modify original financial values.

It also cannot:

- Interpret business meaning. It may extract a name, a number, a date. It may not conclude that a party is a supplier, that an amount is tax, or that a date is a due date.
- Correct, complete or improve content it believes to be wrong. Low confidence is reported, never repaired.
- Discard content it judges irrelevant, redundant or illegible.
- Consult company master data, prior transactions, or any downstream engine.
- Reject a document or halt the pipeline. It reports quality; others decide.
- Send anything but evidence. Conclusions are forbidden on the wire — see [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) Rule 1.

**The invention prohibition.** When information is unclear, the system must **report uncertainty**. It must **never invent information**. An invented value is indistinguishable downstream from an observed one, and the trustworthiness of the whole system rests on that distinction holding.

**Assembly ownership.** The Input Engine owns the internal assembly of its four sub-engines' outputs into the Document Evidence Object, and assigns the Document ID. It does **not** own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, or workflow control. No assembler sub-engine exists, and none may be added. **Document ID carries no accounting meaning and must never influence accounting decisions.**

**Per sub-engine:** `cleaner` alters presentation, never values — and preserves the original where processing may damage information. `reader` extracts, never interprets, and never guesses an unclear word. `parser` structures, never infers or computes a value that is not written — unknown fields remain unknown. `confidence` measures, never re-reads or corrects, never raises confidence without evidence, and never hides uncertainty.

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

The Input Engine extracts what exists. The Understanding Engine determines what it means.

---

## 2. Understanding Engine

**Understanding Engine cannot choose ledgers or tax treatment.**

It also cannot:

- Select accounts, groups or voucher types.
- Determine tax applicability, rates, place of supply or credit eligibility.
- Produce a journal entry, or any debit or credit.
- Invent a fact to fill a gap. An absent fact is recorded as absent.
- Resolve a contradiction by choosing a side. The contradiction travels with the story.
- Re-read or re-extract the artifact. If the extraction is inadequate, it says so.
- Describe business events in accounting vocabulary.

**Per sub-engine:** `transaction_understanding` names the business event, never the voucher type. `party_understanding` identifies parties, never their ledgers, and never merges two parties it believes identical. `item_understanding` describes what moved, never its tax rate or accounting head. `payment_understanding` describes money movement, never the cash or bank account, and never infers payment from silence. `timeline_understanding` records dates, never the accounting period or cut-off. `business_context` owns operating reality, never accounting configuration. `story_builder` assembles, never adds a fact no sub-engine produced.

---

## 3. Accounting Engine

**Accounting Engine cannot post to Tally.**
**Accounting Engine cannot question the user directly.**

It also cannot:

- Communicate with Tally in any way, for any reason.
- Approve its own decision, or declare it correct, safe or final.
- Read the raw artifact or the Document Evidence Object. It reasons from the Transaction Story only.
- Resolve its own doubt by guessing, defaulting, or selecting the most common treatment.
- Suppress a doubt or a risk because it is inconvenient, or because it would delay posting.
- Validate itself. Correctness is judged by the Validation Engine.

**Per sub-engine:** `transaction_analyzer` characterises, never selects accounts. `accounting_rules` applies principle, never invents a rule from the transaction in front of it, and never owns tax rules. `ledger_intelligence` specifies accounts, never provisions them. `journal_intelligence` builds the entry, never selects the accounts itself and never forces a balance with a plug figure. `tax_intelligence` determines treatment, never validates its own compliance and never picks a rate for being common. `company_understanding` supplies configuration, never decides treatment and never modifies a master. `risk_analysis` rates its own decision, never blocks and never changes the decision to improve its own score. `doubt_detection` produces doubt, never asks and never resolves. `decision_output` assembles, never alters a component and never omits a doubt or risk.

---

## 4. Clarification Engine

**Clarification Engine cannot invent answers.**
**Clarification Engine cannot decide accounting treatment on its own.**

It also cannot:

- Assume or default a value the human did not give.
- Mark a decision correct, approved or safe.
- Raise an uncertainty that has no evidence upstream.
- Post to Tally.
- Ask the human to make the accounting decision on the system's behalf.
- Conceal an unresolved uncertainty when it stops asking.

**Per sub-engine:** `understanding` comprehends, never changes the decision. `uncertainty_detection` judges materiality, never resolves and never detects accounting ambiguity itself. `missing_information` locates absences, never fabricates or estimates a value. `question_generator` asks minimally, never in unanswerable jargon, never about what is already known, and never a question whose answer changes nothing. `answer_understanding` interprets, never infers beyond what was said and never accepts a non-answer. `decision_updater` applies answers, never authors treatment, never edits reasoning in place and never discards a doubt the answers did not resolve. `stop_decision` ends questioning, never declares the decision correct.

---

## 5. Validation Engine

**Validation Engine cannot create decisions.**

It also cannot:

- Amend, correct or repair a decision it is judging. A defect is reported, never fixed.
- Recompute ledgers, entries or tax. It judges what it was given.
- Substitute its own preferred treatment for one that is defensible.
- Post to Tally.
- Ask the human questions. A case needing questions returns to the Clarification Engine.
- Approve a decision that still carries an unresolved finding.
- Return a rejection without naming the stage that must act on it.

**Per sub-engine:** `accounting_validation` judges the entry, never rewrites it. `tax_validation` judges tax, never recomputes it. `data_validation` judges data, never corrects or normalises it, and never lowers a requirement the data cannot meet. `duplicate_detection` reports matches, never deletes, merges or reverses, and never decides what to do about a duplicate. `risk_assessment` rates exposure, never re-derives the decision's internal risk and never blocks by itself. `validation_decision` issues one verdict, never creates or amends a decision.

---

## 6. Tally Engine

**Tally Engine cannot reason.**

It also cannot:

- Interpret or make any judgement about the transaction.
- Alter the accounting meaning of what it was given.
- Supply a value that is missing. Missing data is an error, not a gap to fill.
- Decide whether posting should happen. That was decided by the Validation Engine.
- Correct a rejected voucher and resubmit it.
- Alter, delete or omit an audit record — including records of failure.

**Per sub-engine:** `voucher_translator` translates faithfully, never chooses between representations on accounting grounds. `tally_connector` carries payloads, never inspects or modifies them. `posting_manager` controls posting, never changes payload content and never decides whether posting should happen. `response_processor` reads Tally's answer, never retries and never reads an ambiguous or absent response as success. `error_handler` classifies and routes, never corrects data, never retries directly and never suppresses an error it cannot classify. `audit_logger` records, never alters, deletes, omits or summarises away detail.

---

## 7. Cross-Cutting Prohibitions

These bind every engine and every sub-engine.

1. **No engine writes into another engine's output.** Every artifact has exactly one producing engine. Downstream engines read; they do not amend.
2. **No stage is skipped.** However obvious a transaction appears, it passes through every stage in order.
3. **No engine reaches backwards.** An engine consumes only the artifact handed to it — never the internals of the engine that produced it, never an artifact from further upstream than its own input.
4. **No component owns two problems.** If a component finds itself deciding two different kinds of thing, the architecture is wrong: stop and ask.
5. **No problem is owned twice.** If two components could each plausibly make the same call, the ownership is unclear: stop and ask. The four adjacent pairs are separated explicitly in [SUB_ENGINE_RESPONSIBILITIES.md](SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
6. **Doubt is never dropped.** Doubts, risks and low-confidence markers travel with the artifact at every stage.
7. **A gap is never filled by inference.** An absent fact stays absent until a human supplies it. No defaults, no conventions, no most-common-value.
8. **Nothing unapproved is executed.** The only decision that reaches Tally is one the Validation Engine approved.
9. **Every rejection names its owner.** No finding is returned to the pipeline without naming the stage that must handle it.
10. **Failure is as loggable as success.** No error, retry or partial outcome is omitted from the audit record.

---

## 8. Architectural Change

The architecture is the source of truth. It is not adjusted to make an implementation easier.

Do not, under any circumstance:

- Add an engine, remove one, merge two, or rename any.
- Rename a sub-engine, or move a responsibility between components.
- Create a component not listed in [MVP_ARCHITECTURE.md](MVP_ARCHITECTURE.md).
- Introduce a shortcut path between engines that is not in [DATA_FLOW.md](DATA_FLOW.md).

**If something in the architecture seems wrong, it may well be. Stop and ask.** A boundary that is genuinely mis-drawn should be corrected deliberately, in the documentation, before any code depends on it — never worked around in an implementation.
