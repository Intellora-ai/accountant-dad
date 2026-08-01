# Understanding Engine

> Engine 2 of 6. **Specification locked** — deep spec: [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](../../../docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](../../../docs/COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What happened in the business?*

Reading is not understanding, and understanding is not deciding. Extracting `19,800.00` is a perception problem; knowing it is a credit purchase from a recurring supplier is a comprehension problem; deciding it debits Purchases is a *judgement*. Facts can be verified against evidence, judgements must be justified — so this engine establishes the facts and stops there.

It never answers *"how should it be recorded?"*

## Responsibility

Convert the Document Evidence Object into a coherent business story, with every fact traced to its evidence, every gap named, every conflict preserved, and confidence that never exceeds what the evidence supports.

Sub-engines and their output contracts:

| Sub-engine | Produces |
|---|---|
| [`transaction_understanding`](transaction_understanding/) | **Transaction Understanding Result** — identified event · evidence references · confidence · unknowns · conflicts |
| [`party_understanding`](party_understanding/) | **Party Understanding Result** — entities · relationships · evidence · confidence · unknown parties |
| [`item_understanding`](item_understanding/) | **Item Understanding Result** — goods/services · descriptions · evidence · confidence · unknown item details |
| [`payment_understanding`](payment_understanding/) | **Payment Understanding Result** — method · references · amount relationships · confidence · unknown details |
| [`timeline_understanding`](timeline_understanding/) | **Timeline Understanding Result** — dates · sequence · time relationships · confidence · missing dates |
| [`business_context`](business_context/) | **Business Context Result** — context clues · purpose indicators · evidence · confidence · unknown context |
| [`story_builder`](story_builder/) | **Business Understanding Object** |

**Also owns:** Business Understanding Object integrity · understanding confidence · preservation of uncertainty · conflict preservation.

### Dependency graph

**Not a flat pipeline.** The order is load-bearing.

```text
Document Evidence Object
        ↓
transaction_understanding          ← establishes the base event
        ↓
        ├── party_understanding    ← enrich that event
        ├── item_understanding
        ├── payment_understanding
        └── timeline_understanding
        ↓
business_context                   ← requires the previous understanding
        ↓
story_builder                      ← final assembly layer
        ↓
Business Understanding Object
```

The event kind changes how everything else is read: the same name means a different thing on a purchase than on a sales return. `business_context` runs after the others because "is this normal for this business?" cannot be answered before knowing what *this* is.

### Decision authority

> **The Understanding Engine controls only understanding decisions. No engine outside it can modify its decisions.**

The parent engine does **not** orchestrate the system, route workflows, make accounting decisions, or **override sub-engine outputs**. No sub-engine overrides another — where two Results disagree, the disagreement is recorded, never settled.

## Input

The **Document Evidence Object**, created and owned by the Input Engine. Boundary contract: [`docs/COMMUNICATION_RULES_INPUT_ENGINE.md`](../../../docs/COMMUNICATION_RULES_INPUT_ENGINE.md).

Receiving rules: **respect confidence · preserve uncertainty · trace understanding back to evidence · never modify source evidence.**

## Output

One artifact: the **Business Understanding Object**.

```text
Business Understanding Object
├── Transaction Story ................. the final assembled narrative
├── Supporting Understanding Data ..... the six sub-engine Results
├── Identified Unknowns ............... every gap, named
└── Confidence Assessment ............. evidence confidence · understanding confidence ·
                                        missing information · detected conflicts
```

**Transaction Story is not an independent component.** It is the narrative `story_builder` assembles from the six Results, which travel alongside it.

`story_builder` **creates** the artifact; the **Understanding Engine owns** it. Story Builder does not become an independent owner. The artifact is immutable — new information produces a new version authored by its owner.

## Boundary

**MUST NEVER:** create journal entries · choose ledgers · decide debit/credit · apply tax rules · post to Tally · modify evidence · **convert uncertainty into certainty**.

Cannot invent a fact to fill a gap. Cannot re-read or re-extract the artifact. Cannot use accounting vocabulary. Cannot ask the user questions, request documents, or resolve uncertainty itself.

**Conflicts are preserved. Never silently choose one answer.** Where evidence disagrees, the engine returns known facts, conflicting facts, confidence and unknowns — never a resolution.

**Low confidence never becomes certainty.** Confidence Propagation Rule: `Understanding Confidence ≤ Evidence Reliability`.

> **Input Engine provides evidence. Understanding Engine creates interpretation. Accounting Engine decides treatment.**

## Future Notes

- The no-accounting-vocabulary rule is the cheapest available test of whether this boundary is holding. If the story mentions a ledger, something has leaked.
- A story containing an unresolved conflict is the correct output, not a failure. The temptation to tidy it is the main risk this engine carries.
- Identified Unknowns and detected conflicts are what Clarification later turns into questions, so they need to be first-class parts of the structure, not annotations.
