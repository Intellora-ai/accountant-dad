# STATE.md

**Resume point.** Read this first; it exists so a new session restarts in seconds
instead of reconstructing context from a conversation that no longer exists.

Updated: **2026-08-06**

---

## Where the work is

| | |
|---|---|
| **Current engine** | **Engine 1 — Input Engine** (Amendment 3, 2026-08-05) |
| **Current module** | none — every Engine 1 module is written and landed |
| **Current goal** | Make the `mutation` gate produce a **valid score**. It has never produced one |
| **Branch** | `ci/mutation-runs` · PR **#29** |
| **HEAD** | `baabfdb` · pushed · 0 commits ahead of `origin/ci/mutation-runs` |

## Every metric in this file — Law 56

**Every number produced before `baabfdb` is EXPIRED.** `src/` moved **+5785 / −801**
across 15 files since `7e0efe2`. Nothing is carried forward.

| Metric | Value | Commit | Source | Status |
|---|---|---|---|---|
| Mutation | — | `baabfdb` | — | **NEVER MEASURED** — see below |
| Coverage | — | `78e99d4` | — | **PENDING CI** |
| Suite | 3794 passed · 11 skipped | `78e99d4` | local `pytest -p randomly` | **LOCAL ONLY — NOT AUTHORITATIVE** |
| Mutation 90.6% | @ `2625b58` | job 92257409265 | GitHub Actions | **EXPIRED — do not quote** |
| Mutation 95.3% | @ `7e0efe2` | GitHub Actions run 31041552213 | GitHub Actions | **EXPIRED — do not quote** |
| Coverage 97.6449% | @ `7e0efe2` | GitHub Actions | GitHub Actions | **EXPIRED — do not quote** |

The previous revision of this file quoted those three against a HEAD that has since moved
by thousands of lines, and one of them was a **projection** rather than a result. That is
precisely the artifact Law 56 exists to prevent — *a green metric attached to code that
has since moved, read by someone deciding to merge.* They are struck above rather than
deleted, so the correction stays visible.

## Current failure — F-029

**The `mutation` gate has never produced a score on this branch.** Not a low score: no
score. Its statistics phase runs the suite once with `-x`, so one red test there ends the
phase and nothing is scored:

```
NOT SCOREABLE : 4402 (100.00% of 4402)
BLOCKED - 100.00% unscoreable, above the 2% maximum.
THE MUTATION SCORE IS INVALID and is deliberately not reported.
```

The 2% unscoreable cap did its job — it refused to print a number computed over nothing.

The red test was `test_the_pages_after_the_first_are_not_silently_dropped`, failing
because the parser stage failed **on CI only**. Three hypotheses are already REFUTED with
evidence (see `KNOWN_FAILURES.md` F-029): it is not a missing `also_copy` file, not
`docling-slim`, and not the mutmut trampolines. The surviving hypothesis — torch
initialised inside a forked child — is **NOT PROVEN**.

`c13930c` makes the failure print Docling's own `result.errors` instead of only naming
the stage, so the next CI run states the cause rather than requiring a guess.

## The false green found underneath it

CI printed `.F` — a pass, then a fail, and **the pass was the defect**. A parser failure
returns an artifact that still carries reader's real text, so the end-to-end test proving
*"a real document runs end to end"* was green against a document that never parsed. Fixed
at `c13930c`. Full account in `KNOWN_FAILURES.md` F-029.

## What can be done here — CORRECTED

**The previous revision said "mutation testing cannot run on macOS at all" (F-016). That
is DISPROVEN and the hand-patching workaround it prescribed is no longer necessary.**

The cause was never `fork()` after OpenCV/torch. It is `setproctitle`, which calls
CoreFoundation and is not fork-safe on macOS; mutmut calls it first in the forked child.
Measured A/B: `use_setproctitle` off → 2345 tried / 2020 killed; on → 1349 / 1349
segfaulted. mutmut **3.7.0** defaults it to `not Darwin`, so mutation now runs locally.

`LOCAL ONLY — NOT AUTHORITATIVE`, @ `3bd31e2`: a local run reached **1134 of 4402**
mutants before segfaulting inside `docling/document_converter.py:_get_pipeline`, the
model-loading path. Useful as diagnosis; not a score, and not quotable as one.

## Current next action

1. Read `coverage` and `mutation` for `78e99d4`.
2. Act on whatever the F-029 diagnostic prints — that is now the only unknown.
3. When mutation produces a valid score below the 93% floor, read the survivor list and
   make assertions stricter. **Never** by excluding a file, weakening an assertion, or
   moving the floor (Law 4, §J.4, Law 55).

## Waiting on the owner — three, none blocking Engine 1

All in `OWNER_DECISION_QUEUE.md`, each taken to a signature line:

- **D-A** the licence allowlist — measured; exactly one non-permissive licence exists
  across all 24 pinned distributions, and it is PyMuPDF
- **D-B** does the MVP ship as a container
- **D-C** `end-to-end` drives a browser the blueprint forbids

**D-D (PyMuPDF → pypdfium2) and F-001** remain owner items; the abstraction landed, so the
swap is now a one-file rewrite. F-004, F-006/T-004 and T-005 belong to the Brain and P4,
not to Engine 1 (permanent bottleneck rule).
