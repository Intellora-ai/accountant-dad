# confidence

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#84-confidence).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Every downstream engine needs to know how much of this extraction to trust. Measure reliability of extracted information.

## Responsibility

Owns uncertainty estimation — the honest measurement of extraction trustworthiness, per field and overall, and the identification of the specific regions and fields that are weak.

## Input

The outputs of [`cleaner`](../cleaner/), [`reader`](../reader/) and [`parser`](../parser/).

## Output

- Confidence scores.
- Uncertainty markers.
- Reliability assessment.

Together these form the **Confidence Report**, a component of the Document Evidence Object.

Example shape:

```text
Amount confidence:  98%
Vendor confidence:  82%
Date confidence:    65%
```

## Boundary

**Can:** detect uncertain extraction · score reliability · highlight risky fields.

**Cannot:** increase confidence without evidence · hide uncertainty · make accounting decisions.

It cannot re-read, re-parse or correct anything, and cannot reject a document or halt the pipeline. It measures extraction quality, never whether the content makes commercial sense.

## Decision Authority

**Owns.** Reliability estimation.

**Determines.** Confidence scores · uncertainty markers · risky extraction areas.

**Cannot.** Hide uncertainty · change extracted facts.

No other component may override this result — not a sibling sub-engine, and not the parent Input Engine, which assembles outputs but never overrides them. See [`docs/ENGINE_1_INPUT_ENGINE_RULES.md` §3A](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#3a-decision-authority).

## Failure Behaviour

**Reduce confidence and explain the uncertainty.**

- Where reliability cannot be established, confidence goes down — never up, and never to a default "good enough" value.
- Every uncertainty marker carries a reason; a bare score cannot become a good question downstream.
- Uncertainty is never suppressed because it would delay processing.

## Future Notes

- The Confidence Report within the Document Evidence Object is read much later by Clarification's `uncertainty_detection` and by Validation's `data_validation`. Per-field granularity matters more than a single overall score.
- Low confidence never triggers guessing. It creates uncertainty markers and a *possible future clarification requirement* — judged material or not by a different engine entirely.
