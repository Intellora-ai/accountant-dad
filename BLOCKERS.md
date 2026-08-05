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
| **F-010** | `CLAUDE.md` Amendment 3 and `ENGINE_1_ARCHITECTURE.md` §G9.5 contradict each other on classification | Two documents disagree; reconciling them is an ownership decision |

## Blocked on nothing — mine to fix, and being fixed

| ID | Blocker | Status |
|---|---|---|
| **F-014** | The `mutation` gate's baseline fails in `mutants/`, so nothing scores | 🔄 active |
| — | Score was **87.7%** against a floor of 93 when it last ran far enough to report | 🔄 behind F-014 |
| **F-016** | Mutation cannot run on macOS — mutmut forks, `fork()` after OpenCV/torch segfaults | ⬜ unfixable locally; CI is the only route |

## Structural, not blocking today

**F-008** — 17 of 23 CI checks bind nothing. A PR with the required six green and
fourteen red still merges. `merge gate` goes required **last**, when it can pass.
