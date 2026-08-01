# Accounting Engine

> Engine 3 of 6. **Specification locked** — deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](../../../docs/COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*Given what happened in the business, how should this be represented according to accounting rules?*

Understanding is not deciding. "A supplier delivered goods on credit" is a fact; "debit Purchases, credit the supplier ledger, GST input at 18%" is a judgement. Facts can be verified against evidence — **judgements must be justified.** This engine is where judgement lives, and where it must show its reasoning, its assumptions, its risks and its doubts.

It never answers *"what information exists?"* (Engine 1), *"what happened?"* (Engine 2), or *"is this safe to execute?"* (Engine 5).

## Responsibility

Convert the Business Understanding Object into a structured accounting decision while preserving uncertainty, assumptions and reasoning traceability.

Sub-engines and their output contracts:

| Sub-engine | Produces |
|---|---|
| [`transaction_analyzer`](transaction_analyzer/) | **Transaction Analysis Result** — category · implications · supporting facts · unknowns · confidence |
| [`company_understanding`](company_understanding/) | **Company Context Result** — company rules · historical patterns · preferences · confidence |
| [`accounting_rules`](accounting_rules/) | **Accounting Rule Application Result** — applied rules · **period treatment** · recognition timing · references · assumptions · confidence |
| [`ledger_intelligence`](ledger_intelligence/) | **Ledger Recommendation** — recommended ledgers · classification reasoning · confidence |
| [`tax_intelligence`](tax_intelligence/) | **Tax Treatment Recommendation** — applicable treatment · assumptions · risks · confidence |
| [`journal_intelligence`](journal_intelligence/) | **Journal Entry Recommendation** — debits · credits · amounts · reasoning · confidence |
| [`risk_analysis`](risk_analysis/) | **Accounting Risk Analysis** — risk indicators · reasons · severity · confidence |
| [`doubt_detection`](doubt_detection/) | **Accounting Doubt Report** — missing information · conflicts · required clarification areas |
| [`decision_output`](decision_output/) | **Accounting Decision** |

**Also owns:** accounting period treatment · decision confidence · the assumptions every part of the decision rested on.

### Flow

```text
Business Understanding Object          Company information
        ↓                                      ↓
transaction_analyzer                  company_understanding
        ↓                                      ↓
Transaction Analysis Result            Company Context Result
        └──────────────┬───────────────────────┘
                       ↓
   ┌───────────────────┼───────────────────┐
   ↓                   ↓                   ↓
ledger_intelligence  tax_intelligence  accounting_rules
   └───────────────────┴───────────────────┘
                       ↓
        Accounting Treatment Result   ← assembled by the parent engine
                       ↓
              journal_intelligence      guarantees Debit = Credit
                       ↓
        risk_analysis → doubt_detection → decision_output
                       ↓
                Accounting Decision
```

Three sub-engines each decide their own question; their outputs are **combined** into the internal Accounting Treatment Result. **`accounting_rules` does not produce the Ledger Recommendation or the Tax Treatment Recommendation** — that would be fake ownership.

### Decision authority

> **The Accounting Engine controls only accounting decisions. No engine outside it can modify its decisions.**

| Component | Authority |
|---|---|
| [`transaction_analyzer`](transaction_analyzer/) | Understand accounting-relevant transaction facts |
| [`company_understanding`](company_understanding/) | Provide company context |
| [`ledger_intelligence`](ledger_intelligence/) | Ledger classification |
| [`tax_intelligence`](tax_intelligence/) | Tax treatment reasoning |
| [`accounting_rules`](accounting_rules/) | Accounting rule application + period treatment |
| [`journal_intelligence`](journal_intelligence/) | Journal structure + balance |
| [`risk_analysis`](risk_analysis/) | Identify accounting risks |
| [`doubt_detection`](doubt_detection/) | Identify uncertainty |
| [`decision_output`](decision_output/) | Assemble final Accounting Decision |
| **Accounting Engine parent** | **Own final artifact** |

**`decision_output` creates the artifact. The parent owns it. These are different.**

The parent assembles the Accounting Treatment Result **mechanically** — it may combine, organize and create structure, but may never change the Ledger Recommendation, change the Tax Treatment Recommendation, remove uncertainty, or increase confidence. **No sub-engine creates another sub-engine's decision.**

## Input

The **Business Understanding Object**, created and owned by the Understanding Engine, plus **company information**. Boundary contract: [`docs/COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](../../../docs/COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md).

Receiving rules: **preserve evidence references · preserve uncertainty · preserve unknown information · never modify the artifact · never convert assumptions into facts.**

## Output

One artifact: the **Accounting Decision**.

```text
Accounting Decision
├── Decision ID              identity only — IDENTITY ≠ INTELLIGENCE
├── Decision Status          COMPLETE | INCOMPLETE_INFORMATION_REQUIRED
├── Accounting treatment
├── Ledger classification
├── Debit entries
├── Credit entries
├── Journal structure
├── Tax treatment
├── Accounting assumptions
├── Risk indicators
├── Decision confidence
├── Supporting reasoning
└── Unresolved doubts
```

Every decision shows **why it exists · what information supports it · what uncertainty remains**.

`decision_output` **creates** the artifact; the **Accounting Engine owns** it. **Decision ID exists only for identity, traceability, lifecycle tracking and audit history — it has zero accounting meaning.**

## Boundary

**MUST NEVER:** modify the Document Evidence Object · modify the Business Understanding Object · invent missing facts · hide uncertainty · ask users questions directly · post to Tally · override validation results · change source evidence · **pretend assumptions are confirmed facts**.

Cannot decide whether the document information is correct, whether the business story is correct, or whether the user intended something different — those belong upstream.

**Insufficient information produces a named output, never a guess:**

```text
Decision Status:         INCOMPLETE_INFORMATION_REQUIRED
Reason:                  Missing information
Required clarification:  …
```

> **Never guess.** · **Balance ≠ correctness.** · **Nothing may assume silently.**

## Future Notes

- Reasoning and assumptions are part of the output, not debugging aids. Validation judges the decision against the rules and assumptions it claimed.
- `INCOMPLETE_INFORMATION_REQUIRED` with the gap named is a success. A `COMPLETE` decision resting on one silent assumption is a failure, even when the assumption is correct.
