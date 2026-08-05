# PROGRESS.md

The engineering journal. Appended after every meaningful work session — never
rewritten, never summarised away. Routine progress belongs here, not in chat.

**Local execution is not the source of truth. GitHub CI is** (`CLAUDE.md` Law 44).
Every number below says which one produced it.

---

## 2026-08-05 (later) · Engine 1 is built; the mutation gate outgrew its clock

### Completed

**Engine 1 has every module it was authorised to have.** Four sub-engines, the engine's
own assembly, classification, config, measurement, and a pipeline that runs a real
document end to end.

```
cleaner  reader  parser  confidence  assembly  classification  config  measurement  pipeline
```

**`classification` needs no threshold at all**, which is the nicest result of the day.
The three-way outcome is decided by structural pattern matching on tuple *shape* —
`case ()` / `case (only,)` / `case multiple:` — never a numeric comparison. Parameter #9
`classification_accept` stays UNSET and unused. A red-team mutation inserting a
*behaviour-preserving* `if len(candidates) == 0:` was caught by the AST test **and by
nothing else**.

**Integration found four defects that isolation could not.** Every module was green
alone; the chain is where the truth was:

- **F-011** `cleaner.decode` cannot decode a PDF at all — `cv2.imdecode` returns `None`,
  so it raises unconditionally on the MVP's primary input. 57 cleaner tests missed it
  because every one feeds it an image.
- **F-012** the pipeline is **not a pipe**. `reader` and `parser` each re-open the raw
  document; neither consumes `cleaner`'s output. Cleaning currently changes nothing
  downstream — the 0.0017 deskew residual included.
- **F-013** extraction content can never carry a per-field confidence.
- **F-015** the Table Transformer is rebuilt **once per table** — 1.68 s per call, warm
  cache, in production.

**`timm` was undeclared, and exactly one test out of 51 could see it.** With it absent,
50 parser tests pass and the suite looks healthy; the one that runs the real table model
raises `ImportError` from inside `transformers`.

**Two false greens withdrawn.** A "2068 passed" I had reported as evidence ran against
`numpy 2.3.5` and `cv2 4.10.0` while the manifest pinned `2.5.1` and `5.0.0.93` — both
silently overridden by PaddleOCR's tree. CI refused the same install outright; only CI
told the truth.

### GitHub status — `42d2aa4`

```
build                             pass    29s
typecheck                         pass  2m21s
lint                              pass    20s
unit tests                        pass  5m14s
coverage                          pass  6m34s     97.645% vs a 97.464% ratchet
dependency scan                   pass    45s
typecheck · lint · tests · build  pass  5m35s     ← legacy gate, fixed this session
mutation                          ✗ CANNOT FINISH
```

### Numbers

| | |
|---|---|
| Local suite | 2315 passed · 11 skipped · 0 failed |
| Coverage | **97.645%**, floor 97.464% (ratchets to `main`) — margin +0.18pp |
| Suppressions | **124**, unchanged all session |
| Engine 1 | 4,042+ lines source, ~4,500 lines tests |
| Mutants | 1593 → **2933** (+84%) |
| Mutation | ✅ 24m14s / 99.3% at 1593 · ❌ cancelled at 100 min at 2933 |

### Blockers

**F-014 — the mutation gate needs a larger `timeout-minutes`, and that is a number
standing rule 10 forbids an engineer setting.** Four workarounds were tried and rejected
first: cache the model (reverted — see below), lazy imports (already correct), exclude
`parser.py` or drop the Docling tests (**refused** — making a gate pass by measuring
less), lower the floor (never).

The F-015 caching fix was implemented **twice** and reverted both times. Module-level
Protocols cost 0.057pp of coverage; moving them under `TYPE_CHECKING` cost 0.66pp
because the classes then never execute, and the repo forbids a non-empty
`exclude_lines`. It also does not help the mutation clock — each mutant is a fresh
process. Correct fix, wrong moment; recorded rather than forced through.

### Next work

Unblocked: T-025 (9 surviving mutants), T-022 (red-team `cleaner`), T-024 (citation
sweep), Brain expansion. Blocked on the owner: F-014's number, plus the four standing P0s.

---

## 2026-08-05 · Engine 1 sub-engines land, and the mutation gate finishes for the first time

### Completed

**The mutation gate passed. It had never once finished.**

The received wisdom was that it was failing on score — 65.7%, then 99.0%. Both numbers
were beside the point. It was being **cancelled** by `timeout-minutes: 10` at 62.6% of
the way through the mutant list. Three hypotheses were tested and two were killed:

```
✗  "the 77 timeout-mutants are the cost"
   FALSE. In the slow band a timeout takes 2.234s and a non-timeout 2.326s —
   indistinguishable. If every timeout were free the job still needs 10.6 min.

✗  "the unscored tail is cheaper"
   BACKWARDS. mutmut sorts ascending by estimated cost (__main__.py:1023), so the
   596 unscored mutants carried 3.45× the estimated work of the 997 scored, in 60%
   as many mutants.

✓  "no lever exists except the clock"
   Caching: mutmut 3.3.1 overwrites exit_code_by_key with all-None before anything
   reads it (__main__.py:268) — a restored cache saves 23.3s out of 593s.
   Parallelism: --max-children already defaults to cpu_count.
   Faster tests: the per-mutant timeout has a hard 15.00s floor from a +1 term, so
   total achievable movement across all 1593 mutants is 0.5 seconds.
```

Cap raised to **100 minutes** — the owner's number, given against a measured bracket of
10.8 min (provable floor) / 24.1 (mid) / 32.7 (upper).

**Engine 1 went from one sub-engine to four, plus assembly.**

Roughly 30 agents were dispatched across the session. A session limit killed most of
them mid-run. **No work was lost** — every killed agent's output was recovered from its
worktree and finished rather than restarted.

```
cleaner             746 src   already landed
reader              535 src / 716 tests   PyMuPDF text layer, PaddleOCR otherwise
parser              662 src / 725 tests   Docling structure, never meaning
assembly            298 src / 465 tests   four parts → Document Evidence Object
confidence_report   444 src / no tests    ← agent running
config              626 src / no tests    ← agent running
measurement         410 src / no tests    ← agent running
```

**Three real defects found while landing, none a style point:**

1. **`reader.py` resolved PaddleOCR at module scope.** The module reaches it through
   `importlib` deliberately (no `py.typed`, so a plain import is a `mypy --strict`
   error) and then defeated that by calling at import time. Importing the Input Engine
   at all required a ~500 MB ML package, so every gate that merely imports the package
   died at collection. Moved inside the already-`@cache`d builder.
2. **`assembly`'s test imported `DocumentId` from `identity.py`.** It lives in
   `artifacts/evidence.py:290`. The source had it right, the test had it wrong — the
   shape of error you get when two agents code against a contract in parallel.
3. **Two magic `2`s that were the assertion itself**, now named
   `BOTH_DISAGREEING_READINGS` and `CORRECTED_VERSION`.

**Confidence specification written** — 666 lines, nine sections. The owner's decision
existed only as a chat message; it is now a document. Writing it down surfaced four
problems that were invisible while it was prose: F-003 through F-006 in
`KNOWN_FAILURES.md`.

**Seven atomic concepts** landed with every citation verified against six independent
layers. Evidence Library: **41 declared, 41 present, 0 missing**.

### Files changed

```
d85861c  .github/workflows/testing.yml            1 line   timeout-minutes 10 → 100
3b906b6  engines/input_engine/{reader,parser,assembly}.py + 3 test files
         requirements-engine1.txt                 +4 pins, 2 hazards recorded
30f54af  docs/CONFIDENCE_SPECIFICATION.md         666 lines
         docs/ENGINE_1_ARCHITECTURE.md
         Accounting_Brain/Atomic_Concepts/        7 concepts
         Accounting_Brain/Evidence_Library/       GST state codes + sidecar + manifest
```

### Tests executed

```
LOCAL   2068 passed · 14 skipped · 0 failed · 321.71s
        (the 14 are the parser's Docling measurements, skipped with a message
         that says plainly they are not CI evidence)
```

### GitHub status — on `d85861c`, the last commit CI has fully judged

```
build             pass    35s
typecheck         pass    40s
lint              pass    20s
unit tests        pass    47s
coverage          pass  1m00s
dependency scan   pass    39s
mutation          pass   24m14s   ← first completion ever
```

**ALL SEVEN MANDATORY GATES GREEN.**

CI on `3b906b6` and `30f54af` is pending at the time of writing.

### Numbers

| | |
|---|---|
| Mutation score | **99.3%** (floor 93%) — killed 1364, survived 9, timeout 220 |
| Mutation runtime | **24m14s** against a 24.1 min mid projection |
| Coverage | passing its floor (exact figure: see the CI job) |
| Suppressions | **124** against a 128 baseline — a decrease, which the gate allows |
| Evidence documents | 41 declared, 41 present |

### Blockers

Two need the owner and nothing else unblocks them:

- **F-001** PyMuPDF is AGPL-3.0 and this is a hosted commercial product.
- **F-004** Three locked documents specify confidence gating that decision A7 forbids.

### Next work

`T-010`/`T-011` (tests for the three untested modules) are in flight. Then `T-015`,
Engine 1 integration — the sub-engines exist as units and nothing yet runs a real
document end to end through all five. Then `T-014`, promoting `mutation` to a required
check, which needs the deliberately-broken-code proof first.

### Overall

Engine 1 is **four of four sub-engines written**, three of them tested and landed.
Not integrated. Not measured against ground truth — and by Law 52 no accuracy claim
about this system is provable yet, so none is made here.
