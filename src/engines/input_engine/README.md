# Input Engine

> Engine 1 of 6. **Specification locked** — deep spec: [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md) · [`docs/COMMUNICATION_RULES_INPUT_ENGINE.md`](../../../docs/COMMUNICATION_RULES_INPUT_ENGINE.md).
>
> Canonical system-wide map: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What information exists in the document?*

The Input Engine is the **sensory layer** of the AI Accountant. Nothing downstream can be trusted if the reading of the document cannot be trusted, so extraction is a solved and *measured* problem before anyone tries to understand the transaction.

It never answers *"what does this transaction mean?"*

## Responsibility

Convert raw human accounting artifacts into reliable, structured evidence while preserving uncertainty.

Sub-engines and their output contracts:

| Sub-engine | Produces |
|---|---|
| [`cleaner`](cleaner/) | Cleaned document representation · quality issues detected · preservation status |
| [`reader`](reader/) | Raw extracted information · source locations · extraction confidence |
| [`parser`](parser/) | Structured fields · field mappings · missing field information |
| [`confidence`](confidence/) | Confidence scores · uncertainty markers · reliability assessment |

### Engine-level assembly

The **Input Engine itself** combines those four outputs into the Document Evidence Object and assigns the Document ID.

> The Input Engine owns the internal assembly of outputs from its four sub-engines into the Document Evidence Object. It does **not** own system-wide orchestration, engine routing, downstream reasoning, accounting decisions, or workflow control.

**No assembler sub-engine exists, and none may be added.** Architecture expands by making responsibilities clearer, not by adding components.

## Input

Photos · camera photo capture · images and image uploads · PDFs · scanned invoices · handwritten accounting notes · poor-quality human inputs · receipts · bills · supporting accounting documents.

Poor quality is a normal operating condition, not an exception. What varies is the confidence attached to what is read — never whether the artifact is accepted.

Every input preserves its **original source**, its **original information**, and its **document identity**. The engine has no knowledge of the company, its books, or its history.

## Output

One artifact: the **Document Evidence Object**.

```text
Document Evidence Object
├── Document ID
├── Source references
├── Structured Document ── extracted text · detected fields · document structure ·
│                          tables · field values · field locations
└── Confidence Report ──── confidence scores · uncertainty markers ·
                           reliability information · risky fields
```

Every extracted value preserves **where it came from**, **how reliable it is**, and **whether uncertainty exists**.

**Document ID exists only for identity, traceability, and lifecycle tracking. It carries no accounting meaning and must never influence accounting decisions.**

`Document Evidence Object` is the artifact's only name. `Structured Document` and `Confidence Report` name its components, never the artifact itself.

## Boundary

**MUST NEVER:** decide transaction type · decide accounting treatment · select ledger accounts · create journal entries · apply tax rules · understand business intent · ask accounting questions · fill missing information by guessing · modify original financial values.

Cannot correct, complete or "improve" content it believes is wrong — it reports low confidence instead. Cannot discard content it judges irrelevant. Cannot consult company master data, prior transactions, or any downstream engine.

**When information is unclear, report uncertainty. Never invent information.**

> **Input Engine provides evidence. Understanding Engine creates interpretation. The boundary between observation and reasoning must never be crossed.**

## Future Notes

- Document-type detection likely belongs here, as a property of the artifact, not as a business conclusion.
- The Confidence Report is consumed by two distant engines (Clarification and Validation), so its shape should be designed for them, not only for internal use.
- Handwritten and poor-quality inputs are the common case, not the edge case. Confidence granularity matters more there than anywhere else.
