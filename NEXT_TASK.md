# NEXT_TASK.md

> **Pointer, not a copy.** Priorities live in [`TODO.md`](TODO.md), which already carries
> every task with an ID, a priority, a status and its dependencies.

**Next, once `mutation` is green:**

1. **T-014** — promote `mutation` to a *required* check. It has passed on correct code
   (99.3% at 1593 mutants); the lifecycle still needs the deliberately-broken-code proof
   before promotion. Changing the ruleset needs the owner.
2. **T-025** — kill the surviving mutants CI names.
3. **F-011 / F-012 / F-013** — the three Engine 1 architecture gaps integration exposed.
   Each changes a locked contract, so each is the owner's call, not an engineer's.

**Selection rule:** highest-priority unblocked item in `TODO.md`, P0 → P1 → P2 → P3.
