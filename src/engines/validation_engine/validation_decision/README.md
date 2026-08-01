# validation_decision

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#106-validation_decision).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Five opinions must become one answer.

## Responsibility

Owns the **Validation Decision** — the single status, and the naming of the engine responsible for every finding.

## Input

All Validation Results — Data Validation Result · Accounting Validation Result · Tax Validation Result · Duplicate Detection Result · Risk Assessment.

## Output

The **Validation Decision**.

```text
Validation Decision
├── Validation ID · Transaction ID
├── Related Decision ID · Related Artifact Version
├── Validation Status
├── Validation Findings · Errors · Warnings · Risks
├── Failed Validation Rules
├── Supporting Evidence References
├── Validation Confidence · Validation Reasoning
└── Validation Timestamp
```

### Validation Status

| Status | Meaning | Execution |
|---|---|---|
| **Approved** | Safe for Engine 6. | Proceeds |
| **Approved With Warning** | Correct, but unsafe to post unattended. | Proceeds only with human attention |
| **Clarification Required** | May become correct with more information. | Blocked — returns through the clarification loop |
| **Rejected** | Unsafe. | **Prohibited** |

**The middle two are never interchangeable.** The first says the reasoning is sound and the consequences warrant a human; the second says the reasoning is incomplete.

## Boundary

**Can:** assemble · report · publish.

**Cannot:** override sub-engine outputs · **hide failures** · remove uncertainty · create accounting decisions · amend a decision · post · approve while a Critical finding stands · return a rejection without naming the responsible engine · ask the human questions — a case needing questions returns to the Clarification Engine.

> **`validation_decision` creates the artifact. The Validation Engine owns it.**

It does not become an independent owner. Assembly is not permission to edit.

## Failure Behaviour

**Every blocking issue must appear inside the Validation Decision. No approval exists while a Critical finding remains.** Every rejection names the responsible engine and the recommended next step — never simply *"Validation failed."*

## Future Notes

- This is the only gate into the Execution Engine. Nothing reaches the books without passing through here.
- The routing table for rejections lives in [`docs/DATA_FLOW.md`](../../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on) and is part of the contract, not an implementation detail.
- The status mapping is mechanical, not discretionary — see [`docs/COMMUNICATION_RULES_VALIDATION_INTERNAL.md` §4](../../../../docs/COMMUNICATION_RULES_VALIDATION_INTERNAL.md#4-status-assembly).
