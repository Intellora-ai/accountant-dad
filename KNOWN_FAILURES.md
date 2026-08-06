# KNOWN_FAILURES.md

Every unresolved issue in this repository. **Nothing disappears from this file until
it is actually fixed** — not when it is worked around, not when it stops being
visible, not when a gate goes green for some other reason.

Append-only in spirit: an entry changes only its **Status** line, and a closed entry
keeps its history.

Last updated: **2026-08-06**

---

## Measurement state of this file — Law 56

**HEAD is `e921c3c`. Every metric below carries the commit that produced it, or says
UNMEASURED.**

`origin/ci/mutation-runs` is at `f31e3cd`. HEAD is **24 commits ahead and unpushed**, and
GitHub returns *"No commit found for SHA"* for `0babf47` and `e921c3c`. **No CI evidence
exists for any commit after `f31e3cd`** — see F-026.

Source churn `7e0efe2` → `e921c3c`: `src/` 10 files **+2591 / −300**; `tests/` 18 files
**+13335 / −148**. Every measurement taken at or before `f31e3cd` is therefore EXPIRED
for HEAD.

| Metric | Value | Commit | Source | Status |
|---|---|---|---|---|
| Mutation | 95.3% — killed 2324, survived 115, 919 not scoreable | `7e0efe2` | GitHub Actions run 31041552213, job 92426852650 | **EXPIRED** — source moved |
| Mutation runtime | 3h 21m 01s | `7e0efe2` | GitHub Actions, same job | **EXPIRED** |
| Coverage | 97.64%, effective floor 97.46% | `f31e3cd` | GitHub Actions run 31047186940, job 92445466419 | **EXPIRED** — source moved |
| Mutation · coverage · anything at HEAD | — | `e921c3c` | — | **UNMEASURED** |

Previous measurements expired because source changed after commit `7e0efe2`.

---

## F-001 · PyMuPDF is AGPL-3.0 and this is a commercial product

| | |
|---|---|
| **Severity** | HIGH — legal, not technical |
| **Status** | 🟨 **CONTAINED, NOT CLOSED.** The owner ruled 2026-08-06: *"Do NOT purchase an Artifex licence. Keep PyMuPDF temporarily. Immediately abstract it behind a PDF Engine interface so Engine 1 never depends directly on PyMuPDF."* The interface exists. **The licence exposure is unchanged** — the AGPL dependency is still pinned and still in use, so this entry stays OPEN until the backend is actually replaced |
| **Found** | 2026-08-05, landing Engine 1's `reader` |
| **Contained** | 2026-08-06 · `src/accountant_dad/pdf_backend.py` |

**WHAT THE ABSTRACTION CHANGED, AND WHAT IT DID NOT.** Before it, three Engine 1
modules reached PyMuPDF independently — `reader.py` and `pipeline.py` by statement,
`cleaner.py` twice through `importlib` — and `pipeline.BUSINESS_FAILURE` named
`pymupdf.FileDataError` outright, so a vendor exception type was load-bearing in
Engine 1's own business/runtime taxonomy. Replacing the library meant editing three
files, one of which decided what counts as a document failure.

`accountant_dad.pdf_backend` now owns every PDF operation, as FUNCTIONS over an
opaque handle rather than as a passthrough of live backend objects — handing callers
a `pymupdf.Document` would have moved the import and changed nothing. No Engine 1
module names a PyMuPDF type, method, option string or exception.
`pipeline.BUSINESS_FAILURE` names `pdf_backend.BrokenPdfError`.

**Guarded by** `tests/unit/test_pdf_backend.py::test_no_engine_1_module_imports_the_
pdf_library_directly` — an AST sweep of every file under `engines/input_engine/`,
statement imports and `importlib` alike, reading the DIRECTORY rather than an
allowlist. Proven to discriminate: injecting `import pymupdf` into `cleaner.py`
turns it red naming the file, and removing it turns it green again.

**The remaining work is still the owner's.** Swapping the backend is now a rewrite
of one file, which is what the ruling asked for. It has not been done, and until it
is, this repository still ships an AGPL dependency.

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

**The second route is now costed and awaiting the owner** —
`AMENDMENT_DRAFT_F001_PDF_BACKEND.md`, written on commit `fd479eb`, all numbers
`LOCAL ONLY — NOT AUTHORITATIVE`. It evaluates `pypdfium2` (already pinned at
`requirements-engine1.txt:104`, so no new dependency), the `pdfplumber`/`pdfminer.six`
family and `img2pdf`, each licence read from installed metadata. Two findings decide it:
**pypdfium2 covers all eight `pdf_backend` operations alone**, and **pdfminer.six /
pdfplumber emit `(cid:N)` glyph identifiers as ordinary text — 2,660 fabricated ASCII
digits on 79 of 219 pages**, which `CLAUDE.md` §B.8 forbids outright. The draft
recommends REPLACE, names eight costs, and names the one experiment that would overturn
it. **Nothing was changed: `docs/TECHNOLOGY_STACK.md`, the manifests and
`pdf_backend.py` are untouched.**

---

## F-002 · Two OpenCV distributions in one environment

| | |
|---|---|
| **Severity** | HIGH — it was silently active, not latent |
| **Status** | ⚠️ **PARTLY RESOLVED 2026-08-05** — see the correction below and F-023 |
| **Found** | 2026-08-05, installing PaddleOCR |

> **STATUS CORRECTED 2026-08-06.** This entry read ✅ RESOLVED. F-023 then measured that
> the *combined* resolve fails but the *sequential* install still silently downgrades
> numpy and adds `opencv-contrib-python`, and that
> `importlib.metadata.version("opencv-python")` reports `5.0.0.93` while
> `cv2.__version__` reports `4.10.0`. The manifest split was necessary and is not
> undone; it was never sufficient. A guard now exists (`202bed4`, `5066576` —
> `tests/unit/test_runtime_library_versions.py`, `tools/ci/assert_imports_match_pins.sh`),
> so the remaining exposure is tracked under F-023, not here.

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
| **Status** | ✅ **CLOSED 2026-08-06** — Amendment 8, and the count was wrong: **five** documents, not three |
| **Found** | 2026-08-05, writing the confidence specification |

**Description.** The owner's decision A7 is binding: **confidence gates NOTHING until
calibration is proven.** `docs/MEASUREMENT_FRAMEWORK.md` §10 states it outright. These
three were named when this entry was written:

```
docs/ADVERSARIAL_TESTING.md:41       attack 8, "Low confidence → Clarification"
docs/EXECUTION_QUEUE.md:129-130
docs/TECHNOLOGY_STACK.md:30,130      the Gemini vision fallback trigger
```

**Two more were found by sweeping rather than by trusting the list**, and both are
higher-precedence than two of the original three:

```
docs/ACCOUNTING_DEFINITIONS.md:215   Uncertainty defined partly as "any confidence below
                                     the threshold at which the system may act unattended"
docs/APPLICATION_LAYER.md:288        failure class "Confidence below threshold"
```

**Root cause.** They were written before the decision existed. `ADVERSARIAL_TESTING.md`
sits at the **same precedence level** as the rule forbidding it, so precedence alone
does not settle it — which is why the fix had to be an amendment and not a correction.

**Impact.** Whoever implements one of these next will build a threshold, believing a
locked document told them to — and will then have to invent the number, because none
exists. Law 52 and Law 54 broken at the same keystroke, with a locked document as the
defence.

**Permanent fix — LANDED.** `docs/ARCHITECTURE_AMENDMENTS.md` **Amendment 8**, all eight
§M items, approved by the owner 2026-08-06. **Every purpose survives without a
threshold**; only the stated *mechanism* changed in each case:

| Document | Now reads |
|---|---|
| `ADVERSARIAL_TESTING.md` attack 8 | unread regions → missing information → **Clarification** |
| `EXECUTION_QUEUE.md` | 🔄 **by supersession** — the clause line is byte-identical and a block beneath it states what it must be read as. See below |
| `TECHNOLOGY_STACK.md` | the Gemini fallback has **no trigger**; the blocker is a routing decision, not a number |
| `ACCOUNTING_DEFINITIONS.md` §6 | `Uncertainty` = the set of open doubts. Second term **struck** |
| `APPLICATION_LAYER.md` | failure class renamed **Unresolved doubt or unestablished fact** |

**One line remains to be edited, and it is blocked on file ownership, not on a decision.**
`EXECUTION_QUEUE.md`'s clause is cited by CONTENT digest from
`conformance_registry.py:2119` — `#an-incorrect-entry-must@b50bd021b31e` — so editing the
words breaks the citation, and that file belongs to another workstream. **The suite found
it, which is the content-addressed citation doing exactly its job.** The amendment is
applied there by supersession instead: the clause is byte-identical and a block directly
beneath it states what it must be read as and why. The two changes must land together, and
the exact pair is in `docs/ARCHITECTURE_AMENDMENTS.md` Amendment 8, "The one that could not
be edited in place".

**What would prove the fix incomplete.** A sixth document gating on confidence in words
the sweep's eight patterns do not match — *"when the reading is weak, route to review"*
would pass it. Treat that as this entry reopening, not as the amendment being wrong.

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
| **Severity** | **MEDIUM, and rising fast** — re-rated 2026-08-06 on measurement |
| **Status** | ⬜ OPEN · flagged, deliberately not changed |
| **Found** | 2026-08-05, first completed mutation run |

**Description.** `.github/workflows/testing.yml:300-311` computes
`score = killed / (killed + survived)` and reports everything else as `NOT SCOREABLE`.
The first completed run:

```
killed 1364 · survived 9 · timeout 220        @ commit d85861c  (GitHub Actions)
```

Those 220 timeouts are outside the denominator. This is deliberate and documented in the
step's own comment.

**Impact — and the trend this entry predicted has arrived.** A growing timeout population
silently shrinks what the floor is measured over.

| Mutants scored out | Commit | Source |
|---|---|---|
| 77 not scoreable, at 1593 mutants | `d85861c` (earlier run) | GitHub Actions |
| 220 not scoreable | `d85861c` | GitHub Actions |
| **919 not scoreable** — killed 2324, survived 115 | `7e0efe2` | GitHub Actions run 31041552213 |

**919 of 3358 mutants — 27.4% of the population — are outside the denominator** as of
commit `7e0efe2`. That measurement is now EXPIRED (source moved), so the figure at HEAD
is **UNMEASURED**, and the direction of travel is the finding, not the exact number.

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

**Re-verified 2026-08-06** against ruleset `20249495` via the API. The required list is
still exactly those six, unchanged. Measured on `f31e3cd`, the last commit GitHub has
judged:

```
GREEN   build · typecheck · lint · unit tests · coverage · dependency scan
        mutation · conformance · conformance suite · secret scan · CodeQL
        typecheck · lint · tests · build   (the legacy combined gate)
RED     adversarial tests · docker build · end-to-end · golden dataset
        integration tests · license scan · merge gate · negative controls
        negative controls 9 of 9 · performance · semgrep
```

Eleven red, and a pull request carrying them still merges. **`license scan` and `semgrep`
are two reds this entry never listed** — both are real jobs, both fail, both bind nothing.

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

| **Second half closed** | 2026-08-06 · the Document Cleaner and its dispatch registry |

**THE HALF THAT WAS STILL OPEN, AND IS NOW CLOSED.** `CleanedArtifact` fixed the
TYPE. It did not remove the second door: `cleaner.clean(image, settings)` stayed
public, took an `NDArray`, and returned a `CleanedDocument` with no `artifact` on
it — an object `pipeline._payload_of` refuses and that `reader` and `parser` cannot
consume. Measured before the change: **zero callers in `src/` outside `cleaner.py`
itself, sixty-seven in `tests/`.** A door held open by its own tests.

The owner's ruling (2026-08-06) is *"a media-agnostic Document Cleaner as the single
entry point for all supported document types… Remove every legacy bypass and
duplicate path."*

- `clean` is now `_clean_image` — the Image Cleaner, one of the implementations
  `CLEANERS` dispatches to.
- `clean_artifact` is the single entry point and contains **no branch on `kind`**:
  it looks the kind up in `CLEANERS` and calls what it finds. Adding Excel or email
  later is a `MediaKind` member plus a registry entry and nothing else.
- All sixty-seven tests still run: **66 retargeted** at the internal Image Cleaner,
  **1 moved** to the single entry point and made stricter by the move.

**Guarded by** `test_the_module_offers_exactly_one_public_way_to_clean_a_document`
(reads the public surface for ANY function whose name says it cleans, so restoring
the door as `clean_page` fails too), `test_a_kind_this_module_has_never_heard_of_
dispatches_without_the_dispatcher_changing`, `test_every_media_kind_has_an_
implementation_registered_for_it`, and
`test_every_media_kind_travels_the_same_path_and_nothing_re_opens_the_intake` —
which records what `reader` and `parser` were each handed on a real run and compares
it byte for byte to that run's own cleaned payload, across an image, a text-layer
PDF, a scan and a mixed document.
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
| **Status** | ✅ **RESOLVED 2026-08-06** — the cause was `setproctitle`, not `fork`, and `mutmut==3.7.0` already fixes it. Mutation runs on macOS today |
| **Found** | 2026-08-05 (re-derived the expensive way; first noted earlier the same day) |

### THE RECORDED ROOT CAUSE WAS WRONG — falsified by experiment, 2026-08-06

This entry blamed `fork()` after OpenCV/torch/Accelerate initialise threads. **That is
false.** Measured at commit `a467bb2`, macOS 25.4.0 arm64, Python 3.12.13:

```
import cv2 / torch / torchvision / transformers / docling / timm / pypdfium2 / PIL / pymupdf
  -> os.fork() -> child runs pytest      ALL exit 0.  Not one segfault.
parent USES the libraries first (BLAS, parallel_for_, ATen), then forks,
  then the child uses them again          exit 0.
```

Every library the entry accused is innocent. The bisect that finds the real cause needs
**no libraries at all**:

```
setproctitle in parent? | fork | setproctitle in child | result
------------------------|------|-----------------------|--------------
no                      | yes  | yes                   | exit 0
YES                     | yes  | yes                   | SIGNAL 11 SIGSEGV
```

**Root cause.** `setproctitle` uses CoreFoundation on macOS, which is not fork-safe.
mutmut's worker calls it as its first action after `os.fork()` (`__main__.py:1476`).
Upstream says so in mutmut's own source — `mutmut/utils/safe_setproctitle.py`:
*"setproctitle uses CoreFoundation APIs on macOS which aren't fork-safe. Calling
setproctitle after fork() causes segfaults in the child process."*

Two further corrections to the old text. mutmut does call
`multiprocessing.set_start_method('fork')`, but its workers are created by a **raw
`os.fork()`**, so multiprocessing was never in the path. And mutmut maps **both `-11`
(SIGSEGV) and `-9` (SIGKILL)** to the label "segfault" (`mutmut/__init__.py:101-102`), so
the original "every single one: segfault" could not distinguish a crash from a kill.

### THE FIX WAS ALREADY IN THE TREE

`requirements-ci.txt` pins `mutmut==3.7.0`, which routes through `safe_setproctitle` and
defaults `use_setproctitle` to `not platform.system() == "Darwin"` — **off on macOS**
(`mutmut/configuration.py:151-153`). Nothing needed to be written. The entry was stale.

**Proof — one variable, same tree, same commit, same interpreter, same machine:**

```
LOCAL ONLY — NOT AUTHORITATIVE      commit a467bb2      mutmut 3.7.0      macOS
arm  use_setproctitle   tried   killed   survived   segfault-bucket
 a   false (default)     2345     2020        135        176   ( 7.5%)
 b   true  (pre-3.7.0)   1349        0          0       1349   (100%)
```

Arm b reproduces the recorded failure exactly. Arm a scores 2020 mutants. **Mutation
testing runs on macOS.** The 176 residual in arm a is not explained here and is not
claimed to be segfaults — the bucket conflates SIGSEGV with the SIGKILL that mutmut's own
`RLIMIT_CPU` and wall-clock timeout produce.

### TWO BLOCKERS REMAIN, AND NEITHER IS macOS

Both abort mutmut's **stats phase**, which runs the whole suite with `-x` before the first
fork. One red test there scores **zero** mutants, on every platform:

1. `tests/unit/test_declared_dependencies.py` reads the RUNNING tree
   (`Path(__file__).resolve().parents[2]`), which under mutation is `mutants/`, where
   mutmut has injected `from mutmut.mutation.trampoline import ...` into every module. The
   test then reports `import mutmut` as an undeclared dependency. Measured: the same test,
   same interpreter, run from `mutants/` **fails**; run from the authored tree, **7
   passed**. This is exactly the L-013 class and the fix is `tools/ci/authored_source.py`.
   That test did **not exist** at `7e0efe2`, the last commit whose CI mutation run
   completed — which is why CI was green then and is not now.
2. `tests/unit/test_module_wiring.py` is **deliberately red** at HEAD (it is F-018's
   marker). `-x` stops on it.

Neither file is owned by this workstream, so both are recorded rather than changed. Until
one of them is addressed, `mutmut run` scores nothing **anywhere**, not just on macOS.

**Original root-cause text, kept for the record.** mutmut calls
`multiprocessing.set_start_method('fork')`. On macOS, `fork()` without `exec()` in a
process that has already initialised OpenCV, torch or Accelerate leaves the child with
broken thread state, and it dies with SIGSEGV before running a single test. Engine 1
imports all three. — **This is the paragraph the experiment above falsified.**

**Impact — and this is the part worth internalising.** Law 44 says *"a result exists only
if GitHub CI produced it."* For mutation that is not a policy preference, it is a hardware
fact: no amount of local iteration can produce a survivor list. **Every mutation
hypothesis costs a full CI run.**

At the current scale that is roughly **3+ hours per attempt**, which makes guessing
expensive and makes the first attempt worth getting right.

**That estimate is now a measurement.** The completed run took **3h 21m 01s** at commit
`7e0efe2` (GitHub Actions run 31041552213, job 92426852650). The cost per mutation
hypothesis at HEAD is UNMEASURED and can only be larger — `src/` grew by 2591 lines after
that commit.

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
| **Status** | ✅ **CLOSED 2026-08-06** — cap raised to 500 minutes at `66ab8cd`, and a run has since finished |
| **Found** | 2026-08-05, after Engine 1 landed |

**How it closed.** `.github/workflows/testing.yml:213` now reads `timeout-minutes: 500`,
landed by `66ab8cd` — *"the cap was hiding a real score regression, not just a slow job."*
The number came from the owner, not from an engineer, which is what this entry was
blocked on.

**Proof it is actually fixed, not merely re-specified.** The `mutation` job ran to
completion:

```
Commit : 7e0efe2
Source : GitHub Actions run 31041552213, job 92426852650
Runtime: 3h 21m 01s   (19:54:15Z -> 23:15:16Z)
Result : success
```

**Guarding test — there is none, and that is itself a finding (Law 3).** A CI job's
`timeout-minutes` is configuration, not code, and nothing in `tests/` asserts it. If
someone lowers it back to 100 the only signal is a cancelled run three hours later. The
guard that would close this properly is a `.github` change and needs the owner's approval
for that specific change; it is recorded here rather than written.

**Original description, kept.** The `mutation` job was cancelled at the 100-minute cap on
`ed5d504`. It was not failing on score — it could not finish.

**Two things changed at once, and they multiply.**

```
mutant population   1593 → 2933      +84%   @ ed5d504, EXPIRED. Engine 1's new modules
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
| `2625b58` | — | ✅ finished · **90.6%** — killed 2178, survived 227, 953 not scoreable |
| `7e0efe2` | 3358 | ✅ **3h 21m 01s · 95.3%** (floor 93) — killed 2324, survived 115, 919 not scoreable |
| `e921c3c` (HEAD) | — | **UNMEASURED** — never pushed, never run |

Every row above names the commit that produced it. All of them are **EXPIRED** for HEAD:
`src/` moved by **+2591 / −300** lines after `7e0efe2`.

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
at 3.45x the work in 60% as many mutants, @ commit d85861c and now EXPIRED.

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
| **Status** | ✅ **CLOSED 2026-08-06** — both halves built. The residue moved to F-019 |
| **Found** | 2026-08-05, wiring the pipeline |

**How it closed, in two halves and two commits.**

| Half | Commit | Guarding test |
|---|---|---|
| `cleaner → {reader, parser}` — both now read `cleaned.artifact.payload`; the `rasterise_first_page_for_cleaning` adapter was **deleted**, not deprecated | `412eed6` | `tests/unit/test_input_engine_pipeline.py` — three tests replaced two, one asserting on `run`'s own source so the bypass cannot return quietly |
| `reader → parser` — `extracted_regions` converts `reader`'s regions and hands them to `parser.parse`, which is `SUB_ENGINE_RESPONSIBILITIES.md` §1.3's stated input | `6b32425`, `41b23e6`, `d29985a` | `tests/unit/test_input_engine_pipeline_redteam.py::test_reader_and_parser_were_handed_the_same_cleaned_bytes_as_each_other` and siblings — **currently RED for an unrelated reason, see F-025** |

**What did NOT close, stated plainly rather than folded into a green tick.** `parser.parse`
still *also* opens the document, because `reader` reports spans and only Docling reports
layout; and `reader.read` still takes `bytes` rather than `cleaner`'s object. Neither costs
traceability any more — the values that cross now carry their own origin — and both are
recorded in `parser.py`'s own docstring as work outstanding.

**The consequence this entry claimed is gone.** It said *"cleaning does not affect what is
read or parsed."* That is no longer true; it was true when written.

**Original description, kept.** `docs/DATA_FLOW.md` draws `cleaner → reader → parser` as a
chain. The code was not one:

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
| **Status** | 🔄 **HALF CLOSED 2026-08-06** — gap 1 fixed; the text-layer half is F-019 and needs the owner |
| **Found** | 2026-08-05, wiring the pipeline |

**Gap 1 is fixed — `502e166`.** `confidence_report.ReadingState` now names three states,
not two: `UNREAD`, `READ_AND_SCORED`, `READ_BUT_UNSCORED`. It mirrors the
`measurement.AbsentType` precedent that resolved F-005, so no caller re-derives the state
from a bare `is None`. Only the reverse pairing stays refused — a confidence with no text.
**Guarding tests:** `tests/unit/test_input_engine_confidence.py` pins all three states by
name, and two further tests pin that `state` tests `is None` and never falsiness —
load-bearing, because `Decimal("0")` and `""` are both falsy.

**A named, scored field now exists for the OCR path — F-012's `reader → parser` pipe.**
`pipeline.detected_fields` builds a real `evidence.DetectedField` per mapped value and
`parsed_fields` builds the matching `confidence_report.ParsedField`, carrying the identical
`Decimal` object, so the field's provenance and the Confidence Report agree by construction.

**What is still true, and it is the half that matters for the MVP.** A PDF text layer has
no honest score to put on `Provenance.confidence`, which is mandatory. `1.0000` is the
default `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids and `0.0000` asserts a measured
worthlessness nobody measured — so `detected_fields` **skips** an unscored mapping rather
than inventing a number. Tracked as F-019; closing it is a §M amendment to a frozen P2
schema and is the owner's decision.

**Original description, kept.** Two independent gaps composed into one hole.

1. `confidence_report.RegionReading(text="TAX INVOICE", extraction_confidence=None)`
   **always raised** `MalformedSignalError`. Its invariant assumed text-without-a-score
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
| **Severity** | MEDIUM — a precedence question and a definition question, both now answered |
| **Status** | ✅ **CLOSED 2026-08-06** — resolved at `a482ad6` by delegated engineering authority. Neither half needs the owner |
| **Found** | 2026-08-05, building `classification` |

### How it closed — the specification was right, and so is the code

**The owner delegated the decision**, in these words: *"Determine which is correct: the
implementation, or the specification. … Do not leave them inconsistent. The repository
must have one source of truth."*

**Answer: both, because `module` and `sub-engine` are not the same thing** — and the
documents settle that without anybody's preference being involved.

**The clause was never counting files.** `ENGINE_1_INPUT_ENGINE_RULES.md:8`, four lines
below the one that says LOCKED:

> *"**Specification only — no implementation.** No code, no libraries, no OCR, computer
> vision or handwriting systems, no pipelines, no dependencies."*

A count written by a document that forbids source files from existing cannot have been a
count of source files. It counts **owned problems** — the unit
`SUB_ENGINE_RESPONSIBILITIES.md:20` uses: *"Each sub-engine owns exactly one problem."*

**The document already contained the membership test; it was a table caption.**
`ENGINE_1_INPUT_ENGINE_RULES.md:399`, over the four output contracts:

> *"These are the four parts the parent engine combines."*

So: **a component is a sub-engine if and only if it produces one of the four parts the
parent combines into the Document Evidence Object.** Checkable, not a judgement call.

**Engine-level work that is not sub-engine work already existed before any code did.**
`:384` — *"The four sub-engines are specialised workers. The parent engine is the boundary
at which their individual observations become one artifact. **No new assembler sub-engine
is created**"* — while `:62` puts assembly in the engine's own `owns` list and `:95` gives
**Input Engine (parent)** its own row in the Decision Authority table, beside the four and
distinct from them. `SUB_ENGINE_RESPONSIBILITIES.md` §1 says it once more: *"No assembler
sub-engine exists, and none may be added."* That is the proof by construction.

### All nine, classified

| Module | Produces one of the four parts? | Verdict |
|---|---|---|
| `cleaner` | cleaned representation · quality issues · preservation status | **SUB-ENGINE** §1.1 |
| `reader` | raw extracted information · source locations · extraction confidence | **SUB-ENGINE** §1.2 |
| `parser` | structured fields · field mappings · missing field information | **SUB-ENGINE** §1.3 |
| `confidence_report` | confidence scores · uncertainty markers · reliability | **SUB-ENGINE** §1.4 |
| `pipeline` | No — it *calls* the four | **PARENT ENGINE'S OWN MACHINERY** |
| `assembly` | No — it *is* the combining | **PARENT ENGINE'S OWN MACHINERY** |
| `config` | No | **FACILITY** |
| `measurement` | No | **FACILITY** |
| `classification` | No | **FACILITY** |

**Four sub-engines. The lock holds. Nothing is deleted and nothing is refactored.**

### `classification` was the hard one, and the artifact decided it

Verified at `a482ad6`, not asserted:

```
$ grep -c "document_type" src/accountant_dad/artifacts/evidence.py
0

DocumentEvidenceObject.model_fields
    identity · document_id · source_references
    structured_document · human_business_context? · confidence_report
```

**No document-type field. No fifth component.** Its output therefore cannot be one of the
four parts, so it is not a sub-engine — it is a facility, and `exactly four` is untouched.

Two further checks, both run rather than recalled:

```
$ grep -in "classif|document type" docs/ENGINE_1_INPUT_ENGINE_RULES.md
(exit 1 — zero matches in 669 lines)

$ grep -rn "input_engine import|input_engine\." src
pipeline.py:228   from ...input_engine import assembly, cleaner, confidence_report, parser, reader
```

The level-3 locked document is **silent** on classification — it forbids a fifth
*sub-engine*, never a facility. And `classification`, `config` and `measurement` have
**zero consumers in `src/`**; only tests import them (F-018, still open and untouched).

### The G9.5 half, also closed

`ENGINE_1_ARCHITECTURE.md` §G9.5 said document-type detection was *"not authorised … out
of scope until the owner rules."* **The ruling already existed** — `CLAUDE.md` §P
Amendment 3, owner-approved 2026-08-05, names *"document classification"* explicitly. That
document self-declares *"Status: DRAFT — NOT FROZEN"* (`:8`) and *"Where this document
contradicts any of them, this document is wrong"* (`:5`), and appears at no level of the
ladder in `SYSTEM_INVARIANTS.md:11-18`. §M binds **frozen** documents; a draft is revised,
not amended. **G9.5 has now been revised** at `a482ad6` rather than left to rot.

This entry previously said the shape question was *"only the owner may pick."* That was
right on 2026-08-05 and is superseded by the delegation of 2026-08-06.

### What now guards it — four tests, each proven to fail first

| Guard | Traps |
|---|---|
| `test_no_engine_1_module_exists_without_an_architectural_decision` | a tenth module on disk with no decision |
| `test_the_sub_engine_set_is_exactly_the_four_the_locked_specification_names` | a fifth sub-engine promoted quietly |
| `test_the_three_architectural_categories_are_disjoint` | a module left in two categories, i.e. undecided |
| `test_the_evidence_object_has_no_document_type_field` | the amendment's **own stated falsifier** |

All four in `tests/unit/test_package.py`. Each was mutated red before being accepted
(§J.1): a tenth file added, `classification` promoted, a name double-listed, and
`document_type` added to the schema **together with** a matching edit to the field pin —
that last case is why the general type sweep runs *before* the exact-set assertion, since
in the other order it could never fail.

**Written up as Amendment 5** in `docs/ARCHITECTURE_AMENDMENTS.md`, all eight §M items.
The membership test is now `ENGINE_1_INPUT_ENGINE_RULES.md` **§9A** — placed after §9 for
the tooling reason recorded in **F-027**, not for an architectural one.

### The class, not the instance

**A count with no stated unit is Law 52 unmet inside a locked document.** F-010 was not a
disagreement about architecture; it was a number that never said what it counted, sitting
in a document nobody could edit. The general fix is the one applied here: when a locked
document states a quantity, it must also state the predicate that decides membership, and
a test must enforce the predicate. Six other locked documents state counts — 39
sub-engines, 6 engines, 13 invariants, 6 artifacts, 10 contracts, 16 parameters.
**`FORWARD_DEPENDENCY_INVENTORY.md:96` already records the 39 as `Open` — *"no engine's
count has been tested against its real needs."*** This entry is the first instance of that
open question reaching real code, and it will not be the last.

### HISTORY — the G9.5 reasoning as it stood on 2026-08-05, kept verbatim

> *This file's rule: "a closed entry keeps its history." Everything below is the original
> analysis of the capability half. It remains correct; it is no longer the current status.
> The current status is the CLOSED section above.*

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

> **DONE at `a482ad6`.** G9.5 now reads *"Document-type detection — REVISED 2026-08-06, no
> longer open"* and states the capability is authorised as a **facility, never a fifth
> sub-engine**. The line it drew — observation permitted, conclusion forbidden — was the
> right line and is carried forward unchanged.

**Residual, and it is real. STILL OPEN — this half did not close.**
`ClassificationResult.document_type` returns a type rather than a cue. Harmless *today*
only because the module has zero consumers — see F-018, re-verified at `a482ad6`: the only
`src/` import of anything under `input_engine` is `pipeline.py:228`, which names
`assembly, cleaner, confidence_report, parser, reader` and **not** `classification` — so
its output never reaches the Document Evidence Object. The moment assembly wires it
in, `COMMUNICATION_RULES_INPUT_ENGINE.md:71` goes live and the field must arrive
carrying its `MatchedCue`s, never as a bare type.

**This residual now has a tripwire.** `test_the_evidence_object_has_no_document_type_field`
fails the moment a document type reaches the artifact, so the day the wiring happens the
suite says so instead of the defect shipping quietly. **It tracks the residual; it does not
fix it.** The fix is a contract change and belongs with F-018.

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
| **Status** | ✅ **FIXED 2026-08-06.** All three have real consumers in `engines/input_engine/pipeline.py`, and `test_module_wiring.py::test_every_authorised_engine_1_module_is_reachable_from_the_application_layer` is green |
| **Found** | 2026-08-06, while verifying F-010's residual |

**RE-MEASURED 2026-08-06 at commit `e921c3c`.** This entry said *"agent wiring it."* No
agent wired it. `src/` contains exactly two imports of anything under `input_engine`:

```
pipeline.py:228           from ...input_engine import assembly, cleaner,
                              confidence_report, parser, reader
services/pipeline.py:132  from ...input_engine import pipeline as input_engine
```

`classification`, `config` and `measurement` still have **zero consumers**. `pipeline.py`
gained 688 lines after `7e0efe2` and did not gain one of these three. The status is
corrected from *in progress* to *open and untouched* — an entry that says work is happening
when it is not is worse than one that says nothing.

**Original measurement, kept.** `pipeline.py:178` imported `assembly, cleaner,
confidence_report, parser, reader`. Grepping all of `src/` for consumers of the remaining
three returned nothing:

```
classification.py   17.6K   consumers: none
config.py           27.5K   consumers: none
measurement.py      22.7K   consumers: none
```

`PipelineSettings` (`pipeline.py:263`) takes every setting from its caller and never
loads `config.py`.

**THE FIX, 2026-08-06 — a consumer each, not an import each.** Import reachability is
the DETECTOR; it is satisfied by an `import` nothing calls, so each of the three was
given work to do on the real path:

| module | what consumes it |
|---|---|
| `config` | `PipelineSettings.vision_fallback_threshold` — a loose `Decimal` — was REPLACED by `confidence_parameters: ConfidenceParameters`, and `run` hands `ocr_vision_fallback` to `reader.read`. There were two representations of that one number and the one in use had never been range-checked; there is now one, validated (Law 19) |
| `classification` | `run` classifies every document from the `reader.Reading` and `parser.ParsedStructure` it alone holds at the same moment |
| `measurement` | `run` builds one calibration row per completed document — step 2 of `ENGINE_1_CONFIDENCE_PARAMETERS.md`'s "only route" — carrying per-region, per-field, classification and table signals with their instruments, and appends it when `measurement_store` names a destination |

**Nothing entered the Document Evidence Object.** All three stay FACILITIES:
`test_the_evidence_object_has_no_document_type_field` is the falsifier, and
`ENGINE_1_INPUT_ENGINE_RULES.md:353` — *"exactly four"* sub-engines — is why it has
to be.

**Nothing was invented to make the wiring look busy.** `document_score` is `ABSENT`
because #13 is UNDEFINED, `correctness` is `UNLABELLED` because ground truth is P1's
and has not run, and every classification signal carries `None` because
`classification` scores nothing by design. Three tests assert exactly those absences.

**WHY NO GATE SAW IT, and what now would.** Every gate that existed asked a question
about a module IN ISOLATION — `unit tests` imports it and proves it works, `coverage`
counts the lines those tests ran, `mutation` kills the mutants those tests kill. All
three go green on a module nothing calls. `test_module_wiring.py` is the general fix
for that class and it now passes; the tests named above are the specific check that
the modules are CONSUMED rather than merely imported.

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

### DETECTION — `tools/ci/module_wiring.py`, added on top of `a501a69`

**The wiring is NOT done here.** What is added is the thing that was missing: an automated
answer to *"is this module reached by anything that runs?"* Every gate that existed asks
about a module in isolation and goes green on a module nothing calls — `unit tests` imports
it directly and proves it works, `coverage` counts the lines those tests ran, `mutation`
finds its tests kill the mutants. Three green gates, zero consumers.

**The transform (Law 53).** *"Does this module do its job in production?"* needs a running
system, a real document and a human to judge. *"Is this module reachable in the first-party
import graph from the Application Layer's entry point?"* needs a parser, answers in
milliseconds, and fails in the same place.

**STATUS: RED, CORRECTLY.** Measured on `a501a69`, **LOCAL ONLY — NOT AUTHORITATIVE** —
`test_every_authorised_engine_1_module_is_reachable_from_the_application_layer` names:

```
accountant_dad.engines.input_engine.classification
accountant_dad.engines.input_engine.config
accountant_dad.engines.input_engine.measurement
```

Six of the nine `ENGINE_1_AUTHORIZED` modules — `assembly`, `cleaner`, `confidence_report`,
`parser`, `pipeline`, `reader` — pass the same predicate, so this is a gate that
discriminates, not one that is red about everything.

| | |
|---|---|
| **Guarded by** | `tests/unit/test_module_wiring.py` — 14 tests. Three separate requirements, checked separately because they have different fixes: reachable from the Application Layer · imported by at least one test · inside the `[tool.coverage.run] source` tree |
| **Scope** | `ENGINE_1_AUTHORIZED`, imported from `test_package.py` rather than restated, so the list has one owner (Law 19) |
| **Reachability, not popularity** | the predicate is *reachable from the entry point*, never *somebody imports it*. Two orphans importing each other each have a consumer and neither ever runs; only a walk from the thing that starts can tell those apart |
| **Proven it can pass** | temporarily importing all three into `assembly.py` returned `orphans: ()`. It flips green the moment the wiring lands, and was reverted |
| **`engines/input_engine/stub` is excluded** | it is in `AUTHORIZED_STUBS`, is unreachable BY DESIGN because the real pipeline replaced it, and folding it in would mean either a permanently red gate nobody intends to fix or an exception list — and an exception list is how a gate stops meaning anything |
| **False-positive sources, checked** | every `importlib.import_module` call in `src/` takes a third-party literal (`pymupdf`, `paddleocr`, `docling…`), and no `src` module defines a module-level `__getattr__`, so no first-party module is reached in a way the static graph cannot see |

---

## F-019 · Engine 1 emits a confident, empty, valid lie

| | |
|---|---|
| **Severity** | **CRITICAL** — this is the *"never post a wrong entry"* non-goal failing at the source |
| **Status** | ✅ **CLOSED 2026-08-06** — Amendments 6 and 7. Residue tracked as O11–O14, none of which lets a value cross without provenance |
| **Found** | 2026-08-06, by two agents investigating different questions who converged on the same three lines |

### What closed the last of it, 2026-08-06 — Amendment 7

The text-layer half was **blocked on the owner**, correctly: it needed an absent-measurement
state on a frozen P2 schema. The owner ruled, and ruled wider than the block —
**four states, not two**:

```
MEASURED . NOT_MEASURED . NOT_APPLICABLE . FAILED
```

**The root cause was not the missing sentinel.** It was that the architecture modelled the
RESULT of measuring — a number — and used `None` for everything else, while `None` already
meant four other things in the same pipeline. The absence of a measurement had no name, and
a fact with no name cannot be carried, checked or refused. A schema demanding a number from
a world that supplies one only sometimes leaves three moves: **invent, drop, or crash.**
This repository had done the first two.

**Tables, the half this entry recorded as "unchanged and unclaimed", are closed too**, and
the diagnosis in this entry was one layer off. A `parser.Cell` always carried its `box`, so
the LOCATION was never missing — what was missing is a **NAME**, because every route that
attaches a provenance is keyed by name. `parser.map_cells` supplies it, and each cell then
travels the same road a text region already does.

Measured on the hand-drawn invoice fixture with real Docling: **15 cells reported, 0
mapped before, 15 mapped after**, each with a unique locator name and its own bounding box.
The one blank grid position is deliberately NOT mapped — no value crosses from it — and
stays visible as a `Cell` on the table.

**Two silent gaps found while closing it, both now stated rather than omitted:** a
capture-fidelity mismatch recorded nothing in `confidence_scores` (so the name appeared on a
match and vanished on a mismatch, indistinguishable from no human note at all), and a
missing field raised a marker with no reliability entry beside it.

**A latent defect found by a red test:** `model_dump_json()` on any artifact carrying a
stated absence raised `PydanticSerializationError`. It **pre-dated** the four states —
Amendment 6's single sentinel had it too — and stayed invisible because no artifact carrying
one had ever been dumped. An artifact that can be built and not written down cannot be
audited (Law 43).

**What remains, and none of it lets a value cross without provenance:** O11 (the filter in
`pipeline.parsed_fields`), O12 (two `isinstance` call sites that should ask
`measurement_state`), O13 (NOT_APPLICABLE and FAILED have limited live producers — stated
rather than manufactured), O14 (per-cell provenance reaches the artifact through
`detected_fields`, not through `DetectedTable`). All four are in
`docs/ARCHITECTURE_AMENDMENTS.md` Amendment 7.

### What closed, 2026-08-06 — each with its commit and its guarding test

| Mechanism | Fixed at | Guarding test |
|---|---|---|
| `pipeline.py:364` filtered out 100% of PDF text-layer regions before confidence saw them | `41b23e6` | `test_extracted_regions_hands_on_an_unscored_region_rather_than_filtering_it_out` (corrected at `d29985a` — its old premise asserted the drop as correct) |
| `RegionReading` could not represent read-but-unscored | `502e166` | `tests/unit/test_input_engine_confidence.py`, three states pinned by name |
| `parser_output()` unconditionally returned `detected_fields=()` — because nothing joined a NAME to a SCORE | `6b32425` (recovered), `41b23e6` | `tests/unit/test_input_engine_pipeline_redteam.py` — 1081 lines, new. **Currently RED for an unrelated reason: F-025** |
| Engine 1 **raised** where its contract says **emit** — a business failure was indistinguishable from a crash | `1e65b91` | `test_a_document_engine_1_cannot_read_stops_the_run_loudly`, rewritten stricter at `b3c1b51`: four claims where there was one |

**The false number is gone.** `reliability_information` used to publish *"0 of 0 region(s)
reader attempted"* for a document holding three. Measured before and after, same input:

```
with the filter     region_readings 0    markers 0    "0 of 0 region(s) reader attempted"
without it          region_readings 3    markers 3    "0 of 3 ... 3 read but carry no score"
```

Three real `UncertaintyMarker`s that `_unscored_region_markers` was already built to emit
had never reached the artifact. That is `ENGINE_1_ARCHITECTURE.md` P-F3, concealed
uncertainty, and Law 24, a fabricated denominator. Both are now carried. **No score is
invented** — `extraction_confidence` stays exactly `reader`'s `None`.

### What WAS still open — the record as it stood before Amendment 7

> **Everything from here to the end of this entry is the diagnosis as written on
> 2026-08-06 BEFORE the owner ruled.** It is kept because the mechanism it names is what
> the fix had to satisfy, and because the *"Tables are unchanged and unclaimed"* paragraph
> below is one layer off the real cause — see "What closed the last of it" above, which
> corrects it. **Nothing below is current status.**

**The text-layer path still emits values with no per-field confidence.** Measured at HEAD
`e921c3c`, by the test written to catch exactly this, which is **RED**:

```
tests/integration/test_engine1_end_to_end.py
  ::test_every_extracted_value_that_crosses_the_boundary_carries_source_confidence_and_uncertainty

FAILED: 5 extracted values crossed the Input -> Understanding boundary inside
extracted_text while detected_fields is empty, so not one of them carries a
source location, a confidence or an uncertainty marker of its own.
```

That is a **correct test failing against a real defect**, not a wrong expectation. It must
not be eased (Law 4, §J.4).

**Why it cannot be closed by an engineer.** `Provenance.confidence` is mandatory and
`accountant_dad.confidence.Confidence` has no member meaning *not measured*. `1.0000` is
the forbidden default (`ENGINE_1_INPUT_ENGINE_RULES.md:625`); `0.0000` is a lie the other
way; none of the sixteen `ENGINE_1_CONFIDENCE_PARAMETERS.md` entries covers this case, so
the number cannot be looked up either. Closing it means an **absent-measurement state on a
frozen P2 schema** — a §M amendment, mirroring the `measurement.AbsentType` precedent that
resolved F-005. **Owner's decision.**

**Tables are unchanged and unclaimed.** `parser.Cell` knows its row, its column and its
box; it does not know it holds an amount, and no sub-engine scores it. `parser_output`
still returns `detected_tables=()` for exactly the reason it used to return no fields.

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
| **Status** | ✅ **CLOSED 2026-08-06** · `839645a` + the `pyproject.toml` declaration |
| **Found** | 2026-08-06 |

**Permanent fix — LANDED.** `pyproject.toml` now declares every third-party module Engine
1 imports **at module scope**, each pinned to the version already in
`requirements-engine1.txt`, copied character for character, none chosen here:
`pydantic`, `opencv-python`, `numpy`, `pymupdf`, `pillow`. Deliberately **not** declared:
`docling`, `pypdfium2`, `torch`, `transformers`, `paddleocr` — those resolve through
`require_module()` and `importlib.import_module()` *inside a function*, so the package
imports without them, and making them install-time requirements would put ~2 GB of ML
wheels behind `import accountant_dad` to no purpose.

**Guarding test — `tests/unit/test_declared_dependencies.py`, 337 lines, new.** It derives
the module-scope import set **structurally from the code** and fails naming anything
imported but undeclared. A hand-maintained list would drift; a derived one cannot.

**The one `.github` line, approved by the owner 2026-08-06 and reported before and after.**
`.github/workflows/quality.yml:42`:

```
-  /tmp/fresh/bin/pip download --quiet --dest dist pydantic==2.12.3
+  /tmp/fresh/bin/pip download --quiet --dest dist dist/accountant_dad-*.whl
```

The gate pre-downloaded only `pydantic`, so an offline `--no-index` install could not
resolve the rest. Reading the closure from the wheel's own metadata means this line never
goes stale again when a dependency changes. **One line, no other change.**

**Original description, kept.**

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
| **Status** | ✅ **CLOSED 2026-08-06** · the guard now reads code, by AST |
| **Found** | 2026-08-06 |

**Permanent fix — LANDED.** `tests/unit/test_package.py` grew by 408 lines and now parses
every Engine 1 module with `ast` instead of inspecting filenames. Three new tests, each
naming what it proves:

```
test_engine_1_reaches_for_nothing_outside_its_own_boundary
test_engine_1_imports_no_ai_vendor_package
test_engine_1_defines_no_accounting_or_tax_computation_identifier
```

The helpers `imported_names`, `_dynamic_import_target` and `declared_identifiers` walk
`ast.Import`, `ast.ImportFrom`, `ast.Call` (so `importlib.import_module("x")` is caught
too), `ast.FunctionDef`, `ast.ClassDef`, `ast.Name`, `ast.Attribute`, `ast.arg`,
`ast.keyword` and `ast.alias`. `gst_rates.py` full of tax logic no longer passes because it
is spelled innocently — it is refused on what it *contains*.

**The honest limit is stated in the fix, not papered over.** No static check can prove the
absence of accounting reasoning. These three prove specific, checkable things: no
cross-boundary import, no AI vendor package, no accounting or tax identifier declared. They
do not prove the general claim, and the file says so.

**Original description, kept.**

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
| **Status** | 🔄 **HALF CLOSED 2026-08-06** · the guard exists; the unpinned tree does not |
| **Found** | 2026-08-06 |

**What closed — the metadata-vs-runtime hole.** `5066576` and `202bed4` landed
`tests/unit/test_runtime_library_versions.py` (434 lines, new) and
`tools/ci/assert_imports_match_pins.sh`. The guard asserts the version the **imported
library reports about itself** (`cv2.__version__`), not the version
`importlib.metadata` claims, so the exact `5.0.0.93` / `4.10.0` divergence this entry
demonstrated now fails a test. `tests/unit/test_runtime_library_versions.py:360` also
asserts that packages which must be **absent** really are absent.

**What is still OPEN, and it is the larger half.** 151 of 175 packages unpinned, no
lockfile, no hashes; `pydantic` pinned in `requirements-ci.txt` and unpinned in
`requirements-engine1.txt`, so the version of the library that validates every artifact
still depends on manifest install order. `rapidocr` still arrives transitively through
`docling`, a second OCR engine against `TECHNOLOGY_STACK.md`'s one-tool-per-capability
lock. None of that is fixed by a version assertion.

### THREE MORE HOLES, MEASURED AND CLOSED — 2026-08-06, commit `a467bb2`

**1. A shadow outside site-packages defeated BOTH guards.** Every check in
`assert_imports_match_pins.sh` and `tests/unit/test_runtime_library_versions.py` imported
a module and then asked it what version it was. Neither asked **where it came from**. So a
file `cv2.py` earlier on `sys.path` than site-packages, containing one line
`__version__ = "5.0.0"`, satisfied everything. Measured, both directions:

```
with the shadow planted on PYTHONPATH:
  assert_imports_match_pins.sh (at HEAD)  -> exit 0
     "every pinned distribution is installed, unshadowed, and imports at its pin"
  test_runtime_library_versions.py        -> 9 passed
after the fix:
  assert_imports_match_pins.sh            -> exit 1, naming the exact file
  test_runtime_library_versions.py        -> 2 failed, 9 passed
  shadow removed                          -> exit 0 / 11 passed   (no false positive)
```

This is not a contrived path: five CI jobs run with `PYTHONPATH=tools/ci:src`, so those
two directories already outrank every installed package. Closed by a site-location check
in both guards.

**2. A pinned distribution could pass with ZERO of its versions actually verified.**
`__version__` was treated as the rule rather than a convention. `pypdfium2` — an Engine 1
library `parser.py` loads — exposes no `__version__`; it exposes `PYPDFIUM_INFO`. All four
of its modules printed *"(exposes no `__version__`)"* and the run still reported success,
having verified nothing about its version. The shell guard now searches the same attribute
list the unit test already used, so `pypdfium2` reports `5.12.1` against its pin. The run
now also prints how many pins rest on **metadata alone** — 4 of 22 (`mypy`,
`pytest-randomly`, `ruff`, `types-PyYAML`), which genuinely ship no runtime version.
Reported, not refused: refusing them would fail a correct environment.

**3. 13 installed distributions are reachable from no manifest at all.** Independently
re-measured; the same 13 this entry recorded, all from the OCR tree:

```
aistudio-sdk  bce-python-sdk  crc32c  future  imagesize  modelscope  modelscope-hub
prettytable  py-cpuinfo  pycryptodome  python-bidi  ruamel-yaml  ujson
```

Auditing manifests proves things about what was **asked for**. Nothing asked what is
actually **there**. `tools/ci/audit_dependency_manifests.py --orphans` now walks the
installed dependency graph from the pinned roots and names whatever falls outside it. It
is reachability, not membership — demanding that every installed package be pinned would
fail every correct environment.

### THE KNOWN SCOPE HOLE — `dependency scan` audited one manifest of three

`.github/workflows/security.yml:99-145` runs pip-audit against `requirements-ci.txt` and
`pyproject.toml`. It has **never** run against `requirements-engine1.txt` or
`requirements-engine1-ocr.txt`, which four other CI jobs install. Six pinned
distributions, `torch` among them, entered every CI environment with zero advisory
scanning:

```
docling==2.118.0   transformers==5.8.1   torch==2.13.0
torchvision==0.28.0   timm==1.0.28   pypdfium2==5.12.1
```

**Tooling built, and it runs:** `tools/ci/audit_dependency_manifests.{py,sh}` derives the
manifest set by walking the tree — never a written-down list, because a list in a workflow
is the same defect one level out — audits every one, then verifies against the filesystem
that the loop actually covered them all. Measured end to end at `a467bb2`:
**3 files, 24 pins, no known vulnerabilities.**

**Still open:** the workflow does not call it yet. `.github/**` is not modified by this
workstream; the exact one-step wiring is in the handover report.

**Original description, kept.**

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
| **Severity** | **HIGH** — re-rated 2026-08-06. It was worse than this entry said |
| **Status** | ⬜ OPEN · the guard is fixed; the OCR path is still unproven on CI |
| **Found** | 2026-08-05 |

### CORRECTION, 2026-08-06 — those 11 tests had never run ANYWHERE

This entry described a deliberate, bounded gap: 11 tests skip **on CI** and run locally in
a separate environment. The second half was false.

```python
# the guard, as written
[name for name in ("paddleocr", "paddlepaddle") if find_spec(name) is None]
```

`find_spec` takes a **module** name. `paddlepaddle` is a **distribution** name; the module
it installs is `paddle`. Measured with `paddlepaddle 3.3.1` actually present:

```
find_spec("paddlepaddle")  ->  None    # the distribution is not importable by that name
find_spec("paddle")        ->  a spec
```

So the guard reported *missing* in **every possible environment**, including the OCR venv
built specifically to run them. **The 11 tests had never executed on any machine** — the
documented workaround in this entry could not have worked, and nobody noticed because a
skip is green.

**Fixed at `202bed4`.** `tests/unit/test_input_engine_reader.py:89` now reads
`("paddleocr", "paddle")`, with the distribution-vs-module distinction written down at
`:80` so it is not re-derived. `tools/ci/run_ocr_tests.sh:318,329` states the same rule and
resolves an isolated interpreter for the OCR stack.

**What this does NOT fix.** Whether those 11 tests now *pass* is **UNMEASURED** — they have
never run, so there is no prior result to compare against, and CI still does not install
the OCR stack. **The claim in the next paragraph stands unchanged: no OCR accuracy claim is
provable.**

**The class, not the instance.** A skip guard is a test that can only be green. Nothing in
the suite asserted the guard's own premise, so a guard that always fired was
indistinguishable from a guard that never needed to. Same shape as F-018: a thing that
passes its own tests and is never actually exercised.

**Original description, kept.** 11 of `reader`'s tests exercise real PaddleOCR recognition.
PaddleOCR cannot share an environment with `requirements-engine1.txt` (F-002), so it lives
in `requirements-engine1-ocr.txt` and **is not installed on CI**. Those 11 tests skip there.

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

## D1 – D4 · The four `cleaner` defects — recorded here because the source already cites them

| | |
|---|---|
| **Severity** | HIGH — all four destroyed document content and reported that they had not |
| **Status** | ✅ **ALL FOUR CLOSED 2026-08-06**, each with a red-team test |
| **Found** | 2026-08-06, red-teaming `cleaner` (task T-022) |

**Why this section exists at all — a dangling-citation defect.** `cleaner.py` cites
`KNOWN_FAILURES.md` **D2** (`:446`), **D3** (`:212`, `:1227`) and **D4** (`:709`), and the
red-team suite cites **D1**. **None of those IDs existed in this file.** Four IDs referenced
from production source pointed at nothing. They are recorded here under the IDs the code
already uses, so the citation resolves without touching code. *(Naming note: every other
entry here is `F-nnn`. These are `D-n` because the source picked that prefix first and one
source of truth beats a tidy prefix — Law 19.)*

### The single class, named once

**A destructive step or its own audit consulted the rule that caused the damage.** Each
defect is the same shape wearing different clothes: the figure that would report a loss was
computed from the same criterion that produced the loss, so it could only ever report
success. `cleaner.py:18` states it — *"it checks the box against the rule that drew the
box"* — and `:1327`, *"reported full retention, twice over, because the audit consulted the
[same rule]."*

### The four

| ID | Defect | Measured |
|---|---|---|
| **D1** | The crop discards every mark Otsu does not call ink. A faint GSTIN line — 4080 pixels, 30 grey levels darker than the paper, plainly readable — leaves the page, and the module reports `ink_kept_by_crop = 1.0` and *"the cleaned representation is the safer basis for reading"* | RMS contrast rose 57.66 → 90.92, as though the page had been improved |
| **D2** | `ink_lost_to_denoise` is a **net difference of two counts**, not the ink lost. Erasure in one place cancels against accretion in another | reported **−0.014868** while 1094 ink pixels were erased and a decimal point was wiped out — at `max_ink_loss_fraction = 0.0`, the strictest value the setting accepts |
| **D3** | A multi-page scanned PDF reports **page one only**. The same two pages in the opposite order produce the opposite `preservation_status` | the reported quality is a property of **page order**, not of the document. Every page after the first contributes no evidence |
| **D4** | `_to_grey` discards the alpha channel, so a document whose visible content lives in alpha flattens to one grey | a stamp of **40320 visible pixels** and a fully transparent canvas both flattened to a constant page, standard deviation **0.0**, every measurement reporting zero loss |

### The fixes, and what guards them

`tests/unit/test_input_engine_cleaner_redteam.py` — **1053 lines, new**, 22 tests, all
green. Each attack was kept **pointed at the defect rather than retired with it**: where a
fix made the original attack unconstructible, the test was rewritten to hold **both** halves
— the damage must not recur, **and** the figure that would report it must remain able to.

- **D1** — the box is drawn from the line profiles and the retention counted at Otsu's
  split, so the two are no longer the same rule. Measured at commit `1e0df65`: a 600×900
  scan at sigma 14, printed body 46800 ink pixels plus a 3×3 margin mark 480 rows below —
  `ink_kept_by_crop = 0.9998077292828302`, which is `46800/46809` to the bit. The same page
  without the mark returns exactly `1.0` on all 14 seeds tried. **Half one alone would pass
  against a retention hardwired to 1.0; that is why half two is not optional.**
- **D2** — a net count replaced by a count of what was actually erased.
- **D3** — `Marker.page` added (`cleaner.py:215`), one-based, so every measurement carries
  the page it was taken on. `cleaner.py:386` **raises** rather than falling back to page one
  for a multi-page scan it cannot handle.
- **D4** — `_composite_over_paper` (`cleaner.py:700`) flattens four channels **onto the
  page** instead of discarding alpha. *"A transparent pixel is not black and it is not 'no
  information': it is the page showing through."*

**Proven by breaking the code four ways** and re-running the D1 test: retention hardwired to
1.0 → RED; box drawn from the Otsu mask that audits it → RED; `preservation_status` stops
reading the retention → RED; `kept_by_second_crop` dropped from the product → **SURVIVES**.

**The survivor is recorded, not papered over.** Across 28 pages spanning 0–12° of skew and
sigma 0–20, the second crop's factor was 1.0 on every one, because rotation's interpolation
smooths the page and lowers the line profile's allowance. **No page is known that kills it,
and none was invented to.**

**A stale header was corrected too** (`1e0df65`). The file said eight tests are red and
supposed to be. All 22 are green. *A file whose header says its reds are expected is a file
where a real red gets waved through* — Law 12 failing by way of a comment.

---

## F-024 · The repository does not build at HEAD

| | |
|---|---|
| **Severity** | **CRITICAL** — Law 1, keep the repo buildable always. The whole suite cannot collect |
| **Status** | ⬜ **OPEN** · introduced by HEAD itself |
| **Found** | 2026-08-06, running the suite to verify what the documents claim |

**Measured at commit `e921c3c` — LOCAL ONLY — NOT AUTHORITATIVE, but decisive:**

```
$ pytest tests/
ERROR tests/unit/test_conformance_registry.py
E   ImportError: cannot import name 'Exclusion' from 'accountant_dad.conformance'
!!!! Interrupted: 1 error during collection !!!!
1 error in 10.71s
```

**Root cause.** `e921c3c` — *"conformance: a crash is not an enforcement, and every
prohibition is now accounted for"* — designed `Exclusion` and shipped everything around it:
the module docstring explains it at `conformance.py:100`, the `Uncovered` enum that gives it
its reasons is defined at `:148`, and `test_conformance_registry.py:74` imports it. **The
dataclass itself was never written.** Verified: `dir(accountant_dad.conformance)` returns
`Attribution, Enforcement, Finding, NegativeControl, PHASES, Prohibition, Registry,
Uncovered, attribute` — no `Exclusion`. Its parent `b3c1b51` does not import the name, so
the commit introduced the break.

**Impact.** A collection error is not one red test — **nothing runs**. Every other result in
this file measured at HEAD had to be taken with this file excluded, which is stated wherever
such a number appears. Purging `__pycache__` does not change it; this is not the stale-`.pyc`
trap recorded in `PROGRESS.md`.

**Why no gate caught it.** The commit was never pushed (F-026). CI has judged nothing after
`f31e3cd`.

**Permanent fix.** Write the `Exclusion` dataclass the docstring, the enum and the test all
already describe, or remove the import. **Not chosen here — this file changes no code.**

**SYMPTOM RESOLVED after `e921c3c`.** Measured on `a501a69`: `Exclusion` is defined at
`conformance.py:236`, and the suite collects. **LOCAL ONLY — NOT AUTHORITATIVE.**

### PREVENTION — `tools/ci/unresolved_symbols.py`, added on top of `a501a69`

The symptom was patched; nothing stopped it recurring. Four things referred to `Exclusion`
and **only one of them — the import — was an executable claim that it exists.** A docstring
cannot be wrong; an enum member is not a reference; and under `from __future__ import
annotations` every annotation is an unevaluated string. So the only load-bearing check was
reached by RUNNING the suite, which is exactly what had stopped working.

**The transform (Law 53).** *"Does the suite collect?"* is answered by collecting — minutes,
and on failure one line about one file. *"Does every `from accountant_dad… import X` have an
X?"* is a question about TEXT: parse every module, collect what each binds in module scope,
check every import against that table.

| | |
|---|---|
| **Guarded by** | `tests/unit/test_unresolved_symbols.py` — 14 tests, including the `Exclusion` shape reproduced from the module as it shipped |
| **Scope, measured on `a501a69`** | 111 files across `src/`, `tests/`, `tools/ci/`; 43 first-party modules |
| **Also checks** | every `__all__` entry resolves to a definition — an exported symbol cannot exist without an implementation |
| **Proven to fail** | injecting `from accountant_dad.conformance import GhostSymbol` into `identity.py` reported `src/accountant_dad/identity.py:132 … GhostSymbol — imported, but nothing in that module defines it at module scope`; injecting a phantom MODULE reported `no such module in the first-party package`. Both reverted |
| **What it adds over collection** | names EVERY offender at once instead of the first, in milliseconds, and sees an unresolved name in a module **no test imports yet** — which collection can never reach |

---

## F-025 · One signature change, 39 red tests, two files that were never told

| | |
|---|---|
| **Severity** | HIGH — 39 of the 40 failures at HEAD are this one cause |
| **Status** | ⬜ **OPEN** |
| **Found** | 2026-08-06 |

**Measured at commit `e921c3c`** — full suite, `test_conformance_registry.py` excluded
because it cannot collect (F-024). **LOCAL ONLY — NOT AUTHORITATIVE:**

```
17 failed · 2565 passed · 11 skipped · 23 errors      273.97s
```

Forty failures and errors. **Thirty-nine are one line:**

```
TypeError: run() missing 1 required keyword-only argument: 'recorded_at'
```

`pipeline.run` gained a required keyword-only `recorded_at` (`pipeline.py:903`). `b3c1b51`
fixed the Application Layer's side of that call — *"two agents changed opposite sides of the
same call and neither saw the other"* — but two test files were never updated:

```
tests/unit/test_input_engine_pipeline_redteam.py   occurrences of "recorded_at": 0
tests/unit/test_input_engine_ablation.py           occurrences of "recorded_at": 0
tests/unit/test_input_engine_pipeline.py           occurrences of "recorded_at": 24  <- updated
tests/integration/test_engine1_end_to_end.py       occurrences of "recorded_at": 4   <- updated
```

**Root cause.** Both unupdated files were recovered at `211c6b0` — *"recover 10 red-team and
integration files from the interrupted session"* — from a session that **predates** the
signature change. That commit says outright: *"15 of these assertions are RED against real
defects… NOT pushed until the code is fixed."* The count has since grown to 39 and the cause
is no longer a real defect in the product; it is a mechanical signature mismatch.

**Impact.** 1081 lines of pipeline red-team tests and 631 lines of ablation tests — the
tests that guard F-012's `reader → parser` pipe and Engine 1's identity-leak boundary — are
**not running at all.** They cannot fail, so they prove nothing.

**The class.** Recovered work carries the contract it was written against. Recovery-not-
restart (D-006) is still correct, but an inherited file is untrusted until it has been run
against the *current* signature, not merely committed.

**Permanent fix.** Pass `recorded_at` in both files. **Not done here — this file changes no
tests.**

**SYMPTOM RESOLVED after `e921c3c`.** Measured on `a501a69`: every `pipeline.run` call site
passes `recorded_at`, and the full suite runs 3350 passed / 11 skipped. **LOCAL ONLY — NOT
AUTHORITATIVE.**

### PREVENTION — `tools/ci/signature_drift.py`, added on top of `a501a69`

Passing `recorded_at` in two files fixed those two files. Nothing compares a call against
its callee, so the next signature change lands the same way. `mypy` does compare them, but
only through an import it can resolve, and these files reach `pipeline` through fixtures
and helpers it cannot follow.

**The transform (Law 53).** *"Does every test still run?"* needs the whole suite, takes 245
seconds, and presupposes the suite collects — which under F-024 it did not. *"Does every
call's argument list bind to its callee's parameters?"* is arithmetic over two parse trees.

| | |
|---|---|
| **Guarded by** | `tests/unit/test_signature_drift.py` — 21 tests, including the exact `run(intake, identity=…, settings=…)` call the two stale files wrote |
| **Scope, measured on `a501a69`** | 882 checked call sites under `tests/`, 91 distinct callees, of which **28 are `pipeline.run`** — the function this failure was about |
| **Proven to fail** | adding a required keyword-only parameter to `config.load_confidence_parameters` reported **82 stale call sites**, each with file, line, callee and `missing a required keyword-only argument: 'recorded_at'`. Reverted |
| **Mutation-safe by construction** | signatures are built from the AUTHORED `def`, never `inspect.signature`. Under `mutmut run` the live function is a dispatcher taking `(*args, **kwargs)`, which binds ANY call — an `inspect`-based version would report green on a tree full of stale call sites at exactly the moment the tree is most rewritten |
| **Conservative where it cannot be exact** | a call using `*args`/`**kwargs`, or made through a rebound name, is declined rather than guessed, and `unchecked()` reports why. A missed check is a gap; a WRONG check is a false alarm, and a gate that cries wolf is a gate somebody weakens (§J.4) |
| **Deliberately out of scope** | classes. A dataclass's or Pydantic model's `__init__` is generated, not authored, so there is no `def` to read and guessing one would produce exactly those false alarms |

**The class this closes, stated generally (L-012).** Recovered work carries the contract it
was written against. Recovery-not-restart (D-006) is still correct; the missing half was
that an inherited file is untrusted until it has been checked against the CURRENT
signature, not merely committed. That check is now mechanical.

---

## F-026 · Twenty-four commits carry zero CI evidence

| | |
|---|---|
| **Severity** | HIGH — Law 44. Nothing after `f31e3cd` has been verified anywhere that counts |
| **Status** | ⬜ **OPEN** |
| **Found** | 2026-08-06 |

**Measured 2026-08-06 against the GitHub API:**

```
origin/ci/mutation-runs   f31e3cd
local HEAD                e921c3c        24 commits ahead
GET /commits/0babf47/check-runs   422  "No commit found for SHA"
GET /commits/e921c3c/check-runs   422  "No commit found for SHA"
```

**What that costs.** `src/` moved **+2591 / −300** lines and `tests/` **+13335 / −148**
after `7e0efe2`, and **not one line of it has been judged by CI.** Every gate result in this
repository — mutation, coverage, typecheck, the lot — belongs to `f31e3cd` or earlier. Under
Law 56 those numbers are EXPIRED, and under Law 44 there is no replacement, only
**UNMEASURED**.

**This is deliberate in part and not in whole.** `211c6b0` explicitly committed red work so
it would survive an interruption and stated it was *not* to be pushed until fixed — that is
the right call (D-006). But the branch has since accumulated fixes that *are* finished and
are equally unverified, and the two are now indistinguishable from outside.

**Permanent fix.** Fix F-024 and F-025 so the suite is green locally, then push and let CI
judge it. **Merge is not discussable until every mandatory gate is at or above its threshold
(Law 55), and at HEAD not one of them has a current value.**

---

## F-027 · A locked document is append-only after its last cited line, and nothing says so

| | |
|---|---|
| **Severity** | LOW — no wrong output. It silently constrained where a specification could be edited |
| **Status** | ✅ **CLOSED** · fixed at the root; the coordinate is gone from every identity |
| **Found** | 2026-08-06, adding the membership test that closed F-010 |
| **Fixed** | 2026-08-06 · **UNMEASURED on GitHub — PENDING CI** (Law 44, Law 56) |

**`conformance_registry.py` pins conformance predicates to LINE NUMBERS in the locked
documents**, and `test_the_identifier_carries_the_line_its_source_names` requires the line
to appear in **both** the predicate's identifier and its source, so the two cannot drift.
`test_every_quote_is_still_on_the_line_it_cites` then re-reads the file and fails if the
sentence moved.

**The consequence nobody wrote down: inserting a paragraph into a locked document breaks
tests that have nothing to do with the paragraph.** Measured at `a482ad6`, adding ~50 lines
to `ENGINE_1_INPUT_ENGINE_RULES.md` §7:

```
FAILED test_every_quote_is_still_on_the_line_it_cites[ENGINE_1:569/absent-zero-and-unreadable-stay-distinct]
FAILED test_every_quote_is_still_on_the_line_it_cites[ENGINE_1:626/every-uncertainty-marker-carries-a-reason]
```

**Renumbering is not the cheap fix it looks like.** The line number is part of the
predicate's *identity*, and that identity is quoted in prose across the repository. Moving
`626` to `654` would leave six citations pointing at the wrong sentence:

```
src/accountant_dad/artifacts/evidence.py:83          src/.../input_engine/cleaner.py:213
src/accountant_dad/engines/input_engine/confidence_report.py:79
tests/unit/test_evidence.py:722                      tests/unit/test_input_engine_cleaner.py:718
tests/unit/test_input_engine_parser.py:431,603
```

So a documentation edit forces a rename across `src/` and four test files, or it does not
happen. **In practice `ENGINE_1_INPUT_ENGINE_RULES.md` is append-only after line 626** —
its last cited line — and nothing in the repository states that.

**Workaround taken at the time.** The membership test was placed at **§9A**, after §9, the
first position that moved no cited line. **`src/` was not touched.** That workaround is now
obsolete — §9A may sit anywhere, and so may anything else.

**Root cause, stated as a class.** *A stable identifier was built out of a volatile
coordinate.* A line number identifies a position, not a sentence. A sentence does not own
its line number — **the lines above it do** — so any identity derived from it is
invalidated by edits it has nothing to do with.

**Why it was possible, past the immediate cause.** `conformance.py` did not merely permit
the fragile form, it **required** it. `_must_name_a_line()` raised unless a source
contained `:` and a number, so every citation in the repository was *obliged* to be the
shape that breaks. The checker and the citation then shared the same coordinate system —
`_line()` read by ordinal index and the quote test compared text on that index — so
neither could see the other's mistake, and no test ever edited a document. The repository
had already solved this exact problem once, in `tools/evidence/verify.py`, which addresses
a passage by *(document, section, normalised quote)* with a containment proof and no line
numbers at all. Law 15 — reuse before building — is the rule that would have prevented it.

---

### The fix — content-addressed citations

A citation is now `document#words@digest`:

```
docs/SYSTEM_INVARIANTS.md#every-artifact-is-immuta@dd6776b727b3
─────────────┬───────────  ──────────┬───────────  ──────┬─────
        document        the clause's own words     SHA-256 over
                        (readable in a diff)      (section, clause)
```

Resolution searches the document for the line whose content hashes to that digest.
**The line number is not deleted, it is DEMOTED** — recomputed on every run, printed in
failure messages, asserted by nothing.

**The heading path is in the digest, and it is load-bearing.** Measured: **4 of 185** cited
clauses are not unique by their own words. `docs/SYSTEM_BOUNDARIES.md` states
`1. Create journal entries.` at two lines under an identical introducer
(`It **MUST NEVER**:`); they are two different rules — one binds the Understanding Engine,
one the Clarification Engine — separated only by the `##` heading above them. With the
heading hashed in, all 185 resolve uniquely. That coupling is the correct one: renaming a
section changes what the rules inside it govern, and it invalidates **only** the clauses
inside that section, never the rest of the file.

**Normalisation is whitespace and nothing else.** Deliberately narrower than
`tools/evidence/model.normalise`, which folds curly quotes, dashes and NFKC forms because
it reads PDF-extracted text. This reads markdown a human typed, where an em dash is a
character the author chose. Wording, casing, punctuation, digits and typography all still
have to match exactly.

**The class cannot recur.** `_must_be_content_addressed` and `_must_not_be_positional`
refuse a line-pinned source or identifier **at construction**, so such a citation cannot
reach the inventory to be tested at all. The old guard demanded the opposite; the new one
names F-027 in its error message.

### Evidence — both directions, on the real repository

`LOCAL ONLY — NOT AUTHORITATIVE` (Law 44). GitHub has not run this yet.

| Experiment | Before the fix | After |
|---|---|---|
| 3 lines inserted at `docs/SYSTEM_INVARIANTS.md:100` | **12 tests failed** | **0 failed** |
| 140 lines inserted at line 2 of **7** locked documents | not attempted — 1 document already broke it | **0 failed** |
| One cited sentence reworded (`immutable` → `mostly immutable`) | red | **red, 5 tests**, each naming the rule |

The third row is the one that matters as much as the first: content addressing must not
buy stability with tolerance. An edited, deleted, or re-sectioned clause resolves to
**nothing**, loudly.

**Mutation-proven (§J.5).** Six deliberate breaks of the fix — anchor ignoring the section,
normalisation folding case, either guard disabled, a fuzzy resolver matching on the
readable half alone, a heading anchored under itself — **all six caught**, each by a named
new test.

**Guarded by.** `test_a_paragraph_inserted_above_a_cited_clause_does_not_break_the_citation`
· `test_touching_the_cited_clause_itself_still_breaks_the_citation` (3 cases) ·
`test_no_citation_in_the_inventory_is_identified_by_a_line_number` ·
`test_no_clause_the_scanner_derives_is_identified_by_a_line_number` ·
`test_every_citation_resolves_to_exactly_one_clause` (185 cases) ·
`test_a_prohibition_pinned_to_a_line_number_is_refused` (3 cases) ·
`test_normalisation_folds_whitespace_and_nothing_else` (6 cases), and ten more.

**Residual, recorded not fixed.** ~1,126 `FILE.md:NNN` pointers remain in docstrings and
prose across `src/` and `tests/`. Those are **documentation, not identities** — nothing
resolves them, so none can redden a gate — and most live in files owned by other agents.
Out of scope here. If one is ever promoted to an identity — resolved, asserted, or used as
a key — it inherits this defect and needs its own entry.

---

## Closed

| ID | Title | Closed | Fix | Guarded by |
|---|---|---|---|---|
| **F-027** | A locked document is append-only after its last cited line | 2026-08-06 | Citations bind to CONTENT — `document#words@digest` over (heading path, clause). The line number is recomputed, printed, and asserted by nothing. 232 identities migrated; the fragile form is refused at construction | 17 tests, 6 mutations all caught. Both directions measured: 140 lines inserted across 7 locked docs → **0 failures**; one cited sentence reworded → **5 failures**. `LOCAL ONLY — NOT AUTHORITATIVE` |
| **F-010** | *"Exactly four sub-engines"* vs nine modules — and whether classification is authorised | 2026-08-06 | `13ce25d`, `38b97e3`, `a482ad6` — module ≠ sub-engine; membership test stated at §9A; Amendment 5; G9.5 revised. **No code changed** | `test_package.py` — four named tests, each mutated red first. Residual (a bare type reaching the artifact) tracked by `test_the_evidence_object_has_no_document_type_field`, open under F-018 |
| **F-003** | Stale duplicate carrying the inverted `worst_k` row | 2026-08-05 | Deleted after proving nothing depended on it and that its only unique line *was* the bug | — *(deletion; nothing to guard)* |
| **F-002** | Two OpenCV distributions in one environment | 2026-08-05 | OCR stack separated into its own manifest | ⚠️ downgraded to PARTLY RESOLVED — see F-023 |
| **F-012** | The pipeline is not a pipe | 2026-08-06 | `412eed6` (cleaner half) · `6b32425`, `41b23e6`, `d29985a` (reader→parser half) | `test_input_engine_pipeline.py`; the red-team half is **not running** — F-025 |
| **F-014** | The mutation gate no longer fits in 100 minutes | 2026-08-06 | `66ab8cd` — cap 500 min; a run finished in 3h 21m 01s @ `7e0efe2` | ❌ **none.** A CI `timeout-minutes` is config and no test asserts it — recorded as a finding (Law 3) |
| **F-020** | `pip install accountant-dad` ships an unimportable Engine 1 | 2026-08-06 | `839645a` + `pyproject.toml` declarations | `tests/unit/test_declared_dependencies.py` — derives the set from the code |
| **F-021** | The build freeze checks filenames, not code | 2026-08-06 | AST-based guard | `test_package.py` — three named AST tests |
| **D1–D4** | The four `cleaner` content-destruction defects | 2026-08-06 | `1e0df65`, `590c6bb` and the recovered `wip` commits | `test_input_engine_cleaner_redteam.py` — 22 tests, all green |

---

## F-026 · A cleaned scan is not byte-reproducible — the PDF file identifier

| | |
|---|---|
| **Severity** | LOW — no content is affected, and no reading changes |
| **Status** | ⬜ OPEN · recorded, deliberately not fixed |
| **Found** | 2026-08-06, by a byte comparison in the F-017 one-path test |

**Description.** Cleaning the SAME scanned PDF twice does not produce the same bytes.

**Measured**, on a 400x200 one-page scan at 150 dpi, commit `a967a46`: two payloads of
identical length — 5465 bytes — differing in exactly **58** of them, every one inside
`trailer <</ID[...]>>`. The rasters are `np.array_equal`. The cause is PyMuPDF writing
a fresh random file identifier on every save.

**Impact.** None on any reading: nothing in this repository reads `/ID`, and
`CLAUDE.md`'s standing rule is explicit — *"IDENTITY ≠ INTELLIGENCE. IDs identify
objects. They never influence reasoning."* The real cost is that a byte-for-byte
determinism check over a cleaned PDF fails for a reason that has nothing to do with
cleaning, which is how it was found: it cost one red test before it was diagnosed.

**Workaround.** Compare rasters, or compare payloads only up to the trailer.

**Permanent fix.** Making the identifier deterministic is a decision about PDF output
nobody has asked for, and `docs/TECHNOLOGY_STACK.md` locks the backend. Recorded rather
than fixed (`CLAUDE.md` §E.7): it was found while doing something else and is outside
that change's mission.

**Guarded by** `test_a_rebuilt_scan_differs_only_in_the_pdf_file_identifier_never_in_a_
pixel`, which asserts the exact SHAPE of the difference — identical rasters, identical
length, and every differing byte after the trailer — so the day a rebuild starts
differing in a pixel, or before the trailer, it goes red instead of reading as the same
known-harmless noise.

---

## F-028 · A cleaned scan comes back `render_dpi / 96` times its original page size

| | |
|---|---|
| **Severity** | HIGH — every `SourceLocation` read from a cleaned scan is in the wrong coordinate space |
| **Status** | ⬜ OPEN · recorded, deliberately not fixed (`CLAUDE.md` §E.7 — found while evaluating F-001 backends, outside that mission) |
| **Found** | 2026-08-06, probing whether a candidate PDF backend preserves page geometry |

**Description.** `cleaner._pdf_rebuilt_from_cleaned_pages` renders each page at
`render_dpi`, cleans the pixels, re-encodes with `cleaner._encode_png`, and hands the
list to `pdf_backend.pdf_of_page_images`. The rebuilt document's pages are **not** the
size the original's were.

**Measured**, `LOCAL ONLY — NOT AUTHORITATIVE`, commit `fd479eb`, through the real
`accountant_dad.pdf_backend` and the real `cv2.imencode` call, on a one-page 595 x 842 pt
PDF:

| render_dpi | rendered raster | PNG carries a `pHYs` chunk | rebuilt page | scale |
|---|---|---|---|---|
| 150 | 1240 x 1755 px | no | 930.0 x 1316.2 pt | **1.563x** |
| 200 | 1653 x 2339 px | no | 1239.8 x 1754.2 pt | **2.084x** |
| 300 | 2480 x 3509 px | no | 1860.0 x 2631.8 pt | **3.126x** |
| 400 | 3306 x 4678 px | no | 2479.5 x 3508.5 pt | **4.167x** |

The scale is exactly `render_dpi / 96` in every row.

**Root cause.** PyMuPDF recovers a page's size from the PNG's embedded resolution and
falls back to 96 dpi when there is none. `pdf_backend.render_page_png` DOES embed it —
its PNGs report `dpi=(199.9996, 199.9996)` at `dpi=200` — but `cleaner._encode_png` uses
`cv2.imencode(".png", image)`, and OpenCV's PNG encoder writes no `pHYs` chunk. The
resolution is therefore lost between rendering the page and rebuilding it, in the one
step between them.

**Impact.** `reader.py:358-368` emits every `SourceLocation` in PDF points read from the
document it was given. A cleaned scan re-read downstream carries locations scaled by
`render_dpi / 96` against the original the human would check them on. Nothing in the
pipeline compares the two, so nothing rejects it. This is the silent direction: the
numbers stay positive, stay on the right page, and stay in plausible units.

Bounded, and the bound matters: only the **scanned** branch reaches here.
`cleaner._clean_pdf` passes a PDF with a text layer straight through
(`cleaner.py:1076-1078`), so a born-digital invoice is untouched.

**Workaround.** None in place. Nothing currently asserts the rebuilt page size.

**Permanent fix — not an engineer's call, and it is two decisions.** Either
`_encode_png` writes the resolution it rendered at, or `pdf_of_page_images` takes the DPI
as an argument instead of inferring it from the image. The second changes a signature in
the file F-001's containment is built on; the first changes what `cleaner` writes. Both
touch behaviour the owner has not been asked about, and F-017 — the entry this sits under
— is already **BLOCKED on an owner decision (§M)** about the same code path.

**What would guard it.** A test that renders a page at two different DPIs, rebuilds, and
asserts the rebuilt page size equals the ORIGINAL page size in both — which fails today
at every DPI other than 96. Not added here: writing a red test into the suite would break
the build for a defect this task was not authorized to fix.
