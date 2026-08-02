# Phase Report Template

> **Precedence level 2 — Locked Architecture Decisions.** Every phase ends with this, written **before** the commit as part of the DONE GATE.
>
> **A phase without a report is not finished. A report without a CI run URL is not a report.**

---

```
PHASE REPORT — Phase N: <name>

CI                                    ← without this, nothing below counts
  run URL              <github.com/.../actions/runs/...>
  workflow run ID      <id>
  conclusion           success / failure
  ran locally?         if yes → THIS IS NOT A RESULT

PRE-REGISTRATION
  committed at         <sha, timestamp — BEFORE the run started>
  hash                 <hash of pre-registration.md>
  scoring changed?     no / YES → RUN IS VOID

FROZEN
  commit · model + version · temperature · prompt hash
  golden set version · ceiling.json hash
  run date · run by · scored by      ← if same person, state it as a limitation

VALIDITY GATES                        all must pass or no number below is valid
  ran in CI               yes / NO → VOID
  preconditions asserted  N of 8 passed
  negative controls       9 of 9 refused / FAILED → VOID
  conformance ran first   yes / no
  held-out sealed         yes / PREVIOUSLY OPENED → VOID
  correctness repeats     3 / fewer → VOID
  safety repeats          10 / fewer → VOID
  cache disabled          yes / no
  drift canary            unchanged / DRIFT DETECTED

HUMAN CEILING                         frozen — re-measuring requires an amendment
  labeler A               <credential>
  labeler B               <credential>
  inter-rater agreement   N of 16
  intra-rater agreement   N of 2 re-labeled
  disputed documents      N — excluded from correctness denominator
  ceiling.json hash       <hash> — matches committed? yes/no

BASELINES
  dumb baseline           N of 16
  STRONG baseline         N of 16          ← the real bar
  system                  N of 16
  margin over strong      +0.NN            ← must be ≥ 0.30

MEASURED — worst of N, never the average
  correct                 N of 16
  ceiling fraction        NN%              ← must be ≥ 80%
  absolute floor met      yes / no         ← must be yes
  WRONG ENTRIES           N of 160 postings    ← must be 0
  safety confidence       "< N.N% at 95% confidence"   ← never "never"
  clarified               N
  over-asked              N
  SILENT-WRONG            N                ← the dangerous one
  false doubts            N
  spread (best−worst)     N                ← above 2 = failure regardless of score

  All numbers measured, not estimated (Law 52).

CONFORMANCE
  predicates              N total, N passed, N failed
  failures                <which predicate, which artifact>
  ID ablation test        passed / FAILED
  review-only rules       N — NOT covered
  review-only expiries    <any past their re-examination date>

PER-ENGINE                            Phase 5 onward
  engine   isolated   contributed   inherited damage
  E1       0.00       0.00          0.00
  ...
  largest gap → <engine>              ← the one to fix

CONFIDENCE                            Phase 6 onward
  tercile separation      0.NN         ← must be ≥ 0.30 or confidence is REJECTED
  verdict                 usable for ordering / REJECTED
  if rejected             which documents were corrected

ADVERSARIAL
  attacks run             N of 19
  attacks failed          <which, what happened>
  POISON                  caught / POSTED → BUILD FAILED
  poison used             <what it was>

COST
  wall clock / document   N sec        bound: 60s — pass/fail
  token cost / document   ₹N           bound: ₹5 — pass/fail
  human seconds / document  N

REGRESSION
  previous floor          <metric: value>
  this run                <metric: value>
  regression?             no / YES → BLOCKS MERGE

LAWS VERIFIED
  <the specific list from the DONE GATE — not "all of them">

FAILURES — individually
  <document, field, engine, produced vs expected>

RUNS DISCARDED THIS PHASE
  <every one, with the reason>

NEXT PHASE
  <name, and what must be true before it starts>
```

---

## Rules

### No CI run URL, no report

**A local pass is not a result** (`MEASUREMENT_FRAMEWORK.md` §0a, Law 44). Every number carries the run that produced it.

### Correctness and safety are reported separately, always

A report giving a correctness number without a wrong-entry count is incomplete and is **rejected**. Different claims, different thresholds — one has a floor of 80% of ceiling, the other has a floor of **zero**.

### The zero is stated as a confidence interval, never as "never"

```
✗  "never posts a wrong entry"
✓  "0 wrong in 160 postings → true rate < 1.9% at 95% confidence"
```

*"Never"* is a claim no finite test can establish. Making it violates Law 24.

### Sample size, baseline and ceiling, always

*"90% accurate"* is not a result. **"14 of 16, strong baseline 9 of 16, ceiling 15 of 16"** is.

### Failures individually

Not *"two failures"* — which document, which field, which engine, produced vs expected. **An aggregate hides the pattern, and the pattern is the fix.**

### Never average across engines

Six numbers stay six. An average hides which one is broken — the only thing the numbers are for.

### Estimated numbers are not numbers

Every figure is measured or the line reads `not measured`. **"Roughly," "about," "should be around" are forbidden** (Law 52).

### Discarded runs are listed

Omitting one is fabrication under Law 24.
