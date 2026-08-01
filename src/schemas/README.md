# schemas

> **Defined as of Phase 0.** Governed by [`docs/SYSTEM_INVARIANTS.md` INV-6](../../docs/SYSTEM_INVARIANTS.md#inv-6--every-canonical-artifact-has-a-specification-level-schema) — **schemas are architecture, not implementation.**
>
> **Phase 1 placeholder — no implementation.** Written after Engines 5 and 6 are locked, when every artifact exists. Canonical models live alongside these in [`../models/`](../models/).

## Purpose

The shape of the artifacts that cross between engines.

Every arrow in [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md) carries exactly one named artifact. Those artifacts are the system's real contracts — an engine may consume only what it was handed, so the shape of what is handed over is load-bearing.

## What will belong here

The artifacts named in [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md):

Document Evidence Object · Business Understanding Object · Accounting Decision · Clarification Request · Validation Verdict · Approved Accounting Decision · Posting Result · Classified Error · Audit Record

**Every artifact also carries** an Artifact ID, a Version, and its Parent Artifact Version(s) — the universal versioning rule in [`docs/DATA_FLOW.md` §11](../../docs/DATA_FLOW.md#11-artifact-versioning). A version is immutable once created; correction means a new version, never an edit.

Two of these wrap named components. Those components are shapes *within* an artifact, never artifacts in their own right — there is exactly one name for what crosses each arrow.

| Artifact | Components |
|---|---|
| **Document Evidence Object** | Document ID · Source references · **Structured Document** · **Human Business Context** *(optional)* · **Confidence Report** |
| **Business Understanding Object** | **Transaction Story** · **Supporting Understanding Data** (the six Understanding Results) · **Identified Unknowns** · **Confidence Assessment** |
| **Accounting Decision** | Decision ID · **Decision Status** · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts |
| **Clarification Request** | Clarification ID · Related Decision ID · **Related Artifact Version** · missing information · detected conflicts · required clarification · reason · affected decision · priority · supporting evidence references · Clarification Confidence · status |

**IDENTITY ≠ INTELLIGENCE.** `Document ID` and `Decision ID` are identifiers only — identity, traceability, lifecycle tracking, audit history. Neither may be shaped into anything a downstream engine could reason from.

**Internal artifacts do not belong here.** The **Accounting Treatment Result** never crosses an engine boundary; it is Engine 3's internal combination of the Ledger Recommendation, Tax Treatment Recommendation and Accounting Period Treatment.

## What must not belong here

- Logic of any kind. A schema describes shape, not behaviour.
- Shapes internal to a single engine.

## Design notes for later

- Doubts, risks and low-confidence markers must be first-class parts of these shapes, not annotations — they are required to travel with the artifact at every stage.
- A gap must be *representable*. "Absent" and "zero" and "unknown" are three different things, and collapsing them would break the rule that a gap is never filled by inference.

## Status

Empty by design.
