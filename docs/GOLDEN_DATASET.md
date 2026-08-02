# Golden Dataset

> **Precedence level 2 — Locked Architecture Decisions.** The measuring stick. Nothing in this system is provable without it.
>
> Methodology → [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) · definitions → [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md)

---

## What it is

**Twenty-five documents. Two independent labelers. A held-out set sealed by construction.**

The most valuable artifact the project will produce in its first months — and the only one that cannot be created by writing more architecture.

```
10  development     look freely
 6  held-out        SEALED — 37.5% of the golden set
 9  negative        must produce no entry
───
25  total
```

---

## Composition

### Development set — 10 documents

| # | Type | Tests |
|---|---|---|
| 1–4 | Purchase invoices, clean, digital | The baseline case |
| 5–7 | Purchase invoices, **photographed** | The actual product |
| 8 | **Internal contradiction** — line items don't sum to the total | A finding, not a guess |
| 9 | **Ambiguous tax treatment** | A Clarification Request |
| 10 | Vendor name matching **two possible ledgers** | A Clarification Request |

### Held-out set — 6 documents, SEALED

| # | Type |
|---|---|
| 11–12 | Purchase invoices, photographed, poor lighting |
| 13 | Unusual but legitimate tax treatment |
| 14 | Dated into a **closed period** |
| 15 | Reverse-charge transaction |
| 16 | Legitimate near-duplicate — same vendor, same amount, same month |

**Six, not three.** A 3-document gate moves 33% on a single failure; the final gate cannot be the noisiest number in the system. **≥ 30% of the golden set, always.**

### Negative controls — 9 documents

**Hard negatives — the real-world false positives:**

| # | Input | Why it is hard |
|---|---|---|
| N1 | **Proforma invoice** | Looks identical to a tax invoice. **The classic real error.** |
| N2 | **Purchase order** | Invoice-shaped; no liability |
| N3 | **Quotation** | Invoice-shaped; no transaction |
| N4 | **Delivery challan** | Real goods movement; not an invoice |
| N5 | Copy stamped **DUPLICATE** | Genuine, already posted |
| N6 | Invoice to a **different company** | Right document, wrong books |
| N7 | Invoice with **all amounts blanked** | Clarification, never a guess |
| N8 | Blank page | Floor check |
| N9 | Unrelated photograph | Floor check |

A suite of cats and menus proves almost nothing while feeling like a strong gate. **N1–N7 are what a real bookkeeper actually gets wrong.**

### Baseline scores — not new documents

The **dumb** and **strong** baselines (defined in `MEASUREMENT_FRAMEWORK.md` §4) scored against these same labels.

---

## Who chooses the documents

> **Not the person building the system.**

A builder selecting documents selects — unconsciously, sincerely — for cases the system handles. **The selector's brief is to break it.**

Where impossible on a solo project the constraint becomes structural: **all 25 documents are collected and frozen before any engine is built**, so nothing can be tuned to them. The selection is committed with a timestamp.

---

## Two independent labelers

**Both accountants label all 16 golden documents, blind to each other and blind to the system.**

Both meet the §0 definition in [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md). **Credentials recorded and published with the ceiling.**

```
inter-rater agreement  →  ceiling.json  →  FROZEN and hashed
```

**Re-measuring the ceiling with different labelers is an amendment**, never a quiet re-run. Otherwise a low ceiling could be manufactured to lower the bar.

### Intra-rater — the true noise floor

**2 documents are re-labeled by the same person ≥ 2 weeks later.**

A person disagreeing with themselves establishes the floor below which system errors are unattributable. **If intra-rater agreement is poor, inter-rater agreement was measuring human variance, not task difficulty.**

### Disputed documents

Where the two labelers disagree:

1. The document **leaves the correctness denominator**
2. It joins the **ask-or-not set** — measuring whether the system is uncertain
3. **Both entries are kept.** Neither discarded, neither resolved by a third opinion.

**A document two qualified humans answer differently is one the system should be uncertain about.**

---

## Labeling protocol

Written so a second person reproduces it exactly. **Reproducibility is what separates a dataset from a memory.**

1. **Blind to the system.** Never sees output before labeling. Not once, not any document.
2. **Blind to each other.** The two labelers do not confer, before or during.
3. **Stage 3 is produced from the ORIGINAL DOCUMENT**, never from their own stage-1 field labels. Otherwise a misread number propagates into golden truth *correlated with the golden fields* — and the system could match the golden entry with both being wrong.
4. **Four stages per document.** Fields · story · entry · question-if-any.
5. **Understanding is a separate sitting**, minimum one week later.
6. **Verbatim.** Their words as written, never tidied.
7. **A question is a label.** *"I'd have called the vendor about the GST rate"* becomes the golden Clarification Request.
8. **Uncertainty is recorded, not resolved.** If the accountant is unsure, that *is* the label.
9. **Risk band recorded** — reversible-in-period · reversible-with-effort · statutory.
10. **Timestamped and attributed.** Who, when, how long.

```
document_id
source_file            the original, unmodified
set                    development | held-out | negative
labeler                A | B
stage_1_fields         every field, re-keyed by hand
stage_2_story          business terms, no accounting vocabulary
stage_3_entry          ledger · amount (to the paisa) · tax treatment · period
                       PRODUCED FROM THE ORIGINAL DOCUMENT
stage_4_question       the question, or explicitly "none"
risk_band              the accountant's assessment
notes                  anything flagged
labeled_at · duration_minutes
```

---

## The immutability rule

> **A golden label is never changed to match system output.**

If the system disagrees and appears right:

1. **Record the disagreement.** Do not edit.
2. The accountant **re-labels independently**, blind, **without seeing the argument**
3. If they change it, record **both versions and the reason**
4. **The original label is never deleted**

**A dataset edited to make the system look good measures nothing.** This is the single easiest way to destroy the project's ability to know anything — and it will feel entirely reasonable at the time.

---

## Growth

| Size | Enables |
|---|---|
| **25** (16 golden + 9 negative) | **Kill a bad approach.** Enough to learn Engine 1 gets 40% and stop. |
| **~30 golden** | Stable per-engine numbers |
| **~100 golden** | **Confidence separation and calibration** |

**Start here.** Twenty-five is enough to kill; a hundred is what you need to tune. **Never pay for tuning before you have paid for killing.**

**Growth rule:** new documents join the **held-out** side until it holds ≥ 30%. A development set growing faster than held-out is a set you are increasingly tuned to.

---

## Storage

```
src/tests/golden/
  documents/
    development/          10 originals, never modified
    negative/              9 originals
  labels/
    development/          one JSON per document per labeler
    negative/
  heldout.sealed          separate encrypted commit — opening is a recorded action
  ceiling.json            inter-rater + intra-rater, computed once, hashed, FROZEN
  selection.json          what was chosen, by whom, when — frozen before any code
  PROTOCOL.md             this procedure
```

**Everything here must be readable by GitHub CI**, because a result that only exists locally is not a result (`MEASUREMENT_FRAMEWORK.md` §0a).

Version-controlled. A label is superseded, never overwritten — the same rule as every artifact in the system.
