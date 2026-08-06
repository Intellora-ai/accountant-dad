# Engine 1 — Input Engine: Specification Lock

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> **Status: LOCKED.** This is the permanent engineering specification for the Input Engine. Future implementation must follow it.
>
> **Specification only — no implementation.** No code, no libraries, no OCR, computer vision or handwriting systems, no pipelines, no dependencies.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map of all 39 sub-engines. **This document is the deeper authority for Input Engine specifics** — allowed and forbidden actions, output contracts, and failure behaviour. Where they overlap they must agree; a disagreement is a defect to be fixed, not a choice to be made.

---

# 1. Engine Identity

## Engine Name

**Input Engine**

## Core Role

The Input Engine is the **sensory layer** of the AI Accountant.

> Convert raw human accounting artifacts into reliable, structured evidence while preserving uncertainty.

### The question it answers

> **"What information exists in the document?"**

### The question it does not answer

> ~~"What does this transaction mean?"~~

Meaning, interpretation, accounting treatment and decisions belong to later engines.

---

# 2. Mission

**The Input Engine converts raw accounting artifacts into clean, readable, structured evidence while maintaining traceability and uncertainty.**

Three properties define success, and all three are load-bearing:

- **Clean and structured** — the artifact's contents become usable evidence.
- **Traceable** — every extracted value keeps a reference to where it came from.
- **Uncertain where it is uncertain** — doubt about the reading is preserved, never smoothed away.

An extraction that is structured but untraceable, or confident but wrong, has failed even if every character is correct.

---

# 3. Responsibility

## The Input Engine owns

- Document quality improvement.
- Information extraction.
- Field detection.
- Structure extraction.
- Confidence estimation.
- Evidence preservation.
- **Internal assembly of its four sub-engines' outputs into the Document Evidence Object.**

## The Input Engine does NOT own

- Business understanding.
- Transaction interpretation.
- Accounting reasoning.
- Financial decisions.

## Scope of the assembly responsibility

> **The Input Engine owns the internal assembly of outputs from its four sub-engines into the Document Evidence Object.**
>
> **It does not own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, workflow control, or overriding sub-engine outputs.**

Assembly means one thing only: the four parts its own sub-engines produced become one artifact at the engine boundary. Nothing broader is implied and nothing broader is permitted.

---

# 3A. Decision Authority

> **The Input Engine controls only input-processing decisions.**
>
> **No engine outside the Input Engine can modify its decisions.**

Authority is divided internally. Each component decides within its own domain and nowhere else.

| Component | Owns | Determines | Cannot |
|---|---|---|---|
| **Cleaner** | Document preprocessing actions | Allowed transformations · whether preprocessing introduced risk | Interpret information |
| **Reader** | Extraction observations | Detected characters, regions and tables · extraction confidence signals | Understand meaning |
| **Parser** | Evidence structuring | Field mapping · detected relationships between extracted values · missing fields | Infer missing information |
| **Confidence** | Reliability estimation | Confidence scores · uncertainty markers · risky extraction areas | Hide uncertainty · change extracted facts |
| **Input Engine (parent)** | Assembly of all sub-engine outputs into the Document Evidence Object · creation of the Document ID · evidence preservation | — | See below |

## The parent Input Engine does NOT

- Orchestrate the entire system.
- Route workflows.
- Perform business reasoning.
- Make accounting decisions.
- **Override sub-engine outputs.**

The last is the one most easily lost in implementation. The parent assembles what its sub-engines produced; it does not correct, second-guess, or improve any of it. A parent that may overrule `confidence` can quietly raise a score, and the honesty of the whole artifact goes with it.

## Confidence has a single authority

`cleaner`, `reader` and `parser` emit **signals**. Only `confidence` turns signals into scores. No other component — parent included — may raise or lower a confidence value.

## No sub-engine overrides another

`confidence` reads the outputs of `cleaner`, `reader` and `parser`; it cannot correct them. `parser` consumes `reader`'s extraction; it cannot re-read it. Each result stands as its author produced it.

---

# 4. Input Contract

## The Input Engine accepts

- Photos.
- Camera photo capture.
- Images and image uploads.
- PDFs.
- Scanned invoices.
- Handwritten accounting notes.
- Poor-quality human inputs.
- Receipts.
- Bills.
- Supporting accounting documents.
- **Excel files.**
- **Email content.**
- **Structured metadata.**
- **Optional Human Business Description** — plain English, supplied by the user.

Poor quality is a normal operating condition, not an exception. A blurred phone photograph of a handwritten note is a valid input; what varies is the confidence attached to what is read from it, never whether it is accepted.

**The Human Business Description is optional. The system must work correctly when none is provided.** Nothing downstream may require one, and its absence is not a gap to be clarified.

## Every input must preserve

- **Original source** — the artifact as received, unmodified.
- **Original information** — nothing dropped, nothing corrected.
- **Document identity** — the artifact is identifiable throughout its lifecycle.

---

# 4A. Evidence Rules — the Human Business Description

> **A human note is evidence, not truth.**

## What it may contain

- Business purpose.
- Transaction intent.
- Operational context.
- Relationships.
- Additional explanation.

```text
"Bought laptops for the design team."
"Advance payment to supplier."
"This payment settles Invoice 481."
```

Each of these supplies narrative a document cannot: *why* the transaction exists, *what* it relates to, *how* it connects to something else.

## What it may never be

> **The description may never be treated as confirmed fact.**

It may supply intent, explanation, business context or missing narrative. It must **never automatically override** documents, receipts, invoices, bank statements or any other evidence.

Conflicts between the note and other evidence **remain visible** and are handled by later engines. Engine 1 records both, marks neither correct, and passes both forward.

## Duplicate screening — screening is not deciding

The Input Engine performs a **cheap identity screen** on every artifact: same uploaded file · same hash · same document number · same filename.

The result is recorded as **a fact with provenance** — never a rejection, never a decision.

| | Input Engine — **screens** | Validation Engine — **decides** |
|---|---|---|
| Question | Have I seen this **artifact**? | Is this the same **economic transaction**? |
| Basis | File identity, hash, document number, filename | Same accounting effect · same invoice entered differently |
| Output | A fact with provenance | A judgement |
| Purpose | Prevent unnecessary processing | Prevent double-posting |

The Input Engine never rejects a duplicate and never decides one exists in the accounting sense. See [`SYSTEM_INVARIANTS.md` INV-7](SYSTEM_INVARIANTS.md#inv-7--screening-is-not-deciding).

## Every source is evidence; no source is truth

The Input Engine treats a typed sentence, a scanned invoice and a metadata field identically in one respect: each is recorded as **an evidence item with an origin**, and none of them becomes truth by being recorded.

---

# 5. Output Contract

The Input Engine produces exactly one artifact: the **Document Evidence Object**.

```text
Document Evidence Object
│
├── Document ID
│
├── Source references
│
├── Structured Document                 ← extracted evidence
│   ├── Extracted text
│   ├── Detected fields
│   ├── Document structure
│   ├── Detected tables
│   ├── Field values
│   └── Field locations
│
├── Human Business Context              ← provided evidence, optional
│   ├── Original user text              verbatim, never rewritten
│   ├── Source = Human
│   ├── Timestamp
│   └── Evidence reference
│
└── Confidence Report
    ├── Confidence scores
    ├── Uncertainty markers
    ├── Reliability information
    └── Risky fields
```

## Human Business Context

Present only when the user supplied a description. **It remains independent from extracted document evidence.**

> **Engine 1 never merges the two into a single fact.**

The two live as **separate, linked entries**: linked because they describe the same transaction, separate because one was read off an artifact and the other was asserted by a person. Merging them would destroy the only signal that distinguishes an observation from a claim.

## The traceability rule

**Every extracted value must preserve:**

1. **Where the information came from** — its location in the source artifact.
2. **How reliable the extraction is** — its confidence.
3. **Whether uncertainty exists** — its uncertainty markers.

A value carried without all three is not evidence and must not be emitted.

## Document ID

> **Document ID exists only for identity, traceability, and lifecycle tracking.**
>
> **It carries no accounting meaning and must never influence accounting decisions.**

It is assigned by the Input Engine at intake. It is not an invoice number, not a voucher reference, not a business identifier of any kind, and no downstream engine may treat it as one.

## Naming

`Document Evidence Object` is the artifact's **only** name. `Structured Document`, `Human Business Context` and `Confidence Report` name its components and are never used as the name of the artifact itself. No engine may create an alternative name, and no duplicate representation may exist.

---

# 5A. Evidence Provenance

**Every fact carries its origin, permanently.** Engine 1 establishes the provenance envelope; every downstream engine preserves it.

| Attribute | Meaning |
|---|---|
| **Source Type** | `Document` · `Human` · `Structured Metadata` |
| **Source ID** | Which source it came from |
| **Evidence Reference** | Where within that source |
| **Timestamp** | When it entered the system |
| **Confidence** | Extraction confidence for documents; **capture confidence** for provided sources |
| **Corroborated** | Whether another source supports it |

> **No engine may merge these origins into a single anonymous fact.**

## Capture confidence is not truth confidence

For a provided source, confidence measures **how faithfully the input was captured** — not whether the statement is true.

```text
User typed:          "Advance paid to supplier."

Capture confidence:  100%       the system stored exactly what was typed
Truth confidence:    unknown    until supported by other evidence
```

> **Human notes contribute context, not certainty.**
>
> **A human note must never increase Evidence Reliability simply because it exists.**

It can improve understanding once **corroborated**. It can never independently raise confidence. The same holds for structured metadata: capturing a field perfectly says nothing about whether its content is correct.

## Corroboration

Engine 1 records `Corroborated: not assessed` — honestly, because **it cannot assess it.** Establishing that *"advance paid to supplier"* and a document's payment field mean the same thing is **interpretation**, which this engine is forbidden from performing.

The attribute is assessed by the first engine able to assess it and recorded in **that engine's own artifact** — never written back into the Document Evidence Object, which is immutable and owned here. In practice that is the Understanding Engine.

## Where provenance travels

```text
Document Evidence Object → Business Understanding Object → Accounting Decision
    → Clarification Request → Validation Decision → audit history
```

Complete provenance from input to execution. See [`DATA_FLOW.md` §12](DATA_FLOW.md#12-evidence-provenance).

---

# 6. Absolute Engine Boundaries

The Input Engine **MUST NEVER**:

1. Decide transaction type.
2. Decide accounting treatment.
3. Select ledger accounts.
4. Create journal entries.
5. Apply tax rules.
6. Understand business intent.
7. Ask accounting questions.
8. Fill missing information by guessing.
9. Modify original financial values.

## Concerning the Human Business Description, it must never

10. Convert the description into fact.
11. Override document evidence.
12. Remove conflicting evidence.
13. Hide contradictions.
14. **Increase confidence because the user wrote something.**
15. **Rewrite the user's wording.**

The last is absolute: the text is stored **verbatim**. Not tidied, not corrected, not summarised, not normalised. A rewritten note is no longer the user's evidence — it is the system's paraphrase of it, and no downstream engine could tell the difference.

## The invention prohibition

**When information is unclear, the system must report uncertainty. It must never invent information.**

This is the single most important rule in the engine. An invented value is indistinguishable downstream from an observed one, and the entire trustworthiness of the system rests on that distinction holding.

A human note is the sharpest test of it. A user's claim is not an observation, and the moment the two become indistinguishable the system has invented a fact without noticing.

## Observation versus reasoning

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

The Input Engine extracts what exists. The Understanding Engine determines what it means.

---

# 7. Internal Sub-Engine Architecture

The Input Engine contains **exactly four** sub-engines:

```text
Input Engine
├── Cleaner
├── Reader
├── Parser
└── Confidence
```

## Rules

- Do not add new sub-engines.
- Do not remove sub-engines.
- Do not merge responsibilities.

## Assembly

```text
   Cleaner            Reader             Parser           Confidence
      │                  │                  │                  │
 cleaned document   extracted info   structured fields   reliability info
      │                  │                  │                  │
      └──────────────────┴────────┬─────────┴──────────────────┘
                                  │
                           Input Engine
                                  │
                                  ▼
                    Document Evidence Object
```

The four sub-engines are specialised workers. The parent engine is the boundary at which their individual observations become one artifact. **No new assembler sub-engine is created**, and none is needed — architecture expands by making responsibilities clearer, not by adding components.

## Ingesting a provided source

A Human Business Description enters through the **same evidence ingestion path** as every other source. **No sub-engine is added for it.** A typed English note needs no OCR and no document parsing, so the extraction stages simply pass it through:

| Sub-engine | With a provided source |
|---|---|
| `cleaner` | **Passes it through untouched.** There is no image to deskew, no encoding to repair. Any transformation would be a rewrite. |
| `reader` | **Passes it through untouched.** The text is already text; there is nothing to extract from it. |
| `parser` | **Imposes no structure on it.** It is narrative, not fields — and structuring it would begin interpreting it. |
| `confidence` | **Scores capture fidelity** — how faithfully the input was stored. Never whether it is true. |

Engine 1 records it as a **first-class evidence item** with its own origin, timestamp, source type and traceability. The Document Evidence Object then holds extracted document evidence and human-provided evidence as **separate, linked entries** — never merged.

## Sub-engine output contracts

These are the four parts the parent engine combines. They are stated identically here, in [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) and in each sub-engine's README.

| Sub-engine | Produces |
|---|---|
| **Cleaner** | Cleaned document representation · Quality issues detected · Preservation status |
| **Reader** | Raw extracted information · Source locations · Extraction confidence |
| **Parser** | Structured fields · Field mappings · Missing field information |
| **Confidence** | Confidence scores · Uncertainty markers · Reliability assessment |

---

# 8. Sub-Engine Specifications

---

## 8.1 Cleaner

### Purpose

Improve raw document quality before extraction.

### Owns

Document preprocessing.

### Receives

Raw documents.

### Produces

- Cleaned document representation.
- Quality issues detected.
- Preservation status.

### Allowed Actions

Can:

- Reduce visual noise.
- Improve readability.
- Normalize document appearance.
- Improve image quality.

### Forbidden Actions

Cannot:

- Change numbers.
- Remove important evidence.
- Interpret text.
- Correct accounting information.
- Alter original meaning.

### Failure Behaviour

**If processing may damage information: preserve the original input and mark uncertainty.**

- **A provided source passes through untouched.** A Human Business Description has no image to deskew and no encoding to repair; any transformation would be a rewrite, which is forbidden.
- The original artifact is never discarded, so a damaging transformation is always recoverable.
- Preservation status records whether the cleaned representation or the original is the safer basis for reading.
- Detected quality issues are reported as evidence for the Confidence sub-engine, never repaired by guesswork.

---

## 8.2 Reader

### Purpose

Extract visible information from documents.

### Owns

Reading and recognition.

### Receives

Cleaned document representation.

### Produces

- Raw extracted information — text, numbers, dates, names, tables, handwriting output.
- Source locations.
- Extraction confidence.

### Allowed Actions

Can:

- Detect visible characters.
- Extract printed text.
- Extract handwriting.
- Identify document regions.

### Forbidden Actions

Cannot:

- Understand transaction meaning.
- Fix accounting mistakes.
- Guess unclear words.
- Infer missing business information.

### Failure Behaviour

**Return extracted information with confidence levels and uncertainty.**

- **A provided source passes through untouched.** A typed note is already text; there is nothing to extract from it, and reading it would mean interpreting it.
- An unclear character or word is emitted as unclear, with its confidence, never resolved by guessing.
- A region that could not be read at all is reported as unread, not omitted silently.
- Source locations are emitted even for low-confidence extractions — that is what makes a later human check possible.

---

## 8.3 Parser

### Purpose

Convert extracted information into structured evidence.

### Owns

Organization of extracted information.

### Receives

Reader output.

### Produces

- Structured fields.
- Field mappings.
- Missing field information.

Example shape:

```text
Vendor:
Amount:
Date:
Invoice Number:
Items:
Payment Reference:
```

### Allowed Actions

Can:

- Map extracted information into fields.
- Identify relationships between fields.
- Preserve source references.

### Forbidden Actions

Cannot:

- Decide debit or credit.
- Choose ledger accounts.
- Apply accounting rules.
- Create transaction meaning.

### Failure Behaviour

**Unknown fields remain unknown. Never fabricate values.**

- **A provided source receives no structure.** A Human Business Description is narrative, not fields. Imposing structure on it would begin interpreting it, which belongs to the Understanding Engine.
- A field that is absent is recorded in missing field information as absent — not defaulted, not estimated, not omitted.
- "Absent", "zero" and "unreadable" are three different states and must remain distinguishable.
- Field mappings retain the source reference for every mapped value, so a wrong mapping can be traced.

---

## 8.4 Confidence

### Purpose

Measure reliability of extracted information.

### Owns

Uncertainty estimation.

### Receives

- Cleaner output.
- Reader output.
- Parser output.

### Produces

- Confidence scores.
- Uncertainty markers.
- Reliability assessment.

Example shape:

```text
Amount confidence:  98%
Vendor confidence:  82%
Date confidence:    65%
```

### Allowed Actions

Can:

- Detect uncertain extraction.
- Score reliability.
- Highlight risky fields.

### Forbidden Actions

Cannot:

- Increase confidence without evidence.
- Hide uncertainty.
- Make accounting decisions.

### Failure Behaviour

**Reduce confidence and explain the uncertainty.**

- **For a provided source, it scores capture fidelity** — how faithfully the input was stored — never whether the statement is true. A human note may never raise Evidence Reliability simply by existing.
- Where reliability cannot be established, confidence goes down — never up, and never to a default "good enough" value.
- Every uncertainty marker carries a reason. A bare score cannot become a good question downstream.
- Uncertainty is never suppressed because it would delay processing.

---

# 9. Quality Standard

## The Input Engine succeeds when

- ✅ Information extraction is accurate.
- ✅ Evidence is traceable.
- ✅ Uncertainty is visible.
- ✅ Original information is preserved.
- ✅ No accounting reasoning happens inside extraction.

## The Input Engine fails when

- ❌ Information is invented.
- ❌ Uncertainty is hidden.
- ❌ Accounting decisions are made during extraction.

Note the asymmetry: a low-confidence extraction that is honestly marked is a **success**. A confident extraction that quietly guessed is a **failure**, even if the guess happened to be right.

---

# 9A. What is and is not a sub-engine — the membership test

> **This section governs the *"exactly four"* count in §7.** Read the two together.
>
> **Why it is printed here instead of inside §7.** `conformance_registry.py` pins conformance predicates to **line numbers** in this document, and a drift test fails when a quotation moves off the line it cites. Two predicates cite lines 569 and 626 — both inside §8 — so **any insertion above line 626 renumbers them.** Renumbering would strand four further citations in files this change may not edit. So this document is, in practice, **append-only after line 626**, and the rule lands in the first place that does not move a cited line. That constraint is a property of the tooling, not of the architecture, and it is recorded in `KNOWN_FAILURES.md` **F-027**.

> **A component is a sub-engine if, and only if, it produces one of the four parts the parent engine combines into the Document Evidence Object.**

**Added 2026-08-06. The §7 count is unchanged and was never wrong.** What was missing was the predicate that decides membership, and its absence let a *file* count be read as a *sub-engine* count. They are not the same measurement. This section states the test; it removes no rule and adds no sub-engine. Recorded as Amendment 5 in [`ARCHITECTURE_AMENDMENTS.md`](ARCHITECTURE_AMENDMENTS.md), resolving `KNOWN_FAILURES.md` **F-010**.

**A sub-engine is not a file.** This document forbids implementation outright — the header, *"Specification only — no implementation. No code, no libraries … no pipelines"* — so a count written here cannot have been counting source files, because when it was written none were permitted to exist. It counts **owned problems**, the unit [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) uses when it says *"Each sub-engine owns exactly one problem."*

The architecture already proves the two differ. It describes work Engine 1 must perform — assembly — and states in the same breath that **no sub-engine performs it** (§7, *"No new assembler sub-engine is created"*). So engine-level work that is not sub-engine work already existed in the architecture before any code did. §3A shows the same thing structurally: **Input Engine (parent)** is a fifth *row* in the Decision Authority table with its own `Owns` column, and it is not a sub-engine.

## The three categories, and every component belongs to exactly one

| Category | Test | Members |
|---|---|---|
| **Sub-engine** | Produces one of the four parts named in §7's output-contract table | `cleaner` · `reader` · `parser` · `confidence` — **exactly four, permanently** |
| **The parent engine's own machinery** | Calls the four sub-engines, combines their four parts, assigns the Document ID. It is the box labelled *Input Engine* in §7's assembly diagram, not a component inside it | The engine's runner and its combining step |
| **Engine-level facility** | Produces no part of the Document Evidence Object, and answers no question about the contents of any document | Configuration loading · the calibration measurement record · document-type cue detection |

**The test is checkable, not a matter of judgement.** The Document Evidence Object's components are fixed by §5. A component whose output is not one of them did not produce one of the four parts, and is therefore not a sub-engine — whatever it is named, and however many files it occupies.

**Splitting one job across two files creates no second component.** The parent's runner and its combining step are one engine-level responsibility written in two places. File layout is not architecture; a second *owner* would be.

## What each category may and may not do

- **A fifth sub-engine may never be created.** §7's rules stand unchanged: do not add, do not remove, do not merge. Anything that would produce a fifth part of the Document Evidence Object **is** a fifth sub-engine, whatever it is called, and is forbidden.
- **The parent's machinery may never reason.** It assembles what the four produced. §3A binds it in full: it does not override a sub-engine output, and it never raises or lowers a confidence value.
- **A facility may never reach the artifact.** The moment a facility's output enters the Document Evidence Object it has produced a fifth part and has stopped being a facility. **This is the line to watch** — a facility is cheap to add and a sub-engine may not be added at all, so "facility" is where an unwanted fifth sub-engine would hide.

**Document-type cue detection is a facility, and that boundary is load-bearing.** [`CLAUDE.md`](../CLAUDE.md) §P Amendment 3 authorises *"document classification"* by name. It is a facility because the Document Evidence Object has no document-type component and gains none: what cue detection produces is evidence for the calibration record, never a part of the artifact. If a document type is ever to travel to the Understanding Engine it travels as **observed cues carrying their locations**, never as a bare type — Rule 1 of [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md), *"The Input Engine sends **observations**. It does not send **interpretations**."*

---

# 10. Final Validation Checklist

Before this specification is considered complete, confirm:

- [x] Input Engine has exactly four sub-engines.
- [x] §9A states the membership test that decides what counts as one — a component is a sub-engine only if it produces one of the four parts the parent combines. Every Engine 1 component is a sub-engine, the parent's own machinery, or a facility, and exactly one of the three.
- [x] No sub-engine responsibilities overlap.
- [x] No accounting intelligence exists inside the Input Engine.
- [x] No implementation exists.
- [x] Communication boundaries are defined — see [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md).
- [x] Architecture names remain unchanged.

---

## Related documents

- [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) — how this engine communicates with the Understanding Engine.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) — the canonical system-wide sub-engine map.
- [`DATA_FLOW.md`](DATA_FLOW.md) — the Document Evidence Object's place in the pipeline.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
