# AI Accountant

**Turns a real business document into a correct, posted accounting entry — and knows when to ask instead of guess.**

A business generates paper all day: purchase invoices, sales invoices, receipts, payment advices, credit and debit notes. A human accountant reads each one, works out what actually happened commercially, decides how it should be recorded, asks about anything ambiguous, checks the result, and enters it into Tally.

This system performs that same sequence — imitating the accountant's *reasoning order*, not their keystrokes.

Three commitments define it:

1. **Understand before deciding.** What happened in business terms is established before any accounting treatment is considered. A document is not an entry.
2. **Doubt is a first-class output.** When the system is unsure it says so, names precisely what would resolve it, and asks. It never silently defaults.
3. **Nothing reaches the books unvalidated.** A decision is judged by something that did not make it, and the posting itself is recorded immutably.

Intended for accounting practices and business accounts functions working on Indian GST-regime books, posting into Tally.

---

## ⚠️ Current status: specification

**There is no code in this repository. That is the point of this phase.**

What exists is the thing that has to exist first: an unambiguous statement of what each part of the system owns, and what it is forbidden to do.

| Phase | State |
|---|---|
| Architecture foundation — 6 engines, 39 sub-engines, system-wide docs | ✅ Complete |
| **Engine 1 — Input Engine** specification lock | ✅ **Locked** |
| Engines 2–6 specification locks | Not yet started |

### Phase 1 does **not** include

OCR · AI models · LLM calls · prompt systems · database · API · Tally integration · accounting logic · tax logic · dependencies

Every one of those is a later phase.

---

## The six engines

Each engine is one **cognitive stage**, not one technical layer.

| # | Engine | The question it answers |
|---|---|---|
| 1 | **Input** | *What does this document actually say?* |
| 2 | **Understanding** | *What happened in the business?* |
| 3 | **Accounting** | *How should it be recorded?* |
| 4 | **Clarification** | *What do we still need to ask a human?* |
| 5 | **Validation** | *Is this safe to post?* |
| 6 | **Tally** | *Put it in the books, and record that we did.* |

The split exists because these are genuinely different kinds of thinking, and collapsing any two destroys a property that makes the system trustworthy:

- An engine that could both **decide and ask** would always prefer to guess, because guessing is cheaper.
- A decision reviewed by **its own author** is not reviewed.
- Execution that could **reason** would confuse a dropped connection with an accounting error.

The boundaries are the architecture. They are documented as hard prohibitions in [`docs/SYSTEM_BOUNDARIES.md`](docs/SYSTEM_BOUNDARIES.md).

---

## Flow

```text
Input
 ↓
Understanding
 ↓
Accounting Decision
 ↓
Clarification (if required)
 ↓
Validation
 ↓
Tally Execution
```

Work moves forward only. The two backward paths are explicit returns: Clarification returning resolved facts to Accounting, and Validation returning a rejection to a **named** stage. Nothing reaches Tally that Validation has not approved.

Artifact by artifact: [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md).

---

## Repository map

```text
docs/
  MVP_ARCHITECTURE.md ............ mission, the six engines, the full semantic tree
  ENGINE_RESPONSIBILITIES.md ..... per engine: mission, owns, inputs, outputs, cannot do
  SUB_ENGINE_RESPONSIBILITIES.md . per sub-engine: purpose, responsibility, in, out, boundary
  DATA_FLOW.md ................... what artifact crosses each arrow
  SYSTEM_BOUNDARIES.md ........... forbidden behaviour, as absolutes

  ENGINE_1_INPUT_ENGINE_RULES.md ....... Engine 1 specification — LOCKED
  COMMUNICATION_RULES_INPUT_ENGINE.md .. how Engine 1 talks to Engine 2 — LOCKED

src/
  engines/       6 engines, 39 sub-engines — each a folder with a README
  brain/         reserved — role not yet defined
  rules/         reserved — declarative accounting and tax rule content
  models/        reserved — internal representations of domain concepts
  schemas/       reserved — the shape of artifacts passed between engines
  services/      reserved — shared infrastructure concerns
  tests/         reserved — verification

CLAUDE.md        architecture, coding and assistant rules (placeholder)
```

Every engine and sub-engine folder holds exactly one `README.md` stating its **purpose, responsibility, input, output** and **boundary**. The structure is three levels deep and stops there.

---

## Where to start reading

1. [`docs/MVP_ARCHITECTURE.md`](docs/MVP_ARCHITECTURE.md) — what the system is
2. [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) — how information moves
3. [`docs/SYSTEM_BOUNDARIES.md`](docs/SYSTEM_BOUNDARIES.md) — what nothing may do
4. [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](docs/ENGINE_1_INPUT_ENGINE_RULES.md) — the first engine, in full

---

## Contributing during Phase 1

The architecture is the source of truth. Do not add, remove, merge or rename an engine or sub-engine. Do not move a responsibility between components. Do not create folders inside an engine or sub-engine.

**If something in the architecture seems wrong, it may well be — stop and ask.** It gets corrected in the documentation, deliberately, before any code depends on it.
