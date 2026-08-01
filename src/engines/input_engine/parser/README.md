# parser

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#83-parser).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Loose text is not usable; the document's own structure must be recovered. Convert extracted information into structured evidence.

## Responsibility

Owns organization of extracted information — fields, key–value pairs, tables, and line-item rows — faithful to how the document is laid out.

## Input

Raw extracted information with source locations from [`reader`](../reader/).

## Output

- Structured fields.
- Field mappings.
- Missing field information.

Together these form the **Structured Document**, a component of the Document Evidence Object.

Example shape:

```text
Vendor:
Amount:
Date:
Invoice Number:
Items:
Payment Reference:
```

## Boundary

**Can:** map extracted information into fields · identify relationships between fields · preserve source references.

**Cannot:** decide debit or credit · choose ledger accounts · apply accounting rules · create transaction meaning.

It may identify a field labelled "Supplier"; it may not conclude that party is a supplier for accounting purposes. It cannot compute, derive or infer a value that is not written.

## Failure Behaviour

**Unknown fields remain unknown. Never fabricate values.**

- A field that is absent is recorded in missing field information as absent — not defaulted, not estimated, not omitted.
- "Absent", "zero" and "unreadable" are three different states and must remain distinguishable.
- Field mappings retain the source reference for every mapped value, so a wrong mapping can be traced.

## Future Notes

- "Faithful to the document" includes preserving a stated total that does not equal the sum of its lines. The discrepancy is a fact; reconciling it belongs to Validation.
- Field labels are the document's words, not the system's vocabulary. Mapping them to meaning is the Understanding Engine's job.
