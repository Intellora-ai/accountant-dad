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
| **Severity** | HIGH — it was silently active, not latent |
| **Status** | ✅ **RESOLVED 2026-08-05** by separating the manifests |
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

**CORRECTION — I first recorded this as "latent, not currently breaking". That was
wrong, and the error is instructive.** The evidence I cited was a green suite:
2068 passed, 14 skipped, 0 failed. What I had not checked was which libraries were
actually loaded. When I looked:

```
requirements-engine1.txt pins    numpy 2.5.1   ·  opencv-python 5.0.0.93
import numpy, cv2 reported       numpy 2.3.5   ·  cv2 4.10.0
```

**Both pins were already being overridden, silently, with no error and no warning.**
The suite I called evidence had run against neither pinned library. A green test on
the wrong dependency is worse than a red one — it is a false green, which is the exact
failure `CLAUDE.md` §J exists to prevent.

pip also downgraded numpy without complaint locally, while CI — resolving clean —
refused outright with `ResolutionImpossible`. Two environments, two behaviours, and
only the CI one told the truth. Law 44, demonstrated.

**Permanent fix — LANDED.** The OCR stack moved to its own manifest,
`requirements-engine1-ocr.txt`, which is exactly what `docs/TECHNOLOGY_STACK.md`
prescribes: engine dependencies land *"per engine, at its phase, in a separate
manifest."*

Rejected alternative: loosen `numpy==2.5.1` to satisfy paddlex. That would have set a
version nobody measured (Law 24) and left `cleaner`'s deskew assertion — 0.0017 at 32°,
derived on opencv-python 5.0.0.93 — guarding a library the number was never taken
against. It would still pass, and it would no longer mean anything.

**Verified after the fix:** `numpy 2.5.1`, `cv2 5.0.0`, and 2057 passed / 25 skipped /
0 failed locally. The environment now matches the manifest it claims to.

---

## F-003 · `docs/ENGINE_1_CONFIDENCE_PARAMETERS 2.md` carries a dangerous inverted row

| | |
|---|---|
| **Severity** | HIGH — would cause a wrong sign-off |
| **Status** | ✅ **CLOSED 2026-08-05** · deleted after both safety checks passed |
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

**Permanent fix — LANDED.** `git rm "docs/ENGINE_1_CONFIDENCE_PARAMETERS 2.md"`, after
both safety checks passed:

- **(a) Nothing depends on it.** Three files mention the name — `CONFIDENCE_SPECIFICATION.md`,
  `TODO.md` and this file — and all three cite it *as the defect*, never as a source.
- **(b) Its only unique content was the bug.** `diff` against the canonical file returned
  exactly **one** line present in the duplicate and absent from the canonical:

  ```
  | 15 | worst_k | ... | closer to the true worst case | closer to an average, hiding a single bad field |
  ```

  That is the inverted row itself. Deleting the file therefore lost nothing but the error.

Canonical `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md:49` verified correct after the
deletion: **↑ raises k toward an average, hiding a single bad field; ↓ lowers k toward
the true worst case, and `k=1` IS the minimum.**

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
| **Status** | ✅ **CLOSED 2026-08-05** — `NamedSignal` now carries both fields |
| **Found** | 2026-08-05 |

**Description.** The owner's A8 requires the raw signal preserved per field, per region,
**per instrument**, with its origin. `FieldConfidence` in
`src/accountant_dad/artifacts/evidence.py` is `(field_name, confidence)` — no slot for
instrument, no slot for region.

**Chosen resolution — A8 says preserve the raw signal, NOT preserve it inside the
artifact.** The measurement log is the right home: append-only, line-delimited, and
what calibration reads. Amending a frozen contract to solve a problem a new file
already solves is the worse fix.

**Permanent fix — LANDED** (`47c4063`). `NamedSignal` in
`src/accountant_dad/engines/input_engine/measurement.py` now carries:

```python
name: str
value: float | None
instrument: str          # required, non-blank, validated in __post_init__
region: str | None = None
```

Both round-trip through the line-delimited JSON. `region` is **omitted from the JSON
entirely** when absent rather than written as `null` — absent and null-valued are
different claims, and the distinction is the point of the whole record.

A8's requirement — *preserve the raw signal per field, per region, per instrument,
with its origin* — is now satisfiable. Before this, it was satisfiable nowhere in the
system: `FieldConfidence` has no slot for either field and `NamedSignal` had neither.

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

## F-017 · ROOT CAUSE of F-009, F-011 and F-012 — `cleaner` collapses every document to a raster

| | |
|---|---|
| **Severity** | HIGH — architecture. Three recorded failures are symptoms of this one |
| **Status** | 🔒 **BLOCKED · needs an owner decision (§M)** |
| **Found** | 2026-08-05, tracing F-011 to its root instead of patching it |

**The single defect.** `cleaner` was implemented as an **image** cleaner. The
architecture requires a **document** cleaner.

```
Image = npt.NDArray[np.uint8]              cleaner.py:100
def decode(data: bytes) -> Image           cleaner.py:618
class CleanedDocument: cleaned: Image      cleaner.py:263
```

`SUB_ENGINE_RESPONSIBILITIES.md` §1.1 states the input plainly:

> The raw artifact exactly as received: photo, camera capture, image upload,
> **PDF**, scan, handwritten note, **Excel file**, email content, structured
> metadata, or other digital file

A PDF, an Excel file and an email can none of them be an `NDArray[uint8]`. The
phrase *"cleaned document representation"* was read as *"a cleaned raster"*, and
nothing in the codebase forced otherwise.

**The three symptoms, each derived:**

- **F-011** — `decode` cannot decode a PDF, because `cv2.imdecode` cannot rasterise
  one and the return type leaves nowhere else to go. Engine 1's primary input.
- **F-012** — `reader` and `parser` re-open the original rather than consuming
  `cleaner`'s output. **This is correct, not sloppy.** `read_pdf_text_layer` takes
  the original bytes and `parse` takes the original path; handing either a bitmap
  of a PDF **destroys the text layer**, which is the exact thing that makes a
  text-layer PDF readable without OCR. Consuming the cleaned output would be
  strictly worse, so both modules refuse to.
- **F-009** — a raster is the only representation **PaddleOCR** can take, so OCR is
  the only consumer `cleaner`'s output currently fits — and it is the one path CI
  cannot run.

**The measured consequence.** `cleaner`'s deskew residual — **0.0017 at 32°**, the
figure quoted throughout this project — describes work that reaches **no downstream
consumer on the text-layer path**, and only PaddleOCR on the OCR path, which CI never
runs. A real measurement of an effect nothing currently observes.

**Why this was invisible until integration.** `cleaner` has 61 tests and every one
feeds it an image, because that is what `decode` accepts. A test suite shaped by the
signature can never question the signature. Only wiring the chain asked the question
(`LESSONS.md` L-007).

**The fix, and why it is not an engineer's call.** Cleaning must be
**format-preserving**: a cleaned PDF is still a PDF, deskewed, with its text layer
intact. `CleanedDocument.cleaned` becomes a representation carrying its media type
rather than `NDArray[uint8]`. That changes a locked contract across `cleaner`,
`reader`, `parser` and `assembly` — four modules and their specifications (§M).

**Cheapest correct first step:** decide at the SPEC level what *"cleaned document
representation"* means for a non-image input. Everything else follows from that
answer, and guessing it stacks a fifth wrong assumption on four.

---

## F-016 · Mutation testing cannot run on macOS at all

| | |
|---|---|
| **Severity** | MEDIUM — a workflow constraint, not a product defect |
| **Status** | ⬜ OPEN · unfixable locally; CI is the only route |
| **Found** | 2026-08-05 (re-derived the expensive way; first noted earlier the same day) |

**Description.** `mutmut run` on this machine produces **zero usable data**. Measured on a
scratch copy scoped to Engine 1:

```
2133 / 2133 mutants     🎉 0 killed   🙁 0 survived   ⏰ 0 timeout
every single one: segfault
```

**Root cause.** mutmut calls `multiprocessing.set_start_method('fork')`. On macOS,
`fork()` without `exec()` in a process that has already initialised OpenCV, torch or
Accelerate leaves the child with broken thread state, and it dies with SIGSEGV before
running a single test. Engine 1 imports all three.

**Impact — and this is the part worth internalising.** Law 44 says *"a result exists only
if GitHub CI produced it."* For mutation that is not a policy preference, it is a hardware
fact: no amount of local iteration can produce a survivor list. **Every mutation
hypothesis costs a full CI run.**

At the current scale that is roughly **3+ hours per attempt**, which makes guessing
expensive and makes the first attempt worth getting right.

**Two dead ends already paid for**, recorded so nobody pays again:
1. Scoping `paths_to_mutate` to one directory makes mutmut copy *only* that directory, so
   every sibling import fails and the stats phase reports `failed to collect stats`.
2. Adding `"src"` to `also_copy` to fix (1) copies the **unmutated** source over the
   mutated tree, and mutmut refuses to start with `FAILED: Unable to force test failures`
   — correctly, because no test could ever see a mutant. The fix is to copy each sibling
   path individually and never the mutation target.

**Permanent fix.** None available locally. Options are a Linux container for local runs,
or accepting CI as the only source of mutation data.

---

## F-014 · The mutation gate no longer fits in 100 minutes

| | |
|---|---|
| **Severity** | HIGH — blocks the merge |
| **Status** | 🔒 **BLOCKED · needs a number from the owner** |
| **Found** | 2026-08-05, after Engine 1 landed |

**Description.** The `mutation` job was cancelled at the 100-minute cap on `ed5d504`.
It is not failing on score — it cannot finish.

**Two things changed at once, and they multiply.**

```
mutant population   1593 → 2933      +84%   the seven new Engine 1 modules
suite wall-clock     7 s  → 72 s     ~10×   parser's 14 Docling / Table-Transformer
                                             measurements now RUN (they used to skip,
                                             because docling was never pinned)
```

Every mutant re-runs the tests covering the function it mutated. For `parser.py`'s
mutants that now means loading real models.

**The measured history:**

| Commit | Mutants | Result |
|---|---|---|
| `d85861c` | 1593 | ✅ **24m14s · 99.3%** (floor 93) — killed 1364, survived 9 |
| `ed5d504` | 2933 | ❌ **cancelled at 100 min** |
| `27b44b3` | 2933 + 35 more tests | running; strictly slower than the run that already failed |

**Workarounds attempted and rejected — every one, before reporting this.**

1. **Cache the Table Transformer.** `_bands_for` calls `from_pretrained` **once per
   table** and never caches, unlike `reader._recogniser()` which caches for exactly this
   stated reason. Measured cost: **1.68 s per call, warm cache, forever.** Implemented,
   then **reverted** — making it type-safe under `mypy --strict` needs Protocols that
   erode the `float()`/`int()` conversions at the call site, and `disallow_any_explicit`
   rules out the easy route. Trading correctness in production code for CI minutes is a
   bad trade. **Recorded separately below as a real defect worth fixing on its own
   merits, not as a CI expedient.**
2. **Lazy imports.** Already correct — `parser.py` uses `importlib` + `TYPE_CHECKING`.
   Not the cause.
3. **Exclude `parser.py` from mutation**, or drop the Docling tests. **Refused.** Both
   make the gate pass by measuring *less*, which is Law 4 and §J.4 outright.
4. **Lower the floor.** Never.

**What is needed.** A larger `timeout-minutes` for the `mutation` job in
`.github/workflows/testing.yml`. **That is a number, and standing rule 10 forbids an
engineer setting a number the owner did not give.**

**Evidence for choosing one.** 1593 mutants took 24m14s. 2933 did not finish in 100. The
relationship is worse than linear because mutmut sorts ascending by estimated cost, so
the added Engine 1 mutants land in the expensive tail — the same effect measured earlier
at 3.45× the work in 60% as many mutants.

---

## F-015 · The Table Transformer is rebuilt once per table

| | |
|---|---|
| **Severity** | MEDIUM — real production cost, not just CI |
| **Status** | ⬜ OPEN · fix identified, blocked on typing |
| **Found** | 2026-08-05 |

**Description.** `parser.py:580-581` calls `AutoImageProcessor.from_pretrained` and
`TableTransformerForObjectDetection.from_pretrained` inside `_bands_for`, which runs
**once per table**. A three-table invoice constructs the model three times.

**Measured on this machine, weights already in the HuggingFace cache so no download is
involved:**

```
AutoImageProcessor.from_pretrained     3.06 s   first
TableTransformerForObjectDetection     0.78 s   first
both again, warm                       1.68 s   ← paid on EVERY call, forever
```

`model.eval()` is also re-asserted per call, though inference mode is a property of the
instance and does not change.

**This is not merely a CI problem.** In production every table in every document pays
1.68 s of pure setup. `reader._recogniser()` documents precisely this hazard for
PaddleOCR and caches with `@cache`; `parser.require_module` is `@functools.cache`d for
the same reason. This one call site was missed.

**Permanent fix.** `@functools.cache` on a `_table_structure_model()` helper. Attempted
and reverted: `transformers` is reached through `require_module` and typed `ModuleType`,
so today the objects are implicitly `Any` and the call site relies on that for
`float(score)`, `int(label)` and `model.config.id2label`. Annotating a cached function's
return re-types them, and `disallow_any_explicit` blocks the shortcut. The clean fix is
narrow Protocols in `reader.py`'s style — worth doing deliberately, not wedged in to
save CI minutes.

---

## F-011 · `cleaner.decode` cannot decode a PDF — Engine 1's own primary input

| | |
|---|---|
| **Severity** | HIGH |
| **Status** | ⬜ OPEN · worked around in `pipeline.py`, not fixed at source |
| **Found** | 2026-08-05, wiring the pipeline — invisible to every unit test |

**Description.** `cleaner.decode` calls `cv2.imdecode`, which returns `None` on real PDF
bytes, so decode raises `UndecodableArtifactError` **unconditionally for every PDF** —
even though PDF is named in `cleaner`'s own specification.

**Impact.** Taken literally, Engine 1 could never process a PDF. The MVP's primary input.

**Why no unit test caught it.** `cleaner`'s 57 tests feed it images, because that is what
`decode` accepts. Nothing had ever handed it the input the *spec* says it takes.

**Workaround, in `pipeline.py` only.** Render page one via PyMuPDF — already an approved,
already-imported Engine 1 tool — at the **caller's own `render_dpi`**, never a second
invented number. `cleaner.py` is untouched.

**Permanent fix.** Not chosen. Either `cleaner.decode` learns PDFs, or the spec is
revised to say `cleaner` takes rasterised pages and someone else rasterises. That is a
boundary question, so it is the owner's.

---

## F-012 · The pipeline is not a pipe — each stage re-opens the raw document

| | |
|---|---|
| **Severity** | HIGH — architecture, not code |
| **Status** | ⬜ OPEN |
| **Found** | 2026-08-05, wiring the pipeline |

**Description.** `docs/DATA_FLOW.md` draws `cleaner → reader → parser` as a chain. The
code is not one:

```
reader.read(document: bytes, ...)     opens the PDF itself
parser.parse(path: Path, ...)         opens the SAME document a third time, via Docling
```

**Neither consumes `cleaner`'s output.** `parser.py`'s own docstring already admits this
— *"a real departure … it must not stay that way."*

**Impact.** Cleaning does not affect what is read or parsed. A deskewed, denoised,
contrast-corrected page is produced and then **ignored** by both downstream stages.
Every measurement of `cleaner` — the 0.0017 residual included — currently describes work
that changes no output.

**Permanent fix.** Make `reader` and `parser` consume the previous stage's artifact.
That changes three locked module contracts and is an architecture change, not a patch.

---

## F-013 · Extraction content can never carry a per-field confidence

| | |
|---|---|
| **Severity** | HIGH |
| **Status** | ⬜ OPEN |
| **Found** | 2026-08-05, wiring the pipeline |

**Description.** Two independent gaps compose into one hole.

1. `confidence_report.RegionReading(text="TAX INVOICE", extraction_confidence=None)`
   **always raises** `MalformedSignalError`. Its invariant assumes text-without-a-score
   means "unread" — true for OCR, **false for a PDF text layer**, whose entire design is
   real text with an honestly absent score.
2. Deeper, and measured: even a validly-constructed *scored* `RegionReading` never
   becomes a `confidence_scores` entry. `record_confidence`'s `_field_confidence_scores`
   reads only `parsed_fields` — **never `reader_regions`.**

Separately, `assembly.ParserOutput.detected_fields` and `.detected_tables` each need a
`Provenance` carrying a `Confidence`, and **neither `reader` nor `parser` produces one
attached to a name**: `parser.Region`/`Table`/`Cell` carry no confidence at all (by
design — only `confidence` may produce one), and `reader.TextRegion` carries a
confidence but no name. Building either would mean inventing the missing half.

**Combined consequence, stated plainly.** For a PDF-text-layer document, the
`confidence_scores` tuple can carry **no document-content entry at all** — only the
optional Human Business Context's capture-fidelity score can appear there.

Extraction content is still fully traceable via `extracted_text` and
`document_structure`. It is the **per-field confidence** that is structurally
unavailable — which is the number Engine 5 would eventually need.

**Permanent fix.** Not chosen. `RegionReading`'s invariant needs a third state, and
something must name a field before a confidence can be attached to it. Both are contract
changes across `reader`, `parser`, `confidence_report` and `assembly`.

---

## F-010 · Two same-day documents disagree on whether classification is authorised

| | |
|---|---|
| **Severity** | MEDIUM — a precedence question, resolved by precedence but not reconciled |
| **Status** | ⬜ OPEN · built on the permitted side; the documents still contradict |
| **Found** | 2026-08-05, building `classification` |

**Description.** Two documents written on the same day say opposite things.

```
CLAUDE.md §P Amendment 3     names "document classification" among the
                             capabilities EXPLICITLY AUTHORISED for Engine 1
docs/ENGINE_1_ARCHITECTURE.md §G9.5
                             says document-type detection "is not authorised …
                             out of scope until the owner rules"
```

**Root cause.** Amendment 3 is owner-approved and sits in the constitution.
`ENGINE_1_ARCHITECTURE.md` was drafted by an agent the same day, is not owner-approved,
and is not frozen. It also arrived **after** code had started, which is the wrong order
(§F) and was recorded as such rather than backdated.

**Resolution by precedence — CLAUDE.md wins.** `CLAUDE.md` is the constitution and
Amendment 3 carries the owner's approval and date. G9.5 does not.

**Built on the permitted side of G9.5's own line anyway.** G9.5 draws its line between
an *observation* ("invoice-like layout") and a *conclusion* ("this is a proforma
invoice"). `classification.py` produces evidence-carrying observations only: every
`TypeCandidate` must carry at least one `MatchedCue` naming the literal cue, the
instrument that saw it and where it was; `UNKNOWN` and `AMBIGUOUS` are first-class
answers; on ambiguity **every** candidate's evidence survives and no winner is picked.
It makes no accept decision and produces no score at all.

**Why it needs no threshold.** The three-way outcome is decided by Python structural
pattern matching on tuple **shape** — `case ()` / `case (only,)` / `case multiple:` —
never a numeric comparison. So parameter #9 `classification_accept` stays UNSET and
unused, and there is no cutoff to invent. A test walks the module's AST and fails if
any numeric comparison appears anywhere; a red-team mutation inserting a
behaviour-preserving `if len(candidates) == 0:` was caught by that test **alone**.

**Permanent fix — and a correction to what this entry used to say.** This entry
previously ended *"the owner's call, not an engineer's,"* which contradicted its own
Resolution-by-precedence paragraph four lines above. The precedence paragraph is right
and the closing line was wrong, so the closing line is replaced here.

`ENGINE_1_ARCHITECTURE.md` self-declares **"Status: DRAFT — NOT FROZEN"** (`:8`) and
**"Where this document contradicts any of them, this document is wrong"** (`:5`). It
does not appear at any level of the precedence ladder in `SYSTEM_INVARIANTS.md:11-18` —
that ladder lists `ENGINE_1..6_*_RULES.md` at level 3, and this is a different file.
§M binds **frozen** documents; a draft is revised, not amended. So there is nothing here
only the owner can decide.

G9.5 also borrows no authority from anywhere else. Its own document's rule (`:1064`)
is that §G9 binds only where it derives from a locked document, and its three citations
are a level-5 README "Future Note" (which supports classification), an UNSET parameter
(which forbids a *threshold*, not a capability), and
`COMMUNICATION_RULES_INPUT_ENGINE.md:71` (a boundary *test*, not a scope release).
`ENGINE_1_INPUT_ENGINE_RULES.md` — which IS on the ladder — has zero matches for
`document type` or `classif`, and none of its fifteen absolute `MUST NEVER` items
mentions it.

The repository's own guard already behaves as if this were settled:
`tests/unit/test_package.py:102` lists `engines/input_engine/classification` in
`ENGINE_1_AUTHORIZED`, commented `# document classification (Amendment 3)`. If G9.5
governed, that line would be a live freeze violation, and nothing flags it.

**Status: resolved by precedence.** G9.5 is a draft clause that is wrong by its own
declared rule. It should be revised to match Amendment 3 when
`ENGINE_1_ARCHITECTURE.md` is next touched.

**Residual, and it is real.** `ClassificationResult.document_type` returns a type rather
than a cue. Harmless *today* only because the module has zero consumers — see F-018 —
so its output never reaches the Document Evidence Object. The moment assembly wires it
in, `COMMUNICATION_RULES_INPUT_ENGINE.md:71` goes live and the field must arrive
carrying its `MatchedCue`s, never as a bare type.

**The class, not the instance.** An index that restates a conclusion can restate the
wrong one. `BLOCKERS.md:3-6` calls itself *"Index, not a copy"* while its "Why only the
owner" column is a copy — and it copied the half of this entry that was wrong. That is
where the drift entered, and it is why `BLOCKERS.md` now points at entries instead of
paraphrasing them.

---

## F-018 · Three Engine 1 modules are wired to nothing

| | |
|---|---|
| **Severity** | HIGH — three sub-engines are built, tested, mutation-hardened, and never run |
| **Status** | 🔄 OPEN · agent wiring it |
| **Found** | 2026-08-06, while verifying F-010's residual |

**Measured.** `pipeline.py:178` imports `assembly, cleaner, confidence_report, parser,
reader`. Grepping all of `src/` for consumers of the remaining three returns nothing:

```
classification.py   17.6K   consumers: none
config.py           27.5K   consumers: none
measurement.py      22.7K   consumers: none
```

`PipelineSettings` (`pipeline.py:263`) takes every setting from its caller and never
loads `config.py`.

**What that means, if the architecture requires them in the pipeline.**

- Document type is never determined for a real document.
- The 16 named confidence parameters are never loaded on the real path, so the
  **fail-fast-on-missing-configuration** behaviour `CLAUDE.md` requires never fires
  where it matters.
- No measurement is ever recorded, so the raw signal's only home in the entire system
  stays empty.

**Root cause — the same shape as F-012.** A module that exists, passes its tests and is
not in the pipe. Unit tests cannot see this: each module's tests import it directly, so
they prove the module works and say nothing about whether anything calls it. F-012 was
found the same way, by integration rather than by unit tests, and it took three recorded
failures before the single cause was named.

**Permanent fix.** Establish per module whether the locked architecture requires it in
the pipeline — one of the three may legitimately belong to the Application Layer rather
than the engine — then wire only what is required, test-first. In progress.

---

## F-019 · Engine 1 emits a confident, empty, valid lie

| | |
|---|---|
| **Severity** | **CRITICAL** — this is the *"never post a wrong entry"* non-goal failing at the source |
| **Status** | 🔄 OPEN · agents fixing it in three files |
| **Found** | 2026-08-06, by two agents investigating different questions who converged on the same three lines |

**Demonstrated, executed against the real modules.**

```
input : OCR reading, two regions scored 0.31 and 0.28
output: artifact VALIDATED : True
        extracted_text     : 'Total 1,18,OOO.00\nGSTIN 27AAEC'
        confidence_scores  : ()      <-- the 0.31 / 0.28 are gone
        uncertainty_markers: ()
        risky_fields       : ()
```

`1,18,OOO.00` carries letter-`O` where zeros belong — the classic 28%-confidence OCR
failure. It leaves Engine 1 with **no marker and no score**, inside an object marked
VALIDATED. Every downstream engine then reasons from it confidently, and nothing in the
system can tell that it was ever doubtful.

**The sharpest way to see it.** `stub.py`, which reads nothing at all, emits an
uncertainty marker so its emptiness cannot be mistaken for a real reading.
`pipeline.run()`, which read a document and got garbage, emits none. The stub's own
docstring names the exact failure the production pipeline now has.

**Mechanism — three lines, acting jointly.**

```
pipeline.py:456-460        parser_output() unconditionally returns detected_fields=()
pipeline.py:565            run() passes a literal () as record_confidence's parsed_fields
confidence_report.py:378   _field_confidence_scores reads ONLY parsed_fields; the
                           reader_regions path feeds a marker that fires only when
                           text is None — never true for a successful read
pipeline.py:364            filters out 100% of PDF text-layer regions (the MVP's
                           primary input) before confidence ever sees them
```

**Root cause — `reader` and `parser` never meet.** Nothing in Engine 1 joins a name to a
score:

| Producer | Has a NAME | Has a CONFIDENCE |
|---|---|---|
| `reader.TextRegion` | ✗ — only a `SourceLocation` | ✅ |
| `parser.Region` | ✅ `label` | ✗ |
| `parser.Table` / `Cell` | ✗ | ✗ |

`parser.parse` takes a `Path` and re-opens the document; `reader.Reading` is never an
input to it. But `SUB_ENGINE_RESPONSIBILITIES.md` §1.3 — **locked, level 2** — states
parser's input is *"Raw extracted information with source locations from `reader`"* and
that field mappings *"retain the source reference for every mapped value."* Code and a
locked document disagree, so **the document wins and the code is wrong** (§M).

**This is the unfixed half of F-012.** `412eed6` fixed `cleaner → {reader, parser}`. The
`reader → parser` half was never built. F-012's entry is stale in saying otherwise.

**Locked clauses violated** — the four that bite hardest:

- `ENGINE_1_INPUT_ENGINE_RULES.md:245` — *"A value carried without all three is not
  evidence and must not be emitted."* Engine 1 emits it anyway, as bare `str`.
- `COMMUNICATION_RULES_INPUT_ENGINE.md:113-119` — source, confidence and uncertainty
  *"travel with the value permanently."* Zero values carry any of the three.
- `SYSTEM_INVARIANTS.md` INV-11 — *"No engine may merge these origins into a single
  anonymous fact."* `document_structure` is exactly that: every region's label, text and
  box concatenated into one origin-free string.
- Law 24 — `reliability_information` states *"0 of 0 region(s) reader attempted"* for a
  reading where `reader` attempted and read **3**. A false number, shipping inside a
  financial artifact.

**What else this explains.** `evidence.py:337-344` — the artifact's own *"every detected
field must carry a score"* validator — **has never executed a single iteration**, because
`detected_fields` is always empty. A green check guarding nothing. The schema is the one
component in the chain that is right: probed directly, it builds a per-field confidence
without complaint and *refuses* a field whose score disagrees with its own provenance.

**The pattern, stated as a class.** Every sub-engine individually refuses to lie. Every
failure is at a **seam**. Nothing guards composition, and an assembly of honest parts
produced a confident, empty, valid lie. Unit tests are structurally blind to this — each
imports its own module and proves that module honest.

**Permanent fix**, in dependency order:

1. Give `RegionReading` its third state — *read but unscored* — mirroring the
   `measurement.AbsentType` precedent that resolved F-005. Stops the loss and removes the
   false count. Fully authorised, no schema change.
2. Build the `reader → parser` pipe the locked spec already mandates, joining on the
   source location. Closes this entirely for the OCR path. Fully authorised.
3. The text-layer path needs one more thing: `Provenance.confidence` is mandatory and a
   text-layer value has **no honest score**. Assigning `1.0` is the forbidden default
   (`ENGINE_1_INPUT_ENGINE_RULES.md:625`); assigning `0.0` is a lie the other way.
   **This one needs the owner** — it is a §M amendment to a frozen P2 schema.

---

## F-020 · `pip install accountant-dad` ships an unimportable Engine 1

| | |
|---|---|
| **Severity** | HIGH — Law 18, hidden dependencies, and the `build` gate is structurally blind to it |
| **Status** | 🔄 OPEN · agent fixing it |
| **Found** | 2026-08-06 |

`pyproject.toml:11-15` declares **only `pydantic`**. But `cleaner.py:96-98` imports cv2 and
numpy at module scope, `reader.py:101-104` imports pymupdf, PIL and numpy, and
`pipeline.py:171` imports pymupdf.

Measured on a stdlib-only interpreter: `import accountant_dad` succeeds;
`import ...input_engine.cleaner` → `No module named 'cv2'`;
`import ...input_engine.pipeline` → `No module named 'pymupdf'`.

**Why no gate catches it.** `quality.yml:47` imports the **top-level package only**, which
has no heavy imports. The gate is green while the installable artifact is broken for
anyone who installs it the declared way.

**Same class as a defect already paid for.** `reader.py` once resolved PaddleOCR at module
scope, making the whole Input Engine unimportable and killing every gate at collection.
That one was loud because it broke everything. This one is quiet — it breaks only on
install, which nobody currently does.

---

## F-021 · The build freeze checks filenames, not code

| | |
|---|---|
| **Severity** | HIGH — the guard Amendment 3 rests on enforces a naming convention |
| **Status** | 🔄 OPEN · agent fixing it |
| **Found** | 2026-08-06 |

`tests/unit/test_package.py:183` checks module **filenames** against `FROZEN_MARKERS`
(`:66`). It opens no file and inspects no import. Demonstration: a file named
`engines/input_engine/gst_rates.py`, full of tax logic, **passes**.

Amendment 3 states *"No accounting reasoning is permitted inside Engine 1"* and lists among
its binding guards *"a new test proves no module **named** for accounting, tax, LLM, brain
or Tally enters it."* **Named** is doing all the work. Anyone writing forbidden logic under
an innocent filename passes.

Two more holes in the same file:

- **Only 1 of 9 Engine 1 modules has a cross-engine import guard**
  (`test_input_engine_parser.py:357`). All five sibling *stubs* have one — **the stubs are
  better protected than the engine.**
- **`AL-INV-5` appears nowhere in `conformance.py` or `conformance_registry.py`.** It is
  prose in docstrings, enforced by nothing.

**The honest limit, to be stated in the fix rather than papered over:** no static check can
prove the absence of accounting reasoning. A guard claiming to is a worse lie than the
filename check.

---

## F-022 · There is no accounting document in this repository

| | |
|---|---|
| **Severity** | HIGH — blocks the ROADMAP's *"a real document runs end to end"* in its intended sense |
| **Status** | 🔒 OPEN · needs real documents, which must be obtained |
| **Found** | 2026-08-06 |

Measured: **40 PDFs · 55,526,251 bytes · 5,678 pages · 12.9 M characters · every one with a
text layer · 0 image files of any format.**

All 40 are statutes, rules, circulars, notifications and ICAI standards — law *about*
accounting. **No invoice, receipt, bill, voucher or bank statement exists.** This is Engine
3 and Brain feedstock, not Engine 1 feedstock.

| Provable today | Not provable |
|---|---|
| text-layer PDF extraction | OCR — there are zero scans |
| very long documents (880pp Income-tax Act) | photographs, deskew on paper, handwriting |
| legislative rate tables · large files | rotation, multi-invoice pages, non-English |
| | **all nine negative controls** |

**Every document the suite reads is generated in memory.** Three generators are shaped like
real-document coverage and must never be cited as such:
`test_input_engine_reader.py:177` (`an_image_only_pdf` — a clean 300-dpi Helvetica render,
no noise, no skew, no artefacts), `test_input_engine_cleaner.py:865` (`a_scanned_pdf`), and
`test_input_engine_reader.py:118-130` (`INVOICE_LINES` — a hardcoded fake invoice that
**also serves as its own ground truth**, which is §J trap (b) exactly).

**On the 16-vs-100 conflict recorded in `BLOCKERS.md`: the two documents do not contradict
each other.** `GOLDEN_DATASET.md` plans 16 golden (10 dev + 6 held-out) + 9 negative = 25,
and separately says ~100 is what *calibration* needs, sequencing them at `:168`:
*"Twenty-five is enough to kill; a hundred is what you need to tune."* The gap is real; the
contradiction is not. `KNOWN_FAILURES.md:217,234` already names the right next step —
**re-derive the number**, which is a measurement, not a budget decision.

**The number that actually blocks is 0.** The storage layout at `GOLDEN_DATASET.md:177-188`
does not exist — no `src/tests/golden/`, and **zero non-`.py` files anywhere under
`tests/`**. `:79` requires all 25 collected and frozen *before any engine is built*. Engine
1 is built.

---

## F-023 · F-002 is recorded RESOLVED and is half resolved

| | |
|---|---|
| **Severity** | HIGH — a pinned version can be violated while every check reports green |
| **Status** | 🔄 OPEN · agent building the guard that does not exist |
| **Found** | 2026-08-06 |

The combined resolve genuinely fails. The **sequential** install does not:

```
pip install numpy==2.5.1 opencv-python==5.0.0.93   → numpy 2.5.1 · cv2 5.0.0
pip install -r requirements-engine1-ocr.txt        → numpy downgraded to 2.3.5,
                                                     opencv-contrib-python added,
                                                     exit 0, no error, no warning
```

```
importlib.metadata.version("opencv-python") → '5.0.0.93'   # a pin assertion PASSES
cv2.__version__                            → '4.10.0'     # the actual library
```

**A metadata-based guard reports green while the pin is violated.** No such guard exists
anyway — nothing in `tests/`, `src/` or `tools/` asserts `cv2.__version__`, while
`cleaner.py` uses cv2 throughout.

**It has already happened here.** The repo's `.venv` holds 13 packages unreachable from any
manifest root; **13 of 13 are OCR-tree packages.** F-002's recorded verification fixed two
version numbers and never checked the environment was clean.

**What that costs.** `ROADMAP.md` records a measured deskew residual of *"0.0017 at 32°"*.
cv2 measured it. Nothing in the repository can currently establish which cv2. The claim is
not disproven — it is **unverifiable**, which under Law 52 is the same as not having it.

**Reproducibility fails too.** 151 of 175 packages (86%) are unpinned; no lockfile, no
hashes. Measured drift on the same commit: `pydantic` 2.12.3 → **2.13.4**, plus
`docling-parse`, `pydantic-core`, `pyyaml`. `pydantic` is pinned in `requirements-ci.txt`
and unpinned in `requirements-engine1.txt`, so **the version of the library that validates
every artifact depends on manifest install order.**

**Licences, swept properly:** 175 packages, all 41 distinct licence strings reviewed. Six
copyleft packages; **PyMuPDF is the only one with a network clause.** `python-bidi`
(LGPL-3.0) and `crc32c` (LGPL-2.1-or-later) arrive through the OCR tree — nil obligation for
pure SaaS, live if anything ships on-premises, and `TECHNOLOGY_STACK.md:131` records Tally
as on-prem Windows. Owner's call. One claimed exposure was **falsified and withdrawn**:
`docutils` carries a GPL classifier but its only GPL file is not shipped in the wheel.

Also: **`rapidocr==3.9.2` resolves into the engine1 tree transitively via `docling`** — a
second OCR engine, against `TECHNOLOGY_STACK.md`'s one-tool-per-capability lock.

---

## F-009 · The OCR path is not proven on CI

| | |
|---|---|
| **Severity** | MEDIUM — a real coverage gap, honestly stated |
| **Status** | ⬜ OPEN · created by the F-002 fix, deliberately |
| **Found** | 2026-08-05 |

**Description.** 11 of `reader`'s tests exercise real PaddleOCR recognition. PaddleOCR
cannot share an environment with `requirements-engine1.txt` (F-002), so it lives in
`requirements-engine1-ocr.txt` and **is not installed on CI**. Those 11 tests skip there.

They skip the same way `test_input_engine_parser.py` skips its 14 Docling measurements,
with a message that names the missing packages and says outright that the measurements
are local and are not CI evidence.

**Impact, stated plainly rather than softened.** The OCR path — the one that runs on
every photographed invoice, which is the primary input this product exists to handle —
**is not proven where proof lives** (Law 44). A green CI tick on this repository
currently means the text-layer path works. It says nothing about recognition.

```
reader tests total        41
run on CI                 30    text layer, error paths, config refusal
skipped on CI             11    every test that performs real recognition
```

**Workaround.** Run them locally in a separate environment:
```
python -m venv .venv-ocr && .venv-ocr/bin/pip install -r requirements-engine1-ocr.txt
```

**Permanent fix — two candidates, neither chosen yet.**
1. A **separate CI job** for the OCR stack, in its own environment, so the 11 run where
   they count. This is a `.github` change and needs the owner's approval for that
   specific change.
2. Resolve the underlying conflict — a PaddleOCR build that does not pin `numpy<2.4`
   and does not drag in a second OpenCV, or a measured re-derivation of `cleaner`'s
   bound against the versions paddlex permits.

Until one lands, **no claim may be made about OCR accuracy, because none is provable.**

---

## Closed

| ID | Title | Closed | Fix |
|---|---|---|---|
| **F-003** | Stale duplicate carrying the inverted `worst_k` row | 2026-08-05 | Deleted after proving nothing depended on it and that its only unique line *was* the bug |
| **F-002** | Two OpenCV distributions in one environment | 2026-08-05 | OCR stack separated into its own manifest; pinned versions verified actually loaded (`numpy 2.5.1`, `cv2 5.0.0`) |
