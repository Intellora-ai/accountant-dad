# ROADMAP.md

Single source of truth for what is being built and in what order. Updated after every
milestone.

**Subordinate to `CLAUDE.md`.** Where this file and a locked document in `docs/`
disagree, the locked document wins and this file is wrong (§M).

Last updated: **2026-08-06**

**Measurement state — Law 56.** HEAD is `e921c3c`. It is **24 commits ahead of
`origin/ci/mutation-runs` and unpushed**, and GitHub returns *"No commit found for SHA"* for
it. **No gate has a current value.** The last CI-produced numbers belong to `7e0efe2` /
`f31e3cd` and are EXPIRED — `src/` moved `+2591 / −300` lines after them.

| Metric | Value | Commit | Source | Status |
|---|---|---|---|---|
| Mutation | 95.3% — killed 2324, survived 115, 919 not scoreable | `7e0efe2` | GitHub Actions run 31041552213 | **EXPIRED** |
| Coverage | 97.64%, effective floor 97.46% | `f31e3cd` | GitHub Actions run 31047186940 | **EXPIRED** |
| Anything at HEAD | — | `e921c3c` | — | **UNMEASURED** |

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
| **Repository builds** | 🔴 **NO.** `pytest tests/` dies at collection on `e921c3c` — `Exclusion` is imported and was never written (F-024). Law 1 |
| Mandatory CI gates at HEAD | **UNMEASURED.** All seven were green at `f31e3cd`; nothing since has been judged (F-026) |
| Gates that actually *bind* a merge | ⚠️ **6 of 23**, re-verified against ruleset `20249495` on 2026-08-06. `mutation` passes but is not required. `merge gate` binds nothing |
| Engine 1 | 🔄 Nine modules, one real pipeline, running end to end. **Three modules wired to nothing** (F-018) · **1712 lines of red-team tests not executing** (F-025) |
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
- **The mutation gate finishes.** Its cap was raised to 500 minutes at `66ab8cd` on the
  owner's number, closing F-014. Last completed run: **95.3%**, floor 93, in 3h 21m 01s
  (commit `7e0efe2`, GitHub Actions run 31041552213) — **now EXPIRED**

**Measured on `f31e3cd`, the last commit GitHub has judged:**

```
GREEN   build · typecheck · lint · unit tests · coverage · dependency scan
        mutation · conformance · conformance suite · secret scan · CodeQL
        typecheck · lint · tests · build   (legacy combined gate)
RED     adversarial tests · docker build · end-to-end · golden dataset
        integration tests · license scan · merge gate · negative controls
        negative controls 9 of 9 · performance · semgrep
```

**Remaining.**
- `T-052` **push the branch.** 24 commits have no CI result of any kind. Until they do,
  Law 55 cannot even be evaluated — a gate with no current value is neither above nor
  below its threshold
- `T-014` promote `mutation` to required — now needs a **re-measure at a pushed HEAD**
  before the broken-code proof, because the passing score expired
- `T-042` promote `merge gate` — **last**, when it can actually pass. Eight placeholders
  `exit 1` by design and four cannot be implemented until P1/P2 produce artifacts

**Blockers.** Promoting a gate changes the branch ruleset, which needs the owner. Pushing
is blocked behind the two reds, `T-050` and `T-051`.

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

| Component | State |
|---|---|
| `cleaner` §1.1 | ✅ landed · red-teamed. Four content-destruction defects (D1–D4) found and fixed as one class · deskew residual `0.0017 at 32°` is **UNVERIFIABLE** — F-023 shows nothing in the repo can establish which `cv2` measured it |
| `reader` §1.2 | ✅ landed · PyMuPDF text layer works · **OCR path still unproven on CI, and worse than recorded**: the skip guard could never be satisfied in *any* environment, so those 11 tests had never run anywhere (F-009, fixed at `202bed4`; whether they pass is UNMEASURED) |
| `parser` §1.3 | ✅ landed · Docling + Table Transformer · now consumes `reader`'s regions, which is what §1.3 always specified |
| `confidence` §1.4 | ✅ landed · a recorder, not a gate · `ReadingState` gained its third member, `READ_BUT_UNSCORED` (`502e166`) |
| engine assembly | ✅ landed · four parts → Document Evidence Object |
| `pipeline` | ✅ landed · bytes → Document Evidence Object, end to end · an unreadable document now **crosses as an artifact**, never as an exception (`1e65b91`) |
| `classification` | ⚠️ landed · **zero thresholds** — a heading is decided by position, not by a score. **Wired to nothing** (F-018) |
| `config` | ⚠️ landed · 16 parameters, no defaults, fails fast. **Wired to nothing** (F-018) — so the fail-fast behaviour never fires on the real path |
| `measurement` | ⚠️ landed · carries `instrument` + `region`, the raw signal's only home. **Wired to nothing** (F-018) — so that home stays empty |
| benchmarks | ⏸ partial. **No performance number for Engine 1 exists, so no performance claim is provable** |

**Test state at HEAD `e921c3c` — LOCAL ONLY, NOT AUTHORITATIVE (Law 44):**

```
pytest tests/                       cannot collect     F-024
pytest tests/ minus that one file   17 failed · 2565 passed · 11 skipped · 23 errors
                                    39 of the 40 are one signature change   F-025
                                    1 is a correct test failing on a real defect  F-019
```

**What integration and red-teaming found, and what closed.** Every one is recorded in
`KNOWN_FAILURES.md` rather than patched around:

| | |
|---|---|
| **F-012** the pipeline was not a pipe | ✅ **closed** — `412eed6`, then `6b32425`/`41b23e6`/`d29985a` |
| **F-013** no per-field confidence possible | 🔄 **half** — a named, scored field now exists for the OCR path |
| **F-019** Engine 1 emits a confident, empty, valid lie | 🔄 **three of four mechanisms fixed.** The text-layer half is BLOCKED on the owner |
| **F-011** `cleaner.decode` cannot decode a PDF | ⬜ open — worked around in `pipeline.py`, not fixed at source |
| **F-017** `cleaner` collapses every document to a raster | 🔒 open — the root cause of F-011, and a §M question |
| **F-018** three modules wired to nothing | ⬜ open, **unchanged**, re-measured at `e921c3c` |

**Dependencies.** The locked architecture (`a47271d`) and the P2 artifact schemas. **Not
P1** — the blueprint makes Engine 1 depend on the Application Layer and the schemas, both
built. P1 gates the *measurement* of Engine 1, never its construction.

**Blockers.**
- **F-024 / F-025** the repository does not build, and 39 tests are red on one cause.
  Nothing else about Engine 1 is provable until these clear
- **F-001** PyMuPDF is AGPL-3.0 and this is a hosted commercial product — owner decision
- **T-048** `Provenance.confidence` has no absent-measurement state, so the MVP's primary
  input still cannot carry a per-field confidence — **owner, §M**
- **T-049** `ENGINE_1_INPUT_ENGINE_RULES.md:352` says *"exactly four"* sub-engines and
  Engine 1 ships nine modules. That document **is** on the precedence ladder, so unlike
  §G9.5 this one cannot be settled by precedence — **owner**
- The 16 confidence parameters are all UNSET, which blocks *calibration* only

**Completion criteria — restated against what is now true.**

1. The repository builds. `pytest tests/` collects and is green.
2. Every sub-engine tested and green **on CI**, on a **pushed** commit (Law 44). Local is
   exploration, not evidence.
3. A real document runs end to end **as an asserted test**, not by hand —
   `tests/integration/test_engine1_end_to_end.py` exists and is **not yet green**.
4. **Every value that crosses the Input → Understanding boundary carries its source, its
   confidence and its uncertainty**, including on the text-layer path. This is the criterion
   F-019 is failing, and it is the one that matters: `ENGINE_1_INPUT_ENGINE_RULES.md:245`
   — *"a value carried without all three is not evidence and must not be emitted."*
5. Every module in `engines/input_engine/` is either in the pipeline or established as not
   belonging to it (F-018).
6. A measured performance number exists. There is none today.
7. **No accuracy claim until P1 produces a ceiling.**

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
