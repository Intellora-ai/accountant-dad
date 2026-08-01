# Engine 1 — Input Engine: Specification Lock

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
> **It does not own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, or workflow control.**

Assembly means one thing only: the four parts its own sub-engines produced become one artifact at the engine boundary. Nothing broader is implied and nothing broader is permitted.

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

Poor quality is a normal operating condition, not an exception. A blurred phone photograph of a handwritten note is a valid input; what varies is the confidence attached to what is read from it, never whether it is accepted.

## Every input must preserve

- **Original source** — the artifact as received, unmodified.
- **Original information** — nothing dropped, nothing corrected.
- **Document identity** — the artifact is identifiable throughout its lifecycle.

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
├── Structured Document
│   ├── Extracted text
│   ├── Detected fields
│   ├── Document structure
│   ├── Detected tables
│   ├── Field values
│   └── Field locations
│
└── Confidence Report
    ├── Confidence scores
    ├── Uncertainty markers
    ├── Reliability information
    └── Risky fields
```

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

`Document Evidence Object` is the artifact's **only** name. `Structured Document` and `Confidence Report` name its two components and are never used as the name of the artifact itself. No engine may create an alternative name, and no duplicate representation may exist.

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

## The invention prohibition

**When information is unclear, the system must report uncertainty. It must never invent information.**

This is the single most important rule in the engine. An invented value is indistinguishable downstream from an observed one, and the entire trustworthiness of the system rests on that distinction holding.

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

# 10. Final Validation Checklist

Before this specification is considered complete, confirm:

- [x] Input Engine has exactly four sub-engines.
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
