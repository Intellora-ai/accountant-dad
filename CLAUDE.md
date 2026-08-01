# CLAUDE.md

> **Phase 1 placeholder.** The sections below are reserved and intentionally empty. They will be filled in a later phase.

## Binding now

**The architecture is the source of truth. Ask before changing it.**

This applies to every engine, every sub-engine, every boundary and every artifact defined in [`docs/`](docs/). Do not add, remove, merge or rename a component. Do not move a responsibility. Do not create a path between engines that [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) does not define. If something appears wrong, **stop and ask** — a mis-drawn boundary is corrected in the documentation, deliberately, before any code depends on it. Never worked around in an implementation.

Read before doing anything in this repository:

**System-wide**

1. [`docs/MVP_ARCHITECTURE.md`](docs/MVP_ARCHITECTURE.md)
2. [`docs/ENGINE_RESPONSIBILITIES.md`](docs/ENGINE_RESPONSIBILITIES.md)
3. [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](docs/SUB_ENGINE_RESPONSIBILITIES.md) — canonical sub-engine map
4. [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md)
5. [`docs/SYSTEM_BOUNDARIES.md`](docs/SYSTEM_BOUNDARIES.md)

**Locked engine specifications**

6. [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](docs/ENGINE_1_INPUT_ENGINE_RULES.md) — Engine 1: Input Engine
7. [`docs/COMMUNICATION_RULES_INPUT_ENGINE.md`](docs/COMMUNICATION_RULES_INPUT_ENGINE.md) — Engine 1 → Engine 2 contract

**Precedence.** `SUB_ENGINE_RESPONSIBILITIES.md` is canonical for the system-wide map. A locked engine specification is the deeper authority for that engine's allowed and forbidden actions, output contracts and failure behaviour. Where they overlap they must agree — a disagreement is a defect to fix, not a choice to make.

**Artifact naming.** The Input Engine's output has exactly one name: **Document Evidence Object**. `Structured Document` and `Confidence Report` are its components, never the artifact's name. No engine may create alternative names, and no duplicate representation may exist.

---

## Architecture Rules

*Reserved. To be written.*

---

## Coding Rules

*Reserved. To be written.*

---

## AI Assistant Behavior Rules

*Reserved. To be written.*
