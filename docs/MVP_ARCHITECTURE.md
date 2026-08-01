# MVP Architecture

> **Precedence level 2 — Locked Architecture Decisions.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> Status: **Phase 1 — architecture foundation only.** No implementation exists. This document defines the system; it does not describe running software.

---

## 1. Product Mission

**The AI Accountant turns a real business document into a correct, posted accounting entry — and knows when to ask instead of guess.**

A business generates paper and files all day: purchase invoices, sales invoices, receipts, payment advices, debit and credit notes. Today a human accountant reads each one, understands what actually happened commercially, decides how it should be recorded, resolves anything ambiguous by asking, checks the result, and enters it into Tally.

This system performs that same sequence. It is built to imitate the accountant's *reasoning order*, not to automate keystrokes.

Three commitments define the product:

1. **Understand before deciding.** The system establishes what happened in business terms before it touches accounting treatment. A document is not an entry.
2. **Doubt is a first-class output.** When the system is unsure, it says so, names precisely what would resolve it, and asks. It never silently defaults.
3. **Nothing reaches the books unvalidated.** A decision is judged independently before it is posted, and the posting itself is recorded immutably.

The intended user is an accounting practice or a business's accounts function operating on Indian GST-regime books, posting into Tally.

---

## 2. The Six-Engine Architecture

The system is divided into six engines. **Each engine is one cognitive stage, not one technical layer.** The split follows the order a competent accountant thinks in — not the order software is usually built in.

| # | Engine | The question it answers |
|---|---|---|
| 1 | **Input Engine** | *What does this document actually say?* |
| 2 | **Understanding Engine** | *What happened in the business?* |
| 3 | **Accounting Engine** | *How should it be recorded?* |
| 4 | **Clarification Engine** | *What do we still need to ask a human?* |
| 5 | **Validation Engine** | *Is the reasoning chain correct, complete, traceable and safe to execute?* |
| 6 | **Tally Engine** | *Put it in the books, and record that we did.* |

### Why this split exists

Because these are genuinely different kinds of thinking, and collapsing any two of them destroys the property that makes the system trustworthy.

- **Reading is not understanding.** Extracting the characters `19,800.00` is a perception problem. Knowing it is a credit purchase from a recurring supplier is a comprehension problem. Different failure modes, different confidence, different fixes.
- **Understanding is not deciding.** "A supplier delivered goods on credit" is a fact. "Debit Purchases, credit the supplier ledger, GST input at 18%" is a judgement. Facts can be verified; judgements must be justified. Keeping them apart is what lets the system show its reasoning.
- **Deciding is not asking.** An engine that can both decide and ask will always prefer to guess, because guessing is cheaper. Doubt is therefore produced by the Accounting Engine but *acted on* by a separate engine that has no authority to invent answers.
- **Deciding is not approving.** A decision reviewed by its own author is not reviewed. Validation is a separate engine precisely so it can reject.
- **Approving is not posting.** Execution against an external system fails in its own ways — the connection drops, Tally rejects a voucher, a post half-succeeds. Those failures must never be confused with accounting errors, so execution owns no reasoning at all.

The boundaries are the architecture. They are documented as hard prohibitions in [SYSTEM_BOUNDARIES.md](SYSTEM_BOUNDARIES.md).

---

## 3. Complete Semantic Tree

45 components: 6 engines, 39 sub-engines.

```text
AI Accountant
│
├── 1. Input Engine ......................... What does this document say?
│   ├── cleaner ............................. make the artifact readable
│   ├── reader .............................. extract what is written
│   ├── parser .............................. give the extraction structure
│   └── confidence .......................... measure how much to trust it
│
├── 2. Understanding Engine ................. What happened in the business?
│   ├── transaction_understanding ........... what kind of event this was
│   ├── party_understanding ................. who was involved, and as what
│   ├── item_understanding .................. what goods or services moved
│   ├── payment_understanding ............... how money moved, or did not
│   ├── timeline_understanding .............. when each thing happened
│   ├── business_context .................... how this fits the business's reality
│   └── story_builder ....................... assemble one coherent story
│
├── 3. Accounting Engine .................... How should it be recorded?
│   ├── transaction_analyzer ................ the economic substance of the event
│   ├── accounting_rules .................... the principles that govern treatment
│   ├── ledger_intelligence ................. which accounts are involved
│   ├── journal_intelligence ................ the double entry itself
│   ├── tax_intelligence .................... GST, ITC, TDS treatment
│   ├── company_understanding ............... this company's accounting reality
│   ├── risk_analysis ....................... how risky this decision is
│   ├── doubt_detection ..................... where the decision is uncertain
│   └── decision_output ..................... one assembled decision
│
├── 4. Clarification Engine ................. What must we ask a human?
│   ├── missing_information ................. what facts are absent, and who has them
│   ├── uncertainty_detection ............... which uncertainties actually block us
│   ├── understanding ....................... conflict identification
│   ├── stop_decision ....................... is clarification necessary at all
│   ├── answer_understanding ................ clarification priority
│   ├── question_generator .................. the Clarification Request itself
│   └── decision_updater .................... clarification lifecycle tracking
│
├── 5. Validation Engine .................... Is this safe to post?
│   ├── data_validation ..................... are the data sound — the only gate
│   ├── accounting_validation ............... is the entry accounting-correct
│   ├── tax_validation ...................... is the tax treatment compliant
│   ├── duplicate_detection ................. same business event, already recorded?
│   ├── risk_assessment ..................... what posting this would expose us to
│   └── validation_decision ................. the final Validation Decision
│
└── 6. Tally Engine ......................... Put it in the books.
    ├── voucher_translator .................. decision → Tally voucher
    ├── tally_connector ..................... own the connection
    ├── posting_manager ..................... control the act of posting
    ├── response_processor .................. what Tally actually said
    ├── error_handler ....................... classify and route failures
    └── audit_logger ........................ the immutable record
```

Per-engine detail: [ENGINE_RESPONSIBILITIES.md](ENGINE_RESPONSIBILITIES.md).
Per-sub-engine detail: [SUB_ENGINE_RESPONSIBILITIES.md](SUB_ENGINE_RESPONSIBILITIES.md).

---

## 4. System Flow

```text
        Raw Artifact
             │
             ▼
   ┌───────────────────┐
   │  1. INPUT         │  reads the document
   └───────────────────┘
             │  Document Evidence Object
             ▼
   ┌───────────────────┐
   │  2. UNDERSTANDING │  establishes what happened
   └───────────────────┘
             │  Business Understanding Object
             ▼
   ┌───────────────────┐
   │  3. ACCOUNTING    │  decides treatment, declares
   └───────────────────┘  its assumptions, risks, doubts
             │  Accounting Decision
             ├───────────────────────────┐
             ▼                           │
   ┌───────────────────┐                 │
   │  4. CLARIFICATION │  detects what   │
   └───────────────────┘  blocks it      │
             │  Clarification Request    │
             │                           │
             ├──► external actor         │
             │    (UI / API / human)     │
             │         │                 │
             │  Clarification Answer     │
             │         ▼                 │
             │  Engine 1/2/3 rebuild     │
             │  → new artifact version   │
             │                           │
             ▼                           ▼
   ┌───────────────────┐
   │  5. VALIDATION    │  judges the decision —
   └───────────────────┘  receives BOTH artifacts
             │
      approve├──────────────► Approved Decision ──► ┌──────────────┐
             │                                      │  6. TALLY    │  posts it
      reject └──────────────► back to the named     └──────────────┘
                              stage, never forward          │
                                                            ▼
                                             Posting Result + Audit Record
```

### The flow in words

1. A raw artifact enters — a photo, a scan, a PDF, a handwritten note. The **Input Engine** makes it readable, extracts it, structures it, and scores how much of that extraction can be trusted, emitting one **Document Evidence Object**.
2. The **Understanding Engine** converts that evidence into a **Business Understanding Object** — the parties, the goods, the money, the dates, the context, assembled into one narrative with no accounting vocabulary in it, alongside every gap it found and every conflict it refused to resolve.
3. The **Accounting Engine** converts that understanding, together with company context, into an **Accounting Decision**: the ledgers, the double entry, the tax treatment and the accounting period — together with the assumptions it rested on, the risks it carries, the doubts it could not resolve, and a status saying plainly whether it is complete.
4. The **Clarification Engine** detects what would prevent that decision being completed safely — what is missing, what is uncertain, what contradicts what — and emits a **Clarification Request** saying what is required, why it matters and how urgent it is. It resolves nothing and asks no one: a later system layer delivers the request, and any answer re-enters at Engine 1, 2 or 3, which emits a **new artifact version**.
5. The **Validation Engine** independently judges the decision — accounting correctness, tax compliance, data soundness, duplication, posting risk — reading both the Accounting Decision and the Clarification Request, and returns one **Validation Decision**: `Approved`, `Approved With Warning`, `Clarification Required` or `Rejected`, with every finding naming the engine responsible for it.
6. Only an approved decision reaches the **Tally Engine**, which translates it to a voucher, posts it exactly once, reads what Tally actually said, classifies any failure, and writes an immutable audit record.

Artifact-by-artifact detail, including the conditional paths and the return rule: [DATA_FLOW.md](DATA_FLOW.md).

---

## 5. What Phase 1 Deliberately Excludes

There is no OCR, no AI model, no LLM call, no prompt, no database, no API, no Tally connection, no accounting logic and no tax logic in this repository. Those are implementation decisions and belong to later phases.

What exists now is the thing that must exist first: an unambiguous statement of what each part of the system owns, and what it is forbidden to do.
