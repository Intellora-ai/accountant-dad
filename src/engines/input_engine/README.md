# Input Engine

> Engine 1 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*What does this document actually say?*

Nothing downstream can be trusted if the reading of the document cannot be trusted. This engine exists so that extraction is a solved and measured problem before anyone tries to understand the transaction.

## Responsibility

Turn a raw artifact into clean, readable, structured data with a confidence score.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`cleaner`](cleaner/) | The physical quality of the artifact |
| [`reader`](reader/) | Extraction of what is written |
| [`parser`](parser/) | Structure — fields, tables, line items |
| [`confidence`](confidence/) | Honest measurement of trustworthiness |

## Input

A raw artifact as received: scan, photograph, PDF, or digital file. Nothing else — this engine has no knowledge of the company, its books, or its history.

## Output

- **Structured Document** — the artifact's contents as fields, tables and rows, faithful to what is written.
- **Confidence Report** — per-field and overall trust scores, plus the specific weak regions.

## Boundary

**Cannot make accounting decisions.** Cannot interpret business meaning. Cannot correct, complete or improve content it believes wrong — low confidence is reported, never repaired. Cannot discard content it judges irrelevant. Cannot consult company master data or any downstream engine.

## Future Notes

- Document-type detection likely belongs here, as a property of the artifact, not as a business conclusion.
- The Confidence Report is consumed by two distant engines (Clarification and Validation), so its shape should be designed for them, not only for internal use.
