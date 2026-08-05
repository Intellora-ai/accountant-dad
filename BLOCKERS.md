# BLOCKERS.md

> **Index, not a copy.** Every blocker's full detail lives in
> [`KNOWN_FAILURES.md`](KNOWN_FAILURES.md) with its root cause, impact, attempted
> workarounds and permanent fix. This file exists so the question *"what is stopping
> us right now"* has a one-screen answer.

Updated: **2026-08-05**

## Blocked on the owner — an engineer may not decide these

| ID | Blocker | Why only the owner |
|---|---|---|
| **F-001** | PyMuPDF is **AGPL-3.0**; this is a hosted commercial product, so §13 is triggered | Buy the Artifex licence or amend a **locked** stack. Both are commercial/legal calls |
| **F-004** | Three locked documents specify confidence gating that decision **A7 forbids** | Needs a §M amendment carrying the owner's approval and date |
| **F-006** | Calibration is put at ~100 golden documents; **16** are planned | Spending 6× the labelling effort is a budget decision |
| **T-005** | All **16** confidence parameters are UNSET | Law 54 — an engineer inventing one is the exact failure the rule prevents |

## Blocked on nothing — mine to fix, and being fixed

| ID | Blocker | Status |
|---|---|---|
| **F-014** | The `mutation` gate's baseline failure is **fixed** — the gate completes and scores | ✅ closed |
| **F-045** | Score was **90.6%** on the last complete run. 64 kills were needed; **114 delivered**. Awaiting the CI number | 🔄 active |
| **F-018** | **Three Engine 1 modules are wired to nothing** — `classification`, `config`, `measurement` have zero consumers in `src/`. Same shape as F-012 | 🔄 agent wiring it |
| **F-010** | Classification's authorisation — **half resolved, half re-opened.** See below | 🔒 owner, on the narrower question |
| **F-016** | Mutation cannot run on macOS — mutmut forks, `fork()` after OpenCV/torch segfaults | ⬜ unfixable locally; CI is the only route |

**Why F-010 moved.** The losing document self-declares *"Status: DRAFT — NOT FROZEN"*
and *"Where this document contradicts any of them, this document is wrong"*, and it
appears at **no level** of the precedence ladder in `SYSTEM_INVARIANTS.md:11-18`. §M
binds *frozen* documents; a draft is revised, not amended. Nothing here was ever the
owner's to decide.

It was listed here because this file's "Why only the owner" column paraphrased
`KNOWN_FAILURES.md` — and that entry contradicted itself, resolving the question by
precedence in one paragraph and calling it *"the owner's call"* four lines later. The
paraphrase copied the wrong half. This file calls itself *"Index, not a copy"*; the
column was a copy, so it is now a pointer.

## Structural, not blocking today

**F-008** — 17 of 23 CI checks bind nothing. A PR with the required six green and
fourteen red still merges. `merge gate` goes required **last**, when it can pass.
