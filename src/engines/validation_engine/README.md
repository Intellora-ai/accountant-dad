# Validation Engine

> Engine 5 of 6. **Specification locked** — deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_VALIDATION_INTERNAL.md`](../../../docs/COMMUNICATION_RULES_VALIDATION_INTERNAL.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*Is the complete reasoning chain sufficiently correct, complete, traceable and safe for execution?*

Everything before it attempts to understand, reason and clarify. **This engine attempts to prove them wrong.**

A decision reviewed by its own author is not reviewed. This engine exists as a separate authority precisely so that it can reject — and so that *"the entry is correct"* is a claim something other than the decision-maker has tested.

It never answers *what exists?* (Engine 1), *what happened?* (Engine 2), *how should it be accounted?* (Engine 3), *what should be asked?* (Engine 4), or *how should it be posted?* (Engine 6).

## Responsibility

Protect system correctness. Prevent incorrect entries, unsupported decisions, hidden assumptions and the execution of uncertain accounting.

Sub-engines and their output contracts:

| Sub-engine | Owns | Produces |
|---|---|---|
| [`data_validation`](data_validation/) | Data validation · the closed-period gate | **Data Validation Result** |
| [`accounting_validation`](accounting_validation/) | Accounting validation | **Accounting Validation Result** |
| [`tax_validation`](tax_validation/) | Tax validation | **Tax Validation Result** |
| [`duplicate_detection`](duplicate_detection/) | Economic duplicate detection | **Duplicate Detection Result** |
| [`risk_assessment`](risk_assessment/) | Execution risk | **Risk Assessment** |
| [`validation_decision`](validation_decision/) | The final status | **Validation Decision** |

### Flow

```text
Accounting Decision · Clarification Request · reference artifacts
                        ↓
                 data_validation           ← the only gate
                        ↓
        ┌───────────────┼───────────────────┬───────────────┐
        ↓               ↓                   ↓               ↓
accounting_validation  tax_validation  duplicate_detection  risk_assessment
        └───────────────┴─────────┬─────────┴───────────────┘
                                  ↓
                          validation_decision
                                  ↓
                          Validation Decision
```

**Only `data_validation` may stop the pipeline** — with no artifacts there is nothing to validate. Once artifacts exist, all four validators run. A transaction with an accounting error *and* a tax error reports **both**. `risk_assessment` reads the other three because posting risk depends on what they found.

### Decision authority

> **Validation is an independent decision engine. It validates previous engine outputs but never rewrites them.**

The parent assembles the Validation Decision. It never overrides, suppresses or replaces any sub-engine output. **No sub-engine overrides another.**

## Input

**Primary:** the **Accounting Decision** · the **Clarification Request**. **Reference only:** Business Understanding Object · Document Evidence Object · Company Context · Knowledge Brain.

Boundary contracts: [`docs/COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](../../../docs/COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) · [`docs/COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](../../../docs/COMMUNICATION_RULES_CLARIFICATION_ENGINE.md).

Must preserve **evidence provenance · evidence references · assumptions · reasoning · confidence · uncertainty · traceability · artifact versions · Transaction ID.** **Validation never rewrites history.**

## Output

One artifact: the **Validation Decision**.

```text
Validation Decision
├── Validation ID                    identity only — IDENTITY ≠ INTELLIGENCE
├── Transaction ID
├── Related Decision ID · Related Artifact Version
├── Validation Status                Approved | Approved With Warning |
│                                    Clarification Required | Rejected
├── Validation Findings · Errors · Warnings · Risks
├── Failed Validation Rules
├── Supporting Evidence References
├── Validation Confidence
├── Validation Reasoning
└── Validation Timestamp
```

`validation_decision` **creates** it; the **Validation Engine owns** it; the Execution Engine consumes it.

**Severity:** `Critical` prohibits execution · `High` · `Medium` · `Low`, non-blocking but permanently recorded. **Severity is never hidden or downgraded without evidence.**

## Boundary

**MUST NEVER:** create accounting entries · modify accounting decisions · modify business understanding · modify evidence · modify clarification requests · invent facts or confidence · remove assumptions · hide uncertainty · resolve conflicts · ask users · generate clarification · bypass any engine · post transactions · execute journals · **repair accounting mistakes**.

> **Validation only validates.**

**Failure behaviour:** never simply *"Validation failed."* Always what failed, why, the **responsible engine**, the affected artifact, blocking severity, and the recommended next step. Every issue points back to Engine 1, 2, 3 or 4.

**Validation Confidence never exceeds the weakest critical confidence it depends on.** Validation cannot create confidence — it only evaluates the confidence that arrived.

## Future Notes

- `Approved With Warning` is not a soft rejection. It is the only way to say *"correct, but a human should look before this posts"* — and without it `risk_assessment` has no output path at all.
- A rejection must name the responsible engine, or the pipeline has nowhere to send the work. See [`docs/DATA_FLOW.md`](../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on).
- Permission is decided here, before execution: Engine 6 must never discover that posting was impossible.
