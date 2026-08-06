# ARCHITECTURE.md

> **Index, not a copy.** The architecture is **locked at `a47271d`** and lives across 23
> documents in `docs/`. This file is the map. Where it and a locked document disagree,
> **the locked document wins and this file is wrong** (§M).

## Precedence — locks win

```
System Invariants › Locked Architecture Decisions › Engine Specifications
                  › Communication Contracts › READMEs
```

## Highest authority

| Document | What it holds |
|---|---|
| [`docs/SYSTEM_INVARIANTS.md`](docs/SYSTEM_INVARIANTS.md) | the 13 invariants. Every other document is subordinate |
| [`docs/FORWARD_DEPENDENCY_INVENTORY.md`](docs/FORWARD_DEPENDENCY_INVENTORY.md) | required before locking any engine |

## System-wide (frozen)

- [`docs/MVP_ARCHITECTURE.md`](docs/MVP_ARCHITECTURE.md) — the six engines, the full semantic tree
- [`docs/ENGINE_RESPONSIBILITIES.md`](docs/ENGINE_RESPONSIBILITIES.md) — per engine: mission, owns, inputs, outputs, cannot do
- [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](docs/SUB_ENGINE_RESPONSIBILITIES.md) — 39 sub-engines
- [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) — what artifact crosses each arrow
- [`docs/SYSTEM_BOUNDARIES.md`](docs/SYSTEM_BOUNDARIES.md) — forbidden behaviour, as absolutes

## The six engines

```
1 Input  →  2 Understanding  →  3 Accounting  →  4 Clarification  →  5 Validation  →  6 Execution
```

Specifications: `docs/ENGINE_1_INPUT_ENGINE_RULES.md` … `docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`
Boundary contracts: `docs/COMMUNICATION_RULES_*.md` (ten of them)

**Engine 1 only** is released for implementation (Amendment 3, 2026-08-05) —
[`docs/ENGINE_1_ARCHITECTURE.md`](docs/ENGINE_1_ARCHITECTURE.md). Engines 2–6 remain
frozen: no engine reasoning, no accounting logic, no tax logic, no AI calls, no Tally
posting.

## Standing rules that erode easily

- **Six canonical artifacts, one name each.** Document Evidence Object · Business
  Understanding Object · Accounting Decision · Clarification Request · Validation
  Decision · Execution Result. A component is never used as an artifact's name.
- **Artifacts are immutable.** Correction means a new version, never an edit.
- **IDENTITY ≠ INTELLIGENCE.** IDs identify. They never influence reasoning.
- **Confidence changes only when evidence changes** — never because an engine reasoned harder.
- **Knowledge is shared; authority is not.** The Brain is advisory, never binding.
- **Engine 3 uses NO LLM.** **Validation MUST be deterministic** — an LLM may explain a
  failure; it never decides correctness.

**Do not add, remove, merge or rename an engine or sub-engine. Do not move a
responsibility. If something looks wrong, stop and ask** — a mis-drawn boundary is
corrected in the documentation, deliberately, before any code depends on it.
