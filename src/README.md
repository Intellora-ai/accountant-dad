# src

> **Phase 1 placeholder — no implementation.** There is no code in this repository yet, by design.

## What is here

| Directory | Contains |
|---|---|
| [`engines/`](engines/) | The six engines and their 39 sub-engines. The system itself. |
| [`brain/`](brain/) | **The Knowledge Brain** — the system-wide knowledge provider. Advisory, never binding; owns no decisions, artifacts, confidence or workflow. |
| [`rules/`](rules/) | *Reserved* — declarative accounting and tax rule content. |
| [`models/`](models/) | *Reserved* — internal representations of domain concepts. |
| [`schemas/`](schemas/) | *Reserved* — the shape of the artifacts passed between engines. |
| [`services/`](services/) | *Reserved* — shared infrastructure concerns. |
| [`tests/`](tests/) | *Reserved* — verification. |

## The rule that governs this tree

The architecture is the source of truth. The folder structure is not a suggestion about where code might go — it is the statement of who owns what.

- No engine or sub-engine may be added, removed, merged or renamed.
- No responsibility may move between components.
- No folder may be created inside an engine or sub-engine.

If something in the architecture seems wrong, **stop and ask.** See [`docs/SYSTEM_BOUNDARIES.md`](../docs/SYSTEM_BOUNDARIES.md).

## Read first

1. [`docs/MVP_ARCHITECTURE.md`](../docs/MVP_ARCHITECTURE.md) — mission, the six engines, the full tree.
2. [`docs/DATA_FLOW.md`](../docs/DATA_FLOW.md) — what moves between them.
3. [`docs/SYSTEM_BOUNDARIES.md`](../docs/SYSTEM_BOUNDARIES.md) — what none of them may do.
