# Accounting Engine

> Engine 3 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*How should it be recorded?*

Understanding is not deciding. "A supplier delivered goods on credit" is a fact; "debit Purchases, credit the supplier ledger, GST input at 18%" is a judgement. Facts can be verified, judgements must be justified — so this engine is where judgement lives, and where it must show its reasoning, its risks and its doubts.

## Responsibility

Turn the business story into an accounting decision, plus its doubts and risks.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`transaction_analyzer`](transaction_analyzer/) | The economic substance of the event |
| [`accounting_rules`](accounting_rules/) | The principles governing treatment |
| [`ledger_intelligence`](ledger_intelligence/) | Which accounts are involved |
| [`journal_intelligence`](journal_intelligence/) | The double entry itself |
| [`tax_intelligence`](tax_intelligence/) | GST, ITC and TDS treatment |
| [`company_understanding`](company_understanding/) | This company's accounting reality |
| [`risk_analysis`](risk_analysis/) | How risky this decision is |
| [`doubt_detection`](doubt_detection/) | Where the decision is uncertain |
| [`decision_output`](decision_output/) | One assembled decision |

## Input

Transaction Story, from the Understanding Engine. Resolved Facts, when the Clarification Engine returns answers.

## Output

**Accounting Decision** — ledgers, journal entry, tax treatment, the reasoning behind them, the risks they carry, and the doubts that remain.

## Boundary

**Cannot post to Tally, and cannot question the user directly.** Cannot approve its own decision or declare it safe. Cannot read the raw artifact or the Document Evidence Object — it reasons from the Transaction Story only. Cannot resolve its own doubt by guessing, defaulting, or picking the most common treatment.

## Future Notes

- Reasoning is part of the output, not a debugging aid. Validation judges the decision against the rules it claimed to apply.
- This is the only engine the Clarification loop returns to. A decision after clarification is *remade* here, not patched there.
