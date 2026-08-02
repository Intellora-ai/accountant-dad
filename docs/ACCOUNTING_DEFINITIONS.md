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

### Deferred at MVP scale

**This metric is defined but not scored during the MVP.** It costs a full extra accountant session — the scarcest resource in the project — for a number the isolated/contributed gap already points to. It is scored **only if that gap names Engine 2 as the bottleneck.**

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

**The accountant's band is recorded per golden document and compared — but not gated on.** At N=16, gating on a three-band ordinal measures noise.

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

The **set of open doubts**, plus **any confidence below the threshold at which the system may act unattended.**

**Measurement.** `count(open doubts) + count(sub-threshold confidences)`. Zero iff both are zero.

**Until confidence passes the separation test in [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10, the second term is undefined and uncertainty is the doubt count alone.** A threshold on a number that does not separate right from wrong is a threshold on noise.

**Owner:** Engine 4 triages across the whole case.

---

## What is deliberately not here

**Confidence** is defined in [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md). It is a property of the measuring apparatus, not of accounting — and until its separation is measured it is not a probability at all.
