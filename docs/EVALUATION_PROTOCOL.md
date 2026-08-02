# Evaluation Protocol

> **Precedence level 2 — Locked Architecture Decisions.** How an evaluation is run, start to finish.
>
> What the numbers mean → [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) · what is measured against → [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)

---

## 0. Where it runs

> **GitHub Actions. Nowhere else counts.**

A local run is exploration. **It produces no number, no claim and no "tested."** Law 44, enforced structurally.

Every result carries its **CI run URL and workflow run ID**. A figure without one is rejected regardless of how carefully it was obtained.

---

## When it runs

| Trigger | Scope |
|---|---|
| End of every phase | Full — required before the phase may be called done |
| Any change to an engine | That engine, isolated |
| **Any change to model, prompt or temperature** | **Full. A model change invalidates every previous number.** |
| Before any accuracy claim | Full. **No claim without a fresh CI run.** |

---

## 0a. Executable preconditions — the harness REFUSES to run

**Void conditions are not a checklist.** A checklist is checked by the person incentivized not to notice.

The runner asserts these **before doing anything**, and exits non-zero if any fails:

| Precondition | Executable check |
|---|---|
| Pre-registration exists | File present · hash matches · **git commit timestamp precedes run start** |
| Held-out sealed | `heldout.sealed` has no recorded open in this phase |
| Repeat count | Correctness ≥ 3 · **safety ≥ 10** |
| Model pinned | Config hash matches the frozen block |
| Golden labels unmodified | Label file hashes match `ceiling.json` |
| Ceiling frozen | `ceiling.json` hash matches its committed value |
| Cache disabled | Cache flag asserted off, or nonce varies per run |
| Running in CI | `GITHUB_ACTIONS=true` — **local invocation refuses** |

**Not a gate you pass. A gate that will not start.**

---

## The run — eleven steps, in order

### Step 0 — Pre-register

```
runs/<timestamp>/pre-registration.md      COMMITTED BEFORE ANYTHING RUNS

  what is measured · exact scoring rule · pass threshold
  which set · what counts as failure · what makes this void
  time and cost bounds
```

**A run without a committed pre-registration produces no valid number.**

### Step 1 — Freeze and record

```
commit SHA · model + version · temperature · prompt hash
golden set version · ceiling.json hash · CI run URL · workflow run ID
date · run by · scored by
```

**A result without this block is not reproducible and does not count.**

### Step 2 — Drift canary

Three fixed canary documents. **Output changed with no code change → provider drift.** Flagged; all comparisons across that boundary marked incomparable.

### Step 3 — Negative controls FIRST

All 9. **If any produces an accounting entry, the run STOPS and no accuracy number is computed.**

Running accuracy on a system that will invoice a proforma produces a number describing nothing.

### Step 4 — Conformance

Full predicate suite, including the **ID ablation test** (change the Document ID, assert byte-identical output).

**If conformance fails, stop.** You cannot attribute a wrong entry to reasoning when the pipeline is violating its own rules.

### Step 5 — Baselines

Score **dumb** and **strong** baselines against the same labels. **Recorded before the system's own score is computed**, so the comparison cannot be framed after the fact.

### Step 6 — Isolated pass, ×3

Each engine fed the **golden** upstream artifact. **Record the worst.**

Runs before contributed because it is the diagnostic — if Engine 3 is broken alone, the end-to-end number is bad for a reason you already know.

### Step 7 — Contributed pass, ×3

Full pipeline, end to end. **Record the worst.** Record the spread.

### Step 8 — Safety pass, ×10

**Ten repeats, counting wrong entries only.** Three repeats cannot establish a zero — a 1-in-10 catastrophic output appears in 3 runs only 27% of the time.

### Step 9 — Compute

```
inherited damage[e] = isolated[e] − contributed[e]
spread              = best − worst
margin              = system − STRONG baseline          must be ≥ 0.30
ceiling fraction    = system ÷ frozen ceiling            must be ≥ 0.80
absolute floor      = system ≥ floor                     must hold
safety CI           = rule of three on wrong entries
```

**The largest inherited damage names the engine to fix** — usually not the one with the worst contributed score.

### Step 10 — Headline numbers, separately

```
correct         all four fields exact, worst run
WRONG ENTRIES   posted and not matching, across 10 safety runs   ← must be 0
clarified       produced a Clarification Request
over-asked      asked where the accountant would not have
SILENT-WRONG    did not ask where the accountant would have
false doubts    doubts that, when supplied, changed nothing
```

**`correct + clarified` is not a score.** Different outcomes, different values. Reported apart, always.

### Step 11 — Adversarial, then report

Per [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md), then [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md), written **before** the commit as part of the DONE GATE.

---

## Scoring rules

### An entry is correct or it is wrong

All four fields — exact, to the paisa. **No partial credit, no tolerance.** Three of four is a wrong entry.

### Correctness is blind independent production, never acceptance

The accountant produced their entry from the original document without seeing the system's. **"Accepts unchanged" is not the test and is never used** — approving a plausible entry is far easier than generating the right one.

### Clarification is scored against the accountant's question

| System | Accountant | Score |
|---|---|---|
| Asked | Asked | ✅ **Correct** — the ideal outcome for an ambiguous document |
| Asked | Didn't | ⚠️ **Over-asking.** Costs user time. Tolerable. |
| **Didn't** | **Asked** | ❌ **SILENT-WRONG.** The dangerous failure. |
| Didn't | Didn't | ✅ Correct |

**Never netted against each other.** Over-asking is annoying; silent-wrong is a wrong entry nobody knows about.

### A wrong entry fails the run

Regardless of every other number. **Non-goal B.8 has no threshold.**

---

## Void conditions — discarded, never adjusted

Most are now executable (§0a). The remainder:

| Condition | Why |
|---|---|
| **Ran locally, not in CI** | Not a result. Law 44. |
| Scoring rule changed after seeing output | Scoring could have moved to fit |
| **Any negative control produced an entry** | The system does not distinguish invoices from non-invoices |
| Golden label edited after seeing output | Now measures agreement, not correctness |
| Accountant saw output before labeling | Anchoring |
| Held-out previously opened | It is a development set |
| Tuned on the set being evaluated | Measures memorization |
| Ceiling re-measured without amendment | The bar was moved |

**Any of these: discarded, recorded as discarded with the reason, re-run.** Never adjusted.

---

## Honest reporting

- **Always the sample size.** *"90%"* on 16 documents is **"14 of 16."**
- **Always the strong baseline and the frozen ceiling.** *"14 of 16"* alone is not a claim.
- **The zero is never "never."** State it as a confidence interval — *"0 wrong in 160 postings → < 1.9% at 95% confidence."*
- **Never average across engines.** Six numbers stay six.
- **Report failures individually** — which document, which field, which engine.
- **A number that moved without an explanation is noise until explained**, not an improvement.
