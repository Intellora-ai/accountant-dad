# parser

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Loose text is not usable; the document's own structure must be recovered.

## Responsibility

Owns the conversion of extracted text into structure — fields, key–value pairs, tables, and line-item rows — faithful to how the document is laid out.

## Input

Raw extracted text with layout information from [`reader`](../reader/).

## Output

The **Structured Document**: the artifact's contents as named fields, tables and rows.

## Boundary

Cannot decide business meaning — it may identify a field labelled "Supplier", it may not conclude that party is a supplier for accounting purposes. Cannot compute, derive or infer a value that is not written. Cannot fill a field that is absent.

## Future Notes

- "Faithful to the document" includes preserving a stated total that does not equal the sum of its lines. The discrepancy is a fact; reconciling it belongs to Validation.
- Field labels are the document's words, not the system's vocabulary. Mapping them to meaning is the Understanding Engine's job.
