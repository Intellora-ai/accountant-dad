# ROADMAP.md

Single source of truth for what is being built and in what order. Updated after every
milestone.

**Subordinate to `CLAUDE.md`.** Where this file and a locked document in `docs/`
disagree, the locked document wins and this file is wrong (§M).

Last updated: **2026-08-05**

---

## Mission

A user photographs a document or writes a sentence, and an **AI accountant** does the
accounting — as well as a human one. MVP: Tally, Indian GST.

**Two absolute non-goals.** It must never hallucinate. It must never post a wrong entry.
The six-engine architecture exists to make each of those *structurally impossible*
rather than merely unlikely.

---

## Status at a glance

| | |
|---|---|
| Six-engine architecture | ✅ **Locked** — `a47271d` |
| 23 documents · 39 sub-engines · 10 contracts | ✅ Complete |
| Mandatory CI gates | ✅ **7 of 7 green** — mutation **99.3%** vs floor 93 |
| Gates that actually *bind* a merge | ⚠️ **6 of 23**. `mutation` passes but is not required. `merge gate` binds nothing |
| Engine 1 | 🔄 4 of 4 sub-engines written · 3 tested and landed · **not integrated** |
| Engines 2–6 | 🔒 Frozen. Stubs only |
| Ground truth | ❌ **None exists.** No accuracy claim about this system is provable, so none is made |
| Accounting Brain | 🔄 41 evidence documents · concepts and rules growing · every citation six-layer verified |

---

## Phase 0 — Architecture · ✅ COMPLETE

**Objective.** Decide what the system is *allowed to be*, before any code.

**Delivered.** Six engines, 39 sub-engines, 10 boundary contracts, 13 system invariants,
the data flow, the absolute boundaries. Frozen at `a47271d`.

**Completion criteria.** Met. Changes now require a §M amendment.

---

## Phase CI — The gates that make everything else honest · 🔄 IN PROGRESS

**Objective.** A gate that runs is not a gate that binds. Get every gate to (a) pass on
correct code, (b) **fail on deliberately broken code**, then (c) become required.

**Delivered.**
- 23 independent Check Runs across six workflows
- Branch ruleset `20249495` — deletions blocked, force-push blocked, PR required, bypass
  list empty, every required check pinned to `integration_id: 15368`
- The merge gate proven against 11 attacks, 11 blocks (`docs/CI_S2_EVIDENCE.md`)
- **Mutation gate finishes and passes** — 24m14s, 99.3% (`d85861c`)

**Remaining.**
- `T-014` promote `mutation` to required — needs the broken-code proof first
- `T-042` promote `merge gate` — **last**, when it can actually pass. Eight placeholders
  `exit 1` by design and four cannot be implemented until P1/P2 produce artifacts

**Blockers.** Promoting a gate changes the branch ruleset, which needs the owner.

**Completion criteria.** `merge gate` required, and it passes. Not before.

---

## Phase P1 — Human ceiling and golden set · 🔒 NOT STARTED

**Objective.** Establish what a competent human accountant achieves on these documents,
so any claim about the system has something to be measured against.

**Deliverables.** 25 documents · two independent labellers · a frozen ceiling ·
a sealed held-out set.

**Dependencies.** Human accountants. Real documents. Neither is an engineering problem.

**Blockers.** ⛔ **The owner has said they intend to replace this phase.** Stop and ask
before starting it.

**Open question, not yet answered.** `GOLDEN_DATASET.md:166` puts calibration at ~100
documents; the planned set is 16. That figure predates decision A5 removing the
document-level scalar, so it may be stale — but within-document clustering may make 16
inadequate regardless. **Re-derive before spending 6× the labelling effort** (`T-020`).

**Completion criteria.** A frozen ceiling number, with its measurement protocol, that
nobody may change afterwards.

---

## Phase P2 — Infrastructure · ✅ LARGELY COMPLETE

**Objective.** The scaffolding every engine needs, built before any engine reasoning.

**Delivered.** Artifact schemas · conformance predicates · domain models · Application
Layer skeleton · the sealing mechanism · CI gate implementations · document-ingestion
tooling · the whole of `tools/evidence` (six-layer citation verification).

**Completion criteria.** Met for everything Engine 1 depends on.

---

## Phase E1 — Engine 1, the Input Engine · 🔄 IN PROGRESS

**Objective.** Turn a photograph or a PDF into a Document Evidence Object: what is
written, where it sits, and how much of it can be trusted. **No meaning. No accounting.**

Authorised by **Amendment 3** (2026-08-05). Nothing outside Engine 1 is authorised by it.

**Deliverables.**

| Sub-engine | State |
|---|---|
| `cleaner` §1.1 | ✅ landed · deskew residual **0.0017 at 32°** |
| `reader` §1.2 | ✅ landed · PyMuPDF text layer, PaddleOCR otherwise |
| `parser` §1.3 | ✅ landed · Docling structure, never meaning |
| `confidence` §1.4 | 🔄 source written, tests in flight |
| engine assembly | ✅ landed · four parts → Document Evidence Object |
| `config` | 🔄 source written, tests in flight |
| `measurement` | 🔄 source written, tests in flight — **the only home the raw signal has** |
| integration | ⬜ **nothing yet runs a real document through all five** |
| benchmarks | ⏸ partial |

**Dependencies.** The locked architecture (`a47271d`) and the P2 artifact schemas. **Not
P1** — the blueprint makes Engine 1 depend on the Application Layer and the schemas, both
built. P1 gates the *measurement* of Engine 1, never its construction.

**Blockers.**
- **F-001** PyMuPDF is AGPL-3.0 and this is a hosted commercial product — owner decision
- **F-002** two OpenCV distributions in one environment — latent, reproducibility
- The 16 confidence parameters are all UNSET, which blocks *calibration* only

**Completion criteria.** All four sub-engines tested and green on CI · a real document
runs end to end · a measured performance number exists (there is none today, so no
performance claim is provable) · **and no accuracy claim until P1 produces a ceiling.**

---

## Phase E2–E6 · 🔒 FROZEN

Engine reasoning for Engines 2–6, accounting logic, tax logic, AI/LLM calls and Tally
posting all remain frozen. Each unlocks at its scheduled phase **and is asked for before
it is written.**

Two constraints in `TECHNOLOGY_STACK.md` are absolute and easy to erode, so they are
repeated here:

- **Engine 3 uses NO LLM and no AI reasoning.** The engine that decides the entry must be
  reproducible, inspectable and defensible; a model that reasons differently on two runs
  is none of those.
- **Validation MUST be deterministic.** An LLM may *explain* a failure. An LLM never
  decides correctness.

---

## The Accounting Brain · 🔄 CONTINUOUS

Not a phase — it grows alongside every engine, and **the real Brain is built inside P4,
before Engine 3.**

**Delivered.** 41 evidence documents, each declaring url · sha256 · kind · version.
Six-layer citation verification: document checksum · section exists · quote lies **inside**
that section · exact text under declared normalisation · label belongs to that document's
grammar · metadata agrees. Atomic concepts, rules, validations and exceptions, every
citation machine-checked.

**Standing rule.** Official government publication only. A blog, a Big-4 explainer or a
CA firm's summary is not a source — one wrong source poisons every claim built on it.

**Known gap.** No authoritative government publication of the **GSTIN check-digit
algorithm** was found. An honest gap is recorded rather than a plausible third-party page.

---

## What this roadmap deliberately does NOT include

- Any accuracy claim about the system. By Law 52 and Law 54 none is currently provable.
- Any confidence threshold. All 16 parameters are UNSET **by design**, and inventing one
  is forbidden.
- A planner, dispatcher or orchestrator as software. The execution framework is followed
  internally; it does not become a component until the architecture says it must.
- Engines 2–6, in any form beyond their stubs.
