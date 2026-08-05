# STATE.md

**Resume point.** Read this first; it exists so a new session restarts in seconds
instead of reconstructing context from a conversation that no longer exists.

Updated: **2026-08-05 19:35Z**

---

## Where the work is

| | |
|---|---|
| **Current engine** | **Engine 1 — Input Engine** (Amendment 3, 2026-08-05) |
| **Current module** | none — every Engine 1 module is written and landed |
| **Current file** | the Engine 1 test files (five of them, this session) |
| **Current goal** | Get the `mutation` gate green. It is the last red mandatory gate |
| **Branch** | `ci/mutation-runs` · PR **#29** |
| **HEAD** | `7e0efe2` |

## Current GitHub status — measured on `7e0efe2`

```
build                             pass
typecheck                         pass
lint                              pass
unit tests                        pass
coverage                          pass    97.6449% vs a 97.4643% ratchet
dependency scan                   pass
typecheck · lint · tests · build  pass    legacy combined gate
conformance · conformance suite   pass
mutation                          RUNNING ← the last red mandatory gate
```

## Current failure

The baseline failure described in the previous revision of this file is **fixed** and
the gate now completes. The last **complete** mutation run in project history
(job `92257409265`, commit `2625b58`) reported:

```
killed   2178
survived  227
timeout   953        excluded from the denominator by the gate's own scoring
score    90.6%       floor 93%
```

The gate scores `killed / (killed + survived)`. With `killed = 2178`, survivors must
reach **≤ 163** to clear 93% — so **64 kills** were required, not 63.

## What was done about it

Five agents, one per test file so none could collide, worked the 210 unique survivor
names. **114 killed**, all by making an existing assertion stricter or adding a case —
never by excluding a file, weakening an assertion, or touching the floor.

| Module | Survivors | Killed | Left, and why |
|---|---|---|---|
| `cleaner` | 69 | **50** | 19 equivalent — PyMuPDF ignores `filetype` and format-string case for a real stream, proven by measurement against the pinned build |
| `reader` | 101 | **27** | 72 unreachable without PaddleOCR (F-009); 2 equivalent — `.convert("RGB")` guarantees `uint8` whether or not `dtype=` is passed |
| `measurement` | 24 | **23** | 1 equivalent — `ensure_ascii=False` and `None` are equally falsy inside `json.dumps` |
| `config` | 8 | **7** | 1 equivalent — `json.loads` cannot produce a dict with a non-`str` key from any valid JSON, so the branch is unreachable |
| `classification` | 7 | **7** | — |

Projected: `killed 2292 / survived 113` → **95.3%**. **Projection, not a result** — Law 44
means the number does not exist until CI produces it.

## Current next action

1. Wait for `mutation` on `7e0efe2`.
2. If it clears 93%, every mandatory gate is green and Engine 1's CI obligation is met.
3. If it does not, read the new survivor list and repeat. **Never** by excluding a file,
   weakening an assertion, or touching the floor (Law 4, §J.4, Law 55).

## What cannot be done here

**Mutation testing cannot run on macOS at all** — F-016. mutmut forks, and `fork()`
after OpenCV/torch/Accelerate are loaded segfaults the child. Measured: 2133/2133
mutants segfaulted, zero usable data. **Every mutation hypothesis costs a full CI run
of roughly three hours.** Guess carefully.

Every agent this session worked around it the same way: mutmut 3.3.1's mutation
generator (`mutmut.file_mutation`) is a pure `libcst` transform with no fork, so the
exact mutant source can be produced locally, applied to the real module by hand, and
the RED/GREEN pair measured — with `__pycache__` purged before and after every swap,
because a length-preserving mutation restored inside one mtime tick leaves a `.pyc`
Python reuses. That is how a verification was faked once already.

## Waiting on the owner

Four P0 items, all in `TODO.md`, none of which block the mutation work:

- **F-001** PyMuPDF is AGPL-3.0 and this is a hosted commercial product
- **F-004** three locked docs specify confidence gating that decision A7 forbids
- **F-006 / T-004** golden set: 16 planned vs ~100 stated
- **T-005** the 16 confidence parameters have no values (blocks calibration only)
