# Engine 1 — Confidence Parameters

**Status: AWAITING NUMERIC SIGN-OFF.** Every value below is `UNSET`. Amendment 3 (2026-08-05)
requires that no threshold, weight or cutoff in Engine 1 is invented, defaulted, or chosen
because it looks reasonable.

> **Missing required confidence configuration fails fast at startup.** There is no fallback
> value, no `or 0.8`, no "sensible default". A parameter that has not been set makes Engine 1
> refuse to start, loudly, naming the parameter — because a silently defaulted threshold is a
> number nobody decided that decides whether a document reaches a human.

---

## Why this file exists before the code

`CLAUDE.md` Law 52: *nothing is built until it can be measured.* Law 54: *define universally
undefined concepts before building.* `MEASUREMENT_FRAMEWORK.md:258` goes further and blocks the
obvious shortcut outright:

> Until it passes this test, confidence is an ordinal ranking, not a probability, and **it may
> gate NOTHING**.

So this table is not a form to fill in later. Until these have values **derived from measured
data**, Engine 1 runs in measurement mode: it records every signal, and gates nothing.

---

## The parameters

`P` = probability-like score in `0.0000–1.0000`, four decimal places, `Decimal` never `float`
(`src/accountant_dad/confidence.py`). `N` = a count. `ms` = milliseconds.

| # | Parameter | Purpose | Range · unit | ↑ increase means | ↓ decrease means |
|---|---|---|---|---|---|
| 1 | `ocr_region_accept` | Lowest per-region OCR score Engine 1 will treat as read at all | `P` | fewer regions accepted; more marked unreadable; **more true text discarded** | more regions accepted; **more garbled text enters as if it were real** |
| 2 | `ocr_vision_fallback` | Score below which the vision fallback is invoked instead of PaddleOCR | `P` | fallback fires more often; higher cost and latency per document | fallback rarely fires; poor scans pass through unimproved |
| 3 | `field_confidence_floor` | Lowest per-field score a field may carry and still be reported as read | `P` | more fields marked unreadable rather than wrong | more low-quality fields presented as read |
| 4 | `field_risky_mark` | Score at or below which a field is flagged **risky** in the Confidence Report | `P` | more fields flagged; more human attention consumed | fewer flagged; **more wrong fields reach a human unmarked** |
| 5 | `document_confidence_floor` | Lowest whole-document score Engine 1 will emit as a usable Evidence Object | `P` | more documents refused outright | more weak documents flow downstream |
| 6 | `human_review_trigger` | Document score at or below which the document is routed to a human | `P` | more human review; slower, costlier, safer | less review; **more chance a wrong entry reaches the books** |
| 7 | `retry_trigger` | Document score at or below which Engine 1 re-processes with different preprocessing | `P` | more retries; higher latency per document | fewer retries; more first-pass failures accepted |
| 8 | `retry_max_attempts` | Hard cap on retries for one document | `N` | more chances to recover a bad scan; unbounded latency risk | faster failure; recoverable documents given up on |
| 9 | `classification_accept` | Lowest document-type classification score accepted without review | `P` | more documents held for type confirmation | **more documents processed as the wrong type** |
| 10 | `table_structure_accept` | Lowest table-structure detection score accepted | `P` | more tables refused; fewer line items extracted | **more malformed tables treated as correct line items** |
| 11 | `table_cell_accept` | Lowest per-cell score accepted within an accepted table | `P` | more cells marked unreadable | more wrong amounts entering as read values |
| 12 | `capture_fidelity_floor` | Lowest capture-fidelity score for a typed Human Business Description | `P` | more human notes refused as poorly captured | more poorly captured notes treated as faithful |
| 13 | `document_score_rule` | **How per-field scores combine into one document score** | named rule: `min` · `product` · `weighted_mean` · `worst_k` | — | — |
| 14 | `document_score_weights` | Per-field weights, only if #13 is `weighted_mean` | map field → weight, sum `1.0000` | — | — |
| 15 | `worst_k` | How many worst fields the document score uses, only if #13 is `worst_k` | `N` | **closer to an average, hiding a single bad field** | **closer to the true worst case** (`k=1` IS the minimum) |
| 16 | `processing_budget_ms` | Wall-clock budget per document before Engine 1 reports a timeout | `ms` | slower documents allowed to finish | faster failure; complex documents abandoned |

---

## Three that are not merely unset — they are undefined

These carry no rule anywhere in the locked documents, so they cannot be *measured* into
existence either. They are Law 54 gaps and need a decision, not a number.

| # | Gap | What is missing | Evidence |
|---|---|---|---|
| 13 | **How confidences combine** | `ACCOUNTING_DEFINITIONS.md` defers to `MEASUREMENT_FRAMEWORK.md`; §10 there defines only the **gate** confidence must pass (separation ≥ 0.30), the calibration shape, and the six layers. **No rule produces a value** from cleaner/reader/parser signals. `confidence.py` fixes only the representation | `MEASUREMENT_FRAMEWORK.md` §10 |
| 4 | **What makes a field "risky"** | `ENGINE_1_INPUT_ENGINE_RULES.md:604-618` grants the action *"Highlight risky fields"* and the schema has `risky_fields`, but no document says at what score a field becomes risky. Deriving it from `confidence < X` is a confidence gate, which `MEASUREMENT_FRAMEWORK.md:258` forbids until calibration passes | `ENGINE_1:604-618` · `MEASUREMENT_FRAMEWORK.md:258` |
| 12 | **Who computes capture fidelity** | `ENGINE_1:624` and `SUB_ENGINE:90` require `confidence` to score it. `ENGINE_1:283` *illustrates* 100%, but an illustration is not a measurement, and the schema puts the number on `HumanBusinessContext.provenance.confidence` — supplied by the caller. Who computes it, and how, is unstated | `ENGINE_1:624` · `SUB_ENGINE:90` |

**Until #13 has a rule, #1–#12 cannot be calibrated**, because there is no document score to
calibrate against.

### CORRECTION, 2026-08-05 — row #15 was inverted, and dangerously

The two effect columns for `worst_k` were the wrong way round. As first written, the table
told the reader that **raising** `k` moved toward the true worst case. The opposite is true:

```
k = 1   IS the minimum          the true worst case
k = n   IS the arithmetic mean  full compensation
orness(k, n) = (k-1) / (2(n-1))    compensation RISES with k, linearly, from k=2
```

Anyone signing off from the original table would have set `k` **high** believing that was the
conservative choice — on the single parameter that decides whether one misread GSTIN is
visible or averaged away. Corrected above. Recorded rather than quietly edited, because a
sign-off document that silently changes meaning is worse than one that was wrong out loud.

### What the research settled without any data — six methods, four eliminated

The elimination is a **named theorem**, not a preference. Marichal & Mesiar,
*Meaningful aggregation functions mapping ordinal scales into an ordinal scale*
(Aequationes Math. 77(3), 2009), Corollary 5.7 — first proved by Orlov (1981):

> A symmetric, continuous, idempotent function on an ordinal scale is comparison meaningful
> **iff it is an order statistic function.**

Mean, product, Bayesian pooling and Dempster–Shafer combination are not order statistics.
On an ordinal scale they are not merely inaccurate — their **ordering flips** under a
transformation the data permits. Product fails even at the interval level: `φ(x) = x + 1`
reverses which of two documents ranks higher.

```
ELIMINATED on measurement scale     product · weighted_mean
ELIMINATED, no estimable likelihood  Bayesian      (the missing piece is p(s | wrong),
                                                   which needs observed wrong readings)
ELIMINATED, unmeasurable parameter   Dempster-Shafer  (output is ~24x more sensitive to
                                                   the invented ignorance mass than to
                                                   the measured evidence, under conflict)
SURVIVING                            min · worst_k
```

**One correction to the owner's framing, and it matters.** The ordinal argument does not
leave `min` alone — it leaves the whole order-statistic family, so `{min, worst_k}` both
survive. Choosing between them is a policy question about how much compensation to buy,
and it needs data.

**And a second, sharper finding: `min` is not free either.** The same paper, Corollary 6.2 —
on **independent** ordinal scales, the only comparison-meaningful function is a *projection*
onto one coordinate. OCR, table-structure and document-type are three different instruments.
Using `min` across them asserts **commensurability**: that an OCR 0.70 is the same amount of
doubt as a table-structure 0.70. That claim is strictly stronger than ordinality, is not
implied by it, and can only be established with labelled data.

### The consequence for the architecture

`min ≥ t` is *identically* `∀i : c_i ≥ t`. The document scalar adds nothing that per-field
floors do not already carry — and it creates a false affordance, inviting someone downstream
to average it, compare it across documents, or threshold it, all of which are meaningless on
this scale. This is the owner's A5 position, reached independently by the research.

---

## How a value gets set — the only route

```
1  ARCHITECTURE   every parameter above is named, externally configured, no default
2  MEASUREMENT    every document records: per-region OCR · per-field · classification ·
                  table · document score · whether extraction was ACTUALLY correct ·
                  which fields failed · processing time · source document type
3  CALIBRATION    once a validation set exists: histograms · precision vs threshold ·
                  recall vs threshold · false positive rate · false negative rate ·
                  calibration curves · confusion matrices · recommended operating points
4  FREEZE         a report per parameter: recommended value · justification · supporting
                  metrics · trade-offs · effect of raising it · effect of lowering it
                  → the user approves → only then is the value written
```

**Configuration is never modified automatically.** Step 4 produces a recommendation and stops.

A validation set requires ground truth, which is P1. So steps 3 and 4 are genuinely blocked on
P1 — but steps 1 and 2 are not, and they are where Engine 1 starts.

---

## What this forbids in code

- No numeric literal used as a threshold anywhere in `engines/input_engine/`
- No `= 0.8`, no `or 0.9`, no `getattr(cfg, "x", 0.5)`
- No comparison against a constant that is not loaded from configuration
- A missing parameter raises at startup naming the parameter — never at first use, never silently

Two tests enforce it: one proves configuration is respected, one proves no hardcoded threshold
exists. A mutation that inserts a default must turn them red.

---

## Sign-off

| | |
|---|---|
| Parameters awaiting a value | **16** |
| Of those, undefined rather than merely unset | **3** (#4, #12, #13) |
| Values supplied by the user | **0** |
| Status | ⬜ **BLOCKING calibration. Not blocking architecture or measurement.** |
