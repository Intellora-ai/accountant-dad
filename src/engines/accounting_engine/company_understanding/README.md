# company_understanding

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#82-company_understanding).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Understand company-specific accounting context. The same transaction means different things at different companies — a laptop is an employee expense at one and resale inventory at another.

## Responsibility

Owns **company accounting preferences and context** — company profile, industry, accounting preferences, chart of accounts structure, historical patterns, policies.

**Context provision, not decision-making.**

## Input

The **Business Understanding Object** and **company information**.

## Output

**Company Context Result** — company rules · historical patterns · relevant preferences · confidence.

## Boundary

**Can:** provide company profile · industry · accounting preferences · chart of accounts structure · historical patterns · policies.

**Cannot:** decide debit · credit · ledger · tax treatment · journal · override accounting standards · change evidence.

### Historical patterns are evidence, not decisions

It **may influence** reasoning. It may **never** become *"the company usually does X, therefore automatically do X."*

```text
Previous treatment:  Laptop → expense
Future treatment:    Laptop → asset      ← legitimate; history cannot forbid it
```

## Decision Authority

**Owns.** Provide company context.

**Cannot.** Decide anything. Decision authority stays with the Accounting Engine.

No other component may override this Result.

## Failure Behaviour

Mark missing company context. Absent configuration is recorded as absent, never substituted with a general default.

## Future Notes

- Context arrives *before* the decision precisely so it can shape it. The discipline is that shaping is not deciding.
- Distinct from the Understanding Engine's [`business_context`](../../understanding_engine/business_context/), which owns the business's *operating* reality. This owns its *accounting* configuration.
