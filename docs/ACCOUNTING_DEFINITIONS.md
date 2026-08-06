# Accounting Definitions

> **Precedence level 2 — Locked Architecture Decisions.** Required by `CLAUDE.md` **Law 54**: *define universally undefined concepts before building.*
>
> Six load-bearing terms, each with its measurement. **A definition without a measurement is not a definition** (Law 52).
>
> ⚠️ **AWAITING SIGN-OFF.** No build may depend on a term the user has not agreed.

---

## Why this document exists

```
not measurable → not provable → not true → FALSE
```

Until these were defined, every architectural statement using them was unfalsifiable. *"Validation ensures the entry is correct"* asserted nothing, because **correct** had no meaning.

---

## 0. Qualified accountant

**Every definition below rests on this one.** Leaving it undefined would be a Law 54 violation inside the document that enforces Law 54.

```
qualified accountant =
  ≥ 3 years posting Indian GST-regime books
  has independently filed GSTR-1 and GSTR-3B
  currently practicing
```

**Recorded per labeler**: name or identifier · years · credential · whether currently practicing.

**Published alongside every ceiling and every accuracy claim.** A ceiling is a statement about *who was asked*, and hiding that makes the number uninterpretable.

---

## 1. Correct — of an entry

An entry is **correct** iff **all four fields match exactly**:

| Field | Match rule |
|---|---|
| **Ledger** | **Exact string match** against the golden ledger name. A near-miss is a wrong ledger. |
| **Amount** | **Exact to the paisa. Zero tolerance.** ₹0.01 off is wrong. |
| **Tax treatment** | Rate **and** type **and** ITC eligibility — all three |
| **Accounting period** | Exact |

**No partial credit. No rounding tolerance. No "materially correct."**

Three of four is a wrong entry. A wrong entry with three fields right is not 75% of a success — it is a misstatement that happens to contain three correct fields.

**If a tolerance is ever wanted, it is pre-registered before the run or it does not exist.**

### Measurement — one rule, everywhere

> **Blind independent production, diffed field by field.**

The accountant **produces their own entry from the original document**, never having seen the system's output. The two are then diffed by someone who does not know which is which.

**"Accepts unchanged" is not the test and is never used.** Approving a plausible entry is far easier than generating the right one — an acceptance test passes anything not obviously wrong, which is exactly the failure mode this system has.

### When two accountants disagree

**That document has no ground truth.**

1. It **leaves the correctness denominator**
2. It joins the **ask-or-not set** — measuring whether the system is *uncertain*, not whether it is right
3. **Both entries are kept.** Neither discarded, neither "resolved" by a third opinion.

**A document two qualified humans answer differently is a document the system should be uncertain about.** Matching that uncertainty is correct behaviour, not a failure.

**Owner:** Engine 5 judges it. Engine 3 produces the thing judged.

---

## 2. Understanding — of a business event

A Business Understanding Object is **correct** iff:

> **a qualified accountant reading only the Transaction Story — never the source document — independently produces the same accounting treatment they produced from the document itself.**

**Produces, not approves.** An approval test would pass any story that is merely not-obviously-wrong.

### Measurement

| Step | |
|---|---|
| 1 | Accountant produces treatment **from the document** — recorded |
| 2 | **Separate sitting, minimum one week later** |
| 3 | Accountant produces treatment **from the Transaction Story alone** |
| 4 | Compare |

The delay exists because an accountant who read the document an hour ago is not reading the story alone — they are reading it with the document in memory.

| Result | Meaning |
|---|---|
| Same treatment | Understanding was correct |
| Different treatment | The story **lost something load-bearing** |

This is the sharpest of the six because it tests the only property that matters: **does the story carry enough to decide.** A beautifully written story that omits payment terms fails.

### Scored every phase from P4

**This metric is measured, not deferred.** The second accountant session is budgeted into every phase from Phase 4 onward.

```
REQUIRED:  understanding correctness ≥ 80% of the frozen ceiling
```

**It is not redundant with the isolated/contributed gap.** The gap tells you Engine 2 *lost accuracy*. This tells you **what** it lost — a story can score badly for two entirely different reasons:

| Failure | What the gap shows | What this shows |
|---|---|---|
| Story is wrong | Engine 3 underperforms downstream | Accountant reaches a **different** treatment |
| Story is **incomplete** | Engine 3 underperforms downstream | Accountant **cannot reach any** treatment |

The gap cannot distinguish those, and the fix is different for each. **Wrong needs Engine 2's reasoning corrected; incomplete needs its output contract widened.**

It is also the only metric that tests the architecture's central bet — that a business story can carry an accounting decision without the document. **If that bet is wrong, the six-engine split is wrong**, and nothing else in the measurement suite would tell you.

**Owner:** Engine 2.

---

## 3. Safe — of an entry, to post

An entry is **safe** iff **all four** hold:

1. It is **correct** (§1), and
2. Every fact it rests on is **traceable** to a specific evidence reference, and
3. **No Critical validation finding** stands, and
4. The **accounting period is open** and posting is permitted.

### The asymmetry — the most useful fact in this document

Conditions **2, 3 and 4 are checkable by the conformance suite** — no ground truth, no accountant, no cost. **Only condition 1 needs a human.**

> **Safety is cheap to enforce. Correctness is expensive to prove.**

The system can therefore be made **provably safe long before it is provably correct** — and that is the right order, because non-goal B.8 is about safety, not accuracy.

**Owner:** Engine 5.

---

## 4. Risk

```
Risk = P(wrong) × magnitude(consequence if wrong)
```

Two owners, deliberately separated and never merged:

| Artifact | Owner | Measures |
|---|---|---|
| **Accounting Risk Analysis** | Engine 3 | Risk in the **reasoning** — how thin the basis |
| **Risk Assessment** | Engine 5 | Risk in **posting** — exposure, materiality, reversibility |

### Measurement

Magnitude is a **three-band ordinal**, never a currency figure:

| Band | Meaning |
|---|---|
| **Reversible in period** | Correctable before close; cost is time |
| **Reversible with effort** | Reversal entry, possibly a revised return |
| **Statutory or irreversible** | Filed, audited, or legally consequential |

A rupee figure would be a fabricated number (**Law 24**). Three bands can be assigned honestly.

### Risk is a gate, not a note

**The accountant assigns a band to every golden document. The system's band is compared to it, and the comparison gates.**

```
band agreement = documents where the system's band matches the accountant's

REQUIRED:  ≥ 80% band agreement
           AND zero cases where the system rated a
           statutory/irreversible item as reversible-in-period
```

The second condition has **no threshold**. Under-rating an irreversible consequence is the risk failure that matters — it is the one that lets something unrecoverable through a gate designed to catch it. Over-rating is tolerable and reported separately.

**A risk model nobody gates on is decoration.** The band exists to change what the system does; if it never blocks anything, it is not a risk model, it is a label.

At N = 16 the agreement figure is noisy and is **reported with its sample size** — but the statutory-under-rating condition is a count, not a rate, and one occurrence fails it regardless of N.

---

## 5. Doubt

A **doubt** is a **named missing fact whose absence would change the accounting treatment.**

### Measurement — falsifiable, and mandatory

Supply the fact. Re-run.

| Result | Verdict |
|---|---|
| The decision changes | **Real doubt** |
| The decision does not change | **Not a doubt.** Engine 3 raised a false one. |

**Every doubt raised against a golden document is checked this way, every run. False doubts are counted and reported.**

This is what stops *"unresolved doubts"* becoming a list of vague anxieties that make the system look careful while telling nobody anything.

**Owner:** Engine 3 produces doubt. Engine 4 judges which doubts block.

---

## 6. Uncertainty

The **set of open doubts**.

**Measurement.** `count(open doubts)`. Zero iff there are no open doubts.

> **Revised by Amendment 8.** A second term used to sit here — *"plus any confidence below
> **the threshold** at which the system may act unattended"*, measured as
> `count(sub-threshold confidences)`. It is **struck**, for two reasons and not one:
>
> 1. **No such threshold exists and none may be invented** (Law 52, Law 54). All sixteen
>    of Engine 1's parameters are `UNSET` by design.
> 2. **Even given one, Decision A7 forbids it.** Confidence gates NOTHING until the
>    separation test in [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10 passes,
>    so *"the threshold at which the system may act unattended"* names a mechanism this
>    architecture does not permit to exist yet.
>
> **Nothing measurable is lost.** The paragraph below already said the second term was
> undefined and that uncertainty was the doubt count alone — so the definition and its own
> next sentence disagreed, and the definition was the one that was wrong. Restoring a
> second term is an amendment and needs the owner.

**No second term may be added until confidence passes the separation test in [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10 — and adding one then is an amendment, not an automatic consequence.** A threshold on a number that does not separate right from wrong is a threshold on noise.

**Owner:** Engine 4 triages across the whole case.

---

## What is deliberately not here

**Confidence** is defined in [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md). It is a property of the measuring apparatus, not of accounting — and until its separation is measured it is not a probability at all.

---

# §M Amendment — Understanding Confidence Aggregation

**Approved by the owner, 2026-08-06.** Normative from this date.

## What changed

| | |
|---|---|
| **Doc / section** | `ACCOUNTING_DEFINITIONS.md` — new section · `ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §11 |
| **Old rule** | Only a **ceiling** existed: `Understanding Confidence ≤ Evidence Reliability` (`ENGINE_2:757`). Nothing stated how the six sub-engine confidences become the one Understanding Confidence the Business Understanding Object carries |
| **New rule** | The **weakest-link** rule below. Canonical, normative, and replaceable only under *Future Evolution* |
| **Why** | A ceiling bounds a value; it does not produce one. Six sub-engines each report a confidence and Story Builder must emit one number, so the rule was load-bearing and absent. Found while scoping Story Builder — the one Engine 2 sub-engine that needs no model — and it would otherwise have been discovered mid-implementation, where the pressure is to pick something plausible |
| **What failure forced it** | None yet, and that is the point. This closes a specification gap **before** code depends on it. An undefined term in a specification is a false statement waiting to be discovered (Law 54) |
| **Trade-off** | Recorded in full under *Trade-off* below |
| **Guarded by** | Regression tests and adversarial tests named under *Implementation* below |
| **Approved** | The owner, 2026-08-06 |

## The rule

```text
Understanding Confidence = min(
    transaction_confidence,
    party_confidence,
    item_confidence,
    payment_confidence,
    timeline_confidence,
    business_context_confidence,
    evidence_reliability
)
```

`evidence_reliability` is inside the `min`, not applied after it, so the existing
ceiling `Understanding Confidence ≤ Evidence Reliability` holds **by construction**
rather than by a second check that could be forgotten.

### Purpose

- Prevent manufacturing confidence.
- Ensure uncertainty propagates forward.
- Ensure one unresolved required dimension cannot be hidden by stronger dimensions.
- Guarantee the aggregate never exceeds either the weakest supported
  interpretation or the reliability of the evidence underneath it.

### Status — read this before quoting the number

**This is a provisional engineering assumption, not doctrine.** It is the current
best measurable rule in the absence of labelled production data. It is normative
until replaced under *Future Evolution*, and it is not claimed to be optimal —
only to be safe in the correct direction and to be stated.

## Operational definitions

### Major Conflict

A **major conflict** exists when credible evidence supports mutually exclusive
values for any required accounting field, or when the disagreement could change
any of:

- accounting treatment
- debit/credit decision
- transaction amount
- party identity
- transaction date
- tax treatment
- ledger selection
- posting outcome

A disagreement that cannot change any of those is a conflict, and is still
carried forward — it is simply not *major*, and does not on its own block posting.

### Weak Interpretation

A **weak interpretation** is one that:

- falls below its calibrated confidence threshold, **or**
- lacks sufficient supporting evidence, **or**
- depends primarily on unsupported inference, **or**
- contains unresolved competing interpretations.

### Missing Measurement

**A missing required sub-engine output is NOT zero confidence. It is UNMEASURED.**

`UNMEASURED` represents missing knowledge, not low confidence, and the two are
not interchangeable at any point in the system:

```text
0.0000       a measurement was taken and the answer was "no support"
UNMEASURED   no measurement was taken; nothing is known
```

`UNMEASURED` **must propagate forward.** It is never coerced to 0.0, never
defaulted, and never dropped so an aggregate can be computed. A `min()` over a
set containing `UNMEASURED` is `UNMEASURED`, not the smallest number present —
otherwise a missing dimension would silently read as a measured weak one.

This aligns with the four measurement states already carried by
`accountant_dad.confidence` (F-019): `MEASURED · NOT_MEASURED · NOT_APPLICABLE ·
FAILED`.

## Posting policy — separate from confidence calculation

**Confidence alone SHALL NEVER authorize posting.** Auto-post only when **all
five** hold:

1. Understanding Confidence ≥ the approved posting threshold.
2. Evidence Reliability ≥ the approved reliability threshold.
3. No Major Conflict exists.
4. Every required sub-engine result is measured and valid.
5. No mandatory-review rule has triggered.

The two thresholds named in 1 and 2 are **owner values and are UNSET** — no
number is chosen here (Law 10, Law 52). Until they are set, condition 1 and
condition 2 cannot be satisfied, and therefore **nothing auto-posts**. That is
the correct failure direction and is deliberate, not an oversight.

## Calibration

**The raw confidence value SHALL NOT be interpreted as a calibrated probability.**

Before production deployment:

- calibrate confidence against labelled accounting datasets
- validate by document category
- validate by individual field
- validate by transaction class
- measure calibration error
- measure false auto-post rate
- measure false human-review rate

**Aggregate confidence SHALL NEVER hide poor performance within an individual
critical field.** A high aggregate over a field that is reliably wrong is a worse
artifact than a low one, because it is trusted.

## Trade-off — stated, not implied

**The weakest-link rule is intentionally pessimistic.**

| | |
|---|---|
| **Failure mode** | Increases human review volume · lowers automation rate. One weak sub-engine drags an otherwise strong transaction down |
| **Benefit** | Minimises the probability of an incorrect accounting entry · preserves uncertainty · never manufactures confidence unsupported by evidence |
| **Why this direction** | This system posts into real books. A wrong entry is a financial misstatement somebody else answers for; an unnecessary human review costs minutes. **The costs are not symmetric, so the rule is not symmetric** |

## Falsifier — what would prove this rule wrong

Stated in advance, so the rule can be attacked rather than defended:

**On labelled data, weakest-link would be wrong if** a competing aggregation
(mean, weighted, learned) produced a **strictly lower false auto-post rate at an
equal or higher automation rate**. That is a single measurable comparison, and it
is the only evidence that counts.

**It would also be wrong if** the minimum is routinely set by a dimension that
does not affect the entry — e.g. `business_context` reading low on transactions
whose treatment it never changes. The symptom is a high human-review rate whose
cause concentrates in one non-critical dimension. Measurable as: the distribution
of *which* sub-engine supplied the minimum, per transaction class.

## Migration strategy, if it is disproved

The rule is used in exactly one place — the aggregation function — so replacing
it is a one-function change, and this is a design requirement, not an accident.

1. The aggregation lives behind a single named function. No caller computes a
   confidence itself, and no caller is allowed to.
2. A replacement ships **shadowed**: both rules computed, only the incumbent
   authoritative, the disagreement recorded per transaction.
3. Promotion requires the *Future Evolution* conditions below, all of them.
4. The old rule is retained and remains computable, so any historical artifact
   can be re-derived under the rule in force when it was produced.

## Future evolution

This rule may be replaced **only** when **all** hold:

- labelled production-quality accounting data exists
- competing aggregation models are benchmarked against it
- calibration results show a statistically significant improvement
- false auto-post risk does not increase
- the regression suite passes
- owner approval is recorded in a future §M amendment

**Until then, this rule remains normative.** Alternative aggregation models are
not implemented, not partially implemented, and not left behind a flag.

## Implementation — what carries this amendment

| Artefact | Change |
|---|---|
| `ACCOUNTING_DEFINITIONS.md` | this section — the single source of truth |
| Story Builder specification | the aggregation rule and the five posting conditions |
| confidence contracts | `UNMEASURED` propagation through `min` |
| `DATA_FLOW.md` | Understanding Confidence's derivation named on the Engine 2 → Engine 3 arrow |
| regression tests | the rule · the ceiling holding by construction · `UNMEASURED` propagation |
| adversarial tests | attempts to manufacture confidence, to hide a weak dimension, and to coerce `UNMEASURED` to `0.0` |
| engineering rationale | trade-off, falsifier and migration strategy, above |

**Use this amendment as the single source of truth.** Do not implement
alternative aggregation models until they are experimentally validated against
labelled accounting data.
