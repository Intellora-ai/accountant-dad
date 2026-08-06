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
coverage                          pass  6m34s     97.645% @ 42d2aa4 (EXPIRED) vs a 97.464% ratchet
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
| Mutants | 1593 → **2933** (+84%) — @ commit `42d2aa4`, **EXPIRED** |
| Mutation | ✅ 24m14s / 99.3% at 1593 (`d85861c`) · ❌ cancelled at 100 min at 2933 (`ed5d504`). Both **EXPIRED** |

### Blockers

**F-014 — the mutation gate needs a larger `timeout-minutes`, and that is a number
standing rule 10 forbids an engineer setting.** Four workarounds were tried and rejected
first: cache the model (reverted — see below), lazy imports (already correct), exclude
`parser.py` or drop the Docling tests (**refused** — making a gate pass by measuring
less), lower the floor (never).

The F-015 caching fix was implemented **twice** and reverted both times. Module-level
Protocols cost 0.057pp of coverage @ commit `42d2aa4`; under `TYPE_CHECKING`, 0.66pp
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

The received wisdom was that it was failing on score — 65.7%, then 99.0%, both from
cancelled runs predating `d85861c` and both **EXPIRED**. Both numbers were beside the
point. It was being **cancelled** by `timeout-minutes: 10` at 62.6% of the mutant list. Three hypotheses were tested and two were killed:

```
✗  "the 77 timeout-mutants are the cost"
   FALSE. In the slow band a timeout takes 2.234s and a non-timeout 2.326s —
   indistinguishable. If every timeout were free the job still needs 10.6 min.

✗  "the unscored tail is cheaper"
   BACKWARDS. mutmut sorts ascending by estimated cost (__main__.py:1023), so the
   596 unscored mutants carried 3.45x the estimated work of the 997 scored, in 60%
   as many mutants. Measured @ commit d85861c; EXPIRED, and the RATIO is the finding.

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

---

## 2026-08-05 (evening) · One pipeline, and 114 mutants killed

### Completed

**The pipeline became a pipe** — `412eed6`. `reader` and `parser` each used to re-open
the raw document, so cleaning changed nothing downstream (F-012). Both now read
`cleaned.artifact.payload`. The legacy `rasterise_first_page_for_cleaning` adapter was
**deleted**, not deprecated, and `_payload_of` **refuses** a missing artifact rather
than falling back to the original — a fallback would silently reinstate two pipelines
while every test kept passing.

Three tests replaced the two that died with the adapter. One asserts on `run`'s own
source (guarded against mutmut instrumentation), so the bypass cannot return quietly.

**114 mutation survivors killed** — `6d76270`, `73b1a0d`, `efddfb6`, `7e0efe2`. Five
agents, one per test file so none could collide.

| Module | Survivors | Killed | Left alive, and why |
|---|---|---|---|
| `cleaner` | 69 | **50** | 19 equivalent — PyMuPDF ignores `filetype` and format-string case for a real stream, measured against the pinned build |
| `reader` | 101 | **27** | 72 unreachable without PaddleOCR (F-009); 2 equivalent — `.convert("RGB")` guarantees `uint8` regardless of `dtype=` |
| `measurement` | 24 | **23** | 1 equivalent — `ensure_ascii=False` and `None` are equally falsy inside `json.dumps` |
| `config` | 8 | **7** | 1 equivalent — `json.loads` cannot produce a dict with a non-`str` key from any valid JSON |
| `classification` | 7 | **7** | — |

Every kill is an assertion made **stricter** or a case **added**. No file excluded, no
assertion weakened, no floor touched (Law 4, §J.4, Law 55).

### The root cause of the survivors, named once

Almost every survivor was the same defect wearing a different mask: **a test that
checked a fragment of a message instead of the message.** `pytest.raises` with no
`match=`, `assert "no type is guessed" in reasons[0]`, `len(reasons) == 1`. mutmut
rewords, wraps, re-cases and re-separates string literals; a fragment check sees none
of it.

### The trap that ate an hour, recorded so it is not re-derived

mutmut's `"XX" + literal + "XX"` mutation is **not** killed by a substring check. The
wrapped string still *contains* the original contiguously, so `assert "text" in message`
stays green. Only exact equality catches it. One agent hit this empirically, and the
finding was relayed to the other three mid-run.

The exception: a multi-occurrence separator such as `", ".join(...)` mutated to
`"XX, XX".join(...)` **is** caught by a substring check, because the marker lands
between every pair of items rather than only at the two ends.

### Method, given F-016

Mutation cannot run on macOS at all. Every agent used the same route instead: mutmut
3.3.1's mutation generator (`mutmut.file_mutation`) is a pure `libcst` transform with
no fork, so the exact mutant source is producible locally. Applied by hand to the real
module, RED measured, reverted, GREEN measured — with `src/**/__pycache__` purged
before **and** after every swap, because a length-preserving mutation restored inside
one mtime tick leaves a `.pyc` Python happily reuses. That already faked one
verification pass in an earlier session.

### Files changed

```
src/accountant_dad/engines/input_engine/pipeline.py      rewired, adapter deleted
tests/unit/test_input_engine_pipeline.py                 3 tests replace 2
tests/unit/test_input_engine_cleaner.py                 +175 −1
tests/unit/test_input_engine_measurement.py             +263
tests/unit/test_input_engine_reader.py                  +148
tests/unit/test_input_engine_classification.py           +23 −5
tests/unit/test_input_engine_config.py                   +68 −1
```

`src/` was untouched by all five agents — verified byte-identical after every RED/GREEN
round trip.

### Tests executed — local, therefore provisional (Law 44)

```
ruff check src tests          All checks passed!
ruff format --check src tests 86 files already formatted
mypy src tools/ci tests       Success: no issues found in 92 source files
pytest tests/unit -q          2361 passed, 11 skipped
suppressions                  124  (unchanged)
coverage                      97.6449% @ 7e0efe2  vs a 97.4643% ratchet
```

**LOCAL ONLY — NOT AUTHORITATIVE.** Every figure in that block is **EXPIRED**: it belongs
to commit `7e0efe2` and `src/` has moved `+2591 / −300` lines since.

### GitHub status — on `7e0efe2`

```
build · typecheck · lint · unit tests · coverage · dependency scan   pass
conformance · conformance suite · secret scan · CodeQL               pass
mutation                                                             RUNNING
```

### Numbers

| | |
|---|---|
| Last complete mutation run | `2625b58` — killed 2178, survived 227, timeout 953, **90.6%** against a floor of 93 |
| Survivors needed to clear 93% | **≤ 163**, because the gate scores `killed / (killed + survived)` and excludes timeouts |
| Kills required | **64** |
| Kills delivered | **114** |
| Projected score | 2292 / 2405 = **95.3%** — a projection, not a result. It does not exist until CI says it |

**CI has since said it, and the projection was right.** `95.3%` @ commit `7e0efe2`
(GitHub Actions run 31041552213) — killed 2324, survived 115, 919 not scoreable. **That
result is itself now EXPIRED**: `src/` moved `+2591 / −300` lines after it.

### Blockers

Unchanged, all four need the owner: **F-001** PyMuPDF AGPL-3.0 · **F-004** confidence
gating that A7 forbids · **F-006 / T-004** golden-set size · **T-005** the 16 unset
confidence parameters.

### Next work

Wait for `mutation` on `7e0efe2`. If it clears, every mandatory gate is green. If it
does not, read the new survivor list and repeat.

### Overall

Engine 1 is one pipeline for the first time. Its CI obligation is one gate from met.
Still not measured against ground truth — by Law 52 no accuracy claim is provable, so
none is made here.

---

## 2026-08-06 · The mutation gate went green and the number expired the same day

### The one sentence that matters

**Every number this repository could quote is now EXPIRED, and HEAD does not build.**

### Completed

**The mutation gate cleared its floor.**

```
Mutation
95.3%                       killed 2324 · survived 115 · 919 not scoreable
Commit : 7e0efe2
Source : GitHub Actions run 31041552213, job 92426852650
Runtime: 3h 21m 01s
Status : VERIFIED — and now EXPIRED
```

That closes **F-014**. The cap had been the blocker; `66ab8cd` raised
`timeout-minutes` to 500 on the owner's number and the job finished. It has **no guarding
test** — a CI `timeout-minutes` is configuration and nothing in `tests/` asserts it — which
is recorded as a finding under Law 3 rather than glossed as done (`T-055`).

**Law 56 landed, and immediately invalidated the number above.** `6a5dbb3` and `c1eb9be`.
A measurement is bound to the exact commit that produced it; the instant source changes it
expires and may never be reused, quoted as current, or used for a decision. Seven
enforcement layers, including a `PreToolUse` hook that refuses an uncited metric **before
the write lands**. Owner-approved, 2026-08-06. Recorded as **D-007**.

What forced it: the 95.3% above is real, CI-produced and correct, and it stayed quotable
while ~3,000 lines of source moved under it. *"Nothing was wrong with the number.
Everything was wrong with quoting it."*

**Seven defects fixed, each with a commit and a guarding test.**

| | Fixed at | Guarded by |
|---|---|---|
| **F-014** mutation cap | `66ab8cd` | ❌ none — a finding |
| **F-020** the wheel shipped an unimportable Engine 1 | `839645a` | `test_declared_dependencies.py` — derives the import set from the AST |
| **F-021** the build freeze checked filenames, not code | — | `test_package.py`, three named AST tests |
| **F-023** a pinned version could be violated while every check was green | `5066576` | `test_runtime_library_versions.py`, `tools/ci/assert_imports_match_pins.sh` |
| **F-009** the OCR skip guard | `202bed4` | `test_input_engine_reader.py:89` |
| **F-012** the pipeline was not a pipe | `412eed6`, `6b32425`, `41b23e6`, `d29985a` | `test_input_engine_pipeline.py` |
| **D1–D4** four `cleaner` content-destruction defects | `1e0df65`, `590c6bb` | `test_input_engine_cleaner_redteam.py` — 22 tests |

**F-009 was worse than it had been recorded.** The skip guard called
`find_spec("paddlepaddle")` — a **distribution** name. The module is `paddle`. So it
reported *missing* in **every possible environment**, including the OCR venv built
specifically to run those 11 tests. They had **never executed on any machine**, and nobody
noticed because a skip is green. Re-rated MEDIUM → HIGH.

**`cleaner`'s four defects were one class, and the class was fixed.** *A destructive step,
or the audit that reports on it, consulted the rule that caused the damage.* The crop's
retention was counted with the same Otsu mask that drew the box, so it could only ever
report 1.0. The box is now drawn from the line profiles and the retention counted at Otsu's
split — two independent rules, so the figure can move. Measured at `1e0df65` on a 600×900
scan at sigma 14: `ink_kept_by_crop = 0.9998077292828302`, which is `46800/46809` to the
bit; the same page without the margin mark returns exactly `1.0` on all 14 seeds tried.
**Recorded as D-013.**

**Engine 1 stopped raising where its contract says emit** — `1e65b91`. A business outcome
(*this scan is unreadable*) was indistinguishable from a crash (*the code is broken*), so
the Application Layer could not route them differently. The business/runtime line was
**read** off three locked documents, not invented. `VisionFallbackUnavailableError` and
`ParserDependencyMissingError` deliberately still raise: **a missing tool is not a bad
document**, and saying *"unreadable"* about a fine file is worse than crashing. **D-009.**

**Conformance: a crash stopped counting as an enforcement** — `e921c3c`. A negative control
that crashed had been scoring as `ENFORCED`; `Attribution.CONTROL_CRASHED` is the fourth
outcome. And the registry's honest gap was measured: **45 hand-listed rules against 143
prohibition clauses in `docs/`**, with nothing comparing the two. Every clause must now be
cited or excluded with a written reason. **D-012** — and that decision **shipped
incomplete**, see below.

### Red — and both are at HEAD

**1. The repository does not build.** `e921c3c` imports `Exclusion` from
`accountant_dad.conformance` at `test_conformance_registry.py:74`. The dataclass was never
written: the docstring explains it at `conformance.py:100`, the `Uncovered` enum that gives
it its reasons is at `:148`, and the class itself is absent. `pytest tests/` dies at
collection — **not one test runs.** Its parent `b3c1b51` does not import the name, so the
commit introduced it. **Law 1. Recorded as F-024, T-050.**

**2. Thirty-nine red tests, one cause.** `pipeline.run` gained a required keyword-only
`recorded_at`. `b3c1b51` fixed the Application Layer's side — *"two agents changed opposite
sides of the same call and neither saw the other"* — but two files recovered at `211c6b0`
predate the change and mention `recorded_at` **zero times**:

```
test_input_engine_pipeline_redteam.py   1081 lines   recorded_at: 0   NOT RUNNING
test_input_engine_ablation.py            631 lines   recorded_at: 0   NOT RUNNING
test_input_engine_pipeline.py                        recorded_at: 24  updated
test_engine1_end_to_end.py                           recorded_at: 4   updated
```

Those two files are what guards F-012's `reader → parser` pipe and Engine 1's identity-leak
boundary. They cannot fail, so they prove nothing. **F-025, T-051.** The general rule is
**D-015**: recovered work is untrusted until it has **run**, not until it is committed.

### Tests executed — LOCAL ONLY, NOT AUTHORITATIVE (Law 44)

```
Commit: e921c3c
pytest tests/                        1 error during collection, interrupted   (F-024)
pytest tests/ --ignore=<that file>   17 failed · 2565 passed · 11 skipped · 23 errors
                                     273.97s
```

Of the 40 failures and errors: **39** are `TypeError: run() missing 1 required keyword-only
argument: 'recorded_at'`, and **1** is a correct test failing against a real defect —
`test_every_extracted_value_that_crosses_the_boundary_carries_source_confidence_and_uncertainty`.
That one must not be eased (Law 4, §J.4).

### GitHub status

**There is none for HEAD.** Measured against the API on 2026-08-06:

```
origin/ci/mutation-runs   f31e3cd
local HEAD                e921c3c        24 commits ahead, unpushed
GET /commits/e921c3c/check-runs    422  "No commit found for SHA"
GET /commits/0babf47/check-runs    422  "No commit found for SHA"
```

On `f31e3cd`, the last commit GitHub has judged — and which is **docs-only** against
`7e0efe2`, so the source it measured is identical:

```
GREEN   build · typecheck · lint · unit tests · coverage · dependency scan
        mutation · conformance · conformance suite · secret scan · CodeQL
        typecheck · lint · tests · build   (legacy combined gate)
RED     adversarial tests · docker build · end-to-end · golden dataset
        integration tests · license scan · merge gate · negative controls
        negative controls 9 of 9 · performance · semgrep
```

**Required checks re-verified against ruleset `20249495`:** still exactly six — `build`,
`typecheck`, `lint`, `unit tests`, `coverage`, `dependency scan`. Eleven red checks bind
nothing. **`license scan` and `semgrep` are two reds F-008 never listed.**

### Numbers — every one with the commit that produced it

| Metric | Value | Commit | Source | Status |
|---|---|---|---|---|
| Mutation | 95.3% — killed 2324, survived 115, 919 not scoreable | `7e0efe2` | GitHub Actions run 31041552213 | **EXPIRED** |
| Mutation runtime | 3h 21m 01s | `7e0efe2` | GitHub Actions, same job | **EXPIRED** |
| Coverage | 97.64%, effective floor 97.46% | `f31e3cd` | GitHub Actions run 31047186940 | **EXPIRED** |
| `src/` churn since | +2591 / −300 lines, 10 files | `7e0efe2`→`e921c3c` | `git diff --shortstat` | measured |
| `tests/` churn since | +13335 / −148 lines, 18 files | `7e0efe2`→`e921c3c` | `git diff --shortstat` | measured |
| Mutation · coverage · every gate at HEAD | — | `e921c3c` | — | **UNMEASURED** |

Previous measurements expired because source changed after commit `7e0efe2`. Stated
proactively, per Law 56, not on request.

### Blockers

**Engineering, and nothing else unblocks them:** `T-050` the build · `T-051` the 39 red
tests · then `T-052` push, so CI can produce a current number for anything at all.

**The owner, and these are genuinely his:**
- **T-048 / F-019** — `Provenance.confidence` needs an absent-measurement state. A PDF text
  layer has no honest score, `1.0000` is the forbidden default and `0.0000` is a lie the
  other way. §M amendment to a frozen P2 schema. **This is the MVP's primary input.**
- **T-049 / F-010** — `ENGINE_1_INPUT_ENGINE_RULES.md:352` says *"exactly four"* sub-engines;
  Engine 1 ships nine modules. That document **is** on the precedence ladder, so unlike the
  §G9.5 conflict this cannot be settled by precedence.
- Unchanged: **F-001** PyMuPDF AGPL-3.0 · **F-004** confidence gating A7 forbids ·
  **F-006/T-004** golden-set size · **T-005** the 16 unset parameters.

### Next work

Fix the build. Fix the signature. Push. Then, and only then, a number exists again.

### Overall

The honest summary is that this session **fixed seven real defects and ended with a
repository that does not compile its own test suite**. Both halves are true and the second
one governs: by Law 55 merge is not discussable, and at HEAD not one mandatory gate even has
a value to compare against its threshold.

Still not measured against ground truth. By Law 52 no accuracy claim about this system is
provable, so none is made here.

---

## 2026-08-06 · F-019 and F-004 closed — a measurement has four outcomes

Base: `a467bb2`, the tip of `ci/mutation-runs`. Two owner approvals, both verbatim,
both acted on.

### What completed

**Amendment 7 — four measurement states.** `MEASURED · NOT_MEASURED · NOT_APPLICABLE ·
FAILED`, three concrete classes under one abstract base, each carrying a required
non-blank `basis`. No truth value, no ordering, no numeric conversion, no default at any
slot, immutable after construction. `records_the_same_measurement` extended, never
exempted: two DIFFERENT absences now disagree.

**Root cause, and it was one layer above the missing sentinel.** The architecture
modelled the RESULT of measuring — a number — and used `None` for everything else, while
`None` already meant four other things in the same pipeline. The absence of a measurement
had no name, and a fact with no name cannot be carried, checked or refused. A schema
demanding a number from a world that supplies one only sometimes leaves three moves:
invent, drop, or crash. This repository had done the first two.

**Table cells, F-019's unclosed half — and the entry's own diagnosis was off by a layer.**
A `parser.Cell` always carried its `box`, so the LOCATION was never missing. What was
missing is a **NAME**: every route that attaches a provenance is keyed by name.
`parser.map_cells` supplies it, and each cell then travels the same road a text region
already does — no `pipeline.py` change at all.

**Amendment 8 — Decision A7 is authoritative.** Five documents, not the three F-004
listed: `ACCOUNTING_DEFINITIONS.md` §6 and `APPLICATION_LAYER.md` were found by sweeping
every markdown file rather than trusting the list. Every purpose survives; only the stated
mechanism changed in each case.

**One of the five is applied by supersession, and the suite is what found it.**
`EXECUTION_QUEUE.md`'s clause is cited by CONTENT digest from
`conformance_registry.py:2119`, so editing the words breaks the citation — and that file
belongs to another workstream. The clause line is left byte-identical with a block beneath
it stating what it must be read as; the exact paired change for both files is recorded in
Amendment 8 and F-004. **A content-addressed citation catching a cross-workstream edit is
the mechanism working, not a defect.**

**Three defects found while closing them, all fixed:**

- `model_dump_json()` on any artifact carrying a stated absence raised
  `PydanticSerializationError`. **Pre-dated** the four states — Amendment 6's single
  sentinel had it too — and stayed invisible because no artifact carrying one had ever
  been dumped. An artifact that can be built and not written down cannot be audited.
- a capture-fidelity **mismatch** recorded nothing in `confidence_scores`, so that name
  appeared on a match and vanished on a mismatch — indistinguishable from no human note
  at all, and silent about the one case where a preservation guarantee had broken.
- a **missing field** raised an uncertainty marker with no reliability entry beside it.
## 2026-08-06 · Engine 1 — one cleaning entry point, one PDF backend, three modules that run

**Base:** `a467bb2` (tip of `ci/mutation-runs`). Worktree branch, not pushed.

### What completed

**F-017, second half.** `cleaner.clean(image, settings)` stopped being public. It had
**zero callers in `src/` outside `cleaner.py`** and **67 in `tests/`** — measured, not
estimated — so it was a second entry point kept alive by its own tests. It is now
`_clean_image`, the Image Cleaner that `CLEANERS` dispatches to, and `clean_artifact` is
the single Document Cleaner with **no branch on `kind`** in it.

**F-001, contained.** `accountant_dad/pdf_backend.py` is new and owns every PDF
operation. `reader.py`, `cleaner.py` and `pipeline.py` name no PyMuPDF type, method,
option string or exception; `pipeline.BUSINESS_FAILURE` names
`pdf_backend.BrokenPdfError` where it named `pymupdf.FileDataError`. `pipeline.py`'s
copy of reader's PyMuPDF facade was dead in all five of its names and is deleted. **The
licence exposure is unchanged** — PyMuPDF is still pinned and still in use.

**F-018, fixed.** `classification`, `config` and `measurement` have real consumers.
`PipelineSettings.vision_fallback_threshold` was replaced by `confidence_parameters`, so
`ocr_vision_fallback` has one validated representation instead of two.

**semgrep's one ERROR, fixed at the cause.** `_parse_document`'s temporary file flushes
and fsyncs before the path is handed over. No suppression: the count is **124 on the
base commit and 124 here**.

### Files changed

```
src/accountant_dad/confidence.py
src/accountant_dad/artifacts/evidence.py
src/accountant_dad/engines/input_engine/confidence_report.py
src/accountant_dad/engines/input_engine/parser.py
src/accountant_dad/engines/input_engine/assembly.py
tests/unit/test_confidence.py · test_evidence.py · test_input_engine_parser.py
tests/unit/test_input_engine_confidence.py · test_input_engine_confidence_redteam.py
docs/ARCHITECTURE_AMENDMENTS.md (Amendments 7, 8) · CONFIDENCE_SPECIFICATION.md
docs/ADVERSARIAL_TESTING.md · EXECUTION_QUEUE.md · TECHNOLOGY_STACK.md
docs/ACCOUNTING_DEFINITIONS.md · APPLICATION_LAYER.md
KNOWN_FAILURES.md · DECISION_LOG.md (D-020) · ROADMAP.md · TODO.md
```

**Not touched, deliberately:** `pipeline.py`, `reader.py`, `cleaner.py`,
`classification.py`, `config.py`, `conformance*.py`, `tools/ci/*`, `.github/**` — all
owned by other workstreams. `SYSTEM_INVARIANTS.md` INV-11 is **not weakened**: six
provenance attributes, none optional. The `Confidence` type is **unchanged**.

### Measured

```
cells reaching the artifact with a name and a location      before: 0    after: 15
  real Docling, the hand-drawn invoice in test_input_engine_parser.py
  15 cells reported; the one blank grid position is deliberately NOT mapped
```

### Gates — LOCAL ONLY, NOT AUTHORITATIVE (Law 44/56)

```
ruff check --no-fix .    All checks passed
ruff format --check .    126 files already formatted
mypy src tools/ci tests  no issues in 113 source files
full suite               3696 passed · 11 skipped · 1 failed
```

The one failure is **F-018** (`test_module_wiring`), red at the base commit and owned by
another workstream. Baseline at `a467bb2` was 3593 passed, 1 failed — so +103 tests, same
single pre-existing failure.

**Mutation and coverage: UNMEASURED at this HEAD. PENDING GITHUB.** Source changed after
the last run, so every previous number is EXPIRED and none is quoted here.

### Blockers

None introduced. Four open items recorded rather than worked around: **O11/T-052** (the
filter in `pipeline.parsed_fields`), **O12/T-052** (two `isinstance` call sites that should
ask `measurement_state`), **O13/T-053** (NOT_APPLICABLE and FAILED have limited live
producers — stated rather than manufactured), **O14/T-054** (per-cell provenance reaches
the artifact through `detected_fields`, not `DetectedTable`; needs the owner).

### Next work

CI. Every number above is local and therefore not a result.

Still not measured against ground truth. By Law 52 no accuracy claim about this system is
provable, so none is made here.
new     src/accountant_dad/pdf_backend.py
new     tests/unit/test_pdf_backend.py
        src/accountant_dad/engines/input_engine/{cleaner,pipeline,reader}.py
        tests/unit/{test_input_engine_cleaner,test_input_engine_cleaner_redteam}.py
        tests/unit/{test_input_engine_pipeline,test_input_engine_pipeline_redteam}.py
        tests/unit/{test_input_engine_reader,test_input_engine_ablation}.py
        tests/unit/{test_package,test_module_wiring,test_pipeline}.py
        tests/unit/test_conformance_registry.py
        tests/integration/test_engine1_end_to_end.py
```

### Tests

| | base `a467bb2` | here |
|---|---|---|
| passed | 3593 | **3639** |
| failed | 1 (`test_module_wiring`, correctly red) | **0** |
| skipped | 11 | 11 |

`ruff check --no-fix` · `ruff format --check` · `mypy --no-incremental --cache-dir=/dev/null
src tools/ci tests` all clean. Green in randomised order as well as `-p no:randomly`.

`semgrep` at the pinned rule set (`40b8c63`), `--severity ERROR --error` over
`src tools tests`: **exit 0, zero findings**. Proven to discriminate — removing the two
flush lines brings the finding straight back at `pipeline.py:1510`.

### Measurements

```
Suite      : 3639 passed · 0 failed · 11 skipped   Source: LOCAL ONLY - NOT AUTHORITATIVE
semgrep    : 0 ERROR findings                      Source: LOCAL ONLY - NOT AUTHORITATIVE
Suppressions: 124 (base 124, unchanged)            Source: LOCAL ONLY - NOT AUTHORITATIVE
Coverage   : UNMEASURED
Mutation   : UNMEASURED - source changed, every earlier score EXPIRED
```

**Previous mutation and coverage measurements expired because source changed after
`a467bb2`.** ~1400 lines of Engine 1 source moved. No number is quoted (Law 56), and
nothing here is authoritative until GitHub CI produces it (Law 44).

### Blockers

None new. **F-001's licence half is still the owner's** — the abstraction makes the swap
a one-file rewrite, and the swap has not been made.

### Next work

Push, so CI produces a current coverage and mutation number for this tree. Both are
UNMEASURED here and neither may be reported until it does.
