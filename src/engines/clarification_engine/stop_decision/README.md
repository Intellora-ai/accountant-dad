# stop_decision

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#104-stop_decision).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Determine whether clarification is actually required.

Not every uncertainty deserves a clarification request. Some has no effect on accounting treatment; some changes the entire decision. This component prevents unnecessary clarification while ensuring decision-critical uncertainty is never ignored.

## Responsibility

Owns **clarification necessity** — the gate that decides whether the clarification path runs at all.

## Name and responsibility

It was always the go/no-go gate on the clarification path. Phase 1 asked *is questioning complete?*; it now asks *is clarification required at all?* Both are one binary judgement about whether clarification runs.

## Input

**Missing Information Result**, **Uncertainty Analysis Result**, **Conflict Analysis Result**, and the **Accounting Decision**.

## Output

**Clarification Necessity Result** — clarification required · clarification optional · clarification unnecessary · business impact · accounting impact · supporting reasoning.

## Boundary

**Can:** evaluate decision impact · determine necessity · preserve reasoning.

**Cannot:** generate clarification requests · modify accounting decisions · modify uncertainty.

## Failure Behaviour

**If necessity cannot be determined safely, default to Clarification Required. Never silently ignore uncertainty.**

The asymmetry is deliberate: an unnecessary question costs time, a missed one costs correctness.

## Future Notes

- This is the gate for the whole engine. A verdict of *unnecessary* means no Clarification Request exists and the Accounting Decision goes to Validation alone.
- Most transactions should stop here. That is the design working, not the engine failing to find anything.
