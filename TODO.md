# TODO.md

The living engineering backlog. Every task carries an ID, priority, status,
dependency and phase. **Completed tasks move to the Completed section — history is
never deleted.**

Last updated: **2026-08-05**

Priority: **P0** blocks everything · **P1** on the critical path · **P2** real work,
not blocking · **P3** recorded so it is not lost.

Status: ⬜ not started · 🔄 in progress · ⏸ paused · 🔒 blocked · ✅ done

---

## P0 — needs the owner, nothing else unblocks it

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| T-001 | **PyMuPDF licence decision** — buy the Artifex commercial licence, or amend the locked stack (§M). AGPL §13 is triggered by a hosted accounting product. See F-001. | 🔒 | owner | Engine 1 |
| T-002 | **Amendment 4** — three locked docs specify confidence gating that A7 forbids. Draft exists in intent; needs the owner's approval and date. See F-004. | 🔒 | owner | architecture |
| ~~T-003~~ | ~~Delete `ENGINE_1_CONFIDENCE_PARAMETERS 2.md`~~ | ✅ | — | → Completed |
| T-004 | **Golden-set size decision** — 16 planned vs ~100 stated. Re-derive first (T-020), then decide. See F-006. | 🔒 | T-020, owner | P1 |
| T-005 | **The 16 confidence parameters have no values.** All UNSET by design. Blocks calibration, blocks nothing else. | 🔒 | ground truth | Engine 1 |

---

## P1 — critical path

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| ~~T-010~~ | ~~`confidence_report` tests~~ | ✅ | — | → Completed |
| ~~T-011~~ | ~~`config` + `measurement` tests~~ | ✅ | — | → Completed |
| ~~T-012~~ | ~~`instrument` + `region` on every signal~~ | ✅ | — | → Completed · F-005 closed |
| T-013 | **CI must install Engine 1's dependencies.** `requirements-engine1.txt` now pins opencv, numpy, pymupdf, pillow, paddleocr, paddlepaddle. Four jobs install it; `lint` deliberately does not. Verify the new pins do not break any job. | ⬜ | push | CI |
| T-014 | **Promote `mutation` to a required check.** It passed on correct code at 99.3%. The lifecycle needs one more step: prove it FAILS on deliberately broken code. Then add **only** that gate. See F-008. | ⬜ | T-013, owner approval for the ruleset change | CI |
| T-015 | **Engine 1 pipeline runner** — nothing has ever run a real document through all stages together. Agent building it. | 🔄 | — | Engine 1 |
| T-016 | **`classification` sub-engine** — document-type detection. On `ENGINE_1_AUTHORIZED` but never written. Agent building it. | 🔄 | — | Engine 1 |

---

## P2 — real work, not blocking

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| T-020 | **Re-derive the calibration sample size** given A5 removed the document scalar. Must account for within-document clustering — the honest answer may still be "16 is not enough". | ⏸ | — | P1 |
| T-021 | **Benchmark harness for Engine 1** — partial work exists in a worktree. No performance number for Engine 1 exists, so no performance claim is provable. | ⏸ | — | Engine 1 |
| T-022 | **Red-team `cleaner.py`** — hunt information-destroying crops and denoise. Information a cleaner destroys can never be recovered downstream, and nothing later can know it is missing. Agent killed mid-run; probe scripts survive in the scratchpad. | ⏸ | — | Engine 1 |
| T-023 | **Red-team the citation verifier** — six layers, hunt the case that still slips. Agent killed mid-run. | ⏸ | — | Brain |
| T-024 | **Full citation sweep** — every claim, every layer, and re-measure the per-parser resolution rates against ICAI 207/207, Act 397/397, Rules 197/202. A moved rate is a regression. | ⏸ | — | Brain |
| T-025 | **Kill the 9 surviving mutants.** Score is 99.3% against a floor of 93, so this is not blocking — but each survivor is a change to production code no test noticed. | ⬜ | — | testing |
| T-026 | **Audit the 23 locked documents for contradictions** — ownership collisions, artifacts with two names, paths `DATA_FLOW.md` does not define, stale counts. Agent killed mid-run. | ⏸ | — | architecture |
| T-027 | **Suppression audit follow-through** — the report exists (22.6K, in the scratchpad). Count is 124 against a 128 baseline. Act on the STALE and REMOVABLE entries it names. | ⬜ | — | quality |
| T-028 | **Coverage gap analysis** — branch coverage, and specifically every uncovered FAILURE path. An uncovered `except` is a path nobody has proven works, and it is the one that runs during an incident. | ⏸ | — | testing |
| T-029 | **Is `input_engine/stub.py` now duplicated logic?** 175 lines written when Engine 1 was frozen; five real modules now exist. Law 14 forbids duplicated logic. Does any gate pass *because* of it? | ⏸ | — | Engine 1 |
| T-030 | **Audit the 19 adversarial attacks** — which are RUNNABLE NOW against code that exists, versus genuinely blocked on P1/engines/Tally. If even one is runnable, the placeholder's blocker text is broader than the truth. | ⏸ | — | testing |

---

## P3 — recorded so it is not lost

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| T-040 | **GSTIN check-digit algorithm** — no authoritative government publication of it was found. An honest gap was recorded rather than a third-party page. Revisit. | ⬜ | — | Brain |
| T-041 | **Brain expansion** — reverse charge, invoice field validations, blocked credits §17(5), ITC rules. All four agents were killed mid-write; several had already verified citations. | ⏸ | — | Brain |
| T-042 | **`merge gate` promotion** — the only job that polls every other gate. Goes required LAST, when it can actually pass. Eight placeholders `exit 1` by design. | 🔒 | every other gate | CI |
| T-043 | **15 stale agent worktrees** in `.claude/worktrees/`. One (`agent-ad81016cdd833789f`) holds **unmerged `.github/` conflicts** from an earlier session — do not touch without reading it first. | ⬜ | — | housekeeping |
| T-044 | **Dependency + licence audit of the full transitive tree.** F-001 and F-002 were both found by hand; nobody has swept the whole tree. | ⏸ | — | quality |

---

## Completed

| ID | Task | Landed | Evidence |
|---|---|---|---|
| T-100 | **Mutation gate finishes and passes.** It was never failing on score — it was cancelled at 10m17s with 596 mutants unscored. Cap raised to 100 min on the owner's number. | `d85861c` | CI 24m14s · **99.3%**, floor 93 · killed 1364, survived 9 |
| T-101 | **`cleaner` sub-engine** — deskew residual 0.0017 at 32° after reordering the pipeline so CLAHE runs before rotation. | earlier | CI green |
| T-102 | **`reader`, `parser`, `assembly`** — 1,495 lines of source, 1,906 of tests, recovered from killed agents' worktrees and finished. | `3b906b6` | local 2068 passed / 14 skipped / 0 failed; CI pending |
| T-103 | **The import that made Engine 1 unimportable** — `reader.py` resolved PaddleOCR at module scope, so every gate that merely imported the package died at collection. | `3b906b6` | collection now succeeds |
| T-104 | **Confidence specification** — 666 lines. The owner's A1–A8 written down, with the no-scalar result proved from a named theorem rather than asserted. | `30f54af` | — |
| T-105 | **Seven atomic concepts** — GST valuation and place of supply, every citation verified against six independent layers. | `30f54af` | 41/41 documents present |
| T-106 | **Engine 1 architecture document** (§G). | `30f54af` | — |
| T-003 | **Deleted the stale `ENGINE_1_CONFIDENCE_PARAMETERS 2.md`.** Both safety checks passed first: nothing depended on it, and `diff` proved its *only* unique line was the inverted `worst_k` row itself. | `7279ea6` | F-003 closed |
| T-010 | **`confidence_report` + 27 tests.** Found a capture-fidelity score that was computed and then discarded, never reaching the report. Red-teamed — and the attack exposed a defect in the no-threshold test itself, which missed constants nested inside `Decimal("...")`. | `a5979ab` | local green |
| T-011 | **`config` (71 tests) + `measurement` (43).** `config` audited clean, zero defects. `measurement` had a loud-failure path that silently lost its line number, and three UNUSED `type: ignore`s that `warn_unused_ignores` makes hard errors. | `47c4063` | suppressions 124 → 124 |
| T-012 | **`instrument` + `region` on every `NamedSignal`.** The raw signal had no home anywhere in the system before this. | `47c4063` | F-005 closed |
| T-107 | **Pinned the parsing stack** — docling, transformers, torch, torchvision, timm, pypdfium2. `timm` was undeclared and its absence was visible to exactly ONE test out of 51. | `fd929c1` | parser 51/51 |
