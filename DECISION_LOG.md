# DECISION_LOG.md

Every architectural decision, with what it cost. **Append only. History is never
overwritten** — a decision that turns out wrong gets a new entry that supersedes it,
and the original stays.

A decision belongs here when it is hard to reverse, when it closes off options, or
when a future engineer would otherwise have to re-derive the reasoning.

---

## D-001 · The mutation gate's cap is a measurement value, not a permanent one

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `.github/workflows/testing.yml:213` |

**Context.** The `mutation` job had never finished. It read 65.7%, then 99.0%, and
both numbers were beside the point — it was cancelled by `timeout-minutes: 10` at
997 of 1593 mutants.

**Alternatives.**
1. Cut the 77 timeout-mutants. **Falsified by measurement**: a timeout costs 2.234s
   and a non-timeout 2.326s in the same band. Free timeouts still leave 10.6 min.
2. Cache between runs. **Impossible in mutmut 3.3.1** — `__main__.py:268` overwrites
   `exit_code_by_key` with all-`None` before anything reads it. A restored cache saves
   23.3s of 593s.
3. Parallelise. `--max-children` already defaults to `cpu_count`.
4. Speed the slow tests. The per-mutant timeout has a hard **15.00s floor** from a `+1`
   term, so total achievable movement across all 1593 mutants is **0.5 seconds**.
5. Raise the clock.

**Decision.** Raise the clock to **100 minutes**. The number came from the owner
against a measured bracket: 10.8 min provable floor, 24.1 mid, 32.7 upper.

**Reasoning.** The cost is asymmetric. A cancelled run yields **zero information** and
must be re-run; an over-generous cap costs only the difference in minutes, and only
when something actually hangs. Three CI runs had already been burned learning nothing.

**Trade-off.** *Gained:* the gate can finish, so the real runtime becomes knowable.
*Lost:* a PR can now wait up to an hour on this gate.

**Impact.** The run finished in **24m14s** at **99.3%**. Every projection above is now
replaceable by a fact, and the cap can be set from evidence rather than arithmetic.
That is the point — Law 6, never optimize before measuring.

---

## D-002 · Confidence has no document-level scalar

| | |
|---|---|
| **Date** | 2026-08-05 (owner's decision A5; recorded here) |
| **Files** | `docs/CONFIDENCE_SPECIFICATION.md` §4 |

**Context.** Six aggregation methods were on the table for combining per-field
confidence into one document number.

**Alternatives, and how four were eliminated *without any labelled data*.** Marichal &
Mesiar, *Meaningful aggregation functions mapping ordinal scales into an ordinal scale*,
Aequationes Math. 77(3) 2009, **Corollary 5.7** (first proved by Orlov, 1981): a
symmetric, continuous, idempotent function on an ordinal scale is comparison-meaningful
**iff it is an order statistic function.**

```
ELIMINATED  mean · product · Bayesian pooling · Dempster-Shafer
            Not order statistics. On an ordinal scale their ORDERING FLIPS under a
            transformation the data permits. Product fails even at interval level:
            φ(x) = x + 1 reverses which of two documents ranks higher.
SURVIVING   min · worst_k
```

**Corollary 6.2** goes further: across **independent** ordinal scales the only
comparison-meaningful function is a **projection**. OCR, table-structure and
document-type are three different instruments, so `min` across them asserts
**commensurability** — that an OCR 0.70 is the same quantity of doubt as a
table-structure 0.70. That claim is strictly stronger than ordinality and needs data.

**Decision.** **No document-level scalar at all.**

**Reasoning.** `min ≥ t` is *identically* `∀i : cᵢ ≥ t`. The scalar adds nothing the
per-field floors do not already carry, and it creates a false affordance — inviting
someone downstream to average it, compare it across documents, or threshold it, all of
which are meaningless on this scale.

**Trade-off.** *Gained:* no meaningless number can be built on. *Lost:* there is no
single number to show on a dashboard, and anyone expecting one will have to be told why.

**Impact.** `confidence_report` is a **recorder, not a gate**. Six of the sixteen
confidence parameters are dead on arrival because there is no document scalar to
threshold. Recorded as F-005: the frozen `FieldConfidence` has no slot for instrument
or region, so the raw signal lives in the measurement log instead.

---

## D-003 · The raw confidence signal lives in the measurement log, not the artifact

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `src/accountant_dad/engines/input_engine/measurement.py`, `artifacts/evidence.py` |

**Context.** Decision A8 requires the raw signal preserved per field, per region, **per
instrument**, with its origin. `FieldConfidence` is `(field_name, confidence)` — no slot
for either.

**Alternatives.** (1) Amend the frozen artifact schema to add the fields. (2) Put the
raw signal in the append-only measurement log.

**Decision.** The measurement log.

**Reasoning.** **A8 says preserve the raw signal. It does not say preserve it inside the
artifact.** The log is append-only, line-delimited, and is what a calibration run reads.
Amending a frozen contract to solve a problem a new file already solves is the worse fix
— it spends a §M amendment and widens a schema every downstream engine depends on.

**Trade-off.** *Gained:* artifacts stay immutable and frozen; no amendment spent.
*Lost:* the raw signal is no longer co-located with the artifact it describes, so
anything wanting both must join them by document id.

**Impact.** `measurement.py` must carry `instrument` and `region` per signal or the
raw signal has **no home anywhere**. That makes it load-bearing, not optional.

---

## D-004 · PaddleOCR is resolved at first use, not at import

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `src/accountant_dad/engines/input_engine/reader.py` |

**Context.** `reader.py` reaches PaddleOCR through `importlib` because PaddleOCR ships
no `py.typed`, so a plain `import paddleocr` is itself a `mypy --strict` error under a
zero-new-suppressions gate. The lookup was written at **module scope**.

**Decision.** Move the `importlib.import_module("paddleocr")` call inside the
already-`@cache`d `_recogniser()` builder.

**Reasoning.** At module scope, importing the Input Engine **at all** required a ~500 MB
ML package to be present — so every gate that merely imports the package died at
collection. The `importlib` route was chosen precisely to avoid a hard dependency, and
resolving at import time defeated it. Inside the cached builder it costs nothing (it
already ran exactly once) and restores the intended property: the dependency is needed
to **run OCR**, never to **import the module that offers it**.

**Trade-off.** *Gained:* the package imports without the ML stack; every non-OCR gate
survives. *Lost:* a missing PaddleOCR now surfaces at first OCR call rather than at
startup — later, and therefore in a worse place. Accepted because the alternative made
six gates unrunnable.

**Impact.** The literal string stays in the file, so the AST test pinning this module's
dynamic imports still sees it — moving the call does not hide a technology swap from
the stack check.

---

## D-005 · PyMuPDF's licence is recorded, not resolved

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `requirements-engine1.txt`, `KNOWN_FAILURES.md` F-001 |

**Context.** `pymupdf==1.28.0` reports *"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex
Commercial License"* — read from installed metadata, not recalled. AGPL §13 obliges
anyone letting users interact over a network to offer them the complete source. A hosted
accounting platform is exactly that shape.

**Alternatives.** (1) Swap to a permissively licensed PDF reader. (2) Buy the Artifex
commercial licence. (3) Pin it, record the exposure, and escalate.

**Decision.** (3).

**Reasoning.** `docs/TECHNOLOGY_STACK.md:28` **locks** PyMuPDF. A locked component is
not swapped on an engineer's judgement, and `CLAUDE.md` §E.8 forbids removing what the
owner specified. A licence is also not the kind of evidence the stack's replacement
clause contemplates — that clause wants a measured superiority on accuracy, latency,
determinism, maintainability or reliability. This is a legal constraint, not a
measurement, so it goes to the owner intact.

**Trade-off.** *Gained:* the lock holds and the exposure is visible in three places
(the requirements file, `KNOWN_FAILURES.md`, and the commit message).
*Lost:* the exposure is live in the meantime.

**Impact.** Blocks nothing technically. Blocks shipping to a paying customer until
route (1) or (2) is chosen.

---

## D-006 · Killed agents' work is recovered and finished, never restarted

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | process, not code |

**Context.** A session limit killed roughly 30 concurrent agents mid-run. Each had been
given an isolated git worktree.

**Alternatives.** (1) Re-dispatch every task from scratch. (2) Recover each worktree,
audit what survived, and finish from that checkpoint.

**Decision.** (2), always.

**Reasoning.** The worktrees persisted. 3,721 lines of source and 1,906 of tests
survived — restarting would have discarded all of it and re-derived the same three
defects. **State on disk is state**, and a summary is not a substitute for it.

**Trade-off.** *Gained:* nothing was lost, and inherited code got an audit pass it
would not otherwise have had — which is how the `DocumentId` import error and the
module-scope PaddleOCR import were caught. *Lost:* recovery is slower per task than
a clean restart would appear to be, and inherited code must be treated as untrusted.

**Impact.** Made permanent: `isolation: "worktree"` for every code-writing agent, and
recovery-before-restart as the standing response to any interruption.
