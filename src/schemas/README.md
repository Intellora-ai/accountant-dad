# schemas

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Purpose

The shape of the artifacts that cross between engines.

Every arrow in [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md) carries exactly one named artifact. Those artifacts are the system's real contracts — an engine may consume only what it was handed, so the shape of what is handed over is load-bearing.

## What will belong here

The artifacts named in [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md):

Document Evidence Object · Business Understanding Object · Accounting Decision · Question Set · Resolved Facts · Clarification Outcome · Validation Verdict · Approved Accounting Decision · Posting Result · Classified Error · Audit Record

Two of these wrap named components. Those components are shapes *within* an artifact, never artifacts in their own right — there is exactly one name for what crosses each arrow.

| Artifact | Components |
|---|---|
| **Document Evidence Object** | Document ID · Source references · **Structured Document** · **Confidence Report** |
| **Business Understanding Object** | **Transaction Story** · **Supporting Understanding Data** (the six Understanding Results) · **Identified Unknowns** · **Confidence Assessment** |

## What must not belong here

- Logic of any kind. A schema describes shape, not behaviour.
- Shapes internal to a single engine.

## Design notes for later

- Doubts, risks and low-confidence markers must be first-class parts of these shapes, not annotations — they are required to travel with the artifact at every stage.
- A gap must be *representable*. "Absent" and "zero" and "unknown" are three different things, and collapsing them would break the rule that a gap is never filled by inference.

## Status

Empty by design.
