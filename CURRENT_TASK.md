# CURRENT_TASK.md

> **Pointer, not a copy.** The live detail lives in [`STATE.md`](STATE.md), which AEEP
> Part 7 already requires to carry Current Goal, Current Failure and Current Next
> Action. Duplicating it here would create two places to update and one to forget.

**Task:** finish Engine 1 completely — every gate green, every root cause eliminated.

**The one gate still red:** `mutation`. Law 55 — a mandatory gate below its threshold is
not a discussion, and merge is not available until it passes. 114 kills are pushed on
`7e0efe2` against the 64 that were needed; the CI number decides it, not the projection.

**Running in parallel, because none of these depend on the mutation result:**

| Work | Task |
|---|---|
| F-009 root cause — the OCR path has never executed on CI | T-046 |
| Benchmark harness — Engine 1 has **no** measured performance number | T-021 |
| End-to-end proof as a test rather than a session memory | T-047 |
| F-013 — whether extraction content can carry per-field confidence at all | — |
| F-010 — whether the Amendment 3 / §G9.5 contradiction is real | — |
| Red-team the cleaner for information it destroys | T-022 |
| Which of the 19 adversarial attacks are runnable today; uncovered failure paths | T-030, T-028 |
| `stub.py` duplication, and an architecture regression sweep after the rewire | T-029 |

**Full detail:** [`STATE.md`](STATE.md) · **Backlog:** [`TODO.md`](TODO.md)
