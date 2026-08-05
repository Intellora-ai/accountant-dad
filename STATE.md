# STATE.md

**Resume point.** Read this first; it exists so a new session restarts in seconds
instead of reconstructing context from a conversation that no longer exists.

Updated: **2026-08-05 07:50Z**

---

## Where the work is

| | |
|---|---|
| **Current engine** | **Engine 1 — Input Engine** (Amendment 3, 2026-08-05) |
| **Current module** | none — every Engine 1 module is written and landed |
| **Current file** | `.github/workflows/testing.yml` (the `mutation` job) and the Engine 1 test files |
| **Current goal** | Get the `mutation` gate green. It is the last red mandatory gate |
| **Branch** | `ci/mutation-runs` · PR **#29** |
| **HEAD** | `0efb744` |

## Current GitHub status

```
build                             pass
typecheck                         pass
lint                              pass
unit tests                        pass
coverage                          pass    97.645% vs a 97.464% ratchet
dependency scan                   pass
typecheck · lint · tests · build  pass    legacy combined gate
mutation                          FAIL    ← the only red mandatory gate
```

## Current failure

`mutation` reports **3157 mutants "not checked"** — `BLOCKED - mutmut produced no
mutants to score`. The baseline suite is failing inside mutmut's `mutants/` copy, so
nothing can be scored. It fails in ~2m28s, far too fast to be the 500-minute cap.

This is the **second** time this class has bitten. The first was five tests reading
their own source, which mutmut rewrites; those are now guarded. This one appeared after
the 35 coverage tests landed in `27b44b3`.

**Known, separately:** when the gate last ran far enough to score anything it read
**87.7% against a floor of 93** — 938 killed, 131 survived. So there is a real score
regression waiting behind the baseline failure. Fixing the baseline reveals it; it does
not fix it.

## Current next action

1. Reproduce the `mutants/` baseline failure locally — that part **is** reproducible on
   macOS (it is the baseline phase, not the fork phase).
2. Identify which of the 35 new coverage tests fails under instrumentation, and guard it
   the way the other five are guarded.
3. Push. The mutation run then takes ~3 hours; it is the only way to see the survivors.
4. Kill the ~131 survivors. **Never** by excluding a file, weakening an assertion, or
   touching the floor (Law 4, §J.4, Law 55).

## What cannot be done here

**Mutation testing cannot run on macOS at all** — F-016. mutmut forks, and `fork()`
after OpenCV/torch/Accelerate are loaded segfaults the child. Measured: 2133/2133
mutants segfaulted, zero usable data. **Every mutation hypothesis costs a full CI run
of roughly three hours.** Guess carefully.

## Waiting on the owner

Four P0 items, all in `TODO.md`, none of which block the mutation work:

- **F-001** PyMuPDF is AGPL-3.0 and this is a hosted commercial product
- **F-004** three locked docs specify confidence gating that decision A7 forbids
- **F-006 / T-004** golden set: 16 planned vs ~100 stated
- **T-005** the 16 confidence parameters have no values (blocks calibration only)
