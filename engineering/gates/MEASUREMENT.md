# GATE · MEASUREMENT

**Fires when:** producing a number, quoting a number, or claiming an improvement.
Every metric in `ROADMAP.md` · `PROGRESS.md` · `DECISION_LOG.md` · `KNOWN_FAILURES.md`
· `STATE.md` · `BLOCKERS.md` · reports · PR descriptions · chat.

**A number without its commit is an opinion. A number tied to the wrong commit is
false.** Only a measurement tied to the exact commit that produced it is evidence.

---

## THE FOUR STATES — every claim is exactly one

```
MEASURED    an observation was made; the command that produced it is quoted
DERIVED     follows from a measurement by stated arithmetic
INFERRED    plausible, NOT observed — and labelled as such
UNKNOWN     the honest answer, and always an acceptable one
```

**UNKNOWN beats wrong.** Never invent continuity between commits. Never write the
previous number because the current one is not in yet.

## THE FORMAT — value · commit · source · status

```
Mutation : 93.42%   Commit: 7e0efe2   Source: GitHub Actions   Status: VERIFIED
Coverage : 97.54%   Commit: 7e0efe2   Source: GitHub Actions   Status: VERIFIED
```

```
OK    Mutation: 95.3% @ commit 7e0efe2
NO    Mutation: 95.3%
```

## LIFETIME — a measurement expires the moment source changes

A measurement is valid **only** for its commit. The instant any source changes after it:

| | |
|---|---|
| reused | **never** |
| quoted as current | **never** |
| used for a decision | **never** |

The only two valid responses are **re-measure** or **UNMEASURED**.

**Say it before you are asked.** When code lands after a measurement, state it in the
same message:

> Previous measurement expired because source changed after commit `<hash>`.

## AUTHORITY — Law 44

Only **GitHub Actions** is authoritative. A local run may be reported **only** when
labelled `LOCAL ONLY — NOT AUTHORITATIVE`, and never as a substitute for CI.

*"Works on my machine"* is not verification. *"Should be faster"* is banned exactly as
*"should work"* is.

---

## BEFORE REPORTING ANY METRIC — run this

1. Which commit produced it?
2. Does that commit match the current codebase?
3. If HEAD differs → **EXPIRED**.
4. Re-measure, or report **UNMEASURED**.

## NO SCORE WITHOUT A COMPLETE DENOMINATOR

A ratio computed over an unknown population is not a score. State what was excluded
and why, every time:

```
killed / (killed + survived)      hides everything that crashed or timed out
```

Measured 2026-08-06: **919 of 3358 mutants — 27.4% — sat outside the denominator**,
and the reported score never said so. A silently shrinking denominator makes a gate
look healthier as it degrades.

**If a bound was applied — top-N, sampling, no-retry, a cap — say what was dropped.**
Silent truncation reads as "covered everything" when it did not.

## THE COST OF A MEASUREMENT IS PART OF THE PLAN

Re-measuring the mutation gate costs **~3.4 hours**. So expensive gates — mutation,
the coverage ratchet, benchmarks — are **batched to the end of a change set** and paid
once. Cheap gates — lint, typecheck, tests — re-run freely. **That sequencing is
decided before the changes land, not after.**

## FIND THE DATA, DO NOT MANUFACTURE IT

Before building any sensor, ask where this is already recorded: logs, timestamps, what
people corrected, what a counterparty already holds, decisions already made with
consequences attached.

The strongest checks are **quantities that must be equal** — debits and credits, mass
in and mass out, lines and total. **A conservation law needs no expert and no labels.**
It holds or it does not.

If something genuinely cannot be observed, that is a design defect. Rebuild it so it
emits.

---

## CHECKLIST

- [ ] Every number carries value · commit · source · status
- [ ] Every number carries its unit
- [ ] Nothing quoted from a commit older than HEAD without being marked EXPIRED
- [ ] Denominator stated; exclusions named
- [ ] Local results labelled `LOCAL ONLY — NOT AUTHORITATIVE`
- [ ] Improvement claims carry before AND after
- [ ] Nothing fabricated — not a metric, not a log, not a threshold (Law 24)
- [ ] Expensive gates batched, and the sequencing decided in advance
