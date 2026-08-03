# MVP — Build → Verify → Fix

> **Precedence level 3 — Engine Specifications.** One loop, per phase, until green.
>
> Template: `CLAUDE.md` §I and §J. Attacks → [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md) · evaluation → [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) · reporting → [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md)

---

## 1. The loop

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
     BUILD  →  PUSH  →  CI VERIFY  →  green? ──no──→ FIX
                             │                         │
                            yes                        │
                             ▼                         │
                        DONE GATE          ← stated ───┘
                             ▼
                          COMMIT           ← never before the gate
                             ▼
                            TAG
                             ▼
                        next phase
```

**Law 51.** The gate precedes the commit. **The commit is the declaration of done.**

**Law 44.** Verification happens in **GitHub CI**. A local pass is not verification — it is exploration.

> **⛔ BUILD FREEZE — in force, scoped by Amendment 2.**
> An unverifiable commit cannot be called done, so it accumulates as unverified work.
>
> The blanket form of this rule — *no product code until the gates are green* — was
> unsatisfiable: nine gates `exit 1` by design until the thing they test exists.
> `CLAUDE.md` §P **Amendment 2** replaced it. **`CLAUDE.md` §P is the single authority
> on what is permitted; this line is a pointer, never a second copy.**

---

## 2. What "green" means — seven conditions

**All seven. Any six is red.**

| # | Condition | Where |
|---|---|---|
| 1 | **It ran in GitHub Actions** | — **a local pass is not a result** |
| 2 | Typecheck · lint · tests · build pass | ✅ CI |
| 3 | **Conformance suite passes** — every predicate, including the ID ablation test | ✅ CI |
| 4 | **Negative controls 9 of 9** | ✅ CI |
| 5 | **The phase's number met** — worst of N, pre-registered | ❌ DONE GATE |
| 6 | **Margin ≥ 0.30 over the STRONG baseline** | ❌ DONE GATE |
| 7 | **Attack list survived, poison caught** | ❌ DONE GATE |

**A test runner saying "green" satisfies condition 2 only.**

In this build that gap is wider than usual: **a passing unit suite tells you nothing about whether an entry was accounting-correct, because unit tests do not know accounting.** Only condition 5 does.

---

## 3. BUILD

1. **One phase at a time.** Finish, tag, commit.
2. **Reuse before building.** The 23 locked documents specify every component. Build what they describe — do not redesign while building. If a document seems wrong, **stop and ask**; it is an amendment, not a code decision.
3. **Delete before you add.** The best code is removed code.
4. **Work → right → fast.** Speed is measured but not optimized in this build.
5. **If a change is hard, reshape first** — Law 53 applied to code.
6. **Small single-purpose pieces.** One sub-engine, one module. The architecture did the decomposition; follow it.
7. **A stub is a legitimate deliverable in P3.** A stub returning a valid artifact proves the contract; a half-built real engine proves nothing.
8. **Never write an engine that reaches outside its input artifact.** Conformance will catch it — catching it in review is cheaper.
9. **The LLM sits behind one seam** (Law 21). Model swaps without touching an engine.
10. **Pin the model and temperature.** An unpinned model makes every past number unreproducible.
11. **Everything must run in CI.** A component that only works on your machine cannot produce a result, so it cannot be the only path.

---

## 4. VERIFY

### 4.1 Conformance first, on every push

Every `MUST NEVER` is a pure predicate. **No ground truth, no accountant, no AI, no cost.**

| Rule | Predicate |
|---|---|
| Debit equals credit | `journal_balances` |
| Confidence never rises without new evidence | `confidence_recalculated_only_on_evidence_change` |
| No approval while Critical stands | `no_approval_with_critical_finding` |
| Exactly once per Decision ID + Version + Destination | `idempotent_execution` |
| Six provenance attributes per fact | `provenance_complete` |
| No engine modifies an upstream artifact | `artifacts_immutable` |
| Engine 6 has no backward arrow | `no_backward_transition_from_execution` |
| Every finding names a responsible engine | `finding_has_owner` |
| **IDs never influence reasoning** | **`id_ablation`** — change the ID, assert byte-identical output |

**`id_ablation` is how a review-only rule becomes executable.** Any rule of the form *"X must not influence Y"* converts the same way: change X, assert Y unchanged.

**Rules that genuinely cannot be predicates** are published as review-only, each with **a reason and a re-examination date**. A list that only grows is silently declining coverage.

### 4.2 Negative controls, before accuracy

If any of the 9 produces an entry, **stop.** No accuracy number is computed, because none would mean anything.

### 4.3 Test first, and watch it fail

Write it, **watch it fail for the right reason**, then build until it passes. **Passed first try = the test is wrong.**

Easy failure mode here: a test asserting *"an Accounting Decision was produced"* passes against a stub and proves nothing. **Assert the result** — which ledger, which amount to the paisa, which treatment.

### 4.4 Measure per [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md)

**In CI. Pre-registered. Worst of 3 for correctness, worst of 10 for safety. Against the strong baseline. Isolated and contributed.**

The gap names the engine to fix.

### 4.5 Break things on purpose

- **Mutate the code**, confirm the test goes red. A test that stays green against broken code is not a test.
- **Run against the real dependency** — test Tally, not a mock. A mock proves the mock.
- **Poison test.** Rotating, per phase.

### 4.6 Falsify before green

Do not confirm your code works. **Try to prove it WRONG.** Separate pass, separate stance, full 19-attack list in [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md).

**Green is not done. Survived-an-attack is done.**

---

## 5. FIX

1. **A red stops everything.** Do not build on broken.
2. **Ask why until the fundamental cause.** 5 Whys is a mindset, not a count. **If the root is a CLASS, fix the class.** *"Engine 3 got invoice 7 wrong"* is an instance. *"An engine trusted an upstream artifact it should have questioned"* is the class.
3. **Every bug becomes a permanent test** — fails before the fix, guards forever, **runs in CI**.
4. **A wrong entry is never fixed by adjusting the entry.** Root-cause to the engine that produced it. **Adjusting output to match expectation is fabrication (Law 24) and it destroys the measurement.**
5. **Never fix by editing a golden label.** If the label is genuinely wrong, the accountant re-labels blind, and **both versions are kept.**
6. **Never fix by re-measuring the ceiling.** That moves the bar. It is an amendment or it does not happen.
7. **If the root is in a locked document, that is an amendment** (§M), never a code workaround.
8. **Sequence (Law 51):** loop until green in CI → DONE GATE → commit → tag → next phase.

---

## 6. The five failures this loop exists to prevent

| Failure | How it happens | What stops it |
|---|---|---|
| **Works on my machine** | Local green, CI red, or CI never run | Condition 1 — **only CI produces a result** |
| **False green** | Unit tests pass; the entry is still wrong | Condition 5 — the number, against a blind independent entry |
| **Contaminated measurement** | Engine 3 scored on Engine 2's output; the wrong engine gets rewritten | Isolated **and** contributed |
| **Measuring nothing** | Scores well on invoices; would also post a proforma | 9 hard negative controls, condition 4 |
| **Silent wrong posting** | The system is unsure, guesses, and is right often enough that nobody notices | Poison test + the absolute 0 across 10 safety runs |

**The fifth is the one that matters.** It is the only failure mode that **gets worse as the system gets better** — a system guessing correctly 95% of the time is more dangerous than one at 60%, because nobody checks it any more.

---

## 7. Per-phase notes

| Phase | What "verify" means |
|---|---|
| **P1** | No code. Two accountants confirm the labels; **the ceiling is computed and frozen**; intra-rater measured; a second person reads the protocol. |
| **P2** | CI green. Conformance green + **ID ablation passes** + malformed artifact rejected **by the correct predicate**, not merely rejected. Review-only list published with expiries. **Brain interface contract defined; the predicate proving the Brain never returns a decision, treatment, approval, ledger, rate or instruction passes.** |
| **P3** | End to end on 1 hardcoded document, **in CI**. **Application Layer verified: it creates the Transaction ID, holds exactly one state per transaction, routes every artifact, and NO engine calls another** — conformance proves no engine module imports another engine or the state store. **Brain stub answers structurally and fabricates no accounting truth.** **No accuracy claim is possible or permitted at this phase.** |
| **P4** | The first real number. One entry, **worst of 3**, blind-verified, plus 3-submission idempotency and 9/9 negatives. Both baselines recorded. **Brain populated for this one document and built BEFORE Engine 3 within the phase.** |
| **P5** | Held-out opened **once**. Isolated + contributed per engine. **Safety at 10 repeats.** Full 19-attack list. |
| **P6** | Confidence separation. **If below 0.30, say so and correct every document that implies confidence can gate anything.** Cost bounds enforced. |

---

### Verifying the two components the phases now schedule

**Neither the Brain nor the Application Layer owns a decision, so neither is ever measured for accuracy.** Both are verified structurally — by predicate, not by score.

| Component | What "verified" means | How |
|---|---|---|
| **Brain** | It never returns a decision, treatment, approval, ledger, rate or instruction | Pure predicate. Feed it a question whose answer would be a decision; assert it returns knowledge and a source, never an instruction |
| **Brain** | It is advisory — an engine may ignore it | Predicate: an engine that acts against Brain knowledge still produces a valid artifact, recording why |
| **Application Layer** | Exactly one state per Transaction ID | Predicate: the state store permits one row per ID. Zero or two is a hard failure |
| **Application Layer** | No engine calls another | Predicate: no engine module imports another engine |
| **Application Layer** | No engine touches state | Predicate: no engine module imports the state store |
| **Application Layer** | No stage is skipped | Predicate: every transition validated against the allowed-transitions table; a disallowed one is rejected, never logged-and-permitted |
| **Application Layer** | It never queries the Brain | Predicate: `src/services/` never imports `src/brain/` |
| **Application Layer** | Engine failure produces nothing | Break an engine on purpose; assert zero artifacts and that completed artifacts survive |

**These are all P2/P3 checks — free, no AI, no ground truth, run on every commit.**

---

## 8. Reporting

Every phase ends with [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md), written **before** the commit as part of the DONE GATE.

**A report without a CI run URL is not a report. A report giving a correctness number without a wrong-entry count, a strong baseline and a frozen ceiling is incomplete and is rejected.**
