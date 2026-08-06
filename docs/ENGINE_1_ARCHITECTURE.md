# Engine 1 — Input Engine: Build Architecture

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md), and to the level-2 locks
> ([`MVP_ARCHITECTURE.md`](MVP_ARCHITECTURE.md) · [`DATA_FLOW.md`](DATA_FLOW.md) · [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) ·
> [`ENGINE_RESPONSIBILITIES.md`](ENGINE_RESPONSIBILITIES.md) · [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md)).
> **Where this document contradicts any of them, this document is wrong.**
>
> **Status: DRAFT — NOT FROZEN.** Two sections block the freeze: **G2** has no number, and **G10** carries eleven unresolved conflicts.
> By [`SYSTEM_INVARIANTS.md:32`](SYSTEM_INVARIANTS.md) *"conflicts are resolved before the specification is written, never during propagation"* —
> so §G10 is the section to read first, and the one that decides when the rest may be locked.

---

## What this document is, and what it is not

`CLAUDE.md` §F fixes the order: **Architecture → Blueprint → Code.** Engine 1 was released for implementation by
**Amendment 3, 2026-08-05** (`CLAUDE.md` §P), and code is being written now. No per-build architecture existed. This closes that gap.

**It is not a second specification.** [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) is locked and remains the
deeper authority on Engine 1's allowed and forbidden actions, output contract and failure behaviour
([`ENGINE_1_INPUT_ENGINE_RULES.md:10`](ENGINE_1_INPUT_ENGINE_RULES.md)). [`SYSTEM_INVARIANTS.md:20`](SYSTEM_INVARIANTS.md) forbids restating a
locked rule in different words — *"two differing statements of the same rule is a defect."* So this document **cites rather than
paraphrases**, and adds only what §G requires and no locked document supplies:

| §G section | What is genuinely new here |
|---|---|
| G2 | The **measurement method** for Engine 1's finish line. The number is not here and must not be. |
| G3 | Confidence recorded as the owner ruled it; the three Law 54 gaps named and left open |
| G5 | Prohibitions rewritten as **predicates a test can evaluate**, marked executable or review-only |
| G6 | The **four internal boundaries** — Engine 1 is the only engine with no `COMMUNICATION_RULES_*_INTERNAL.md` (§G10 C-8) |
| G7 | Invariants that bind Engine 1, ranked, with the precedence tie-breaks made explicit |
| G9 | The exhaustive non-goal list |
| G10 | Every promise already made about Engine 1 by a locked document, checked one at a time |

Everything else is a pointer. A pointer is not laziness — it is the only way one rule stays one rule.

---

# G1. Mission

> **Engine 1 converts a raw accounting artifact into structured, traceable evidence whose stated uncertainty is honest.**

Locked wording: [`ENGINE_1_INPUT_ENGINE_RULES.md:40`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`ENGINE_RESPONSIBILITIES.md:28`](ENGINE_RESPONSIBILITIES.md). The question it answers is *"what information exists in the document?"*
and the question it does not answer is *"what does this transaction mean?"*
([`ENGINE_1_INPUT_ENGINE_RULES.md:26-34`](ENGINE_1_INPUT_ENGINE_RULES.md)).

The asymmetry at [`ENGINE_1_INPUT_ENGINE_RULES.md:647`](ENGINE_1_INPUT_ENGINE_RULES.md) is the mission restated as a scoring rule, and it
is the sentence to build against:

```
a low-confidence extraction, honestly marked      = SUCCESS
a confident extraction that quietly guessed       = FAILURE, even when the guess was right
```

**This is one build.** It is not two. Extraction and confidence estimation are not separable — a reading without its uncertainty is
not evidence ([`ENGINE_1_INPUT_ENGINE_RULES.md:245`](ENGINE_1_INPUT_ENGINE_RULES.md)).

---

# G2. Measurable finish line

## ⬜ AWAITING THE OWNER'S NUMBER

**No number is recorded here, and none may be inferred.** Law 52 requires a number with a unit before work starts; Law 24 forbids
fabricating one; standing rule 10 forbids the engineer choosing it. `CLAUDE.md` §E.3 makes *setting a measurable target* one of the
four things that must be **asked**, not decided.

### The question, in the form it must be answered

> **At what field-level extraction accuracy, on which document class, is Engine 1 finished?**

```
Engine 1 is finished when field-level extraction accuracy ≥  ______ %
on document class                                            ______
measured by the method below.
```

**Owner of the answer: the user.** Nobody else can supply it.

### Why the number cannot be derived from anything already locked

Four separate attempts were made to find it. All four fail, and the reasons are worth recording because each one is also a gap:

| Attempt | Where it fails |
|---|---|
| Read it off the golden dataset | The golden labels are **entry-level, four fields** ([`ACCOUNTING_DEFINITIONS.md:40-47`](ACCOUNTING_DEFINITIONS.md), [`GOLDEN_DATASET.md:25`](GOLDEN_DATASET.md)). **No field-level extraction ground truth exists anywhere in the repository.** |
| Derive it from the ceiling rule | [`MEASUREMENT_FRAMEWORK.md:70-75`](MEASUREMENT_FRAMEWORK.md) gives a dual target — `≥ 80% of frozen ceiling` **and** `≥ absolute floor`. The ceiling is for **entries**, not extractions, and the absolute floor is *"set at sign-off"*, which has not happened. |
| Take it from the definitions | [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) defines **Correct** for an *entry* (§1) and **Understanding** for a *Business Understanding Object* (§2). **There is no definition of "correct" for a Document Evidence Object.** |
| Take it from the per-engine table | [`PHASE_REPORT_TEMPLATE.md:74-78`](PHASE_REPORT_TEMPLATE.md) has an `E1` row, but it is *"Phase 5 onward"* and carries no threshold. |

**This is itself a Law 54 gap** and is filed as conflict **C-1** in §G10.

### The measurement method — specified in full, so only the value is missing

Specifying *how* is the engineer's job. It is done here, completely, so that supplying the number is a one-line decision.

**Unit.** `field-level extraction accuracy` = `correctly extracted fields ÷ fields present on the document`, expressed as a percentage,
per document, then reported as the worst run over repeats and as a count with its denominator
([`EVALUATION_PROTOCOL.md:189`](EVALUATION_PROTOCOL.md) — *"90% on 16 documents is 14 of 16"*).

**A field is correctly extracted iff both hold:**

| Component | Rule | Reason |
|---|---|---|
| **Value** | Exact string match against the human re-keying, after Unicode NFC normalisation only. No numeric tolerance, no whitespace collapse beyond NFC. | Mirrors [`ACCOUNTING_DEFINITIONS.md:49`](ACCOUNTING_DEFINITIONS.md) — *no partial credit, no rounding tolerance*. A near-miss on a GSTIN is a wrong GSTIN. |
| **Location** | The emitted source location overlaps the human-marked region. | [`ENGINE_1_INPUT_ENGINE_RULES.md:239-245`](ENGINE_1_INPUT_ENGINE_RULES.md) — a value without its location *"is not evidence and must not be emitted."* A right value at the wrong place is an unchecked value. |

⬜ **`overlap` needs a rule and a number** — IoU threshold, or containment of the value's bounding box. Also awaiting the owner. Recorded rather than chosen.

**The three-state rule is scored, not collapsed.** [`ENGINE_1_INPUT_ENGINE_RULES.md:569`](ENGINE_1_INPUT_ENGINE_RULES.md) requires
`absent`, `zero` and `unreadable` to stay distinguishable. They are therefore scored as a **3×3 confusion matrix**, not as right/wrong:

```
                      human says
                absent   zero   unreadable
    system  absent   ✓      ✗        ✗
      says  zero     ✗      ✓        ✗
       unreadable    ✗      ✗        ✓
```

`system=zero, human=absent` is the cell that becomes a wrong entry downstream. It is reported on its own line and never netted
against the diagonal — the same treatment `EVALUATION_PROTOCOL.md:151-160` gives over-asking versus silent-wrong.

**Ground truth.** Human re-keying by a labeler meeting [`ACCOUNTING_DEFINITIONS.md:26-30`](ACCOUNTING_DEFINITIONS.md), blind to the
system's output, transcribing every field present on the artifact. **Two independent labelers**, as
[`MEASUREMENT_FRAMEWORK.md:55`](MEASUREMENT_FRAMEWORK.md) requires — inter-rater disagreement on a *character* is the extraction task's
own noise floor, and a system error below it is unattributable ([`MEASUREMENT_FRAMEWORK.md:77`](MEASUREMENT_FRAMEWORK.md)).

**Document class.** Reported **per class, never pooled**. Pooling lets clean digital PDFs carry photographed handwriting.
The classes come from the golden set: digital purchase invoices (`GOLDEN_DATASET.md:29`), photographed invoices (`:30`),
poor-lighting photographs (`:38`). ⬜ **Which class the finish line applies to is part of the owner's answer.**

**Run conditions — all inherited, none new.** Worst of 3 repeats ([`MEASUREMENT_FRAMEWORK.md:87`](MEASUREMENT_FRAMEWORK.md)) ·
spread > 2 documents is a failure regardless of score (`:102`) · caching asserted off (`:106`) · pre-registered before the run
([`MEASUREMENT_FRAMEWORK.md:13`](MEASUREMENT_FRAMEWORK.md)) · **GitHub Actions only** ([`MEASUREMENT_FRAMEWORK.md:35`](MEASUREMENT_FRAMEWORK.md),
Law 44) · every number carries its CI run URL and workflow run ID (`:45`).

**Baseline.** Stated against the strong baseline, never in isolation ([`MEASUREMENT_FRAMEWORK.md:151`](MEASUREMENT_FRAMEWORK.md)).
Engine 1's strong baseline is the **regex field extraction** half of `MEASUREMENT_FRAMEWORK.md:139` — the vendor→ledger and GST rate
tables belong to Engine 3 and are not Engine 1's bar.

### One structural fact about Engine 1's numbers that no other engine shares

[`MEASUREMENT_FRAMEWORK.md:178-201`](MEASUREMENT_FRAMEWORK.md) gives every engine two numbers — *isolated* (fed the **golden** upstream
artifact) and *contributed* (fed the **real** one) — and `inherited damage = isolated − contributed`.

**Engine 1's upstream artifact is the raw document, which is identical in both passes.** Therefore, for Engine 1 and only Engine 1:

```
isolated  ≡  contributed
inherited damage  ≡  0        by construction, not by achievement
```

A report showing `E1 inherited damage = 0.00` says nothing. **The row must be annotated as structurally zero**, or a reader will
read it as evidence that nothing upstream is hurting Engine 1 — a claim the number cannot make, because there is no upstream.

### Bounds that already bind Engine 1, without sign-off

| Bound | Value | Source |
|---|---|---|
| Wall clock, **whole pipeline**, per document | ≤ 60 s | [`MEASUREMENT_FRAMEWORK.md:323`](MEASUREMENT_FRAMEWORK.md) |
| Token cost, **whole pipeline**, per document | ≤ ₹5 | [`MEASUREMENT_FRAMEWORK.md:324`](MEASUREMENT_FRAMEWORK.md) |
| Engine 1's **share** of either | ⬜ **UNKNOWN — never allocated.** `processing_budget_ms` is `UNSET` ([`ENGINE_1_CONFIDENCE_PARAMETERS.md:50`](ENGINE_1_CONFIDENCE_PARAMETERS.md)) | filed as **C-9** |

---

# G3. Undefined terms, defined

Law 54: an undefined term in a specification is a false statement waiting to be discovered. Engine 1 depends on seven terms. Four
are settled by an existing locked document. **One is settled by the owner's ruling and recorded below. Three are open and are not
resolved here** — [`ENGINE_1_CONFIDENCE_PARAMETERS.md:54-63`](ENGINE_1_CONFIDENCE_PARAMETERS.md) already names them as gaps, and
inventing a resolution would be the exact failure Law 54 exists to stop.

## G3.1 Confidence — settled by the owner, binding, and narrower than most readers expect

**The ruling, as it governs Engine 1:**

| # | The rule | What it forbids |
|---|---|---|
| 1 | **Confidence is the estimated uncertainty of an OBSERVATION.** | Treating it as a probability that the *business fact* is true. It is a property of the measuring apparatus, not of accounting — [`ACCOUNTING_DEFINITIONS.md:227`](ACCOUNTING_DEFINITIONS.md). |
| 2 | **Confidence is never permission to post.** | Any code path where a confidence value alone decides that something proceeds. Permission is Engine 5's, decided before execution — [`SYSTEM_INVARIANTS.md:205`](SYSTEM_INVARIANTS.md) INV-8. |
| 3 | **There is NO document-level confidence scalar.** | A single number on the Document Evidence Object. The Confidence Report carries **per-field** scores and nothing above them — [`ENGINE_1_INPUT_ENGINE_RULES.md:222-226`](ENGINE_1_INPUT_ENGINE_RULES.md). |
| 4 | **In this build, confidence gates NOTHING.** | Every threshold behaviour in `ENGINE_1_CONFIDENCE_PARAMETERS.md` #1–#12. Engine 1 v1 runs in **measurement mode**: it records every signal and acts on none — [`ENGINE_1_CONFIDENCE_PARAMETERS.md:20-24`](ENGINE_1_CONFIDENCE_PARAMETERS.md). |

**Canonical home.** [`CONFIDENCE_SPECIFICATION.md`](CONFIDENCE_SPECIFICATION.md) records this ruling system-wide and states the same
four positions. The table above is Engine 1's **application** of it, not a second statement of it — where the two differ, that
document governs the ruling and this one governs only how Engine 1 obeys it.

Rule 4 is not a preference and not this document's addition. [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) states it as an
absolute: *"until it passes this test, confidence is an ordinal ranking, not a probability, and it may gate NOTHING."* The test is
`accuracy(top tercile) − accuracy(bottom tercile) ≥ 0.30` ([`MEASUREMENT_FRAMEWORK.md:261`](MEASUREMENT_FRAMEWORK.md)), and it needs
labelled volume that does not exist until P6 ([`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md), *CONFIDENCE — Phase 6 onward*).

### Rule 3 is a design decision with a proof behind it, not a simplification

[`ENGINE_1_CONFIDENCE_PARAMETERS.md:84-125`](ENGINE_1_CONFIDENCE_PARAMETERS.md) records the argument. Summarised, not restated:
on an ordinal scale only order statistics are comparison-meaningful (Marichal & Mesiar 2009, Cor. 5.7), which eliminates mean,
product, Bayesian pooling and Dempster–Shafer; and `min ≥ t` is *identically* `∀i : cᵢ ≥ t`, so the scalar adds nothing per-field
floors do not already carry, while creating a false affordance inviting someone downstream to average it
([`ENGINE_1_CONFIDENCE_PARAMETERS.md:120-125`](ENGINE_1_CONFIDENCE_PARAMETERS.md)).

**Consequence for this architecture:** the Document Evidence Object carries no document score, and no downstream engine may compute
one from what Engine 1 emits. Four locked documents nevertheless consume a scalar called *Evidence Reliability* from Engine 1 —
filed as **C-2**, the largest conflict in §G10.

### One wording difference, recorded rather than smoothed

`src/accountant_dad/confidence.py` quotes the owner's ruling as *"the system's degree of confidence in an artifact's correctness"*
and *"must not be used as the **sole** gating criterion."* The ruling governing this build says **estimated uncertainty of an
observation** and **gates nothing**. These are not the same rule: *"not the sole criterion"* permits confidence to be one input to a
gate; *"gates nothing"* does not.

**For Engine 1, the narrower reading governs**, because [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) independently
forbids any gating and outranks a docstring. Recorded here so the difference is visible rather than resolved by whoever reads which
file first. Filed as **C-3**.

## G3.2 The three open Law 54 gaps — stated, not resolved

Each is a **decision the owner must make**, not a number that measurement can produce.
[`ENGINE_1_CONFIDENCE_PARAMETERS.md:65`](ENGINE_1_CONFIDENCE_PARAMETERS.md): *"until #13 has a rule, #1–#12 cannot be calibrated."*

| Gap | Term | What is missing | Why measurement cannot supply it | Blocks |
|---|---|---|---|---|
| **#4** | **Risky — of a field** | [`ENGINE_1_INPUT_ENGINE_RULES.md:610`](ENGINE_1_INPUT_ENGINE_RULES.md) grants `confidence` the action *"highlight risky fields"* and the output contract carries `risky fields` ([`:226`](ENGINE_1_INPUT_ENGINE_RULES.md)). **No document says what makes a field risky.** | The obvious rule — `confidence < X` — **is a confidence gate**, forbidden by [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) until separation passes. So the shortcut is closed by construction, not by preference. | `risky_fields` cannot be populated by any rule. Engine 1 v1 emits it **empty**, and that emptiness must be stated, not look like a clean document. |
| **#12** | **Capture fidelity — who computes it** | [`ENGINE_1_INPUT_ENGINE_RULES.md:624`](ENGINE_1_INPUT_ENGINE_RULES.md) and [`SUB_ENGINE_RESPONSIBILITIES.md:90`](SUB_ENGINE_RESPONSIBILITIES.md) both require `confidence` to score it. [`ENGINE_1_INPUT_ENGINE_RULES.md:283`](ENGINE_1_INPUT_ENGINE_RULES.md) *illustrates* 100%. **An illustration is not a measurement**, and the schema puts the number on the provenance of the supplied text. | There is nothing to measure. A typed note either arrived intact or did not; "how faithfully stored" has no scale until someone defines what partial storage means. | The provenance `confidence` field on `Human Business Context` and on every `Structured Metadata` fact. |
| **#13** | **How confidences combine** | [`ACCOUNTING_DEFINITIONS.md:227`](ACCOUNTING_DEFINITIONS.md) defers to [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10, which defines the **gate** confidence must pass and the six layers — **but no rule that produces a value** from cleaner/reader/parser signals. | The research eliminated four of six candidate methods on measurement-scale grounds; choosing between the two survivors (`min` · `worst_k`) is a **policy** question about how much compensation to buy, and needs labelled data ([`ENGINE_1_CONFIDENCE_PARAMETERS.md:108-118`](ENGINE_1_CONFIDENCE_PARAMETERS.md)). | Calibration of #1–#12. **Not** blocked: recording raw per-signal scores, which is what v1 does. |

**Architectural consequence, stated so it cannot be quietly worked around.** Engine 1 v1 emits per-field, per-region and per-cell
scores **as recorded signals**, combines nothing, thresholds nothing, and flags nothing. A pull request introducing a combination
rule, a risky-field rule, or a capture-fidelity formula before these three are answered is **out of scope by definition**, whatever
its quality.

## G3.3 Terms already settled elsewhere — pointers only

| Term | Settled in |
|---|---|
| **Correct** — of an entry | [`ACCOUNTING_DEFINITIONS.md:38-73`](ACCOUNTING_DEFINITIONS.md). Engine 5 judges; Engine 1 never asserts it. |
| **Safe** — of an entry to post | [`ACCOUNTING_DEFINITIONS.md:126-143`](ACCOUNTING_DEFINITIONS.md). Engine 5's. Engine 1's contribution is condition 2 — traceability to an evidence reference. |
| **Doubt** · **Uncertainty** | [`ACCOUNTING_DEFINITIONS.md:192-221`](ACCOUNTING_DEFINITIONS.md). Engine 3 produces doubt, Engine 4 triages. **Engine 1 produces neither** — it produces *uncertainty markers*, a different and lower-level thing (§G9). |
| **Qualified accountant** | [`ACCOUNTING_DEFINITIONS.md:26-30`](ACCOUNTING_DEFINITIONS.md). Needed by G2's ground truth. |

---

# G4. Components and ownership

**Exactly four sub-engines, plus the parent.** No sub-engine is added, removed or merged
([`ENGINE_1_INPUT_ENGINE_RULES.md:365-367`](ENGINE_1_INPUT_ENGINE_RULES.md)). **No assembler sub-engine exists, and none may be added**
([`SUB_ENGINE_RESPONSIBILITIES.md:28`](SUB_ENGINE_RESPONSIBILITIES.md)).

```
                    Raw Artifact  +  optional Human Business Description
                                       │
                    ┌──────────────────┼───────────────────────────────┐
                    │            INPUT ENGINE (parent)                 │
                    │                                                  │
                    │   cleaner ──► reader ──► parser                   │
                    │      │           │          │                     │
                    │      └───────────┴──────────┴──► confidence       │
                    │                                      │            │
                    │        ┌───────────┬─────────┬───────┘            │
                    │        ▼           ▼         ▼                    │
                    │           mechanical assembly only                │
                    └──────────────────┬───────────────────────────────┘
                                       ▼
                            Document Evidence Object
```

Assembly diagram source: [`ENGINE_1_INPUT_ENGINE_RULES.md:371-382`](ENGINE_1_INPUT_ENGINE_RULES.md).

## One problem each — INV-10, applied

[`SYSTEM_INVARIANTS.md:229`](SYSTEM_INVARIANTS.md): *no responsibility exists in two places; no component owns two problems.*

| Component | Owns exactly one problem | Never touches |
|---|---|---|
| `cleaner` | **Physical readability** of the artifact | Content. It alters presentation only. |
| `reader` | **Getting the characters off the page**, with their locations | Structure, meaning, or whether a character is plausible |
| `parser` | **Recovering the document's own structure** — fields, tables, rows | Values. It maps what `reader` produced; it never re-reads. |
| `confidence` | **Honest measurement of extraction trustworthiness** | The extraction itself. It cannot re-read, re-parse or correct. |
| **parent** | **Mechanical assembly** of four outputs into one artifact, and creation of the Document ID | The content of any of the four |

Full entries: [`SUB_ENGINE_RESPONSIBILITIES.md:30-90`](SUB_ENGINE_RESPONSIBILITIES.md). Deeper authority:
[`ENGINE_1_INPUT_ENGINE_RULES.md:416-627`](ENGINE_1_INPUT_ENGINE_RULES.md).

## Confidence has a single authority — the rule most easily lost in code

[`ENGINE_1_INPUT_ENGINE_RULES.md:109`](ENGINE_1_INPUT_ENGINE_RULES.md):

> `cleaner`, `reader` and `parser` emit **signals**. Only `confidence` turns signals into scores.
> **No other component — parent included — may raise or lower a confidence value.**

`reader`'s output contract names *"extraction confidence"* ([`ENGINE_1_INPUT_ENGINE_RULES.md:406`](ENGINE_1_INPUT_ENGINE_RULES.md)),
which reads like an exception and is not one. The authority table at [`:92`](ENGINE_1_INPUT_ENGINE_RULES.md) settles it: `reader`
determines *"extraction confidence **signals**."* **A per-region OCR score is a signal. Only `confidence` may name a number a
score.** This distinction must survive into the type system, or it will not survive at all.

## Creator and owner

| | |
|---|---|
| **Creator** of the Document Evidence Object | The **Input Engine parent** — not a sub-engine |
| **Owner** | The **Input Engine**, permanently ([`DATA_FLOW.md:320`](DATA_FLOW.md)) |

Engine 1 is the **only** engine where creator and owner are the same component. Engines 2, 3, 4 and 6 each have a sub-engine that
creates while the engine owns ([`DATA_FLOW.md:327-329`](DATA_FLOW.md)). This is a direct consequence of *"no assembler sub-engine
exists"* and is worth stating: a future refactor that introduces an `assembler` under Engine 1 would break `SUB_ENGINE:28`, not
merely rearrange code.

## What the parent is, exactly

[`SYSTEM_INVARIANTS.md:235`](SYSTEM_INVARIANTS.md): *"a parent engine assembles **mechanically**. It may combine, organize and
structure; it may never author, modify, approve, override or suppress a sub-engine's output."*

**Mechanical** is testable and is made so in §G5 (predicate **P-P1**): every value in the Document Evidence Object must be
byte-identical to the sub-engine output it came from, plus the identity envelope the parent is authorised to add.

---

# G5. Boundaries — what each component may never do

Absolute prohibitions, per component. Each carries a **predicate** written so a test can evaluate it.
[`MEASUREMENT_FRAMEWORK.md:308-315`](MEASUREMENT_FRAMEWORK.md) requires that anything not executable carries *the reason it cannot be
a predicate* and *a re-examination date* — so `EXEC` and `REVIEW` are marked, and no `REVIEW` entry is left without both.

## G5.1 `cleaner`

Source: [`ENGINE_1_INPUT_ENGINE_RULES.md:445-462`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`SUB_ENGINE_RESPONSIBILITIES.md:40-42`](SUB_ENGINE_RESPONSIBILITIES.md).

| ID | Prohibition | Predicate | Kind |
|---|---|---|---|
| **P-C1** | Never discards the original | The original artifact bytes are retrievable from the engine's output for every input, including inputs that failed | `EXEC` |
| **P-C2** | Never discards content it judges irrelevant, redundant or illegible | No cleaner operation is content-conditional: the operation set applied is a pure function of measured image properties, never of what was read. Assert the operation log contains no reference to extracted text | `EXEC` |
| **P-C3** | A **provided source passes through untouched** | For `source_type ∈ {Human, Structured Metadata}`, `cleaner_output == cleaner_input`, byte for byte | `EXEC` |
| **P-C4** | Never changes numbers or alters original meaning | Cannot be a predicate on an image: "the numbers are unchanged" needs a reading, and reading is `reader`'s. Enforced indirectly by P-C1 (the original survives) and by preservation status. **Re-examine when field-level ground truth exists (G2) — at that point, cleaned-vs-original extraction diff becomes executable.** Re-examination date: **at P1 completion** | `REVIEW` |
| **P-C5** | Never interprets | No cleaner code path imports, calls or reads anything under `parser`, `confidence`, or any engine ≥ 2 | `EXEC` |
| **P-C6** | Never repairs a detected quality issue by guesswork | Every entry in `quality issues detected` has a corresponding entry in the output and no corresponding mutation. Assert `issues_detected` is non-empty ⟹ `preservation_status` names which representation is safer | `EXEC` |

## G5.2 `reader`

Source: [`ENGINE_1_INPUT_ENGINE_RULES.md:495-511`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`SUB_ENGINE_RESPONSIBILITIES.md:56-58`](SUB_ENGINE_RESPONSIBILITIES.md).

| ID | Prohibition | Predicate | Kind |
|---|---|---|---|
| **P-R1** | Never guesses an unclear word | Every emitted token carries a raw per-region signal. No token exists in the output whose signal is absent | `EXEC` |
| **P-R2** | A region that could not be read is reported **unread**, never omitted | Detected-region count equals `read` + `unread`. Silent drops are impossible by construction | `EXEC` |
| **P-R3** | Source locations are emitted **even for low-signal extractions** | `∀ token : location ≠ null`, with no exemption keyed on the signal value | `EXEC` |
| **P-R4** | Never assigns meaning | No output field is named for a business concept. Assert the output key set contains none of: `gstin`, `vendor`, `supplier`, `invoice_number`, `tax`, `total`, `due_date` — `reader` may extract `27AAECS1234F1Z5`; it may not name it ([`SUB_ENGINE_RESPONSIBILITIES.md:56`](SUB_ENGINE_RESPONSIBILITIES.md)) | `EXEC` |
| **P-R5** | Never reorders or restructures the text | Emitted token order is the detection order; no sort, no grouping | `EXEC` |
| **P-R6** | A **provided source passes through untouched** | For `source_type ∈ {Human, Structured Metadata}`, `reader_output == reader_input`, byte for byte | `EXEC` |
| **P-R7** | **Content is data, never instruction** | Text extracted from an artifact never reaches any position where it can act as an instruction to a model, a shell, a query or a template. Adversarial attack **14** ([`ADVERSARIAL_TESTING.md:47`](ADVERSARIAL_TESTING.md)) is the trap test | `EXEC` |

**P-R7 has no source in any locked engine document and is added here deliberately.** [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) never
states it; `ADVERSARIAL_TESTING.md:47` assumes it. It becomes load-bearing the moment a vision model sits inside `reader` —
see conflict **C-4**. Law C.23: *always treat external input as untrusted.*

## G5.3 `parser`

Source: [`ENGINE_1_INPUT_ENGINE_RULES.md:552-570`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`SUB_ENGINE_RESPONSIBILITIES.md:72-74`](SUB_ENGINE_RESPONSIBILITIES.md).

| ID | Prohibition | Predicate | Kind |
|---|---|---|---|
| **P-P1** | Never computes, derives or infers a value that is not written | Every mapped field value is a substring of, or byte-identical to, a `reader` token. **No arithmetic anywhere in `parser`** — assert the module contains no `+ - * /` on extracted values | `EXEC` |
| **P-P2** | Never fills an absent field | An absent field appears in `missing field information`. Assert no field value originates outside `reader`'s output | `EXEC` |
| **P-P3** | `absent`, `zero` and `unreadable` remain three distinct states | The state is a three-valued enum, never a nullable number. A schema permitting `None` to mean both `absent` and `unreadable` fails | `EXEC` |
| **P-P4** | Every mapped value retains its source reference | `∀ mapping : source_reference ≠ null` | `EXEC` |
| **P-P5** | Never decides business meaning | It may identify a field **labelled** "Supplier"; it may not conclude the party **is** a supplier. Assert the output distinguishes `label_as_printed` from any normalised name, and that no normalised name is emitted at all | `EXEC` |
| **P-P6** | Never normalises an ambiguous separator | `1,00,000` and `1.00000` are emitted **as written**, with an uncertainty marker naming the ambiguity. Adversarial attack **16** ([`ADVERSARIAL_TESTING.md:49`](ADVERSARIAL_TESTING.md)) is the trap test | `EXEC` |
| **P-P7** | A **provided source receives no structure** | For `source_type = Human`, `parser` emits zero fields, zero mappings and zero missing-field entries | `EXEC` |
| **P-P8** | Never decides debit/credit, ledger, tax or transaction meaning | No `parser` module imports anything under `engines/accounting_engine/`, and no module under `input_engine/` is named for accounting, tax, LLM, brain or Tally. **Already enforced by an Amendment 3 guard test** (`CLAUDE.md` §P, guard 3) | `EXEC` |

## G5.4 `confidence`

Source: [`ENGINE_1_INPUT_ENGINE_RULES.md:614-627`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`SUB_ENGINE_RESPONSIBILITIES.md:88-90`](SUB_ENGINE_RESPONSIBILITIES.md).

| ID | Prohibition | Predicate | Kind |
|---|---|---|---|
| **P-F1** | Cannot re-read, re-parse or correct anything | Every value in `confidence`'s output that is not a score is byte-identical to its `cleaner`/`reader`/`parser` input | `EXEC` |
| **P-F2** | Cannot **increase** confidence without evidence | INV-2 makes this a **recalculation**, not a direction ([`SYSTEM_INVARIANTS.md:46`](SYSTEM_INVARIANTS.md)). The executable form: a score changes **only** when its input signal set changes. Fix the signals, re-run, assert byte-identical scores | `EXEC` |
| **P-F3** | Cannot **hide** uncertainty | Every uncertainty marker carries a reason string; markers are never dropped, summarised or deduplicated. Assert marker count out ≥ marker count in | `EXEC` |
| **P-F4** | Cannot use **business plausibility** as evidence | It measures extraction quality, not whether content makes commercial sense ([`SUB_ENGINE_RESPONSIBILITIES.md:88`](SUB_ENGINE_RESPONSIBILITIES.md)). No `confidence` input includes a field's *semantic* identity — only its extraction signals | `EXEC` |
| **P-F5** | Cannot reject a document or halt the pipeline | `confidence` has exactly one output path and no error path that terminates processing | `EXEC` |
| **P-F6** | For a provided source, scores **capture fidelity**, never truth | ⬜ **Cannot be a predicate — the term is undefined (G3.2 #12).** Until it is defined, `confidence` emits **no score** for a provided source rather than an invented one. Re-examination date: **at owner sign-off on gap #12** | `REVIEW` |
| **P-F7** | A human note never raises Evidence Reliability by existing | Run the pipeline with and without a Human Business Description on identical document bytes. **Assert every extracted-field score is byte-identical.** An ablation test, in the shape of [`MEASUREMENT_FRAMEWORK.md:313`](MEASUREMENT_FRAMEWORK.md) | `EXEC` |
| **P-F8** | **Gates nothing** (G3.1 rule 4) | No comparison of a confidence value against any constant or configured threshold exists anywhere in `input_engine/`. This is strictly stronger than [`ENGINE_1_CONFIDENCE_PARAMETERS.md:153-156`](ENGINE_1_CONFIDENCE_PARAMETERS.md), which forbids *hardcoded* thresholds; here **the comparison itself is forbidden**, configured or not | `EXEC` |

## G5.5 The parent Input Engine

Source: [`ENGINE_1_INPUT_ENGINE_RULES.md:97-105`](ENGINE_1_INPUT_ENGINE_RULES.md) ·
[`SYSTEM_BOUNDARIES.md:58`](SYSTEM_BOUNDARIES.md) · [`SYSTEM_INVARIANTS.md:235`](SYSTEM_INVARIANTS.md).

| ID | Prohibition | Predicate | Kind |
|---|---|---|---|
| **P-A1** | Never **overrides** a sub-engine output | Every leaf value in the Document Evidence Object is byte-identical to the sub-engine output it came from. **The parent's only additions are the identity envelope and the Document ID** | `EXEC` |
| **P-A2** | Never orchestrates, routes workflow, or retries | No parent code path starts another engine, reads transaction state, or re-invokes its own sub-engines. Workflow is the Application Layer's — INV-4 ([`SYSTEM_INVARIANTS.md:102`](SYSTEM_INVARIANTS.md)) | `EXEC` |
| **P-A3** | Never communicates with the user | Engine 1 has one outbound path and it goes to Engine 2 ([`COMMUNICATION_RULES_INPUT_ENGINE.md:24`](COMMUNICATION_RULES_INPUT_ENGINE.md)) | `EXEC` |
| **P-A4** | Never rejects a document or halts the pipeline | [`SYSTEM_BOUNDARIES.md:51`](SYSTEM_BOUNDARIES.md). Assert no code path returns a refusal | `EXEC` |
| **P-A5** | Never consults company master data, prior transactions, or any downstream engine | [`SYSTEM_BOUNDARIES.md:50`](SYSTEM_BOUNDARIES.md) · [`ENGINE_RESPONSIBILITIES.md:46`](ENGINE_RESPONSIBILITIES.md). No import of `brain`, `services.store`, or any engine ≥ 2. **Note the tension with INV-12 — conflict C-5** | `EXEC` |
| **P-A6** | Never sends a **conclusion** on the wire | The test at [`COMMUNICATION_RULES_INPUT_ENGINE.md:71`](COMMUNICATION_RULES_INPUT_ENGINE.md): *if a sentence could be wrong about the **business** rather than wrong about the **document**, it is an interpretation.* Partially executable via P-R4 and P-P5; the general form needs judgement. Re-examination date: **at P4, against the golden set** | `REVIEW` |
| **P-A7** | The **Document ID never influences anything** | Change the Document ID, re-run, assert output identical **outside the identity fields**. INV-9 · adversarial attack **19** ([`ADVERSARIAL_TESTING.md:52`](ADVERSARIAL_TESTING.md)) · [`EVALUATION_PROTOCOL.md:87`](EVALUATION_PROTOCOL.md). **Note: "byte-identical output" cannot mean the artifact itself, which contains the ID — conflict C-6** | `EXEC` |
| **P-A8** | Never merges extracted evidence with provided evidence | The Document Evidence Object holds `Structured Document` and `Human Business Context` as separate members. **No code path produces a value derived from both** ([`ENGINE_1_INPUT_ENGINE_RULES.md:233`](ENGINE_1_INPUT_ENGINE_RULES.md)) | `EXEC` |
| **P-A9** | Never assesses corroboration | `Corroborated` is emitted as `not assessed` for every fact, unconditionally ([`ENGINE_1_INPUT_ENGINE_RULES.md:295`](ENGINE_1_INPUT_ENGINE_RULES.md)) | `EXEC` |
| **P-A10** | Never rejects, decides or acts on a duplicate | The duplicate screen emits **a fact with provenance** and nothing else. INV-7 ([`SYSTEM_INVARIANTS.md:189`](SYSTEM_INVARIANTS.md)). Assert no code path branches on the screen result | `EXEC` |
| **P-A11** | Never rewrites the user's wording | `human_business_context.original_user_text == input_text`, byte for byte. Not tidied, corrected, summarised or normalised ([`ENGINE_1_INPUT_ENGINE_RULES.md:333`](ENGINE_1_INPUT_ENGINE_RULES.md)) | `EXEC` |
| **P-A12** | Never invents | The whole of §G5 in one line. Not a single predicate; it is the conjunction of all of them ([`ENGINE_1_INPUT_ENGINE_RULES.md:337`](ENGINE_1_INPUT_ENGINE_RULES.md)) | — |

**Review-only count: 3** (P-C4, P-F6, P-A6). Each carries a reason and a re-examination date, as
[`MEASUREMENT_FRAMEWORK.md:310`](MEASUREMENT_FRAMEWORK.md) requires. The list must shrink, not grow.

---

# G6. Contracts — what crosses each boundary

Engine 1 has **six** boundaries. One is already contracted, one is new-and-external, and **four are internal and have no contract
anywhere in the repository** — see conflict **C-8**.

## B0. Application Layer → Input Engine

Nine items. Source: [`APPLICATION_LAYER_CONTRACTS.md:20-31`](APPLICATION_LAYER_CONTRACTS.md).

| # | Item | Definition |
|---|---|---|
| 1 | Input artifact | Raw document(s) · **Transaction ID** · optional human business context |
| 2 | Output artifact | Document Evidence Object — **one per document** |
| 3 | Creator | Input Engine (parent) |
| 4 | Owner | Input Engine, permanently |
| 5 | Allowed transformation | The Application Layer may **route** the artifact and read its identity envelope to choose a state transition |
| 6 | Forbidden transformation | It may not interpret the document, pre-classify it, decide it is *"obviously"* an invoice, or add/infer/complete provenance ([`APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md:33-34`](APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md)) |
| 7 | Decision authority | The Application Layer decides **when** Engine 1 runs and **which** documents share a Transaction ID. Engine 1 decides extraction method, extraction confidence and document structure ([`DATA_FLOW.md:352`](DATA_FLOW.md)) |
| 8 | Uncertainty movement | **Inbound: none.** The Application Layer supplies no confidence, no assumption and no hint. It is forbidden from supplying a preference ([`APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md:37`](APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md)) |
| 9 | Failure movement | **Runtime** failure (crash, timeout) → nothing produced, Application Layer restarts. **Business** failure (unreadable, corrupt, zero-byte) → ⚠️ **contested — conflict C-7**. Two locked documents give opposite answers |

## B1. Input Engine → Understanding Engine

**Already contracted, with all nine items, at [`COMMUNICATION_RULES_INPUT_ENGINE.md:149-159`](COMMUNICATION_RULES_INPUT_ENGINE.md).**

It is **not restated here.** [`SYSTEM_INVARIANTS.md:20`](SYSTEM_INVARIANTS.md) forbids a second statement of the same rule in
different words, and [`DATA_FLOW.md:404`](DATA_FLOW.md) fixes *one contract per boundary*. Two additions this architecture makes,
neither of which changes the contract:

1. **Item 8 is the one that carries the G3 ruling.** *"Understanding confidence may never exceed the evidence reliability it
   received"* ([`COMMUNICATION_RULES_INPUT_ENGINE.md:158`](COMMUNICATION_RULES_INPUT_ENGINE.md)) must be read **per field**, because
   there is no document scalar (G3.1 rule 3). The worked example at
   [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:765-773`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) is per field and confirms this reading.
   Filed as **C-2**.
2. **Item 9 is Engine 1's whole failure model.** *"The Input Engine does not halt the pipeline. Unreadable regions, damaged
   artifacts and failed extractions cross the boundary **as low confidence and named uncertainty**, not as errors."* This is why
   Engine 1 has no error return type — see §G8.

## B2–B5. The four internal boundaries

**No `COMMUNICATION_RULES_INPUT_INTERNAL.md` exists.** Engines 2, 3, 4, 5 and 6 each have one; the contract table at
[`DATA_FLOW.md:390-402`](DATA_FLOW.md) has no *"Input, internal"* row. Defined here as an interim measure and filed as **C-8**;
the permanent home is a communication contract owned by Engine 1.

### B2. `cleaner` → `reader`

| # | Item | Definition |
|---|---|---|
| 1 | Input artifact | The raw artifact exactly as received |
| 2 | Output artifact | Cleaned document representation · quality issues detected · preservation status |
| 3 | Creator | `cleaner` |
| 4 | Owner | Input Engine |
| 5 | Allowed transformation | `reader` may **read** the cleaned representation, or the original where preservation status names it safer |
| 6 | Forbidden transformation | `reader` may not re-clean, re-orient, re-encode, or ask `cleaner` for a different rendering. **`reader` never re-invokes `cleaner`** |
| 7 | Decision authority | `cleaner` decides allowed transformations and whether preprocessing introduced risk. `reader` decides detected characters, regions and tables ([`ENGINE_1_INPUT_ENGINE_RULES.md:91-92`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 8 | Uncertainty movement | Quality issues cross as **evidence for `confidence`**, never as instructions to `reader` and never repaired ([`ENGINE_1_INPUT_ENGINE_RULES.md:462`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 9 | Failure movement | If cleaning may damage information, the **original** is preserved and marked. Nothing is dropped; `reader` receives both representations plus the status |

### B3. `reader` → `parser`

| # | Item | Definition |
|---|---|---|
| 1 | Input artifact | Cleaned document representation (+ original, + preservation status) |
| 2 | Output artifact | Raw extracted information · source locations · **extraction confidence signals** |
| 3 | Creator | `reader` |
| 4 | Owner | Input Engine |
| 5 | Allowed transformation | `parser` may **map** tokens into fields, identify relationships between them, and carry their locations forward |
| 6 | Forbidden transformation | `parser` may **not re-read** ([`ENGINE_1_INPUT_ENGINE_RULES.md:113`](ENGINE_1_INPUT_ENGINE_RULES.md)), not reorder tokens, not compute a value, not fill an absence |
| 7 | Decision authority | `reader` decides what characters exist and where. `parser` decides field mapping, detected relationships and missing fields |
| 8 | Uncertainty movement | An unclear token crosses **as unclear, with its signal**. An unread region crosses **as unread**. Locations cross even for low-signal tokens |
| 9 | Failure movement | A region `reader` could not read becomes, in `parser`, a field in `unreadable` state — **never `absent`, never `zero`** (P-P3) |

### B4. `{cleaner, reader, parser}` → `confidence`

| # | Item | Definition |
|---|---|---|
| 1 | Input artifact | All three outputs ([`ENGINE_1_INPUT_ENGINE_RULES.md:586-588`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 2 | Output artifact | Confidence scores · uncertainty markers · reliability assessment — together the **Confidence Report** ([`SUB_ENGINE_RESPONSIBILITIES.md:86`](SUB_ENGINE_RESPONSIBILITIES.md)) |
| 3 | Creator | `confidence` |
| 4 | Owner | Input Engine |
| 5 | Allowed transformation | Read the three outputs · detect uncertain extraction · score reliability · attach markers |
| 6 | Forbidden transformation | **Never re-read, re-parse or correct** (P-F1). Never use business plausibility (P-F4). Never combine per-field scores into a document scalar (G3.1 rule 3) |
| 7 | Decision authority | **`confidence` is the sole authority on any number called a score** ([`ENGINE_1_INPUT_ENGINE_RULES.md:109`](ENGINE_1_INPUT_ENGINE_RULES.md)). The other three own signals only |
| 8 | Uncertainty movement | This boundary is where a **signal** becomes a **score**. It is the only place in Engine 1 where that conversion is permitted, and the only place it may be tested |
| 9 | Failure movement | Where reliability cannot be established, confidence goes **down** — never up, never to a default *"good enough"* value ([`ENGINE_1_INPUT_ENGINE_RULES.md:625`](ENGINE_1_INPUT_ENGINE_RULES.md)) |

### B5. Four sub-engines → parent (assembly)

| # | Item | Definition |
|---|---|---|
| 1 | Input artifact | Four sub-engine outputs |
| 2 | Output artifact | **Document Evidence Object** — its only name ([`ENGINE_1_INPUT_ENGINE_RULES.md:257`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 3 | Creator | The **parent**. No assembler sub-engine exists ([`SUB_ENGINE_RESPONSIBILITIES.md:28`](SUB_ENGINE_RESPONSIBILITIES.md)) |
| 4 | Owner | The Input Engine, permanently |
| 5 | Allowed transformation | **Combine · organize · structure**, and add the identity envelope: Artifact ID · Version · Parent Artifact Version(s) · Transaction ID ([`DATA_FLOW.md:32`](DATA_FLOW.md)) · Document ID · source references |
| 6 | Forbidden transformation | **Author · modify · approve · override · suppress** any sub-engine output ([`SYSTEM_INVARIANTS.md:235`](SYSTEM_INVARIANTS.md)). Predicate **P-A1** |
| 7 | Decision authority | The parent decides **nothing about content**. Its only decisions are assembly order and Document ID creation ([`ENGINE_1_INPUT_ENGINE_RULES.md:95`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 8 | Uncertainty movement | Every marker and every score crosses intact. **The parent may not summarise the Confidence Report into a single figure** — the false affordance G3.1 rule 3 exists to prevent |
| 9 | Failure movement | If a sub-engine cannot complete, the parent produces **nothing**, never a partial artifact ([`SYSTEM_INVARIANTS.md:122`](SYSTEM_INVARIANTS.md)). Distinguished from a *business* failure in §G8 |

---

# G7. Invariants

Always true, at every moment, for every artifact Engine 1 produces. Ranked by precedence.
[`SYSTEM_INVARIANTS.md:26`](SYSTEM_INVARIANTS.md): **locks win** — a newer document never silently changes a locked one.

| # | Invariant | Rank | Source |
|---|---|---|---|
| **E1-I1** | Nothing is invented. Unclear ⟹ report uncertainty | 1 | [`SYSTEM_INVARIANTS.md:291`](SYSTEM_INVARIANTS.md) · [`ENGINE_1_INPUT_ENGINE_RULES.md:337`](ENGINE_1_INPUT_ENGINE_RULES.md) |
| **E1-I2** | Every fact carries its origin, permanently — six attributes, never merged | 1 | INV-11, [`SYSTEM_INVARIANTS.md:241`](SYSTEM_INVARIANTS.md) |
| **E1-I3** | Every emitted value carries **location + confidence + uncertainty**. A value without all three is not evidence and is not emitted | 1 | [`ENGINE_1_INPUT_ENGINE_RULES.md:245`](ENGINE_1_INPUT_ENGINE_RULES.md) |
| **E1-I4** | The Document Evidence Object is **immutable after creation**. Correction is a new version, created only by Engine 1 | 1 | INV-5, [`SYSTEM_INVARIANTS.md:142`](SYSTEM_INVARIANTS.md) |
| **E1-I5** | IDENTITY ≠ INTELLIGENCE. The Document ID influences nothing | 1 | INV-9, [`SYSTEM_INVARIANTS.md:215`](SYSTEM_INVARIANTS.md) |
| **E1-I6** | One concept, one owner. Only `confidence` scores; the parent assembles mechanically | 1 | INV-10, [`SYSTEM_INVARIANTS.md:229`](SYSTEM_INVARIANTS.md) |
| **E1-I7** | Screening is not deciding. The duplicate screen emits a **fact**, never a rejection | 1 | INV-7, [`SYSTEM_INVARIANTS.md:189`](SYSTEM_INVARIANTS.md) |
| **E1-I8** | Confidence changes only when **evidence** changes — recalculated, not directional | 1 | INV-2, [`SYSTEM_INVARIANTS.md:46`](SYSTEM_INVARIANTS.md) |
| **E1-I9** | Engine failure is not an artifact. A runtime failure produces **nothing** | 1 | INV-4, [`SYSTEM_INVARIANTS.md:122`](SYSTEM_INVARIANTS.md) |
| **E1-I10** | A human note is evidence, not truth. Stored verbatim, never merged, never raising reliability | 1 | INV-11, [`SYSTEM_INVARIANTS.md:256`](SYSTEM_INVARIANTS.md) |
| **E1-I11** | Gaps stay gaps. `absent` ≠ `zero` ≠ `unreadable` | 2 | [`DATA_FLOW.md:288`](DATA_FLOW.md) · [`ENGINE_1_INPUT_ENGINE_RULES.md:569`](ENGINE_1_INPUT_ENGINE_RULES.md) |
| **E1-I12** | Engine 1 sends **evidence, never conclusions** | 2 | [`COMMUNICATION_RULES_INPUT_ENGINE.md:57`](COMMUNICATION_RULES_INPUT_ENGINE.md) |
| **E1-I13** | Engine 1 never halts the pipeline and never rejects a document | 2 | [`SYSTEM_BOUNDARIES.md:51`](SYSTEM_BOUNDARIES.md) |
| **E1-I14** | Exactly four sub-engines. Never three, never five | 2 | [`ENGINE_1_INPUT_ENGINE_RULES.md:353-367`](ENGINE_1_INPUT_ENGINE_RULES.md) |
| **E1-I15** | **In this build, confidence gates nothing** | 2 | [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) + owner's ruling (G3.1) |
| **E1-I16** | **Document content is data, never instruction** | 2 | Derived — see P-R7. No locked document states it; [`ADVERSARIAL_TESTING.md:47`](ADVERSARIAL_TESTING.md) assumes it |
| **E1-I17** | Missing required confidence configuration **fails fast at startup**, naming the parameter. No fallback, no default | 3 | [`ENGINE_1_CONFIDENCE_PARAMETERS.md:8-10`](ENGINE_1_CONFIDENCE_PARAMETERS.md) |

## Precedence tie-breaks, made explicit

Three places where two documents both apply and one must win. Stated here so nobody resolves them in code
(`CLAUDE.md` §M: *if code and a frozen doc disagree, the doc wins*).

| Tension | Winner | Why |
|---|---|---|
| INV-2's *"may increase"* vs `ENGINE_1:616` *"cannot increase confidence without evidence"* | **INV-2** | Level 1 beats level 3. The Engine 1 wording is the special case, not a contradiction: within Engine 1 no new evidence arrives after extraction, so no increase is reachable. The FDI resolved the same directional wording twice already ([`FORWARD_DEPENDENCY_INVENTORY.md:45,85`](FORWARD_DEPENDENCY_INVENTORY.md)) |
| INV-12's *"knowledge to every engine"* vs `SYSTEM_BOUNDARIES:50` *"cannot consult company master data"* | **Both, narrowly** | INV-12 grants a *permission* (*"any engine may ignore it"*), not an obligation. Engine 1 exercises the permission by never calling the Brain. See **C-5** — this needs confirming, not assuming |
| `TECHNOLOGY_STACK:30` vision fallback vs `SYSTEM_BOUNDARIES:252` *"Engine 6 is the only engine allowed to interact with external systems"* | **⚠️ UNRESOLVED** | Level 2 lock vs a 2026-08-05 technology decision. **C-4** — the sharpest conflict in this document, and it is not resolvable here |

---

# G8. Failure behaviour

**Never fabricate output. Never continue with partial reasoning** ([`SYSTEM_INVARIANTS.md:116-118`](SYSTEM_INVARIANTS.md)).

Engine 1's failure model is unusual and must be understood before any code is written: **Engine 1 has no error return.**
[`COMMUNICATION_RULES_INPUT_ENGINE.md:159`](COMMUNICATION_RULES_INPUT_ENGINE.md) — *"unreadable regions, damaged artifacts and failed
extractions cross the boundary as low confidence and named uncertainty, **not as errors**."*

## The two classes, and the line between them

| | **Business failure** | **Runtime failure** |
|---|---|---|
| Owner | The sub-engine | The Application Layer |
| Example | Illegible photograph · unread region · absent field · ambiguous separator | Process crash · timeout · out of memory |
| Output | A **complete** Document Evidence Object recording low confidence and named uncertainty | **Nothing.** Never a partial artifact |
| Retryable | **No.** Re-running reasoning that already succeeded could produce a different conclusion from identical input, destroying reproducibility ([`APPLICATION_LAYER.md:276`](APPLICATION_LAYER.md)) | **Yes**, by the Application Layer |
| Source | [`APPLICATION_LAYER_FAILURE_MATRIX.md:32-33`](APPLICATION_LAYER_FAILURE_MATRIX.md) | [`SYSTEM_INVARIANTS.md:114-122`](SYSTEM_INVARIANTS.md) |

## Per component

| Component | Cannot complete ⟹ |
|---|---|
| `cleaner` | Preserve the original, mark uncertainty, record which representation is safer. **Never discard the original** ([`ENGINE_1_INPUT_ENGINE_RULES.md:455-462`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| `reader` | Emit unclear as unclear, unread as unread. **Locations emitted even at low signal** ([`:504-511`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| `parser` | Absent stays absent, in `missing field information`. Three states stay three ([`:563-570`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| `confidence` | Confidence goes **down**, with a reason on every marker. Never to a default ([`:620-627`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| parent | Any sub-engine that produced nothing ⟹ the parent produces **nothing**. INV-4 |

## The unresolved case — a zero-byte or corrupt file

Two locked documents give opposite instructions:

```
APPLICATION_LAYER_CONTRACTS.md:27   "a document that cannot be read produces an
                                     object recording that failure"
APPLICATION_LAYER.md:282            "Zero-byte file. Produces a Document Evidence
                                     Object recording the failure"

ADVERSARIAL_TESTING.md:44           attack 11 — "Empty / corrupt / zero-byte file"
                                     Must happen: Fails LOUDLY
                                     FAILS IF:    Empty artifact produced
```

Both are precedence level 2, so **precedence supplies no tie-break.** Filed as **C-7**. Until it is answered, Engine 1 must not
implement either branch — and a code author right now can pick either one and be defensibly wrong.

## What is preserved, and where restart happens

- **Preserved:** the original artifact bytes, always (P-C1) · every completed artifact ([`SYSTEM_INVARIANTS.md:118`](SYSTEM_INVARIANTS.md))
- **Reported:** the runtime failure, by the Application Layer, never by Engine 1
- **Restart point:** the last completed artifact. Engine 1 is the first stage, so its restart point is the raw artifact — which is
  why P-C1 is not a nicety but the recovery guarantee itself
- **Failure is as loggable as success** ([`SYSTEM_INVARIANTS.md:296`](SYSTEM_INVARIANTS.md))

---

# G9. What this build deliberately does NOT include

The section that makes scope creep unarguable. **Anything not named in G4 is out.**

## G9.1 Not Engine 1's, because it belongs to another engine

| Excluded | Owner | Source |
|---|---|---|
| Deciding transaction type · accounting treatment · ledger accounts · journal entries · tax rules | Engine 3 | [`ENGINE_1_INPUT_ENGINE_RULES.md:314-318`](ENGINE_1_INPUT_ENGINE_RULES.md) |
| Understanding business intent · interpreting what a field means · concluding a party is a supplier | Engine 2 | [`:319`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`SUB_ENGINE_RESPONSIBILITIES.md:56`](SUB_ENGINE_RESPONSIBILITIES.md) |
| Asking any question, accounting or otherwise | Engine 4 | [`:320`](ENGINE_1_INPUT_ENGINE_RULES.md) · [`COMMUNICATION_RULES_INPUT_ENGINE.md:141`](COMMUNICATION_RULES_INPUT_ENGINE.md) |
| Judging whether an uncertainty is **material** | Engine 4 `uncertainty_detection` | [`COMMUNICATION_RULES_INPUT_ENGINE.md:141`](COMMUNICATION_RULES_INPUT_ENGINE.md) |
| Deciding **economic** duplication | Engine 5 `duplicate_detection` | INV-7 · [`ENGINE_5_VALIDATION_ENGINE_RULES.md:411`](ENGINE_5_VALIDATION_ENGINE_RULES.md) |
| Assessing **corroboration** | Engine 2 | [`DATA_FLOW.md:573`](DATA_FLOW.md) |
| Aggregating several documents into one business event | Engine 2 | INV-3 · [`DATA_FLOW.md:617-621`](DATA_FLOW.md) |
| Any interaction with an external accounting system | Engine 6 | [`SYSTEM_BOUNDARIES.md:252`](SYSTEM_BOUNDARIES.md) |
| Creating the Transaction ID · routing · retrying · state transitions | Application Layer | INV-4 |

## G9.2 Not in this build, because it is architecturally impossible right now

| Excluded | Blocked by |
|---|---|
| **Any confidence threshold behaviour** — `ocr_region_accept` · `field_confidence_floor` · `document_confidence_floor` · `classification_accept` · `table_structure_accept` · `table_cell_accept` | [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) — confidence gates nothing until separation ≥ 0.30 |
| **A document-level confidence scalar**, and `document_score_rule` / `document_score_weights` / `worst_k` | G3.1 rule 3 · [`ENGINE_1_CONFIDENCE_PARAMETERS.md:120-125`](ENGINE_1_CONFIDENCE_PARAMETERS.md) |
| **`risky_fields` population** | Law 54 gap #4 (G3.2). The field exists and is emitted **empty** |
| **A capture-fidelity score** for provided sources | Law 54 gap #12 (G3.2) |
| **The Gemini Vision fallback** (`ocr_vision_fallback`) | Threshold `UNKNOWN` ([`TECHNOLOGY_STACK.md:35-38`](TECHNOLOGY_STACK.md)) **and** conflict C-4 |
| **Human-review routing** (`human_review_trigger`) | Engine 1 does not route (INV-4) and does not communicate with the user ([`COMMUNICATION_RULES_INPUT_ENGINE.md:24`](COMMUNICATION_RULES_INPUT_ENGINE.md)). See **C-10** |
| **Internal retry** (`retry_trigger`, `retry_max_attempts`) | A confidence gate (blocked above), **and** it introduces non-determinism into the one engine whose output must be reproducible. See **C-10** |
| **Any accuracy claim about Engine 1** | No ground truth, no ceiling, no G2 number. `CLAUDE.md` §P: *no accuracy claim before the ceiling exists* |

## G9.3 Deliberate non-goals, even when they become possible

| Excluded | Why, permanently |
|---|---|
| A single "document quality" score | Same false affordance as the document confidence scalar: it invites averaging and cross-document comparison on a scale that supports neither |
| Correcting a value the engine believes is wrong | [`SYSTEM_BOUNDARIES.md:48`](SYSTEM_BOUNDARIES.md) — *low confidence is reported, never repaired* |
| Discarding content judged irrelevant or illegible | [`SYSTEM_BOUNDARIES.md:49`](SYSTEM_BOUNDARIES.md). The engine does not get to decide what matters |
| Rewriting, tidying or normalising the human note | [`ENGINE_1_INPUT_ENGINE_RULES.md:333`](ENGINE_1_INPUT_ENGINE_RULES.md). Verbatim is the whole point |
| Merging document evidence with human evidence | [`:233`](ENGINE_1_INPUT_ENGINE_RULES.md). Merging destroys the only signal separating an observation from a claim |
| A Document Evidence Object holding several documents | INV-3, [`SYSTEM_INVARIANTS.md:94`](SYSTEM_INVARIANTS.md) — *never redesigned to hold several documents* |
| An `assembler` sub-engine | [`SUB_ENGINE_RESPONSIBILITIES.md:28`](SUB_ENGINE_RESPONSIBILITIES.md) |
| Handwriting *interpretation* as opposed to *extraction* | `reader` extracts handwriting ([`:492`](ENGINE_1_INPUT_ENGINE_RULES.md)); reading intent from it is Engine 2's |

## G9.4 Out of scope for this **document**

Amendment 3 authorised Engine 1 and nothing else. This architecture describes Engine 1 only. **Engines 2–6, accounting logic, tax
logic, AI/LLM calls and Tally posting remain frozen** (`CLAUDE.md` §P). Where §G10 finds a conflict inside another engine's
document, it is **named and left for its owner**, never fixed here.

## G9.5 Document-type detection — REVISED 2026-08-06, no longer open

> **This clause used to say document-type detection was "not authorised … out of scope until the owner rules."
> That was wrong when written and is corrected here.** The ruling it waited for already existed: `CLAUDE.md` §P
> **Amendment 3**, owner-approved 2026-08-05, names *"document classification"* among the capabilities released
> for Engine 1. This document is a **draft** and states at `:5` that where it contradicts a lock, **this document
> is wrong** — so this is a revision, not an amendment. See `KNOWN_FAILURES.md` **F-010**.

[`src/engines/input_engine/README.md:119`](../src/engines/input_engine/README.md) records a future note:
*"document-type detection likely belongs here, as a property of the artifact, not as a business conclusion."*
**That note is correct, and Amendment 3 authorises it.**

**Authorised — as a facility, never as a fifth sub-engine.** [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md)
§7 *"What is and is not a sub-engine"* settles the shape question that this clause conflated with the capability
question: a component is a sub-engine **only if it produces one of the four parts the parent combines into the
Document Evidence Object.** Document-type cue detection produces none of them — the Document Evidence Object has
no document-type component and gains none — so it is an engine-level facility, and the *"exactly four"* count at
§7 is untouched.

**The line this clause drew is the right line, and it still binds.** *"This artifact is a scanned image with an
invoice-like layout"* is an observation and is permitted. *"This is a proforma invoice"* is a conclusion that
decides whether anything posts — negative control N1, [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md) — and remains
forbidden, by Rule 1 of `COMMUNICATION_RULES_INPUT_ENGINE.md`. What may travel is **matched cues carrying their
locations**, never a bare type.

**No threshold, and none is invented.** `classification_accept` stays `UNSET`
([`ENGINE_1_CONFIDENCE_PARAMETERS.md:43`](ENGINE_1_CONFIDENCE_PARAMETERS.md)) and no cutoff is chosen here. A
facility that scores nothing and gates nothing needs none — Law 52, and `CLAUDE.md` §P: *"never fabricate a
number, including a threshold."*

**The residual is real and is tracked, not closed.** Emitting a bare document type into the Document Evidence
Object would create a fifth part and violate the count. Nothing consumes the facility today, so nothing violates
it today — see `KNOWN_FAILURES.md` **F-018**, three Engine 1 modules wired to nothing. The check falls due the
moment anything wires it in.

---

# G10. Forward Dependency Inventory — Engine 1

> Required by [`SYSTEM_INVARIANTS.md:32`](SYSTEM_INVARIANTS.md) INV-1 before any engine is locked.
> Rule, verbatim from [`FORWARD_DEPENDENCY_INVENTORY.md:13`](FORWARD_DEPENDENCY_INVENTORY.md):
> **a commitment that is neither honoured nor revised is a defect, not a choice.**

Engine 1 was locked at `6416be4` **before** the Forward Dependency Inventory existed —
[`FORWARD_DEPENDENCY_INVENTORY.md:105`](FORWARD_DEPENDENCY_INVENTORY.md) records only one settled row for it. Five engines, an
Application Layer, a measurement framework, an adversarial suite and a technology stack have been locked **since**, and every one
of them makes assumptions about Engine 1. **This is the first time those assumptions have been checked.**

## Part 1 — commitments made about Engine 1 by already-locked documents

| # | Commitment | Made in | Status |
|---|---|---|---|
| 1 | Engine 1 owns the **Document Evidence Object**, permanently; no engine may edit it | [`DATA_FLOW.md:320-325`](DATA_FLOW.md) · [`ENGINE_2:190`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`ENGINE_3:257`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`ENGINE_4:208`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`ENGINE_6:218`](ENGINE_6_EXECUTION_ENGINE_RULES.md) | **Honoured** — G4, G6 B1 |
| 2 | Engine 1 sends **facts, never interpretations**; an interpretation in the artifact is an Engine 1 **defect** | [`ENGINE_2:193-210`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) | **Honoured** — P-R4, P-P5, P-A6 |
| 3 | Engine 1 records `Corroborated: not assessed`; Engine 2 assesses it | [`ENGINE_2:181`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`DATA_FLOW.md:573`](DATA_FLOW.md) | **Honoured** — P-A9 |
| 4 | The Human Business Context arrives **inside** the Document Evidence Object, separate and never merged | [`ENGINE_2:169-181`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) · [`DATA_FLOW.md:65`](DATA_FLOW.md) | **Honoured** — P-A8, P-A11 |
| 5 | Engine 1 **screens** artifact duplicates and emits a fact; Engine 5 **decides** economic duplication | INV-7 · [`ENGINE_5:411`](ENGINE_5_VALIDATION_ENGINE_RULES.md) | **Honoured** — P-A10, E1-I7 |
| 6 | Six provenance attributes on every fact; Engine 1 establishes the envelope, all downstream preserve it | [`DATA_FLOW.md:523`](DATA_FLOW.md) · [`APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md:34`](APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md) | **Honoured** — E1-I2 |
| 7 | **New information re-enters at Engine 1** as a new artifact version; there is no backward mutation | [`ENGINE_3:243`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) · [`ENGINE_4:296`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) · [`DATA_FLOW.md:340`](DATA_FLOW.md) · [`DATA_FLOW.md:698`](DATA_FLOW.md) | **Honoured** — E1-I4. Note: **corrections enter here**, so Engine 1 is on the correction path, not only the intake path |
| 8 | Engine 4 **never communicates directly with Engine 1** | [`ENGINE_4:143`](ENGINE_4_CLARIFICATION_ENGINE_RULES.md) | **Honoured** — P-A3, one outbound path only |
| 9 | Engine 1 emits **one Document Evidence Object per document**; several may share one Transaction ID | [`APPLICATION_LAYER_CONTRACTS.md:25-29`](APPLICATION_LAYER_CONTRACTS.md) · INV-3 | **Honoured** — G6 B0 |
| 10 | Engine 1 produces a **low-confidence artifact** for an illegible photograph — never a guess | [`APPLICATION_LAYER_FAILURE_MATRIX.md:33`](APPLICATION_LAYER_FAILURE_MATRIX.md) · [`ADVERSARIAL_TESTING.md:41`](ADVERSARIAL_TESTING.md) attack 8 | **Honoured** — G8 |
| 11 | A conflict between a document and its own human note stays **visible**; the note never silently wins | [`ADVERSARIAL_TESTING.md:37`](ADVERSARIAL_TESTING.md) attack 4 | **Honoured** — P-A8. Engine 1 records both and marks neither correct ([`ENGINE_1:174`](ENGINE_1_INPUT_ENGINE_RULES.md)) |
| 12 | Changing the Document ID leaves output unchanged — the executable form of INV-9 | [`ADVERSARIAL_TESTING.md:52`](ADVERSARIAL_TESTING.md) attack 19 · [`EVALUATION_PROTOCOL.md:87`](EVALUATION_PROTOCOL.md) · [`MEASUREMENT_FRAMEWORK.md:313`](MEASUREMENT_FRAMEWORK.md) | **Honoured with a stated imprecision** — P-A7, and **C-6** |
| 13 | The identity envelope — Artifact ID · Version · Parent Artifact Version(s) · Transaction ID — is on **every** artifact | [`DATA_FLOW.md:32`](DATA_FLOW.md) · INV-3 · INV-5 | **Honoured by convention, not by the Engine 1 spec** — see **C-11** |
| 14 | Engine 1's Confidence Report is consumed by **Clarification and Validation**, two distant engines | [`COMMUNICATION_RULES_INPUT_ENGINE.md:119`](COMMUNICATION_RULES_INPUT_ENGINE.md) · [`src/engines/input_engine/README.md:120`](../src/engines/input_engine/README.md) | **Honoured** — but see **C-2**, which is about *what shape* they expect |
| 15 | Engine 1's technology is OpenCV · PaddleOCR · Docling · PyMuPDF · Table Transformer, with Gemini Vision as fallback | [`TECHNOLOGY_STACK.md:23-30`](TECHNOLOGY_STACK.md) | **Contested** — **C-4** |
| 16 | Engine 1 never consults company master data, prior transactions, or any downstream engine | [`SYSTEM_BOUNDARIES.md:50`](SYSTEM_BOUNDARIES.md) · [`ENGINE_RESPONSIBILITIES.md:46`](ENGINE_RESPONSIBILITIES.md) | **Contested against INV-12** — **C-5** |
| 17 | "Engines 1–6 real" is **Phase 4** work | [`MVP_IMPLEMENTATION_BLUEPRINT.md:102`](MVP_IMPLEMENTATION_BLUEPRINT.md) | **Revised by Amendment 3, but the blueprint was never updated** — **C-12** |

## Part 2 — the conflicts. Twelve, none smoothed over

Every one of these is a promise that is **neither honoured nor revised**. By `FORWARD_DEPENDENCY_INVENTORY.md:13` each is a
**defect**, not a choice, and each is listed with the decision it needs and who owns it.

---

### C-1 · Engine 1 has no definition of "correct", and no ground truth to be scored against ⛔ BLOCKS G2

```
ACCOUNTING_DEFINITIONS.md:40    "correct" is defined for an ENTRY  (four fields)
ACCOUNTING_DEFINITIONS.md:79    "correct" is defined for a BUSINESS UNDERSTANDING OBJECT
                                — nothing for a DOCUMENT EVIDENCE OBJECT
GOLDEN_DATASET.md:25         25 documents, labelled at ENTRY level
PHASE_REPORT_TEMPLATE.md:76     an `E1` row exists — with no scoring rule and no threshold
```

**Consequence.** Engine 1 can be built and cannot be scored. `MEASUREMENT_FRAMEWORK.md:180` requires *every engine, two numbers,
every run*; Engine 1 has no rule to produce either.

**Needs:** a definition of *correct* for a Document Evidence Object, and field-level re-keying of the golden set.
**Owner:** the user. §G2 specifies the method so that only the definition and the number are missing.

---

### C-2 · Four locked documents consume a scalar called *Evidence Reliability* that Engine 1 does not emit ⛔ HIGHEST IMPACT

```
ENGINE_2:759   Understanding Confidence  ≤  Evidence Reliability
ENGINE_3:706   Decision Confidence       ←  Evidence Reliability + …
ENGINE_4:602   Clarification Confidence  ←  Evidence Reliability (Engine 1) + …
ENGINE_5:479   Validation Confidence     ←  Evidence Reliability + …
ENGINE_6:565   Execution Confidence      ←  Evidence Reliability + …
INV-2:67       "a later confidence never exceeds the weakest critical confidence it depends on"

vs

ENGINE_1_CONFIDENCE_PARAMETERS.md:120-125   there is NO document-level scalar,
                                            and the scalar is a FALSE AFFORDANCE
ENGINE_1:222-226                            the Confidence Report carries per-field scores
```

**Five documents name a quantity the producing engine does not produce.** The name appears nowhere in Engine 1's output contract —
[`ENGINE_1:226`](ENGINE_1_INPUT_ENGINE_RULES.md) says *"reliability information"*, and
[`SUB_ENGINE_RESPONSIBILITIES.md:86`](SUB_ENGINE_RESPONSIBILITIES.md) says *"reliability assessment"*. Three names, one undefined
thing.

**The reading that saves it:** `ENGINE_2:765-773`'s worked example is **per field** — *amount extraction confidence 40% ⟹ amount
understanding confidence ≤ 40%*. Under that reading `Evidence Reliability` is not a scalar at all but a **per-fact bound**, and
everything is consistent.

**Why that is not enough.** `ENGINE_4:602`, `ENGINE_5:479` and `ENGINE_6:565` compose it into a **single engine-level confidence
with a `+`**. A per-field bound cannot be summed. Under the ordinal argument at
[`ENGINE_1_CONFIDENCE_PARAMETERS.md:99-105`](ENGINE_1_CONFIDENCE_PARAMETERS.md), a sum is **eliminated by theorem**, not merely
inaccurate.

**Needs:** one decision, then the losing documents revised. Either (a) `Evidence Reliability` is a **per-fact bound**, and
Engines 4/5/6 must state how a per-fact bound enters an engine-level figure without summing it; or (b) it is a scalar, and
`ENGINE_1_CONFIDENCE_PARAMETERS.md`'s ordinal argument must be overturned with evidence. **Owner: the user.**
**Nothing downstream of Engine 1 can be built correctly until this is answered.**

---

### C-3 · Two versions of the owner's confidence ruling are in the repository

```
src/accountant_dad/confidence.py   "degree of confidence in an artifact's CORRECTNESS"
                                   "must not be used as the SOLE gating criterion"

the ruling governing this build    "estimated uncertainty of an OBSERVATION"
                                   "gates NOTHING in this build"
```

*Not the sole criterion* permits confidence to be one input to a gate. *Gates nothing* does not. And *correctness of an artifact*
is a claim about the world; *uncertainty of an observation* is a claim about the instrument — the distinction
[`ACCOUNTING_DEFINITIONS.md:227`](ACCOUNTING_DEFINITIONS.md) draws deliberately.

**Resolved for Engine 1 only**, and only because [`MEASUREMENT_FRAMEWORK.md:258`](MEASUREMENT_FRAMEWORK.md) independently forbids
gating. **Unresolved for Engines 2–6.**

**Partially closed while this document was being written.** [`CONFIDENCE_SPECIFICATION.md`](CONFIDENCE_SPECIFICATION.md) now records
the ruling in one canonical place, which removes the *"which file do I read"* problem. **It does not close the conflict**: the
`confidence.py` docstring still states the older wording, and a docstring is what a code author reads first.

**Needs:** the `src/accountant_dad/confidence.py` docstring corrected to match `CONFIDENCE_SPECIFICATION.md`, or an explicit note in
it deferring to that document. **Owner: the user** — the docstring quotes the ruling verbatim and only its author may restate it.

---

### C-4 · Engine 1's locked technology stack puts an external API call inside an engine forbidden to make one ⛔ SHARPEST

```
TECHNOLOGY_STACK.md:30      Gemini 2.5 Flash Vision — Engine 1, "fallback only"
TECHNOLOGY_STACK.md:128     Gemini API key blocks "Engines 1 (fallback), 2, 4"

SYSTEM_BOUNDARIES.md:252    "Engine 6 is the ONLY engine allowed to interact with
                             external systems. Tally, Zoho, Busy, SAP, QuickBooks,
                             portals, APIs, webhooks, email, WhatsApp, notifications,
                             file exports — all of it passes through here, and NO
                             EARLIER ENGINE MAY REACH OUTSIDE."
```

A Gemini Vision call is an HTTPS call to an external API. `APIs` is in the list. `no earlier engine may reach outside` is the
sentence.

**Precedence.** `SYSTEM_BOUNDARIES.md` is level 2 and was locked first; `TECHNOLOGY_STACK.md` is a 2026-08-05 decision.
By INV-1 (*locks win*), **the newer document must be revised** — not the boundary.

**Three further consequences, each real on its own:**

1. **Determinism.** [`MEASUREMENT_FRAMEWORK.md:245`](MEASUREMENT_FRAMEWORK.md) — providers change models under fixed names. A vision
   model inside Engine 1 makes the sensory layer non-reproducible, and the drift canary would flag Engine 1 output changing with
   no code change.
2. **Interpretation.** A vision model asked to read a document will volunteer *"invoice from Acme for ₹19,800"* — a conclusion,
   forbidden on the wire by [`COMMUNICATION_RULES_INPUT_ENGINE.md:57`](COMMUNICATION_RULES_INPUT_ENGINE.md). Constraining it to
   observations is a design problem no locked document addresses.
3. **Injection.** A vision model is an instruction-follower reading untrusted input — adversarial attack 14
   ([`ADVERSARIAL_TESTING.md:47`](ADVERSARIAL_TESTING.md)) stops being hypothetical. This is why **P-R7 / E1-I16** are written here
   despite having no locked source.

**Needs:** either an amendment carving an exception into `SYSTEM_BOUNDARIES.md:252`, or the Gemini fallback withdrawn from Engine 1.
**Owner: the user.** Independently blocked meanwhile: the threshold is `UNKNOWN`
([`TECHNOLOGY_STACK.md:35-38`](TECHNOLOGY_STACK.md)) and confidence gates nothing (G3.1 rule 4).

---

### C-5 · INV-12 gives every engine the Knowledge Brain; two level-2 documents forbid Engine 1 the same knowledge

```
INV-12  SYSTEM_INVARIANTS.md:266   "provides knowledge to EVERY ENGINE on identical terms"
        SYSTEM_INVARIANTS.md:271    Company Knowledge = chart of accounts, ledger
                                    mappings, GST registrations, bank accounts …

SYSTEM_BOUNDARIES.md:50            Engine 1 "cannot consult company master data,
                                    prior transactions, or any downstream engine"
ENGINE_RESPONSIBILITIES.md:46      "Nothing else. The Input Engine has no knowledge
                                    of the company, its books, or its history."
```

**The reconciliation offered in §G7** — INV-12 is a *permission* (*"any engine may ignore it"*), and Engine 1 exercises it by never
calling — is plausible and is **not confirmed by any document.**

**Why it matters concretely:** knowing a company's GSTIN would let `reader` disambiguate a smudged character. That is exactly the
capability `SYSTEM_BOUNDARIES.md:50` removes, and removing it is deliberate — a reader that knows the expected answer will find it
whether or not it is on the page.

**Needs:** one sentence in `SYSTEM_INVARIANTS.md` INV-12 naming Engine 1's exemption, or one in `SYSTEM_BOUNDARIES.md` §1 stating
that Global Knowledge is permitted while Company Knowledge is not. **Owner: the user.**

---

### C-6 · Attack 19's "byte-identical output" is impossible as written

```
ADVERSARIAL_TESTING.md:52     "Document ID changed, nothing else → BYTE-IDENTICAL OUTPUT"
EVALUATION_PROTOCOL.md:87     "change the Document ID, assert byte-identical output"

ENGINE_1:204                  the Document Evidence Object CONTAINS the Document ID
```

Change the ID and the artifact differs — in exactly the field that was changed. **The test as written can never pass.**

**Needs:** the assertion narrowed to *"identical outside the identity envelope"*, with the excluded field set named exhaustively so
it cannot quietly grow. **Owner:** whoever owns `ADVERSARIAL_TESTING.md` and `EVALUATION_PROTOCOL.md`. Low severity, certain
failure.

---

### C-7 · A zero-byte file: two level-2 documents, opposite instructions ⛔ BLOCKS CODE NOW

```
APPLICATION_LAYER_CONTRACTS.md:27   "produces an object recording that failure"
APPLICATION_LAYER.md:282            "Produces a Document Evidence Object recording the failure"
APPLICATION_LAYER_FAILURE_MATRIX.md:32   → "Document Evidence Object recording the failure"

ADVERSARIAL_TESTING.md:44           attack 11: must "fail LOUDLY";
                                    FAILS IF an "Empty artifact produced"
```

Both level 2. **Precedence gives no tie-break.**

The gap may be verbal — *"an object recording a failure"* is arguably not *"an empty artifact"*. But it is not verbal in code: one
reading returns a populated Document Evidence Object with an empty Structured Document; the other raises. **A code author must pick
one today, and either choice is defensible and possibly wrong.**

**Needs:** one ruling, and the losing document revised. **Owner: the user.**

---

### C-8 · Engine 1 is the only engine with no internal communication contract

```
COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md    exists
COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md       exists
COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md    exists
COMMUNICATION_RULES_VALIDATION_INTERNAL.md       exists
COMMUNICATION_RULES_EXECUTION_INTERNAL.md        exists
COMMUNICATION_RULES_INPUT_INTERNAL.md            ✗ DOES NOT EXIST

DATA_FLOW.md:390-402   the contract table has no "Input, internal" row
DATA_FLOW.md:365       "every engine boundary MUST define all nine"
```

Engine 1's four internal boundaries have no nine-item definition anywhere. **§G6 B2–B5 supply them as an interim measure**, which
is itself irregular: an architecture document is not the right home for a communication contract, and
[`DATA_FLOW.md:404`](DATA_FLOW.md) says *one contract per boundary*.

**Needs:** `COMMUNICATION_RULES_INPUT_INTERNAL.md` written, and the `DATA_FLOW.md` table row added. **Owner: the user**, since it
adds a document to a locked set.

---

### C-9 · Engine 1 has no latency or cost budget

```
MEASUREMENT_FRAMEWORK.md:323   ≤ 60 s / document,  END TO END across six engines
MEASUREMENT_FRAMEWORK.md:324   ≤ ₹5 / document,    END TO END

ENGINE_1_CONFIDENCE_PARAMETERS.md:50   processing_budget_ms — UNSET
```

Engine 1 is the heaviest engine in the stack — OCR, layout detection, table structure and possibly a vision model. **Nobody has
allocated its share of 60 seconds.** Without an allocation the bound is unenforceable per engine, and it will only be discovered
violated at P4, end to end, when attributing the overrun is hardest.

**Needs:** a per-engine allocation summing to ≤ 60 s and ≤ ₹5, or an explicit statement that only the end-to-end bound is enforced.
**Owner: the user.**

---

### C-10 · Two confidence parameters give Engine 1 authority it does not have

```
ENGINE_1_CONFIDENCE_PARAMETERS.md:40   human_review_trigger — "document score at or
                                        below which the document is ROUTED TO A HUMAN"
ENGINE_1_CONFIDENCE_PARAMETERS.md:41   retry_trigger — "score at or below which Engine 1
                                        RE-PROCESSES with different preprocessing"

INV-4  SYSTEM_INVARIANTS.md:106         routing and retrying engine execution are the
                                        APPLICATION LAYER's
COMMUNICATION_RULES_INPUT_ENGINE.md:24  Engine 1 "does not communicate with the user"
COMMUNICATION_RULES_INPUT_ENGINE.md:141 Engine 1 "never asks a question, never decides
                                        an uncertainty is unimportant"
APPLICATION_LAYER.md:276                retrying a BUSINESS failure "could produce a
                                        DIFFERENT conclusion from identical input —
                                        destroying reproducibility"
```

`human_review_trigger` as worded gives Engine 1 a routing decision INV-4 places in the Application Layer, and a user-facing action
its own communication contract forbids. `retry_trigger` gives Engine 1 an internal retry that would make the sensory layer
non-deterministic — in the engine whose reproducibility every downstream number rests on.

Both are already blocked by G3.1 rule 4 (confidence gates nothing), so **nothing breaks today**. But both are on a sign-off sheet
awaiting a number, and supplying one would authorise the behaviour by the back door.

**Needs:** #6 reworded so Engine 1 **emits a signal** the Application Layer routes on, and #7 either withdrawn or restated as a
deterministic multi-pass extraction whose passes are fixed rather than confidence-triggered. **Owner: the user.**

---

### C-11 · The Engine 1 output contract omits the identity envelope

```
DATA_FLOW.md:32      "Every artifact carries an Artifact ID, a Version, its Parent
                      Artifact Version(s), and exactly one Transaction ID"
INV-5:146            every artifact carries Artifact ID · Version · Parent Version(s)
INV-3:81             every artifact references exactly one Transaction ID

ENGINE_1:202-227     the output tree lists: Document ID · Source references ·
                     Structured Document · Human Business Context · Confidence Report
                     — and NOTHING ELSE
```

`DATA_FLOW.md:32` explains the convention — *"the identity envelope is universal and not repeated"* — so this is a documentation
gap rather than a contradiction. **It is still a defect**, because `ENGINE_1:199` presents its tree as the complete output
contract, and INV-6 requires that *"two independent engineers must build identical artifacts from the specification"*
([`SYSTEM_INVARIANTS.md:185`](SYSTEM_INVARIANTS.md)). Two engineers reading only `ENGINE_1_INPUT_ENGINE_RULES.md` build a Document
Evidence Object with no Transaction ID and no version chain.

**A second, smaller question falls out of it:** is `Document ID` the same field as `Artifact ID`, or a second identifier?
[`DATA_FLOW.md:433`](DATA_FLOW.md) gives Document ID *"identity of the artifact only"*; [`:474`](DATA_FLOW.md) gives Artifact ID
*"identity of the artifact across all its versions."* **UNKNOWN.** The current code treats them as distinct
(`src/accountant_dad/artifacts/evidence.py` carries both `identity` and `document_id`), which is a reasonable reading of two
documents that do not settle it.

**Needs:** one line in `ENGINE_1_INPUT_ENGINE_RULES.md` §5 pointing at the envelope, and one sentence settling Document ID vs
Artifact ID. **Owner: the user.**

---

### C-12 · The blueprint still schedules Engine 1 for P4; Amendment 3 released it now

```
MVP_IMPLEMENTATION_BLUEPRINT.md:102   "Engines 1–6 real | P4"
MVP_IMPLEMENTATION_BLUEPRINT.md:105   "Zero forward dependencies"

CLAUDE.md §P Amendment 3, 2026-08-05  "Engine 1, and only Engine 1, is released for
                                       implementation" — now, before P1 and P4
```

Amendment 3's own reasoning cites [`MVP_IMPLEMENTATION_BLUEPRINT.md:100,102`](MVP_IMPLEMENTATION_BLUEPRINT.md) and concludes P1
gates the *measurement* of Engine 1, never its construction. That reasoning is sound. **But the blueprint was never updated**, so
the locked plan and the amendment disagree in writing, and `CLAUDE.md` §N requires *"blueprint updated to match reality (Law 19)."*

**A second-order effect worth stating:** the blueprint's *"zero forward dependencies"* proof assumed Engine 1 real at P4, after the
Application Layer (P3) and the Brain (P4). Engine 1 built now depends on the Application Layer, which is P3 and **not yet built**.
That is a genuine forward dependency the proof no longer covers.

**Needs:** the blueprint's dependency table amended, and the forward-dependency proof re-checked. **Owner: the user.**

---

## Part 3 — carried forward from the existing inventory

| Item | Bearing on Engine 1 |
|---|---|
| **39 sub-engine count — Open** ([`FORWARD_DEPENDENCY_INVENTORY.md:96`](FORWARD_DEPENDENCY_INVENTORY.md)) — *"no engine's count has been tested against its real needs"* | Engine 1's four are **not** reopened here. [`ENGINE_1:365`](ENGINE_1_INPUT_ENGINE_RULES.md) forbids adding, removing or merging, and E1-I14 holds. Recorded because the general question is open and Engine 1 will be the first engine to test it against real code |
| **Reality Probe — deferred by decision** ([`FORWARD_DEPENDENCY_INVENTORY.md:95`](FORWARD_DEPENDENCY_INVENTORY.md)) | INV-13 requires measurement before commitment. **Engine 1 is the one engine where the probe is cheap**: run PaddleOCR on ten real photographed invoices and measure. Doing so before the G2 number is set would make the number evidence-based instead of a guess |
| **Structured Document + Confidence Report as artifact names — Settled** ([`FORWARD_DEPENDENCY_INVENTORY.md:105`](FORWARD_DEPENDENCY_INVENTORY.md)) | Honoured. Both survive as **components**; `Document Evidence Object` is the only artifact name (P-A1, [`ENGINE_1:257`](ENGINE_1_INPUT_ENGINE_RULES.md)) |

## Part 4 — the summary that decides whether this may be locked

```
commitments checked                    17
honoured                                12
honoured with a stated imprecision       1   (#12 — C-6)
neither honoured nor revised            12   C-1 … C-12
                                        ──
BLOCKING the freeze                      4   C-1 (no metric) · C-2 (no Evidence Reliability)
                                             C-4 (external call) · C-7 (zero-byte file)
```

**C-2, C-4 and C-7 must be answered before Engine 1 code is correct.** C-1 must be answered before Engine 1 can be **called done**
at all, because without it there is no §G2 and Law 52 has no definition of done to enforce.

The remaining eight are real defects with lower urgency: they make the documents wrong, not the code wrong.

---

# G11. Freeze and amendment

## Freeze conditions — not yet met

This document is **DRAFT**. It may be frozen when all four hold:

| # | Condition | Status |
|---|---|---|
| 1 | §G2 carries a number and a unit, supplied by the owner | ⬜ **AWAITING** |
| 2 | C-1, C-2, C-4 and C-7 are resolved, and the losing documents revised | ⬜ **AWAITING** — 4 open |
| 3 | The remaining eight conflicts are each **honoured or explicitly revised**, per [`FORWARD_DEPENDENCY_INVENTORY.md:13`](FORWARD_DEPENDENCY_INVENTORY.md) | ⬜ **AWAITING** — 8 open |
| 4 | The three Law 54 gaps (#4, #12, #13) are answered, **or** the build's scope is recorded as excluding what depends on them (§G9.2) | ⬜ Partially — G9.2 records the exclusions; the gaps are open |

**Freezing with §G2 blank would defeat the point.** `CLAUDE.md` §G2 requires the number *before the architecture is approved*.

## What is already binding, draft or not

Sections **G4, G5, G6 B2–B5, G7, G8 and G9** restate or derive from locked documents. **They bind now**, because their authority
comes from those documents, not from this one. A pull request violating a `P-` predicate is violating
`ENGINE_1_INPUT_ENGINE_RULES.md`, `SYSTEM_BOUNDARIES.md` or `SYSTEM_INVARIANTS.md` — this document only makes it checkable.

## Amendment process

Per `CLAUDE.md` §M, unchanged. Any amendment records: what changed (old → new) · which document and section · why · what failure
forced it · the trade-off · the test that now guards it · who approved, with the date.

**Specific to Engine 1:**

- **Adding, removing or merging a sub-engine** is an amendment to `ENGINE_1_INPUT_ENGINE_RULES.md:365` **and**
  `SUB_ENGINE_RESPONSIBILITIES.md:28`, never a refactor.
- **Introducing any confidence gate** is an amendment to `MEASUREMENT_FRAMEWORK.md:258` and requires the separation test to have
  passed first.
- **Setting any of the 16 parameters** follows the four-step route at
  [`ENGINE_1_CONFIDENCE_PARAMETERS.md:131-147`](ENGINE_1_CONFIDENCE_PARAMETERS.md) — architecture, measurement, calibration, then a
  per-parameter report the user approves. **Step 4 produces a recommendation and stops.**
- **Every `.github/**` change is reported line by line, before and after** (`CLAUDE.md` §P).

## If code and this document disagree

`CLAUDE.md` §M and [`SYSTEM_INVARIANTS.md:5`](SYSTEM_INVARIANTS.md): **the document wins and the code is wrong.** Report it. Never
resolve it silently in code.

If **this** document disagrees with a locked one, **this document is wrong** — it is level 3, and INV-1 gives the lock the win.

---

## Related documents

- [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) — the locked specification. Deeper authority on everything in G5 and G8.
- [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) — the Input → Understanding contract, all nine items.
- [`ENGINE_1_CONFIDENCE_PARAMETERS.md`](ENGINE_1_CONFIDENCE_PARAMETERS.md) — the 16 parameters, all `UNSET`, three undefined.
- [`SUB_ENGINE_RESPONSIBILITIES.md` §1](SUB_ENGINE_RESPONSIBILITIES.md) — the canonical four-sub-engine map.
- [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md) — the 13 invariants. Highest authority in the repository.
- [`FORWARD_DEPENDENCY_INVENTORY.md`](FORWARD_DEPENDENCY_INVENTORY.md) — where §G10's conflicts belong once they are settled.
- [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) · [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) — how a number is obtained and what it may claim.
