# NEXT_TASK.md

> **Pointer, not a copy.** Priorities live in [`TODO.md`](TODO.md), which already carries
> every task with an ID, a priority, a status and its dependencies.

**Next, once `mutation` produces a valid score at or above its floor:**

1. **T-014** — promote `mutation` to a *required* check. **Blocked, and the reason is
   stronger than it was:** the gate has never produced a valid score on this branch at all
   (`KNOWN_FAILURES.md` F-029), so the lifecycle's first step — *passes on correct code* —
   is not satisfied. The 99.3% at 1593 mutants recorded here previously was measured
   **@ `d85861c`** (killed 1364, survived 9, 24m14s — GitHub Actions) and is **EXPIRED**:
   the mutant population has since gone 1593 → 4402. It must not be used as the
   passes-on-correct-code proof. The deliberately-broken-code proof is still outstanding
   too, and changing the ruleset needs the owner.
2. **T-025** — kill the surviving mutants CI names.
3. **F-011 / F-012 / F-013** — the three Engine 1 architecture gaps integration exposed.
   Each changes a locked contract, so each is the owner's call, not an engineer's.

**Selection rule:** highest-priority unblocked item in `TODO.md`, P0 → P1 → P2 → P3.
