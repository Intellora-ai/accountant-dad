# brain — the Knowledge Brain

> **Defined as of the Engine 4 specification lock.** This directory's role was reserved and undefined from Phase 1 until now.
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The **Knowledge Brain** is the system-wide knowledge provider used by multiple engines.

**It is not an engine. It is not a decision maker.** It holds what the system *knows*; it holds none of what the system *decides*.

> **Knowledge flows into engines. Decision authority never leaves engines.**

## What it owns

Reusable knowledge only:

- Accounting standards.
- Indian accounting rules.
- GST guidance.
- Company accounting policies.
- Chart of accounts references.
- Historical accounting patterns.
- Accounting terminology.
- Reference material.
- Previously resolved clarification patterns.

## What it never owns

- **Decisions** — every decision belongs to the engine responsible for it.
- **Artifacts** — it creates none, owns none, and versions none.
- **Confidence** — the four confidence types belong to Engines 1, 2, 3 and 4.
- **Workflow** — it never routes, orchestrates or sequences anything.

## Interface

Identical for every engine. No engine gets a privileged channel.

| | |
|---|---|
| **An engine may request** | Standards, rules, guidance, terminology, references and historical patterns relevant to a stated question. |
| **The Brain returns** | Knowledge, with its source reference and the Brain's own confidence **in the knowledge** — never in the decision. |
| **The Brain must never return** | A decision · a recommended treatment · an approval · a ledger to use · a rate to use · an instruction of any kind. |
| **Determinism** | **Advisory, never binding.** The Brain informs; it does not constrain. |
| **May engines ignore it?** | **Yes, always.** An engine that acts against Brain knowledge records why in its own reasoning. |
| **Ownership** | Unchanged by the exchange. The engine that asked still owns every decision it makes with the answer. |

### The distinction that matters

```text
✓ Engine asks:    "What does the standard say about capitalising a laptop?"
  Brain returns:  the standard, its source, and its confidence in that reading.
  Engine decides: asset or expense — and owns that decision.

✗ Brain returns:  "Treat as Office Equipment."
```

The second is a decision wearing knowledge's clothing. The Brain may state what a rule says and what it implies; it may never state what should be done.

## Boundary

The Brain **may never**:

- **Rewrite the Human Business Description.** It may use a user's plain-English note to improve interpretation; it may never restate, tidy, summarise or normalise it, and never treat it as confirmed fact.
- Create clarification requests.
- Approve clarification.
- Make accounting decisions.
- Override engine outputs.
- Become a hidden decision maker by returning knowledge shaped as an instruction.

The last is the failure this boundary exists to prevent. A knowledge provider that answers *"what should I do?"* instead of *"what is true?"* has taken authority no one granted it, and nothing downstream can tell that a decision was made outside the engine that owns it.

## Why knowledge and authority are separated

Three properties depend on it:

- **Decisions stay traceable.** A decision made by an engine cites its own reasoning. A decision made by a shared service cites nothing an auditor can follow.
- **Knowledge can be wrong without being catastrophic.** An advisory answer an engine may reject is a suggestion; a binding one is a silent single point of failure across every engine at once.
- **Ownership stays countable.** Every decision has exactly one owner. A service that decides would be an owner appearing in no authority table.

## Status

Empty by design. No knowledge content is added until implementation begins.

## Related documents

- [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md` §8](../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#8-knowledge-brain-boundary) — the Knowledge Brain boundary.
- [`docs/SYSTEM_BOUNDARIES.md`](../../docs/SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
- [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md) — artifact ownership, decision authority, confidence, versioning.
