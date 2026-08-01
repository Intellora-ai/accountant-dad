# Clarification Engine

> Engine 4 of 6. **Specification locked** — deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](../../../docs/COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What information is missing, uncertain, conflicting or unsupported, and what clarification is required before this decision can safely continue?*

**A reliable system must know when it does not know.** This engine does not remove uncertainty by guessing — it removes it by causing better information to be obtained, and it never obtains that information itself.

It never answers *what exists?* (Engine 1), *what happened?* (Engine 2), *how should it be accounted?* (Engine 3), or *is it approved?* (Engine 5).

## Responsibility

Prevent incorrect execution by detecting uncertainty before validation.

> **Validation should never discover uncertainty that Clarification should have identified.**

Sub-engines and their output contracts:

| Sub-engine | Owns | Produces |
|---|---|---|
| [`missing_information`](missing_information/) | Missing information detection | **Missing Information Result** |
| [`uncertainty_detection`](uncertainty_detection/) | Uncertainty evaluation | **Uncertainty Analysis Result** |
| [`understanding`](understanding/) | Conflict identification | **Conflict Analysis Result** |
| [`stop_decision`](stop_decision/) | Clarification necessity | **Clarification Necessity Result** |
| [`answer_understanding`](answer_understanding/) | Clarification priority | **Clarification Priority Result** |
| [`question_generator`](question_generator/) | Clarification Request creation | **Clarification Request** |
| [`decision_updater`](decision_updater/) | Clarification lifecycle | **Clarification Status Result** |

### Names are historical; responsibilities are current

Three of these names were coined in Phase 1 for a clarification loop that then ran *inside* the engine. That loop now runs outside it. **Identities are part of the system contract and do not change.** Each sub-engine's README states why its name owns its present responsibility.

### Flow

One-directional. Feedback occurs only through new artifact versions from the responsible upstream engine.

```text
Accounting Decision  (+ Business Understanding Object, reference only)
        ↓
missing_information → uncertainty_detection → understanding → stop_decision
        ↓
answer_understanding → question_generator → decision_updater
        ↓
Clarification Request
```

Each step needs the one before it: absence feeds uncertainty · uncertainty weights conflicts · conflicts drive necessity · necessity precedes priority · priority is a field of the request · the request must exist before it can be tracked.

### Decision authority

> **The Clarification Engine controls only clarification decisions.**

The parent assembles the final Clarification Request. It never rewrites sub-engine outputs, resolves a conflict, changes a priority, or removes uncertainty. **No sub-engine overrides another.**

## Input

**Primary:** the **Accounting Decision**. **Secondary:** the **Business Understanding Object**, *reference only* — traceability, explanation, conflict identification, context.

Boundary contract: [`docs/COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](../../../docs/COMMUNICATION_RULES_ACCOUNTING_ENGINE.md). It never communicates directly with Engine 1.

Must preserve **evidence references · reasoning · assumptions · confidence · uncertainty · traceability.**

## Output

One artifact: the **Clarification Request**.

```text
Clarification Request
├── Clarification ID                 identity only — IDENTITY ≠ INTELLIGENCE
├── Related Decision ID
├── Related Artifact Version         the decision version this was raised against
├── Missing Information
├── Detected Conflicts
├── Required Clarification
├── Reason Clarification Is Required
├── Affected Decision
├── Priority                         Critical | High | Medium | Low
├── Supporting Evidence References
├── Clarification Confidence
└── Status                           Created | Waiting for Information |
                                     Information Received | Obsolete | Closed
```

`question_generator` **creates** it; the **Clarification Engine owns** it, with Clarification Status and Clarification History.

**Emit-only.** Questions are outputs, not actions. A later system layer may deliver the request; **Engine 4 never asks anyone directly and never receives answers.** New information re-enters through Engine 1, 2 or 3 as a new artifact version.

## Boundary

**MUST NEVER:** create journal entries · choose ledgers · decide accounting treatment · decide tax treatment · modify evidence · modify business understanding · modify accounting decisions · approve execution · reject execution · invent facts · **silently resolve conflicts** · convert assumptions into facts · convert uncertainty into certainty · **ask users directly** · bypass previous engines or validation.

**Failure behaviour:** return what is known, what is unknown, why clarification is required, and which decision is affected. **Never guess.**

**Clarification Confidence may never exceed upstream confidence.** Higher certainty cannot emerge from weaker evidence.

## Future Notes

- Most transactions should never produce a Clarification Request. `stop_decision` exists to keep it that way — but defaults to *required* when it cannot tell.
- A request naming an uncertainty that turns out to be harmless is a success. A clean pipeline that missed one blocking uncertainty is a failure, even if the entry happened to be right.
- The lifecycle is where this engine's real complexity lives: a request is not done when it is asked, only when a new artifact version no longer carries the uncertainty that caused it.
