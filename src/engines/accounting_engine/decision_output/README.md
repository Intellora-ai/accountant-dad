# decision_output

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#89-decision_output).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Assemble the final Accounting Decision artifact.

## Responsibility

Owns **final accounting decision assembly**, including setting **Decision Status** from the state of the doubts and missing information.

## Input

The outputs of all eight preceding Accounting sub-engines.

## Output

The **Accounting Decision** — the sole artifact handed onward.

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

## Boundary

| **CAN** | **CANNOT** |
|---|---|
| Combine accounting outputs | Invent conclusions |
| Organize them | Remove uncertainty |
| Present the final reasoning | Override sub-engines |
| Set Decision Status | Alter, reconcile or soften any component |
| | Omit risks or doubts |
| | Bypass validation |
| | Mark the decision approved or safe |

## Decision Authority

**Owns.** Assemble the final Accounting Decision.

> **`decision_output` creates the artifact. The Accounting Engine owns it.**

It does not become an independent owner. Assembly is not permission to edit.

## Failure Behaviour

Where the sub-engine outputs do not support a complete decision, it emits:

```text
Decision Status:         INCOMPLETE_INFORMATION_REQUIRED
Reason:                  Missing information
Required clarification:  …
```

> **Never guess.** It does not complete the decision by assumption.

## Future Notes

- Three consumers read this artifact — Clarification, Validation and (once approved) Tally. Design it for all three.
- **Decision Status** exists so a downstream engine can ask *can this move forward?* and get a structured answer rather than infer one from prose.
- The decision needs an identity that survives the clarification loop, so before and after can be compared — and that identity must never influence reasoning.
