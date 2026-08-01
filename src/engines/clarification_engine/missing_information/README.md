# missing_information

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#101-missing_information).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Identify every piece of information required to safely continue that is currently unavailable.

## Responsibility

Owns **missing information identification**. Runs first in the chain — absence is one of uncertainty's sources, so it must be known before uncertainty can be measured.

## Name and responsibility

Name and role are identical. It found what was absent in Phase 1, and it finds what is absent now.

## Input

The **Accounting Decision**, and the **Business Understanding Object** (reference only).

## Output

**Missing Information Result** — missing facts · missing relationships · missing supporting evidence · affected accounting decisions · confidence · evidence references.

## Boundary

**Can:** compare required information against available information · detect absent information · preserve traceability.

**Cannot:** infer missing facts · invent values · modify previous artifacts · ask users directly.

## Failure Behaviour

If completeness cannot be determined, **preserve uncertainty and report incomplete detection rather than assuming completeness.** An undetermined completeness is never recorded as complete.

## Future Notes

- Distinct from the two gaps named upstream: `parser` records a field the document lacks; `story_builder` records a business fact the evidence does not establish. This records what the **accounting decision** needs and does not have. See [Ownership Collisions](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
- Only a gap that reaches here is a candidate for a Clarification Request — and only after `stop_decision` judges it necessary.
