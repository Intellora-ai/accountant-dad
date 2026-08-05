# KNOWN_FAILURES.md

Every unresolved issue in this repository. **Nothing disappears from this file until
it is actually fixed** — not when it is worked around, not when it stops being
visible, not when a gate goes green for some other reason.

Append-only in spirit: an entry changes only its **Status** line, and a closed entry
keeps its history.

Last updated: **2026-08-05**

---

## F-001 · PyMuPDF is AGPL-3.0 and this is a commercial product

| | |
|---|---|
| **Severity** | HIGH — legal, not technical |
| **Status** | ⬜ OPEN · needs an owner decision |
| **Found** | 2026-08-05, landing Engine 1's `reader` |

**Description.** `pymupdf==1.28.0` reports its licence as *"Dual Licensed - GNU AFFERO
GPL 3.0 or Artifex Commercial License"* — read from installed metadata, not recalled.

**Root cause.** `docs/TECHNOLOGY_STACK.md:28` locks PyMuPDF as the PDF text-layer tool.
The lock was made on capability grounds; the licence question was never asked.

**Impact.** AGPL-3.0 §13 obliges anyone who lets users interact with the software **over
a network** to offer those users the complete corresponding source. A hosted accounting
platform is exactly that shape. This is not a theoretical exposure.

**Workaround.** None. The dependency is pinned and in use.

**Permanent fix — two lawful routes, both the owner's to choose.** Buy the Artifex
commercial licence, or write a §M amendment moving the locked stack to a permissively
licensed PDF reader. **Not an engineer's call:** a locked component is not swapped on
judgement, and `CLAUDE.md` §E.8 forbids removing what the owner specified.

---

## F-002 · Two OpenCV distributions in one environment

| | |
|---|---|
| **Severity** | MEDIUM — reproducibility |
| **Status** | ⬜ OPEN · latent, not currently breaking |
| **Found** | 2026-08-05, installing PaddleOCR |

**Description.**

```
opencv-python          5.0.0.93   pinned; what `cleaner` was measured on
opencv-contrib-python  4.10.0.84  pulled in transitively by paddlex
```

Both provide `cv2`. Which one `import cv2` resolves to is decided by installation
order, not by anything in `requirements-engine1.txt`.

**Root cause.** `paddleocr` → `paddlex` → `opencv-contrib-python`, unpinned.

**Impact.** `cleaner`'s deskew residual of **0.0017 at 32°** was measured against
5.0.0.93. A silent resolution to 4.10 would move that number with no code change —
and the test asserting the bound would then be measuring a different library than the
one the bound was derived from.

**Measured, not assumed.** With both present the full unit suite is green: **2068
passed, 14 skipped, 0 failed** (local, 2026-08-05). So this is latent.

**Permanent fix.** Not yet chosen. Pinning `opencv-contrib-python` to a version nobody
has measured would be inventing a number (Law 24). The honest options are: measure
`cleaner` against both and pin the one that holds the bound, or isolate the OCR
dependency so the two never share an environment.

---

## F-003 · `docs/ENGINE_1_CONFIDENCE_PARAMETERS 2.md` carries a dangerous inverted row

| | |
|---|---|
| **Severity** | HIGH — would cause a wrong sign-off |
| **Status** | ⬜ OPEN · deletion authorised, agent killed before completing it |
| **Found** | 2026-08-05, writing the confidence specification |

**Description.** A macOS Finder duplicate (`" 2"` suffix, mode 600 against the real
file's 644), **tracked in git**. Its line 49 still reads:

```
| 15 | worst_k | ... | ↑ closer to the true worst case | ↓ closer to an average |
```

That is backwards. **`k = 1` IS the minimum** — the true worst case. **`k = n` IS the
arithmetic mean.** `orness(k, n) = (k−1) / (2(n−1))`, so compensation *rises* with k.

**Impact.** Anyone signing off from this copy sets `worst_k` **high** believing that is
the conservative choice, on the one parameter deciding whether a single misread GSTIN
stays visible or is averaged away. The canonical file was corrected; this one was not.

**Permanent fix.** `git rm "docs/ENGINE_1_CONFIDENCE_PARAMETERS 2.md"` after proving
(a) nothing references it and (b) it holds no content the canonical file lacks. The
agent doing this was killed at step (a).

---

## F-004 · Three locked documents specify confidence gating the architecture forbids

| | |
|---|---|
| **Severity** | HIGH — a precedence conflict, not a typo |
| **Status** | ⬜ OPEN · needs Amendment 4 |
| **Found** | 2026-08-05, writing the confidence specification |

**Description.** The owner's decision A7 is binding: **confidence gates NOTHING until
calibration is proven.** `docs/MEASUREMENT_FRAMEWORK.md` §10 states it outright. These
three specify gating anyway:

```
docs/ADVERSARIAL_TESTING.md:41       attack 8, "Low confidence → Clarification"
docs/EXECUTION_QUEUE.md:129-130
docs/TECHNOLOGY_STACK.md:30,130      the Gemini vision fallback trigger
```

**Root cause.** They were written before the decision existed. `ADVERSARIAL_TESTING.md`
sits at the **same precedence level** as the rule forbidding it, so precedence alone
does not settle it.

**Impact.** Whoever implements one of these next will build a threshold, believing a
locked document told them to.

**Permanent fix.** Amendment 4 under §M — eight required items including the owner's
approval and date. **The purpose of each document survives without a threshold**:
attack 8's intent is reachable as `unread region → missing information → Clarification`,
with no number anywhere. Only the stated *mechanism* is wrong.

---

## F-005 · The frozen artifact cannot carry the raw confidence signal

| | |
|---|---|
| **Severity** | MEDIUM |
| **Status** | ⬜ OPEN · a resolution is chosen, not yet built |
| **Found** | 2026-08-05 |

**Description.** The owner's A8 requires the raw signal preserved per field, per region,
**per instrument**, with its origin. `FieldConfidence` in
`src/accountant_dad/artifacts/evidence.py` is `(field_name, confidence)` — no slot for
instrument, no slot for region.

**Chosen resolution — A8 says preserve the raw signal, NOT preserve it inside the
artifact.** The measurement log is the right home: append-only, line-delimited, and
what calibration reads. Amending a frozen contract to solve a problem a new file
already solves is the worse fix.

**Permanent fix.** `measurement.py` must carry `instrument` and `region` per signal.
An agent is building exactly that. Until it lands, the raw signal has no home.

---

## F-006 · Calibration may need ~6× the golden documents that are planned

| | |
|---|---|
| **Severity** | MEDIUM — scope, and it is the owner's decision |
| **Status** | ⬜ OPEN · the ~100 figure may itself be stale |
| **Found** | 2026-08-05 |

**Description.** `docs/GOLDEN_DATASET.md:166` puts calibration at roughly **100** golden
documents. The planned set is **16**. Taken at face value, confidence gates nothing for
the entire MVP.

**Why it may be stale.** That figure was written when a **document-level confidence
scalar** existed. Decision A5 removed it. The unit of observation is now per-field and
per-instrument, and 16 documents carry far more than 16 observations.

**The counter-argument, which is the honest one.** Field observations inside one
document are **not independent** — same scan, same lighting, same instrument, same
operator. The design effect could be large enough that 16 documents remain inadequate
regardless of field count. And **MCE is a maximum**, the most sample-size-sensitive
statistic there is.

**Permanent fix.** Re-derive the number before spending 6× the labelling effort. That
is a measurement, not a decision. The agent doing it was killed mid-run.

---

## F-007 · 220 mutants are excluded from the score's denominator

| | |
|---|---|
| **Severity** | LOW now, rising |
| **Status** | ⬜ OPEN · flagged, deliberately not changed |
| **Found** | 2026-08-05, first completed mutation run |

**Description.** `.github/workflows/testing.yml:300-311` computes
`score = killed / (killed + survived)` and reports everything else as `NOT SCOREABLE`.
The first completed run:

```
killed 1364 · survived 9 · timeout 220 · score 99.3% (floor 93%)
```

The 220 timeouts are outside the denominator. This is deliberate and documented in the
step's own comment.

**Impact.** A growing timeout population silently shrinks what the 93% floor is measured
over. At 1593 mutants the timeouts were 77; at the full run they are 220.

**Permanent fix.** Not proposed. Changing how a gate scores is a `.github` change
requiring the owner's approval for that specific change, and `CLAUDE.md` standing rule 9
forbids inventing a gate rule. **Flagged only.**

---

## F-008 · 17 of 23 CI checks still bind nothing

| | |
|---|---|
| **Severity** | HIGH — structural |
| **Status** | ⬜ OPEN · by design, until each gate can pass |
| **Found** | pre-existing; recorded here 2026-08-05 |

**Description.** Only six checks are on the required list: `build · typecheck · lint ·
unit tests · coverage · dependency scan`. `mutation` now passes but **is not required**.
`merge gate` — the one job that polls every other gate — binds nothing.

**Impact.** A pull request with the required six green and fourteen others red still
merges. That means merging on *"it compiles and imports resolve."*

**Permanent fix.** The lifecycle in `CLAUDE.md` §P: implement → prove it passes on
correct code → prove it FAILS on deliberately broken code → merge → add **only that
gate** to the required list → lock. `merge gate` goes required **last**, when it can
actually pass. **`mutation` is now the next candidate** — it has passed on correct code;
it still needs the deliberately-broken-code proof before promotion.

---

## Closed

*(none yet — an entry moves here only when the permanent fix has landed and CI proves it)*
