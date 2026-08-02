# Measurement Framework

> **Precedence level 2 — Locked Architecture Decisions.** Required by `CLAUDE.md` **Law 52**: *nothing is built until it can be measured.*
>
> How a number is obtained and **what it is allowed to claim.**
>
> **This framework assumes you are trying to fool yourself.** Not from dishonesty — from the ordinary human tendency to stop looking once the answer is good. Every rule below closes a specific, common, well-documented way of accidentally lying.

---

## 0. Pre-registration — outranks everything below

> **Before any run: write the number, the scoring rule and the analysis. Commit it. Hash it.**

```
runs/<timestamp>/pre-registration.md      committed BEFORE the run

  what is being measured
  the exact scoring rule, field by field
  the pass threshold
  which set — development or held-out
  what counts as FAILURE
  what makes this run VOID
  time and cost bounds
```

**Any change to scoring after seeing results invalidates the run.** Not *discouraged* — **invalidates**.

Costs nothing. Closes the largest hole there is: deciding what counts as success after seeing the output is how honest people fool themselves, every time, without noticing.

---

## 0a. A result exists only if GitHub CI produced it

> **Local runs do not count. Not as evidence, not as a number, not as "tested."**

This is the concrete enforcement of **Law 44** — *never accept "works on my machine" as verification.*

| Where it ran | Status |
|---|---|
| Your machine | **Not a result.** Exploration only. |
| **GitHub Actions, green** | **The only thing that counts** |
| GitHub Actions, red | A result — a failing one |

**Every number in every report carries its CI run URL and workflow run ID.** A figure without one is unverified and is rejected, however carefully it was obtained locally.

**Why this is absolute.** A local environment has your cached models, your uncommitted files, your shell variables and your patience. It is not reproducible by anyone including you next week. **A measurement nobody else can regenerate is an anecdote** (§8), and CI is the cheapest way to make regeneration automatic rather than aspirational.

**Consequence for the harness:** the golden set, the labels, the sealed held-out file and the evaluation runner must all be executable inside CI. Anything that only runs locally cannot produce a result, so it must not be the only path.

---

## 1. The human ceiling — measured once, then FROZEN

**Two independent qualified accountants** (defined in [`ACCOUNTING_DEFINITIONS.md` §0](ACCOUNTING_DEFINITIONS.md)) label the same documents, blind to each other and blind to the system.

```
inter-rater agreement = documents where both produced an identical entry
```

| Agreement | Meaning | What follows |
|---|---|---|
| High (≥ 90%) | Task well-defined | The machine is held near the ceiling |
| **~70–90%** | Real ambiguity exists | Target = fraction of ceiling **+ absolute floor** |
| **< 70%** | **The task is underspecified** | **STOP. Fix the definitions before building anything.** |

### The anti-gaming rules — the ceiling is a hard gate

1. **The ceiling is measured once and FROZEN** in `ceiling.json`, hashed. **Re-measuring with different labelers to move it is an amendment** (`CLAUDE.md` §M) — never a quiet re-run.
2. **The target is dual.** Both must hold:
   ```
   system ≥ 80% of frozen ceiling      (relative)
   system ≥ absolute floor             (absolute — set at sign-off)
   ```
   Without the floor, worse labelers make the target easier — a lower ceiling would *reduce* what the system must achieve. The floor makes that impossible.
3. **Labeler credentials are published with the ceiling.** A ceiling is a statement about who was asked.
4. **Intra-rater agreement is also measured**: 2 documents re-labeled by the **same** person ≥ 2 weeks later. **A person disagreeing with themselves is the true noise floor**, and system errors below it are unattributable.

Documents where the two labelers disagree have **no ground truth** — they leave the correctness denominator and become the *ask-or-not* set.

**This runs before Phase 1 completes.** A system beating a ceiling that was never measured is a claim about nothing.

---

## 2. Repeats — worst of N, and N depends on the claim

**Never the average. In production the user gets one run, not the mean of three.**

| Claim being established | Repeats | Score |
|---|---|---|
| **Correctness** | ×3 identical input | **The worst run** |
| **SAFETY — the zero** | **×10** identical input | **Any wrong entry in any run fails** |

Safety gets more runs because a 1-in-10 catastrophic output has only a **27% chance of appearing in 3 runs**. Three repeats establish an average-ish property; **they cannot establish a zero.** The zero is the entire point.

### Variance is itself a metric

```
spread = best − worst    (over the correctness repeats)
```

**Spread > 2 documents is a failure regardless of the score.** A system producing 6-to-9 on identical input is not an 8-system — it is an unpredictable one, and unpredictable disqualifies it for accounting.

### Cache honesty

Before repeats: **assert caching is disabled**, or vary a semantically-inert nonce per run. Identical outputs from a cache read as determinism when they are memoization. The run harness checks this — not the operator.

---

## 3. Negative controls — HARD negatives

Feed it things that **must not** produce an entry. The controls are the **real-world false positives**, not toys:

| # | Input | Why it is hard |
|---|---|---|
| N1 | **Proforma invoice** | Looks identical to a tax invoice. **Must not post.** The classic real bookkeeping error. |
| N2 | **Purchase order** | Invoice-shaped; no liability exists |
| N3 | **Quotation** | Invoice-shaped; no transaction occurred |
| N4 | **Delivery challan** | Real goods movement; not an invoice |
| N5 | Invoice copy stamped **DUPLICATE** | Genuine document, already posted |
| N6 | Genuine invoice addressed to a **different company** | Right document, wrong books |
| N7 | Invoice with **all amounts blanked** | Clarification, never a guess |
| N8 | Blank page | Floor check |
| N9 | Photograph of unrelated content | Floor check |

> **If any control produces an accounting entry, the run is VOID and no accuracy number is computed.**

A suite of easy negatives (cats, menus) proves almost nothing while feeling like a strong gate — the gate that voids a whole run must be the hardest test in the suite, not the softest. N8–N9 stay only as a floor.

**A system that posts a proforma invoice has failed in exactly the way real bookkeepers fail.** That is the test worth running.

---

## 4. Baselines — two, and the strong one is the bar

| Baseline | What it is | Purpose |
|---|---|---|
| **Dumb** | Total → Purchases, ignore tax, today's date | Sanity floor. Below this = actively harmful. |
| **STRONG** | Regex field extraction + vendor→ledger lookup table + GST rate table | **The real bar.** What two weeks of ordinary scripting achieves without any AI. |

```
required margin:  system ≥ strong baseline + 0.30 absolute
```

| Result | Verdict |
|---|---|
| ≫ strong baseline | The reasoning is doing work |
| **≈ strong baseline** | **The AI is doing nothing a lookup table doesn't.** Stop and rethink — do not tune. |
| < dumb baseline | Actively harmful |

Beating only the dumb baseline is a strawman victory. **Every accuracy claim is stated against the strong baseline, never in isolation.**

---

## 5. Held-out set — sealed by construction, opened once

```
DEVELOPMENT   10 documents    tune freely, look as often as you like
HELD-OUT       6 documents    SEALED — ≥ 30% of the set, always
```

**Opened exactly once per phase, at the end**, by a recorded, timestamped action.

| Event | Consequence |
|---|---|
| Peeking early | **The set is burned. Permanently.** Six new documents required. |
| Tuning after seeing held-out results | **Run void.** Fresh set required. |
| Running held-out twice in a phase | The second run does not count |

**Sealing is structural, not disciplinary**: labels live in a separately-committed encrypted file; the harness records every open with a timestamp. Guarded by construction, not by care (`CLAUDE.md` §J.6).

**Growth rule:** new documents join the **held-out** side until it holds ≥ 30% — a development set that grows faster than held-out is a set you are increasingly tuned to.

Six documents, not three: a 3-document gate moves 33% on a single failure. **The final gate cannot be the noisiest number in the system.**

---

## 6. Isolated vs contributed

**Every engine gets two numbers, every run.**

```
✗   Engine 3 score = f(real BUO)     ← contaminated by Engine 2's errors
✓   Engine 3 score = f(golden BUO)   ← measures Engine 3 alone

inherited damage = isolated − contributed
```

| Number | Input fed | Answers |
|---|---|---|
| **Isolated** | The **golden** upstream artifact | Is *this engine* right? |
| **Contributed** | The **real** upstream artifact | Is it right in situ? |

```
Engine 3 isolated:     0.90
Engine 3 contributed:  0.50
                       ────
inherited damage:      0.40   ← Engine 2 is the problem, not Engine 3
```

**Without the split you spend a month rewriting Engine 3 and the number does not move.** A run reporting only end-to-end accuracy is **incomplete and rejected** — the largest gap names the engine to fix, and it is usually not the engine with the worst contributed score.

---

## 7. Blinded scoring, and the builder never scores

1. **The person who built an engine does not score it.**
2. **The scorer does not know which output is the system's.** Golden and system entries shuffled, diffed by identity.
3. Where blinding is genuinely impossible (solo project): score in a separate sitting, from a shuffled file, code closed — and **the report records this as a limitation.** Never waved away.

---

## 8. Every run is recorded, including the bad ones

> **You may not run 5 times and report the best.**

```
runs/
  2026-08-02-1430-abc123/
    pre-registration.md
    result.json              all repeats
    discarded: false
  2026-08-02-1615-abc123/
    discarded: true
    reason: "wrong model pinned"
```

**A discarded run is recorded with its reason.** An unrecorded run is data destruction — under **Law 24**, fabrication.

---

## 9. Regression floor and drift detection

**Once a number is achieved, it becomes a floor.**

```
best_ever[metric]   recorded permanently
run below floor     = REGRESSION = BLOCKS MERGE
```

Not a warning. A block. A change improving one number while dropping another has improved nothing until both are stated.

### Provider-drift canary

**Model providers change models under fixed names.** Three fixed canary documents are re-run at the start of every evaluation:

```
canary output changed + no code change  →  PROVIDER DRIFT
→ flagged, all cross-run comparisons before/after marked incomparable
```

Without this, numbers silently stop being comparable and nobody knows when it happened.

---

## 10. Confidence — must SEPARATE before it may do anything

> **Until it passes this test, confidence is an ordinal ranking, not a probability, and it may gate NOTHING.**

```
accuracy(top confidence tercile) − accuracy(bottom tercile)  ≥  0.30
```

| Result | Verdict |
|---|---|
| Separation ≥ 0.30 | Confidence carries information — may be used for ordering |
| **Separation < 0.30** | **Confidence is REJECTED.** It gates nothing. Every document implying it can is corrected. |

**No document, message, log line or interface may present confidence as a probability until separation passes and calibration is measured at N ≥ 100.** Doing so is a false statement under Law 54.

A confidence value that does not separate right from wrong is decoration — and decoration shaped like a measurement is **worse than nothing, because it manufactures trust.**

**Calibration curves are deferred until N ≥ 100.** Below that they cannot be computed honestly, and the separation test carries all the weight. *(Deliberate simplification — one strong test instead of two weak ones.)*

### The six layers

| Layer | Owner | Asks |
|---|---|---|
| Evidence | E1 | Was this read correctly? |
| Understanding | E2 | Does the evidence support this interpretation? |
| Decision | E3 | Is the treatment likely correct? |
| Clarification | E4 | Has every blocking uncertainty been found? |
| Validation | E5 | Is execution safe and permitted? |
| Execution | E6 | Did execution succeed? **Transport only.** |

Recalculated only when **evidence** changes — never because an engine reasoned harder.

---

## 11. The review-only list has shrink pressure

Rules that cannot be executable predicates are published as review-only — **but the list is not a dumping ground:**

1. Every entry carries **the reason it cannot be a predicate** and **a re-examination date**.
2. **IDENTITY ≠ INTELLIGENCE is NOT on the list — it is executable**: change the Document ID, re-run, **assert byte-identical output.** An ablation test. Any rule of the form *"X must not influence Y"* converts the same way.

A review-only list that only grows is silently declining coverage.

---

## 12. Time and cost bounds — with defaults, now

| Bound | Default | Changed by |
|---|---|---|
| Wall clock, end to end | **≤ 60 seconds / document** | Amendment only |
| Token cost | **≤ ₹5 / document** | Amendment only |
| Human intervention | Recorded per document | — |

Defaults exist **now** because "to be pre-registered later" was the one place in this framework where a number could be set after seeing results. **A correct entry taking 30 minutes and ₹200 fails the product at any accuracy.**

---

## 13. What may be claimed — and the safety claim's honest form

| Evidence held | May claim |
|---|---|
| Conformance green | *"Obeys its own rules."* **Nothing about correctness.** |
| Not pre-registered · negatives failed · held-out peeked · < required repeats | **Nothing. Void.** |
| 1 document, worst-of-3 | *"One case verified."* Nothing general. |
| Full set, worst-of-N, vs strong baseline, negatives passed, pre-registered | *"N of M, baseline B, ceiling C."* **All four numbers or none.** |
| ~100 labeled + separation ≥ 0.30 | Statements about confidence |

### The zero is never "never"

**Zero wrong entries at MVP scale does not prove the system never posts wrong entries.** By the rule of three:

```
0 wrong in 160 postings (16 docs × 10 safety runs)
→ true wrong-entry rate < 1.9% at 95% confidence
```

**Every safety claim is stated in that form.** *"Never posts a wrong entry"* is a claim no finite test can establish, and making it would violate Law 24. What the MVP can do is **fail** the safety condition — one wrong entry disproves it forever — and survive it at a stated confidence.

**A number without its sample size, its baseline and its ceiling is not a measurement.**

---

## What this costs

| Hardening | Cost |
|---|---|
| Two labelers + intra-rater | **More than double the accountant time** — the scarcest resource |
| Worst-of-3 + safety ×10 | ~13 runs per evaluation |
| Held-out at 6, sealed | Only 10 documents to develop against |
| 9 hard negatives | 9 more documents to prepare |
| Strong baseline | Two weeks of scripting before the AI gets credit for anything |
| Pre-registration | You cannot change your mind after seeing results |

**And the numbers will drop.** A system scoring "8 of 10" under a soft framework may score **5 of 10 worst-of-3 against a strong baseline of 4** under this one.

That is not the framework being unfair.

> **That is the first honest number the project has ever produced — and the only kind you can build on.**
