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

**Assembly ownership.** The Input Engine owns the internal assembly of its four sub-engines' outputs into the Document Evidence Object, and assigns the Document ID. It does **not** own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, workflow control, or overriding sub-engine outputs. No assembler sub-engine exists, and none may be added. **Document ID carries no accounting meaning and must never influence accounting decisions.**

**Per sub-engine:** `cleaner` alters presentation, never values — and preserves the original where processing may damage information. `reader` extracts, never interprets, and never guesses an unclear word. `parser` structures, never infers or computes a value that is not written — unknown fields remain unknown. `confidence` measures, never re-reads or corrects, never raises confidence without evidence, and never hides uncertainty.

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

The Input Engine extracts what exists. The Understanding Engine determines what it means.

---

## 2. Understanding Engine

> **Specification locked.** Deeper authority: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).

**The Understanding Engine establishes what happened. It does not decide how it is recorded.**

It **MUST NEVER**:

1. Create journal entries.
2. Choose ledgers.
3. Decide debit/credit.
4. Apply tax rules.
5. Post to Tally.
6. Modify evidence.
7. **Convert uncertainty into certainty.**

It also cannot:

- Select accounts, groups or voucher types.
- Determine tax applicability, rates, place of supply or credit eligibility.
- Invent a fact to fill a gap. An absent fact is recorded as absent.
- Re-read or re-extract the artifact. If the extraction is inadequate, it says so.
- Describe business events in accounting vocabulary.
- Ask the user questions, request documents, or resolve uncertainty itself.

**The uncertainty prohibition.** Rule 7 is the one this engine exists to protect. Understanding is where a system is most tempted to tidy up — to pick the likelier reading, to round away a discrepancy, to let a coherent story paper over a gap. Uncertainty entering this engine leaves it. It may be *described* more precisely; it is never *removed*. **Low confidence never becomes certainty.**

**The conflict prohibition.** Conflicts are preserved. **Never silently choose one answer.** Where evidence disagrees, the engine returns known facts, conflicting facts, confidence and unknowns — never a resolution. Conflicts belong to the Understanding Engine; no other engine may settle one by editing this engine's artifact.

**Confidence Propagation Rule.** `Understanding Confidence ≤ Evidence Reliability`. A confident interpretation of an unreliable reading is not understanding; it is invention with a score attached.

**Assembly ownership.** `story_builder` **creates** the Business Understanding Object; the **Understanding Engine owns** it. Story Builder does not become an independent owner. The parent engine does not orchestrate the system, route workflows, make accounting decisions, or override sub-engine outputs.

**Per sub-engine:** `transaction_understanding` names the business event, never the voucher type. `party_understanding` identifies parties, never their ledgers, and never merges two parties it believes identical. `item_understanding` describes what moved, never asset, expense or inventory, and never its tax rate. `payment_understanding` describes money movement, never the cash or bank account, and never infers payment from silence. `timeline_understanding` records dates, never the accounting period or cut-off. `business_context` records purpose *indicators*, never concluded intent, and never accounting configuration. `story_builder` assembles, never adds a fact no sub-engine produced, never resolves a conflict, never removes an unknown, and never increases confidence.

> **Input Engine provides evidence. Understanding Engine creates interpretation. Accounting Engine decides treatment.**

---

## 3. Accounting Engine

> **Specification locked.** Deeper authority: [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).

**The Accounting Engine decides treatment. It does not read documents, discover business events, ask users, post, or approve.**

It **MUST NEVER**:

1. Modify the Document Evidence Object.
2. Modify the Business Understanding Object.
3. Invent missing facts.
4. Hide uncertainty.
5. Ask users questions directly.
6. Post transactions to Tally.
7. Override validation results.
8. Change source evidence.
9. **Pretend assumptions are confirmed facts.**

It also cannot:

- Communicate with Tally in any way, for any reason.
- Approve its own decision, or declare it correct, safe or final.
- Read the raw artifact or the Document Evidence Object. It reasons from the Business Understanding Object and company information only.
- Resolve its own doubt by guessing, defaulting, or selecting the most common treatment.
- Suppress a doubt or a risk because it is inconvenient, or because it would delay posting.
- Decide whether the document information is correct, whether the business story is correct, or whether the user intended something different. **Those belong upstream.**

**The assumptions rule.** Every sub-engine relying on an assumption records it in its own Result — what was assumed, and why. **Nothing may assume silently.** An unrecorded assumption is the mechanism by which assumptions become confirmed facts: one that is written down can be challenged, questioned or spotted; one that is not, cannot.

**Insufficient information.** The engine returns a named output, never a guess:

```text
Decision Status:         INCOMPLETE_INFORMATION_REQUIRED
Reason:                  Missing information
Required clarification:  …
```

> **Never guess.**

**Balance ≠ correctness.** `journal_intelligence` guarantees internal journal mathematical balance only — debit = credit. It does **not** guarantee accounting, tax or business correctness. *Wrong ledger + balanced journal = still wrong.* Correctness is judged by the Validation Engine.

**Assembly ownership.** `decision_output` **creates** the Accounting Decision; the **Accounting Engine owns** it. The parent assembles the Accounting Treatment Result **mechanically** — it may combine, organize and structure, but may never change the Ledger Recommendation, change the Tax Treatment Recommendation, remove uncertainty, or increase confidence. It does not orchestrate the system, route workflows, or **override sub-engine outputs**. **No sub-engine creates another sub-engine's decision** — no hidden override, no circular reasoning.

**Per sub-engine:** `transaction_analyzer` characterises, never selects accounts and never decides tax. `accounting_rules` applies principle and decides accounting period, never invents a rule from the transaction in front of it, and **never produces the Ledger Recommendation or Tax Treatment Recommendation**. `ledger_intelligence` specifies accounts, never provisions them. `journal_intelligence` designs and balances the entry, never calculates or interprets tax, never selects the accounts itself, and never forces a balance with a plug figure. `tax_intelligence` recommends treatment, never files, never guarantees compliance, and never picks a rate for being common. `company_understanding` supplies context, never decides treatment — **historical patterns are evidence, not decisions**: *"the company usually does X, therefore automatically do X"* is forbidden. `risk_analysis` rates its own decision, never blocks and never changes the decision to improve its own score. `doubt_detection` produces doubt, never asks and never resolves. `decision_output` assembles, never alters a component and never omits a doubt or risk.

> **Understanding Engine creates interpretation. Accounting Engine decides treatment. Validation Engine decides safety.**

---

## 4. Clarification Engine

> **Specification locked.** Deeper authority: [`ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).

**The Clarification Engine detects what prevents a decision from being safely completed. It resolves nothing.**

It **MUST NEVER**:

1. Create journal entries.
2. Choose ledgers.
3. Decide accounting treatment.
4. Decide tax treatment.
5. Modify evidence.
6. Modify business understanding.
7. Modify accounting decisions.
8. Approve execution.
9. Reject execution.
10. Invent facts.
11. **Silently resolve conflicts.**
12. Convert assumptions into facts.
13. Convert uncertainty into certainty.
14. **Ask users directly.**
15. Bypass previous engines or bypass validation.

It also cannot:

- Assume or default a value nobody supplied.
- Mark a decision correct, approved or safe.
- Raise an uncertainty that has no evidence upstream.
- Communicate directly with Engine 1.
- Increase confidence without new evidence.

**Emit-only.** Engine 4 produces a structured **Clarification Request** and stops. A later system layer may deliver it to a user, accountant or external system. **Engine 4 never receives answers as a decision engine** — new information re-enters through Engine 1, 2 or 3, which emits a **new artifact version**. This is why no backward mutation exists anywhere in the system.

**Failure behaviour.** If clarification cannot safely continue, return what is known, what is unknown, why clarification is required, and which decision is affected. **Never guess.**

**Lifecycle.** `Created → Waiting for Information → Information Received → Closed`, with `Obsolete` reachable from any state; both terminals. Engine 4 owns **every transition** but no **resolution** — a request closes only when a new artifact version no longer carries the uncertainty that caused it. **Obsolete ≠ Closed.**

**Conflict handling.** Every conflict remains visible until either new information arrives and the responsible upstream engine emits a new artifact version, or the conflict is explicitly accepted by a future validation or human process. **Clarification exists to expose uncertainty, never to hide it.**

**Assembly ownership.** `question_generator` **creates** the Clarification Request; the **Clarification Engine owns** it, with Clarification Status and Clarification History. The parent assembles; it never rewrites sub-engine outputs, resolves a conflict, changes a priority, or removes uncertainty.

**Per sub-engine:** `missing_information` locates absences, never fabricates, estimates or infers a value. `uncertainty_detection` measures and classifies uncertainty, never removes it and never raises confidence without evidence. `understanding` identifies contradictions, never resolves one and never chooses an interpretation. `stop_decision` judges whether clarification is required, never modifies a decision — and defaults to *Clarification Required* when necessity cannot be determined. `answer_understanding` prioritises, never removes a clarification requirement — and defaults to *High* when priority is unknown. `question_generator` assembles the Request, never invents clarification, hides uncertainty or rewrites reasoning. `decision_updater` tracks status and history, never resolves clarification, modifies decisions or approves execution.

> **Accounting Engine decides treatment. Clarification Engine detects what blocks it. Validation Engine decides safety.**

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
11. **IDENTITY ≠ INTELLIGENCE.** **IDs identify objects. They do not influence reasoning.** Document ID, Decision ID, Transaction ID, User ID and any future identifier exist only for identity, traceability, lifecycle tracking and audit history. None may influence ledger selection, journal creation, tax treatment, validation outcome, confidence, or any future decision. *"Because ACC-000123 existed before, choose the same treatment"* — never. See [`DATA_FLOW.md` §9](DATA_FLOW.md#9-identity--intelligence).
12. **Confidence only decreases.** **Confidence can only decrease downstream unless new evidence is introduced.** Later engines may maintain, reduce or request clarification — never magically increase certainty. The single exemption is new evidence, which is what the Clarification Engine exists to obtain. See [`DATA_FLOW.md` §10](DATA_FLOW.md#10-confidence-across-engines).
13. **Nothing assumes silently.** Every component relying on an assumption records what it assumed and why. An unrecorded assumption becomes a confirmed fact by default, and nothing downstream can tell the difference.
14. **Artifacts are versioned, never edited.** Every artifact carries an Artifact ID, a Version and its Parent Artifact Version(s). A version is immutable once created — **correction means a new version, never an edit** — and only the owning engine may create one. Superseded versions are never deleted; the version chain is the audit trail. A downstream artifact whose parent version is no longer current is **stale**, and staleness is structural rather than noticed. See [`DATA_FLOW.md` §11](DATA_FLOW.md#11-artifact-versioning).
15. **Knowledge is shared; authority is not.** The **Knowledge Brain** ([`src/brain/`](../src/brain/)) provides accounting standards, rules, guidance, terminology, references and historical patterns to every engine on identical terms. It is **advisory, never binding** — any engine may ignore it, recording why. It may never return a decision, a recommended treatment, an approval, a ledger, a rate, or an instruction; may never create clarification requests, approve clarification, make accounting decisions, or override engine outputs; and owns no decisions, artifacts, confidence or workflow. **Knowledge flows into engines. Decision authority never leaves engines.**

---

## 8. Architectural Change

The architecture is the source of truth. It is not adjusted to make an implementation easier.

Do not, under any circumstance:

- Add an engine, remove one, merge two, or rename any.
- Rename a sub-engine, or move a responsibility between components.
- Create a component not listed in [MVP_ARCHITECTURE.md](MVP_ARCHITECTURE.md).
- Introduce a shortcut path between engines that is not in [DATA_FLOW.md](DATA_FLOW.md).

**If something in the architecture seems wrong, it may well be. Stop and ask.** A boundary that is genuinely mis-drawn should be corrected deliberately, in the documentation, before any code depends on it — never worked around in an implementation.
