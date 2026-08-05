# Confidence Specification

> **Status: the owner's decision, written down.** Every position below was decided by the
> owner before this document existed. This file records it, grounds each part in the
> repository, and states what remains open. **It does not reopen anything.**
>
> **Precedence.** Subordinate to `SYSTEM_INVARIANTS.md` (level 1) and to the level-2 locked
> decisions — `MEASUREMENT_FRAMEWORK.md`, `ACCOUNTING_DEFINITIONS.md`,
> `SUB_ENGINE_RESPONSIBILITIES.md`. Where this document and any of those disagree, **they
> win and this document is wrong.** Report it; never resolve it in code
> (`SYSTEM_INVARIANTS.md:26`).
>
> **Companion, not replacement.** The 16 parameters live in
> [`ENGINE_1_CONFIDENCE_PARAMETERS.md`](ENGINE_1_CONFIDENCE_PARAMETERS.md) and are **not
> restated here** (Law 19, one source of truth). §8 says only what this document adds.
>
> **No number in this file is invented.** Where a value is required and none has been
> supplied, the text reads `UNSET` and names who supplies it (Law 52, Law 54;
> `CLAUDE.md:660`).

---

## 1. What confidence IS in this system

> **Confidence is the estimated uncertainty of an OBSERVATION.**

It answers exactly one question, and it is the question the `confidence` sub-engine was
given: *how much of this reading should be trusted?*
(`SUB_ENGINE_RESPONSIBILITIES.md:82` — *"Owns the honest measurement of extraction
trustworthiness, per field and overall, and the identification of the specific regions and
fields that are weak."*)

The scope differs by origin, and the two are never merged:

| Origin | Confidence measures | Source |
|---|---|---|
| **Document** — read off an artifact | How reliably it was **read** | `SUB_ENGINE_RESPONSIBILITIES.md:825` |
| **Human** / **Structured Metadata** — asserted | How faithfully it was **captured** | `SUB_ENGINE_RESPONSIBILITIES.md:826`, `ENGINE_1_INPUT_ENGINE_RULES.md:271` |

> **Neither measures whether the content is true**
> (`SUB_ENGINE_RESPONSIBILITIES.md:828`).

### What confidence is NOT — stated explicitly, because each mistake has a real cost

| Confidence is **not** | Why, and where the repository already says so |
|---|---|
| **A probability of correctness** | The owner's ruling, in the code: *"It is not a probability"* (`src/accountant_dad/confidence.py:6-8`). And until the separation test passes, *"confidence is an ordinal ranking, not a probability"* (`MEASUREMENT_FRAMEWORK.md:258`). A four-place `Decimal` **looks** like a probability, which is exactly why the ruling says in words that it is not one (`confidence.py:43-47`). |
| **`P(the entry is correct)`** | Correct is a property of an **entry**, defined over four fields, judged by Engine 5 (`ACCOUNTING_DEFINITIONS.md:40-48, 73`). Confidence is a property of a **reading**. They are different objects with different owners; no arithmetic connects them. |
| **Permission to post** | See §2. `Safe` has four conditions and confidence is not one of them (`ACCOUNTING_DEFINITIONS.md:128-133`). |
| **A judgement of business plausibility** | *"Cannot use business plausibility as evidence — it measures extraction quality, not whether the content makes commercial sense"* (`SUB_ENGINE_RESPONSIBILITIES.md:88`). |
| **Truth confidence for a human note** | *"Capture confidence: the system stored exactly what was typed. Truth confidence: unknown until supported by other evidence"* (`ENGINE_1_INPUT_ENGINE_RULES.md:280-285`). A human note *"must never increase Evidence Reliability simply because it exists"* (`ENGINE_1_INPUT_ENGINE_RULES.md:289`). |
| **Commensurable across instruments** | An OCR score of 0.70 and a table-structure score of 0.70 are not established to be the same amount of doubt. That claim is strictly stronger than ordinality and needs labelled data (`ENGINE_1_CONFIDENCE_PARAMETERS.md:113-118`). See §4. |
| **Something an engine may raise by reasoning harder** | *"Confidence never changes because an engine reasoned harder"* (`SYSTEM_INVARIANTS.md:51`). It is recalculated **only when evidence changes** (`SYSTEM_INVARIANTS.md:46`, `MEASUREMENT_FRAMEWORK.md:304`). |

### The representation — one type, already built

The stored form is `Confidence` in `src/accountant_dad/confidence.py:113-117`. **This
specification describes that type. It does not define a second one, and no schema may
declare its own** (`confidence.py:13-14`).

What the type enforces structurally (`confidence.py:65-105`):

```
Decimal only        float and int are REFUSED, never converted    confidence.py:76-81
finite              NaN and the infinities refused                confidence.py:82-87
[0.0000, 1.0000]    inclusive                                     confidence.py:88-89
≤ 4 decimal places  refused rather than rounded                   confidence.py:97-104
```

What the type **cannot** enforce, stated here because a reader who assumes importing it
satisfies the whole ruling would be quietly wrong (`confidence.py:34-41`):

> *"must not be used as the sole gating criterion for any decision"* — that constrains how
> a **caller** reasons, not what a value contains. No type can see the decision a number
> was used for.

That prohibition is enforced by §2 of this document, by review, and by the conformance
registry's review-only list — never by the type.

---

## 2. What confidence may NEVER do

**Each line below is written so it can become a test.** The right-hand column names the
observation that would prove a violation.

### 2.1 Confidence is never permission to post

> **Posting is a multi-gate decision. It is never `if confidence > t: POST`.**

| # | Prohibition | Source | What would catch a violation |
|---|---|---|---|
| **P1** | No code path may make execution conditional on a confidence value alone. | `confidence.py:6-8` (the ruling) · `ACCOUNTING_DEFINITIONS.md:128-133` | A single comparison of a `Confidence` against a constant or a configured threshold, whose true-branch reaches Engine 6. Grep-able; also a mutation test — change the threshold, assert the posting decision does not move. |
| **P2** | `Safe` is the conjunction of **four** conditions — correct · traceable · no Critical finding standing · period open and posting permitted. Confidence is not among them and may not be substituted for any of them. | `ACCOUNTING_DEFINITIONS.md:128-133` | An approval produced with any of the four unsatisfied. |
| **P3** | Permission to execute is decided by Engine 5 **before** execution. Confidence never grants it and never accelerates it. | `SYSTEM_INVARIANTS.md:203-209` (INV-8) | Engine 6 discovering a permission problem. That is the failure INV-8 exists to make impossible. |
| **P4** | The `confidence` sub-engine may not reject a document or halt the pipeline. | `SUB_ENGINE_RESPONSIBILITIES.md:88` | Any control-flow exit from `confidence` other than returning a Confidence Report. |
| **P5** | No component — parent Input Engine included — may raise or lower a confidence value produced by the `confidence` sub-engine. | `ENGINE_1_INPUT_ENGINE_RULES.md:109` · `SYSTEM_INVARIANTS.md:235` | A Confidence Report score disagreeing with the provenance score for the same field. **Already enforced structurally** — `evidence.py:347-353` refuses the artifact rather than reconciling it. |
| **P6** | A later confidence never exceeds the weakest critical confidence it depends on; specifically `Understanding Confidence ≤ Evidence Reliability`. | `SYSTEM_INVARIANTS.md:67` · `SUB_ENGINE_RESPONSIBILITIES.md:787` | Two confidences read off one artifact chain, compared. Arithmetic, no threshold. See §6, check H6. |

### 2.2 Confidence gates nothing until calibration is proven

> **This is not a policy. It is a level-2 lock:** *"Until it passes this test, confidence is
> an ordinal ranking, not a probability, and **it may gate NOTHING**"*
> (`MEASUREMENT_FRAMEWORK.md:258`).

| # | Prohibition | Source | What would catch a violation |
|---|---|---|---|
| **P7** | Until `accuracy(top confidence tercile) − accuracy(bottom tercile) ≥ 0.30` is measured and passes, no confidence value may gate, route, filter, block, escalate or suppress anything. | `MEASUREMENT_FRAMEWORK.md:261, 266-267` | Any branch on a confidence value taken before a separation result exists in `runs/`. |
| **P8** | No document, message, log line or interface may present confidence as a probability until separation passes **and** the calibration curve is measured. Doing so is a false statement under Law 54. | `MEASUREMENT_FRAMEWORK.md:269` | A UI string, log format or docstring rendering confidence as *"90% likely correct"*. |
| **P9** | If the curve is flat, the obligation is to **say so publicly and correct every document implying otherwise** — not to quietly stop using it. | `MEASUREMENT_FRAMEWORK.md:283, 289-291` | A flat curve measured and not published. |
| **P10** | Statements about confidence require ~100 labelled documents **and** separation ≥ 0.30. Below that, nothing may be claimed. | `MEASUREMENT_FRAMEWORK.md:339` · `GOLDEN_DATASET.md:166` | Any confidence claim in a phase report without both. |
| **P11** | Missing required confidence configuration **fails fast at startup, naming the parameter**. Never a default, never a fallback, never at first use. | `CLAUDE.md:660` · `ENGINE_1_CONFIDENCE_PARAMETERS.md:7-10, 152-159` | Startup succeeding with a parameter absent; or any numeric literal used as a threshold under `engines/input_engine/`. |

### 2.3 Confidence never conceals

| # | Prohibition | Source |
|---|---|---|
| **P12** | Uncertainty is never suppressed because it would delay processing. | `SUB_ENGINE_RESPONSIBILITIES.md:90` · `ENGINE_1_INPUT_ENGINE_RULES.md:627` |
| **P13** | Where reliability cannot be established, confidence goes **down** — never up, and never to a default *"good enough"* value. | `SUB_ENGINE_RESPONSIBILITIES.md:90` · `ENGINE_1_INPUT_ENGINE_RULES.md:625` |
| **P14** | Every uncertainty marker carries a reason. A bare score cannot become a good question downstream. | `ENGINE_1_INPUT_ENGINE_RULES.md:626` — **enforced**: `evidence.py:220-231` refuses a blank reason. |
| **P15** | A confidently-wrong reading is a **failure** even when the guess was right; a low-confidence reading that is honestly marked is a **success**. | `ENGINE_1_INPUT_ENGINE_RULES.md:647` |

---

## 3. The raw signal

> **Preserve the raw signal — per field, per region, per instrument, with its origin.**

### 3.1 Why raw, and not a summary

A summary is a lossy, irreversible transform performed **before** anyone knows which
transform is correct. Three consequences, each concrete:

1. **The combining rule is undecided** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:61`). Summarising
   now would commit to the rule the specification says does not yet exist.
2. **Calibration needs the inputs, not the output.** Stage 2 of the only permitted route
   requires every document to record *"per-region OCR · per-field · classification · table
   · document score · whether extraction was ACTUALLY correct · which fields failed ·
   processing time · source document type"* (`ENGINE_1_CONFIDENCE_PARAMETERS.md:133-135`).
   A summary discards the terms the calibration would be computed over.
3. **Artifacts are immutable** (`SYSTEM_INVARIANTS.md:142`). A signal not recorded at
   creation cannot be recovered later; the document would have to be re-processed, and the
   original processing conditions no longer exist.

> **A summary computed before the rule is known is a decision nobody made, taken
> irreversibly.**

### 3.2 Granularity — what is recorded

| Level | What it is | Why it is separate |
|---|---|---|
| **Per region** | The reader's score for one located region of the page | `SUB_ENGINE_RESPONSIBILITIES.md:54` — the reader emits *"source locations · extraction confidence"*. A region is the unit the OCR instrument actually scores. |
| **Per field** | The score for one named parsed field | `ENGINE_1_INPUT_ENGINE_RULES.md:599-601` shows the emitted shape keyed by field name. `evidence.py:211-217` is the type. |
| **Per cell** | The score for one cell inside an accepted table | Parameter #11 in `ENGINE_1_CONFIDENCE_PARAMETERS.md:45` exists only because cells are scored separately from tables. |
| **Per instrument** | Which tool produced the signal — OCR, table-structure detection, document-type classification, PDF text layer, vision fallback | Corollary 6.2 (§4): these are **independent scales**. Merging them destroys the only information that would let anyone establish, later, whether they are commensurable. Instruments are named in `TECHNOLOGY_STACK.md:23-30`. |
| **Per provided source** | Capture fidelity for a Human Business Description or metadata field | `ENGINE_1_INPUT_ENGINE_RULES.md:624` · `SUB_ENGINE_RESPONSIBILITIES.md:90`. A different quantity entirely — see §1. |

### 3.3 Provenance carried with every signal

Every fact already carries six attributes, none optional (`SYSTEM_INVARIANTS.md:243-252`,
enforced in `evidence.py:118-130`): **Source Type · Source ID · Evidence Reference ·
Timestamp · Confidence · Corroborated**.

> **No engine may merge these origins into a single anonymous fact**
> (`SYSTEM_INVARIANTS.md:254`).

A raw confidence signal is subject to the same rule. **A score without its origin is not
evidence about the reading — it is a number about nothing** (`ENGINE_1_INPUT_ENGINE_RULES.md:245`
— *"A value carried without all three is not evidence and must not be emitted"*).

Engine 1 records `Corroborated: not assessed`, honestly, because it cannot assess it
(`ENGINE_1_INPUT_ENGINE_RULES.md:295`; the enum has exactly one member, `evidence.py:112-115`).

### 3.4 Where the raw signal lives today — and the gap

The frozen artifact carries:

| Component | Type | Carries |
|---|---|---|
| `ConfidenceReport.confidence_scores` | `tuple[FieldConfidence, ...]` | one score per **name**; the name need not be a detected field (`evidence.py:211-217`) |
| `ConfidenceReport.uncertainty_markers` | `tuple[UncertaintyMarker, ...]` | subject + **reason**, both non-blank (`evidence.py:220-231`) |
| `ConfidenceReport.reliability_information` | `str` | free text (`evidence.py:241`) |
| `ConfidenceReport.risky_fields` | `tuple[str, ...]` | names, de-duplicated (`evidence.py:242, 256-259`) |

Two structural guarantees already hold, and they are worth naming because they are the
skeleton of A8:

- **Every detected field is scored, or the artifact is refused** (`evidence.py:337-344`).
- **The Confidence Report and the field's own provenance must agree, or the artifact is
  refused** — not reconciled (`evidence.py:347-353`).

**The gap.** `FieldConfidence` is `(field_name, confidence)`. It has **no structured slot
for the instrument that produced the score, and no slot for a page region**. Per-name
scoring can carry a region or an instrument only by encoding it into a string, which is a
convention, and conventions drift — the exact failure `confidence.py:16-24` was written
after. **Recorded as open item O4 in §9. Not fixed here: the schema is frozen P2 work and a
change is an amendment (§M).**

---

## 4. Why there is no document-level scalar

> **There is NO document-level confidence scalar. None.**

This is not a preference and not a simplification. **The elimination is a named theorem.**

### 4.1 The theorem

> **Marichal, J.-L. & Mesiar, R.** *Meaningful aggregation functions mapping ordinal scales
> into an ordinal scale: a state of the art.* **Aequationes Mathematicae 77(3), 2009,
> pp. 207–236.** **Corollary 5.7** — first proved by **Orlov, 1981**:
>
> *A symmetric, continuous, idempotent function on an ordinal scale is comparison
> meaningful **iff it is an order statistic function**.*

Cited in the repository at `ENGINE_1_CONFIDENCE_PARAMETERS.md:86-92`.

**What that means, plainly.** An ordinal scale is one where only the *order* of values is
information — "this reading is worse than that one" is meaningful, "this reading is twice
as good" is not. Such a scale may be re-expressed by any strictly increasing transformation
`φ` without losing information. A function is *comparison meaningful* if the comparison it
produces survives every such `φ`.

**Order statistics** are the functions that pick the k-th smallest value: min, max, median,
`worst_k`. They survive, because picking the k-th smallest commutes with any monotone
re-labelling.

**Mean, product, Bayesian pooling and Dempster–Shafer combination are not order
statistics.** On an ordinal scale they are not merely inaccurate — **their ordering flips**
under a transformation the data permits. The repository records the concrete counterexample
for product: `φ(x) = x + 1` reverses which of two documents ranks higher, and product
therefore fails even at the *interval* level
(`ENGINE_1_CONFIDENCE_PARAMETERS.md:93-96`).

The two additional eliminations, on grounds of unmeasurable inputs rather than scale
(`ENGINE_1_CONFIDENCE_PARAMETERS.md:100-104`):

```
Bayesian          no estimable likelihood — p(s | wrong) needs observed wrong readings
Dempster-Shafer   output ~24x more sensitive to the INVENTED ignorance mass than to the
                  MEASURED evidence, under conflict
```

Inventing either input is forbidden outright (Law 24; `SYSTEM_INVARIANTS.md:291`).

### 4.2 The second corollary — why even `min` is not free

> **Same paper, Corollary 6.2:** on **independent** ordinal scales, the only
> comparison-meaningful function is a **projection onto one coordinate**.

Cited at `ENGINE_1_CONFIDENCE_PARAMETERS.md:113-118`.

OCR, table-structure detection and document-type classification are **three different
instruments** (`TECHNOLOGY_STACK.md:26, 29` and the classifier implied by parameter #9 at
`ENGINE_1_CONFIDENCE_PARAMETERS.md:43`). Taking `min` across them asserts
**commensurability** — that an OCR 0.70 is the same amount of doubt as a table-structure
0.70.

> **That claim is strictly stronger than ordinality, is not implied by it, and can only be
> established with labelled data** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:117-118`).

So the surviving family is `{min, worst_k}` on a *single* scale, and **nothing survives
across instruments** without a commensurability claim nobody can currently support.

### 4.3 The conclusion — the scalar adds nothing and creates a hazard

The arithmetic identity that settles it:

```
min(c₁ … cₙ) ≥ t     is IDENTICALLY     ∀i : cᵢ ≥ t
```

A minimum-based document floor and a set of per-field floors at the same value are **the
same predicate**. Therefore:

| | |
|---|---|
| **What the scalar adds** | Nothing that per-field floors do not already carry |
| **What the scalar costs** | A **false affordance** — a single number invites someone downstream to average it, compare it across documents, or threshold it, **all of which are meaningless on this scale** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:120-125`) |

**The research reached the owner's A5 position independently**
(`ENGINE_1_CONFIDENCE_PARAMETERS.md:125`).

### 4.4 What follows for implementation

1. **No `document_confidence` field is created**, in any artifact, in any engine.
2. **No aggregation of confidences is computed** — not mean, not product, not min, not
   `worst_k`, not Bayes, not Dempster–Shafer.
3. **Every constraint on confidence is expressed per field, per region, per cell or per
   instrument** — the level at which the signal was produced.
4. `ConfidenceReport` (`evidence.py:234-242`) **has no document-level score field, and none
   is added.** The absence is correct and is not an omission.
5. Parameters #5, #6, #7, #13, #14 and #15 are defined over a document score. **They have
   no referent.** See §8.

---

## 5. How confidence is measured

> **Expected Calibration Error is the WRONG headline metric here. The reliability diagram
> in the high-confidence region, plus Maximum Calibration Error, replace it.**

**Neither ECE, MCE nor "reliability diagram" appears anywhere in `docs/` or `src/` today** —
verified by search, 2026-08-05. This section introduces them. It does not replace the two
tests already locked in `MEASUREMENT_FRAMEWORK.md` §10; it specifies the **shape** half of
them.

### 5.1 The two locked tests come first, and neither is replaced

| Test | Question | Threshold | Source |
|---|---|---|---|
| **Separation** — the **gate** | Does confidence carry information at all? | `accuracy(top tercile) − accuracy(bottom tercile) ≥ 0.30` | `MEASUREMENT_FRAMEWORK.md:261` |
| **Calibration** — the **shape** | What kind of thing is confidence? | Diagonal / monotonic / flat | `MEASUREMENT_FRAMEWORK.md:281-283` |

> *"Neither replaces the other"* (`MEASUREMENT_FRAMEWORK.md:287`). **Separation is passed
> before calibration means anything** — a curve fitted to a number that does not separate
> right from wrong is a shape drawn on noise.

### 5.2 Why ECE is the wrong headline

**Expected Calibration Error** is the sample-weighted mean over bins of the gap between a
bin's mean stated confidence and its observed accuracy:

```
ECE = Σᵦ (nᵦ / N) · | accuracy(b) − mean_confidence(b) |
```

> **Naeini, M. P., Cooper, G. F. & Hauskrecht, M.** *Obtaining Well Calibrated Probabilities
> Using Bayesian Binning.* **Proceedings of AAAI 2015, pp. 2901–2907** — the paper that
> defines both ECE and MCE.

**The defect, stated concretely: within-bin cancellation.** Every term in the sum is a
non-negative absolute gap, so ECE does not cancel *between* bins — it cancels *inside*
them. Two failures at once:

1. **Inside a bin**, over-confident and under-confident items offset each other before the
   absolute value is taken. A bin whose members are half badly over-confident and half
   badly under-confident reports a small gap and looks well behaved.
2. **Across bins**, weighting by `nᵦ / N` means the bins that hold most of the mass
   dominate. In a working extraction system most readings land in the **high** band — but
   if the well-populated bands are mid-range, a severe error in a sparse high-confidence
   bin is multiplied by a small weight and disappears into a good-looking average.

> **A well-behaved average can hide severe miscalibration exactly where the decisions are
> made.**

For this system that is not an academic point. **The high-confidence region is the only
region that matters**, because it is the region in which the system would act without a
human, and a confidently wrong reading is precisely the failure mode
`ENGINE_1_INPUT_ENGINE_RULES.md:647` and `ADVERSARIAL_TESTING.md:13` name as the dangerous
one:

> *"The dangerous failure is not a crash — it is a confident wrong answer."*
> (`ADVERSARIAL_TESTING.md:13`)

**A single averaged number that can be dragged down by good behaviour elsewhere is exactly
the wrong instrument for finding it.**

### 5.3 What replaces it — two things, reported together

#### (a) The reliability diagram, restricted to the high-confidence region

Bucket every scored reading by stated confidence; measure observed correctness per bucket;
plot observed against stated. The locked procedure is already written
(`MEASUREMENT_FRAMEWORK.md:277`) and the verdict table is already fixed
(`MEASUREMENT_FRAMEWORK.md:281-283`).

> **DeGroot, M. H. & Fienberg, S. E.** *The Comparison and Evaluation of Forecasters.*
> **The Statistician 32(1–2), 1983, pp. 12–22** — the origin of reliability diagrams and
> of the calibration/refinement decomposition.

**The addition this specification makes: the diagram is read in the high-confidence region
specifically, and the region is where the verdict is taken.** The whole-range plot is still
produced and still published; it is not the headline.

Required, and all `UNSET`:

| Quantity | Status | Supplied by |
|---|---|---|
| The lower boundary of the "high-confidence region" | `UNSET` | **The owner**, after Stage 3 measurement (§7). It is an operating point, and `CLAUDE.md:660` forbids choosing one before the data exists. |
| Number of bins, and whether they are equal-width or equal-mass | `UNSET` | **The owner.** Bin choice changes the reported number; picking it after seeing results would void the run (`MEASUREMENT_FRAMEWORK.md:27`). |
| Minimum bin occupancy below which a bin is reported but not scored | `UNSET` | **The owner.** |

#### (b) Maximum Calibration Error

```
MCE = maxᵦ | accuracy(b) − mean_confidence(b) |
```

Same reference: **Naeini, Cooper & Hauskrecht, AAAI 2015.**

**Why MCE and not ECE:** MCE takes the maximum, not the weighted mean. **A single badly
miscalibrated bin cannot be averaged away by well-behaved bins, and cannot be diluted by a
small sample weight.** It answers the question the accounting use actually asks —
*"what is the worst the stated confidence has ever lied by?"* — which is the same shape of
question as `MEASUREMENT_FRAMEWORK.md:88` (*worst run, never the average*) and
`MEASUREMENT_FRAMEWORK.md:102` (*spread is itself a metric*). **This framework already
prefers worst-case over average everywhere else; MCE is that preference applied to
calibration.**

| Quantity | Status | Supplied by |
|---|---|---|
| The MCE ceiling that must hold | `UNSET` | **The owner.** |
| Whether MCE is computed over the whole range or the high-confidence region only | `UNSET` | **The owner.** |

### 5.4 Rules that bind every calibration run

1. **Pre-registered.** Bins, region boundary and MCE ceiling are committed and hashed
   **before** the run. *"Any change to scoring after seeing results invalidates the run"*
   (`MEASUREMENT_FRAMEWORK.md:27`).
2. **CI only.** A local calibration run produces no number
   (`MEASUREMENT_FRAMEWORK.md:33-45`, `EVALUATION_PROTOCOL.md:45`).
3. **Sample size on the plot.** Below `N = 100` the curve is **indicative**, is still
   computed and still published, and may not support a probability claim
   (`MEASUREMENT_FRAMEWORK.md:285`).
4. **Computed from Phase 4 onward, at whatever N exists**
   (`MEASUREMENT_FRAMEWORK.md:275`).
5. **A flat curve is published, not buried** (`MEASUREMENT_FRAMEWORK.md:289-291`).
6. **Per instrument and per level, never pooled.** Pooling OCR, table and classification
   signals into one diagram asserts the commensurability Corollary 6.2 says is unestablished
   (§4.2). One diagram per scale.

---

## 6. The eight deterministic hard checks

> **These need no threshold. They are checkable by arithmetic or by lookup, never by
> judgment. THEY ARE NOT CONFIDENCE CODE.**

They are listed in a confidence specification for one reason: **they are what actually
protects the books.** Every one of them holds or fails on its own terms whatever confidence
says, and none of them becomes weaker when confidence is uncalibrated — which is why the
system can be made *provably safe long before it is provably correct*
(`ACCOUNTING_DEFINITIONS.md:139-141`).

Checks **H1–H5** are the owner's own *five structural safety gates*, recorded verbatim in
`EXECUTION_QUEUE.md:132-143`. **H6–H8** are the threshold-free checks that bear directly on
confidence and evidence.

| # | Check | The rule | Arithmetic or lookup | Home | Authorised now? |
|---|---|---|---|---|---|
| **H1** | **Arithmetic** | `taxable × rate = tax` **and** `taxable + tax = total` | Arithmetic, `Decimal` | **Engine 5** — `tax_validation` (internal tax consistency, `SUB_ENGINE_RESPONSIBILITIES.md:528`) and `data_validation` (*"totals reconciling to their lines"*, `SUB_ENGINE_RESPONSIBILITIES.md:544`) | ❌ **No.** Engines 2–6 frozen (`CLAUDE.md:670`) |
| **H2** | **Traceability** | Every field resolves to a source region in the document | Lookup — reference resolves or it does not | **Split.** (a) *Every emitted value carries provenance and a score*: **Engine 1** — `ENGINE_1_INPUT_ENGINE_RULES.md:245`, already structural at `evidence.py:322-354`. (b) *Traceability status across the chain*: **Engine 5** `data_validation` (`SUB_ENGINE_RESPONSIBILITIES.md:548`) | (a) ✅ **Yes** — Engine 1, Amendment 3 (`CLAUDE.md:645`). (b) ❌ **No** |
| **H3** | **Balance** | debit = credit, **exact to the paisa** | Arithmetic, `Decimal` | **Engine 3** `journal_intelligence` produces it (`SUB_ENGINE_RESPONSIBILITIES.md:312`); **Engine 5** `accounting_validation` checks it (`SUB_ENGINE_RESPONSIBILITIES.md:512`, Critical at `ENGINE_5_VALIDATION_ENGINE_RULES.md:156`). **Balance ≠ correctness** (`SYSTEM_BOUNDARIES.md:146`) | ❌ **No.** Both frozen |
| **H4** | **Period** | A closed accounting period is detected **before** Tally is contacted | Lookup against Company Knowledge (`SYSTEM_INVARIANTS.md:271` — financial year) | **Engine 5** `data_validation` owns the closed-period gate (`SUB_ENGINE_RESPONSIBILITIES.md:544`); mandated by INV-8 (`SYSTEM_INVARIANTS.md:203-209`) — *"Execution must never discover that posting was impossible"* | ❌ **No** |
| **H5** | **Idempotency** | Key = **Decision ID + Decision Version + Destination System**. Never Transaction ID | Lookup — key seen or not seen | **Engine 6** `posting_manager` (`COMMUNICATION_RULES_EXECUTION_INTERNAL.md:108`, `DATA_FLOW.md:693`) | ❌ **No** |
| **H6** | **Confidence-chain bound** | A later confidence never exceeds the weakest critical confidence it depends on. Specifically `Understanding Confidence ≤ Evidence Reliability` | Arithmetic — a comparison **between two confidences**, never against a cutoff | System-wide invariant (`SYSTEM_INVARIANTS.md:67`); the Engine 2 bound at `SUB_ENGINE_RESPONSIBILITIES.md:787`. **Engine 1 supplies the lower bound only** | ⚠️ **Partly.** Engine 1's half is authorised; the comparison needs Engine 2, which is frozen |
| **H7** | **Tri-state distinguishability** | **Absent**, **zero** and **unreadable** are three different states and must remain distinguishable | Lookup — a type check, no arithmetic | **Engine 1** `parser` (`ENGINE_1_INPUT_ENGINE_RULES.md:568-569`, `SUB_ENGINE_RESPONSIBILITIES.md:74`). **Already enforced**: `None` = unreadable, `"0"` = a read zero, `""` refused (`evidence.py:149-151`) | ✅ **Yes** |
| **H8** | **Identity ablation** | Change every identifier, hold everything else byte-identical, re-derive: **the outcome must not move** | Byte comparison | Not an engine. The conformance harness — `src/accountant_dad/ablation.py`. INV-9 (`SYSTEM_INVARIANTS.md:213-219`), converted to a predicate at `MEASUREMENT_FRAMEWORK.md:313`, run at `EVALUATION_PROTOCOL.md:87`, attack 19 at `ADVERSARIAL_TESTING.md:52`, P2 done-condition at `MVP_IMPLEMENTATION_BLUEPRINT.md:135` | ✅ **Yes** — built |

### 6.1 Each gate ships with a canary that MUST be rejected

> *"A gate that exits 0 without examining anything is hollow, and a hollow gate is worse than
> no gate — it manufactures trust"* (`EXECUTION_QUEUE.md:145`).

This is the same rule as §J.5 and the gate lifecycle in `CLAUDE.md` — *prove it passes on
correct code, prove it FAILS on deliberately broken code, then promote it.* **A hard check
without a canary is not one of the eight.**

### 6.2 What the eight are NOT

- **Not a substitute for correctness.** They enforce conditions 2, 3 and 4 of `Safe`. Only
  condition 1 — the entry being **correct** — needs a human
  (`ACCOUNTING_DEFINITIONS.md:137-139`).
- **Not confidence.** None of them reads a confidence value, and adding one to any of them
  would convert a threshold-free check into a threshold, which is the whole failure this
  specification exists to prevent.
- **Not exhaustive of everything deterministic.** Further threshold-free candidates were
  found and are **not** silently folded in — see open item **O7** in §9.

---

## 7. The calibration route

The only permitted route is the four-stage one already written at
`ENGINE_1_CONFIDENCE_PARAMETERS.md:129-147`. Restated here as **what blocks each stage and
what unblocks it** — the part that document leaves implicit.

```
1  ARCHITECTURE   every parameter named, externally configured, no default
2  MEASUREMENT    every document records every raw signal + whether extraction was
                  ACTUALLY correct
3  CALIBRATION    once a validation set exists: histograms · precision/recall vs
                  threshold · FPR · FNR · calibration curves · confusion matrices ·
                  recommended operating points
4  FREEZE         a report per parameter → the user approves → only then is a value
                  written
```

| Stage | Blocked by | Unblocked by | Needs labelled ground truth? |
|---|---|---|---|
| **1 · ARCHITECTURE** | Nothing. | Already permitted — Engine 1 is released in full (Amendment 3, `CLAUDE.md:645`) and the confidence sub-engine is explicitly named as configuration-driven (`CLAUDE.md:660`). | **No** |
| **2 · MEASUREMENT** | Nothing but Stage 1. Engine 1 runs in **measurement mode**: it records every signal and **gates nothing** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:23-24`). | Stage 1 complete + the recording surface of §3 existing. | **No** |
| **3 · CALIBRATION** | **A validation set with ground truth.** That is P1 (`MVP_IMPLEMENTATION_BLUEPRINT.md:70, 119`) — 25 documents, two qualified labelers, ceiling frozen and hashed (`MVP_IMPLEMENTATION_BLUEPRINT.md:134`, `GOLDEN_DATASET.md:11`). Also blocked by the undefined combining rule for anything document-level, which §4 removes the need for. | P1 delivering labels; then the separation test at `MEASUREMENT_FRAMEWORK.md:261`. | **YES** |
| **4 · FREEZE** | Stage 3, plus **the owner's written approval per parameter.** *"Configuration is never modified automatically. Step 4 produces a recommendation and stops"* (`ENGINE_1_CONFIDENCE_PARAMETERS.md:144`). | A per-parameter report — recommended value · justification · supporting metrics · trade-offs · effect of raising it · effect of lowering it — then the owner approves (`ENGINE_1_CONFIDENCE_PARAMETERS.md:139-141`). | **YES** |

> **Stated plainly: stages 3 and 4 need labelled ground truth. Stages 1 and 2 do not**
> (`ENGINE_1_CONFIDENCE_PARAMETERS.md:146-147`).

**And therefore, plainly: today, and for the whole of Stages 1 and 2, confidence gates
nothing.** That is not a limitation being worked around. It is
`MEASUREMENT_FRAMEWORK.md:258` operating exactly as written.

### 7.1 The sample-size problem, recorded rather than buried

Separation and calibration are what **~100 golden documents** enable
(`GOLDEN_DATASET.md:166`). The golden set as specified is **16 golden + 9 negative**
(`GOLDEN_DATASET.md:15-21`). **Passing P1 in full therefore does not by itself unblock
Stage 3 to the point where confidence may gate anything.** Open item **O9** in §9.

---

## 8. The 16 parameters

**The table is not reproduced here.** It lives at
[`ENGINE_1_CONFIDENCE_PARAMETERS.md:33-50`](ENGINE_1_CONFIDENCE_PARAMETERS.md) and that is
its only home (Law 19; `SYSTEM_INVARIANTS.md:20` — *an invariant is stated once*).

This section adds exactly one thing: **which parameters still have a referent once A5
removes the document scalar, and which do not.**

### 8.1 Dead on arrival — no document scalar exists to threshold

| # | Parameter | Why it has no referent |
|---|---|---|
| **5** | `document_confidence_floor` | *"Lowest **whole-document score**…"* — there is no whole-document score (§4). |
| **6** | `human_review_trigger` | *"**Document score** at or below which the document is routed to a human"* — no document score, and routing on confidence is barred by P7 regardless. |
| **7** | `retry_trigger` | *"**Document score** at or below which Engine 1 re-processes"* — no document score. |
| **13** | `document_score_rule` | The rule combines per-field scores into **one document score**. §4 removes the output. Also already the deepest of the three Law 54 gaps (`ENGINE_1_CONFIDENCE_PARAMETERS.md:61`). |
| **14** | `document_score_weights` | Conditional on #13 being `weighted_mean` — **eliminated by Corollary 5.7 independently** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:99`). Dead twice over. |
| **15** | `worst_k` | Conditional on #13 being `worst_k`. Survives the theorem as an order statistic, but has nothing to compute over. **Its two effect columns were inverted and were corrected on 2026-08-05** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:68-82`); the correction stands whether or not the parameter is ever used. |

**Six of sixteen.** Note that `ENGINE_1_CONFIDENCE_PARAMETERS.md:65` states *"Until #13 has
a rule, #1–#12 cannot be calibrated, because there is no document score to calibrate
against."* **Under A5 that dependency does not bind**: with no document scalar, #1–#12 are
calibrated against **observed per-field / per-region correctness directly** — the very thing
Stage 2 records (`ENGINE_1_CONFIDENCE_PARAMETERS.md:133-135`). **Removing the scalar
removes the blocker.** This is the practical dividend of A5 and it should be stated
plainly.

### 8.2 Surviving — a real referent exists at the level the signal is produced

| # | Parameter | Level it lives at |
|---|---|---|
| **1** | `ocr_region_accept` | per region |
| **2** | `ocr_vision_fallback` | per region — see O6 |
| **3** | `field_confidence_floor` | per field |
| **4** | `field_risky_mark` | per field — **Law 54 gap**, see §9 |
| **9** | `classification_accept` | per instrument (document-type) |
| **10** | `table_structure_accept` | per instrument (table structure) |
| **11** | `table_cell_accept` | per cell |
| **12** | `capture_fidelity_floor` | per provided source — **Law 54 gap**, see §9 |

**Surviving ≠ usable.** Every one of these eight is a **gate**, and P7 forbids all gating
until separation passes. Until then they are **named, externally configured, and inert** —
Stage 1 and Stage 2 exactly as written.

### 8.3 Not confidence parameters at all — unaffected by A5

| # | Parameter | Kind |
|---|---|---|
| **8** | `retry_max_attempts` | a count (`N`). No confidence is read. Unaffected. |
| **16** | `processing_budget_ms` | wall-clock (`ms`). No confidence is read. Unaffected. Sits under the global bound of ≤ 60 s/document (`MEASUREMENT_FRAMEWORK.md:323`). |

### 8.4 Tally

```
16  total
 6  dead on arrival — no document scalar to threshold   (#5 #6 #7 #13 #14 #15)
 8  surviving, at the level the signal is produced, INERT until separation passes
 2  not confidence parameters at all                     (#8 #16)
```

**Values supplied by the user: 0** (`ENGINE_1_CONFIDENCE_PARAMETERS.md:169`). Unchanged by
this document, which supplies none.

---

## 9. What is still open

**Format:** what is missing · who owns the answer · what unblocks it.

### The three Law 54 gaps, unchanged

| # | Gap | What is missing | Owner | Unblocked by |
|---|---|---|---|---|
| **O1** *(param #4)* | **What makes a field "risky"** | `ENGINE_1_INPUT_ENGINE_RULES.md:604-610` grants the action *"Highlight risky fields"* and `ConfidenceReport.risky_fields` exists (`evidence.py:242`) — but **no document says at what point a field becomes risky.** Deriving it from `confidence < X` is a confidence gate, barred by `MEASUREMENT_FRAMEWORK.md:258` and P7. | **The owner** — Law 54 forbids the engineer inventing it (`CLAUDE.md` §E.3). | Either (a) a **threshold-free** definition of risky — e.g. *a field the reader reported as unread*, which is a state and not a score (`ENGINE_1_INPUT_ENGINE_RULES.md:568-569`) — or (b) waiting for separation to pass and then setting a per-field threshold at Stage 4. **(a) is available now; (b) is not.** |
| **O2** *(param #12)* | **Who computes capture fidelity, and how** | `ENGINE_1_INPUT_ENGINE_RULES.md:624` and `SUB_ENGINE_RESPONSIBILITIES.md:90` require `confidence` to score it. `ENGINE_1_INPUT_ENGINE_RULES.md:283` *illustrates* 100% — **an illustration is not a measurement.** The schema puts the number on the provenance of `HumanBusinessContext` (`evidence.py:276`), which is supplied by the caller. **Who computes it is unstated.** | **The owner.** | A one-line ruling: is capture fidelity (a) computed by `confidence` from a comparison of stored bytes against submitted bytes — deterministic, threshold-free, and arguably a ninth hard check — or (b) asserted by the Application Layer at intake? These have different owners and INV-10 forbids both. |
| **O3** *(param #13)* | **How confidences combine** | No rule anywhere produces a combined value from cleaner/reader/parser signals (`ENGINE_1_CONFIDENCE_PARAMETERS.md:61`). | **The owner.** | **A5 answers it: they do not combine.** What remains is a *documentation* action — `ENGINE_1_CONFIDENCE_PARAMETERS.md:65` still asserts that #1–#12 cannot be calibrated until #13 has a rule, which under A5 is no longer true (§8.1). That line needs revising, and revising a level-2 document is §M. |

### Discovered while writing this specification

| # | Finding | Owner | What unblocks it |
|---|---|---|---|
| **O4** | **The frozen schema cannot carry A8's raw signal.** `FieldConfidence` is `(field_name, confidence)` (`evidence.py:211-217`). **No structured slot for the instrument, and none for a page region.** Encoding either into the name is a convention, and `confidence.py:16-24` records what happened last time a convention was relied on. | **The owner.** | A ruling: does the raw signal (a) live **outside** the Document Evidence Object in a measurement log — cheap, no amendment, but then it is not evidence and does not travel; or (b) require a **schema amendment** adding instrument and region to `FieldConfidence`? Option (b) is §M and touches P2 work. |
| **O5** | **`docs/ENGINE_1_CONFIDENCE_PARAMETERS 2.md` is a stale duplicate** — 111 lines against 170. It **still carries the inverted row #15**, the exact error the CORRECTION section was written to fix (`ENGINE_1_CONFIDENCE_PARAMETERS.md:68-82`). Anyone signing off from the stale copy would set `k` **high** believing that is the conservative choice. Two files for one concept also breaks INV-10 (`SYSTEM_INVARIANTS.md:229`) and Law 19. **Not touched — this specification modifies no existing file.** | **The owner.** | Delete the stale copy, or record why two exist. |
| **O6** | **Three locked-or-live documents promise confidence gating that P7 forbids.** (a) `ADVERSARIAL_TESTING.md:41` attack 8 requires *"Low confidence → **Clarification**"* — that is a confidence gate, and `ADVERSARIAL_TESTING.md` is precedence level 2, the same level as `MEASUREMENT_FRAMEWORK.md:258`. (b) `EXECUTION_QUEUE.md:129-130` — *"Insufficient confidence produces `I don't know` or a Clarification Request"* (weaker: that file declares itself to have **no authority**, `EXECUTION_QUEUE.md:3`). (c) `TECHNOLOGY_STACK.md:30, 130` makes the Gemini Vision fallback conditional on *"when OCR confidence is below threshold"* and records the threshold as a blocker. | **The owner.** | A ruling on the **scope of "gates NOTHING"**: does it bind (i) only the `confidence` sub-engine's emitted Confidence Report, or (ii) every score in the system including a raw instrument score? Under (ii) the Gemini fallback cannot be built at all until separation passes. **A threshold-free route exists for attack 8 and should be considered first:** an illegible photograph produces regions the reader reports as **unread** (`SUB_ENGINE_RESPONSIBILITIES.md:58`), unread required fields become missing field information (`SUB_ENGINE_RESPONSIBILITIES.md:844`), and missing information is what reaches Clarification (`SUB_ENGINE_RESPONSIBILITIES.md:846-848`) — **a state, not a score.** |
| **O7** | **The set of eight is my enumeration from the locked documents, not a list the owner wrote down.** H1–H5 are verbatim from `EXECUTION_QUEUE.md:137-143`; H6–H8 are my selection. **Further threshold-free candidates were found and deliberately NOT folded in**: line-items-sum-to-total (`ADVERSARIAL_TESTING.md:43`, `GOLDEN_DATASET.md:33`); ledger exists in the chart of accounts, a pure lookup against Company Knowledge (`SYSTEM_INVARIANTS.md:271`, `SUB_ENGINE_RESPONSIBILITIES.md:544` *"every referenced master existing"*); recipient identity — invoice addressed to a different company (`GOLDEN_DATASET.md:60`); document-type postability for proforma/PO/quotation/challan (`GOLDEN_DATASET.md:55-58`). | **The owner.** | Confirm the eight are these eight, or name the ones I have wrong. **Adding a check is a gate-count increase, which `CLAUDE.md` permits; removing one is not mine to propose.** |
| **O8** | **Every calibration parameter is `UNSET` and must be fixed BEFORE the first run.** High-confidence region boundary · bin count and edges · minimum bin occupancy · MCE ceiling · whether MCE is region-restricted. Pre-registration means these are committed and hashed before results are seen (`MEASUREMENT_FRAMEWORK.md:11-27`); choosing any of them afterwards **invalidates the run**. | **The owner.** | Five numbers, supplied once, before the first calibration run — not before Stage 3 begins. |
| **O9** | **Calibration may not be reachable inside the MVP.** `GOLDEN_DATASET.md:166` puts confidence separation and calibration at **~100 golden documents**; the planned set is **16 golden** (`GOLDEN_DATASET.md:15-21`). If that stands, **confidence gates nothing for the entire MVP** — which is a coherent outcome and arguably the intended one, but it should be a decision rather than a discovery. `MEASUREMENT_FRAMEWORK.md:285` permits an **indicative** curve below N = 100, which supports no probability claim and therefore does not unblock gating. | **The owner.** | Either (a) accept that confidence is measurement-only through MVP and say so in the blueprint, or (b) fund the growth of the golden set toward ~100, which is accountant time — *"the scarcest resource"* (`MEASUREMENT_FRAMEWORK.md:360`). |
| **O10** | **`ACCOUNTING_DEFINITIONS.md:215` defines `Uncertainty` partly as *"any confidence below **the threshold** at which the system may act unattended."*** The singular *"the threshold"* implies a single, document-level cutoff — which A5 removes. Line 219 already self-corrects (*"until confidence passes the separation test … the second term is undefined and uncertainty is the doubt count alone"*), so nothing is currently broken. **But the wording will be implemented by whoever reads it next.** | **The owner.** | A wording revision under §M, re-expressing the second term per-field, or striking it. |

---
---

# Objections, for the owner

> **Nothing in this section changes the body.** The specification above implements the
> decision as given. These are three places where I think the decision, as written, will
> cost something — recorded because §C.26 forbids hiding a trade-off, and confined here
> because §E.8 forbids acting on one.

### Objection 1 — A5 is right, and it moves a hazard rather than removing it

The theorem is not in dispute and the conclusion follows. But the *reason* the scalar is
dangerous is that a single number invites meaningless downstream arithmetic
(`ENGINE_1_CONFIDENCE_PARAMETERS.md:120-125`). **Removing the field does not remove the
temptation — it relocates it.** With per-field scores available and no sanctioned way to
combine them, the first engineer who needs one number will write `min(...)` at the call
site, and it will be invisible because it is not a schema field anyone reviews.

**What I think is missing:** a conformance predicate that fails when more than one
`Confidence` value flows into a single arithmetic expression. `IDENTITY ≠ INTELLIGENCE`
was converted from a review-only rule into an executable one exactly this way
(`MEASUREMENT_FRAMEWORK.md:313`), and *"any rule of the form 'X must not influence Y'
converts the same way"* (`ADVERSARIAL_TESTING.md:58`). *"Confidences must not combine"* has
that shape. **Without it, A5 is enforced by memory, and this file is the memory.**

### Objection 2 — MCE has a failure mode of its own, and it is the opposite of ECE's

MCE is the right choice against within-bin cancellation. But **a maximum is the single most
sample-size-sensitive statistic available.** At the N this project will have for a long
time, the worst bin may hold two or three items, and its gap is then dominated by sampling
noise rather than by miscalibration. **The number will be loud, unstable between runs, and
will look like a regression when nothing changed** — which collides with
`MEASUREMENT_FRAMEWORK.md:234-241`, where a number below its floor **blocks merge.**

I am **not** proposing ECE, and not proposing a softer statistic. I am flagging that MCE
needs a **minimum bin occupancy** to be meaningful, that this is one of the `UNSET` values
in §5.3, and that if it is left unset the first calibration run will produce a headline
number nobody can act on. `MEASUREMENT_FRAMEWORK.md:174` already makes exactly this
argument about the held-out set — *"the final gate cannot be the noisiest number in the
system."*

### Objection 3 — A7 plus the current dataset size means confidence may never gate anything

This is O9 restated as an objection rather than a gap, because I think it deserves a
decision rather than an entry on a list.

A7 is correct and I would not weaken it. But its practical effect, combined with
`GOLDEN_DATASET.md:166` (~100 documents needed) against a planned 16, is that **the entire
confidence apparatus — 16 parameters, a sub-engine, a report component in the frozen
artifact — is built, carried through every artifact, and gates nothing for the foreseeable
life of the project.**

That may be exactly right: measurement mode is honest, and the eight hard checks are what
protect the books anyway (§6). But it is worth saying out loud that **the system's actual
safety comes from H1–H8, not from confidence**, and that if that stays true, the honest
question at some later phase is Law 54's own:

> *A number that predicts nothing but is still displayed is worse than no number*
> (`MEASUREMENT_FRAMEWORK.md:291`).

**Not a proposal to remove anything.** A flag that the flat-curve obligation at
`MEASUREMENT_FRAMEWORK.md:289-291` may eventually apply, and that the project should
decide in advance what it will do when it does.
