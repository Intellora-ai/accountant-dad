# TODO.md

The living engineering backlog. Every task carries an ID, priority, status,
dependency and phase. **Completed tasks move to the Completed section — history is
never deleted.**

Last updated: **2026-08-06**

Priority: **P0** blocks everything · **P1** on the critical path · **P2** real work,
not blocking · **P3** recorded so it is not lost.

Status: ⬜ not started · 🔄 in progress · ⏸ paused · 🔒 blocked · ✅ done

**Measurement state.** HEAD is `addcae3`, **pushed**; CI is judging it now. Every gate value at HEAD is **UNMEASURED**; the last CI numbers belong to
`7e0efe2` / `f31e3cd` and are **EXPIRED** because `src/` moved `+2591 / −300` lines after
them (Law 56).

---

## P0 — needs the owner, nothing else unblocks it

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| T-001 | **PyMuPDF licence decision** — buy the Artifex commercial licence, or amend the locked stack (§M). AGPL §13 is triggered by a hosted accounting product. See F-001. | 🔒 | owner | Engine 1 |
| ~~T-002~~ | ~~**Amendment 4** — three locked docs specify confidence gating that A7 forbids.~~ **Done 2026-08-06 as Amendment 8, approved by the owner. FIVE documents, not three** — `ACCOUNTING_DEFINITIONS.md` §6 and `APPLICATION_LAYER.md` were found by sweeping every markdown file rather than trusting the list. See F-004, closed. | ✅ | — | → Completed |
| ~~T-003~~ | ~~Delete `ENGINE_1_CONFIDENCE_PARAMETERS 2.md`~~ | ✅ | — | → Completed |
| T-004 | **Golden-set size decision** — 16 planned vs ~100 stated. Re-derive first (T-020), then decide. See F-006. | 🔒 | T-020, owner | P1 |
| T-005 | **The 16 confidence parameters have no values.** All UNSET by design. Blocks calibration, blocks nothing else. | 🔒 | ground truth | Engine 1 |
| ~~T-048~~ | ~~**`Provenance.confidence` needs an absent-measurement state**~~ **Done 2026-08-06 as Amendment 7, approved by the owner — and wider than asked: FOUR states, `MEASURED · NOT_MEASURED · NOT_APPLICABLE · FAILED`, each carrying a required reason. Table cells wired too. F-019 closed.** | ✅ | — | → Completed |
| T-052 | **Close O11 and O12 in `pipeline.py`** — remove the `is not None` filter in `parsed_fields` (returns sole ownership of `confidence_scores` to the `confidence` sub-engine), and replace two `isinstance(x, UnmeasuredType)` call sites with `measurement_state(x)` so a NOT_APPLICABLE or FAILED value is never classified as measured. Neither is reachable today; both are traps for the day one becomes reachable. | ⬜ | pipeline workstream | Engine 1 |
| T-053 | **NOT_APPLICABLE and FAILED have limited live producers** (O13). FAILED fires only on a capture-fidelity mismatch; NOT_APPLICABLE only when `parser` is given an expected-field list, and it is given none. Unblocked by `reader` reporting a per-region recognition failure as a STATE rather than raising for the whole reading. **Stated, not manufactured** — inventing a producer is the fabrication the states exist to refuse. | ⬜ | reader workstream | Engine 1 |
| T-054 | **Per-cell provenance reaches the artifact through `detected_fields`, not `DetectedTable`** (O14), which carries one `Provenance` per table. A schema limit, not a choice. Needs the owner: change the schema, or confirm the `detected_fields` route is the intended one and close it as designed. | 🔒 | owner | Engine 1 |
| ~~T-049~~ | ~~**`ENGINE_1_INPUT_ENGINE_RULES.md:353` says "exactly four sub-engines"; Engine 1 ships nine modules.**~~ **Resolved 2026-08-06 by delegated engineering authority, not by the owner deciding.** The clause is correct and so is the code: **module ≠ sub-engine.** A sub-engine is a component that produces one of the four parts the parent combines (`:399`), and the count sits in a document that forbids code existing at all (`:8`), so it never counted files. Four sub-engines · `assembly`+`pipeline` are the parent engine's own machinery (`:384`, *"No new assembler sub-engine is created"*) · `config`, `measurement`, `classification` are facilities producing no part of the artifact. **No code changed.** Membership test at §9A, Amendment 5, four guard tests. See F-010. | ✅ | — | → Completed |

---

## P1 — critical path

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| ~~T-010~~ | ~~`confidence_report` tests~~ | ✅ | — | → Completed |
| ~~T-011~~ | ~~`config` + `measurement` tests~~ | ✅ | — | → Completed |
| ~~T-012~~ | ~~`instrument` + `region` on every signal~~ | ✅ | — | → Completed · F-005 closed |
| ~~T-050~~ | ~~THE REPOSITORY DOES NOT BUILD~~ — **STALE, never true at a landed commit.** Measured at `e921c3c`, which was a mid-cherry-pick tree where `conformance.py` still held conflict markers. Re-verified at `addcae3`: `Exclusion` is present, `conformance` and `conformance_registry` both import, **3264 tests collect**. See F-024. | ✅ | — | conformance |
| T-051 | **24 red tests, one cause** — down from 39. `pipeline.run` and `parser.parse` changed shape; `test_input_engine_pipeline_redteam.py` predates both, so its spy carries the old signature and six of its tests still expect a raise where an unreadable document now crosses as an artifact. Measured at `addcae3`: **3229 passed · 24 failed**, LOCAL ONLY — NOT AUTHORITATIVE. Owned by the F-019 agent, since it is the same change set. See F-025. | 🔄 | — | Engine 1 |
| T-052 | **Push the branch and let CI judge it** — **done.** `f31e3cd..addcae3` pushed, 25 commits, `src/` +2973/−363. The cheap gates judge the real tree while the 24 red tests are fixed in parallel; a red suite makes `unit tests` red, which is honest and is evidence. Merging red is what is forbidden (Law 55), not measuring red. | ✅ | — | CI |
| ~~T-013~~ | ~~CI must install Engine 1's dependencies~~ | ✅ | — | → Completed |
| T-014 | **Promote `mutation` to a required check.** It passed on correct code — 95.3% @ commit `7e0efe2`, floor 93 — but that number is **EXPIRED** (source moved) and the current score is **UNMEASURED**. Two steps remain: re-measure at a pushed HEAD, and prove it FAILS on deliberately broken code. Then add **only** that gate. See F-008. | 🔒 | T-052, owner approval for the ruleset change | CI |
| T-015 | **Engine 1 pipeline runner** — built, then made an actual pipe. `412eed6` rewired `reader`/`parser` onto `cleaned.artifact.payload`; `6b32425`/`41b23e6`/`d29985a` built the `reader → parser` half. F-012 closed. | ✅ | — | Engine 1 |
| T-016 | **`classification` sub-engine** — built. Decides on tuple shape, not on a number: zero thresholds anywhere in the module, guarded by an AST test that scans its own source. | ✅ | — | Engine 1 |
| T-047 | **Prove Engine 1 end to end as a TEST.** `tests/integration/test_engine1_end_to_end.py` now exists — 893 lines. **Not done:** one of its tests is RED against a real defect (F-019's text-layer half, blocked on T-048), so the end-to-end claim is not yet provable. Do not ease the test (Law 4). | 🔄 | T-048 | Engine 1 |
| T-053 | **Wire `classification`, `config` and `measurement` into the pipeline, or establish that they belong to the Application Layer.** Re-measured at `e921c3c`: still **zero consumers** in `src/`. `pipeline.py` gained 688 lines after `7e0efe2` and gained none of the three. F-018, unchanged since it was raised. | ⬜ | T-049 | Engine 1 |

---

## P2 — real work, not blocking

| ID | Task | Status | Depends on | Phase |
|---|---|---|---|---|
| T-020 | **Re-derive the calibration sample size** given A5 removed the document scalar. Must account for within-document clustering — the honest answer may still be "16 is not enough". | ⏸ | — | P1 |
| T-021 | **Benchmark harness for Engine 1** — partial work exists in a worktree. No performance number for Engine 1 exists, so no performance claim is provable. | ⏸ | — | Engine 1 |
| T-022 | **Red-team `cleaner.py`** — done. Four content-destroying defects found and fixed as **one class**: a destructive step or its audit consulted the rule that caused the damage. `tests/unit/test_input_engine_cleaner_redteam.py`, 1053 lines, 22 tests, all green. See D1–D4 and D-013. | ✅ | — | → Completed |
| T-023 | **Red-team the citation verifier** — six layers, hunt the case that still slips. Agent killed mid-run. | ⏸ | — | Brain |
| T-024 | **Full citation sweep** — every claim, every layer, and re-measure the per-parser resolution rates against ICAI 207/207, Act 397/397, Rules 197/202. A moved rate is a regression. | ⏸ | — | Brain |
| ~~T-025~~ | ~~Kill the 9 surviving mutants~~ — **superseded by T-045** | ✅ | — | → Completed |
| ~~T-045~~ | ~~Mutation gate back above its floor~~ — **CI answered.** 95.3% @ commit `7e0efe2`, floor 93. Now EXPIRED; re-measurement is T-014. | ✅ | — | → Completed |
| T-046 | **74 reader mutants are unreachable without PaddleOCR**, and 23 more across four modules are provably equivalent (measured, not assumed). The 74 close with F-009; the 23 never close and should not be chased. **Note:** F-009's skip guard could never be satisfied in *any* environment, so the 74 were unreachable for a second, different reason as well. | 🔒 | F-009 | testing |
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
| T-043 | **Stale agent worktrees** in `.claude/worktrees/` — **74 directories as of 2026-08-06**, up from 15; `git worktree list` reports 7 as `locked`. One (`agent-ad81016cdd833789f`) holds **unmerged `.github/` conflicts** from an earlier session. Do not touch any without reading it first (D-006: state on disk is state). | ⬜ | — | housekeeping |
| T-054 | **`cleaner.py` cites `KNOWN_FAILURES.md` D2, D3 and D4** at `:212`, `:446`, `:709`, `:1227` — IDs that did not exist in that file until 2026-08-06. Now recorded under the IDs the source uses. Decide whether to renumber them to the `F-nnn` convention (a code change) or keep the source's prefix (no code change, one inconsistent prefix). | ⬜ | — | quality |
| T-055 | **A CI `timeout-minutes` has no guarding test.** F-014 closed on a config value nothing asserts; lowering it back to 100 produces no signal until a run is cancelled hours later. Writing the guard is a `.github` change and needs the owner's approval for that specific change. | 🔒 | owner | CI |
| T-044 | **Dependency + licence audit of the full transitive tree.** F-001 and F-002 were both found by hand; nobody has swept the whole tree. | ⏸ | — | quality |
| T-056 | **Conformance predicates are identified by a line number, so a locked document is append-only after its last cited line.** Adding a paragraph to `ENGINE_1_INPUT_ENGINE_RULES.md` above line 626 reddens two drift tests that have nothing to do with the paragraph, and renumbering strands six prose citations across `src/` and four test files. Identify a prohibition by its **quoted sentence** and let the drift test *recompute* the line rather than assert it — the quote is already stored on every predicate. Touches `conformance_registry.py` and `test_conformance_registry.py`. See F-027. **Second, smaller defect in the same tooling:** `_PROHIBITION_MARKER` matches the substring `must never`, so ordinary prose containing *"must nevertheless"* is flagged as an uncovered prohibition clause. Hit once on 2026-08-06 and worked around by rewording. A word boundary after `never` fixes it. | ⬜ | — | quality |

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
| T-013 | **CI installs Engine 1's dependencies**, and the OCR stack runs in an isolated interpreter of its own. | `5066576` | `tools/ci/run_ocr_tests.sh` |
| T-025 | **Superseded by T-045** and closed with it. That earlier score was measured on a far smaller tree; all of Engine 1 landed after it. | — | see T-045 |
| T-045 | **Mutation gate back above its floor.** 114 survivors killed across five test files, every one an assertion made stricter or a case added — no file excluded, no assertion weakened, no floor touched. CI then answered on `7e0efe2`: **95.3%**, floor 93 — killed 2324, survived 115, 919 not scoreable. **Now EXPIRED** (source moved `+2591 / −300`); re-measurement is T-014. | `7e0efe2` | GitHub Actions run 31041552213, job 92426852650 · 3h 21m 01s |
| T-022 | **`cleaner` red-teamed.** Four content-destruction defects (D1–D4) found and fixed as one class. The D1 test holds both halves — the damage must not recur **and** the figure that would report it must stay able to — because half one alone would pass against a retention hardwired to 1.0. One surviving mutation is recorded in the docstring rather than papered over. | `1e0df65`, `590c6bb` | `test_input_engine_cleaner_redteam.py` — 1053 lines, 22 tests green |
| T-108 | **F-014 closed** — mutation cap raised to 500 minutes on the owner's number, and a run has since finished. | `66ab8cd` | run completed in 3h 21m 01s @ commit `7e0efe2` |
| T-109 | **F-020 closed** — the wheel now declares every module-scope import, each pinned to the value already in `requirements-engine1.txt`. One approved `.github` line resolves the install closure from the wheel's own metadata. | `839645a` | `tests/unit/test_declared_dependencies.py` — 337 lines, derives the set from the AST |
| T-110 | **F-021 closed** — the build-freeze guard reads code by AST instead of matching filenames, so `gst_rates.py` full of tax logic no longer passes on its name. The honest limit is written into the fix. | — | `test_package.py` +408 lines · three named AST tests |
| T-111 | **F-009's skip guard fixed** — `find_spec` was called on a *distribution* name, so the 11 OCR tests skipped in **every** environment and had never run anywhere. Whether they now pass is UNMEASURED. | `202bed4` | `test_input_engine_reader.py:80,89` · `tools/ci/run_ocr_tests.sh:318` |
| T-112 | **F-023's runtime-version guard built** — asserts what the imported library reports about itself, not what packaging metadata claims, so the `5.0.0.93` vs `4.10.0` divergence now fails a test. The unpinned-tree half stays open. | `5066576` | `test_runtime_library_versions.py` — 434 lines · `tools/ci/assert_imports_match_pins.sh` |
| T-113 | **Law 56 written and enforced** — commit-bound measurements, seven layers, owner-approved 2026-08-06. | `6a5dbb3`, `c1eb9be` | `CLAUDE.md` §C.56 · `ENGINEERING_RULES.md` · `PreToolUse` hook · `LESSONS.md` L-011 |
| T-114 | **Engine 1 emits an artifact for an unreadable document** instead of raising, so the Application Layer can route a bad scan differently from an outage. A missing *tool* still raises — that is not a bad document. | `1e65b91`, `b3c1b51` | `test_a_document_engine_1_cannot_read_stops_the_run_loudly`, rewritten stricter: four claims where there was one |
