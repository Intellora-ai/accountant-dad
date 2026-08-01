# Communication Rules — Understanding Engine, Internal

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.


> How the seven Understanding sub-engines communicate with one another.
>
> Companion to [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md). **Specification only — no implementation.**
>
> This document governs communication *inside* Engine 2. The boundary into it is governed by [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md).

---

# 1. Sub-Engines Do Not Communicate Freely

**They communicate through controlled outputs.**

There is no shared state, no back-channel, and no sub-engine reaching into another's working. A sub-engine sees exactly one thing from a sibling: that sibling's published **Result**.

This is what makes each Result checkable. A fact that arrived through a side channel cannot be traced, and an untraceable fact is indistinguishable from an invented one.

---

# 2. Dependency Graph

**The Understanding Engine is not a flat pipeline.** The order is load-bearing.

```text
Document Evidence Object
        ↓
Transaction Understanding          ← establishes the base event
        ↓
        ├── Party Understanding    ← enrich that event
        ├── Item Understanding
        ├── Payment Understanding
        └── Timeline Understanding
        ↓
Business Context                   ← requires the previous understanding
        ↓
Story Builder                      ← final assembly layer
        ↓
Business Understanding Object
```

## Why the order exists

- **Transaction Understanding runs first** because it establishes the base event, and the event kind changes how everything else is read. The same name means a different thing on a purchase than on a sales return; the same date means a different thing on an invoice than on a receipt.
- **Party, Item, Payment and Timeline run next**, each receiving the event nature. They are independent of one another and may proceed in any order among themselves.
- **Business Context requires the preceding understanding** — "is this normal for this business?" cannot be answered before knowing what *this* is.
- **Story Builder is last** because it assembles, and there is nothing to assemble until the six Results exist.

---

# 3. What Each Sub-Engine Owns

| Sub-engine | Owns the question |
|---|---|
| **Transaction Understanding** | What happened? |
| **Party Understanding** | Who is involved? |
| **Item Understanding** | What goods/services exist? |
| **Payment Understanding** | How was money involved? |
| **Timeline Understanding** | When did events occur? |
| **Business Context** | Why did this happen? |
| **Story Builder** | Combine understanding into one coherent story. |

**Business Context owns "why" as *indicators*, not as conclusion.** It records observed clues to why a transaction exists in this business's operations. It never determines intent — see [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §8.6](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#86-business-context).

Each sub-engine owns **only** its domain. No sub-engine answers another's question, even when it can see the answer.

---

# 4. Communication Rules

---

## Rule 1 — Sub-engines communicate only through defined outputs

Each sub-engine publishes exactly one named **Result**, and that Result is the entirety of what siblings may see.

| Sub-engine | Publishes |
|---|---|
| Transaction Understanding | Transaction Understanding Result |
| Party Understanding | Party Understanding Result |
| Item Understanding | Item Understanding Result |
| Payment Understanding | Payment Understanding Result |
| Timeline Understanding | Timeline Understanding Result |
| Business Context | Business Context Result |
| Story Builder | Business Understanding Object |

Contents of each: [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §7](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#sub-engine-output-contracts).

---

## Rule 2 — No direct hidden communication

No shared mutable state. No side channels. No implicit coupling through anything other than a published Result.

If a sub-engine needs something a sibling knows, that something must be part of the sibling's Result — which means it is named, traceable, and checkable. If it is not in the Result, it is not available, and the correct response is to record an unknown.

---

## Rule 3 — No sub-engine modifies another sub-engine's result

A Result is **read-only** to every sibling, permanently.

A sub-engine that believes a sibling's Result is wrong does not correct it. It records the disagreement in its own Result as a **conflict** — see [Conflict Handling](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md#10-conflict-handling).

This holds for Story Builder too. Assembly is not permission to edit.

---

## Rule 4 — Every output preserves confidence

Every Result carries confidence. No Result may omit it, and no Result may raise it.

The propagation rule binds throughout:

```text
Understanding Confidence  ≤  Evidence Reliability
```

A sub-engine consuming a sibling's Result inherits that Result's uncertainty. It cannot become more certain than what it consumed.

---

## Rule 5 — Every output preserves evidence references

Every fact in every Result points back to the evidence that produced it, in the Document Evidence Object.

A fact with no evidence reference cannot appear in a Result. There is no mechanism for producing one, and that is deliberate: it is the structural reason this engine cannot hallucinate.

---

## Rule 6 — Story Builder consumes outputs but cannot rewrite history

Story Builder receives all six Results and creates the Business Understanding Object.

| Story Builder CAN | Story Builder CANNOT |
|---|---|
| Combine six sub-engine outputs | Change source observations |
| Organize information | Override sub-engine results |
| Create the Transaction Story component | Resolve conflicts |
| Create the Business Understanding Object | Choose the "correct" interpretation when evidence disagrees |
| | Remove unknowns |
| | Increase confidence |
| | Create accounting conclusions |

The six Results travel into the Business Understanding Object as **Supporting Understanding Data**, unaltered. The Transaction Story is built *from* them; it does not replace them, and a downstream engine may always read what the story was built on.

**Story Builder creates the artifact. The Understanding Engine owns it.** Story Builder does not become an independent owner.

---

# 5. What These Rules Protect

Every rule above defends one property: **a fact in the Business Understanding Object can be traced to the evidence that produced it, and its uncertainty is the uncertainty that evidence actually had.**

Break any one and that property goes:

- Allow a side channel, and a fact appears with no source.
- Allow a sub-engine to edit a sibling's Result, and the author of a fact is no longer knowable.
- Allow confidence to be raised, and the number stops meaning anything.
- Allow Story Builder to resolve a conflict, and a choice was made that nothing downstream can see.

None of these fail loudly. They all produce output that looks better than the honest version — which is exactly why they are prohibitions rather than guidance.

---

## Related documents

- [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — the Understanding Engine specification.
- [`COMMUNICATION_RULES_INPUT_ENGINE.md`](COMMUNICATION_RULES_INPUT_ENGINE.md) — the inbound boundary contract.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, boundary contract requirement.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
