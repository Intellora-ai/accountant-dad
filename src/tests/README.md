# tests

> **Defined as of Phase 0.** **Phase 1 placeholder — no implementation.**

## Purpose

**Verification that the system obeys its own architecture.**

## What will belong here

| Kind | Verifies |
|---|---|
| **Golden architecture tests** | The repository structure matches the specification — engine and sub-engine counts, no additions, no renames |
| **Repository invariants** | Each of the thirteen invariants in [`docs/SYSTEM_INVARIANTS.md`](../../docs/SYSTEM_INVARIANTS.md), stated as a checkable assertion |
| **Simulation tests** | A transaction traversing the pipeline, asserting ownership, provenance and confidence rules hold at every boundary |
| **Specification verification** | Documents do not contradict each other — naming, ownership, precedence |

## Why invariants must be executable

An invariant expressed only in prose will be violated silently within a month of coding.

*"No engine may merge origins into a single anonymous fact"* is a rule; it needs an assertion. *"Confidence is recalculated whenever evidence changes"* needs one too. **The specification's authority evaporates the moment code exists unless the invariants can fail a test.**

Every invariant in `SYSTEM_INVARIANTS.md` gets a corresponding check here. **No invariant without verification** is a requirement of the Final Consistency Pass.

## Status

Empty by design. There is nothing to test yet.
