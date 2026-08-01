# Communication Rules — Input Engine

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> How the Input Engine communicates with the rest of the system.
>
> Companion to [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md). **Specification only — no implementation.**

---

# 1. The Only Path

The Input Engine communicates with exactly one engine, in exactly one direction, by sending exactly one artifact.

```text
Input Engine
     ↓
Document Evidence Object
     ↓
Understanding Engine
```

There is no other outbound path. The Input Engine does not communicate with the Accounting, Clarification, Validation or Execution Engines, and does not communicate with the user.

---

# 2. What Is Sent

**The Input Engine communicates only by sending evidence.**

The Document Evidence Object carries:

- **Extracted facts** — what is written on the artifact.
- **Structured fields** — that content organised into fields, tables and rows.
- **Source locations** — where on the artifact each value came from.
- **Confidence scores** — how reliable each extraction is.
- **Uncertainty markers** — where doubt exists, and why.
- **Human Business Context** *(optional)* — the user's plain-English description, verbatim, with source, timestamp and evidence reference.

Plus the **Document ID** and **source references** that make the artifact identifiable and traceable throughout its lifecycle.

**Every fact carries its provenance** — Source Type (`Document` · `Human` · `Structured Metadata`), Source ID, Evidence Reference, Timestamp, Confidence and Corroborated. See [`DATA_FLOW.md` §12](DATA_FLOW.md#12-evidence-provenance).

Full structure: [`ENGINE_1_INPUT_ENGINE_RULES.md` §5](ENGINE_1_INPUT_ENGINE_RULES.md#5-output-contract).

**The Understanding Engine receives evidence and creates meaning.** That division is the whole point of the handoff.

---

# 3. Communication Rules

---

## Rule 1 — Evidence, Not Conclusions

The Input Engine sends **observations**. It does not send **interpretations**.

**✗ Incorrect**

> "Purchase of machinery."

**✓ Correct**

> "Document contains item name, vendor name, amount, and date."

The first sentence is a conclusion: it asserts a transaction type, a direction, and an asset class. Every one of those is the Understanding Engine's to determine and the Accounting Engine's to act on. The second states only what was observed.

### The test

If a sentence in the output could be **wrong about the business** rather than **wrong about the document**, it is an interpretation and does not belong in the Document Evidence Object.

| Observation ✓ | Interpretation ✗ |
|---|---|
| "Field labelled *Supplier* contains `Acme Traders`." | "The supplier is Acme Traders." |
| "Extracted `27AAECS1234F1Z5` at top right." | "GSTIN is 27AAECS1234F1Z5." |
| "Amount field contains `19,800.00`." | "Total payable is ₹19,800." |
| "No field matching a payment reference was detected." | "This was an unpaid credit purchase." |
| "The user wrote: *This payment settles Invoice 481.*" | "This payment settles Invoice 481." |

The last row is the one this engine most easily gets wrong. Recording **that a user said something** is an observation. Recording **what they said as true** is an interpretation — and once the quotation marks are gone, nothing downstream can tell which happened.

---

## Rule 2 — No Stage Skipping

The required flow is:

```text
Input Engine
     ↓
Understanding Engine
```

The Input Engine cannot directly create accounting decisions, and cannot reach any engine beyond the Understanding Engine. There is no shortcut for a document that appears obvious.

---

## Rule 3 — Output Ownership

The Document Evidence Object belongs to the Input Engine. **No other engine may:**

- Modify Input Engine output.
- Change extracted evidence.
- Remove uncertainty information.

Downstream engines read it. They do not amend it. An engine that believes the evidence is wrong records that judgement in **its own** output — it does not edit the evidence to match.

---

## Rule 4 — Traceability

**Every extracted value must maintain:**

1. **Source** — where in the artifact it came from.
2. **Confidence** — how reliable the extraction is.
3. **Uncertainty** — whether, and why, doubt exists.

These travel with the value permanently. They are not stripped at the engine boundary, not summarised into a single score, and not dropped by any downstream engine — including the ones that read the Confidence Report much later, in Clarification and Validation.

---

## Rule 5 — Low Confidence Handling

**Low confidence does not trigger guessing.**

Low confidence creates:

- **Uncertainty markers** — recorded on the value, with a reason.
- **A possible future clarification requirement** — a candidate for a human question later.

It does **not** create:

- A guessed value.
- A default value.
- A silently omitted field.
- An upgraded confidence score.

### Who acts on it, and when

The Input Engine only **marks** uncertainty. Whether an uncertainty is material enough to block posting is judged much later, by the Clarification Engine's [`uncertainty_detection`](../src/engines/clarification_engine/uncertainty_detection/). The Input Engine never asks a question, never decides an uncertainty is unimportant, and never resolves one.

---

# 4. Boundary Contract

Every engine boundary must define all nine items ([`DATA_FLOW.md` §8](DATA_FLOW.md#8-boundary-contract-requirement)). For Input → Understanding:

| # | Item | Definition |
|---|---|---|
| 1 | **Input artifact** | Raw artifact — photo, camera capture, image upload, PDF, scan, handwritten note, Excel file, email content, structured metadata, receipt, bill, or other supporting accounting document — plus an **optional Human Business Description**. |
| 2 | **Output artifact** | **Document Evidence Object** — including the optional **Human Business Context** when the user supplied one. |
| 3 | **Artifact creator** | The Input Engine (parent), assembling its four sub-engines' outputs and assigning the Document ID. |
| 4 | **Artifact owner** | The **Input Engine**, permanently. |
| 5 | **Allowed transformation** | The Understanding Engine may **read**, **analyze** and **reference** the Document Evidence Object, and produce its own artifact from it. |
| 6 | **Forbidden transformation** | It may **not** modify, rewrite, delete, remove uncertainty from, or change confidence in the Document Evidence Object. Artifacts are immutable after creation. |
| 7 | **Decision authority** | Input decides extraction method, extraction confidence and document structure. Understanding decides business event interpretation, entity relationships and the business story. Neither may make the other's decision. |
| 8 | **Uncertainty movement** | Confidence scores, uncertainty markers, reliability information and risky fields cross intact. **Evidence provenance crosses intact** — Source Type, Source ID, Evidence Reference, Timestamp, Confidence and Corroborated travel with every fact, and the receiver may never merge origins into an anonymous fact. A human note is evidence, not truth: it may never be treated as confirmed fact and never raises Evidence Reliability by existing. Understanding confidence may never exceed the evidence reliability it received. Uncertainty is only ever described more precisely — never removed. |
| 9 | **Failure movement** | The Input Engine does not halt the pipeline. Unreadable regions, damaged artifacts and failed extractions cross the boundary **as low confidence and named uncertainty**, not as errors. A Validation finding that the data are unsound returns to Input — or to Clarification, if a human can supply what is missing ([`DATA_FLOW.md` §4.4](DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on)). |

## Engine 2 receiving rules

The Understanding Engine must:

1. **Respect confidence** — a value extracted at 40% is not treated as a value known at 100%.
2. **Preserve uncertainty** — every uncertainty marker received travels forward.
3. **Trace understanding back to evidence** — every fact it produces points to the evidence that produced it.
4. **Never modify source evidence** — the Document Evidence Object is read-only to it, permanently.

## Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

The Input Engine defines what the Document Evidence Object asserts. If the Understanding Engine disagrees with the evidence, it records that disagreement in **its own** artifact — it never amends the evidence to match.

---

# 5. What This Boundary Protects

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

The Input Engine extracts what exists. The Understanding Engine determines what it means.

If the Input Engine were permitted to send conclusions, three things would break at once:

- **Errors would become untraceable.** A wrong conclusion looks identical to a correct one downstream; a wrong *observation* can be checked against the artifact.
- **Uncertainty would collapse.** A conclusion carries one confidence; the observations behind it carry several, and the difference is exactly what a good question is built from.
- **Reasoning would happen twice, differently.** Two engines interpreting the same document would eventually disagree, and nothing in the system would be able to say which was right.

---

## Related documents

- [`ENGINE_1_INPUT_ENGINE_RULES.md`](ENGINE_1_INPUT_ENGINE_RULES.md) — the Input Engine specification.
- [`DATA_FLOW.md`](DATA_FLOW.md) — every artifact in the pipeline, and the rules that govern movement.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
