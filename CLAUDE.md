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
7. [`docs/COMMUNICATION_RULES_INPUT_ENGINE.md`](docs/COMMUNICATION_RULES_INPUT_ENGINE.md) — Engine 1 → Engine 2 boundary
8. [`docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](docs/ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — Engine 2: Understanding Engine
9. [`docs/COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](docs/COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — Engine 2 → Engine 3 boundary
10. [`docs/COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](docs/COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) — inside Engine 2
11. [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md) — Engine 3: Accounting Engine
12. [`docs/COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md`](docs/COMMUNICATION_RULES_ACCOUNTING_INTERNAL.md) — inside Engine 3

**Precedence.** `SUB_ENGINE_RESPONSIBILITIES.md` is canonical for the system-wide map. A locked engine specification is the deeper authority for that engine's allowed and forbidden actions, output contracts and failure behaviour. Where they overlap they must agree — a disagreement is a defect to fix, not a choice to make.

**Artifact naming.** One name per artifact. No engine may create alternative names, and no duplicate representation may exist.

| Artifact | Owner | Components — never used as the artifact's name |
|---|---|---|
| **Document Evidence Object** | Input Engine | Document ID · Source references · Structured Document · Confidence Report |
| **Business Understanding Object** | Understanding Engine | Transaction Story · Supporting Understanding Data · Identified Unknowns · Confidence Assessment |
| **Accounting Decision** | Accounting Engine | Decision ID · Decision Status · accounting treatment · ledger classification · debit entries · credit entries · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts — **name final** |

**Artifact ownership.** Every artifact has exactly one owner: the engine that creates it. Artifacts are **immutable after creation**. Other engines may read, analyze and reference; they may never modify, rewrite, delete, remove uncertainty, or change confidence. New information produces a **new version authored by the owner**, never an edit in place. See [`docs/DATA_FLOW.md` §6–8](docs/DATA_FLOW.md#6-artifact-ownership).

**Decision authority.** Authority belongs only to the engine responsible for that decision, and no parent engine may override its own sub-engines' outputs. **No sub-engine creates another sub-engine's decision.** Parent assembly is **mechanical** — combine, organize, structure; never change a recommendation, remove uncertainty, or increase confidence. Per-engine table in [`docs/DATA_FLOW.md` §7](docs/DATA_FLOW.md#7-decision-authority); internal tables in each locked engine specification.

**IDENTITY ≠ INTELLIGENCE.** **IDs identify objects. They do not influence reasoning.** Document ID, Decision ID, Transaction ID, User ID and any future identifier exist only for identity, traceability, lifecycle tracking and audit history. None may influence ledger selection, journal creation, tax treatment, validation outcome, confidence, or any future decision. See [`docs/DATA_FLOW.md` §9](docs/DATA_FLOW.md#9-identity--intelligence).

**Confidence only decreases.** **Confidence can only decrease downstream unless new evidence is introduced.** Later engines may maintain, reduce or request clarification — never raise. Evidence → Understanding → Decision → Validation. See [`docs/DATA_FLOW.md` §10](docs/DATA_FLOW.md#10-confidence-across-engines).

**One contract per boundary.** The sending engine owns the contract of what leaves it; the receiving engine references it. No duplicate communication documents.

---

## Architecture Rules

*Reserved. To be written.*

---

## Coding Rules

*Reserved. To be written.*

---

## AI Assistant Behavior Rules

*Reserved. To be written.*
