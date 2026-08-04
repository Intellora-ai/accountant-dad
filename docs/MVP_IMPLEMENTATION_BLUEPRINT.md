# MVP — Implementation Blueprint

> **Precedence level 3 — Engine Specifications.** Written under the frozen architecture. **If this and the architecture conflict, the architecture wins** — report it, never resolve silently in code.
>
> **Six questions. Nothing else.**
>
> Definitions → [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) · measurement → [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) · dataset → [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md) · evaluation → [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) · attacks → [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md) · reporting → [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md) · loop → [`MVP_BUILD_VERIFY_FIX.md`](MVP_BUILD_VERIFY_FIX.md)

---

## 1. What are we building?

**One real business document → one correct accounting entry in Tally — and evidence, produced in CI and survived an attack, that it was correct.**

### The finish line — nine conditions, all required

| # | Condition | Threshold |
|---|---|---|
| **1** | **Correctness** — worst of 3, held-out, blind independent production | **≥ 80% of the FROZEN human ceiling** |
| **2** | **Absolute floor** — independent of the ceiling | **≥ the floor agreed at sign-off** |
| **3** | **Safety** — wrong entries, across 10 safety runs | **exactly 0**, reported as a confidence interval |
| **4** | **Margin over the STRONG baseline** | **≥ 0.30 absolute** |
| **5** | **Negative controls refused** | **9 of 9**, including 7 hard negatives |
| **6** | **Poison caught** | **yes** — one miss fails the build |
| **7** | **Understanding** — accountant reaches the same treatment from the story alone | **≥ 80% of the frozen ceiling** |
| **8** | **Risk band agreement** | **≥ 80%**, and **zero** statutory items under-rated as reversible |
| **9** | **Calibration curve** — measured and published, with its sample size | **not flat** |

**Conditions 1 and 2 are dual on purpose.** A relative target alone is gameable: worse labelers lower the ceiling, which lowers the bar. **The frozen ceiling plus an absolute floor closes that.**

**Condition 3 is never stated as "never."** Zero wrong in 160 postings means *"true rate < 1.9% at 95% confidence."* No finite test establishes *never*, and claiming it violates Law 24.

Documents the system cannot answer must produce a **Clarification Request**, not a guess. *Didn't know and said so* = success. **Didn't know and posted = the build failed, regardless of every other number.**

### Everything is verified in GitHub CI

> **A local pass is not a result.** Law 44, enforced structurally. Every number carries its CI run URL.

### Stack

Python 3.12 · immutable JSON artifacts on disk · Pydantic · pytest · GitHub Actions · **test Tally company only** · CLI, no UI.

> ⚠️ **AWAITING SIGN-OFF** — the nine conditions (Law 52) and the six definitions (Law 54).

---

## 2. In what order?

> ## ⛔ BUILD FREEZE — in force, scoped by Amendment 2
>
> **Original rule:** *no engine, no artifact, no schema and no pipeline code is written until the GitHub CI gates exist and are green on an empty repository.*
>
> **That rule was unsatisfiable by its own terms.** Nine gates `exit 1` by design and stay red until the thing they test exists, so *"all gates green on an empty repository"* could never be reached. `CLAUDE.md` §P **Amendment 2** replaced it, and names this section as amended. This is that amendment applied here — the two documents said different things until now, and a half-applied amendment is a defect, not a choice (§G10).
>
> **Permitted now — exhaustive, copied from `CLAUDE.md` §P:**
>
> ```
> artifact schemas · conformance predicates · domain models · Application Layer skeleton
> held-out sealing mechanism · strong baseline · CI gate implementations
> document-ingestion tooling
> ```
>
> **Still frozen:** engine reasoning · accounting logic · tax logic · AI/LLM calls · Tally posting. Each unlocks at its scheduled phase, and is asked for before it is written.
>
> Reason the freeze exists at all, unchanged: a result exists only if CI produced it (Law 44). **Code written before the gates cannot be verified**, so it cannot be called done, so it accumulates as unverified work — the exact debt this whole framework exists to prevent.
>
> **The gates are still a prerequisite, not a phase.** What changed is *which* gates must be green before a given component may be written: the ones that can actually judge it. A gate with nothing to examine gates nothing, and waiting on it was waiting on nothing.

```
P1  Ceiling + Golden Set        no code       the measuring stick AND its ceiling
P2  Artifacts + Conformance     no AI         the enforcement layer
P3  Walking Skeleton            stubs         proves the pipeline
P4  Vertical Slice              real          ONE correct entry, worst of 3
P5  The Full Set                widen         the finish line
P6  Confidence + Hardening      measure       separation, calibration, cost
```

### Which component is built in which phase

> **Gap closed.** `src/brain/` and `src/services/` are specified in the architecture but were scheduled nowhere. **The six phases are unchanged** — no phase renamed, split or added. Components are assigned to existing phases, dependency-driven.

| Component | Phase | Why that phase and no earlier |
|---|---|---|
| **Brain interface contract** | **P2** | *"The Brain never returns a decision"* is a **pure predicate** — no AI, no ground truth, no cost. It belongs exactly where conformance lives. **Cannot be later:** engines call it from P3, and calling an undefined interface is a forward dependency |
| **Application Layer** (`src/services/`) | **P3** | P3 proves the pipeline. A pipeline **is** orchestration — nothing can be sequenced before the sequencer exists. It contains **no AI**, so it is fully buildable here. **Cannot be later:** P3 is defined as proving the pipeline |
| **Brain stub** (`src/brain/`) | **P3** | Proves the seam without knowledge. Engines call it and it answers structurally; nothing is faked as accounting truth |
| **Brain — real knowledge, 1 document** | **P4** | P4 is ONE correct entry. The Brain needs only what that one document requires. **Built before Engine 3 within P4** |
| **Brain — widened** | **P5** | P5 widens to the full golden set; the Brain widens with it |

### Dependency table

| Component | Phase | Depends On | Required By |
|---|---|---|---|
| Six artifact schemas | P2 | — | everything downstream |
| Transaction ID format | P2 | artifact schemas | Application Layer |
| Conformance predicates | P2 | artifact schemas | every later phase |
| **Brain interface contract** | **P2** | — | Brain stub · Engines 2–6 |
| **Application Layer** | **P3** | Transaction ID format · artifact schemas (both P2) | every engine · every workflow · P4–P6 |
| **Brain stub** | **P3** | Brain interface contract (P2) | Engine stubs 2–6 |
| Engine stubs 1–6 | P3 | Application Layer · artifact schemas | walking skeleton |
| **Brain real (1 doc)** | **P4** | Brain stub (P3) · golden set (P1) | Engine 3 |
| Engines 1–6 real | P4 | Application Layer (P3) · **Brain (P4, built first within the phase)** | vertical slice |
| **Brain widened** | **P5** | Brain P4 · full golden set | Engines at P5 |

**Forward-dependency proof.** Every `Depends On` resolves to the **same phase or an earlier one**. The single same-phase case — Brain before Engine 3 inside P4 — is stated explicitly rather than left implied. No component is required by anything built before it. **Zero forward dependencies.**

Full specification: [`APPLICATION_LAYER.md`](APPLICATION_LAYER.md) · [`APPLICATION_LAYER_INVARIANTS.md`](APPLICATION_LAYER_INVARIANTS.md) · [`APPLICATION_LAYER_API.md`](APPLICATION_LAYER_API.md) · [`APPLICATION_LAYER_CONTRACTS.md`](APPLICATION_LAYER_CONTRACTS.md)

---

### Why this order

> **The hard problem is "build an AI accountant." The equivalent easier problem is "make one specific invoice post correctly, then widen."** (Law 53.)

Building six engines to completion and testing at the end means discovering at P6 that Engine 2 was wrong all along.

| Phase | Why it must precede the next |
|---|---|
| **P1** | Without ground truth **and its frozen ceiling**, nothing is measurable and Law 52 forbids building it. A system beating a ceiling never measured is a claim about nothing. |
| **P2** | Needs no ground truth and no AI — free, runs on every commit, and surfaces contradictions between locked documents |
| **P3** | Proves the pipeline separately from the reasoning. When P4 is wrong you already know the plumbing is not the cause. |
| **P4** | Law 5 — prove one case before scaling |
| **P5** | Widening before one case works is wasted work |
| **P6** | Confidence separation needs volume that only exists after P5 |

---

## 3. What is finished?

Per phase. Not *"it works"* — the number, from CI.

| Phase | Done when |
|---|---|
| **P1** | 25 documents collected and frozen · **2 qualified labelers** · 4 stages each · **ceiling frozen and hashed** · intra-rater measured · held-out sealed by construction · protocol written · 6 definitions + 6 conditions signed off |
| **P2** | Every `MUST NEVER` is a predicate or on the review-only list with an expiry · **ID ablation test passes** · malformed artifact rejected **by the correct predicate** · **Brain interface contract defined, and "the Brain never returns a decision" enforced as a predicate** · CI green |
| **P3** | End to end on 1 hardcoded document in CI · all artifacts valid · conformance green · Transaction ID intact · audit complete · **Application Layer creates the Transaction ID, runs the state machine and routes every artifact — no engine calls another** · **Brain stub answers structurally without faking knowledge** · **no accuracy claim permitted at this phase** |
| **P4** | **1 correct entry, worst of 3**, blind-verified, in test Tally · posted exactly once on 3 submissions · **9/9 negatives** · both baselines recorded · pre-registered · **CI run URL recorded** |
| **P5** | **≥ 80% of frozen ceiling AND ≥ absolute floor, worst of 3, held-out** · **0 wrong in 10 safety runs** · **margin ≥ 0.30 over strong baseline** · **spread ≤ 2** · isolated + contributed per engine · 19/19 attacks · poison caught |
| **P6** | Confidence **separation ≥ 0.30** or confidence formally rejected and every document corrected · **calibration curve published and not flat** · **understanding ≥ 80% of ceiling** · **risk band agreement ≥ 80% with zero statutory under-ratings** · cost bounds met (60s, ₹5) · drift canary clean |

**The build is finished when all nine conditions in §1 hold simultaneously, on a pre-registered, non-void, CI-produced run.**

---

## 4. What blocks progress?

| Blocker | State | Consequence |
|---|---|---|
| **Two qualified accountants' time** | ⬜ Not secured | **Hardest dependency in the project — and it is people, not technology.** Without both there is no ceiling, and without a frozen ceiling no number means anything. |
| 25 documents | ⬜ Not collected | Blocks P1 |
| **The 6 definitions** | ⬜ **Awaiting sign-off** | **Law 54 — blocks everything** |
| **The 9 finish conditions + absolute floor** | ⬜ **Awaiting sign-off** | **Law 52 — blocks everything** |
| **GitHub Actions workflow** | ✅ **Built** | Six workflows, 23 Check Runs, merge gate proven against 11 attacks (`CI_S2_EVIDENCE.md`). Build freeze narrowly amended for CI scaffolding only — see `CLAUDE.md` §P Amendment 1. |
| Held-out sealing mechanism | ⬜ Not built | Blocks P1 — must be structural, not disciplinary |
| Strong baseline implementation | ⬜ Not built | Blocks P4 — the AI gets no credit until it beats this |
| Test Tally company | ⬜ Not created | Blocks P4 |
| Tally XML/HTTP access | ⬜ Unverified | Blocks P4 |
| LLM endpoint | ⬜ Not chosen | Blocks P4 |
| Architecture | ✅ Locked `a47271d` | — |
| Python 3.12 | ✅ Chosen | — |

### Stop points

| # | Halt | Why |
|---|---|---|
| **S1** | Before P1 — definitions, conditions, absolute floor | Everything downstream is built on them |
| **S2** | **After the ceiling is computed** | **If inter-rater agreement is below 70%, STOP.** The task is underspecified and no amount of engineering fixes an undefined target. This is a finding, not a setback. |
| **S3** | After P1 — golden set frozen | If the labels reveal the architecture assumed something false, better now than after six phases |
| **S4** | After P2 — conformance green in CI | Contradictions between locked documents surface here; the fix is an amendment, not code |
| **S5** | **After P4 — one correct entry, worst of 3** | **The real gate.** If one document cannot post correctly three times running, widening is wasted. |
| **S6** | Before any real ledger | Not in this build at all — the stop point exists to make that explicit |

---

## 5. What happens if something fails?

| Failure | Detected by | Response |
|---|---|---|
| **Only one accountant available** | P1 | **No ceiling can be computed.** Secure a second, or every subsequent number is reported **without a ceiling and explicitly weaker.** Never fabricate one. |
| **Inter-rater agreement below 70%** | P1 | **Stop.** The task is underspecified — fix the definitions before building. |
| **Intra-rater agreement poor** | P1 | Inter-rater was measuring human variance, not task difficulty. **The noise floor is higher than assumed** — every threshold is revisited. |
| A negative control produces an entry | Any run | **Run void.** No accuracy number. Fix, re-run. |
| Extraction accuracy very low | P4 | **Stop and rethink Engine 1 before widening.** Catching this at P4 rather than P6 is the entire reason for the ordering. |
| **High spread across repeats** | P4/P5 | The system is unpredictable. **Unpredictable disqualifies it regardless of average.** Pin, reduce temperature, re-measure. |
| A locked document is wrong | Conformance can't express a rule, or two contradict | **Amendment (§M), never a code workaround. The doc wins.** |
| **System ≈ strong baseline** | P5 | **The AI is doing nothing a lookup table doesn't.** Stop and rethink the approach — do not tune. |
| Confidence separation < 0.30 | P6 | **Confidence rejected. It gates nothing. Every document implying otherwise is corrected.** |
| **Calibration curve flat** | P4 onward | **Confidence is noise.** Say so publicly, correct every document, decide whether to keep it at all. |
| **Understanding below 80% of ceiling** | P4 onward | The story does not carry the decision. **If it is *incomplete* rather than *wrong*, Engine 2's output contract is too narrow — that is an amendment, not a tuning problem.** |
| **A statutory item rated reversible** | Any | **Fails condition 8 regardless of the agreement rate.** One occurrence. Root-cause to the class. |
| Provider drift detected | Any run | Comparisons across the boundary marked **incomparable**. Re-baseline. |
| **A wrong entry posts** | Any | **Build fails.** Root-cause to the class. Permanent trap test in CI. Re-run from P4. |
| **Poison posts** | Any | **Build fails**, regardless of every other number |
| Held-out peeked at | Any | **Set burned. Six new documents.** No exception. |
| Ceiling re-measured without amendment | Audit | **The bar was moved.** All numbers since are void. |
| Result claimed from a local run | Report review | **Not a result.** Re-run in CI. |
| Scope creep | Anything not in §1 | Revert. `Found: … · Not changed: out of current scope`. |

**Every phase tagged on completion. Rollback is `git revert` to the previous phase tag.** No phase depends on another's uncommitted work.

---

## 6. What is the next phase?

> **Phase 1 — Human Ceiling and Golden Set.**

**Blocked on:** sign-off of the 6 definitions, the 9 conditions and the absolute floor — and **two** accountants' time. Also blocked by the build freeze above: **the GitHub CI gates must exist first.**

**No code is written in Phase 1.**

The first real output of this project is not software. It is **a number describing how often two qualified humans agree** — and if that number is low, it is the most important thing anyone will learn this year.

The first real output of this project is not software. It is **a number describing how often two qualified humans agree** — and if that number is low, it is the most important thing anyone will learn this year.
