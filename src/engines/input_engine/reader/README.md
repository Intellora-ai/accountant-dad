# reader

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Somebody must actually get the characters off the page.

## Responsibility

Owns extraction of everything written on the normalised artifact, together with where on the page each piece of text sits.

## Input

The normalised artifact from [`cleaner`](../cleaner/).

## Output

Raw extracted text with layout and positional information, and per-region extraction quality signals.

## Boundary

Cannot assign meaning to what it extracts — it may extract `27AAECS1234F1Z5`, it may not conclude that this is a GSTIN. Cannot correct suspected extraction errors. Cannot reorder or restructure the text.

## Future Notes

- Digital-native files (a PDF with a text layer) and scans are different extraction problems with very different confidence characteristics; both paths end at the same output shape.
- Positional information is not optional — [`parser`](../parser/) cannot recover table structure without it.
