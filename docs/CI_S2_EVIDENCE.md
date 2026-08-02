# CI Merge Gate — S2 Proof Suite Evidence

> Every protection below was **attacked, not assumed**. A protection is listed as proven
> only because the corresponding attack was executed against a real pull request or run
> and the system blocked it. Executed 2026-08-03 against `main` @ `687bb85`.
>
> Method: one throwaway branch per case, cut from `main`, deliberately mutated, evidence
> captured from the live GitHub API and workflow logs, then closed and deleted.
> **No S2 branch was ever merged. `main` was never touched.**

---

## The proof table

| # | Protection | Attack performed | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|---|
| 1 | Green path — the gate can pass | All 22 gates set to `exit 0` (PR #5) | merge gate GREEN | `all 22 gates succeeded` → `completed/success` | **PASS** | [run 30763821273](https://github.com/Intellora-ai/accountant-dad/actions/runs/30763821273) |
| 2 | A failed gate blocks | 21 gates pass, `semgrep` forced `exit 1` (PR #7) | merge gate RED, names the gate | `BLOCKED — FAILURE semgrep` | **PASS** | [run 30763986894](https://github.com/Intellora-ai/accountant-dad/actions/runs/30763986894) |
| 3 | A skipped gate blocks | Job added with `if: false` — GitHub gives it conclusion `skipped`, which **natively satisfies a required check** | merge gate rejects it anyway | `BLOCKED — SKIPPED s2 skipped gate` | **PASS** | [run 30764178716](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764178716) |
| 4 | A cancelled gate blocks | Sleeping job cancelled mid-run via API | merge gate RED | `BLOCKED — CANCELLED s2 cancelme gate` | **PASS** | [run 30764360615](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764360615) |
| 5 | A timed-out gate blocks | Job with `timeout-minutes: 1` sleeping 300s | merge gate RED | `BLOCKED — CANCELLED s2 timeout gate` — **finding: GitHub reports a timeout kill as `cancelled`, not `timed_out`**; both are rejected | **PASS** | [run 30764243512](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764243512) |
| 6 | An absent check blocks | Dispatch-only workflow declares a gate that never runs; poll timeout lowered to 2 min on the branch | merge gate times out RED | `BLOCKED — timed out after 2.0 minutes`, waiting on `s2 ghost gate` | **PASS** | [run 30764439168](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764439168) |
| 7 | **Gate-removal attack** | `lint` job deleted entirely; **every remaining gate green** (PR #6) | `DECLARED ⊇ EXPECTED` fails | `gates on base branch : 22 / gates on this ref : 21 / BLOCKED — REMOVED lint` | **PASS** | [run 30763879749](https://github.com/Intellora-ai/accountant-dad/actions/runs/30763879749) |
| 8 | A renamed gate blocks | `lint` renamed to `lint-v2` | detected as removal of the original | `ADDED lint-v2` + `BLOCKED — REMOVED lint` | **PASS** | [run 30764056740](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764056740) |
| 9 | Auto-discovery of new gates | A 23rd gate added, nothing else changed | expected set grows, all pass | `ADDED s2 extra gate` → `all 23 gates succeeded` | **PASS** | [run 30764093048](https://github.com/Intellora-ai/accountant-dad/actions/runs/30764093048) |
| 10 | GitHub actually blocks the merge | `merge gate` temporarily required (pinned `integration_id: 15368`); PR #13 opened with a red merge gate | merge refused | `mergeStateStatus: BLOCKED` · merge attempt: *"the base branch policy prohibits the merge"* | **PASS** | PR #13 |
| 11 | **Spoof attack** | Fake commit status `context: "merge gate", state: success` posted with a user token against PR #13's head SHA | still blocked | status accepted by the API, **PR stayed BLOCKED**, merge still refused — the `integration_id` pin ignores commit statuses | **PASS** | PR #13 |

Cases 2–9 each ran with **all other gates green**, so every failure is attributable to
exactly the injected fault and nothing else.

---

## Findings recorded along the way

1. **A timeout kill surfaces as `cancelled`.** The check-run conclusion for a job exceeding
   `timeout-minutes` is `cancelled`, not `timed_out`. The merge gate rejects both, so the
   protection holds either way — recorded so nobody later greps logs for `TIMED_OUT` and
   concludes timeouts never happened.
2. **A rename is a removal.** The set comparison decomposes `rename` into `ADDED` + `REMOVED`,
   and the `REMOVED` side blocks. There is no rename path around the ratchet.
3. **The spoof vector is real but closed.** The Commit Status API happily accepted a forged
   `merge gate` success from a user token. Only the `integration_id: 15368` pin on the
   required check made it inert. **Any future required check must carry the pin.**

## Deliberately not tested

- **`--admin` bypass of the ruleset.** The bypass list is empty, so per GitHub's ruleset
  semantics there is no administrator exemption — but proving it requires attempting an
  admin merge of a throwaway PR into `main`, and a wrong assumption there *pollutes `main`*.
  Left untested rather than risked.

## State after the suite (everything restored)

| | |
|---|---|
| Ruleset 20249495 | `deletion` · `non_fast_forward` · `pull_request` — required checks **none**, bypass list **empty** |
| Required status checks | **0** — per the approved lifecycle, a gate becomes required only after it is implemented and proven |
| S2 branches | all closed and deleted, none merged |
| `main` | untouched throughout — still `687bb85` |
| Spoofed status | exists only on the deleted probe branch's orphaned commit; unreachable |

## What this suite does NOT claim

The 19 gate placeholders still `exit 1` — they are **scaffolding, proven wired, not
implemented**. This document proves the *aggregation and enforcement machinery*; it makes
no claim that any real quality check (lint, typecheck, tests…) exists yet. Implementing
those requires product code, which remains behind the build freeze.
