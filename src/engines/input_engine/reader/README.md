# reader

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#82-reader).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Somebody must actually get the characters off the page. Extract visible information from documents.

## Responsibility

Owns reading and recognition — extraction of everything written on the cleaned document representation, printed text and handwriting alike, together with where on the page each piece of text sits.

## Input

The cleaned document representation from [`cleaner`](../cleaner/).

## Output

- Raw extracted information — text, numbers, dates, names, tables, handwriting output.
- Source locations.
- Extraction confidence.

## Boundary

**Can:** detect visible characters · extract printed text · extract handwriting · identify document regions.

**Cannot:** understand transaction meaning · fix accounting mistakes · guess unclear words · infer missing business information.

It may extract `27AAECS1234F1Z5`; it may not conclude that this is a GSTIN. It cannot reorder or restructure the text.

## Decision Authority

**Owns.** Extraction observations.

**Determines.** Detected characters, regions and tables · extraction confidence signals.

**Cannot.** Understand meaning.

No other component may override this result — not a sibling sub-engine, and not the parent Input Engine, which assembles outputs but never overrides them. See [`docs/ENGINE_1_INPUT_ENGINE_RULES.md` §3A](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#3a-decision-authority).

## Failure Behaviour

**Return extracted information with confidence levels and uncertainty.**

- An unclear character or word is emitted as unclear, with its confidence — never resolved by guessing.
- A region that could not be read at all is reported as unread, not omitted silently.
- Source locations are emitted even for low-confidence extractions; that is what makes a later human check possible.

## Future Notes

- Digital-native files (a PDF with a text layer), scans, and handwriting are three different extraction problems with very different confidence characteristics; all three end at the same output shape.
- Source locations are not optional — [`parser`](../parser/) cannot recover table structure without them.
